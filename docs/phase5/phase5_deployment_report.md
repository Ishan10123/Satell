# Phase 5 deployment report

## Current local topology

- Django: container `django_app-django-1`, host binding `127.0.0.1:8001`, networks `rag-app-network` and `satell-chat-rag`.
- FastAPI: container `django_app-rag-api-1`, port 8000 is not published to the host, networks `satell-chat-rag` and `satell-rag-service`.
- PostgreSQL: reused `rag-postgres`, existing `rag_postgres_data`, loopback host port only, on `rag-app-network`.
- Qdrant: reused `qdrant`, existing `qdrant_storage`, loopback host ports only, on `satell-rag-service`.
- Ollama: Windows host runtime reached from FastAPI through `host.docker.internal:11434`; real browser queries confirmed the path.

## Implemented and verified

- Built updated Django and FastAPI images; recreated only those two application containers.
- Django starts through `startup.py`, which retries the PostgreSQL connection and authenticated FastAPI `/ready` with bounded attempts. Compose waits for FastAPI container health first.
- Both app containers use non-root users, read-only root filesystems, dropped capabilities, `no-new-privileges`, health checks, and restart policies.
- Compose configuration validates with the existing external networks. The RAG API has no host port mapping. Django is loopback-bound.
- FastAPI `/health` container health and authenticated `/ready` returned success. Django health was healthy. The Qdrant collection returned green.
- Existing database volumes, networks, Qdrant collection, and data services were not recreated.

## Reproduce

From PowerShell at `E:\RAG_Project`:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml config --quiet
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --build rag-api django
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/accounts/login/ | Select-Object StatusCode
docker inspect django_app-django-1 --format '{{.State.Health.Status}}'
docker inspect django_app-rag-api-1 --format '{{.State.Health.Status}}'
docker exec django_app-rag-api-1 python -c "import os,urllib.request; r=urllib.request.Request('http://127.0.0.1:8000/ready',headers={'Authorization':'Bearer '+os.environ['RAG_API_TOKEN']}); print(urllib.request.urlopen(r,timeout=10).status)"
Invoke-RestMethod http://127.0.0.1:6333/collections/rag_docs_v2 | Select-Object status, result
```

Stop only the application services:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml stop django rag-api
```

## Limitations

This project composes only Django and FastAPI and depends on already existing PostgreSQL/Qdrant containers, external networks, volumes, Windows Ollama, local models, and the local `.env`. It is not a clean-machine deployment bundle. Do not run `down -v`; avoid using `down` because external service lifecycle belongs to the existing infrastructure. Development static assets are served with `runserver --insecure`, so replace that before any private deployment. No public service exposure was added.
