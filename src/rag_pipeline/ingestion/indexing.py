from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ..chunking import ChunkConfig, Tokenizer, chunk_document
from ..embeddings import EmbeddingProvider
from ..normalization import NORMALIZER_VERSION, normalize_segments
from ..parsing import DocumentParseError, parse_file
from ..storage import QdrantVectorStore
from .approval import authorize_document, load_approval_registry
from .parsing_job import document_id_for


class IndexingError(RuntimeError):
    pass


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise IndexingError(f"Invalid JSON in {path.name}:{line_number}.") from exc
            if not isinstance(value, dict):
                raise IndexingError(f"Expected an object in {path.name}:{line_number}.")
            yield value


def _content_digest(segments: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        segments,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def index_normalized_run(
    normalized_run_directory: str | Path,
    inventory: Iterable[dict[str, Any]],
    approval_registry: dict[str, Any],
    project_root: str | Path,
    allowed_extensions: set[str] | frozenset[str],
    approved_license_statuses: set[str] | frozenset[str],
    embedding_provider: EmbeddingProvider,
    vector_store: QdrantVectorStore,
    tokenizer: Tokenizer,
    tenant_id: str,
    acl_principals: tuple[str, ...],
    approval_registry_path: str | Path | None = None,
    strategy: str = "heading_aware",
    chunk_config: ChunkConfig | None = None,
    max_file_bytes: int = 50 * 1024 * 1024,
    dry_run: bool = False,
    document_approval_registry_path: str | Path | None = None,
    operator_authorized_unreviewed: bool = False,
    parser_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reauthorize and reparse each source before chunking and vector upsert."""
    if not tenant_id or not acl_principals or any(not principal for principal in acl_principals):
        raise ValueError("Tenant and ACL principals are required for indexing.")
    chunk_config = chunk_config or ChunkConfig()
    tokenizer_validate = getattr(tokenizer, "validate_config", None)
    if callable(tokenizer_validate):
        tokenizer_validate(chunk_config)
    project_root = Path(project_root).resolve()
    processed_root = (project_root / "knowledge_base" / "processed").resolve()
    run_directory = Path(normalized_run_directory).resolve()
    if not run_directory.is_relative_to(processed_root):
        raise ValueError("Normalized run must be inside knowledge_base/processed.")
    provenance_path = run_directory / "provenance.jsonl"
    content_directory = (run_directory / "content").resolve()
    if not content_directory.is_relative_to(run_directory) or not provenance_path.is_file() or not content_directory.is_dir():
        raise IndexingError("Normalized run is missing provenance or content files.")

    by_document_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in inventory:
        if isinstance(document, dict):
            by_document_id[document_id_for(document)].append(document)

    provider_spec = getattr(embedding_provider, "spec", None)
    max_batch_size = getattr(provider_spec, "max_batch_size", 16)
    if not isinstance(max_batch_size, int) or max_batch_size < 1:
        raise IndexingError("Embedding provider has an invalid batch limit.")
    provider_dimensions = getattr(provider_spec, "dimensions", None)
    provider_model = getattr(provider_spec, "model_name", None)
    provider_digest = getattr(provider_spec, "model_digest", None)
    if provider_dimensions is not None and provider_dimensions != vector_store.embedding.dimensions:
        raise IndexingError("Configured embedding dimensions do not match the managed collection.")
    if provider_model is not None and provider_model != vector_store.embedding.model_name:
        raise IndexingError("Configured embedding model does not match the managed collection.")
    if provider_digest is not None and provider_digest != vector_store.embedding.model_digest:
        raise IndexingError("Configured embedding digest does not match the managed collection.")

    status_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    indexed_documents = 0
    indexed_chunks = 0
    eligible_documents = 0
    planned_chunks = 0
    seen_provenance: set[tuple[str, str]] = set()
    pending_embeddings: list[dict[str, Any]] = []

    def current_document_approvals() -> dict[str, Any]:
        if not document_approval_registry_path:
            return {}
        path = Path(document_approval_registry_path)
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexingError("Document approval registry is unreadable.") from exc
        if not isinstance(value, dict) or not isinstance(value.get("documents", {}), dict):
            raise IndexingError("Document approval registry has an invalid shape.")
        return value

    for provenance in _read_jsonl(provenance_path):
        document_id = provenance.get("document_id")
        source_id = provenance.get("source_id")
        content_id = provenance.get("content_id")
        if not all(isinstance(value, str) and value for value in (document_id, source_id, content_id)):
            status_counts["invalid_provenance"] += 1
            continue
        document_identity = provenance.get("document_identity")
        if not isinstance(document_identity, str) or not document_identity:
            document_identity = document_id
        pair = (document_identity, content_id)
        if pair in seen_provenance:
            status_counts["duplicate_provenance"] += 1
            continue
        seen_provenance.add(pair)
        candidates = by_document_id.get(document_id, [])
        document = next((item for item in candidates if item.get("source_id") == source_id and item.get("relative_path") == provenance.get("relative_path")), None)
        if document is None and candidates and all(item.get("relative_path") is None for item in candidates):
            document = next((item for item in candidates if item.get("source_id") == source_id), None)
        if document is None:
            status_counts["inventory_record_missing"] += 1
            continue
        current_registry = load_approval_registry(approval_registry_path) if approval_registry_path else approval_registry
        authorization = authorize_document(
            document,
            current_registry,
            project_root,
            allowed_extensions=allowed_extensions,
            approved_license_statuses=approved_license_statuses,
            document_approval_registry=current_document_approvals(),
            operator_authorized_unreviewed=operator_authorized_unreviewed,
        )
        if not authorization["authorized"]:
            status_counts[f"blocked:{authorization['authorization_status']}"] += 1
            source_counts[source_id] += 1
            continue
        if provenance.get("source_content_hash") != document.get("sha256"):
            status_counts["provenance_checksum_mismatch"] += 1
            continue

        content_path = (content_directory / f"{content_id}.json").resolve()
        if not content_path.is_relative_to(content_directory) or not content_path.is_file():
            status_counts["normalized_content_missing"] += 1
            continue
        try:
            normalized_content = json.loads(content_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            status_counts["normalized_content_invalid"] += 1
            continue
        if not isinstance(normalized_content, dict) or normalized_content.get("content_id") != content_id:
            status_counts["normalized_content_invalid"] += 1
            continue
        if normalized_content.get("normalizer_version") != NORMALIZER_VERSION:
            status_counts["normalizer_version_mismatch"] += 1
            continue
        try:
            segments, _content_page_numbers = normalize_segments(normalized_content.get("segments"))
        except ValueError:
            status_counts["normalized_content_invalid"] += 1
            continue
        page_numbers = provenance.get("segment_page_numbers")
        if (
            not isinstance(page_numbers, list)
            or len(page_numbers) != len(segments)
            or any(value is not None and (type(value) is not int or value < 1) for value in page_numbers)
            or _content_digest(segments) != content_id
        ):
            status_counts["normalized_content_integrity_failed"] += 1
            continue

        # Parse the current authorized raw source again and ensure the processed copy
        # still corresponds to it; this catches stale or locally modified run artifacts.
        try:
            parsed = parse_file(document["local_path"], max_file_bytes=max_file_bytes, parser_registry=parser_registry)
            current_segments, current_pages = normalize_segments([
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
            ])
        except (DocumentParseError, OSError, ValueError):
            status_counts["source_reparse_failed"] += 1
            continue
        if current_segments != segments or current_pages != page_numbers or _content_digest(current_segments) != content_id:
            status_counts["normalized_source_mismatch"] += 1
            continue
        # Recheck file hash/license/source approval after parsing to reduce TOCTOU risk.
        current_registry = load_approval_registry(approval_registry_path) if approval_registry_path else approval_registry
        authorization = authorize_document(
            document,
            current_registry,
            project_root,
            allowed_extensions=allowed_extensions,
            approved_license_statuses=approved_license_statuses,
            document_approval_registry=current_document_approvals(),
            operator_authorized_unreviewed=operator_authorized_unreviewed,
        )
        if not authorization["authorized"]:
            status_counts[f"blocked_after_reparse:{authorization['authorization_status']}"] += 1
            continue

        chunk_provenance = {
            "document_id": document_id,
            "document_identity": provenance.get("document_identity"),
            "segment_page_numbers": page_numbers,
        }
        chunks = chunk_document(
            {"content_id": content_id, "segments": segments},
            chunk_provenance,
            tokenizer,
            strategy=strategy,
            config=chunk_config,
        )
        if not chunks:
            status_counts["empty_chunk_result"] += 1
            continue

        token_counter = getattr(tokenizer, "count", None)
        if callable(token_counter):
            chunk_counts = [token_counter(chunk.text) for chunk in chunks]
            maximum_context = getattr(tokenizer, "max_context_tokens", None)
            if maximum_context is not None and any(count > maximum_context for count in chunk_counts):
                raise IndexingError("A produced chunk exceeds the embedding model context limit.")
        else:
            chunk_counts = [len(tokenizer.encode(chunk.text)) for chunk in chunks]
        planned_chunks += len(chunks)
        eligible_documents += 1
        if dry_run:
            status_counts["dry_run_ready"] += 1
            continue

        current_registry = load_approval_registry(approval_registry_path) if approval_registry_path else approval_registry
        authorization = authorize_document(
            document,
            current_registry,
            project_root,
            allowed_extensions=allowed_extensions,
            approved_license_statuses=approved_license_statuses,
            document_approval_registry=current_document_approvals(),
            operator_authorized_unreviewed=operator_authorized_unreviewed,
        )
        if not authorization["authorized"]:
            status_counts[f"blocked_before_embedding:{authorization['authorization_status']}"] += 1
            continue

        metadata = {
            "tenant_id": tenant_id,
            "source_id": source_id,
            "document_id": document_id,
            "document_identity": provenance.get("document_identity"),
            "acl_principals": list(acl_principals),
            "license_review_status": "operator_authorized_unreviewed" if operator_authorized_unreviewed else document.get("license_review_status"),
            "ingestion_authority": "explicit_operator_instruction" if operator_authorized_unreviewed else "approved_source_and_document_review",
            "source_type": document.get("source_type"),
            "title": document.get("title") or parsed.title or "Untitled document",
            "source_reference": document.get("source_url"),
            "relative_path": document.get("relative_path"),
            "content_hash": document.get("sha256"),
            "document_version": document.get("source_version") or document.get("sha256"),
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for chunk, token_count in zip(chunks, chunk_counts):
            pending_embeddings.append({
                "text": chunk.text,
                "token_count": token_count,
                "chunk": chunk.to_dict(),
                "metadata": metadata.copy(),
                "document_id": document_id,
                "document_identity": document_identity,
                "source_id": source_id,
                "document": document,
            })

    # Batch across document boundaries so a corpus of short pages does not turn
    # into thousands of tiny Ollama requests. Each document is reauthorized just
    # before its chunks enter an embedding batch.
    remaining_by_document = Counter(item["document_identity"] for item in pending_embeddings)
    indexed_document_ids: set[str] = set()
    blocked_document_ids: set[str] = set()
    authorized_document_ids: set[str] = set()
    for offset in range(0, len(pending_embeddings), max_batch_size):
        end = min(offset + max_batch_size, len(pending_embeddings))
        batch_items = pending_embeddings[offset:end]
        eligible_batch = []
        for item in batch_items:
            document_id = item["document_identity"]
            if document_id in blocked_document_ids:
                continue
            if document_id not in authorized_document_ids:
                current_registry = load_approval_registry(approval_registry_path) if approval_registry_path else approval_registry
                authorization = authorize_document(
                    item["document"], current_registry, project_root,
                    allowed_extensions=allowed_extensions,
                    approved_license_statuses=approved_license_statuses,
                    document_approval_registry=current_document_approvals(),
                    operator_authorized_unreviewed=operator_authorized_unreviewed,
                )
                if not authorization["authorized"]:
                    blocked_document_ids.add(document_id)
                    status_counts[f"blocked_before_embedding:{authorization['authorization_status']}"] += 1
                    continue
                authorized_document_ids.add(document_id)
            eligible_batch.append(item)
        if not eligible_batch:
            continue
        batch = embedding_provider.embed([item["text"] for item in eligible_batch])
        if batch.input_token_count is not None and batch.input_token_count > sum(item["token_count"] for item in eligible_batch):
            raise IndexingError("Actual embedding input tokens exceed the conservative local chunk token budget.")
        descriptor = batch.descriptor
        if (
            descriptor.model_name != vector_store.embedding.model_name
            or descriptor.model_digest != vector_store.embedding.model_digest
            or descriptor.dimensions != vector_store.embedding.dimensions
        ):
            raise IndexingError("Embedding provider does not match the managed vector collection configuration.")
        count = vector_store.upsert_chunks(
            [item["chunk"] for item in eligible_batch], batch.vectors,
            [item["metadata"] for item in eligible_batch],
        )
        indexed_chunks += count
        for item in eligible_batch:
            document_id = item["document_identity"]
            remaining_by_document[document_id] -= 1
            if remaining_by_document[document_id] == 0 and document_id not in indexed_document_ids:
                indexed_document_ids.add(document_id)
                indexed_documents += 1
                source_counts[item["source_id"]] += 1
                status_counts["indexed"] += 1

    return {
        "dry_run": dry_run,
        "eligible_documents": eligible_documents,
        "planned_chunks": planned_chunks,
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "source_document_counts": dict(source_counts),
        "status_counts": dict(status_counts),
        "collection_name": vector_store.collection_name,
        "embedding_model": vector_store.embedding.model_name,
        "embedding_model_digest": vector_store.embedding.model_digest,
        "dimensions": vector_store.embedding.dimensions,
        "chunking_strategy": strategy,
        "authorization_mode": "operator_authorized_unreviewed" if operator_authorized_unreviewed else "reviewed_source_and_document_approval",
    }
