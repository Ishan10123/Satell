# Phase 4 — Final Test and Runtime Report

Date: 2026-11-19

## Automated tests

| Validation | Result |
|---|---|
| RAG suite: `.venv\Scripts\python.exe -m unittest discover -s tests -v` | 259 tests; 258 passed, 1 skipped |
| Django/PostgreSQL: `docker exec django_app-django-1 python manage.py test --keepdb -v 1` | 39 tests; 37 passed, 2 skipped |
| Django/SQLite: `docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=:memory: django_app-django-1 python manage.py test -v 1` | 39 tests; 37 passed, 2 skipped |
| Django `manage.py check` | no issues |
| Django `makemigrations --check --dry-run` | no changes detected |
| Python compileall | passed |
| Host/API/Django `pip check` | no broken requirements |

## Live infrastructure/evaluation

FastAPI health and authenticated readiness: HTTP 200 each. Qdrant green, `rag_docs_v2` has 58,856 points before/after. Temporary evaluation rows were rolled back; zero temporary users/conversations remained. Thirty real Django → FastAPI requests completed; synthetic response count zero. Outcomes: 21 verified, 4 partial, 2 abstentions, 3 fail-closed. End-to-end p50 6614.243 ms, p95 11482.518 ms, min 505.761 ms, max 12144.442 ms.

The local final result JSON records all question-level timings, scores, context and citations. Earlier pass GPU sampling saw up to 100% utilization and 4,415 MiB/8,151 MiB VRAM; CPU/process memory were not sampled.

Skipped tests are not counted as passed. These tests do not establish browser workflow, legal rights, or production readiness.
