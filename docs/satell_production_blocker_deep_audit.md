# satell Production Blocker Deep Audit

**Audit date:** 2026-11-18  
**Scope:** Read-only code, configuration, local metadata, and live-service inspection  
**Readiness:** `NOT_READY`

## 1. Executive readiness assessment

satell is a working local development stack and the RAG components pass synthetic tests, but it is not a functioning end-to-end production RAG deployment. The current user-facing Django request selects `MockRAGClient`; no FastAPI service is running. The production API would reject the current `operator_authorized_unreviewed` manifest before retrieval. The source registry has 14 pending decisions, the configured document registry does not exist, and all 58,856 Qdrant points are explicitly marked `operator_authorized_unreviewed`.

I did not change source code, configurations, containers, approvals, manifests, database rows, Qdrant points, or volumes. I did not run tests during this read-only audit. This report is the only intentional project-file change.

### Confirmed current system state

| Component | Evidence and state |
|---|---|
| Django | `django_app-django-1` is healthy and published only on `127.0.0.1:8001`. Compose sets `RAG_ADAPTER=mock`. |
| PostgreSQL | `rag-postgres` is healthy and published only on `127.0.0.1:5432`; the audit did not query or change application rows. |
| FastAPI | No API process/container is running. The application Docker network has no FastAPI service. |
| Qdrant | `qdrant` is running; its published ports are loopback-only. Collection `rag_docs_v2` is green with 58,856 points. |
| Ollama | Host-local service on `127.0.0.1:11434`; installed models are `nomic-embed-text:v1.5` and `qwen3.5:4b`. |
| Manifest | `knowledge_base/metadata/index_manifests/rag_docs_v2.json`: ready, 6,565 documents, 58,856 chunks, `operator_authorized_unreviewed`. |
| Payload authorization | Read-only Qdrant scroll: all 58,856 points have `license_review_status=operator_authorized_unreviewed`, `ingestion_authority=explicit_operator_instruction`, and ACL `local-admin`. |
| Approval registries | All 14 source records are `pending_review`. `configs/approval.json` points to `knowledge_base/metadata/document_approvals.json`, which is absent. |
| Docker networks | `rag-app-network` contains Django and PostgreSQL. Qdrant is on a separate `bridge` network. Ollama runs on the host. |

The manifest’s `status: ready` is structural/index readiness, not production authorization. `scripts/ragctl.py validate-index` validates index compatibility and point count; the production authorization-mode check is separately enforced in the API.

## 2. Completed components

- Django authentication, CSRF middleware, owner-scoped conversation queries, PostgreSQL message/citation persistence, and the mock disclosure are implemented in `django_app/config/settings.py`, `django_app/conversations/views.py`, `django_app/chat/views.py`, and the conversation templates.
- A synchronous `FastAPIRAGClient` exists in `django_app/rag_client/client.py`. It sends `POST /v1/query` with `query`, `top_k`, a server-side Bearer token, and `X-Correlation-ID`; it validates response structure and citation fields.
- FastAPI defines `/health`, authenticated `/ready`, and authenticated `/v1/query` in `src/rag_pipeline/api/app.py`.
- Dense retrieval, optional BM25/reciprocal-rank fusion (RRF), optional ONNX reranking, context assembly, Ollama generation, and claim verification are modularized. These components have unit/in-process tests and a prior synthetic smoke run.
- Approval helpers bind evidence to source/document IDs and verify evidence-file checksums and project-local paths. Parsing and indexing re-run authorization rather than trusting an earlier parse decision.
- Compose publishes Django, PostgreSQL, and Qdrant only on host loopback. This is an appropriate local-only boundary for the currently running UI/database/vector service arrangement.

## 3. Exact source and document authorization requirements

### Source registry

`knowledge_base/metadata/source_approvals.json` uses registry version `1.0` and a `sources` object. Valid statuses are `pending_review`, `approved`, and `rejected`. For an `approved` source, `load_approval_registry` in `src/rag_pipeline/ingestion/approval.py` requires non-empty `reviewed_by`, `reviewed_at`, `license_name`, `evidence_path`, `evidence_sha256`, `evidence_catalog`, `evidence_record_sha256`, `evidence_source_id`, `review_notes`, and `approval_scope`.

