import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.normalization import normalize_parsed_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize and deduplicate an authorized parsed run.")
    parser.add_argument("parsed_run", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    run_id = args.run_id or f"normalized-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.urandom(3).hex()}"
    summary = normalize_parsed_run(
        source_run_directory=args.parsed_run,
        project_root=PROJECT_ROOT,
        destination_directory=PROJECT_ROOT / "knowledge_base" / "processed" / "normalized_runs" / run_id,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()