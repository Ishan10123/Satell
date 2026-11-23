"""Versioned local BM25 index built from the managed Qdrant payload snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from ..storage import AccessScope, IndexCompatibilityError, QdrantVectorStore, RetrievalFilters


class SparseIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class SparseSearchHit:
    point_id: str
    chunk_id: str
    document_id: str
    source_id: str
    score: float
    rank: int
    title: str | None
    chunk_text: str
    source_reference: str | None
    content_id: str | None
    heading_paths: tuple[tuple[str, ...], ...]
    page_references: tuple[int, ...]
    tenant_id: str
    acl_principals: tuple[str, ...]
    license_review_status: str
    source_type: str | None

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id, "content_id": self.content_id,
            "document_id": self.document_id, "source_id": self.source_id,
            "tenant_id": self.tenant_id, "acl_principals": list(self.acl_principals),
            "license_review_status": self.license_review_status, "source_type": self.source_type,
            "title": self.title, "chunk_text": self.chunk_text,
            "source_reference": self.source_reference,
            "heading_paths": [list(path) for path in self.heading_paths],
            "page_references": list(self.page_references),
        }


@dataclass(frozen=True)
class SparseRetrievalResult:
    query: str
    hits: tuple[SparseSearchHit, ...]
    retrieval_ms: float


def sparse_index_directory(project_root: str | Path, index_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", index_id):
        raise ValueError("Index ID is invalid for a sparse index path.")
    root = Path(project_root).resolve()
    path = (root / "knowledge_base" / "processed" / "sparse_indexes" / index_id / "fts5-v2").resolve()
    if not path.is_relative_to(root / "knowledge_base" / "processed"):
        raise ValueError("Sparse index path escapes processed data.")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keys = ("chunk_id", "content_id", "document_id", "source_id", "tenant_id", "acl_principals",
            "license_review_status", "source_type", "title", "chunk_text", "source_reference")
    value = {key: payload.get(key) for key in keys}
    for key in ("chunk_id", "document_id", "source_id", "tenant_id", "license_review_status", "chunk_text"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise SparseIndexError(f"Qdrant payload is missing required sparse-index field: {key}.")
    if not isinstance(value["acl_principals"], list) or not value["acl_principals"] or any(not isinstance(x, str) or not x for x in value["acl_principals"]):
        raise SparseIndexError("Qdrant payload has invalid principal ACL metadata.")
    return value


def build_sparse_index(vector_store: QdrantVectorStore, project_root: str | Path,
                       readiness_manifest: dict[str, Any], batch_size: int = 512) -> dict[str, Any]:
    if batch_size < 1 or batch_size > 1000:
        raise ValueError("Sparse build batch size must be between 1 and 1000.")
    index_id = readiness_manifest.get("index_id")
    collection = readiness_manifest.get("collection_name")
    expected_count = readiness_manifest.get("chunk_count")
    if (not isinstance(index_id, str) or collection != vector_store.collection_name
            or type(expected_count) is not int or expected_count < 1
            or readiness_manifest.get("status") != "ready"):
        raise SparseIndexError("A matching ready dense index manifest is required.")
    directory = sparse_index_directory(project_root, index_id)
    database_path = directory / "chunks.sqlite3"
    manifest_path = directory / "manifest.json"
    if directory.exists():
        if not manifest_path.is_file() or not database_path.is_file():
            raise SparseIndexError("Sparse index path already exists but is incomplete; refusing to overwrite it.")
        existing = load_sparse_manifest(directory)
        if existing.get("index_id") == index_id and existing.get("dense_collection") == collection:
            return existing
        raise SparseIndexError("Sparse index path already contains an incompatible manifest.")
    directory.mkdir(parents=True, exist_ok=False)
    temporary = directory / ".chunks.sqlite3.tmp"
    connection = sqlite3.connect(temporary)
    seen_ids: set[str] = set()
    count = 0
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.executescript("""
            CREATE TABLE chunks (
                rowid INTEGER PRIMARY KEY,
                point_id TEXT NOT NULL UNIQUE,
                chunk_id TEXT NOT NULL UNIQUE,
                content_id TEXT,
                document_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                acl_principals TEXT NOT NULL,
                license_review_status TEXT NOT NULL,
                source_type TEXT,
                title TEXT,
                chunk_text TEXT NOT NULL,
                source_reference TEXT,
                heading_paths TEXT NOT NULL,
                page_references TEXT NOT NULL
            );
            CREATE INDEX chunks_auth ON chunks(tenant_id, license_review_status, source_id);
            CREATE VIRTUAL TABLE chunk_fts USING fts5(chunk_text, content='chunks', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2');
        """)
        offset = None
        while True:
            points, offset = vector_store.client.scroll(
                collection_name=collection, limit=batch_size, offset=offset,
                with_payload=True, with_vectors=False,
            )
            rows = []
            for point in points:
                point_id = str(point.id)
                if point_id in seen_ids:
                    raise SparseIndexError("Qdrant returned a duplicate point ID while building the sparse snapshot.")
                seen_ids.add(point_id)
                payload = _clean_payload(point.payload or {})
                rows.append((point_id, payload))
            if rows:
                connection.executemany(
                    "INSERT INTO chunks(point_id, chunk_id, content_id, document_id, source_id, tenant_id, acl_principals, license_review_status, source_type, title, chunk_text, source_reference, heading_paths, page_references) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(pid, p["chunk_id"], p.get("content_id"), p["document_id"], p["source_id"], p["tenant_id"],
                      json.dumps(p["acl_principals"], ensure_ascii=False), p["license_review_status"],
                      p.get("source_type"), p.get("title"), p["chunk_text"], p.get("source_reference"),
                      json.dumps(p.get("heading_paths", []), ensure_ascii=False),
                      json.dumps(p.get("page_references", []), ensure_ascii=False))
                     for pid, p in rows],
                )
                connection.executemany("INSERT INTO chunk_fts(rowid, chunk_text) SELECT rowid, chunk_text FROM chunks WHERE point_id=?",
                                       [(pid,) for pid, _ in rows])
                count += len(rows)
            if offset is None:
                break
        if count != expected_count:
            raise SparseIndexError(f"Qdrant snapshot count {count} does not match ready manifest chunk count {expected_count}.")
        connection.execute("INSERT INTO chunk_fts(chunk_fts) VALUES ('optimize')")
        connection.commit()
        connection.close()
        temporary.replace(database_path)
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        for child in directory.iterdir():
            child.unlink(missing_ok=True)
        directory.rmdir()
        raise
    result = {
        "sparse_manifest_version": "2.0",
        "index_id": index_id,
        "dense_collection": collection,
        "dense_authorization_mode": readiness_manifest.get("authorization_mode"),
        "database": "chunks.sqlite3",
        "database_sha256": _sha256(database_path),
        "point_count": count,
        "bm25": {"implementation": "SQLite FTS5 bm25", "k1": 1.2, "b": 0.75, "tokenizer": "unicode61 remove_diacritics 2"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def load_sparse_manifest(directory: str | Path) -> dict[str, Any]:
    root = Path(directory).resolve()
    try:
        value = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SparseIndexError("Sparse index manifest is missing or invalid.") from exc
    if not isinstance(value, dict):
        raise SparseIndexError("Sparse index manifest has an invalid shape.")
    database = (root / str(value.get("database", ""))).resolve()
    if not database.is_relative_to(root):
        raise SparseIndexError("Sparse database path escapes its index directory.")
    if (value.get("sparse_manifest_version") != "2.0" or not database.is_file()
            or not isinstance(value.get("point_count"), int) or value["point_count"] < 1
            or _sha256(database) != value.get("database_sha256")):
        raise SparseIndexError("Sparse index checksum or manifest validation failed.")
    return value


class BM25Retriever:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory).resolve()
        self.manifest = load_sparse_manifest(self.directory)
        database_path = (self.directory / self.manifest["database"]).resolve()
        if not database_path.is_relative_to(self.directory):
            raise SparseIndexError("Sparse database path escapes its index directory.")
        uri = database_path.as_uri() + "?mode=ro&immutable=1"
        self.connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        try:
            count = self.connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        except sqlite3.Error as exc:
            self.connection.close()
            raise SparseIndexError("Sparse SQLite index is unreadable.") from exc
        if count != self.manifest["point_count"]:
            self.connection.close()
            raise SparseIndexError("Sparse SQLite row count does not match its manifest.")

    @staticmethod
    def _match_expression(query: str) -> str:
        terms = list(dict.fromkeys(re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)))
        if not terms:
            raise ValueError("Sparse query contains no searchable terms.")
        return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms[:64])

    def search(self, query: str, scope: AccessScope, limit: int = 10, *,
               filters: RetrievalFilters | None = None, development_unreviewed: bool = False,
               explicit_operator_authorization: bool = False) -> SparseRetrievalResult:
        import time
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Sparse query must be non-empty text.")
        if not 1 <= limit <= 100:
            raise ValueError("Sparse retrieval limit must be between 1 and 100.")
        status = "approved"
        if development_unreviewed:
            if explicit_operator_authorization is not True or self.manifest.get("dense_authorization_mode") != "operator_authorized_unreviewed":
                raise SparseIndexError("Unreviewed sparse retrieval requires explicit operator authorization and a development index.")
            status = "operator_authorized_unreviewed"
        if not scope.allowed_source_ids:
            return SparseRetrievalResult(query.strip(), (), 0.0)
        sources = set(scope.allowed_source_ids)
        if filters is not None and filters.source_ids:
            sources.intersection_update(filters.source_ids)
        if not sources:
            return SparseRetrievalResult(query.strip(), (), 0.0)
        expression = self._match_expression(query)
        conditions = ["chunk_fts MATCH ?", "c.tenant_id = ?", "c.license_review_status = ?"]
        params: list[Any] = [expression, scope.tenant_id, status]
        source_values = sorted(sources)
        conditions.append(f"c.source_id IN ({','.join('?' for _ in source_values)})")
        params.extend(source_values)
        principal_match = " OR ".join("EXISTS (SELECT 1 FROM json_each(c.acl_principals) WHERE value = ?)" for _ in scope.principals)
        conditions.append(f"({principal_match})")
        params.extend(scope.principals)
        if filters is not None and filters.document_ids:
            conditions.append(f"c.document_id IN ({','.join('?' for _ in filters.document_ids)})")
            params.extend(filters.document_ids)
        if filters is not None and filters.source_types:
            conditions.append(f"c.source_type IN ({','.join('?' for _ in filters.source_types)})")
            params.extend(filters.source_types)
        if filters is not None and filters.excluded_document_ids:
            conditions.append(f"c.document_id NOT IN ({','.join('?' for _ in filters.excluded_document_ids)})")
            params.extend(filters.excluded_document_ids)
        if filters is not None and filters.restricted_source_ids:
            restricted = filters.restricted_source_ids
            clause = f"c.source_id NOT IN ({','.join('?' for _ in restricted)})"
            params.extend(restricted)
            if filters.permitted_document_ids:
                allowed_documents = filters.permitted_document_ids
                clause = f"({clause} OR c.document_id IN ({','.join('?' for _ in allowed_documents)}))"
                params.extend(allowed_documents)
            conditions.append(clause)
        sql = """SELECT c.point_id, c.chunk_id, c.content_id, c.document_id, c.source_id,
                        c.tenant_id, c.acl_principals, c.license_review_status, c.source_type,
                        c.title, c.chunk_text, c.source_reference, c.heading_paths, c.page_references,
                        bm25(chunk_fts, 1.0, 0.0) AS bm25_rank
                 FROM chunk_fts JOIN chunks c ON c.rowid = chunk_fts.rowid
                 WHERE """ + " AND ".join(conditions) + " ORDER BY bm25_rank ASC LIMIT ?"
        params.append(limit)
        started = time.perf_counter()
        try:
            rows = self.connection.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise SparseIndexError("Sparse BM25 query failed.") from exc
        elapsed = (time.perf_counter() - started) * 1000
        hits = tuple(SparseSearchHit(
            point_id=row["point_id"], chunk_id=row["chunk_id"], document_id=row["document_id"],
            source_id=row["source_id"], score=-float(row["bm25_rank"]), rank=rank,
            title=row["title"], chunk_text=row["chunk_text"], source_reference=row["source_reference"],
            content_id=row["content_id"],
            heading_paths=tuple(tuple(x for x in path if isinstance(x, str)) for path in json.loads(row["heading_paths"])
                                if isinstance(path, list)),
            page_references=tuple(x for x in json.loads(row["page_references"]) if isinstance(x, int) and not isinstance(x, bool)),
            tenant_id=row["tenant_id"], acl_principals=tuple(json.loads(row["acl_principals"])),
            license_review_status=row["license_review_status"], source_type=row["source_type"],
        ) for rank, row in enumerate(rows, start=1))
        return SparseRetrievalResult(query.strip(), hits, elapsed)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "BM25Retriever":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
