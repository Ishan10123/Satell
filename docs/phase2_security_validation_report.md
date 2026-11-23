# Phase 2 Security Validation Report

**Run date:** 2026-11-18  
**Verdict:** Local demo scope remains constrained; production use remains blocked.

## Authorization state

- The Qdrant collection remains `rag_docs_v2`, `ready`, with `58,856` points. Its manifest remains `operator_authorized_unreviewed`.
- The local demo source registry has 14 source entries and the document registry authorizes 6,458 distinct documentation document IDs / 6,489 inventory records, bound to 58,856 indexed point IDs. The registry `legal_review_status` remains `pending`.
- `knowledge_base/metadata/source_approvals.json` has 14/14 entries at `pending_review`. The production document approvals file is absent. The production API readiness gate remains separate and requires reviewed source/document approvals; the current index cannot pass production authorization.
- API `/ready` returned 200 only in the explicitly configured local demo runtime with the service bearer credential. `/health` returned 200 without authentication. No authorization mode, registry, legal status or production filter was changed in this task.

## Security checks and evidence

| Control | Result | Evidence |
|---|---|---|
| Signed local demo registry validation | Passed | FastAPI startup/readiness validated the signed registries against inventory and manifest point mapping. |
| Documentation-only retrieval | Passed in evaluation | `src/rag_pipeline/api/app.py::check_demo_index` and `src/rag_pipeline/service.py::LocalRAGService.answer` pass the demo source/document allowlist and `source_types=("documentation",)` filters. |
| Context authorization recheck | Passed in evaluation | `src/rag_pipeline/retrieval/context.py::ContextAssembler._authorized` rechecks tenant, principal, source, unreviewed-demo authority and document metadata before assembly. No authorization exclusion was reported in final diagnostics. |
| Production fail-closed behavior | Regression suite passed | `tests/test_api.py::test_production_api_rejects_unreviewed_development_index`; source/document approval checks remain unchanged. |
| Citation and claim verification | Preserved | Final run had four `verified`, one `partially_verified`, two `uncited_claim_rejected` failures, and one pre-generation comparison abstention. No citations were fabricated or bypassed. |
| Error data exposure | Improved | Static enum-like `X-RAG-Error-Code`/`X-RAG-Error-Stage` labels are regex-bounded; Django persists only those labels and HTTP status. Internal error detail and prompts are not returned. New API/client regression tests pass. |
| Secrets | Preserved | Bearer credentials remained environment-only between Django and FastAPI; none were emitted in this report or evaluation JSON. |
| Network exposure | Unchanged | Django remains bound to host loopback; FastAPI remains container-network-only. Qdrant and Ollama were not published by this task. |
| Persistent data | Preserved | Qdrant point count is 58,856 after the work. PostgreSQL test suite used the existing test DB; evaluation created dedicated conversations/messages/citation snapshots. No volume was removed or reset. |

## Limits

This is not a penetration test or load test. Browser UI, multi-user concurrency, rate-limit behavior under load, backup restoration, production secrets rotation, and production reviewed-document authorization were not validated. The Django browser flow was invoked with Django's test client inside the running container; no browser automation was performed.

The signed local demo registry is an operator authorization for local academic evaluation only, not a legal license approval. Do not describe the underlying sources as license-approved. The current production index remains unavailable until the human source/document review requirements are completed and the manifest is rebuilt/validated under the reviewed production authorization mode in a separately authorized change.

## Regression tests

- RAG suite: 241 tests, 240 passed, 1 skipped.
- Django/PostgreSQL: 34 tests, 32 passed, 2 skipped.
- Django/SQLite: 34 tests, 32 passed, 2 skipped.
- `manage.py check`: passed; `makemigrations --check --dry-run`: no changes.
- `compileall` and `pip check`: passed.

Skipped tests were environment-dependent (Windows symlink support and the two existing Django skips); they were not converted to passes or removed.
