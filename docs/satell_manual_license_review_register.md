# satell Manual Source License Review Register

**Purpose:** evidence collection and human review preparation only. This document records available evidence and gaps; it is not a legal opinion, license determination, source approval, or document approval.

## Status and scope

- The ingestion inventory contains **14 distinct source IDs**: seven documentation sources and seven arXiv paper collections. The CSV has one row per source ID.
- All 14 entries in `knowledge_base/metadata/source_approvals.json` remain `pending_review`. No approval decision has been entered by this task.
- `knowledge_base/metadata/document_approvals.json` is absent. Individual paper-level review and decisions are therefore not represented in a document approval registry.
- Inventory source records remain pending license review and `eligible_for_processing=false`; this packet does not change them.
- The existing `index_manifests/rag_docs_v2.json` reports `operator_authorized_unreviewed` (6,565 documents / 58,856 chunks). That development index state is not evidence of human license review or production authorization.
- Evidence binding below means the artifact is listed for that source in the evidence catalog and its path/hash were checked. It does **not** mean the artifact was legally sufficient, the captured documentation is entirely covered, or the source has been approved.

The machine-readable register is [`knowledge_base/metadata/manual_source_license_review.csv`](../knowledge_base/metadata/manual_source_license_review.csv). Human review status is initialized to `pending`; decision and reviewer notes are blank. Recommendations below are triage guidance only.

## Source-by-source evidence register

