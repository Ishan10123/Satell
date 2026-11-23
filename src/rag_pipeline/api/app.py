from pathlib import Path
import json
import logging
import uuid
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from ..generation import GenerationError
from ..generation.evaluation_artifact import EvaluationArtifactStore
from ..embeddings import EmbeddingError
from ..authorization.local_academic_demo import (DemoAuthorizationError, validate_demo_registry,
    validate_local_demo_policy, validate_source_registry)
from ..ingestion.approval import load_approval_registry
from ..ingestion.approval_workflow import validate_record
from ..ingestion.parsing_job import document_id_for
from ..retrieval import ContextBudgetError, RetrievalRequestError
from ..security import ApiRateLimiter, validate_api_token
from ..storage import AccessScope, VectorStoreError
from ..storage.index_manifest import validate_index_manifest

MAX_QUERY_CHARACTERS = 5000
# Covers up to 5,000 astral code points represented as JSON surrogate escapes,
# plus framing, while keeping the request body explicitly bounded.
MAX_QUERY_BODY_BYTES = 64 * 1024
LOCAL_DEMO_ABSTENTION = "I cannot answer from the local academic demo sources available."
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARACTERS)
    top_k: int = Field(default=8, ge=1, le=20)
    response_style: Literal["natural", "concise", "detailed"] = "natural"


class QueryResponse(BaseModel):
    answer: str
    citations: tuple[dict[str, object], ...]
    request_id: str
    retrieval_mode: str = "dense"
    timings_ms: dict[str, float] = Field(default_factory=dict)
    verification_status: Literal["verified", "partially_verified", "abstained", "failed", "not_reported"] = "not_reported"
    diagnostics: dict[str, object] = Field(default_factory=dict)
    synthetic: bool = False


