# Phase 6C security review

## Controls retained or added

- Profile/preferences pages require authentication; profile edits query by authenticated user; creator-visibility writes require the explicitly assigned profile owner. CSRF middleware and CSRF tokens remain enabled on forms.
- Creator public output is an allowlisted projection. It omits all disabled fields and private account email. Link rendering requires HTTPS and the expected platform hostname, with escaped labels and new-tab isolation attributes. No user URL input is accepted.
- Founder questions are resolved from the configured public metadata, produce no unrelated citations, and do not call the RAG client. Ordinary RAG requests retain the existing authorization/citation/verifier pipeline.
- SMTP configuration is environment-driven; no secret values were printed or changed. Rate limiting and token handling remain as existing code. Failures return generic public confirmation; operational logs exclude raw SMTP exceptions and account identifiers.
- Django image context excludes local `.env`, SQLite, tests, and corpus/docs via the smaller app context. PostgreSQL/Qdrant/container state and approvals were not touched.

## Remaining risks / not verified

- Browser visual, keyboard, mobile, and outside-click behavior was not executed because the browser automation skill file was missing; markup/JS tests are not equivalent to browser validation.
- PostgreSQL tests and service-network checks were not run because Docker Engine was unavailable. SQLite tests pass.
- SMTP credentials/host are absent; real mailbox delivery, tenant authentication, TLS negotiation, and production HTTPS reset-link delivery are untested. Django emits a configuration warning, and non-HTTPS `PUBLIC_APP_BASE_URL` in non-debug mode now emits a separate warning.
- Docker image scan/build and image-size comparison are blocked. Prior OpenSSL candidate findings remain a production release blocker.
- Creator profile edit ownership is unassigned until the operator explicitly binds the verified account. No phone number was supplied in this request; no private contact value was created.
- Existing legal/source/document approvals remain unresolved. This phase did not change or bypass production authorization.
