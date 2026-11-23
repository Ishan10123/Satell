import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.ingestion.discovery import (
    discover_documents,
    write_inventory,
)
from rag_pipeline.ingestion.registry import (
    load_config,
    validate_registry,
)


def main():
    config_path = PROJECT_ROOT / "configs" / "ingestion_sources.json"

    config = load_config(config_path)
    validate_registry(config)

    candidates = discover_documents(config)
    summary = write_inventory(config, candidates)

    print("\n===== INGESTION DISCOVERY COMPLETE =====")
    print(f"Total candidates: {summary['total_candidates']}")
    print(
        "Eligible for processing: "
        f"{summary['eligible_for_processing']}"
    )

    print("\n===== DISCOVERY STATUS =====")
    for status, count in summary["discovery_status_counts"].items():
        print(f"{status}: {count}")

    print("\n===== SOURCE COUNTS =====")
    for source, count in summary["source_counts"].items():
        print(f"{source}: {count}")

    print("\n===== OUTPUT FILES =====")
    print(config.inventory_path)
    print(config.summary_path)


if __name__ == "__main__":
    main()
