# RAG ingestion category eligibility audit

**Audit date:** 2026-11-18  
**Result:** **NOT_READY** — source/document authorization and license review remain unresolved. This audit did not change inventory, code, tests, approvals, manifests, or Qdrant.

## Executive finding

The 686 `review_required` rows are classified `unsupported_category` because the active documentation policy allows only `file_category="documentation"`. All 686 rows have categories outside that allowlist: 544 `structured_data` and 142 `supporting_artifact`. The classification is reproducible from `documentation_candidates()` in `src/rag_pipeline/ingestion/discovery.py`; the function checks category before extension and ingestion status.

The policy is conservative and broadly consistent with the written workflow: parser availability does not grant ingestion eligibility, unsupported files and supporting assets remain excluded, and source approval is required. However, the usefulness of some individual JSON/YAML files is not captured by a file-wide category rule. At least one JSON API reference and multiple YAML OpenAPI definitions look like plausible technical reference candidates. That warrants human, path-specific policy review; it does not justify enabling structured formats globally or treating public availability as license approval.

The primary audit weakness is diagnostic: `unsupported_category` hides the additional `review_required` or `supporting_asset` reason. There is also policy duplication between the config allowlist and the hard-coded authorization allowlist, and no checked-in code was found that generates the documentation manifest's category/status annotations. These are maintainability and auditability gaps, not evidence that the blocked records should be ingested.

## Implementation trace

### Where the fields come from

- `scripts/build_ingestion_inventory.py::main()` loads `configs/ingestion_sources.json`, calls `discover_documents()`, and writes the inventory. It does not classify documentation files itself.
- `src/rag_pipeline/ingestion/discovery.py::documentation_candidates()` reads `file_category`, `ingestion_status`, and `license_review_status` from `knowledge_base/metadata/documentation_manifest.jsonl`; it copies those fields into inventory rows and derives `discovery_status` and `eligible_for_processing`.
- `src/rag_pipeline/ingestion/discovery.py::arxiv_candidates()` sets research-paper `file_category` to `research_paper`, copies/defaults ingestion status, derives audit/license discovery status, and sets `eligible_for_processing` to `False` unconditionally.
- `knowledge_base/metadata/documentation_manifest.jsonl` and `documentation_manifest_summary.json` are the checked-in category/status source. A repository search of `src/` and `scripts/` found the inventory consumer but no executable documentation-manifest classifier/generator that assigns `structured_data`, `supporting_artifact`, `image`, `code`, or `review_required`. The origin and version of those annotations therefore cannot be reproduced from current code alone.

### Discovery and authorization rules

`configs/ingestion_sources.json` sets:

- `allowed_documentation_categories`: `documentation` only.
- `allowed_extensions`: `.md`, `.html`, `.rst`, `.pdf`, `.txt` only.
- `require_license_approval`: `true`.
- `approved_license_statuses`: `approved` only.

`src/rag_pipeline/ingestion/discovery.py::documentation_candidates()` checks each documentation record in this order:

1. File exists.
2. Category is in the configured category allowlist.
3. Manifest extension matches the path suffix.
4. Extension is in the ingestion allowlist.
5. Ingestion status is not `review_required` or `supporting_asset` and is one of `candidate_not_reviewed`/`candidate`.
6. If required, license status is approved.

`technically_eligible` is true only for `candidate` or `pending_license_review`; `eligible_for_processing` then additionally requires an approved license. Thus a valid documentation candidate with a pending license can have `discovery_status=pending_license_review` while its final eligibility flag is false.

`src/rag_pipeline/ingestion/approval.py::authorize_document()` independently checks file/path integrity, the supported extension set, `SUPPORTED_DOCUMENTATION_CATEGORIES={"documentation"}`, ingestion status (`ALLOWED_INGESTION_STATUSES={"candidate_not_reviewed","candidate"}`), discovery denials, checksum/size, and then evidence-backed source/document decisions and license status. The category and status checks occur before the explicit exclusion checks. `operator_authorized_unreviewed` is reached only after those file/category/status/integrity checks; it does not admit a non-document category or `review_required`/`supporting_asset` row.

