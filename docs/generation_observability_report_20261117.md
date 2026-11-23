# Generation Observability and Error Classification — 2026-11-17

## Implemented

- Added a stable structured exception hierarchy for Ollama connection, timeout, HTTP, malformed-response, empty-response, citation, and uncited-claim failures, plus claim-verifier connection, timeout, HTTP, malformed-response, invalid-verdict, and input-budget failures.
- Preserved exception chaining. Where applicable, the original HTTPX exception remains `__cause__`; diagnostic output records its type only.
- The generator now reports answer-request time, verifier-request time, total generation-pipeline time, retry counts, and HTTP statuses separately. A stage that did not execute is `null` or omitted, never represented as a zero-duration request.
- The diagnostic script classifies failures by typed attributes rather than inspecting error strings. It writes fixed sanitized messages and does not include exception text, prompts, or response bodies in error details.
- `LocalRAGService` keeps citation-validation failures distinct internally while returning the existing safe abstention. Infrastructure and verifier failures remain typed internally and continue to result in a generic service-unavailable response at the API boundary.

## Diagnosis from the 24-question rerun

Run output: `evaluation/results/rag_generation_diagnostic_structured_20261117_220433.json`.

| Question IDs | Category | Evidence from diagnostics |
|---|---|---|
| q001, q020 | `claim_verifier_malformed_response` | Verifier HTTP 200, nested JSON parsing raised `JSONDecodeError`; answer generation completed; no retries. |
| q005, q014 | `claim_verifier_invalid_verdict_set` | Verifier HTTP 200, response did not satisfy the complete strict verdict schema; no retries. |
| q018 | `claim_verifier_input_budget_exceeded` | Verification request was not sent because serialized claims plus evidence exceeded the configured context budget. |
| q006, q010, q013, q022 | `uncited_claim_rejected` | Answer request returned HTTP 200, then factual prose without a citation was rejected. Verification did not run. |

These were observed causes in this run; they do not imply that future generation failures will share the same causes. No output was accepted without citation and semantic verification.

The 24-question status totals were 13 generated, 1 generated partially, 1 insufficient-evidence abstention, and 9 fail-closed errors. No connection, timeout, or Ollama HTTP failures occurred in this diagnostic. The verifier returned malformed or schema-invalid results for four questions; those remain unresolved model-output failures, not successful answers.

## Timing findings

For successful generated answers, mean request timings were approximately 2.17 seconds for answer generation and 2.87 seconds for claim verification; mean generation-pipeline duration was 5.04 seconds. Mean end-to-end time was 9.44 seconds because it additionally includes query embedding, dense and sparse search, fusion, reranking, and context assembly.

For q001, answer generation took 12.67 seconds and verification took 6.39 seconds, for a 19.51-second generation pipeline and 28.61 seconds end to end. Its embedding and reranking each took about 4.4 seconds, accounting for much of the additional elapsed time. This explains why end-to-end duration substantially exceeded earlier retrieval/reranking-only timings: those measurements did not include both local model requests.

All values are machine timings from one run and are not a performance benchmark.

## Validation and preserved state

- Full tests: **207 passed, 1 skipped** (Windows symlink test unavailable).
- `compileall`: passed.
- `pip check`: passed.
- Read-only index validation: passed for `index-20261116T044640Z-b53eb021`, collection `rag_docs_v2`, 6,565 documents, 58,856 chunks, status `ready`.
- Authorization mode remains `operator_authorized_unreviewed`; production authorization behavior was not changed.
- No ingestion, reindexing, collection recreation, or approval changes were performed.

## Modified files

- `src/rag_pipeline/generation/errors.py` — structured errors and stable error codes.
- `src/rag_pipeline/generation/ollama.py` — typed Ollama failures and stage timing metadata.
- `src/rag_pipeline/generation/claim_verifier.py` — typed verifier failures, request timing, retries, and status metadata.
- `src/rag_pipeline/generation/__init__.py` — public exception exports.
- `scripts/test_rag_generation.py` — sanitized structured diagnostics and stage timings.
- `src/rag_pipeline/service.py` — internal validation failure retention and stage timings, with fail-closed public behavior.
- `tests/test_generation.py` — deterministic Ollama and timing regressions.
- `tests/test_claim_verifier.py` — deterministic verifier transport, schema, and budget regressions.
- `docs/generation_observability_report_20261117.md` — this report.
- `evaluation/results/rag_generation_diagnostic_structured_20261117_220433.json` — timestamped diagnostic result.

## Remaining issues

- The five former generic failures are now diagnosed, not repaired: q001/q020 need valid verifier JSON; q005/q014 need complete, schema-valid verdict sets; q018 needs smaller verification input or a separately designed safe evidence-packing strategy.
- Four model answers still fail citation-presence validation. Do not relax that boundary; investigate prompt/output behavior separately if desired.
- Local model verdicts are not human correctness judgments. Human-labeled claim/evidence evaluation remains necessary before making semantic-quality claims.

## Next diagnostic command

This reruns the same 24-question set against the existing diagnostic-only index and writes a fresh timestamped result:

```powershell
$diagStamp = Get-Date -Format yyyyMMdd_HHmmss
$diagOut = "evaluation\results\rag_generation_diagnostic_structured_$diagStamp.json"
.\.venv\Scripts\python.exe scripts\test_rag_generation.py `
  --questions-file evaluation\questions_dense_diagnostic_20261116.jsonl `
  --output $diagOut --max-questions 24 --top-k 5 --development-unreviewed
```
