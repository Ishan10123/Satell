# Backend Django Integration Readiness Audit

**Audit date:** 2026-11-17  
**Project:** `E:\RAG_Project`  
**Scope:** Read-only architecture audit. This report was the only project file created or changed for this task. No source code, tests, index artifacts, approvals, Qdrant data, or raw documents were changed.

## Executive assessment

The repository has a modular, local development RAG pipeline and one small FastAPI query interface. Retrieval, context assembly, local Ollama generation, citation checking, and claim-level verification are separate components behind `LocalRAGService.answer`. The API is useful as a local single-user integration seam, but it is not yet a stable multi-user chat backend: it has no conversation model or persistence, user identity is one server-configured principal behind one shared bearer token, no streaming, and no cancellation contract.

**Production use is blocked.** The current `rag_docs_v2` readiness manifest is `ready` but its authorization mode is `operator_authorized_unreviewed` (6,565 documents, 58,856 chunks). `create_app.check_index` requires `reviewed_source_and_document_approval`, and the API checks this before every query and at readiness. The report does not recommend bypassing that gate.

The most appropriate Django boundary is an authenticated, versioned HTTP API in a separately managed RAG process, once its identity boundary is upgraded. Direct imports of `LocalRAGService` would couple Django to local model clients, Qdrant, artifacts, and approval registries, and would share sync/blocking resource lifetimes with web workers.

## 1. Current architecture and actual request flow

### Components

- **HTTP application:** `src/rag_pipeline/api/app.py:create_app` exposes the FastAPI app and request handlers.
- **Process composition:** `scripts/run_api.py:main` loads JSON settings, creates the Ollama embedding and generation clients, Qdrant store, optional BM25/reranker, `LocalRAGService`, and API. It binds Uvicorn to `127.0.0.1` with access logging disabled.
- **Application service:** `src/rag_pipeline/service.py:LocalRAGService.answer` coordinates retrieval, context, generation, and final citation selection.
- **Dense retrieval:** `src/rag_pipeline/retrieval/dense.py:DenseRetriever.retrieve_detailed` embeds the query and calls Qdrant.
- **Sparse/hybrid retrieval:** `src/rag_pipeline/retrieval/sparse.py:BM25Retriever.search`; `src/rag_pipeline/retrieval/hybrid.py:HybridRetriever.retrieve` and `reciprocal_rank_fusion` combine candidate rankings. This route is conditional on `configs/retrieval.json` selecting a hybrid strategy.
- **Reranking:** `src/rag_pipeline/retrieval/rerank.py:LocalCrossEncoderReranker.rerank`, enabled only for `hybrid_rerank` with the configured local artifact.
- **Context and citations:** `src/rag_pipeline/retrieval/context.py:ContextAssembler.assemble` rechecks tenant, source, approval status and ACL; caps context; creates citation IDs and strips unsafe source URL components.
- **Generation and verification:** `src/rag_pipeline/generation/ollama.py:OllamaGenerator.generate` makes a non-streaming local Ollama chat request, validates citation IDs and per-claim citation presence, then invokes `src/rag_pipeline/generation/claim_verifier.py:LocalClaimVerifier.verify`. The verifier validates structured verdicts against the supplied claim/evidence IDs. Only claims returned as supported are rendered; otherwise the service abstains or omits the claim.
- **Dense persistence:** `src/rag_pipeline/storage/qdrant_store.py:QdrantVectorStore` performs scoped vector searches against Qdrant. `src/rag_pipeline/storage/index_manifest.py:validate_index_manifest` validates the managed index and compatibility.
- **Sparse persistence:** `src/rag_pipeline/retrieval/sparse.py` opens an index-specific SQLite artifact in read-only URI mode for BM25 queries.
- **Conversation persistence:** no conversation, message, session, or chat-history persistence implementation exists in `src/rag_pipeline`.

### Incoming request call path

`POST /v1/query` → `request_boundary` assigns a request ID and checks the declared body length → FastAPI/Pydantic validates `QueryRequest` → `authenticate` checks the bearer token → `check_index` validates the managed index and rejects unreviewed authorization mode → process-local IP rate limit → `build_scope` reloads evidence-backed source approvals → `document_policy` reloads document decisions and derives arXiv allow/deny sets → `LocalRAGService.answer` → configured retrieval strategy → `ContextAssembler.assemble` → `OllamaGenerator.generate` → local claim verifier → verified response/citations/timings.