| Source ID | Source / count | Source URL and provenance | License evidence and copyright | Checksum / binding | Scope concerns and human review | Recommendation |
|---|---|---|---|---|---|---|
| `docker` | Docker Documentation; 1,114 documentation records | https://docs.docker.com/ ; upstream repository https://github.com/docker/docs.git, commit `553482ce632f00c6e7faabab863422b4916e7c18`. | Apache License 2.0; version 2.0. The captured LICENSE text does not itself establish a specific copyright holder. | `knowledge_base/raw/official_documentation/_sources/docker/LICENSE` — SHA-256 `089009c932d3cc296355e429fa9d6faf80ac89597da866e2424b4ea09add64b1`. The same bytes are present at `knowledge_base/raw/official_documentation/docker/docs/LICENSE`. Catalog checksum matches and catalog record is explicitly bound to `docker`. | Review that the docs snapshot is within the intended upstream license scope; check examples, integrations, embedded assets and third-party references/content. Inventory text/path keyword hits are only indicators, not proof of separately licensed content. Confirm whether code examples have any additional terms. | **CANDIDATE_FOR_HUMAN_REVIEW** |
| `fastapi` | FastAPI Documentation; 158 documentation records | https://github.com/fastapi/fastapi ; repository `https://github.com/fastapi/fastapi.git`, version 0.162.7, commit `5758a9c8347d911444dca97a55b708cc4a8de4f8`. | MIT License; artifact does not state a license version. Copyright 2018 Sebastián Ramírez. | `knowledge_base/raw/official_documentation/_sources/fastapi/LICENSE` — SHA-256 `2853a942962e3bb755239b5fecb736503be392554c1d90f97cea7f29f4465d34`. Catalog checksum matches and record is bound to `fastapi`. | Inspect documentation scope at the pinned commit and integrations/examples referring to third-party components. Confirm whether documentation, sample code, logos/assets or embedded material have different terms. Nine phrase matches are review cues only. | **CANDIDATE_FOR_HUMAN_REVIEW** |
| `huggingface_transformers` | Hugging Face Transformers Documentation; 787 documentation records | https://huggingface.co/docs/transformers/ ; repository `https://github.com/huggingface/transformers.git`, commit `3a134bc37f7c22c801b618e289b0255425f22647` (inventory version field is blank). | Apache License 2.0; version 2.0. LICENSE identifies “Copyright 2018- The Hugging Face team.” | `knowledge_base/raw/official_documentation/_sources/huggingface_transformers/LICENSE` — SHA-256 `10fe554b4ffd57008fd1b44474b005f2c35af7312608dbd95fecad82fe87ab42`. Catalog checksum matches and record is bound to `huggingface_transformers`. | Confirm the captured docs correspond to the pinned repository state and whether model/dataset pages, examples, assets, or third-party materials have separate terms. Six phrase hits do not establish a license conflict. | **CANDIDATE_FOR_HUMAN_REVIEW** |
| `pytorch` | PyTorch Documentation; 263 documentation records | https://pytorch.org/docs/stable/ ; repository `https://github.com/pytorch/pytorch.git`, commit `242a9cf0e013551eaada7827cfff1aa8d293dfb1` (inventory version is blank). | `LICENSE` and `NOTICE` contain multiple license texts and copyright statements, including Facebook, Idiap, DeepMind, NEC and NYU; no single identifier or single holder is assigned to the entire documentation corpus. The NOTICE says third_party software are submodule links whose licenses are in their respective repositories. | `knowledge_base/raw/official_documentation/_sources/pytorch/LICENSE` — SHA-256 `0fc92425d130d9c87a5eb7427082e3afdbff6ef169bc678e15abba4c2d37c934`; related `NOTICE` — SHA-256 `1c3dec6c0342c7ed9e12af59b296c7bb1d394af5cf881db74191cc8299efce5c`. Both are checksum-matched and catalog-bound to `pytorch`. | Human must map applicable terms and copyright notices to the documentation subtree, inspect NOTICE component-by-component, and assess third_party references/examples/assets. Third-party submodule licenses are not supplied by this catalog. Code/docs scope may differ. | **EXCLUDE_PENDING_REVIEW** |
| `python_3_13` | Python 3.13 Documentation; 553 documentation records | https://docs.python.org/3.13/ (captured local rendered docs identify Python 3.13.18; inventory source version is 3.13). | No single license for the captured documentation scope is established from the catalog. Local `license.html` describes PSF License Version 2, historical BeOpen/CNRI/CWI terms, Zero-Clause BSD for code in Python documentation, and incorporated-software acknowledgements. `copyright.html` lists Python Software Foundation, BeOpen, CNRI, and Stichting Mathematisch Centrum. | Candidate local material: `knowledge_base/raw/official_documentation/python/3.13/python-3.13-docs-html/license.html` — SHA-256 `8a7bdde40d20897ebd2cc23549498362dcfe8f4f40e3f02f10823cf3bde34a07`; related `copyright.html` — SHA-256 `c42a98f946a76edd69a1d556acc560ccdd7a4c4e04a8c37e962e182d3125c873`. Both files exist and hashes were computed, but neither has a source-bound `license_evidence.jsonl` record. | Human must establish the applicable terms for the exact captured build, determine how docs text vs code examples are licensed, and inspect incorporated-software notices/third-party material. 88 pages matched a third-party phrase heuristic; that is not a finding. | **INSUFFICIENT_EVIDENCE** |
| `postgresql_18` | PostgreSQL 18 Documentation; 1 PDF documentation record | https://www.postgresql.org/files/documentation/pdf/18/postgresql-18-A4.pdf (inventory source version 18). | No exact license identifier/version is established here. The local PDF metadata says “PostgreSQL 18.7 Documentation” and “The PostgreSQL Global Development Group”; page 2 contains a legal notice naming PostgreSQL Global Development Group and Regents of the University of California. This notice is not treated as an established license identifier. | Candidate local material: `knowledge_base/raw/official_documentation/postgresql/18/postgresql-18-A4.pdf` — SHA-256 `58311c9709cf28503cd9f58b85f3918d643b81d1503aeecbe96d0ebb1c175ca8`. File hash matches inventory, but no source-bound evidence-catalog row or separate license artifact exists. | Human must check the notice and the exact PDF/build against authoritative PostgreSQL terms and assess incorporated material. Confirm the mismatch between inventory source version 18 and PDF metadata version 18.7. Do not infer a license label from the notice alone. | **INSUFFICIENT_EVIDENCE** |
| `qdrant` | Qdrant Documentation; 3,613 documentation records | https://qdrant.tech/documentation/ ; captured from `https://github.com/qdrant/landing_page.git`, commit `799edaa9d0ef562790402d6d4ddf370db92162e5` (documentation subtree). | No license identifier, copyright holder, or local LICENSE/NOTICE evidence was established in the project snapshot/catalog. This does not establish that upstream has no license. | No evidence path/hash can be listed. The catalog has no Qdrant source-bound license artifact; local snapshot review found no license/NOTICE artifact. | Obtain authoritative terms applicable to the pinned docs subtree and determine whether repository terms cover docs, generated snippets, examples, assets and third-party content. File-path heuristics indicate many generated/example paths and require scoped review. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_ai_systems` | arXiv AI Systems; 15 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_artificial_intelligence` | arXiv Artificial Intelligence; 13 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_database_vector_search` | arXiv Database / Vector Search; 15 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_information_retrieval` | arXiv Information Retrieval; 15 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_llm_rag` | arXiv LLM / RAG; 16 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_llm_transformers` | arXiv LLM / Transformers; 15 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |
| `arxiv_machine_learning` | arXiv Machine Learning; 18 individual papers | Each paper has its own `source_url` and `pdf_url` in `knowledge_base/metadata/arxiv_documents.jsonl`; individual exact URLs are listed in the appendix. | **No uniform license asserted.** Per-paper license metadata is absent in the local metadata records. | No source-bound evidence artifact or license catalog row. | Every paper requires its own license/rights and provenance check; paper license/metadata must not be inferred from the arXiv collection or another paper. Each document needs evidence and its own human decision. | **INSUFFICIENT_EVIDENCE** |

