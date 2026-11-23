# Retrieval implementation progress

Updated: 2026-11-16

## Implemented

- Dense Qdrant retrieval with rank, timing, scoped filters, threshold support, effective API `top_k`, and a read-only diagnostic CLI.
- Explicitly isolated development retrieval for the ready `operator_authorized_unreviewed` manifest. This remains available only to local diagnostics with an explicit operator flag; the production API rejects that manifest.
- Versioned, checksum-bound SQLite FTS5 BM25 snapshot built from a read-only scroll of the existing dense collection.
- Dense + BM25 reciprocal-rank fusion with component score/rank provenance.
- Local CPU ONNX cross-encoder reranking with pinned model/tokenizer hashes and bounded candidate/token lengths.
- Server-configured `dense`, `hybrid`, and `hybrid_rerank` service strategies. Clients cannot choose access scope or retrieval mode.
- Context assembly remains tenant, source, ACL, and license checked; document-level rejections are applied as deny filters. arXiv sources require separately evidence-validated per-paper approvals at the API boundary.
- Stage timing response fields for embedding, dense, sparse, fusion, reranking, context assembly, and generation.
- ASGI integration test with real in-memory Qdrant retrieval, evidence-validated synthetic source approval, citation mapping, timing response, and document-rejection blocking.
- 24-question technical diagnostic, pending human relevance-label template, and evaluator for Precision/Recall/MRR/nDCG that refuses incomplete labels.
- Four-question local RAG generation diagnostic with unreviewed-mode system/context notices, answer/citation review template, and a strict human-label evaluator.

## Diagnostic status

The 24-question local corpus diagnostic is unlabeled. It verifies operation and exposes candidate examples, not relevance quality. Median total measured latency in the recorded run was 1,687.51 ms, with 1,845.41 ms observed p95; cold and warm local-model timing differences make these figures directional only. No human quality metric is claimed. The collection had 58,856 points during validation and remained unreviewed.

## Remaining prerequisites

1. Have a human review the 24 rows in `evaluation/relevance_judgments_reranked_hybrid_20261116.jsonl`, identify relevant chunk IDs, and mark reviewed rows complete. Then compare dense, BM25, hybrid, and reranked results against the same judgments.
2. Complete evidence-backed source reviews and per-paper arXiv document decisions. No approvals have been created automatically.
3. Build a reviewed index only after the decisions are complete; the current API intentionally returns 503 for the current unreviewed manifest.
4. Evaluate answer support, citation correctness, abstention behavior, and prompt-injection resistance on a human-reviewed question set. The current generation smoke test is synthetic.
5. Run a live loopback API integration against an approved index or an isolated approved test fixture. Current API integration runs through ASGI with real in-memory Qdrant, mocked embeddings, and mocked generation. The separate local RAG smoke uses real Ollama with in-memory Qdrant; the corpus generation diagnostic used real local retrieval and Ollama but remains explicitly unreviewed.

## Validation

The current verification run passed 171 automated tests, `compileall`, `pip check`, index validation, and the synthetic Ollama/Qdrant smoke test. The current Qdrant manifest remains `rag_docs_v2`, 6,565 documents, 58,856 points, authorization mode `operator_authorized_unreviewed`. No approval registry, raw corpus file, persistent Qdrant point, collection, or volume was modified for retrieval development.
