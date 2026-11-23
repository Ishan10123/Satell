import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.rag_pipeline.embeddings import EmbeddingDescriptor
from src.rag_pipeline.ingestion.approval_workflow import decide_document, decide_source, validate_record
from src.rag_pipeline.ingestion.approval_workflow import load_approval_paths
from src.rag_pipeline.storage import QdrantVectorStore
from src.rag_pipeline.storage.index_manifest import validate_index_manifest, write_index_manifest


class ApprovalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.artifact = self.root / "synthetic-license.txt"
        self.artifact.write_text("synthetic license terms", encoding="utf-8")
        self.source_id = "arxiv_synthetic"
        self.document_id = "a" * 64
        self.catalog = self.root / "evidence.jsonl"
        common = {"source_id": self.source_id, "path": str(self.artifact),
                  "sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}
        rows = [{**common}, {**common, "document_id": self.document_id}]
        self.catalog.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        self.source_registry = self.root / "sources.json"
        self.source_registry.write_text(json.dumps({"registry_version": "1.0", "sources": {self.source_id: {"status": "pending_review"}}}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_source_and_document_decisions_are_explicit_and_evidence_bound(self):
        source = decide_source(self.source_registry, self.source_id, "approved", "reviewer",
                               self.catalog, "source provenance reviewed", self.root, "arXiv terms",
                               "paper_source_metadata_only")
        self.assertEqual(source["status"], "approved")
        self.assertTrue(validate_record(source, self.source_id, self.root))
        doc_path = self.root / "documents.json"
        record = decide_document(doc_path, self.document_id, self.source_id, "approved", "reviewer",
                                 self.catalog, "paper license reviewed individually", self.root, "CC BY 4.0")
        self.assertTrue(validate_record(record, self.source_id, self.root, self.document_id))
        self.assertEqual(record["license_name"], "CC BY 4.0")

    def test_wrong_document_and_changed_evidence_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "expected document_id"):
            decide_document(self.root / "documents.json", "b" * 64, self.source_id, "approved", "reviewer",
                            self.catalog, "wrong paper", self.root, "CC BY 4.0")
        self.artifact.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "checksum"):
            decide_source(self.source_registry, self.source_id, "approved", "reviewer",
                          self.catalog, "changed evidence", self.root, "license", "paper_source_metadata_only")

    def test_wrong_source_and_missing_evidence_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "does not explicitly identify source"):
            decide_source(self.source_registry, "other_source", "approved", "reviewer",
                          self.catalog, "wrong source", self.root, "license", "documentation_candidates")
        with self.assertRaises(FileNotFoundError):
            decide_source(self.source_registry, self.source_id, "approved", "reviewer",
                          self.root / "missing-evidence.jsonl", "missing evidence", self.root,
                          "license", "paper_source_metadata_only")

    def test_evidence_symlink_escape_fails_closed(self):
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir) / "outside-license.txt"
            outside.write_text("external license", encoding="utf-8")
            link = self.root / "linked-license.txt"
            try:
                link.symlink_to(outside, target_is_directory=False)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlink creation unavailable in this Windows environment: {type(exc).__name__}")
            row = {"source_id": self.source_id, "path": str(link),
                   "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()}
            self.catalog.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "project-local"):
                decide_source(self.source_registry, self.source_id, "approved", "reviewer",
                    self.catalog, "external evidence must be rejected", self.root,
                    "license", "paper_source_metadata_only")

    def test_approval_config_paths_are_project_local(self):
        paths = load_approval_paths(Path(__file__).resolve().parents[1])
        self.assertTrue(paths["source_registry"].is_relative_to(Path(__file__).resolve().parents[1]))


class IndexManifestTests(unittest.TestCase):
    def test_manifest_must_match_a_real_collection_and_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            descriptor = EmbeddingDescriptor("synthetic", "synthetic-model", "a" * 64, 3, True, "test")
            store = QdrantVectorStore(root, "rag_manifest_test", descriptor, "chunk-v1", client=__import__("qdrant_client").QdrantClient(":memory:"))
            try:
                store.ensure_collection()
                store.upsert_chunks(
                    [{"chunk_id": "chunk-1", "content_id": "content-1", "text": "synthetic chunk", "segments": [0]}],
                    [[1.0, 0.0, 0.0]],
                    [{"tenant_id": "tenant", "source_id": "docs", "document_id": "doc", "acl_principals": ["user"], "license_review_status": "approved"}],
                )
                tokenizer = type("Tokenizer", (), {"identifier": "synthetic@v1", "runtime_version": "1", "sha256": "b" * 64})()
                source_manifest = root / "inventory.jsonl"
                source_manifest.write_text("synthetic inventory\n", encoding="utf-8")
                write_index_manifest(root, index_id="synthetic-index", vector_store=store, tokenizer=tokenizer,
                    chunking_config={"version": "chunk-v1"}, source_ids=["docs"], document_count=1, chunk_count=1,
                    source_manifest_sha256=hashlib.sha256(source_manifest.read_bytes()).hexdigest(), status="ready")
                self.assertEqual(validate_index_manifest(store, root, tokenizer, {"version": "chunk-v1"}, source_manifest)["status"], "ready")
                source_manifest.write_text("changed inventory\n", encoding="utf-8")
                with self.assertRaisesRegex(Exception, "inventory checksum"):
                    validate_index_manifest(store, root, tokenizer, {"version": "chunk-v1"}, source_manifest)
                store.embedding = EmbeddingDescriptor("synthetic", "different-model", "d" * 64, 3, True, "test")
                with self.assertRaisesRegex(Exception, "does not match"):
                    validate_index_manifest(store, root)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
