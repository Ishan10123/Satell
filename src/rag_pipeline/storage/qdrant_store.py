from dataclasses import dataclass
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Sequence
from urllib.parse import urlsplit
import uuid

from qdrant_client import QdrantClient, models

from ..embeddings import EmbeddingDescriptor


ID_NAMESPACE = uuid.UUID("113e2a1f-2067-4d27-a4f2-696f7a612e52")
COLLECTION_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,62}$")
FORBIDDEN_PAYLOAD_KEYS = {"local_path", "file_path", "source_path", "absolute_path"}


class VectorStoreError(RuntimeError):
    pass


class IndexCompatibilityError(VectorStoreError):
    pass


@dataclass(frozen=True)
class AccessScope:
    tenant_id: str
    principals: tuple[str, ...]
    allowed_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.principals or any(not item for item in self.principals):
            raise ValueError("A tenant and at least one authorized principal are required.")


@dataclass(frozen=True)
class SearchHit:
    point_id: str
    score: float
    payload: dict[str, Any]
    rank: int | None = None


@dataclass(frozen=True)
class RetrievalFilters:
    source_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    source_types: tuple[str, ...] = ()
    excluded_document_ids: tuple[str, ...] = ()
    restricted_source_ids: tuple[str, ...] = ()
    permitted_document_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, values in (("source_ids", self.source_ids), ("document_ids", self.document_ids),
                             ("source_types", self.source_types), ("excluded_document_ids", self.excluded_document_ids),
                             ("restricted_source_ids", self.restricted_source_ids),
                             ("permitted_document_ids", self.permitted_document_ids)):
            if any(not isinstance(value, str) or not value for value in values):
                raise ValueError(f"{name} filters must contain non-empty strings.")


