# Phase 1 Test and Runtime Report

## Automated verification

| Check | Result |
|---|---|
| Full RAG unittest suite | **239 tests; 238 passed, 1 skipped** |
| Python `compileall` | passed |
| `pip check` | no broken requirements |
| Django system check | no issues |
| Django migration check | no changes detected |
| Full Django suite against PostgreSQL | **32 tests; 30 passed, 2 skipped** |
| Live Django → real RAG E2E test | **1 passed**; real HTTP adapter, Qdrant, Ollama, verifier and PostgreSQL test database |
| Registry integrity validation | 14 source records, 6,458 authorized documentation IDs, 107 explicitly excluded research-paper IDs, 58,856 mapped point IDs |

The regular RAG suite includes tests for demo-default-disabled behavior, source and document signature/tamper checks, missing registries, unknown IDs, category exclusions, hash/inventory mismatch, context document allowlisting, and production-mode rejection. The E2E test is opt-in via `SATELL_LIVE_RAG_E2E=1`; it uses Django’s isolated PostgreSQL test database, persists the real answer and citations there, and deletes that test database after the run.

## Live service checks

- Django container: healthy; `RAG_ADAPTER=http` and server-side bearer credential configured.
- FastAPI `http://rag-api:8000/health`: **200**; authenticated `/ready`: **200**; invalid bearer: **401**.
- Django container resolved and reached the `rag-api` service name on the private `satell-chat-rag` network.
- Qdrant health/status: **green**; collection `rag_docs_v2` remained at **58,856 points**.
- FastAPI-to-host Ollama `/api/version`: **200** using `host.docker.internal`; Ollama remains host-local.
- FastAPI has no published host port. No Qdrant/PostgreSQL container was recreated.

## Actual retrieval and citation evidence

A real authenticated dense query through the API returned HTTP 200 and one verifier-accepted citation. The citation was `S1`, source `docker`, document ID `7ebe38988e9b807dc9a200eb5d73d609960217cf0f6ec4b7d8303f4fbc788d02`; it matched the signed documentation registry. The live Django end-to-end test confirmed that assistant message, citation snapshot, and request metadata were persisted in its isolated PostgreSQL test database. No synthetic adapter or response was used in this test.

An earlier diagnostic Python-list query was correctly fail-closed by the existing claim/citation verifier and returned no citation. It was not counted as a successful grounded result. A source-specific Docker query then passed retrieval, generation, claim verification and citation validation. The suite includes `test_semantic_verifier_omits_unsupported_claim_and_keeps_supported_claim` and `test_invalid_generated_citation_becomes_fail_closed_abstention` to verify that unsupported claims and invalid citations fail closed.

## Preserved state and limits

- Qdrant collection, point IDs and payloads were read only; no re-embedding or reindexing occurred.
- PostgreSQL application database and volume were not changed. Django test runs created and dropped only the isolated test database.
- Source legal approvals, document approvals, inventory, and index manifest were not changed. Legal review remains `pending`; manifest remains `operator_authorized_unreviewed`.
- FastAPI/Django images were rebuilt; only those two application services were recreated. `rag-postgres` and `qdrant` remained running.
- A stale password in ignored `django_app/.env` prevented Django startup during the first compose recreation. The file was synchronized to the credential already configured in the active PostgreSQL container; PostgreSQL credentials and data were not changed. Existing FastAPI bearer credential was carried in the ignored env file for Compose operation and is not included in registries or reports.

## Readiness

**Phase 1 technical local-demo criteria: READY.** The documentation-only local demo path is explicitly enabled and validated end to end.  
**Production / legal authorization: NOT READY.** All 14 legal source decisions and document-level reviews remain pending; arXiv papers remain excluded. Unsupported inventory categories remain excluded.
