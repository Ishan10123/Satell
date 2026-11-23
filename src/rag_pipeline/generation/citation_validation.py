"""Fail-closed citation classification used by local generation."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Pattern, Sequence

from ..retrieval.context import Citation


def _valid_id(citation_pattern: Pattern[str], value: object) -> bool:
    return isinstance(value, str) and citation_pattern.fullmatch(f"[{value}]") is not None


@dataclass(frozen=True)
class CitationValidation:
    citation_ids: tuple[str, ...]
    claim_mappings: tuple[dict[str, object], ...]
    citation_mapping: tuple[dict[str, object], ...]


class CitationFailure(ValueError):
    def __init__(self, reason: str, *, citation_ids: Sequence[str] = (),
                 claim_mappings: Sequence[dict[str, object]] = (),
                 citation_mapping: Sequence[dict[str, object]] = ()) -> None:
        super().__init__(reason)
        self.reason = reason
        self.citation_ids = tuple(citation_ids)
        self.claim_mappings = tuple(claim_mappings)
        self.citation_mapping = tuple(citation_mapping)


def _citation_mapping_rows(citations: Sequence[Citation], citation_pattern: Pattern[str]) -> tuple[dict[str, object], ...]:
    rows = []
    seen: set[str] = set()
    for citation in citations:
        citation_id = getattr(citation, "citation_id", None)
        source_id = getattr(citation, "source_id", None)
        document_id = getattr(citation, "document_id", None)
        chunk_id = getattr(citation, "chunk_id", None)
        if (not _valid_id(citation_pattern, citation_id)
                or citation_id in seen or not isinstance(source_id, str) or not source_id
                or not isinstance(document_id, str) or not document_id
                or not isinstance(chunk_id, str) or not chunk_id):
            raise CitationFailure("invalid_citation_mapping")
        seen.add(citation_id)
        rows.append({
            "citation_id": citation_id,
            "source_id": source_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "title": getattr(citation, "title", ""),
            "section": getattr(citation, "section", None),
            "page_references": list(getattr(citation, "page_references", ()) or ()),
            "source_reference": getattr(citation, "source_reference", None),
        })
    if not rows:
        raise CitationFailure("invalid_citation_mapping")
    return tuple(rows)


def validate_generated_citations(
    answer: str,
    context_citations: Sequence[Citation],
    citation_pattern: Pattern[str],
    extract_claims: Callable[[str, Pattern[str]], list[dict[str, object]]],
    is_nonclaim: Callable[[str], bool],
    all_claims_have_citations: Callable[[str], bool],
) -> CitationValidation:
    """Classify actual citation parser/coverage failures without relaxing checks."""
    mappings = _citation_mapping_rows(context_citations, citation_pattern)
    allowed = {row["citation_id"] for row in mappings}

    # Inspect bracket markers that look like citations, including malformed and
    # unterminated forms, before relying on the strict [S1] parser.
    marker_pattern = re.compile(r"\[(?P<body>[^\]\r\n]*)(?P<closed>\])?")
    parsed: list[str] = []
    found_marker = False
    missing_id = False
    invalid_syntax = False
    for match in marker_pattern.finditer(answer):
        body = match.group("body").strip()
        if body == "":
            # Empty brackets are a citation marker with an absent identifier.
            found_marker = True
            missing_id = True
            continue
        if body[:1].lower() != "s":
            continue
        found_marker = True
        if body.lower() == "s":
            missing_id = True
        elif match.group("closed") is None or not _valid_id(citation_pattern, body):
            invalid_syntax = True
        else:
            parsed.append(body)

    claim_rows = tuple(
        {"claim_id": row["claim_id"], "claim_text": row["text"],
         "citation_ids": list(row.get("citation_ids", []))}
        for row in extract_claims(answer, citation_pattern)
        if not is_nonclaim(str(row["text"]))
    )
    unique_parsed = tuple(dict.fromkeys(parsed))
    if not found_marker:
        raise CitationFailure("missing_citation_marker", citation_ids=unique_parsed,
                              claim_mappings=claim_rows, citation_mapping=mappings)
    if missing_id:
        raise CitationFailure("missing_citation_id", citation_ids=unique_parsed,
                              claim_mappings=claim_rows, citation_mapping=mappings)
    if invalid_syntax:
        raise CitationFailure("invalid_citation_syntax", citation_ids=unique_parsed,
                              claim_mappings=claim_rows, citation_mapping=mappings)
    if not unique_parsed:
        raise CitationFailure("missing_citation_id", claim_mappings=claim_rows,
                              citation_mapping=mappings)
    unknown = tuple(item for item in unique_parsed if item not in allowed)
    if unknown:
        raise CitationFailure("unknown_citation_id", citation_ids=unique_parsed,
                              claim_mappings=claim_rows, citation_mapping=mappings)
    if not all_claims_have_citations(answer):
        raise CitationFailure("insufficient_claim_citation_coverage", citation_ids=unique_parsed,
                              claim_mappings=claim_rows, citation_mapping=mappings)
    return CitationValidation(unique_parsed, claim_rows, mappings)
