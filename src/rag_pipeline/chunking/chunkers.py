from dataclasses import dataclass, field
import hashlib
import json
import re
from time import perf_counter_ns
from typing import Callable, Protocol, Sequence, Any


class Tokenizer(Protocol):
    def encode(self, text: str) -> Sequence[Any]: ...
    def decode(self, tokens: Sequence[Any]) -> str: ...


@dataclass(frozen=True)
class ChunkConfig:
    max_tokens: int = 512
    overlap_tokens: int = 64
    child_max_tokens: int = 128
    parent_max_tokens: int = 768
    semantic_similarity_threshold: float = 0.72
    max_characters: int = 2000
    overlap_characters: int = 200

    def __post_init__(self) -> None:
        if self.max_tokens < 1 or self.child_max_tokens < 1 or self.parent_max_tokens < 1:
            raise ValueError("Chunk token budgets must be positive.")
        if self.overlap_tokens < 0 or self.overlap_tokens >= self.max_tokens:
            raise ValueError("Overlap must be non-negative and smaller than max_tokens.")
        if self.max_characters < 1 or self.overlap_characters < 0 or self.overlap_characters >= self.max_characters:
            raise ValueError("Character budget must be positive and exceed its overlap.")
        if not 0.0 <= self.semantic_similarity_threshold <= 1.0:
            raise ValueError("Semantic similarity threshold must be between 0 and 1.")


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_identity: str | None
    content_id: str
    strategy: str
    text: str
    segments: list[dict[str, Any]]
    token_count: int
    heading_paths: list[list[str]]
    page_references: list[int]
    source_segment_indices: list[int]
    parent_chunk_id: str | None = None
    child_chunk_ids: list[str] = field(default_factory=list)
    oversized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_identity": self.document_identity,
            "content_id": self.content_id,
            "strategy": self.strategy,
            "text": self.text,
            "segments": self.segments,
            "token_count": self.token_count,
            "heading_paths": self.heading_paths,
            "page_references": self.page_references,
            "source_segment_indices": self.source_segment_indices,
            "parent_chunk_id": self.parent_chunk_id,
            "child_chunk_ids": self.child_chunk_ids,
            "oversized": self.oversized,
        }


@dataclass(frozen=True)
class ChunkBenchmark:
    strategy: str
    elapsed_ms: float
    chunk_count: int
    mean_tokens: float
    max_tokens: int
    oversized_chunks: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "elapsed_ms": self.elapsed_ms,
            "chunk_count": self.chunk_count,
            "mean_tokens": self.mean_tokens,
            "max_tokens": self.max_tokens,
            "oversized_chunks": self.oversized_chunks,
        }


SemanticSimilarity = Callable[[str, str], float]


def _canonical_token_count(text: str, tokenizer: Tokenizer) -> int:
    return len(tokenizer.encode(text))


def _fixed_windows(text: str, maximum: int, overlap: int, tokenizer: Tokenizer) -> list[str]:
    tokens = list(tokenizer.encode(text))
    if len(tokens) <= maximum:
        return [text]
    step = maximum - overlap
    windows = []
    for start in range(0, len(tokens), step):
        part = tokenizer.decode(tokens[start:start + maximum])
        if part:
            windows.append(part)
        if start + maximum >= len(tokens):
            break
    return windows


def _character_windows(text: str, maximum: int, overlap: int) -> list[str]:
    if len(text) <= maximum:
        return [text]
    step = maximum - overlap
    windows = []
    for start in range(0, len(text), step):
        windows.append(text[start:start + maximum])
        if start + maximum >= len(text):
            break
    return windows


def _recursive_parts(text: str, maximum: int, tokenizer: Tokenizer) -> list[str]:
    if _canonical_token_count(text, tokenizer) <= maximum:
        return [text]
    separators = ("\n\n", "\n", ". ", "; ", " ")
    for separator in separators:
        parts = text.split(separator)
        if len(parts) < 2:
            continue
        merged = []
        current = ""
        for part in parts:
            candidate = part if not current else current + separator + part
            if current and _canonical_token_count(candidate, tokenizer) > maximum:
                merged.extend(_recursive_parts(current, maximum, tokenizer))
                current = part
            else:
                current = candidate
        if current:
            merged.extend(_recursive_parts(current, maximum, tokenizer))
        return merged
    return _fixed_windows(text, maximum, 0, tokenizer)


