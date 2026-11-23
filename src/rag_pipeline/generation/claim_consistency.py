"""Deterministic checks for a narrow, version-sensitive Python dict-ordering case.

This is deliberately not a general natural-language contradiction detector. Any
case outside the covered patterns remains the claim verifier's responsibility.
"""
from __future__ import annotations

import re
from typing import Sequence


_DICT_SUBJECT = re.compile(
    r"\b(?:regular\s+(?:python\s+)?dictionaries?|dictionaries?|dictionary|"
    r"regular\s+dict|built[- ]in\s+dict|dict\s+objects?)\b", re.I,
)
_UNORDERED = re.compile(
    r"\b(?:(?:arbitrary|unordered|un-ordered|not guaranteed|no guaranteed)\s+(?:insertion\s+)?order|"
    r"(?:did not|does not|do not)\s+guarantee(?:d)?\s+(?:insertion\s+)?order)\b", re.I,
)
_INSERTION_ORDERED = re.compile(
    r"\b(?:insertion[- ]ordered|insertion order|ordered by insertion|"
    r"guaranteed insertion order|preserv(?:e|es|ed|ing) insertion order)\b", re.I,
)
_VERSION = re.compile(r"\b(?:python\s*)?(\d+)\.(\d+)\b", re.I)
_BEFORE = re.compile(r"\b(?:before|prior to|pre[- ]?)\s*(?:python\s*)?(\d+)\.(\d+)\b", re.I)
_SINCE = re.compile(r"\b(?:since|starting in|as of|from)\s*(?:python\s*)?(\d+)\.(\d+)\b", re.I)
_HISTORICAL_DOC = re.compile(r"(?:whatsnew[/\\](\d+)\.(\d+)|what(?:'|’)s new\s+in\s+python\s+(\d+)\.(\d+))", re.I)


def _state(text: str) -> str | None:
    if not _DICT_SUBJECT.search(text):
        return None
    unordered = _UNORDERED.search(text)
    insertion = _INSERTION_ORDERED.search(text)
    if unordered and not insertion:
        return "unordered"
    if insertion and not unordered:
        return "insertion_ordered"
    return None


def _scope(text: str) -> tuple[str, tuple[int, int] | None]:
    before = _BEFORE.search(text)
    if before:
        return "before", (int(before.group(1)), int(before.group(2)))
    since = _SINCE.search(text)
    if since:
        return "since", (int(since.group(1)), int(since.group(2)))
    versions = list(_VERSION.finditer(text))
    if versions:
        match = versions[-1]
        return "exact", (int(match.group(1)), int(match.group(2)))
    return "unqualified", None


def _historical_evidence(citation_ids: Sequence[str], evidence: Sequence[dict]) -> tuple[str, ...]:
    ids = set(citation_ids)
    chunks = []
    for item in evidence:
        if item.get("citation_id") not in ids:
            continue
        source = f"{item.get('title', '')} {item.get('relative_path', '')}"
        match = _HISTORICAL_DOC.search(source)
        if match:
            major, minor = match.group(1) or match.group(3), match.group(2) or match.group(4)
            if major is not None and (int(major), int(minor)) < (3, 7):
                chunk_id = item.get("chunk_id")
                if isinstance(chunk_id, str) and chunk_id:
                    chunks.append(chunk_id)
    return tuple(dict.fromkeys(chunks))


def analyze_claim_consistency(
    claims: Sequence[dict[str, object]],
    verdicts: Sequence[object],
    evidence: Sequence[dict],
) -> tuple[dict[str, object], ...]:
    """Return deterministic findings over claims accepted by the semantic verifier."""
    verdict_by_id = {getattr(item, "claim_id", None): item for item in verdicts}
    accepted = []
    findings: list[dict[str, object]] = []
    for claim in claims:
        claim_id = claim.get("claim_id")
        verdict = verdict_by_id.get(claim_id)
        if verdict is None or getattr(verdict, "status", None) != "supported":
            continue
        text = str(claim.get("text", ""))
        state = _state(text)
        if state is None:
            continue
        citation_ids = tuple(claim.get("citation_ids", ()) or ())
        historical_chunks = _historical_evidence(citation_ids, evidence)
        scope_kind, scope_version = _scope(text)
        if historical_chunks and scope_kind == "unqualified":
            findings.append({
                "reason_code": "version_qualification_missing",
                "claim_ids": [claim_id],
                "evidence_ids": list(historical_chunks),
            })
        accepted.append((claim_id, state, scope_kind, scope_version,
                         tuple(getattr(verdict, "supporting_evidence_ids", ()) or ())))

    for index, left in enumerate(accepted):
        for right in accepted[index + 1:]:
            if left[1] == right[1]:
                continue
            if not _scopes_overlap(left[2], left[3], right[2], right[3]):
                continue
            findings.append({
                "reason_code": "contradictory_supported_claims",
                "claim_ids": [left[0], right[0]],
                "evidence_ids": list(dict.fromkeys(left[4] + right[4])),
            })
    # Stable de-duplication when a historical unqualified claim also conflicts
    # with a current claim; keep both distinct findings for auditability.
    return tuple(findings)


def _scopes_overlap(left_kind: str, left_version: tuple[int, int] | None,
                    right_kind: str, right_version: tuple[int, int] | None) -> bool:
    if left_kind == "unqualified" or right_kind == "unqualified":
        return True
    if left_kind == "exact" and right_kind == "exact":
        return left_version == right_version
    if left_kind == "exact":
        return _version_in_scope(left_version, right_kind, right_version)
    if right_kind == "exact":
        return _version_in_scope(right_version, left_kind, left_version)
    if left_kind == right_kind:
        return True
    # `before X` and `since X` are disjoint by definition when the boundary is
    # the same. For different boundaries, their intervals overlap if the since
    # boundary precedes the before boundary.
    before = left_version if left_kind == "before" else right_version
    since = left_version if left_kind == "since" else right_version
    return bool(before and since and since < before)


def _version_in_scope(version: tuple[int, int] | None, kind: str,
                      boundary: tuple[int, int] | None) -> bool:
    if version is None or boundary is None:
        return True
    if kind == "before":
        return version < boundary
    if kind == "since":
        return version >= boundary
    return version == boundary
