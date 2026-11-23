# Local API

The first API is a single-user local service. It listens on `127.0.0.1`, authenticates every query with a high-entropy bearer token, and derives its tenant and principal from server environment settings. Query clients cannot set tenant, principal, or source scope. The source approval registry is reloaded for every query so a source revocation takes effect without restarting the API. The service reads no prompt or document text into application logs.

This local token is not an identity provider and does not support multiple user identities. Keep the API on loopback. Remote or multi-user access requires TLS and an issuer-backed identity integration before binding to any non-loopback address. Source approvals and document rejections are reloaded for every query. arXiv sources require an individually approved, evidence-valid document record; approving arXiv source metadata alone does not expose any paper.

## Start

The API validates local model, tokenizer, and connection configuration at startup, but does not contact model servers or create an index during startup. It can start before indexing so `/health` and diagnostics remain available. `/ready` and every retrieval request validate the versioned index manifest against the embedding model, tokenizer, chunking configuration, and Qdrant collection. Retrieval returns HTTP 503 while the index is absent, building, failed, or incompatible.

In PowerShell, generate a token into the current process environment and supply the trusted identity and the exact collection configuration used by indexing:

```powershell
$env:RAG_API_TOKEN = (& .venv\Scripts\python.exe scripts\generate_api_token.py).Trim()
$env:RAG_TENANT_ID = "local"
$env:RAG_PRINCIPAL_ID = "local-admin"
# Defaults match the ragctl indexing configuration.
$env:RAG_QDRANT_COLLECTION = "rag_docs_v2"
$env:RAG_CHUNKING_VERSION = "1.2"
.\.venv\Scripts\python.exe scripts\run_api.py
```

The current `rag_docs_v2` corpus was ingested in `operator_authorized_unreviewed` mode. The API rejects the index manifest before retrieval unless its authorization mode is `reviewed_source_and_document_approval`, then filters by approved source IDs, tenant, ACL, license status, and document decisions. It will not return this development corpus. Use the explicitly gated local diagnostic CLI or synthetic smoke test until evidence-backed review and a reviewed-index build are complete.

## Synthetic retrieval smoke test

To exercise local retrieval and generation without reading the corpus or changing persistent Qdrant collections, run the smoke test without `--live-qdrant`:

```powershell
.\.venv\Scripts\python.exe scripts/run_synthetic_rag_smoke.py
```

This uses synthetic approved passages and an in-memory Qdrant client. It validates the local retrieval/generation path, not corpus-specific relevance or answer quality.

Keep the token out of source control and logs. The server binds to `127.0.0.1:8000`; no reload mode or public binding is enabled. With no ready index, `/health` returns 200 and `/v1/query` returns 503.

## Endpoints

- `GET /health`: unauthenticated liveness response with no dependency details.
- `GET /ready`: bearer-authenticated check of local Ollama models and the managed Qdrant index.
- `POST /v1/query`: bearer-authenticated retrieval and answer generation. JSON body fields are only `query` and optional `top_k` (1–20). The strategy is server-configured in `configs/retrieval.json`; clients cannot select a retrieval mode or authorization scope. Responses include stage timings and the configured mode.

Example query body:

```json
{"query":"How does this source describe its installation process?","top_k":6}
```

`RAG_API_TOKEN`, `RAG_TENANT_ID`, and `RAG_PRINCIPAL_ID` are required. `RAG_QDRANT_COLLECTION` defaults to `rag_docs_v2`; `RAG_CHUNKING_VERSION` defaults to `1.2`. `RAG_API_PORT` defaults to `8000`; `RAG_QDRANT_URL` defaults to `http://127.0.0.1:6333` and must remain loopback.

To use `hybrid`, first build the sparse artifact for the ready manifest, then set `strategy` to `hybrid` in `configs/retrieval.json`. To use `hybrid_rerank`, set that strategy and `reranker.enabled` to `true`; the pinned ONNX model and CPU runtime are local. All modes retain the same production manifest and approval checks.