def _split_segment(
    segment: dict[str, Any],
    index: int,
    maximum: int,
    overlap: int,
    strategy: str,
    tokenizer: Tokenizer,
    max_characters: int,
    overlap_characters: int,
) -> list[tuple[dict[str, Any], int]]:
    text = segment["text"]
    character_mode = strategy == "fixed_size"
    budget = max_characters if character_mode else maximum
    measure = len if character_mode else lambda value: _canonical_token_count(value, tokenizer)
    if measure(text) <= budget:
        return [(segment, index)]
    if segment["segment_type"] == "code":
        lines = text.splitlines(keepends=True)
        parts: list[tuple[str, int, int]] = []
        current = ""
        current_start = segment.get("line_start")
        line_cursor = segment.get("line_start")
        for line in lines:
            candidate = current + line
            if current and _canonical_token_count(candidate, tokenizer) > maximum:
                current_lines = current.count("\n") or 1
                parts.append((current, current_start or 1, (current_start or 1) + current_lines - 1))
                line_cursor = (current_start or 1) + current_lines
                current_start = line_cursor
                current = line
            else:
                current = candidate
        if current:
            current_lines = current.count("\n") or 1
            parts.append((current, current_start or 1, (current_start or 1) + current_lines - 1))
        return [({**segment, "text": part, "line_start": first, "line_end": last}, index)
                for part, first, last in parts if part]
    elif strategy in {"recursive", "semantic"}:
        windows = _recursive_parts(text, maximum, tokenizer)
    elif character_mode:
        windows = _character_windows(text, max_characters, overlap_characters)
    else:
        windows = _fixed_windows(text, maximum, overlap, tokenizer)
    return [({**segment, "text": part}, index) for part in windows if part]


