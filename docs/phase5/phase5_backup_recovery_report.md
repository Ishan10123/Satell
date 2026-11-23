# Phase 5 backup and recovery report

## Executed backups

Backups were written locally under `%LOCALAPPDATA%\satell-backups\20261119_103859\` (the directory contains personal conversation data and should remain protected by the Windows user account). The PostgreSQL archive was 66,081 bytes; the Qdrant collection snapshot was 351,885,824 bytes. SHA-256 values are recorded in the operator-local backup output; no credentials or `.env` values were included.

Six control files were copied with a SHA-256 inventory: retrieval configuration, legal source decisions, local demo authorization records, and the `rag_docs_v2` index manifest. Environment secrets were excluded. The `.env` file must be separately protected in an encrypted secret store; do not distribute it with the data backup.

## Restore validation

- PostgreSQL `pg_dump -Fc` restored into a unique temporary database. Restored counts were 1 user, 7 conversations, and 82 messages, matching the existing app data. The temporary database was dropped afterward; `rag_application` was not changed by the restore test.
- Qdrant collection snapshot restored into a unique temporary collection. It became green with 58,856 points. The temporary restore collection was deleted afterward; `rag_docs_v2` remained green with 58,856 points.
- No destructive restore was run against either original data service.

See [backup and recovery guide](backup_recovery_guide.md) for exact commands. Qdrant uses its supported collection snapshot/recovery API; consult the [Qdrant snapshot API](https://api.qdrant.tech/api-reference/snapshots/create-snapshot) and [snapshot documentation](https://qdrant.tech/documentation/snapshots/) when operating on other versions.

## Limits

The backup is a one-time local copy, not scheduled or offsite. The user-local directory is not encrypted by this procedure. PostgreSQL point-in-time recovery, automated retention, offsite copies, key escrow, RPO/RTO targets, and clean-machine disaster recovery remain unimplemented.
