# Phase 1 Document Identity Report

## Identity model and exact mapping

The existing Qdrant collection uses the legacy content-based document ID `SHA256(source_id + NUL + content_sha256)`. That ID was preserved. The signed document registry maps each ID to source ID, SHA-256, all inventory provenance paths, and the complete indexed Qdrant point-ID list. It does not modify Qdrant payloads or point IDs.

- Documentation inventory records: **6,489**.
- Canonical documentation document IDs: **6,458**.
- Repeated inventory paths/content records: **31 extra records across 25 canonical IDs** (24 duplicate groups in Qdrant source; 1 in Docker). Each group was accepted only when all records had the same source ID and SHA-256; all paths are retained in the registry.
- Individually indexed research papers: **107**; each has its own document ID, source URL/version, acquisition path, hash, and indexed point IDs.
- Live Qdrant: **6,565 documents / 58,856 points**; all documents and points match the selected inventory identity map, with no missing, extra, or conflicting Qdrant document identities.
- Documentation points: **53,420**; research-paper points: **5,436**.

| Source ID | Documentation inventory records | Canonical authorized IDs | Duplicate extra records | Indexed point IDs |
|---|---:|---:|---:|---:|
| `arxiv_ai_systems` | 0 | 0 | 0 | 701 |
| `arxiv_artificial_intelligence` | 0 | 0 | 0 | 660 |
| `arxiv_database_vector_search` | 0 | 0 | 0 | 763 |
| `arxiv_information_retrieval` | 0 | 0 | 0 | 769 |
| `arxiv_llm_rag` | 0 | 0 | 0 | 610 |
| `arxiv_llm_transformers` | 0 | 0 | 0 | 724 |
| `arxiv_machine_learning` | 0 | 0 | 0 | 1209 |
| `docker` | 1113 | 1113 | 1 | 12521 |
| `fastapi` | 158 | 158 | 0 | 2398 |
| `huggingface_transformers` | 787 | 787 | 0 | 8948 |
| `postgresql_18` | 1 | 1 | 0 | 5541 |
| `python_3_13` | 553 | 553 | 0 | 13817 |
| `pytorch` | 263 | 263 | 0 | 2594 |
| `qdrant` | 3583 | 3583 | 30 | 7601 |

Exact mappings are in `knowledge_base/metadata/local_academic_demo_document_authorizations_phase1_v3.json` (all authorized documentation point IDs and all excluded research-paper point IDs). The inventory’s `relative_path` field is absent for all 107 research papers; the registry marks this provenance gap and records a project-relative acquisition path derived from the existing `local_path` field. They remain excluded.

## Category eligibility

The inventory has 9,932 records across categories:

| Category | Inventory records | Demo/index disposition |
|---|---:|---|
| documentation | 6489 | 6,489 records represented by 6,458 authorized canonical IDs |
| research_paper | 107 | 107 indexed records mapped and excluded pending individual license review |
| code | 2067 | excluded from demo retrieval |
| image | 583 | excluded from demo retrieval |
| structured_data | 544 | excluded from demo retrieval |
| supporting_artifact | 142 | excluded from demo retrieval |

The 3,336 non-documentation records are not silently treated as documentation. The Qdrant retrieval filter requires documentation source type and exact document IDs from the signed allowlist. Context assembly independently rechecks tenant, source, ACL, unreviewed development status, source/hash identity and document allowlist membership. The generated context carries a local-unreviewed diagnostic notice.

## Unmapped and unresolved records

- Indexed selected-category documents with no inventory identity: **0**.
- Inventory documentation IDs missing from Qdrant: **0**.
- Qdrant payload source/hash inconsistencies: **0**.
- Unmapped Qdrant point IDs: **0**.
- Research papers lacking `relative_path`: **107/107**. They have acquisition paths and paper-specific URLs, but remain excluded for both missing repository-relative provenance and pending individual license review.
- All non-documentation non-paper categories remain technically excluded; their inventory bytes and hashes validated, but they receive no demo retrieval authorization.

The source inventory and legal statuses remain unchanged. All source and document legal reviews are still pending. This document mapping is operator-authorized local evaluation only.
