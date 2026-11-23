"""Summarize human correctness and citation-support reviews for generated answers."""
import argparse
import json
from pathlib import Path
import sys


CORRECTNESS = {"correct", "partially_correct", "incorrect", "abstained"}
CITATION_SUPPORT = {"all_supported", "partially_supported", "unsupported", "not_applicable"}


def evaluate(path: Path):
    rows = []
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Expected a JSON object at line {line_number}.")
            if row.get("review_status") != "complete":
                raise ValueError(f"Answer review is incomplete for {row.get('query_id', 'unknown query')}.")
            if row.get("correctness") not in CORRECTNESS or row.get("citation_support") not in CITATION_SUPPORT:
                raise ValueError(f"Answer review labels are invalid for {row.get('query_id', 'unknown query')}.")
            rows.append(row)
    if not rows:
        raise ValueError("No completed answer reviews were found.")
    count = len(rows)
    return {
        "reviewed_answers": count,
        "correctness_counts": {label: sum(row["correctness"] == label for row in rows) for label in sorted(CORRECTNESS)},
        "citation_support_counts": {label: sum(row["citation_support"] == label for row in rows) for label in sorted(CITATION_SUPPORT)},
        "correct_rate": sum(row["correctness"] == "correct" for row in rows) / count,
        "fully_supported_citation_rate": sum(row["citation_support"] == "all_supported" for row in rows) / count,
        "abstention_rate": sum(row["correctness"] == "abstained" for row in rows) / count,
        "query_ids": [row.get("query_id") for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judgments", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.judgments)
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
