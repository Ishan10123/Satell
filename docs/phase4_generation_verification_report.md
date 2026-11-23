# Phase 4 — Generation and Verification Report

Date: 2026-11-19

## Live path and configuration

All 30 prompts traversed Django’s real authenticated message endpoint and HTTP RAG adapter to FastAPI, Qdrant, Ollama generation and claim verification, then Django message/citation persistence. No synthetic response was included. Generation model was `qwen3.5:4b`; context window 8,192, output allowance 1,024, safety reserve 512, temperature 0. Dense retrieval only; no config or model budgets were increased.

## Results and failure classification

21 fully verified, 4 partially verified (Q01, Q13, Q14, Q23), 2 abstained (Q08, Q21), and 3 fail-closed (Q03, Q17, Q29). Q03/Q29 failed `insufficient_claim_citation_coverage`; Q17 passed citation validation but was rejected as `version_qualification_missing` on historical Python ordering evidence. There were no timeouts or service unavailable failures in this run. The verifier did not emit the invalid verdict/citation combinations seen in the immediately prior 30-query run after its system instructions were made explicit; no threshold or validator rule was relaxed.

| Query | Outcome | Stage | Failure code/reason |
|---|---|---|---|
| Q01 | partially_verified | partial / safe abstention | — |
| Q03 | failed | answer_validation | uncited_claim_rejected |
| Q08 | abstained | partial / safe abstention | — |
| Q13 | partially_verified | partial / safe abstention | — |
| Q14 | partially_verified | partial / safe abstention | — |
| Q17 | failed | claim_consistency | claim_consistency_rejected |
| Q21 | abstained | partial / safe abstention | — |
| Q23 | partially_verified | partial / safe abstention | — |
| Q29 | failed | answer_validation | uncited_claim_rejected |

Q08 and Q21 are abstentions, not answer successes. Q08 is an unsupported cross-source comparison; Q21 is a version-bounded question for which the system conservatively did not establish a supported claim.

## Latency

End-to-end Django HTTP duration: n=30, minimum 505.761 ms, p50 6614.243 ms, p95 11482.518 ms, maximum 12144.442 ms. Stage timings (ms):

| Stage | min | p50 | p95 | max |
|---|---:|---:|---:|---:|
| answer_generation | 900.576 | 3112.445 | 5364.489 | 5603.392 |
| answer_validation_rejected | 1.0 | 1.0 | 1.0 | 1.0 |
| claim_verification | 1130.08 | 3220.787 | 5300.167 | 6272.778 |
| context | 0.648 | 0.913 | 1.347 | 1.489 |
| dense_search | 46.138 | 74.833 | 113.001 | 131.412 |
| django_rag_http | 498.415 | 6604.156 | 11474.184 | 12136.035 |
| embedding | 19.064 | 25.656 | 95.996 | 2693.1 |
| generation | 2031.293 | 6578.993 | 10176.576 | 11726.346 |
| generation_pipeline | 984.892 | 6181.869 | 11027.499 | 11726.343 |

GPU was sampled during the earlier evaluation pass only: RTX 5050 Laptop GPU peak observed utilization 100%, VRAM 4,415/8,151 MiB. CPU and process-memory peaks were not measured; do not treat this as a complete capacity benchmark.

## Remaining issues

The final 7/30 answers were partial, abstained, or failed closed. General contradiction detection, broad source-version freshness, human relevance labels, and calibrated semantic verifier reliability remain incomplete. Keep the safe rejection/abstention rules.
