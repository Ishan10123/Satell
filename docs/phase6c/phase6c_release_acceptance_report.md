# Phase 6C release acceptance and integration closure

**Assessment date:** 2026-11-23  
**Decision:** Local academic demo path validated on isolated candidates. Private/public release is **NOT READY**. Phase 7 has not started.

## Accepted evidence

- Candidate Django and FastAPI images built and ran as non-root users with read-only root filesystems. Candidate health checks were healthy.
- FastAPI authenticated `/ready` returned 200 after adding its required Qdrant compatibility manifest to the runtime image. Candidate Django startup passed its PostgreSQL and authenticated FastAPI readiness checks.
- Candidate services used a dedicated private internal network for Django ↔ FastAPI; FastAPI also joined the existing private Qdrant network and used the configured host-gateway path to local Ollama. No FastAPI port was published. Candidate Django was bound only to `127.0.0.1:8002`.
- Chrome workflows ran against candidate Django and an isolated PostgreSQL test database. A real documentation query went through candidate Django → candidate FastAPI → Qdrant → Ollama → verifier and persisted one citation. It was non-synthetic and **partially verified**.
- Django suites passed on SQLite and PostgreSQL; the RAG suite passed. See [test report](phase6c_test_report.md).
- The creator editor is now bound to the verified active owner account after additive profile migrations. See [ownership report](phase6c_creator_profile_ownership_report.md).

## Not accepted for deployment

- Production authorization is blocked: the 14 source legal reviews remain pending and the document approval registry remains absent. The manifest remains `operator_authorized_unreviewed`; production mode remains fail-closed.
- Docker Scout reported **6 High, 0 Critical** vulnerabilities for each candidate image (four OpenSSL, two glibc). Current OpenSSL has no scanner-reported fixed version; glibc has a newer fixed version. Remediate and rescan before promotion or record an explicit security exception.
- SMTP is not configured; no real recovery email was delivered. The current local public base URL is HTTP, not suitable for deployed reset links.
- Backup/recovery drill, monitoring, TLS/reverse proxy, deployment hardening and operational incident procedures are not release-validated.
- The candidate stack was not promoted. Existing app/API containers and existing PostgreSQL/Qdrant services remain untouched.

## Data preservation

Qdrant collections/points, Qdrant volume, PostgreSQL volume, source decisions, document decisions, and index manifest were preserved. The application database received only the additive profile/verification migrations and the explicitly requested owner binding. Automated PostgreSQL tests used a separate uniquely named test database and it was retained.

## Decision

- **Supervised local academic demonstration:** ACCEPTED WITH LIMITATIONS; use only the signed local demo scope and label partial/abstained answers accurately.
- **Private or public production release:** BLOCKED.
- **Phase 7:** stop until the blockers in [final blockers](phase6c_final_blockers.md) are cleared and reviewed.

Detailed records: [Docker](phase6c_docker_validation_report.md), [PostgreSQL](phase6c_postgresql_integration_report.md), [SMTP](phase6c_smtp_delivery_validation.md), [browser](phase6c_browser_acceptance_report.md), [security](phase6c_final_security_regression_report.md).
