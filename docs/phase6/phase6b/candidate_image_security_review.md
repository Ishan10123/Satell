# Phase 6B candidate image security review

## Candidate image configuration

| Image | Digest | Runtime user | Exposed container port | Image-embedded healthcheck |
|---|---|---|---|---|
| Django | `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9` | `django` | 8000/tcp | None |
| FastAPI | `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78` | `ragapi` | 8000/tcp | None |

The 8000/tcp image metadata does not itself publish a host port. The Compose definitions provide health checks: Django polls its login page and FastAPI polls `/health`. For this direct candidate run, health/readiness endpoints were checked manually. No image-level `HEALTHCHECK` instruction exists.

## Runtime security controls observed in the candidate test containers

- Django and FastAPI ran as their non-root image users.
- Both app containers used read-only root filesystems, `cap_drop: ALL`, and `no-new-privileges`.
- Django was published only to `127.0.0.1:18081`; FastAPI had no host port.
- The disposable PostgreSQL and Qdrant containers had no host port bindings and used tmpfs for their data. They were reachable only on the temporary Docker bridge.
- FastAPI reached Ollama using `host.docker.internal:11434`; this was tested with a successful health check and real model query. Host firewall/bind-address policy was not independently audited.
- The staging bridge was non-internal to permit the Windows-host gateway route. No internal service was published publicly, but outbound network policy for that bridge was not constrained or measured.
- Candidate browser HTML contained neither the `RAG_API_TOKEN` variable name nor the isolated service token.
- Candidate image configuration contained no RAG API token or PostgreSQL password. Temporary test credentials were supplied to runtime containers and not written to image layers. No credential was included in this report.
- Runtime writable paths for the application containers were limited to tmpfs `/tmp` and (for the API compose service) its configured logs tmpfs. The temporary database/vector data were discarded with their containers.

## Dependency and layer review

- CycloneDX SBOMs are attached under `evidence/`.
- `pip`, `setuptools`, and `wheel` are absent from both SBOM component lists.
- Python TLS requires the installed OpenSSL libraries; `ldd` confirms `_ssl` links to `libssl.so.3` and `libcrypto.so.3` in both images.
- Dockerfiles share a pinned Python 3.13 slim base digest. OpenSSL is inherited from the Debian Trixie base, not from the application dependency installation step.
- Three High OpenSSL findings remain on each candidate; see the CVE assessment. No suppression or version override was applied.

## Reliability checks and gaps

Candidate processes started successfully. FastAPI `/health` returned 200, local-demo `/ready` returned 200, the production-mode `/ready` returned 503, and Django’s login endpoint returned 200. A real local-model query, citation validation, verifier success, PostgreSQL persistence, and fail-closed abstention were exercised.

Graceful container shutdown behavior was not explicitly tested. The staged candidate services used direct `docker run` rather than the full Compose project, so Compose healthchecks and restart policies were inspected in configuration but were not active on those containers. The host-side Ollama network exposure and bridge egress policy need a separate host/deployment review. These gaps, plus the OpenSSL findings, prevent a production security conclusion.
