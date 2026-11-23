"""Validate RAG evaluation annotation JSONL without interpreting its labels as truth."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


INTENTS = {
    "direct", "multi_part", "comparison", "version_specific", "cross_document",
    "multi_hop", "exact_identifier", "ambiguous", "out_of_domain",
    "insufficient_evidence", "contradictory", "outdated", "prompt_injection",
}
REVIEW_STATES = {"unreviewed", "human_reviewed"}
LABEL_ORIGINS = {"unreviewed", "heuristic", "human"}
REQUIRED_FIELDS = {
    "record_version", "dataset_version", "query_id", "question", "intent",
    "relevant_document_ids", "relevant_chunk_ids", "expected_answer_concepts",
    "required_evidence", "expected_abstention", "source_versions",
    "review_status", "label_origin", "reviewer_id", "reviewed_at", "confidence",
}
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PLACEHOLDERS = {"replace_me", "replace with a reviewed evaluation question"}


def _require_string(value: Any, field: str, *, nonempty: bool = True) -> None:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ValueError(f"{field} must be {'a non-empty' if nonempty else 'a'} string.")
    if value.strip().casefold() in _PLACEHOLDERS:
        raise ValueError(f"{field} still contains a template placeholder.")


def _require_string_list(value: Any, field: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings.")


def validate_record(record: Any, *, line_number: int | None = None) -> dict[str, Any]:
    prefix = f"line {line_number}: " if line_number is not None else ""
    if not isinstance(record, dict):
        raise ValueError(prefix + "record must be a JSON object.")
    missing = REQUIRED_FIELDS - record.keys()
    extra = record.keys() - REQUIRED_FIELDS
    if missing:
        raise ValueError(prefix + "missing required fields: " + ", ".join(sorted(missing)))
    if extra:
        raise ValueError(prefix + "unexpected fields: " + ", ".join(sorted(extra)))

    for field in ("record_version", "dataset_version", "question"):
        _require_string(record[field], field)
    _require_string(record["query_id"], "query_id")
    if not _ID.fullmatch(record["query_id"]):
        raise ValueError(prefix + "query_id contains unsupported characters.")
    if len(record["question"]) > 5000:
        raise ValueError(prefix + "question exceeds the 5,000-character query limit.")
    if record["record_version"] != "1.0":
        raise ValueError(prefix + "unsupported record_version.")
    if not isinstance(record["intent"], str) or record["intent"] not in INTENTS:
        raise ValueError(prefix + "intent is not in the annotation taxonomy.")
    for field in ("relevant_document_ids", "relevant_chunk_ids", "expected_answer_concepts", "source_versions"):
        _require_string_list(record[field], field)
    evidence = record["required_evidence"]
    if not isinstance(evidence, list) or any(
        not isinstance(item, dict) or set(item) != {"evidence_id", "requirement"}
        or not isinstance(item["evidence_id"], str) or not item["evidence_id"].strip()
        or not isinstance(item["requirement"], str) or not item["requirement"].strip()
        for item in evidence
    ):
        raise ValueError(prefix + "required_evidence must contain evidence_id and requirement objects.")

    if (not isinstance(record["review_status"], str) or record["review_status"] not in REVIEW_STATES
            or not isinstance(record["label_origin"], str) or record["label_origin"] not in LABEL_ORIGINS):
        raise ValueError(prefix + "invalid review_status or label_origin.")
    abstention = record["expected_abstention"]
    if abstention is not None and type(abstention) is not bool:
        raise ValueError(prefix + "expected_abstention must be true, false, or null.")
    reviewer = record["reviewer_id"]
    reviewed_at = record["reviewed_at"]
    confidence = record["confidence"]
    if record["review_status"] == "human_reviewed":
        _require_string(reviewer, "reviewer_id")
        _require_string(reviewed_at, "reviewed_at")
        try:
            parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(prefix + "reviewed_at must be an ISO-8601 timestamp.") from exc
        if parsed.tzinfo is None:
            raise ValueError(prefix + "reviewed_at must include a timezone.")
        if record["label_origin"] != "human" or abstention is None:
            raise ValueError(prefix + "human_reviewed records require human labels and an abstention judgment.")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError(prefix + "human_reviewed records require confidence between 0 and 1.")
    else:
        if reviewer not in (None, "") or reviewed_at not in (None, "") or confidence is not None:
            raise ValueError(prefix + "unreviewed records cannot claim a reviewer, timestamp, or human confidence.")
        if record["label_origin"] == "human":
            raise ValueError(prefix + "unreviewed records cannot claim human label origin.")
    return record


def validate_jsonl(path: Path) -> dict[str, Any]:
    seen: set[tuple[str, str]] = set()
    total = reviewed = unreviewed = 0
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = validate_record(json.loads(line), line_number=line_number)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON.") from exc
            key = (record["dataset_version"], record["query_id"])
            if key in seen:
                raise ValueError(f"line {line_number}: duplicate dataset/query identity.")
            seen.add(key)
            total += 1
            if record["review_status"] == "human_reviewed":
                reviewed += 1
            else:
                unreviewed += 1
    if total == 0:
        raise ValueError("dataset contains no records.")
    return {"records": total, "human_reviewed": reviewed, "unreviewed": unreviewed,
            "label_quality": "human_reviewed" if unreviewed == 0 else "mixed_or_unreviewed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Annotation JSONL to validate; contents are not printed.")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate_jsonl(args.dataset), indent=2))
    except (OSError, ValueError) as exc:
        print(f"Dataset validation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
