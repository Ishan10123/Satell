# Local backup and recovery guide

Run from PowerShell on the machine that owns the existing local services. Backups contain conversation data and indexed documentation; store them in a user-restricted location. The example intentionally does not copy `.env` or print credentials.

## Create a PostgreSQL custom archive

The existing PostgreSQL container is `rag-postgres`. Its container-local socket can use the configured database role without putting a password in the command line:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $env:LOCALAPPDATA ("satell-backups\$stamp")
New-Item -ItemType Directory -Path $backupDir | Out-Null
$name = "rag_application_$stamp.dump"
$containerFile = "/tmp/$name"
$dumpCommand = 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f ' + $containerFile
docker exec rag-postgres sh -c $dumpCommand
docker cp "rag-postgres:$containerFile" (Join-Path $backupDir $name)
docker exec rag-postgres rm -f $containerFile
Get-FileHash -Algorithm SHA256 (Join-Path $backupDir $name)
```

## Restore PostgreSQL into an isolated test database

Never test a restore against `rag_application`. Use a unique temporary name, verify counts, then remove only that temporary database:

```powershell
$restoreDb = 'satell_restore_check_' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$dumpPath = (Resolve-Path (Join-Path $backupDir $name)).Path
$containerFile = "/tmp/$name"
docker cp $dumpPath "rag-postgres:$containerFile"
$createCommand = 'createdb -U "$POSTGRES_USER" ' + $restoreDb
docker exec rag-postgres sh -c $createCommand
$restoreCommand = 'pg_restore --no-owner --no-privileges -U "$POSTGRES_USER" -d ' + $restoreDb + ' ' + $containerFile
docker exec rag-postgres sh -c $restoreCommand
$verifyCommand = 'psql -X -At -U "$POSTGRES_USER" -d ' + $restoreDb + ' -c ''SELECT (SELECT count(*) FROM auth_user), (SELECT count(*) FROM conversations_conversation), (SELECT count(*) FROM conversations_message);'''
docker exec rag-postgres sh -c $verifyCommand
# After verifying this temporary database only:
$dropCommand = 'dropdb -U "$POSTGRES_USER" --if-exists ' + $restoreDb
docker exec rag-postgres sh -c $dropCommand
docker exec rag-postgres rm -f $containerFile
```

## Qdrant collection snapshot

This uses the supported collection snapshot API. The Qdrant host port is loopback-bound on this workstation.

```powershell
$snapshot = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:6333/collections/rag_docs_v2/snapshots?wait=true'
$snapshotName = $snapshot.result.name
$snapshotPath = Join-Path $backupDir $snapshotName
Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:6333/collections/rag_docs_v2/snapshots/" + [uri]::EscapeDataString($snapshotName)) -OutFile $snapshotPath
Get-FileHash -Algorithm SHA256 $snapshotPath
```

## Test a snapshot without touching `rag_docs_v2`

Qdrant only accepts recovery snapshot files located inside `/qdrant/snapshots`. Copy the file to the running Qdrant container's temporary filesystem, restore to a unique collection, compare point counts, then remove only the test collection and copied file:

```powershell
$target = 'satell_restore_check_' + [Guid]::NewGuid().ToString('N').Substring(0,12)
$source = Invoke-RestMethod http://127.0.0.1:6333/collections/rag_docs_v2
if ($source.result.points_count -ne 58856) { throw 'Unexpected source point count; stop.' }
$containerSnapshot = "/qdrant/snapshots/phase5-$snapshotName"
docker cp $snapshotPath "qdrant:$containerSnapshot"
$body = @{ location = "file://$containerSnapshot" } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:6333/collections/$target/snapshots/recover?priority=snapshot" -ContentType 'application/json' -Body $body
$restored = Invoke-RestMethod -Uri "http://127.0.0.1:6333/collections/$target"
if ($restored.result.points_count -ne $source.result.points_count) { throw 'Snapshot point count mismatch.' }
# Remove only the uniquely created validation collection:
Invoke-RestMethod -Method Delete -Uri "http://127.0.0.1:6333/collections/$target"
docker exec qdrant rm -f $containerSnapshot
```

For disaster recovery, restore only into a new cluster/collection after verifying the snapshot, Qdrant version compatibility, required space, authorization metadata, and application manifest. Never use overwrite/force restore against the only active collection.

## Configuration and authorization files

The local backup process copied retrieval configuration, legal source decisions, local academic-demo authorization registries, and the `rag_docs_v2` manifest into a separate `project-controls` folder with SHA-256 inventory. Preserve exact signed bytes; do not edit a registry to make a restore pass. Restore config/registry artifacts to a staged directory first, verify hashes and signatures, then activate only through the existing reviewed change workflow.

For a new backup, copy the active files explicitly and hash the copied bytes:

```powershell
$controlsDir = Join-Path $backupDir 'project-controls'
New-Item -ItemType Directory -Path $controlsDir | Out-Null
$controlFiles = @(
  'configs/retrieval.json',
  'knowledge_base/metadata/source_approvals.json',
  'knowledge_base/metadata/local_academic_demo_authorization.json',
  'knowledge_base/metadata/local_academic_demo_source_authorizations.json',
  'knowledge_base/metadata/local_academic_demo_document_authorizations.json',
  'knowledge_base/metadata/index_manifests/rag_docs_v2.json'
)
foreach ($relative in $controlFiles) {
  $sourcePath = Join-Path (Get-Location) ($relative -replace '/', '\\')
  Copy-Item -LiteralPath $sourcePath -Destination $controlsDir
}
Get-ChildItem -LiteralPath $controlsDir -File | Get-FileHash -Algorithm SHA256
```

Do not include `django_app/.env`, API bearer tokens, Django secret keys, or database passwords in documentation or distributable backups. Store them in an encrypted, access-controlled secret manager or encrypted offline vault; test access restoration separately. This project does not configure secret escrow or automated encryption/retention.
