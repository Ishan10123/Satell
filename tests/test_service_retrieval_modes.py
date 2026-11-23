import unittest
from types import SimpleNamespace

from src.rag_pipeline.generation import GenerationResult
from pathlib import Path
from src.rag_pipeline.retrieval import ContextAssembler, HybridSearchHit, LocalCrossEncoderReranker, RerankResult
from src.rag_pipeline.generation import CitationValidationError
from src.rag_pipeline.service import LocalRAGService
from src.rag_pipeline.storage import AccessScope, SearchHit


class DenseStub:
    embedding_provider = None
    vector_store = None


class GeneratorStub:
    calls = 0
    def generate(self, query, context):
        self.calls += 1
        return GenerationResult("Supported [S1]", ("S1",), "stub", "test", 1.0)


def hit(chunk_id="c1"):
    payload = {
        "chunk_id": chunk_id, "document_id": "doc", "source_id": "docs",
        "chunk_text": "The documented answer is here.", "title": "Reference",
        "tenant_id": "tenant", "acl_principals": ["reader"], "license_review_status": "approved",
        "page_references": [], "source_reference": "https://docs.example/guide",
    }
    return HybridSearchHit("p1", chunk_id, "doc", "docs", payload, 0.03, 1, 1, 1, 0.8, 2.0)


class ServiceRetrievalModeTests(unittest.TestCase):
    def test_hybrid_rerank_mode_retrieves_bounded_candidates_then_assembles_context(self):
        class HybridStub:
            def retrieve(self, query, scope, limit, candidate_limit, filters=None):
                self.args = (query, limit, candidate_limit)
                return SimpleNamespace(hits=(hit(),), query=query, embedding_ms=1.0,
                    dense_ms=2.0, sparse_ms=3.0, fusion_ms=0.1)

        class RerankerStub:
            def rerank(self, query, hits, limit):
                self.args = (query, len(hits), limit)
                return RerankResult(tuple(hits[:limit]), 2.5, "stub-reranker")

        hybrid, reranker = HybridStub(), RerankerStub()
        service = LocalRAGService(DenseStub(), ContextAssembler(), GeneratorStub(), retrieval_limit=5,
            retrieval_mode="hybrid_rerank", hybrid_retriever=hybrid, reranker=reranker, candidate_limit=20)
        answer = service.answer("question", AccessScope("tenant", ("reader",), ("docs",)), limit=3)
        self.assertEqual(hybrid.args, ("question", 20, 20))
        self.assertEqual(reranker.args, ("question", 1, 3))
        self.assertEqual(answer.citations[0]["citation_id"], "S1")
        self.assertEqual(answer.retrieved_count, 1)
        self.assertIn("rerank", answer.retrieval)

    def test_hybrid_modes_require_dependencies_and_valid_candidate_bound(self):
        with self.assertRaises(ValueError):
            LocalRAGService(DenseStub(), ContextAssembler(), GeneratorStub(), retrieval_mode="hybrid")
        with self.assertRaises(ValueError):
            LocalRAGService(DenseStub(), ContextAssembler(), GeneratorStub(), retrieval_mode="hybrid_rerank",
                            hybrid_retriever=object())

    def test_comparison_abstains_when_a_named_source_is_missing_after_auth_recheck(self):
        first = hit("c1")
        first = HybridSearchHit(first.point_id, first.chunk_id, "doc-1", "huggingface_transformers",
            {**first.payload, "document_id": "doc-1", "source_id": "huggingface_transformers"},
            first.score, first.rank, first.dense_rank, first.sparse_rank, first.dense_score, first.sparse_score)
        second = HybridSearchHit(first.point_id, "c2", "doc-2", "huggingface_transformers",
            {**first.payload, "chunk_id": "c2", "document_id": "doc-2"}, first.score, 2, 2, 2, 0.7, 0.5)

        class HybridStub:
            def retrieve(self, query, scope, limit, candidate_limit, filters=None):
                return SimpleNamespace(hits=(first, second), query=query, embedding_ms=1.0,
                    dense_ms=2.0, sparse_ms=3.0, fusion_ms=0.1)

        generator = GeneratorStub()
        reranker = LocalCrossEncoderReranker(Path("unused"), scorer=lambda _q, passages: [1.0, 0.9])
        service = LocalRAGService(DenseStub(), ContextAssembler(), generator, retrieval_limit=5,
            retrieval_mode="hybrid_rerank", hybrid_retriever=HybridStub(), reranker=reranker,
            candidate_limit=20, comparison_source_aliases={
                "pytorch": ("pytorch", "torch"), "huggingface_transformers": ("transformers",)})
        result = service.answer("Compare PyTorch and Transformers", AccessScope(
            "tenant", ("reader",), ("huggingface_transformers", "pytorch")), limit=2)
        self.assertFalse(result.citations)
        self.assertEqual(generator.calls, 0)

    def test_invalid_generated_citation_becomes_fail_closed_abstention(self):
        class HybridStub:
            def retrieve(self, query, scope, limit, candidate_limit, filters=None):
                return SimpleNamespace(hits=(hit(),), query=query, embedding_ms=1.0,
                    dense_ms=2.0, sparse_ms=3.0, fusion_ms=0.1)

        class InvalidCitationGenerator:
            def generate(self, query, context):
                raise CitationValidationError("invalid citation")

        class RerankerStub:
            def rerank(self, query, hits, limit):
                return RerankResult(tuple(hits[:limit]), 1.0, "stub")

        service = LocalRAGService(DenseStub(), ContextAssembler(), InvalidCitationGenerator(),
            retrieval_mode="hybrid_rerank", hybrid_retriever=HybridStub(), reranker=RerankerStub(),
            candidate_limit=10)
        result = service.answer("question", AccessScope("tenant", ("reader",), ("docs",)))
        self.assertEqual(result.answer, "I cannot answer from the approved sources available to you.")
        self.assertFalse(result.citations)
        self.assertEqual(result.timings_ms["answer_validation_rejected"], 1.0)


if __name__ == "__main__":
    unittest.main()
