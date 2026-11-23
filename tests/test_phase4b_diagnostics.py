import json
import os
from pathlib import Path
import tempfile
import unittest
import re

from src.rag_pipeline.generation.citation_validation import CitationFailure, validate_generated_citations
from src.rag_pipeline.generation.claim_consistency import analyze_claim_consistency
from src.rag_pipeline.generation.claim_verifier import ClaimVerdict
from src.rag_pipeline.generation.evaluation_artifact import EvaluationArtifactStore
from src.rag_pipeline.retrieval.context import Citation


PATTERN = re.compile(r"\[(S[1-9][0-9]*)\]")


def citations(chunk_id="chunk-1"):
    return (Citation("S1", "python", "doc-1", "Python docs", (), None, None,
                     chunk_id=chunk_id, evidence_text="PRIVATE EVIDENCE MUST NOT BE STORED"),)


def validate(answer, citation_rows=None):
    from src.rag_pipeline.generation.claim_verifier import extract_claims
    return validate_generated_citations(answer, citation_rows if citation_rows is not None else citations(),
        PATTERN, extract_claims, lambda _text: False,
        lambda value: all(row["citation_ids"] for row in extract_claims(value, PATTERN)))


class CitationDiagnosticTests(unittest.TestCase):
    def test_each_citation_failure_reason_is_distinct(self):
        cases = {
            "A factual sentence.": "missing_citation_marker",
            "A factual sentence [].": "missing_citation_id",
            "A factual sentence [S].": "missing_citation_id",
            "A factual sentence [S1.": "invalid_citation_syntax",
            "A factual sentence [s1].": "invalid_citation_syntax",
            "A factual sentence [S2].": "unknown_citation_id",
            "A factual sentence [S1]. Another unsupported sentence.": "insufficient_claim_citation_coverage",
        }
        for answer, reason in cases.items():
            with self.subTest(reason=reason), self.assertRaises(CitationFailure) as caught:
                validate(answer)
            self.assertEqual(caught.exception.reason, reason)

    def test_invalid_and_duplicate_citation_mappings_fail_closed(self):
        with self.assertRaises(CitationFailure) as caught:
            validate("Claim [S1].", citations(chunk_id=None))
        self.assertEqual(caught.exception.reason, "invalid_citation_mapping")
        with self.assertRaises(CitationFailure) as caught:
            validate("Claim [S1].", citations() + citations())
        self.assertEqual(caught.exception.reason, "invalid_citation_mapping")

    def test_valid_claim_preserves_claim_to_citation_mapping(self):
        result = validate("A factual sentence [S1].")
        self.assertEqual(result.citation_ids, ("S1",))
        self.assertEqual(result.claim_mappings[0]["claim_text"], "A factual sentence .")
        self.assertEqual(result.claim_mappings[0]["citation_ids"], ["S1"])
        self.assertEqual(result.citation_mapping[0]["chunk_id"], "chunk-1")


class ClaimConsistencyTests(unittest.TestCase):
    def test_q17_supported_contradiction_is_rejected(self):
        claims = [
            {"claim_id": "C1", "text": "Regular Python dictionaries iterate in arbitrary order", "citation_ids": ["S1"]},
            {"claim_id": "C2", "text": "Regular Python dictionaries preserve insertion order", "citation_ids": ["S2"]},
        ]
        verdicts = [ClaimVerdict("C1", "supported", ("S1",), (), claims[0]["text"], ("chunk-old",)),
                    ClaimVerdict("C2", "supported", ("S2",), (), claims[1]["text"], ("chunk-new",))]
        findings = analyze_claim_consistency(claims, verdicts, [])
        self.assertIn("contradictory_supported_claims", [row["reason_code"] for row in findings])

    def test_historical_support_requires_version_qualification(self):
        claim = {"claim_id": "C1", "text": "Regular Python dictionaries iterate in arbitrary order", "citation_ids": ["S1"]}
        verdict = ClaimVerdict("C1", "supported", ("S1",), (), claim["text"], ("old-chunk",))
        evidence = [{"citation_id": "S1", "chunk_id": "old-chunk", "relative_path": "whatsnew/3.1.html"}]
        findings = analyze_claim_consistency([claim], [verdict], evidence)
        self.assertEqual(findings[0]["reason_code"], "version_qualification_missing")
        self.assertEqual(findings[0]["evidence_ids"], ["old-chunk"])

    def test_qualified_historical_and_current_claims_are_not_contradictory(self):
        claims = [
            {"claim_id": "C1", "text": "Before Python 3.7, regular dictionaries did not guarantee insertion order", "citation_ids": ["S1"]},
            {"claim_id": "C2", "text": "Since Python 3.7, regular dictionaries preserve insertion order", "citation_ids": ["S2"]},
        ]
        verdicts = [ClaimVerdict(row["claim_id"], "supported", (row["citation_ids"][0],), (), row["text"], (row["claim_id"],)) for row in claims]
        self.assertEqual(analyze_claim_consistency(claims, verdicts, []), ())

    def test_unsupported_claim_is_not_reclassified_by_consistency_layer(self):
        claim = {"claim_id": "C1", "text": "Regular Python dictionaries iterate in arbitrary order", "citation_ids": ["S1"]}
        verdict = ClaimVerdict("C1", "unsupported", (), (), claim["text"], (), (), "no_entailing_evidence")
        self.assertEqual(analyze_claim_consistency([claim], [verdict], []), ())


class EvaluationArtifactTests(unittest.TestCase):
    def test_artifact_is_bounded_and_redacts_evidence_and_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "artifacts" / "evaluation.jsonl"
            store = EvaluationArtifactStore(path, temp, max_records=2, max_bytes=4096)
            for index in range(3):
                store.record_result(request_id=f"req-{index}", query=f"question {index}",
                    result=type("Result", (), {
                        "generation": type("Generation", (), {
                            "raw_generated_answer": f"claim [S1] {index}",
                            "parsed_claims": ({"claim_id": "C1", "claim_text": "claim", "citation_ids": ["S1"]},),
                            "parsed_citation_ids": ("S1",),
                            "citation_mapping": ({"citation_id": "S1", "chunk_id": "c1"},),
                            "claim_verdicts": (ClaimVerdict("C1", "supported", ("S1",), (), "claim", ("c1",)),),
                            "model_name": "local-test", "verification_model": "local-test",
                            "verification_context_window_tokens": 8192,
                            "verification_output_tokens": 1024,
                            "verification_safety_margin_tokens": 512,
                            "consistency_findings": (),
                        })(), "generation_error": None, "answer": "answer", "verification_status": "verified",
                        "diagnostics": {"citation_validation_status": "passed"},
                    })(), model_configuration={"model_name": "local-test", "api_token": "DO_NOT_STORE"})
            raw = path.read_text(encoding="utf-8")
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual([row["request_id"] for row in rows], ["req-1", "req-2"])
            self.assertNotIn("PRIVATE EVIDENCE MUST NOT BE STORED", raw)
            self.assertNotIn("DO_NOT_STORE", raw)
            self.assertLessEqual(len(path.read_bytes()), 4096)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_artifact_path_cannot_escape_project_root_or_follow_symlink(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ValueError):
                EvaluationArtifactStore(Path(outside) / "x.jsonl", temp)


if __name__ == "__main__":
    unittest.main()
