# Phase 4B — Citation Observability and Claim Consistency

Date: 2026-11-18

## Outcome

Implemented more specific internal failure diagnostics for citation validation and claim verification, plus an opt-in, bounded artifact writer for controlled local academic evaluation. Added a deterministic consistency gate for a narrow, known Python dictionary-ordering/version case. Existing citation validation, semantic verification, authorization and abstention gates remain fail-closed.

This does not make retrieval quality or answer quality production-ready. The consistency check is intentionally narrow; it is not a general contradiction detector.

## Root causes established

The Phase 4A report at `docs/phase4a_rag_quality_failure_investigation.md` records these causes and evidence:

- The eight fully rejected queries stopped at generation citation validation. The previous API-compatible error codes grouped multiple validation conditions into `citation_validation_failed` or `uncited_claim_rejected`, so the saved samples could not identify whether the particular answer had a missing marker, unknown ID, bad syntax, bad mapping, or insufficient per-claim coverage.
- The generator raised after receiving the model response, and the ordinary run artifacts did not retain that original answer or the parsed citation-to-claim mapping. The public API intentionally returned a safe fallback or generic dependency response.
- The claim verifier evaluated claims independently. Its old result preserved verdict status and citation IDs but not the exact claim text, mapped evidence chunk/document IDs, or a reason code. Consequently, partial answers could not be reconstructed from the saved result alone.
- Q17 was reported as 16/16 independently supported while saying both that dictionaries iterate in arbitrary order and that insertion order is guaranteed beginning with Python 3.7. The historical/current context established a version transition, but there was no cross-claim consistency stage.
- Phase 4A also found 75 of 160 candidate occurrences omitted at the configured context budget. This work did not alter retrieval, context selection, token limits, or the corpus.

These are observability and consistency gaps. The original citation and claim checks were already fail-closed; their thresholds have not been relaxed.

## Implemented changes

### Citation validation diagnostics

`src/rag_pipeline/generation/citation_validation.py` now checks the actual validation conditions and raises a structured `CitationFailure.reason`:

| Reason | Condition |
| --- | --- |
| `missing_citation_marker` | No bracketed citation marker is present. |
| `missing_citation_id` | A citation marker is present but contains no ID, or no valid ID was parsed. |
| `invalid_citation_syntax` | An `S` citation marker is malformed or unterminated. |
| `unknown_citation_id` | The parsed citation ID is not in the assembled context. |
| `invalid_citation_mapping` | Context citation IDs are invalid/duplicated or required source, document, or chunk mapping is absent. |
| `insufficient_claim_citation_coverage` | The existing per-claim coverage check fails. |

`src/rag_pipeline/generation/ollama.py` maps these back to the existing API-compatible high-level error classes and codes. The detailed reason, parsed claim-to-citation rows, parsed IDs, and safe citation metadata are attached to the error for the restricted evaluation writer. The existing exception codes remain unchanged for the existing citation failure classes.

### Claim verification detail

`src/rag_pipeline/generation/claim_verifier.py` now returns a `ClaimVerdict` containing the claim ID, exact claim text, status, supporting and contradicting citation IDs, corresponding evidence chunk/document IDs, and a deterministic rejection reason where applicable. `ClaimVerificationRun.overall_verdict` reports `verified`, `partially_verified`, or `rejected`.

The verifier still rejects malformed, incomplete, duplicate, unknown, or internally inconsistent verdict rows. For example, an `unsupported` or `uncertain` row carrying a support/contradiction citation is invalid; a `contradicted` row must provide contradictory citations and cannot simultaneously claim support.

### Controlled evaluation artifacts

`src/rag_pipeline/generation/evaluation_artifact.py` implements a local JSONL writer with:

- Default-off activation in `scripts/run_api.py` via `RAG_EVALUATION_DIAGNOSTICS_ENABLED=0`.
- Opt-in environment variables `RAG_EVALUATION_DIAGNOSTICS_ENABLED=1`, `RAG_EVALUATION_ARTIFACT_PATH`, `RAG_EVALUATION_MAX_RECORDS`, and `RAG_EVALUATION_MAX_BYTES`.
- Path containment within the project root, target symlink rejection, atomic replacement, in-process locking, FIFO record retention, and byte retention. Defaults are 200 records and 10,000,000 bytes; configured limits are range-checked.
- File mode `0600` and directory mode `0700` where the host OS supports POSIX permission bits.
- Request correlation ID, question, response status, original generated answer, parsed claims/citation IDs, citation mappings, validation reason, per-claim verifier results, consistency findings, and a small allowlist of model configuration fields.
- No credential/config secrets, raw verifier response, internal prompt, or retrieved evidence passages.
- A sanitized fixed warning if an artifact write fails; artifact errors do not fail or change the RAG answer.

`src/rag_pipeline/api/app.py` rejects an artifact store unless authorization mode is explicitly `local_academic_demo`. The writer is not part of the API response schema, and raw generations are not returned to callers. `.gitignore` excludes the default artifact path.

