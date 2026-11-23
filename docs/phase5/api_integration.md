# Django ↔ FastAPI integration

Django uses `RAG_ADAPTER=http` and calls the private service URL `http://rag-api:8000`. The bearer token is configured server-side from the environment and is never added to templates or browser JavaScript.

## Request contract

`POST /v1/query`, authenticated with `Authorization: Bearer …` and a Django-generated `X-Correlation-ID`.

```json
{"query":"What is a FastAPI path parameter?","top_k":8}
```

The API rejects extra fields, empty queries, more than 5,000 characters, and `top_k` outside 1–20. Its bounded body limit is 64 KiB. Tenant, principal, source, and document scopes are not accepted from browser input.

## Response contract

The typed response contains `answer`, `citations`, `request_id`, `retrieval_mode`, `timings_ms`, `verification_status`, `diagnostics`, and `synthetic`. Citation metadata contains citation/source/document/chunk IDs, title, pages, section, and a sanitized HTTP(S) source reference. Django validates limits and identity format before persistence.

Internal generation artifacts are opt-in, bounded, local-demo-only, and not serialized into ordinary user pages. The web UI displays only answer text, citation metadata, and a user-safe verification message.

## Health and readiness

- `GET /health` is a liveness check.
- `GET /ready` is authenticated and validates the active index/authorization state.
- Django startup waits for database connectivity and authenticated FastAPI readiness (bounded retry window), after Compose waits for the FastAPI container health check.

The API contract is implemented in `src/rag_pipeline/api/app.py`; the client boundary is `django_app/rag_client/client.py`. Production readiness remains blocked while reviewed approvals are pending.
