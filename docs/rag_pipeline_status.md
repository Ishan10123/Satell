# Local RAG Pipeline Status

Updated: 2026-11-15

## Implemented

The repository contains source discovery and inventory, evidence-backed source approvals, individual document decisions, parsing, provenance-preserving normalization, model-compatible chunking, local embeddings and generation, managed Qdrant storage, dense retrieval, bounded prompt context, and a local FastAPI service.

`scripts/ragctl.py` provides `inventory`, `license-report`, `authorization-report`, `approve-source`, `approve-document`, `index --dry-run`, `index`, `validate-index`, and `index-status`. Approval records require an explicit status, reviewer, license name, notes, declared scope, and source/document-bound evidence. Evidence artifact and record hashes are rechecked at authorization time. Research papers require metadata-only source review plus separate evidence and approval per stable document ID. Document rejection overrides source approval.

The tokenizer is the pinned Hugging Face tokenizer JSON for `nomic-ai/nomic-embed-text-v1.5` at revision `e9b6763023c676ca8431644204f50c2b100d9aab`, SHA-256 `d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66`. It is matched to local Ollama `nomic-embed-text:v1.5` (768 dimensions; pinned digest in `configs/embedding.json`). Local token counts, including `[CLS]` and `[SEP]`, matched Ollama `prompt_eval_count` for eight synthetic samples. Chunk limits reserve the special tokens within the configured 2048-token local context.

The versioned readiness manifest records the index ID, collection, embedding model and digest, dimensions, cosine distance, tokenizer identifier/version/hash, full chunk config, authorized source IDs, document/chunk counts, source inventory checksum, timestamp, and `building`/`ready`/`failed` state. Retrieval validates this manifest against Qdrant and current tokenizer/chunking/model configuration. API startup validates configuration without creating an index or requiring live model/Qdrant health; `/health` remains available when unindexed, while `/ready` and `/v1/query` fail with 503 until the manifest and collection match.

## Current corpus state

- 9,932 inventory records in 14 source groups.
- All 14 source decisions remain `pending_review`.
- 0 documents are authorized; current records are pending license review or unsupported assets.
- No real knowledge-base document has been parsed, chunked, embedded, or indexed during this work.
- No production index manifest or collection was created. Existing Qdrant collections were left untouched.
- License evidence exists for only a subset of documentation sources. Evidence existence is not a legal determination and does not automatically cover third-party assets. The arXiv metadata currently lacks per-paper license evidence, so papers remain individually blocked.

## Validation performed

- `python -m unittest discover -s tests`: 117 tests pass (synthetic/in-memory Qdrant only).
- `python -m compileall -q src scripts`: passes.
- `python -m pip check`: no broken requirements.
- `scripts/validate_embedding_tokenizer.py`: eight of eight synthetic local Ollama token-count comparisons match.
- CLI read-only reports show all sources pending, zero authorized documents, and no ready index manifest.

## Remaining before real corpus indexing

1. A human must review and explicitly decide every source, with evidence that covers the intended documentation scope. Missing source evidence remains pending.
2. Every arXiv paper needs its own license evidence row bound to its stable `document_id` and a separate decision.
3. Prepare or update the evidence catalog and document license review state for each intended source; excluded third-party assets remain outside ingestion.
4. Run parsing, normalization, an indexing dry run, then indexing only after the authorization report shows the intended documents authorized.
5. Build a representative retrieval and answer evaluation set before claiming corpus quality or production readiness.

See [indexing_workflow.md](indexing_workflow.md) for exact approval, indexing, and API commands. This project is indexing-ready in code for synthetic validation, but no real corpus or production index is approved or ready yet.
