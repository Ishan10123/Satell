import unittest

from src.rag_pipeline.embeddings import EmbeddingBatch, EmbeddingDescriptor
from src.rag_pipeline.retrieval import DenseRetriever, RetrievalRequestError
from src.rag_pipeline.storage import AccessScope, SearchHit


class EmbeddingStub:
    def __init__(self, vectors=((1.0, 0.0),)):
        self.vectors = vectors

    def embed(self, texts):
        return EmbeddingBatch(self.vectors, EmbeddingDescriptor("test", "test", None, 2, False, None))


class StoreStub:
    def __init__(self):
        self.args = None

    def search(self, vector, scope, limit=10, *, score_threshold=None, filters=None):
        self.args = (vector, scope, limit, score_threshold, filters)
        return [SearchHit("point", 0.8, {"chunk_id": "chunk"}, 1)]

    def search_development_unreviewed(self, vector, scope, limit=10, *, explicit_operator_authorization=False,
                                      score_threshold=None, filters=None):
        if not explicit_operator_authorization:
            raise ValueError("authorization required")
        self.args = (vector, scope, limit, score_threshold, filters, explicit_operator_authorization)
        return [SearchHit("point", 0.8, {"chunk_id": "chunk"}, 1)]


class DenseRetrieverTests(unittest.TestCase):
    def test_detailed_retrieval_preserves_rank_and_stage_timings(self):
        store = StoreStub()
        result = DenseRetriever(EmbeddingStub(), store).retrieve_detailed(
            "  example   query ", AccessScope("tenant", ("user",), ("docs",)),
            limit=4, score_threshold=0.25,
        )
        self.assertEqual(result.query, "example query")
        self.assertEqual(result.hits[0].rank, 1)
        self.assertEqual(store.args[2], 4)
        self.assertEqual(store.args[3], 0.25)
        self.assertGreaterEqual(result.total_ms, result.embedding_ms)
        self.assertGreaterEqual(result.total_ms, result.retrieval_ms)

    def test_invalid_queries_limits_and_embedding_shapes_fail_explicitly(self):
        retriever = DenseRetriever(EmbeddingStub(vectors=()), StoreStub())
        with self.assertRaisesRegex(RetrievalRequestError, "non-empty"):
            retriever.retrieve("  ", AccessScope("tenant", ("user",), ("docs",)))
        with self.assertRaisesRegex(RetrievalRequestError, "limit"):
            DenseRetriever(EmbeddingStub(), StoreStub()).retrieve("q", AccessScope("tenant", ("user",), ("docs",)), 0)
        with self.assertRaisesRegex(RetrievalRequestError, "invalid query result"):
            retriever.retrieve("q", AccessScope("tenant", ("user",), ("docs",)))

    def test_default_query_boundary_accepts_5000_and_rejects_5001_without_truncation(self):
        store = StoreStub()
        retriever = DenseRetriever(EmbeddingStub(), store)
        prompt = "x" * 5000
        result = retriever.retrieve_detailed(prompt, AccessScope("tenant", ("user",), ("docs",)))
        self.assertEqual(result.query, prompt)
        self.assertEqual(store.args[0], (1.0, 0.0))
        with self.assertRaisesRegex(RetrievalRequestError, "character limit"):
            retriever.retrieve_detailed("x" * 5001, AccessScope("tenant", ("user",), ("docs",)))

    def test_development_mode_requires_explicit_operator_authorization(self):
        retriever = DenseRetriever(EmbeddingStub(), StoreStub())
        scope = AccessScope("tenant", ("user",), ("docs",))
        with self.assertRaisesRegex(RetrievalRequestError, "explicit operator"):
            retriever.retrieve_detailed("q", scope, development_unreviewed=True)
        result = retriever.retrieve_detailed("q", scope, development_unreviewed=True,
                                             explicit_operator_authorization=True)
        self.assertEqual(result.hits[0].payload["chunk_id"], "chunk")


if __name__ == "__main__":
    unittest.main()
