import json
from pathlib import Path
import tempfile
import unittest
import asyncio
import hashlib

import httpx

from src.rag_pipeline.api import MAX_QUERY_CHARACTERS, MAX_QUERY_BODY_BYTES, create_app
from src.rag_pipeline.authorization.local_academic_demo import (
    AUTHORIZATION_SCOPE, POLICY_ID, REGISTRY_VERSION, SOURCE_AUTHORIZATION_SCOPE,
    SOURCE_AUTHORIZATION_STATUS, expected_document_map, expected_source_map, sign_registry,
)
from src.rag_pipeline.embeddings import EmbeddingError
from src.rag_pipeline.generation import OllamaTimeoutFailure
from src.rag_pipeline.service import RAGAnswer
from src.rag_pipeline.retrieval import ContextBudgetError
from src.rag_pipeline.storage import VectorStoreError


TOKEN = "test-only-secret-token-that-is-longer-than-32-bytes"


class ServiceStub:
    def __init__(self):
        self.scopes = []
        self.queries = []
        self.context_overflow = False
        self.generation_failure = False
        self.dependency_failure = False

    def answer(self, query, scope, limit=None, excluded_document_ids=(), restricted_source_ids=(), permitted_document_ids=(),
               permitted_document_metadata=None, development_unreviewed=False, explicit_operator_authorization=False,
               response_style="natural"):
        if self.context_overflow:
            raise ContextBudgetError("synthetic context overflow")
        if self.generation_failure:
            raise OllamaTimeoutFailure(stage="answer_generation")
        if self.dependency_failure:
            raise VectorStoreError("private Qdrant endpoint detail")
        self.queries.append(query)
        self.scopes.append(scope)
        self.top_k = limit
        self.excluded_document_ids = excluded_document_ids
        self.restricted_source_ids = restricted_source_ids
        self.permitted_document_ids = permitted_document_ids
        self.permitted_document_metadata = permitted_document_metadata
        self.development_unreviewed = development_unreviewed
        self.explicit_operator_authorization = explicit_operator_authorization
        self.response_style = response_style
        return RAGAnswer("Synthetic answer [S1].", ({"citation_id": "S1", "source_id": "docs"},), 1, None)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry_path = Path(self.temp_dir.name) / "source_approvals.json"
        self.root = Path(self.temp_dir.name).resolve()
        self.evidence = self.root / "license.txt"
        self.evidence.write_text("synthetic API license", encoding="utf-8")
        self.evidence_catalog = self.root / "evidence.jsonl"
        row = {"source_id": "docs", "path": str(self.evidence),
               "sha256": hashlib.sha256(self.evidence.read_bytes()).hexdigest()}
        self.evidence_catalog.write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.write_registry("approved")
        self.service = ServiceStub()
        self.app = create_app(
            self.service,
            api_token=TOKEN,
            tenant_id="tenant-from-server",
            principal_id="user-from-server",
            approval_registry_path=self.registry_path,
            index_validator=lambda: True,
            project_root=self.root,
            document_approval_registry_path=self.root / "document_approvals.json",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def post(self, app, body, headers=None):
        async def send():
            transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 12345))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post("/v1/query", json=body, headers=headers)
        return asyncio.run(send())

    def write_registry(self, status):
        entry = {
            "status": status,
            "reviewed_by": "test reviewer" if status == "approved" else None,
            "reviewed_at": "2026-11-15T00:00:00Z" if status == "approved" else None,
            "license_name": "synthetic test license" if status == "approved" else None,
            "approval_scope": "documentation_candidates" if status == "approved" else None,
            "evidence_path": "license.txt" if status == "approved" else None,
        }
        if status == "approved":
            row = json.loads(self.evidence_catalog.read_text(encoding="utf-8"))
            entry.update({
                "evidence_sha256": row["sha256"], "evidence_catalog": "evidence.jsonl",
                "evidence_record_sha256": hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                "evidence_source_id": "docs", "review_notes": "synthetic review",
            })
        self.registry_path.write_text(json.dumps({"registry_version": "1.0", "sources": {"docs": entry}}), encoding="utf-8")

    def auth(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    def test_query_uses_server_derived_scope_and_request_id(self):
        response = self.post(self.app, {"query": "test question"}, {**self.auth(), "X-Correlation-ID": "satell-e2e-42"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["citations"][0]["citation_id"], "S1")
        self.assertEqual(response.json()["retrieval_mode"], "dense")
        self.assertEqual(response.headers["x-request-id"], "satell-e2e-42")
        self.assertEqual(response.headers["x-correlation-id"], "satell-e2e-42")
        self.assertEqual(response.json()["request_id"], "satell-e2e-42")
        scope = self.service.scopes[-1]
        self.assertEqual(scope.tenant_id, "tenant-from-server")
        self.assertEqual(scope.principals, ("user-from-server",))
        self.assertEqual(scope.allowed_source_ids, ("docs",))

    def test_generation_artifact_details_and_raw_text_are_not_in_api_response(self):
        from src.rag_pipeline.generation import CitationValidationError
        error = CitationValidationError()
        error.failure_reason = "unknown_citation_id"
        error.raw_generated_answer = "PRIVATE_RAW_MODEL_OUTPUT"
        self.service.answer = lambda *args, **kwargs: RAGAnswer(
            "I cannot answer from the approved sources available to you.", (), 1, None,
            generation_error=error, verification_status="failed",
            diagnostics={"failure_code": error.error_code, "failure_stage": error.error_stage,
                         "failure_reason": error.failure_reason},
        )
        response = self.post(self.app, {"query": "test question"}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PRIVATE_RAW_MODEL_OUTPUT", response.text)
        self.assertNotIn("raw_generated_answer", response.json())

    def test_evaluation_artifact_cannot_be_enabled_in_production_mode(self):
        from src.rag_pipeline.generation.evaluation_artifact import EvaluationArtifactStore
        store = EvaluationArtifactStore(self.root / "evaluation.jsonl", self.root)
        with self.assertRaisesRegex(ValueError, "local academic demo mode"):
            create_app(self.service, api_token=TOKEN, tenant_id="tenant", principal_id="principal",
                       approval_registry_path=self.registry_path, project_root=self.root,
                       index_validator=lambda: True, evaluation_artifact_store=store)

    def test_query_top_k_is_passed_to_retrieval_service(self):
        response = self.post(self.app, {"query": "test question", "top_k": 3}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.top_k, 3)

    def test_response_style_is_validated_and_passed_to_generation_service(self):
        response = self.post(self.app, {"query": "test question", "response_style": "concise"}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.response_style, "concise")
        invalid = self.post(self.app, {"query": "test question", "response_style": "invented"}, self.auth())
        self.assertEqual(invalid.status_code, 422)

    def test_context_overflow_returns_safe_actionable_413(self):
        self.service.context_overflow = True
        response = self.post(self.app, {"query": "x" * 5000}, self.auth())
        self.assertEqual(response.status_code, 413)
        self.assertIn("Shorten the question", response.json()["detail"])
        self.assertNotIn("synthetic context overflow", response.text)

    def test_generation_failure_has_safe_machine_readable_classification(self):
        self.service.generation_failure = True
        response = self.post(self.app, {"query": "test question"}, self.auth())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["X-RAG-Error-Code"], "ollama_timeout")
        self.assertEqual(response.headers["X-RAG-Error-Stage"], "answer_generation")
        self.assertNotIn("Ollama", response.text)

    def test_vector_store_failure_is_generic_and_machine_classified(self):
        self.service.dependency_failure = True
        response = self.post(self.app, {"query": "test question"}, self.auth())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["X-RAG-Error-Code"], "local_dependency_failure")
        self.assertNotIn("Qdrant endpoint", response.text)

    def test_query_accepts_exactly_5000_characters_without_truncation(self):
        self.assertEqual(MAX_QUERY_CHARACTERS, 5000)
        prompt = "x" * 5000
        response = self.post(self.app, {"query": prompt}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.queries[-1], prompt)

    def test_query_rejects_5001_characters_and_empty_query(self):
        too_long = self.post(self.app, {"query": "x" * 5001}, self.auth())
        empty = self.post(self.app, {"query": ""}, self.auth())
        self.assertEqual(too_long.status_code, 422)
        self.assertEqual(empty.status_code, 422)
        self.assertEqual(self.service.queries, [])

    def test_ready_endpoint_refuses_operator_authorized_unreviewed_manifest(self):
        app = create_app(
            self.service, api_token=TOKEN, tenant_id="tenant", principal_id="user",
            approval_registry_path=self.registry_path,
            index_validator=lambda: {"status": "ready", "authorization_mode": "operator_authorized_unreviewed"},
            project_root=self.root,
        )
        async def send():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/ready", headers=self.auth())
        response = asyncio.run(send())
        self.assertEqual(response.status_code, 503)

    def test_query_accepts_5000_multibyte_characters_within_body_limit(self):
        prompt = "🙂" * 5000
        self.assertLessEqual(len(prompt.encode("utf-8")) + 32, MAX_QUERY_BODY_BYTES)
        response = self.post(self.app, {"query": prompt}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.queries[-1], prompt)

    def test_query_accepts_5000_characters_in_ascii_escaped_json(self):
        prompt = "🙂" * 5000
        encoded = json.dumps({"query": prompt}, ensure_ascii=True).encode("ascii")
        self.assertLessEqual(len(encoded), MAX_QUERY_BODY_BYTES)
        async def send():
            transport = httpx.ASGITransport(app=self.app, client=("127.0.0.1", 12345))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post("/v1/query", content=encoded,
                    headers={**self.auth(), "Content-Type": "application/json"})
        response = asyncio.run(send())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.queries[-1], prompt)

    def test_document_rejection_is_reloaded_and_passed_as_a_deny_filter(self):
        rejected_id = "a" * 64
        path = self.root / "document_approvals.json"
        path.write_text(json.dumps({"registry_version": "1.0", "documents": {
            rejected_id: {"source_id": "docs", "status": "rejected"}}}), encoding="utf-8")
        response = self.post(self.app, {"query": "test question"}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.excluded_document_ids, (rejected_id,))

    def test_malformed_document_decision_registry_fails_closed(self):
        (self.root / "document_approvals.json").write_text("{}", encoding="utf-8")
        response = self.post(self.app, {"query": "test question"}, self.auth())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.service.scopes, [])

    def test_authentication_is_required_and_invalid_token_is_rejected(self):
        self.assertEqual(self.post(self.app, {"query": "x"}).status_code, 401)
        self.assertEqual(self.post(self.app, {"query": "x"}, {"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.service.scopes, [])

    def test_client_cannot_supply_tenant_principal_or_source_scope(self):
        response = self.post(
            self.app,
            {"query": "do not echo me", "tenant_id": "tenant-attacker", "principal_id": "user-attacker", "source_ids": ["private"]},
            self.auth(),
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("do not echo me", response.text)
        self.assertEqual(self.service.scopes, [])

    def test_local_embedding_failure_returns_generic_service_error(self):
        class BrokenService(ServiceStub):
            def answer(self, query, scope, limit=None, excluded_document_ids=(), restricted_source_ids=(), permitted_document_ids=()):
                raise EmbeddingError("private runtime detail")

        broken_app = create_app(
            BrokenService(),
            api_token=TOKEN,
            tenant_id="tenant-from-server",
            principal_id="user-from-server",
            approval_registry_path=self.registry_path,
            index_validator=lambda: True,
            project_root=self.root,
        )
        response = self.post(broken_app, {"query": "question"}, self.auth())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private runtime detail", response.text)

    def test_approved_sources_are_reloaded_for_revocation(self):
        self.write_registry("pending_review")
        response = self.post(self.app, {"query": "x"}, self.auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.scopes[-1].allowed_source_ids, ())

    def test_query_body_size_is_bounded(self):
        response = self.post(self.app, {"query": "x" * 70000}, self.auth())
        self.assertEqual(response.status_code, 413)

    def test_authenticated_query_rate_limit(self):
        app = create_app(
            self.service,
            api_token=TOKEN,
            tenant_id="tenant-from-server",
            principal_id="user-from-server",
            approval_registry_path=self.registry_path,
            requests_per_minute=1,
            index_validator=lambda: True,
            project_root=self.root,
        )
        self.assertEqual(self.post(app, {"query": "first"}, self.auth()).status_code, 200)
        self.assertEqual(self.post(app, {"query": "second"}, self.auth()).status_code, 429)

    def test_token_minimum_length_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "32 characters"):
            create_app(
                self.service,
                api_token="short",
                tenant_id="tenant",
                principal_id="user",
                approval_registry_path=self.registry_path,
            )

    def test_query_returns_503_without_ready_index(self):
        app = create_app(self.service, api_token=TOKEN, tenant_id="tenant", principal_id="user",
                         approval_registry_path=self.registry_path,
                         index_validator=lambda: (_ for _ in ()).throw(RuntimeError("missing manifest")),
                         project_root=self.root)
        response = self.post(app, {"query": "question"}, self.auth())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.service.scopes, [])

    def test_production_api_rejects_unreviewed_development_index(self):
        app = create_app(
            self.service, api_token=TOKEN, tenant_id="tenant", principal_id="user",
            approval_registry_path=self.registry_path,
            index_validator=lambda: {"status": "ready", "authorization_mode": "operator_authorized_unreviewed"},
            project_root=self.root,
        )
        response = self.post(app, {"query": "question"}, self.auth())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.service.scopes, [])

    def test_health_is_available_without_an_index(self):
        async def send():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.get("/health")
        response = asyncio.run(send())
        self.assertEqual(response.status_code, 200)


class LocalAcademicDemoApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.meta = self.root / "knowledge_base" / "metadata"
        self.meta.mkdir(parents=True)
        self.inventory_path = self.meta / "ingestion_inventory.jsonl"
        self.demo_registry_path = self.meta / "local_academic_demo_authorization.json"
        self.source_registry_path = self.meta / "local_academic_demo_source_authorizations.json"
        self.approval_path = self.meta / "source_approvals.json"
        doc = {
            "source_type": "documentation", "source_id": "docs", "source_name": "Docs",
            "relative_path": "guide.md", "file_category": "documentation",
            "ingestion_status": "candidate_not_reviewed", "license_review_status": "pending",
            "sha256": "a" * 64,
        }
        code = {
            "source_type": "documentation", "source_id": "docs", "source_name": "Docs",
            "relative_path": "example.py", "file_category": "code",
            "ingestion_status": "supporting_asset", "license_review_status": "pending",
            "sha256": "b" * 64,
        }
        self.inventory_path.write_text(json.dumps(doc) + "\n" + json.dumps(code) + "\n", encoding="utf-8")
        policy_path = self.root / "configs" / "local_academic_demo_policy.json"
        policy_path.parent.mkdir(parents=True)
        policy_path.write_text(json.dumps({
            "policy_id": POLICY_ID, "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
            "permitted_source_types": ["documentation"],
            "permitted_file_categories": ["documentation"],
            "excluded_file_categories": ["research_paper", "code", "image", "structured_data", "supporting_artifact"],
            "legal_review_required": False, "legal_review_status": "pending", "production_authorization": False,
        }), encoding="utf-8")
        self.doc_id = __import__("src.rag_pipeline.ingestion.parsing_job", fromlist=["document_id_for"]).document_id_for(doc)
        self.service = ServiceStub()
        self.index = {"status": "ready", "authorization_mode": "operator_authorized_unreviewed",
                      "collection_name": "rag_docs_v2", "index_id": "synthetic-index"}
        self.app = self.make_app(enabled=True)
        self.write_source_registry()
        self.write_demo_registry()

    def tearDown(self):
        self.temp.cleanup()

    def make_app(self, *, enabled):
        return create_app(
            self.service, api_token=TOKEN, tenant_id="tenant", principal_id="operator",
            approval_registry_path=self.approval_path,
            index_validator=lambda: self.index,
            project_root=self.root,
            authorization_mode="local_academic_demo",
            local_academic_demo_enabled=enabled,
            local_academic_demo_registry_path=self.demo_registry_path,
            local_academic_demo_source_registry_path=self.source_registry_path,
        )

    def write_source_registry(self):
        inventory_sha, expected = expected_source_map(self.inventory_path)
        now = "2026-11-18T12:00:00+00:00"
        sources = {source_id: {
            **value,
            "inventory_record_count": value["record_count"],
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
            "operator": "test-operator", "authorized_at": now,
            "policy_id": POLICY_ID, "inventory_sha256": inventory_sha,
            "validation_status": "validated", "legal_review_status": "pending",
        } for source_id, value in expected.items()}
        registry = sign_registry({
            "registry_version": REGISTRY_VERSION,
            "registry_type": "source_operator_authorization", "policy_id": POLICY_ID,
            "authorization_scope": SOURCE_AUTHORIZATION_SCOPE, "operator": "test-operator",
            "authorized_at": now, "legal_review_status": "pending",
            "inventory_sha256": inventory_sha, "source_count": len(sources), "sources": sources,
        }, TOKEN)
        self.source_registry_path.write_text(json.dumps(registry), encoding="utf-8")

    def write_demo_registry(self):
        inventory_sha, documents, sources = expected_document_map(self.inventory_path)
        now = "2026-11-18T12:00:00+00:00"
        rows = {doc_id: {
            "document_id": doc_id, **value, "operator": "test-operator", "authorized_at": now,
            "policy_id": POLICY_ID, "authorization_scope": AUTHORIZATION_SCOPE,
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "legal_review_status": "pending",
            "indexed_point_ids": ["synthetic-point"],
            "inventory_record_count": len(value["provenance_paths"]),
        } for doc_id, value in documents.items()}
        registry = sign_registry({
            "registry_version": REGISTRY_VERSION, "registry_type": "document_operator_authorization",
            "policy_id": POLICY_ID,
            "authorization_scope": AUTHORIZATION_SCOPE, "operator": "test-operator",
            "authorized_at": now, "legal_review_status": "pending",
            "inventory_sha256": inventory_sha, "index_id": "synthetic-index",
            "collection_name": "rag_docs_v2", "source_ids": list(sources),
            "operator": "test-operator",
            "authorized_inventory_record_count": 1, "authorized_document_count": 1,
            "indexed_document_count": 1, "indexed_point_count": 1, "excluded_document_count": 0,
            "documents": rows,
            "excluded_documents": {},
        }, TOKEN)
        self.demo_registry_path.write_text(json.dumps(registry), encoding="utf-8")

    def post(self, app=None):
        async def send():
            transport = httpx.ASGITransport(app=app or self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post("/v1/query", json={"query": "documentation question"},
                                         headers={"Authorization": f"Bearer {TOKEN}"})
        return asyncio.run(send())

    def test_demo_mode_is_disabled_by_default(self):
        app = create_app(self.service, api_token=TOKEN, tenant_id="tenant", principal_id="operator",
                         approval_registry_path=self.approval_path, index_validator=lambda: self.index,
                         project_root=self.root, authorization_mode="local_academic_demo")
        self.assertEqual(self.post(app).status_code, 503)

    def test_demo_allows_only_inventory_documentation_and_keeps_legal_review_pending(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.scopes[-1].allowed_source_ids, ("docs",))
        self.assertEqual(self.service.permitted_document_ids, (self.doc_id,))
        self.assertEqual(self.service.permitted_document_metadata[self.doc_id]["content_sha256"], "a" * 64)
        self.assertEqual(self.service.development_unreviewed, True)
        self.assertEqual(self.service.explicit_operator_authorization, True)
        registry = json.loads(self.demo_registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry["legal_review_status"], "pending")
        self.assertEqual(registry["documents"][self.doc_id]["legal_review_status"], "pending")

    def test_demo_abstention_does_not_imply_legal_approval(self):
        class AbstainingService(ServiceStub):
            def answer(self, *args, **kwargs):
                from src.rag_pipeline.service import ABSTENTION
                return RAGAnswer(ABSTENTION, (), 0, None)
        app = create_app(
            AbstainingService(), api_token=TOKEN, tenant_id="tenant", principal_id="operator",
            approval_registry_path=self.approval_path, index_validator=lambda: self.index,
            project_root=self.root, authorization_mode="local_academic_demo",
            local_academic_demo_enabled=True,
            local_academic_demo_registry_path=self.demo_registry_path,
            local_academic_demo_source_registry_path=self.source_registry_path,
        )
        response = self.post(app)
        self.assertEqual(response.status_code, 200)
        self.assertIn("local academic demo", response.json()["answer"])
        self.assertNotIn("approved sources", response.json()["answer"])

    def test_unknown_document_id_is_rejected(self):
        registry = json.loads(self.demo_registry_path.read_text(encoding="utf-8"))
        registry["documents"]["f" * 64] = {"document_id": "f" * 64}
        # Keep the signature valid to exercise inventory binding, not only HMAC.
        registry = sign_registry(registry, TOKEN)
        self.demo_registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.assertEqual(self.post().status_code, 503)

    def test_unsupported_category_cannot_be_added_to_demo_registry(self):
        registry = json.loads(self.demo_registry_path.read_text(encoding="utf-8"))
        registry["authorized_inventory_record_count"] = 2
        registry = sign_registry(registry, TOKEN)
        self.demo_registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.assertEqual(self.post().status_code, 503)

    def test_tampered_registry_fails_closed(self):
        registry = json.loads(self.demo_registry_path.read_text(encoding="utf-8"))
        registry["operator"] = "tampered"
        self.demo_registry_path.write_text(json.dumps(registry), encoding="utf-8")
        self.assertEqual(self.post().status_code, 503)

    def test_missing_demo_registry_fails_closed(self):
        self.demo_registry_path.unlink()
        self.assertEqual(self.post().status_code, 503)

    def test_demo_requires_unreviewed_index_manifest(self):
        self.index["authorization_mode"] = "reviewed_source_and_document_approval"
        self.assertEqual(self.post().status_code, 503)

if __name__ == "__main__":
    unittest.main()
