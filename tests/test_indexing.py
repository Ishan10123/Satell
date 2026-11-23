import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import warnings

from qdrant_client import QdrantClient

from src.rag_pipeline.chunking import ChunkConfig
from src.rag_pipeline.embeddings import EmbeddingBatch, EmbeddingDescriptor
from src.rag_pipeline.ingestion.indexing import index_normalized_run
from src.rag_pipeline.ingestion.parsing_job import run_parsing_job
from src.rag_pipeline.ingestion.approval_workflow import decide_source
from src.rag_pipeline.normalization import normalize_parsed_run
from src.rag_pipeline.storage import AccessScope, QdrantVectorStore


class Tokenizer:
    def encode(self, text):
        return text.split()

    def decode(self, tokens):
        return " ".join(tokens)


class FakeEmbeddingProvider:
    class Spec:
        max_batch_size = 2

    spec = Spec()

    def __init__(self):
        self.descriptor = EmbeddingDescriptor("fake", "fake-embed", "a" * 64, 3, True, "test")
        self.calls = []

    def embed(self, texts):
        self.calls.append(tuple(texts))
        return EmbeddingBatch(tuple((1.0, 0.0, 0.0) for _ in texts), self.descriptor)


class IndexingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.processed = self.root / "knowledge_base" / "processed"
        self.raw_dir = self.root / "knowledge_base" / "raw" / "docs"
        self.raw_dir.mkdir(parents=True)
        self.raw_path = self.raw_dir / "guide.md"
        self.raw_path.write_text("# Synthetic Guide\n\nIndexing pipeline uses synthetic content.", encoding="utf-8")
        self.document = {
            "source_id": "docs",
            "source_type": "documentation",
            "source_url": "https://example.org/guide",
            "source_version": "v1",
            "relative_path": "guide.md",
            "local_path": str(self.raw_path),
            "extension": ".md",
            "file_category": "documentation",
            "ingestion_status": "candidate_not_reviewed",
            "discovery_status": "candidate",
            "license_review_status": "approved",
            "sha256": hashlib.sha256(self.raw_path.read_bytes()).hexdigest(),
            "file_size_bytes": self.raw_path.stat().st_size,
            "title": "Synthetic Guide",
        }
        evidence_artifact = self.root / "synthetic-license.txt"
        evidence_artifact.write_text("synthetic license terms", encoding="utf-8")
        evidence_row = {"source_id": "docs", "path": str(evidence_artifact),
                        "sha256": hashlib.sha256(evidence_artifact.read_bytes()).hexdigest()}
        evidence_catalog = self.root / "evidence.jsonl"
        evidence_catalog.write_text(json.dumps(evidence_row) + "\n", encoding="utf-8")
        approval_path = self.root / "source_approvals.json"
        approval_path.write_text(json.dumps({"registry_version": "1.0", "sources": {"docs": {"status": "pending_review"}}}), encoding="utf-8")
        approved_source = decide_source(approval_path, "docs", "approved", "synthetic reviewer",
                                        evidence_catalog, "synthetic approval scope", self.root,
                                        "synthetic test license", "documentation_candidates")
        self.registry = {"registry_version": "1.0", "sources": {"docs": approved_source}}
        self.parsed_run = self.processed / "parse_runs" / "parsed-test"
        self.parsed_run.parent.mkdir(parents=True)
        self.normalized_run = self.processed / "normalized_runs" / "normalized-test"
        run_parsing_job(
            [self.document], self.registry, self.root, self.processed / "parse_runs",
            {".md"}, {"approved"}, run_id="parsed-test",
        )
        normalize_parsed_run(self.parsed_run, self.root, self.normalized_run)
        self.client = QdrantClient(":memory:")
        self.provider = FakeEmbeddingProvider()
        self.store = QdrantVectorStore(
            self.root, "rag_index_test", self.provider.descriptor, "heading-aware-test", client=self.client,
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def run_index(self, registry=None, approval_registry_path=None, dry_run=False, provider=None, tokenizer=None,
                  operator_authorized_unreviewed=False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return index_normalized_run(
                self.normalized_run,
                [self.document],
                registry or self.registry,
                self.root,
                {".md"},
                {"approved"},
                provider or self.provider,
                self.store,
                tokenizer or Tokenizer(),
                "tenant-test",
                ("user:test",),
                approval_registry_path=approval_registry_path,
                strategy="heading_aware",
                chunk_config=ChunkConfig(max_tokens=32, overlap_tokens=0, max_characters=300, overlap_characters=0),
                dry_run=dry_run,
                operator_authorized_unreviewed=operator_authorized_unreviewed,
            )

    def test_authorized_normalized_run_is_rechecked_chunked_embedded_and_indexed(self):
        summary = self.run_index()
        self.assertEqual(summary["indexed_documents"], 1)
        self.assertGreaterEqual(summary["indexed_chunks"], 1)
        self.assertTrue(self.client.collection_exists("rag_index_test"))
        hits = self.store.search([1.0, 0.0, 0.0], AccessScope("tenant-test", ("user:test",), ("docs",)))
        self.assertEqual(len(hits), summary["indexed_chunks"])
        self.assertTrue(all("local_path" not in hit.payload for hit in hits))
        self.assertEqual(hits[0].payload["license_review_status"], "approved")
        self.run_index()
        self.assertEqual(self.client.count("rag_index_test", exact=True).count, summary["indexed_chunks"])

    def test_dry_run_plans_authorized_chunks_without_embeddings_or_vectors(self):
        summary = self.run_index(dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["eligible_documents"], 1)
        self.assertGreaterEqual(summary["planned_chunks"], 1)
        self.assertEqual(summary["indexed_chunks"], 0)
        self.assertEqual(self.provider.calls, [])
        self.assertFalse(self.client.collection_exists("rag_index_test"))

    def test_operator_authorized_dry_run_works_with_pending_source_without_mutating_registry(self):
        pending = json.loads(json.dumps(self.registry))
        pending["sources"]["docs"]["status"] = "pending_review"
        summary = self.run_index(registry=pending, dry_run=True, operator_authorized_unreviewed=True)
        self.assertEqual(summary["authorization_mode"], "operator_authorized_unreviewed")
        self.assertEqual(summary["eligible_documents"], 1)
        self.assertEqual(self.provider.calls, [])
        self.assertFalse(self.client.collection_exists("rag_index_test"))

    def test_operator_authorized_unreviewed_chunks_are_stored_with_truthful_provenance(self):
        pending = json.loads(json.dumps(self.registry))
        pending["sources"]["docs"]["status"] = "pending_review"
        summary = self.run_index(registry=pending, operator_authorized_unreviewed=True)
        self.assertEqual(summary["authorization_mode"], "operator_authorized_unreviewed")
        self.assertGreater(summary["indexed_chunks"], 0)
        points, _ = self.client.scroll("rag_index_test", limit=10, with_payload=True, with_vectors=False)
        self.assertTrue(points)
        self.assertEqual(points[0].payload["license_review_status"], "operator_authorized_unreviewed")
        self.assertEqual(points[0].payload["ingestion_authority"], "explicit_operator_instruction")

    def test_pending_and_rejected_sources_are_blocked_without_embedding(self):
        for source_status in ("pending_review", "rejected"):
            registry_path = self.root / f"source_approvals_{source_status}.json"
            registry = json.loads(json.dumps(self.registry))
            registry["sources"]["docs"]["status"] = source_status
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            summary = self.run_index(approval_registry_path=registry_path)
            self.assertEqual(summary["indexed_documents"], 0)
            self.assertIn(f"blocked:source_{source_status}", summary["status_counts"])
            self.assertEqual(self.provider.calls, [])
            self.assertFalse(self.client.collection_exists("rag_index_test"))

    def test_missing_source_evidence_blocks_indexing(self):
        registry_path = self.root / "source_approvals_missing_evidence.json"
        registry = json.loads(json.dumps(self.registry))
        for field in ("evidence_path", "evidence_sha256", "evidence_catalog", "evidence_record_sha256", "evidence_source_id"):
            registry["sources"]["docs"].pop(field, None)
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing: evidence_path"):
            self.run_index(approval_registry_path=registry_path)
        self.assertEqual(self.provider.calls, [])

    def test_modified_normalized_content_is_not_indexed(self):
        content_path = next((self.normalized_run / "content").glob("*.json"))
        content = json.loads(content_path.read_text(encoding="utf-8"))
        content["segments"][0]["text"] += " tampered"
        content_path.write_text(json.dumps(content), encoding="utf-8")
        summary = self.run_index()
        self.assertEqual(summary["indexed_documents"], 0)
        self.assertIn("normalized_content_integrity_failed", summary["status_counts"])
        self.assertFalse(self.client.collection_exists("rag_index_test"))

    def test_normalized_run_outside_processed_tree_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, "inside knowledge_base/processed"):
            index_normalized_run(
                outside, [self.document], self.registry, self.root, {".md"}, {"approved"},
                self.provider, self.store, Tokenizer(), "tenant", ("user",),
            )

    def test_embedding_dimension_mismatch_fails_before_vector_insertion(self):
        mismatched = FakeEmbeddingProvider()
        mismatched.descriptor = EmbeddingDescriptor("fake", "fake-embed", "a" * 64, 4, True, "test")
        with self.assertRaisesRegex(Exception, "does not match"):
            self.run_index(provider=mismatched)
        self.assertFalse(self.client.collection_exists("rag_index_test"))

    def test_invalid_tokenizer_context_configuration_blocks_indexing(self):
        class TooSmallTokenizer(Tokenizer):
            max_context_tokens = 16
            special_tokens_per_input = 2

            def validate_config(self, config):
                if config.max_tokens + self.special_tokens_per_input > self.max_context_tokens:
                    raise ValueError("configured chunk exceeds tokenizer context")

        with self.assertRaisesRegex(ValueError, "exceeds tokenizer context"):
            self.run_index(tokenizer=TooSmallTokenizer())
        self.assertFalse(self.client.collection_exists("rag_index_test"))


if __name__ == "__main__":
    unittest.main()
