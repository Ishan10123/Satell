# Phase 6C Docker candidate validation

## Build and runtime

Both candidate images built successfully from the current workspace:

- `satell-django:phase6c-candidate` — Linux/amd64, image ID `sha256:070c8e5e87b155696848d77ec542ff99a3fd04bcdb2804bc0969695635acfc29`, raw image size 276,779,970 bytes (Docker Scout compressed size 60 MB).
- `satell-rag-api:phase6c-candidate` — Linux/amd64, image ID `sha256:c0ee2de84c02feb225e5ad0660d607dbea78d07b23695b91cd5a496ebf0c9153`, raw image size 591,623,395 bytes.

`docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml config --quiet` passed. Django `collectstatic` ran during image build. `pip check` passed in each build before build tooling was removed from runtime images.

Container inspection confirmed Django UID 10001 and API UID 10002. Both candidate containers used a read-only root filesystem and temporary writable filesystems. Runtime checks found no `.env`, SQLite database, tests, or docs copied into the images. Candidate Django alone bound to loopback (`127.0.0.1:8002`); FastAPI had no host-published port. No existing service container was recreated.

## Private networking and readiness

Candidate Django ↔ candidate FastAPI used a separate Docker internal network with service alias `rag-api`; Django also joined the existing app/PostgreSQL network. FastAPI joined the existing Qdrant private network and chat bridge and received the Docker host-gateway mapping for Ollama. The exact API DNS name is `rag-api:8000`. Qdrant and Ollama returned HTTP 200 from the API container. Authenticated candidate `/ready` returned HTTP 200. Candidate Django startup authenticated to API readiness and PostgreSQL before serving; its health check became healthy.

The first candidate readiness check failed closed because `Dockerfile.rag-api` omitted `knowledge_base/metadata/qdrant_indexes/rag_docs_v2.json`. That metadata file is now copied explicitly. No Qdrant collection, payload, or point was changed. The temporary `rag-api-candidate` alias was not added to the application's HTTP allowlist; the final isolated topology uses the already-supported exact DNS alias `rag-api`.

## Docker Scout

Final candidate scans reported **0 Critical / 6 High** for both images. Findings are four OpenSSL entries (`CVE-2026-107493`, `CVE-2026-84786`, `CVE-2026-121482`, `CVE-2026-107496`) and two glibc entries (`CVE-2026-19499`, `CVE-2026-5435`). Scanner package versions: OpenSSL `3.5.7-1~deb13u3` with no fixed version reported; glibc `2.41-12+deb13u4`, fixed version `2.41-12+deb13u5` reported. These findings block candidate promotion pending remediation/rescan or security exception.

## Result

Build, contents, least-privilege identity, health, and private connectivity checks passed. Security scan did not pass release policy due to the six High findings. Candidate containers are temporary acceptance services; existing containers and data stores remain intact. See [blockers](phase6c_final_blockers.md).
