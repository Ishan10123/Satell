# Phase 1 Source Verification Report

**Generated:** 2026-11-18T15:39:14.375616+00:00 (UTC)  
**Project:** `E:\RAG_Project`

## Scope and method

Read-only verification covered the ingestion inventory, all referenced local files, source/license evidence catalog, approval records, current index manifest, and a full read-only scroll of Qdrant collection `rag_docs_v2`. The registry builder checked every inventory file’s project containment, recorded byte size, and SHA-256. It matched each indexed document identity and every Qdrant point payload to the inventory. No source URL, release, license identifier, copyright statement, or missing provenance was invented.

Inventory fingerprint: `3a5b96b0b6271fd12c3875470c69747c8015f58a78c423d100c75d058aa11f33`. All 9,932 inventory file records were present under the project root with size and SHA-256 matching their records. The source group metadata is structurally consistent. Publisher/repository identity was not independently fetched from the network; recorded source URLs and repository/commit fields are the inventory’s provenance evidence.

## Source-by-source inventory and index mapping

| Source ID | Records | Inventory categories | Extensions | Indexed docs | Excluded papers | Qdrant points | URL/version/commit metadata |
|---|---:|---|---|---:|---:|---:|---|
| `arxiv_ai_systems` | 15 | research_paper: 15 | .pdf: 15 | 15 | 15 | 701 | URL: 15 per-document URLs recorded (see signed source registry); version: 15 distinct version value(s); commit: not recorded |
| `arxiv_artificial_intelligence` | 13 | research_paper: 13 | .pdf: 13 | 13 | 13 | 660 | URL: 13 per-document URLs recorded (see signed source registry); version: 13 distinct version value(s); commit: not recorded |
| `arxiv_database_vector_search` | 15 | research_paper: 15 | .pdf: 15 | 15 | 15 | 763 | URL: 15 per-document URLs recorded (see signed source registry); version: 15 distinct version value(s); commit: not recorded |
| `arxiv_information_retrieval` | 15 | research_paper: 15 | .pdf: 15 | 15 | 15 | 769 | URL: 15 per-document URLs recorded (see signed source registry); version: 15 distinct version value(s); commit: not recorded |
| `arxiv_llm_rag` | 16 | research_paper: 16 | .pdf: 16 | 16 | 16 | 610 | URL: 16 per-document URLs recorded (see signed source registry); version: 16 distinct version value(s); commit: not recorded |
| `arxiv_llm_transformers` | 15 | research_paper: 15 | .pdf: 15 | 15 | 15 | 724 | URL: 15 per-document URLs recorded (see signed source registry); version: 15 distinct version value(s); commit: not recorded |
| `arxiv_machine_learning` | 18 | research_paper: 18 | .pdf: 18 | 18 | 18 | 1209 | URL: 18 per-document URLs recorded (see signed source registry); version: 18 distinct version value(s); commit: not recorded |
| `docker` | 1935 | code: 17, documentation: 1114, image: 237, structured_data: 538, supporting_artifact: 29 | .avif: 21, .css: 11, .dot: 3, .excalidraw: 1, .gliffy: 8, .gotmpl: 3, .jpg: 4, .js: 11, .json: 2, .md: 1114, .mjs: 4, .png: 59, .sh: 2, .svg: 43, .webp: 110, .yaml: 535, .yml: 1, [no_extension]: 3 | 1113 | 0 | 12521 | URL: `https://docs.docker.com/`; version: not recorded; commit: 1 distinct commit value(s) |
| `fastapi` | 410 | code: 3, documentation: 158, image: 247, supporting_artifact: 2 | .css: 2, .jpg: 4, .js: 3, .md: 158, .png: 187, .svg: 56 | 158 | 0 | 2398 | URL: `https://github.com/fastapi/fastapi`; version: 1 distinct version value(s); commit: 1 distinct commit value(s) |
| `huggingface_transformers` | 790 | code: 1, documentation: 787, structured_data: 2 | .md: 787, .py: 1, .yml: 2 | 787 | 0 | 8948 | URL: `https://huggingface.co/docs/transformers/`; version: not recorded; commit: 1 distinct commit value(s) |
| `postgresql_18` | 1 | documentation: 1 | .pdf: 1 | 1 | 0 | 5541 | URL: `https://www.postgresql.org/files/documentation/pdf/18/postgresql-18-A4.pdf`; version: 1 distinct version value(s); commit: not recorded |
| `python_3_13` | 602 | code: 15, documentation: 553, image: 21, structured_data: 3, supporting_artifact: 10 | .css: 7, .html: 553, .inv: 1, .js: 14, .json: 2, .png: 20, .py: 1, .svg: 1, .woff2: 1, .xml: 1, [no_extension]: 1 | 553 | 0 | 13817 | URL: `https://docs.python.org/3.13/`; version: 1 distinct version value(s); commit: not recorded |
| `pytorch` | 352 | code: 7, documentation: 263, image: 78, structured_data: 1, supporting_artifact: 3 | .conf: 1, .css: 3, .gif: 1, .jpg: 4, .md: 255, .png: 71, .py: 7, .rst: 7, .svg: 2, .txt: 1 | 263 | 0 | 2594 | URL: `https://pytorch.org/docs/stable/`; version: not recorded; commit: 1 distinct commit value(s) |
| `qdrant` | 5735 | code: 2024, documentation: 3613, supporting_artifact: 98 | .cs: 300, .css: 96, .csv: 1, .go: 299, .gotmpl: 1, .java: 301, .js: 97, .md: 3613, .mjs: 5, .py: 355, .rs: 306, .sh: 59, .ts: 302 | 3583 | 0 | 7601 | URL: `https://qdrant.tech/documentation/`; version: not recorded; commit: 1 distinct commit value(s) |

