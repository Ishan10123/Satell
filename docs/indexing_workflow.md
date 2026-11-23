# Indexing readiness and source approval

`scripts/ragctl.py` is the local workflow CLI. It does not approve any source by itself. An approval decision records the reviewer, UTC timestamp, license name, notes, source-bound evidence reference, evidence checksum, and (for document decisions) the stable document ID. Evidence artifacts and their catalog records must remain inside the project and match their recorded SHA-256 values.

## Read-only review

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py inventory
.\.venv\Scripts\python.exe scripts/ragctl.py license-report
.\.venv\Scripts\python.exe scripts/ragctl.py authorization-report
.\.venv\Scripts\python.exe scripts/ragctl.py index-status
```

`license-report` counts evidence records and validates that referenced evidence files still match their checksums. Evidence presence is not a legal determination. A source decision must explicitly establish what documentation scope it covers; third-party assets remain excluded. arXiv papers require distinct evidence and an individual document decision.

## Record explicit decisions

### FastAPI documentation: first source review

Review the exact current FastAPI repository license artifact recorded in the evidence catalog. These commands only display and hash the local copy; they do not make the decision:

```powershell
Get-Content .\knowledge_base\raw\official_documentation\_sources\fastapi\LICENSE
Get-FileHash .\knowledge_base\raw\official_documentation\_sources\fastapi\LICENSE -Algorithm SHA256
.\.venv\Scripts\python.exe scripts/ragctl.py license-report
```

Confirm that the FastAPI row reports a verified candidate evidence record, review the license terms and intended use, and decide whether the scope below is acceptable. The scope is limited to inventory entries with `source_type=documentation`, `file_category=documentation`, an allowed text/document extension, and a candidate ingestion status. Unsupported files, supporting assets, and third-party assets remain excluded. The decision does not cover other source IDs.

After a human reviewer has completed that review, run this explicit command, replacing the reviewer identity and notes with the actual review details:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-source fastapi `
  --decision approved --reviewer "<reviewer name>" --license-name "MIT" `
  --scope documentation_candidates `
  --evidence knowledge_base\metadata\license_evidence.jsonl `
  --notes "Reviewed the FastAPI LICENSE artifact and approved only eligible FastAPI documentation candidates; excluded third-party and supporting assets."
```

Then confirm the decision and its evidence binding, and inspect the resulting authorization count:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py license-report
.\.venv\Scripts\python.exe scripts/ragctl.py authorization-report
```

The approval command records the actual UTC decision time. It fails if the `fastapi` catalog row is missing, its path escapes the project, the artifact is missing, or the SHA-256 does not match. The command has not been run as part of implementation; FastAPI remains pending until a human reviewer chooses to run it.

For any source, provide the catalog containing a matching `source_id`, evidence file path, and SHA-256, and declare the allowed approval scope:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-source docker `
  --decision approved --reviewer "Reviewer Name" --license-name "Apache-2.0" `
  --scope documentation_candidates `
  --evidence knowledge_base\metadata\license_evidence.jsonl `
  --notes "Reviewed license scope for documentation candidates; excluded third-party assets remain out of scope."
```

For an arXiv source, first record a separate `paper_source_metadata_only` source decision using evidence about the source metadata (a catalog row without `document_id`). That decision only permits review of the source metadata; it does not approve any paper. Then, for each paper, the evidence catalog row must include that paper's stable `document_id`, and record an individual decision:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-document <document_id> `
  --source-id arxiv_llm_rag --decision approved --reviewer "Reviewer Name" `
  --license-name "CC BY 4.0" --evidence knowledge_base\metadata\license_evidence.jsonl `
  --notes "Verified this paper's own license evidence."
