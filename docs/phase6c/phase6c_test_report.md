# Phase 6C release acceptance test report

**Run date:** 2026-11-23  
**Scope:** release acceptance and integration closure. No Phase 7 work was started.

## Automated tests and checks

- Django/SQLite: **77 passed, 2 skipped**. The skips are opt-in integration tests.
- Django/PostgreSQL: **77 passed, 2 skipped** against a unique, previously absent test database (`rag_phase6c_test_acceptance_65872caf`). It was retained. Existing application data was not used as a test database.
- RAG suite: **273 passed, 1 skipped**. The skip is the existing Windows symlink capability check.
- Django system checks: completed with warnings `accounts.W001` (SMTP host unset) and `accounts.W002` (local public URL is HTTP).
- `makemigrations --check --dry-run`: **No changes detected**.
- Docker Compose configuration: valid with `compose.rag.yaml` and `compose.yaml` together.
- Both candidate images built. Dependency `pip check` passed during each image build; Django `collectstatic` completed during build.
- Candidate containers ran as non-root users, with read-only root filesystems and writable temporary filesystems only. Candidate Django and FastAPI health checks reached `healthy`.
- The FastAPI candidate's authenticated `/ready` returned HTTP 200 after the Qdrant compatibility manifest was added to the image. Qdrant and Ollama connectivity checks returned HTTP 200. The candidate Django startup check passed for PostgreSQL and authenticated FastAPI readiness.

## Actual browser and RAG workflow

Google Chrome, controlled by Playwright, exercised the candidate Django application at loopback port 8002 with a synthetic user in an isolated PostgreSQL test database. The broader acceptance run covered login success and rejection, conversation creation, trusted founder metadata, profile visibility, preferences, theme persistence, exports, keyboard and mobile conversation menus, rename/lock/share/revoke/delete, logout, and history after login.

A separate candidate-stack browser query passed through candidate Django → candidate FastAPI → Qdrant → Ollama → claim verification → Django/PostgreSQL persistence. It produced one citation, no synthetic notice, and a persisted **partially verified** result. This is evidence of a functional local academic demo path; it is not a claim that every answer is fully verified or that the system is production-ready. Screenshot: [candidate-stack real RAG query](screenshots/10_candidate_stack_real_rag.png).

The initial candidate browser attempt failed because the experimental alias `rag-api-candidate` was outside the HTTP client's explicit Docker service allowlist. The candidate services were then placed on a dedicated isolated internal network with the existing expected service alias `rag-api`; the browser query and authenticated startup check passed. No application security allowlist was broadened.

Other screenshots are in [screenshots](screenshots/). Earlier screenshots show the same candidate UI and one real, cited answer with partial verification.

## Database and owner binding

PostgreSQL migrations applied to `rag_application` were additive: creator profile/preferences tables and seed data, plus the existing verification-status choice migration. Before binding, the account was confirmed as a single active superuser matching the supplied owner identity. The owner binding command completed successfully. No data was dropped or reset.

The PostgreSQL suite used a separate test database. An unrelated, pre-existing test-named database was discovered during an earlier attempt; it was not dropped and was not reused for the final run.

## Not validated

- SMTP delivery to a real mailbox: no provider host or credentials are configured.
- Public or private production deployment: not performed.
- Full legal/source/document approvals: remain pending; production authorization remains fail-closed.
- Full browser coverage across all supported browsers and real user accounts: not performed.

See [release acceptance](phase6c_release_acceptance_report.md), [Docker validation](phase6c_docker_validation_report.md), and [final blockers](phase6c_final_blockers.md).
