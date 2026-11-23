import json
from pathlib import Path
import tempfile
import unittest

from scripts.evaluate_answers import evaluate


class AnswerEvaluationTests(unittest.TestCase):
    def test_computes_human_review_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "answers.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in [
                {"query_id": "q1", "review_status": "complete", "correctness": "correct", "citation_support": "all_supported"},
                {"query_id": "q2", "review_status": "complete", "correctness": "abstained", "citation_support": "not_applicable"},
            ]), encoding="utf-8")
            result = evaluate(path)
        self.assertEqual(result["reviewed_answers"], 2)
        self.assertEqual(result["correct_rate"], 0.5)
        self.assertEqual(result["abstention_rate"], 0.5)

    def test_refuses_pending_or_invalid_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "answers.jsonl"
            path.write_text(json.dumps({"query_id": "q1", "review_status": "pending",
                "correctness": None, "citation_support": None}), encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluate(path)


if __name__ == "__main__":
    unittest.main()
