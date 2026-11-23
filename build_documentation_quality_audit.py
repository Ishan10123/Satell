import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"E:\RAG_Project")
DOCS_ROOT = ROOT / "knowledge_base" / "raw" / "official_documentation"
METADATA_ROOT = ROOT / "knowledge_base" / "metadata"

MANIFEST_PATH = METADATA_ROOT / "documentation_manifest.jsonl"
REPORT_PATH = METADATA_ROOT / "documentation_quality_audit.json"

SOURCE_ROOTS = {
    "python_3_13": DOCS_ROOT / "python" / "3.13" / "python-3.13-docs-html",
    "postgresql_18": DOCS_ROOT / "postgresql" / "18",
    "fastapi": DOCS_ROOT / "fastapi" / "docs",
    "qdrant": DOCS_ROOT / "qdrant" / "documentation",
    "huggingface_transformers": DOCS_ROOT / "huggingface_transformers" / "docs",
    "pytorch": DOCS_ROOT / "pytorch" / "docs",
    "docker": DOCS_ROOT / "docker" / "docs"
}

SOURCE_REPOSITORIES = {
    "fastapi": DOCS_ROOT / "_sources" / "fastapi",
    "qdrant": DOCS_ROOT / "_sources" / "qdrant",
    "huggingface_transformers": DOCS_ROOT / "_sources" / "huggingface_transformers",
    "pytorch": DOCS_ROOT / "_sources" / "pytorch",
    "docker": DOCS_ROOT / "_sources" / "docker"
}

LICENSE_NAMES = {
    "license",
    "license.md",
    "license.txt",
    "copying",
    "copying.md",
    "copying.txt",
    "notice",
    "notice.md",
    "notice.txt"
}

SMALL_FILE_LIMIT = 100


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_manifest():
    records = []

    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            try:
                record = json.loads(line)
                record["_line_number"] = line_number
                records.append(record)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON at manifest line {line_number}: {error}"
                ) from error

    return records


def find_license_files():
    found = []

    for source_id, source_root in SOURCE_ROOTS.items():
        for path in source_root.rglob("*"):
            if path.is_file() and path.name.lower() in LICENSE_NAMES:
                found.append({
                    "source_id": source_id,
                    "path": str(path),
                    "location": "documentation_copy"
                })

    for source_id, source_root in SOURCE_REPOSITORIES.items():
        for path in source_root.iterdir():
            if path.is_file() and path.name.lower() in LICENSE_NAMES:
                found.append({
                    "source_id": source_id,
                    "path": str(path),
                    "location": "source_repository_root"
                })

    return found


def main():
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(MANIFEST_PATH)

    records = load_manifest()

    hash_groups = defaultdict(list)
    source_counts = Counter()
    extension_counts = Counter()
    category_counts = Counter()

    missing_files = []
    empty_files = []
    small_files = []
    checksum_mismatches = []
    unknown_extensions = []

    total_bytes = 0
    verified_files = 0

    for record in records:
        source_id = record["source_id"]
        source_root = SOURCE_ROOTS.get(source_id)

        if source_root is None:
            missing_files.append({
                "source_id": source_id,
                "relative_path": record["relative_path"],
                "reason": "Unknown source ID"
            })
            continue

        path = source_root / Path(record["relative_path"])

        if not path.is_file():
            missing_files.append({
                "source_id": source_id,
                "relative_path": record["relative_path"],
                "reason": "File not found"
            })
            continue

        file_size = path.stat().st_size
        actual_hash = calculate_sha256(path)
        verified_files += 1
        total_bytes += file_size

        source_counts[source_id] += 1
        extension_counts[record["extension"]] += 1
        category_counts[record["file_category"]] += 1

        if file_size == 0:
            empty_files.append({
                "source_id": source_id,
                "relative_path": record["relative_path"]
            })

        if 0 < file_size < SMALL_FILE_LIMIT:
            small_files.append({
                "source_id": source_id,
                "relative_path": record["relative_path"],
                "file_size_bytes": file_size
            })

        if actual_hash != record["sha256"]:
            checksum_mismatches.append({
                "source_id": source_id,
                "relative_path": record["relative_path"],
                "expected_sha256": record["sha256"],
                "actual_sha256": actual_hash
            })

        if record["extension"] == "[no_extension]":
            unknown_extensions.append({
                "source_id": source_id,
                "relative_path": record["relative_path"]
            })

        hash_groups[actual_hash].append({
            "source_id": source_id,
            "relative_path": record["relative_path"],
            "file_size_bytes": file_size
        })

    duplicate_groups = []

    for digest, files in hash_groups.items():
        if len(files) > 1:
            duplicate_groups.append({
                "sha256": digest,
                "duplicate_count": len(files),
                "files": files
            })

    duplicate_groups.sort(
        key=lambda group: group["duplicate_count"],
        reverse=True
    )

    license_files = find_license_files()

    report = {
        "audit_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_records": len(records),
        "verified_files": verified_files,
        "verified_total_bytes": total_bytes,
        "missing_files": missing_files,
        "empty_files": empty_files,
        "small_files_below_100_bytes": small_files,
        "checksum_mismatches": checksum_mismatches,
        "unknown_extension_files": unknown_extensions,
        "duplicate_hash_groups": duplicate_groups,
        "duplicate_file_count_in_groups": sum(
            group["duplicate_count"] for group in duplicate_groups
        ),
        "duplicate_excess_copies": sum(
            group["duplicate_count"] - 1 for group in duplicate_groups
        ),
        "license_file_candidates": license_files,
        "source_counts": dict(source_counts),
        "extension_counts": dict(extension_counts),
        "category_counts": dict(category_counts)
    }

    temporary_report = REPORT_PATH.with_suffix(".json.tmp")

    temporary_report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    temporary_report.replace(REPORT_PATH)

    print("\n========== DOCUMENTATION QUALITY AUDIT ==========")
    print(f"Manifest records: {len(records):,}")
    print(f"Verified files: {verified_files:,}")
    print(f"Verified bytes: {total_bytes:,}")
    print(f"Missing files: {len(missing_files):,}")
    print(f"Empty files: {len(empty_files):,}")
    print(f"Files below 100 bytes: {len(small_files):,}")
    print(f"Checksum mismatches: {len(checksum_mismatches):,}")
    print(f"Unknown extension files: {len(unknown_extensions):,}")
    print(f"Duplicate hash groups: {len(duplicate_groups):,}")
    print(f"Files in duplicate groups: {report['duplicate_file_count_in_groups']:,}")
    print(f"Excess duplicate copies: {report['duplicate_excess_copies']:,}")
    print(f"License file candidates: {len(license_files):,}")
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()