For the current `configs/retrieval.json`, `strategy` is **`dense`** and `reranker.enabled` is false. Thus BM25, RRF, and reranking are implemented as selectable capabilities but are not active in the current API composition. They must not be described as currently used by the endpoint.

### Authorization behavior

`QdrantVectorStore._search` pushes tenant, source, license-review status and ACL filters into Qdrant, plus document exclusions and restricted-source/permitted-document conditions. `ContextAssembler._authorized` independently checks tenant, allowed source, license-review state and principal ACL before building a prompt. The API reloads source and document approvals per query. It fails closed when approval data is malformed. arXiv documents require an individually approved document record. This boundary is intentionally incompatible with the current unreviewed index.

## 2. Existing API and callable interfaces

Defined routes in `src/rag_pipeline/api/app.py:create_app`:

| Method/path | Authentication | Actual behavior |
|---|---|---|
| `GET /health` | None | Liveness only; returns `{ "status": "ok" }`, with no dependency checks. |
| `GET /ready` | Bearer token | Checks reviewed index, embedding model, Qdrant, and generation model. Returns `{ "ready": true }` or generic 503. |
| `POST /v1/query` | Bearer token | One-shot query and answer. Returns answer, citations, request ID, retrieval mode, and stage timings. |

OpenAPI, Swagger, and ReDoc routes are disabled. There are no conversation, message, history, citation-detail, or streaming endpoints.

The internal Python seam is `LocalRAGService.answer(query, scope, limit, excluded_document_ids, restricted_source_ids, permitted_document_ids) -> RAGAnswer`. It is synchronous and expects callers to create a trusted `AccessScope`; it is not itself a tenant-authenticated Django contract. `scripts/run_api.py` is the actual production-style composition entry point.

**Classification:** endpoints and Python service boundary — **Implemented and verified** by code and API/integration tests. Multi-user boundary and chat endpoints — **Not implemented**. Current production use — **Blocked by source authorization or external review**.

## 3. Actual request and response schemas

The API uses Pydantic v2 models in `src/rag_pipeline/api/app.py`:

```json
{
  "query": "non-empty string, maximum 2000 characters",
  "top_k": "integer, default 8, range 1 through 20"
}
```

`extra="forbid"`; clients cannot submit tenant, principal, source IDs, retrieval strategy, or approval scope. Middleware also requires `Content-Length` for this POST and limits declared body size to 8,192 bytes by default. A generic 422 is returned without echoing Pydantic input errors.

Response model:

```json
{
  "answer": "string",
  "citations": [
    {
      "citation_id": "S1",
      "source_id": "...",
      "document_id": "...",
      "chunk_id": "...",
      "title": "...",
      "page_references": [],
      "section": "string or null",
      "source_reference": "public HTTP(S) URL or null"
    }
  ],
  "request_id": "string",
  "retrieval_mode": "dense, hybrid, or hybrid_rerank",
  "timings_ms": {"stage": 0.0}
}
```

`QueryResponse` does not include a conversation ID, message ID, model version, verifier summary, refusal category, or durable citation object. The internal context carries evidence text, but `LocalRAGService.answer` returns only citation metadata to the API; evidence text and prompts are not part of the HTTP response.

**Classification:** query schema and structured citation metadata — **Implemented and verified**. Stable versioned chat schemas, standard error schema, and pagination — **Not implemented**.

## 4. Streaming and cancellation

No streaming route or generator interface exists. `OllamaGenerator.generate` sends `"stream": false`; `LocalClaimVerifier.verify` also sends `"stream": false`. The API waits for a complete model answer and its claim-verification pass before returning.

FastAPI routes that perform work are synchronous `def` handlers, so FastAPI runs them in its worker thread pool. There is no propagation of an HTTP disconnect/cancellation signal into embedding, Qdrant, Ollama, or claim verification. Configured component timeouts bound individual HTTP calls (embedding 60 seconds, generation/verifier 120 seconds, Qdrant 5 seconds), but there is no end-to-end request deadline. Retries may extend elapsed time.

Because claims are verified only after generation, directly exposing raw model tokens would send unverified text before the final verifier can reject it. If incremental UI updates are required, initially stream progress/status events and emit answer text only after complete verification. Verified answer text may then be emitted in chunks, but that is post-verification delivery rather than incremental model generation.

**Classification:** bounded component calls — **Implemented and verified**. Genuine incremental streaming, request cancellation, and unified deadline — **Not implemented**.

