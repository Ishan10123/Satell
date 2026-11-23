# Phase 6B candidate PostgreSQL validation

**Candidate:** `satell-django:phase6-candidate` (`sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9`)  
**Database:** isolated `postgres:17-alpine`, disposable container and tmpfs data directory; no host port and no persistent volume.

## Results

| Check | Result |
|---|---|
| Django system check | Passed; 0 issues. |
| Migrations | All application migrations applied successfully to the isolated PostgreSQL database. |
| PostgreSQL test suite | 65 tests run; 63 passed, 0 failed, 2 skipped. |
| SQLite test suite in candidate image | 65 tests run; 63 passed, 0 failed, 2 skipped. |
| Authentication and owner isolation | Covered by the PostgreSQL suite and separately exercised via the running candidate HTTP application. |
| Citation and generation metadata persistence | Passed in the isolated end-to-end query: one citation snapshot and one generation metadata record persisted. |

The two skips are explicitly opt-in integration tests: `test_synthetic_http_integration` requires `RUN_SYNTHETIC_RAG_HTTP_TESTS=1`, and `test_local_academic_demo_e2e` requires `SATELL_LIVE_RAG_E2E=1`. The actual candidate HTTP E2E was run separately in this tranche; it used a real local FastAPI/model query against a single synthetic fixture, not a mock adapter.

The test log also emitted a password-reset email delivery warning because staging had no SMTP server. The suite passed; this was not an SMTP delivery test.

## Isolation and preservation

PostgreSQL was run only on the disposable `satell-phase6b-e2e-net` network with a tmpfs data directory and no published port. The candidate service used the network alias `postgres`. The test database was created and dropped by Django’s test runner. The application schema used for the candidate HTTP workflow lived only in the disposable PostgreSQL container. No existing `rag-postgres` container, volume, or data was connected.

The candidate app container used the test database credentials through runtime environment configuration. No credential is recorded in this report or stored in the image. The temporary staging containers and network were removed after evidence collection; candidate images were retained.

## Reproducible invocation shape

```powershell
docker run --rm --network <isolated-candidate-network> --env-file <ephemeral-candidate-env> satell-django:phase6-candidate python manage.py check
docker run --rm --network <isolated-candidate-network> --env-file <ephemeral-candidate-env> satell-django:phase6-candidate python manage.py test --verbosity 1
docker run --rm --network <isolated-candidate-network> --env-file <ephemeral-candidate-env> satell-django:phase6-candidate python manage.py migrate --noinput
```

The env file contained only temporary test credentials and configuration; it was not added to the repository. The PostgreSQL-backed test result is independent of the SQLite result.