`src/rag_pipeline/ingestion/parsing_job.py::parse_documents()` calls `authorize_document()` before `parse_file()`. `scripts/ragctl.py::main()` for `index` prefilters to candidate ingestion statuses and allowed extensions, then calls `authorize_document()`. `src/rag_pipeline/ingestion/indexing.py::index_normalized_run()` rechecks authorization before accepting normalized data and before indexing. None of these paths uses `eligible_for_processing` as its authorization decision; the field is a discovery/reporting result, not the final runtime gate.

## Current eligibility matrix

| Source/document class | Current category rule | Extension/status rule | License / authorization result |
|---|---|---|---|
| Documentation category, `.md/.html/.rst/.pdf/.txt`, candidate status | Allowed | Must pass path, checksum, and status checks | Pending license yields `pending_license_review` and `eligible_for_processing=false`; evidence-backed approval is still required at authorization time. |
| `structured_data`, including `.json/.xml/.yaml/.yml` | Rejected: only `documentation` is allowed | These formats are also outside the five-extension ingestion allowlist; the affected inventory rows have `review_required` | Rejected before parsing. Parser support does not override category, extension, or status policy. |
| `supporting_artifact` | Rejected | The 142 records have `review_required`; most extensions are outside the ingestion allowlist | Rejected before parsing. |
| `image` | Rejected | All 583 records have `supporting_asset`; image extensions are outside the allowlist | Rejected before parsing. |
| `code` | Rejected | 2,067 rows are candidate-status, but their extensions are outside the allowlist | Rejected before parsing. |
| `research_paper` | Handled by separate arXiv audit and document-approval rules | Inventory has 107 paper records | `arxiv_candidates()` always reports `eligible_for_processing=false`; paper authorization is per document and requires evidence and a document decision. |

The category allowlist is represented twice: in `configs/ingestion_sources.json` and as the constant `SUPPORTED_DOCUMENTATION_CATEGORIES` in `src/rag_pipeline/ingestion/approval.py`. They currently agree, but the authorization function does not receive the configured category set. A future config change that adds a category would make discovery and authorization disagree: discovery could accept it while authorization still rejects it.

The parser registry is deliberately broader. `configs/parser_registry.json` enables JSON, JSONL, YAML/YML, CSV, XML, TOML, and INI parsers. `src/rag_pipeline/ingestion/registry.py::load_config()` only verifies that every ingestion-allowed extension has an enabled parser; it does not add parser-supported extensions to the ingestion allowlist. The parser registry's own note states that parser availability is independent of authorization. `docs/indexing_workflow.md` likewise says unsupported/supporting/third-party assets remain excluded.

## Inventory evidence

Read-only recount of `knowledge_base/metadata/ingestion_inventory.jsonl`:

- Total records: **9,932**.
- `review_required`: **686**, all `discovery_status=unsupported_category`.
- `supporting_asset`: **583**, all `file_category=image` and all `discovery_status=unsupported_category`.
- `supporting_artifact` category: **142**, all `ingestion_status=review_required` and all `discovery_status=unsupported_category`.
- `structured_data` category: **544**, all `ingestion_status=review_required` and all `discovery_status=unsupported_category`.
- `license_review_status=pending`: **9,932**; `eligible_for_processing=false`: **9,932**.
- `discovery_status` totals: `unsupported_category` **3,336**, `pending_license_review` **6,596**.
- All **686** `review_required` paths exist on disk; their exclusion is policy/status-related, not missing-file fallout.

The 686 `review_required` records by source are Docker **567**, Qdrant **98**, Python 3.13 **13**, PyTorch **4**, FastAPI **2**, and Hugging Face Transformers **2**. Category and extension detail:

| Category | Count | Extension breakdown | Ingestion status |
|---|---:|---|---|
| `structured_data` | 544 | `.yaml` 535, `.json` 4, `.yml` 3, `.xml` 1, `.conf` 1 | All `review_required` |
| `supporting_artifact` | 142 | `.css` 119, `.gliffy` 8, `.gotmpl` 4, `.dot` 3, `.excalidraw` 1, `.csv` 1, `.inv` 1, `.woff2` 1, no extension 4 | All `review_required` |
| `image` | 583 | `.png` 337, `.webp` 110, `.svg` 102, `.avif` 21, `.jpg` 12, `.gif` 1 | All `supporting_asset` |

