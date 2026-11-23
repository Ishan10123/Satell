"""Build machine-readable unsupported-format and license-review reports."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "knowledge_base" / "metadata"


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def classify(record):
    ext = record.get("extension", "[no_extension]").lower()
    category = record.get("file_category")
    if category == "image" or ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".woff", ".woff2", ".ttf", ".otf"}:
        return "binary_or_visual_asset", "none", "Not prose; image, font, or visual asset can be referenced by a page but should not become a text vector.", "Keep as asset; exclude from text ingestion."
    if category == "code":
        return "source_code_or_example", "low", "Executable source/example content is outside documentation text scope and may duplicate code samples.", "Keep excluded unless a reviewed source-code corpus is explicitly added."
    if ext in {".json", ".jsonl", ".yaml", ".yml", ".csv", ".xml", ".toml", ".ini"}:
        return "structured_text_candidate", "medium", "Contains machine-readable fields or records; parser support exists but parser support alone does not establish documentation scope or rights.", "Review path and purpose; only ingest if explicitly in approved documentation scope."
    if ext in {".dot", ".excalidraw", ".gliffy"}:
        return "diagram_source", "low", "Diagram source is not reliably useful as standalone prose and may contain embedded or generated content.", "Keep excluded; consider diagram-specific extraction in a separate reviewed task."
    if category == "supporting_artifact" or ext in {".inv", "[no_extension]", ".sh", ".conf"}:
        return "generated_or_supporting_artifact", "low", "Build, navigation, configuration, or operational artifact rather than user-facing documentation.", "Keep excluded unless manually identified as a documentation source."
    return "unclassified", "manual_review", "Automated classification cannot establish that this item is meaningful documentation.", "Manually inspect and keep excluded until scope is reviewed."


def build_unsupported():
    audit = json.loads((META / "ingestion_audit_20261116.json").read_text(encoding="utf-8"))
    rows = [r for r in audit["records"] if r.get("discovery_status") == "unsupported_category"]
    extensions, sources, categories, classes = Counter(), Counter(), Counter(), Counter()
    records = []
    for row in rows:
        ext = row.get("extension") or "[no_extension]"
        kind, priority, reason, action = classify(row)
        extensions[ext] += 1
        sources[row.get("source_id", "unknown")] += 1
        categories[row.get("file_category", "unknown")] += 1
        classes[kind] += 1
        records.append({
            "document_id": row.get("document_id"), "source_id": row.get("source_id"),
            "file_path": row.get("file_path"), "local_path": row.get("local_path"),
            "extension": ext, "file_category": row.get("file_category"),
            "processing_status": row.get("processing_status"),
            "authorization_status": row.get("authorization_status"),
            "current_exclusion_reason": row.get("exclusion_reason"),
            "proposed_classification": kind, "proposed_parser": {
                ".json": "json", ".jsonl": "jsonl", ".yaml": "yaml", ".yml": "yaml",
                ".csv": "csv", ".xml": "xml", ".toml": "toml", ".ini": "ini",
            }.get(ext, "none"),
            "priority": priority, "reason": reason, "recommended_action": action,
        })
    result = {
        "report_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "inventory_report": "ingestion_audit_20261116.json", "total_unsupported_records": len(rows),
        "excluded_records_remain_excluded": True,
        "extension_counts": dict(sorted(extensions.items())),
        "source_counts": dict(sorted(sources.items())),
        "file_category_counts": dict(sorted(categories.items())),
        "proposed_classification_counts": dict(sorted(classes.items())),
        "records": records,
    }
    (META / "unsupported_format_review_20261116.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_license_review():
    approvals = json.loads((META / "source_approvals.json").read_text(encoding="utf-8-sig"))
    evidence = list(read_jsonl(META / "license_evidence.jsonl"))
    inventory = list(read_jsonl(META / "ingestion_inventory.jsonl"))
    by_source: dict[str, list] = {}
    for item in evidence:
        by_source.setdefault(item.get("source_id", "unknown"), []).append(item)
    counts = Counter(row.get("source_id", "unknown") for row in inventory)
    sources = []
    for source_id, decision in sorted(approvals["sources"].items()):
        artifacts = []
        for item in by_source.get(source_id, []):
            path = Path(item.get("path", ""))
            exists = path.is_file()
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if exists else None
            artifacts.append({"path": str(path), "exists": exists, "catalog_sha256": item.get("sha256"),
                              "current_sha256": digest, "checksum_matches": bool(exists and digest == item.get("sha256")),
                              "evidence_status": item.get("evidence_status"), "location": item.get("location")})
        sources.append({
            "source_id": source_id, "decision_status": decision.get("status", "pending_review"),
            "inventory_record_count": counts[source_id], "discovered_document_count": decision.get("discovered_document_count"),
            "evidence_artifacts": artifacts,
            "review_status": "pending human review; no approval made",
            "scope_note": ("Each arXiv paper requires its own evidence and document decision." if source_id.startswith("arxiv_") else
                           "Review must define documentation-only scope; root license files do not cover third-party assets or unsupported files."),
        })
    result = {"report_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(),
              "approval_registry": "source_approvals.json", "sources": sources,
              "all_sources_pending": all(s["decision_status"] == "pending_review" for s in sources),
              "approvals_changed": False}
    (META / "license_review_status_20261116.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build_unsupported()
    build_license_review()
    print("Created unsupported format and license review reports.")
