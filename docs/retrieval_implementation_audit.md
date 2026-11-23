# Retrieval implementation audit

> Historical Phase 0 baseline. Dense diagnostics, local BM25, hybrid RRF, the pinned local reranker, strategy wiring, and human-label tooling have since been added. See [the current implementation status](retrieval_progress_20261116.md) and [the reranked hybrid diagnostic](reranked_hybrid_diagnostic_20261116.md).

Audit date: 2026-11-16  
Project: `E:\RAG_Project`  
Phase: 0, read-only repository and existing verification review

## Scope and current index

This audit inspected configuration, service orchestration, local Ollama clients, dense retrieval, Qdrant storage and manifests, context construction, API/authentication, tests, dependencies, and the synthetic smoke runner. It did not run a corpus scan, modify approval registries, issue corpus queries, or alter Qdrant.

The current `rag_docs_v2` index manifest is `ready`, with 6,565 documents and 58,856 chunks/points, using the pinned 768-dimensional `nomic-embed-text:v1.5` vector and the `dense` vector name. Its authorization mode is `operator_authorized_unreviewed`. All 14 source approval records remain pending review. The index has been validated by `ragctl validate-index`; that validates index/manifest compatibility and point count, not retrieval relevance.

The existing synthetic smoke test exercises real local Ollama embedding and generation with an **in-memory** Qdrant collection and synthetic passages. It does not read or query `rag_docs_v2`. API tests use ASGI transport and service stubs; Qdrant unit tests use in-memory Qdrant. No real question has been evaluated against the corpus in this audit.

## Existing architecture

```text
FastAPI /v1/query
  -> bearer authentication and server-derived tenant/principal
  -> reload evidence-backed source approval registry
  -> LocalRAGService
      -> DenseRetriever
          -> OllamaEmbeddingProvider (/api/embed)
          -> QdrantVectorStore (named dense vector, tenant/source/license/ACL filter)
      -> ContextAssembler (authorization recheck, dedupe, source references, bounded context)
      -> OllamaGenerator (/api/chat; citation marker validation)
```

There is no retrieval-specific config file. The Qdrant endpoint and collection are in `configs/indexing.json`; model names, digests, limits and loopback Ollama URL are in `configs/embedding.json` and `configs/generation.json`. The Qdrant compatibility marker and the versioned ready-index manifest separately pin the collection vector/model/chunking and index counts.

## Component status

