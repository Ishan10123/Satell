# Testing and evaluation

## Test layers

- Python `unittest` RAG suite: parser, ingestion, identity, authorization, retrieval, generation, verifier, citation, API behavior.
- Django `TestCase` suites: auth, ownership, persistence, client behavior, forms and endpoints.
- Opt-in PostgreSQL tests: verify the deployed database backend without deleting data.
- SQLite tests: fast local backend regression; two integration cases are opt-in.
- API integration: authenticated Django-to-FastAPI synthetic and live query checks.
- Browser E2E: Playwright-driven actual UI workflow, distinct from HTTP/API tests.
- Benchmarks/evaluations: retrieval and live query artifacts; diagnostic sample sizes only.

## Latest recorded results

The dated 2026-11-19 rerun is recorded in `evidence/test_run_summary_20261119.md`: the RAG suite ran 263 tests (262 passed, one Windows symlink-creation test skipped); Django ran 65/65 against PostgreSQL and 65/65 against SQLite with live and synthetic integration opt-ins. The later Phase 6 run on 2026-11-20 ran 270 RAG tests (269 pass and one Windows symlink skip); an isolated Linux environment ran all 270 successfully. The new Django candidate image ran 65 SQLite tests (63 pass, two opt-in integrations skipped). The earlier PostgreSQL/SQLite 65-test runs are preserved as the latest PostgreSQL validation; the candidate image was not separately tested against PostgreSQL. Current evidence is in [`../phase6/evidence/phase6_candidate_validation_20261120.md`](../phase6/evidence/phase6_candidate_validation_20261120.md). No test suite reset Qdrant or the application database.

## Quality evidence

The 30-query retrieval benchmark used source/topic labels, not expert human relevance judgments. Dense Recall@8 0.981; RRF 0.981; local reranker 1.000, but reranker precision/MRR/nDCG were lower than dense on the same small evaluation, and it was much slower (retrieval p50 199 ms dense, 1,590 ms RRF, 3,401 ms rerank). Do not turn these results into general quality guarantees.

The earlier 20-query live generation run recorded 12 verified, 4 partial, 1 abstention, 3 failed/withheld; p50 end-to-end latency 6.253 s, p95 9.755 s, max 15.961 s, minimum 626 ms. The later 30-query browser evaluation recorded 13 verified, 6 partial, 4 abstentions, and 7 failed/rejected outcomes; 19 had citations; latency minimum 486.54 ms, p50 4,768.02 ms, p95 6,484.96 ms, maximum 7,202.05 ms. These are separate diagnostic samples with heuristic expected labels, not capacity planning or expert correctness judgments. Earlier resource samples measured GPU utilization up to 100% and VRAM 4,415/8,151 MiB. Host CPU and Ollama RAM peak were not measured.

## Reproducible commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
docker exec -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test --keepdb
docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/satell-chat-experience-tests.sqlite3 -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test
docker exec django_app-django-1 python manage.py check
docker exec django_app-django-1 python manage.py makemigrations --check --dry-run
docker exec django_app-django-1 python -m pip check
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

Use the documented opt-in flags/settings to run full backend integration tests; do not invent or print secrets. Check actual test runner instructions in Django test modules before setting environment variables. Browser suite: `.\.venv\Scripts\python.exe scripts/phase5_browser_e2e.py` only when its documented temporary-user setup is safe and cleanup is verified.

## Interpretation

A unit test proves a specific branch under a fixture. Synthetic integration tests do not prove corpus quality. A browser test does not prove legal rights. A passing health check does not prove capacity or failover. Record exact command, count, skips and environment with every new run.

## Chat experience follow-up — 2026-11-19

The RAG suite ran 263 tests: 262 passed, one skipped because Windows symlink creation was unavailable. Django ran 65 tests against PostgreSQL and 65 against SQLite; all 130 passed with live/synthetic integration opt-ins. The current in-turn representative real FastAPI query via Django returned `synthetic=false`, `verified`, two citations and the original correlation ID in 3,696.64 ms. An immediately preceding query returned `failed` with zero citations in 2,672.45 ms. Both contacted the actual endpoint; this shows output variation, not a stable quality pass. Chrome end-to-end and 30-query measurements are separately documented in [the chat experience report](SATELL_CHAT_EXPERIENCE_RECOVERY_AND_QUALITY_REPORT.md).

`manage.py check` reported the expected `accounts.W001` warning: `SMTP_HOST` is empty, so password-reset email cannot be delivered. `makemigrations --check --dry-run` reported no changes. Host `pip check`, `compileall`, and Compose config validation passed. The current authenticated FastAPI `/ready` request from Django returned HTTP 200 with `ready=true`; `/health` returned HTTP 200. Qdrant reported green with 58,856 points; PostgreSQL `pg_isready` accepted connections. Application tables remained at one user, two conversations, ten messages and fourteen citation snapshots after these test runs.

A new actual Chrome run verified login, password visibility, generic reset confirmation, real RAG response, chat layout, copy controls, follow-up, rename, exports, sharing/revocation, lock/unlock, deletion confirmation, mobile width, theme, logout and relogin. The 30-query browser evaluation recorded 13 verified, 6 partial, 4 abstentions and 7 failed/rejected responses. It did not include expert relevance or factual correctness judgments. Do not treat citation presence or automated verifier outcomes as correctness.
