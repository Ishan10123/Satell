# Document/content identity migration plan

## Current compatibility state

The live `rag_docs_v2` collection remains unchanged. Existing point IDs and manifest counts were created with the legacy document ID derived from source ID plus raw file SHA-256. Do not rewrite those payloads or delete points in place as part of parser or identity work.

## Version 2 identities

- `content_id`: SHA-256 of canonical JSON for normalized segments (including text, segment type, and headings). The normalizer version is recorded separately.
- `document_identity`: SHA-256 of canonical source ID plus normalized relative path. This is stable across reprocessing and distinguishes same-content files at different paths and across sources.
- `document_id`: retained as the legacy compatibility key while current downstream consumers are migrated.
- `canonical_content_map.jsonl`: one content row mapped to all distinct document identities and their source/path/version/hash provenance.
- Chunk IDs include both legacy and version 2 identity plus content ID; payloads carry both identifiers and the source/path provenance.

The unit suite checks stable path identity, cross-source identity separation, normalized-content reuse, and retention of source provenance. New runs are append-only artifacts with fresh run IDs; existing artifacts are not rewritten.

## Collection migration before retrieval cutover

1. Keep `rag_docs_v2` read-only and preserve its manifest and Qdrant volume.
2. After source/document approvals and explicit indexing scope are complete, build a new versioned collection (for example `rag_docs_v3`) from reviewed normalized runs. Do not use operator-authorized-unreviewed data for production retrieval.
3. Compare source/path identity coverage, canonical content mappings, point counts, chunk ID uniqueness, and representative retrieval results in the new collection. Verify no source/path provenance is missing when identical content is shared.
4. Run index validation and authorization-boundary tests against the candidate collection. Keep the old collection available until a separately approved cutover.
5. Only after validation and explicit cutover approval should the application configuration point to the new collection. Retain the prior collection and volume until a separately planned retention decision.

No live collection migration or cutover is performed by the pre-retrieval parser task.