```

The source decision command for the metadata-only step uses `--scope paper_source_metadata_only`. The CLI rejects a source decision with a document-specific paper evidence row, and paper authorization remains blocked until that paper's separate `approve-document` decision is approved with matching evidence.

`pending_review` and `rejected` are valid explicit decisions too. No command makes an implicit approval. Missing, mismatched, changed, or out-of-project evidence blocks authorization.

## Parse, normalize, and index

After the required human reviews and document license metadata are complete:

```powershell
.\.venv\Scripts\python.exe scripts/run_parsing_job.py
.\.venv\Scripts\python.exe scripts/normalize_parsed_run.py <parse-run-directory>
.\.venv\Scripts\python.exe scripts/ragctl.py index --normalized-run knowledge_base\processed\normalized_runs\<generated-run-id> --dry-run
.\.venv\Scripts\python.exe scripts/ragctl.py index --normalized-run knowledge_base\processed\normalized_runs\<generated-run-id>
.\.venv\Scripts\python.exe scripts/ragctl.py validate-index
.\.venv\Scripts\python.exe scripts/ragctl.py index-status
```

The index command refuses if eligible candidates are unauthorized. Dry-run does not call the embedding provider or create/upsert vectors. Actual indexing uses local Ollama, deterministic chunk IDs, and Qdrant upserts; it does not delete collections. The readiness manifest is marked `building` first and becomes `ready` only if all authorized normalized documents complete and Qdrant's point count matches. A failed or incomplete run remains unavailable to retrieval.

The source registry remains pending unless a reviewer explicitly records evidence-backed decisions. A separate operator-authorized development run was performed on 2026-11-16 as described below. Its index is marked `operator_authorized_unreviewed`; this is not a license approval and does not enable API retrieval for pending sources.

## Parser registry and structured data

`configs/parser_registry.json` maps file extensions to registered parser names and resource limits. JSON, JSONL, YAML/YML, CSV, XML, TOML, and INI extraction retains field paths, headers, row numbers, and parent/child relationships as segment heading metadata. Structured files are bounded by file size, nesting, node/record, column, and field limits. YAML uses the safe loader and rejects aliases; XML rejects DTD/entity declarations; malformed inputs fail closed.

Parser availability is separate from authorization. The registry does not add structured formats to `configs/ingestion_sources.json`'s allowed extension scope, approve a source, or make any file eligible by itself. A reviewer must explicitly define documentation scope and make evidence-backed decisions before enabling these files for a reviewed run. Images, fonts, code, diagrams, generated files, and supporting artifacts remain excluded by default. The full per-record proposal is in `knowledge_base/metadata/unsupported_format_review_20261116.json`.

The parser registry also now provides bounded extractors for source code (`.py`, `.js`, `.mjs`, `.ts`, `.java`, `.cs`, `.go`, `.rs`, `.sh`), diagram/config text (`.dot`, `.gotmpl`, `.conf`, `.excalidraw`, `.gliffy`, `.svg`) and Office Open XML (`.docx`, `.xlsx`, `.pptx`). `.ipynb` and `.sql` are available for development review. Python symbols use AST metadata; other source formats are structurally segmented without executing or compiling files. Office packages receive archive size, ratio, entry, and member-path checks. Notebook outputs are discarded. The live ingestion allowlist remains `.md`, `.html`, `.rst`, `.pdf`, and `.txt`; parser availability alone does not make these additional formats candidates. See [ingestion format support](ingestion_format_support.md) and the reconciled [`unsupported_extension_distribution_20261116.json`](../knowledge_base/metadata/unsupported_extension_distribution_20261116.json). The old 2,801 extension tally omitted 535 `.yaml` records; the corrected report accounts for all 3,336 records.

The 2026-11-16 human review package is at `docs/license_human_review_guide.md` and `knowledge_base/metadata/license_human_review_checklist_20261116.csv`, `license_human_review_packet_20261116.json`, and `license_evidence_inventory_20261116.json`. It contains all 14 source records and one row for each of 107 arXiv papers. Paper-specific rights links were retrieved for 105 pages; retrieval gaps remain visible for human follow-up. This package is review material only. All source and document decisions remain pending, and the approval registries were not modified.

New normalization outputs use version 2 identities: `content_id` is SHA-256 of canonical normalized segments; `document_identity` is SHA-256 of normalized source ID plus relative path. The older `document_id` remains present for current-index compatibility. `canonical_content_map.jsonl` maps one content ID to every distinct source/path provenance, and chunks carry both document identifiers. Existing normalized runs, approval registries, `rag_docs_v2`, and its Qdrant volume are not migrated by adding this design.

## Explicit operator-authorized development ingestion

When the project owner explicitly instructs an unreviewed development ingest, both parsing and indexing accept `--operator-authorized-unreviewed`. This records `operator_authorized_unreviewed` on parse outcomes, vector payloads, summaries, and the index manifest. It does not alter approval registries or claim a license review occurred. The path still limits input to parser-supported documentation candidates; unsupported assets and excluded records are not parsed. Run it only when that operator authorization is intended:

```powershell
.\.venv\Scripts\python.exe scripts/run_parsing_job.py --operator-authorized-unreviewed
.\.venv\Scripts\python.exe scripts/normalize_parsed_run.py knowledge_base\processed\parse_runs\<parse-run-id>
.\.venv\Scripts\python.exe scripts/ragctl.py index --normalized-run knowledge_base\processed\normalized_runs\<normalized-run-id> --dry-run --operator-authorized-unreviewed
.\.venv\Scripts\python.exe scripts/ragctl.py index --normalized-run knowledge_base\processed\normalized_runs\<normalized-run-id> --operator-authorized-unreviewed
```

### Completed development ingest (2026-11-16)

Using the explicit operator instruction, the project parsed and normalized 6,596 supported candidate paths and indexed 6,565 unique legacy document IDs into `rag_docs_v2` (58,856 chunks). Three Markdown failures were recovered selectively; 31 repeated paths shared canonical legacy IDs. The remaining 3,336 unsupported or out-of-scope files are recorded in `knowledge_base/metadata/ingestion_audit_20261116.json` and are itemized with proposed handling in `knowledge_base/metadata/unsupported_format_review_20261116.json`. Four distinct legacy document IDs with identical normalized content remain indexed as separate documents. The index manifest is `knowledge_base/metadata/index_manifests/rag_docs_v2.json` and is marked `ready` with `authorization_mode: operator_authorized_unreviewed`.

The earlier partial collection `rag_docs_v1` is preserved, including 20 points left by failed attempts. `rag_docs_v2` contains the completed run and the three selectively recovered documents. The smoke-test collection and Qdrant volume were preserved. All 14 source approvals remain pending. The API derives query scope from approved sources and requires `license_review_status=approved`, so this unreviewed development corpus cannot be served through the API. Use the evidence-backed review workflow above, then build a reviewed index before real retrieval.
