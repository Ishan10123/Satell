# Technology decision records

This record separates evidence of actual use from rationale. Unless a historical source explicitly says otherwise, “rationale” below is current engineering rationale, not a claim about original author intent.

| Decision | Evidence/current use | Engineering rationale | Trade-off / alternative |
|---|---|---|---|
| Django for application layer | `django_app/`, auth, ORM, sessions, CSRF, admin | Mature batteries-included web framework for identity and relational user data | More framework structure than a small FastAPI-only UI; alternative Flask/FastAPI templates. |
| FastAPI for RAG service | `src/rag_pipeline/api/app.py` | Typed HTTP boundary, Pydantic validation and independent engine deployment | Separate service/network and credential lifecycle; alternative Django in-process integration. |
| PostgreSQL for app state | Django settings/Compose and migrations | Relational integrity, transactions and durable multi-user records | Operational service required; SQLite is retained for tests/local development. |
| Qdrant for vectors | `rag_docs_v2`, vector-store adapter | Purpose-built vector search and payload filters | Separate service and backup plan; PostgreSQL pgvector could reduce service count. |
| Ollama/local models | generator/embedding clients and host runtime | Local inference and data control; no paid API dependency | Laptop GPU/latency and operational capacity limits; remote inference alternative has privacy/cost trade-offs. |
| qwen3.5:4b generation/verification | Runtime config; live tests | Fits observed local hardware and enables local evaluation | Smaller model may reduce reasoning quality; larger model requires capacity evidence. |
| nomic-embed-text:v1.5 | embedding config, 768 dimensions | Local embedding service compatible with existing index | Changing model/dimensions requires new index; embeddings are not interchangeable. |
| Dense search active | retrieval config and live trace | Semantic matching is the validated active baseline | Lexical exact matches can be missed; BM25/RRF evaluated but slower/quality trade-offs. |
| BM25 + RRF implemented | FTS5 and fusion modules; benchmark | Complement semantic and lexical rankings without score calibration | Added latency/complexity; inactive in current request path. |
| ONNX reranker optional | local assets and benchmark code | Cross-encoder can improve ordering of a small candidate set | High added latency; inactive in live path. No active Cohere usage. |
| Separate claim verification | generation/verification modules | Check answer claims against available evidence after generation | Verifier shares model family and can err; deterministic ground truth remains absent. |
| Separate citation validator | citation validation module/tests | Enforce known IDs, syntax and mappings independently from model text | Correct citation mapping does not guarantee semantic support. |
| Signed local demo registries | authorization code/config | Detect tampering and bind a limited local-demo scope | Key custody/signing process is operationally sensitive; signatures do not grant legal rights. |
| Docker Compose | compose files | Repeatable local service wiring while preserving separate services | Mutable tags and existing external state weaken clean-machine reproducibility. |
| Gunicorn + WhiteNoise | Django Dockerfile/Compose | Production-style WSGI process and static serving in local container | One sync worker limits concurrency; external static server appropriate at scale. |
| Playwright | browser E2E script | Exercises real UI and browser security behavior | Browser setup is heavier than unit tests and does not replace manual accessibility review. |
| unittest/Django TestCase | tests and app suites | Standard library and Django-integrated regression tests | No pytest runner/fixture ecosystem; consistency requires explicit conventions. |

## Dependency caveats

The checked-in requirements pin direct dependencies, but no complete transitive lock/SBOM was found. `arxiv==4.1.0` exists in the inspected host environment and is imported by the root-level downloader scripts, but is not declared in the root requirements. Those scripts are not part of serving; their dependency and machine-specific path limit clean-machine use. `pytest`, `pip-audit`, `trivy` and `grype` were not installed in the inspected environment. Do not infer a dependency is active merely because it is installed or listed; inspect runtime imports and actual call graph. Detailed inventory: `SATELL_TECH_STACK_AND_DEPENDENCIES.md`.
