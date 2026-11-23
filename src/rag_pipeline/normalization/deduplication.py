from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable
import unicodedata


NORMALIZER_VERSION = "2.0"
SEGMENT_TYPES = {"text", "code"}


def _normalize_prose(text: str) -> str:
    value = unicodedata.normalize("NFC", text)
    value = value.replace("\u00a0", " ").replace("\u200b", "")
    lines = [" ".join(line.split()) for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _normalize_code(text: str) -> str:
    value = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def normalize_segments(raw_segments: Any) -> tuple[list[dict[str, Any]], list[int | None]]:
    if not isinstance(raw_segments, list) or not raw_segments:
        raise ValueError("Parsed document must contain a non-empty segments list.")
    segments = []
    page_numbers = []
    for index, segment in enumerate(raw_segments):
        if not isinstance(segment, dict):
            raise ValueError(f"Segment {index} must be an object.")
        text = segment.get("text")
        segment_type = segment.get("segment_type")
        headings = segment.get("headings", [])
        page_number = segment.get("page_number")
        line_start = segment.get("line_start")
        line_end = segment.get("line_end")
        language = segment.get("language")
        symbol_name = segment.get("symbol_name")
        if not isinstance(text, str) or segment_type not in SEGMENT_TYPES:
            raise ValueError(f"Segment {index} has invalid text or type.")
        if not isinstance(headings, list) or any(not isinstance(item, str) for item in headings):
            raise ValueError(f"Segment {index} has invalid heading metadata.")
        if page_number is not None and (type(page_number) is not int or page_number < 1):
            raise ValueError(f"Segment {index} has an invalid page number.")
        if (line_start is None) != (line_end is None) or (line_start is not None and
                (type(line_start) is not int or type(line_end) is not int or line_start < 1 or line_end < line_start)):
            raise ValueError(f"Segment {index} has an invalid line range.")
        if language is not None and not isinstance(language, str):
            raise ValueError(f"Segment {index} has invalid language metadata.")
        if symbol_name is not None and not isinstance(symbol_name, str):
            raise ValueError(f"Segment {index} has invalid symbol metadata.")
        normalized = _normalize_code(text) if segment_type == "code" else _normalize_prose(text)
        if not normalized:
            continue
        normalized_headings = [_normalize_prose(item) for item in headings]
        normalized_segment = {
            "text": normalized,
            "segment_type": segment_type,
            "headings": [item for item in normalized_headings if item],
        }
        for key, value in (("line_start", line_start), ("line_end", line_end), ("language", language), ("symbol_name", symbol_name)):
            if value is not None:
                normalized_segment[key] = value
        segments.append(normalized_segment)
        page_numbers.append(page_number)
    if not segments:
        raise ValueError("Document has no non-empty segments after normalization.")
    return segments, page_numbers


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(value, file, ensure_ascii=False, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path.name}:{line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object at {path.name}:{line_number}")
            yield value


def normalize_parsed_run(
    source_run_directory: str | Path,
    project_root: str | Path,
    destination_directory: str | Path,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    processed_root = (project_root / "knowledge_base" / "processed").resolve()
    source_directory = Path(source_run_directory).resolve()
    destination = Path(destination_directory).resolve()
    if not processed_root.is_relative_to(project_root):
        raise ValueError("knowledge_base/processed resolves outside the project root.")
    if not source_directory.is_relative_to(processed_root):
        raise ValueError("Parsed input must be inside knowledge_base/processed.")
    if not destination.is_relative_to(processed_root):
        raise ValueError("Normalized output must be inside knowledge_base/processed.")
    if destination == source_directory or destination.is_relative_to(source_directory):
        raise ValueError("Normalized output cannot be inside the parsed input run.")
    if not (source_directory / "outcomes.jsonl").is_file():
        raise FileNotFoundError(f"Parsed run manifest is missing: {source_directory}")
    destination.mkdir(parents=True, exist_ok=False)
    content_directory = destination / "content"
    content_directory.mkdir()
    provenance_path = destination / "provenance.jsonl"
    manifest_path = destination / "manifest.jsonl"
    seen_content_ids: set[str] = set()
    provenance_keys: set[tuple[str, str]] = set()
    canonical_provenance: dict[str, dict[str, dict[str, Any]]] = {}
    parsed_documents = 0
    unique_contents = 0
    duplicate_documents = 0
    source_outcome_counts: Counter[str] = Counter()

    with provenance_path.open("x", encoding="utf-8", newline="\n") as provenance_file, manifest_path.open("x", encoding="utf-8", newline="\n") as manifest_file:
        for outcome in _read_jsonl(source_directory / "outcomes.jsonl"):
            outcome_status = outcome.get("status")
            if not isinstance(outcome_status, str):
                raise ValueError("Parsed run outcome has no valid status.")
            source_outcome_counts[outcome_status] += 1
            if outcome_status != "parsed":
                continue
            relative_output = outcome.get("output_file")
            if not isinstance(relative_output, str) or not relative_output:
                raise ValueError("Parsed outcome is missing output_file.")
            input_path = (source_directory / relative_output).resolve()
            if not input_path.is_relative_to(source_directory) or not input_path.is_file():
                raise ValueError("Parsed output path escapes its run directory or is missing.")
            with input_path.open("r", encoding="utf-8-sig") as file:
                parsed = json.load(file)
            document_id = parsed.get("document_id")
            source_id = parsed.get("source_id")
            if not isinstance(document_id, str) or document_id != outcome.get("document_id"):
                raise ValueError("Parsed outcome and document IDs do not match.")
            if not isinstance(source_id, str) or source_id != outcome.get("source_id"):
                raise ValueError("Parsed outcome and document source IDs do not match.")
            segments, page_numbers = normalize_segments(parsed.get("segments"))
            canonical = json.dumps(
                segments,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            content_id = hashlib.sha256(canonical).hexdigest()
            content_path = content_directory / f"{content_id}.json"
            if content_id not in seen_content_ids:
                _atomic_write_json(content_path, {
                    "content_id": content_id,
                    "normalizer_version": NORMALIZER_VERSION,
                    "segments": segments,
                })
                seen_content_ids.add(content_id)
                unique_contents += 1
            else:
                duplicate_documents += 1

            provenance = {
                "content_id": content_id,
                "document_id": document_id,
                "document_identity": parsed.get("document_identity") or _legacy_identity(source_id, parsed.get("relative_path")),
                "source_id": source_id,
                "source_type": parsed.get("source_type"),
                "source_content_hash": parsed.get("content_hash"),
                "source_version": parsed.get("source_version"),
                "source_url": parsed.get("source_url"),
                "relative_path": parsed.get("relative_path"),
                "segment_page_numbers": page_numbers,
            }
            identity = provenance["document_identity"]
            if not isinstance(identity, str) or len(identity) != 64:
                raise ValueError("Parsed document has an invalid document_identity.")
            provenance_key = (identity, content_id)
            if provenance_key in provenance_keys:
                continue
            provenance_keys.add(provenance_key)
            canonical_provenance.setdefault(content_id, {})[identity] = {
                "document_identity": identity,
                "document_id": document_id,
                "source_id": source_id,
                "source_type": provenance["source_type"],
                "source_url": provenance["source_url"],
                "source_version": provenance["source_version"],
                "relative_path": provenance["relative_path"],
                "source_content_hash": provenance["source_content_hash"],
            }
            provenance_file.write(json.dumps(provenance, ensure_ascii=False) + "\n")
            manifest_file.write(json.dumps({
                "document_id": document_id,
                "content_id": content_id,
                "source_id": source_id,
                "status": "normalized",
            }, ensure_ascii=False) + "\n")
            parsed_documents += 1
            if parsed_documents % 100 == 0:
                provenance_file.flush()
                manifest_file.flush()
                os.fsync(provenance_file.fileno())
                os.fsync(manifest_file.fileno())
        provenance_file.flush()
        manifest_file.flush()
        os.fsync(provenance_file.fileno())
        os.fsync(manifest_file.fileno())

    canonical_map_path = destination / "canonical_content_map.jsonl"
    with canonical_map_path.open("x", encoding="utf-8", newline="\n") as mapping_file:
        for content_id in sorted(canonical_provenance):
            mapping_file.write(json.dumps({
                "content_id": content_id,
                "content_sha256": content_id,
                "identity_version": "2",
                "provenance": sorted(canonical_provenance[content_id].values(), key=lambda row: (row["source_id"], row["relative_path"] or "")),
            }, ensure_ascii=False, sort_keys=True) + "\n")
        mapping_file.flush()
        os.fsync(mapping_file.fileno())

    summary = {
        "normalization_run_id": destination.name,
        "normalizer_version": NORMALIZER_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parsed_documents": parsed_documents,
        "unique_contents": unique_contents,
        "duplicate_documents": duplicate_documents,
        "provenance_records": parsed_documents,
        "identity_version": "2",
        "content_identity": "sha256(normalized_segments_json)",
        "document_identity": "sha256(source_id+normalized_relative_path)",
        "canonical_content_map": "canonical_content_map.jsonl",
        "source_outcome_counts": dict(source_outcome_counts),
    }
    _atomic_write_json(destination / "summary.json", summary)
    return summary


def _legacy_identity(source_id: str, relative_path: Any) -> str:
    """Derive a path identity for hand-authored/legacy parsed records."""
    from ..ingestion.parsing_job import document_identity_for
    return document_identity_for({"source_id": source_id, "relative_path": relative_path})
