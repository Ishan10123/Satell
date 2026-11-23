# Phase 6C final blockers and next actions

## Readiness decisions

| Target | Decision | Evidence |
|---|---|---|
| Supervised local academic demo | **ACCEPTED WITH LIMITATIONS** | Candidate Docker/browser path and real non-synthetic cited query passed; that query was partially verified. Use only local demo authorization. |
| Private deployment | **BLOCKED** | Six High image vulnerabilities, no real SMTP delivery/HTTPS origin, and backup/recovery/monitoring/deployment controls not validated. |
| Public/commercial production | **BLOCKED** | All 14 legal source reviews remain pending, document approval registry is absent, and production authorization must remain fail-closed. Other private-deployment blockers also apply. |

## Required before promoting a candidate

1. Patch the candidate images for the four OpenSSL and two glibc High findings, rebuild, and rerun Docker Scout. If a vulnerability has no fix, document exploitability analysis and obtain an explicit security exception.
2. Configure SMTP using deployment secrets and HTTPS public origin, then perform a controlled mailbox reset test.
3. Complete a backup and restore drill for PostgreSQL and Qdrant, define monitoring/alerts, and validate TLS/reverse proxy, capacity limits, and incident response.
4. Keep the existing containers running until a separate, reviewed deployment plan authorizes promotion. Candidate containers are not production rollout.

## Required before production RAG authorization

1. Human reviewers must review source license evidence and record a decision for each of the 14 sources. Do not infer approval from repository root license files.
2. Create/validate the document approval registry through its evidence-backed workflow, with individual arXiv/document decisions where applicable.
3. Revalidate the manifest and production readiness. Do not change local demo mode or filters to work around missing approvals.

## Stop point

Phase 6C closure is documented. **Do not start Phase 7** until the user reviews these concrete blockers and explicitly chooses the next authorized work. No source/document approvals were made; no Qdrant points or collections were modified.
