# Phase 6C browser acceptance

## Environment

Google Chrome via Playwright headless on Windows. Candidate Django was available only at `http://127.0.0.1:8002`; its synthetic user and conversations lived in an isolated PostgreSQL test database. Candidate Django and FastAPI communicated over a private internal Docker network. This is actual browser automation, not an HTTP-only substitute.

## Scenarios passed

- Login page, invalid credentials rejected, valid login and workspace.
- New conversation, real query submission, loading/answer flow, citation rendering, follow-up question, history after logout/login.
- Founder question routed through trusted creator metadata without corpus citation; public links and visibility toggles checked.
- Profile edit, theme/light-dark preferences, settings page, password-recovery generic confirmation, password reset page.
- Menu keyboard navigation, Escape/focus restoration, single-open behavior, desktop placement, scroll handling, mobile viewport collision and layout.
- Conversation rename, lock/unlock, share/revoke, exports (Markdown/text/JSON), deletion confirmation, logout and relogin.

## Real RAG result

The candidate-stack browser query asked: “In Python, what is the key behavioral difference between a list and a tuple, and how do you create a one-item tuple?” The actual Django HTTP adapter called the candidate FastAPI service; Qdrant/Ollama ran the query. One citation was persisted, the response was non-synthetic, and the API classified it `partially_verified`. No fully verified answer is claimed for this query.

Screenshot: [candidate-stack response](screenshots/10_candidate_stack_real_rag.png). Earlier workflow screenshots: [login](screenshots/01_login.png), [workspace](screenshots/02_workspace.png), [profile links](screenshots/04_profile_links.png), [creator profile](screenshots/05_creator_profile.png), [founder answer](screenshots/07_founder_answer.png), [real RAG answer](screenshots/08_real_rag_answer.png), [mobile menu](screenshots/09_mobile_menu.png).

## Limitations

SMTP delivery was not tested. Testing was headless on one Chrome version and used a synthetic account/database. The app was not promoted; existing services were not replaced. See the [final readiness assessment](phase6c_release_acceptance_report.md).
