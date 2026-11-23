# Satell technology stack and dependency inventory

**Version basis:** repository pins and current runtime inspected 2026-11-20. Running services remain on their existing image digests; Phase 6 candidate images use separate updated package pins. Rationale below is marked as engineering rationale where no original decision record was found. A package appearing in a requirements file does not by itself prove it is active in every request.

## Languages and user interface

| Technology | Version/status | Use and layer | Current engineering rationale, alternative and trade-off |
|---|---|---|---|
| Python | 3.13.17 on host/container | Django, FastAPI, RAG, ingestion, tests | One language across service and pipeline lowers integration friction. Alternatives include Java/Kotlin/Go or Node; Python has the local AI ecosystem. Python packaging/runtime reproducibility still needs locks and security scanning. |
| HTML/Django templates | Running image 5.2.13; candidate 5.2.17 | Server-rendered login, dashboard and chat | Avoids a separate SPA/API auth stack and keeps sessions/CSRF on the server. Candidate update is not deployed. |
| CSS | App-local `django_app/chat/static/chat/app.css`; Django admin CSS | Layout/responsive visual system | Small local app needs no CSS framework build chain. Styling is custom and requires ongoing browser checks. |
| JavaScript | Vanilla ES modules/script in `app.js` | Markdown DOM creation, form feedback, clipboard controls | No frontend package manager or browser-held API credential. A framework is not needed for current interaction scope; larger interactive state could change that trade-off. |
| SQL/SQLite FTS5 | Python `sqlite3` stdlib; FTS5 | Optional local sparse snapshot | Small, local BM25 corpus snapshot without another server. Not the Django DB and not active for current dense request path. |

## Backend and protocol dependencies

| Direct package | Pinned source | Actual role/status | Alternative/trade-off |
|---|---|---|---|
| Django | Running image 5.2.13; requirements/candidate 5.2.17 | Active application, auth, ORM, templates, admin, migrations | Candidate-only update is not deployed. FastAPI-only would require rebuilding sessions/ORM/admin/presentation. Django is appropriate for the user-facing app; synchronous view blocks through RAG. |
| FastAPI 0.163.1 | `requirements.txt`, `requirements-api.txt` | Active typed `/v1/query`, `/ready`, `/health` service | Could use Django REST Framework or a single Django service. Separate service isolates engine API and uses Pydantic; adds network/service operations. |
| Pydantic 2.14.3 | API requirements; synthetic API | `QueryRequest`/`QueryResponse` validation and FastAPI schema | Dataclasses/manual validation are alternatives; Pydantic integrates well, though response citations are dictionaries rather than a dedicated nested model. |
| Uvicorn 0.54.0 | API requirements | ASGI server started by `scripts/run_api.py` | Hypercorn/Granian alternatives. Current endpoint logic is synchronous, so async concurrency is not fully exploited. |
| Gunicorn 27.0.1 | Django Docker-only requirements | Active WSGI server, 1 sync worker, bounded timeout | Django dev server is not appropriate for deployment. More workers/threads may improve throughput but must be profiled against the single GPU. |
| WhiteNoise 6.12.0 | Django Docker-only requirements | Active production static serving from build-collected files | Separate Nginx/CDN alternatives add infrastructure. WhiteNoise is sufficient for current local app, not a complete edge/TLS layer. |
| HTTPX 0.28.1 | root, API, Django requirements | Synchronous Ollama calls, Django→FastAPI client, readiness checks, tests | `requests`/aiohttp alternatives. HTTPX has typed timeouts/transports; current user path remains blocking. |
| Psycopg 3.3.9 + binary wheel | root/Django Docker requirements | PostgreSQL driver | psycopg2 alternative. v3 is current async-capable but app uses Django's synchronous ORM. Binary wheel simplifies local container; pin/scan is still required. |

## Data, parsing and model/runtime packages

| Direct package | Pinned version | Actual role/status | Alternatives and trade-off |
|---|---:|---|---|
| `qdrant-client` | 1.20.0 | Active Qdrant access, payload filters, point/search/health operations | pgvector/Milvus/Weaviate alternatives. Qdrant has dedicated vector search; creates a second datastore and requires snapshot/ACL operations. Server currently reports Qdrant 1.20.1. |
| `numpy` | 2.5.4 | Imported by local reranker scoring code; deployed even though reranking is disabled | Pure Python/torch alternatives. NumPy is suitable for ONNX tensors, but increases image footprint. |
| `onnxruntime` | 1.32.0 | Optional cross-encoder ONNX runtime; not loaded in current dense mode | PyTorch runtime or remote reranker. ONNX CPU is bounded/private; no current request uses it. |
| `tokenizers` | 0.22.1 | Active pinned local Nomic tokenizer for chunk/index validation; optional reranker tokenizer | Transformers tokenizer alternatives; this library avoids loading full Transformers/PyTorch at query time. |
| `lxml` | 6.1.3 | XML/HTML parser support | stdlib XML is smaller; lxml offers robust extraction but native dependency surface needs patching/scanning. |
| `PyYAML` | 6.0.3 | YAML structured ingestion parser | JSON-only or ruamel.yaml alternatives; supports corpus configuration files with safe loader in parser code. |
| `pypdf` | 7.1.0 | PDF extraction in ingestion/audit utilities | Poppler/Tika alternatives add native services; text layout/table reconstruction remains limited. |
| `python-docx` | 1.2.0 | DOCX extraction | LibreOffice/Tika alternatives heavier; keeps extraction Python-local. |
| `openpyxl` | 3.1.5 | XLSX extraction | pandas/LibreOffice alternatives; avoids pandas but spreadsheets can have complex semantics. |
| `python-pptx` | 1.0.2 | PPTX extraction | LibreOffice/Tika alternatives; current parser extracts text/metadata, not complete visual meaning. |

