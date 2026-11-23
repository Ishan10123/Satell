import json
from pathlib import Path
import tempfile
import unittest

from scripts.evaluate_retrieval import evaluate


class RetrievalEvaluationTests(unittest.TestCase):
    def test_computes_metrics_from_completed_human_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "results.json"
            judgments = root / "judgments.jsonl"
            results.write_text(json.dumps({"results": [{"query_id": "q001", "question": "q", "results": [
                {"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"},
            ]}]}), encoding="utf-8")
            judgments.write_text(json.dumps({"query_id": "q001", "review_status": "complete",
                "relevant_chunk_ids": ["c2", "c3"]}) + "\n", encoding="utf-8")
            report = evaluate(results, judgments, ks=(1, 3))
        self.assertEqual(report["query_count"], 1)
        self.assertAlmostEqual(report["metrics"]["3"]["recall"], 1.0)
        self.assertAlmostEqual(report["metrics"]["3"]["reciprocal_rank"], 0.5)

    def test_refuses_pending_or_unlabeled_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "results.json"
            judgments = root / "judgments.jsonl"
            results.write_text(json.dumps({"results": [{"query_id": "q001", "results": [{"chunk_id": "c1"}]}]}), encoding="utf-8")
            judgments.write_text(json.dumps({"query_id": "q001", "review_status": "pending", "relevant_chunk_ids": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluate(results, judgments)


if __name__ == "__main__":
    unittest.main()
