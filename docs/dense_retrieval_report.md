# Dense retrieval baseline

Run date: 2026-11-16  
Collection: `rag_docs_v2`  
Index: `index-20261116T044640Z-b53eb021`  
Access: operator-authorized unreviewed, read-only local diagnostic

## Implementation

The existing Ollama embedding provider and Qdrant store are reused. Dense retrieval now returns a typed `DenseRetrievalResult` with query, ranked `SearchHit` records, embedding latency, Qdrant latency, and total latency. Hits include their one-based retrieval rank. Qdrant search accepts a cosine score threshold and typed source/document/source-type filters. Any source filter intersects with the already authorized source scope; it cannot widen it.

Default `QdrantVectorStore.search` remains `license_review_status=approved`. A separate development method requires an explicit operator flag and a ready manifest whose authorization mode is exactly `operator_authorized_unreviewed`. It still filters tenant, principal ACL, and source IDs. It is not called by the API. The API now rejects a returned readiness manifest unless its authorization mode is `reviewed_source_and_document_approval`.

The diagnostic CLI is `scripts/test_dense_retrieval.py`. It validates the index and model/tokenizer compatibility before querying, maps document IDs back to paths through the local inventory, and can emit JSON. It does not write Qdrant. `configs/retrieval.json` owns the active dense top-k and query settings. API `top_k` now reaches the retrieval service instead of being ignored.

## Corpus diagnostic

The diagnostic ran 24 questions, two per domain across FastAPI, Python, PostgreSQL, Qdrant, Docker, Transformers, PyTorch, machine learning, information retrieval, RAG, LLMs, and vector databases. It requested five results per question. Every query returned five hits. Questions and full previews/results are in [`evaluation/results/dense_diagnostic_20261116.json`](../evaluation/results/dense_diagnostic_20261116.json); the question set is [`evaluation/questions_dense_diagnostic_20261116.jsonl`](../evaluation/questions_dense_diagnostic_20261116.jsonl).

This is an unlabeled diagnostic, not a relevance evaluation. No Recall@k, Precision@k, MRR, nDCG, or correctness percentage is claimed. The questions have no human-verified relevance labels.

### Timing

| Measurement | Median | Min | Max |
|---|---:|---:|---:|
| Query embedding | 39.12 ms | 16.42 ms | 107.51 ms |
| Qdrant retrieval | 27.39 ms | 11.70 ms | 95.46 ms |
| Dense pipeline total | 69.26 ms | 39.03 ms | 158.88 ms |

A separate first query after a cold process/model startup took approximately 13.94 seconds for embedding and 0.31 seconds for Qdrant. That single cold observation is not a stable cold-start benchmark. Twenty-four warm samples are insufficient for a robust p95 claim, so p95 is omitted. Generation was not part of these measurements.

### Manual observations

- FastAPI dependency-injection questions returned the FastAPI dependencies guide in the top result; OAuth2 scopes returned the FastAPI security tools documentation.
- Both Python questions returned Python 3.13 asyncio documentation. PostgreSQL questions returned its concurrency-control and performance chapters.
- Qdrant filter and HNSW questions returned matching Qdrant documentation. Docker multi-stage and health-check questions returned the corresponding Docker pages.
- Transformers pipeline and chat-template questions, and PyTorch autograd and DataLoader questions, returned matching source documentation.
- BM25 and RRF questions returned Qdrant full-text/hybrid search documentation. RAG questions returned Qdrant GraphRAG and pipeline-evaluation pages, which are related but do not establish general RAG answer quality.
- The overfitting/regularization question returned a Qdrant sparse-embedding passage, and both LLM questions returned Docker model configuration material. These are weaker or likely wrong-source top results and should be included in the human-labeled evaluation set.
- Fourteen of the 24 top-five lists contained repeated chunks from the same document; the mean number of distinct documents in the top five was 3.83. This is a retrieval-diversity observation, not a relevance score. Consider document-level diversification or MMR only after human relevance labels exist.

## Authorization and data safety

The run required `--development-unreviewed`, reported that access mode in the output, used only the loopback Qdrant and Ollama clients, and passed the manifest/point-count validation first. It did not call `ensure_collection`, upsert, delete, create indexes, change manifests, or alter source/document approval registries. Production API calls remain blocked on the current unreviewed manifest.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\test_dense_retrieval.py --question "How does FastAPI dependency injection work?" --top-k 5 --development-unreviewed
.\.venv\Scripts\python.exe scripts\test_dense_retrieval.py --question "How does FastAPI dependency injection work?" --top-k 5 --development-unreviewed --json
.\.venv\Scripts\python.exe scripts\test_dense_retrieval.py --questions-file evaluation\questions_dense_diagnostic_20261116.jsonl --top-k 5 --development-unreviewed --json
```

## Remaining dense work

Human relevance judgments are required before tuning thresholds or describing quality. Query embedding cold-start and warm latency should be benchmarked over a longer run. The diagnostic exposes local paths for operator review; those remain absent from Qdrant payloads and API responses. Dense search is implemented and executed, but this phase does not complete sparse, hybrid, reranking, generation evaluation, or API end-to-end work.
