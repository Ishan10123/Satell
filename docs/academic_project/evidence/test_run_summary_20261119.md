# Final test and integrity evidence — 2026-11-19

This is a same-day record of commands actually executed during academic-project consolidation. It does not certify all behavior or production readiness.

## Automated tests

| Suite | Command | Result |
|---|---|---|
| RAG/unit/API/security/regression | `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 260 ran; 259 passed; 1 skipped. Skip: Windows symlink creation unavailable (`OSError`) in symlink-escape test. |
| Django + PostgreSQL with opt-ins | `docker exec -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test --keepdb` | 42 ran; all passed. Includes live local RAG persistence and synthetic HTTP persistence tests. Existing Django test DB reused; application data database was not reset. |
| Django + SQLite, normal | `docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/satell-academic-test.sqlite3 django_app-django-1 python manage.py test` | 42 ran; 40 passed; 2 skipped because explicit live/synthetic integration flags were absent. |
| Django + SQLite with opt-ins | `docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/satell-academic-test.sqlite3 -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test` | 42 ran; all passed. Both test integrations ran against isolated SQLite test DB; live RAG call reached the real FastAPI service. |

## Static/configuration checks

- `docker exec django_app-django-1 python manage.py check` — passed, no issues.
- `docker exec django_app-django-1 python manage.py makemigrations --check --dry-run` — passed, no changes detected.
- `docker exec django_app-django-1 python -m pip check` — passed, no broken requirements. Pip emitted a cache ownership warning only; cache disabled.
- `.\.venv\Scripts\python.exe -m compileall -q src scripts tests` — passed.
- `docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml config --quiet` — passed.
- `.\.venv\Scripts\python.exe scripts/ragctl.py validate-index` — passed; manifest ready, 6,565 documents / 58,856 chunks, `rag_docs_v2`, `operator_authorized_unreviewed`.

## Live application checks

- Docker reported Django, FastAPI and PostgreSQL healthy; Qdrant was up. FastAPI remained un-published to host.
- Authenticated FastAPI `/ready` from the Django container returned HTTP 200.
- Qdrant collection `rag_docs_v2` remained green at 58,856 points.
- Chrome/Playwright browser run via `scripts/phase5_browser_e2e.py`: application 200; invalid login rejected; valid login/dashboard passed; real non-synthetic response complete with one citation and verification label; missing CSRF token returned expected 403; history reopened; response/code/citation clipboard behaviors passed; mobile width/navigation passed; private-service-secret question was safely refused; logout/protected route passed. Browser elapsed query time: 1,918.597 ms; refusal probe: 1,607.349 ms. No page errors; the sole HTTP 403 was the expected CSRF probe.
- The first browser attempt stopped at an expected clipboard fixture absent from the temporary account. The successful run seeded that synthetic UI fixture only in a temporary account and removed the account in `finally` cleanup.

## Persistent data and authorization checks

- PostgreSQL application counts after the browser run: 1 user, 7 conversations, 82 messages; `academic_e2e_` temporary users: 0. These match the prior recorded user/conversation/message counts.
- Qdrant: 58,856 points after validation.
- Source registry still contains 14 source groups, each `pending_review`.
- Manifest remains `ready` with `authorization_mode=operator_authorized_unreviewed`; `document_approvals.json` remains absent.
- No approvals, legal statuses, manifest, Qdrant collection/points, source/raw files, database volumes or service credentials were modified. Browser screenshots and `docs/phase5/browser_e2e_results.json` were regenerated as test artifacts.

## Not tested in this run

- Independent vulnerability scan (no scanner was available), public-network/TLS deployment, destructive/shared-service outage recovery, clean-machine installation, sustained load, formal SLO validation and legal review.
- No real ingestion, indexing, embedding regeneration, corpus reauthorization or Phase 6 work was performed.

## Chat-experience implementation follow-up — 2026-11-19

This later run supersedes the older test counts above for the changed application code.

### Automated tests and checks

- RAG suite: 263 tests passed; 1 Windows symlink test skipped because symlink creation was unavailable.
- Django/PostgreSQL with live/synthetic integration flags: 65 tests passed.
- Django/SQLite with the same integration flags: 65 tests passed.
- Django system check completed with expected warning accounts.W001: SMTP_HOST is empty, so password-reset mail cannot be delivered.
- makemigrations check: no changes detected.
- compileall and host virtual-environment pip check: passed.
- Compose configuration: valid.
- Authenticated FastAPI /ready from Django container: HTTP 200, ready=true; private /health: HTTP 200.

### Browser and live RAG

- scripts/chat_experience_browser_e2e.py passed using a temporary account removed after the run. The workflow covered password show/hide, enumeration-safe reset UI, bad/good login, real RAG answer, user-right/Satell-left layout, citations and copy actions, follow-up, automatic title, rename, three exports, no-session read-only share, revocation, lock/unlock, delete confirmation, mobile width, theme, logout and relogin persistence.
- Browser RAG answer: one paragraph, zero list items, one citation, verified label; automatic title was “FastAPI Path Parameter”; end-to-end time 2,025.02 ms.
- Live 30-question run used Chrome → Django → authenticated FastAPI → Qdrant/Ollama → PostgreSQL. Results: 13 verified, 6 partial, 4 abstained, 7 failed/rejected; citation cards appeared on 19 responses. End-to-end latency min 486.54 ms, p50 4,768.02 ms, p95 6,484.96 ms, max 7,202.05 ms. These are single local-run measurements.
- Expected abstention matched for 2 of 4 heuristic abstention cases. SAT-16 and SAT-19 abstained unexpectedly; SAT-26 and SAT-27 failed/rejected instead of producing the expected explicit abstention. Seven failure/partial cases need human source-evidence review.
- Expectations were heuristic and no human factual-correctness or semantic citation judgments were performed. Do not treat automated verifier outcomes or citation presence as correctness.

### Persistence

- Application PostgreSQL counts before and after temporary browser/evaluation accounts were created and deleted: 1 user, 2 conversations, 10 messages, 14 citation snapshots.
- Qdrant rag_docs_v2 remained green with 58,856 points before and after.
- No application migration was added in this follow-up; previously applied conversation migration 0003 remains applied.
- No Qdrant data, manifest, source approval, license status, raw source, or persistent volume was changed.

Detailed implementation and live results: [chat experience report](../SATELL_CHAT_EXPERIENCE_RECOVERY_AND_QUALITY_REPORT.md), [browser scenario JSON](chat_experience_browser_results.json), [30-query result JSON](../../../evaluation/results/satell_chat_quality_live_20261119.json).

## Final comprehensive diagnosis rerun — 2026-11-19

Commands actually rerun for final consolidation:

| Check | Command | Result |
|---|---|---|
| RAG/API/auth/retrieval/generation suite | ` .\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 263 tests ran; 262 passed; one skipped because Windows symlink creation raised `OSError`. Exit 0. |
| Django + PostgreSQL and live/synthetic opt-ins | `docker exec -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test --keepdb` | 65 tests passed. Existing test database preserved. Exit 0. |
| Django + isolated SQLite and live/synthetic opt-ins | `docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/satell-chat-experience-tests.sqlite3 -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test` | 65 tests passed. Isolated test database destroyed by Django test runner. Exit 0. |
| Django configuration | `docker exec django_app-django-1 python manage.py check` | Only expected `accounts.W001`: SMTP host not configured. No application errors. |
| Migration consistency | `docker exec django_app-django-1 python manage.py makemigrations --check --dry-run` | No changes detected. |
| Host dependencies | `.\.venv\Scripts\python.exe -m pip check` | No broken requirements. |
| Python compile | `.\.venv\Scripts\python.exe -m compileall -q src scripts tests` | Passed. |
| Compose syntax | `docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml config --quiet` | Passed. |
| Index validation | `.\.venv\Scripts\python.exe scripts\ragctl.py validate-index` | Exit 0. Manifest remained ready for `rag_docs_v2`, 6,565 documents / 58,856 chunks, `operator_authorized_unreviewed`. |

