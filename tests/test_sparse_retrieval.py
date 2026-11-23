import json
import tempfile
import unittest
import warnings
from pathlib import Path

from qdrant_client import QdrantClient

from src.rag_pipeline.embeddings import EmbeddingDescriptor
from src.rag_pipeline.retrieval import BM25Retriever, SparseIndexError, build_sparse_index, sparse_index_directory
from src.rag_pipeline.storage import AccessScope, QdrantVectorStore, RetrievalFilters


class SparseRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = QdrantClient(":memory:")
        self.store = QdrantVectorStore(self.root, "sparse_test_v1",
            EmbeddingDescriptor("test", "test-model", "sha256:test", 2, True, "test"),
            "chunk-v1", client=self.client)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def add(self, chunk_id, doc_id, text, *, tenant="tenant-a", source="docs", acl=None, status="approved"):
        metadata = {
            "tenant_id": tenant, "source_id": source, "document_id": doc_id,
            "acl_principals": acl or ["alice"], "license_review_status": status,
            "source_type": "documentation", "title": doc_id,
            "content_hash": "sha256:test", "document_version": "v1",
            "ingestion_timestamp": "2026-11-16T00:00:00Z",
        }
        if status == "operator_authorized_unreviewed":
            metadata["ingestion_authority"] = "explicit_operator_instruction"
        chunk = {"chunk_id": chunk_id, "content_id": doc_id, "text": text,
                 "segments": [], "heading_paths": [], "page_references": [], "parent_chunk_id": None}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.store.upsert_chunks([chunk], [(1.0, 0.0)], [metadata])

    def readiness(self, mode="reviewed_source_and_document_approval", count=1):
        return {"index_id": "index-sparse-test", "collection_name": "sparse_test_v1",
                "status": "ready", "authorization_mode": mode, "chunk_count": count}

    def test_build_and_search_bm25_applies_live_authorization_scope(self):
        self.add("c1", "doc-a", "PostgreSQL indexes improve database lookup performance.")
        self.add("c2", "doc-b", "Docker health checks monitor container liveness.", tenant="tenant-b")
        directory = sparse_index_directory(self.root, "index-sparse-test")
        manifest = build_sparse_index(self.store, self.root, self.readiness(count=2), batch_size=1)
        self.assertEqual(manifest["point_count"], 2)
        with BM25Retriever(directory) as retriever:
            result = retriever.search("PostgreSQL database indexes", AccessScope("tenant-a", ("alice",), ("docs",)))
            self.assertEqual(result.hits[0].document_id, "doc-a")
            self.assertGreater(result.hits[0].score, 0)
            self.assertEqual(result.hits[0].rank, 1)
            denied = retriever.search("Docker health checks", AccessScope("tenant-a", ("alice",), ("docs",)))
            self.assertEqual(denied.hits, ())

    def test_sparse_filters_intersect_source_scope_and_apply_document_acl(self):
        self.add("c1", "doc-a", "vector retrieval database index")
        self.add("c2", "doc-b", "vector retrieval database index", source="other")
        self.add("c3", "doc-c", "vector retrieval database index", acl=["bob"])
        manifest = build_sparse_index(self.store, self.root, self.readiness(count=3))
        with BM25Retriever(sparse_index_directory(self.root, manifest["index_id"])) as retriever:
            hits = retriever.search("vector retrieval", AccessScope("tenant-a", ("alice",), ("docs", "other")),
                filters=RetrievalFilters(source_ids=("docs",), document_ids=("doc-a", "doc-b")))
            self.assertEqual([hit.document_id for hit in hits.hits], ["doc-a"])

            denied = retriever.search("vector retrieval", AccessScope("tenant-a", ("alice",), ("docs", "other")),
                filters=RetrievalFilters(excluded_document_ids=("doc-a",)))
            self.assertEqual([hit.document_id for hit in denied.hits], ["doc-b"])

    def test_arxiv_source_requires_an_individually_permitted_document(self):
        self.add("c1", "doc-a", "retrieval systems overview", source="docs")
        self.add("c2", "paper-1", "retrieval systems overview", source="arxiv_ai_systems")
        manifest = build_sparse_index(self.store, self.root, self.readiness(count=2))
        with BM25Retriever(sparse_index_directory(self.root, manifest["index_id"])) as retriever:
            scope = AccessScope("tenant-a", ("alice",), ("docs", "arxiv_ai_systems"))
            denied = retriever.search("retrieval systems", scope,
                filters=RetrievalFilters(restricted_source_ids=("arxiv_ai_systems",)))
            self.assertEqual([hit.document_id for hit in denied.hits], ["doc-a"])
            allowed = retriever.search("retrieval systems", scope,
                filters=RetrievalFilters(restricted_source_ids=("arxiv_ai_systems",), permitted_document_ids=("paper-1",)))
            self.assertEqual({hit.document_id for hit in allowed.hits}, {"doc-a", "paper-1"})

    def test_unreviewed_sparse_access_requires_explicit_operator_authorization(self):
        self.add("c1", "doc-dev", "unreviewed local documentation", status="operator_authorized_unreviewed")
        manifest = build_sparse_index(self.store, self.root, self.readiness("operator_authorized_unreviewed", 1))
        with BM25Retriever(sparse_index_directory(self.root, manifest["index_id"])) as retriever:
            scope = AccessScope("tenant-a", ("alice",), ("docs",))
            with self.assertRaisesRegex(SparseIndexError, "explicit operator"):
                retriever.search("local documentation", scope, development_unreviewed=True)
            result = retriever.search("local documentation", scope, development_unreviewed=True,
                                      explicit_operator_authorization=True)
            self.assertEqual(result.hits[0].document_id, "doc-dev")

    def test_index_checksum_and_query_validation_fail_closed(self):
        self.add("c1", "doc-a", "single synthetic passage")
        manifest = build_sparse_index(self.store, self.root, self.readiness(count=1))
        directory = sparse_index_directory(self.root, manifest["index_id"])
        database = directory / "chunks.sqlite3"
        database.write_bytes(database.read_bytes() + b"tampered")
        with self.assertRaisesRegex(SparseIndexError, "checksum"):
            BM25Retriever(directory)
        with self.assertRaises(ValueError):
            sparse_index_directory(self.root, "..\\outside")


if __name__ == "__main__":
    unittest.main()
