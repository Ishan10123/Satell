"""Explicit, evidence-backed source and per-document review records."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any


def load_approval_paths(project_root: str | Path) -> dict[str, Path]:
    root = Path(project_root).resolve()
    config_path = root / "configs" / "approval.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Approval workflow configuration is missing or invalid.") from exc
    if not isinstance(config, dict) or config.get("config_version") != "1.0":
        raise ValueError("Unsupported approval workflow configuration version.")
    result = {}
    for key in ("source_registry", "document_registry", "evidence_catalog"):
        value = config.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Approval workflow configuration is missing {key}.")
        candidate = (root / value).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"Configured {key} escapes the project root.")
        result[key] = candidate
    return result


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
    temp.replace(path)


def _evidence(evidence_path: str | Path, expected_source: str, project_root: Path,
              expected_document: str | None = None) -> dict[str, Any]:
    path = Path(evidence_path).resolve(strict=True)
    if not path.is_relative_to(project_root) or not path.is_file():
        raise ValueError("Evidence must be an existing file inside the project root.")
    # Evidence records are JSON/JSONL with an explicit source binding. Plain license
    # text is not enough to establish which corpus source it covers.
    records: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8-sig")
        for line in raw.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
    except OSError as exc:
        raise ValueError("Evidence file cannot be read.") from exc
    bound = [item for item in records if item.get("source_id") == expected_source]
    if not bound:
        raise ValueError(f"Evidence does not explicitly identify source {expected_source!r}.")
    # A source-level arXiv decision must be backed by source metadata, never by
    # borrowing one paper's license row for the whole collection.
    if expected_source.startswith("arxiv_") and expected_document is None:
        bound = [item for item in bound if not item.get("document_id")]
        if not bound:
            raise ValueError("arXiv source review needs source-level evidence; per-paper evidence cannot approve the collection.")
    if expected_document is not None and not any(item.get("document_id") == expected_document for item in bound):
        raise ValueError("Evidence does not explicitly identify the expected document_id.")
    chosen = next((item for item in bound if expected_document is None or item.get("document_id") == expected_document), None)
    if not chosen or not isinstance(chosen.get("path"), str) or not isinstance(chosen.get("sha256"), str):
        raise ValueError("Evidence record must include the evidence file path and SHA-256.")
    recorded_artifact = Path(chosen["path"])
    artifact = (recorded_artifact if recorded_artifact.is_absolute() else project_root / recorded_artifact).resolve(strict=True)
    if not artifact.is_relative_to(project_root) or not artifact.is_file():
        raise ValueError("Evidence artifact must be an existing project-local file.")
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != chosen["sha256"]:
        raise ValueError("Evidence artifact checksum does not match its evidence record.")
    canonical_record_hash = hashlib.sha256(json.dumps(chosen, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"path": str(artifact.relative_to(project_root)), "sha256": chosen["sha256"],
            "catalog_path": str(path.relative_to(project_root)), "record_sha256": canonical_record_hash,
            "source_id": expected_source, "document_id": expected_document}


def decide_source(registry_path: str | Path, source_id: str, decision: str, reviewer: str,
                  evidence_path: str | Path, notes: str, project_root: str | Path,
                  license_name: str, approval_scope: str) -> dict[str, Any]:
    if decision not in {"approved", "rejected", "pending_review"} or not reviewer.strip() or not notes.strip() or not license_name.strip():
        raise ValueError("Decision, reviewer identity, license name, and review notes are required.")
    valid_scope = "paper_source_metadata_only" if source_id.startswith("arxiv_") else "documentation_candidates"
    if approval_scope != valid_scope:
        raise ValueError(f"Source {source_id} requires approval_scope={valid_scope!r}.")
    root = Path(project_root).resolve()
    ev = _evidence(evidence_path, source_id, root)
    path = Path(registry_path)
    registry = json.loads(path.read_text(encoding="utf-8-sig"))
    if source_id not in registry.get("sources", {}):
        raise ValueError(f"Unknown source_id: {source_id}")
    registry["sources"][source_id].update({
        "status": decision, "reviewed_by": reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "license_name": license_name.strip(),
        "approval_scope": approval_scope,
        "evidence_path": ev["path"], "evidence_sha256": ev["sha256"],
        "evidence_catalog": ev["catalog_path"], "evidence_record_sha256": ev["record_sha256"],
        "evidence_source_id": source_id, "review_notes": notes.strip(),
    })
    _atomic_json(path, registry)
    return registry["sources"][source_id]


def decide_document(registry_path: str | Path, document_id: str, source_id: str, decision: str,
                    reviewer: str, evidence_path: str | Path, notes: str,
                    project_root: str | Path, license_name: str) -> dict[str, Any]:
    if not document_id or decision not in {"approved", "rejected", "pending_review"} or not reviewer.strip() or not notes.strip() or not license_name.strip():
        raise ValueError("Document ID, decision, reviewer identity, license name, and review notes are required.")
    root = Path(project_root).resolve()
    ev = _evidence(evidence_path, source_id, root, document_id)
    path = Path(registry_path)
    registry = {"registry_version": "1.0", "documents": {}}
    if path.is_file():
        registry = json.loads(path.read_text(encoding="utf-8-sig"))
    documents = registry.setdefault("documents", {})
    documents[document_id] = {
        "source_id": source_id, "status": decision, "reviewed_by": reviewer.strip(),
        "license_name": license_name.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(), "evidence_path": ev["path"],
        "evidence_sha256": ev["sha256"], "evidence_catalog": ev["catalog_path"],
        "evidence_record_sha256": ev["record_sha256"], "evidence_source_id": source_id,
        "document_id": document_id, "review_notes": notes.strip(),
    }
    _atomic_json(path, registry)
    return documents[document_id]


def validate_record(record: dict[str, Any], source_id: str, project_root: str | Path,
                    document_id: str | None = None) -> bool:
    try:
        root = Path(project_root).resolve()
        path = (root / record["evidence_path"]).resolve(strict=True)
        catalog = (root / record["evidence_catalog"]).resolve(strict=True)
        if not path.is_relative_to(root) or not catalog.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != record.get("evidence_sha256"):
            return False
        if record.get("evidence_source_id") != source_id:
            return False
        if document_id is not None and record.get("document_id") != document_id:
            return False
        records = []
        for line in catalog.read_text(encoding="utf-8-sig").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
        matched = []
        for item in records:
            if item.get("source_id") != source_id or not isinstance(item.get("path"), str):
                continue
            catalog_artifact = Path(item["path"])
            catalog_artifact = (catalog_artifact if catalog_artifact.is_absolute() else root / catalog_artifact)
            try:
                resolved_catalog_artifact = catalog_artifact.resolve(strict=True)
            except (OSError, RuntimeError, ValueError):
                continue
            if resolved_catalog_artifact.is_relative_to(root) and resolved_catalog_artifact == path:
                matched.append(item)
        if not matched:
            return False
        if document_id is not None:
            matched = [item for item in matched if item.get("document_id") == document_id]
        else:
            matched = [item for item in matched if not item.get("document_id")]
        if not matched:
            return False
        canonical = hashlib.sha256(json.dumps(matched[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if canonical != record.get("evidence_record_sha256"):
            return False
        return True
    except (KeyError, OSError, ValueError, TypeError):
        return False
