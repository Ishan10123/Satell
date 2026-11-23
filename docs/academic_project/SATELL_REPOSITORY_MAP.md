# Satell repository map and implementation status

**Assessment date:** 2026-11-19. This map describes the checked-out workspace and local deployment observed on this date. It does not imply that every script is part of the serving path.

## Top-level layout

| Path | Purpose and status |
|---|---|
| `src/rag_pipeline/` | Active Python RAG, authorization, parsing, retrieval, generation, verification, API and storage package. |
| `django_app/` | Active Django application split into `accounts`, `chat`, `conversations`, `rag_client`, and `config`. Owns browser sessions and user conversation data. |
| `tests/` | Standard-library `unittest` suite for RAG, API, ingestion, authorization, retrieval, generation, citations and verification. Django tests are beside their apps. |
| `configs/` | Parser, ingestion, chunking, embedding, indexing, retrieval, authorization and local-demo policy configuration. |
| `scripts/` | Operator and validation entry points plus historical/specialized evaluation and ingestion scripts. `run_api.py` starts FastAPI; `ragctl.py` runs checks and operator workflows. Not every script belongs to runtime serving. |
| `knowledge_base/metadata/` | Inventory, manifests, evidence and signed authorization registries. Dated registry versions remain as historical evidence; active paths are selected by code/configuration. |
| `knowledge_base/raw/` | Preserved documentation, research papers and supporting source material. |
| `knowledge_base/processed/` | Parse/normalize runs and optional sparse-index artifacts. |
| `assets/` | Pinned tokenizer and optional local reranker assets. The reranker is not loaded by the current dense configuration. |
| `evaluation/` | Query sets and machine-readable results. Heuristic expectations are not human relevance labels. |
| `docs/` | Phase-specific evidence reports, workflows and operator instructions. Historical reports keep their run dates. |
| `docs/academic_project/` | Consolidated academic handbook, readiness assessment, diagrams and execution evidence. |
| `infrastructure/` | PostgreSQL Compose and persistence/backup support. It does not create all host infrastructure from scratch. |
| `logs/` | Historical operator ingestion logs; protect and review before sharing. |
| `.venv/`, `.vscode/` | Local Python environment and editor configuration; neither is a deployment lock/provisioning source. |

Root-level operational files include `requirements*.txt`, `Dockerfile.rag-api`, `Dockerfile.synthetic-rag-test`, `.dockerignore`, and audit/download utilities. Django configuration lives in `django_app/Dockerfile`, `django_app/compose.yaml`, and `django_app/compose.rag.yaml`. No root `package.json`, `pyproject.toml`, or `Pipfile` was found; the UI uses templates, CSS and vanilla JavaScript. No root `.git` directory was found, so Git status/history and a source-control diff are unavailable.

## Active application packages

### `src/rag_pipeline/`

- `api/`: FastAPI routes, request/response models, authentication, readiness, rate limiting and error boundary.
- `authorization/`: source/document approvals and the separate signed local-academic-demo policy/registries.
- `configuration.py`: settings and model/provider construction.
- `chunking/`, `parsing/`, `normalization/`, `ingestion/`: corpus processing and index workflow; not invoked for ordinary chat requests.
- `embeddings/`: local query embedding provider and model descriptor checks.
- `retrieval/`: active dense path, optional sparse/BM25, hybrid RRF, optional reranker and bounded context assembly.
- `generation/`: Ollama generation, citation validation, claim verification, consistency/freshness checks and restricted evaluation artifacts.
- `security/`: service-token checks and request limiting.
- `storage/`: Qdrant access filters and index manifest validation.
- `service.py`: query orchestration through retrieval/context/generation/verification.

### `django_app/`

- `accounts/`: session login, logout and password recovery.
- `conversations/`: owner-scoped history, titles, export, sharing, lock/delete behavior, models and migrations.
- `chat/`: message submission, server-side RAG invocation, templates and static assets.
- `rag_client/`: HTTP and explicitly synthetic adapters, schema validation, timeouts and typed errors.
- `config/`: Django settings, URL routing, WSGI and startup configuration.

## Tests and evidence

- RAG/API regression tests: 26 modules under `tests/`.
- Django tests: app-local `tests.py` plus focused integration tests.
- Browser automation: `scripts/chat_experience_browser_e2e.py`, `scripts/phase5_browser_e2e.py`, and evaluation scripts.
- Synthetic HTTP API: `scripts/synthetic_rag_test_api.py`, test-only.
- Current browser and evaluation artifacts: `docs/academic_project/evidence/chat_experience_browser_results.json`, `evaluation/results/satell_chat_quality_live_20261119.json`, and `evaluation/results/satell_chat_quality_failure_diagnostics_20261119.json`.
- Current test record: `docs/academic_project/evidence/test_run_summary_20261119.md`.

## Active request path versus optional components

The active chat path is Django → authenticated FastAPI → server-derived authorization scope → dense Qdrant retrieval → context authorization/budget checks → Ollama generation → citation and claim checks → Django persistence. The live retrieval configuration is `strategy=dense`, `default_top_k=8`, and `reranker.enabled=false`. BM25, RRF and ONNX reranking are implemented/benchmark-only, not active in the configured request path. Ingestion/operator tools are separate from query serving.

Use imports, Compose configuration, image contents and current configuration to establish what is active. Do not remove a file based only on this map. Raw corpus and processed artifacts were not recursively inspected or modified in this assessment.