`_evidence`, `decide_source`, `decide_document`, and `validate_record` in `src/rag_pipeline/ingestion/approval_workflow.py` require the catalog and artifact to resolve inside the project, exist, match the expected source ID (and document ID for paper decisions), and match SHA-256 hashes. The evidence catalog row is canonically hashed. Source scopes are exact: documentation sources require `documentation_candidates`; arXiv collection metadata requires `paper_source_metadata_only`.

Source approval is a human decision; a verified candidate evidence file alone does not change `pending_review` or bind evidence to a decision. Do not treat a repository-root license as blanket coverage for third-party content.

### Document registry

The configured path is missing. `decide_document` creates the expected version 1.0 shape:

```json
{
  "registry_version": "1.0",
  "documents": {
    "<64-character document ID>": {
      "source_id": "<arxiv source ID>",
      "status": "approved|rejected|pending_review",
      "reviewed_by": "<reviewer>",
      "license_name": "<verified license> or documented rights basis",
      "reviewed_at": "<timestamp>",
      "evidence_path": "<project-relative artifact>",
      "evidence_sha256": "<SHA-256>",
      "evidence_catalog": "<project-relative JSONL catalog>",
      "evidence_record_sha256": "<canonical record SHA-256>",
      "evidence_source_id": "<same source ID>",
      "document_id": "<same document ID>",
      "review_notes": "<human review scope and decision basis>"
    }
  }
}
```

All 107 arXiv documents require an individual rights review and evidence-backed document decision. The packet currently reports: 52 papers with insufficient evidence, 37 with evidence sufficient only for human consideration, 16 with incomplete scope, and 2 with missing rights information. Although 105 rights links were found and 107 PDF audits passed, all 107 records say manual review is required; none is automatically authorized.

### Current source inventory and indexed counts

The following values were obtained from the current `license-report`, current source registry, and a read-only Qdrant scroll. Inventory candidates and indexed documents are not interchangeable; 31 fewer unique documents are indexed than the supported-candidate total.

| Source ID | Inventory docs | Indexed docs | Qdrant chunks | Current evidence/review classification |
|---|---:|---:|---:|---|
| `arxiv_ai_systems` | 15 | 15 | 701 | No source-level candidate evidence; each paper needs separate review. |
| `arxiv_artificial_intelligence` | 13 | 13 | 660 | No source-level candidate evidence; each paper needs separate review. |
| `arxiv_database_vector_search` | 15 | 15 | 763 | No source-level candidate evidence; each paper needs separate review. |
| `arxiv_information_retrieval` | 15 | 15 | 769 | No source-level candidate evidence; each paper needs separate review. |
| `arxiv_llm_rag` | 16 | 16 | 610 | No source-level candidate evidence; each paper needs separate review. |
| `arxiv_llm_transformers` | 15 | 15 | 724 | No source-level candidate evidence; each paper needs separate review. |
| `arxiv_machine_learning` | 18 | 18 | 1,209 | No source-level candidate evidence; each paper needs separate review. |
| `docker` | 1,114 | 1,113 | 12,521 | 2 checksum-verified candidates; Apache-2.0 docs artifact, but scope/third-party review incomplete. |
| `fastapi` | 158 | 158 | 2,398 | 1 checksum-verified candidate; MIT repository artifact, but docs/assets scope incomplete. |
| `huggingface_transformers` | 787 | 787 | 8,948 | 1 checksum-verified candidate; Apache-2.0 repository artifact, content scope incomplete. |
| `postgresql_18` | 1 | 1 | 5,541 | No catalog candidate row; official license page covers docs, still requires human edition/attribution review. |
| `python_3_13` | 553 | 553 | 13,817 | No catalog candidate row; PSF terms and separate Zero-Clause BSD examples need human review. |
| `pytorch` | 263 | 263 | 2,594 | 2 checksum-verified candidates; separate docs repo says BSD; broader repo license is not blanket coverage. |
| `qdrant` | 3,613 | 3,583 | 7,601 | No candidate evidence; pinned license URL returned 404; obtain authoritative docs terms. |
| **Total** | **6,596** | **6,565** | **58,856** | **14/14 sources pending** |

