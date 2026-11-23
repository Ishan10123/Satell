# satell Branding, Query Limit, and RAG Integration Findings

**Project:** `E:\RAG_Project`  
**Date:** 2026-11-18

## Summary

The Django UI is now branded **satell** with the subtitle **SECURE RAG CHAT WORKSPACE**. Prompt validation is 5,000 Unicode code points through the Django form, frontend counter/validation, Django RAG client, FastAPI request schema, retrieval configuration, and dense retriever. The FastAPI JSON body cap is 24 KiB so a 5,000-code-point UTF-8 query also fits. No database migration, credential, approval, manifest, Qdrant, or Ollama setting was changed. The Django adapter remains `mock`.

The request path accepts 5,000 characters without truncation, but the existing 4,096-token generation context cannot necessarily generate an answer for a query that long. That separate limit is detailed below; the context window and output limits were not increased.

## Branding

- Sidebar and login branding: `satell`, subtitle `SECURE RAG CHAT WORKSPACE`.
- Browser title, mobile navigation, welcome eyebrow, and footer use `satell`.
- Existing layout, palette, responsive styles, and Django app/package/container names are unchanged.

## 5,000-character request path

| Boundary | Current limit and evidence |
|---|---|
| Browser textarea | `maxlength="5000"` plus a configured counter. JavaScript counts Unicode code points, enforces 5,000, and adjusts the native UTF-16 maxlength so valid astral characters are not under-counted. |
| Django form/view | `MAX_MESSAGE_CHARS = 5000`; `MessageForm` rejects empty and 5,001-character content. The existing message model uses `TextField`, so it has no smaller database-field cap. Django’s 65,536-byte form-body cap accommodates a 5,000-code-point URL-encoded form, including the worst-case 4-byte UTF-8 characters (about 60 KiB plus fields). |
| Django RAG client | `FastAPIRAGClient` and `MockRAGClient` both validate 1–5,000 characters and pass the accepted query unchanged. |
| FastAPI request | `QueryRequest.query` accepts 1–5,000 characters; `top_k` remains 1–20. Empty and over-limit values fail request validation. |
| FastAPI body cap | 64 KiB, enough for 5,000 astral code points represented using ASCII JSON surrogate escapes plus framing. Requests above the byte cap fail with 413. |
| Retrieval config/service | `configs/retrieval.json` sets `query_max_characters` to 5,000. `scripts/run_api.py` passes that value to both dense retrievers and fails startup if it disagrees with the API schema limit. `DenseRetriever` also defaults to 5,000. |
| Embedding provider | `configs/embedding.json` permits 12,000 input characters, so 5,000 is inside that character limit. |
| Message persistence | `Message.content` is a `TextField`; no database schema change was necessary. |

The 2,000-character `configs/chunking.json` value remains unchanged because it controls document chunk size, not user query size. Generation output settings and model context settings also remain unchanged.

### Downstream generation constraint

`configs/generation.json` configures a 4,096-token context window and 512 output tokens. `OllamaGenerator` reserves another 256 tokens, leaving a 3,328-token input budget. Its context planner uses a conservative UTF-8-byte estimate and reserves a 163-byte safety preamble. A 5,000-character ASCII query alone estimates to 5,000 input units, so it leaves no passage budget; context assembly raises `ContextBudgetError`, which the API returns as a generic 400 query error. This is a bounded refusal, not prompt truncation. Useful generation may require a shorter query, depending on its contents and the fixed prompt. No model context or output limit was raised here.

## Real RAG integration diagnosis

### Why the UI returns synthetic answers

The running Compose configuration sets `RAG_ADAPTER: mock` explicitly. `settings.py` also defaults to `mock` if the variable is absent. `get_rag_client()` therefore constructs `MockRAGClient`, whose answer and citation are fixed, synthetic examples. This is the exact reason the UI currently shows synthetic responses.

### HTTP adapter and schema compatibility

`FastAPIRAGClient` is implemented against the current API contract:

- It posts `{"query": ..., "top_k": ...}` to `/v1/query`, with a server-side bearer token and a correlation header.
- FastAPI accepts those request fields and returns `answer`, `citations`, `request_id`, `retrieval_mode`, and `timings_ms`.
- The Django client parses `timings_ms`, citations, request ID, and retrieval mode; it sanitizes source URLs and rejects malformed response data.
- Contract, response parsing, timeout, HTTP error, and no-truncation tests pass.

FastAPI does not return a `synthetic` field; the Django client correctly treats an HTTP response as non-synthetic and stores verification as `not_reported` unless a status is explicitly available. The HTTP client converts non-success HTTP responses to a generic typed error. The chat view persists a generic failed assistant response and flash message without exposing upstream details.

### Why the HTTP adapter cannot currently reach FastAPI