## 5. Citation and verification structure

`ContextAssembler.assemble` assigns request-local citation IDs (`S1`, `S2`, …), tied to an authorized chunk and its source/document metadata. `OllamaGenerator.generate` rejects unknown citation IDs and factual claims missing citations. It extracts claims and sends claims plus evidence to `LocalClaimVerifier.verify`, which constrains the model response with a JSON schema and validates exact claim IDs, verdict statuses, and citation IDs in ordinary Python. Unsupported/contradicted claims are excluded; no supported claims yields abstention. Citation validation failures yield a safe abstention in `LocalRAGService.answer`; verifier/network failures are propagated as typed errors and become generic API 503s.

This is a meaningful local grounding safeguard, but the semantic entailment verdict is itself generated by the same configured local model. Structural validation proves response shape and ID binding, not semantic correctness. It should be evaluated as a probabilistic verifier, not a formal proof or guarantee against hallucinations. The existing synthetic smoke test and unit tests do not establish corpus-wide claim precision/recall or production answer quality.

Citation metadata returned is structured and useful for a UI, but there is no stable citation lookup endpoint or immutable persisted citation snapshot. `source_reference` is sanitized to remove query strings/fragments; local filesystem paths are not included.

**Classification:** claim/citation pipeline — **Implemented and verified** in unit/synthetic integration tests. Semantic verifier quality — **Implemented but insufficiently tested** on approved real corpus. Durable citation/history references — **Not implemented**.

## 6. Authentication, authorization, and security assessment

### Implemented protections

- `security/api_auth.py:validate_api_token` uses constant-time comparison. `create_app` requires a token of at least 32 characters.
- Server configuration supplies one `tenant_id` and one `principal_id`; request models forbid client-controlled scope.
- `ApiRateLimiter.allow` limits by client IP, in-process, with a lock and monotonic-time window.
- Request body/query length, top-k, and unexpected fields are bounded.
- Generic validation, index, dependency and unexpected-error responses avoid returning raw exception details.
- FastAPI access logging is disabled in `scripts/run_api.py`; docs say application code does not log prompt/document text.
- Retrieval applies tenant, ACL, source-approval, license status and document rejection filters in Qdrant and repeats authorization checks at context assembly.
- Document-level rejection is included as a Qdrant deny filter; source approval alone does not allow arXiv papers.
- Retrieved passages are explicitly framed as untrusted; generation prompts tell the model not to follow passage instructions.
- Ollama and Qdrant addresses are validated as loopback-only by their respective clients; reranker loads pinned local files and checks hashes.
- Current index manifest remains `operator_authorized_unreviewed`; production API rejects it. No code path in this API changes the manifest or approval state.

### Gaps and limits

- The bearer token is a shared service secret, not user authentication. `tenant_id` and `principal_id` are static per process; there is no issuer validation, token rotation lifecycle, per-user identity, or per-conversation ownership check. A Django deployment must not pass through untrusted user-supplied scope.
- IP-based throttling is not identity-based, resets on process restart, is not coordinated across workers/replicas, and keeps per-IP queues in memory. It does not impose a global inference concurrency cap.
- There are no user-level conversation boundaries because conversations do not exist yet.
- Prompt-injection defenses are prompt framing and HTML escaping, not a deterministic sanitizer or isolation mechanism. Retrieved text can still influence model behavior; claim verification mitigates but does not eliminate this risk.
- The claim verifier shares the generation model/runtime and is not an independent trusted oracle.
- No application-level metrics exporter, tracing, or structured operational event stream was found. Timings are returned in response bodies; there is no authenticated/admin metric surface.
- No Dockerfile, Compose file, or service deployment file was found outside data assets. Current loopback-only design is suitable for local development, not direct Django-to-RAG communication across hosts. Exposing it requires deliberate TLS/network/auth changes.

**Classification:** local token auth, server-derived scope, request validation, generic errors and retrieval ACL checks — **Implemented and verified**. Prompt injection defenses — **Partially implemented**. Multi-user auth/isolation, distributed abuse controls and production network identity — **Not implemented**. Production use of current corpus — **Blocked by source authorization or external review**.

## 7. Conversation persistence and model configuration

No conversation/message/session database or history assembly is present. `LocalRAGService.answer` takes only the current query; prior turns do not reach retrieval or generation. Qdrant stores document chunks/vectors and metadata; SQLite stores sparse-index data; JSON/JSONL files hold ingestion, manifest and approval state. None of these are chat-history stores.

