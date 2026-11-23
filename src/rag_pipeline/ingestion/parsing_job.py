from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable
import unicodedata

from .approval import authorize_document
from ..parsing import DocumentParseError
from ..parsing import parse_file


RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")


def document_id_for(document: dict[str, Any]) -> str:
    """Legacy content-based ID retained for compatibility with the live index."""
    source_id = str(document.get("source_id", "unknown"))
    content_hash = str(document.get("sha256", ""))
    value = f"{source_id}\0{content_hash}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def document_identity_for(document: dict[str, Any]) -> str:
    """Version 2 document identity binds a source to its normalized relative path."""
    source_id = unicodedata.normalize("NFC", str(document.get("source_id", "unknown"))).strip().casefold()
    relative_path = str(document.get("relative_path", "")).replace("\\", "/")
    path_parts = [unicodedata.normalize("NFC", part).strip().casefold() for part in relative_path.split("/") if part not in {"", "."}]
    if not source_id or not path_parts or any(part == ".." for part in path_parts):
        raise ValueError("Version 2 document identity requires a source ID and safe relative path.")
    canonical = json.dumps({"identity_version": "2", "source_id": source_id, "relative_path": "/".join(path_parts)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(value, file, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _outcome_record(
    document: dict[str, Any],
    document_id: str,
    status: str,
    authorization_status: str,
    output_file: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "document_identity": document_identity_for(document),
        "source_id": document.get("source_id"),
        "source_type": document.get("source_type"),
        "content_hash": document.get("sha256"),
        "ingestion_status": document.get("ingestion_status"),
        "status": status,
        "authorization_status": authorization_status,
        "output_file": output_file,
        "error": error,
    }


def run_parsing_job(
    documents: Iterable[dict[str, Any]],
    approval_registry: dict[str, Any],
    project_root: str | Path,
    output_root: str | Path,
    allowed_extensions: set[str] | frozenset[str],
    approved_license_statuses: set[str] | frozenset[str],
    run_id: str | None = None,
    max_file_bytes: int = 50 * 1024 * 1024,
    document_approval_registry: dict[str, Any] | None = None,
    operator_authorized_unreviewed: bool = False,
    parser_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    processed_root = (project_root / "knowledge_base" / "processed").resolve()
    output_root = Path(output_root).resolve()
    if not output_root.is_relative_to(processed_root):
        raise ValueError("Parsing outputs must remain under knowledge_base/processed.")
    if run_id is None:
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"parse-{now}-{os.urandom(3).hex()}"
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Invalid parse run ID.")
    run_directory = (output_root / run_id).resolve()
    if not run_directory.is_relative_to(processed_root):
        raise ValueError("Parse run directory escapes processed output root.")
    run_directory.mkdir(parents=True, exist_ok=False)
    manifest_path = run_directory / "outcomes.jsonl"
    status_counts: Counter[str] = Counter()
    total_documents = 0
    authorized_documents = 0
    parsed_documents = 0
    parse_failures = 0

    with manifest_path.open("x", encoding="utf-8", newline="\n") as manifest:
        for document in documents:
            if not isinstance(document, dict):
                raise ValueError("Parsing job received a non-object inventory record.")
            total_documents += 1
            document_id = document_id_for(document)
            document_identity = document_identity_for(document)
            authorization = authorize_document(
                document,
                approval_registry,
                project_root=project_root,
                allowed_extensions=allowed_extensions,
                approved_license_statuses=approved_license_statuses,
                document_approval_registry=document_approval_registry,
                operator_authorized_unreviewed=operator_authorized_unreviewed,
            )
            if not authorization["authorized"]:
                status = "blocked"
                outcome = _outcome_record(
                    document,
                    document_id,
                    status,
                    authorization["authorization_status"],
                )
            else:
                authorized_documents += 1
                try:
                    parsed = parse_file(document["local_path"], max_file_bytes=max_file_bytes, parser_registry=parser_registry)
                except DocumentParseError as exc:
                    status = "parse_failed"
                    parse_failures += 1
                    outcome = _outcome_record(
                        document,
                        document_id,
                        status,
                        authorization["authorization_status"],
                        error=f"{type(exc).__name__}: {exc}",
                    )
                else:
                    status = "parsed"
                    parsed_documents += 1
                    output_name = f"{document_identity}.json"
                    output_path = run_directory / "documents" / output_name
                    _atomic_write_json(output_path, {
                        "document_id": document_id,
                        "document_identity": document_identity,
                        "legacy_document_id": document_id,
                        "source_id": document.get("source_id"),
                        "source_type": document.get("source_type"),
                        "title": parsed.title,
                        "content_hash": document.get("sha256"),
                        "source_url": document.get("source_url"),
                        "source_version": document.get("source_version"),
                        "relative_path": document.get("relative_path"),
                        "segments": [
                            {
                                "text": segment.text,
                                "segment_type": segment.segment_type,
                                "headings": list(segment.headings),
                                "page_number": segment.page_number,
                                "line_start": segment.line_start,
                                "line_end": segment.line_end,
                                "language": segment.language,
                                "symbol_name": segment.symbol_name,
                            }
                            for segment in parsed.segments
                        ],
                        "metadata": parsed.metadata,
                    })
                    outcome = _outcome_record(
                        document,
                        document_id,
                        status,
                        authorization["authorization_status"],
                        output_file=f"documents/{output_name}",
                    )
            status_counts[status] += 1
            manifest.write(json.dumps(outcome, ensure_ascii=False) + "\n")
            manifest.flush()
            os.fsync(manifest.fileno())

    summary = {
        "run_id": run_id,
        "total_documents": total_documents,
        "authorized_documents": authorized_documents,
        "parsed_documents": parsed_documents,
        "blocked_documents": status_counts["blocked"],
        "parse_failures": parse_failures,
        "status_counts": dict(status_counts),
        "authorization_mode": "operator_authorized_unreviewed" if operator_authorized_unreviewed else "reviewed_source_and_document_approval",
    }
    _atomic_write_json(run_directory / "summary.json", summary)
    return summary
