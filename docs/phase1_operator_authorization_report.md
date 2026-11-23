# Phase 1 Operator Authorization Report

**Operator:** Ishan Kaushik  
**Authorized at:** 2026-11-18T15:39:14.375616+00:00 (UTC)  
**Policy:** `satell-local-academic-demo-v1`  
**Source scope:** `local_academic_demo_only`  
**Inventory fingerprint:** `3a5b96b0b6271fd12c3875470c69747c8015f58a78c423d100c75d058aa11f33`

## Authorization meaning

The operator explicitly authorized all 14 source groups for local Satell academic evaluation. Each source registry record has status `operator_authorized_local_demo`, an operator, UTC timestamp, policy ID, authorization reason, associated inventory/document counts, and validation status. This is a separate technical operator instruction. It does **not** mean a license was reviewed or grant legal clearance, redistribution rights, or commercial-use permission.

Source statuses in the pre-existing legal registry remain: {'pending_review': 14}. Inventory legal statuses remain: {'pending': 9932}. No legal source/document approval record was changed. The existing document approval registry remains absent; production readiness still requires the reviewed source and document approval workflow.

## Source authorization records

| Source ID | Operator status | Inventory records | Indexed documents | Legal status | Validation |
|---|---|---:|---:|---|---|
| `arxiv_ai_systems` | `operator_authorized_local_demo` | 15 | 15 | `pending` | `validated` |
| `arxiv_artificial_intelligence` | `operator_authorized_local_demo` | 13 | 13 | `pending` | `validated` |
| `arxiv_database_vector_search` | `operator_authorized_local_demo` | 15 | 15 | `pending` | `validated` |
| `arxiv_information_retrieval` | `operator_authorized_local_demo` | 15 | 15 | `pending` | `validated` |
| `arxiv_llm_rag` | `operator_authorized_local_demo` | 16 | 16 | `pending` | `validated` |
| `arxiv_llm_transformers` | `operator_authorized_local_demo` | 15 | 15 | `pending` | `validated` |
| `arxiv_machine_learning` | `operator_authorized_local_demo` | 18 | 18 | `pending` | `validated` |
| `docker` | `operator_authorized_local_demo` | 1935 | 1113 | `pending` | `validated` |
| `fastapi` | `operator_authorized_local_demo` | 410 | 158 | `pending` | `validated` |
| `huggingface_transformers` | `operator_authorized_local_demo` | 790 | 787 | `pending` | `validated` |
| `postgresql_18` | `operator_authorized_local_demo` | 1 | 1 | `pending` | `validated` |
| `python_3_13` | `operator_authorized_local_demo` | 602 | 553 | `pending` | `validated` |
| `pytorch` | `operator_authorized_local_demo` | 352 | 263 | `pending` | `validated` |
| `qdrant` | `operator_authorized_local_demo` | 5735 | 3583 | `pending` | `validated` |

The signed source registry has 14 source records at `knowledge_base/metadata/local_academic_demo_source_authorizations_phase1_v3.json`. Its contents are protected with an HMAC signature using the existing FastAPI bearer credential as the signing key; the key is not stored in the registry. Rotating that credential requires regenerating and redeploying the registries. The document registry uses the same operator, timestamp, policy and inventory fingerprint.

## Category boundary

`configs/local_academic_demo_policy.json` explicitly allows only `source_type=documentation` and `file_category=documentation`. Research papers, code, images, structured data, and supporting artifacts remain excluded. This category boundary is independent of source-level operator authorization. The 107 indexed arXiv papers require individual license review and are explicitly excluded from the demo document allowlist.

Production API mode remains `production` by default and continues to require the existing reviewed manifest and evidence-backed approvals. The separate mode is available only with explicit `RAG_AUTHORIZATION_MODE=local_academic_demo` and `RAG_LOCAL_ACADEMIC_DEMO_ENABLED=1`; those values are explicitly set only in the local ignored environment file for this local project instance.

## Integrity and human review

The API verifies registry signatures, registry-to-inventory fingerprint, exact source IDs, exact document IDs, content hashes, provenance paths, operator identity/timestamp, point-ID uniqueness, and exact paper exclusion mapping before readiness or query. Missing/tampered/mismatched registries fail closed. Legal review remains pending for every source and document.
