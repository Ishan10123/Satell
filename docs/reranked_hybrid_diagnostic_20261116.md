# Hybrid Retrieval and Reranking Diagnostic

This local read-only diagnostic compared dense retrieval, FTS5 BM25, reciprocal-rank fusion, and a local ONNX cross-encoder over 24 questions in 12 technical domains. Access used the explicitly gated `operator_authorized_unreviewed` development path. It did not change source decisions or Qdrant points, and is not available through the production API.

## Components

- Dense vectors: existing `rag_docs_v2` collection and local Ollama embeddings.
- Sparse retrieval: versioned local SQLite FTS5 artifact built from a read-only Qdrant scroll.
- Fusion: reciprocal-rank fusion, `k=60`, 30 candidates per retriever.
- Reranking: `cross-encoder/ms-marco-MiniLM-L2-v2`, pinned revision `f5f4b747a632df48bdc5572fc23e8fd991714edb`, Apache-2.0, CPU ONNX Runtime. The ONNX file is 31,268,615 bytes; its SHA-256 is checked before loading. The tokenizer file checksum is also checked.

## Observed results

- 24 of 24 questions returned candidates.
- Median reranker latency was 314.15 ms.
- Median total measured pipeline latency was 1,687.51 ms (embedding, dense, sparse, fusion, reranking); observed p95 was 1,845.41 ms. Cold embedding calls and local runtime variance make this diagnostic unsuitable as a service-level benchmark.
- The first FastAPI dependency-injection question ranked the `Dependencies` documentation chunk first after reranking. Its score was 5.50; the original RRF score remains separately available.
- The five returned results averaged 3.46 distinct documents per query. Several passages still came from the same document.

These are retrieval observations only. No human relevance labels exist yet, so no precision, recall, MRR, nDCG, or claim of improvement is reported. `evaluation/relevance_judgments_reranked_hybrid_20261116.jsonl` contains 24 pending label rows. A reviewer should mark each row `review_status: "complete"` and list relevant chunk IDs before running:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_retrieval.py `
  --results evaluation\results\reranked_hybrid_diagnostic_20261116.json `
  --judgments evaluation\relevance_judgments_reranked_hybrid_20261116.jsonl `
  --output evaluation\results\reranked_hybrid_metrics.json
```

The evaluator refuses pending, missing, or empty relevance labels. Metrics will be meaningful only after reviewing the candidate set; this first label template contains the top five displayed results per query.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\test_hybrid_retrieval.py `
  --questions-file evaluation\questions_dense_diagnostic_20261116.jsonl `
  --top-k 5 --candidate-top-k 30 --development-unreviewed --rerank --json `
  | Set-Content -Encoding utf8 evaluation\results\reranked_hybrid_diagnostic_20261116.json
```

The command is a read-only development diagnostic. It requires explicit `--development-unreviewed`; it does not call the generation model or alter the current index.
