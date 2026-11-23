import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"E:\RAG_Project")
DOCS_ROOT = ROOT / "knowledge_base" / "raw" / "official_documentation"
METADATA_ROOT = ROOT / "knowledge_base" / "metadata"

MANIFEST_PATH = METADATA_ROOT / "documentation_manifest.jsonl"
SUMMARY_PATH = METADATA_ROOT / "documentation_manifest_summary.json"

SOURCES = [
    {
        "source_id": "python_3_13",
        "name": "Python Documentation",
        "root": DOCS_ROOT / "python" / "3.13" / "python-3.13-docs-html",
        "source_url": "https://docs.python.org/3.13/",
        "version": "3.13",
        "commit": None,
        "repository": None
    },
    {
        "source_id": "postgresql_18",
        "name": "PostgreSQL Documentation",
        "root": DOCS_ROOT / "postgresql" / "18",
        "source_url": "https://www.postgresql.org/files/documentation/pdf/18/postgresql-18-A4.pdf",
        "version": "18",
        "commit": None,
        "repository": None
    },
    {
        "source_id": "fastapi",
        "name": "FastAPI Documentation",
        "root": DOCS_ROOT / "fastapi" / "docs",
        "source_url": "https://github.com/fastapi/fastapi",
        "version": "0.162.7",
        "commit": "5758a9c8347d911444dca97a55b708cc4a8de4f8",
        "repository": "https://github.com/fastapi/fastapi.git"
    },
    {
        "source_id": "qdrant",
        "name": "Qdrant Documentation",
        "root": DOCS_ROOT / "qdrant" / "documentation",
        "source_url": "https://qdrant.tech/documentation/",
        "version": None,
        "commit": "799edaa9d0ef562790402d6d4ddf370db92162e5",
        "repository": "https://github.com/qdrant/landing_page.git"
    },
    {
        "source_id": "huggingface_transformers",
        "name": "Hugging Face Transformers Documentation",
        "root": DOCS_ROOT / "huggingface_transformers" / "docs",
        "source_url": "https://huggingface.co/docs/transformers/",
        "version": None,
        "commit": "3a134bc37f7c22c801b618e289b0255425f22647",
        "repository": "https://github.com/huggingface/transformers.git"
    },
    {
        "source_id": "pytorch",
        "name": "PyTorch Documentation",
        "root": DOCS_ROOT / "pytorch" / "docs",
        "source_url": "https://pytorch.org/docs/stable/",
        "version": None,
        "commit": "242a9cf0e013551eaada7827cfff1aa8d293dfb1",
        "repository": "https://github.com/pytorch/pytorch.git"
    },
    {
        "source_id": "docker",
        "name": "Docker Documentation",
        "root": DOCS_ROOT / "docker" / "docs",
        "source_url": "https://docs.docker.com/",
        "version": None,
        "commit": "553482ce632f00c6e7faabab863422b4916e7c18",
        "repository": "https://github.com/docker/docs.git"
    }
]

EXTENSION_CATEGORIES = {
    ".md": "documentation",
    ".rst": "documentation",
    ".txt": "documentation",
    ".html": "documentation",
    ".htm": "documentation",
    ".pdf": "documentation",
    ".py": "code",
    ".js": "code",
    ".mjs": "code",
    ".ts": "code",
    ".go": "code",
    ".rs": "code",
    ".java": "code",
    ".cs": "code",
    ".sh": "code",
    ".ps1": "code",
    ".yaml": "structured_data",
    ".yml": "structured_data",
    ".json": "structured_data",
    ".toml": "structured_data",
    ".ini": "structured_data",
    ".conf": "structured_data",
    ".xml": "structured_data",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".avif": "image",
    ".svg": "image",
    ".gif": "image",
    ".bmp": "image"
}


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def classify_file(path):
    extension = path.suffix.lower()
    category = EXTENSION_CATEGORIES.get(extension, "supporting_artifact")

    ingestion_status = {
        "documentation": "candidate_not_reviewed",
        "code": "candidate_not_reviewed",
        "structured_data": "review_required",
        "image": "supporting_asset",
        "supporting_artifact": "review_required"
    }[category]

    return category, ingestion_status


def main():
    METADATA_ROOT.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "manifest_version": "1.0",
        "generated_at": generated_at,
        "manifest_path": str(MANIFEST_PATH),
        "sources": [],
        "total_files": 0,
        "total_bytes": 0,
        "categories": {},
        "extensions": {}
    }

    total_categories = Counter()
    total_extensions = Counter()
    temporary_manifest = MANIFEST_PATH.with_suffix(".jsonl.tmp")

    with temporary_manifest.open("w", encoding="utf-8") as output:
        for source in SOURCES:
            source_root = source["root"]

            if not source_root.exists():
                raise FileNotFoundError(
                    f"Source directory does not exist: {source_root}"
                )

            source_files = sorted(
                path for path in source_root.rglob("*") if path.is_file()
            )

            source_summary = {
                "source_id": source["source_id"],
                "name": source["name"],
                "root": str(source_root),
                "source_url": source["source_url"],
                "version": source["version"],
                "commit": source["commit"],
                "repository": source["repository"],
                "file_count": 0,
                "total_bytes": 0,
                "categories": {},
                "extensions": {}
            }

            source_categories = Counter()
            source_extensions = Counter()

            for path in source_files:
                relative_path = path.relative_to(source_root).as_posix()
                extension = path.suffix.lower() or "[no_extension]"
                file_size = path.stat().st_size
                category, ingestion_status = classify_file(path)

                record = {
                    "manifest_version": "1.0",
                    "source_id": source["source_id"],
                    "source_name": source["name"],
                    "source_url": source["source_url"],
                    "source_version": source["version"],
                    "source_commit": source["commit"],
                    "repository": source["repository"],
                    "relative_path": relative_path,
                    "file_name": path.name,
                    "extension": extension,
                    "file_category": category,
                    "ingestion_status": ingestion_status,
                    "file_size_bytes": file_size,
                    "sha256": calculate_sha256(path),
                    "source_file_modified_at": datetime.fromtimestamp(
                        path.stat().st_mtime,
                        timezone.utc
                    ).isoformat(),
                    "manifest_generated_at": generated_at,
                    "license_review_status": "pending"
                }

                output.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )

                source_categories[category] += 1
                source_extensions[extension] += 1
                total_categories[category] += 1
                total_extensions[extension] += 1

                source_summary["file_count"] += 1
                source_summary["total_bytes"] += file_size

            source_summary["categories"] = dict(source_categories)
            source_summary["extensions"] = dict(source_extensions)
            summary["sources"].append(source_summary)
            summary["total_files"] += source_summary["file_count"]
            summary["total_bytes"] += source_summary["total_bytes"]

            print(
                f"{source['source_id']}: "
                f"{source_summary['file_count']} files, "
                f"{source_summary['total_bytes']:,} bytes"
            )

    temporary_manifest.replace(MANIFEST_PATH)

    summary["categories"] = dict(total_categories)
    summary["extensions"] = dict(total_extensions)

    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("\nDocumentation manifest generated.")
    print(f"Total files: {summary['total_files']:,}")
    print(f"Total size: {summary['total_bytes']:,} bytes")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()