| Component | Existing implementation | Tested | Required work |
|---|---|---|---|
| Embeddings | `OllamaEmbeddingProvider` checks loopback URL, installed model/tag digest, request limits, vector count/dimensions, finite values and zero vectors; retries and timeout are configured. Model and 768 dimensions are pinned. | MockTransport unit tests; prior synthetic smoke used local Ollama. No corpus-query latency or dimensions observation report. | Measure and return query embedding latency; map connection/timeout failures into a stable retrieval error; optional bounded cache only if justified. Preserve strict model/digest checks. |
| Dense retrieval | `DenseRetriever` embeds one normalized query and calls Qdrant. Qdrant uses the `dense` cosine vector and returns score plus payload. | Qdrant scope/filter behavior tested in-memory; synthetic end-to-end smoke tested against in-memory Qdrant. No diagnostic has queried `rag_docs_v2`. | Add typed retrieval result/rank metadata, configurable score threshold and safe filters; validate actual collection search behavior. Do not issue production corpus queries until an explicit development access path is designed. |
| BM25 | No BM25/sparse implementation, sparse-vector configuration, sparse dependency, or persisted sparse index was found in `src`, `tests`, `scripts`, `configs`, or `requirements.txt`. | None. | Select deterministic local tokenization and a versioned sparse-index artifact synchronized to the current index/chunk IDs. Define update/rebuild and authorization filtering before implementation. |
| Hybrid retrieval | Not implemented. | None. | Add strategy selection only after dense and sparse baselines are independently measured. |
| RRF | Not implemented. | None. | Add rank-based fusion with stable chunk deduplication and per-retriever rank provenance; test ties and missing candidates. |
| Reranking | No reranker code or reranking model/dependency found. | None. | Compare viable local models and resource needs first; do not download a large model before choosing a measured candidate. |
| Context construction | `ContextAssembler` filters tenant/source/license/ACL, drops malformed hits, removes duplicate chunk/content/text, escapes delimiters, creates S# citations, strips query/fragment from public source URLs and omits chunks that exceed budget. | Unit tests cover authorization, delimiters, duplicate text, private paths/URLs and overflow. | Its default measure is Python character count, not model tokens; API constructs it with a 2,500-character budget. Use a validated generation-token budget, and expose omitted-count / selected-chunk telemetry. Current content dedupe may collapse separate provenance for identical content; preserve alternate source provenance when useful. |
| Generation | `OllamaGenerator` pins `qwen3.5:4b` and digest, uses local chat API, bounded timeout/retry/output, temperature 0, disables thinking and rejects missing/unknown S# markers. | MockTransport tests and prior local synthetic smoke. | Validate citation coverage/faithfulness beyond marker existence; add abstention and adversarial corpus tests. Streaming and structured output are absent. Keep retrieved content untrusted. |
| Citations | Context maps S# to source/document/title/pages/section/public reference; generator returns citation markers which service maps back to the context. Local filesystem paths are intentionally excluded from Qdrant payloads and citations. | Context and generator unit tests cover citation IDs, metadata, and URL sanitization. | Add citation correctness evaluation against manually reviewed questions; the current marker check cannot prove a claim is supported by its cited passage. |
| API | Loopback FastAPI, bearer token, generic errors, request size/query bounds, server-side tenant/principal, live source registry reload, rate limiter, `/health`, authenticated `/ready`, and `POST /v1/query`. | ASGI tests use stubs; not a live HTTP API integration. | `top_k` is accepted (1–20) but not passed to `LocalRAGService`; service uses fixed retrieval limit 8. No retrieval-mode/score/filter controls or performance fields in response. Add a diagnostic route/CLI before expanding public response shape. |
| Security | Qdrant filters tenant, authorized source IDs, `license_review_status=approved`, and principal ACL before returning points; context repeats these checks. API source IDs come only from validated approved source decisions. Loopback and token controls are enforced. | Authorization, API boundary, context filtering, and prompt-delimiter tests. | API readiness does not explicitly reject an index whose manifest says `operator_authorized_unreviewed`. Current pending approvals and approved-only point filters prevent corpus content from reaching the API now, but production mode must explicitly reject this development mode. Add adversarial retrieval/generation tests; prompt instructions and escaping do not fully prevent poisoning. |
| Evaluation | Chunk benchmark helpers exist, but no `evaluation/` dataset, relevance labels, expected answers, or corpus retrieval metrics exist. | Chunking implementation tests only; no Recall/Precision/MRR/nDCG or answer-faithfulness results. | Build a human-reviewed, reproducible corpus set with verified chunk IDs before claiming retrieval quality. |

## Findings and risks

1. **No real corpus retrieval baseline exists.** The existing smoke uses synthetic points in memory. Scores from the existing index have not been manually inspected, and the system has no corpus quality measurements.
2. **The development index is not approved content.** Its manifest says `operator_authorized_unreviewed`; all 14 source decisions are pending. Qdrant search and context construction require `license_review_status=approved`, so this corpus intentionally does not flow through the production API. Do not relax either filter to make the diagnostic work. Phase 1 needs a separately explicit development-only access mode with unmistakable labeling and no production route to it, or must wait for a reviewed index.
3. **API `top_k` is ineffective.** The request model accepts it, but the handler calls `service.answer(body.query, scope)` and the service uses its fixed limit. This is a correctness defect for the API contract.
4. **Retrieval outputs are not yet a stable public schema.** Qdrant `SearchHit` contains point UUID, score and payload; payload includes chunk/document/source IDs, title, text, headings/pages and source URL, but no file path by design. List position implicitly conveys rank; no rank field, score threshold, or caller-safe metadata filter is exposed.
5. **Context budget is not a token budget.** The production API currently uses character length. It may not represent Qwen prompt tokens and does not account for full serialized generation overhead.
6. **Authorization mode should be checked at the production boundary.** `validate_index_manifest` checks ready status, model, collection health, point count and optional tokenizer/inventory checks but does not require an approved authorization mode. The API must explicitly refuse an unreviewed manifest in production mode before approvals or collections change.
7. **Generation citation validation is syntactic.** It checks that citations exist in the selected context; it does not verify each claim against cited evidence or measure abstention/factuality.
8. **No sparse index lifecycle is defined.** BM25 should be synchronized to the same point/chunk set and index identity, with clear rebuild/update behavior and authorization applied before context assembly.
9. **Logging is minimal.** No application logging framework/configuration was found in the pipeline. This avoids current prompt logging, but stage timing, request correlation and operational failures need structured, redacted telemetry before a full service rollout.
10. **Source and path visibility is constrained intentionally.** Local paths are forbidden in Qdrant payloads. Retrieval diagnostics should report available source URL/title/IDs, and must not fabricate paths. If a local corpus path is needed for operator diagnostics, resolve it through a separately protected inventory mapping.

