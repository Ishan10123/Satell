# Repository cleanup inventory

## Inventory method and classification

Enumerated 33,052 filesystem entries (about 1.04 GB) under `E:\RAG_Project`, excluding `.venv`, `.git`, Python caches, and pytest cache. The repository is not a Git checkout in this environment, so the inventory is a filesystem inventory, not a tracked-file list. Top-level counts:

| Area | Files | Classification |
|---|---:|---|
| `knowledge_base/` | 32,472 | Raw/source corpus, manifests, inventories, logs, and related generated/index metadata. Preserve; runtime API needs selected metadata/config paths, not a Django image copy. |
| `docs/` | 302 | Academic handbook and historical engineering evidence. Preserve. |
| `django_app/` | 89 | Django runtime code, templates, migrations, tests, local SQLite DB, local `.env`, compose and developer assets. Runtime image includes only explicit application packages and required migration/template/static files; tests/local DB/env are excluded from build context. |
| `evaluation/` | 50 | Evaluation datasets and artifacts. Preserve outside Django runtime. |
| `src/` | 44 | RAG runtime source. Used by the separate API image; not copied into Django image. |
| `scripts/` | 36 | Development, ingestion, audit, and operator scripts. Preserve; not part of Django runtime image. |
| `tests/` | 27 | RAG test code. Preserve outside runtime image. |
| `configs/` | 9 | Runtime/index configuration. API image dependency; not copied into Django image. |
| `assets/` | 4 | Runtime tokenizer assets for API. Not copied into Django image. |
| `logs/` | 3 | Generated diagnostics/log artifacts. Preserve for evidence policy; exclude from Django image. |

Remaining root files include Dockerfiles, requirements, inventory/build scripts, README, `.dockerignore`, and infrastructure metadata. Extension counts are primarily JSON (13,245), Markdown (12,153), YAML (1,077), Python (897), code snapshots/examples (roughly 3,000 across Rust/TypeScript/Java/C#/Go), images, and PDFs. Counts overlap semantic roles and do not imply removals.

## Dependency/reference review and proposed deletions

No files are proposed for deletion. This avoids deleting source mirrors, license evidence, historical reports, notebooks, generated datasets, or dynamically loaded configuration without complete import/path/Compose/migration/CI references. No references were removed. The only packaging change is additive: use `django_app/` as the Django Docker context, ignore tests/local state, and copy runtime packages, templates, static assets, migrations, `manage.py`, and startup wrapper explicitly. The RAG API build context and its required configuration were not changed.

## Verification limitation

Docker packaging rules are configured, but `docker build` could not be run because `dockerDesktopLinuxEngine` was unavailable. Image contents and size reduction therefore remain **NOT_MEASURED**. No historical docs, screenshots, corpus files, approval artifacts, or reports were deleted.
