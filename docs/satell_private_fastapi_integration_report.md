# satell Private FastAPI Service Integration Report

**Date:** 2026-11-18  
**Scope:** private Docker service and synthetic integration only. This does not certify production RAG readiness.

## Readiness summary

The FastAPI image builds and the authenticated API process runs on private Docker networks with no published host port. Django resolves the API service name and can reach its liveness endpoint. A separate synthetic-only HTTP fixture was used to verify bearer authentication, request/response compatibility, correlation propagation, and Django persistence of the synthetic answer, citation, and generation metadata.

The real query path remains fail-closed. The index manifest is still `operator_authorized_unreviewed`, all 14 source decisions remain pending, and `knowledge_base/metadata/document_approvals.json` is absent. Authenticated `/ready` and `/v1/query` requests to the real API return 503 before retrieval. Django still selects `RAG_ADAPTER=mock`. No real corpus query was run.

## Architecture and network topology

```text
Browser --loopback host port--> Django
                                  |
                          satell-chat-rag
                           /           \
                       Django          FastAPI
                                          | \
                             satell-rag-service \
                                   |              \
                                 Qdrant       host.docker.internal
                                                  |
                                      Windows Ollama (loopback bind)
```

- `satell-chat-rag` is a dedicated Docker bridge for Django and FastAPI. FastAPI uses Docker Desktop's `host.docker.internal:11434` gateway to reach the Windows Ollama listener. The listener remains bound to Windows `127.0.0.1:11434`; this was verified by an HTTP version request from the API container. No Ollama host bind change was made.
- `satell-rag-service` is an internal Docker network shared by FastAPI and the existing Qdrant container. A read-only request to `http://qdrant:6333/collections/rag_docs_v2` returned 200. Django is not attached to this vector network.
- FastAPI has no `ports` mapping (`8000/tcp` is container-only). Qdrant remains host-bound to `127.0.0.1:6333-6334`; PostgreSQL remains host-bound to `127.0.0.1:5432`.
- The existing Django container was rebuilt and attached to the dedicated app network. The PostgreSQL and Qdrant containers were not recreated or restarted.
- The chat-to-RAG bridge is not Docker `internal`, because Docker Desktop's internal network could not reach the host's loopback Ollama endpoint. It has no inbound host port mapping, but ordinary bridge outbound egress is available. Restricting all egress to only the host gateway would require an additional host/network firewall policy and remains an operational hardening task.

## Service configuration and controls

- `Dockerfile.rag-api` builds from Python 3.13 slim, installs the pinned API runtime set from `requirements-api.txt`, runs as UID 10002, and copies only application code, selected configs, metadata and the tokenizer asset. It does not copy raw corpus files or reranker model weights.
- `django_app/compose.rag.yaml` defines `rag-api` separately from Django, attaches it only to the app and vector networks, publishes no ports, uses a read-only root filesystem, drops capabilities, enables `no-new-privileges`, and checks `/health` for liveness.
- A 32-byte random runtime bearer credential was generated for this local service start. It was not given to Django, printed, or written to the repository. Compose requires an operator-supplied `RAG_API_TOKEN` when the service is next created with Compose. Tenant and principal values are server-side configuration; browser input cannot set them.
- `RAG_API_BIND_HOST` accepts only `127.0.0.1` or `0.0.0.0`; the container uses the latter internally. The API's default remains loopback for direct local runs.
- Ollama URL overrides are accepted only for loopback or the exact `host.docker.internal:11434` target. Qdrant accepts loopback or the exact `qdrant:6333` Docker target. These do not permit arbitrary remote hosts.
- Existing API bearer authentication, request limits, rate limit, server-derived access scope, index validator, source approval checks, document rejection filters, and generation verification were left in place.
- `GET /health` is liveness only. Authenticated `/ready` performs production index/dependency readiness and returns 503 for the current unreviewed manifest.
- API response now has an optional `synthetic` boolean, false on real API responses. Django strictly validates this field, records fixture responses as synthetic, and labels them in response details. Correlation IDs matching a bounded safe character set are preserved through the API response body and headers.

