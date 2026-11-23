# Production packaging report

The Django Compose build context now resolves to `django_app/` instead of the repository root. `django_app/.dockerignore` excludes `.env*`, local SQLite files, bytecode/caches, and test modules. The Dockerfile explicitly copies configuration, accounts, conversations (including migrations and management commands), chat/static assets, RAG HTTP client, templates, `manage.py`, and the startup wrapper. It collects static files at image-build time; the service does not collect static assets per request.

This isolates the Django build from the 32,472 knowledge-base files, academic reports, screenshots, evaluation artifacts, and RAG source/configuration. No project docs or evidence were deleted. This does not alter the separate FastAPI build.

`docker build` and image-size comparison are **BLOCKED / NOT_MEASURED** because Docker Engine was not reachable (`npipe:////./pipe/dockerDesktopLinuxEngine` missing). Phase 6B also identified unresolved OpenSSL High findings in prior base-image candidates; this product change does not remediate them. A new candidate must be built, scanned, and approved before any release, and must not be promoted automatically.
