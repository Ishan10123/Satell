import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.rag_pipeline.ingestion.parsing_job import run_parsing_job
from src.rag_pipeline.ingestion.approval_workflow import decide_source


class ParsingJobTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.output_root = self.root / "knowledge_base" / "processed" / "parse_runs"
        self.output_root.mkdir(parents=True)
        self.source_root = self.root / "knowledge_base" / "raw" / "docs"
        self.source_root.mkdir(parents=True)
        self.document_path = self.source_root / "guide.md"
        self.document_path.write_text("# Guide\n\nSynthetic text.", encoding="utf-8")
        license_file = self.root / "license.txt"
        license_file.write_text("synthetic license", encoding="utf-8")
        row = {"source_id": "docs", "path": str(license_file),
               "sha256": hashlib.sha256(license_file.read_bytes()).hexdigest()}
        catalog = self.root / "evidence.jsonl"
        catalog.write_text(json.dumps(row) + "\n", encoding="utf-8")
        approval_path = self.root / "source_approvals.json"
        approval_path.write_text(json.dumps({"registry_version": "1.0", "sources": {"docs": {"status": "pending_review"}}}), encoding="utf-8")
        approved = decide_source(approval_path, "docs", "approved", "synthetic reviewer", catalog,
                                 "synthetic test source scope", self.root, "synthetic test license", "documentation_candidates")
        self.registry = {"registry_version": "1.0", "sources": {"docs": approved}}
        self.document = {
            "source_id": "docs",
            "source_type": "documentation",
            "source_url": "https://example.invalid/guide",
            "source_version": "synthetic-v1",
            "relative_path": "guide.md",
            "local_path": str(self.document_path),
            "extension": ".md",
            "file_category": "documentation",
            "ingestion_status": "candidate_not_reviewed",
            "discovery_status": "candidate",
            "license_review_status": "approved",
            "sha256": hashlib.sha256(self.document_path.read_bytes()).hexdigest(),
            "file_size_bytes": self.document_path.stat().st_size,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_job(self, documents=None, registry=None, output_root=None, run_id="synthetic-run"):
        return run_parsing_job(
            documents=documents or [self.document],
            approval_registry=registry or self.registry,
            project_root=self.root,
            output_root=output_root or self.output_root,
            allowed_extensions={".md", ".html", ".rst", ".pdf", ".txt"},
            approved_license_statuses={"approved"},
            run_id=run_id,
        )

    def test_authorized_synthetic_document_is_written_with_provenance(self):
        summary = self.run_job()
        self.assertEqual(summary["parsed_documents"], 1)
        run_dir = self.output_root / "synthetic-run"
        outcome = json.loads((run_dir / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()[0])
        output_path = run_dir / outcome["output_file"]
        parsed = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["source_id"], "docs")
        self.assertEqual(parsed["segments"][0]["headings"], ["Guide"])
        self.assertNotIn("source_path", parsed)
        self.assertNotIn("local_path", parsed)

    def test_pending_source_is_recorded_without_parsing_or_output(self):
        registry = json.loads(json.dumps(self.registry))
        registry["sources"]["docs"]["status"] = "pending_review"
        summary = self.run_job(registry=registry)
        self.assertEqual(summary["blocked_documents"], 1)
        self.assertEqual(summary["parsed_documents"], 0)
        outcomes = (self.output_root / "synthetic-run" / "outcomes.jsonl").read_text(encoding="utf-8")
        self.assertIn('"authorization_status": "source_pending_review"', outcomes)
        self.assertFalse((self.output_root / "synthetic-run" / "documents").exists())

    def test_authorized_parse_failure_is_persisted_without_dropping_record(self):
        self.document_path.write_text("   \n\n", encoding="utf-8")
        self.document["sha256"] = hashlib.sha256(self.document_path.read_bytes()).hexdigest()
        self.document["file_size_bytes"] = self.document_path.stat().st_size
        summary = self.run_job()
        self.assertEqual(summary["parse_failures"], 1)
        outcome = json.loads((self.output_root / "synthetic-run" / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(outcome["status"], "parse_failed")
        self.assertIn("no extractable text", outcome["error"])

    def test_output_location_must_be_inside_processed_tree(self):
        with self.assertRaisesRegex(ValueError, "under knowledge_base/processed"):
            self.run_job(output_root=self.root / "elsewhere")

    def test_existing_run_directory_is_not_overwritten(self):
        (self.output_root / "already-used").mkdir()
        with self.assertRaises(FileExistsError):
            self.run_job(run_id="already-used")


if __name__ == "__main__":
    unittest.main()
