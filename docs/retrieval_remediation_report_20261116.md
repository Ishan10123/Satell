# Local RAG Retrieval Remediation Report — 2026-11-16

## Executive summary

The confirmed context-loss and candidate-pool defects were fixed and exercised against the existing local index. Comparison retrieval now keeps relevant candidates through reranking, diversifies evidence, and abstains when a named comparison source is not eligible after the authorization recheck. Context prompts use a conservative UTF-8 byte estimate, are bounded against the configured Qwen context window, and record Ollama's actual `prompt_eval_count` when returned.

This is an engineering remediation, not production approval. The local index remains `operator_authorized_unreviewed`, all 14 source decisions remain `pending_review`, and the production API must continue returning 503 for this index. Semantic claim entailment is not automatically proven: citation presence is validated, but citations can still be attached to unsupported or misattributed claims. Human answer review remains required.

## Root-cause analysis

| Issue | Evidence and root cause | Fix | Verification |
|---|---|---|---|
| PostgreSQL evidence disappeared under the context cap | `ContextAssembler` used `len()` and dropped an entire passage when its cost exceeded remaining space. A long top passage could leave no usable evidence. | Default budget measure now counts UTF-8 bytes as a conservative estimate for byte-fallback tokenization. The top passage can be safely excerpted, explicitly marked as shortened, and retain its citation metadata. Full prompt content, system instructions, query, formatting, output reserve, and configured 4,096-token context window are bounded. | Synthetic five-passage PostgreSQL regression retains the top evidence within budget. The final 24-question diagnostic answered the PostgreSQL index-performance case with a passage and citation. Ollama-reported input counts were 362–927; conservative estimates were 1,466–3,168. |
| Distinct chunks within one document were collapsed | Context assembly treated document-level `content_id` as chunk identity, suppressing later chunks from that document. | Removed `content_id` deduplication from passage assembly. Chunk IDs and exact normalized passage text still deduplicate repeats. | Added same-document distinct-chunk regression. Exact duplicate passage text still collapses. |
| Hybrid evaluation discarded the reranker candidate pool | `test_hybrid_retrieval.py` passed `top_k` to RRF as the output limit even when reranking was enabled. RRF therefore returned only five candidates before reranking. The service path already requested the larger pool. | The evaluation CLI now gives RRF the configured candidate limit when reranking is enabled, then lets the reranker select final `top_k`. | Read-only dense/BM25/RRF/ONNX trace now puts Qdrant candidates into the PostgreSQL/Qdrant top five and a PyTorch candidate into the PyTorch/Transformers top five. |
| Comparison results over-concentrated on a few documents | The reranker selected only by score; large passages could consume the entire context budget. | Added configurable comparison detection, source/document caps, per-document context budget, omitted passage IDs/reasons, and a comparison evidence-coverage gate. The gate checks named source aliases when two or more sources are named; otherwise it requires at least two documents. | In the 24-question diagnostic, m01–m04 generated with multiple relevant documents. m05 abstained because its PyTorch candidate failed the authorization recheck. |
| PyTorch comparison evidence failed context authorization | Candidate chunk `ce24da3a90ed218410712161940255816a3f719cf3aaf52c41a740e50e453e5d`, titled `torch.nested`, has `license_review_status=operator_authorized_unreviewed` and ACL `local-admin`, but `ingestion_authority` is absent. The development context recheck requires `explicit_operator_instruction`. | Kept the fail-closed recheck. The diagnostic now records `authorization_recheck`; a named-source comparison missing PyTorch abstains. No Qdrant payload was rewritten. | m05 diagnostic: expected sources `huggingface_transformers` and `pytorch`; available authorized context contained only Transformers; result `abstained_incomplete_comparison_evidence`. |
| Uncited and invalid-citation model output could be returned or become a service error | The generator previously checked only for at least one citation and whether citation IDs existed; it did not require a citation for each factual sentence. | Added sentence-level citation-presence validation, tighter local answer format, explicit abstention recognition, and typed citation/uncited-claim validation errors. Service maps rejected answers to a generic fail-closed abstention. | Tests cover uncited claims, allowed disclaimers, unknown citations, explicit insufficiency, and service abstention. The final 24-question run rejected 2 invalid-citation and 3 uncited-claim answers; 2 answers abstained for insufficient evidence. |
| Test discovery depended on an implicit import path | `test_model_tokenizer.py` imported `rag_pipeline` while other tests use `src.rag_pipeline`, causing a failure under plain `unittest discover`. | Standardized those imports. | Plain `python -m unittest discover -s tests -q` passes. |

