"""Compare dense and FTS5 BM25 candidates with reciprocal-rank fusion."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.configuration import load_chunking_components, load_embedding_provider
from rag_pipeline.embeddings import EmbeddingDescriptor
from rag_pipeline.ingestion.parsing_job import document_id_for
from rag_pipeline.retrieval import (BM25Retriever, DenseRetriever, HybridRetriever,
                                    LocalCrossEncoderReranker, sparse_index_directory)
from rag_pipeline.storage import AccessScope, QdrantVectorStore, RetrievalFilters
from rag_pipeline.storage.index_manifest import validate_index_manifest


def read_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question")
    group.add_argument("--questions-file", type=Path)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--candidate-top-k", type=int)
    parser.add_argument("--rrf-constant", type=int)
    parser.add_argument("--rerank", action="store_true", help="Rerank the bounded hybrid candidates with the pinned local ONNX model.")
    parser.add_argument("--source-id")
    parser.add_argument("--development-unreviewed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    retrieval_config = json.loads((PROJECT_ROOT / "configs" / "retrieval.json").read_text(encoding="utf-8-sig"))
    top_k = args.top_k or retrieval_config["default_top_k"]
    candidates = args.candidate_top_k or retrieval_config["candidate_top_k"]
    rrf_constant = args.rrf_constant or retrieval_config["rrf_constant"]
    if not 1 <= top_k <= retrieval_config["maximum_top_k"]:
        parser.error(f"--top-k must be between 1 and {retrieval_config['maximum_top_k']}.")
    if not 1 <= candidates <= retrieval_config["maximum_candidate_top_k"]:
        parser.error("--candidate-top-k exceeds the configured maximum.")
    if not 1 <= rrf_constant <= 1000:
        parser.error("--rrf-constant must be between 1 and 1000.")
    indexing = json.loads((PROJECT_ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    embedding = load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json")
    descriptor = EmbeddingDescriptor("ollama", embedding.spec.model_name, embedding.spec.model_digest,
                                     embedding.spec.dimensions, True, None)
    store = QdrantVectorStore(PROJECT_ROOT, indexing["collection_name"], descriptor,
                              indexing["chunking_version"], qdrant_url=indexing["qdrant_url"])
    sparse = None
    try:
        tokenizer, _chunk_config, _strategy, chunking = load_chunking_components(
            PROJECT_ROOT, PROJECT_ROOT / "configs" / "chunking.json", PROJECT_ROOT / "configs" / "embedding.json",
        )
        readiness = validate_index_manifest(store, PROJECT_ROOT, tokenizer, chunking,
            PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl")
        sparse = BM25Retriever(sparse_index_directory(PROJECT_ROOT, readiness["index_id"]))
        if sparse.manifest.get("index_id") != readiness.get("index_id"):
            raise RuntimeError("Sparse index does not match the ready dense index.")
        if args.development_unreviewed:
            if readiness.get("authorization_mode") != "operator_authorized_unreviewed":
                raise RuntimeError("Development mode only applies to an operator-authorized unreviewed index.")
            sources = tuple(readiness.get("authorized_source_ids", []))
            access_mode = "operator_authorized_unreviewed; local diagnostic only"
        else:
            approvals = json.loads((PROJECT_ROOT / "knowledge_base" / "metadata" / "source_approvals.json").read_text(encoding="utf-8-sig"))
            sources = tuple(sorted(source for source, decision in approvals.get("sources", {}).items()
                                   if isinstance(decision, dict) and decision.get("status") == "approved"))
            access_mode = "approved-source-only"
        scope = AccessScope(indexing["tenant_id"], (indexing["principal_id"],), sources)
        path_map = {document_id_for(row): str(row.get("local_path") or row.get("file_path") or "")
                    for row in read_jsonl(PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl")
                    if isinstance(row, dict) and row.get("source_id")}
        questions = ([{"question": args.question}] if args.question else list(read_jsonl(args.questions_file)))
        hybrid = HybridRetriever(DenseRetriever(embedding, store), sparse, rrf_constant)
        reranker = None
        if args.rerank:
            rerank_config = retrieval_config["reranker"]
            reranker = LocalCrossEncoderReranker(PROJECT_ROOT / Path(rerank_config["artifact"]).parent,
                batch_size=rerank_config["batch_size"], max_length=rerank_config["max_length"])
        result_rows = []
        for question_index, row in enumerate(questions, 1):
            # When reranking is enabled, RRF must return the configured candidate
            # pool; passing top_k here silently discarded candidates before the
            # reranker could evaluate or diversify them.
            fused_limit = candidates if reranker is not None else top_k
            result = hybrid.retrieve(row["question"], scope, fused_limit, candidates,
                filters=RetrievalFilters(source_ids=(args.source_id,) if args.source_id else ()),
                development_unreviewed=args.development_unreviewed,
                explicit_operator_authorization=args.development_unreviewed)
            rerank_ms = 0.0
            result_hits = result.hits
            diversity_applied = False
            if reranker is not None:
                diversity_config = retrieval_config.get("comparison_diversity", {})
                diversity_applied = (diversity_config.get("enabled", False)
                    and reranker.is_comparison_query(row["question"], diversity_config.get("terms", ())))
                reranked = reranker.rerank(row["question"], result.hits, top_k,
                    max_per_source=diversity_config.get("max_per_source", 4) if diversity_applied else None,
                    max_per_document=diversity_config.get("max_per_document", 2) if diversity_applied else None)
                result_hits = reranked.hits
                rerank_ms = reranked.elapsed_ms
            result_rows.append({
                "query_id": row.get("query_id", f"q{question_index:03d}"),
                "question": result.query, "domain": row.get("domain"),
                "embedding_ms": round(result.embedding_ms, 3), "dense_ms": round(result.dense_ms, 3),
                "sparse_ms": round(result.sparse_ms, 3), "fusion_ms": round(result.fusion_ms, 3),
                "total_ms": round(result.total_ms, 3),
                "rerank_ms": round(rerank_ms, 3),
                "total_with_rerank_ms": round(result.total_ms + rerank_ms, 3),
                "comparison_diversity_applied": diversity_applied,
                "results": [{"rank": hit.rank, "rrf_score": hit.score, "rerank_score": hit.rerank_score,
                    "dense_rank": hit.dense_rank, "dense_score": hit.dense_score,
                    "sparse_rank": hit.sparse_rank, "sparse_score": hit.sparse_score,
                    "source_id": hit.source_id, "document_id": hit.document_id,
                    "chunk_id": hit.chunk_id, "title": hit.payload.get("title"),
                    "file_path": path_map.get(hit.document_id),
                    "text_preview": str(hit.payload.get("chunk_text") or "")[:700]}
                    for hit in result_hits],
            })
        output = {"collection": readiness["collection_name"], "index_id": readiness["index_id"],
                  "access_mode": access_mode, "rrf_constant": rrf_constant,
                  "candidate_top_k_per_retriever": candidates, "reranked": reranker is not None, "read_only": True,
                  "query_count": len(result_rows), "results": result_rows}
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"Hybrid dense + BM25 + RRF | {access_mode} | read-only")
            for row in result_rows:
                print(f"\nQuestion: {row['question']} | total={row['total_ms']} ms")
                for hit in row["results"]:
                    print(f"  #{hit['rank']} RRF={hit['rrf_score']:.5f} dense={hit['dense_rank']} BM25={hit['sparse_rank']} | {hit['source_id']} | {hit['title']} | {hit['file_path']}")
                    print(f"    {hit['text_preview'].replace(chr(10), ' ')}")
        return 0
    finally:
        if sparse is not None:
            sparse.close()
        store.close()
        embedding.close()


if __name__ == "__main__":
    raise SystemExit(main())
