# Authorization governance and production license gate

**As-of 2026-11-20:** 14 source groups are `pending_review`; all 9,932 inventory license statuses are `pending`; the production index manifest is `operator_authorized_unreviewed`; `knowledge_base/metadata/document_approvals.json` is absent. The current live API uses explicit `RAG_AUTHORIZATION_MODE=local_academic_demo` and a separate demo enable flag. These facts were inspected; no records were modified.

## Existing controls

- Source decisions and evidence validation: `src/rag_pipeline/ingestion/approval.py`, `approval_workflow.py`.
- Production readiness and document deny/permitted logic: `src/rag_pipeline/api/app.py::check_index`, `document_policy`, query route.
- Index manifest and fingerprints: `src/rag_pipeline/storage/index_manifest.py`.
- Demo policy, signed registries and inventory/document identity: `src/rag_pipeline/authorization/local_academic_demo.py`.
- Qdrant filters and context-time rechecks: `src/rag_pipeline/storage/qdrant_store.py`, `src/rag_pipeline/retrieval/context.py`.
- Regression coverage: `tests/test_authorization.py`, `tests/test_local_academic_demo_authorization.py`, `tests/test_api.py`, `tests/test_retrieval_context.py`.

The production gate fails closed when approvals, the document registry, signatures, evidence hashes, index bindings or reviewed manifest mode are missing/mismatched. No local academic demo allowlist is a production fallback.

## Governance model required before production

Each decision should bind immutable IDs, source origin/provenance, evidence path/origin/hash, license/terms classification, explicit use scope, reviewer identity, timestamp, rationale, expiration/re-review date, and immutable audit event. Document overrides must be expressible as approved-within-scope, restricted, rejected or revoked. A source approval must not imply third-party/vendored content coverage or per-paper rights. Revocation must affect retrieval immediately and create an auditable event. Signatures provide integrity/authenticity under key control; they do not establish legal sufficiency.

Existing evidence-bound workflow already exists for manually controlled source/document decisions; this phase did not replace it or mark any decisions. Before extending schema, map its current version and establish migration compatibility against human-reviewed requirements. A reviewer and, where appropriate, counsel must assess source-specific terms. arXiv papers require individual metadata/terms review.

## Human review queue

Use `docs/license_reviews/` and the current manual register as preparation, not approval. For every source: inspect the actual license/notice, version, holder, source binding, checksum, documentation-specific and third-party terms, and proposed use. For every document exception: inspect provenance/content origin and matching source/document identity. Record a real reviewer and decision only after they perform the review. Pending, missing or conflicting evidence remains blocked.

## Gate status

**BLOCKED.** No production registry generation, signed production manifest, reindex, or legal conclusion was performed. The current RAG corpus is authorized only by the narrow local academic demo mechanism and remains legally unreviewed.