## Retrieval and answer evaluation

Fresh read-only local diagnostic: `evaluation/results/remediation_release_20261116.json` (24 questions, hybrid dense + FTS5 BM25 + RRF + local ONNX reranking, local Ollama generation, explicitly gated development-unreviewed mode).

- 16 generated, 5 rejected during answer validation (2 invalid/missing citations, 3 uncited factual claims), 2 explicit insufficient-evidence abstentions, and 1 abstention because a required comparison source was unavailable after authorization checks.
- Direct answerable cases: 9 generated, 1 rejected for uncited claims.
- Multi-document cases: m01 PostgreSQL/Qdrant generated from 3 documents and 2 sources; m02 retrieved 4 FastAPI documents but its answer was rejected for uncited claims; m03 Docker generated from 2 documents; m04 Python generated from 2 documents; m05 abstained because the PyTorch point lacked the required operator-authority payload.
- End-to-end latency across this diagnostic: median 2,371 ms; p95 2,990 ms. These are local measurements from this run, not a production service benchmark.
- Stage medians / p95 (ms): embedding 31.9 / 54.8; dense search 19.5 / 40.9; sparse search 123.1 / 145.3; fusion 0.1 / 0.1; ONNX rerank 243.3 / 272.4; context assembly 0.7 / 1.0; generation 2,037.6 / 2,605.6 (19 calls). Memory usage was not measured.
- Conservative input estimates: 1,466–3,168 bytes/tokens; Ollama prompt evaluation reported 362–927 tokens. This provides an observed safety margin but is not a tokenizer equivalence claim.
- The PostgreSQL/Qdrant comparison now includes both sources. The PyTorch/Transformers comparison correctly abstains under current point metadata. One direct-answer case (a04) and one multi-document answer (m02) were rejected for uncited claims.

The results do **not** demonstrate semantic entailment. In the prompt-injection set, no hidden system prompt or local secret was disclosed, and the unsupported `[S99]` citation was rejected. However, the model answered the “latest FastAPI release” adversarial question with citations. Citation syntax cannot prove that the cited passage supports the claim or that its temporal framing is valid. Human review and a labeled answer-quality set remain necessary before any claim of hallucination resistance.

## Security and authorization

- Context authorization rechecks tenant, source, ACL, review status, and explicit operator authority in development mode. Document rejection continues to override source approval.
- Comparison evidence coverage is checked after authorization; missing expected source evidence produces an abstention.
- Invalid citation IDs and uncited factual sentences fail closed. API service converts those validation failures to a generic abstention, without returning the model text.
- Existing tests cover API token rejection, request scope control, unreviewed-index readiness rejection, document rejection, malformed registries, and path traversal. A symlink-escape test was added but skipped because this Windows environment could not create a symlink (`OSError`).
- No API authorization filter or approval decision was changed. The existing production API remains unavailable for the unreviewed manifest.

## Verification results

- Full tests: **192 run, 191 passed, 0 failed, 1 skipped**. The skipped test is the Windows symlink-escape test described above.
- `compileall`: passed.
- `pip check`: passed, no broken requirements.
- `scripts/ragctl.py validate-index`: passed. Manifest remains ready at index ID `index-20261116T044640Z-b53eb021`, 6,565 documents, 58,856 chunks, 768 dimensions, authorization mode `operator_authorized_unreviewed`.
- `scripts/run_synthetic_rag_smoke.py`: passed. It used in-memory Qdrant and synthetic text only.
- Exact Qdrant point count after verification: **58,856**.

