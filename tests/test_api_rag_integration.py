import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

import httpx
from qdrant_client import QdrantClient

from src.rag_pipeline.api import create_app
from src.rag_pipeline.generation import GenerationResult
from src.rag_pipeline.retrieval import ContextAssembler, DenseRetriever
from src.rag_pipeline.service import ABSTENTION, LocalRAGService
from src.rag_pipeline.storage import QdrantVectorStore
from src.rag_pipeline.embeddings import EmbeddingDescriptor
from src.rag_pipeline.ingestion.approval_workflow import decide_source


TOKEN = "integration-test-token-with-more-than-thirty-two-characters"


class EmbeddingStub:
    def embed(self, texts):
        return SimpleNamespace(vectors=[[1.0, 0.0] for _ in texts])


class GenerationStub:
    called = False

    def generate(self, query, context):
        self.called = True
        return GenerationResult("The guide states this fact [S1].", ("S1",), "stub", "test", 1.0,
                                claim_count=1, supported_claim_count=1,
                                claim_verification_ms=1.0)


class ApiRagIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry_path = self.root / "source_approvals.json"
        self.registry_path.write_text(json.dumps({"registry_version": "1.0", "sources": {
            "docs": {"status": "pending_review"}}}), encoding="utf-8")
        artifact = self.root / "license.txt"
        artifact.write_text("Synthetic integration license", encoding="utf-8")
        catalog = self.root / "evidence.jsonl"
        record = {"source_id": "docs", "path": str(artifact),
                  "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
        catalog.write_text(json.dumps(record) + "\n", encoding="utf-8")
        decide_source(self.registry_path, "docs", "approved", "integration reviewer", catalog,
            "Synthetic integration fixture", self.root, "fixture license", "documentation_candidates")
        self.client = QdrantClient(":memory:")
        descriptor = EmbeddingDescriptor("test", "test-embedding", "sha256:integration", 2, True, "test")
        self.store = QdrantVectorStore(self.root, "integration_rag_v1", descriptor, "chunk-v1", client=self.client)
        chunk = {"chunk_id": "chunk-one", "content_id": "content-one", "text": "The guide states a verified integration fact.",
                 "segments": [], "heading_paths": [["Guide"]], "page_references": [1], "parent_chunk_id": None}
        metadata = {"tenant_id": "tenant", "source_id": "docs", "document_id": "a" * 64,
            "acl_principals": ["reader"], "license_review_status": "approved", "source_type": "documentation",
            "title": "Integration guide", "content_hash": "sha256:source", "document_version": "v1",
            "ingestion_timestamp": "2026-11-16T00:00:00Z", "source_reference": "https://docs.example/guide"}
        self.store.upsert_chunks([chunk], [[1.0, 0.0]], [metadata])
        self.generator = GenerationStub()
        service = LocalRAGService(DenseRetriever(EmbeddingStub(), self.store), ContextAssembler(), self.generator)
        self.document_registry_path = self.root / "document_approvals.json"
        self.app = create_app(service, api_token=TOKEN, tenant_id="tenant", principal_id="reader",
            approval_registry_path=self.registry_path, document_approval_registry_path=self.document_registry_path,
            project_root=self.root,
            index_validator=lambda: {"status": "ready", "authorization_mode": "reviewed_source_and_document_approval"})

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def post(self):
        async def send():
            transport = httpx.ASGITransport(app=self.app, client=("127.0.0.1", 12345))
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.post("/v1/query", json={"query": "integration fact", "top_k": 3},
                    headers={"Authorization": f"Bearer {TOKEN}"})
        return asyncio.run(send())

    def test_api_runs_retrieval_context_generation_and_returns_citation_and_timings(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["answer"], "The guide states this fact [S1].")
        self.assertEqual(body["citations"][0]["document_id"], "a" * 64)
        self.assertEqual(body["retrieval_mode"], "dense")
        self.assertIn("embedding", body["timings_ms"])
        self.assertEqual(body["verification_status"], "verified")
        self.assertIn("retrieval_hits", body["diagnostics"])
        self.assertGreater(body["diagnostics"]["context_bytes"], 0)
        self.assertGreater(body["diagnostics"]["context_chunk_count"], 0)
        self.assertEqual(body["diagnostics"]["context_exclusion_reasons"], {})
        self.assertEqual(body["diagnostics"]["citation_validation_status"], "passed")
        self.assertEqual(body["diagnostics"]["claim_verifier_status"], "verified")
        self.assertEqual(body["diagnostics"]["retrieval_strategy"], "dense")
        self.assertFalse(body["diagnostics"]["reranker_active"])
        self.assertTrue(self.generator.called)

    def test_document_rejection_blocks_generation_end_to_end(self):
        self.document_registry_path.write_text(json.dumps({"registry_version": "1.0", "documents": {
            "a" * 64: {"source_id": "docs", "status": "rejected"}}}), encoding="utf-8")
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], ABSTENTION)
        self.assertEqual(response.json()["citations"], [])
        self.assertFalse(self.generator.called)


if __name__ == "__main__":
    unittest.main()
