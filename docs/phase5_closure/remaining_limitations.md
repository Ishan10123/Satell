# Remaining limitations and readiness

## Local academic demonstration

**Operational for controlled local use**, with the real HTTP path, signed local demo registry, citation/claim validation, PostgreSQL persistence, static assets, and demonstrated browser flow. RAG answer quality is not complete: the repeated 20-query evaluation returned three failures, four partial verifications, and one abstention. The single-worker app serializes requests and shows materially variable latency.

## Private deployment

**Not ready.** Needs TLS/session-cookie deployment, a fresh-host reproducible infrastructure and model bootstrap, tested backup/restore including Qdrant and app config, real isolated outage/recovery exercises, monitoring/alerts, concurrency/load limits, and independent security review.

## Public/commercial production

**Not ready / blocked.** Human legal license review and document-level authorization remain pending. The production manifest is still `operator_authorized_unreviewed`. No public deployment or production authorization was tested. Do not change local-demo mode into production mode to address these gaps.

## Unverified or incomplete

- Physical Qdrant, PostgreSQL, Ollama, and live FastAPI outage/recovery was not tested to avoid disrupting shared services; client and API failure behavior is covered by tests and safe auth probes.
- Browser clipboard and query flow passed in local Chrome; this is not cross-browser validation.
- Host CPU utilization and peak Ollama system RAM were not captured. GPU/container resources are periodic samples, not continuous profiler output.
- Performance results are one machine, one model, one 20-query sequence, and one 2/3-request burst each; they are not SLAs.
- Isolated injection probe covers one synthetic retrieved malicious passage and is not comprehensive red-team evidence.
- Source URLs may navigate to source pages rather than exact evidence anchors; no source URL changes were made.
- No new tests were created for every OS/browser/runtime outage combination.

**Next step:** complete human source/document licensing decisions and a reviewed production authorization manifest before any real production corpus use. Separately, run isolated replica-based outage, backup/restore, and deployment reproducibility exercises before private deployment.
