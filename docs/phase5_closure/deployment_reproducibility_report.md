# Deployment reproducibility

## Existing machine

This project can rebuild/restart only the application services while reusing the existing PostgreSQL, Qdrant, Ollama, named volume, and external Docker networks. The setup expects `django_app/.env` to already contain matching credentials and expects the existing `rag-app-network` and `satell-chat-rag` networks. It binds the Django UI and existing data-service host ports to loopback; FastAPI has no published host port. Ollama remains a Windows-host service reached from the private container network.

Safe preflight/start commands from `E:\RAG_Project`:

```powershell
docker network inspect rag-app-network
docker volume inspect rag_postgres_data
docker inspect rag-postgres --format '{{.State.Status}} {{.State.Health.Status}}'
docker inspect qdrant --format '{{.State.Status}} {{.State.Health.Status}}'
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml config --quiet
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --build rag-api django
```

The existing `rag-postgres` container's old environment metadata was replaced safely and now matches the rotated environment configuration. `infrastructure/postgres.compose.yaml` documents its local layout, but is not required during ordinary application restarts.

## Fresh machine

**Not reproducible from this repository alone.** A fresh host needs Docker Desktop/Compose, provisioned secrets, the existing PostgreSQL backup or a deliberately initialized new database, a compatible Qdrant collection plus manifests/registries, the pinned Ollama models, and the external Docker network topology. This repository does not contain the user's full infrastructure/bootstrap and model-provisioning procedure. Do not create an empty database or collection and mistake it for a restored deployment. First obtain/verify backups and operator-provisioned authorization assets, create required external networks/volumes explicitly, restore into them, then run the same readiness checks. Never use `down -v` or remove/recreate existing collections as a shortcut.

Detailed existing-machine steps remain in `docs/phase5/startup_guide.md` and `docs/phase5/backup_recovery_guide.md`.
