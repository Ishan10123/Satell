# Satell — Secure RAG Chat Workspace

Satell is a local academic demonstration application for asking questions over an explicitly operator-authorized documentation subset. The browser talks only to Django. Django owns authentication, conversations, messages, and citation snapshots; its server-side HTTP client calls the private FastAPI service. FastAPI applies the signed local-demo authorization scope before Qdrant retrieval, context assembly, Ollama generation, claim verification, and citation validation.

This is not a public or commercial deployment. The local academic demo policy is not legal license approval. Legal review remains pending, production authorization remains fail-closed, and the known RAG limitations are listed in [Phase 5 known limitations](docs/phase5/phase5_known_limitations.md).

## Start the existing local deployment

The current setup reuses existing PostgreSQL, Qdrant, volumes, and Docker networks. Do not replace or reset `django_app/.env`; it contains the matching local credentials. From `E:\RAG_Project` in PowerShell:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --build rag-api django
```

Open `http://127.0.0.1:8001/`. Sign in with an account already provisioned in the Django database. There is no public self-registration route.

Verify readiness:

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8001/accounts/login/ -UseBasicParsing | Select-Object StatusCode
docker inspect django_app-django-1 --format '{{.State.Health.Status}}'
docker inspect django_app-rag-api-1 --format '{{.State.Health.Status}}'
docker exec django_app-django-1 python manage.py shell -c "from django.conf import settings; import httpx; print(httpx.get(settings.RAG_API_BASE_URL + '/ready', headers={'Authorization': 'Bearer ' + settings.RAG_API_TOKEN}, timeout=10).status_code)"
Invoke-RestMethod http://127.0.0.1:6333/collections/rag_docs_v2 | Select-Object status, result
```

Stop only the Django and RAG application services while leaving the existing database and vector store running:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml stop django rag-api
```

The Compose files reference external networks and existing data services. They intentionally do not create a second PostgreSQL or Qdrant. See [the deployment report](docs/phase5/phase5_deployment_report.md) before setting up a new machine.

## Documentation

- [Complete academic and engineering handbook](docs/academic_project/README.md)
- [Local academic demo procedure](docs/phase5/academic_demo_guide.md)
- [Application architecture](docs/phase5/architecture.md)
- [Django and FastAPI API integration](docs/phase5/api_integration.md)
- [Troubleshooting](docs/phase5/troubleshooting.md)
- [Backup and recovery](docs/phase5/backup_recovery_guide.md)
- [Phase 5 reports](docs/phase5/)
- [Phase 5 closure and hardening reports](docs/phase5_closure/)
