"""Idempotently recover Markdown parse failures into the existing managed index."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import ragctl  # noqa: E402
from rag_pipeline.configuration import load_chunking_components  # noqa: E402
from rag_pipeline.ingestion.approval import load_approval_registry  # noqa: E402
from rag_pipeline.ingestion.discovery import read_jsonl  # noqa: E402
from rag_pipeline.ingestion.indexing import index_normalized_run  # noqa: E402
from rag_pipeline.ingestion.parsing_job import document_id_for, run_parsing_job  # noqa: E402
from rag_pipeline.normalization import normalize_parsed_run  # noqa: E402
from rag_pipeline.storage.index_manifest import (  # noqa: E402
    index_manifest_path,
    validate_index_manifest,
    write_index_manifest,
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def _collection_document_ids(store) -> tuple[set[str], set[str], int]:
    document_ids: set[str] = set()
    source_ids: set[str] = set()
    point_count = 0
    offset = None
    while True:
        points, offset = store.client.scroll(
            collection_name=store.collection_name,
            limit=1000,
            offset=offset,
            with_payload=["document_id", "source_id"],
            with_vectors=False,
        )
        point_count += len(points)
        for point in points:
            payload = point.payload or {}
            document_id = payload.get("document_id")
            source_id = payload.get("source_id")
            if isinstance(document_id, str):
                document_ids.add(document_id)
            if isinstance(source_id, str):
                source_ids.add(source_id)
        if offset is None or not points:
            break
    return document_ids, source_ids, point_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parse-run", type=Path, required=True, help="Original parse run containing parse_failed outcomes")
    parser.add_argument("--report", type=Path, required=True, help="Audit JSON to update with recovery results")
    args = parser.parse_args(argv)

    parse_run = args.parse_run.resolve()
    processed_root = (PROJECT_ROOT / "knowledge_base" / "processed").resolve()
    if not parse_run.is_relative_to(processed_root) or not (parse_run / "outcomes.jsonl").is_file():
        raise SystemExit("Parse run must be a valid run inside knowledge_base/processed.")
    report_path = args.report.resolve()
    if not report_path.is_relative_to((PROJECT_ROOT / "knowledge_base" / "metadata").resolve()):
        raise SystemExit("Audit report must be inside knowledge_base/metadata.")
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    inventory_path = PROJECT_ROOT / "knowledge_base" / "metadata" / "ingestion_inventory.jsonl"
    inventory = _read_jsonl(inventory_path)
    documents_by_id: dict[str, dict] = {}
    for document in inventory:
        documents_by_id.setdefault(document_id_for(document), document)

    original_outcomes = _read_jsonl(parse_run / "outcomes.jsonl")
    failed_ids = {
        row["document_id"] for row in original_outcomes
        if row.get("status") == "parse_failed" and isinstance(row.get("document_id"), str)
    }
    candidates = [documents_by_id[doc_id] for doc_id in sorted(failed_ids) if doc_id in documents_by_id]
    if len(candidates) != len(failed_ids):
        raise SystemExit("One or more parse-failed IDs do not map to a current inventory record.")

    embedding, store = ragctl._make_store({})
    try:
        tokenizer, chunk_config, strategy, raw_chunking = load_chunking_components(
            PROJECT_ROOT,
            PROJECT_ROOT / "configs" / "chunking.json",
            PROJECT_ROOT / "configs" / "embedding.json",
        )
        current_manifest = validate_index_manifest(
            store,
            PROJECT_ROOT,
            tokenizer,
            raw_chunking,
            inventory_path,
        )
        if current_manifest.get("authorization_mode") != "operator_authorized_unreviewed":
            raise SystemExit("Recovery requires the existing operator-authorized development index.")

        existing_document_ids, _, _ = _collection_document_ids(store)
        already_present = sorted(failed_ids & existing_document_ids)
        recover_documents = [document for document in candidates if document_id_for(document) not in existing_document_ids]
        if not recover_documents:
            previous_recovery = report.get("recovery", {})
            if previous_recovery.get("status") == "recovered":
                previous_recovery["idempotent_reruns"] = previous_recovery.get("idempotent_reruns", 0) + 1
                recovery = previous_recovery
                recovered_ids = set(recovery.get("recovered_document_ids", []))
                for record in report.get("records", []):
                    if record.get("document_id") in recovered_ids and record.get("original_parse_status") == "parse_failed":
                        record["processing_status"] = "recovered_and_indexed"
                        record["index_status"] = "indexed"
                        record["recovery_parse_run_id"] = recovery.get("parse_run_id")
                        record["recovery_normalized_run_id"] = recovery.get("normalized_run_id")
                summary = report.setdefault("summary", {})
                summary["recovered_documents"] = recovery.get("recovered_documents", 0)
                summary["recovered_chunks"] = recovery.get("recovered_chunks", 0)
                summary["remaining_parse_failures"] = recovery.get("parse_summary", {}).get("parse_failures", 0)
                summary["indexed_documents_after_recovery"] = recovery.get("final_document_count")
                summary["qdrant_points_after_recovery"] = recovery.get("final_chunk_count")
                summary["parsed_unique_documents_missing_from_qdrant_after_recovery"] = 0
            else:
                recovery = {
                    "status": "already_present",
                    "recovered_documents": 0,
                    "already_present_documents": len(already_present),
                    "parse_run_id": None,
                    "normalized_run_id": None,
                    "recovered_document_ids": [],
                }
            report["recovery"] = recovery
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps(report["recovery"], indent=2))
            return 0

        config = ragctl._config()
        approval_registry = load_approval_registry(ragctl.APPROVALS)
        recovery_suffix = uuid.uuid4().hex[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        parse_id = f"parse-recovery-{timestamp}-{recovery_suffix}"
        document_approval_registry = (
            json.loads(ragctl.DOC_APPROVALS.read_text(encoding="utf-8-sig"))
            if ragctl.DOC_APPROVALS.is_file()
            else None
        )
        parse_summary = run_parsing_job(
            recover_documents,
            approval_registry,
            PROJECT_ROOT,
            PROJECT_ROOT / "knowledge_base" / "processed" / "parse_runs",
            config.allowed_extensions,
            config.approved_license_statuses,
            run_id=parse_id,
            document_approval_registry=document_approval_registry,
            operator_authorized_unreviewed=True,
        )
        if parse_summary["parse_failures"] or parse_summary["parsed_documents"] != len(recover_documents):
            raise SystemExit(f"Recovery parse did not succeed for all requested records: {parse_summary}")

        normalized_id = f"normalized-recovery-{timestamp}-{recovery_suffix}"
        normalized_path = PROJECT_ROOT / "knowledge_base" / "processed" / "normalized_runs" / normalized_id
        normalize_summary = normalize_parsed_run(
            PROJECT_ROOT / "knowledge_base" / "processed" / "parse_runs" / parse_id,
            PROJECT_ROOT,
            normalized_path,
        )

        old_index = json.loads(index_manifest_path(PROJECT_ROOT, store.collection_name).read_text(encoding="utf-8-sig"))
        write_index_manifest(
            PROJECT_ROOT,
            index_id=old_index["index_id"],
            vector_store=store,
            tokenizer=tokenizer,
            chunking_config=raw_chunking,
            source_ids=old_index["authorized_source_ids"],
            document_count=old_index["document_count"],
            chunk_count=old_index["chunk_count"],
            source_manifest_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            status="building",
            authorization_mode="operator_authorized_unreviewed",
        )
        result = index_normalized_run(
            normalized_path,
            recover_documents,
            approval_registry,
            PROJECT_ROOT,
            config.allowed_extensions,
            config.approved_license_statuses,
            embedding,
            store,
            tokenizer,
            old_index.get("tenant_id", "local") or "local",
            ("local-admin",),
            approval_registry_path=ragctl.APPROVALS,
            strategy=strategy,
            chunk_config=chunk_config,
            document_approval_registry_path=ragctl.DOC_APPROVALS,
            operator_authorized_unreviewed=True,
        )
        if result["indexed_documents"] != result["eligible_documents"] or result["indexed_documents"] != len(recover_documents):
            raise SystemExit(f"Recovery indexing did not complete all documents: {result}")

        deadline = time.monotonic() + 180
        health = store.health_check()
        while health.get("healthy") is not True and time.monotonic() < deadline:
            time.sleep(2)
            health = store.health_check()
        if health.get("healthy") is not True:
            raise SystemExit(f"Qdrant did not return green within 180 seconds after recovery: {health}")
        document_ids, source_ids, point_count = _collection_document_ids(store)
        manifest = write_index_manifest(
            PROJECT_ROOT,
            index_id=old_index["index_id"],
            vector_store=store,
            tokenizer=tokenizer,
            chunking_config=raw_chunking,
            source_ids=sorted(source_ids),
            document_count=len(document_ids),
            chunk_count=point_count,
            source_manifest_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
            status="ready",
            authorization_mode="operator_authorized_unreviewed",
        )
        validate_index_manifest(store, PROJECT_ROOT, tokenizer, raw_chunking, inventory_path)
        recovery = {
            "status": "recovered",
            "recovered_documents": result["indexed_documents"],
            "recovered_chunks": result["indexed_chunks"],
            "already_present_documents": len(already_present),
            "parse_run_id": parse_id,
            "normalized_run_id": normalized_id,
            "recovered_document_ids": sorted(document_id_for(d) for d in recover_documents),
            "parse_summary": parse_summary,
            "normalization_summary": normalize_summary,
            "index_id": manifest["index_id"],
            "final_document_count": manifest["document_count"],
            "final_chunk_count": manifest["chunk_count"],
        }
        recovered_ids = set(recovery["recovered_document_ids"])
        for record in report.get("records", []):
            if record.get("document_id") in recovered_ids and record.get("original_parse_status") == "parse_failed":
                record["processing_status"] = "recovered_and_indexed"
                record["index_status"] = "indexed"
                record["recovery_parse_run_id"] = parse_id
                record["recovery_normalized_run_id"] = normalized_id
        summary = report.setdefault("summary", {})
        summary["recovered_documents"] = recovery["recovered_documents"]
        summary["recovered_chunks"] = recovery["recovered_chunks"]
        summary["remaining_parse_failures"] = parse_summary["parse_failures"]
        summary["indexed_documents_after_recovery"] = manifest["document_count"]
        summary["qdrant_points_after_recovery"] = manifest["chunk_count"]
        summary["parsed_unique_documents_missing_from_qdrant_after_recovery"] = 0
        report["recovery"] = recovery
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(recovery, indent=2, ensure_ascii=False))
        return 0
    finally:
        store.close()
        embedding.close()


if __name__ == "__main__":
    raise SystemExit(main())
