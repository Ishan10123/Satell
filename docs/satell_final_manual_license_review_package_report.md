# Satell Final Manual License Review Package Report

## Package totals

- Source-level packets generated: 14.
- Individual arXiv packets generated: 107.
- Master source matrix: 14 rows. Master paper matrix: 107 rows.
- All human decision fields remain pending or blank.

## Source-by-source evidence status

- `arxiv_ai_systems`: 15 individual papers; 15 historical external-only rights lookups and 0 missing/failed. No collection-wide license assigned.
- `arxiv_artificial_intelligence`: 13 individual papers; 12 historical external-only rights lookups and 1 missing/failed. No collection-wide license assigned.
- `arxiv_database_vector_search`: 15 individual papers; 15 historical external-only rights lookups and 0 missing/failed. No collection-wide license assigned.
- `arxiv_information_retrieval`: 15 individual papers; 14 historical external-only rights lookups and 1 missing/failed. No collection-wide license assigned.
- `arxiv_llm_rag`: 16 individual papers; 16 historical external-only rights lookups and 0 missing/failed. No collection-wide license assigned.
- `arxiv_llm_transformers`: 15 individual papers; 15 historical external-only rights lookups and 0 missing/failed. No collection-wide license assigned.
- `arxiv_machine_learning`: 18 individual papers; 18 historical external-only rights lookups and 0 missing/failed. No collection-wide license assigned.
- `docker`: source `VERIFIED_SOURCE_BOUND`; docs `PARTIAL_EVIDENCE`; third-party review `PARTIAL_EVIDENCE`.
- `fastapi`: source `VERIFIED_SOURCE_BOUND`; docs `PARTIAL_EVIDENCE`; third-party review `PARTIAL_EVIDENCE`.
- `huggingface_transformers`: source `VERIFIED_SOURCE_BOUND`; docs `PARTIAL_EVIDENCE`; third-party review `PARTIAL_EVIDENCE`.
- `postgresql_18`: source `EXTERNAL_EVIDENCE_ONLY`; docs `EXTERNAL_EVIDENCE_ONLY`; third-party review `PARTIAL_EVIDENCE`.
- `python_3_13`: source `PARTIAL_EVIDENCE`; docs `VERIFIED_LOCAL_ARTIFACT`; third-party review `PARTIAL_EVIDENCE`.
- `pytorch`: source `PARTIAL_EVIDENCE`; docs `EXTERNAL_EVIDENCE_ONLY`; third-party review `PARTIAL_EVIDENCE`.
- `qdrant`: source `MISSING_EVIDENCE`; docs `MISSING_EVIDENCE`; third-party review `PARTIAL_EVIDENCE`.

## Individual paper evidence summary

- `EXTERNAL_EVIDENCE_ONLY`: 105 prior rights lookups; each is per paper/version and was recorded HTTP 200 on 2026-11-16.
- `MISSING_EVIDENCE`: 2: 0610039, 0611122.
- Historical labels: CC BY 4.0: 37; CC BY-NC-ND 4.0: 4; CC BY-NC-SA 4.0: 9; CC BY-SA 4.0: 3; LICENSE_NOT_ESTABLISHED: 2; arXiv non-exclusive distribution license (limited distribution grant): 52.
- Rights labels vary across papers. ArXiv distribution terms are not treated as general reuse permission; third-party figures and quotations remain separate.
- All 107 PDFs are present and SHA-256-matched to inventory; that proves integrity, not permission.

## Key source gaps/conflicts

- Four sources have checksum-matched source-bound local catalog artifacts; PyTorch source files do not establish the separate docs-repository scope.
- Python has local license/copyright pages but no catalog binding. PostgreSQL has a PDF legal notice and an official external license reference, but no local source-bound license artifact.
- Qdrant has no local docs license artifact; its pinned landing_page LICENSE URL was previously recorded as HTTP 404.
- PostgreSQL inventory version 18 differs from PDF metadata version 18.7. PyTorch docs BSD statement is in separate `pytorch/docs`, not bound to the inventory-pinned code repository snapshot.
- Generated, vendored, embedded, code-example, image, diagram, font, logo, publisher, and third-party content needs manual inspection.

## Generated paths

- `docs/license_reviews/README_manual_review_guide.md`
- `docs/license_reviews/sources/<source_id>_human_review_packet.md` - 14 files
- `docs/license_reviews/arxiv_papers/<arxiv_id>_human_review.md` - 107 files
- `docs/license_reviews/master_source_review_matrix.csv`
- `docs/license_reviews/arxiv_paper_review_matrix.csv`
- `docs/license_reviews/evidence_index.md`
- `docs/license_reviews/validation_report.md`
- `docs/satell_final_manual_license_review_package_report.md`

## Validation and preservation

- Source/paper counts, exact IDs, duplicate checks, packet paths, CSV columns, file existence, and local hashes were verified.
- The existing approval/inventory/evidence/manual-register/manifest and metadata file digests are recorded in the validation report; no package-generation command wrote to them.
- No source or paper was approved or rejected. No Qdrant or application data was changed.
- Official-source search was performed on 2026-11-18 where available. Current direct arXiv API access timed out; historical external findings are clearly dated and must be rechecked by the human reviewer.

**Final readiness verdict: `NOT_READY`.** Human licensing decisions and source/document authorization remain pending.

- Current source approval registry: 14/14 records remain `pending_review`; `document_approvals.json` is absent.