The `supporting_asset` and `supporting_artifact` labels are not synonyms: the former is an ingestion-status value attached here to 583 `image` category rows; the latter is a file category attached here to 142 `review_required` rows. Both are denied. Because discovery and authorization evaluate category first, the inventory's primary reason for both groups is `unsupported_category`, not `explicitly_excluded`. The `supporting_asset` status would also fail the later ingestion-status check if category/extension checks passed. This is consistent in outcome (deny) but not transparent in reported reason.

The 6,596 `pending_license_review` records comprise the 6,489 documentation-category records and 107 arXiv records. For documentation candidates, pending license prevents `eligible_for_processing`; `arxiv_candidates()` hardcodes false. This confirms that no file-type classification can resolve the separate license gate.

## Representative files and usefulness

The following files were read locally for type/content inspection only; none was parsed into the RAG corpus or changed:

- `docker/docs/data/api-reference.json` (`file_category=structured_data`, `.json`, about 2.24 MB) contains six API entries and substantial descriptive/API material. This is a plausible technical-reference candidate, subject to checking overlap with adjacent Markdown and source scope.
- `docker/docs/content/reference/api/ai-governance/api.yaml` (`structured_data`, `.yaml`) declares an OpenAPI 3.2.0 document for the Docker AI Governance Policy API. The inventory has **7** Docker `.yaml` paths under `content/reference/api/`; a path-based sample shows that at least some structured records are API schemas, not generic build debris.
- `python/.../_static/glossary.json` contains documentation terms and definitions, but is a generated static UI data file; usefulness and duplication should be reviewed before inclusion.
- `python/.../_static/opensearch.xml` is an OpenSearch Description document with the Python docs search URL and encoding metadata. It is valid structured XML, but has little standalone answer content.
- `python/.../_static/basic.css` contains Sphinx theme/style rules, not instructional prose. The `.woff2` font is binary (47,972 bytes; WOFF2 signature), not ordinary text. These are appropriately excluded from text chunking absent a separate asset/OCR/rendering use case.
- Python `.buildinfo` (231 bytes) records Sphinx build/configuration fingerprints. It is build metadata, not user-facing documentation. `objects.inv` is Sphinx cross-reference inventory metadata. These should remain excluded from ordinary RAG text.
- The only CSV in this review group is `pytorch/docs/headless/reranker/gain/data.csv`; its location suggests evaluation data and warrants specific purpose/rights review rather than default inclusion.

Conclusion: **some structured files are plausibly useful**, especially API schemas and carefully selected glossary/configuration material. The entire category is not uniformly useful, nor uniformly irrelevant. The correct decision unit is a reviewed source path/purpose (and possibly a scoped category), not “all JSON/YAML/XML” based on extension.

## Pipeline consistency and mismatches

1. **Parser vs ingestion policy:** JSON/XML/YAML support exists in `configs/parser_registry.json`, but these extensions and categories are excluded by `configs/ingestion_sources.json` and `authorize_document()`. This is intentional separation, documented in the parser registry and workflow. It is not a parser defect.
2. **Manifest classification provenance:** current repository code reads the documentation manifest categories/statuses but does not generate them. The exact classifier that labeled these files `structured_data`, `supporting_artifact`, or `review_required` is not reproducible here. This is an auditability gap.
3. **Diagnostic precedence:** category is checked before extension/status in both discovery and authorization, so an excluded row reports `unsupported_category` even when it is also explicitly `review_required` or `supporting_asset`. This does not create an authorization bypass, but it hides the full reason.
4. **Duplicated category policy:** discovery uses config `allowed_documentation_categories`, authorization uses a hard-coded category set. Values match now, but can drift.
5. **Eligibility field vs runtime:** `eligible_for_processing` is not used as the parse/index authorization decision. The index CLI prefilters statuses/extensions and then performs evidence/file authorization. In addition, the arXiv discovery path permanently writes `eligible_for_processing=false`; after a paper gets its own review, rebuilding inventory still would not reflect that authorization in this field. Treat this flag as discovery-time summary, not a live source of authorization truth.
6. **No observed ingestion bypass:** parse and index re-check categories, status, file integrity, and license/source/document decisions. The supported-operator development mode does not bypass category or excluded-ingestion-status checks. Production readiness remains subject to the reviewed manifest/API gate.

