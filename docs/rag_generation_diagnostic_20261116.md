# Local RAG Answer Generation Diagnostic

Four questions were run through the read-only development path: dense retrieval, BM25, RRF, cross-encoder reranking, bounded context assembly, and local Ollama generation. The command required `--development-unreviewed`, and both the context and system prompt clearly marked the references as unreviewed. The production API remains unavailable for the current manifest.

All four answers generated, and every answer's citation IDs passed the generator's check against citations present in the assembled context. Median end-to-end latency was 5,766 ms; median generation time was 3,802 ms. One question about `asyncio.TaskGroup` failures abstained because its retrieved high-level API index passage did not explain failure semantics. That is a useful retrieval/context limitation surfaced by this run, not a measured answer-quality result.

The model's citation markers are syntactically validated only; no reviewer has judged factual correctness or whether each claim is supported by the cited chunk. The answers and reference metadata are in `evaluation/results/rag_generation_diagnostic_20261116.json`. Four pending answer-review rows are in `evaluation/answer_judgments_rag_generation_20261116.jsonl`.

After a reviewer completes every row with:

- `correctness`: `correct`, `partially_correct`, `incorrect`, or `abstained`;
- `citation_support`: `all_supported`, `partially_supported`, `unsupported`, or `not_applicable`;
- `review_status`: `complete`;

run:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_answers.py `
  --judgments evaluation\answer_judgments_rag_generation_20261116.jsonl `
  --output evaluation\results\rag_generation_metrics.json
```

The evaluator refuses missing or pending human labels. Do not treat this diagnostic as approval or production advice; source decisions remain unchanged.
