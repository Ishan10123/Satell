# Phase 5 known limitations

## Readiness classification

- **Local academic demo: PARTIAL / usable for supervised demonstration.** Browser login, chat, real RAG, citation display, history, CSRF, and logout passed. Use only the configured local demo authorization. Several responses were partial or failed closed, so demonstrate the verifier states honestly.
- **Private deployment: NOT_READY.** The Compose bundle requires external data services/networks and host Ollama; it is not a clean-machine deployment. Local Django `runserver --insecure`, host-level service policy, secret lifecycle, TLS, backup operations, monitoring, outage drills, and concurrency limits need deployment-grade solutions.
- **Public/commercial production: NOT_READY.** Legal source/document reviews and production authorization remain pending. Production authorization checks remain fail-closed. Operational security, privacy/legal review, backups/recovery objectives, and independent security review are incomplete.

## Quality and security limitations

- 20-query real run produced 12 verified, 4 partially verified, 1 abstention, and 3 failed-closed responses. Topic labels are heuristic; human relevance labels are not complete.
- Contradiction detection is narrow; broad version freshness and cross-source conflict handling need evaluation.
- The injection test uses isolated synthetic retrieved-context data, not a malicious document in Qdrant or a complete retrieval attack path.
- No actual service outages were induced; network/database error tests use controlled unit-level fault injection.
- No limited-concurrency inference test was run. GPU reached 100% sampled utilization; concurrency capacity is unknown.
- Host/process peak memory and workload-wide host CPU were not captured; Docker container samples and GPU samples are recorded.
- Clipboard copy could not be verified in headless Chrome due unavailable clipboard permissions.
- The browser may show generic documentation-based refusal for private/unsupported requests; this does not itself prove an answer's factual safety beyond existing verifier tests.

## Deployment and operations

- No self-registration; an operator provisions accounts.
- Static files are served through Django's development staticfiles mode.
- Backups exist locally and isolated restore tests passed, but no schedule, encryption, offsite storage, or formal RPO/RTO is configured.
- A local credential was rotated after an accidental diagnostic echo; no secret values are present in reports. Maintain the rotated value in the local secret file.
