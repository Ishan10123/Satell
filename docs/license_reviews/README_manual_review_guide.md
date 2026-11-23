# Manual License Review Guide - Satell Secure RAG

## Purpose and scope

This package collects local provenance, original artifacts, hashes, and previously recorded official-source lookups for independent human review. It covers all 14 inventory source IDs and all 107 unique arXiv paper records. It does not make a legal determination or authorize ingestion. All human decision fields are pending or blank.

A SHA-256 checksum proves that the referenced local bytes match the digest at verification time. It does **not** prove ownership, license applicability, permission for the intended use, or that third-party material is covered. A source-bound catalog record binds metadata to a source ID; it is not approval.

## Package map

- `sources/<source_id>_human_review_packet.md`: 14 collection/source packets.
- `arxiv_papers/<arxiv_id>_human_review.md`: one packet per unique paper.
- `master_source_review_matrix.csv`: one row per source.
- `arxiv_paper_review_matrix.csv`: one row per unique paper.
- `evidence_index.md`: local artifacts, external URLs, hashes, and limitations.
- `validation_report.md`: counts, checks, exceptions, and protected-file digest comparisons.

## Review procedure

1. Confirm source ID, source URL, repository, commit/version, local collection path, and exact scope the reviewer intends to consider.
2. Inspect the complete original license, copyright notice, and NOTICE file. Open the exact local paths in the packet. Check external sources at the recorded revision, not merely the current project homepage.
3. Recalculate local file hashes in PowerShell, for example:

   ```powershell
   Get-FileHash -Algorithm SHA256 -LiteralPath 'E:\RAG_Project\knowledge_base\raw\...\LICENSE'
   ```

   Compare with the packet. If the bytes differ, stop and reconcile. Hash equality establishes integrity only.
4. Determine whether terms cover documentation prose, code snippets, generated reference pages, images, diagrams, fonts, logos, screenshots, datasets, and embedded third-party material. Do not assume repository-root licensing applies uniformly.
5. Follow notices and links for copied examples, dependencies, generated assets, figures, quotations, or publisher content. Heuristic matches are review leads, not findings.
6. Inspect each arXiv paper separately: exact version, selected rights metadata, PDF front matter, publication status, figures/tables, quoted material, supplementary files, and attribution. ArXiv availability is not unrestricted reuse permission.
7. Record reviewer/date, exact evidence inspected, scope, exceptions, required attribution, unresolved issues, and a decision through the formal workflow only after human review. Source-level approval does not decide paper-level rights.
8. If evidence is missing, conflicting, or not pinned to the captured material, leave the item pending and obtain original evidence or qualified legal review.

## Evidence labels

Use only these evidence-quality labels: `VERIFIED_SOURCE_BOUND`, `VERIFIED_LOCAL_ARTIFACT`, `EXTERNAL_EVIDENCE_ONLY`, `PARTIAL_EVIDENCE`, `MISSING_EVIDENCE`, `CONFLICTING_EVIDENCE`, `NOT_APPLICABLE`. These labels never mean approved.

- `MISSING_EVIDENCE`: no sufficient original artifact/rights record was located. Do not infer from public access or file type.
- `CONFLICTING_EVIDENCE`: source version, file scope, notice, or license statements do not align.
- `EXTERNAL_EVIDENCE_ONLY`: an official URL/lookup is logged, but the original page is not retained locally. Reopen it before deciding.
- `PARTIAL_EVIDENCE`: some evidence exists, but scope, examples/media, exceptions, or third-party rights remain open.

## Attribution and redistribution

Inspect whether the original terms require retaining copyright notices, including the license or NOTICE file, attribution, marking changes, providing a license link, or satisfying conditions on adaptations or redistribution. This packet records source language and references; it does not decide how a particular legal obligation applies to local indexing, retrieval, display, retention, or redistribution. Keep notices traceable to the exact source file.

## arXiv handling

The current `arxiv_documents.jsonl` lacks rights fields. The existing prior review packet contains a per-paper lookup log for 105 papers and two failed lookups. The underlying pages are not archived as local original evidence; the direct API call timed out during this run. Reopen each exact version’s official page and license URL. A non-exclusive distribution license to arXiv does not establish general reuse permission. A selected paper license also does not clear third-party figures, tables, or quotations.

## Qualified legal advice

Ask qualified counsel when intended ingestion/embedding/storage/retrieval/citation/retention or redistribution scope is unclear; ownership or third-party permissions are uncertain; publisher terms may conflict with arXiv records; non-commercial, no-derivatives, or share-alike conditions may matter; or text/data-mining, derivative outputs, or jurisdiction-specific rules need interpretation. Codex does not answer these legal questions.

## External evidence and limitations

Official project pages were searched on 2026-11-18 when available; the prior local review metadata records some results retrieved 2026-11-16. A direct request to the arXiv API timed out in this run. External results may not match the exact captured revision. Where a pinned source or local artifact could not be established, the packet says so.
