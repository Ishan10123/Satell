import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.rag_pipeline.ingestion.parsing_job import document_identity_for, run_parsing_job
from src.rag_pipeline.ingestion.approval_workflow import decide_source
from src.rag_pipeline.normalization import normalize_parsed_run


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.processed = self.root / "knowledge_base" / "processed"
        self.parsed_root = self.processed / "parse_runs"
        self.parsed_root.mkdir(parents=True)
        self.raw_root = self.root / "knowledge_base" / "raw"
        self.raw_root.mkdir(parents=True)
        self.registry = {"registry_version": "1.0", "sources": {}}
        evidence_lines = []
        for source_id in ("docs_a", "docs_b"):
            license_file = self.root / f"{source_id}-license.txt"
            license_file.write_text(f"synthetic license for {source_id}", encoding="utf-8")
            evidence_lines.append({"source_id": source_id, "path": str(license_file),
                                  "sha256": hashlib.sha256(license_file.read_bytes()).hexdigest()})
        catalog = self.root / "evidence.jsonl"
        catalog.write_text("".join(json.dumps(row) + "\n" for row in evidence_lines), encoding="utf-8")
        approval_path = self.root / "source_approvals.json"
        approval_path.write_text(json.dumps({"registry_version": "1.0", "sources": {sid: {"status": "pending_review"} for sid in ("docs_a", "docs_b")}}), encoding="utf-8")
        self.registry["sources"] = {
            sid: decide_source(approval_path, sid, "approved", "synthetic reviewer", catalog,
                               "synthetic scoped review", self.root, "synthetic test license", "documentation_candidates")
            for sid in ("docs_a", "docs_b")
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_equal_normalized_content_keeps_both_provenance_records(self):
        documents = []
        for source_id, subdir, text in (
            ("docs_a", "a", "# Same title\n\n  Identical   content.  "),
            ("docs_b", "b", "# Same title\n\nIdentical content."),
        ):
            source_dir = self.raw_root / subdir
            source_dir.mkdir()
            path = source_dir / "guide.md"
            path.write_text(text, encoding="utf-8")
            documents.append({
                "source_id": source_id,
                "source_type": "documentation",
                "source_url": f"https://example.invalid/{source_id}",
                "source_version": "v1",
                "relative_path": "guide.md",
                "local_path": str(path),
                "extension": ".md",
                "file_category": "documentation",
                "ingestion_status": "candidate_not_reviewed",
                "discovery_status": "candidate",
                "license_review_status": "approved",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "file_size_bytes": path.stat().st_size,
            })
        parse_summary = run_parsing_job(
            documents,
            self.registry,
            self.root,
            self.parsed_root,
            {".md"},
            {"approved"},
            run_id="synthetic-parsed",
        )
        self.assertEqual(parse_summary["parsed_documents"], 2)
        destination = self.processed / "normalized_runs" / "synthetic-normalized"
        summary = normalize_parsed_run(
            self.parsed_root / "synthetic-parsed",
            self.root,
            destination,
        )
        self.assertEqual(summary["parsed_documents"], 2)
        self.assertEqual(summary["unique_contents"], 1)
        self.assertEqual(summary["duplicate_documents"], 1)
        content_files = list((destination / "content").glob("*.json"))
        provenance = [json.loads(line) for line in (destination / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(content_files), 1)
        self.assertEqual({record["source_id"] for record in provenance}, {"docs_a", "docs_b"})
        self.assertEqual(len({record["content_id"] for record in provenance}), 1)
        mapping = [json.loads(line) for line in (destination / "canonical_content_map.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(mapping), 1)
        self.assertEqual(len(mapping[0]["provenance"]), 2)

    def test_document_identity_is_path_stable_and_content_independent(self):
        base = {"source_id": "Docs_A", "relative_path": "manual/Guide.md"}
        same_path = {"source_id": "docs_a", "relative_path": "manual/guide.md"}
        other_path = {"source_id": "docs_a", "relative_path": "manual/other.md"}
        other_source = {"source_id": "docs_b", "relative_path": "manual/guide.md"}
        self.assertEqual(document_identity_for(base), document_identity_for(same_path))
        self.assertNotEqual(document_identity_for(base), document_identity_for(other_path))
        self.assertNotEqual(document_identity_for(base), document_identity_for(other_source))

    def test_same_source_identical_content_at_distinct_paths_keeps_two_provenance_rows(self):
        documents = []
        for relative in ("copies/a.md", "copies/b.md"):
            path = self.raw_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Shared\n\nSame normalized content.", encoding="utf-8")
            documents.append({
                "source_id": "docs_a", "source_type": "documentation", "source_url": "https://example.invalid/docs",
                "source_version": "v1", "relative_path": relative, "local_path": str(path), "extension": ".md",
                "file_category": "documentation", "ingestion_status": "candidate_not_reviewed",
                "discovery_status": "candidate", "license_review_status": "approved",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "file_size_bytes": path.stat().st_size,
            })
        parse = run_parsing_job(documents, self.registry, self.root, self.parsed_root, {".md"}, {"approved"}, run_id="same-source-copies")
        self.assertEqual(parse["parsed_documents"], 2)
        destination = self.processed / "normalized_runs" / "same-source-copies-normalized"
        normalize_parsed_run(self.parsed_root / "same-source-copies", self.root, destination)
        provenance = [json.loads(line) for line in (destination / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len({row["content_id"] for row in provenance}), 1)
        self.assertEqual(len({row["document_identity"] for row in provenance}), 2)
        self.assertEqual({row["relative_path"] for row in provenance}, {"copies/a.md", "copies/b.md"})
        mapping = json.loads((destination / "canonical_content_map.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(len(mapping["provenance"]), 2)
        repeat_destination = self.processed / "normalized_runs" / "same-source-copies-repeat"
        normalize_parsed_run(self.parsed_root / "same-source-copies", self.root, repeat_destination)
        repeated = [json.loads(line) for line in (repeat_destination / "provenance.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["document_identity"], r["content_id"]) for r in repeated],
                         [(r["document_identity"], r["content_id"]) for r in provenance])

    def test_normalized_segments_preserve_code_indentation_and_page_references(self):
        source_run = self.parsed_root / "manual-run"
        (source_run / "documents").mkdir(parents=True)
        content = {
            "document_id": "manual-id",
            "source_id": "docs_a",
            "source_type": "documentation",
            "content_hash": "source-file-sha",
            "source_version": "v2",
            "source_url": "https://example.invalid/guide",
            "relative_path": "manual.pdf",
            "segments": [
                {"text": "    if ready:\n        run()", "segment_type": "code", "headings": ["Example"], "page_number": 3}
            ],
        }
        (source_run / "documents" / "manual.json").write_text(json.dumps(content), encoding="utf-8")
        (source_run / "outcomes.jsonl").write_text(json.dumps({
            "status": "parsed",
            "document_id": "manual-id",
            "source_id": "docs_a",
            "output_file": "documents/manual.json",
        }) + "\n", encoding="utf-8")
        destination = self.processed / "normalized_runs" / "manual-normalized"
        normalize_parsed_run(source_run, self.root, destination)
        provenance = json.loads((destination / "provenance.jsonl").read_text(encoding="utf-8").splitlines()[0])
        segment = json.loads(next((destination / "content").glob("*.json")).read_text(encoding="utf-8"))["segments"][0]
        self.assertEqual(segment["text"], "    if ready:\n        run()")
        self.assertEqual(provenance["segment_page_numbers"], [3])

    def test_normalizer_rejects_input_outside_processed_directory(self):
        outside = self.root / "outside"
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, "inside knowledge_base/processed"):
            normalize_parsed_run(outside, self.root, self.processed / "normalized_runs" / "out")

    def test_normalizer_summary_counts_blocked_and_failed_parse_outcomes(self):
        source = self.parsed_root / "outcomes-run"
        source.mkdir()
        (source / "outcomes.jsonl").write_text(
            json.dumps({"status": "blocked"}) + "\n" + json.dumps({"status": "parse_failed"}) + "\n",
            encoding="utf-8",
        )
        summary = normalize_parsed_run(
            source,
            self.root,
            self.processed / "normalized_runs" / "outcomes-normalized",
        )
        self.assertEqual(summary["source_outcome_counts"], {"blocked": 1, "parse_failed": 1})
        self.assertEqual(summary["parsed_documents"], 0)

    def test_normalizer_refuses_to_overwrite_existing_run(self):
        source = self.parsed_root / "empty-run"
        source.mkdir()
        (source / "outcomes.jsonl").write_text("", encoding="utf-8")
        destination = self.processed / "normalized_runs" / "existing"
        destination.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            normalize_parsed_run(source, self.root, destination)


if __name__ == "__main__":
    unittest.main()
