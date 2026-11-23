"""Reciprocal-rank fusion over authorized dense and sparse candidate lists."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Sequence

from ..storage import RetrievalFilters, SearchHit
from .dense import DenseRetriever
from .sparse import BM25Retriever, SparseSearchHit


@dataclass(frozen=True)
class HybridSearchHit:
    point_id: str
    chunk_id: str
    document_id: str
    source_id: str
    payload: dict[str, Any]
    score: float
    rank: int
    dense_rank: int | None
    sparse_rank: int | None
    dense_score: float | None
    sparse_score: float | None
    rerank_score: float | None = None


@dataclass(frozen=True)
class HybridRetrievalResult:
    query: str
    hits: tuple[HybridSearchHit, ...]
    embedding_ms: float
    dense_ms: float
    sparse_ms: float
    fusion_ms: float
    total_ms: float
    rrf_constant: int


def reciprocal_rank_fusion(dense_hits: Sequence[SearchHit], sparse_hits: Sequence[SparseSearchHit],
                           limit: int = 10, constant: int = 60) -> tuple[HybridSearchHit, ...]:
    if not 1 <= limit <= 100:
        raise ValueError("Hybrid result limit must be between 1 and 100.")
    if not 1 <= constant <= 1000:
        raise ValueError("RRF constant must be between 1 and 1000.")
    merged: dict[str, dict[str, Any]] = {}
    for family, hits in (("dense", dense_hits), ("sparse", sparse_hits)):
        for ordinal, hit in enumerate(hits, start=1):
            if family == "dense":
                payload = hit.payload
                chunk_id = payload.get("chunk_id")
                rank = hit.rank or ordinal
                point_id = hit.point_id
                score = hit.score
            else:
                payload = hit.payload
                chunk_id = hit.chunk_id
                rank = hit.rank or ordinal
                point_id = hit.point_id
                score = hit.score
            if not isinstance(chunk_id, str) or not chunk_id:
                continue
            item = merged.setdefault(chunk_id, {
                "point_id": point_id, "payload": payload, "score": 0.0,
                "dense_rank": None, "sparse_rank": None, "dense_score": None, "sparse_score": None,
            })
            item["score"] += 1.0 / (constant + rank)
            item[f"{family}_rank"] = rank
            item[f"{family}_score"] = score
            if family == "dense" or not item["payload"]:
                item["payload"] = payload
                item["point_id"] = point_id
    ordered = sorted(merged.items(), key=lambda pair: (-pair[1]["score"], pair[0]))[:limit]
    results = []
    for position, (chunk_id, item) in enumerate(ordered, start=1):
        payload = item["payload"]
        results.append(HybridSearchHit(
            point_id=item["point_id"], chunk_id=chunk_id,
            document_id=str(payload.get("document_id", "")),
            source_id=str(payload.get("source_id", "")), payload=payload,
            score=item["score"], rank=position,
            dense_rank=item["dense_rank"], sparse_rank=item["sparse_rank"],
            dense_score=item["dense_score"], sparse_score=item["sparse_score"],
        ))
    return tuple(results)


@dataclass
class HybridRetriever:
    dense_retriever: DenseRetriever
    sparse_retriever: BM25Retriever
    rrf_constant: int = 60

    def retrieve(self, query: str, scope, limit: int = 10, candidate_limit: int = 30, *,
                 score_threshold: float | None = None, filters: RetrievalFilters | None = None,
                 development_unreviewed: bool = False,
                 explicit_operator_authorization: bool = False) -> HybridRetrievalResult:
        if not 1 <= candidate_limit <= 100:
            raise ValueError("Hybrid candidate limit must be between 1 and 100.")
        started = time.perf_counter()
        dense_result = self.dense_retriever.retrieve_detailed(
            query, scope, candidate_limit, score_threshold=score_threshold, filters=filters,
            development_unreviewed=development_unreviewed,
            explicit_operator_authorization=explicit_operator_authorization,
        )
        dense_ms = dense_result.retrieval_ms
        sparse_result = self.sparse_retriever.search(
            query, scope, candidate_limit, filters=filters,
            development_unreviewed=development_unreviewed,
            explicit_operator_authorization=explicit_operator_authorization,
        )
        sparse_ms = sparse_result.retrieval_ms
        fusion_started = time.perf_counter()
        hits = reciprocal_rank_fusion(dense_result.hits, sparse_result.hits, limit, self.rrf_constant)
        fusion_ms = (time.perf_counter() - fusion_started) * 1000
        return HybridRetrievalResult(
            query=dense_result.query, hits=hits, embedding_ms=dense_result.embedding_ms,
            dense_ms=dense_ms, sparse_ms=sparse_ms, fusion_ms=fusion_ms,
            total_ms=(time.perf_counter() - started) * 1000, rrf_constant=self.rrf_constant,
        )
