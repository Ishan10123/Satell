"""Small HTTP boundary for the separate FastAPI service; no engine imports."""

from dataclasses import dataclass
import ipaddress
import math
import re
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
import uuid

import httpx

MAX_QUERY_CHARS = 5000


class RAGClientError(RuntimeError):
    """Safe base error; messages intentionally exclude request bodies and secrets."""

    def __init__(self, message: str, *, error_code: str = "rag_client_error",
                 error_stage: str = "client", http_status: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_stage = error_stage
        self.http_status = http_status


class RAGClientTimeout(RAGClientError):
    pass


class RAGClientUnavailable(RAGClientError):
    pass


class RAGClientProtocolError(RAGClientError):
    pass


class RAGClientInputTooLarge(RAGClientError):
    pass


class RAGClientConfigurationError(RAGClientError):
    pass


@dataclass(frozen=True)
class CitationMetadata:
    citation_id: str
    source_id: str
    document_id: str
    chunk_id: str
    title: str
    page_references: tuple[int, ...]
    section: str
    source_reference: str


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    citations: tuple[CitationMetadata, ...]
    request_id: str
    retrieval_mode: str
    stage_timings: dict[str, float]
    verification_status: str
    diagnostics: dict[str, object]
    synthetic: bool = False


class RAGClient(Protocol):
    def query(self, query: str, *, top_k: int, correlation_id: str,
              response_style: str = "natural") -> RAGResponse: ...


def _safe_source_reference(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    try:
        address = ipaddress.ip_address(parsed.hostname)
        if not address.is_global:
            return ""
    except ValueError:
        if parsed.hostname.lower() == "localhost" or "." not in parsed.hostname:
            return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _parse_response(payload: object, fallback_request_id: str, *, synthetic: bool = False) -> RAGResponse:
    if not isinstance(payload, dict):
        raise RAGClientProtocolError("RAG service returned an invalid response.")
    answer = payload.get("answer")
    request_id = payload.get("request_id", fallback_request_id)
    mode = payload.get("retrieval_mode", "synthetic_mock" if synthetic else "unknown")
    raw_citations = payload.get("citations", [])
    raw_timings = payload.get("timings_ms", {})
    raw_diagnostics = payload.get("diagnostics", {})
    verification_status = payload.get("verification_status", "synthetic" if synthetic else "not_reported")
    response_synthetic = payload.get("synthetic", synthetic)
    if (not isinstance(answer, str) or not answer.strip() or len(answer) > 100_000
            or not isinstance(request_id, str) or not request_id or len(request_id) > 128
            or not isinstance(mode, str) or not mode or len(mode) > 32
            or not isinstance(raw_citations, (list, tuple)) or len(raw_citations) > 100
            or not isinstance(raw_timings, dict) or not isinstance(raw_diagnostics, dict)
            # Keep the boundary bounded while allowing the complete, versioned
            # retrieval/generation/verification telemetry returned by FastAPI.
            or len(raw_diagnostics) > 24
            or verification_status not in {"verified", "partially_verified", "abstained", "failed", "not_reported", "synthetic"}
            or type(response_synthetic) is not bool):
        raise RAGClientProtocolError("RAG service returned an invalid response.")
    citations: list[CitationMetadata] = []
    seen_ids: set[str] = set()
    for row in raw_citations:
        if not isinstance(row, dict):
            raise RAGClientProtocolError("RAG service returned invalid citation metadata.")
        citation_id = row.get("citation_id")
        source_id = row.get("source_id")
        document_id = row.get("document_id")
        chunk_id = row.get("chunk_id") or ""
        title = row.get("title") or "Untitled source"
        pages = row.get("page_references") or []
        section = row.get("section") or ""
        if (not isinstance(citation_id, str) or not re.fullmatch(r"S[1-9][0-9]*", citation_id)
                or citation_id in seen_ids
                or not isinstance(source_id, str) or not source_id or len(source_id) > 128
                or not isinstance(document_id, str) or not document_id or len(document_id) > 128
                or not isinstance(chunk_id, str) or len(chunk_id) > 128
                or not isinstance(title, str) or len(title) > 500
                or not isinstance(pages, (list, tuple)) or len(pages) > 100
                or any(type(page) is not int or page < 1 for page in pages)
                or not isinstance(section, str) or len(section) > 1000):
            raise RAGClientProtocolError("RAG service returned invalid citation metadata.")
        seen_ids.add(citation_id)
        citations.append(CitationMetadata(
            citation_id=citation_id, source_id=source_id, document_id=document_id,
            chunk_id=chunk_id, title=title, page_references=tuple(pages),
            section=section, source_reference=_safe_source_reference(row.get("source_reference")),
        ))
    timings: dict[str, float] = {}
    for key, value in raw_timings.items():
        if (not isinstance(key, str) or len(key) > 64 or isinstance(value, bool)
                or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            raise RAGClientProtocolError("RAG service returned invalid timing metadata.")
        timings[key] = float(value)
    diagnostics: dict[str, object] = {}
    for key in ("retrieval_hit_count", "context_bytes", "context_token_estimate",
                "context_chunk_count", "context_exclusion_count"):
        value = raw_diagnostics.get(key)
        if value is not None and (type(value) is not int or value < 0 or value > 10_000_000):
            raise RAGClientProtocolError("RAG service returned invalid diagnostics.")
        if value is not None:
            diagnostics[key] = value
    reranker_active = raw_diagnostics.get("reranker_active")
    if reranker_active is not None and type(reranker_active) is not bool:
        raise RAGClientProtocolError("RAG service returned invalid diagnostics.")
    if reranker_active is not None:
        diagnostics["reranker_active"] = reranker_active
    for key in ("retrieval_strategy", "citation_validation_status", "claim_verifier_status",
                "failure_code", "failure_stage"):
        value = raw_diagnostics.get(key)
        allowed = {
            "retrieval_strategy": {"dense", "hybrid", "hybrid_rerank"},
            "citation_validation_status": {"passed", "rejected", "not_applicable"},
            "claim_verifier_status": {"verified", "partially_verified", "rejected", "not_run"},
            "failure_code": None,
            "failure_stage": None,
        }[key]
        if value is not None and (not isinstance(value, str) or len(value) > 64
                                  or allowed is not None and value not in allowed):
            raise RAGClientProtocolError("RAG service returned invalid diagnostics.")
        if value is not None:
            diagnostics[key] = value
    exclusion_reasons = raw_diagnostics.get("context_exclusion_reasons", {})
    if not isinstance(exclusion_reasons, dict) or len(exclusion_reasons) > 16:
        raise RAGClientProtocolError("RAG service returned invalid context diagnostics.")
    safe_exclusions: dict[str, int] = {}
    for reason, count in exclusion_reasons.items():
        if not isinstance(reason, str) or len(reason) > 64 or type(count) is not int or count < 0:
            raise RAGClientProtocolError("RAG service returned invalid context diagnostics.")
        safe_exclusions[reason] = count
    diagnostics["context_exclusion_reasons"] = safe_exclusions
    raw_hits = raw_diagnostics.get("retrieval_hits", [])
    if not isinstance(raw_hits, list) or len(raw_hits) > 20:
        raise RAGClientProtocolError("RAG service returned invalid retrieval diagnostics.")
    safe_hits: list[dict[str, object]] = []
    for hit in raw_hits:
        if not isinstance(hit, dict):
            raise RAGClientProtocolError("RAG service returned invalid retrieval diagnostics.")
        row: dict[str, object] = {}
        for name in ("document_id", "source_id", "chunk_id"):
            value = hit.get(name, "")
            if not isinstance(value, str) or len(value) > 128:
                raise RAGClientProtocolError("RAG service returned invalid retrieval diagnostics.")
            row[name] = value
        for name in ("score", "dense_score", "sparse_score", "rerank_score"):
            value = hit.get(name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise RAGClientProtocolError("RAG service returned invalid retrieval diagnostics.")
                row[name] = float(value)
        for name in ("rank", "dense_rank", "sparse_rank"):
            value = hit.get(name)
            if value is not None and (type(value) is not int or not 1 <= value <= 1000):
                raise RAGClientProtocolError("RAG service returned invalid retrieval diagnostics.")
            if value is not None:
                row[name] = value
        safe_hits.append(row)
    diagnostics["retrieval_hits"] = safe_hits
    for key in ("generation_model", "verification_model"):
        value = raw_diagnostics.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > 128):
            raise RAGClientProtocolError("RAG service returned invalid diagnostics.")
        if value is not None:
            diagnostics[key] = value
    for key in ("claim_count", "supported_claim_count", "rejected_claim_count", "prompt_tokens_estimated"):
        value = raw_diagnostics.get(key)
        if value is not None and (type(value) is not int or value < 0 or value > 1_000_000):
            raise RAGClientProtocolError("RAG service returned invalid diagnostics.")
        if value is not None:
            diagnostics[key] = value
    return RAGResponse(answer, tuple(citations), request_id, mode, timings,
                       verification_status, diagnostics, response_synthetic)


class FastAPIRAGClient:
    """Synchronous, bounded HTTP adapter for the independent FastAPI service."""

    def __init__(self, base_url: str, bearer_token: str, timeout_seconds: float = 15.0,
                 *, client: httpx.Client | None = None, top_k: int = 8) -> None:
        if not bearer_token or len(bearer_token) < 32:
            raise RAGClientConfigurationError("RAG API credentials are not configured.")
        if timeout_seconds <= 0 or not 1 <= top_k <= 20:
            raise RAGClientConfigurationError("RAG API client limits are invalid.")
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise RAGClientConfigurationError("RAG API URL is invalid.")
        if parsed.scheme == "http":
            host = parsed.hostname.lower()
            loopback = host == "localhost"
            if not loopback:
                try:
                    loopback = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    loopback = False
            docker_service = host in {"rag-api", "rag-api-synthetic"} and parsed.port == 8000
            if not loopback and not docker_service:
                raise RAGClientConfigurationError("Non-loopback RAG API URLs must use HTTPS.")
        self.base_url = base_url.rstrip("/")
        self._token = bearer_token
        self.top_k = top_k
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_seconds), follow_redirects=False)
        self._owns_client = client is None

    def query(self, query: str, *, top_k: int | None = None, correlation_id: str | None = None,
              response_style: str = "natural") -> RAGResponse:
        selected_top_k = self.top_k if top_k is None else top_k
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise RAGClientProtocolError("RAG query is outside the accepted limits.")
        if type(selected_top_k) is not int or not 1 <= selected_top_k <= 20:
            raise RAGClientProtocolError("RAG result limit is outside the accepted range.")
        if response_style not in {"natural", "concise", "detailed"}:
            raise RAGClientProtocolError("RAG response style is outside the accepted options.")
        request_id = correlation_id or uuid.uuid4().hex
        payload = {"query": query, "top_k": selected_top_k}
        if response_style != "natural":
            payload["response_style"] = response_style
        try:
            response = self._client.post(
                f"{self.base_url}/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {self._token}", "X-Correlation-ID": request_id},
            )
        except httpx.TimeoutException as exc:
            raise RAGClientTimeout("RAG service request timed out.", error_code="client_timeout",
                                   error_stage="http_client") from exc
        except httpx.TransportError as exc:
            raise RAGClientUnavailable("RAG service could not be reached.", error_code="service_unavailable",
                                       error_stage="http_client") from exc
        if response.is_error:
            raw_code = response.headers.get("X-RAG-Error-Code", "upstream_error")
            raw_stage = response.headers.get("X-RAG-Error-Stage", "api")
            error_code = raw_code if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", raw_code) else "upstream_error"
            error_stage = raw_stage if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", raw_stage) else "api"
            if response.status_code in {408, 504}:
                raise RAGClientTimeout("RAG service request timed out.", error_code=error_code,
                                       error_stage=error_stage, http_status=response.status_code)
            if response.status_code == 413:
                raise RAGClientInputTooLarge(
                    "The question leaves too little room for reference evidence in the model context. Shorten it and try again.",
                    error_code=error_code, error_stage=error_stage, http_status=response.status_code
                )
            raise RAGClientUnavailable("RAG service could not complete the request.", error_code=error_code,
                                       error_stage=error_stage, http_status=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RAGClientProtocolError("RAG service returned an invalid response.") from exc
        return _parse_response(payload, request_id)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class MockRAGClient:
    """Explicit synthetic adapter for local UI wiring; never represents real retrieval."""

    def query(self, query: str, *, top_k: int = 8, correlation_id: str | None = None,
              response_style: str = "natural") -> RAGResponse:
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise RAGClientProtocolError("RAG query is outside the accepted limits.")
        if response_style not in {"natural", "concise", "detailed"}:
            raise RAGClientProtocolError("RAG response style is outside the accepted options.")
        request_id = correlation_id or uuid.uuid4().hex
        return _parse_response({
            "answer": "Synthetic mock response only. This is not a real RAG result.",
            "request_id": request_id,
            "retrieval_mode": "synthetic_mock",
            "citations": [{
                "citation_id": "S1", "source_id": "synthetic_source",
                "document_id": "synthetic-document", "chunk_id": "synthetic-chunk",
                "title": "Synthetic test citation", "page_references": [],
                "section": "Mock adapter", "source_reference": "",
            }],
            "timings_ms": {},
            "verification_status": "synthetic",
            "diagnostics": {},
        }, request_id, synthetic=True)


def get_rag_client() -> RAGClient:
    """Construct the configured adapter server-side; secrets never reach browser code."""
    from django.conf import settings

    if settings.RAG_ADAPTER == "mock":
        return MockRAGClient()
    if settings.RAG_ADAPTER == "http":
        return FastAPIRAGClient(
            settings.RAG_API_BASE_URL, settings.RAG_API_TOKEN,
            settings.RAG_API_TIMEOUT_SECONDS, top_k=settings.RAG_API_TOP_K,
        )
    raise RAGClientConfigurationError("Configured RAG adapter is unsupported.")
