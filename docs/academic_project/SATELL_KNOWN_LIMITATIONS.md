# Known limitations

Snapshot: 2026-11-19. This list favors verified limits over speculative claims.

## Legal and authorization

- All 14 source approvals remain `pending_review`; all 9,932 inventory license statuses remain pending.
- Production manifest is `operator_authorized_unreviewed`; production document approval registry is missing.
- Local demo authorization is scoped, signed and explicit, but is not legal clearance or production approval.

## Product and identity

- No public self-registration route; accounts are operator-provisioned.
- The corpus is shared within the demo scope. No per-user document ACL exists.
- Follow-up text is not supplied as conversation history to the RAG service, so follow-up questions are standalone.
- No raw-token streaming, cancellation, async job queue, or message idempotency contract.
- No verified MFA or distributed login throttling.
- Password reset supports username/email and expiring one-time tokens, but real SMTP delivery is unavailable until SMTP_HOST and a sender are configured. The local system check warns while this remains unset.
- Optional read-only share links expose the selected conversation to anyone holding the capability URL until expiry or revocation; sharing stays off by default.
- Locking a conversation enforces app-level read-only state; it does not encrypt data.

## Retrieval and answer quality

- Dense retrieval is active; sparse BM25/RRF and ONNX reranking are implemented/benchmarked but inactive.
- Evaluation sets are small and do not use comprehensive expert judgments.
- Live evaluation had partial, rejected, and abstained responses; citation and claim checks do not prove truth.
- Same local model family performs generation and verification, reducing verifier independence.
- Contradiction and documentation-version reasoning remain incomplete.
- Context token estimation and semantic relevance are imperfect.
- Latest 30-query evaluation had 7 failed/rejected answers and 2 unexpected abstentions; two additional heuristic-answerable questions failed rather than returning explicit abstentions. No human expert judgments were completed. Current results are diagnostic, not a quality guarantee.
- A same-question live API rerun returned a failed response once and a verified two-citation response next; request success and verification labels vary with the model output.

## Operations and scaling

- One synchronous Gunicorn worker serializes inference requests; sustained concurrency and capacity are not established.
- No production SLO, centralized monitoring/alerting, distributed rate limiting, HA/failover or tested disaster recovery evidence.
- Local HTTP and loopback bindings are suitable for this supervised workstation setup only; no remote TLS deployment validated.
- Mutable image tags and incomplete transitive lock weaken reproducibility.
- No verified automated vulnerability scanner or CI/CD pipeline.
- GPU and latency measurements represent one laptop and a small sample.

## Data/privacy

- User conversations are persisted; retention/deletion governance for a multi-user service is not complete.
- Opt-in diagnostics can hold user prompts/model answers; keep disabled except controlled evaluations, bound retention and restrict access.
- Qdrant payloads and raw corpus need backup/access policy for any expanded deployment.

## What this does not imply

These limitations do not mean the supervised local demo is unusable. They mean its scope must remain explicit and no public/commercial readiness claim is justified.
