# Phase 2 RAG Retrieval Evaluation

**Run date:** 2026-11-18  
**Evaluation:** Same eight prompts submitted before and after targeted changes through the running Django message endpoint. Full result payloads are in [baseline JSON](phase2_rag_evaluation_baseline.json) and [final JSON](phase2_rag_evaluation_results.json).

## Configuration and benchmark

The live API used dense Qdrant retrieval (`strategy=dense`, `top_k=8`), `ContextAssembler`, Ollama `qwen3.5:4b`, and claim-level verification. ONNX reranking was disabled. BM25/RRF code was present but inactive. A read-only Dense/Hybrid retrieval benchmark used the signed demo registry scope and existing FTS5 index; it did not modify the index. Hybrid took roughly 2.75–4.34 seconds per query while dense took roughly 0.09–0.21 seconds. Hybrid reordered results, with mixed title/heading relevance and no consistent improvement. Dense remains selected. No ONNX scores exist because the reranker is disabled.

The retrieval benchmark was a ranking comparison, not a labeled recall benchmark. No adjudicated relevance set was supplied, so relevance descriptions below use returned source/title/heading evidence and are not presented as formal recall.

## Before and after

| Measure | Baseline | Final run |
|---|---:|---:|
| Prompts | 8 | 8 |
| Retrieval strategy | Dense | Dense |
| Candidate hits where a request completed | 5/8 | 8/8 |
| Citation-bearing responses | 0/8 | 5/8 |
| Fully verified responses | 0 | 4 |
| Partially verified responses | 0 | 1 |
| Safe validation failures | 3 | 2 |
| Safe abstentions without citations | 2 | 1 |
| HTTP/client failures | 3, unclassified in original persisted metadata | 0 |

The final run's five cited responses contained 16 citation snapshots total. One of those responses was partially verified; the verifier rejected unsupported claim(s) while preserving only supported citations. The other four were verified. The change is substantial in this sample, but model output is stochastic and this single eight-question comparison is not a quality guarantee.

## Per-question findings

| # | Topic | Final top result (document ID prefix, dense score) | Final context | Final answer state | Diagnosis |
|---|---|---|---:|---|---|
| 1 | Python list vs tuple | `cec0a6b1`, 0.8091; Python tuple/sequence documentation | 3 chunks / 4,063-byte estimate; 5 budget exclusions | 2 citations, verified | Baseline context admitted 1 chunk (772 bytes) and abstained. The 2,500-byte cap was the confirmed evidence bottleneck. |
| 2 | FastAPI path and query parameters | `209b04a4`, 0.8557; “Query Parameters” | 6 / 4,695; 2 exclusions | 5 citations, verified | Baseline request failed before answer persistence. The final path returned a correct source-specific candidate set and verified answer. |
| 3 | Compose `service_healthy` | `632e66c3`, 0.8618; Docker `services-healthcheck` | 4 / 4,542; 4 exclusions | No citations; abstention | `uncited_claim_rejected`: generation emitted a factual claim without a valid citation; validation rejected it. No context or authorization exclusion caused the final failure. |
| 4 | Qdrant collection and point | `7f9a1678`, 0.8757; Qdrant “Create a Collection” | 7 / 4,906; 1 exclusion | 5 citations, partially verified | The verifier retained supported claims and rejected unsupported ones. Retrieval found topic-matched Qdrant documentation. |
| 5 | Transformers pipeline API | `d8605734`, 0.7975; “Pipeline” | 4 / 4,796; 4 exclusions | 2 citations, verified | Final retrieval was source-specific and generation was verified. Baseline request had no persisted retrieval diagnostics. |
| 6 | PyTorch `torch.no_grad` | `d4846204`, 0.7675; Autograd “Locally disabling gradient computation” | 5 / 4,691; 3 exclusions | No citations; abstention | `uncited_claim_rejected`; strict answer validation blocked uncited model output. Retrieval reached the relevant source and heading. |
| 7 | PostgreSQL transactions | `b0c77039`, 0.8334; PostgreSQL documentation | 2 / 4,205; 6 exclusions | 2 citations, verified | Baseline had `citation_validation_failed`; final output passed claim/citation validation. Qdrant payload headings for this source are sparse, but evidence was sufficient in this run. |
| 8 | Docker health dependencies vs FastAPI validation | `f90b8afb`, 0.7503; Docker tutorial | 3 / 4,683; 5 exclusions | No citations; safe abstention | Comparison coverage gate requires both named sources (Docker and FastAPI). Top-eight dense results were Docker-only, so `comparison_evidence_complete` returned false and generation did not run. This is ranking/source coverage, not an authorization filter. |

The full JSON captures every retrieved document/source/chunk ID and score, stage timing, diagnostic, citation and answer for the final run. The original baseline has no retrieval fields for its three failed upstream requests because the old persisted path did not retain safe upstream classifications; the report does not invent those causes.

## Confirmed causes and changes

1. **Evidence budget was too restrictive.** Baseline context commonly excluded 5–8 of eight retrieved chunks. In the first prompt the assembler kept one chunk; the cross-source comparison kept none. The retrieval config now allows up to 5,000 conservative byte-estimated tokens and 2,500 per comparison document group. The generator's dynamic budget still caps evidence based on query/system prompt space, so the 8K context and output reservation remain unchanged.
2. **Django rejected complete diagnostics.** FastAPI returned 17 diagnostic fields while the HTTP client allowed at most 16. The client now accepts at most 24; a 17-field response regression test passes. This fixed responses previously classified as `rag_client_error`.
3. **Context omission IDs could be misattributed at `max_chunks`.** `ContextAssembler.assemble` read the previous loop's payload before assigning the current hit. Assignment order is corrected and covered by a test asserting the exact omitted chunk ID.
4. **Two final prompts still fail closed.** The Docker and PyTorch generations were rejected for `uncited_claim_rejected`; citation validation and claim verification were not bypassed. The comparison prompt lacked FastAPI evidence and safely abstained before generation.
5. **Transient baseline service errors are not retrospectively classifiable.** The initial conversation stored no diagnostics for questions 2, 4 and 5. The current API now emits validated static error code/stage headers for future upstream errors; no raw exception text is exposed.

## Retrieval exclusions and authorization

No final result reported `authorization_recheck`, `document_not_in_demo_allowlist`, or `document_identity_mismatch`. Context exclusions were `context_budget`. Retrieved hits were documentation from the signed local academic demo scope. Research papers, unsupported categories and unregistered documents remained excluded by the existing filters. No source or document authorization records, legal statuses, production approvals, manifest or Qdrant points were changed.

## Conclusion

The targeted changes improved context coverage and removed a confirmed Django response-schema rejection. Five of eight prompts now return cited answers, including four fully verified and one partially verified. The pipeline still safely abstains or rejects two prompts, has limited cross-source coverage for comparisons, and shows roughly 5–9 second answer/verification latency. This remains a local academic demonstration, not production retrieval readiness.