Model and retrieval choices are server configuration, not client request fields:

- `configs/embedding.json`: local Ollama embedding model, pinned digest, 768 dimensions, batch/input limits and 60-second configured timeout.
- `configs/generation.json`: local Ollama Qwen model, pinned digest, 4,096 context, 512 output tokens, deterministic temperature, 120-second timeout and one retry. Its status says synthetic generation was verified and production answer quality/latency are unbenchmarked.
- `configs/retrieval.json`: currently dense; BM25/RRF/rerank parameters are configured but inactive under the current strategy.
- `configs/indexing.json`: managed `rag_docs_v2`, loopback Qdrant and chunking version.
- `scripts/run_api.py:required_environment` loads bearer token, tenant and principal from environment; port and Qdrant settings can be overridden by environment.

There is no managed secret store or token rotation facility. Docs instruct operators to keep the token out of source control and logs.

**Classification:** local pinned model configuration — **Implemented and verified**. Conversation persistence/context — **Not implemented**. User-scoped retention/deletion policy — **Not implemented**.

## 8. Concurrency and resource management

`create_app.lifespan` closes `LocalRAGService` on shutdown. `LocalRAGService.close` closes the shared embedding, vector-store, generation clients and sparse retriever when configured. HTTP clients are synchronous `httpx.Client` instances, and Qdrant has a configured 5-second timeout. The SQLite BM25 handle is opened with `check_same_thread=False` in read-only mode. Default Uvicorn invocation has no multiple workers configured.

This supports a local development process but is not an explicit production concurrency design. Synchronous inference can occupy FastAPI thread-pool workers for up to long component timeouts. No semaphore, admission queue, backpressure policy, request-wide deadline, GPU/model batching policy, per-model parallelism cap, graceful cancellation of in-flight work, or load test was found. Multiple threads may share the same provider clients and sparse SQLite connection; the tests reviewed do not establish safe high-concurrency behavior. If multiple Uvicorn workers are introduced, each process would duplicate model/client resources and its own in-memory rate limiter.

**Classification:** lifespan cleanup and component timeouts — **Implemented and verified** by code. Controlled inference concurrency and high-load resource behavior — **Not implemented / insufficiently tested**.

## 9. Error handling and observability

Generation and verifier errors have typed subclasses in `src/rag_pipeline/generation/errors.py`. Ollama and verifier distinguish timeouts, connection failures, HTTP failures, malformed responses, truncation, invalid verdicts and verifier input budget errors. The API maps invalid queries to generic 400, auth to 401, rate limit to 429, and authorization/index/dependency failures to generic 503. A request ID is generated and returned in both the response body and `X-Request-ID` header. The service returns stage timings; generator/verifier collect operational counters such as retries, status, token estimates and durations, but the public API exposes only stage timing dicts.

There is no common response envelope for errors: most errors have `{detail: ...}`, while request validation includes `{detail, request_id}`. Errors do not consistently include a documented machine-readable code, retryability flag, or support correlation ID in JSON. The query handler catches broad exceptions and hides details, which protects information but leaves no obvious safe internal logging/diagnostic path. No metrics backend or tracing integration was found. Health is liveness only; readiness is authenticated and probes model plus Qdrant, but there is no differentiated dependency state.

**Classification:** typed dependency errors, generic API mapping and request correlation — **Implemented and verified**. Operational telemetry, standardized error schema and dependency-specific readiness reporting — **Partially implemented / not implemented**.

## 10. Operational readiness

- **Startup:** `scripts/run_api.py:main` validates required environment values, loads settings/artifacts and constructs local clients. Per `docs/local_api.md`, it does not contact Ollama or create a Qdrant collection during startup. Client health is checked through `/ready` and before first embedding/generation use.
- **Shutdown:** FastAPI lifespan closes service-owned resources.
- **Liveness:** `/health` only confirms the process responds.
- **Readiness:** authenticated `/ready` validates the reviewed manifest plus configured embedding model, Qdrant collection and generation model. Every query revalidates the index manifest.
- **Failure behavior:** dependency and readiness failures return generic 503; retrieval/generation paths fail closed rather than returning unverified answer text.
- **Timeouts:** component-specific HTTP timeouts exist; there is no global deadline or queue wait limit.
- **Logs/metrics:** API access logs disabled; code/docs avoid query-content logging; no metrics exporter/tracing found. Timing data is returned to callers only.
- **Deployment:** loopback bind, local HTTP dependencies, no checked-in Docker/Compose/service deployment definitions. There is no evidence of TLS, remote secret management, backup/restore, process supervision, or production scaling configuration.
- **Quality status:** embedding and generation config note local/synthetic verification, while corpus-specific relevance, latency and approved-source answer quality are not benchmarked. A synthetic smoke test validates component wiring, not production behavior.

