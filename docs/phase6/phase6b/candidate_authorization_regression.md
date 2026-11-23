# Phase 6B candidate authorization regression

## Findings

- Existing source approval registry still contains 14 records, all `pending_review`.
- Existing legal review statuses were not changed.
- Existing production index manifest remains `operator_authorized_unreviewed`.
- The expected production document approval registry is absent.
- No fake legal approvals were created.
- The candidate synthetic fixture had one documentation record. Its synthetic source and document authorization registries were temporary, HMAC-signed with an isolated test-only credential, bound to the fixture inventory hash, and retained legal status `pending`.
- Demo mode was enabled explicitly only in the isolated candidate FastAPI container with `RAG_AUTHORIZATION_MODE=local_academic_demo` and `RAG_LOCAL_ACADEMIC_DEMO_ENABLED=1`.
- A separate candidate API process used `RAG_AUTHORIZATION_MODE=production` and `RAG_LOCAL_ACADEMIC_DEMO_ENABLED=0`. Its `/ready` returned HTTP 503 because the manifest did not claim reviewed source/document authorization.
- An invalid bearer credential returned HTTP 401.
- No original approval registry or manifest was mounted writable or modified.

## Automated fail-closed coverage

The Linux candidate RAG suite ran **270 tests, all passed**. The authorization-related coverage includes:

- `test_production_api_rejects_unreviewed_development_index`
- `test_demo_mode_is_disabled_by_default`
- `test_demo_allows_only_inventory_documentation_and_keeps_legal_review_pending`
- `test_demo_abstention_does_not_imply_legal_approval`
- `test_unknown_document_id_is_rejected`
- `test_unsupported_category_cannot_be_added_to_demo_registry`
- `test_tampered_registry_fails_closed`
- `test_missing_demo_registry_fails_closed`
- `test_demo_requires_unreviewed_index_manifest`
- `test_source_registry_tampering_and_missing_registry_fail_closed`
- `test_unknown_source_is_rejected_even_with_a_valid_signature`
- `test_unknown_document_and_hash_mismatch_fail_closed`
- `test_pending_and_rejected_sources_remain_blocked`
- `test_approval_registry_requires_complete_manual_evidence`

The live production-mode readiness check independently confirmed rejection of the unreviewed synthetic manifest. This did not test the production gate against the real Qdrant corpus because that corpus was intentionally not attached to candidate infrastructure.

## Remaining authorization blockers

Production remains **NOT_READY**. A human reviewer must complete the evidence-backed source decisions and per-document decisions required by the production approval logic. The source registry has 14 pending sources; individual document approvals remain unresolved and the production document registry is missing. Local demo operator authorization remains a distinct evaluation policy and does not establish license review or production approval.
### Test harness note

A first candidate-image invocation mounted only the test directory; 262 tests executed and 8 errored because that reduced harness omitted project `configs/` and `scripts/` files required by test discovery. Those were test-environment import/configuration errors, not accepted test results. The run was repeated with the repository `tests/`, `configs/`, and `scripts/` mounted read-only into the Linux candidate image; the full result was 270 tests passed, 0 failures, 0 errors.
