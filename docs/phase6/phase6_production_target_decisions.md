# Production target decisions and ADRs

**Date:** 2026-11-20. **Status:** no production provider or paid service selected.

## Human decisions required

| Decision | Options to evaluate | Evidence needed | Current state |
|---|---|---|---|
| Deployment target | Self-hosted GPU, cloud-hosted, hybrid | Data classification, regional/legal constraints, cost quote, support model, tested capacity | Pending owner approval. |
| Identity | Managed OIDC/SSO or controlled self-hosted identity | MFA, recovery, account lifecycle, audit and tenant group mapping | Current Django password/session auth is local demo only. |
| Inference placement | Dedicated local GPU, private GPU service, managed inference | Model quality/cost/privacy, throughput, queue and failover behavior | Current Windows Ollama is workstation-bound. |
| Queue | PostgreSQL outbox worker, Redis/Celery-like broker, managed queue | Durability, operational skills, throughput, retry/DLQ and cost | No queue selected or implemented. |
| Tenant model | Shared company library, tenant-private corpus, mixed collections | Data ownership, cross-tenant policy, retention, legal and ACL requirements | Current RAG scope is one fixed demo principal. |
| Reliability objectives | Availability, latency, RPO/RTO | Product owner target and measured load/restore results | Not defined. |
| Monitoring and secrets | Self-hosted or managed observability/secrets | Data residency, redaction, access, retention, on-call responsibility | No service selected. |

## ADR-001: Separate presentation and RAG trust boundaries

**Decision:** retain Django for user identity/conversations and FastAPI for the RAG HTTP boundary. **Status:** current design, retain provisionally. **Evidence:** `django_app/rag_client/client.py`, `src/rag_pipeline/api/app.py`. **Trade-off:** separate process/network is easier to isolate but adds service discovery, auth, timeout and failure handling. **Acceptance:** private TLS transport, service identity/rotation, request idempotency and operational monitoring validated in the approved target.

## ADR-002: Preserve separate transactional and vector stores

**Decision:** PostgreSQL remains system of record for application data; Qdrant remains vector index. **Status:** retain; no migration approved. **Evidence:** Django models/migrations and Qdrant storage implementation. **Trade-off:** independent backup and consistency operations are required. **Acceptance:** combined restore drill proves app/index version compatibility.

## ADR-003: Dense retrieval remains fallback

**Decision:** retain dense as current strategy. **Status:** implemented. **Evidence:** `configs/retrieval.json`; heuristic benchmark showed RRF no recall gain and local reranker increased latency/lowered some rank metrics. **Trade-off:** exact identifier queries may be weaker. **Acceptance to change:** pre-registered, human-reviewed dataset; same filters/hardware; improved quality with acceptable latency and no security regression.

## ADR-004: Provider-neutral deployment proposal

**Decision:** document a hybrid private RAG + dedicated inference candidate without creating cloud resources. **Status:** proposal only. **Reason:** laptop capacity is unvalidated and data rights/residency/provider costs are unresolved. **Acceptance:** accountable owner selects target after legal, cost, threat and capacity review.

## ADR-005: No production legal authorization by automation

**Decision:** source/document decisions remain human-controlled; local demo remains separate. **Status:** mandatory invariant. **Evidence:** `src/rag_pipeline/authorization/local_academic_demo.py`, production checks in `src/rag_pipeline/api/app.py`. **Acceptance:** reviewed evidence-backed records, signatures, manifest binding, revocation and rejection tests after actual human decisions.

## ADR-006: Durable inference work is required before production

**Decision:** use an outbox-backed durable job contract as a design candidate; broker technology remains open. **Status:** not implemented. **Reason:** current synchronous request can leave pending rows and lacks idempotency/recovery. **Acceptance:** crash, retry, duplicate-submit, timeout, cancellation and worker-restart tests in isolated staging; no unbounded pending records.
