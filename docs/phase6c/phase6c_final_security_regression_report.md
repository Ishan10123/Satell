# Phase 6C final security regression report

## Passed controls

- Candidate Django and FastAPI run under non-root users (UIDs 10001 and 10002) with read-only root filesystems; only bounded temporary filesystems are writable.
- Runtime image checks found no `.env`, SQLite DB, tests or docs copied into either image. Django is published only on host loopback for local acceptance; FastAPI has no host-published port.
- Candidate Django ↔ FastAPI used an isolated internal Docker network. FastAPI joined the private Qdrant network and got explicit host-gateway access for Ollama; neither internal service was exposed on a public interface.
- API bearer authentication, signed local-demo registry checks, authorization filters, citation validation, claim verification and production fail-closed checks were not weakened.
- All 14 legal source statuses, document decisions, index manifest, Qdrant points, and persistent volumes were preserved.
- Django tests and RAG regression tests passed; ownership isolation and trusted metadata tests remained in the suite.

## Release security blockers

Docker Scout found 0 Critical and 6 High findings on each candidate: four OpenSSL and two glibc. Current OpenSSL scanner findings report no fixed package version; glibc has a newer fixed package version. See [Docker validation](phase6c_docker_validation_report.md) for exact IDs and versions.

Production authorization remains blocked by pending legal reviews and the absent document approval registry. Local academic demo signatures do not establish a legal license decision. SMTP and HTTPS deployment configuration are incomplete. Production backup/recovery and monitoring controls remain unverified.

## Scope limits

This regression report validates the candidate configuration and tests. It is not a penetration test or production security certification. Existing runtime services were not restarted or replaced. No secret values are included in the report.
