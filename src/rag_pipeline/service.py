from dataclasses import dataclass
from dataclasses import field
from collections import Counter
import time
from typing import Mapping

from .generation import (CitationValidationError, ClaimConsistencyError, GenerationError, GenerationResult,
                         OllamaGenerator, UncitedClaimError)
from .retrieval import (ContextAssembler, DenseRetrievalResult, DenseRetriever, HybridRetriever,
                        LocalCrossEncoderReranker, RetrievalRequestError)
from .storage import AccessScope, RetrievalFilters


ABSTENTION = "I cannot answer from the approved sources available to you."


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    citations: tuple[dict[str, object], ...]
    retrieved_count: int
    generation: GenerationResult | None
    retrieval: object | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    generation_error: GenerationError | None = None
    verification_status: str = "abstained"
    diagnostics: dict[str, object] = field(default_factory=dict)


class LocalRAGService:
    """Orchestrate dense retrieval, authorization recheck, context assembly and local generation."""

    def __init__(
        self,
        retriever: DenseRetriever,
        context_assembler: ContextAssembler,
        generator: OllamaGenerator,
        retrieval_limit: int = 8,
        retrieval_mode: str = "dense",
        hybrid_retriever: HybridRetriever | None = None,
        reranker: LocalCrossEncoderReranker | None = None,
        candidate_limit: int = 30,
        comparison_source_cap: int = 4,
        comparison_document_cap: int = 2,
        comparison_diversity_enabled: bool = True,
        comparison_terms: tuple[str, ...] = ("compare", "comparison", "contrast", "difference", "differ", "versus", "vs", "between", "relate", "relationship"),
        comparison_context_group_budget_tokens: int = 1200,
        comparison_source_aliases: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        if not 1 <= retrieval_limit <= 100:
            raise ValueError("Retrieval limit must be between 1 and 100.")
        if retrieval_mode not in {"dense", "hybrid", "hybrid_rerank"}:
            raise ValueError("Retrieval mode must be dense, hybrid, or hybrid_rerank.")
        if retrieval_mode != "dense" and hybrid_retriever is None:
            raise ValueError("Hybrid retrieval mode requires a hybrid retriever.")
        if retrieval_mode == "hybrid_rerank" and reranker is None:
            raise ValueError("hybrid_rerank mode requires a reranker.")
        if not retrieval_limit <= candidate_limit <= 100:
            raise ValueError("Candidate limit must be between retrieval_limit and 100.")
        if comparison_source_cap < 1 or comparison_document_cap < 1 or comparison_context_group_budget_tokens < 1:
            raise ValueError("Comparison diversity caps must be positive.")
        self.retriever = retriever
        self.context_assembler = context_assembler
        self.generator = generator
        self.retrieval_limit = retrieval_limit
        self.retrieval_mode = retrieval_mode
        self.hybrid_retriever = hybrid_retriever
        self.reranker = reranker
        self.candidate_limit = candidate_limit
        self.comparison_source_cap = comparison_source_cap
        self.comparison_document_cap = comparison_document_cap
        self.comparison_diversity_enabled = comparison_diversity_enabled
        self.comparison_terms = comparison_terms
        self.comparison_context_group_budget_tokens = comparison_context_group_budget_tokens
        self.comparison_source_aliases = comparison_source_aliases or {}

    def answer(self, query: str, scope: AccessScope, limit: int | None = None,
               excluded_document_ids: tuple[str, ...] = (),
               restricted_source_ids: tuple[str, ...] = (),
               permitted_document_ids: tuple[str, ...] = (),
               permitted_document_metadata: Mapping[str, Mapping[str, str]] | None = None,
               development_unreviewed: bool = False,
               explicit_operator_authorization: bool = False,
               response_style: str = "natural") -> RAGAnswer:
        if response_style not in {"natural", "concise", "detailed"}:
            raise RetrievalRequestError("Response style is unsupported.")
        if development_unreviewed and explicit_operator_authorization is not True:
            raise RetrievalRequestError("Development-unreviewed retrieval requires explicit operator authorization.")
        if not scope.allowed_source_ids:
            return RAGAnswer(ABSTENTION, (), 0, None)
        selected_limit = self.retrieval_limit if limit is None else limit
        if not 1 <= selected_limit <= 100:
            raise RetrievalRequestError("Retrieval limit must be between 1 and 100.")
        development_options = ({"development_unreviewed": True,
                                "explicit_operator_authorization": True}
                               if development_unreviewed else {})
        if self.retrieval_mode == "dense":
            retrieval = self.retriever.retrieve_detailed(query, scope, limit=selected_limit,
                filters=RetrievalFilters(excluded_document_ids=excluded_document_ids,
                    restricted_source_ids=restricted_source_ids, permitted_document_ids=permitted_document_ids,
                    source_types=("documentation",) if development_unreviewed else ()),
                **development_options)
            hits = retrieval.hits
            timings = {"embedding": retrieval.embedding_ms, "dense_search": retrieval.retrieval_ms}
        else:
            retrieval = self.hybrid_retriever.retrieve(
                query, scope, limit=(self.candidate_limit if self.retrieval_mode == "hybrid_rerank" else selected_limit),
                candidate_limit=self.candidate_limit,
                filters=RetrievalFilters(excluded_document_ids=excluded_document_ids,
                    restricted_source_ids=restricted_source_ids, permitted_document_ids=permitted_document_ids,
                    source_types=("documentation",) if development_unreviewed else ()),
                **development_options,
            )
            hits = retrieval.hits
            timings = {"embedding": retrieval.embedding_ms, "dense_search": retrieval.dense_ms,
                       "sparse_search": retrieval.sparse_ms, "fusion": retrieval.fusion_ms}
            if self.retrieval_mode == "hybrid_rerank":
                diversity = (self.comparison_diversity_enabled
                             and LocalCrossEncoderReranker.is_comparison_query(query, self.comparison_terms))
                if diversity:
                    reranked = self.reranker.rerank(query, hits, selected_limit,
                        max_per_source=self.comparison_source_cap,
                        max_per_document=self.comparison_document_cap)
                else:
                    reranked = self.reranker.rerank(query, hits, selected_limit)
                hits = reranked.hits
                timings["rerank"] = reranked.elapsed_ms
                retrieval = {"hybrid": retrieval, "rerank": reranked}
        context_started = time.perf_counter()
        budget_factory = getattr(self.generator, "context_budget_for", None)
        if callable(budget_factory):
            context_budget = (budget_factory(query) if response_style == "natural" else
                              budget_factory(query, response_style=response_style))
        else:
            context_budget = None
        comparison_query = (self.comparison_diversity_enabled
            and LocalCrossEncoderReranker.is_comparison_query(query, self.comparison_terms))
        context = self.context_assembler.assemble(hits, scope, excluded_document_ids,
                                                development_unreviewed=development_unreviewed,
                                                explicit_operator_authorization=explicit_operator_authorization,
                                                permitted_document_ids=permitted_document_ids,
                                                permitted_document_metadata=permitted_document_metadata,
                                                max_budget=context_budget,
                                                max_tokens_per_document_group=(
                                                    self.comparison_context_group_budget_tokens
                                                    if comparison_query else None))
        timings["context"] = (time.perf_counter() - context_started) * 1000
        diagnostics = self._diagnostics(retrieval, context)
        if not context.citations:
            return RAGAnswer(ABSTENTION, (), len(hits), None, retrieval, timings,
                             verification_status="abstained", diagnostics=diagnostics)
        if (comparison_query and not LocalCrossEncoderReranker.comparison_evidence_complete(
                query, context.citations, self.comparison_source_aliases)):
            return RAGAnswer(ABSTENTION, (), len(hits), None, retrieval, timings,
                             verification_status="abstained", diagnostics=diagnostics)
        try:
            generated = (self.generator.generate(query, context) if response_style == "natural" else
                         self.generator.generate(query, context, response_style=response_style))
        except (CitationValidationError, UncitedClaimError, ClaimConsistencyError) as exc:
            timings["answer_validation_rejected"] = 1.0
            if exc.answer_generation_ms is not None:
                timings["answer_generation"] = exc.answer_generation_ms
            if exc.total_generation_ms is not None:
                timings["generation_pipeline"] = exc.total_generation_ms
            return RAGAnswer(ABSTENTION, (), len(hits), None, retrieval, timings,
                             generation_error=exc, verification_status="failed",
                             diagnostics={**diagnostics,
                                "citation_validation_status": ("passed" if isinstance(exc, ClaimConsistencyError) else "rejected"),
                                "claim_verifier_status": ("rejected"
                                                          if isinstance(exc, ClaimConsistencyError) else "not_run"),
                                "failure_code": exc.error_code,
                                "failure_stage": exc.error_stage,
                                "failure_reason": exc.failure_reason})
        except GenerationError as exc:
            # Fail closed. Do not return an uncited or partially validated model response.
            exc.rag_diagnostics = diagnostics
            exc.rag_timings_ms = timings
            raise
        timings["generation"] = generated.elapsed_ms
        if generated.answer_generation_ms is not None:
            timings["answer_generation"] = generated.answer_generation_ms
        if generated.claim_verification_ms is not None:
            timings["claim_verification"] = generated.claim_verification_ms
        if generated.total_generation_ms is not None:
            timings["generation_pipeline"] = generated.total_generation_ms
        diagnostics = {
            **diagnostics,
            "generation_model": generated.model_name,
            "verification_model": generated.verification_model or generated.model_name,
            "claim_count": generated.claim_count,
            "supported_claim_count": generated.supported_claim_count,
            "rejected_claim_count": generated.rejected_claim_count,
            "prompt_tokens_estimated": generated.prompt_tokens_estimated,
            "citation_validation_status": "passed" if generated.citations else "not_applicable",
            "claim_verifier_status": (
                "not_run" if generated.claim_verification_ms is None else
                "partially_verified" if generated.rejected_claim_count else
                "verified" if generated.supported_claim_count else "rejected"
            ),
        }
        if generated.abstained:
            return RAGAnswer(ABSTENTION, (), len(hits), generated, retrieval, timings,
                             verification_status="abstained", diagnostics=diagnostics)
        citations_by_id = {citation.citation_id: citation for citation in context.citations}
        citations = tuple({
            "citation_id": citations_by_id[citation_id].citation_id,
            "source_id": citations_by_id[citation_id].source_id,
            "document_id": citations_by_id[citation_id].document_id,
            "chunk_id": citations_by_id[citation_id].chunk_id,
            "title": citations_by_id[citation_id].title,
            "page_references": citations_by_id[citation_id].page_references,
            "section": citations_by_id[citation_id].section,
            "source_reference": citations_by_id[citation_id].source_reference,
        } for citation_id in generated.citations)
        verification_status = ("partially_verified" if generated.rejected_claim_count else "verified")
        return RAGAnswer(generated.answer, citations, len(hits), generated, retrieval, timings,
                         verification_status=verification_status, diagnostics=diagnostics)

    def _diagnostics(self, retrieval: object, context: object) -> dict[str, object]:
        """Return bounded metadata only; never include retrieved passage text."""
        result = retrieval
        if isinstance(retrieval, dict):
            result = retrieval.get("rerank") or retrieval.get("hybrid") or retrieval
        hit_rows = []
        for hit in tuple(getattr(result, "hits", ()) or ())[:20]:
            payload = getattr(hit, "payload", {})
            if not isinstance(payload, dict):
                payload = {}
            score = getattr(hit, "score", None)
            row: dict[str, object] = {
                "document_id": payload.get("document_id", getattr(hit, "document_id", "")),
                "source_id": payload.get("source_id", getattr(hit, "source_id", "")),
                "chunk_id": payload.get("chunk_id", getattr(hit, "chunk_id", "")),
                "score": score,
            }
            for name in ("dense_score", "sparse_score", "rerank_score", "rank", "dense_rank", "sparse_rank"):
                value = getattr(hit, name, None)
                if value is not None:
                    row[name] = value
            hit_rows.append(row)
        context_text = getattr(context, "text", "")
        allowed_reasons = {
            "authorization_recheck", "document_not_in_demo_allowlist", "document_identity_mismatch",
            "invalid_chunk_metadata", "empty_passage", "duplicate_chunk_id", "max_chunks",
            "duplicate_passage_text", "context_budget",
        }
        exclusion_counts = Counter(
            reason for reason in getattr(context, "omitted_reasons", ())
            if isinstance(reason, str) and reason in allowed_reasons
        )
        return {
            "retrieval_strategy": self.retrieval_mode,
            "retrieval_hits": hit_rows,
            "retrieval_hit_count": len(tuple(getattr(result, "hits", ()) or ())),
            "reranker_active": self.retrieval_mode == "hybrid_rerank",
            "context_bytes": len(context_text.encode("utf-8")) if isinstance(context_text, str) else 0,
            "context_token_estimate": getattr(context, "budget_used", 0),
            "context_chunk_count": len(getattr(context, "included_chunk_ids", ()) or ()),
            "context_chunk_ids": list(getattr(context, "included_chunk_ids", ()) or ())[:8],
            "context_exclusion_count": getattr(context, "omitted_count", 0),
            "context_exclusion_reasons": dict(exclusion_counts),
            "context_exclusion_details": [
                {"chunk_id": chunk_id, "reason": reason}
                for chunk_id, reason in tuple(getattr(context, "omitted_passages", ()) or ())[:30]
                if reason in allowed_reasons
            ],
            "citation_validation_status": "not_applicable",
            "claim_verifier_status": "not_run",
        }

    def close(self) -> None:
        """Close owned retrieval and generation resources during API shutdown."""
        if self.hybrid_retriever is not None:
            self.hybrid_retriever.sparse_retriever.close()
        for client in (self.generator, self.retriever.embedding_provider, self.retriever.vector_store):
            close = getattr(client, "close", None)
            if callable(close):
                close()