## Four checksum-matched source artifacts: reviewer inspection checklist

These are the four sources represented by source-bound evidence records (Docker, FastAPI, Hugging Face Transformers, PyTorch). The catalog rows match the listed file hashes, but source approval remains pending. The reviewer should inspect:

1. The exact full artifact at the recorded path, not only its extracted text or summary; confirm title/issuer, terms, version, copyright and notices.
2. The source binding: catalog `source_id`, source URL/repository, pinned revision, and that artifact applies to the exact documentation snapshot being considered.
3. Whether terms cover the documentation text, code samples, generated pages, logos/images, snippets and examples, or whether any of those have separate terms.
4. Copyright/attribution and notice obligations, any exclusions, and how identified third-party materials will be excluded or separately documented.
5. The proposed documentation-only ingestion scope; do not treat the repository license as blanket authorization for vendored dependencies or unrelated repository content.
6. Whether evidence needs additional per-document records for exceptions, third-party material, or separately licensed subtrees before any approval decision.

## Source-specific missing and conflicting evidence

- **Python:** two useful local HTML pages exist and their hashes are recorded above, but no source-bound evidence-catalog records exist. The license page presents multiple terms and incorporated-software acknowledgements. Establish exact scope and bind evidence before a decision.
- **PostgreSQL:** a locally captured PDF contains a legal notice, and the source checksum matches inventory. There is no source-bound evidence record or separate license file in the catalog. Resolve document version 18 vs PDF 18.7 and verify authoritative terms; do not infer an SPDX identifier.
- **Qdrant:** no local/catalog license artifact was found for the pinned documentation subtree. Obtain the authoritative terms for that revision and documentation scope; absence from the snapshot is not proof no upstream terms exist.
- **PyTorch:** catalog artifacts match and bind to the source, but the files expose multiple component licenses. `NOTICE` directs the reviewer to licenses in third-party submodule repositories, so a single corpus-wide label would be misleading.
- **Docker, FastAPI, Hugging Face:** source-bound artifacts are checksum-matched, but approval still requires human confirmation of scope, notices, examples/assets, and third-party material. Docker’s captured generic Apache-2.0 license artifact does not itself identify a holder in that file.

