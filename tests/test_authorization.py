import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.rag_pipeline.ingestion.approval import authorize_document, load_approval_registry
from src.rag_pipeline.ingestion.discovery import documentation_candidates
from src.rag_pipeline.ingestion.registry import IngestionConfig, SourceDefinition, load_config
from src.rag_pipeline.ingestion.approval_workflow import decide_document


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.document_path = self.root / "guide.md"
        self.document_path.write_text("approved test content", encoding="utf-8")
        self.evidence_artifact = self.root / "license.txt"
        self.evidence_artifact.write_text("synthetic license evidence", encoding="utf-8")
        evidence_row = {"source_id": "docs", "path": str(self.evidence_artifact),
                        "sha256": hashlib.sha256(self.evidence_artifact.read_bytes()).hexdigest()}
        self.evidence_catalog = self.root / "evidence.jsonl"
        self.evidence_catalog.write_text(json.dumps(evidence_row) + "\n", encoding="utf-8")
        from src.rag_pipeline.ingestion.approval_workflow import decide_source
        registry_path = self.root / "approvals.json"
        registry_path.write_text(json.dumps({"registry_version": "1.0", "sources": {"docs": {"status": "pending_review"}}}), encoding="utf-8")
        approved = decide_source(registry_path, "docs", "approved", "test reviewer", self.evidence_catalog,
                                 "synthetic license reviewed", self.root, "synthetic test license", "documentation_candidates")
        self.registry = {
            "registry_version": "1.0",
            "sources": {"docs": approved},
        }
        self.document = {
            "source_type": "documentation",
            "source_id": "docs",
            "local_path": str(self.document_path),
            "relative_path": "guide.md",
            "extension": ".md",
            "file_category": "documentation",
            "ingestion_status": "candidate_not_reviewed",
            "license_review_status": "approved",
            "discovery_status": "candidate",
            "sha256": hashlib.sha256(self.document_path.read_bytes()).hexdigest(),
            "file_size_bytes": self.document_path.stat().st_size,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def authorize(self, document=None, registry=None):
        return authorize_document(document or self.document, registry or self.registry, self.root)

    def test_approved_source_and_valid_file_are_authorized(self):
        self.assertTrue(self.authorize()["authorized"])

    def test_verified_source_review_covers_documentation_candidates_in_scope(self):
        document = {**self.document, "license_review_status": "pending"}
        self.assertTrue(self.authorize(document)["authorized"])

    def test_explicit_operator_run_bypasses_review_but_keeps_document_scope(self):
        pending = {"registry_version": "1.0", "sources": {"docs": {"status": "pending_review"}}}
        result = authorize_document(self.document, pending, self.root, operator_authorized_unreviewed=True)
        self.assertTrue(result["authorized"])
        self.assertEqual(result["authorization_status"], "operator_authorized_unreviewed")
        unsupported = {**self.document, "file_category": "code", "relative_path": "guide.md"}
        self.assertEqual(authorize_document(unsupported, pending, self.root,
                                            operator_authorized_unreviewed=True)["authorization_status"],
                         "unsupported_category")

    def test_source_scoped_license_review_does_not_require_duplicate_document_evidence(self):
        document = {key: value for key, value in self.document.items() if key != "license_review_status"}
        self.assertTrue(self.authorize(document)["authorized"])

    def test_rejected_document_license_is_blocked(self):
        document = {**self.document, "license_review_status": "rejected"}
        self.assertEqual(self.authorize(document)["authorization_status"], "document_license_rejected")

    def test_pending_and_rejected_sources_remain_blocked(self):
        for status in ("pending_review", "rejected"):
            registry = json.loads(json.dumps(self.registry))
            registry["sources"]["docs"]["status"] = status
            self.assertFalse(self.authorize(registry=registry)["authorized"])

    def test_unregistered_source_is_blocked(self):
        document = {**self.document, "source_id": "unknown"}
        self.assertEqual(self.authorize(document)["authorization_status"], "source_not_registered")

    def test_missing_file_is_blocked_even_for_approved_source(self):
        document = {**self.document, "local_path": str(self.root / "missing.md")}
        self.assertEqual(self.authorize(document)["authorization_status"], "missing_file")

    def test_checksum_mismatch_is_blocked_even_for_approved_source(self):
        self.document_path.write_text("changed after manifest", encoding="utf-8")
        self.assertEqual(self.authorize()["authorization_status"], "checksum_mismatch")

    def test_missing_checksum_is_blocked(self):
        document = {key: value for key, value in self.document.items() if key != "sha256"}
        self.assertEqual(self.authorize(document)["authorization_status"], "missing_or_invalid_checksum")

    def test_unsupported_extension_is_blocked(self):
        path = self.root / "guide.py"
        path.write_text("print('not parsed')", encoding="utf-8")
        document = {**self.document, "local_path": str(path), "relative_path": "guide.py", "extension": ".py"}
        self.assertEqual(self.authorize(document)["authorization_status"], "unsupported_extension")

    def test_invalid_manifest_metadata_is_blocked(self):
        document = {**self.document, "discovery_status": "invalid_metadata"}
        self.assertEqual(self.authorize(document)["authorization_status"], "invalid_metadata")

    def test_explicitly_excluded_manifest_record_is_blocked(self):
        document = {**self.document, "ingestion_status": "review_required"}
        self.assertEqual(self.authorize(document)["authorization_status"], "explicitly_excluded")

    def test_path_outside_project_is_blocked(self):
        outside = Path(self.temp_dir.name).parent / "outside.md"
        outside.write_text("synthetic", encoding="utf-8")
        try:
            document = {**self.document, "local_path": str(outside), "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()}
            self.assertEqual(self.authorize(document)["authorization_status"], "path_outside_project")
        finally:
            outside.unlink(missing_ok=True)

    def test_research_paper_explicit_exclusion_is_blocked(self):
        pdf_path = self.root / "paper.pdf"
        pdf_path.write_bytes(b"synthetic pdf placeholder")
        document = {
            **self.document,
            "source_type": "research_paper",
            "local_path": str(pdf_path),
            "ingestion_status": "review_required",
            "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            "file_size_bytes": pdf_path.stat().st_size,
            "audit_status": "PASS",
            "sha256_valid": True,
        }
        self.assertEqual(self.authorize(document)["authorization_status"], "explicitly_excluded")

    def test_research_audit_and_checksum_flags_are_required(self):
        document = {**self.document, "source_type": "research_paper", "extension": ".pdf", "file_category": "research_paper", "audit_status": "FAIL", "sha256_valid": False, "license_review_status": "approved"}
        pdf_path = self.root / "paper.pdf"
        pdf_path.write_bytes(b"synthetic pdf placeholder")
        document["local_path"] = str(pdf_path)
        document["sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        document["file_size_bytes"] = pdf_path.stat().st_size
        self.assertEqual(self.authorize(document)["authorization_status"], "audit_failed")

    def test_research_paper_requires_individual_document_decision(self):
        pdf_path = self.root / "paper.pdf"
        pdf_path.write_bytes(b"synthetic pdf")
        document = {**self.document, "source_type": "research_paper", "local_path": str(pdf_path),
                    "extension": ".pdf", "file_category": "research_paper", "relative_path": None,
                    "audit_status": "PASS", "sha256_valid": True,
                    "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                    "file_size_bytes": pdf_path.stat().st_size}
        registry = json.loads(json.dumps(self.registry))
        registry["sources"]["docs"]["approval_scope"] = "paper_source_metadata_only"
        result = self.authorize(document, registry)
        self.assertEqual(result["authorization_status"], "document_approval_missing_or_pending")

    def test_document_rejection_overrides_source_approval(self):
        from src.rag_pipeline.ingestion.parsing_job import document_id_for
        document_id = document_id_for(self.document)
        row = {"source_id": "docs", "document_id": document_id,
               "path": str(self.evidence_artifact), "sha256": hashlib.sha256(self.evidence_artifact.read_bytes()).hexdigest()}
        with self.evidence_catalog.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row) + "\n")
        document_registry_path = self.root / "document_approvals.json"
        decision = decide_document(document_registry_path, document_id, "docs", "approved", "reviewer",
                                   self.evidence_catalog, "document-level approval", self.root, "MIT")
        result = authorize_document(self.document, self.registry, self.root,
                                    document_approval_registry={"documents": {document_id: decision}})
        self.assertTrue(result["authorized"])
        decision = decide_document(document_registry_path, document_id, "docs", "rejected", "reviewer",
                                   self.evidence_catalog, "document contains out-of-scope license", self.root,
                                   "Third-party terms")
        # A document rejection must take precedence over a source-level approval.
        result = authorize_document(self.document, self.registry, self.root,
                                    document_approval_registry={"documents": {document_id: decision}})
        self.assertEqual(result["authorization_status"], "document_approval_rejected")


class DiscoveryTests(unittest.TestCase):
    def test_project_ingestion_configuration_validates(self):
        config = load_config(Path(__file__).resolve().parents[1] / "configs" / "ingestion_sources.json")
        self.assertEqual(len(config.sources), 2)
        self.assertTrue(config.require_license_approval)


    def test_discovery_preserves_manifest_status_and_lists_excluded_extensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            source_root = root / "docs"
            source_root.mkdir()
            (source_root / "guide.md").write_text("guide", encoding="utf-8")
            (source_root / "example.py").write_text("print('x')", encoding="utf-8")
            manifest = root / "manifest.jsonl"
            records = [
                {"source_id": "docs", "relative_path": "guide.md", "extension": ".md", "file_category": "documentation", "ingestion_status": "candidate_not_reviewed", "license_review_status": "pending"},
                {"source_id": "docs", "relative_path": "example.py", "extension": ".py", "file_category": "code", "ingestion_status": "supporting_asset", "license_review_status": "pending"},
            ]
            manifest.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
            summary = root / "summary.json"
            summary.write_text(json.dumps({"sources": [{"source_id": "docs", "root": str(source_root)}]}), encoding="utf-8")
            config = IngestionConfig(
                project_root=root,
                inventory_path=root / "inventory.jsonl",
                summary_path=root / "inventory.json",
                allowed_extensions=frozenset({".md", ".html", ".rst", ".pdf", ".txt"}),
                allowed_categories=frozenset({"documentation"}),
                require_license_approval=True,
                approved_license_statuses=frozenset({"approved"}),
                sources=(),
            )
            source = SourceDefinition("official", "documentation_manifest", True, manifest, summary)
            candidates = documentation_candidates(config, source)
            self.assertEqual(len(candidates), 2)
            self.assertEqual(candidates[0]["ingestion_status"], "candidate_not_reviewed")
            self.assertEqual(candidates[0]["discovery_status"], "pending_license_review")
            self.assertEqual(candidates[1]["discovery_status"], "unsupported_category")

    def test_manifest_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            source_root = root / "docs"
            source_root.mkdir()
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps({"source_id": "docs", "relative_path": "../escape.md", "extension": ".md", "file_category": "documentation"}) + "\n", encoding="utf-8")
            summary = root / "summary.json"
            summary.write_text(json.dumps({"sources": [{"source_id": "docs", "root": str(source_root)}]}), encoding="utf-8")
            config = IngestionConfig(root, root / "inventory.jsonl", root / "inventory.json", frozenset({".md"}), frozenset({"documentation"}), True, frozenset({"approved"}), ())
            source = SourceDefinition("official", "documentation_manifest", True, manifest, summary)
            with self.assertRaises(ValueError):
                documentation_candidates(config, source)

    def test_approval_registry_requires_complete_manual_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "approvals.json"
            path.write_text(json.dumps({"registry_version": "1.0", "sources": {"docs": {"status": "approved"}}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_approval_registry(path)


if __name__ == "__main__":
    unittest.main()
