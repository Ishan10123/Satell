"""Verify the local corpus/index and build signed source/document demo registries."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_pipeline.authorization.local_academic_demo import (  # noqa: E402
    AUTHORIZATION_SCOPE, POLICY_ID, REGISTRY_VERSION, SOURCE_AUTHORIZATION_SCOPE,
    SOURCE_AUTHORIZATION_STATUS, expected_document_map, expected_source_map,
    sign_registry, validate_local_demo_policy,
)
from rag_pipeline.ingestion.parsing_job import document_id_for  # noqa: E402


INVENTORY = ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl"
MANIFEST = ROOT / "knowledge_base" / "metadata" / "index_manifests" / "rag_docs_v2.json"
POLICY = ROOT / "configs" / "local_academic_demo_policy.json"
SOURCE_OUTPUT = ROOT / "knowledge_base" / "metadata" / "local_academic_demo_source_authorizations_phase1_v3.json"
DOCUMENT_OUTPUT = ROOT / "knowledge_base" / "metadata" / "local_academic_demo_document_authorizations_phase1_v3.json"
EXPECTED_SOURCES = {
    "python_3_13", "postgresql_18", "fastapi", "qdrant", "huggingface_transformers", "pytorch", "docker",
    "arxiv_information_retrieval", "arxiv_llm_rag", "arxiv_machine_learning", "arxiv_llm_transformers",
    "arxiv_artificial_intelligence", "arxiv_database_vector_search", "arxiv_ai_systems",
}


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            tmp = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        tmp.replace(path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", required=True, help="Operator identity recorded in the local authorization packet.")
    parser.add_argument("--qdrant-url", default=os.environ.get("RAG_QDRANT_URL", "http://127.0.0.1:6333"))
    args = parser.parse_args()
    if not args.operator.strip():
        raise SystemExit("Operator identity is required.")
    token = os.environ.get("RAG_API_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("RAG_API_TOKEN must be available in the process environment.")
    if SOURCE_OUTPUT.exists() or DOCUMENT_OUTPUT.exists():
        raise SystemExit("Refusing to overwrite an existing Phase 1 authorization registry.")
    policy = validate_local_demo_policy(POLICY)

    raw_inventory = INVENTORY.read_bytes()
    rows = [json.loads(line) for line in raw_inventory.decode("utf-8-sig").splitlines() if line.strip()]
    inventory_sha, sources = expected_source_map(INVENTORY)
    if set(sources) != EXPECTED_SOURCES or len(rows) != 9932:
        raise SystemExit("The source inventory differs from the explicitly requested 14-source inventory.")
    if any(row.get("license_review_status") != "pending" for row in rows):
        raise SystemExit("Legal review state is no longer uniformly pending; refusing to build registries.")

    category_counts: dict[str, Counter] = defaultdict(Counter)
    extension_counts: dict[str, Counter] = defaultdict(Counter)
    source_doc_ids: dict[str, set[str]] = defaultdict(set)
    paper_rows: dict[str, dict] = {}
    for row in rows:
        source_id = row["source_id"]
        category_counts[source_id][str(row.get("file_category"))] += 1
        extension_counts[source_id][str(row.get("extension"))] += 1
        digest = row.get("sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)):
            raise SystemExit("Inventory contains a missing or invalid SHA-256 value.")
        source_path = Path(row.get("local_path", "")).resolve(strict=True)
        if not source_path.is_relative_to(ROOT.resolve()) or not source_path.is_file():
            raise SystemExit("An inventory file is missing or outside the project root.")
        if source_path.stat().st_size != row.get("file_size_bytes"):
            raise SystemExit("An inventory file size differs from the recorded metadata.")
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != digest:
            raise SystemExit("An inventory file SHA-256 differs from its recorded metadata.")
        if row.get("source_type") == "documentation" and row.get("file_category") == "documentation":
            source_doc_ids[source_id].add(document_id_for(row))
        if row.get("source_type") == "research_paper" and row.get("file_category") == "research_paper":
            did = document_id_for(row)
            previous = paper_rows.setdefault(did, row)
            if (previous.get("source_id"), previous.get("sha256")) != (row.get("source_id"), row.get("sha256")):
                raise SystemExit("Research-paper document identity is ambiguous.")

    doc_inventory_sha, documentation, documentation_sources = expected_document_map(INVENTORY)
    if doc_inventory_sha != inventory_sha or len(documentation) != 6458:
        raise SystemExit("The permitted documentation inventory differs from the audited document scope.")
    if sum(len(value["provenance_paths"]) for value in documentation.values()) != 6489:
        raise SystemExit("The documentation provenance mapping is incomplete.")
    if len(paper_rows) != 107:
        raise SystemExit("Research-paper inventory count differs from the audited 107 records.")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if (manifest.get("status") != "ready" or manifest.get("collection_name") != "rag_docs_v2"
            or manifest.get("authorization_mode") != "operator_authorized_unreviewed"
            or manifest.get("source_manifest_sha256") != inventory_sha
            or manifest.get("document_count") != 6565 or manifest.get("chunk_count") != 58856):
        raise SystemExit("The current index manifest does not match the verified development index.")

    client = QdrantClient(url=args.qdrant_url, timeout=30)
    info = client.get_collection(manifest["collection_name"])
    if info.points_count != manifest["chunk_count"]:
        raise SystemExit("Live Qdrant point count does not match the manifest.")
    indexed: dict[str, dict] = {}
    point_ids_seen: set[str] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=manifest["collection_name"], offset=offset, limit=1000,
            with_payload=["document_id", "source_id", "source_type", "content_hash", "license_review_status"],
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            document_id = payload.get("document_id")
            if not isinstance(document_id, str) or len(document_id) != 64:
                raise SystemExit("Qdrant contains a point with a missing or invalid document ID.")
            point_id = str(point.id)
            if point_id in point_ids_seen:
                raise SystemExit("Qdrant contains a duplicate point ID.")
            point_ids_seen.add(point_id)
            source_id, source_type, content_hash = (payload.get("source_id"), payload.get("source_type"),
                                                     payload.get("content_hash"))
            identity = (source_id, source_type, content_hash)
            current = indexed.setdefault(document_id, {"source_id": source_id, "source_type": source_type,
                "content_sha256": content_hash, "point_ids": []})
            if (current["source_id"], current["source_type"], current["content_sha256"]) != identity:
                raise SystemExit("Qdrant points for one document have conflicting identity metadata.")
            if payload.get("license_review_status") != "operator_authorized_unreviewed":
                raise SystemExit("Qdrant contains an unexpected legal/index review status.")
            current["point_ids"].append(point_id)
        if offset is None:
            break

    expected_indexed: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        if ((row.get("source_type") == "documentation" and row.get("file_category") == "documentation")
                or (row.get("source_type") == "research_paper" and row.get("file_category") == "research_paper")):
            did = document_id_for(row)
            identity = (row["source_id"], row["source_type"], row["sha256"])
            if did in expected_indexed and expected_indexed[did] != identity:
                raise SystemExit("Inventory contains conflicting indexed document identities.")
            expected_indexed[did] = identity
    live_identities = {did: (v["source_id"], v["source_type"], v["content_sha256"]) for did, v in indexed.items()}
    if live_identities != expected_indexed:
        raise SystemExit("Qdrant and the documentation/paper inventory do not map exactly.")
    if len(indexed) != 6565 or sum(len(v["point_ids"]) for v in indexed.values()) != 58856:
        raise SystemExit("Live Qdrant document or point counts differ from the audited totals.")
    for value in indexed.values():
        value["point_ids"].sort()

    now = datetime.now(timezone.utc).isoformat()
    indexed_docs_by_source = Counter(value["source_id"] for value in indexed.values())
    documentation_by_source = Counter(value["source_id"] for value in documentation.values())
    source_records = {}
    for source_id, expected in sorted(sources.items()):
        source_records[source_id] = {
            **expected,
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
            "operator": args.operator,
            "authorized_at": now,
            "policy_id": POLICY_ID,
            "inventory_sha256": inventory_sha,
            "authorization_reason": "Explicit operator authorization for the local Satell academic demonstration; not legal license approval.",
            "associated_document_count": expected["record_count"],
            "inventory_record_count": expected["record_count"],
            "documentation_category_document_count": documentation_by_source[source_id],
            "indexed_document_count": indexed_docs_by_source[source_id],
            "category_counts": dict(sorted(category_counts[source_id].items())),
            "extension_counts": dict(sorted(extension_counts[source_id].items())),
            "validation_status": "validated",
            "legal_review_status": "pending",
        }
    source_registry = sign_registry({
        "registry_version": REGISTRY_VERSION,
        "registry_type": "source_operator_authorization",
        "policy_id": POLICY_ID,
        "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
        "operator": args.operator,
        "authorized_at": now,
        "inventory_sha256": inventory_sha,
        "source_count": len(source_records),
        "legal_review_status": "pending",
        "sources": source_records,
    }, token)

    authorized_documents = {}
    for document_id, value in sorted(documentation.items()):
        index_value = indexed.get(document_id)
        if index_value is None or index_value["source_type"] != "documentation":
            raise SystemExit("A permitted documentation ID is missing from Qdrant.")
        authorized_documents[document_id] = {
            "document_id": document_id,
            "source_id": value["source_id"],
            "content_sha256": value["content_sha256"],
            "inventory_record_count": len(value["provenance_paths"]),
            "provenance_paths": value["provenance_paths"],
            "indexed_point_ids": index_value["point_ids"],
            "operator": args.operator,
            "authorized_at": now,
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "policy_id": POLICY_ID,
            "authorization_scope": AUTHORIZATION_SCOPE,
            "legal_review_status": "pending",
        }
    excluded_papers = {}
    for document_id, row in sorted(paper_rows.items()):
        index_value = indexed.get(document_id)
        if index_value is None or index_value["source_type"] != "research_paper":
            raise SystemExit("A research-paper inventory ID is missing from Qdrant.")
        excluded_papers[document_id] = {
            "document_id": document_id,
            "source_id": row["source_id"],
            "content_sha256": row["sha256"],
            "relative_path": (row["relative_path"].replace("\\", "/")
                              if isinstance(row.get("relative_path"), str) else None),
            "source_url": row.get("source_url"),
            "source_version": row.get("source_version"),
            "source_commit": row.get("source_commit"),
            "acquisition_path": Path(row["local_path"]).resolve().relative_to(ROOT.resolve()).as_posix(),
            "provenance_status": ("complete" if isinstance(row.get("relative_path"), str)
                                  else "relative_path_missing"),
            "indexed_point_ids": index_value["point_ids"],
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "operator": args.operator,
            "authorized_at": now,
            "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
            "policy_id": POLICY_ID,
            "technical_status": "excluded_pending_individual_license_review",
            "exclusion_reason": "Research papers are outside the documentation-only demo category policy; each paper needs document-specific license review.",
            "legal_review_status": "pending",
        }
    doc_registry = sign_registry({
        "registry_version": REGISTRY_VERSION,
        "registry_type": "document_operator_authorization",
        "policy_id": POLICY_ID,
        "authorization_scope": AUTHORIZATION_SCOPE,
        "operator": args.operator,
        "authorized_at": now,
        "inventory_sha256": inventory_sha,
        "index_id": manifest["index_id"],
        "collection_name": manifest["collection_name"],
        "source_ids": list(documentation_sources),
        "permitted_source_types": policy["permitted_source_types"],
        "permitted_file_categories": policy["permitted_file_categories"],
        "authorized_inventory_record_count": sum(v["inventory_record_count"] for v in authorized_documents.values()),
        "authorized_document_count": len(authorized_documents),
        "indexed_document_count": len(indexed),
        "indexed_point_count": sum(len(v["point_ids"]) for v in indexed.values()),
        "excluded_document_count": len(excluded_papers),
        "legal_review_status": "pending",
        "documents": authorized_documents,
        "excluded_documents": excluded_papers,
    }, token)
    write_new(SOURCE_OUTPUT, source_registry)
    try:
        write_new(DOCUMENT_OUTPUT, doc_registry)
    except Exception:
        SOURCE_OUTPUT.unlink(missing_ok=True)
        raise
    print(f"Verified inventory records: {len(rows)}; source groups: {len(source_records)}")
    print(f"Live Qdrant: {len(indexed)} documents; {sum(len(v['point_ids']) for v in indexed.values())} points")
    print(f"Authorized documentation: 6489 inventory records -> {len(authorized_documents)} canonical IDs")
    print(f"Excluded individual research papers: {len(excluded_papers)}; all legal review statuses remain pending")
    print(f"Created source registry: {SOURCE_OUTPUT}")
    print(f"Created document registry: {DOCUMENT_OUTPUT}")


if __name__ == "__main__":
    main()