**Classification:** local startup, liveness/readiness, shutdown, timeout configuration and generic recovery — **Implemented and verified** at source level. Production deployment/observability/scaling/backup — **Not implemented**. Corpus-level production readiness — **Blocked by source authorization or external review** and quality evaluation.

## 11. Existing test coverage reviewed

Relevant tests include `tests/test_api.py`, `tests/test_api_rag_integration.py`, `tests/test_qdrant_store.py`, and `tests/test_claim_verifier.py`. They cover authentication, request scope restrictions, body size, rate limits, approval reload/revocation, document rejection, fail-closed index state, request IDs, query response path, Qdrant tenant/ACL filters, arXiv per-document gating, verifier schema/ID failures, and sanitized diagnostics. The synthetic integration tests exercise retrieval through response citation/timing and verify that document rejection prevents generation.

The reviewed tests do not establish multi-user identity isolation, persisted conversations, history truncation/ownership, real incremental streaming, cancellation/disconnect handling, multi-worker limiter semantics, concurrent inference/resource limits, production load, or real-corpus semantic answer quality. No tests were run for this read-only audit; test source was inspected only.

## 12. Django integration recommendation

### Boundary choice

Use a separate RAG HTTP service, not direct imports of internal Python modules. HTTP provides process and dependency isolation, a stable Pydantic-validated contract, and allows the RAG service to own local model/Qdrant resources. Django should own UI, authentication, conversation records, message records, retention, user/session controls, and conversation-level authorization. The existing API must first gain a trusted multi-user identity boundary; its present shared-token/static-principal contract is only suitable for local single-user use.

For an initial local integration, Django can call the existing `POST /v1/query` only when the index is eligible and the service is intentionally local/single-user. It cannot currently serve the requested ChatGPT-style conversation workflow or production corpus.

### Proposed stable contract (recommendation only; not implemented)

All routes should be versioned, use authenticated server-validated identity, return a documented error envelope, and carry a request/correlation ID. Django should not be allowed to supply arbitrary `tenant_id`, ACL principals, or source allowlists.

1. `POST /v1/conversations` — create a conversation; response `{conversation_id, created_at}`. Conversation ownership is enforced by Django for every operation.
2. `POST /v1/conversations/{conversation_id}/messages` — body `{message, retrieval_options?}`; response `{message_id, status, answer, citations[], request_id, model/retrieval metadata}`. History policy and size limits must be explicit. Send only scoped conversation history needed by the RAG service, or keep history assembly in a trusted orchestration layer.
3. `GET /v1/conversations/{conversation_id}/messages?cursor=&limit=` — return paginated user/assistant messages and citation snapshots, after ownership check.
4. `GET /v1/citations/{citation_id}` (or immutable citation snapshots embedded in each message) — return title, source/document/chunk IDs, section/pages, and a safe source reference. Avoid exposing local paths or raw evidence unless an explicit authorized endpoint is designed.
5. `POST /v1/conversations/{conversation_id}/messages:stream` — optional SSE. Prefer progress events while retrieval/generation/verifier run and emit answer events only after verification succeeds. Include terminal `complete`, `abstained`, and `error` events; define disconnect behavior and cancellation policy. Do not stream raw unverified tokens.
6. `GET /health` — unauthenticated liveness only. `GET /ready` — authenticated/internal readiness with reviewed-index status and dependency health; do not leak detailed host/model metadata to public callers.

Django conversation persistence should use its relational database with an ownership constraint tying every conversation and message to the authenticated user/tenant. Store the verified answer and citation metadata as an immutable response snapshot, plus request/model/index versions needed for later audit. Do not treat a conversation ID as authorization by itself.

## 13. Prioritized implementation roadmap

### P0 — Make an authorized corpus available

1. Complete human source/document evidence review and build/validate an index whose manifest is `reviewed_source_and_document_approval`; preserve existing fail-closed behavior. This is an external human review dependency, not a Django code change.
2. Run corpus-level retrieval/answer evaluations on approved documents, including citation accuracy, abstention, relevance and latency. Synthetic smoke success is not sufficient evidence.

