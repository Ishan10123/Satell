import unittest

from src.rag_pipeline.retrieval import reciprocal_rank_fusion
from src.rag_pipeline.storage import SearchHit
from src.rag_pipeline.retrieval.sparse import SparseSearchHit


def sparse_hit(chunk_id, document_id, source_id, rank):
    return SparseSearchHit(
        point_id=f"point-{chunk_id}", chunk_id=chunk_id, document_id=document_id,
        source_id=source_id, score=10.0 / rank, rank=rank, title="Title",
        chunk_text="passage", source_reference="https://docs.example/page",
        content_id=document_id, heading_paths=(("Guide",),), page_references=(2,),
        tenant_id="tenant", acl_principals=("alice",), license_review_status="approved",
        source_type="documentation",
    )


class HybridRetrievalTests(unittest.TestCase):
    def test_rrf_fuses_ranks_deduplicates_chunks_and_preserves_component_ranks(self):
        dense = [
            SearchHit("point-a", 0.8, {"chunk_id": "a", "document_id": "doc-a", "source_id": "docs"}, 2),
            SearchHit("point-b", 0.9, {"chunk_id": "b", "document_id": "doc-b", "source_id": "docs"}, 1),
        ]
        sparse = [sparse_hit("a", "doc-a", "docs", 1), sparse_hit("c", "doc-c", "docs", 2)]
        fused = reciprocal_rank_fusion(dense, sparse, limit=3, constant=60)
        self.assertEqual([hit.chunk_id for hit in fused], ["a", "b", "c"])
        self.assertEqual(fused[0].dense_rank, 2)
        self.assertEqual(fused[0].sparse_rank, 1)
        self.assertAlmostEqual(fused[0].score, (1 / 62) + (1 / 61))
        self.assertEqual(fused[1].dense_rank, 1)
        self.assertIsNone(fused[1].sparse_rank)
        self.assertEqual(fused[2].payload["page_references"], [2])

    def test_rrf_validates_limits_and_constant(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], [], limit=0)
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], [], constant=0)


if __name__ == "__main__":
    unittest.main()
