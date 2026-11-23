# Phase 5 closure test report

## Automated tests

- RAG: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` — 260 tests, 259 passed, 1 skipped because symlink creation is unavailable in this Windows environment.
- Django/PostgreSQL: 42 tests, 40 passed, 2 skipped because the synthetic HTTP and live RAG tests are explicitly opt-in.
- Django/SQLite: 42 tests, 40 passed, 2 skipped for the same opt-in integration paths.
- With both opt-in flags enabled against the isolated PostgreSQL test database, all 42 Django tests ran and passed, including synthetic HTTP persistence and real local-demo Django-to-FastAPI-to-Qdrant/Ollama persistence.
- Django system check: no issues.
- `makemigrations --check --dry-run`: no changes detected.
- Container `pip check`: no broken requirements (only a harmless warning that the unprivileged user cannot write pip's cache directory).
- Docker Compose configuration parse: passed.

## Live evidence

- Gunicorn and WhiteNoise container healthy; admin CSS/JS and Satell CSS/JS returned HTTP 200.
- FastAPI health 200, authenticated readiness 200, invalid service credential 401.
- 20-question real browser evaluation: 12 verified, 4 partial, 1 abstained, 3 failed; no mock answers.
- Post-refresh user-facing RAG browser workflow passed, including citation, copy, history, CSRF, refusal, responsive navigation, and logout checks.
- Isolated Qdrant prompt-injection probe passed and left the production collection unchanged.
- 2- and 3-request measured browser bursts returned complete real assistant messages.

Exact non-destructive commands:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml exec -T -e POSTGRES_TEST_DB=satell_phase5_final_pg django python manage.py test
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml exec -T -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/satell_phase5_final.sqlite3 django python manage.py test
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/phase5_isolated_qdrant_injection.py
```

The opt-in Django integrations ran against isolated test databases; synthetic responses were explicitly tagged and the live test used the already configured local demo path. No tests were weakened.