The 31-record inventory/index delta is one Docker record and 30 Qdrant records. It matches the previously recorded duplicate-path deduplication total but was not re-audited here. No reindex is justified by this audit.

Documentation decisions must define documentation-only scope and explicitly exclude unsupported content and unreviewed third-party images, figures, examples, code samples, logos, or notices. For arXiv, collection-level evidence may establish only metadata-source scope; it cannot grant permission for paper text. Paper rights must be decided per document and may differ by version, publisher/funder, figures, and tables.

## 4. Authorization flow and enforcement points

1. **Candidate validation:** `authorize_document` in `src/rag_pipeline/ingestion/approval.py` checks project-local existing raw paths, allowed extensions/categories, source type, relative-path metadata, ingestion status, raw SHA-256/size, and research-paper audit status. The optional `operator_authorized_unreviewed` flag bypasses the review decision only for explicit development indexing; the production API does not pass this flag.
2. **Parse authorization:** `run_parsing_job` in `src/rag_pipeline/ingestion/parsing_job.py` invokes `authorize_document` before parsing and records blocked/authorized outcomes.
3. **Index authorization:** `index_normalized_run` in `src/rag_pipeline/ingestion/indexing.py` reloads approvals for each provenance row, reauthorizes the raw document, and checks source/content hash before embedding/upsert. Missing document registry becomes an empty decision map; `authorize_document` then blocks research papers lacking a per-document approval. Documentation candidates can be source-scoped.
4. **Manifest compatibility:** `validate_index_manifest` in `src/rag_pipeline/storage/index_manifest.py` verifies manifest version, collection, embedding identity/dimensions, distance, readiness, optional tokenizer/config/inventory checksum, Qdrant health/point count, and positive counts. It does not itself require a reviewed authorization mode.
5. **Production API gate:** `check_index` in `src/rag_pipeline/api/app.py` additionally requires `authorization_mode == reviewed_source_and_document_approval`. The query and readiness routes both call it. The live manifest is rejected here before retrieval.
6. **Current source scope:** `build_scope` reloads the source registry and includes only `approved` records with valid evidence according to `validate_record`. With the current registry, the approved source scope is empty.
7. **Paper decisions:** `document_policy` restricts approved arXiv sources to document IDs explicitly approved in the document registry, matching source and inventory-derived document ID and passing evidence validation. Rejected document IDs are passed to retrieval as exclusions. If the registry file is missing, no arXiv paper is permitted. Documentation sources do not require individual document decisions under this policy; they require source-level documentation scope approval.
8. **Qdrant filter:** `QdrantVectorStore._search` requires tenant ID, approved source IDs, `license_review_status`, and matching principal ACL. It applies excluded document IDs and, for restricted arXiv sources, allows only the permitted document IDs. Production `search()` requires payload status `approved`; the separate development method requires an explicit operator flag plus a matching development manifest.
9. **Context defense:** `ContextAssembler._authorized` in `src/rag_pipeline/retrieval/context.py` independently rechecks tenant, source allowlist, ACL principal, and review status; in development mode it also requires `explicit_operator_instruction`. It marks passages untrusted and escapes delimiters. It does not itself re-open source/document registries; the live API relies on upstream Qdrant document filters.

Current state has multiple independent blocks: API manifest mode is unreviewed; no source is approved; Qdrant points are all unreviewed and production search filters for `approved`; and arXiv documents have no registry decisions. If human approvals are later recorded, the current points still carry the development review status and normal retrieval will not return them. The approved payload/manifest state must be produced through the controlled indexing workflow; changing the manifest mode alone would not make the points approved.

