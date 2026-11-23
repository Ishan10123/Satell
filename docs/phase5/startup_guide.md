# Local startup and shutdown

Run from the repository root in PowerShell. The current deployment reuses the existing `rag-postgres`, Qdrant, volumes, and external Docker networks; it does not create duplicate infrastructure.

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --build rag-api django
```

The Django startup wrapper waits for its PostgreSQL connection and authenticated FastAPI `/ready` response. The Docker health status of FastAPI is liveness only; authenticated readiness is the stronger RAG/index check.

Django runs as a non-root Gunicorn WSGI service with WhiteNoise serving the image-collected static assets. The local health check allows up to 20 seconds for a response because its one synchronous worker can be occupied during model generation. One worker intentionally bounds concurrent inference on this GPU; the 2/3-request burst timings and limitations are in [the Phase 5 resource report](../phase5_closure/resource_and_concurrency_benchmark.md).

Open `http://127.0.0.1:8001/` and sign in with a pre-provisioned Django account. Ask a documentation question, inspect its citation cards and verification message, then return to the workspace to reopen the saved conversation.

Stop just the application services:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml stop django rag-api
```

Do not use `down -v`, remove the external networks, or remove either persistent volume. PostgreSQL, Qdrant, and Ollama service lifecycle is managed by the existing local infrastructure setup; the original infrastructure Compose project was not present in this repository, so a clean-machine bootstrap is not yet reproducible from this project alone.