The seven arXiv groups contain individual paper URLs and versions. A single group-level URL/version would be misleading; the signed source registry retains the per-record values. Indexed document and point counts above are live Qdrant counts. Documentation record duplicates are consolidated by the legacy index ID and retain all original inventory `relative_path` values.

## License and notice evidence

All 9,932 inventory rows still have `license_review_status=pending`. The evidence catalog has 6 artifacts bound by `source_id`; the six recorded artifact files exist within the project and their SHA-256 values match:

| Source | Evidence file | SHA-256 | Exists, source-bound and checksum matched |
|---|---|---|---|
| `docker` | `knowledge_base/raw/official_documentation/docker/docs/LICENSE` | `089009c932d3cc296355e429fa9d6faf80ac89597da866e2424b4ea09add64b1` | yes |
| `fastapi` | `knowledge_base/raw/official_documentation/_sources/fastapi/LICENSE` | `2853a942962e3bb755239b5fecb736503be392554c1d90f97cea7f29f4465d34` | yes |
| `huggingface_transformers` | `knowledge_base/raw/official_documentation/_sources/huggingface_transformers/LICENSE` | `10fe554b4ffd57008fd1b44474b005f2c35af7312608dbd95fecad82fe87ab42` | yes |
| `pytorch` | `knowledge_base/raw/official_documentation/_sources/pytorch/LICENSE` | `0fc92425d130d9c87a5eb7427082e3afdbff6ef169bc678e15abba4c2d37c934` | yes |
| `pytorch` | `knowledge_base/raw/official_documentation/_sources/pytorch/NOTICE` | `1c3dec6c0342c7ed9e12af59b296c7bb1d394af5cf881db74191cc8299efce5c` | yes |
| `docker` | `knowledge_base/raw/official_documentation/_sources/docker/LICENSE` | `089009c932d3cc296355e429fa9d6faf80ac89597da866e2424b4ea09add64b1` | yes |

Source-specific inventory inspection also found: `knowledge_base/raw/official_documentation/docker/docs/LICENSE`, `knowledge_base/raw/official_documentation/_sources/docker/LICENSE`, `knowledge_base/raw/official_documentation/_sources/fastapi/LICENSE`, `knowledge_base/raw/official_documentation/_sources/huggingface_transformers/LICENSE`, `knowledge_base/raw/official_documentation/_sources/pytorch/LICENSE`, `knowledge_base/raw/official_documentation/_sources/pytorch/NOTICE`, `knowledge_base/raw/official_documentation/python/3.13/python-3.13-docs-html/license.html`, `knowledge_base/raw/official_documentation/python/3.13/python-3.13-docs-html/copyright.html`. Python’s generated documentation includes local `license.html` and `copyright.html` pages, but no Python source-bound `license_evidence.jsonl` catalog row was found. No source-bound catalog evidence was found for PostgreSQL or Qdrant, and no arXiv evidence rows exist. A file’s presence or source association does not establish that its terms cover examples, generated assets, vendored material, or third-party content.

## Verification result

- 14 of 14 requested source IDs are present and internally consistent in inventory metadata.
- 9,932 of 9,932 local inventory files passed path, size, and hash checks.
- Qdrant has 6,565 documents and 58,856 points; all indexed document IDs map to the selected documentation or research-paper inventory categories with matching source and content hash.
- The operator registries record local academic authorization only. The existing legal source approvals remain `pending_review` for all 14 sources.
- Legal review is **not complete**. These checks are technical provenance validation, not a legal conclusion.