**Defense-in-depth gap to close before promoting the service:** context assembly trusts upstream document-ID filters rather than independently receiving/rechecking the approved/rejected document set. The current API→Qdrant route applies those filters, and tests cover the route, so this is not evidence of a live bypass; it is a missing second check at the context boundary.

## 5. Complete request-path diagnosis

| Transition | Current implementation/evidence | Status and gap |
|---|---|---|
| Browser → Django | Chat form posts with CSRF; `chat.views.message_create` requires login, validates `MessageForm` (1–5,000 chars), and queries the conversation filtered by `user=request.user`. Frontend disables the submit control after submit. | Implemented. Server-side duplicate/idempotency key is absent; duplicate POSTs can create multiple user/assistant rows. A process crash after pending-row creation can leave an assistant message pending. |
| Django → RAG client | `get_rag_client` selects from server settings. `django_app/compose.yaml` explicitly sets `RAG_ADAPTER: mock`; mock returns fixed synthetic answer/citation. | Confirmed synthetic UI path. HTTP adapter is implemented but unselected. |
| HTTP adapter → FastAPI | `FastAPIRAGClient.query` sends JSON `{query,top_k}`, bearer token, and `X-Correlation-ID`; client timeout defaults to 15 seconds. Settings have no token configured in the running container. | No reachable FastAPI address or credential. The HTTP client rejects absent/short tokens. API currently generates a new request ID and does not propagate Django’s correlation header. |
| FastAPI validation/auth | `QueryRequest` forbids extra fields, accepts 1–5,000 characters and top_k 1–20; middleware requires Content-Length and caps body at 64 KiB. `authenticate` validates a server token with constant-time comparison. | Implemented in code, in-process tests only; service is not running. Tenant/principal are fixed environment settings, not mapped from authenticated Django users. |
| FastAPI readiness | `/health` is unauthenticated liveness only. Authenticated `/ready` calls index check, embedding, Qdrant, and generation health checks. | No live endpoint. Current `/ready` would return 503 for the unreviewed manifest before dependency checks. |
| Authorization → retrieval | Query calls `check_index` before scope, approvals, or RAG service. Current mode is rejected. | Confirmed production blocker; no production query reaches retrieval. |
| Dense retrieval → Qdrant | `DenseRetriever.retrieve_detailed` normalizes whitespace and limits query length; `QdrantVectorStore._search` enforces tenant/source/status/ACL/document filters. Config uses top_k 8 by default, API max 20. | Implemented but no live production query. Current Qdrant payload status is all unreviewed, so production `search()` would match zero points even if the manifest gate were bypassed. |
| BM25 → RRF | `BM25Retriever`, `HybridRetriever`, and `reciprocal_rank_fusion` are selectable; config strategy is `dense`. | Not active in the API. `rrf_constant=60`, candidate_top_k=30 are inactive for the current dense path. |
| Reranking | ONNX cross-encoder is pinned in `configs/retrieval.json`, CPU execution configured, but `enabled=false`; `run_api.py` constructs it only for `hybrid_rerank`. | Not active. No evidence supports enabling it as the production default. |
| Context assembly | Current evidence cap is 2,500 UTF-8 bytes and max 8 chunks. `ContextAssembler` rechecks tenant/source/ACL/status and treats content as untrusted. Current implementation includes whole passages only. | Implemented, but context-level document decision recheck is absent. Long chunks are omitted whole and may cause abstention. |
| Ollama generation | Local `qwen3.5:4b`; output is non-streaming, temperature 0, thinking disabled; request sets `num_ctx` and `num_predict`. Generator and verifier use local HTTP clients. | No production API request. Ollama is on the host loopback, inaccessible at `127.0.0.1` from a container. |
| Claim verification/citations | `OllamaGenerator` checks citation IDs and sentence-level citation presence, then `LocalClaimVerifier` requests structured verdicts against claims/evidence; invalid/unsupported results fail closed. | Implemented; LLM verdicts are not proof of semantic truth. Human-reviewed support/precision metrics remain absent. |
| FastAPI → Django response | API returns answer, citations, request ID, retrieval mode and stage timings; Django client validates fields and sanitizes source URLs. | Contract is structurally compatible, but citation response type in FastAPI is `dict[str, object]`, no explicit API version negotiation exists, and no live HTTP contract test ran. |
| Django persistence → browser | User/assistant messages, citation snapshots, and generation metadata persist in PostgreSQL; views and templates render them. | Implemented for mock/integration tests. HTTP success records `NOT_REPORTED` verification status unless API adds a verification field; no real response has been persisted. |

