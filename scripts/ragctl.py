"""Local RAG inventory, approval, indexing, and readiness CLI."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag_pipeline.configuration import load_chunking_components, load_embedding_provider
from rag_pipeline.embeddings import EmbeddingDescriptor
from rag_pipeline.ingestion.approval import authorize_document, load_approval_registry
from rag_pipeline.ingestion.approval_workflow import decide_document, decide_source, load_approval_paths, validate_record
from rag_pipeline.ingestion.discovery import read_jsonl
from rag_pipeline.ingestion.indexing import index_normalized_run
from rag_pipeline.ingestion.registry import load_config
from rag_pipeline.parsing import load_parser_registry
from rag_pipeline.storage import QdrantVectorStore
from rag_pipeline.storage.index_manifest import index_manifest_path, validate_index_manifest, write_index_manifest

META = ROOT / "knowledge_base" / "metadata"
INVENTORY = META / "ingestion_inventory.jsonl"
APPROVAL_PATHS = load_approval_paths(ROOT)
APPROVALS = APPROVAL_PATHS["source_registry"]
DOC_APPROVALS = APPROVAL_PATHS["document_registry"]
EVIDENCE = APPROVAL_PATHS["evidence_catalog"]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ragctl", description="Secure local RAG workflow")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("inventory", "license-report", "authorization-report", "index-status", "validate-index"):
        sub.add_parser(name)
    for name in ("approve-source", "approve-document"):
        item = sub.add_parser(name)
        item.add_argument("subject_id", help="source_id or stable document_id")
        item.add_argument("--source-id", help="required for document decisions")
        item.add_argument("--decision", choices=("pending_review", "approved", "rejected"), required=True)
        item.add_argument("--reviewer", required=True)
        item.add_argument("--license-name", required=True)
        item.add_argument("--scope", choices=("documentation_candidates", "paper_source_metadata_only"),
                          help="required for approve-source; arXiv scope covers source metadata only")
        item.add_argument("--evidence", required=True, help="project-local evidence file with explicit source_id binding")
        item.add_argument("--notes", required=True)
    index = sub.add_parser("index")
    index.add_argument("--normalized-run", type=Path, required=True)
    index.add_argument("--dry-run", action="store_true")
    index.add_argument("--operator-authorized-unreviewed", action="store_true",
                       help="index under the user's explicit operator instruction without changing approval records")
    return p


def _config():
    return load_config(ROOT / "configs" / "ingestion_sources.json")


def _documents():
    return list(read_jsonl(INVENTORY))


def _print(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _approval_statuses():
    registry = load_approval_registry(APPROVALS)
    counts = Counter(entry.get("status", "invalid") for entry in registry["sources"].values())
    return registry, counts


def _make_store(config):
    index_config = json.loads((ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
    index_config.update(config)
    embedding = load_embedding_provider(ROOT / "configs" / "embedding.json")
    health_digest = embedding.spec.model_digest
    descriptor = EmbeddingDescriptor("ollama", embedding.spec.model_name, health_digest,
                                     embedding.spec.dimensions, True, None)
    collection = index_config["collection_name"]
    return embedding, QdrantVectorStore(ROOT, collection, descriptor, index_config["chunking_version"],
                                        qdrant_url=index_config["qdrant_url"])


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "inventory":
            summary = json.loads((META / "ingestion_inventory_summary.json").read_text(encoding="utf-8-sig"))
            _print(summary)
            return 0
        if args.command == "license-report":
            approvals, statuses = _approval_statuses()
            evidence_by_source = Counter(); evidence_valid = Counter()
            for entry in read_jsonl(EVIDENCE):
                source_id = entry.get("source_id")
                if source_id:
                    evidence_by_source[source_id] += 1
                    try:
                        evidence_file = Path(entry["path"]).resolve(strict=True)
                        actual = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
                        if evidence_file.is_relative_to(ROOT) and evidence_file.is_file() and actual == entry.get("sha256"):
                            evidence_valid[source_id] += 1
                    except (KeyError, OSError, ValueError, RuntimeError):
                        pass
            rows = []
            for source_id, approval in sorted(approvals["sources"].items()):
                review_bound = validate_record(approval, source_id, ROOT) if approval.get("status") in {"approved", "rejected"} else False
                rows.append({"source_id": source_id, "decision": approval["status"],
                             "inventory_documents": approval.get("discovered_document_count", 0),
                             "candidate_evidence_records": evidence_by_source[source_id],
                             "verified_candidate_evidence_records": evidence_valid[source_id],
                             "source_evidence_available": evidence_valid[source_id] > 0,
                             "review_evidence_bound": review_bound,
                             "approval_scope": approval.get("approval_scope")})
            _print({"source_decision_counts": dict(statuses), "sources": rows,
                    "note": "Candidate artifacts are source-bound and checksum-verified where counted. They become review-bound only after an explicit decision. Evidence presence is not a legal determination or blanket coverage of third-party assets."})
            return 0
        if args.command == "authorization-report":
            config = _config(); registry = load_approval_registry(APPROVALS)
            doc_registry = json.loads(DOC_APPROVALS.read_text(encoding="utf-8-sig")) if DOC_APPROVALS.is_file() else {}
            documents = _documents(); counts = Counter(); authorized = 0
            for document in documents:
                decision = authorize_document(document, registry, ROOT, config.allowed_extensions,
                                              config.approved_license_statuses, doc_registry)
                counts[decision["authorization_status"]] += 1
                authorized += int(decision["authorized"])
            _print({"total_documents": len(documents), "authorized_documents": authorized,
                    "blocked_documents": len(documents)-authorized, "status_counts": counts})
            return 0 if authorized else 2
        if args.command in {"approve-source", "approve-document"}:
            if args.command == "approve-source":
                result = decide_source(APPROVALS, args.subject_id, args.decision, args.reviewer,
                                       args.evidence, args.notes, ROOT, args.license_name, args.scope or "")
            else:
                if not args.source_id:
                    raise ValueError("approve-document requires --source-id.")
                result = decide_document(DOC_APPROVALS, args.subject_id, args.source_id,
                                         args.decision, args.reviewer, args.evidence, args.notes, ROOT, args.license_name)
            _print(result)
            return 0
        if args.command == "index-status":
            cfg = json.loads((ROOT / "configs" / "embedding.json").read_text(encoding="utf-8-sig"))
            chunk_cfg = json.loads((ROOT / "configs" / "chunking.json").read_text(encoding="utf-8-sig"))
            index_config = json.loads((ROOT / "configs" / "indexing.json").read_text(encoding="utf-8-sig"))
            index_doc = index_manifest_path(ROOT, index_config["collection_name"])
            report = {"manifest_path": str(index_doc), "manifest_exists": index_doc.is_file(),
                      "collection": index_config["collection_name"], "embedding_model": cfg["model_name"],
                      "embedding_dimensions": cfg["dimensions"], "chunk_config_version": chunk_cfg["config_version"]}
            if index_doc.is_file():
                report["manifest"] = json.loads(index_doc.read_text(encoding="utf-8-sig"))
            _print(report)
            return 0
        if args.command == "validate-index":
            embedding, store = _make_store({})
            try:
                tokenizer, _chunk_config, _strategy, chunking = load_chunking_components(
                    ROOT, ROOT / "configs" / "chunking.json", ROOT / "configs" / "embedding.json")
                _print(validate_index_manifest(store, ROOT, tokenizer, chunking, INVENTORY))
            finally:
                store.close(); embedding.close()
            return 0
        if args.command == "index":
            cfg = _config(); registry = load_approval_registry(APPROVALS)
            doc_registry = json.loads(DOC_APPROVALS.read_text(encoding="utf-8-sig")) if DOC_APPROVALS.is_file() else {}
            documents = _documents()
            eligible = [d for d in documents if d.get("source_type") in {"documentation", "research_paper"}
                        and d.get("ingestion_status") in {"candidate", "candidate_not_reviewed"}
                        and str(d.get("extension", "")).lower() in cfg.allowed_extensions]
            blocked = []
            for document in eligible:
                decision = authorize_document(document, registry, ROOT, cfg.allowed_extensions,
                                             cfg.approved_license_statuses, doc_registry,
                                             operator_authorized_unreviewed=args.operator_authorized_unreviewed)
                if not decision["authorized"]:
                    blocked.append({"source_id": document.get("source_id"), "status": decision["authorization_status"]})
            if blocked:
                _print({"error": "Indexing refused: one or more eligible documents are unauthorized.",
                        "eligible_documents": len(eligible), "blocked_count": len(blocked), "sample": blocked[:10]})
                return 3
            embedding, store = _make_store({})
            try:
                tokenizer, chunk_config, strategy, chunking = load_chunking_components(
                    ROOT, ROOT / "configs" / "chunking.json", ROOT / "configs" / "embedding.json")
                run_id = f"index-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
                manifest_args = dict(index_id=run_id, vector_store=store, tokenizer=tokenizer,
                    chunking_config=chunking, source_ids=[], document_count=0, chunk_count=0,
                    source_manifest_sha256=hashlib.sha256(INVENTORY.read_bytes()).hexdigest(),
                    authorization_mode="operator_authorized_unreviewed" if args.operator_authorized_unreviewed else "reviewed_source_and_document_approval")
                if not args.dry_run:
                    write_index_manifest(ROOT, **manifest_args, status="building")
                result = index_normalized_run(args.normalized_run, documents, registry, ROOT,
                    cfg.allowed_extensions, cfg.approved_license_statuses, embedding, store, tokenizer,
                    os.environ.get("RAG_TENANT_ID", "local"), (os.environ.get("RAG_PRINCIPAL_ID", "local-admin"),),
                    approval_registry_path=APPROVALS, strategy=strategy, chunk_config=chunk_config,
                    dry_run=args.dry_run, document_approval_registry_path=DOC_APPROVALS,
                    operator_authorized_unreviewed=args.operator_authorized_unreviewed,
                    parser_registry=load_parser_registry(ROOT / "configs" / "parser_registry.json"))
                if not args.dry_run:
                    health = store.health_check()
                    if (result["indexed_documents"] != result["eligible_documents"]
                            or result["indexed_chunks"] < 1
                            or health.get("points_count") != result["indexed_chunks"]
                            or health.get("healthy") is not True):
                        write_index_manifest(ROOT, **manifest_args, status="failed")
                        raise RuntimeError("Index incomplete; manifest remains failed and retrieval will stay unavailable.")
                    ready_args = {**manifest_args,
                        "source_ids": list(result["source_document_counts"]),
                        "document_count": result["indexed_documents"],
                        "chunk_count": result["indexed_chunks"]}
                    manifest = write_index_manifest(ROOT, **ready_args, status="ready")
                    result["index_manifest"] = manifest
                _print(result)
                return 0
            finally:
                store.close(); embedding.close()
        return 1
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"ragctl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
