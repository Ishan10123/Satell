"""Compute retrieval metrics from completed, human-authored relevance judgments."""
import argparse
import json
import math
from pathlib import Path
import sys


def load_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at line {line_number}.") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"Expected an object at line {line_number}.")
                rows.append(value)
    return rows


def evaluate(result_path: Path, judgment_path: Path, ks=(1, 3, 5, 10)):
    results_doc = json.loads(result_path.read_text(encoding="utf-8-sig"))
    results = results_doc.get("results") if isinstance(results_doc, dict) else None
    if not isinstance(results, list) or not results:
        raise ValueError("Retrieval result file contains no results.")
    judgments = load_jsonl(judgment_path)
    by_query = {item.get("query_id"): item for item in judgments}
    if len(by_query) != len(judgments):
        raise ValueError("Relevance judgments contain duplicate query_id values.")
    per_query = []
    for index, row in enumerate(results, 1):
        query_id = row.get("query_id") or f"q{index:03d}"
        judgment = by_query.get(query_id)
        if not judgment or judgment.get("review_status") != "complete":
            raise ValueError(f"Human relevance review is incomplete for {query_id}.")
        relevant = judgment.get("relevant_chunk_ids")
        if not isinstance(relevant, list) or not relevant or not all(isinstance(x, str) and x for x in relevant):
            raise ValueError(f"{query_id} must have at least one reviewed relevant chunk ID.")
        relevant_set = set(relevant)
        hits = row.get("results")
        if not isinstance(hits, list):
            raise ValueError(f"Retrieval results are malformed for {query_id}.")
        ranks = [hit.get("chunk_id") for hit in hits]
        metrics = {"query_id": query_id, "question": row.get("question"), "relevant_count": len(relevant_set), "at_k": {}}
        for k in ks:
            found = [chunk_id for chunk_id in ranks[:k] if chunk_id in relevant_set]
            reciprocal_rank = next((1.0 / rank for rank, chunk_id in enumerate(ranks, 1) if chunk_id in relevant_set), 0.0)
            dcg = sum(1.0 / math.log2(rank + 1) for rank, chunk_id in enumerate(ranks[:k], 1) if chunk_id in relevant_set)
            ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant_set), k) + 1))
            metrics["at_k"][str(k)] = {
                "precision": len(found) / k,
                "recall": len(found) / len(relevant_set),
                "reciprocal_rank": reciprocal_rank,
                "ndcg": dcg / ideal if ideal else 0.0,
            }
        per_query.append(metrics)
    missing = set(by_query) - {item.get("query_id") or f"q{idx:03d}" for idx, item in enumerate(results, 1)}
    if missing:
        raise ValueError(f"Judgments include unknown query IDs: {sorted(missing)}")
    aggregate = {}
    for k in ks:
        keys = ("precision", "recall", "reciprocal_rank", "ndcg")
        aggregate[str(k)] = {key: sum(item["at_k"][str(k)][key] for item in per_query) / len(per_query) for key in keys}
    return {"result_file": str(result_path), "judgment_file": str(judgment_path),
            "query_count": len(per_query), "metrics": aggregate, "per_query": per_query}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--judgments", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.results, args.judgments)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Evaluation stopped: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