## Generated documentation, examples, assets, and third-party material

The inventory captures documentation-category records, not a uniform legal-content unit. Generated pages can include code snippets, examples, product integrations, assets and text from other projects. Search/path heuristics in the prior eligibility audit are review leads only; they do not prove inclusion or exclusion. Human reviewers should check page provenance and upstream notices for the captured revisions and define an explicit documentation scope. Source approval alone must not be read as blanket approval of third-party assets or unsupported content. For PyTorch the local NOTICE explicitly identifies third_party submodule licensing as separate; Python’s local license page includes incorporated software notices. For all other docs sources, the existence of third-party references in pages is a prompt for inspection, not evidence that their terms are violated or satisfied.

## arXiv paper-by-paper review

The 107 records are organized under seven discovery collections. `arxiv_documents.jsonl` contains per-paper identifiers, titles, authors, versioned abstract URLs, PDF URLs, local paths, and content hashes. It does **not** contain per-paper license name/URL/status or rights-information fields. The arXiv audit records do not fill that gap. There are no arXiv license evidence rows in `license_evidence.jsonl`. Therefore no collection-level license may be inferred.

For each paper, a human must inspect the paper’s arXiv metadata and rights/license selection, the exact version downloaded, any publisher or third-party content, and applicable reuse terms; preserve a separate evidence artifact/hash and a document-level decision. A source-level decision for an arXiv collection is not a substitute. The individual `source_url` values below are from local metadata; they identify papers but do not establish rights:

### arxiv_ai_systems — AI Systems (15 papers)

- `0802.3267v1` — The Forgiving Tree: A Self-Healing Distributed Data Structure — http://arxiv.org/abs/0802.3267v1
- `0902.2501v1` — The Forgiving Graph: A distributed data structure for low stretch under adversarial attack — http://arxiv.org/abs/0902.2501v1
- `2004.03072v1` — Characterizing and Modeling Distributed Training with Transient Cloud GPU Servers — http://arxiv.org/abs/2004.03072v1
- `2406.01698v3` — Demystifying AI Platform Design for Distributed Inference of Next-Generation LLM models — http://arxiv.org/abs/2406.01698v3
- `2501.14743v1` — KVDirect: Distributed Disaggregated LLM Inference — http://arxiv.org/abs/2501.14743v1
- `2503.02550v3` — SpecInF: Exploiting Idle GPU Resources in Distributed DL Training via Speculative Inference Filling — http://arxiv.org/abs/2503.02550v3
- `2507.10259v2` — Temporal-Aware GPU Resource Allocation for Distributed LLM Inference via Reinforcement Learning — http://arxiv.org/abs/2507.10259v2
- `2507.21276v1` — LeMix: Unified Scheduling for LLM Training and Inference on Multi-GPU Systems — http://arxiv.org/abs/2507.21276v1
- `2512.08242v1` — Chopper: A Multi-Level GPU Characterization Tool & Derived Insights Into LLM Training Inefficiency — http://arxiv.org/abs/2512.08242v1
- `2512.19606v2` — RAPID-LLM: Resilience-Aware Performance analysis of Infrastructure for Distributed LLM Training and Inference — http://arxiv.org/abs/2512.19606v2
- `2601.17768v2` — LLM-42: Enabling Determinism in LLM Inference with Verified Speculation — http://arxiv.org/abs/2601.17768v2
- `2602.24044v2` — Data Driven Optimization of GPU efficiency for Distributed LLM-Adapter Serving — http://arxiv.org/abs/2602.24044v2
- `2603.22774v3` — Characterizing CPU-Induced Slowdowns in Multi-GPU LLM Inference — http://arxiv.org/abs/2603.22774v3
- `2603.28622v1` — Trust-Aware Routing for Distributed Generative AI Inference at the Edge — http://arxiv.org/abs/2603.28622v1
- `2609.05565v1` — Toward Sustainable Distributed LLM Inference: A Systems Synthesis and Research Agenda for an Energy-, Carbon-, and Cache-Aware llm-d Control Plane — http://arxiv.org/abs/2609.05565v1

