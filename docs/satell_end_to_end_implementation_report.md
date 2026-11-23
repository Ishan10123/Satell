# satell End-to-End RAG Implementation Report

**Date:** 2026-11-18  
**Readiness:** `NOT_READY`

## Summary

Synthetic-only local RAG execution succeeds. Django/PostgreSQL is healthy, but Django still selects the synthetic `mock` adapter. FastAPI is not running or reachable from Django. The production API rejects the current index because it is `operator_authorized_unreviewed`; all 14 sources remain `pending_review`. No source/document was approved, and no authorization registry or manifest was changed.

This implementation configures 8,192 context / 1,024 output / 512 safety-reserve tokens, changes evidence assembly to use complete passages only, and returns a safe user-visible error when the configured model budget cannot fit the request. It does not switch to HTTP mode or claim production readiness.

## Observed system state

| Component | Current evidence |
|---|---|
| Django | `django_app-django-1` healthy at loopback `127.0.0.1:8001`; `RAG_ADAPTER=mock`. |
| PostgreSQL | `rag-postgres` healthy; existing application DB/volume preserved. |
| FastAPI | No running FastAPI process/container; no API service on the app Docker network. |
| Docker network | `rag-app-network` includes Django and PostgreSQL. Qdrant is attached to a separate bridge. |
| Ollama | Reachable on host loopback `127.0.0.1:11434`; embedding `nomic-embed-text:v1.5` and generation `qwen3.5:4b` are installed. |
| Generation model | Qwen3.5 4B is 4.2B Q4_K_M; pinned digest matches config; model metadata advertises 262,144 native context. App sends configured `num_ctx`. |
| Reranker | Artifact/config exists but `configs/retrieval.json` sets `reranker.enabled=false`. |
| Retrieval mode | `dense`; BM25/RRF are not selected, and reranking is disabled. |
| Index | Qdrant `rag_docs_v2` green, 58,856 points; manifest validates at 6,565 documents / 58,856 chunks / 768 dimensions. |
| Authorization | Manifest mode `operator_authorized_unreviewed`; source decisions 14 pending; configured document registry `knowledge_base/metadata/document_approvals.json` is absent. |

Manifest `ready` means structurally ready; it does not mean production-authorized.

### Indexed corpus counts

Read-only Qdrant scroll counts: “docs” are distinct document IDs, “chunks” are points.

| Source | Origin | Docs | Chunks |
|---|---|---:|---:|
| `arxiv_ai_systems` | arXiv papers | 15 | 701 |
| `arxiv_artificial_intelligence` | arXiv papers | 13 | 660 |
| `arxiv_database_vector_search` | arXiv papers | 15 | 763 |
| `arxiv_information_retrieval` | arXiv papers | 15 | 769 |
| `arxiv_llm_rag` | arXiv papers | 16 | 610 |
| `arxiv_llm_transformers` | arXiv papers | 15 | 724 |
| `arxiv_machine_learning` | arXiv papers | 18 | 1,209 |
| `docker` | Docker docs repository | 1,113 | 12,521 |
| `fastapi` | FastAPI docs repository | 158 | 2,398 |
| `huggingface_transformers` | Transformers repository | 787 | 8,948 |
| `postgresql_18` | PostgreSQL 18 docs | 1 | 5,541 |
| `python_3_13` | Python 3.13 docs | 553 | 13,817 |
| `pytorch` | PyTorch docs/repository | 263 | 2,594 |
| `qdrant` | Qdrant docs repository | 3,583 | 7,601 |
| **Total** |  | **6,565** | **58,856** |

Supported candidate inventory is 6,596: 31 more than indexed. Current per-source delta is Docker 1 and Qdrant 30, matching the previously recorded duplicate-path deduplication total. Those records were not re-audited in this milestone; retain as an inventory reconciliation item. No reindex was performed.

## Evidence-backed license review

`ragctl license-report` reports all 14 source decisions pending. Its verified candidate evidence is not review-bound before a human decision; artifact presence is not a legal determination or blanket permission. Seven arXiv collections contain 107 indexed paper records total; each paper requires its own evidence and decision. Source approval does not approve papers. Third-party assets/content remain excluded unless separately reviewed.

