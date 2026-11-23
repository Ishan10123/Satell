# Retrieval quality engineering

## Current measured baseline

- Runtime: dense cosine Qdrant, `default_top_k=8`, max top-k 20; reranker disabled in `configs/retrieval.json`.
- BM25/SQLite FTS5 and RRF are implemented/benchmark-only. ONNX reranking is benchmark-only. No Cohere service is used.
- Prior 30-query retrieval benchmark used source-topic heuristics, not human relevance labels: dense Recall@8 0.981, RRF 0.981, rerank 1.000; reranking was slower and had worse precision/MRR/nDCG on some measures. Do not treat this as production relevance proof.
- Live 30-question browser run: 13 verified, 6 partial, 4 abstained, 7 failed/rejected. No human factuality/citation entailment labels.
- Selected failure traces identify some retrieval mismatches, context-budget omissions, citation formatting failures, verifier rejection and safe comparison abstentions. Raw generations are unavailable for several cases; see `docs/academic_project/SATELL_CHAT_EXPERIENCE_RECOVERY_AND_QUALITY_REPORT.md`.

## New annotation validator

Added `scripts/validate_human_review_dataset.py`, a JSONL schema contract, blank/unreviewed `evaluation/human_review_template.jsonl`, and `tests/test_human_review_dataset.py`. It validates query/version identity, taxonomy, document/chunk labels, evidence requirements, abstention label, review origin, reviewer/timezone/confidence, duplicates and size. It refuses contradictory review metadata. It reports only counts and review-state quality; it does not infer truth or calculate a retrieval score.

All existing browser-evaluation expectations remain `heuristic`; no human judgments were fabricated. Reviewers must independently inspect source passages and use a versioned dataset. Do not run the heuristic set through this human schema as if reviewed without mapping and explicit reviewer work.

## Evaluation protocol

Pre-register dataset version, fixed query set, corpus/index/model versions, authorization scope, top-k, context budget and hardware. At least two reviewers label relevant docs/chunks, intent, answer concepts, mandatory evidence, expected abstention, source version and confidence. Adjudicate disagreements and track inter-reviewer agreement. Keep held-out queries. Run dense/BM25/hybrid/RRF/reranker against identical filters and query set; report Recall/Precision@k, MRR, nDCG, source diversity, duplicates, context admission and latency. Bootstrap confidence intervals where sample supports them. Do not activate an alternative based on heuristic metrics alone.

## Out-of-domain and context quality

Similarity score alone is not a relevance probability. Candidate acceptance needs reviewed calibration across in-domain, ambiguous, OOD and insufficient-evidence queries. Track source/topic agreement, exact identifier preservation, duplicate rate, document version conflicts, comparison coverage, and relevance of admitted chunks. Abstain without irrelevant citations when evidence is insufficient. No score threshold was changed in this phase.
