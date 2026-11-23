# Phase 6 remaining blockers

**As of 2026-11-20.** This list identifies work that cannot be completed honestly without human, legal, target, infrastructure or staging decisions.

## P0 release blockers

1. Human review of source and document licenses; no legal review may be automated or inferred.
2. Evidence-bound, signed production source/document registry and reviewed manifest; current source decisions pending and production document registry absent.
3. Owner selection of deployment target/data residency, identity policy and production user model.
4. Tenant membership and document ACL implementation plus cross-tenant tests in separate staging DB/Qdrant.
5. Approved backup encryption/retention, RPO/RTO and successful isolated complete restore.
6. Independent security assessment and dependency/container scanning with remediation evidence.
7. Privacy/retention policy, incident response owner, SLOs and on-call operational acceptance.
8. Durable inference scheduling/idempotency/recovery and measured capacity on target hardware.
9. Clean-machine deployment, TLS/service identity, immutable artifacts and rollback rehearsal.
10. Human-reviewed RAG quality and citation entailment criteria; latest 30-query labels are heuristic and results include 7 failures/rejections.
11. Candidate container images retain three high OpenSSL findings each (CVE-2026-107493, CVE-2026-84786, CVE-2026-107496; Docker Scout lists no fixed version). The candidate zlib fix is present, but image release remains blocked until OpenSSL findings are resolved or reviewed through an approved exception process.

## P1/P2 engineering

- Staging index versioning, immutable publication and rollback; retain `rag_docs_v2` untouched.
- Retrieval strategy comparison on a human-reviewed held-out set.
- Out-of-domain confidence calibration and no-irrelevant-citation behavior.
- Independent verifier comparison and broader contradiction/version coverage.
- Redacted metrics, tracing, alerting and tested runbooks.
- Full dependency lock/hash coverage, CI gates and software update SLA. Candidate SBOMs and digest-pinned builds now exist, but OpenSSL findings are unresolved.
- Conversation history policy and bounded authorized context if multi-turn behavior is approved.
- Email recovery delivery and identity abuse protections.

## External decisions needed

Production provider/hardware, costs, data residency, IdP/SSO/MFA requirements, shared-vs-private corpus tenancy, legal scope, privacy retention, SLO/RPO/RTO, broker/queue selection, observability stack, security assessment scope, and accountable service owners. No service provider or paid infrastructure is selected.

## What must not be treated as resolved

Passing unit/integration suites are not tenant-security proof, a green Qdrant collection is not a restore drill, an HMAC signature is not a license, local demo authorization is not production authorization, a citation is not entailment, and one verified answer is not a quality guarantee.
