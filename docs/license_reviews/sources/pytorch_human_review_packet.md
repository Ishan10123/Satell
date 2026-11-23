# Human License Review Packet - PyTorch Documentation

Evidence organization only; not legal advice, approval, or permission to ingest.

## 1. Source identity

- Source ID: `pytorch`
- Source name: PyTorch Documentation
- Original documentation URL: https://pytorch.org/docs/stable/
- Original repository URL: https://github.com/pytorch/pytorch.git
- Recorded repository commit: 242a9cf0e013551eaada7827cfff1aa8d293dfb1
- Recorded source version: Not recorded
- Publisher/owner: verify against the official source and original notices.
- Local sample path: `E:\RAG_Project\knowledge_base\raw\official_documentation\pytorch\docs\_static\css\copybutton.css`
- Snapshot records: 352 total; documentation category 263; categories: code=7, documentation=263, image=78, structured_data=1, supporting_artifact=3.
- Extensions: .conf=1, .css=3, .gif=1, .jpg=4, .md=255, .png=71, .py=7, .rst=7, .svg=2, .txt=1.

## 2. License and evidence
- Candidate license name/identifier: **Separate pytorch/docs repository reports BSD for docs; local pytorch/pytorch LICENSE/NOTICE contain multiple terms**
- Version: Not established for captured docs
- Copyright holders/notices: Notices name Facebook, Idiap, DeepMind, NEC, NYU, Google, Kakao Brain, Cruise, Tri Dao, Arm, and others.
- Evidence quality label: `PARTIAL_EVIDENCE` (not approval).
- Scope and missing-evidence summary: Scope mismatch: inventory pins pytorch/pytorch, while BSD docs statement is in separate pytorch/docs and not pinned to the captured snapshot. Local NOTICE identifies third_party submodule licenses held in their repositories.
- Prior review scope note: The separate pytorch/docs project states its docs are BSD licensed. Local source inventory includes PyTorch LICENSE and NOTICE, which cover a larger code repository with multiple dependency licenses; do not use those as blanket docs evidence.
- Official reference: https://github.com/pytorch/docs
- Official-source search date: 2026-11-18 where available; existing prior lookups dated 2026-11-16. Exact captured revision applicability is for the reviewer to confirm.

### Original local artifacts
- `E:\RAG_Project\knowledge_base\raw\official_documentation\_sources\pytorch\LICENSE`; exists `true`; catalog SHA-256 `0fc92425d130d9c87a5eb7427082e3afdbff6ef169bc678e15abba4c2d37c934`; recomputed `0fc92425d130d9c87a5eb7427082e3afdbff6ef169bc678e15abba4c2d37c934`; match `true`; catalog source binding `pytorch`; status `text_extracted`.
- `E:\RAG_Project\knowledge_base\raw\official_documentation\_sources\pytorch\NOTICE`; exists `true`; catalog SHA-256 `1c3dec6c0342c7ed9e12af59b296c7bb1d394af5cf881db74191cc8299efce5c`; recomputed `1c3dec6c0342c7ed9e12af59b296c7bb1d394af5cf881db74191cc8299efce5c`; match `true`; catalog source binding `pytorch`; status `text_extracted`.
- Related notice/page `knowledge_base/raw/official_documentation/_sources/pytorch/NOTICE`; exists `true`; SHA-256 `1c3dec6c0342c7ed9e12af59b296c7bb1d394af5cf881db74191cc8299efce5c`.
- Separate docs repository license file: https://github.com/pytorch/docs/blob/main/LICENSE (the repository states docs are BSD licensed). It is external evidence, not locally hashed or pinned to the inventory capture; it is not the same repository as inventory-pinned pytorch/pytorch.
- NOTICE says third_party libraries are submodule links with licenses in their respective repositories.

## 3. Documentation, code examples, and media

- Documentation license evidence status: `EXTERNAL_EVIDENCE_ONLY`.
- Code-example terms: inspect origin and per-file notices; root repository license is not automatically applied to copied or external examples.
- Images/diagrams/screenshots/logos/fonts: no complete asset-level rights review is established; inspect individual provenance and attribution.
- Third-party/vendored/generated/embedded content: integrations, snippets, generated reference pages and assets need review. Heuristic hits are leads, not findings.
- Non-documentation inventory categories (code, data, images, supporting artifacts) need separate provenance and rights review.

## 4. Attribution and separate notices

- Inspect full terms for copyright/NOTICE preservation, attribution, license-copy/link, change marking, or redistribution conditions. This packet does not determine compliance.
- Do not assume the repository license covers every docs file or third-party contribution. Scope must match the captured revision.

## 5. Missing or conflicting evidence

- Scope mismatch: inventory pins pytorch/pytorch, while BSD docs statement is in separate pytorch/docs and not pinned to the captured snapshot. Local NOTICE identifies third_party submodule licenses held in their repositories.
- Identify any separately licensed page, example, asset, component, or contribution and record its own evidence.

## 6. Human review questions

1. Does evidence apply to the exact captured revision and intended RAG use?
2. Do documentation text, examples, generated output, and media have different terms?
3. Are third-party materials covered, excluded, or separately licensed?
4. What attribution and notice conditions apply?
5. Is more evidence, written permission, or qualified legal review required?
6. What exact content scope must remain excluded?

## 7. Evidence paths and references
- Documentation URL: https://pytorch.org/docs/stable/
- Repository URL: https://github.com/pytorch/pytorch.git
- Primary local artifact: `knowledge_base/raw/official_documentation/_sources/pytorch/LICENSE`
- See `../evidence_index.md` for all paths, hashes and evidence limits.

## Human review decision

- Reviewer: ____________________
- Review date: ____________________
- Original license inspected: ____________________
- Source applicability verified: ____________________
- Third-party material reviewed: ____________________
- Attribution obligations understood: ____________________
- Additional legal review required: ____________________
- Human decision: PENDING
- Reviewer notes: ____________________
