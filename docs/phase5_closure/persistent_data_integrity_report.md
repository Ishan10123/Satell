# Persistent data integrity

## Before/after evidence

| Data | Verified result |
|---|---|
| Qdrant `rag_docs_v2` | Green, 58,856 points before and after; same collection retained |
| PostgreSQL named volume | Existing `rag_postgres_data` stayed attached during container recreation |
| PostgreSQL app rows | 1 user, 7 conversations, 82 messages after cleanup |
| Source approval registry | 14 records, all `pending_review` |
| Inventory license statuses | 9,932 records, all `pending` |
| Production manifest | `ready`, `operator_authorized_unreviewed`; unchanged by this work |
| Temporary Qdrant probe | Unique synthetic collection removed; zero production points changed |
| Temporary browser accounts | Removed; related temporary conversations/messages cascaded with their user |

The PostgreSQL replacement was preceded by a dump whose SHA-256 and restore counts are in `postgres_secret_rotation_and_container_report.md`. No volume deletion/reset, Qdrant production-collection rebuild, embedding regeneration, source/raw-file edit, approval change, or corpus ingestion occurred.

Transient writes are disclosed: Django test databases were created and dropped; temporary browser users/conversations were inserted and removed; PostgreSQL internal state advanced normally during container restart. The isolated prompt probe created and deleted a synthetic Qdrant collection, so the Qdrant storage engine may retain normal operation metadata even though the temporary collection is absent and `rag_docs_v2` was not changed.
