# Phase 6B release gate

**Assessment date:** 2026-11-20  
**Final gate:** **NOT ELIGIBLE — do not promote the candidate images.**

## Decision summary

| Area | Decision | Evidence |
|---|---|---|
| Candidate build status | PASS — candidate images exist and were not rebuilt in Phase 6B. | Digests recorded below. |
| Candidate component tests | PASS WITH SKIPS. | Linux RAG suite: 270 passed. Django/PostgreSQL: 65 run, 63 passed, 2 opt-in skips. Django/SQLite: same. |
| Candidate synthetic HTTP integration | PASS for the isolated synthetic path. | One synthetic Qdrant point, real local Ollama embedding/generation, verified citation, PostgreSQL persistence, and safe fail-closed response. |
| Visual browser workflow | INCOMPLETE. | Browser control could not determine the active Chrome URL; HTTP sessions were exercised instead. No screenshots were captured. |
| Candidate security status | OPEN / HOLD. | Docker Scout reports 3 High OpenSSL findings on each candidate. No fixed Debian package version was available. No approved risk exception exists. |
| Candidate release eligibility | NOT ELIGIBLE. | Open high findings and incomplete browser validation fail the release acceptance criteria. |
| Production authorization | NOT_READY. | 14 sources remain pending; document approval registry is absent; current manifest is `operator_authorized_unreviewed`. |

## Candidate digests

- Django: `satell-django:phase6-candidate` — `sha256:aa08af08903a6d3756bd115be6647a9036bb73853b06dfe8137304984d56e1f9`.
- FastAPI: `satell-rag-api:phase6-candidate` — `sha256:0ab84e45ec8fd0f85a371d62d6d0c0bde01ce0b9f1dbb72fdc869d946c2f8c78`.

## Preservation result

The existing `rag_docs_v2` collection remained green with **58,856 points** at the final read-only check. The existing application containers and persistent services were not restarted, connected to the synthetic test network, or modified. No PostgreSQL or Qdrant production volume was deleted or recreated. The synthetic PostgreSQL/Qdrant data lived only in temporary containers and tmpfs and were discarded after validation. Source approvals, legal-review statuses, the production manifest, and Qdrant payloads were not changed.

## Open release blockers

1. Resolve the three OpenSSL findings through a supported Debian/Python base package update, then rebuild new candidate digests and rerun scans/tests; or obtain an explicit, time-bounded risk exception from the security owner. The candidate must not be called fixed while the scanner finds these vulnerabilities.
2. Complete the real browser visual workflow against the isolated candidate deployment. The HTTP-session workflow is evidence for server integration but does not replace the browser acceptance criterion.
3. Keep real-corpus production authorization blocked until the required human source/document decisions are complete and the production document registry validates against the unchanged index.
4. Complete host-side Ollama exposure/egress review and graceful-shutdown verification before staging approval.

No candidate image was promoted. No production authorization was granted. The appropriate next release action is to wait for supported OpenSSL packages, rebuild and rescan, then repeat the candidate gate including an actual browser session.
