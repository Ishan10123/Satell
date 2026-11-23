"""Inspect local dense-retrieval results without changing Qdrant."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.configuration import load_chunking_components, load_embedding_provider
from rag_pipeline.ingestion.parsing_job import document_id_for
from rag_pipeline.retrieval import DenseRetriever
from rag_pipeline.storage import AccessScope, QdrantVectorStore, RetrievalFilters
from rag_pipeline.storage.index_manifest import validate_index_manifest


def read_jsonl(path: Path):
    with path.open(encoding="utf-8-sig") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)


def local_path_map(path: Path) -> dict[str, str]:
    result = {}
    for record in read_jsonl(path):
        if isinstance(record, dict) and isinstance(record.get("source_id"), str):
            result[document_id_for(record)] = str(record.get("local_path") or record.get("file_path") or "")
    return result


def load_questions(args) -> list[dict]:
    questions = []
    if args.question:
        questions.append({"question": args.question, "domain": args.domain})
    if args.questions_file:
        for row in read_jsonl(args.questions_file):
            if not isinstance(row, dict) or not isinstance(row.get("question"), str) or not row["question"].strip():
                raise ValueError("Each question-file row must contain non-empty question text.")
            questions.append(row)
    if not questions:
        raise ValueError("Pass --question or --questions-file.")
    return questions


def run(args) -> dict:
    settings = json.loads((PROJECT_ROOT / "configs" / "retrieval.json").read_text(encoding="utf-8-sig"))
    indexing = json.loads((PROJECT_ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    embedding = load_embedding_provider(PROJECT_ROOT / "configs" / "embedding.json")
    tokenizer, _chunk_config, _strategy, chunking = load_chunking_components(
        PROJECT_ROOT, PROJECT_ROOT / "configs" / "chunking.json", PROJECT_ROOT / "configs" / "embedding.json",
    )
    collection = args.collection or indexing["collection_name"]
    store = QdrantVectorStore(
        PROJECT_ROOT, collection,
        embedding_descriptor(embedding), indexing["chunking_version"],
        qdrant_url=indexing["qdrant_url"],
    )
    try:
        manifest = validate_index_manifest(
            store, PROJECT_ROOT, tokenizer, chunking,
            PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl",
        )
        if args.development_unreviewed:
            if manifest.get("authorization_mode") != "operator_authorized_unreviewed":
                raise ValueError("--development-unreviewed only applies to an operator-authorized unreviewed index.")
            sources = tuple(manifest.get("authorized_source_ids", []))
            status_label = "operator_authorized_unreviewed; local diagnostic only"
        else:
            approval = json.loads((PROJECT_ROOT / "knowledge_base" / "metadata" / "source_approvals.json").read_text(encoding="utf-8-sig"))
            sources = tuple(sorted(source for source, decision in approval.get("sources", {}).items()
                                   if isinstance(decision, dict) and decision.get("status") == "approved"))
            status_label = "approved-source-only"
        scope = AccessScope(indexing["tenant_id"], (indexing["principal_id"],), sources)
        retriever = DenseRetriever(embedding, store, max_query_characters=settings["query_max_characters"])
        paths = local_path_map(PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl")
        outputs = []
        for query_record in load_questions(args):
            result = retriever.retrieve_detailed(
                query_record["question"], scope,
                limit=args.top_k or settings["default_top_k"],
                score_threshold=args.minimum_score if args.minimum_score is not None else settings["minimum_score"],
                filters=RetrievalFilters(
                    source_ids=(args.source_id,) if args.source_id else (),
                    document_ids=(args.document_id,) if args.document_id else (),
                ),
                development_unreviewed=args.development_unreviewed,
                explicit_operator_authorization=args.development_unreviewed,
            )
            hits = []
            for hit in result.hits:
                payload = hit.payload
                doc_id = payload.get("document_id")
                hits.append({
                    "rank": hit.rank,
                    "score": hit.score,
                    "source_id": payload.get("source_id"),
                    "document_id": doc_id,
                    "chunk_id": payload.get("chunk_id"),
                    "title": payload.get("title"),
                    "file_path": paths.get(doc_id) if isinstance(doc_id, str) else None,
                    "source_reference": payload.get("source_reference"),
                    "text_preview": (payload.get("chunk_text") or "")[:settings["result_preview_characters"]],
                })
            outputs.append({
                "question": result.query,
                "domain": query_record.get("domain"),
                "authorization_mode": status_label,
                "embedding_ms": round(result.embedding_ms, 3),
                "retrieval_ms": round(result.retrieval_ms, 3),
                "total_ms": round(result.total_ms, 3),
                "result_count": len(hits),
                "results": hits,
            })
        return {
            "collection": collection,
            "index_id": manifest.get("index_id"),
            "manifest_authorization_mode": manifest.get("authorization_mode"),
            "access_mode": status_label,
            "read_only": True,
            "query_count": len(outputs),
            "results": outputs,
        }
    finally:
        store.close()
        embedding.close()


def embedding_descriptor(provider):
    from rag_pipeline.embeddings import EmbeddingDescriptor
    return EmbeddingDescriptor(
        provider="ollama", model_name=provider.spec.model_name,
        model_digest=provider.spec.model_digest, dimensions=provider.spec.dimensions,
        vectors_are_unit_normalized=True, runtime_version=None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--question")
    query_group.add_argument("--questions-file", type=Path)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--minimum-score", type=float)
    parser.add_argument("--source-id")
    parser.add_argument("--document-id")
    parser.add_argument("--collection")
    parser.add_argument("--development-unreviewed", action="store_true",
                        help="Allow read-only diagnostic results from an operator-authorized unreviewed index. Never used by the API.")
    parser.add_argument("--json", action="store_true", help="Emit full JSON including result previews.")
    args = parser.parse_args()
    settings = json.loads((PROJECT_ROOT / "configs" / "retrieval.json").read_text(encoding="utf-8-sig"))
    selected_top_k = args.top_k or settings["default_top_k"]
    if not 1 <= selected_top_k <= settings["maximum_top_k"]:
        parser.error(f"--top-k must be between 1 and {settings['maximum_top_k']}.")
    if args.minimum_score is not None and not -1 <= args.minimum_score <= 1:
        parser.error("--minimum-score must be between -1 and 1.")
    try:
        report = run(args)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Collection: {report['collection']} | mode: {report['access_mode']} | read-only: yes")
        for item in report["results"]:
            print(f"\nQuestion: {item['question']}")
            print(f"Embedding: {item['embedding_ms']} ms | retrieval: {item['retrieval_ms']} ms | total: {item['total_ms']} ms")
            for result in item["results"]:
                print(f"\n  #{result['rank']} score={result['score']:.4f} source={result['source_id']} document={result['document_id']} chunk={result['chunk_id']}")
                print(f"  Title: {result['title']}")
                print(f"  Path: {result['file_path']}")
                print(f"  Source: {result['source_reference']}")
                print(f"  Text: {result['text_preview'].replace(chr(10), ' ')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