### arxiv_artificial_intelligence — Artificial Intelligence (13 papers)

- `0611122v1` — Knowledge Representation Concepts for Automated SLA Management — http://arxiv.org/abs/cs/0611122v1
- `1307.7351v2` — Knowledge Representation for Robots through Human-Robot Interaction — http://arxiv.org/abs/1307.7351v2
- `1603.03511v1` — A Set Theoretic Approach for Knowledge Representation: the Representation Part — http://arxiv.org/abs/1603.03511v1
- `1706.05261v1` — From Propositional Logic to Plausible Reasoning: A Uniqueness Theorem — http://arxiv.org/abs/1706.05261v1
- `1808.03852v1` — A Parameterized Complexity View on Description Logic Reasoning — http://arxiv.org/abs/1808.03852v1
- `2202.07412v1` — Knowledge Graph Reasoning with Logics and Embeddings: Survey and Perspective — http://arxiv.org/abs/2202.07412v1
- `2206.04801v1` — Learning Attention-based Representations from Multiple Patterns for Relation Prediction in Knowledge Graphs — http://arxiv.org/abs/2206.04801v1
- `2306.08302v3` — Unifying Large Language Models and Knowledge Graphs: A Roadmap — http://arxiv.org/abs/2306.08302v3
- `2406.19502v2` — Hierarchical Deconstruction of LLM Reasoning: A Graph-Based Framework for Analyzing Knowledge Utilization — http://arxiv.org/abs/2406.19502v2
- `2504.16021v1` — Navigating the State of Cognitive Flow: Context-Aware AI Interventions for Effective Reasoning Support — http://arxiv.org/abs/2504.16021v1
- `2509.00710v1` — On Verifiable Legal Reasoning: A Multi-Agent Framework with Formalized Knowledge Representations — http://arxiv.org/abs/2509.00710v1
- `2511.11017v1` — AI Agent-Driven Framework for Automated Product Knowledge Graph Construction in E-Commerce — http://arxiv.org/abs/2511.11017v1
- `2512.13930v1` — Hierarchical Multi-agent Large Language Model Reasoning for Autonomous Functional Materials Discovery — http://arxiv.org/abs/2512.13930v1

### arxiv_database_vector_search — Database / Vector Search (15 papers)

- `1112.2155v1` — A Concurrency Control Method Based on Commitment Ordering in Mobile Databases — http://arxiv.org/abs/1112.2155v1
- `1706.06697v1` — Index Search Algorithms for Databases and Modern CPUs — http://arxiv.org/abs/1706.06697v1
- `2401.07119v1` — Curator: Efficient Indexing for Multi-Tenant Vector Databases — http://arxiv.org/abs/2401.07119v1
- `2411.00970v1` — Incremental IVF Index Maintenance for Streaming Vector Search — http://arxiv.org/abs/2411.00970v1
- `2501.11216v3` — TigerVector: Supporting Vector Search in Graph Databases for Advanced RAGs — http://arxiv.org/abs/2501.11216v3
- `2503.01823v2` — Cracking Vector Search Indexes — http://arxiv.org/abs/2503.01823v2
- `2504.20018v3` — MINT: Multi-Vector Search Index Tuning — http://arxiv.org/abs/2504.20018v3
- `2505.12524v1` — HAKES: Scalable Vector Database for Embedding Search Service — http://arxiv.org/abs/2505.12524v1
- `2506.15987v1` — Filter-Centric Vector Indexing: Geometric Transformation for Efficient Filtered Vector Search — http://arxiv.org/abs/2506.15987v1
- `2509.05750v1` — Toward Efficient and Scalable Design of In-Memory Graph-Based Vector Search — http://arxiv.org/abs/2509.05750v1
- `2510.10123v1` — The Hybrid Multimodal Graph Index (HMGI): A Comprehensive Framework for Integrated Relational and Vector Search — http://arxiv.org/abs/2510.10123v1
- `2603.08036v3` — Samyama: A Unified Graph-Vector Database with In-Database Optimization, Agentic Enrichment, and Hardware Acceleration — http://arxiv.org/abs/2603.08036v3
- `2606.03151v1` — ACRONYM: Accelerated Approximate Nearest Neighbor Search in Memory for Dynamic Vector Databases — http://arxiv.org/abs/2606.03151v1
- `2606.19803v1` — Policy-aware Vector Search: A Vision for Fine Grained Access Control in Vector Databases — http://arxiv.org/abs/2606.19803v1
- `2608.14648v1` — Stop Indexing at Full Precision: Revisiting Clustering for Vector Embeddings — http://arxiv.org/abs/2608.14648v1

