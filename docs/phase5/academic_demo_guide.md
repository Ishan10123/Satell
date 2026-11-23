# Satell local academic demonstration

## Start and verify

Follow [startup_guide.md](startup_guide.md). Confirm Django and FastAPI are healthy, authenticated FastAPI `/ready` returns 200 from the Django container, and Qdrant collection `rag_docs_v2` is green. The local setup uses the real HTTP adapter, signed local academic demo authorization, dense retrieval, and local Ollama. Local-demo operator authorization is not legal license approval.

## Browser flow

1. Open `http://127.0.0.1:8001/` and sign in with an existing account.
2. Start a conversation and ask one concise question from the currently authorized documentation subset.
3. Read the answer and its verification note. Open a citation source reference to inspect the source; a citation may use a generic landing-page URL.
4. Reopen saved conversations from history.
5. Ask about information outside the documentation subset. A query may be rejected, partially verified, or abstained; do not promise a fixed answer.
6. Sign out and confirm the protected workspace redirects to sign-in.

## Phase 6C profile and trusted creator metadata

The public creator profile is available at `/creator/` and displays only individually enabled `CreatorProfile` fields. It contains the owner's verified name and five supplied professional URLs; no Instagram or phone field is configured. Founder/creator questions use trusted application metadata instead of Qdrant retrieval and do not attach documentation citations. The profile editor is bound to the verified active owner account. See [the creator ownership report](../phase6c/phase6c_creator_profile_ownership_report.md).

User preferences are stored per account. Response style changes presentation guidance only; authorization, source evidence, citation validation, and claim verification remain in force. Password reset cannot deliver mail until an SMTP provider is configured and a controlled mailbox delivery test succeeds.

## Executed examples

The Phase 5 Chrome browser run asked, “In FastAPI, what is a path parameter? Give one concise fact from its documentation.” It produced a real, non-synthetic response with one citation. A private-service-password prompt did not reveal a credential. See `browser_e2e_results.json`.

Phase 6C used Chrome on an isolated candidate Django/PostgreSQL/FastAPI stack. Login and workflow checks passed. A real documentation query returned one persisted citation with a **partially verified** result. The screenshot and conditions are recorded in [the Phase 6C browser report](../phase6c/phase6c_browser_acceptance_report.md).

The broader 30-question live set is in `../phase4_live_evaluation_results.json`. It was sent through real Django requests, not browser clicks.

## Stop and limitations

Use the safe stop command in [startup_guide.md](startup_guide.md). Production is blocked by pending legal/document authorization, six High candidate image findings, unconfigured SMTP, and unvalidated production deployment/backup/monitoring controls. RAG answers can be partial or abstain. See [Phase 6C final blockers](../phase6c/phase6c_final_blockers.md) and [Phase 5 limitations](phase5_known_limitations.md).
