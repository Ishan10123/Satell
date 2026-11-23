import json
from pathlib import Path
import tempfile
import unittest

from src.rag_pipeline.authorization.local_academic_demo import (
    AUTHORIZATION_SCOPE, POLICY_ID, REGISTRY_VERSION, SOURCE_AUTHORIZATION_SCOPE,
    SOURCE_AUTHORIZATION_STATUS, DemoAuthorizationError, expected_document_map,
    expected_source_map, sign_registry, validate_demo_registry,
    validate_source_registry,
)
from src.rag_pipeline.ingestion.parsing_job import document_id_for


TOKEN = "unit-test-local-demo-signing-key-at-least-thirty-two-characters"


class LocalDemoRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inventory = self.root / "ingestion_inventory.jsonl"
        self.source_path = self.root / "local_academic_demo_source_authorizations.json"
        self.doc_path = self.root / "local_academic_demo_document_authorizations.json"
        self.rows = []
        # Exercise the exact fourteen source-group schema, including per-paper URLs/versions.
        for index in range(14):
            paper = index >= 7
            source_id = f"source_{index:02d}"
            row = {
                "source_type": "research_paper" if paper else "documentation",
                "source_id": source_id, "source_name": f"Source {index}",
                "source_url": f"https://arxiv.org/abs/{index}" if paper else f"https://docs.example/{index}",
                "source_version": f"v{index}" if paper else "1.0", "repository": None,
                "relative_path": f"source-{index}/paper.pdf" if paper else f"source-{index}/guide.md",
                "file_category": "research_paper" if paper else "documentation",
                "ingestion_status": "candidate_not_reviewed", "license_review_status": "pending",
                "sha256": f"{index:064x}",
            }
            self.rows.append(row)
        # Two inventory paths collapse to one content identity and retain both provenances.
        duplicate = dict(self.rows[0], relative_path="source-00/guide-copy.md")
        self.rows.append(duplicate)
        self.inventory.write_text("\n".join(json.dumps(row) for row in self.rows) + "\n", encoding="utf-8")
        self.write_registries()

    def tearDown(self):
        self.temp.cleanup()

    def write_registries(self):
        inventory_sha, sources = expected_source_map(self.inventory)
        now = "2026-11-18T12:00:00+00:00"
        source_rows = {source_id: {
            **value, "inventory_record_count": value["record_count"],
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
            "operator": "test operator", "authorized_at": now, "policy_id": POLICY_ID,
            "inventory_sha256": inventory_sha, "validation_status": "validated",
            "legal_review_status": "pending",
        } for source_id, value in sources.items()}
        source_registry = sign_registry({
            "registry_version": REGISTRY_VERSION, "registry_type": "source_operator_authorization",
            "policy_id": POLICY_ID, "authorization_scope": SOURCE_AUTHORIZATION_SCOPE,
            "operator": "test operator", "authorized_at": now,
            "inventory_sha256": inventory_sha, "source_count": 14,
            "legal_review_status": "pending", "sources": source_rows,
        }, TOKEN)
        self.source_path.write_text(json.dumps(source_registry), encoding="utf-8")

        _sha, docs, doc_sources = expected_document_map(self.inventory)
        doc_rows = {doc_id: {
            "document_id": doc_id, **value,
            "inventory_record_count": len(value["provenance_paths"]),
            "indexed_point_ids": [f"point-{doc_id}"],
            "operator": "test operator", "authorized_at": now,
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "policy_id": POLICY_ID, "authorization_scope": AUTHORIZATION_SCOPE,
            "legal_review_status": "pending",
        } for doc_id, value in docs.items()}
        papers = {document_id_for(row): {
            "document_id": document_id_for(row), "source_id": row["source_id"],
            "content_sha256": row["sha256"], "indexed_point_ids": [f"paper-{row['source_id']}"],
            "operator_authorization_status": SOURCE_AUTHORIZATION_STATUS,
            "operator": "test operator", "authorized_at": now,
            "technical_status": "excluded_pending_individual_license_review",
            "legal_review_status": "pending",
        } for row in self.rows if row["source_type"] == "research_paper"}
        doc_registry = sign_registry({
            "registry_version": REGISTRY_VERSION, "registry_type": "document_operator_authorization",
            "policy_id": POLICY_ID, "authorization_scope": AUTHORIZATION_SCOPE,
            "operator": "test operator", "authorized_at": now, "legal_review_status": "pending",
            "inventory_sha256": inventory_sha, "index_id": "test-index", "collection_name": "rag_docs_v2",
            "source_ids": list(doc_sources), "authorized_inventory_record_count": 8,
            "authorized_document_count": 7, "indexed_document_count": 14,
            "indexed_point_count": 14, "excluded_document_count": 7,
            "documents": doc_rows, "excluded_documents": papers,
        }, TOKEN)
        self.doc_path.write_text(json.dumps(doc_registry), encoding="utf-8")

    def test_all_fourteen_source_records_and_exact_document_mapping_validate(self):
        sources = validate_source_registry(self.source_path, self.inventory, TOKEN)
        docs = validate_demo_registry(self.doc_path, self.inventory, TOKEN,
                                       operator=sources["operator"], source_registry=sources)
        self.assertEqual(len(sources["sources"]), 14)
        self.assertEqual(len(docs["documents"]), 7)
        self.assertEqual(len(docs["excluded_documents"]), 7)
        self.assertTrue(all(row["legal_review_status"] == "pending" for row in sources["sources"].values()))

    def test_source_registry_tampering_and_missing_registry_fail_closed(self):
        altered = json.loads(self.source_path.read_text(encoding="utf-8"))
        altered["sources"]["source_00"]["operator_authorization_status"] = "approved"
        self.source_path.write_text(json.dumps(altered), encoding="utf-8")
        with self.assertRaises(DemoAuthorizationError):
            validate_source_registry(self.source_path, self.inventory, TOKEN)

    def test_unknown_source_is_rejected_even_with_a_valid_signature(self):
        altered = json.loads(self.source_path.read_text(encoding="utf-8"))
        altered["sources"]["unknown_source"] = dict(altered["sources"]["source_00"])
        altered = sign_registry(altered, TOKEN)
        self.source_path.write_text(json.dumps(altered), encoding="utf-8")
        with self.assertRaises(DemoAuthorizationError):
            validate_source_registry(self.source_path, self.inventory, TOKEN)
        self.source_path.unlink()
        with self.assertRaises(DemoAuthorizationError):
            validate_source_registry(self.source_path, self.inventory, TOKEN)

    def test_unknown_document_and_hash_mismatch_fail_closed(self):
        altered = json.loads(self.doc_path.read_text(encoding="utf-8"))
        altered["documents"]["f" * 64] = {"document_id": "f" * 64, "indexed_point_ids": ["unknown"]}
        altered = sign_registry(altered, TOKEN)
        self.doc_path.write_text(json.dumps(altered), encoding="utf-8")
        sources = validate_source_registry(self.source_path, self.inventory, TOKEN)
        with self.assertRaises(DemoAuthorizationError):
            validate_demo_registry(self.doc_path, self.inventory, TOKEN, source_registry=sources)
        self.write_registries()
        row = dict(self.rows[0], sha256="e" * 64)
        self.inventory.write_text("\n".join(json.dumps(item) for item in [row, *self.rows[1:]]) + "\n", encoding="utf-8")
        with self.assertRaises(DemoAuthorizationError):
            validate_demo_registry(self.doc_path, self.inventory, TOKEN)


if __name__ == "__main__":
    unittest.main()
