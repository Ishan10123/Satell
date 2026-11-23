# Deployment and operations

This describes the existing local Windows/Docker setup, not a portable production installer.

## Startup and health

From `E:\RAG_Project` in PowerShell:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --build rag-api django
Invoke-WebRequest http://127.0.0.1:8001/accounts/login/ -UseBasicParsing | Select-Object StatusCode
docker inspect django_app-django-1 --format '{{.State.Health.Status}}'
docker inspect django_app-rag-api-1 --format '{{.State.Health.Status}}'
docker exec django_app-django-1 python manage.py shell -c "from django.conf import settings; import httpx; print(httpx.get(settings.RAG_API_BASE_URL + '/ready', headers={'Authorization': 'Bearer ' + settings.RAG_API_TOKEN}, timeout=10).status_code)"
Invoke-RestMethod http://127.0.0.1:6333/collections/rag_docs_v2 | Select-Object status, result
```

Do not use `docker compose down -v`. Stop only app services:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml stop django rag-api
```

## Runtime and deployment facts

Django: Gunicorn plus WhiteNoise static assets. FastAPI: Uvicorn service on the private network, not host-published. PostgreSQL and Qdrant are separate existing services with persistent data. Ollama runs on the Windows host. Django is synchronous; current single worker serializes long generation requests. Health checks distinguish liveness and authenticated readiness. Readiness can fail when model, Qdrant, index or authorization prerequisites fail.

## Configuration and secrets

Runtime configuration comes from environment and JSON config. `django_app/.env` is sensitive; never print, commit or replace it. Commands above use it only as Compose input. Rotate service secrets through a planned coordinated procedure, not an ad hoc container edit. Image tags include mutable upstream tags, so reproducible deployment needs digest pinning and a reviewed lock/SBOM.

### Password-reset email

Account recovery requires Django to receive SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_USE_TLS or SMTP_USE_SSL, SMTP_FROM_EMAIL, and PUBLIC_APP_BASE_URL through environment configuration. Do not place credentials in templates or source control. The local setup currently has SMTP_HOST unset; Django emits accounts.W001 and will not pretend that reset email was delivered. Use HTTPS and a matching public base URL remotely. Tests using Django’s in-memory email backend verify token behavior but do not prove live mail delivery.

## Backup, recovery and incident operations

Follow `docs/phase5/backup_recovery_guide.md`. Before any schema/data operation: verify backup completion and restore viability, record counts, and have a rollback plan. Current documentation does not establish automated off-host backups, tested RPO/RTO, or an incident-response rotation. Those remain blockers for remote deployment.

## Clean machine gap

The project is coupled to existing Docker networks, volumes, host Ollama, local models/assets, and operator-created environment. There is no verified fresh-host bootstrap that safely provisions all services, keys, model files, registry signing material and data. Do not claim one-command reproducibility.