### HTTP timeout/correlation specifics

`django_app/config/settings.py` defaults `RAG_API_TIMEOUT_SECONDS` to 15 seconds. `configs/embedding.json` uses a 60-second embedding timeout, Qdrant uses 5 seconds, and `configs/generation.json` uses 120 seconds for generation and verifier calls with one retry. The full API request therefore has no single end-to-end deadline and may outlast Django’s client timeout. A Django timeout can occur while FastAPI/Ollama continues working; the user can retry and produce duplicate inference/work. There is no disconnect-to-cancellation propagation.

The Django client sends `X-Correlation-ID`; API middleware currently assigns its own random request ID and only returns that generated ID. Successful Django persistence can store the API request ID, but a unified end-to-end correlation chain is not implemented.

## 6. Docker networking requirements

### Existing topology

- Django container `django_app-django-1`: joined to external `rag-app-network`, mapped to host loopback `127.0.0.1:8001`.
- PostgreSQL `rag-postgres`: joined to `rag-app-network`, mapped to host loopback `127.0.0.1:5432`; Compose uses the service name `postgres` at port 5432 from Django.
- Qdrant: joined to a separate Docker `bridge`, mapped to host loopback `127.0.0.1:6333-6334`.
- Ollama: host process listening on host loopback `127.0.0.1:11434`.
- FastAPI: absent. `scripts/run_api.py:main` binds host Uvicorn to `127.0.0.1` and uses loopback URLs from `configs/indexing.json` and Ollama configs.

`127.0.0.1` in Django’s container names the Django container, not the Windows host or FastAPI. The running Django configuration has `RAG_API_BASE_URL=http://127.0.0.1:8000` and no RAG token; a request to that address returned Django’s 404. Therefore changing only `RAG_ADAPTER` to HTTP cannot work.

### Safest target design (not implemented)

1. Add FastAPI as an internal-only service with no host-published port; Django calls it by Docker DNS/service name on `rag-app-network`, with a generated server-side bearer token mounted only in service environments.
2. Give FastAPI and Qdrant a dedicated private Docker network. Do not attach Django to the Qdrant network and do not publish Qdrant ports for service-to-service use. Preserve current loopback host bindings if local operator access is retained.
3. Keep PostgreSQL on its app network and do not attach FastAPI unless it has a documented need.
4. Ollama is the topology constraint: it listens on host loopback, so a Docker FastAPI container cannot use that address. Either keep the API and model runtime on the host, move Ollama into a private container network while preserving/verifying model artifacts, or design a host relay restricted to the Docker bridge and protected by host firewall rules. A relay would require explicit network/security review; do not broaden Ollama’s bind address or expose a public port as an expedient.
5. Use no public service ports; verify host firewall behavior, network membership, and service-name DNS before enabling the HTTP adapter.

No container was recreated, deleted, attached to a network, or reconfigured during this audit.

## 7. LLM context and retrieval assessment

### Active generation settings

`configs/generation.json` currently sets Qwen3.5 4B, context 8,192, max output 1,024, safety reserve 512, temperature 0, thinking false, timeout 120 seconds, one retry. Available estimator budget before system/query framing is 6,656. The generator sends `num_ctx=8192` and `num_predict=1024`; verifier receives the same configured context/output ceiling and uses a separate approximate Qwen estimator.

No compatible local Qwen tokenizer was found. Generator estimation uses UTF-8 byte length; verifier estimation uses a separate character/punctuation heuristic that its own docstring says is not an exact count or mathematical upper bound. The Nomic embedding tokenizer is not used as a Qwen tokenizer. This is conservative but wastes budget for normal ASCII and is not an exact-token guarantee.

