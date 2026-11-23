# Phase 4 — Citation Integrity Report

Date: 2026-11-19

## Persistence and identity checks

For each of 30 final live Django submissions, extracted emitted `[S<n>]` markers and compared them with persisted `CitationSnapshot` citation IDs. Sets matched on 30/30. The run produced 81 citation snapshots in a temporary PostgreSQL transaction; all evaluation rows were rolled back after capture. Every snapshot held source/document/chunk identity fields; the final machine-readable results preserve those mappings.

This verifies marker-to-snapshot identity and Django persistence for this run. It does not independently prove semantic claim entailment or deep-link navigation.

## Citation failures

Citation validation: `{'passed': 26, 'rejected': 2, 'not_applicable': 2}`. Q03 and Q29 were rejected with `uncited_claim_rejected` / `insufficient_claim_citation_coverage`. Q17 had syntactically valid, mapped citations but failed the later version consistency check. No invalid citation ID was accepted. Citation coverage failures remain fail-closed.

## Traceability limits

Citation records include sanitized `source_reference`, title, section and optional page references. Marker-to-snapshot comparison confirms IDs are real persisted metadata; this evaluation did not fetch and compare every citation URL to the cited chunk. Prior audits noted some source references are generic documentation roots/repository roots rather than section anchors. PDF page-specific navigation also cannot be assumed.

The API does not expose raw diagnostic records; local opt-in artifacts are disabled outside evaluation. See `phase4_live_evaluation_results.json` and `phase4_failure_analysis.json`.