## Existing tests and coverage gaps

Relevant tests are in `tests/test_authorization.py` and `tests/test_configuration.py`:

- `AuthorizationTests.test_explicit_operator_run_bypasses_review_but_keeps_document_scope` verifies a code category remains rejected even in operator-unreviewed mode.
- `AuthorizationTests.test_explicitly_excluded_manifest_record_is_blocked` verifies `review_required` is rejected when the category/extension are otherwise allowed.
- `AuthorizationTests.test_unsupported_extension_is_blocked` covers an unsupported extension.
- `DiscoveryTests.test_discovery_preserves_manifest_status_and_lists_excluded_extensions` checks one allowed documentation record and one code/supporting-asset record.
- `DiscoveryTests.test_project_ingestion_configuration_validates` checks the configured sources and license requirement.
- `tests/test_configuration.py` checks that ingestion-allowed extensions have parsers; it does not assert that all parser-enabled formats are eligible.

Missing focused coverage:

- No discovery/authorization fixtures for representative JSON, XML, YAML, CSS, font, build-info, or Sphinx inventory files.
- No tests pin the complete category × extension × ingestion-status decision matrix or the category-before-status reason precedence.
- No assertion explains why a row that is both `review_required` and wrong-category is reported as `unsupported_category`.
- No tests prove that `.json/.yaml/.xml` parser availability does not alter the production allowlist or approval requirements.
- No test checks that `eligible_for_processing` is a discovery-time summary and not the index authorization gate, or documents the arXiv hardcoded false behavior.
- No test or checked-in generator provides reproducible category/status classification for the documentation manifest.

No tests were executed during this read-only audit; the test suite was inspected, not modified or run.

## Recommendations

### Policy decisions — require human review

1. Keep the current conservative policy until source owners/reviewers decide whether any exact structured paths belong in the documentation scope. Do not enable all JSON/YAML/XML by extension.
2. If OpenAPI references or glossary data are desired, review those exact paths for relevance, duplication, generated content, third-party inclusions, and source license/scope. Record evidence-backed source/document decisions using the existing human workflow. No file type or public URL establishes a license grant.
3. Keep CSS, fonts, images, Sphinx build metadata, and navigation indexes excluded from ordinary text ingestion. Any OCR, visual asset, or diagram workflow should be a separate reviewed policy.
4. Continue requiring the existing source and document authorization workflow and the production reviewed-index gate; this audit provides no basis to change either.

### Minimal implementation improvements — do not apply in this audit

1. Make documentation manifest category/status generation reproducible and versioned, or record its generator/version and classification rationale with the manifest.
2. Keep configured category eligibility and `authorize_document()` on one shared policy source so a configuration change cannot produce discovery/authorization disagreement.
3. Preserve multiple exclusion reasons (or explicitly name the first/highest-priority reason) so `unsupported_category` does not conceal `review_required`/`supporting_asset` and unsupported extension reasons.
4. Add tests for the actual inventory-shaped examples and for category/extension/status/license interaction, including the invariant that parser enablement never implies authorization.
5. Clarify or rename/report `eligible_for_processing` as discovery-time technical eligibility, and test its distinct meaning for documentation versus research papers. Do not make it authoritative without reconciling it with approvals and the index CLI.

## Authorization status and readiness

**NOT_READY.** This audit does not resolve rights or authorize any source. Inventory evidence remains 9,932 pending licenses and zero eligible rows. The source approval workflow and per-document review must be completed by authorized human reviewers before real ingestion, and the document authorization/index readiness conditions must pass. No approval or policy change is implied by the useful-schema examples above.
