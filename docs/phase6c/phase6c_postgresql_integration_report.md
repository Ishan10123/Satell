# Phase 6C PostgreSQL integration validation

## Configuration and tests

Django candidates used the existing PostgreSQL service at `postgres:5432` over `rag-app-network`. Candidate browser data used an isolated PostgreSQL database, not the application database.

- Django test suite on PostgreSQL: **77 passed, 2 skipped**.
- Final run used `rag_phase6c_test_acceptance_65872caf`, confirmed absent before the run, and retained after.
- Django test suite on SQLite: **77 passed, 2 skipped**.
- `manage.py check`: completed with two known configuration warnings: SMTP host unset and local base URL not HTTPS.
- `makemigrations --check --dry-run`: **No changes detected**.

The app database had no `CreatorProfile` table before these changes. An active superuser matching the owner identity was verified before running the additive creator-profile/preferences and verification-choice migrations, then `assign_creator_profile_owner` was run. The only app data change was this additive schema/seed and explicit owner binding. No PostgreSQL database/volume was deleted or reset.

An earlier test attempt discovered a test-named database that already existed; it was left in place and excluded from the final run. Automated test databases were not dropped.

## Result

PostgreSQL integration and owner-scoped profile persistence passed. See [creator ownership](phase6c_creator_profile_ownership_report.md) and [final blocker register](phase6c_final_blockers.md).