### P1 — Establish the integration contract and identity boundary

3. Define a versioned RAG API contract with stable success/error schemas, correlation IDs, model/index/retrieval versions, timeouts and idempotency behavior.
4. Replace shared static-user semantics for Django integration with trusted issuer-backed identity or authenticated service-to-service identity plus validated user/tenant context. Enforce authorization per request and per conversation; never trust client-provided ACL scope.
5. Decide the conversation/history model and ownership. Prefer Django DB ownership and a constrained RAG request containing only the authenticated conversation context actually needed.

### P2 — Conversation and streaming lifecycle

6. Implement create/message/history/citation endpoints and persistence, retention, deletion, pagination, and ownership tests.
7. Add optional SSE progress and verified completion events only after the verifier passes. Define cancel/disconnect and partial-result semantics before exposing a stream.

### P3 — Capacity, observability, and operations

8. Introduce bounded concurrency/admission control, a request deadline, worker/model resource policy, and concurrency/load testing for Ollama, Qdrant, and SQLite.
9. Standardize safe structured logs/metrics/tracing. Keep prompts, evidence, answers, tokens and credentials out of logs; make diagnostics queryable by request ID.
10. Define deployment, TLS/network boundary, secret rotation, health checks, process supervision, backups/restore and recovery for Django, RAG, Qdrant and local model runtime.

### P4 — Security and integration validation

11. Add end-to-end Django↔RAG tests for cross-user isolation, tenant boundaries, revoked approvals, document rejection, stale citations, timeouts, cancellation, retries and service outages.
12. Threat-model prompt injection and retrieval poisoning and measure false support/false abstention rates before choosing further controls.

## Finding classification index

| Finding | Classification |
|---|---|
| Modular retrieval/service/generation flow and local API composition | Implemented and verified |
| Dense retrieval is active; sparse/RRF/reranking are conditional and currently disabled by strategy | Implemented and verified (capabilities); production use by current API is dense only |
| Pydantic one-shot query schema, body bounds, generic validation errors | Implemented and verified |
| Structured request-scoped citations and claim verification | Implemented and verified structurally; semantic quality is insufficiently tested |
| Shared bearer token and static tenant/principal | Implemented and verified for local single-user operation; insufficient for multi-user Django |
| Conversation/message persistence, user-level isolation, history API | Not implemented |
| Streaming and cancellation | Not implemented |
| Source/ACL/document filters and fail-closed unreviewed index gate | Implemented and verified; production corpus use is blocked by source authorization or external review |
| Component timeouts, shutdown cleanup, liveness/readiness | Implemented and verified at code level; no end-to-end/load evidence |
| Concurrency caps, production telemetry, deploy/backup/scaling | Not implemented |
| Real-corpus quality and latency evidence | Blocked by source authorization or external review and evaluation work |

## Files inspected

- `src/rag_pipeline/api/app.py`
- `src/rag_pipeline/service.py`
- `src/rag_pipeline/security/api_auth.py`
- `src/rag_pipeline/retrieval/dense.py`
- `src/rag_pipeline/retrieval/sparse.py`
- `src/rag_pipeline/retrieval/hybrid.py`
- `src/rag_pipeline/retrieval/rerank.py`
- `src/rag_pipeline/retrieval/context.py`
- `src/rag_pipeline/generation/ollama.py`
- `src/rag_pipeline/generation/claim_verifier.py`
- `src/rag_pipeline/generation/errors.py`
- `src/rag_pipeline/embeddings/ollama.py`
- `src/rag_pipeline/storage/qdrant_store.py`
- `src/rag_pipeline/storage/index_manifest.py`
- `src/rag_pipeline/ingestion/approval.py`
- `src/rag_pipeline/ingestion/approval_workflow.py`
- `scripts/run_api.py`
- `configs/retrieval.json`
- `configs/generation.json`
- `configs/embedding.json`
- `configs/indexing.json`
- `docs/local_api.md`
- `tests/test_api.py`
- `tests/test_api_rag_integration.py`
- `tests/test_qdrant_store.py`
- `tests/test_claim_verifier.py`
- `requirements.txt`

No Django files or deployment definitions were found in the project code/configuration search. No test suite, live service, Qdrant mutation, or source approval command was run as part of this read-only audit.