## AI models and retrieval components

| Technology | Version/config | Status and purpose | Why appropriate / trade-off |
|---|---|---|---|
| Ollama | Host 0.40.16 | Active local model runtime; FastAPI reaches it through `host.docker.internal:11434` | Keeps prompts/reference text local and avoids a hosted API. Host process is an external runtime dependency; no HA or managed SLA. |
| Qwen 3.5 4B | `qwen3.5:4b`, Q4_K_M, pinned digest; configured ctx 8192 | Active generation and verifier model | Quantized 4B model runs on the RTX 5050 Laptop GPU (8,151 MiB observed VRAM). Smaller/cheaper than a hosted large model; less capacity, and verification may share model blind spots. Original selection rationale is not recorded; this is a current hardware-fit explanation. |
| Nomic Embed Text v1.5 | 768 dimensions, pinned digest | Active query embedding; document vectors already in Qdrant | Local and dimension-configured against corpus. Alternatives include BGE/E5/OpenAI embeddings; changing model requires reindexing a separate collection. Original benchmark rationale not documented. |
| Dense cosine retrieval | Qdrant, active default | Main retrieval path | Efficient semantic retrieval for paraphrase. Exact tokens/identifiers may benefit from lexical retrieval. |
| SQLite FTS5 BM25 | `unicode61 remove_diacritics 2`, k1 1.2, b 0.75 | Implemented and benchmarked, inactive | Local exact-term complement; doubles index lifecycle/consistency work. |
| Reciprocal Rank Fusion | RRF constant 60 | Implemented/benchmark-only | Combines ranks without normalizing different score scales; benchmark was slower with no recall improvement. |
| ONNX cross encoder | `cross-encoder/ms-marco-MiniLM-L2-v2`, local checksummed assets, CPU provider | Implemented/benchmark-only; config disabled | Can refine top candidates but costs CPU latency; the benchmark showed lower heuristic precision/MRR/nDCG and 3.4 s median retrieval. |
| Cohere | None | Not installed/imported/configured | Not an active dependency or service; no external reranker call is made. |

## Security, testing and observability

| Technology | Version/status | Use | Limit |
|---|---|---|---|
| Python `hmac`, `hashlib`, `secrets`, `uuid`, `json` | Standard library | API token compare, HMAC demo registry, content identity, request IDs and manifests | Key operations still need secret lifecycle and legal review; HMAC is not an external legal signature. |
| PyTorch | Not declared as a Satell runtime dependency; no active request-path import found | The corpus includes PyTorch documentation, but Satell inference runs through Ollama and the optional reranker through ONNX Runtime | Do not infer that the model server uses the application’s Python PyTorch package. Installing PyTorch would add substantial footprint without serving the current query path. |
| Django CSRF/session/auth | Running image 5.2.13; candidate 5.2.17 | Browser user identity, forms, session cookies | Local deployment uses HTTP/secure-cookie false; deployment behind TLS is not configured/tested. |
| Qdrant payload ACL filters | Qdrant client/API | Tenant/principal/source/status/category filtering plus context recheck | Assumes private Qdrant network and trusted payload integrity. |
| `unittest` | Standard library | Active suite, 270 RAG tests in current run (269 passed, 1 Windows platform skip) | No `pytest` package/runner is pinned or installed. |
| Django `TestCase` | Django | Active app/db tests on PostgreSQL and SQLite | Two opt-in tests require explicit flags. |
| HTTPX `MockTransport` / FastAPI TestClient | HTTPX/Starlette dependency | Boundary/error/API tests | Mocks do not prove each live dependency's outage recovery. |
| Playwright Python | 1.65.2 in `requirements-e2e.txt` | Actual Chrome browser tests and clipboard checks | Optional, not in runtime image; browser/channel availability is host-specific. |
| Docker Desktop / Compose | Server 29.9.3 observed | Local service isolation, process/runtime packaging | Compose tags and external infra are not a reproducible clean-host system. |
| `docker stats`, `nvidia-smi` | Host tools | Periodic CPU/memory/GPU sampling | Not continuous profiling or host CPU peak measurement. No Prometheus/Grafana. |

## Runtime and transitive dependency notes

Direct packages are pinned, but there is no comprehensive hash-locked transitive requirements file. Phase 6 generated digest-bound SPDX SBOMs and high/critical Docker Scout reports for separate candidate images; each reports three high OpenSSL findings with no fixed version listed. Candidate images have not replaced the running 5.2.13 Django/previous API images. See the [Phase 6 dependency report](../phase6/phase6_dependency_and_sbom_report.md) and [candidate validation evidence](../phase6/evidence/phase6_candidate_validation_20261120.md). Django's Docker requirements are a separate smaller set; API and synthetic services have their own requirement files. `requirements-e2e.txt` contains only Playwright.

The host virtual environment contains `arxiv==4.1.0`; root-level `download_arxiv.py` and `download_arxiv_backup.py` import `arxiv`, but it is not declared in the reviewed requirements files. These are operator downloader scripts, not the serving request path; they also contain machine-specific project paths and should be isolated/refactored before being used on a clean machine. This is an ingestion-utility reproducibility defect, not a runtime dependency of the current application. Other packages installed in `.venv` may be transitive; do not assume they are direct application dependencies. `pytest`, `pip-audit`, Trivy, Grype and Syft were not found; Docker Scout CLI 1.28.0 is available and produced the bounded Phase 6 candidate scans/SBOMs.

No JavaScript `package.json` for the Satell frontend exists. Raw acquired documentation may itself contain package manifests; those do not define the Satell UI build.
