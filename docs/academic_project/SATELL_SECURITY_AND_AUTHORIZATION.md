# Security and authorization assessment

Snapshot date: 2026-11-19. This is a bounded engineering assessment, not a penetration-test certificate.

## Trust boundaries

1. Browser to Django: authenticated server-side session, CSRF-protected forms, Django ownership-scoped queries.
2. Django to FastAPI: private Docker network and bearer service credential; credential stays server-side.
3. FastAPI to authorization data/Qdrant: signed demo policy, inventory/provenance/hash validation and retrieval filters.
4. FastAPI to Windows Ollama: host-local service routed to the intended host endpoint; not a public model API.
5. Generated response back to user: claim verification and citation validation gate the result; this lowers risk but does not prove correctness.

See `src/rag_pipeline/api/app.py`, authorization modules in `src/rag_pipeline/`, `django_app/conversations/views.py`, `django_app/rag_client/client.py`, Compose files, and `configs/`.

## Authorization states must not be conflated

The local demo registries are explicitly signed operator-controlled allowlists covering 14 source groups and 6,458 canonical documentation IDs. The live demo excludes 107 indexed research papers. Legal review statuses remain pending (14 source decisions; 9,932 inventory license statuses). The production manifest remains `operator_authorized_unreviewed`; production authorization requires reviewed source and document approvals and remains blocked. `document_approvals.json` is missing. No local-demo record changes those legal or production states.

## Implemented controls

- Django authentication/session middleware and CSRF protection.
- Conversation ownership enforced in database query scopes and application views.
- FastAPI bearer authentication for query/readiness routes.
- Bounded query length, top-k and request body size; in-process request rate limit.
- Private service network; no FastAPI host port; PostgreSQL/Qdrant host bindings restricted to loopback in the observed deployment.
- Signed local demo registry and fail-closed registry/hash/identity validation.
- Tenant/principal/source/license metadata filters at retrieval and rechecks during context assembly.
- Citation ID/mapping validation and fail-closed claim-verification behavior.
- No browser exposure of the FastAPI token.

## Residual risks and gaps

| Finding | Status/evidence | Impact | Required action |
|---|---|---|---|
| Legal authorization unresolved | Pending source/inventory states; production manifest unreviewed | No production corpus rights established | Human license review and document-level decisions, with evidence. |
| Local HTTP, no TLS | Compose is local/private; browser uses HTTP loopback | Unsuitable for hostile networks | TLS and deployment ingress design before remote use. |
| No MFA/login throttling evidence | Django auth is present; no verified MFA/distributed login limiter | Credential stuffing risk in exposed deployment | Add identity controls before public access. |
| Rate limit is process-local | FastAPI implementation | Does not coordinate across replicas/restarts | Shared limiter only if/when scaled. |
| No per-user document ACL | Shared authorized corpus and fixed server-side scope | Users share the same document visibility | Define tenant/document ACL semantics before multi-tenant use. |
| Prompt injection cannot be eliminated | Retrieved content is untrusted; tests are limited | Model may follow malicious text or misstate evidence | Continue adversarial testing and retain abstention/verification. |
| Diagnostic artifacts may contain sensitive text | Opt-in, bounded artifacts; disabled by default | Evaluation records can expose prompts/answers | Keep access restricted, retention short and redaction verified. |
| Service bearer secret via environment | Configured server-side | Secret rotation and container access matter | Secret manager/rotation procedures before deployment. |
| No complete supply-chain scan | No scanner evidence | Vulnerable image/dependency risk unknown | Scan pinned dependencies and images; create remediation SLA. |
| Qdrant/DB network trust | Private network and loopback host mapping observed | No independent service authentication demonstrated | Add network/auth controls for any shared/remote deployment. |

## Threat model

This is a bounded, code-and-test review for the current loopback academic demo. “Test evidence” means a named regression or observed boundary, not an independent penetration test. No claim that the threat is impossible is implied.

