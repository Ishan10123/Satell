# Backup and disaster recovery plan

## Protected state

PostgreSQL app records; Qdrant collection, payloads and collection config; raw source files; inventory/provenance; parse/normalization outputs needed to reproduce; production/demo registries; approval evidence; manifests; tokenizer/model configs/assets; secrets and signing-key recovery; deployment configuration. A Qdrant snapshot alone is not a whole-system backup.

## Current evidence

Existing backup/recovery guidance exists under `docs/phase5/backup_recovery_guide.md`, but no current full isolated restore test was performed in this Phase 6 run. The live environment was preserved. No RPO/RTO, off-host encryption/retention proof, or key escrow process is owner-approved. Do not infer recovery from a green health check or historical restore report.

## Target policy template (values pending owner)

| Control | Required decision/evidence |
|---|---|
| RPO/RTO | Product/operations owner sets acceptable loss and restoration time, separately for chat, index, source/evidence and authorization. |
| Backup cadence | Based on RPO; include consistent PostgreSQL backup and Qdrant snapshot strategy. |
| Encryption | Encryption in transit/at rest; key custody and rotation separate from data access. |
| Retention | Explicit retention by data class; legal hold and deletion propagation. |
| Off-host copy | Separate account/region/device with least-privilege and immutable retention where required. |
| Restore test | Isolated staging only; validate schema, counts, registry signatures, manifest hashes, Qdrant vector dimensions/payload ACL and model compatibility. |
| Rollback | Restore prior app image/config and prior immutable index alias, with audit and operator approval. |

## Restore drill acceptance

Create isolated test DB and distinct temporary Qdrant collection; restore a known encrypted backup; compare expected user/conversation/message counts from the backup manifest; verify authorization registry signatures and content hashes; query only synthetic/staging fixtures; confirm collection vector config and index version; record RTO/RPO measured; destroy only isolated test resources after independent path verification. Never restore into or overwrite the live app DB or `rag_docs_v2` during a drill.

**Status: PARTIAL/BLOCKED.** No new backup or restore was performed here.
