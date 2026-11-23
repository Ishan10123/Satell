# Production ingestion and index lifecycle

## Current implementation

The repository has source discovery/inventory, evidence-bound approval, parser registry, bounded structured/advanced extraction, normalization and content hashes, chunking, embedding, idempotent point upsert and a manifest validation CLI. Relevant code: `src/rag_pipeline/ingestion/`, `parsing/`, `normalization/`, `chunking/`, `embeddings/`, `storage/index_manifest.py`, `scripts/ragctl.py`. The existing reference is `rag_docs_v2`, 58,856 points and a ready manifest in `operator_authorized_unreviewed` mode. No ingestion/index operation was run in Phase 6.

## Production gaps

- Current `ragctl index` has a single managed collection path, not an immutable release/publish/rollback workflow.
- A production build must bind source, inventory, document decisions, parser/normalization/chunking/model versions, source hashes, and point counts into a signed build manifest.
- Parsing needs process-level time/resource isolation for PDFs, office files and pathological inputs in addition to parser-level checks.
- Retry/quarantine/dead-letter and incremental dependency graphs need a durable job store.
- Revocation/deletion propagation and cache invalidation must be demonstrated.
- Existing Qdrant aliases/versioned collection publication have not been exercised here. Do not assume rollback behavior without staged validation.

## Recommended immutable release flow

1. Freeze a reviewed source manifest and authorized documents; record acquisition origin/date/version/hash.
2. Run deterministic parser/normalizer/chunker/embedding pipeline in isolated workers with quotas and per-document outcome ledger.
3. Write to a new versioned collection, never the active collection. Idempotency key includes document content hash, processing versions and chunk identity.
4. Validate point counts, vectors/dimensions/model digests, payload schema, ACL metadata, duplicate rates, per-source counts, sampled content hashes and authorized document set.
5. Run security and human-reviewed retrieval evaluation against candidate index.
6. Sign immutable manifest and require authorized operator approval to activate alias/config.
7. Retain prior index and a tested rollback pointer until retention expiry. Revoked content has explicit fast deny-list propagation independent of build schedule.
8. Restore candidate from backup in a separate environment before any release.

## Preservation

Keep `rag_docs_v2`, its 58,856 points, manifest, raw corpus and current demo registry unchanged. Staging experiments require a separate collection name and disposable credentials/network, with point-count proof before/after. Current task performed no ingestion, embedding, index or Qdrant writes.
