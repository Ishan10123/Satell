# Satell Phase 3 Security and Reliability Review

Date: 2026-11-18

## Scope and outcome

This review exercised the current local academic demo deployment and its automated regression suites. It did not change source/document legal decisions, authorization registries, index manifests, Qdrant points or PostgreSQL application data. The disposable workflow account and its associated rows were deleted at the end of the run.

## Verified controls

- Django conversation reads, writes and deletes are scoped through the authenticated user's conversations in `django_app/conversations/views.py`. Cross-user detail access returns 404; the regression test also checks that message and citation markers are not disclosed.
- Login, CSRF-protected message submission, logout, session invalidation, and unauthenticated protected-route behavior are covered in `django_app/conversations/tests.py`. CSRF middleware remains enabled.
- The Django-to-RAG client uses the server-side bearer credential (`django_app/rag_client/client.py` and `django_app/config/settings.py`); browser JavaScript does not receive it. The FastAPI service has no host-published port. Authenticated `/ready` returned 200 from the Django container; unauthenticated readiness returned 401.
- Django now rejects startup without `DJANGO_SECRET_KEY`; the previous development fallback was removed in `django_app/config/settings.py`. `django_app/compose.yaml` requires that value through environment interpolation.
- `DatabaseAvailabilityMiddleware` returns a generic 503 and `Retry-After` for database connection failure without returning exception details (`django_app/config/middleware.py`). Its regression test uses an injected database error.
- The 20 live query outcomes were recorded with verifier and citation validation diagnostics. Unsupported claims and invalid citations were rejected; no mock fallback was counted as a real response.
- Local demo authorization is explicitly selected in the FastAPI configuration, signed registries are validated, and production authorization remains separate. Registry tampering, missing registry, unauthorized documents and production rejection are covered by RAG tests, including `tests/test_local_academic_demo_authorization.py`, `tests/test_api.py`, and `tests/test_workflow_readiness.py`.

## Network exposure observed

- Django is published only as `127.0.0.1:8001 -> 8000`.
- Qdrant ports 6333/6334 are published only on `127.0.0.1`.
- PostgreSQL port 5432 is published only on `127.0.0.1`.
- FastAPI has no host port binding. Django and FastAPI share the private `satell-chat-rag` Docker network; FastAPI and Qdrant share `satell-rag-service`. Django and PostgreSQL share `rag-app-network`.
- Windows reports Ollama listening on `127.0.0.1:11434`. This is not a LAN wildcard listener. The current local Docker Desktop path reaches the host Ollama service; it is a host-local integration, not a deployable private-service boundary.

These are observations of the current machine, not firewall or remote-host penetration tests.

## Reliability checks

The full suites include injected cases for FastAPI connection failure/timeouts, malformed response parsing, invalid/empty/oversized queries, Qdrant/vector-store errors, Ollama connection/timeouts, verifier rejection, invalid citations, missing/tampered authorization registries, and database outage handling. The actual dependencies were not stopped during this task; fault behavior was tested with controlled unit/integration doubles to avoid disrupting the shared running services. Thus a real process-kill/outage recovery drill remains unverified.

## Production and operational gaps

- `python manage.py check --deploy` reports four expected local-deployment warnings: HSTS unset, SSL redirect off, secure session cookie off, and secure CSRF cookie off. HTTPS termination is not configured; those settings must be addressed at a real TLS deployment boundary.
- The Django Compose command runs Django's development `runserver`, which is not a production application server.
- No backup/restore drill, disaster recovery objective, centralized monitoring/alerting, or sustained load/concurrency test was performed.
- The APIs and database are locally networked but their availability and recovery across host restart were not tested.
- A query can include sensitive user text. Review retention, access to application logs, and production data retention policies before accepting private or commercial data.
- Legal source reviews remain pending and the corpus remains `operator_authorized_unreviewed`; local demo operator authorization is not production legal approval.

## Test evidence

- Django/PostgreSQL: 39 tests passed, 2 skipped.
- Django/SQLite: 39 tests passed, 2 skipped.
- RAG: 242 tests passed, 1 skipped.
- Django `check`: passed. Migration check: no changes detected; existing migrations applied.
- `pip check`: no broken requirements.

See [phase3_final_readiness_report.md](phase3_final_readiness_report.md) for readiness classification.
