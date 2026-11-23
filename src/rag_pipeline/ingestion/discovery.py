import json
from collections import Counter
from pathlib import Path
from typing import Any

from .registry import IngestionConfig, SourceDefinition


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected an object in {path} at line {line_number}")
            yield record


def load_documentation_roots(path: Path, project_root: Path) -> dict[str, Path]:
    with path.open("r", encoding="utf-8-sig") as file:
        summary = json.load(file)
    roots = {}
    for item in summary.get("sources", []):
        source_id = item.get("source_id")
        root = Path(item["root"]).resolve()
        if not isinstance(source_id, str) or not root.is_relative_to(project_root.resolve()):
            raise ValueError(f"Invalid or out-of-project documentation root: {item!r}")
        if source_id in roots:
            raise ValueError(f"Duplicate documentation source root: {source_id}")
        roots[source_id] = root
    return roots


def documentation_candidates(config: IngestionConfig, source: SourceDefinition) -> list[dict[str, Any]]:
    roots = load_documentation_roots(source.manifest_summary_path, config.project_root)
    candidates = []
    excluded_statuses = {"review_required", "supporting_asset"}
    for record in read_jsonl(source.manifest_path):
        source_id = record.get("source_id")
        relative_path = record.get("relative_path")
        if not isinstance(source_id, str) or source_id not in roots:
            raise ValueError(f"Unknown documentation source: {source_id!r}")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("Documentation manifest record has no relative_path.")
        root = roots[source_id]
        local_path = (root / relative_path).resolve()
        if not local_path.is_relative_to(root):
            raise ValueError(f"Manifest path escapes source root: {relative_path}")

        extension = str(record.get("extension", "")).lower()
        actual_extension = Path(relative_path).suffix.lower()
        category = record.get("file_category")
        ingestion_status = record.get("ingestion_status")
        license_status = record.get("license_review_status", "unknown")
        exists = local_path.is_file()
        if not exists:
            discovery_status = "missing_file"
        elif category not in config.allowed_categories:
            discovery_status = "unsupported_category"
        elif extension != actual_extension:
            discovery_status = "invalid_metadata"
        elif extension not in config.allowed_extensions:
            discovery_status = "unsupported_extension"
        elif ingestion_status in excluded_statuses:
            discovery_status = "explicitly_excluded"
        elif ingestion_status not in {"candidate_not_reviewed", "candidate"}:
            discovery_status = "invalid_ingestion_status"
        elif config.require_license_approval and license_status not in config.approved_license_statuses:
            discovery_status = "pending_license_review"
        else:
            discovery_status = "candidate"

        technically_eligible = discovery_status in {"candidate", "pending_license_review"}
        candidates.append({
            "source_type": "documentation",
            "source_id": source_id,
            "source_name": record.get("source_name"),
            "source_url": record.get("source_url"),
            "source_version": record.get("source_version"),
            "source_commit": record.get("source_commit"),
            "repository": record.get("repository"),
            "relative_path": relative_path,
            "file_name": record.get("file_name"),
            "extension": extension,
            "file_category": category,
            "ingestion_status": ingestion_status,
            "local_path": str(local_path),
            "file_size_bytes": record.get("file_size_bytes"),
            "sha256": record.get("sha256"),
            "license_review_status": license_status,
            "discovery_status": discovery_status,
            "eligible_for_processing": technically_eligible and (
                not config.require_license_approval or license_status in config.approved_license_statuses
            ),
        })
    return candidates


def arxiv_candidates(config: IngestionConfig, source: SourceDefinition) -> list[dict[str, Any]]:
    audit_records = {}
    for record in read_jsonl(source.audit_path):
        arxiv_id = record.get("arxiv_id")
        if arxiv_id in audit_records:
            raise ValueError(f"Duplicate arXiv audit record: {arxiv_id}")
        audit_records[arxiv_id] = record

    candidates = []
    for record in read_jsonl(source.metadata_path):
        arxiv_id = record.get("arxiv_id")
        if not isinstance(arxiv_id, str):
            raise ValueError("arXiv metadata record has no valid arxiv_id.")
        audit = audit_records.get(arxiv_id, {})
        local_path = Path(record["local_path"]).resolve()
        if not local_path.is_relative_to(config.project_root.resolve()):
            raise ValueError(f"arXiv path escapes project root: {local_path}")
        exists = local_path.is_file()
        audit_passed = audit.get("status") == "PASS"
        sha256_valid = audit.get("sha256_valid") is True
        ingestion_status = record.get("ingestion_status", "candidate_not_reviewed")
        if not exists:
            discovery_status = "missing_file"
        elif ingestion_status in {"review_required", "supporting_asset"}:
            discovery_status = "explicitly_excluded"
        elif ingestion_status not in {"candidate_not_reviewed", "candidate"}:
            discovery_status = "invalid_ingestion_status"
        elif not audit_passed or not sha256_valid:
            discovery_status = "audit_failed"
        else:
            discovery_status = "pending_license_review"
        candidates.append({
            "source_type": "research_paper",
            "source_id": f"arxiv_{record.get('collection', 'unknown')}",
            "source_name": "arXiv Research Paper",
            "source_url": record.get("source_url"),
            "source_version": record.get("versioned_id"),
            "source_commit": None,
            "repository": None,
            "arxiv_id": arxiv_id,
            "title": record.get("title"),
            "authors": record.get("authors", []),
            "abstract": record.get("abstract"),
            "published": record.get("published"),
            "updated": record.get("updated"),
            "categories": record.get("categories", []),
            "relative_path": None,
            "file_name": local_path.name,
            "extension": local_path.suffix.lower(),
            "file_category": "research_paper",
            "ingestion_status": record.get("ingestion_status", "candidate_not_reviewed"),
            "local_path": str(local_path),
            "file_size_bytes": record.get("file_size_bytes"),
            "sha256": record.get("sha256"),
            "audit_status": audit.get("status", "missing_audit_record"),
            "sha256_valid": sha256_valid,
            "license_review_status": "pending",
            "discovery_status": discovery_status,
            "eligible_for_processing": False,
        })
    return candidates


def discover_documents(config: IngestionConfig) -> list[dict[str, Any]]:
    candidates = []
    for source in config.sources:
        if not source.enabled:
            continue
        if source.source_type == "documentation_manifest":
            candidates.extend(documentation_candidates(config, source))
        elif source.source_type == "arxiv_metadata":
            candidates.extend(arxiv_candidates(config, source))
        else:
            raise ValueError(f"Unsupported source type: {source.source_type}")
    return candidates


def build_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "inventory_version": "1.1",
        "total_candidates": len(candidates),
        "eligible_for_processing": sum(record["eligible_for_processing"] for record in candidates),
        "discovery_status_counts": dict(Counter(record["discovery_status"] for record in candidates)),
        "source_counts": dict(Counter(record["source_id"] for record in candidates)),
        "extension_counts": dict(Counter(record["extension"] for record in candidates)),
    }


def write_inventory(config: IngestionConfig, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    config.inventory_path.parent.mkdir(parents=True, exist_ok=True)
    config.summary_path.parent.mkdir(parents=True, exist_ok=True)
    with config.inventory_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in candidates:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = build_summary(candidates)
    with config.summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)
    return summary