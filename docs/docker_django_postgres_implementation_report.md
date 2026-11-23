# Dockerized Django + PostgreSQL Integration Report

**Date:** 2026-11-18  
**Project:** `E:\RAG_Project`  
**Result:** Django is running in its own Docker service and connected to the existing PostgreSQL container. Django migrations applied, all 15 tests passed against PostgreSQL, and the web login page returned HTTP 200.

## Implemented architecture

- Added `django_app/Dockerfile` using `python:3.13-slim`. It installs only the Django application's pinned dependencies (`Django`, `httpx`, and `psycopg[binary]`), copies only `django_app/`, runs as an unprivileged user, and does not install the larger RAG requirements set.
- Added `django_app/compose.yaml` with exactly one service: `django`. It has no PostgreSQL or Qdrant service definition and no volume declaration.
- Django joins the pre-existing external network `rag-app-network`. The running PostgreSQL container is named `rag-postgres` and advertises Docker network alias `postgres`; Django connects using `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`.
- Database name, user, and password are required Compose environment substitutions. The values used for this run were read in-memory from the existing `rag-postgres` container configuration; no credentials were added to files or printed in command output.
- `DJANGO_SECRET_KEY` is also required through the environment. `RAG_ADAPTER=mock` remains enabled; this milestone does not call the RAG service or change its authorization gate.
- Preserved explicit SQLite configuration for local tests by `DJANGO_DB_ENGINE=sqlite`. The PostgreSQL test database name is configurable through `POSTGRES_TEST_DB`.
- Changed the Django timezone default to `Asia/Kolkata`, which is recognized by the Linux image. The earlier `Asia/Calcutta` default raised a Django settings error inside the container before any database connection.
- Bound the Django port only to host loopback at `127.0.0.1:8001`. The Compose service runs the Django development server; it is a development milestone, not a production server deployment.
- Container protections include a non-root UID, read-only root filesystem, temporary `/tmp`, dropped Linux capabilities, `no-new-privileges`, and a login-page health check.

## Existing resources verified and preserved

Before implementation, Docker inspection showed:

- `rag-postgres`: `postgres:17-alpine`, running and healthy.
- PostgreSQL database: `rag_application`; no user tables existed before the Django migration.
- Existing network: `rag-app-network` (bridge network); the PostgreSQL container's `postgres` network alias resolved to this container.
- Existing volume: `rag_postgres_data`, mounted at `/var/lib/postgresql/data` in `rag-postgres`.
- Qdrant container: `qdrant` was running before and after. It was not attached to the Compose service, started, stopped, or otherwise changed by this task.

The Compose file declares only the external network and Django. It does not declare, recreate, remove, or reset `rag-postgres`, `rag_postgres_data`, or Qdrant. The Django migration was applied to `rag_application`, which was verified to have no public application tables before this work. It now contains the Django auth/session/admin and conversation tables. The unique test DB `rag_django_test_20261118` did not exist before testing; Django created it for the test run and removed it afterward. No test database remains.

## Build output

Command:

```powershell
docker compose -f django_app/compose.yaml build django
```

Result: **Image `django_app-django:latest` built successfully.** Docker downloaded `python:3.13-slim`, installed `Django==5.2.13`, `httpx==0.28.1`, `psycopg==3.3.9`, and the Linux `psycopg-binary==3.3.9` wheel, created the `django` system user, and copied the Django project. The final build output ended with `Image django_app-django Built`.

The first container migration attempt exposed the timezone alias issue and stopped before PostgreSQL was touched. After changing to `Asia/Kolkata`, the image rebuilt and the migration succeeded.

## Migration output

Command:

```powershell
docker compose -f django_app/compose.yaml run --rm django python manage.py migrate --noinput
```

Result: **All migrations applied successfully** in `rag_application`:

- `contenttypes.0001_initial`, `contenttypes.0002_remove_content_type_name`
- `auth.0001_initial` through `auth.0012_update_proxy_permissions`
- `admin.0001_initial` through `admin.0003_logentry_add_action_flag_choices`
- `conversations.0001_initial`
- `sessions.0001_initial`

Post-migration inspection found the expected Django tables, including `conversations_conversation`, `conversations_message`, `conversations_citationsnapshot`, and `conversations_generationmetadata`.

## PostgreSQL test output

