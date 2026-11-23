
import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl"
APPROVAL_PATH = PROJECT_ROOT / "knowledge_base" / "metadata" / "source_approvals.json"


def read_inventory():
    records = []

    with INVENTORY_PATH.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid inventory JSON at line {line_number}"
                ) from exc

    return records


def main():
    if not INVENTORY_PATH.is_file():
        raise FileNotFoundError(
            f"Inventory not found: {INVENTORY_PATH}"
        )

    if APPROVAL_PATH.exists():
        raise FileExistsError(
            f"Approval registry already exists: {APPROVAL_PATH}. "
            "Refusing to overwrite existing approval decisions."
        )

    records = read_inventory()
    grouped = defaultdict(list)

    for record in records:
        grouped[record["source_id"]].append(record)

    registry = {
        "registry_version": "1.0",
        "approval_policy": "explicit_source_level_approval",
        "default_status": "pending_review",
        "sources": {}
    }

    for source_id, source_records in sorted(grouped.items()):
        registry["sources"][source_id] = {
            "status": "pending_review",
            "reviewed_by": None,
            "reviewed_at": None,
            "license_name": None,
            "license_url": None,
            "evidence_path": None,
            "review_notes": None,
            "discovered_document_count": len(source_records)
        }

    APPROVAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with APPROVAL_PATH.open("x", encoding="utf-8") as file:
        json.dump(registry, file, indent=2, ensure_ascii=False)

    print(f"Sources registered: {len(registry['sources'])}")
    print(f"Registry created: {APPROVAL_PATH}")
    print("All sources remain pending_review.")


if __name__ == "__main__":
    main()
