import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .approval_workflow import validate_record


VALID_STATUSES = {"pending_review", "approved", "rejected"}
# Default processing eligibility, intentionally narrower than parser support.
ELIGIBLE_INGESTION_EXTENSIONS = frozenset({".md", ".html", ".rst", ".pdf", ".txt"})
SUPPORTED_EXTENSIONS = ELIGIBLE_INGESTION_EXTENSIONS
SUPPORTED_DOCUMENTATION_CATEGORIES = {"documentation"}
ALLOWED_INGESTION_STATUSES = {"candidate_not_reviewed", "candidate"}


def load_approval_registry(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as file:
        registry = json.load(file)
    if not isinstance(registry, dict) or registry.get("registry_version") != "1.0":
        raise ValueError("Unsupported approval registry version.")
    sources = registry.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("Approval registry must contain a sources object.")
    for source_id, entry in sources.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", source_id) or not isinstance(entry, dict):
            raise ValueError(f"Invalid approval registry entry: {source_id!r}")
        status = entry.get("status")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            raise ValueError(f"Invalid approval status for {source_id}: {status}")
        if status == "approved":
            required_fields = ("reviewed_by", "reviewed_at", "license_name", "evidence_path",
                               "evidence_sha256", "evidence_catalog", "evidence_record_sha256",
                               "evidence_source_id", "review_notes", "approval_scope")
            missing = [field for field in required_fields if not isinstance(entry.get(field), str) or not entry[field].strip()]
            if missing:
                raise ValueError(f"Approved source {source_id} is missing: {', '.join(missing)}")
    return registry


def _denied(status: str, source_id: str) -> dict[str, Any]:
    return {"authorized": False, "authorization_status": status, "source_id": source_id}


def authorize_document(
    document: dict[str, Any],
    registry: dict[str, Any],
    project_root: str | Path,
    allowed_extensions: set[str] | frozenset[str] | None = None,
    approved_license_statuses: set[str] | frozenset[str] | None = None,
    document_approval_registry: dict[str, Any] | None = None,
    operator_authorized_unreviewed: bool = False,
) -> dict[str, Any]:
    source_id = document.get("source_id")
    if not isinstance(source_id, str):
        return _denied("invalid_metadata", "unknown")

    path_value = document.get("local_path")
    if not isinstance(path_value, str) or not path_value:
        return _denied("invalid_path", source_id)
    try:
        local_path = Path(path_value).resolve(strict=False)
        if not local_path.is_relative_to(Path(project_root).resolve()):
            return _denied("path_outside_project", source_id)
    except (OSError, RuntimeError, TypeError, ValueError):
        return _denied("invalid_path", source_id)

    if not local_path.is_file():
        return _denied("missing_file", source_id)

    source_type = document.get("source_type")
    extension = local_path.suffix.lower()
    extension_policy = SUPPORTED_EXTENSIONS if allowed_extensions is None else allowed_extensions
    allowed = {value.lower() for value in extension_policy}
    if extension not in allowed:
        return _denied("unsupported_extension", source_id)
    if source_type == "documentation" and document.get("file_category") not in SUPPORTED_DOCUMENTATION_CATEGORIES:
        return _denied("unsupported_category", source_id)
    if source_type == "documentation":
        relative_path = document.get("relative_path")
        if not isinstance(relative_path, str) or not relative_path:
            return _denied("invalid_metadata", source_id)
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != extension:
            return _denied("invalid_metadata", source_id)
    ingestion_status = document.get("ingestion_status")
    if ingestion_status is not None and ingestion_status not in ALLOWED_INGESTION_STATUSES:
        return _denied("explicitly_excluded" if ingestion_status in {"review_required", "supporting_asset"} else "invalid_ingestion_status", source_id)
    if source_type == "documentation" and ingestion_status is None:
        return _denied("invalid_ingestion_status", source_id)

    if document.get("discovery_status") in {"missing_file", "audit_failed", "checksum_mismatch", "unsupported_extension", "unsupported_category", "invalid_metadata", "explicitly_excluded", "invalid_ingestion_status", "invalid_path"}:
        return _denied(str(document["discovery_status"]), source_id)

    expected_hash = document.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        return _denied("missing_or_invalid_checksum", source_id)
    digest = hashlib.sha256()
    try:
        with local_path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        actual_hash = digest.hexdigest()
        actual_size = local_path.stat().st_size
    except OSError:
        return _denied("file_integrity_check_failed", source_id)
    if actual_hash.lower() != expected_hash.lower():
        return _denied("checksum_mismatch", source_id)
    expected_size = document.get("file_size_bytes")
    if expected_size is not None and (type(expected_size) is not int or expected_size != actual_size):
        return _denied("file_size_mismatch", source_id)

    if source_type == "research_paper":
        if document.get("audit_status") != "PASS":
            return _denied("audit_failed", source_id)
        if document.get("sha256_valid") is not True:
            return _denied("checksum_not_valid", source_id)
    elif source_type != "documentation":
        return _denied("unsupported_source_type", source_id)

    # This mode is only for an explicitly operator-authorized development run.
    # It keeps file integrity, parser type, scope, and exclusion checks intact;
    # it does not mutate or impersonate a source/document license decision.
    if operator_authorized_unreviewed:
        return {"authorized": True, "authorization_status": "operator_authorized_unreviewed",
                "source_id": source_id}

    approval = registry.get("sources", {}).get(source_id)
    if approval is None:
        return _denied("source_not_registered", source_id)
    status = approval.get("status")
    if status != "approved":
        return _denied(f"source_{status}" if status in VALID_STATUSES else "invalid_approval_status", source_id)
    source_evidence_verified = validate_record(approval, source_id, project_root)
    if not source_evidence_verified:
        return _denied("source_approval_evidence_missing_or_changed", source_id)
    expected_scope = "paper_source_metadata_only" if source_type == "research_paper" else "documentation_candidates"
    if approval.get("approval_scope") != expected_scope:
        return _denied("source_approval_scope_mismatch", source_id)

    document_id = hashlib.sha256(f"{source_id}\0{expected_hash}".encode("utf-8")).hexdigest()
    document_decision = (document_approval_registry or {}).get("documents", {}).get(document_id)
    if source_type == "research_paper" and not isinstance(document_decision, dict):
        return _denied("document_approval_missing_or_pending", source_id)
    if isinstance(document_decision, dict):
        if document_decision.get("source_id") != source_id:
            return _denied("document_approval_source_mismatch", source_id)
        if document_decision.get("status") != "approved":
            return _denied("document_approval_rejected" if document_decision.get("status") == "rejected" else "document_approval_missing_or_pending", source_id)
        if not validate_record(document_decision, source_id, project_root, document_id):
            return _denied("document_approval_evidence_missing_or_changed", source_id)

    license_status = document.get("license_review_status")
    approved_licenses = {"approved"} if approved_license_statuses is None else approved_license_statuses
    if license_status == "rejected":
        return _denied("document_license_rejected", source_id)
    if license_status not in approved_licenses and source_type == "documentation" and (source_evidence_verified or document_decision is not None):
        # This is a source-scoped human decision grounded in verified evidence;
        # it applies only to documentation candidates (not excluded assets).
        license_status = "approved"
    if license_status not in approved_licenses and source_type == "research_paper" and document_decision is not None:
        # Research rights are resolved per paper, never inherited from the arXiv
        # query/collection source.
        license_status = "approved"
    if license_status not in approved_licenses:
        return _denied("document_license_pending_review" if license_status == "pending" else "document_license_evidence_missing", source_id)

    return {"authorized": True, "authorization_status": "approved", "source_id": source_id}
