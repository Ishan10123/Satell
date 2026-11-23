# Phase 5 reliability report

## Implemented behavior

- `django_app/startup.py` checks the database and authenticated FastAPI readiness with bounded retry attempts and fixed, non-secret logs before starting Django.
- Django's HTTP adapter has bounded timeouts and maps connection, timeout, bad-status, malformed schema, and oversized-context errors into typed errors. It does not silently fall back to mock mode in the running Compose configuration.
- A failed RAG call persists a generic failed assistant message and safe failure metadata. The user sees a retry-oriented message without upstream details.
- Successful response, citation snapshots, generation metadata, and conversation timestamp are written together in a database transaction. The timing row is updated with Django persistence duration.
- Existing database-unavailable middleware returns a generic retryable 503 with `Retry-After`; tests assert no database internals leak.
- FastAPI liveness and authenticated readiness remain separate. Readiness checks the actual index authorization state; production remains blocked unless the configured authorization policy qualifies.

## Verified coverage

- Django tests: RAG timeout/unavailable transport, malformed response/citation, context overflow, failed response persistence, database operational error, CSRF, expired session/logout, and ownership.
- FastAPI tests cover invalid bearer token, unavailable vector store as a safe classified error, readiness and authorization failure, registry tampering, and invalid schema inputs.
- Actual app readiness and real browser-to-FastAPI-to-Qdrant/Ollama request passed. All 20 current evaluation responses were persisted.

## Not exercised

FastAPI, Qdrant, Ollama, or PostgreSQL were not stopped during this task because they are shared stateful services. Actual outage behavior is therefore not live fault-injection verified. Bounded request deadlines cover individual calls; there is no queue or distributed concurrency control. Automatic retries of non-idempotent chat submissions are not added. A browser disconnect may leave an already persisted user message and pending assistant state until the HTTP request completes; recovery/reconciliation of orphan pending messages remains a follow-up.
