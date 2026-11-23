# Validation Report - Manual License Review Package

Date: 2026-11-18

## Inventory and packet coverage

- Inventory records: 9932; distinct source IDs: 14.
- Source packets: 14/14; IDs match inventory and existing manual register: PASS.
- Research paper records: 107; unique arXiv IDs: 107.
- Paper packets: 107/107; exact IDs match inventory: PASS.
- Duplicate arXiv IDs: 0 (none).
- Missing/extra PDF audit entries: 0/0 (none).

## Evidence checks

- Local license catalog files exist and checksum match: 6/6.
- Local paper PDFs exist and checksum-match inventory: 107/107.
- Source-matrix populated evidence paths exist and listed hashes match: PASS.
- Paper-matrix metadata paths and PDF paths exist; hashes match exact local bytes: PASS.
- Inventory hash matches manifest source hash: TRUE (`3a5b96b0b6271fd12c3875470c69747c8015f58a78c423d100c75d058aa11f33`).
- Historical per-paper rights evidence: 105 external-only, 2 missing/failed.
- Missing/failed per-paper license records: 0610039, 0611122.
- Existing per-paper license labels: CC BY 4.0: 37; CC BY-NC-ND 4.0: 4; CC BY-NC-SA 4.0: 9; CC BY-SA 4.0: 3; LICENSE_NOT_ESTABLISHED: 2; arXiv non-exclusive distribution license (limited distribution grant): 52.
- Direct official arXiv API request timed out; historical per-paper lookups date to 2026-11-16 and are not local original license-page copies.

## CSV and human review fields

- Both CSVs parse with Python csv.DictReader and have the exact required columns.
- Row counts/unique IDs and inventory correspondence: 14 sources, 107 papers; PASS.
- Every human_review_status is `pending`; decision and notes columns are blank.
- All 121 packets end with `Human decision: PENDING`.

## Source exceptions

- Six checksum-matched catalog artifact rows cover four sources (Docker, FastAPI, Hugging Face Transformers, PyTorch).
- Python local legal pages and PostgreSQL PDF legal notice are unbound candidate materials.
- PyTorch docs BSD statement is external to the inventory-pinned `pytorch/pytorch` repo; Qdrant docs license remains missing.
- PostgreSQL inventory version 18 vs PDF metadata 18.7 requires review.

## Protected-file digests

- `knowledge_base\metadata\ingestion_inventory.jsonl`: `3a5b96b0b6271fd12c3875470c69747c8015f58a78c423d100c75d058aa11f33`
- `knowledge_base\metadata\license_evidence.jsonl`: `9b32db0ba2da0321402a9dc4b22943a9629755a489fa2a167a4c86b36fe4d494`
- `knowledge_base\metadata\manual_source_license_review.csv`: `e9739d328d74bedf32ac7e93623890c55c7cd9123ada8e581fad6d50a07e42b2`
- `knowledge_base\metadata\source_approvals.json`: `a3e7aa922855053b8be40e74aa9446b36c9246441d5ebc5d80c36b258da7fcb2`
- `knowledge_base\metadata\index_manifests\rag_docs_v2.json`: `9b1540893ac73bfbeb01c7a10155fa9f6739457df7e9bd369919cc14c119c1ed`
- `knowledge_base\metadata\license_human_review_packet_20261116.json`: `41291ecf83e2e403766e4d9d070144a0981bd8b9c58d432b84e69e9ee4729e92`
- `knowledge_base\metadata\arxiv_documents.jsonl`: `35ffcf31e035bbb330be11dd1f6b9fd4e227a36019d41765709e45bd65d8b19c`
- `knowledge_base\metadata\arxiv_audit_report.jsonl`: `e0a7957496b888ea793950e620ed244ad3165fdb03e570280bf750d791924b12`

No package-generation command wrote to these protected project inputs. Their current SHA-256 values were recorded and checked during final validation. Only new review artifacts under `docs/license_reviews/` and the requested final report were created.

- Current source approval registry: 14/14 records remain `pending_review`; `document_approvals.json` is absent.
