# Claim Verifier Reliability Remediation — 2026-11-17

## Confirmed implementation causes

- The verifier used `format: "json"`, so Ollama received no schema constraining response shape, claim IDs, verdict count, or citation IDs. Python validation correctly rejected malformed and incomplete results, but the model often returned output the parser could not use.
- The verifier calculated `max_prompt_bytes` from UTF-8 byte length and compared it with a token-window budget. That mixed units and caused q018's input to be rejected before an HTTP request.
- `OllamaGenerator` silently capped verifier output with `min(configured_max_output_tokens, 384)`. The checked-in configuration allows 512 tokens; the 384 cap had no configuration entry or documented evidence behind it.
- The previous diagnostic did not record `done_reason`, token counts, response character count, or output allowance. Historical truncation therefore cannot be established retrospectively.

## Runtime and tokenizer investigation

- The installed runtime reports Ollama **0.40.16**. `/api/show` identifies `qwen3.5:4b` as a Qwen 3.5 4.2B GGUF model using the `qwen35` renderer/parser; its reported capabilities include completion, tools, vision, and thinking.
- A local `/api/chat` probe using JSON Schema returned HTTP 200 and a schema-conforming verdict. That response reported `done_reason="stop"`, `eval_count=61`, `prompt_eval_count=42`, and 155 response characters. This demonstrates support for this installed runtime/model combination, but Python validation remains authoritative.
- The only checked-in tokenizers are for Nomic embeddings and MiniLM reranking. Neither is suitable as a Qwen generation tokenizer. No standalone Qwen tokenizer asset was found in the local Hugging Face cache. No model or tokenizer was downloaded.
- The existing shared `conservative_token_estimate` counts UTF-8 bytes; the verifier no longer uses that byte count. It now uses a separate documented estimate: ASCII alphanumeric runs at one token per two characters (minimum one), punctuation at one token, and non-ASCII code points at two tokens each. It is an approximation, not an exact Qwen count or a formal upper bound. The budget also reserves 64 tokens for message framing plus the configured safety margin.

## Changes

- Replaced the verifier's byte comparison with a token-oriented preflight estimate that includes the complete verifier system prompt, serialized claims and evidence, dynamic JSON Schema, message-format overhead, output allowance, and the 256-token safety margin. It rejects before HTTP when the estimate plus reservations exceeds the configured 4,096-token context. It does not discard claims or evidence.
- Switched from JSON-only mode to a generated JSON Schema. It restricts verdict count, claim-ID enum, status enum, citation-ID enums, field types, and additional properties. Existing Python checks still enforce exact claim coverage, uniqueness, valid citations, status consistency, and complete verdicts.
- Removed the unexplained 384-token clamp. Verifier output allowance is `min(configured_max_output_tokens, 64 + 128 * claim_count)`, capped by the configured 512 tokens. The one-claim local probe used 61 tokens; the allowance is bounded and sized by claim count.
- Added safe verifier metadata to successes and failures: `done_reason`, `eval_count`, `prompt_eval_count`, response character count, estimated input tokens, context size, safety margin, and output-token allowance. `done_reason="length"` has its own typed truncation error and always fails closed. Other malformed results are not labeled truncated.
- Updated diagnostic output to use stable error codes and to redact question text, generated response text, and retrieved passage text. Error details contain only fixed safe messages, exception type names, numeric metadata, and statuses.
- Preserved existing exception chaining, retries, fail-closed behavior, tenant/ACL filters, source approval state, and the unreviewed-index restriction.

## Before-and-after diagnostic

Fresh 24-question result: `evaluation/results/rag_generation_verifier_remediation_20261117_223802.json`.

| Previously failing question | Before | After |
|---|---|---|
| q001 | Malformed verifier JSON | Generated; 8/8 claims supported; verifier stopped normally. |
| q005 | Invalid verdict set | Partial answer; 4/5 claims supported; one claim omitted. |
| q014 | Invalid verdict set | Generated; 3/3 claims supported. |
| q018 | Input byte-budget rejection before verifier call | Generated; 9/9 claims supported. |
| q020 | Malformed verifier JSON | Generated; 9/9 claims supported. |

All five now completed without a verifier exception. They returned HTTP 200 with zero retries. Their verifier `done_reason` was `stop`; output counts ranged from 90 to 259 tokens, within allowances of 448 or 512. There were **zero truncation signals** across all 19 verifier calls. The old diagnostic lacked completion metadata, so this establishes the current rerun's behavior but cannot prove whether the earlier malformed responses were truncated.

The four previous citation failures remain fail-closed:

- q006: uncited-claim rejection, 3 extracted claims.
- q010: uncited-claim rejection, 5 extracted claims.
- q013: uncited-claim rejection, 7 extracted claims.
- q022: uncited-claim rejection, 2 extracted claims.

Overall, failures fell from **9/24 to 4/24**. The new result contains 17 generated answers, 2 partial answers, 1 insufficient-evidence abstention, and 4 uncited-claim rejections. No incomplete verdict was accepted.

For the four formerly verifier-failing questions that actually made a verifier request in the previous run, mean answer time changed from **5.23 s to 4.75 s**, mean verifier time from **5.71 s to 3.39 s**, and mean total generation-pipeline time from **11.05 s to 8.32 s**. q018 had no previous verifier request: its preflight rejection took 4.75 s total; it now completes both stages in 9.03 s (4.49 s answer generation plus 4.54 s verification). These are single-run diagnostic timings, not a benchmark.

Across the new 24-question run, means were 2.64 s answer generation, 2.56 s verification, 4.70 s generation pipeline, and 7.72 s end to end. For the 19 verifier calls, the estimator was 1.99–2.83 times Ollama's `prompt_eval_count` (median 2.42); it did not underestimate any of those samples. This is useful calibration, not proof of a universal token upper bound.

## Validation and state

- Verifier and generation regression tests: passed.
- Full suite: **215 passed, 1 skipped** (Windows symlink creation unavailable).
- `compileall`: passed.
- `pip check`: passed.
- Read-only index validation: passed for index `index-20261116T044640Z-b53eb021`, collection `rag_docs_v2`, 6,565 documents, and 58,856 chunks.
- Index remains `operator_authorized_unreviewed`. No manifest, raw document, Qdrant point/volume, approval decision, or authorization rule was modified.
- The saved diagnostic is redacted: it preserves IDs, status, counts, citations, timings, and verifier metadata, but not question text, retrieved passage text, or generated answer text.

## Files changed

- `src/rag_pipeline/generation/claim_verifier.py`
- `src/rag_pipeline/generation/ollama.py`
- `src/rag_pipeline/generation/errors.py`
- `src/rag_pipeline/generation/__init__.py`
- `scripts/test_rag_generation.py`
- `tests/test_claim_verifier.py`
- `tests/test_generation.py`
- `docs/claim_verifier_reliability_remediation_report_20261117.md`
- `evaluation/results/rag_generation_verifier_remediation_20261117_223802.json`

## Remaining issues

- Four questions still produce factual text without citations and are correctly rejected. Their prompts/output behavior needs separate work; citation validation must stay enabled.
- q005 returns a partial result because one of five claims was not supported; the claim is omitted.
- The token estimator remains an approximation because no suitable local Qwen tokenizer is installed. Keep Ollama's reported prompt counts in diagnostics and revisit calibration if the model/runtime changes.
- Local-model verdicts are not human correctness labels. The automated support rate is not an independently measured answer-quality score.