### arxiv_information_retrieval — Information Retrieval (15 papers)

- `0610039v1` — The Application of Fuzzy Logic to the Construction of the Ranking Function of Information Retrieval Systems — http://arxiv.org/abs/cs/0610039v1
- `1511.05800v1` — The Retrieval Effectiveness of Web Search Engines: Considering Results Descriptions — http://arxiv.org/abs/1511.05800v1
- `1511.05806v1` — Ranking library materials — http://arxiv.org/abs/1511.05806v1
- `1601.04605v1` — Dynamic Information Retrieval: Theoretical Framework and Application — http://arxiv.org/abs/1601.04605v1
- `1705.06979v2` — End-to-End Cross-Modality Retrieval with CCA Projections and Pairwise Ranking Loss — http://arxiv.org/abs/1705.06979v2
- `1807.05631v1` — Joint Modeling and Optimization of Search and Recommendation — http://arxiv.org/abs/1807.05631v1
- `1811.08772v1` — Overcoming low-utility facets for complex answer retrieval — http://arxiv.org/abs/1811.08772v1
- `2102.11903v2` — Neural ranking models for document retrieval — http://arxiv.org/abs/2102.11903v2
- `2103.16669v3` — An In-depth Analysis of Passage-Level Label Transfer for Contextual Document Ranking — http://arxiv.org/abs/2103.16669v3
- `2210.05512v1` — On the Interpolation of Contextualized Term-based Ranking with BM25 for Query-by-Example Retrieval — http://arxiv.org/abs/2210.05512v1
- `2210.07774v3` — Learning To Rank Diversely At Airbnb — http://arxiv.org/abs/2210.07774v3
- `2504.05181v2` — Lightweight and Direct Document Relevance Optimization for Generative Information Retrieval — http://arxiv.org/abs/2504.05181v2
- `2604.23396v1` — Lost in Decoding? Reproducing and Stress-Testing the Look-Ahead Prior in Generative Retrieval — http://arxiv.org/abs/2604.23396v1
- `2605.05991v1` — A Case-Driven Multi-Agent Framework for E-Commerce Search Relevance — http://arxiv.org/abs/2605.05991v1
- `2611.08228v1` — Domain-specific information retrieval — http://arxiv.org/abs/2611.08228v1

### arxiv_llm_rag — LLM / RAG (16 papers)

