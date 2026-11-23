from dataclasses import dataclass
import time
from typing import Sequence

from ..embeddings import EmbeddingProvider
from ..storage import AccessScope, QdrantVectorStore, RetrievalFilters, SearchHit


class RetrievalRequestError(ValueError):
    pass


@dataclass(frozen=True)
class DenseRetrievalResult:
    query: str
    hits: tuple[SearchHit, ...]
    embedding_ms: float
    retrieval_ms: float
    total_ms: float


@dataclass
class DenseRetriever:
    embedding_provider: EmbeddingProvider
    vector_store: QdrantVectorStore
    max_query_characters: int = 5000

    def retrieve(self, query: str, scope: AccessScope, limit: int = 10) -> list[SearchHit]:
        return list(self.retrieve_detailed(query, scope, limit=limit).hits)

    def retrieve_detailed(
        self,
        query: str,
        scope: AccessScope,
        limit: int = 10,
        *,
        score_threshold: float | None = None,
        filters: RetrievalFilters | None = None,
        development_unreviewed: bool = False,
        explicit_operator_authorization: bool = False,
    ) -> DenseRetrievalResult:
        if not isinstance(query, str) or not query.strip():
            raise RetrievalRequestError("Query must be non-empty text.")
        normalized = " ".join(query.split())
        if len(normalized) > self.max_query_characters:
            raise RetrievalRequestError("Query exceeds the configured character limit.")
        if not 1 <= limit <= 100:
            raise RetrievalRequestError("Retrieval limit must be between 1 and 100.")
        started = time.perf_counter()
        embedding_started = time.perf_counter()
        try:
            batch = self.embedding_provider.embed([normalized])
        except ValueError as exc:
            raise RetrievalRequestError("Query embedding request was invalid.") from exc
        if len(batch.vectors) != 1:
            raise RetrievalRequestError("Embedding provider returned an invalid query result.")
        embedding_ms = (time.perf_counter() - embedding_started) * 1000
        retrieval_started = time.perf_counter()
        if development_unreviewed:
            if not explicit_operator_authorization:
                raise RetrievalRequestError("Development-unreviewed retrieval requires explicit operator authorization.")
            hits = self.vector_store.search_development_unreviewed(
                batch.vectors[0], scope, limit=limit,
                explicit_operator_authorization=explicit_operator_authorization,
                score_threshold=score_threshold, filters=filters,
            )
        else:
            hits = self.vector_store.search(
                batch.vectors[0], scope, limit=limit,
                score_threshold=score_threshold, filters=filters,
            )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        return DenseRetrievalResult(normalized, tuple(hits), embedding_ms, retrieval_ms,
                                    (time.perf_counter() - started) * 1000)