## Recommended implementation sequence

1. **Phase 1, dense baseline:** add a typed result, ensure `top_k` works end-to-end, add a JSON/text diagnostic CLI with stage timings and an explicit score threshold. First settle a development-only access design that cannot be selected by the API or production configuration. Do not change approvals or the index. If using corpus results, label them unreviewed and keep them local to an operator diagnostic.
2. **Inspect 20+ questions manually:** prepare questions by source/domain, capture the real top results and metadata, and have a reviewer label relevance. Include irrelevant/ambiguous results rather than assuming similarity means relevance. Keep a reproducible JSONL transcript without secrets.
3. **Phase 2, sparse baseline:** produce a versioned local BM25 artifact whose manifest is tied to the collection/index ID and chunk IDs. Verify synchronization and source/tenant/principal filtering. Do not modify Qdrant vectors.
4. **Phase 3, hybrid/RRF:** fuse independent dense and sparse ranks, preserve rank provenance, deduplicate by stable chunk ID and evaluate against labels.
5. **Phase 4, local reranking:** compare a small local candidate only after RAM/VRAM/latency requirements and a quality baseline are known. Measure improvement, not merely score changes.
6. **Phase 5, context/generation:** use a measured token budget, retain passage provenance, add citation coverage and abstention evaluation, then adversarially test prompt injection and poisoning.
7. **Phase 6, security boundaries:** explicitly distinguish production-approved from development-unreviewed indexes, reject unreviewed manifests in production mode, and test authorization before content enters context.
8. **Phase 7, evaluation/optimization:** collect real human relevance labels and answer/citation judgments, then report retrieval/generation metrics and warm/cold stage latency.
9. **Phase 8, API integration:** thread mode/top-k and actual stage telemetry into the existing API, retain server-derived identities and approved-only filters, and run a live loopback integration only against an approved index or a clearly isolated development test fixture.

## Dependencies and compatibility

- Python 3.13.17 and Windows PowerShell 5.1 are the configured environment.
- Pinned runtime packages include FastAPI, HTTPX, `qdrant-client`, `tokenizers`, NumPy, Pydantic, and the existing parser/Office libraries. `pip check` passed in the preceding pre-retrieval verification.
- No BM25, reranker, sparse-vector, or evaluation dependency is present. Avoid adding one until its role and resource cost are clear; BM25 can be implemented or selected as a small local CPU component.
- Ollama is constrained to loopback and configured with `nomic-embed-text:v1.5` (768 dimensions) and `qwen3.5:4b`; both models and digests are pinned in project config.
- Qdrant is constrained to loopback. The current collection uses cosine distance and named vector `dense`.
- No retrieval config exists. Add one only when it owns actual retrieval settings rather than duplicating indexing/model configuration.

## Verification status and exact commands

The existing verification from the pre-retrieval work is 139 passing unit tests, successful `compileall`, clean `pip check`, passing `ragctl validate-index`, and a passing synthetic smoke test. These do not constitute corpus retrieval evaluation or a live HTTP API integration.

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall src scripts
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\ragctl.py validate-index
.\.venv\Scripts\python.exe scripts\run_synthetic_rag_smoke.py
```

When the dense diagnostic is implemented and an approved or explicitly isolated development dataset is available:

```powershell
.\.venv\Scripts\python.exe scripts\test_dense_retrieval.py --question "How does FastAPI dependency injection work?"
.\.venv\Scripts\python.exe scripts\test_dense_retrieval.py --question "How does FastAPI dependency injection work?" --json
```

## Phase 0 disposition

Phase 0 audit is complete. No application code, approval registry, raw corpus, Qdrant collection, or persistent volume was changed for this audit. The next safe step is Phase 1 only after the operator chooses how to permit local diagnostic access to the unreviewed development index without making that access available to production/API callers.
