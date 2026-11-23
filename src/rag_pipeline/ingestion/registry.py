import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    source_type: str
    enabled: bool
    manifest_path: Path | None = None
    manifest_summary_path: Path | None = None
    metadata_path: Path | None = None
    audit_path: Path | None = None


@dataclass(frozen=True)
class IngestionConfig:
    project_root: Path
    inventory_path: Path
    summary_path: Path
    allowed_extensions: frozenset[str]
    allowed_categories: frozenset[str]
    require_license_approval: bool
    approved_license_statuses: frozenset[str]
    sources: tuple[SourceDefinition, ...]
    parser_registry_path: Path | None = None
    parser_supported_extensions: frozenset[str] = frozenset()


def resolve_project_path(project_root: Path, relative_path: str) -> Path:
    resolved_root = project_root.resolve()
    resolved_path = (resolved_root / relative_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"Path escapes project root: {relative_path}")
    return resolved_path


def load_config(config_path: str | Path) -> IngestionConfig:
    config_path = Path(config_path).resolve()
    with config_path.open("r", encoding="utf-8-sig") as file:
        raw: dict[str, Any] = json.load(file)
    if not isinstance(raw, dict) or raw.get("config_version") != "1.0":
        raise ValueError("Unsupported ingestion config version.")
    for field in ("project_root", "policy", "output", "sources"):
        if field not in raw:
            raise ValueError(f"Missing ingestion config field: {field}")
    configured_root = Path(raw["project_root"])
    project_root = (configured_root.resolve() if configured_root.is_absolute()
                    else (config_path.parent / configured_root).resolve())
    policy = raw["policy"]
    output = raw["output"]
    if not isinstance(policy, dict) or not isinstance(output, dict):
        raise ValueError("Ingestion policy and output must be objects.")
    require_license_approval = policy.get("require_license_approval")
    if not isinstance(require_license_approval, bool):
        raise ValueError("policy.require_license_approval must be a boolean.")
    allowed_extensions = policy.get("allowed_extensions")
    allowed_categories = policy.get("allowed_documentation_categories")
    approved_license_statuses = policy.get("approved_license_statuses")
    parser_registry_value = raw.get("parser_registry")
    parser_registry_path = resolve_project_path(project_root, parser_registry_value) if parser_registry_value else None
    parser_supported_extensions: frozenset[str] = frozenset()
    if parser_registry_path is not None:
        try:
            parser_config = json.loads(parser_registry_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Parser registry is missing or invalid.") from exc
        parser_entries = parser_config.get("parsers") if isinstance(parser_config, dict) else None
        if not isinstance(parser_config, dict) or parser_config.get("config_version") != "1.0" or not isinstance(parser_entries, dict):
            raise ValueError("Parser registry has an invalid shape.")
        parser_supported_extensions = frozenset(ext.lower() for ext, spec in parser_entries.items()
                                               if isinstance(spec, dict) and spec.get("enabled") is True)
    if not isinstance(allowed_extensions, list) or not allowed_extensions:
        raise ValueError("policy.allowed_extensions must be a non-empty list.")
    if not isinstance(allowed_categories, list) or not allowed_categories:
        raise ValueError("policy.allowed_documentation_categories must be a non-empty list.")
    if not isinstance(approved_license_statuses, list):
        raise ValueError("policy.approved_license_statuses must be a list.")
    if any(not isinstance(value, str) or not value.startswith(".") for value in allowed_extensions):
        raise ValueError("Allowed extensions must be strings beginning with '.'.")
    if parser_registry_path is not None and not {v.lower() for v in allowed_extensions} <= parser_supported_extensions:
        raise ValueError("Ingestion eligibility includes an extension without an enabled parser.")
    if any(not isinstance(value, str) or not value for value in allowed_categories + approved_license_statuses):
        raise ValueError("Category and license status values must be non-empty strings.")
    if not isinstance(raw["sources"], list):
        raise ValueError("sources must be a list.")

    sources = []
    for item in raw["sources"]:
        if not isinstance(item, dict):
            raise ValueError("Each source configuration must be an object.")
        source_id = item.get("source_id")
        source_type = item.get("source_type")
        enabled = item.get("enabled")
        if not isinstance(source_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", source_id):
            raise ValueError(f"Invalid source ID: {source_id!r}")
        if source_type not in {"documentation_manifest", "arxiv_metadata"}:
            raise ValueError(f"Unsupported source type: {source_type}")
        if not isinstance(enabled, bool):
            raise ValueError(f"enabled must be a boolean for {source_id}.")
        source = SourceDefinition(
            source_id=source_id,
            source_type=source_type,
            enabled=enabled,
            manifest_path=resolve_project_path(project_root, item["manifest_path"]) if item.get("manifest_path") else None,
            manifest_summary_path=resolve_project_path(project_root, item["manifest_summary_path"]) if item.get("manifest_summary_path") else None,
            metadata_path=resolve_project_path(project_root, item["metadata_path"]) if item.get("metadata_path") else None,
            audit_path=resolve_project_path(project_root, item["audit_path"]) if item.get("audit_path") else None,
        )
        if source.enabled:
            required_paths = {
                "documentation_manifest": (source.manifest_path, source.manifest_summary_path),
                "arxiv_metadata": (source.metadata_path, source.audit_path),
            }[source.source_type]
            if any(path is None for path in required_paths):
                raise ValueError(f"Required metadata paths are missing for {source_id}.")
        sources.append(source)

    if len({source.source_id for source in sources}) != len(sources):
        raise ValueError("Duplicate source IDs found in configuration.")
    for field in ("inventory_jsonl", "summary_json"):
        if not isinstance(output.get(field), str) or not output[field]:
            raise ValueError(f"output.{field} must be a non-empty path.")

    return IngestionConfig(
        project_root=project_root,
        inventory_path=resolve_project_path(project_root, output["inventory_jsonl"]),
        summary_path=resolve_project_path(project_root, output["summary_json"]),
        allowed_extensions=frozenset(value.lower() for value in allowed_extensions),
        allowed_categories=frozenset(allowed_categories),
        require_license_approval=require_license_approval,
        approved_license_statuses=frozenset(approved_license_statuses),
        sources=tuple(sources),
        parser_registry_path=parser_registry_path,
        parser_supported_extensions=parser_supported_extensions,
    )


def validate_registry(config: IngestionConfig) -> None:
    if not config.project_root.is_dir():
        raise FileNotFoundError(f"Project root does not exist: {config.project_root}")
    if not config.sources:
        raise ValueError("No sources are configured.")
    if config.parser_registry_path is not None and not config.parser_registry_path.is_file():
        raise FileNotFoundError(f"Parser registry file not found: {config.parser_registry_path}")
    for source in config.sources:
        if not source.enabled:
            continue
        paths = (source.manifest_path, source.manifest_summary_path, source.metadata_path, source.audit_path)
        for path in paths:
            if path is not None and not path.is_file():
                raise FileNotFoundError(f"Source metadata file not found: {path}")
