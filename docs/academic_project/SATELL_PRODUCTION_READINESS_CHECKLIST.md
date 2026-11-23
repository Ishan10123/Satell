# Production readiness matrix

Snapshot date: 2026-11-19. A `PASS` means only the stated local check passed, not that the whole category is certified. Status vocabulary: PASS, PARTIAL, FAIL, NOT_TESTED, BLOCKED, NOT_APPLICABLE.

| Category | Status | Evidence | Risk / impact | Required action | Priority | Human intervention |
|---|---|---|---|---|---|---|
| Architecture | PARTIAL | Django/FastAPI/data boundaries run locally | Workstation-coupled | Define production target and threat model | P1 | Yes |
| Backend | PARTIAL | Live API request and tests | Limited capacity/error exercises | Capacity/recovery validation | P1 | Yes |
| Frontend | PASS | Browser E2E recorded for local scope | Not a public UI assessment | Accessibility and remote deployment review | P2 | Yes |
| Authentication | PARTIAL | Django session auth tested | No verified MFA/login throttling | Identity policy and abuse controls | P1 | Yes |
| Authorization | BLOCKED | Demo scope signed; production manifest unreviewed | Production access must deny | Human decisions + production registry | P0 | Yes |
| Multi-user isolation | PARTIAL | Owner-scoped Django tests | No per-user document ACL | Threat-model and tenant tests | P1 | Yes |
| API security | PARTIAL | Bearer auth, bounds, CSRF upstream | No TLS, distributed limits | TLS, rate policy, independent test | P1 | Yes |
| RAG retrieval | PARTIAL | Dense runtime; small benchmark | Labels not expert relevance | Human-labeled evaluation | P2 | Yes |
| Generation | PARTIAL | Local model live | Hallucination/latency risk remains | Representative evaluation/capacity | P1 | Yes |
| Citation validation | PARTIAL | Regression tests and live citations | Citation validity is not entailment | Expand semantic navigation/support tests | P2 | Yes |
| Claim verification | PARTIAL | Fail-closed verifier tests | Same model family; verifier can err | Independent evaluation and consistency controls | P1 | Yes |
| Prompt-injection defense | PARTIAL | Isolated probes and controls | No complete prevention guarantee | Independent adversarial testing | P1 | Yes |
| Legal authorization | BLOCKED | All source/license decisions pending | Rights not established | Legal/human source and document review | P0 | Yes |
| Database reliability | PARTIAL | PostgreSQL persistent and tested | No HA/restore drill evidence | Restore exercise and RPO/RTO | P1 | Yes |
| Vector DB reliability | PARTIAL | Qdrant green with 58,856 points matching manifest | Backup/failover proof incomplete; `indexed_vectors_count` reports 57,325 and was not independently diagnosed | Confirm Qdrant index metric semantics, then execute restore/availability exercise | P1 | Yes |
| Backup and recovery | PARTIAL | Guide exists | Fresh off-host backup and recovery unproven | Execute documented restore drill | P0 | Yes |
| Observability | PARTIAL | Correlation and diagnostics exist | No full tracing/SLO dashboards | Define telemetry and alert ownership | P1 | Yes |
| Logging | PARTIAL | Redaction controls and bounded artifacts | Persistence/retention needs governance | Approve retention and audit logs | P1 | Yes |
| Monitoring | NOT_TESTED | Health checks only | No alerting evidence | Add monitoring, alerts and runbooks | P1 | Yes |
| Performance | PARTIAL | 30-query browser sample plus a live single-query rerun | 7/30 failed/rejected, 6/30 partial; no human truth labels or SLO | Human-reviewed evaluation and load tests against an agreed SLO | P1 | Yes |
| Concurrency | PARTIAL | 2/3 request bursts completed | Single worker serializes inference | Capacity/load test and queue policy | P1 | Yes |
| Scalability | FAIL | One local worker/runtime | No horizontal strategy | Design and benchmark multi-worker inference | P2 | Yes |
| Docker deployment | PARTIAL | Existing compose healthy | External state, mutable tags | Pin digests and validate deploy/rollback | P1 | Yes |
| Clean-machine deployment | NOT_TESTED | Existing workstation dependencies | Not reproducible from clean host | Provisioning/restore rehearsal | P1 | Yes |
| CI/CD | NOT_TESTED | No validated pipeline evidence | Regressions may escape | Add gated CI and artifact provenance | P2 | Yes |
| Dependency management | PARTIAL/BLOCKED | Candidate images are digest-pinned and have SPDX SBOMs plus Docker Scout scans | Three high OpenSSL findings per candidate; no complete hash-locked dependencies or release exception process; candidates not deployed | Resolve/review findings, complete locks and recurring scan policy | P1 | Yes |
| Disaster recovery | NOT_TESTED | Guide only | Recovery time/data loss unknown | Define and test RTO/RPO | P0 | Yes |
| Documentation | PARTIAL | 20-chapter report, technical handbooks, 160-question interview bank, diagrams and repository map | Phase reports are dated snapshots; user decision rationales not always recorded | Keep current evidence linked and label engineering rationale vs historical rationale | P2 | Yes |
| Testing | PARTIAL | Current host RAG 270 tests (269 passed/1 Windows symlink skip), Linux candidate RAG 270 passed; candidate Django SQLite 63 passed/2 opt-in skipped; prior Django PostgreSQL and SQLite suites 65/65 each | Passing suites are bounded; candidate image was not PostgreSQL-tested; live output varies and isolated fault/recovery tests incomplete | Retain regressions and add candidate PostgreSQL plus isolated staging fault, recovery and quality tests | P1 | Yes |

## Readiness by deployment class

| Class | Verdict | Basis |
|---|---|---|
| Local academic demonstration | READY WITH SUPERVISION | Real local query/browser flow works in recorded checks; keep loopback, monitor service health, explain pending legal scope and quality limits. |
| Private deployment | NOT READY | TLS, per-user corpus policy, vulnerability assessment, monitoring, backup/restore, SLO and capacity evidence remain incomplete. |
| Public production | NOT READY | Legal and production authorization blocked; security, operations, privacy, scale and support requirements remain open. |
| Commercial production | NOT READY | Commercial use and redistribution rights have not been established. |

## Explicit 100% answers

- **100% secure?** No; no system can be certified that way, and independent testing is incomplete.
- **100% reliable?** No; outages, single-worker queuing and recovery limits remain.
- **100% factually correct?** No; retrieval, generation and verification can all fail.
- **100% production-ready?** No.
- **Production-grade components present?** Yes: Django/PostgreSQL, authenticated FastAPI, Qdrant and containerized services have production-oriented features.
- **Entire application production-ready?** No. Component maturity does not establish end-to-end legal, operational, security or quality readiness.