Read-only calculation through `OllamaGenerator.context_budget_for` for 5,000-code-point prompts:

| Prompt | Estimated evidence allowance before assembler’s 2,500-byte cap |
|---|---:|
| ASCII letters | 1,068 bytes |
| Python-like code | 1,209 bytes |
| 5,000 emoji | 0 bytes |

The context assembler then takes the smaller of this amount and `max_evidence_context_bytes=2500`. It will omit any whole chunk that does not fit; therefore a valid 5,000-character prompt can still return an abstention or the safe 413 context-budget message. The 5,000-character UI limit is not a promise that every prompt can be answered with evidence.

### Resource and retrieval-quality evidence

- The prior synthetic 4K/8K benchmark used a 5,000-character synthetic prompt and only 32 output tokens. Ollama loaded the requested context size; observed VRAM was roughly 3.7 GiB at 4K and 4.0 GiB at 8K on the 8 GiB RTX 5050 Laptop GPU. The 8K call followed the 4K call, so latency was not a cold-start comparison. Full 1,024-token generation/verifier memory, long-query workload, sustained concurrency, and production latency have not been established.
- Historical local retrieval diagnostics ran 24 questions with dense + BM25 + RRF + ONNX rerank in explicitly authorized development mode. `evaluation/relevance_judgments_reranked_hybrid_20261116.jsonl` still has 24 pending rows; `evaluation/independent_answer_citation_review_20261116.jsonl` has 25 pending rows. No human Recall@K, MRR/nDCG, citation precision, or claim-support metric is established.
- `docs/retrieval_remediation_report_20261116.md` records that, in one adversarial diagnostic, the model answered a “latest FastAPI release” question with citations despite insufficient temporal support. Citation IDs and an LLM verifier do not establish truth or freshness.
- Current API configuration is dense only. BM25/RRF and reranking results from historical diagnostics are not evidence that those stages are active now or that their quality is superior.

## 8. Security and reliability findings