The artifacts intentionally contain user questions and model-generated content when explicitly enabled. They are plaintext local files; filesystem access control and controlled retention remain the operator's responsibility. Windows does not provide the same POSIX mode semantics, so the chmod assertions are tested only where supported. The writer serializes concurrent threads in a process; the current API runner uses one Uvicorn worker. Multi-process shared-file writing is not provided.

### Q17 contradiction and version consistency

`src/rag_pipeline/generation/claim_consistency.py` adds deterministic checks for supported claims about regular Python dictionary ordering:

- Opposite supported ordering claims whose version scopes overlap produce `contradictory_supported_claims`.
- An unqualified ordering claim supported only by a historical Python documentation item before 3.7 produces `version_qualification_missing` and identifies the supporting chunk.
- Explicit, non-overlapping pre-3.7 and since-3.7 statements are allowed when the semantic verifier supports each claim.
- Unsupported claims are not converted into consistency findings or accepted by this stage.

`OllamaGenerator.generate()` invokes this check after semantic claim verification. Any finding raises `ClaimConsistencyError`; `LocalRAGService` returns the existing safe abstention. This does not independently decide whether arbitrary prose is contradictory. New concepts, phrasing, languages, and other versioned behaviors remain outside the detector and need broader evaluation before any general claim can be made.

The Q17 regression now exercises generation, citation parsing, mocked supported verdicts, and the consistency gate. It confirms the Q17-style answer is rejected with `version_qualification_missing` while retaining two verifier rows in the restricted diagnostic error state.

## API and security compatibility

- The request/response schemas were not changed.
- Existing coarse citation error codes and safe generic API error text are preserved.
- Detailed failure reasons do not include raw model output in HTTP responses. The Django HTTP client retains its current diagnostics allowlist and does not forward the detailed reason into browser-facing fields.
- Evaluation capture is disabled by default and application startup rejects enabling it outside local academic demo authorization mode.
- Existing authorization checks, signed demo registries, source/document decisions, Qdrant data, index manifests, model settings, retrieval configuration, context window, and retrieval strategies were not changed.
- No BM25, RRF, reranking, ingestion, re-indexing, or real-corpus evaluation was run as part of this change.

## Files changed

- `.gitignore`
- `src/rag_pipeline/api/app.py`
- `src/rag_pipeline/generation/citation_validation.py` (new)
- `src/rag_pipeline/generation/claim_consistency.py` (new)
- `src/rag_pipeline/generation/errors.py`
- `src/rag_pipeline/generation/evaluation_artifact.py` (new)
- `src/rag_pipeline/generation/claim_verifier.py`
- `src/rag_pipeline/generation/ollama.py`
- `src/rag_pipeline/generation/__init__.py`
- `src/rag_pipeline/service.py`
- `scripts/run_api.py`
- `tests/test_phase4b_diagnostics.py` (new)
- `tests/test_generation.py`
- `tests/test_claim_verifier.py`
- `tests/test_api.py`
- `docs/phase4b_citation_observability_implementation_report.md` (this report)

## Test results

Executed on 2026-11-18:

- Full RAG suite: `.venv\Scripts\python.exe -m unittest discover -s tests -v` — **256 tests, 255 passed, 1 skipped**. The skipped test requires symlink creation unavailable in this Windows environment.
- Focused citation, consistency, artifact, generation, verifier, API, and service regression run — **81 tests passed** before the final two integration regressions were added; the complete final suite above includes them.
- Python compile check: `.venv\Scripts\python.exe -m compileall -q src/rag_pipeline scripts/run_api.py tests` — passed.
- Django/PostgreSQL: `docker exec django_app-django-1 python manage.py test --keepdb -v 1` — **39 tests, 37 passed, 2 skipped**.
- Django/SQLite: `docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=:memory: django_app-django-1 python manage.py test -v 1` — **39 tests, 37 passed, 2 skipped**.

The Django tests were run against the existing healthy container and did not modify application records. No live corpus query or browser test was performed for this phase.

## Remaining unresolved issues

1. The deterministic contradiction detector covers only Python dictionary ordering. General contradictions and version-sensitive claims still need a broader, carefully evaluated method; an LLM-only checker is not considered sufficient.
2. Historical-version detection depends on available evidence metadata (`relative_path`/title) and a known Python documentation path pattern. Missing provenance or alternate naming can prevent the deterministic rule from firing.
3. The semantic verifier's rejection reason is a deterministic category derived from its verdict, not a natural-language explanation of its reasoning.
4. Diagnostic artifacts are plaintext, intentionally sensitive evaluation records. Enable them only for controlled local evaluation, restrict filesystem access, and remove the file according to the evaluation retention policy. Retention limits do not encrypt data.
5. Cross-process shared artifact-file coordination and production-grade audit storage are not implemented.
6. Phase 4A's retrieval/context omissions, coarse source-reference navigation, query-specific failed outputs, and production authorization/legal-review blockers remain as previously reported. This work did not claim to fix retrieval relevance or production readiness.

## Assessment

The failure mechanisms are now more identifiable at the generation/validation boundary, and Q17's specific historical/current dictionary-order contradiction is rejected. Citation validation and claim verification remain fail-closed. The improvements reduce diagnostic ambiguity and cover one confirmed consistency defect; they do not address all retrieval, context-budget, citation-navigation, or general reasoning quality issues.