- `2210.02627v1` — Improving the Domain Adaptation of Retrieval Augmented Generation (RAG) Models for Open Domain Question Answering — http://arxiv.org/abs/2210.02627v1
- `2309.15217v2` — Ragas: Automated Evaluation of Retrieval Augmented Generation — http://arxiv.org/abs/2309.15217v2
- `2312.07796v1` — Harnessing Retrieval-Augmented Generation (RAG) for Uncovering Knowledge Gaps — http://arxiv.org/abs/2312.07796v1
- `2401.15391v1` — MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries — http://arxiv.org/abs/2401.15391v1
- `2402.07483v2` — T-RAG: Lessons from the LLM Trenches — http://arxiv.org/abs/2402.07483v2
- `2402.12317v2` — EVOR: Evolving Retrieval for Code Generation — http://arxiv.org/abs/2402.12317v2
- `2404.07220v2` — Blended RAG: Improving RAG (Retriever-Augmented Generation) Accuracy with Semantic Search and Hybrid Query-Based Retrievers — http://arxiv.org/abs/2404.07220v2
- `2411.00744v2` — CARROT: A Learned Cost-Constrained Retrieval Optimization System for RAG — http://arxiv.org/abs/2411.00744v2
- `2411.18583v1` — Automated Literature Review Using NLP Techniques and LLM-Based Retrieval-Augmented Generation — http://arxiv.org/abs/2411.18583v1
- `2412.12881v1` — RAG-Star: Enhancing Deliberative Reasoning with Retrieval Augmented Verification and Refinement — http://arxiv.org/abs/2412.12881v1
- `2502.00306v2` — Riddle Me This! Stealthy Membership Inference for Retrieval-Augmented Generation — http://arxiv.org/abs/2502.00306v2
- `2504.01346v4` — RAG over Tables: Hierarchical Memory Index, Multi-Stage Retrieval, and Benchmarking — http://arxiv.org/abs/2504.01346v4
- `2504.19754v1` — Reconstructing Context: Evaluating Advanced Chunking Strategies for Retrieval-Augmented Generation — http://arxiv.org/abs/2504.19754v1
- `2507.23334v2` — MUST-RAG: MUSical Text Question Answering with Retrieval Augmented Generation — http://arxiv.org/abs/2507.23334v2
- `2510.22344v1` — FAIR-RAG: Faithful Adaptive Iterative Refinement for Retrieval-Augmented Generation — http://arxiv.org/abs/2510.22344v1
- `2511.22858v1` — RAG System for Supporting Japanese Litigation Procedures: Faithful Response Generation Complying with Legal Norms — http://arxiv.org/abs/2511.22858v1

### arxiv_llm_transformers — LLM / Transformers (15 papers)

- `1610.00030v1` — Modeling Language Change in Historical Corpora: The Case of Portuguese — http://arxiv.org/abs/1610.00030v1
- `1610.00031v1` — Discriminating Similar Languages: Evaluations and Explorations — http://arxiv.org/abs/1610.00031v1
- `2304.12244v3` — WizardLM: Empowering large pre-trained language models to follow complex instructions — http://arxiv.org/abs/2304.12244v3
- `2308.16149v2` — Jais and Jais-chat: Arabic-Centric Foundation and Instruction-Tuned Open Generative Large Language Models — http://arxiv.org/abs/2308.16149v2
- `2310.00034v2` — PB-LLM: Partially Binarized Large Language Models — http://arxiv.org/abs/2310.00034v2
- `2310.14025v1` — Large Language Models and Multimodal Retrieval for Visual Word Sense Disambiguation — http://arxiv.org/abs/2310.14025v1
- `2312.10793v3` — Demystifying Instruction Mixing for Fine-tuning Large Language Models — http://arxiv.org/abs/2312.10793v3
- `2402.11651v2` — Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models as Agents — http://arxiv.org/abs/2402.11651v2
- `2403.17811v1` — Are Compressed Language Models Less Subgroup Robust? — http://arxiv.org/abs/2403.17811v1
- `2407.12036v2` — Exploring Advanced Large Language Models with LLMsuite — http://arxiv.org/abs/2407.12036v2
- `2409.02228v2` — Unforgettable Generalization in Language Models — http://arxiv.org/abs/2409.02228v2
- `2503.21676v2` — How do language models learn facts? Dynamics, curricula and hallucinations — http://arxiv.org/abs/2503.21676v2
- `2512.08480v1` — Soft Inductive Bias Approach via Explicit Reasoning Perspectives in Inappropriate Utterance Detection Using Large Language Models — http://arxiv.org/abs/2512.08480v1
- `2608.05850v2` — MameLoshnLM: Yiddish Language Model and Evaluation Benchmark — http://arxiv.org/abs/2608.05850v2
- `2610.00223v1` — A Holistic Assessment of the Carbon Footprint of Noor, a Very Large Arabic Language Model — http://arxiv.org/abs/2610.00223v1