| Classification | Finding and evidence |
|---|---|
| Implemented and verified by code/tests; runtime path unverified | Django uses session auth, CSRF middleware, owner-scoped conversation queries, and server-side RAG credentials. Relevant code: `django_app/config/settings.py`, `django_app/conversations/views.py:_owned_conversation`, `django_app/chat/views.py:message_create`; tests include `test_cross_user_read_update_and_delete_are_rejected`, CSRF login tests, and browser-secret non-disclosure. |
| Implemented and verified by code; current gate blocks queries | FastAPI Bearer auth, Pydantic request bounds, generic validation errors, body limit, production index gate, tenant/source/ACL/document filters, context trust framing, citation checks, and verifier fail-closed behavior. See `src/rag_pipeline/api/app.py`, `src/rag_pipeline/storage/qdrant_store.py`, `src/rag_pipeline/retrieval/context.py`, and tests `test_production_api_rejects_unreviewed_development_index`, `test_client_cannot_supply_tenant_principal_or_source_scope`, `test_document_rejection_is_reloaded_and_passed_as_a_deny_filter`, `test_document_rejection_excludes_passage_even_after_source_approval`, and generation/verifier citation tests. |
| Confirmed production blocker | One server-configured `tenant_id` and `principal_id` are loaded by `scripts/run_api.py`; Django does not pass authenticated per-user scope. This is acceptable only for a consciously shared single-tenant corpus; distinct user/tenant authorization is not integrated or verified. Do not accept scope from browser input. |
| Confirmed reliability gap | Rate limiting (`ApiRateLimiter`) is process-local, keyed by FastAPI’s client IP, and set to 30/min by default. In a Django→FastAPI deployment, requests may all appear to come from Django; the limiter is neither per-user nor cross-worker. No inference semaphore/admission queue or GPU concurrency policy exists. |
| Confirmed reliability gap | Component timeouts exist but no end-to-end deadline or cancellation propagation. Django defaults to 15 seconds; Ollama calls use 120 seconds and may retry. A timed-out browser request may leave inference running. |
| Confirmed reliability gap | Browser button disabling is not server idempotency. `message_create` creates a new user and pending assistant message for each POST; a retry can duplicate work, and a process crash can leave a pending assistant record. |
| Missing feature | No production metrics exporter, tracing backend, structured operational event pipeline, or health detail for individual dependency states was found. Uvicorn access logging is disabled; this limits accidental prompt logging but also limits diagnostics. API generates request IDs, but Django correlation ID is not propagated. |
| Missing feature | No project-configured PostgreSQL backup/restore schedule or tested Qdrant snapshot/recovery procedure was found in Compose/configuration. Persistent volumes existing is not a backup. |
| Confirmed deployment limitation | Django Compose runs `manage.py runserver --insecure` for local static-file serving. It binds host port only to loopback and uses a read-only/non-root container, but the development server is not a production WSGI/ASGI deployment. Local HTTP also uses insecure-cookie settings. |
| Potential defense-in-depth gap | `ContextAssembler` checks tenant/source/ACL/review status but does not itself receive the registry’s permitted/rejected document IDs. The current API applies document filters in Qdrant first, so no live bypass was demonstrated. Add an independent context-level policy check before production multi-service use. |
| Potential fail-closed contract gap | `create_app.check_index` only checks authorization mode when the injected `index_validator` returns a `dict`. The production `scripts/run_api.py` callback returns a manifest dict, so its current path fails closed. A future bad callback returning `True`/`None` could skip that mode comparison; require a validated manifest object in production composition. Tests currently use boolean validators as fixtures. |
| Potential evidence/semantic risk | Retrieved documents are escaped and framed as untrusted, and the verifier judges claim/evidence support, but both are LLM prompt-level defenses. Prior evaluation includes a cited but unsupported freshness answer. Continue treating retrieved text as untrusted and require human-labeled quality evidence. |
| Contract/observability gap | FastAPI `QueryResponse.citations` is `tuple[dict[str, object], ...]`, not a fully typed citation schema; Django validates more strictly. There is no API version negotiation, documented stable error envelope, or unified correlation ID. |
| Configuration drift | `src/rag_pipeline/generation/claim_verifier.py` comments still describe a 512-token configured hard cap although current `configs/generation.json` sets 1,024. Runtime config is passed correctly in code; update/documentation alignment should be verified in the next change. |

No verified vulnerability was found that permits a production query against the current index: the production manifest gate, empty source scope, Qdrant approved-status filter, and context recheck all block it. Findings above distinguish missing production controls from an observed unauthorized-access exploit.

## 9. Tests and evidence supporting conclusions

### Read-only evidence collected for this report

- `docker ps`, `docker network inspect rag-app-network`, and `docker inspect qdrant` confirmed service membership, state, and local port publication.
- `scripts/ragctl.py license-report` reported 14 pending source decisions; verified candidate artifact rows exist only for Docker (2), FastAPI (1), Hugging Face Transformers (1), and PyTorch (2). All have `review_evidence_bound=false` because no human decision exists.
- `scripts/ragctl.py authorization-report` reported 9,932 total inventory rows, 0 authorized, 9,932 blocked (3,336 unsupported extensions; 6,596 pending source review).
- Read-only manifest inspection and Qdrant scroll confirmed manifest counts and all 58,856 point authorization payload values.
- Read-only evaluation packet scan confirmed 24 retrieval judgments and 25 answer/citation reviews are still pending.
- Read-only 8K config budget calculation produced the ASCII/code/emoji estimates above.
- No test command was executed during this audit, in order to keep the investigation strictly read-only.

### Existing regression coverage inspected

