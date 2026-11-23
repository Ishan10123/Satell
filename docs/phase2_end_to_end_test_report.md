# Phase 2 End-to-End Test Report

**Run date:** 2026-11-18

## Live path

Eight fixed prompts were submitted through `conversations:message_create` using Django's test client while the Django, FastAPI, PostgreSQL, Qdrant and Windows-host Ollama services were running. This exercised real HTTP transport and real indexed retrieval/generation; no mock adapter or synthetic response was counted. Evaluation conversation: `b56527be-f26e-469d-b200-2e79b5b00ab5`.

Runtime checks:

- Django container: healthy; host binding remained `127.0.0.1:8001`.
- FastAPI container: healthy; no host port published.
- FastAPI `/health`: 200; authenticated `/ready`: 200.
- FastAPI container → Qdrant collection endpoint: 200; exact collection count: 58,856 points.
- FastAPI container → Ollama tags endpoint: 200.
- Final evaluation: eight retrievals completed; five citation-bearing answers were persisted, two validation failures were stored as safe abstentions, and one insufficient cross-source comparison abstained before generation.
- Citation snapshots and generation diagnostics were persisted in PostgreSQL for successful RAG responses. Failure codes/stages were persisted for controlled validation failures.

## Automated tests

| Command | Result |
|---|---|
| `\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 241 run; 240 passed; 1 skipped |
| `docker exec django_app-django-1 python manage.py test --keepdb` | 34 run; 32 passed; 2 skipped (PostgreSQL) |
| `docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=:memory: django_app-django-1 python manage.py test -v 1` | 34 run; 32 passed; 2 skipped (SQLite) |
| `python manage.py check` | Passed |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `\.venv\Scripts\python.exe -m compileall -q src tests scripts` | Passed |
| `\.venv\Scripts\python.exe -m pip check` | No broken requirements |

The new tests cover: current-chunk omission-ID accounting at the max-chunk boundary; safe API error classification; Django parsing of a full 17-field diagnostic response; and rejection of malformed error-classification headers.

## Data preservation

The API and Django application images were rebuilt, then only the `rag-api` and `django` services were restarted with `up -d --no-deps`. PostgreSQL and Qdrant containers and volumes were not removed or reset. No embedding or ingestion job ran. Qdrant remained at 58,856 points. Source/legal approval records, the signed demo registries, index manifest and Qdrant payloads were not edited.

The evaluation itself added dedicated conversations/messages/citations and associated generation metadata to the existing application database. No existing conversation was deleted.

## Browser verification

Not performed. The evaluation used Django's test client inside the running Django container, not a real browser. Do not treat this report as verification of the rendered browser workflow.

## Remaining blockers

- Production retrieval remains blocked by `operator_authorized_unreviewed`, 14 pending source reviews and the missing production document approval registry.
- Two of eight prompts still fail claim-level citation validation; one cross-source prompt safely abstains because dense top-k evidence lacks FastAPI material.
- Hybrid retrieval was benchmarked read-only but not enabled; its sparse index is absent from the regular FastAPI image and its measured latency was substantially higher.
- Generation plus verification latency ranged roughly 5.4–8.5 seconds for successful responses in this sample.

Per-question payloads, retrieved IDs/scores, stage timings and citations are in [phase2_rag_evaluation_results.json](phase2_rag_evaluation_results.json); the original run is in [phase2_rag_evaluation_baseline.json](phase2_rag_evaluation_baseline.json).