Current runtime checks: Django, FastAPI and PostgreSQL Docker health states were `healthy`; Qdrant was `up`; PostgreSQL accepted connections; Qdrant collection was green with 58,856 points; authenticated FastAPI `/ready` from Django returned HTTP 200 with `ready=true`, and `/health` returned HTTP 200. `ragctl validate-index` did not write the manifest.

`python -m pip check` inside both Django and FastAPI containers reported no broken requirements. Docker printed a non-fatal warning that the non-root container cannot write the pip cache; pip disabled its cache automatically.

The direct real query through Django's container made two sequential requests for the same short FastAPI question. The first was non-synthetic but returned `failed`, zero citations, 2,672.45 ms. The second was non-synthetic, `verified`, two citations, and preserved its correlation ID, 3,696.64 ms. This is a live integration check, not a browser test or reliability estimate. The separately recorded Chrome end-to-end workflow and 30-question browser evaluation remain the browser evidence.

Persistent-state check after test reruns: PostgreSQL has 1 user, 2 conversations, 10 messages and 14 citation snapshots; Qdrant has 58,856 points. The source approval registry still has 14 `pending_review` source decisions, the 9,932 license review statuses remain pending, `document_approvals.json` is absent, and the manifest authorization remains `operator_authorized_unreviewed`. No application data, persistent volumes, Qdrant points, manifests, registries or legal status fields were changed by this diagnostic run.

Not executed in this rerun: new browser automation, vulnerability scanning, public/TLS deployment, backup restore, sustained load, destructive outage recovery or legal review. Previously recorded browser results are linked above; no new browser result is claimed.
