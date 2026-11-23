"""Versioned readiness manifest layered over the Qdrant compatibility marker."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .qdrant_store import IndexCompatibilityError


def source_manifest_checksum(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def index_manifest_path(project_root: str | Path, collection_name: str) -> Path:
    return Path(project_root).resolve() / "knowledge_base" / "metadata" / "index_manifests" / f"{collection_name}.json"


def write_index_manifest(project_root: str | Path, *, index_id: str, vector_store: Any,
                         tokenizer: Any, chunking_config: dict[str, Any], source_ids: list[str],
                         document_count: int, chunk_count: int, source_manifest_sha256: str,
                         status: str,
                         authorization_mode: str = "reviewed_source_and_document_approval") -> dict[str, Any]:
    if status not in {"building", "ready", "failed"}:
        raise ValueError("Index status must be building, ready, or failed.")
    manifest = {
        "manifest_version": "1.0", "index_id": index_id,
        "collection_name": vector_store.collection_name,
        "embedding_model": vector_store.embedding.model_name,
        "embedding_model_version": vector_store.embedding.model_digest,
        "embedding_dimensions": vector_store.embedding.dimensions,
        "distance_metric": "Cosine",
        "tokenizer_identifier": getattr(tokenizer, "identifier", getattr(tokenizer, "model_id", type(tokenizer).__name__)),
        "tokenizer_version": getattr(tokenizer, "runtime_version", getattr(tokenizer, "tokenizer_version", "unknown")),
        "tokenizer_sha256": getattr(tokenizer, "sha256", None),
        "chunking_configuration": chunking_config,
        "authorized_source_ids": sorted(set(source_ids)),
        "document_count": document_count, "chunk_count": chunk_count,
        "source_manifest_sha256": source_manifest_sha256,
        "authorization_mode": authorization_mode,
        "created_at": datetime.now(timezone.utc).isoformat(), "status": status,
    }
    path = index_manifest_path(project_root, vector_store.collection_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return manifest


def validate_index_manifest(vector_store: Any, project_root: str | Path | None = None,
                            tokenizer: Any | None = None,
                            chunking_config: dict[str, Any] | None = None,
                            source_manifest_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root or vector_store.project_root).resolve()
    path = index_manifest_path(root, vector_store.collection_name)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexCompatibilityError("Versioned index manifest is missing or unreadable.") from exc
    expected = {
        "manifest_version": "1.0", "collection_name": vector_store.collection_name,
        "embedding_model": vector_store.embedding.model_name,
        "embedding_model_version": vector_store.embedding.model_digest,
        "embedding_dimensions": vector_store.embedding.dimensions,
        "distance_metric": "Cosine", "status": "ready",
    }
    if not isinstance(value, dict) or any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise IndexCompatibilityError("Versioned index manifest is not ready or does not match configured models.")
    if tokenizer is not None:
        tokenizer_expected = {
            "tokenizer_identifier": getattr(tokenizer, "identifier", getattr(tokenizer, "model_id", type(tokenizer).__name__)),
            "tokenizer_version": getattr(tokenizer, "runtime_version", getattr(tokenizer, "tokenizer_version", "unknown")),
            "tokenizer_sha256": getattr(tokenizer, "sha256", None),
        }
        if any(value.get(key) != expected_value for key, expected_value in tokenizer_expected.items()):
            raise IndexCompatibilityError("Index tokenizer does not match the configured tokenizer asset.")
    if chunking_config is not None and value.get("chunking_configuration") != chunking_config:
        raise IndexCompatibilityError("Index chunking configuration does not match the current configuration.")
    if source_manifest_path is not None:
        try:
            current_checksum = source_manifest_checksum(source_manifest_path)
        except OSError as exc:
            raise IndexCompatibilityError("Source inventory is missing or unreadable.") from exc
        if value.get("source_manifest_sha256") != current_checksum:
            raise IndexCompatibilityError("Index source inventory checksum does not match the current inventory.")
    health = vector_store.health_check()
    if health.get("healthy") is not True or health.get("points_count") != value.get("chunk_count"):
        raise IndexCompatibilityError("Qdrant collection state does not match the ready index manifest.")
    if type(value.get("document_count")) is not int or value["document_count"] < 1 or type(value.get("chunk_count")) is not int or value["chunk_count"] < 1:
        raise IndexCompatibilityError("Ready manifest has invalid document or chunk counts.")
    if not isinstance(value.get("source_manifest_sha256"), str) or len(value["source_manifest_sha256"]) != 64:
        raise IndexCompatibilityError("Ready manifest is missing its source manifest checksum.")
    return value
