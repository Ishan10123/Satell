# Answer Grounding Remediation Report — 2026-11-17

## Changes

- Added a local claim-verification pass in `src/rag_pipeline/generation/claim_verifier.py`. The generator sends the answer's sentence-level claims and the authorized context passages to the configured local Ollama model. The verifier must return one strict JSON verdict per claim, and any missing, malformed, contradictory, unknown, or unbound verdict fails closed.
- Added claim/evidence identity to the generation path. Each citation now retains its Qdrant `chunk_id` and the exact assembled passage (including a shortened excerpt if context budgeting shortened it). API citation metadata includes `chunk_id`; evidence text stays internal to generation.
- The answer now includes only claims marked `supported`, with the citation IDs explicitly returned as supporting evidence. Unsupported, contradicted, and uncertain claims are omitted. If none are supported, generation abstains. Partial results carry a fixed notice that claims were omitted.
- Added a freshness gate for software release/version questions containing `latest`, `newest`, `most recent`, `current`, or `up-to-date`. It abstains because the local index does not provide a verified current-release signal. Historical/version-specific questions still proceed through local evidence.
- Added automated verifier counts and support-rate fields to generation diagnostics. They are explicitly labeled automated local-model estimates; the report does not treat them as human correctness labels.

## PyTorch `ingestion_authority` trace

The previously identified chunk is `ce24da3a90ed218410712161940255816a3f719cf3aaf52c41a740e50e453e5d`, from document `21c43e2df87337329e41478a7ffec7c5a36a50130f03bd0a7a7bc0e27397869d` (`pytorch`, `docs/nested.md`). The inventory record has no `ingestion_authority`; its status remains `candidate_not_reviewed` and license review remains pending. The corresponding parse and normalization artifacts also do not contain this run-time authorization field.

The pipeline has no durable intermediate chunk-run directory: indexing constructs chunks from the normalized document and builds parallel metadata records in memory. At `src/rag_pipeline/ingestion/indexing.py:283`, the indexer assigns `ingestion_authority="explicit_operator_instruction"` for an operator-authorized unreviewed run and sends those metadata records with the chunks to `upsert_chunks` (`:347`). `src/rag_pipeline/storage/qdrant_store.py:268-269` validates that authority before accepting the development-only payload. Existing indexing and authorization tests cover this assignment and downstream access gate. The sparse SQLite schema does not store the field. The exact historical Qdrant payload and its insertion path could not be inspected in this run because the configured Qdrant service (`127.0.0.1:6333`) is refusing connections. Therefore the stored discrepancy's exact cause is **unresolved**; assigning a cause or changing the current authorization code without the payload would be speculation. No Qdrant payload was repaired.

The PyTorch document remains unreviewed and excluded from production access. No license or source decision changed.

## Verification

- Full unit suite: **199 tests passed, 1 skipped**. The skipped test requires Windows symlink creation, which is unavailable in this environment.
- `python -m compileall -q src scripts tests`: passed.
- `python -m pip check`: passed (`No broken requirements found`).
- Synthetic live-model RAG smoke test: **passed**. It used actual local Ollama models and in-memory Qdrant, returned one cited synthetic answer, confirmed tenant/ACL/source filtering, and did not access the knowledge base.
- Read-only `ragctl validate-index`: **not completed**; it failed on connection refusal to `127.0.0.1:6333` before it could validate the collection.
- Fresh corpus generation diagnostic: **not completed** for the same Qdrant connection refusal. The attempted output path was `evaluation/results/remediation_release_20261117_202252.json`; no output file was produced.
- The actual Ollama service is reachable (`0.40.16`, configured model `qwen3.5:4b`). The latest-release gate is covered by unit tests and abstains before model generation.

## Data and authorization state

- No persistent Qdrant collection, point, or volume was modified. The smoke test used in-memory Qdrant.
- No raw files, inventory entries, approval decisions, or manifests were modified.
- All source approvals remain pending review. Production authorization filters are unchanged.
- Corpus point and document counts were not re-measured because Qdrant is offline; the last known index state remains the previously verified state, not a new validation result.

## Changed files

- `src/rag_pipeline/generation/claim_verifier.py` — new strict local claim-verifier client and claim extraction.
- `src/rag_pipeline/generation/ollama.py` — semantic verification, supported-claim rendering, diagnostics, and latest-release abstention.
- `src/rag_pipeline/retrieval/context.py` — internal evidence text and chunk identity bound to each citation.
- `src/rag_pipeline/service.py` — includes citation chunk identity in response metadata.
- `scripts/test_rag_generation.py` — automated claim-verification counts and explicit human-label status.
- `tests/test_claim_verifier.py` — verifier schema, evidence-binding, unknown-ID, and fail-closed tests.
- `tests/test_generation.py` — semantic filtering, malformed-verdict, and freshness-gate tests.
- `docs/answer_grounding_remediation_report_20261117.md` — this report.

## Remaining blockers and next steps

1. Start the existing Qdrant service without recreating the collection or its volume.
2. Rerun `\.venv\Scripts\python.exe scripts\ragctl.py validate-index` and confirm the manifest, point count, and collection health.
3. Rerun a fresh corpus diagnostic with an unused timestamped result path, for example:

   ```powershell
   $stamp = Get-Date -Format yyyyMMdd_HHmmss
   .\.venv\Scripts\python.exe scripts\test_rag_generation.py `
     --questions-file evaluation\questions_dense_diagnostic_20261116.jsonl `
     --output "evaluation\results\remediation_release_$stamp.json" `
     --max-questions 24 --top-k 5 --development-unreviewed
   ```

4. Inspect the PyTorch chunk's existing Qdrant payload read-only after the service is available. Only repair the insertion/metadata path if a reproducible provenance-based defect is established; do not authorize the document as part of that repair.
5. Treat local-model claim verdicts as triage metrics. Add blinded human claim/evidence labels before describing semantic precision or correctness as measured quality.

No live-corpus retrieval or production use should be considered verified until the Qdrant-backed validation and fresh diagnostic complete.