## Synthetic integration path

The synthetic fixture is a separate minimal container image (`Dockerfile.synthetic-rag-test`, `requirements-synthetic-api.txt`) that contains only FastAPI, Uvicorn, Pydantic, and `scripts/synthetic_rag_test_api.py`. It has no RAG modules, Qdrant, Ollama or corpus metadata in the image. The fixture accepts the same bounded query shape, requires a bearer token, returns one explicitly synthetic citation, and echoes a validated correlation ID. It is only enabled with Compose profile `synthetic-test` and was stopped after validation.

The opt-in Django test `django_app/conversations/test_synthetic_http_integration.py` sends a message through the real Django view and HTTP client to that fixture, then checks the saved answer, citation snapshot, request ID, retrieval mode, synthetic verification status, and rendered synthetic label. It passed against PostgreSQL. Existing client unit tests cover invalid responses, upstream errors and timeouts; live fixture authentication was also checked (valid 200, invalid 401).

## Authorization and index state

Read-only checks after service validation showed:

- 14 source approvals, all 14 `pending_review`.
- `knowledge_base/metadata/document_approvals.json` does not exist.
- Manifest authorization mode remains `operator_authorized_unreviewed`.
- Qdrant `rag_docs_v2` status is green with 58,856 points.
- With valid API authentication, `/ready` and `/v1/query` return 503. With invalid authentication, `/ready` returns 401. The rejected query was a synthetic gate-check prompt and was denied before retrieval.
- Django runtime setting remains `RAG_ADAPTER=mock`.

No source or document approval, manifest, index, Qdrant collection, or persistent Qdrant volume was changed. Django integration tests created and dropped a separate temporary PostgreSQL test database; application database rows were not modified by those tests.

## Changed files

- `.dockerignore` — excludes local environments, raw corpus and unrelated assets from the API build context; explicitly includes required configs, metadata, source and tokenizer assets.
- `Dockerfile.rag-api` — minimal non-root FastAPI image.
- `Dockerfile.synthetic-rag-test`, `requirements-synthetic-api.txt` — isolated minimal fixture image with no RAG code or index data.
- `requirements-api.txt` — pinned API runtime dependencies without Django or PostgreSQL client dependencies.
- `django_app/compose.rag.yaml` — private FastAPI and synthetic fixture services, health checks and network declarations.
- `django_app/compose.yaml` — attaches Django to the private app network while keeping its existing loopback-only host port and mock adapter.
- `scripts/run_api.py` — container-safe bind host and environment-based local Ollama URL override.
- `scripts/synthetic_rag_test_api.py` — isolated synthetic HTTP fixture.
- `src/rag_pipeline/api/app.py` — bounded correlation-ID preservation and explicit real-response synthetic flag.
- `src/rag_pipeline/configuration.py` — optional Ollama URL override while retaining checked-in config defaults.
- `src/rag_pipeline/embeddings/ollama.py`, `src/rag_pipeline/generation/ollama.py` — exact Docker Desktop host gateway allowance.
- `src/rag_pipeline/storage/qdrant_store.py` — exact private Qdrant service DNS allowance.
- `django_app/rag_client/client.py` — exact private API service names and synthetic response parsing.
- `django_app/templates/conversations/detail.html` — explicit synthetic test response label.
- `django_app/conversations/test_synthetic_http_integration.py` — opt-in end-to-end persistence test.
- `django_app/rag_client/tests.py`, `tests/test_api.py`, `tests/test_configuration.py`, `tests/test_qdrant_store.py` — regression coverage.

## Validation results

