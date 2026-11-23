"""Inspect local sparse BM25 results without changing Qdrant."""

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.ingestion.parsing_job import document_id_for
from rag_pipeline.retrieval import BM25Retriever, sparse_index_directory
from rag_pipeline.storage import AccessScope, RetrievalFilters


def read_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)


def path_map(path: Path) -> dict[str, str]:
    return {document_id_for(row): str(row.get("local_path") or row.get("file_path") or "")
            for row in read_jsonl(path) if isinstance(row, dict) and row.get("source_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question")
    group.add_argument("--questions-file", type=Path)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--source-id")
    parser.add_argument("--document-id")
    parser.add_argument("--development-unreviewed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20.")
    indexing = json.loads((PROJECT_ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    ready_path = PROJECT_ROOT / "knowledge_base" / "metadata" / "index_manifests" / f"{indexing['collection_name']}.json"
    readiness = json.loads(ready_path.read_text(encoding="utf-8-sig"))
    directory = sparse_index_directory(PROJECT_ROOT, readiness["index_id"])
    retriever = BM25Retriever(directory)
    try:
        sparse_manifest = retriever.manifest
        if sparse_manifest.get("index_id") != readiness.get("index_id") or sparse_manifest.get("dense_collection") != readiness.get("collection_name"):
            raise RuntimeError("Sparse artifact does not match the ready dense index.")
        if readiness.get("authorization_mode") == "operator_authorized_unreviewed":
            if not args.development_unreviewed:
                raise RuntimeError("This index is unreviewed; pass --development-unreviewed for local diagnostics.")
            sources = tuple(readiness.get("authorized_source_ids", []))
            mode = "operator_authorized_unreviewed; local diagnostic only"
        else:
            approvals = json.loads((PROJECT_ROOT / "knowledge_base" / "metadata" / "source_approvals.json").read_text(encoding="utf-8-sig"))
            sources = tuple(sorted(s for s, d in approvals.get("sources", {}).items()
                                   if isinstance(d, dict) and d.get("status") == "approved"))
            mode = "approved-source-only"
        scope = AccessScope(indexing["tenant_id"], (indexing["principal_id"],), sources)
        if args.question:
            questions = [{"question": args.question}]
        else:
            questions = list(read_jsonl(args.questions_file))
        paths = path_map(PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl")
        results = []
        for row in questions:
            result = retriever.search(row["question"], scope, args.top_k,
                filters=RetrievalFilters(source_ids=(args.source_id,) if args.source_id else (),
                                         document_ids=(args.document_id,) if args.document_id else ()),
                development_unreviewed=args.development_unreviewed,
                explicit_operator_authorization=args.development_unreviewed)
            results.append({
                "question": row["question"], "domain": row.get("domain"), "access_mode": mode,
                "retrieval_ms": round(result.retrieval_ms, 3),
                "results": [{"rank": h.rank, "score": h.score, "source_id": h.source_id,
                    "document_id": h.document_id, "chunk_id": h.chunk_id, "title": h.title,
                    "file_path": paths.get(h.document_id), "source_reference": h.source_reference,
                    "text_preview": h.chunk_text[:700]} for h in result.hits],
            })
        output = {"index_id": readiness["index_id"], "access_mode": mode,
                  "sparse_point_count": sparse_manifest["point_count"], "read_only": True,
                  "query_count": len(results), "results": results}
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"Sparse BM25 | {mode} | read-only")
            for result in results:
                print(f"\nQuestion: {result['question']} ({result['retrieval_ms']} ms)")
                for hit in result["results"]:
                    print(f"  #{hit['rank']} score={hit['score']:.6f} {hit['source_id']} | {hit['title']} | {hit['file_path']}")
                    print(f"    {hit['text_preview'].replace(chr(10), ' ')}")
        return 0
    finally:
        retriever.close()


if __name__ == "__main__":
    raise SystemExit(main())
