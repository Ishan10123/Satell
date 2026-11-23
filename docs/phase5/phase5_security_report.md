# Phase 5 security report

## Verified protections

- Django session authentication protects chat routes. Browser tests rejected invalid login and redirected after logout.
- Django CSRF middleware remained active; the actual browser form worked and a same-origin state-changing request without the token returned 403.
- ORM queries scope conversation lookup to the authenticated user. Tests cover cross-user conversation/message/citation reads, updates, and deletion.
- The browser did not contain the FastAPI bearer credential. Django-to-FastAPI HTTP uses the server-side credential and typed response validation.
- Markdown rendering uses DOM construction and text nodes, safe URL protocol checks, and no `innerHTML`. Existing tests cover escaping.
- API/local-demo authorization and citation/claim verification were unchanged. The 20-query live run kept verified/partial/abstention/fail-closed distinctions.
- Containers run non-root, read-only where configured, with dropped Linux capabilities and `no-new-privileges`. Internal FastAPI has no published port; Django/PostgreSQL/Qdrant host bindings are loopback only.
- Generation prompt was strengthened against secret disclosure, policy override, fabricated evidence/citations, external URL/tool requests, and cross-user data. The isolated real-model fixture probe did not disclose its fake secret or attacker URL and passed citation validation and claim verification.

## Limitations and residual security work

- The prompt-injection probe uses an isolated synthetic `AssembledContext`, not malicious content stored in Qdrant or a full retrieval path. It does not prove comprehensive prompt-injection resistance.
- Production authorization remains fail-closed; local academic-demo operator authorization is not legal review. Source/document legal decisions remain pending.
- No actual service outage was induced. Fault behavior is covered by typed-client/middleware unit tests; database, Qdrant, and Ollama shutdown behavior was not tested against shared live services.
- No external penetration test, secret-scanning service, formal threat model, production TLS/identity provider, or public deployment controls were added.
- Static files are served by Django's local development server mode; this is not suitable for private/public deployment.

## Credential incident handled during this work

A diagnostic command unintentionally printed two local environment secret values into the tool output. Both affected credentials were immediately rotated: Django's secret key and the PostgreSQL application role password. The updated local environment file is active, Django was restarted, authenticated FastAPI readiness and PostgreSQL-backed tests passed, and no secret values were copied into project reports or evaluation artifacts. The previous values should be considered invalid. This incident is recorded here for operator awareness.

The existing PostgreSQL container was deliberately not recreated. Its Docker environment metadata can therefore retain the old, now-invalid bootstrap password string until a separately planned container lifecycle update; the database role itself accepts the rotated password. Do not expose container environment metadata in logs or reports. A later infrastructure change should update the container configuration while preserving `rag_postgres_data`.

## Test evidence

The 260-test RAG suite and 41-test Django suites passed as detailed in [the final test report](phase5_final_test_report.md). The real Chrome flow confirmed that CSRF and authentication remained effective after the implementation.
