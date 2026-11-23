import json
import tempfile
import unittest
import warnings
from pathlib import Path

from qdrant_client import QdrantClient, models

from src.rag_pipeline.embeddings import EmbeddingDescriptor
from src.rag_pipeline.storage import AccessScope, IndexCompatibilityError, QdrantVectorStore, RetrievalFilters, VectorStoreError


class QdrantVectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.client = QdrantClient(":memory:")
        self.embedding = EmbeddingDescriptor("ollama", "synthetic-embed", "sha256:fixture", 3, True, "0.40.16")
        self.store = QdrantVectorStore(self.root, "rag_chunks_v1", self.embedding, "chunking-v1", client=self.client, batch_size=2)

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def chunk(self, chunk_id="chunk-one", text="A synthetic chunk"):
        return {
            "chunk_id": chunk_id,
            "content_id": "content-one",
            "text": text,
            "segments": [{"text": text, "segment_type": "text", "headings": ["Manual"], "page_number": 2}],
            "heading_paths": [["Manual"]],
            "page_references": [2],
            "parent_chunk_id": None,
        }

    def metadata(self, tenant="tenant-a", source="docs", document="doc-a", principals=None):
        return {
            "tenant_id": tenant,
            "source_id": source,
            "document_id": document,
            "acl_principals": principals or ["user:alice"],
            "license_review_status": "approved",
            "source_type": "documentation",
            "title": "Synthetic manual",
            "content_hash": "sha256:source",
            "document_version": "v1",
            "ingestion_timestamp": "2026-01-01T00:00:00Z",
        }

    def upsert(self, chunk=None, metadata=None, vector=(1.0, 0.0, 0.0)):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            return self.store.upsert_chunks([chunk or self.chunk()], [vector], [metadata or self.metadata()])

    def test_collection_manifest_records_embedding_and_chunk_versions(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.store.ensure_collection()
        self.assertTrue(self.client.collection_exists("rag_chunks_v1"))
        manifest = self.store.manifest_path
        self.assertTrue(manifest.is_file())
        import json
        values = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(values["dimensions"], 3)
        self.assertEqual(values["embedding_model_digest"], "sha256:fixture")
        self.assertEqual(values["chunking_version"], "chunking-v1")

    def test_search_always_filters_tenant_and_acl(self):
        self.upsert(self.chunk("a-alice"), self.metadata(tenant="tenant-a", document="doc-a", principals=["user:alice"]))
        self.upsert(self.chunk("a-bob"), self.metadata(tenant="tenant-a", document="doc-b", principals=["user:bob"]))
        self.upsert(self.chunk("b-alice"), self.metadata(tenant="tenant-b", document="doc-c", principals=["user:alice"]))
        hits = self.store.search([1.0, 0.0, 0.0], AccessScope("tenant-a", ("user:alice",), ("docs",)))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].payload["document_id"], "doc-a")

    def test_search_returns_rank_and_supports_threshold_and_scoped_metadata_filters(self):
        self.upsert(self.chunk("a-one"), self.metadata(source="docs", document="doc-a"), vector=(1.0, 0.0, 0.0))
        self.upsert(self.chunk("b-one"), self.metadata(source="other", document="doc-b"), vector=(0.0, 1.0, 0.0))
        scope = AccessScope("tenant-a", ("user:alice",), ("docs", "other"))
        hits = self.store.search((1.0, 0.0, 0.0), scope, limit=5,
                                 score_threshold=0.5,
                                 filters=RetrievalFilters(source_ids=("docs",), document_ids=("doc-a",)))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].rank, 1)
        self.assertEqual(hits[0].payload["document_id"], "doc-a")
        self.assertEqual(self.store.search((1.0, 0.0, 0.0), scope,
                         filters=RetrievalFilters(source_ids=("not-allowed",))), [])
        with self.assertRaisesRegex(ValueError, "Score threshold"):
            self.store.search((1.0, 0.0, 0.0), scope, score_threshold=2)

    def test_document_deny_filter_excludes_rejected_document(self):
        self.upsert(self.chunk("a-one"), self.metadata(document="doc-a"))
        self.upsert(self.chunk("b-one"), self.metadata(document="doc-b"))
        hits = self.store.search((1.0, 0.0, 0.0), AccessScope("tenant-a", ("user:alice",), ("docs",)),
            filters=RetrievalFilters(excluded_document_ids=("doc-a",)))
        self.assertEqual([item.payload["document_id"] for item in hits], ["doc-b"])

    def test_arxiv_source_requires_an_individually_permitted_document(self):
        self.upsert(self.chunk("docs-one"), self.metadata(source="docs", document="doc-docs"))
        self.upsert(self.chunk("paper-one"), self.metadata(source="arxiv_ai_systems", document="paper-1"))
        scope = AccessScope("tenant-a", ("user:alice",), ("docs", "arxiv_ai_systems"))
        filters = RetrievalFilters(restricted_source_ids=("arxiv_ai_systems",))
        hits = self.store.search((1.0, 0.0, 0.0), scope, limit=5, filters=filters)
        self.assertEqual([item.payload["document_id"] for item in hits], ["doc-docs"])
        allowed = RetrievalFilters(restricted_source_ids=("arxiv_ai_systems",), permitted_document_ids=("paper-1",))
        hits = self.store.search((1.0, 0.0, 0.0), scope, limit=5, filters=allowed)
        self.assertEqual({item.payload["document_id"] for item in hits}, {"doc-docs", "paper-1"})

    def test_unreviewed_search_requires_explicit_flag_and_matching_development_manifest(self):
        metadata = self.metadata()
        metadata["license_review_status"] = "operator_authorized_unreviewed"
        metadata["ingestion_authority"] = "explicit_operator_instruction"
        self.upsert(self.chunk("dev-one"), metadata)
        with self.assertRaisesRegex(VectorStoreError, "explicit operator authorization"):
            self.store.search_development_unreviewed((1.0, 0.0, 0.0), AccessScope("tenant-a", ("user:alice",), ("docs",)))
        readiness_path = Path(self.root) / "knowledge_base" / "metadata" / "index_manifests" / "rag_chunks_v1.json"
        readiness_path.parent.mkdir(parents=True)
        readiness_path.write_text(json.dumps({"collection_name": "rag_chunks_v1", "status": "ready",
                                              "authorization_mode": "operator_authorized_unreviewed"}), encoding="utf-8")
        hits = self.store.search_development_unreviewed(
            (1.0, 0.0, 0.0), AccessScope("tenant-a", ("user:alice",), ("docs",)),
            explicit_operator_authorization=True,
        )
        self.assertEqual([hit.payload["document_id"] for hit in hits], ["doc-a"])

    def test_upsert_is_idempotent_for_same_chunk_id(self):
        self.assertEqual(self.upsert(), 1)
        self.assertEqual(self.upsert(), 1)
        self.assertEqual(self.client.count("rag_chunks_v1", exact=True).count, 1)

    def test_health_check_reports_managed_collection_without_creating_it(self):
        with self.assertRaisesRegex(VectorStoreError, "does not exist"):
            self.store.health_check()
        self.assertFalse(self.client.collection_exists("rag_chunks_v1"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.store.ensure_collection()
        health = self.store.health_check()
        self.assertTrue(health["healthy"])
        self.assertEqual(health["dimensions"], 3)

    def test_document_and_source_deletion_are_tenant_scoped(self):
        self.upsert(self.chunk("a-one"), self.metadata(tenant="tenant-a", source="docs", document="doc-a"))
        self.upsert(self.chunk("b-one"), self.metadata(tenant="tenant-b", source="docs", document="doc-a"))
        self.assertEqual(self.store.delete_document("tenant-a", "doc-a"), 1)
        self.assertEqual(self.client.count("rag_chunks_v1", exact=True).count, 1)
        self.assertEqual(self.store.delete_source("tenant-a", "docs"), 0)
        self.assertEqual(self.store.delete_source("tenant-b", "docs"), 1)
        self.assertEqual(self.client.count("rag_chunks_v1", exact=True).count, 0)

    def test_deletion_requires_explicit_scope(self):
        with self.assertRaises(ValueError):
            self.store.delete_document("", "doc-a")
        with self.assertRaises(ValueError):
            self.store.delete_source("tenant-a", "")

    def test_missing_acl_metadata_and_local_paths_are_rejected(self):
        metadata = self.metadata()
        metadata.pop("acl_principals")
        with self.assertRaisesRegex(ValueError, "access-control"):
            self.upsert(metadata=metadata)
        metadata = self.metadata()
        metadata["local_path"] = "E:\\private\\secret.pdf"
        with self.assertRaisesRegex(ValueError, "Filesystem paths"):
            self.upsert(metadata=metadata)

    def test_dimension_change_is_rejected_by_compatibility_manifest(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.store.ensure_collection()
        changed = EmbeddingDescriptor("ollama", "other-model", "sha256:other", 4, True, "0.40.16")
        incompatible = QdrantVectorStore(self.root, "rag_chunks_v1", changed, "chunking-v1", client=self.client)
        with self.assertRaises(IndexCompatibilityError):
            incompatible.ensure_collection()

    def test_existing_collection_without_manifest_fails_closed(self):
        self.client.create_collection("unmanaged_v1", vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE))
        unmanaged = QdrantVectorStore(self.root, "unmanaged_v1", self.embedding, "chunking-v1", client=self.client)
        with self.assertRaisesRegex(IndexCompatibilityError, "no compatibility manifest"):
            unmanaged.ensure_collection()

    def test_wrong_vector_dimensions_fail_before_collection_creation(self):
        with self.assertRaisesRegex(ValueError, "wrong dimensions"):
            self.upsert(vector=(1.0, 0.0))
        self.assertFalse(self.client.collection_exists("rag_chunks_v1"))

    def test_external_qdrant_addresses_are_rejected(self):
        with self.assertRaises(ValueError):
            QdrantVectorStore(self.root, "rag_chunks_v1", self.embedding, "v1", qdrant_url="http://example.com:6333")

    def test_explicit_private_docker_qdrant_service_url_is_allowed(self):
        store = QdrantVectorStore(self.root, "rag_chunks_v1", self.embedding, "v1", qdrant_url="http://qdrant:6333")
        self.assertEqual(store.qdrant_url, "http://qdrant:6333")
        store.close()

    def test_smoke_collection_is_not_a_valid_production_target(self):
        with self.assertRaises(ValueError):
            QdrantVectorStore(self.root, "rag_pipeline_smoke_test_4d", self.embedding, "v1", client=self.client)

    def test_scope_must_have_tenant_and_principals(self):
        with self.assertRaises(ValueError):
            AccessScope("", ("user:alice",))
        with self.assertRaises(ValueError):
            AccessScope("tenant-a", ())


if __name__ == "__main__":
    unittest.main()