| Validation | Result |
|---|---|
| FastAPI Docker image build | Passed; `satell-rag-api:test` built, and the Compose API image built successfully. |
| FastAPI container | Healthy; `/health` 200; no host port mapping. |
| Django-to-FastAPI DNS/HTTP | Passed; `http://rag-api:8000/health` returned 200 from Django container. |
| Ollama gateway | Passed; `/api/version` returned 200 from the API container; Windows listener stayed loopback-bound. |
| Private Qdrant path | Passed; Qdrant collections endpoint returned 200 from the internal vector network. |
| API auth / production gate | Invalid bearer 401; valid bearer `/ready` 503 and `/v1/query` 503 due unreviewed-index gate. |
| Synthetic fixture auth | Invalid bearer 401; valid bearer 200 with `synthetic=true` and correlation echo. |
| Django synthetic persistence | Passed, 1 test against PostgreSQL; synthetic answer, citation, metadata and label persisted. |
| Django full suite, PostgreSQL | 31 tests, passed; 1 opt-in integration test skipped in the general run and passed separately. |
| Django full suite, SQLite | 31 tests, passed; 1 opt-in integration test skipped in the general run. |
| RAG regression suite | 225 tests, passed; 1 existing skip. |
| Django system check | Passed, no issues. |
| Migration check | Passed, no changes detected. |
| API image `pip check` | Passed, no broken requirements. |
| Python compileall | Passed for `src`, `scripts`, and `django_app` using a temporary bytecode cache. |
| Qdrant state | Green, 58,856 points after checks. No writes were issued. |

The RAG regression run emitted the existing Qdrant warning that payload indexes have no effect in local in-memory Qdrant tests; the suite passed.

## Remaining blockers and limitations

1. **Production source authorization is blocked.** All 14 source decisions are still pending. Each source requires the human evidence review already defined by the approval workflow.
2. **Document-level approval registry is missing.** Create/populate it through the documented human review workflow; do not replace it with an empty or permissive registry.
3. **The manifest is unreviewed.** Rebuild/review the index only after the required human decisions and a separately reviewed migration plan. The API will continue rejecting query/readiness requests until validation reports `reviewed_source_and_document_approval`.
4. **Django remains on mock.** Real HTTP adapter selection was deliberately not enabled. After authorization and explicit integration acceptance, set server-side `RAG_API_BASE_URL=http://rag-api:8000` and provide the same bearer secret to Django, then run the end-to-end authorized-corpus checks.
5. **Timeout mismatch requires a realistic service test.** Django's HTTP client default is 15 seconds, while the configured generation request may take up to 120 seconds. Keep mock selected until the request deadline policy is intentionally reconciled.
6. **Bridge egress is not firewall-restricted.** The dedicated bridge has no public inbound port and is only attached to Django/FastAPI, but ordinary Docker bridge outbound egress exists. Consider a host firewall policy before production deployment.
7. **This is not a production deployment.** No real corpus query, license decision, latency/VRAM benchmark, load/concurrency test, backup/restore test, or external security review was performed.

## Manual verification

From PowerShell at the repository root, set a fresh runtime API credential without printing it, then start the service:

```powershell
$env:RAG_API_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
docker compose -f django_app/compose.rag.yaml up -d --build rag-api
Remove-Item Env:RAG_API_TOKEN
docker ps --filter name=rag-api-1 --format "{{.Names}} {{.Status}} {{.Ports}}"
```

The displayed port list should show `8000/tcp` without a host mapping. Use a persistent secret manager or a protected, ignored local environment file for routine restarts; never commit the credential. Do not set Django to HTTP mode until source/document review is complete and integration is explicitly accepted.

The current machine already has the external networks created. On a fresh host, create the networks and attach the already-running containers without replacing them:

```powershell
docker network create satell-chat-rag
docker network create --internal satell-rag-service
docker network connect satell-chat-rag django_app-django-1
docker network connect --alias qdrant satell-rag-service qdrant
```

To rerun the synthetic-only PostgreSQL persistence check:

```powershell
$env:RAG_API_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
docker compose -f django_app/compose.rag.yaml --profile synthetic-test up -d --build rag-api-synthetic
Remove-Item Env:RAG_API_TOKEN
docker compose -f django_app/compose.yaml exec -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 -e POSTGRES_TEST_DB=rag_satell_synthetic_test django python manage.py test conversations.test_synthetic_http_integration --verbosity 2
docker stop django_app-rag-api-synthetic-1
```

The test fixture uses only synthetic content and never queries the production API or index.
