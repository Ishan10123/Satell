# Satell Phase 3 Browser and User Workflow Validation

Date: 2026-11-18

## Result

The login page was opened in the in-app browser at `http://127.0.0.1:8001` and rendered successfully. Browser-side form submission was not performed, so the visual browser workflow is **incomplete**. To validate the actual application path without automating a browser authentication dialog, the running Django application was exercised through its real HTTP interface using a disposable, unprivileged test account. That account was removed after the run.

## Actual HTTP workflow evidence

The workflow used Django's CSRF-protected login and message forms, the configured real FastAPI HTTP adapter, Qdrant dense retrieval, and Ollama generation. The test account and its dependent conversation data were deleted at completion.

| Check | Result |
|---|---|
| Login page | HTTP 200 |
| Invalid credentials | Rejected |
| Valid login | Completed |
| Dashboard | HTTP 200 |
| First conversation | Created; detail HTTP 200 |
| Real RAG messages | 20 submitted; all completed through the HTTP path |
| Citation rendering | 34 citation links rendered; citation provenance present |
| Citation link spot checks | Python 3.13 docs, FastAPI repository, and Qdrant docs each returned HTTP 200 |
| Follow-up messages | Completed in the existing conversation |
| Conversation history | Listed and survived logout/login |
| Logout | Redirected; logged-out detail access redirected to login |
| Relogin | Completed |
| Second conversation | Created |

The 20 responses were not mock output. The captured performance artifact records retrieved document/source IDs, scores, retrieval diagnostics, generation/verification status and citations for each query. Eleven of the 20 contained cited answers; the other requests completed with fail-closed rejection or safe abstention behavior. See [phase3_performance_samples.json](phase3_performance_samples.json).

The live browser check did not visually observe the loading transition or click the displayed citations. The loading label and busy-state behavior are present in `django_app/chat/static/chat/app.js` and are covered by `ConversationOwnershipTests.test_composer_counter_uses_unicode_code_points_and_configured_limit`; the HTTP run confirmed links were rendered and spot-checked their targets independently.

## Limitations

- This is one local HTTP workflow using a temporary account, not a sustained browser or cross-device test.
- The second conversation was created but not populated with a RAG question.
- The three citation URLs are spot checks, not exhaustive validation of all citation targets.
- The running application remains local-only and uses HTTP on loopback.