Relevant current tests include `tests/test_authorization.py` (pending/rejected source, explicit operator mode, paper-per-document decision, document rejection precedence, registry evidence), `tests/test_workflow_readiness.py` (evidence path/checksum/source/document binding and manifest compatibility), `tests/test_qdrant_store.py` (tenant/source/ACL, rejected document and arXiv allowlist filters), `tests/test_api.py` (auth, server-derived scope, unreviewed manifest readiness rejection, malformed document registry, body bounds, rate limit), `tests/test_retrieval_context.py` (authorization recheck, injection delimiter escape, document rejection), `tests/test_generation.py`, `tests/test_claim_verifier.py`, and `tests/test_api_rag_integration.py`.

The latest recorded general verification in `docs/satell_end_to_end_implementation_report.md` is 223 RAG tests passed / 1 skipped, 28 Django tests on SQLite, 28 on PostgreSQL, compileall and pip check passed, and a synthetic in-memory-Qdrant/Ollama smoke test passed. Those are prior synthetic/test results, not proof of production readiness or live browser-to-FastAPI behavior.

## 10. Prioritized remediation roadmap

1. **Human rights review before any promotion:** Decide a narrow documentation scope source by source; resolve missing evidence; separately review all arXiv papers. Keep pending when rights or third-party content are unclear. Do not change a registry until the reviewer has made the decision.
2. **Implement the private service boundary:** Add FastAPI as a non-published internal service; define private Qdrant connectivity and resolve the host-loopback Ollama constraint; retain the existing production authorization gate. Add a synthetic Django→FastAPI contract test on this topology before any real corpus request.
3. **Create/rebuild a reviewed index only through the authorization workflow:** Current indexed points are all operator-authorized and production `search()` filters for `approved`. Do not hand-edit the manifest or relabel existing point payloads. Preserve current collection/data while designing an additive/rollback-safe reviewed index path.
4. **Bind application identity server-side:** Define how Django authenticated users map to trusted tenant/principal scopes. Never accept scopes from browser fields; add multi-user cross-scope retrieval and citation tests.
5. **Add bounded inference reliability:** One request-wide deadline, bounded concurrency/backpressure, cancellation semantics, idempotency key, pending-message recovery, and retry policy compatible with expensive generation.
6. **Add operational protections:** Structured redacted logging/correlation, dependency-level readiness, metrics, PostgreSQL backup/restore tests, and Qdrant recovery plan. Replace Django development `runserver` before production deployment.
7. **Measure quality before enabling hybrid/reranking:** Complete the pending human relevance/citation judgments; compare dense vs BM25/RRF/rerank on the same labeled questions and report quality/latency. Benchmark long/code/multisource prompts and full output+verification on hardware.

## 11. Exact human decisions required

- For each of the seven documentation sources, decide whether the exact local docs scope (prose, code samples, examples, diagrams/media, notices, and retention) is covered; explicitly list exclusions for third-party assets and unsupported content. Candidate evidence does not decide this.
- For PostgreSQL and Python, inspect the exact local edition and attributed/example content against official license/copyright pages.
- For Docker, FastAPI, Transformers, and PyTorch, inspect the pinned artifact/revision plus the documentation-specific content and third-party material; repository-level license alone is insufficient.
- For Qdrant, obtain an authoritative docs license or written permission because the pinned license URL failed.
- For each of 107 arXiv papers, inspect the specific version, selected license URI, PDF front matter, publisher/funder terms, figures/tables, and intended corpus use. Decide individually; collection metadata approval cannot approve a paper.
- Decide whether rejected/pending material should remain physically in the preserved development collection but excluded from any reviewed index, or whether an additive reviewed collection is preferred. Do not delete the development index as part of this decision.

## 12. Single highest-priority next implementation task

**Implement a private, non-host-published FastAPI integration path with a synthetic Django→FastAPI→Qdrant/Ollama contract test, while preserving the production authorization gate.**

This is the first implementation task after the rights-review precondition because the current UI is provably on the mock adapter and no FastAPI service is reachable from the Django container. Until the private route exists, the project cannot verify the real API contract, health/readiness behavior, timeout handling, persistence of a real structured response, or infrastructure failure paths. The test must use synthetic fixtures and must not make the unreviewed corpus queryable. The Ollama host-loopback connection strategy must be settled as part of that work; do not bind Ollama publicly to make the test pass.
