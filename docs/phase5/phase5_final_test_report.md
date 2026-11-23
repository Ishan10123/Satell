# Phase 5 final test report

## Automated suites

| Suite | Command | Result |
|---|---|---|
| RAG pipeline | `python -m unittest discover -s tests -v` from project `.venv` | 260 run; 259 passed; 1 skipped |
| Django/PostgreSQL | `python manage.py test` in Django container with a unique temporary test DB name | 41 run; 39 passed; 2 skipped |
| Django/SQLite | `python manage.py test` in Django container with unique `/tmp` SQLite path | 41 run; 39 passed; 2 skipped |
| Python compilation | `python -m compileall -q src tests scripts` | Passed |
| Dependencies | `python -m pip check` | No broken requirements |
| Django checks | `python manage.py check` | No issues |
| Migration drift | `python manage.py makemigrations --check --dry-run` | No changes detected |
| Compose config | `docker compose ... config --quiet` | Passed |

The RAG suite skip was `test_evidence_symlink_escape_fails_closed`, because symlink creation was unavailable in this Windows environment. Django skips were the explicit live-authorization test and opt-in synthetic Docker integration test. Real RAG was instead exercised by the browser workflow and 20-query browser evaluation; the synthetic test was not counted as real RAG.

## Runtime checks

- Django and FastAPI containers healthy; authenticated FastAPI `/ready` returned HTTP 200.
- `/static/admin/css/base.css` and the Satell favicon returned HTTP 200.
- Real browser login, invalid login, conversation, real RAG answer/citation, history, CSRF, mobile navigation, secret refusal, logout, and protected redirect passed.
- Prompt injection probe passed for an isolated malicious context fixture using local Ollama; this is not a Qdrant retrieval injection test.
- Isolated PostgreSQL and Qdrant snapshot restoration tests passed.

## RAG outcomes

20 real browser questions: 12 verified, 4 partial, 1 abstention, 3 fail-closed; 16 had citations. Query-level metadata and resource samples are in `live_evaluation_results.json`. This is diagnostic evidence, not a human-judged relevance benchmark or proof of factual correctness.

## Persistence integrity

After temporary E2E/evaluation users were removed: PostgreSQL had 1 user, 7 conversations, 82 messages. Qdrant `rag_docs_v2` remained green with 58,856 points. `rag_postgres_data` and `qdrant_storage` volumes remained mounted; existing PostgreSQL and Qdrant containers stayed running. No approvals, manifest, or legal statuses were modified.
