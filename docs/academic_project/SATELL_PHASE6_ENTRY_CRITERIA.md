# Phase 6 entry criteria

**Recommendation: do not begin Phase 6 production-readiness execution yet.** First resolve legal/source-document review and define a production deployment target. Phase 6 must not be treated as authorization to change the corpus or weaken current checks.

## Mandatory prerequisites

| Prerequisite | Why | Current status | Evidence and acceptance condition |
|---|---|---|---|
| Human source and document license review | Establish lawful use and scope | BLOCKED: pending | Signed human decisions with source-bound evidence and per-document exceptions; legal reviewer record. |
| Reviewed production authorization | Keep serving allowlist auditable | BLOCKED: manifest unreviewed; document registry missing | Valid source/document registries, signed, matched to manifest; production readiness passes without demo mode. |
| Defined deployment threat model | Bound users, data and adversaries | PARTIAL: local demo assessed | Approved target architecture, trust boundaries, data classification and abuse cases. |
| Independent security assessment | Find flaws not covered by unit tests | NOT_TESTED | Remediated security review/penetration test with retest evidence. |
| Dependency/image vulnerability assessment | Supply-chain risk is unknown | NOT_TESTED | SBOM, pinned artifacts, scanner report, severity SLA and resolved critical/high findings. |
| Multi-user isolation | Protect conversations and any private corpora | PARTIAL | Automated owner/tenant tests plus adversarial API tests for messages/citations/history. |
| Backup and restore | Protect PostgreSQL, Qdrant, registries and keys | PARTIAL | Off-host backup, encryption/access controls, documented RPO/RTO, successful restore drill. |
| Monitoring and incident response | Detect/contain failures and abuse | NOT_READY | Metrics/log redaction, alerts, on-call ownership, incident/key-rotation exercises. |
| Failure/recovery validation | Verify dependency outages and recovery | PARTIAL: unit fault injection | Controlled outage/recovery tests with service-level evidence and no data loss. |
| Reproducible deployment and rollback | Avoid workstation-only deployment | BLOCKED | Clean-machine deploy, immutable image digests, secrets provisioning, migration/rollback plan. |
| SLO and capacity plan | Match latency/concurrency to users | NOT_DEFINED | Agreed SLO, representative load test and GPU/CPU/memory capacity model. |
| Production inference strategy | Protect local model service under load | PARTIAL | Capacity, isolation, timeouts, overload behavior and fallback policy tested. |
| Privacy/retention policy | Define conversation and diagnostics lifecycle | NOT_DEFINED | Data retention/deletion policy and verified enforcement. |
| Legal operational support | Handle rights complaints and incidents | NOT_DEFINED | Review owner, takedown/correction workflow and contact process. |

## Recommended improvements

Expert-labeled retrieval evaluation; broader contradiction/version checks; freshness monitoring; scalable inference queue; tracing and per-stage metrics; distributed rate limits; richer administrator controls; higher coverage browser/accessibility tests. These improve quality and operability but do not substitute for the mandatory prerequisites.

## Acceptance workflow

1. Freeze and identify the reviewed corpus and legal scope.
2. Produce source/document approval records and manifest from human decisions; validate signatures/hashes and test rejection paths.
3. Build an immutable deployment candidate with SBOM and secret provisioning plan.
4. Run security, ownership, privacy and failure tests in an isolated staging environment.
5. Restore backups and execute load tests on representative hardware.
6. Approve SLO, incident response, rollback and monitoring.
7. Have accountable human owners accept evidence and residual risks before production exposure.

Phase 6 can begin only as a controlled planning/review effort after ownership and target scope are defined. Production implementation or corpus authorization must wait until the blocked prerequisites have evidence-backed closure. This current task does not start Phase 6.
