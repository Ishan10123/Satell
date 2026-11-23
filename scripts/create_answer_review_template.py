"""Create a human answer/citation review template from local generation diagnostics."""
import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8-sig"))
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        parser.error("Generation result file must contain a non-empty results array.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps({
                "query_id": row.get("query_id"), "question": row.get("question"),
                "answer": row.get("answer"), "answer_citations": row.get("answer_citations", []),
                "references": row.get("citations", []), "supporting_chunks": row.get("supporting_chunks", []),
                "review_status": "pending",
                "correctness": None, "citation_support": None, "review_notes": "",
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} pending answer review rows to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
