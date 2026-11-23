import unittest
from pathlib import Path

from src.rag_pipeline.retrieval import HybridSearchHit, LocalCrossEncoderReranker


def hit(chunk_id, rank, source="docs", document=None):
    return HybridSearchHit(
        point_id=f"p-{chunk_id}", chunk_id=chunk_id, document_id=document or f"d-{chunk_id}",
        source_id=source, payload={"chunk_text": f"passage {chunk_id}"},
        score=1 / (60 + rank), rank=rank, dense_rank=rank, sparse_rank=None,
        dense_score=0.5, sparse_score=None,
    )


class RerankerTests(unittest.TestCase):
    def test_reranks_bounded_candidates_preserving_rrf_and_provenance(self):
        reranker = LocalCrossEncoderReranker(Path("unused"), scorer=lambda q, passages: [0.1, 0.9, 0.5])
        result = reranker.rerank("question", [hit("a", 1), hit("b", 2), hit("c", 3)], limit=2)
        self.assertEqual([item.chunk_id for item in result.hits], ["b", "c"])
        self.assertEqual([item.rank for item in result.hits], [1, 2])
        self.assertEqual(result.hits[0].score, hit("b", 2).score)
        self.assertEqual(result.hits[0].rerank_score, 0.9)
        self.assertEqual(result.hits[0].payload["chunk_text"], "passage b")

    def test_invalid_scores_fail_closed(self):
        reranker = LocalCrossEncoderReranker(Path("unused"), scorer=lambda q, passages: [1.0])
        with self.assertRaises(ValueError):
            reranker.rerank("question", [hit("a", 1), hit("b", 2)])
        reranker.scorer = lambda q, passages: [float("nan"), 0.1]
        with self.assertRaises(ValueError):
            reranker.rerank("question", [hit("a", 1), hit("b", 2)])

    def test_empty_candidates_and_argument_limits(self):
        reranker = LocalCrossEncoderReranker(Path("unused"), scorer=lambda q, passages: [])
        self.assertEqual(reranker.rerank("question", []).hits, ())
        with self.assertRaises(ValueError):
            reranker.rerank(" ", [])
        with self.assertRaises(ValueError):
            reranker.rerank("question", [], limit=0)

    def test_comparison_diversity_promotes_second_document_without_changing_scores(self):
        candidates = [hit("a1", 1, document="a"), hit("a2", 2, document="a"),
                      hit("a3", 3, document="a"), hit("b1", 4, source="other", document="b")]
        reranker = LocalCrossEncoderReranker(Path("unused"),
            scorer=lambda q, passages: [0.99, 0.98, 0.97, 0.70])
        default = reranker.rerank("direct question", candidates, limit=3)
        diverse = reranker.rerank("compare concepts", candidates, limit=3,
            max_per_source=2, max_per_document=1)
        self.assertEqual([item.chunk_id for item in default.hits], ["a1", "a2", "a3"])
        self.assertEqual([item.chunk_id for item in diverse.hits], ["a1", "a2", "b1"])
        self.assertEqual(diverse.hits[0].rerank_score, 0.99)

    def test_comparison_intent_detection(self):
        self.assertTrue(LocalCrossEncoderReranker.is_comparison_query("Compare Docker and Compose behavior"))
        self.assertTrue(LocalCrossEncoderReranker.is_comparison_query("How does X relate to Y?"))
        self.assertFalse(LocalCrossEncoderReranker.is_comparison_query("How does a Docker health check work?"))

    def test_comparison_evidence_requires_named_sources_or_distinct_documents(self):
        aliases = {"pytorch": ("pytorch", "torch"), "huggingface_transformers": ("transformers",)}
        citations = [type("C", (), {"source_id": "huggingface_transformers", "document_id": "d1"})(),
                     type("C", (), {"source_id": "huggingface_transformers", "document_id": "d2"})()]
        self.assertFalse(LocalCrossEncoderReranker.comparison_evidence_complete(
            "Compare PyTorch and Transformers", citations, aliases))
        both_sources = [citations[0], type("C", (), {"source_id": "pytorch", "document_id": "d3"})()]
        self.assertTrue(LocalCrossEncoderReranker.comparison_evidence_complete(
            "Compare PyTorch and Transformers", both_sources, aliases))
        self.assertTrue(LocalCrossEncoderReranker.comparison_evidence_complete(
            "Compare two FastAPI mechanisms", citations, aliases))


if __name__ == "__main__":
    unittest.main()