The isolated database name `rag_django_test_20261118` was checked to be absent before the test run. The tests ran in a one-off Django container connected to the same PostgreSQL host/database configuration; Django created and dropped only that isolated test database.

Command:

```powershell
docker compose -f django_app/compose.yaml run --rm django python manage.py test accounts conversations chat rag_client --noinput --verbosity 1
```

Result:

```text
Found 15 test(s).
System check identified no issues (0 silenced).
Ran 15 tests in 2.605s
OK
Destroying test database for alias 'default' ('rag_django_test_20261118')...
```

This is the same 15-test Django suite previously run on SQLite, now verified against PostgreSQL. The Django service also passed its health check, and `GET http://127.0.0.1:8001/accounts/login/` returned HTTP 200.

## Changed files in this Docker/PostgreSQL milestone

- `django_app/Dockerfile` — minimal Linux Django image and unprivileged runtime.
- `django_app/compose.yaml` — Django-only service using required environment variables and external `rag-app-network`; PostgreSQL endpoint is `postgres:5432`.
- `django_app/requirements-docker.txt` — minimal container dependencies, including Psycopg binary for Linux.
- `django_app/config/settings.py` — configurable PostgreSQL test DB name and Linux-compatible timezone default; SQLite remains available.
- `docs/django_application_foundation_report.md` — updated to record that Docker verified PostgreSQL after the native Windows driver restriction.
- `docs/docker_django_postgres_implementation_report.md` — this implementation/build/migration/test record.

The root `requirements.txt`, RAG source, RAG tests, Qdrant collection/data, approval registries, and authorization manifests were not changed in this milestone.

## Start and test procedure

Compose requires the database variables to be in the calling PowerShell process. For this existing container, load them without printing values:

```powershell
$raw = docker inspect --format '{{json .Config.Env}}' rag-postgres
$items = ConvertFrom-Json -InputObject ($raw -join '')
foreach ($name in @('POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD')) {
    $entry = $items | Where-Object { $_.StartsWith($name + '=') } | Select-Object -First 1
    if (-not $entry) { throw "Missing $name from rag-postgres." }
    [Environment]::SetEnvironmentVariable($name, $entry.Substring($name.Length + 1), 'Process')
}
$env:POSTGRES_HOST = 'postgres'
$env:POSTGRES_PORT = '5432'
$env:DJANGO_DB_ENGINE = 'postgresql'
$env:DJANGO_SECRET_KEY = '<supply from your secret manager or process environment>'
$env:DJANGO_DEBUG = '0'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1'
$env:POSTGRES_TEST_DB = 'rag_django_test_20261118'
$env:DJANGO_HOST_PORT = '8001'
$env:RAG_ADAPTER = 'mock'
```

Do not type the placeholder as a real value; provide a secret through the local process environment or a secret manager. Then run:

```powershell
docker compose -f django_app/compose.yaml config --quiet
docker compose -f django_app/compose.yaml build django
docker compose -f django_app/compose.yaml run --rm django python manage.py migrate --noinput
docker compose -f django_app/compose.yaml up -d django
docker compose -f django_app/compose.yaml run --rm django python manage.py test accounts conversations chat rag_client --noinput --verbosity 1
docker compose -f django_app/compose.yaml ps
```

For the already running service, its current `DJANGO_SECRET_KEY` remains in its container environment. A later Compose invocation can reuse it without displaying it by reading the `DJANGO_SECRET_KEY=` entry from `docker inspect django_app-django-1` into the calling process environment.

## Remaining work and limits

- The Dockerized app currently uses Django's development server. Select a production WSGI/ASGI server and deployment policy in a separate milestone.
- Configure durable secret management, HTTPS, secure cookies, allowed hosts, and CSRF trusted origins for any non-local deployment.
- The current browser adapter stays in mock mode. Switching to HTTP does not bypass the existing FastAPI authorization rule; the current `operator_authorized_unreviewed` index remains blocked for production queries.
- Django conversation history is persisted but is not sent to the current stateless FastAPI query endpoint.
- No RAG service, Qdrant, source approval, indexing, or retrieval changes were performed.

## Review patch

The project directory is not a Git working tree, so a Git-native unstaged diff is unavailable. The companion `docs/docker_django_postgres_changes.patch` contains the Docker and settings source patch; the implementation and foundation report updates are provided as separate review documents.
