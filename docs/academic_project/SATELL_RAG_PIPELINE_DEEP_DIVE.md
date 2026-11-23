# Satell RAG pipeline deep dive

Assessment snapshot: 2026-11-19. This describes the active local academic demo path, not production authorization.

## Query path

`LocalRAGService.answer` validates the request and runtime readiness, derives the signed local-demo scope, embeds the question with `nomic-embed-text:v1.5` (768 dimensions), searches `rag_docs_v2`, applies metadata/authorization checks, assembles a bounded context, calls Ollama with `qwen3.5:4b`, verifies claims against admitted evidence, validates citation syntax and mappings, and returns a structured result. FastAPI exposes this through authenticated `POST /v1/query`; Django calls it using its server-side HTTP adapter. See `src/rag_pipeline/api/app.py`, the service/retrieval/generation modules under `src/rag_pipeline/`, `configs/retrieval.json`, and `django_app/rag_client/client.py`.

## Retrieval components and status

| Stage | Current status | Notes |
|---|---|---|
| Dense embedding and Qdrant search | Active | Collection `rag_docs_v2`; 58,856 points at snapshot. Authorization metadata is applied. |
| SQLite FTS5 / BM25 | Implemented, inactive in live strategy | Sparse store exists; do not infer hybrid usage from its presence. |
| RRF | Implemented and benchmarked | Not selected for the active request path. |
| ONNX cross-encoder | Optional/benchmark-only | Not enabled for live queries; Cohere is not active. |
| Deduplication and context assembly | Active | Context assembly filters, budgets and maps evidence to citation IDs. |
| Generation | Active | Local Ollama model; context window 8,192, output reserve 1,024, safety reserve 512. |
| Claim verification | Active | Same local model family is used for verification; this is not independent ground truth. |
| Citation validation | Active | Separate deterministic validation checks citation syntax, known IDs/mappings and coverage conditions. |

## Context and grounding

The assembled prompt contains a fixed system instruction, query, admitted document excerpts and evidence/citation mappings. Admission is bounded by token estimates and authorization. Retrieved text is untrusted data; prompt-injection defenses and post-generation evidence checks reduce risk but cannot prove semantic truth. Excluded chunks and truncation can cause abstention. Token estimates are approximations, not an Ollama tokenizer guarantee.

## Evaluation evidence and limits

The 30-query retrieval benchmark used source-topic heuristics rather than human relevance judgments; reported dense Recall@8 was 0.981 and reranking Recall@8 was 1.000 in that dataset, but reranking was slower and had lower precision/MRR/nDCG than dense in some measures. A separate earlier 20-query live run produced 12 verified, 4 partially verified, 1 abstention and 3 failed/withheld responses. The latest 30-query browser evaluation produced 13 verified, 6 partial, 4 abstentions and 7 failed/rejected responses. These separate small sets are diagnostic, not production quality certification; no expert relevance or factual labels are available. See `evaluation/`, the chat experience report, and Phase 2–4 reports.

## Failure behavior

Unavailable dependencies and malformed/unsupported model outputs fail as errors or safe abstentions, not synthetic answers in the real adapter path. Citation or claim validation can reject a plausible-looking answer. The user response is intentionally less detailed than controlled evaluation diagnostics. No raw model output is promised to be preserved for every ordinary request.

## Important boundaries

- The active demo uses explicit signed local-demo registries. The production manifest remains `operator_authorized_unreviewed` and production authorization is fail-closed.
- All source legal decisions remain pending. Demo authorization is a local evaluation scope, not legal approval.
- BM25/RRF/reranker must not be described as active without a new runtime configuration check.
- No corpus rebuild or embedding regeneration is needed to explain or test the current path.

## Relevant code map

Start with `src/rag_pipeline/api/app.py` (`/health`, `/ready`, `/v1/query`), the `LocalRAGService` implementation, Qdrant vector-store adapter, context assembler, Ollama generator, claim verifier, citation validator, and `configs/retrieval.json`. Exact module names are discoverable with `rg "class LocalRAGService|def answer|class ContextAssembler|class .*Verifier|citation" src/rag_pipeline`.