### arxiv_machine_learning — Machine Learning (18 papers)

- `1805.09921v4` — Meta-Learning Probabilistic Inference For Prediction — http://arxiv.org/abs/1805.09921v4
- `1806.05009v3` — Tree Edit Distance Learning via Adaptive Symbol Embeddings — http://arxiv.org/abs/1806.05009v3
- `1812.01662v1` — Feed-Forward Neural Networks Need Inductive Bias to Learn Equality Relations — http://arxiv.org/abs/1812.01662v1
- `1812.09225v4` — Learning Representations from Dendrograms — http://arxiv.org/abs/1812.09225v4
- `1905.12588v2` — Meta-Learning Representations for Continual Learning — http://arxiv.org/abs/1905.12588v2
- `1909.08167v1` — Weighed Domain-Invariant Representation Learning for Cross-domain Sentiment Analysis — http://arxiv.org/abs/1909.08167v1
- `1910.02574v1` — Representation Learning of EHR Data via Graph-Based Medical Entity Embedding — http://arxiv.org/abs/1910.02574v1
- `1910.03081v1` — On the Interpretability and Evaluation of Graph Representation Learning — http://arxiv.org/abs/1910.03081v1
- `2011.01014v1` — Chess2vec: Learning Vector Representations for Chess — http://arxiv.org/abs/2011.01014v1
- `2107.02363v4` — Asymptotics of Network Embeddings Learned via Subsampling — http://arxiv.org/abs/2107.02363v4
- `2109.05472v2` — Compute and Energy Consumption Trends in Deep Learning Inference — http://arxiv.org/abs/2109.05472v2
- `2110.04844v3` — Frequency-aware SGD for Efficient Embedding Learning with Provable Benefits — http://arxiv.org/abs/2110.04844v3
- `2301.12636v2` — Exploring Image Augmentations for Siamese Representation Learning with Chest X-Rays — http://arxiv.org/abs/2301.12636v2
- `2302.14017v1` — Full Stack Optimization of Transformer Inference: a Survey — http://arxiv.org/abs/2302.14017v1
- `2304.13195v1` — Connector 0.5: A unified framework for graph representation learning — http://arxiv.org/abs/2304.13195v1
- `2402.06492v1` — Inducing Systematicity in Transformers by Attending to Structurally Quantized Embeddings — http://arxiv.org/abs/2402.06492v1
- `2506.09781v2` — On the Similarities of Embeddings in Contrastive Learning — http://arxiv.org/abs/2506.09781v2
- `2611.11365v1` — MG-Cache: Multi-Granularity Caching for Accelerating Diffusion Transformer Inference — http://arxiv.org/abs/2611.11365v1

## Human decision record and status

The CSV deliberately has `human_review_status=pending`, while `human_decision` and `reviewer_notes` are empty for every row. Its triage field values do not approve or reject any source. Record a reviewer identity, date, exact scope, evidence references and reasoned decision through the project’s approval workflow only after review; for arXiv, handle each paper individually in the document decision workflow. Do not edit the inventory or evidence catalog as a substitute for the formal approval process.

## Validation and readiness

- Inventory source IDs: 14 unique IDs; CSV source IDs match exactly, one row per source.
- All non-empty CSV evidence paths designate one existing file. Each recorded SHA-256 was recomputed from that file; catalog artifact hashes were also compared with their source-bound catalog records.
- CSV was parsed with Python’s `csv.DictReader`; exact required column order and row count were checked.
- Human status fields remain pending and no decision or reviewer note was populated.
- No inventory, license evidence, approval registry, manifest, Qdrant collection, or raw source file was modified by this review packet.

**Overall verdict: NOT_READY.** Human source reviews and evidence gaps remain; the seven arXiv collections additionally require individual paper-level rights review and decisions. This packet is not a legal conclusion and does not authorize ingestion.