## Data preservation

- Raw documents: unchanged.
- Qdrant collections and volumes: unchanged; the live collection was read only. Exact point count remains 58,856.
- Existing dense manifest: unchanged.
- Sparse index: unchanged.
- Source and document approval registries: unchanged; all 14 sources remain `pending_review`.
- No source or document was approved, no ingestion or reindexing was run, and no real-corpus index was written.
- The synthetic smoke test used an in-memory collection and deleted only its synthetic test point/collection.

## Changed implementation and verification files

- Retrieval/context/generation: `src/rag_pipeline/retrieval/context.py`, `src/rag_pipeline/retrieval/rerank.py`, `src/rag_pipeline/service.py`, `src/rag_pipeline/generation/ollama.py`, `src/rag_pipeline/generation/__init__.py`, `src/rag_pipeline/configuration.py`.
- Configuration and diagnostics: `configs/retrieval.json`, `scripts/run_api.py`, `scripts/test_hybrid_retrieval.py`, `scripts/test_rag_generation.py`.
- Tests: `tests/test_retrieval_context.py`, `tests/test_rerank.py`, `tests/test_generation.py`, `tests/test_service_retrieval_modes.py`, `tests/test_workflow_readiness.py`, `tests/test_model_tokenizer.py`.
- New evaluation artifacts: `evaluation/remediation_comparison_questions_20261116.jsonl`, `evaluation/remediation_m05_question_20261116.jsonl`, and timestamped JSON outputs under `evaluation/results/remediation_*.json`. Earlier intermediate diagnostic outputs are retained; `remediation_release_20261116.json` is the final 24-question run.
- `E:\RAG_Project` is not a Git worktree, so `git status`/diff could not provide a baseline; the paths above list files edited or generated during this remediation.

## Remaining blockers

### Code and retrieval quality

1. The PyTorch document’s missing `ingestion_authority` must be reconciled with the source manifest and indexing metadata. Do not bypass the context check or edit the live point. A separately planned, additive metadata repair/migration would need tests and a before/after point-count validation.
2. Citation validation now enforces citation presence and ID validity, but not semantic entailment. The injected “latest FastAPI release” case demonstrates this limitation. A representative labeled answer-review set and a local entailment/claim-checking approach need evaluation before relying on generated answers.
3. Six of 24 answers were rejected rather than returned. Rejection is safe, but the answer format needs further quality work, especially on questions with weak or contradictory evidence.
4. The retrieval question set is small and human judgments are not complete. These metrics cannot establish broad retrieval quality or non-hallucination.

### Human decisions

All 14 source approvals remain pending. Human reviewers must evaluate the license evidence and documentation scope. Each research paper still needs an individual evidence-backed decision. The current index cannot be promoted to production before those decisions and an appropriately reviewed index exist.

### Operations

Production `/ready` and `/v1/query` remain intentionally unavailable for the current manifest. No live production query was run. A production API token, reviewed index, and operational review are still required.

## Reproduction commands (PowerShell, from `E:\RAG_Project`)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\ragctl.py validate-index
.\.venv\Scripts\python.exe scripts\run_synthetic_rag_smoke.py

$diag = "evaluation\results\remediation_replay_$((Get-Date).ToString('yyyyMMdd_HHmmss')).json"
.\.venv\Scripts\python.exe scripts\test_rag_generation.py `
  --questions-file evaluation\independent_verification_questions_20261116.jsonl `
  --output $diag --max-questions 24 --top-k 5 --development-unreviewed

.\.venv\Scripts\python.exe scripts\test_hybrid_retrieval.py `
  --question "Compare PostgreSQL B-tree indexes with Qdrant vector indexes: what data and query patterns is each designed for?" `
  --top-k 5 --candidate-top-k 30 --rerank --development-unreviewed --json
```

The `--development-unreviewed` flag is only for local diagnostics. It does not authorize the production API or change any source/document decision.