| Threat / attack surface | Preconditions and impact | Existing mitigation and evidence | Residual risk | Remediation / status |
|---|---|---|---|---|
| Cross-user conversation access | Attacker has an authenticated account and guesses/obtains another UUID; could expose questions, answers or citations. | Owner-filtered ORM helper in `django_app/conversations/views.py::_owned_conversation`; foreign UUID tests in `django_app/conversations/tests.py`. | Any missed endpoint or future unscoped query could leak data. | Retain adversarial route coverage and add independent review before multi-user deployment. Partial. |
| Session theft / CSRF | Attacker can induce requests or steal a session; state-changing account/conversation operations could be abused. | Django session/CSRF middleware; CSRF regression tests; local loopback scope. | Local HTTP is not suitable for hostile networks; MFA/login throttling not established. | TLS, secure-cookie policy, identity abuse controls before remote use. Partial. |
| Stored/reflected XSS through answers or citations | A user/model/source value reaches unsafe HTML/URL rendering; script execution in another user's session. | Autoescaped templates, client-side text-node Markdown rendering and citation URL sanitization; browser checks. | Parser/rendering edge cases and browser security policy need independent testing. | Fuzz Markdown/URL inputs and evaluate CSP in a TLS deployment. Partial. |
| Direct/indirect prompt injection | User query or retrieved document attempts to override system instructions or exfiltrate data. | Retrieved text is delimited/untrusted; authorization/context checks, verifier, prompt-injection probes and regression tests in `tests/test_api.py`, `tests/test_retrieval_context.py`, and Phase 5 isolated probes. | A local generative model may still follow malicious content or produce unsupported claims. | Continue red-team cases and human review; no complete prevention guarantee. Partial. |
| Unauthorized document retrieval | Registry/config/index mismatch, tampering or unknown document is presented to Qdrant/context. | Signed local-demo registry validation, manifest binding, fail-closed production gate, retrieval payload filters and context rechecks; `tests/test_local_academic_demo_authorization.py`, `tests/test_authorization.py`, `tests/test_retrieval_context.py`. | Human/legal license decisions are not made; local demo operator authorization is a distinct technical scope. | Keep production blocked until human source/document decisions and registry validation. Blocked. |
| Citation fabrication or unsupported answer | Model emits unknown/incorrect citations or unsupported claims. | Separate citation parser/mapping, claim coverage, claim verifier and consistency checks; `tests/test_generation.py`, `tests/test_claim_verifier.py`, `tests/test_phase4b_diagnostics.py`. | Citation correctness does not equal entailment; verifier shares model-family failure modes. | Improve human-labeled evaluation and contradiction/version coverage. Partial. |
| Invalid API credential / cross-scope request | Caller reaches FastAPI and supplies absent/invalid bearer or tries to select tenant/principal. | Bearer auth, constant-time compare, server-derived scope and Pydantic `extra=forbid`; `tests/test_api.py` invalid-token and scope tests. | Shared network trust and environment-secret lifecycle remain. | Add rotation/runbook and independent API review before remote deployment. Partial. |
| Resource exhaustion / request flooding | Authenticated or network-adjacent actor floods long generations or password resets. | Query/body bounds, top-k limit, timeouts, in-process rate limit, reset throttling, one worker. | Process-local limits do not coordinate; bounded long requests can still queue the single inference worker. | Define quotas/backpressure/SLO and test under isolated load. Partial. |
| Sensitive diagnostic/log exposure | Evaluation diagnostics or logs contain user prompts, generated text or claims. | Diagnostics are opt-in, bounded and excluded from ordinary API response; tests in `tests/test_phase4b_diagnostics.py` and `tests/test_api.py`. | Retention, access and consent governance incomplete; logs may persist elsewhere. | Keep diagnostics disabled normally; add retention/access procedure and verify log redaction. Partial. |
| Service network exposure | Misconfigured host port or network makes FastAPI, Qdrant or PostgreSQL reachable externally. | Current FastAPI has no published port; Django, PostgreSQL and Qdrant host bindings observed on loopback; Compose network boundaries. | Host firewall/Docker Desktop behavior and host Ollama listener need deployment-specific verification. | Recheck port bindings/firewall on every deployment; do not reuse this layout on shared networks without review. Partial. |
| Data loss or ransomware | Host/device failure or compromised operator affects PostgreSQL, Qdrant and source files. | Existing volumes and backup/restore guides; persistent-data integrity checks. | Current run did not execute a fresh backup restore drill or define RPO/RTO. | Establish off-host protected backups and run restore exercises. Blocked for production. |
| Dependency/container compromise | Vulnerable or malicious pinned package/image enters build/runtime. | Direct requirements are pinned and some model assets checksum-bound. | No complete transitive lock/SBOM or vulnerability scan was verified; image tags may be mutable. | Generate SBOM, scan dependencies/images, pin immutable digests and define remediation SLA. Not tested. |

No specific exploitable vulnerability was established by these bounded checks. That is not evidence of absence; independent penetration testing and image/dependency scanning remain open.

## Fail-closed expectations

Missing, malformed, unsigned or tampered policy data must not widen scope. A production manifest in the current mode must reject production readiness/query use. Do not use a local demo flag as a production fallback. Registry signatures authenticate integrity under the configured key; they do not establish that a source license is legally sufficient.

## Security validation limits

Prior isolated injection tests used a temporary collection and removed it afterward; the live corpus was preserved. Unit/integration authorization tests and local browser tests do not substitute for independent penetration testing, a dependency/image scan, incident exercises or legal review. See `docs/phase5_closure/` and `docs/phase4/` reports for dated evidence.

## Credential-handling evidence

FastAPI reads the required service token from `RAG_API_TOKEN` through `scripts/run_api.py::required_environment`; Compose injects it server-side into Django and FastAPI. The Django `.env` file is ignored by `django_app/.gitignore` and excluded from the Docker build context by root `.dockerignore`. I did not read or print any `.env` contents. A bounded source search found environment-variable access rather than a literal token assignment in `scripts/run_api.py`; no dedicated secret scanner or repository history scan was available, and no `.git` repository exists. This is limited static evidence, not a certification that no secret has ever entered the workspace or historical artifacts. Secret rotation and external secret storage remain deployment work.
