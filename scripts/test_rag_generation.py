"""Run a local, unreviewed-corpus RAG diagnostic (read-only, operator gated)."""
import argparse
import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.configuration import load_chunking_components, load_embedding_provider, load_generator  # noqa: E402
from rag_pipeline.embeddings import EmbeddingDescriptor  # noqa: E402
from rag_pipeline.generation import GenerationError  # noqa: E402
from rag_pipeline.retrieval import (BM25Retriever, ContextAssembler, DenseRetriever, HybridRetriever,
                                    LocalCrossEncoderReranker, sparse_index_directory)  # noqa: E402
from rag_pipeline.service import ABSTENTION  # noqa: E402
from rag_pipeline.storage import AccessScope, QdrantVectorStore  # noqa: E402
from rag_pipeline.storage.index_manifest import validate_index_manifest  # noqa: E402


def read_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("Question rows must be JSON objects.")
                yield value


def classify_generation_error(exc: GenerationError) -> dict[str, object]:
    """Return stable, sanitized diagnostics without exception text or payloads."""
    cause = exc.__cause__
    verification_error = getattr(exc, "error_stage", "") == "claim_verification"
    status = (getattr(exc, "verification_http_status", None) if verification_error
              else getattr(exc, "generation_http_status", None))
    if status is None:
        status = getattr(exc, "http_status", None)
    return {
        "error_code": getattr(exc, "error_code", "generation_error"),
        "claim_count": getattr(exc, "claim_count", None),
        "error_type": type(exc).__name__,
        "error_stage": getattr(exc, "error_stage", "generation"),
        "error_message": getattr(exc, "safe_message", "Local generation failed."),
        "original_cause_type": type(cause).__name__ if cause is not None else None,
        "generation_duration_ms": getattr(exc, "answer_generation_ms", None),
        "verification_duration_ms": getattr(exc, "claim_verification_ms", None),
        "retry_count": (getattr(exc, "generation_retry_count", 0)
                        + getattr(exc, "verification_retry_count", 0)),
        "generation_retry_count": getattr(exc, "generation_retry_count", 0),
        "verification_retry_count": getattr(exc, "verification_retry_count", 0),
        "http_status": status,
        "generation_http_status": getattr(exc, "generation_http_status", None),
        "verification_http_status": getattr(exc, "verification_http_status", None),
        "generation_pipeline_duration_ms": getattr(exc, "total_generation_ms", None),
        "verification_done_reason": getattr(exc, "verification_done_reason", None),
        "verification_eval_count": getattr(exc, "verification_eval_count", None),
        "verification_prompt_eval_count": getattr(exc, "verification_prompt_eval_count", None),
        "verification_response_chars": getattr(exc, "verification_response_chars", None),
        "verification_output_tokens": getattr(exc, "verification_output_tokens", None),
        "verification_input_tokens_estimated": getattr(exc, "verification_input_tokens_estimated", None),
        "verification_context_window_tokens": getattr(exc, "verification_context_window_tokens", None),
        "verification_safety_margin_tokens": getattr(exc, "verification_safety_margin_tokens", None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-questions", type=int, default=6)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--development-unreviewed", action="store_true",
                        help="Required explicit operator authorization for the current unreviewed development corpus.")
    args = parser.parse_args()
    if not args.development_unreviewed:
        parser.error("--development-unreviewed is required; the production API rejects the current index.")
    if not 1 <= args.max_questions <= 24 or not 1 <= args.top_k <= 20:
        parser.error("--max-questions must be 1–24 and --top-k must be 1–20.")
    questions = list(read_jsonl(args.questions_file))[:args.max_questions]
    if not questions or any(not isinstance(row.get("question"), str) or not row["question"].strip() for row in questions):
        parser.error("Question file contains no valid questions.")

    retrieval_config = json.loads((PROJECT_ROOT / "configs" / "retrieval.json").read_text(encoding="utf-8-sig"))
    indexing = json.loads((PROJECT_ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    rerank_config = retrieval_config["reranker"]
    embedding = load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json")
    generator = load_generator(PROJECT_ROOT / "configs" / "generation.json")
    descriptor = EmbeddingDescriptor("ollama", embedding.spec.model_name, embedding.spec.model_digest,
        embedding.spec.dimensions, True, None)
    store = QdrantVectorStore(PROJECT_ROOT, indexing["collection_name"], descriptor,
        indexing["chunking_version"], qdrant_url=indexing["qdrant_url"])
    sparse = None
    try:
        tokenizer, _cfg, _strategy, chunking = load_chunking_components(
            PROJECT_ROOT, PROJECT_ROOT / "configs" / "chunking.json", PROJECT_ROOT / "configs" / "embedding.json")
        manifest = validate_index_manifest(store, PROJECT_ROOT, tokenizer, chunking,
            PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl")
        if manifest.get("authorization_mode") != "operator_authorized_unreviewed":
            raise RuntimeError("This diagnostic command is only for the explicitly unreviewed development index.")
        sparse = BM25Retriever(sparse_index_directory(PROJECT_ROOT, manifest["index_id"]))
        if sparse.manifest.get("index_id") != manifest.get("index_id"):
            raise RuntimeError("Sparse and dense index IDs do not match.")
        reranker = LocalCrossEncoderReranker(PROJECT_ROOT / Path(rerank_config["artifact"]).parent,
            batch_size=rerank_config["batch_size"], max_length=rerank_config["max_length"])
        hybrid = HybridRetriever(DenseRetriever(embedding, store), sparse, retrieval_config["rrf_constant"])
        scope = AccessScope(indexing["tenant_id"], (indexing["principal_id"],),
                            tuple(manifest["authorized_source_ids"]))
        assembler = ContextAssembler(max_budget=2500, max_chunks=8)
        output_rows = []
        for index, row in enumerate(questions, 1):
            question = row["question"].strip()
            started = time.perf_counter()
            retrieved = hybrid.retrieve(question, scope, limit=rerank_config["max_candidates"],
                candidate_limit=rerank_config["max_candidates"], development_unreviewed=True,
                explicit_operator_authorization=True)
            diversity_config = retrieval_config.get("comparison_diversity", {})
            diversity_applied = (diversity_config.get("enabled", False)
                                 and reranker.is_comparison_query(question, diversity_config.get("terms", ())))
            reranked = reranker.rerank(
                question, retrieved.hits, args.top_k,
                max_per_source=diversity_config.get("max_per_source", 4) if diversity_applied else None,
                max_per_document=diversity_config.get("max_per_document", 2) if diversity_applied else None,
            )
            context_started = time.perf_counter()
            context = assembler.assemble(reranked.hits, scope,
                development_unreviewed=True, explicit_operator_authorization=True,
                max_tokens_per_document_group=(
                    diversity_config.get("context_group_budget_tokens", 1200) if diversity_applied else None))
            context_ms = (time.perf_counter() - context_started) * 1000
            row_result = {
                "query_id": row.get("query_id", f"q{index:03d}"),
                "question": "REDACTED; prompt text is not persisted",
                "question_characters": len(question),
                "domain": row.get("domain"), "test_case_type": row.get("test_case_type"),
                "access_mode": "operator_authorized_unreviewed; local diagnostic only",
                "index_id": manifest["index_id"],
                "candidate_chunk_ids": list(context.included_chunk_ids),
                "context_budget_estimated_tokens": context.budget_used,
                "context_chunks_omitted": context.omitted_count,
                "context_omission_reasons": list(context.omitted_reasons),
                "context_omitted_passages": [
                    {"chunk_id": chunk_id, "reason": reason}
                    for chunk_id, reason in context.omitted_passages
                ],
                "context_citation_count": len(context.citations),
                "comparison_diversity_applied": diversity_applied,
                "required_comparison_source_ids": list(reranker.expected_comparison_sources(
                    question, diversity_config.get("source_aliases", {}))) if diversity_applied else [],
                "supporting_chunks": [{
                    "rank": hit.rank, "chunk_id": hit.chunk_id, "source_id": hit.source_id,
                    "document_id": hit.document_id, "title": hit.payload.get("title"),
                    "rrf_score": hit.score, "rerank_score": hit.rerank_score,
                    "dense_rank": hit.dense_rank, "sparse_rank": hit.sparse_rank,
                    "text_characters": len(str(hit.payload.get("chunk_text") or "")),
                } for hit in reranked.hits if hit.chunk_id in set(context.included_chunk_ids)],
                "reranked_candidates": [{
                    "rank": hit.rank, "source_id": hit.source_id, "document_id": hit.document_id,
                    "chunk_id": hit.chunk_id, "title": hit.payload.get("title"),
                    "rerank_score": hit.rerank_score,
                    "tenant_id": hit.payload.get("tenant_id"),
                    "license_review_status": hit.payload.get("license_review_status"),
                    "ingestion_authority": hit.payload.get("ingestion_authority"),
                    "acl_principals": hit.payload.get("acl_principals"),
                } for hit in reranked.hits],
                "citations": [{"citation_id": c.citation_id, "source_id": c.source_id,
                    "document_id": c.document_id, "title": c.title,
                    "pages": list(c.page_references), "section": c.section,
                    "source_reference": c.source_reference} for c in context.citations],
                "timings_ms": {"embedding": retrieved.embedding_ms, "dense_search": retrieved.dense_ms,
                    "sparse_search": retrieved.sparse_ms, "fusion": retrieved.fusion_ms,
                    "rerank": reranked.elapsed_ms, "context": context_ms},
            }
            comparison_complete = (not diversity_applied or reranker.comparison_evidence_complete(
                question, context.citations, diversity_config.get("source_aliases", {})))
            row_result["comparison_evidence_complete"] = comparison_complete
            if not context.citations or not comparison_complete:
                row_result["status"] = ("abstained_incomplete_comparison_evidence"
                                         if context.citations and not comparison_complete
                                         else "abstained_insufficient_context")
                row_result["answer"] = ABSTENTION
                row_result["answer_citations"] = []
                row_result["answer_generation_ms"] = None
                row_result["claim_verification_ms"] = None
                row_result["generation_pipeline_ms"] = None
            else:
                try:
                    generated = generator.generate(question, context, development_unreviewed=True)
                    row_result["answer"] = "REDACTED; generated response text is not persisted"
                    row_result["answer_characters"] = len(generated.answer)
                    row_result["answer_citations"] = list(generated.citations)
                    row_result["timings_ms"]["generation"] = generated.elapsed_ms
                    row_result["timings_ms"]["answer_generation"] = generated.answer_generation_ms
                    if generated.claim_verification_ms is not None:
                        row_result["timings_ms"]["claim_verification"] = generated.claim_verification_ms
                    row_result["timings_ms"]["generation_pipeline"] = generated.total_generation_ms
                    row_result["answer_generation_ms"] = generated.answer_generation_ms
                    row_result["claim_verification_ms"] = generated.claim_verification_ms
                    row_result["generation_pipeline_ms"] = generated.total_generation_ms
                    row_result["generation_retry_count"] = generated.generation_retry_count
                    row_result["verification_retry_count"] = generated.verification_retry_count
                    row_result["generation_http_status"] = generated.generation_http_status
                    row_result["verification_http_status"] = generated.verification_http_status
                    row_result["verification_done_reason"] = generated.verification_done_reason
                    row_result["verification_eval_count"] = generated.verification_eval_count
                    row_result["verification_prompt_eval_count"] = generated.verification_prompt_eval_count
                    row_result["verification_response_chars"] = generated.verification_response_chars
                    row_result["verification_output_tokens"] = generated.verification_output_tokens
                    row_result["verification_input_tokens_estimated"] = generated.verification_input_tokens_estimated
                    row_result["verification_context_window_tokens"] = generated.verification_context_window_tokens
                    row_result["verification_safety_margin_tokens"] = generated.verification_safety_margin_tokens
                    row_result["claim_count"] = generated.claim_count
                    row_result["generation_prompt_tokens_estimated"] = generated.prompt_tokens_estimated
                    row_result["generation_prompt_tokens_reported"] = generated.prompt_tokens_reported
                    row_result["claim_verification"] = {
                        "method": "automated_local_model_entailment_check",
                        "verification_model": generated.verification_model,
                        "claims": generated.claim_count,
                        "supported": generated.supported_claim_count,
                        "rejected": generated.rejected_claim_count,
                        "support_rate_automated": (generated.supported_claim_count / generated.claim_count
                                                    if generated.claim_count else None),
                        "human_correctness": "not_assessed",
                        "done_reason": generated.verification_done_reason,
                        "eval_count": generated.verification_eval_count,
                        "prompt_eval_count": generated.verification_prompt_eval_count,
                        "response_chars": generated.verification_response_chars,
                        "output_token_allowance": generated.verification_output_tokens,
                        "estimated_input_tokens": generated.verification_input_tokens_estimated,
                        "context_window_tokens": generated.verification_context_window_tokens,
                        "safety_margin_tokens": generated.verification_safety_margin_tokens,
                    }
                    row_result["status"] = "abstained_insufficient_evidence" if generated.abstained else "generated"
                    if generated.claim_count and generated.supported_claim_count < generated.claim_count:
                        row_result["status"] = "generated_partial"
                except GenerationError as exc:
                    row_result["status"] = "generation_failed"
                    row_result.update(classify_generation_error(exc))
                    if exc.answer_generation_ms is not None:
                        row_result["timings_ms"]["answer_generation"] = exc.answer_generation_ms
                    if exc.claim_verification_ms is not None:
                        row_result["timings_ms"]["claim_verification"] = exc.claim_verification_ms
                    if exc.total_generation_ms is not None:
                        row_result["timings_ms"]["generation_pipeline"] = exc.total_generation_ms
            row_result["timings_ms"]["end_to_end"] = (time.perf_counter() - started) * 1000
            output_rows.append(row_result)
            print(f"[{index}/{len(questions)}] {row_result['status']}: {row_result['query_id']}", flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        evaluated = [row["claim_verification"] for row in output_rows if "claim_verification" in row]
        total_claims = sum(row["claims"] for row in evaluated)
        total_supported = sum(row["supported"] for row in evaluated)
        summary = {
            "automated_claim_support_rate": total_supported / total_claims if total_claims else None,
            "automated_claims": total_claims,
            "automated_supported_claims": total_supported,
            "automated_rejected_claims": sum(row["rejected"] for row in evaluated),
            "human_labeled_claims": 0,
            "human_answer_correctness": "not_assessed",
            "limitation": "Local-model verdicts are diagnostic estimates; they are not independent human correctness labels.",
            "error_counts_by_code": {
                code: sum(1 for row in output_rows if row.get("error_code") == code)
                for code in sorted({row.get("error_code") for row in output_rows if row.get("error_code")})
            },
            "verifier_done_reason_counts": {
                reason: sum(1 for row in output_rows if (
                    row.get("verification_done_reason") == reason
                    or row.get("claim_verification", {}).get("done_reason") == reason))
                for reason in sorted({
                    reason for row in output_rows for reason in (
                        row.get("verification_done_reason"),
                        row.get("claim_verification", {}).get("done_reason")) if reason
                })
            },
            "truncated_verifier_responses": sum(
                1 for row in output_rows if row.get("error_code") == "claim_verifier_truncated_response"),
        }
        args.output.write_text(json.dumps({"read_only": True, "result_type": "unreviewed_generation_diagnostic",
            "index_id": manifest["index_id"], "query_count": len(output_rows), "evaluation": summary,
            "results": output_rows},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved local diagnostic to {args.output}")
        return 0
    finally:
        if sparse is not None:
            sparse.close()
        generator.close()
        embedding.close()
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
