# Satell academic engineering project

This directory is the evidence-led project handbook for **Satell — Secure RAG Chat Workspace**. It describes the code and local deployment as inspected on **2026-11-19**. It does not grant legal rights, change authorization records, or certify production readiness.

## Start here

1. [Complete project report](SATELL_COMPLETE_PROJECT_REPORT.md) — 20-chapter overview and evidence links.
2. [Repository map](SATELL_REPOSITORY_MAP.md) — active code, operator tooling, data, tests and historical artifacts.
3. [Architecture](SATELL_ARCHITECTURE.md) and [request lifecycle](SATELL_DATA_FLOW_AND_REQUEST_LIFECYCLE.md) — components, networks and sequence.
4. [Technology and dependencies](SATELL_TECH_STACK_AND_DEPENDENCIES.md) and [decision records](SATELL_TECHNOLOGY_DECISION_RECORDS.md) — usage, rationale and trade-offs.
5. [RAG deep dive](SATELL_RAG_PIPELINE_DEEP_DIVE.md) and [security/authorization](SATELL_SECURITY_AND_AUTHORIZATION.md).
6. [Database/infrastructure](SATELL_DATABASE_AND_INFRASTRUCTURE.md), [deployment/operations](SATELL_DEPLOYMENT_AND_OPERATIONS.md), and [testing/evaluation](SATELL_TESTING_AND_EVALUATION.md).
7. [Known limitations](SATELL_KNOWN_LIMITATIONS.md), [production readiness](SATELL_PRODUCTION_READINESS_CHECKLIST.md), and [Phase 6 entry criteria](SATELL_PHASE6_ENTRY_CRITERIA.md).
8. [Interview preparation](SATELL_INTERVIEW_PREPARATION.md), [150+ question bank](SATELL_INTERVIEW_QUESTION_BANK.md), and [demonstration guide](SATELL_DEMONSTRATION_GUIDE.md).
9. [Glossary](SATELL_GLOSSARY.md).
10. [Chat experience, recovery and quality report](SATELL_CHAT_EXPERIENCE_RECOVERY_AND_QUALITY_REPORT.md) — account recovery, conversation controls, browser proof and live 30-question evaluation.

The six Mermaid views are in [`diagrams/`](diagrams/). Dated verification records are in [`evidence/`](evidence/), including the [assessment snapshot](evidence/assessment_snapshot_20261119.md) and [test/integrity results](evidence/test_run_summary_20261119.md). The ongoing [Phase 6 engineering package](../phase6/README.md) contains current candidate image and production-readiness evidence (production remains blocked).

## Repository map

Top-level directories are `.venv`, `.vscode`, `assets`, `configs`, `django_app`, `docs`, `evaluation`, `infrastructure`, `knowledge_base`, `logs`, `scripts`, `src`, and `tests`. The workspace has **no `.git` directory**, so Git history/status and a source-control diff cannot be used as evidence.

| Path | Contents and role |
|---|---|
| `src/rag_pipeline/` | FastAPI application, RAG service, retrieval, storage, parsing, indexing, authorization, generation and verification packages. |
| `django_app/` | Django project; `accounts`, `conversations`, `chat`, and `rag_client` apps; templates, CSS/JS, migrations and Docker configuration. |
| `configs/` | Nine JSON settings files for ingestion, parsing, chunking, embedding, generation, retrieval, indexing, approvals and local demo policy. |
| `scripts/` | 33 operator utilities for ingestion, indexing, API startup, audits, benchmarks, evaluation and browser/injection probes. |
| `tests/` | 26 RAG/API/ingestion/retrieval/generation/security regression modules. Django tests live beside their apps. |
| `knowledge_base/metadata/` | Inventory, approval/evidence registries, index/readiness manifests, demo allowlists and reports. |
| `knowledge_base/raw/` | Acquired official documentation, research papers, and supporting security/standards files. Preserve as source data. |
| `knowledge_base/processed/` | Parse runs, normalized runs and sparse-index snapshots. |
| `assets/` | Local tokenizer and optional ONNX reranker assets; no model is downloaded during a query. |
| `evaluation/` | Evaluation questions, judgments and result JSON artifacts. |
| `docs/` | Historical engineering, audit, licensing, deployment and Phase 1–5 reports. Some are dated snapshots; prefer the current-state docs linked above. |
| `infrastructure/` | PostgreSQL Compose description referencing the existing external volume/network. No complete fresh-host Qdrant/Ollama bootstrap is present. |
| `logs/` | Local operator-run logs. Diagnostic files can contain prompts/answers when explicitly enabled; protect them. |

File counts at audit time (excluding `.venv` and `.git`): `src` 44, `django_app` 50, `configs` 9, `scripts` 33, `tests` 26, `docs` 252, `evaluation` 45, `assets` 4, `infrastructure` 1, `knowledge_base` 32,472 and `logs` 3. Counts include data artifacts; they are not source-code counts. Adding the repository-map report in this consolidation increased the `docs` count by one.

## Current verified snapshot

- Local academic demo: running through Django → private FastAPI → Qdrant/Ollama; API `/health` and authenticated `/ready` passed.
- `rag_docs_v2`: green, 58,856 points; manifest: 6,565 documents / 58,856 chunks, `operator_authorized_unreviewed`.
- Demo allowlist: 14 source groups, 6,458 documentation IDs; 107 indexed research papers explicitly excluded from demo retrieval.
- Legal review: all 14 source decisions pending; inventory has 9,932 pending license statuses; production document approval registry is missing.
- The latest 30-query live browser evaluation yielded 13 verified, 6 partially verified, 4 abstentions and 7 failed/rejected responses; expectations were heuristic and not expert-reviewed.
- Application database at Phase 6 final inspection (2026-11-20): 1 user, 3 conversations, 44 messages and 39 citation snapshots. The 2026-11-19 values below are dated historical evidence.
- Local supervised demo is operational. Private, public and commercial production are not ready.

These values are snapshots, not constants. Recheck readiness before a demonstration or deployment. For the Phase 5 closure evidence, see [`docs/phase5_closure/`](../phase5_closure/).
