# Deployment and CI/CD readiness

## Existing-machine deployment

Compose files: `django_app/compose.yaml` and `django_app/compose.rag.yaml`. Current services are `django` and `rag-api`; PostgreSQL (`rag-postgres`) and Qdrant (`qdrant`) are external pre-existing services. Django binds host loopback 127.0.0.1:8001, FastAPI has no host port, PostgreSQL and Qdrant bindings are loopback-only in the observed runtime. Networks are `rag-app-network`, `satell-chat-rag`, and `satell-rag-service`; Ollama is reached via `host.docker.internal`. App containers use non-root users, read-only filesystems, tmpfs, dropped capabilities and `no-new-privileges`.

The existing deployment is not a clean-machine package: it depends on existing networks, volumes/data, host Ollama/model assets and local secrets. Candidate `Dockerfile.rag-api` and `django_app/Dockerfile` pin the Python base image digest, patch zlib to the scanned fixed Debian package, verify dependencies during build, and omit build package tooling from runtime images. Compose configuration validation passed; this does not validate remote TLS deployment or disaster recovery. Candidate image digests have not been promoted to the running services.

## Pipeline proposal

1. Resolve immutable dependency locks and image base digests; produce SBOM and scan reports. Candidate scans currently retain three high OpenSSL findings each.
2. Build signed images from reviewed source; store by digest.
3. Validate required environment schema and provision secrets from approved manager.
4. Verify production index manifest and authorization before starting query service.
5. Apply backward-compatible migrations using a single controlled job and backup checkpoint.
6. Deploy canary/blue-green app and API; run health/readiness and synthetic contract checks.
7. Run an approved non-sensitive real query only after legal/production authorization.
8. Promote with observation gate; rollback app and index alias independently with documented operator command.
9. Maintain migration rollback compatibility and retain prior images/index versions.

## CI/CD status

No validated CI/CD pipeline or clean-machine rehearsal was evidenced. No platform was selected or configured. Do not create cloud resources. Required checks: unit, Django SQLite/PostgreSQL staging, API contract, authorization fail-closed, migration plan, static/security tests, SBOM/vulnerability policy, image digest attestation, configuration lint, and deployment smoke test. Protect fixtures and secrets; never point CI at existing persistent data or production Qdrant.

## Gate

**PARTIAL/BLOCKED.** Local Compose runs and config validates. Remote TLS, immutable image provenance, secret provisioning, clean host bootstrap, rollback and CI/CD remain unverified.