def _build_chunks(
    content: dict[str, Any],
    provenance: dict[str, Any],
    tokenizer: Tokenizer,
    maximum: int,
    overlap: int,
    strategy: str,
    heading_boundaries: bool = False,
    semantic_similarity: SemanticSimilarity | None = None,
    semantic_threshold: float = 0.72,
    max_characters: int = 2000,
    overlap_characters: int = 200,
) -> list[ChunkRecord]:
    segments = content.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Normalized content must contain a non-empty segments list.")
    document_id = provenance.get("document_id")
    document_identity = provenance.get("document_identity")
    content_id = content.get("content_id")
    if not isinstance(document_id, str) or not isinstance(content_id, str):
        raise ValueError("Chunking requires document_id and content_id provenance.")
    page_numbers = provenance.get("segment_page_numbers", [])
    if not isinstance(page_numbers, list) or len(page_numbers) != len(segments):
        raise ValueError("Segment page references must align with normalized segments.")

    split_segments: list[tuple[dict[str, Any], int]] = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise ValueError(f"Invalid normalized segment at index {index}.")
        if segment.get("segment_type") not in {"text", "code"}:
            raise ValueError(f"Invalid segment type at index {index}.")
        headings = segment.get("headings", [])
        if not isinstance(headings, list) or any(not isinstance(item, str) for item in headings):
            raise ValueError(f"Invalid heading path at segment {index}.")
        page_number = page_numbers[index]
        if page_number is not None and (type(page_number) is not int or page_number < 1):
            raise ValueError(f"Invalid page number for segment {index}.")
        split_segments.extend(_split_segment(
            segment, index, maximum, overlap, strategy, tokenizer,
            max_characters, overlap_characters,
        ))

    groups: list[list[tuple[dict[str, Any], int]]] = []
    current: list[tuple[dict[str, Any], int]] = []
    budget = max_characters if strategy == "fixed_size" else maximum
    measure = len if strategy == "fixed_size" else lambda value: _canonical_token_count(value, tokenizer)
    current_tokens = 0
    previous_segment: dict[str, Any] | None = None
    for piece, source_index in split_segments:
        piece_tokens = measure(piece["text"])
        boundary = False
        if current and heading_boundaries and previous_segment is not None:
            boundary = piece.get("headings", []) != previous_segment.get("headings", [])
        if current and semantic_similarity is not None and previous_segment is not None:
            similarity = semantic_similarity(previous_segment["text"], piece["text"])
            if not 0.0 <= similarity <= 1.0:
                raise ValueError("Semantic similarity callback must return a score from 0 to 1.")
            boundary = boundary or similarity < semantic_threshold
        candidate_text = "\n".join([entry[0]["text"] for entry in current] + [piece["text"]])
        candidate_tokens = measure(candidate_text)
        if current and (boundary or candidate_tokens > budget):
            groups.append(current)
            current = []
            current_tokens = 0
        current.append((piece, source_index))
        current_tokens = measure("\n".join(entry[0]["text"] for entry in current))
        previous_segment = piece
    if current:
        groups.append(current)

    chunks = []
    for ordinal, group in enumerate(groups):
        chunk_segments = []
        heading_paths = []
        page_references = []
        source_indices = []
        for segment, source_index in group:
            chunk_segments.append({
                "text": segment["text"],
                "segment_type": segment["segment_type"],
                "headings": list(segment.get("headings", [])),
                "page_number": page_numbers[source_index],
                **{key: segment[key] for key in ("line_start", "line_end", "language", "symbol_name") if key in segment},
            })
            heading_path = list(segment.get("headings", []))
            if heading_path not in heading_paths:
                heading_paths.append(heading_path)
            page_number = page_numbers[source_index]
            if page_number is not None and page_number not in page_references:
                page_references.append(page_number)
            source_indices.append(source_index)
        text = "\n".join(segment["text"] for segment in chunk_segments)
        token_count = _canonical_token_count(text, tokenizer)
        identity = json.dumps({
            "document_id": document_id,
            "document_identity": document_identity,
            "content_id": content_id,
            "strategy": strategy,
            "ordinal": ordinal,
            "segments": chunk_segments,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        chunks.append(ChunkRecord(
            chunk_id=chunk_id,
            document_id=document_id,
            document_identity=document_identity,
            content_id=content_id,
            strategy=strategy,
            text=text,
            segments=chunk_segments,
            token_count=token_count,
            heading_paths=heading_paths,
            page_references=page_references,
            source_segment_indices=source_indices,
            oversized=measure(text) > budget,
        ))
    return chunks


def chunk_document(
    content: dict[str, Any],
    provenance: dict[str, Any],
    tokenizer: Tokenizer,
    strategy: str = "heading_aware",
    config: ChunkConfig | None = None,
    semantic_similarity: SemanticSimilarity | None = None,
) -> list[ChunkRecord]:
    config = config or ChunkConfig()
    if strategy not in {"fixed", "fixed_size", "token_based", "recursive", "heading_aware", "semantic", "parent_child"}:
        raise ValueError(f"Unsupported chunking strategy: {strategy}")
    if strategy == "semantic" and semantic_similarity is None:
        raise ValueError("Semantic strategy requires a local similarity callback.")
    if strategy != "parent_child":
        return _build_chunks(
            content,
            provenance,
            tokenizer,
            maximum=config.max_tokens,
            overlap=config.overlap_tokens,
            strategy="token_based" if strategy == "fixed" else strategy,
            heading_boundaries=strategy == "heading_aware",
            semantic_similarity=semantic_similarity if strategy == "semantic" else None,
            semantic_threshold=config.semantic_similarity_threshold,
            max_characters=config.max_characters,
            overlap_characters=config.overlap_characters,
        )

    parent_chunks = _build_chunks(
        content,
        provenance,
        tokenizer,
        maximum=config.parent_max_tokens,
        overlap=0,
        strategy="parent",
        heading_boundaries=True,
    )
    child_chunks = []
    for parent in parent_chunks:
        parent_content = {
            "content_id": parent.content_id,
            "segments": [
                {
                    "text": segment["text"],
                    "segment_type": segment["segment_type"],
                    "headings": segment["headings"],
                    **{key: segment[key] for key in ("line_start", "line_end", "language", "symbol_name") if key in segment},
                }
                for segment in parent.segments
            ],
        }
        parent_provenance = {
            "document_id": parent.document_id,
            "document_identity": parent.document_identity,
            "segment_page_numbers": [segment["page_number"] for segment in parent.segments],
        }
        local_children = _build_chunks(
            parent_content,
            parent_provenance,
            tokenizer,
            maximum=config.child_max_tokens,
            overlap=min(config.overlap_tokens, max(0, config.child_max_tokens - 1)),
            strategy="child",
            heading_boundaries=True,
        )
        for child in local_children:
            child.source_segment_indices = [
                parent.source_segment_indices[index]
                for index in child.source_segment_indices
            ]
            child_identity = json.dumps({"parent_chunk_id": parent.chunk_id, "child_chunk_id": child.chunk_id}, sort_keys=True, separators=(",", ":"))
            child.chunk_id = hashlib.sha256(child_identity.encode("utf-8")).hexdigest()
            child.parent_chunk_id = parent.chunk_id
            parent.child_chunk_ids.append(child.chunk_id)
        child_chunks.extend(local_children)
    return [*parent_chunks, *child_chunks]


def benchmark_chunking_strategies(
    content: dict[str, Any],
    provenance: dict[str, Any],
    tokenizer: Tokenizer,
    strategies: Sequence[str] = ("fixed_size", "token_based", "recursive", "heading_aware"),
    config: ChunkConfig | None = None,
    semantic_similarity: SemanticSimilarity | None = None,
) -> list[ChunkBenchmark]:
    results = []
    for strategy in strategies:
        start = perf_counter_ns()
        chunks = chunk_document(
            content,
            provenance,
            tokenizer,
            strategy=strategy,
            config=config,
            semantic_similarity=semantic_similarity,
        )
        elapsed_ms = (perf_counter_ns() - start) / 1_000_000
        counts = [chunk.token_count for chunk in chunks]
        results.append(ChunkBenchmark(
            strategy=strategy,
            elapsed_ms=elapsed_ms,
            chunk_count=len(chunks),
            mean_tokens=sum(counts) / len(counts) if counts else 0.0,
            max_tokens=max(counts, default=0),
            oversized_chunks=sum(chunk.oversized for chunk in chunks),
        ))
    return results