- There is no FastAPI container or service in the current Docker listing or `rag-app-network`; only Django and PostgreSQL are attached to that network.
- From inside the Django container, `http://127.0.0.1:8000` is Django itself. A live request to that address returned 404, not FastAPI. The host’s `127.0.0.1:8000/health` was unreachable.
- `django_app/compose.yaml` does not provide `RAG_API_BASE_URL` or `RAG_API_TOKEN`. The current setting therefore resolves to `http://127.0.0.1:8000`, and the bearer token is empty. The HTTP adapter requires a token of at least 32 characters and would fail closed before a query.
- `scripts/run_api.py` starts Uvicorn on host loopback (`127.0.0.1`). Even if launched on the host, that listener is not a container-network service and is not a reachable Docker DNS endpoint.
- The configured Django HTTP timeout defaults to 15 seconds, while the local Ollama generation timeout is configured for 120 seconds. This needs an explicit operational timeout decision before real requests are enabled.

### Health, readiness, and current authorization state

- The real FastAPI process is not running at the expected host port, so live FastAPI `/health`, `/ready`, and `/v1/query` requests could not be made. Django’s own `127.0.0.1:8000/health` probe returns 404 because that port is the Django server inside its container.
- In FastAPI code, unauthenticated `/health` is a liveness route. Its route test returns 200.
- Authenticated `/ready` calls the production index check before checking local dependencies. That check requires manifest authorization mode `reviewed_source_and_document_approval`. A regression test confirms it returns 503 for `operator_authorized_unreviewed`.
- The current `rag_docs_v2` manifest reports `status=ready`, 6,565 documents, 58,856 chunks, and `authorization_mode=operator_authorized_unreviewed`. “Ready” describes the built index; it does not mean production-authorized.
- All 14 source decisions remain `pending_review`; the configured document approval registry file is currently absent. The production query guard rejects the manifest before retrieval. Independently, source-scope construction would return no approved source IDs. The current API therefore cannot execute a corpus query under production authorization.

## Validation

- Django/PostgreSQL: **26 tests passed** using the isolated temporary test database `rag_django_test_20261118_branding5000_unicode`; Django removed it after the run.
- Django/SQLite: **26 tests passed**.
- FastAPI API and RAG integration tests (`test_api*.py`): **21 tests passed**.
- Dense retrieval tests: **4 tests passed**.
- Coverage includes empty input, exactly 5,000, rejection at 5,001, unchanged prompt forwarding, 5,000 multibyte API input, body-size rejection, frontend counter logic, HTTP request/response shape, and unreviewed-manifest readiness rejection.
- Django `check`: no issues. Migration check: no changes detected. `pip check`: no broken requirements. `compileall` passed for `src`, `scripts`, and `tests`.
- Live Django login returned 200 and contained the new brand/subtitle. Django, PostgreSQL, Qdrant, and the existing PostgreSQL volume remain present; only Django was rebuilt/restarted for these changes.

The relevant FastAPI tests use in-process API/service fixtures. They do not constitute a live Qdrant/Ollama query or a production readiness check.

## Files changed

- `django_app/templates/base.html`
- `django_app/templates/accounts/login.html`
- `django_app/templates/conversations/list.html`
- `django_app/templates/conversations/detail.html`
- `django_app/chat/forms.py`
- `django_app/chat/static/chat/app.js`
- `django_app/rag_client/client.py`
- `django_app/rag_client/tests.py`
- `django_app/conversations/views.py`
- `django_app/conversations/tests.py`
- `configs/retrieval.json`
- `src/rag_pipeline/api/app.py`
- `src/rag_pipeline/api/__init__.py`
- `src/rag_pipeline/retrieval/dense.py`
- `scripts/run_api.py`
- `tests/test_api.py`
- `tests/test_dense_retrieval.py`
- `docs/satell_branding_query_limit_rag_integration_20261118.md`

No migrations were created. No credentials, Compose adapter settings, approvals, authorization rules, manifests, Qdrant data, or Ollama settings were modified.

## Safe next steps

1. Keep `RAG_ADAPTER=mock` while source and document approvals remain unreviewed.
2. Have a human reviewer complete evidence-backed source decisions and the separate document decisions. Build and validate a reviewed index through the existing approval workflow; do not edit the manifest by hand.
3. Design a private FastAPI deployment reachable by Django through an internal Docker network name. Keep Qdrant and Ollama private and do not publish their ports. Configure a server-side token only after the private route and reviewed index are verified.
4. Resolve user/tenant/principal identity propagation before enabling multi-user real retrieval; browser input must never supply those values.
5. Set and verify an HTTP timeout that accounts for local generation/verification latency, then check authenticated `/ready` and API/client contract against the reviewed index before explicitly authorizing a switch from mock.
6. Treat 5,000 characters as an input ceiling, not a guarantee of successful generation under the existing context window. If long prompts must produce answers, handle model-context budgeting in a separately reviewed task without silently truncating the query.
