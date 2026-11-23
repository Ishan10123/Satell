# Assessment snapshot — 2026-11-19

Evidence is a dated snapshot; rerun health and authorization checks before reuse.

- Running containers observed: `django_app-django-1` healthy, `django_app-rag-api-1` healthy, `rag-postgres` healthy, `qdrant` up, and `django_app-rag-api-synthetic-1` healthy (test-only).
- Compose application services: `rag-api`, `django`.
- Host publications observed: Django `127.0.0.1:8001`; PostgreSQL `127.0.0.1:5432`; Qdrant `127.0.0.1:6333-6334`; FastAPI not published.
- Qdrant `rag_docs_v2`: green, 58,856 points.
- Index manifest: 6,565 documents, 58,856 chunks, ready; authorization `operator_authorized_unreviewed`.
- Local demo: 14 source groups; 6,458 canonical documentation IDs; 107 indexed research papers excluded.
- Legal state: 14 source decisions pending; 9,932 inventory license statuses pending; production document registry missing.
- Current PostgreSQL application count after temporary evaluation cleanup and final regression reruns: 1 user, 2 conversations, 10 messages, 14 citation snapshots.
- One live query through Django container returned HTTP 200, verified response, one citation, preserved correlation ID, and `synthetic=false`.
- Model: `qwen3.5:4b`, context 8,192, output 1,024, safety 512; embedding model `nomic-embed-text:v1.5`, 768 dimensions.
- Hardware: Windows 11, RTX 5050 Laptop 8,151 MiB, i7-13645HX, 15.7 GiB RAM.

No credential values are recorded. No Qdrant, PostgreSQL, approval or manifest mutation was performed for this snapshot.

## Final consolidation check

- 2026-11-19 rerun: RAG 263 tests (262 passed, 1 skipped for unavailable Windows symlink creation); Django 65/65 on PostgreSQL and 65/65 on isolated SQLite with live/synthetic test opt-ins.
- `manage.py check` reported only the known SMTP warning (`accounts.W001`); migrations check reported no changes.
- Current authenticated FastAPI readiness from Django returned HTTP 200 and `ready=true`; liveness returned HTTP 200.
- Direct real query attempts from the Django container returned one failed/no-citation result, followed by a verified result with two citations. Both were non-synthetic and preserved request correlation. This is direct API-path evidence, not an additional browser test.
- Qdrant remained green with 58,856 points. Application tables remained at the counts above. Production/legal authorization was not changed.
