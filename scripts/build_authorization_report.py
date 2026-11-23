import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rag_pipeline.ingestion.approval import authorize_document, load_approval_registry
from rag_pipeline.ingestion.approval_workflow import load_approval_paths
from rag_pipeline.ingestion.registry import load_config

METADATA_DIR = PROJECT_ROOT / "knowledge_base" / "metadata"
INVENTORY_PATH = METADATA_DIR / "ingestion_inventory.jsonl"
APPROVAL_PATHS = load_approval_paths(PROJECT_ROOT)
APPROVAL_PATH = APPROVAL_PATHS["source_registry"]
DOCUMENT_APPROVAL_PATH = APPROVAL_PATHS["document_registry"]
OUTPUT_PATH = METADATA_DIR / "ingestion_authorization.jsonl"
SUMMARY_PATH = METADATA_DIR / "ingestion_authorization_summary.json"


def read_inventory():
    with INVENTORY_PATH.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid inventory JSON at line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object at inventory line {line_number}")
            yield record


def main():
    config = load_config(PROJECT_ROOT / "configs" / "ingestion_sources.json")
    registry = load_approval_registry(APPROVAL_PATH)
    document_registry = json.loads(DOCUMENT_APPROVAL_PATH.read_text(encoding="utf-8-sig")) if DOCUMENT_APPROVAL_PATH.is_file() else {}
    status_counts = Counter()
    authorized_count = 0
    total_count = 0
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as output:
        for document in read_inventory():
            result = authorize_document(
                document,
                registry,
                project_root=PROJECT_ROOT,
                allowed_extensions=config.allowed_extensions,
                approved_license_statuses=config.approved_license_statuses,
                document_approval_registry=document_registry,
            )
            output.write(json.dumps({
                "source_id": document.get("source_id"),
                "local_path": document.get("local_path"),
                "sha256": document.get("sha256"),
                "ingestion_status": document.get("ingestion_status"),
                "discovery_status": document.get("discovery_status"),
                "authorized": result["authorized"],
                "authorization_status": result["authorization_status"],
            }, ensure_ascii=False) + "\n")
            total_count += 1
            status_counts[result["authorization_status"]] += 1
            authorized_count += int(result["authorized"])
    summary = {
        "report_version": "1.1",
        "total_documents": total_count,
        "authorized_documents": authorized_count,
        "blocked_documents": total_count - authorized_count,
        "authorization_status_counts": dict(status_counts),
        "approval_registry": str(APPROVAL_PATH),
    }
    with SUMMARY_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
    print("\n===== AUTHORIZATION REPORT =====")
    print(json.dumps(summary, indent=2))
    print("\n===== OUTPUT FILES =====")
    print(OUTPUT_PATH)
    print(SUMMARY_PATH)


if __name__ == "__main__":
    main()
