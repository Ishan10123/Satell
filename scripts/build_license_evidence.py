
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = PROJECT_ROOT / "knowledge_base" / "metadata" / "documentation_quality_audit.json"
SUMMARY_PATH = PROJECT_ROOT / "knowledge_base" / "metadata" / "documentation_manifest_summary.json"
OUTPUT_PATH = PROJECT_ROOT / "knowledge_base" / "metadata" / "license_evidence.jsonl"
REPORT_PATH = PROJECT_ROOT / "knowledge_base" / "metadata" / "license_evidence_summary.json"
MAX_LICENSE_BYTES = 512_000
MAX_TEXT_CHARS = 20_000


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def inspect_candidate(candidate):
    path = Path(candidate["path"]).resolve()

    if not path.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"License path escapes project root: {path}")

    result = {
        "source_id": candidate.get("source_id"),
        "path": str(path),
        "location": candidate.get("location"),
        "exists": path.is_file(),
        "file_size_bytes": None,
        "sha256": None,
        "text": None,
        "evidence_status": "pending_manual_review"
    }

    if not path.is_file():
        result["evidence_status"] = "missing"
        return result

    size = path.stat().st_size
    result["file_size_bytes"] = size
    result["sha256"] = sha256_file(path)

    if size > MAX_LICENSE_BYTES:
        result["evidence_status"] = "too_large_for_automatic_preview"
        return result

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        result["evidence_status"] = "not_decodable_as_utf8"
        return result

    result["text"] = text[:MAX_TEXT_CHARS]
    result["evidence_status"] = "text_extracted"

    if len(text) > MAX_TEXT_CHARS:
        result["text"] += "\n[PREVIEW TRUNCATED]"

    return result


def main():
    audit = load_json(AUDIT_PATH)
    manifest_summary = load_json(SUMMARY_PATH)

    candidates = audit.get("license_file_candidates", [])
    evidence = [inspect_candidate(item) for item in candidates]

    source_ids = [
        item["source_id"]
        for item in manifest_summary["sources"]
    ]

    summary = {
        "report_version": "1.0",
        "total_license_candidates": len(evidence),
        "existing_candidates": sum(item["exists"] for item in evidence),
        "missing_candidates": sum(not item["exists"] for item in evidence),
        "sources_requiring_review": source_ids,
        "approval_status": "not_approved",
        "evidence_status_counts": {}
    }

    for item in evidence:
        status = item["evidence_status"]
        summary["evidence_status_counts"][status] = (
            summary["evidence_status_counts"].get(status, 0) + 1
        )

    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as file:
        for item in evidence:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    with REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    print("\n===== LICENSE EVIDENCE REPORT =====")
    print(json.dumps(summary, indent=2))
    print("\n===== OUTPUT FILES =====")
    print(OUTPUT_PATH)
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
