"""Read-only, authorization-scoped retrieval comparison for Phase 4 evaluation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_pipeline.authorization.local_academic_demo import (  # noqa: E402
    validate_demo_registry, validate_local_demo_policy, validate_source_registry,
)
from rag_pipeline.configuration import load_chunking_components, load_embedding_provider, load_generator  # noqa: E402
from rag_pipeline.embeddings import EmbeddingDescriptor  # noqa: E402
from rag_pipeline.retrieval import (  # noqa: E402
    BM25Retriever, ContextAssembler, DenseRetriever, LocalCrossEncoderReranker,
    reciprocal_rank_fusion, sparse_index_directory,
)
from rag_pipeline.storage import AccessScope, QdrantVectorStore, RetrievalFilters  # noqa: E402
from rag_pipeline.storage.index_manifest import validate_index_manifest  # noqa: E402


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def metrics(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "minimum_ms": None, "p50_ms": None, "p95_ms": None, "maximum_ms": None}
    ordered = sorted(values)
    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {"count": len(values), "minimum_ms": round(ordered[0], 3),
            "p50_ms": round(statistics.median(ordered), 3), "p95_ms": round(percentile(.95), 3),
            "maximum_ms": round(ordered[-1], 3)}


def ranked_metrics(hits, expected_sources: set[str]) -> dict[str, float | int | None]:
    if not expected_sources:
        return {"labelled": False, "recall_at_8": None, "precision_at_8_source_heuristic": None,
                "mrr_source_heuristic": None, "ndcg_at_8_source_heuristic": None,
                "expected_source_coverage": None}
    rows = list(hits[:8])
    # Labels are at source level, so duplicate documents from one expected
    # source count once. This avoids pretending that every document in a source
    # is individually relevant.
    observed_order = list(dict.fromkeys(
        getattr(hit, "source_id", None) or getattr(hit, "payload", {}).get("source_id")
        for hit in rows
    ))
    relevant = [source_id in expected_sources for source_id in observed_order]
    first = next((index + 1 for index, value in enumerate(relevant) if value), None)
    dcg = sum((1.0 / __import__("math").log2(index + 2)) for index, value in enumerate(relevant) if value)
    ideal_count = min(len(expected_sources), len(observed_order))
    idcg = sum(1.0 / __import__("math").log2(index + 2) for index in range(ideal_count))
    observed = set(observed_order)
    covered = len(observed & expected_sources)
    return {"labelled": True, "recall_at_8": covered / len(expected_sources),
            "precision_at_8_source_heuristic": (covered / len(observed) if observed else 0.0),
            "mrr_source_heuristic": (1.0 / first if first else 0.0),
            "ndcg_at_8_source_heuristic": (dcg / idcg if idcg else 0.0),
            "expected_source_coverage": len(observed & expected_sources) / len(expected_sources)}


def main() -> None:
    load_dotenv(ROOT / "django_app" / ".env")
    token = os.environ.get("RAG_API_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("Local evaluation signing credential is unavailable.")
    questions = json.loads((ROOT / "docs" / "phase4_evaluation_questions.json").read_text(encoding="utf-8"))["queries"]
    index_config = json.loads((ROOT / "configs" / "indexing.json").read_text(encoding="utf-8"))
    retrieval_config = json.loads((ROOT / "configs" / "retrieval.json").read_text(encoding="utf-8"))
    model_config = json.loads((ROOT / "configs" / "embedding.json").read_text(encoding="utf-8"))
    inventory = ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl"
    source_path = ROOT / "knowledge_base" / "metadata" / "local_academic_demo_source_authorizations_phase1_v3.json"
    document_path = ROOT / "knowledge_base" / "metadata" / "local_academic_demo_document_authorizations_phase1_v3.json"
    validate_local_demo_policy(ROOT / "configs" / "local_academic_demo_policy.json")
    source_registry = validate_source_registry(source_path, inventory, token)
    demo_registry = validate_demo_registry(document_path, inventory, token,
        operator=source_registry["operator"], source_registry=source_registry)
    tenant, principal = os.environ.get("RAG_TENANT_ID", "local"), os.environ.get("RAG_PRINCIPAL_ID", "local-admin")
    scope = AccessScope(tenant, (principal,), tuple(demo_registry["source_ids"]))
    permitted = tuple(demo_registry["documents"])
    filters = RetrievalFilters(permitted_document_ids=permitted, source_types=("documentation",))

    embedding = load_embedding_provider(ROOT / "configs" / "embedding.json", base_url="http://127.0.0.1:11434")
    generator = load_generator(ROOT / "configs" / "generation.json", base_url="http://127.0.0.1:11434")
    descriptor = EmbeddingDescriptor("ollama", embedding.spec.model_name, embedding.spec.model_digest,
                                     embedding.spec.dimensions, True, None)
    store = QdrantVectorStore(ROOT, index_config["collection_name"], descriptor,
        index_config["chunking_version"], qdrant_url=os.environ.get("RAG_QDRANT_URL", "http://127.0.0.1:6333"))
    tokenizer, _, _, _ = load_chunking_components(ROOT, ROOT / "configs" / "chunking.json",
                                                  ROOT / "configs" / "embedding.json")
    manifest = validate_index_manifest(store, ROOT, tokenizer, source_manifest_path=inventory)
    dense = DenseRetriever(embedding, store, max_query_characters=5000)
    sparse = BM25Retriever(sparse_index_directory(ROOT, manifest["index_id"]))
    rerank_config = retrieval_config["reranker"]
    reranker = LocalCrossEncoderReranker(ROOT / Path(rerank_config["artifact"]).parent,
        batch_size=rerank_config["batch_size"], max_length=rerank_config["max_length"])
    assembler = ContextAssembler(max_budget=retrieval_config["max_evidence_context_bytes"], max_chunks=8)
    strategies = {name: {"latencies": [], "recall_values": [], "precision_values": [], "mrr_values": [],
                         "ndcg_values": [], "coverage_values": [], "context_admissions": 0}
                  for name in ("dense", "hybrid_rrf", "hybrid_rerank")}
    results = []
    collection_health = store.health_check()
    for row in questions:
        query = row["question"]
        started = time.perf_counter()
        candidates = dense.retrieve_detailed(query, scope, limit=30, filters=filters,
            development_unreviewed=True, explicit_operator_authorization=True)
        sparse_hits = sparse.search(query, scope, limit=30, filters=filters,
            development_unreviewed=True, explicit_operator_authorization=True)
        fusion_started = time.perf_counter()
        fused30 = reciprocal_rank_fusion(candidates.hits, sparse_hits.hits, limit=30,
                                         constant=retrieval_config["rrf_constant"])
        fusion_ms = (time.perf_counter() - fusion_started) * 1000
        rerank_started = time.perf_counter()
        reranked = reranker.rerank(query, fused30, limit=8)
        rerank_ms = (time.perf_counter() - rerank_started) * 1000
        selections = {
            "dense": tuple(candidates.hits[:8]),
            "hybrid_rrf": tuple(fused30[:8]),
            "hybrid_rerank": tuple(reranked.hits[:8]),
        }
        strategy_rows = {}
        expected = set(row["expected_sources"])
        for strategy, hits in selections.items():
            context_started = time.perf_counter()
            assembled = assembler.assemble(hits, scope,
                development_unreviewed=True, explicit_operator_authorization=True,
                permitted_document_ids=permitted, permitted_document_metadata=demo_registry["documents"],
                max_budget=min(retrieval_config["max_evidence_context_bytes"], generator.context_budget_for(query)))
            context_ms = (time.perf_counter() - context_started) * 1000
            selected_hits = list(hits)
            def field(hit, name):
                return getattr(hit, name, None) or getattr(hit, "payload", {}).get(name)
            score = ranked_metrics(selected_hits, expected)
            stage_ms = {
                "dense_embedding_and_search": candidates.total_ms,
                "bm25_search": sparse_hits.retrieval_ms if strategy != "dense" else None,
                "rrf_fusion": fusion_ms if strategy != "dense" else None,
                "reranker": rerank_ms if strategy == "hybrid_rerank" else None,
                "context_assembly": context_ms,
            }
            stage_total = candidates.total_ms + context_ms
            if strategy == "hybrid_rerank":
                stage_total += sparse_hits.retrieval_ms + fusion_ms + rerank_ms
            elif strategy == "hybrid_rrf":
                stage_total += sparse_hits.retrieval_ms + fusion_ms
            strategy_rows[strategy] = {
                "hits": [{"rank": i + 1, "chunk_id": field(hit, "chunk_id"),
                          "document_id": field(hit, "document_id"),
                          "source_id": field(hit, "source_id"), "score": hit.score,
                          "dense_score": getattr(hit, "dense_score", None),
                          "sparse_score": getattr(hit, "sparse_score", None),
                          "rerank_score": getattr(hit, "rerank_score", None)}
                         for i, hit in enumerate(selected_hits)],
                "context_chunk_ids": list(assembled.included_chunk_ids),
                "context_chunk_count": len(assembled.included_chunk_ids),
                "context_token_estimate": assembled.budget_used,
                "context_exclusions": list(assembled.omitted_reasons),
                "retrieval_stages_ms": stage_ms,
                "estimated_combined_retrieval_ms": round(stage_total, 3),
                **score,
            }
            acc = strategies[strategy]
            acc["latencies"].append(stage_total)
            if score["labelled"]:
                acc["recall_values"].append(score["recall_at_8"])
                acc["precision_values"].append(score["precision_at_8_source_heuristic"])
                acc["mrr_values"].append(score["mrr_source_heuristic"])
                acc["ndcg_values"].append(score["ndcg_at_8_source_heuristic"])
                acc["coverage_values"].append(score["expected_source_coverage"])
            acc["context_admissions"] += int(bool(assembled.included_chunk_ids))
        results.append({"query_id": row["query_id"], "question": query,
                        "expected_sources": row["expected_sources"],
                        "expected_behavior": row["expected_behavior"], "strategies": strategy_rows})
        print(f"retrieval {row['query_id']} complete", flush=True)
    summary = {}
    for name, values in strategies.items():
        count = len(values["latencies"])
        summary[name] = {
            "retrieval_latency": metrics(values["latencies"]),
            "labelled_query_count": len(values["recall_values"]),
            "recall_at_8_source_heuristic": (sum(values["recall_values"]) / len(values["recall_values"])
                                                if values["recall_values"] else None),
            "precision_at_8_source_heuristic": (sum(values["precision_values"]) / len(values["precision_values"])
                                                   if values["precision_values"] else None),
            "mrr_source_heuristic": (sum(values["mrr_values"]) / len(values["mrr_values"])
                                      if values["mrr_values"] else None),
            "ndcg_at_8_source_heuristic": (sum(values["ndcg_values"]) / len(values["ndcg_values"])
                                            if values["ndcg_values"] else None),
            "expected_source_coverage": (sum(values["coverage_values"]) / len(values["coverage_values"])
                                         if values["coverage_values"] else None),
            "context_assembly_success_rate": values["context_admissions"] / count if count else 0.0,
        }
    output = {"evaluation_id": "satell-phase4-retrieval-30-v1", "live_qdrant": True,
              "live_ollama_embeddings": True, "generation_performed": False,
              "authorization_mode": "local_academic_demo", "collection": manifest["collection_name"],
              "index_id": manifest["index_id"], "point_count": collection_health["points_count"],
              "embedding_model": model_config["model_name"], "reranker_model": rerank_config["model_id"],
              "retrieval_config_strategy": retrieval_config["strategy"],
              "reranker_runtime_activation": "evaluation-only; existing config remains disabled",
              "metric_label_limitations": "Binary source-topic heuristics; not human-judged document relevance.",
              "summary": summary, "queries": results}
    out = ROOT / "docs" / "phase4_retrieval_benchmark.json"
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sparse.close()
    embedding.close()
    generator.close()
    store.close()
    print(f"saved {out}", flush=True)


if __name__ == "__main__":
    main()
