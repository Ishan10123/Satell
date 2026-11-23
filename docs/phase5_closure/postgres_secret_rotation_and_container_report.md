# PostgreSQL credential rotation and container metadata

## Result

**Passed.** The old `rag-postgres` container was stopped gracefully and recreated from `infrastructure/postgres.compose.yaml`, which references the existing environment file and preserves the existing external volume and network. Password values were never printed. A redacted equality check confirmed the new container's configured role password matches the current rotated configuration.

## Backup and preservation evidence

Before container replacement, a PostgreSQL custom-format archive was created at:

`C:\Users\Ishan Kaushik\AppData\Local\satell-backups\phase5_closure_20261119_111139\rag_application_pre_pg_recreate_20261119_111139.dump`

- Size: 66,497 bytes.
- SHA-256: `D73ACED078265CEDCC4F780B70D49AED720356BE89CB51E51C54DA141EC180C6`.
- Restored into a uniquely named isolated test database and checked at 1 user / 7 conversations / 82 messages before the live container was replaced.
- The original volume name `rag_postgres_data` remained attached. PostgreSQL startup logged that the existing database directory was found and initialization was skipped.

After recreation, the Django app reached PostgreSQL over the existing Docker alias `postgres:5432`. The app again reports 1 user / 7 conversations / 82 messages after all temporary test users were removed. The container retains a loopback-only `127.0.0.1:5432` host binding and the existing `rag-app-network` alias.

## Commands used

```powershell
docker compose --env-file django_app/.env -p satell-infra -f infrastructure/postgres.compose.yaml config --quiet
# A custom-format pg_dump was made and restored into a temporary database before replacement.
docker compose --env-file django_app/.env -p satell-infra -f infrastructure/postgres.compose.yaml up -d postgres
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --no-deps django
```

The report intentionally omits credentials and the temporary database name. The custom archive remains available for operator-controlled recovery. No PostgreSQL volume was deleted, renamed, or recreated.