| Source | Candidate evidence rows | Existing evidence and remaining review |
|---|---:|---|
| `arxiv_ai_systems` | 0 | No source-level evidence located; review 15 papers individually. |
| `arxiv_artificial_intelligence` | 0 | No source-level evidence located; review 13 papers individually. |
| `arxiv_database_vector_search` | 0 | No source-level evidence located; review 15 papers individually. |
| `arxiv_information_retrieval` | 0 | No source-level evidence located; review 15 papers individually. |
| `arxiv_llm_rag` | 0 | No source-level evidence located; review 16 papers individually. |
| `arxiv_llm_transformers` | 0 | No source-level evidence located; review 15 papers individually. |
| `arxiv_machine_learning` | 0 | No source-level evidence located; review 18 papers individually. |
| `docker` | 2 verified candidates | Apache-2.0 docs artifact at pinned revision; scope incomplete; review examples, diagrams, media, and third-party assets. |
| `fastapi` | 1 verified candidate | MIT repository license artifact; docs/examples/assets coverage not established. |
| `huggingface_transformers` | 1 verified candidate | Apache-2.0 repo artifact; review docs, model examples, datasets, media, and third-party materials. |
| `postgresql_18` | 0 | Official PostgreSQL page says license covers docs; inspect edition, attributed extracts, figures, and intended use. |
| `python_3_13` | 0 | Official Python page distinguishes PSF license and Zero-Clause BSD examples; review examples and third-party content. |
| `pytorch` | 2 verified candidates | Separate docs repo states BSD; broader PyTorch license/NOTICE is not blanket coverage. Review examples/media/third parties. |
| `qdrant` | 0 | Pinned license URL returned 404; obtain authoritative docs license or written permission. |

The human review guide is `docs/license_human_review_guide.md`; its packet is `knowledge_base/metadata/license_human_review_packet_20261116.json`. No approval command was run.

## Request flow and integration blockers

The current user-facing path is `django_app/chat/views.py:message_create` → `django_app/rag_client/client.py:get_rag_client` → `MockRAGClient` (explicitly selected in `django_app/compose.yaml`) → PostgreSQL message/citation persistence. This is the exact reason the UI returns synthetic answers.

`FastAPIRAGClient` is implemented and its contract matches `src/rag_pipeline/api/app.py` (`POST /v1/query`, `query/top_k`, bearer auth, structured answer/citations/request ID/retrieval mode/timings). The client validates and sanitizes response metadata. It is not selected in the running app.

Real integration blockers:

- Django defaults to `http://127.0.0.1:8000`, which from inside its container is Django itself; probing `/health` returned 404. No RAG token is configured, so the HTTP adapter fails closed.
- No FastAPI service is running. `scripts/run_api.py` binds to host loopback; that is not a Docker service DNS address.
- Qdrant is on a different Docker bridge; Ollama listens only on host loopback. No network/listener exposure was changed.
- `src/rag_pipeline/api/app.py:check_index` requires `reviewed_source_and_document_approval`. `/ready` and `/v1/query` reject the current `operator_authorized_unreviewed` manifest before retrieval. All 14 sources are pending and the configured document registry is missing.
- Django HTTP timeout defaults to 15 seconds, while Ollama generation timeout is 120 seconds per model call and verification also calls the model. Align before enabling HTTP.

If directly invoked with an authorized scope, `LocalRAGService.answer` runs dense retrieval → source/document filters → `ContextAssembler` authorization recheck/untrusted evidence framing → Ollama generation → claim/citation verification. Django stores citation snapshots, not raw evidence or internal prompts. However, the actual browser → Django → FastAPI → production Qdrant path is not connected. The synthetic end-to-end test invokes the RAG service in process with an in-memory Qdrant collection; it is not production API integration.

## Changes implemented

- `configs/generation.json`: configured 8,192 context, 1,024 output tokens, 512 safety reserve. `load_generator` supplies these to both generator and claim verifier; Ollama request options carry `num_ctx` and `num_predict`.
- `configs/retrieval.json` and `scripts/run_api.py`: moved the 2,500-byte evidence context cap into config instead of keeping it hardcoded at composition time.
- `src/rag_pipeline/retrieval/context.py`: removed partial-passage excerpting. A chunk now enters context in full or is omitted; dynamic budget cannot exceed the configured cap.
- `src/rag_pipeline/api/app.py`: context-budget failures return safe HTTP 413.
- `django_app/rag_client/client.py`, `django_app/rag_client/__init__.py`, `django_app/chat/views.py`: 413 maps to a typed client error and user-visible “shorten it” guidance, without exposing upstream details.
- Added regression coverage in `tests/test_configuration.py`, `tests/test_retrieval_context.py`, `tests/test_api.py`, `django_app/rag_client/tests.py`, and `django_app/conversations/tests.py`.

The generation budget uses conservative UTF-8 byte length because no exact compatible Qwen tokenizer is installed. It is not an exact token count and must not be confused with the Nomic embedding tokenizer. No query is truncated; an over-budget request fails visibly. A 5,000-character maximum does not guarantee enough context remains for evidence.

