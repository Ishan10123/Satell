"""Create a pending human-label template from a retrieval diagnostics JSON file."""
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
        parser.error("The results file must contain a non-empty results array.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(rows, 1):
            candidates = []
            for result in row.get("results", []):
                candidates.append({key: result.get(key) for key in
                    ("rank", "source_id", "document_id", "chunk_id", "title", "file_path", "text_preview")})
            item = {
                "query_id": row.get("query_id", f"q{index:03d}"),
                "question": row.get("question"),
                "review_status": "pending",
                "relevant_chunk_ids": [],
                "ranked_candidates": candidates,
                "review_notes": "",
            }
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} pending judgment rows to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
