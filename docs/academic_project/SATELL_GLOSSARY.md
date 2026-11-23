# Satell glossary

| Term | Meaning in Satell |
|---|---|
| API | HTTP boundary between Django and FastAPI. |
| Authorization registry | Validated policy data deciding which sources/documents may be queried. |
| BM25 | Lexical ranking algorithm used by the SQLite FTS5 sparse retrieval implementation. |
| Canonical document ID | Stable identity used to deduplicate paths while preserving provenance. |
| Claim verifier | Component evaluating answer claims against retrieved evidence. |
| Citation mapping | Binding between a generated citation ID and a retrieved evidence chunk/document. |
| Context assembly | Filtering and budgeting evidence chunks to form the model context. |
| Dense retrieval | Similarity search over embedding vectors in Qdrant. |
| Embedding | Numeric representation of text for semantic search. |
| Evidence chunk | A bounded excerpt with provenance and identity used in retrieval/context. |
| Fail closed | Reject access when authorization or validation cannot be established. |
| FTS5 | SQLite full-text search extension used for sparse retrieval. |
| HMAC signature | Keyed integrity tag for a registry; it proves integrity under a secret, not license rights. |
| Index manifest | Metadata describing index build, counts, versions and authorization state. |
| Local academic demo | Explicit limited retrieval mode for supervised local evaluation; not legal approval. |
| NDCG | Ranking metric rewarding relevant results near the top, with graded relevance. |
| Ollama | Local model runtime used for embeddings and generation/verification. |
| Point | Qdrant vector plus payload and point ID. |
| RAG | Retrieval-augmented generation: retrieve evidence, then generate conditioned output. |
| Recall@k | Fraction of relevant items present in the first k retrieved results. |
| RRF | Reciprocal Rank Fusion, combining ranked lists using rank-based scores. |
| Source approval | Human-controlled source-level legal/policy decision; currently pending for all sources. |
| Document approval | Per-document decision that may reject/override source-level scope. |
| Tenant/principal | Scope metadata used in retrieval filters; not currently a full per-user document ACL. |
| Top-k | Maximum requested/retrieved candidate count. |
| Verification status | Outcome such as verified, partial, rejected or abstained; not a proof of truth. |
| WhiteNoise | Django static file serving middleware used with Gunicorn in this deployment. |
| Qdrant | Vector database holding the `rag_docs_v2` collection. |
