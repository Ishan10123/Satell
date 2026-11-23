# Service outage and recovery validation

## Verified

- FastAPI `/health`: HTTP 200.
- Authenticated FastAPI `/ready`: HTTP 200 from the Django container.
- Invalid bearer credential on a query request: HTTP 401.
- After the invalid-credential request and isolated Qdrant probe, authenticated readiness remained 200 and the app containers remained healthy.
- Django HTTP-client regression tests cover timeout typing, unavailable-service typing, generic error messages, protocol failures, and no secret leakage. FastAPI regressions cover generation/dependency errors and safe HTTP classifications. These are part of the complete suites reported in `phase5_closure_test_report.md`.

## Not fault-injected against shared infrastructure

PostgreSQL, Qdrant, Ollama, and the live FastAPI container were not stopped or misconfigured. They are shared persistent/runtime services and stopping them would interrupt the user's local deployment. The tests validate their failure boundaries with controlled client/test fixtures; those results are not equivalent to physically severing each live dependency. No recovery claim is made for a real PostgreSQL/Qdrant/Ollama outage. A safe maintenance window with isolated disposable replicas is still required to verify those recovery paths end to end.

The probe endpoint used a deliberately invalid synthetic credential, never the configured service token. No mock response was accepted as a real answer, and Django remained configured with `RAG_ADAPTER=http`.
