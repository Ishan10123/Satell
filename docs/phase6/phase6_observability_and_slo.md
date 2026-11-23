# Observability and SLO proposal

## Existing signals

FastAPI returns correlation IDs, stage timings and bounded diagnostic metadata. Django persists request ID, retrieval strategy, timings, model/index version and verification status. Health and readiness are separate. Evaluation artifacts are opt-in and bounded, but can contain sensitive evaluation prompts/answers. There is no verified central metrics, tracing, alerting or dashboard deployment.

## Privacy-safe metric candidates

- Web: request count/status/latency, login failure count, CSRF rejection count, database failures.
- RAG: request status by safe error code, embedding/retrieval/context/generation/verification/citation latency, abstention/partial/failure count, context admission counts and queue depth.
- Infrastructure: GPU utilization/VRAM, host/container CPU/memory, DB pool/connection wait, Qdrant latency/health, Ollama availability, worker saturation.
- Security: auth failures, authorization denials, registry validation failure, rate-limit events, without prompt/document payloads.

Avoid high-cardinality user/query labels. Do not log raw prompt, evidence, answer or credentials by default. Request IDs are operational identifiers and require retention/access policy. Diagnostic artifacts must remain isolated, access-controlled, bounded and time-limited.

## Candidate SLOs (not approved)

| Signal | Candidate definition | Owner decision needed |
|---|---|---|
| Availability | Successful authenticated service readiness / query completion over a calendar window | Target percentage and maintenance window. |
| Latency | p50/p95/p99 from accepted job to terminal result, separately for queue, retrieval, generation and verification | Query mix and acceptable latency. |
| Durability | Accepted job reaches persisted terminal outcome or explicit recoverable state | Loss tolerance and retry window. |
| Recovery | Restore time and data-loss window after dependency/storage loss | RTO/RPO. |
| Security | Time to detect/respond to credential, authorization or exposure incident | On-call ownership and severity SLA. |

Do not call these business SLOs until approved. Current single-machine results (30-query p50 4.77s, p95 6.48s) are not capacity targets.

## Alert/runbook candidates

Alert on repeated readiness failure, authorization registry failure, elevated dependency timeouts, queue age/depth, GPU memory exhaustion, DB connection exhaustion, Qdrant unhealthy state, backup age, verifier/citation rejection spike and disk pressure. Each alert needs an owner, runbook, threshold derived from staging baseline, and test. No alerts were deployed in this milestone.