class QdrantVectorStore:
    def __init__(
        self,
        project_root: str | Path,
        collection_name: str,
        embedding: EmbeddingDescriptor,
        chunking_version: str,
        qdrant_url: str = "http://127.0.0.1:6333",
        client: QdrantClient | None = None,
        batch_size: int = 64,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        if not COLLECTION_PATTERN.fullmatch(collection_name):
            raise ValueError("Invalid Qdrant collection name.")
        if collection_name == "rag_pipeline_smoke_test_4d":
            raise ValueError("Production storage cannot target the preserved smoke-test collection.")
        self.collection_name = collection_name
        self.embedding = embedding
        self.chunking_version = chunking_version
        self.batch_size = batch_size
        if batch_size < 1 or timeout_seconds <= 0:
            raise ValueError("Batch size and timeout must be positive.")
        self.qdrant_url = self._validate_loopback_url(qdrant_url)
        self.manifest_path = (self.project_root / "knowledge_base" / "metadata" / "qdrant_indexes" / f"{collection_name}.json").resolve()
        if not self.manifest_path.is_relative_to(self.project_root):
            raise ValueError("Qdrant index manifest path escapes the project root.")
        self._owns_client = client is None
        self._collection_ready = False
        self.client = client or QdrantClient(url=self.qdrant_url, timeout=timeout_seconds)

    @staticmethod
    def _validate_loopback_url(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Qdrant URL must be an unauthenticated HTTP loopback URL.")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("Qdrant base URL cannot contain a path, query, or fragment.")
        host = parsed.hostname.lower()
        is_loopback = host == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                is_loopback = False
        # Exact private Docker DNS target on the dedicated vector network.
        docker_qdrant = host == "qdrant" and parsed.port == 6333
        if not is_loopback and not docker_qdrant:
            raise ValueError("Qdrant client is restricted to loopback addresses.")
        return f"http://{parsed.netloc}"

    def _expected_manifest(self) -> dict[str, Any]:
        return {
            "manifest_version": "1.0",
            "collection_name": self.collection_name,
            "vector_name": "dense",
            "dimensions": self.embedding.dimensions,
            "distance": "Cosine",
            "embedding_provider": self.embedding.provider,
            "embedding_model": self.embedding.model_name,
            "embedding_model_digest": self.embedding.model_digest,
            "chunking_version": self.chunking_version,
        }

    def _read_manifest(self) -> dict[str, Any] | None:
        if not self.manifest_path.is_file():
            return None
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexCompatibilityError("Qdrant index manifest is unreadable.") from exc
        if not isinstance(value, dict):
            raise IndexCompatibilityError("Qdrant index manifest has an invalid shape.")
        return value

    @staticmethod
    def _write_manifest(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(value, file, indent=2, ensure_ascii=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def ensure_collection(self) -> None:
        expected = self._expected_manifest()
        existing_manifest = self._read_manifest()
        exists = self.client.collection_exists(self.collection_name)
        if existing_manifest is not None and existing_manifest != expected:
            raise IndexCompatibilityError("Configured embedding or chunking metadata does not match this collection manifest.")
        if exists and existing_manifest is None:
            raise IndexCompatibilityError("Existing collection has no compatibility manifest; refusing to assume its vector model.")
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(size=self.embedding.dimensions, distance=models.Distance.COSINE),
                },
            )
            if existing_manifest is None:
                self._write_manifest(self.manifest_path, expected)
        else:
            info = self.client.get_collection(self.collection_name)
            vectors = info.config.params.vectors
            dense = vectors.get("dense") if isinstance(vectors, dict) else None
            if dense is None or dense.size != self.embedding.dimensions or dense.distance != models.Distance.COSINE:
                raise IndexCompatibilityError("Qdrant collection dimensions or distance do not match the configured embedding.")
        for field_name in ("tenant_id", "source_id", "document_id", "acl_principals", "license_review_status"):
            field_schema = models.PayloadSchemaType.KEYWORD
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=field_schema,
                wait=True,
            )

    def health_check(self) -> dict[str, Any]:
        """Inspect a managed collection without creating or changing it."""
        if not self.client.collection_exists(self.collection_name):
            raise VectorStoreError("Configured Qdrant collection does not exist.")
        manifest = self._read_manifest()
        if manifest is None or manifest != self._expected_manifest():
            raise IndexCompatibilityError("Qdrant collection is missing a matching compatibility manifest.")
        info = self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        dense = vectors.get("dense") if isinstance(vectors, dict) else None
        if dense is None or dense.size != self.embedding.dimensions or dense.distance != models.Distance.COSINE:
            raise IndexCompatibilityError("Qdrant collection dimensions or distance do not match the configured embedding.")
        return {
            "healthy": info.status == models.CollectionStatus.GREEN,
            "collection_name": self.collection_name,
            "status": str(info.status),
            "points_count": info.points_count,
            "dimensions": dense.size,
            "embedding_model": self.embedding.model_name,
            "embedding_model_digest": self.embedding.model_digest,
        }

    def _assert_managed_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            raise VectorStoreError("Configured Qdrant collection does not exist.")
        if self._read_manifest() != self._expected_manifest():
            raise IndexCompatibilityError("Refusing to mutate a collection without its matching compatibility manifest.")

    def delete_document(self, tenant_id: str, document_id: str) -> int:
        """Delete all points for one document inside one tenant."""
        if not tenant_id or not document_id:
            raise ValueError("Tenant and document IDs are required for deletion.")
        self._assert_managed_collection()
        query_filter = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
            models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)),
        ])
        before = self.client.count(self.collection_name, count_filter=query_filter, exact=True).count
        if before:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=query_filter),
                wait=True,
            )
        return before

    def delete_source(self, tenant_id: str, source_id: str) -> int:
        """Delete all points for one source inside one tenant."""
        if not tenant_id or not source_id:
            raise ValueError("Tenant and source IDs are required for deletion.")
        self._assert_managed_collection()
        query_filter = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
            models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id)),
        ])
        before = self.client.count(self.collection_name, count_filter=query_filter, exact=True).count
        if before:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(filter=query_filter),
                wait=True,
            )
        return before

    def _validate_payload(self, chunk: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        if any(key in metadata for key in FORBIDDEN_PAYLOAD_KEYS):
            raise ValueError("Filesystem paths cannot be stored in the Qdrant payload.")
        required = ("tenant_id", "source_id", "document_id", "acl_principals", "license_review_status")
        if any(key not in metadata for key in required):
            raise ValueError("Chunk payload is missing required access-control metadata.")
        if not isinstance(metadata["tenant_id"], str) or not metadata["tenant_id"]:
            raise ValueError("Chunk payload tenant_id must be a non-empty string.")
        if not isinstance(metadata["source_id"], str) or not metadata["source_id"] or not isinstance(metadata["document_id"], str) or not metadata["document_id"]:
            raise ValueError("Chunk payload source and document IDs must be strings.")
        if metadata["license_review_status"] != "approved" and not (
            metadata["license_review_status"] == "operator_authorized_unreviewed"
            and metadata.get("ingestion_authority") == "explicit_operator_instruction"
        ):
            raise ValueError("Only reviewed or explicitly operator-authorized records may be indexed.")
        principals = metadata["acl_principals"]
        if not isinstance(principals, list) or not principals or any(not isinstance(item, str) or not item for item in principals):
            raise ValueError("Chunk payload ACL must contain at least one principal.")
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Chunk is missing a stable chunk_id.")
        payload = {
            **metadata,
            "chunk_id": chunk_id,
            "content_id": chunk.get("content_id"),
            "chunk_text": chunk.get("text"),
            "segments": chunk.get("segments"),
            "heading_paths": chunk.get("heading_paths", []),
            "page_references": chunk.get("page_references", []),
            "parent_chunk_id": chunk.get("parent_chunk_id"),
            "embedding_model": self.embedding.model_name,
            "embedding_model_digest": self.embedding.model_digest,
            "embedding_dimensions": self.embedding.dimensions,
            "chunking_version": self.chunking_version,
        }
        if not isinstance(payload["chunk_text"], str) or not payload["chunk_text"]:
            raise ValueError("Chunk text must be non-empty.")
        return payload

    def upsert_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        vectors: Sequence[Sequence[float]],
        metadata_records: Sequence[dict[str, Any]],
    ) -> int:
        if not (len(chunks) == len(vectors) == len(metadata_records)):
            raise ValueError("Chunk, vector, and metadata counts must match.")
        if not chunks:
            return 0
        inserted = 0
        for offset in range(0, len(chunks), self.batch_size):
            batch_points = []
            end = min(offset + self.batch_size, len(chunks))
            for index in range(offset, end):
                vector = vectors[index]
                if len(vector) != self.embedding.dimensions:
                    raise ValueError(f"Vector {index} has the wrong dimensions.")
                values = []
                for value in vector:
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError(f"Vector {index} contains a non-finite value.")
                    values.append(float(value))
                if not any(values):
                    raise ValueError(f"Vector {index} is zero.")
                payload = self._validate_payload(chunks[index], metadata_records[index])
                point_id = str(uuid.uuid5(ID_NAMESPACE, chunks[index]["chunk_id"]))
                batch_points.append(models.PointStruct(id=point_id, vector={"dense": values}, payload=payload))
            self.ensure_collection()
            self.client.upsert(collection_name=self.collection_name, points=batch_points, wait=True)
            inserted += len(batch_points)
        return inserted

    def search(
        self,
        vector: Sequence[float],
        scope: AccessScope,
        limit: int = 10,
        *,
        score_threshold: float | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[SearchHit]:
        return self._search(vector, scope, limit, "approved", score_threshold, filters)

    def search_development_unreviewed(
        self,
        vector: Sequence[float],
        scope: AccessScope,
        limit: int = 10,
        *,
        explicit_operator_authorization: bool = False,
        score_threshold: float | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[SearchHit]:
        if explicit_operator_authorization is not True:
            raise VectorStoreError("Unreviewed retrieval requires explicit operator authorization.")
        readiness_path = self.project_root / "knowledge_base" / "metadata" / "index_manifests" / f"{self.collection_name}.json"
        try:
            readiness = json.loads(readiness_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexCompatibilityError("Development retrieval requires a readable readiness manifest.") from exc
        if (not isinstance(readiness, dict) or readiness.get("collection_name") != self.collection_name
                or readiness.get("status") != "ready"
                or readiness.get("authorization_mode") != "operator_authorized_unreviewed"):
            raise IndexCompatibilityError("Development retrieval is only available for a ready operator-authorized unreviewed index.")
        return self._search(vector, scope, limit, "operator_authorized_unreviewed", score_threshold, filters)

    def _search(
        self,
        vector: Sequence[float],
        scope: AccessScope,
        limit: int,
        license_status: str,
        score_threshold: float | None,
        filters: RetrievalFilters | None,
    ) -> list[SearchHit]:
        if len(vector) != self.embedding.dimensions:
            raise ValueError("Query vector dimensions do not match the collection.")
        if not 1 <= limit <= 100:
            raise ValueError("Search limit must be between 1 and 100.")
        if score_threshold is not None and (isinstance(score_threshold, bool) or not isinstance(score_threshold, (int, float)) or not math.isfinite(score_threshold) or not -1 <= score_threshold <= 1):
            raise ValueError("Score threshold must be a finite cosine score between -1 and 1.")
        values = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("Query vector contains a non-finite value.")
            values.append(float(value))
        if not any(values):
            raise ValueError("Query vector cannot be zero.")
        if not scope.allowed_source_ids:
            return []
        allowed_sources = set(scope.allowed_source_ids)
        if filters is not None and filters.source_ids:
            allowed_sources.intersection_update(filters.source_ids)
            if not allowed_sources:
                return []
        query_filter = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=scope.tenant_id)),
            models.FieldCondition(key="source_id", match=models.MatchAny(any=sorted(allowed_sources))),
            models.FieldCondition(key="license_review_status", match=models.MatchValue(value=license_status)),
            models.FieldCondition(key="acl_principals", match=models.MatchAny(any=list(scope.principals))),
        ], must_not=[])
        if filters is not None and filters.document_ids:
            query_filter.must.append(models.FieldCondition(key="document_id", match=models.MatchAny(any=list(filters.document_ids))))
        if filters is not None and filters.source_types:
            query_filter.must.append(models.FieldCondition(key="source_type", match=models.MatchAny(any=list(filters.source_types))))
        if filters is not None and filters.excluded_document_ids:
            query_filter.must_not.append(models.FieldCondition(
                key="document_id", match=models.MatchAny(any=list(filters.excluded_document_ids))))
        if filters is not None and filters.restricted_source_ids:
            branches = [models.Filter(must_not=[models.FieldCondition(
                key="source_id", match=models.MatchAny(any=list(filters.restricted_source_ids)))])]
            if filters.permitted_document_ids:
                branches.append(models.Filter(must=[models.FieldCondition(
                    key="document_id", match=models.MatchAny(any=list(filters.permitted_document_ids)))]))
            query_filter.must.append(models.Filter(should=branches))
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=values,
            using="dense",
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [
            SearchHit(point_id=str(point.id), score=float(point.score), payload=point.payload or {}, rank=rank)
            for rank, point in enumerate(response.points, start=1)
        ]

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "QdrantVectorStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
