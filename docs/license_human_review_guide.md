# Human license review guide

Generated 2026-11-16. This packet prepares evidence for the project owner; it does not make legal determinations. **All 14 source decisions remain `pending_review`.** No approval command was run and no approval registry was edited.

## Read the package

- `knowledge_base/metadata/license_human_review_checklist_20261116.csv`: Excel-friendly checklist, one row for each of the 14 source records (7 documentation sources and 7 arXiv collections), plus each of 107 individual arXiv papers.
- `knowledge_base/metadata/license_human_review_packet_20261116.json`: complete source and paper records, evidence classifications, local paths, hashes, rights URLs and retrieval status.
- `knowledge_base/metadata/license_evidence_inventory_20261116.json`: local and online evidence artifact inventory.
- `knowledge_base/metadata/source_approvals.json`: authoritative decision registry; it remains unchanged and pending.

Start with read-only reports:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py license-report
.\.venv\Scripts\python.exe scripts/ragctl.py authorization-report
```

For each documentation source, inspect the pinned commit, recorded local legal artifacts and the official license link. Determine whether permission covers docs prose, examples/code, diagrams/media, third-party snippets, and supporting files. A root license alone is not blanket permission for third-party material. For arXiv, open each paper's individual abstract and selected license URL; distinguish the submitter's arXiv distribution license from rights to reuse text in this local RAG corpus. The arXiv page states versions can have different licenses and warns authors about journal/funder obligations. The local packet records the exact page retrieval date and failures; a failed fetch stays missing evidence.

## Decision rules

Use the packet's classifications only as review aids. `Evidence verified and scope sufficiently documented for human consideration` still requires the owner to read the exact terms and check the intended local storage, chunking, retrieval, citation, and retention use. If license identity, version, scope, third-party ownership, or intended-use compatibility is unclear, leave `pending_review` and obtain more evidence. Record one decision per documentation source, and one decision per arXiv document. Source metadata approval never approves papers.

After reviewing a documentation source, record the owner's decision with an in-project evidence catalog and accurate reviewer details, for example:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-source fastapi `
  --decision approved --reviewer "<owner name>" --license-name "MIT" `
  --scope documentation_candidates `
  --evidence knowledge_base\metadata\license_evidence.jsonl `
  --notes "<scope and third-party review actually completed>"
```

For an arXiv paper, first establish metadata-source scope if required by the CLI workflow, then decide the exact paper using its `document_id` from the checklist:

```powershell
.\.venv\Scripts\python.exe scripts/ragctl.py approve-document <document_id> `
  --source-id arxiv_<collection> --decision approved --reviewer "<owner name>" `
  --license-name "<verified license>" --evidence knowledge_base\metadata\license_evidence.jsonl `
  --notes "<paper-specific rights and third-party review completed>"
```

Do not copy placeholder values or choose `approved` unless the owner has completed that review. The commands above are procedural examples only and were not executed.

## Source review notes

### arxiv_ai_systems (`arxiv_ai_systems`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### arxiv_artificial_intelligence (`arxiv_artificial_intelligence`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### arxiv_database_vector_search (`arxiv_database_vector_search`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### arxiv_information_retrieval (`arxiv_information_retrieval`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### arxiv_llm_rag (`arxiv_llm_rag`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### arxiv_llm_transformers (`arxiv_llm_transformers`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### arxiv_machine_learning (`arxiv_machine_learning`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: not located.
- Scope question: No source-specific evidence record is available.
- Third-party check: Unknown; review required.

### Docker documentation (`docker`)

- Evidence class: **Evidence exists but scope is incomplete**.
- Official reference: https://github.com/docker/docs/blob/553482ce632f00c6e7faabab863422b4916e7c18/docs/LICENSE.
- Scope question: The repository contains a docs/LICENSE artifact. Review its exact pinned revision, examples, third-party snippets, images and notices individually.
- Third-party check: Documentation has code samples, diagrams, screenshots, product marks and bundled assets; repository-level license does not establish the license of each asset.

### FastAPI documentation (`fastapi`)

- Evidence class: **Evidence exists but scope is incomplete**.
- Official reference: https://github.com/fastapi/fastapi/blob/5758a9c8347d911444dca97a55b708cc4a8de4f8/LICENSE.
- Scope question: A repository MIT license exists at the pinned source revision; inspect each documentation asset and code sample provenance.
- Third-party check: Interactive API documentation, icons, external projects and embedded examples may have separate terms.

### Hugging Face Transformers documentation (`huggingface_transformers`)

- Evidence class: **Evidence exists but scope is incomplete**.
- Official reference: https://github.com/huggingface/transformers/blob/3a134bc37f7c22c801b618e289b0255425f22647/LICENSE.
- Scope question: Pinned repository license is Apache-2.0; confirm which documentation text/examples are contributed or generated and inspect referenced assets.
- Third-party check: Model examples, datasets, external model cards, badges, figures and third-party components may carry independent terms.

### PostgreSQL 18 documentation (`postgresql_18`)

- Evidence class: **Evidence verified and scope sufficiently documented for human consideration**.
- Official reference: https://www.postgresql.org/about/licence/.
- Scope question: The official license page expressly includes documentation. Reviewer should check notices and attributed third-party excerpts in the specific PDF edition.
- Third-party check: PDF figures, cited extracts, trademarks and any externally credited material remain subject to their own terms.

### Python 3.13 documentation (`python_3_13`)

- Evidence class: **Evidence verified and scope sufficiently documented for human consideration**.
- Official reference: https://docs.python.org/3.13/copyright.html.
- Scope question: The official copyright page distinguishes the main docs from code examples. Confirm use of examples fits their additional license and inspect included third-party content.
- Third-party check: Third-party libraries, logos, screenshots, fonts and copied examples can have separate rights.

### PyTorch documentation (`pytorch`)

- Evidence class: **Evidence exists but scope is incomplete**.
- Official reference: https://github.com/pytorch/docs.
- Scope question: The separate pytorch/docs project states its docs are BSD licensed. Local source inventory includes PyTorch LICENSE and NOTICE, which cover a larger code repository with multiple dependency licenses; do not use those as blanket docs evidence.
- Third-party check: Tutorial/code examples, embedded project names, dependencies, generated API content and media require separate attribution and license review.

### Qdrant documentation (`qdrant`)

- Evidence class: **Not enough evidence to recommend approval**.
- Official reference: https://github.com/qdrant/landing_page/blob/799edaa9d0ef562790402d6d4ddf370db92162e5/LICENSE.
- Scope question: The pinned repository LICENSE URL returned 404 and no local Qdrant license artifact is cataloged. Request an authoritative docs/content license or written permission.
- Third-party check: Docs include code examples, diagrams, customer logos and externally linked material; all need scope/attribution review.

## arXiv review notes

There are 107 paper-specific rows. arXiv says each submitter chooses a license, different versions can have different licenses, and the arXiv non-exclusive license grants arXiv a limited distribution right; that link alone does not grant broad reuse permission to other users. Verify the per-paper selected URI and the first-page copyright/license text. Check publisher/funder restrictions and third-party figures/tables. Keep each paper pending when rights remain unclear.
