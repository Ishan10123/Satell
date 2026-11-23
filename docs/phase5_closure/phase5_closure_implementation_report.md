# Phase 5 closure and hardening implementation

**Assessment: local academic demonstration is operational; private deployment requires additional controls; public/commercial production is not ready.** Legal source/document review remains pending, the production manifest still says `operator_authorized_unreviewed`, and local demo authorization remains a distinct operator-authorized demo policy.

## Completed in this closure

- Recreated only `rag-postgres` from `infrastructure/postgres.compose.yaml` after making and restore-testing a custom-format backup. It reused `rag_postgres_data`, the existing `rag-app-network`, alias `postgres`, and loopback port binding. The rotated configured database password matches the recreated container environment; stale old container metadata is gone.
- Replaced Django `runserver --insecure` with Gunicorn WSGI, non-root runtime, build-time `collectstatic`, WhiteNoise compressed manifest storage, and a larger HTTP liveness probe timeout for synchronous inference.
- Added clipboard controls for rendered assistant answers, code blocks, and public citation references. Internal source/document/chunk identifiers are no longer rendered in citation cards or copied to the clipboard; identifiers remain persisted server-side.
- Added a real dense-retrieval prompt-injection probe using a disposable Qdrant collection and real local embeddings/generation/claim verification. The collection is deleted in `finally`; production collection count stayed 58,856.
- Added controlled 2/3-request browser workload measurements and stored safe aggregate results in `concurrency_probe_results.json`.
- Ran live API authentication/readiness, full 20-question browser evaluation, and post-refresh browser workflow. Temporary test users and their conversations were removed.

## Changed files

- `django_app/requirements-docker.txt`, `django_app/config/settings.py`, `django_app/Dockerfile`, `django_app/compose.yaml`
- `django_app/templates/conversations/detail.html`, `django_app/chat/static/chat/app.js`, `django_app/chat/static/chat/app.css`, `django_app/conversations/tests.py`
- `infrastructure/postgres.compose.yaml`
- `scripts/phase5_browser_e2e.py`, `scripts/phase5_isolated_qdrant_injection.py`, `scripts/phase5_concurrency_probe.py`
- `README.md`, `docs/phase5/startup_guide.md`, and this closure report package.

No source/document authorization registry, inventory, index manifest, raw corpus, or existing `rag_docs_v2` point was intentionally modified. PostgreSQL's existing volume was reused through container recreation; its application row set returned to the prior 1/7/82 counts after temporary browser/test rows were removed. Qdrant received one isolated temporary collection for the required probe; that collection was deleted in `finally`, and the original collection remained at the same point count. The underlying Qdrant volume may retain normal create/delete operation metadata.

## Final verified counts

- Qdrant `rag_docs_v2`: green, 58,856 points before and after.
- PostgreSQL after temporary-account cleanup: 1 user, 7 conversations, 82 messages.
- Source approvals: 14 `pending_review`; inventory: 9,932 license statuses `pending`.
- Django: 42 tests, 40 passed, 2 opt-in integration tests skipped, on each of PostgreSQL and SQLite.
- RAG: 260 tests, 259 passed, one Windows symlink-capability test skipped.
- Browser: real answer and citation, history persistence, clipboard, CSRF rejection, responsive navigation, safe refusal, logout all passed; exact details in the linked closure reports.

The complete report index is in this directory. Do not infer legal approval or production authorization from these engineering results.
