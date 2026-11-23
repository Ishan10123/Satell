# Phase 6 evaluation results and human-review protocol

**Date:** 2026-11-20. No new real-corpus evaluation or human labels were generated in this Phase 6 setup task.

## Existing baseline (separate runs)

| Run | Evidence | Result | Limitation |
|---|---|---|---|
| Retrieval benchmark | 30 heuristic query labels, Phase 2 reports | Dense Recall@8 0.981; RRF 0.981; rerank Recall@8 1.000; rerank slower and some rank metrics lower | Labels are source/topic heuristics, not expert relevance judgments. |
| Live browser generation | `evaluation/results/satell_chat_quality_live_20261119.json` | 13 verified, 6 partial, 4 abstained, 7 failed/rejected; citations on 19/30 | No human factuality, entailment or completeness judgments. |
| Selected failure diagnostics | `evaluation/results/satell_chat_quality_failure_diagnostics_20261119.json` | Observed retrieval/context/citation/verifier stage flags for selected queries | Raw generated answers and exact rejected claim text unavailable. |
| Final direct live query check | `docs/academic_project/evidence/test_run_summary_20261119.md` | One failed/no-citation, then one verified/two-citation non-synthetic response | Two requests do not establish quality or reliability. |

## Annotation tooling added

`evaluation/human_review_template.jsonl` is explicitly unreviewed. `scripts/validate_human_review_dataset.py` validates a versioned record, intent taxonomy, relevant doc/chunk IDs, answer concepts, evidence requirements, abstention expectation, source versions and human review metadata. It rejects duplicate dataset/query IDs and prevents unreviewed records claiming a reviewer/confidence. Tests in `tests/test_human_review_dataset.py` cover these gates. The tool only validates structure; it does not grade answers, invent labels or publish metrics.

Example validation command:

```powershell
.\.venv\Scripts\python.exe scripts\validate_human_review_dataset.py evaluation\human_review_template.jsonl
```

The unedited template is expected to fail because its question/query ID contain placeholders. Replace it only while preparing a real dataset record; a structurally valid `unreviewed` record remains unreviewed and is never considered human truth.

## Human review process

Reviewers independently assess question intent, relevant documents/chunks, required evidence, answer concepts, expected abstention, version scope, factuality, completeness and citation entailment. Record reviewer, UTC-offset timestamp and confidence. Adjudicate disagreements and preserve dataset version and corpus/index/model/prompt IDs. Keep heuristic labels distinct. Protect private prompts and judgments with access and retention controls.
