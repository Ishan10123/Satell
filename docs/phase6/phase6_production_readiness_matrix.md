# Phase 6 production readiness matrix

**As-of:** 2026-11-20. Status applies to a production deployment candidate, not the supervised local demo. No owner approvals are implied. P0 indicates a release-blocking gate.

| Requirement | Status | Evidence | Risk | Owner | Remediation | Validation | Acceptance condition | Approval |
|---|---|---|---|---|---|---|---|---|
| 1. Legal authorization | BLOCKED | 14 source decisions pending | Rights unresolved | Human reviewer/counsel | Review evidence and scope | Signed review record | Explicit permitted use | Pending |
| 2. Source/document approvals | BLOCKED | 9,932 license statuses pending; production doc registry absent | Unreviewed docs served if gate weakened | License owner | Complete evidence-bound decisions | Registry signature/hash/rejection tests | All served docs have current decisions | Pending |
| 3. Architecture | PARTIAL | Local separated Django/API design | Workstation-coupled | Product/architect | Approve target threat model | Architecture review | Target, trust zones and dependencies approved | Pending |
| 4. Backend | PARTIAL | Live API and tests | Sync request/capacity | Backend owner | Durable job lifecycle | Staging crash/retry tests | No stranded work; bounded retries | Pending |
| 5. Frontend | PARTIAL | Local browser E2E | Public a11y/TLS unknown | Product/accessibility | Remote UX/accessibility review | Browser/a11y audit | Approved accessibility criteria met | Pending |
| 6. Authentication | PARTIAL | Django sessions/password validators | No verified MFA/login abuse control | Identity owner | OIDC/MFA/throttle decision | Identity adversarial tests | Approved identity policy | Pending |
| 7. Authorization | BLOCKED | Production manifest unreviewed | Unauthorized corpus access | Security/legal owner | Reviewed source/doc scope | Fail-closed integration suite | Production readiness passes reviewed registry only | Pending |
| 8. Multi-tenancy | BLOCKED | One fixed RAG tenant/principal; no membership model | Cross-tenant data disclosure | Security/backend | Tenant and ACL implementation | Separate staging DB/Qdrant | Adversarial matrix passes | Pending |
| 9. Retrieval quality | PARTIAL | Heuristic benchmark/live evaluation | Irrelevant/missing evidence | RAG/eval owner | Human labels and controlled comparison | Held-out reviewed set | Owner-approved thresholds met | Pending |
| 10. Generation quality | PARTIAL | 30 live queries; variable failures | Unsupported/unstable answers | RAG owner | Human factual review; model version control | Blind human eval | Quality thresholds approved/met | Pending |
| 11. Citation validation | PARTIAL | Syntax/mapping regression tests | Valid IDs may not entail claims | RAG/eval owner | Entailment and navigation review | Human citations audit | Required claims have correct supporting sources | Pending |
| 12. Claim verification | PARTIAL | Fail-closed same model-family verifier | Correlated verifier errors | AI safety owner | Benchmark independent/deterministic checks | Human claim-level review | Approved false-accept/false-reject rates | Pending |
| 13. Prompt injection | PARTIAL | Bounded isolated probes | No complete prevention | Security owner | Broader red team | Isolated adversarial suite | Residual risk accepted with controls | Pending |
| 14. API security | PARTIAL | Bearer auth, bounds, private network | No remote TLS/mTLS/rotation proof | Platform security | Identity, TLS and rate policy | Security test | Approved threat controls pass | Pending |
| 15. Database reliability | PARTIAL | PostgreSQL healthy/tests pass | Restore/HA uncertain | DBA | Backup/PITR/migration plan | Isolated restore | Data and migration acceptance | Pending |
| 16. Vector DB reliability | PARTIAL | Qdrant green, 58,856 points | Restore/failover unverified | Data platform | Snapshot/restore/version plan | Isolated Qdrant restore | Manifest and ACL integrity pass | Pending |
| 17. Backup/DR | BLOCKED | Guide only; no current drill | Data loss | SRE/DBA | Encrypted off-host backup and RPO/RTO | Full isolated restore | Owner accepts measured RPO/RTO | Pending |
| 18. Monitoring | NOT_TESTED | Health only | Incidents may be missed | SRE | Metrics/alerts/runbooks | Alert exercises | Critical alerts tested/owned | Pending |
| 19. Observability | PARTIAL | Correlation, timings, bounded diagnostics | No central trace/dashboard | SRE/privacy | Redacted metrics/tracing | Sensitive-data scan | Coverage and retention approved | Pending |
| 20. Performance | PARTIAL | 30-query laptop timings | No capacity SLO | Performance owner | Representative workload | Staging load study | SLO accepted with headroom | Pending |
| 21. Concurrency | PARTIAL | Limited bursts only | Inference queue overload | Platform | Backpressure and bounded worker pool | Increasing staged concurrency | No uncontrolled overload/data loss | Pending |
| 22. Scalability | FAIL | One local sync worker/runtime | Cannot claim horizontal capacity | Platform/AI infra | GPU scheduling/capacity architecture | Multi-worker benchmark | Target load sustained | Pending |
| 23. Deployment | PARTIAL | Existing Compose healthy | Host state/tags mutable | Release owner | Immutable images/rollback/TLS | Clean host rehearsal | Reproducible install and rollback | Pending |
| 24. Dependency security | PARTIAL/BLOCKED | Candidate image digests scanned with Docker Scout; SPDX SBOMs generated; 0 critical, 3 high OpenSSL advisories per candidate | OpenSSL findings unresolved; scan filtered high/critical; licenses/transitive locks not reviewed | Security/supply chain | Resolve or formally assess OpenSSL findings; full lock, license and recurring scans | Exact image scan plus approved applicability review | Policy thresholds met and exceptions signed | Pending |
| 25. CI/CD | NOT_TESTED | No validated pipeline | Unreviewed changes can ship | Release engineering | Gated pipeline | Pipeline execution | Signed artifacts and approval gate | Pending |
| 26. Incident response | NOT_TESTED | No verified on-call/playbook exercise | Slow containment | Operations owner | Incident plan/key rotation | Tabletop exercise | Named roles and timings accepted | Pending |
| 27. Privacy/retention | NOT_TESTED | Conversations persist; policy incomplete | Excess retention/exposure | Privacy owner | Data lifecycle policy | Deletion/retention test | Approved schedule enforced | Pending |
| 28. Testing | PARTIAL | 263 RAG; 65+65 Django; browser evidence | Coverage is bounded; one platform skip | QA owner | Staging failures/security/eval | Acceptance suite | Required gates green and skips resolved/accepted | Pending |
| 29. Documentation | PARTIAL | Academic handbook + Phase 6 package | Reports have dated snapshots | Engineering owner | Keep evidence/version current | Independent review | Reviewer signs completeness | Pending |
| 30. Operational ownership | NOT_TESTED | No approved service owners/SLO | No accountable responder | Product/ops | Assign owners/on-call/vendor | Ownership tabletop | Named owner for all critical controls | Pending |

**Gate result: NOT READY for private, public or commercial production.** Production legal approval, reviewed authorization, tenancy, restore evidence, independent security/supply-chain assessment, operational ownership and capacity are release blockers.
