# Phase 6 security assessment

**Date:** 2026-11-20. **Type:** bounded source/config/test review. This is not penetration testing or an independent audit.

## Strengths verified

- Django session auth, CSRF middleware, owner-scoped conversation queries and safe output rendering.
- FastAPI bearer boundary, server-derived single demo scope, bounded query/request size and Pydantic extra-field rejection.
- Separate local-demo signatures and production fail-closed manifest/source/document checks.
- Qdrant source/tenant/principal filters plus context-time authorization and provenance rechecks.
- Citation validation and structured claim verification fail closed.
- Private FastAPI host exposure; current Django and DB/vector bindings are loopback-bound. API and Qdrant share a private Docker network; Ollama is host-accessible from FastAPI.
- Non-root/read-only app containers, dropped Linux capabilities and `no-new-privileges` in app Compose definitions.

## Risks (severity is engineering priority, not exploitability proof)

| Priority | Finding | Evidence | Impact | Action/status |
|---|---|---|---|---|
| Critical blocker | Production corpus legal rights and reviewed approvals unresolved | 14 source decisions pending, 9,932 license fields pending, manifest unreviewed, production doc registry absent | Cannot authorize production retrieval or distribution | Human review/counsel and signed production registry; blocked. |
| High | No RAG tenant/member/document ACL for application users | Single `RAG_TENANT_ID`/principal from environment; no tenant models | Users share demo corpus; private tenant data would not be isolated | Implement after target/data policy; staging tests required. |
| High | No remote TLS/secure-cookie production ingress | Current HTTP loopback deployment; Compose secure cookies disabled | Not safe for hostile/shared networks | Provider-neutral target approved, then TLS ingress and secure cookies. |
| High | No durable asynchronous processing/idempotency | Synchronous view path; pending row can survive crash | Duplicate or stranded requests under process/network failures | Outbox and bounded workers; not implemented. |
| High | Inference resource exhaustion/queueing | One synchronous Gunicorn worker; 120s model timeout; local GPU | Latency/availability degradation under demand | Staging capacity/backpressure and approved SLO. |
| High | Candidate image scan has unresolved findings | Docker Scout 1.28.0 reports three high OpenSSL advisories (CVE-2026-107493, CVE-2026-84786, CVE-2026-107496), no fixed version listed; digest-bound output under `docs/phase6/evidence/` | Residual OS library exposure; applicability not independently assessed | Candidate zlib and Python package issues were addressed; OpenSSL findings remain blocked pending fixed base or approved security assessment. Candidate only; live images unchanged. |
| High | Backup restore and RPO/RTO not established | Guides exist; no current isolated full restore run | Uncertain recovery after host/storage loss | Encrypted off-host backups and restore test. |
| Medium | Password reset email unavailable | `accounts.W001`, SMTP unset | Account recovery cannot deliver reset link | Configure and test actual SMTP before remote account use. |
| Medium | Prompt injection cannot be completely prevented | Untrusted retrieved context and local model; bounded adversarial tests | Model may misinterpret hostile instructions | Keep content untrusted, no tools, expand isolated red-team tests. |
| Medium | Same model family generates/verifies | Generation configuration and verifier code | Correlated verifier failure possible | Benchmark independent verification, retain current fail-closed controls. |
| Medium | In-process rate limits | API limiter and cache behavior | Limits do not coordinate across replicas | Distributed rate limit after scale target selected. |
| Medium | Diagnostic artifacts can contain evaluation text when enabled | `EvaluationArtifactStore`, opt-in config | Sensitive text retention/access risk | Off by default, restricted path, retention and consent governance. |

## Validation limits

Current test and scanner results are recorded in `docs/phase6/evidence/phase6_candidate_validation_20261120.md`. Docker Scout's OpenSSL findings are scanner detections, not an independent exploitability determination. No public-network test, independent penetration test, real shared-service outage/recovery test or production tenant test was performed in this Phase 6 run. Passing tests do not establish absence of vulnerabilities.
