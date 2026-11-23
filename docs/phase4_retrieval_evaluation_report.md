# Phase 4 — Retrieval Evaluation

Date: 2026-11-19

## Method and active mode

Thirty identical prompts were run through retrieval-only comparisons against the existing live Qdrant collection, using local embeddings and the signed local academic demo authorization. Twenty-seven queries had expected source-topic labels; three adversarial/ambiguous prompts were unlabelled. These automated source characteristics are not human relevance judgments. Candidate top-k was 30 and final top-k 8. The live app remains `strategy=dense` with reranking disabled.

## Retrieval comparison

| Mode | Recall@8 source heuristic | Precision@8 source heuristic | MRR | nDCG@8 | p50 retrieval ms | p95 retrieval ms |
|---|---:|---:|---:|---:|---:|---:|
| dense | 0.981 | 0.883 | 1.000 | 1.000 | 198.7 | 485.0 |
| hybrid_rrf | 0.981 | 0.895 | 1.000 | 1.000 | 1589.6 | 2383.1 |
| hybrid_rerank | 1.000 | 0.870 | 0.963 | 0.973 | 3400.9 | 4013.3 |

Dense remains selected. Hybrid RRF did not improve recall and was slower; hybrid plus reranking had a small recall increase but lower precision/MRR/nDCG and much higher latency. No alternative was activated.

## Live query context

The final 30-query Django run recorded 240 retrieved candidate occurrences: 136 chunks admitted and 104 excluded by context limits. Per-query JSON includes all retrieved chunk/document/source IDs and scores, context chunk count, token estimate, exclusion reasons, and strategy. Context assembly completed without a service error; this does not mean all relevant evidence fit in the budget.

## Limitations

Expected relevance is source-topic heuristic, not document-level or human relevance. There is no statistical significance claim from 30 items. The ONNX reranker evaluation was offline/read-only and not active in the FastAPI container path. The unchanged configured context cap is 8,192 with an 1,024 output allowance and 512 safety reserve; its token estimate is conservative rather than exact Qwen tokenization.
