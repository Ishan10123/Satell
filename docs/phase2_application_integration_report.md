# Phase 2 Application Integration Report

**Run date:** 2026-11-18  
**Result:** Local end-to-end integration verified for this evaluation run. This is not a production-readiness certification.

## Request path actually exercised

The evaluation submitted each message through Django's authenticated `conversations:message_create` view. The configured adapter was `RAG_ADAPTER=http` with `RAG_API_BASE_URL=http://rag-api:8000`; the browser-facing Django service stayed loopback-bound at `127.0.0.1:8001`. Django sent a server-side bearer credential and correlation ID to FastAPI. FastAPI used the local academic demo signed registries to construct scope, then the configured dense retriever queried Qdrant, `ContextAssembler` rechecked authorization and assembled evidence, and Ollama generated and verified claims. Django stored the response, diagnostics, verification status and citation snapshots in PostgreSQL.

The exercised route is `django_app/chat/views.py::message_create` → `django_app/rag_client/client.py::FastAPIRAGClient.query` → `src/rag_pipeline/api/app.py::create_app` `/v1/query` → `src/rag_pipeline/service.py::LocalRAGService.answer` → `src/rag_pipeline/retrieval/dense.py::DenseRetriever.retrieve_detailed` → Qdrant → `src/rag_pipeline/retrieval/context.py::ContextAssembler.assemble` → `src/rag_pipeline/generation/ollama.py::OllamaGenerator.generate` and `LocalClaimVerifier` → Django persistence.

## Runtime evidence

- `rag-api` and `django` containers were rebuilt from the changed app images and restarted with `up -d --no-deps`; PostgreSQL and Qdrant were not recreated.
- FastAPI `/health`: HTTP 200. Authenticated `/ready`: HTTP 200. Ollama tags and Qdrant collection API both returned HTTP 200 from the FastAPI container.
- Eight requests traversed the real Django view and real FastAPI HTTP client. The final evaluation stored eight user/assistant pairs in a dedicated PostgreSQL conversation. Five produced citation-bearing answers; two failed answer validation and one comparison safely abstained.
- The FastAPI response and Django client agreed on the response schema, including retrieval IDs/scores, stage timings, citation metadata, verification status and bounded diagnostics.
- No browser automation was run for this evaluation. The application was invoked through Django's test client inside the running container.

## Confirmed integration defect fixed

`django_app/rag_client/client.py::_parse_response` capped diagnostics at 16 fields. A successful FastAPI response contained 17 fields, including retrieval, generation and verifier metrics. Django consequently marked valid upstream responses as `rag_client_error`. The bound is now 24, with tests covering the full diagnostic payload and invalid error-header values. The server sends only constrained error code/stage labels in headers; it does not send internal exception text.

## Active retrieval configuration

`configs/retrieval.json` selects `dense`. `reranker.enabled` is false. Although BM25 and RRF implementations exist, the live API does not use them. A read-only comparison with the existing FTS5 index showed 2.75–4.34 seconds for hybrid retrieval versus approximately 0.09–0.21 seconds for dense retrieval. Hybrid did not consistently improve rankings, so it was not enabled. The current API image also excludes `knowledge_base/processed/sparse_indexes` through `.dockerignore`/`Dockerfile.rag-api`; hybrid cannot be deployed in that image without a separate, reviewed packaging change.

Context assembly is active. The evidence allowance increased from 2,500 to 5,000 conservative UTF-8-byte tokens, still bounded by `OllamaGenerator.context_budget_for` against the configured 8,192 context, 1,024 output reservation and 512 safety margin. The comparison per-document allowance increased from 600 to 2,500. These changes do not alter the model context or output limit.

## Persistence and limitations

The normal Django message path persisted final answers, citation snapshots and generation metadata. Failed validation results persisted a safe abstention and failure code. The overall latency remains material: successful generation plus verification took about 5.4–8.5 seconds in this eight-question sample. This is local development evidence only; it does not establish production capacity, browser behavior, multi-user isolation under load, or long-run Ollama/Qdrant reliability.

Full per-question request and response evidence (including all retrieved IDs and scores) is in [phase2_rag_evaluation_results.json](phase2_rag_evaluation_results.json). The baseline capture is [phase2_rag_evaluation_baseline.json](phase2_rag_evaluation_baseline.json).