## Model and hardware benchmark

Observed hardware: RTX 5050 Laptop GPU, 8,151 MiB VRAM; host RAM 15.7 GiB total, about 2.9 GiB free at inspection.

| Synthetic request | Context loaded by Ollama | Prompt tokens reported | Output tokens | Total call time | GPU VRAM after load |
|---|---:|---:|---:|---:|---:|
| 4K | 4,096 | 743 | 32 | 20.65 s | ~3,742 MiB |
| 8K | 8,192 | 743 | 32 | 9.40 s | ~3,958 MiB |

Both used a synthetic 5,000-character prompt. The 8K request followed the 4K request, so its warm/reload latency is not a fair cold-start comparison. This verifies Ollama accepted each configured context and fit in VRAM during short samples. Full 1,024-token generation, sustained concurrency, and production latency remain unbenchmarked. The synthetic RAG smoke test reported 6.879 seconds generation/verification elapsed.

## Validation

- `python -m unittest discover -s tests -q`: **223 passed, 1 skipped**.
- Focused API suite: **20 passed**.
- Django/SQLite: **28 passed** (`DJANGO_DB_ENGINE=sqlite`, `DJANGO_SQLITE_PATH=:memory:`).
- Django/PostgreSQL in Docker: **28 passed**; Django created and removed its temporary `rag_django_test_20261118` database. Existing `rag_application` data was preserved.
- Django system check and migration check: passed; no unapplied migrations.
- `python -m compileall -q src scripts tests`: passed.
- `python -m pip check`: no broken requirements.
- `scripts/run_synthetic_rag_smoke.py`: passed with installed local embedding/generation models, synthetic approved passages, in-memory Qdrant, citation validation, and tenant/ACL/source isolation. No corpus data was read.
- `scripts/ragctl.py validate-index`: passed; collection remained green at 58,856 points.
- Django image built and only Django was recreated. PostgreSQL/Qdrant containers and persistent volumes were not restarted or modified.

These results do not establish production-corpus quality, production API readiness, or browser-to-FastAPI integration.

## Remaining actions

1. Human-review a narrow source scope and its evidence; exclude third-party/unsupported content. Review each of the 107 arXiv papers separately. Create document approvals through the existing workflow. Do not edit the manifest directly.
2. The existing FastAPI source approval example is only procedural. After a reviewer actually checks rights and scope, a command may look like:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-source fastapi `
  --decision approved --reviewer "<reviewer name>" --license-name "MIT" `
  --scope documentation_candidates `
  --evidence knowledge_base\metadata\license_evidence.jsonl `
  --notes "<reviewed documentation scope; third-party assets excluded>"
```

Do not use placeholders or execute this until the human review is complete. This implementation did not run it.

3. After a reviewed index exists, implement a private Docker-only FastAPI path, service-name URL, server-side token, aligned request deadline, and health/readiness checks. Keep Qdrant and Ollama unpublished and private. Do not switch `RAG_ADAPTER` until authenticated `/ready` passes on the reviewed index.
4. Establish bounded inference concurrency and verify server-side user-to-scope mapping before multi-user real queries.
5. Build a human-reviewed quality set; evaluate Recall@K, MRR/nDCG, citation precision, claim support, abstention, and latency. Benchmark full 4K/8K workloads including long prompts and verification.
6. Consider BM25/RRF/reranking only after controlled retrieval evaluation; dense remains current default.

## Changed files

- `configs/generation.json`
- `configs/retrieval.json`
- `scripts/run_api.py`
- `src/rag_pipeline/retrieval/context.py`
- `src/rag_pipeline/api/app.py`
- `tests/test_configuration.py`
- `tests/test_retrieval_context.py`
- `tests/test_api.py`
- `django_app/rag_client/client.py`
- `django_app/rag_client/__init__.py`
- `django_app/rag_client/tests.py`
- `django_app/chat/views.py`
- `django_app/conversations/tests.py`
- `docs/satell_end_to_end_implementation_report.md`

## Repeatable commands

```powershell
Set-Location E:\RAG_Project
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/ragctl.py validate-index
```

```powershell
Set-Location E:\RAG_Project\django_app
$env:DJANGO_DB_ENGINE = 'sqlite'
$env:DJANGO_SQLITE_PATH = ':memory:'
..\.venv\Scripts\python.exe manage.py test -v 1
docker compose exec django python manage.py test -v 1
```

Do not enable HTTP mode or issue production corpus queries while authorization remains blocked. The safe next step is the required human source/document rights review, then a separately scoped private-network integration.
