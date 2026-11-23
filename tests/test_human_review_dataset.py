import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_human_review_dataset import validate_jsonl, validate_record


def record(**overrides):
    value = {
        "record_version": "1.0", "dataset_version": "test-v1", "query_id": "Q-1",
        "question": "What does the documentation say?", "intent": "direct",
        "relevant_document_ids": [], "relevant_chunk_ids": [],
        "expected_answer_concepts": [], "required_evidence": [],
        "expected_abstention": None, "source_versions": [],
        "review_status": "unreviewed", "label_origin": "unreviewed",
        "reviewer_id": None, "reviewed_at": None, "confidence": None,
    }
    value.update(overrides)
    return value


class HumanReviewDatasetTests(unittest.TestCase):
    def test_unreviewed_record_is_valid_but_not_counted_as_human_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.jsonl"
            path.write_text(json.dumps(record()) + "\n", encoding="utf-8")
            result = validate_jsonl(path)
        self.assertEqual(result, {"records": 1, "human_reviewed": 0, "unreviewed": 1,
                                  "label_quality": "mixed_or_unreviewed"})

    def test_human_review_requires_reviewer_timestamp_and_confidence(self):
        reviewed = record(review_status="human_reviewed", label_origin="human",
                          expected_abstention=False, reviewer_id="reviewer-1",
                          reviewed_at="2026-11-20T12:00:00+05:30", confidence=0.9)
        self.assertEqual(validate_record(reviewed), reviewed)
        reviewed["reviewer_id"] = None
        with self.assertRaisesRegex(ValueError, "reviewer_id"):
            validate_record(reviewed)

    def test_duplicate_query_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.jsonl"
            row = json.dumps(record())
            path.write_text(row + "\n" + row + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                validate_jsonl(path)

    def test_unknown_fields_and_oversized_question_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "unexpected"):
            validate_record(record(secret="no"))
        with self.assertRaisesRegex(ValueError, "5,000"):
            validate_record(record(question="x" * 5001))

    def test_template_placeholder_cannot_be_counted_as_a_dataset_record(self):
        with self.assertRaisesRegex(ValueError, "placeholder"):
            validate_record(record(query_id="REPLACE_ME"))

    def test_unreviewed_heuristic_cannot_claim_reviewer_or_confidence(self):
        with self.assertRaisesRegex(ValueError, "cannot claim"):
            validate_record(record(label_origin="heuristic", confidence=0.99))

    def test_human_review_timestamp_must_include_timezone(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_record(record(review_status="human_reviewed", label_origin="human",
                expected_abstention=True, reviewer_id="r1", reviewed_at="2026-11-20T12:00:00",
                confidence=0.5))


if __name__ == "__main__":
    unittest.main()