def create_app(
    service,
    *,
    api_token: str,
    tenant_id: str,
    principal_id: str,
    approval_registry_path: str | Path,
    requests_per_minute: int = 30,
    max_body_bytes: int = MAX_QUERY_BODY_BYTES,
    index_validator=None,
    project_root: str | Path | None = None,
    document_approval_registry_path: str | Path | None = None,
    authorization_mode: str = "production",
    local_academic_demo_enabled: bool = False,
    local_academic_demo_registry_path: str | Path | None = None,
    local_academic_demo_source_registry_path: str | Path | None = None,
    local_academic_demo_policy_path: str | Path | None = None,
    evaluation_artifact_store: EvaluationArtifactStore | None = None,
    evaluation_model_configuration: dict[str, object] | None = None,
) -> FastAPI:
    if len(api_token) < 32:
        raise ValueError("API bearer token must contain at least 32 characters.")
    if not tenant_id or not principal_id:
        raise ValueError("Server-side tenant and principal IDs are required.")
    if max_body_bytes < 256:
        raise ValueError("Maximum request body size is too small.")
    registry_path = Path(approval_registry_path).resolve()
    document_registry_path = (Path(document_approval_registry_path).resolve() if document_approval_registry_path
                              else registry_path.parent / "document_approvals.json")
    approval_project_root = Path(project_root).resolve() if project_root else registry_path.parent
    demo_registry_path = (Path(local_academic_demo_registry_path).resolve()
                          if local_academic_demo_registry_path else
                          approval_project_root / "knowledge_base" / "metadata" / "local_academic_demo_document_authorizations_phase1_v3.json")
    demo_source_registry_path = (Path(local_academic_demo_source_registry_path).resolve()
                                 if local_academic_demo_source_registry_path else
                                 approval_project_root / "knowledge_base" / "metadata" / "local_academic_demo_source_authorizations_phase1_v3.json")
    demo_policy_path = (Path(local_academic_demo_policy_path).resolve() if local_academic_demo_policy_path
                        else approval_project_root / "configs" / "local_academic_demo_policy.json")
    if authorization_mode not in {"production", "local_academic_demo"}:
        raise ValueError("RAG_AUTHORIZATION_MODE must be production or local_academic_demo.")
    if type(local_academic_demo_enabled) is not bool:
        raise ValueError("Local academic demo enablement must be boolean.")
    if evaluation_artifact_store is not None and authorization_mode != "local_academic_demo":
        raise ValueError("Evaluation diagnostics are restricted to local academic demo mode.")
    research_inventory_path = approval_project_root / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl"
    known_research_papers: dict[str, str] = {}
    if research_inventory_path.is_file():
        try:
            with research_inventory_path.open("r", encoding="utf-8-sig") as stream:
                for line in stream:
                    if line.strip():
                        row = json.loads(line)
                        if isinstance(row, dict) and row.get("source_type") == "research_paper":
                            known_research_papers[document_id_for(row)] = str(row.get("source_id", ""))
        except (OSError, ValueError, json.JSONDecodeError):
            known_research_papers = {}
    limiter = ApiRateLimiter(requests_per_minute=requests_per_minute)
    bearer = HTTPBearer(auto_error=False)

    def check_index() -> None:
        if callable(index_validator):
            manifest = index_validator()
        else:
            store = getattr(getattr(service, "retriever", None), "vector_store", None)
            if store is None:
                raise VectorStoreError("No managed index is configured.")
            manifest = validate_index_manifest(store)
        if isinstance(manifest, dict) and manifest.get("authorization_mode") != "reviewed_source_and_document_approval":
            raise VectorStoreError("Production API requires a reviewed source and document index.")

    def check_demo_index() -> tuple[dict, dict]:
        if authorization_mode != "local_academic_demo" or not local_academic_demo_enabled:
            raise VectorStoreError("Local academic demo authorization is disabled.")
        if not callable(index_validator):
            raise VectorStoreError("Local academic demo requires managed index validation.")
        manifest = index_validator()
        if (not isinstance(manifest, dict) or manifest.get("status") != "ready"
                or manifest.get("authorization_mode") != "operator_authorized_unreviewed"
                or manifest.get("collection_name") != "rag_docs_v2"):
            raise VectorStoreError("Local academic demo requires the existing ready development index.")
        validate_local_demo_policy(demo_policy_path)
        sources = validate_source_registry(demo_source_registry_path, research_inventory_path, api_token)
        registry = validate_demo_registry(demo_registry_path, research_inventory_path, api_token,
                                          operator=sources["operator"], source_registry=sources)
        if not set(registry.get("source_ids", [])) <= set(sources.get("sources", {})):
            raise DemoAuthorizationError("Demo document scope references an unauthorized source.")
        if (registry.get("index_id") != manifest.get("index_id")
                or registry.get("collection_name") != manifest.get("collection_name")):
            raise DemoAuthorizationError("Demo authorization registry does not match the current index.")
        return manifest, registry

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        service_close = getattr(service, "close", None)
        if callable(service_close):
            service_close()
            return
        for client in (
            getattr(service, "generator", None),
            getattr(getattr(service, "retriever", None), "embedding_provider", None),
            getattr(getattr(service, "retriever", None), "vector_store", None),
        ):
            close = getattr(client, "close", None)
            if callable(close):
                close()

    app = FastAPI(
        title="Secure Local RAG API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.service = service

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id", "")
        request.state.request_id = correlation_id if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", correlation_id) else uuid.uuid4().hex
        if request.method == "POST" and request.url.path == "/v1/query":
            content_length = request.headers.get("content-length")
            if content_length is None:
                response = JSONResponse({"detail": "Content-Length is required."}, status_code=411)
                response.headers["X-Request-ID"] = request.state.request_id
                response.headers["X-Correlation-ID"] = request.state.request_id
                return response
            try:
                body_size = int(content_length)
            except ValueError:
                response = JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)
                response.headers["X-Request-ID"] = request.state.request_id
                response.headers["X-Correlation-ID"] = request.state.request_id
                return response
            if body_size < 0 or body_size > max_body_bytes:
                response = JSONResponse({"detail": "Request body is too large."}, status_code=413)
                response.headers["X-Request-ID"] = request.state.request_id
                response.headers["X-Correlation-ID"] = request.state.request_id
                return response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Correlation-ID"] = request.state.request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def hide_validation_input(request: Request, exc: RequestValidationError):
        # Pydantic errors can include the submitted query. Keep validation responses generic.
        return JSONResponse(
            {"detail": "Invalid request.", "request_id": request.state.request_id},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            headers={"X-Request-ID": request.state.request_id,
                     "X-Correlation-ID": request.state.request_id},
        )

    def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
        if credentials is None or credentials.scheme.lower() != "bearer" or not validate_api_token(credentials.credentials, api_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return credentials.credentials

    def build_scope() -> AccessScope:
        try:
            registry = load_approval_registry(registry_path)
        except (OSError, ValueError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authorization policy is unavailable.")
        sources = registry.get("sources", {})
        approved_source_ids = tuple(sorted(
            source_id for source_id, entry in sources.items()
            if isinstance(entry, dict) and entry.get("status") == "approved"
            and validate_record(entry, source_id, approval_project_root)
        ))
        return AccessScope(tenant_id, (principal_id,), approved_source_ids)

    def document_policy(scope: AccessScope) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        restricted_sources = tuple(sorted(source_id for source_id in scope.allowed_source_ids
                                           if source_id.startswith("arxiv_")))
        if not document_registry_path.is_file():
            return (), (), restricted_sources
        try:
            registry = json.loads(document_registry_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Authorization policy is unavailable.")
        decisions = registry.get("documents") if isinstance(registry, dict) and registry.get("registry_version") == "1.0" else None
        if not isinstance(decisions, dict):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Authorization policy is unavailable.")
        excluded = set()
        permitted_papers = set()
        for document_id, entry in decisions.items():
            if not isinstance(document_id, str) or not re.fullmatch(r"[0-9a-f]{64}", document_id) or not isinstance(entry, dict):
                continue
            source_id = entry.get("source_id")
            if entry.get("status") == "rejected":
                excluded.add(document_id)
            if (entry.get("status") == "approved" and source_id in scope.allowed_source_ids
                    and source_id in restricted_sources and known_research_papers.get(document_id) == source_id
                    and entry.get("document_id") == document_id
                    and validate_record(entry, source_id, approval_project_root, document_id)):
                permitted_papers.add(document_id)
        return tuple(sorted(excluded)), tuple(sorted(permitted_papers)), restricted_sources

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/v1/query", response_model=QueryResponse)
    def query(request: Request, body: QueryRequest, _token: str = Depends(authenticate)):
        try:
            if authorization_mode == "local_academic_demo":
                _manifest, demo_registry = check_demo_index()
            else:
                check_index()
                demo_registry = None
        except Exception:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="A compatible ready index is unavailable.")
        client_ip = request.client.host if request.client else "unknown"
        if not limiter.allow(client_ip):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")
        is_demo = demo_registry is not None
        if is_demo:
            demo_sources = tuple(demo_registry["source_ids"])
            scope = AccessScope(tenant_id, (principal_id,), demo_sources)
            rejected_ids, approved_papers, restricted_sources = (), tuple(demo_registry["documents"]), demo_sources
        else:
            scope = build_scope()
            rejected_ids, approved_papers, restricted_sources = document_policy(scope)
        try:
            style_options = ({"response_style": body.response_style}
                             if body.response_style != "natural" else {})
            result = service.answer(body.query, scope, limit=body.top_k,
                                    excluded_document_ids=rejected_ids,
                                    restricted_source_ids=restricted_sources,
                                    permitted_document_ids=approved_papers,
                                    **({"permitted_document_metadata": demo_registry["documents"]} if is_demo else {}),
                                    **({"development_unreviewed": True,
                                        "explicit_operator_authorization": True} if is_demo else {}),
                                    **style_options)
        except ContextBudgetError:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="The question and available evidence exceed the configured model context. Shorten the question and try again.",
                headers={"X-RAG-Error-Code": "context_budget_exceeded",
                         "X-RAG-Error-Stage": "context_assembly"},
            )
        except RetrievalRequestError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query could not be processed.",
                                headers={"X-RAG-Error-Code": "retrieval_request_invalid",
                                         "X-RAG-Error-Stage": "retrieval"})
        except GenerationError as exc:
            if evaluation_artifact_store is not None and authorization_mode == "local_academic_demo":
                try:
                    evaluation_artifact_store.record_error(
                        request_id=request.state.request_id, query=body.query, error=exc,
                        model_configuration=evaluation_model_configuration,
                    )
                except Exception:
                    logger.warning("Evaluation diagnostics artifact write failed.")
            code = exc.error_code if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", exc.error_code) else "generation_error"
            stage = exc.error_stage if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", exc.error_stage) else "generation"
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Local RAG service is unavailable.",
                                headers={"X-RAG-Error-Code": code, "X-RAG-Error-Stage": stage})
        except (EmbeddingError, VectorStoreError, OSError, TimeoutError):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Local RAG service is unavailable.",
                                headers={"X-RAG-Error-Code": "local_dependency_failure",
                                         "X-RAG-Error-Stage": "retrieval_or_generation"})
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query could not be processed.")
        except Exception:
            # Keep internal dependency errors and their details out of HTTP responses.
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Local RAG service is unavailable.")
        if evaluation_artifact_store is not None and authorization_mode == "local_academic_demo":
            try:
                evaluation_artifact_store.record_result(
                    request_id=request.state.request_id, query=body.query, result=result,
                    model_configuration=evaluation_model_configuration,
                )
            except Exception:
                logger.warning("Evaluation diagnostics artifact write failed.")
        answer = (LOCAL_DEMO_ABSTENTION if is_demo and result.answer ==
                  "I cannot answer from the approved sources available to you." else result.answer)
        return QueryResponse(answer=answer, citations=result.citations, request_id=request.state.request_id,
                             retrieval_mode=getattr(service, "retrieval_mode", "dense"),
                             timings_ms=getattr(result, "timings_ms", {}),
                             verification_status=getattr(result, "verification_status", "not_reported"),
                             diagnostics=getattr(result, "diagnostics", {}), synthetic=False)

    @app.get("/ready")
    def ready(_token: str = Depends(authenticate)):
        try:
            if authorization_mode == "local_academic_demo":
                check_demo_index()
            else:
                check_index()
            service.retriever.embedding_provider.health_check()
            service.retriever.vector_store.health_check()
            service.generator.health_check()
        except Exception:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Local RAG dependencies are not ready.")
        return {"ready": True}

    return app
