"""Strict registry validation for the opt-in, local academic demo policy.

This policy is intentionally separate from legal source/document approvals.
It grants only a bounded local evaluation scope and never records legal review.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any

from ..ingestion.parsing_job import document_id_for


POLICY_ID = "satell-local-academic-demo-v1"
REGISTRY_VERSION = "1.0"
AUTHORIZATION_SCOPE = "local_academic_evaluation_documentation_only"
SOURCE_AUTHORIZATION_STATUS = "operator_authorized_local_demo"
SOURCE_AUTHORIZATION_SCOPE = "local_academic_demo_only"
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DemoAuthorizationError(ValueError):
    """A missing, invalid, or mismatched local demo authorization registry."""


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    unsigned = {key: item for key, item in value.items() if key != "signature_hmac_sha256"}
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_registry(registry: dict[str, Any], api_token: str) -> dict[str, Any]:
    if not api_token or len(api_token) < 32:
        raise DemoAuthorizationError("Demo authorization signing key is unavailable.")
    result = dict(registry)
    result.pop("signature_hmac_sha256", None)
    key = hashlib.sha256(("satell-local-demo-v1\0" + api_token).encode("utf-8")).digest()
    result["signature_hmac_sha256"] = hmac.new(key, _canonical_bytes(result), hashlib.sha256).hexdigest()
    return result


def expected_document_map(inventory_path: str | Path) -> tuple[str, dict[str, dict[str, Any]], tuple[str, ...]]:
    path = Path(inventory_path)
    try:
        raw = path.read_bytes()
        lines = raw.decode("utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DemoAuthorizationError("Demo authorization inventory is unavailable.") from exc
    grouped: dict[str, dict[str, Any]] = {}
    sources: set[str] = set()
    all_ids: set[str] = set()
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DemoAuthorizationError("Demo authorization inventory is invalid.") from exc
        if not isinstance(row, dict):
            raise DemoAuthorizationError("Demo authorization inventory is invalid.")
        if row.get("source_type") == "documentation" and row.get("file_category") == "documentation":
            source_id, content_hash, relative_path = row.get("source_id"), row.get("sha256"), row.get("relative_path")
            if (not isinstance(source_id, str) or not source_id
                    or not isinstance(content_hash, str) or not HEX_SHA256.fullmatch(content_hash)
                    or not isinstance(relative_path, str) or not relative_path or ".." in Path(relative_path).parts
                    or row.get("ingestion_status") != "candidate_not_reviewed"
                    or row.get("license_review_status") != "pending"):
                raise DemoAuthorizationError("Demo authorization inventory contains an ineligible documentation record.")
            document_id = document_id_for(row)
            if not HEX_SHA256.fullmatch(document_id):
                raise DemoAuthorizationError("Demo authorization inventory contains an invalid document identity.")
            prior = grouped.get(document_id)
            if prior is None:
                grouped[document_id] = {
                    "source_id": source_id,
                    "content_sha256": content_hash,
                    "provenance_paths": [relative_path.replace("\\", "/")],
                }
            else:
                if prior["source_id"] != source_id or prior["content_sha256"] != content_hash:
                    raise DemoAuthorizationError("Conflicting records share a document identity.")
                prior["provenance_paths"].append(relative_path.replace("\\", "/"))
            sources.add(source_id)
            all_ids.add(document_id)
    for document in grouped.values():
        paths = document["provenance_paths"]
        if len(paths) != len(set(paths)):
            raise DemoAuthorizationError("Duplicate inventory provenance path.")
        paths.sort()
    return hashlib.sha256(raw).hexdigest(), grouped, tuple(sorted(sources))


def validate_demo_registry(
    registry_path: str | Path,
    inventory_path: str | Path,
    api_token: str,
    *,
    operator: str | None = None,
    source_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        registry = json.loads(Path(registry_path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise DemoAuthorizationError("Demo authorization registry is unavailable.") from exc
    if not isinstance(registry, dict):
        raise DemoAuthorizationError("Demo authorization registry is invalid.")
    signature = registry.get("signature_hmac_sha256")
    if not isinstance(signature, str) or not HEX_SHA256.fullmatch(signature):
        raise DemoAuthorizationError("Demo authorization registry signature is invalid.")
    expected_signature = sign_registry(registry, api_token)["signature_hmac_sha256"]
    if not hmac.compare_digest(signature, expected_signature):
        raise DemoAuthorizationError("Demo authorization registry signature is invalid.")
    if (registry.get("registry_version") != REGISTRY_VERSION
            or registry.get("registry_type") != "document_operator_authorization"
            or registry.get("policy_id") != POLICY_ID
            or registry.get("authorization_scope") != AUTHORIZATION_SCOPE
            or not isinstance(registry.get("operator"), str) or not registry["operator"].strip()
            or not isinstance(registry.get("authorized_at"), str) or not registry["authorized_at"]
            or registry.get("legal_review_status") != "pending"):
        raise DemoAuthorizationError("Demo authorization registry policy metadata is invalid.")
    inventory_sha256, expected_documents, expected_sources = expected_document_map(inventory_path)
    if registry.get("inventory_sha256") != inventory_sha256:
        raise DemoAuthorizationError("Demo authorization registry does not match the current inventory.")
    if registry.get("source_ids") != list(expected_sources):
        raise DemoAuthorizationError("Demo authorization registry source scope does not match the inventory.")
    documents = registry.get("documents")
    if not isinstance(documents, dict) or set(documents) != set(expected_documents):
        raise DemoAuthorizationError("Demo authorization registry documents do not match the inventory.")
    record_count = 0
    for document_id, expected in expected_documents.items():
        row = documents.get(document_id)
        if (not isinstance(row, dict) or row.get("document_id") != document_id
                or row.get("source_id") != expected["source_id"]
                or row.get("content_sha256") != expected["content_sha256"]
                or row.get("provenance_paths") != expected["provenance_paths"]
                or row.get("policy_id") != POLICY_ID
                or row.get("authorization_scope") != AUTHORIZATION_SCOPE
                or row.get("operator_authorization_status") != SOURCE_AUTHORIZATION_STATUS
                or row.get("legal_review_status") != "pending"
                or row.get("operator") != registry.get("operator")
                or row.get("authorized_at") != registry.get("authorized_at")
                or row.get("inventory_record_count") != len(expected["provenance_paths"])):
            raise DemoAuthorizationError("Demo authorization registry contains a mismatched document.")
        point_ids = row.get("indexed_point_ids")
        if (not isinstance(point_ids, list) or not point_ids or any(not isinstance(value, str) or not value for value in point_ids)
                or len(point_ids) != len(set(point_ids))):
            raise DemoAuthorizationError("Demo authorization registry has an invalid indexed point mapping.")
        record_count += len(row["provenance_paths"])
    if (registry.get("authorized_inventory_record_count") != record_count
            or registry.get("authorized_document_count") != len(expected_documents)):
        raise DemoAuthorizationError("Demo authorization registry counts are invalid.")
    if operator is not None and registry.get("operator") != operator:
        raise DemoAuthorizationError("Demo authorization operator does not match the configured operator.")
    if source_registry is not None and (
            registry.get("operator") != source_registry.get("operator")
            or registry.get("authorized_at") != source_registry.get("authorized_at")
            or registry.get("inventory_sha256") != source_registry.get("inventory_sha256")):
        raise DemoAuthorizationError("Document registry does not bind to the source operator registry.")
    excluded = registry.get("excluded_documents")
    if not isinstance(excluded, dict):
        raise DemoAuthorizationError("Demo registry has no explicit excluded-document mapping.")
    expected_papers: dict[str, dict[str, Any]] = {}
    try:
        inventory_lines = Path(inventory_path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise DemoAuthorizationError("Demo authorization inventory is unavailable.") from exc
    for line in inventory_lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DemoAuthorizationError("Demo authorization inventory is invalid.") from exc
        if item.get("source_type") == "research_paper" and item.get("file_category") == "research_paper":
            document_id = document_id_for(item)
            identity = {"source_id": item.get("source_id"), "content_sha256": item.get("sha256")}
            previous = expected_papers.setdefault(document_id, identity)
            if previous != identity:
                raise DemoAuthorizationError("Research-paper identity is ambiguous.")
    if set(excluded) != set(expected_papers):
        raise DemoAuthorizationError("Demo registry research-paper exclusions do not match inventory.")
    for document_id, expected in expected_papers.items():
        row = excluded[document_id]
        if (not isinstance(row, dict) or row.get("document_id") != document_id
                or row.get("source_id") != expected["source_id"]
                or row.get("content_sha256") != expected["content_sha256"]
                or row.get("technical_status") != "excluded_pending_individual_license_review"
                or row.get("legal_review_status") != "pending"
                or row.get("operator_authorization_status") != SOURCE_AUTHORIZATION_STATUS
                or row.get("operator") != registry.get("operator")
                or row.get("authorized_at") != registry.get("authorized_at")):
            raise DemoAuthorizationError("Demo registry contains a mismatched excluded research paper.")
        point_ids = row.get("indexed_point_ids")
        if (not isinstance(point_ids, list) or not point_ids
                or any(not isinstance(value, str) or not value for value in point_ids)
                or len(point_ids) != len(set(point_ids))):
            raise DemoAuthorizationError("Demo registry has an invalid excluded paper point mapping.")
    all_point_ids = [point_id for group in list(documents.values()) + list(excluded.values())
                     for point_id in group["indexed_point_ids"]]
    if len(all_point_ids) != len(set(all_point_ids)):
        raise DemoAuthorizationError("Demo registry maps a Qdrant point more than once.")
    if (registry.get("indexed_document_count") != len(documents) + len(excluded)
            or registry.get("indexed_point_count") != len(all_point_ids)
            or registry.get("excluded_document_count") != len(excluded)):
        raise DemoAuthorizationError("Demo registry indexed identity counts are invalid.")
    return registry


def expected_source_map(inventory_path: str | Path) -> tuple[str, dict[str, dict[str, Any]]]:
    path = Path(inventory_path)
    try:
        raw = path.read_bytes()
        lines = raw.decode("utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DemoAuthorizationError("Source authorization inventory is unavailable.") from exc
    sources: dict[str, dict[str, Any]] = {}
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DemoAuthorizationError("Source authorization inventory is invalid.") from exc
        if not isinstance(row, dict):
            raise DemoAuthorizationError("Source authorization inventory is invalid.")
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise DemoAuthorizationError("Source authorization inventory contains an unknown source.")
        current = sources.setdefault(source_id, {
            "source_id": source_id,
            "source_name": row.get("source_name"),
            "source_type": row.get("source_type"),
            "source_urls": set(),
            "source_versions": set(),
            "repositories": set(),
            "source_commits": set(),
            "record_count": 0,
        })
        for field in ("source_name", "source_type"):
            if current.get(field) != row.get(field):
                raise DemoAuthorizationError("Source authorization inventory has conflicting source metadata.")
        for field, key in (("source_url", "source_urls"), ("source_version", "source_versions"),
                           ("repository", "repositories"), ("source_commit", "source_commits")):
            value = row.get(field)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise DemoAuthorizationError("Source authorization inventory contains invalid provenance metadata.")
                current[key].add(value)
        current["record_count"] += 1
    if not sources:
        raise DemoAuthorizationError("Source authorization inventory is empty.")
    for source in sources.values():
        for plural, singular in (("source_urls", "source_url"), ("source_versions", "source_version"),
                                 ("repositories", "repository"), ("source_commits", "source_commit")):
            values = sorted(source[plural])
            source[plural] = values
            source[singular] = values[0] if len(values) == 1 else None
    return hashlib.sha256(raw).hexdigest(), sources


def validate_source_registry(registry_path: str | Path, inventory_path: str | Path,
                             api_token: str, *, expected_source_ids: tuple[str, ...] | None = None) -> dict[str, Any]:
    try:
        registry = json.loads(Path(registry_path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise DemoAuthorizationError("Source operator authorization registry is unavailable.") from exc
    if not isinstance(registry, dict):
        raise DemoAuthorizationError("Source operator authorization registry is invalid.")
    signature = registry.get("signature_hmac_sha256")
    if not isinstance(signature, str) or not HEX_SHA256.fullmatch(signature):
        raise DemoAuthorizationError("Source operator authorization signature is invalid.")
    if not hmac.compare_digest(signature, sign_registry(registry, api_token)["signature_hmac_sha256"]):
        raise DemoAuthorizationError("Source operator authorization signature is invalid.")
    inventory_sha256, expected_sources = expected_source_map(inventory_path)
    records = registry.get("sources")
    if (registry.get("registry_version") != REGISTRY_VERSION
            or registry.get("registry_type") != "source_operator_authorization"
            or registry.get("policy_id") != POLICY_ID
            or registry.get("authorization_scope") != SOURCE_AUTHORIZATION_SCOPE
            or registry.get("inventory_sha256") != inventory_sha256
            or registry.get("legal_review_status") != "pending"
            or not isinstance(registry.get("operator"), str) or not registry["operator"].strip()
            or not isinstance(registry.get("authorized_at"), str) or not registry["authorized_at"]
            or not isinstance(records, dict) or set(records) != set(expected_sources)):
        raise DemoAuthorizationError("Source operator authorization registry does not match the inventory.")
    if expected_source_ids is not None and set(expected_source_ids) - set(records):
        raise DemoAuthorizationError("Document registry references an unauthorized source.")
    for source_id, expected in expected_sources.items():
        row = records.get(source_id)
        if (not isinstance(row, dict) or row.get("source_id") != source_id
                or row.get("operator_authorization_status") != SOURCE_AUTHORIZATION_STATUS
                or row.get("authorization_scope") != SOURCE_AUTHORIZATION_SCOPE
                or row.get("policy_id") != POLICY_ID
                or row.get("legal_review_status") != "pending"
                or row.get("validation_status") != "validated"
                or row.get("operator") != registry.get("operator")
                or row.get("authorized_at") != registry.get("authorized_at")
                or row.get("inventory_record_count") != expected["record_count"]
                or row.get("source_name") != expected["source_name"]
                or row.get("source_url") != expected["source_url"]
                or row.get("source_urls") != expected["source_urls"]
                or row.get("source_type") != expected["source_type"]
                or row.get("source_version") != expected["source_version"]
                or row.get("source_versions") != expected["source_versions"]
                or row.get("repository") != expected["repository"]
                or row.get("repositories") != expected["repositories"]
                or row.get("source_commit") != expected["source_commit"]
                or row.get("source_commits") != expected["source_commits"]
                or row.get("inventory_sha256") != inventory_sha256):
            raise DemoAuthorizationError("Source operator authorization contains a mismatched source.")
    if registry.get("source_count") != len(expected_sources):
        raise DemoAuthorizationError("Source operator authorization count is invalid.")
    return registry


def validate_local_demo_policy(policy_path: str | Path) -> dict[str, Any]:
    try:
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise DemoAuthorizationError("Local demo category policy is unavailable.") from exc
    if (not isinstance(policy, dict) or policy.get("policy_id") != POLICY_ID
            or policy.get("authorization_scope") != SOURCE_AUTHORIZATION_SCOPE
            or policy.get("permitted_source_types") != ["documentation"]
            or policy.get("permitted_file_categories") != ["documentation"]
            or set(policy.get("excluded_file_categories", [])) !=
            {"research_paper", "code", "image", "structured_data", "supporting_artifact"}
            or policy.get("legal_review_required") is not False
            or policy.get("legal_review_status") != "pending"
            or policy.get("production_authorization") is not False):
        raise DemoAuthorizationError("Local demo category policy is invalid.")
    return policy
