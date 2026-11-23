# Satell chat experience, recovery, and answer-quality implementation report

**Run date:** 2026-11-19  
**Scope:** local academic demo only  
**Readiness:** supervised local demonstration; not production ready

## Summary

The chat workspace now has a keyboard-accessible password visibility control, Django password reset pages and email templates, two-sided user/Satell message styling, safer citation labels, automatic/manual titles, owner-only conversation actions, and deterministic post-verification answer formatting. Verification status remains persisted and visible; citation validation, claim verification, authorization and abstention were not relaxed.

This implementation was exercised in a real Chrome browser against Django and the real HTTP RAG adapter. A 30-question live evaluation was run through the browser and existing FastAPI/Qdrant/Ollama stack. It found answer-quality failures that remain to be investigated; the evaluation is evidence, not a pass.

## Implemented behavior

### Login and account recovery

- The password input begins masked. The keyboard-operable button changes its type and accessible label without clearing the value.
- The password-reset page accepts a username or registered email. Exact username matches take precedence; ambiguous case-insensitive usernames or email addresses fail closed and do not send multiple links.
- Django’s password-reset token generator supplies an expiring token. A successful password change invalidates reuse. Existing password validators and CSRF middleware remain active.
- The same public confirmation is used for unknown, ambiguous and valid identifiers. Requests are IP-keyed and throttled through the configured cache; throttling failure rejects the request.
- Reset templates contain no submitted password. Reset delivery logs contain only a fixed redacted diagnostic.
- SMTP settings are environment-driven and passed into the Django container. The running environment has no SMTP_HOST; system check accounts.W001 warns that messages cannot be delivered. Unit tests use Django’s in-memory email backend; no real SMTP delivery is claimed.

Configure delivery in the ignored local environment file using the operator’s SMTP values:

    EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
    SMTP_HOST=<mail-server>
    SMTP_PORT=587
    SMTP_USERNAME=<mail-user>
    SMTP_PASSWORD=<mail-password>
    SMTP_USE_TLS=1
    SMTP_USE_SSL=0
    SMTP_FROM_EMAIL=Satell <no-reply@your-domain>
    PUBLIC_APP_BASE_URL=https://<application-host>
    PASSWORD_RESET_TIMEOUT_SECONDS=3600
    PASSWORD_RESET_RATE_LIMIT=5
    PASSWORD_RESET_RATE_WINDOW_SECONDS=3600

Restart only Django after changing its environment. Remote deployment must use HTTPS. Do not use the console backend outside an explicitly configured debug environment.

### Chat and titles

- User cards align right; Satell cards align left. The browser verified Satell labels, response and citation copying, follow-up persistence, 390px layout without horizontal overflow, and theme control.
- Markdown is rendered from text nodes; supported code, list, table and link markup does not use raw HTML insertion. The generation pipeline now emits a paragraph by default after claim verification; an explicit list or step request retains bullets. Citation markers are inserted immediately before final punctuation.
- Unsupported claims remain omitted. The database retains partially_verified and the UI shows “Partially verified.” The fixed technical footer and generic claim-omission sentence are not appended.
- First-message titles are generated without another model call; sensitive-looking prompts fall back to “New conversation.” A manual rename sets a flag and is not overwritten.

### Conversation lifecycle

Reads and mutations use owner-scoped database queries. Rename validates 1–70 characters. Markdown, text and JSON exports are backend-generated and omit internal IDs, prompts, API credentials and private diagnostics. JSON validity and ownership are covered by tests.

Sharing is off by default. Creating a link generates a high-entropy random token and stores only SHA-256; the owner sees it only in the no-store create response. It expires in 1–30 days and can be revoked. The public view is read-only, rate-limited, noindex, no-store and no-referrer. Anyone holding the selected link can read that one conversation until expiration or revocation.

Locking is enforced in Django before calling RAG and in the message transaction. A locked conversation remains viewable/exportable but cannot be modified or deleted until its owner unlocks it. Locking is an application state, not encryption.

### Citation presentation and source fidelity

The presentation filter strips raw and spaced Markdown anchors (including the form with spaces around the anchor), template placeholders, repeated title/section labels, control whitespace and unsafe URL forms. Browser output for the FastAPI query showed a clean “Request Body” card. Citation snapshots and Qdrant payloads were not rewritten.

The current indexed source_reference can be a repository landing URL rather than a deep page/heading URL. This implementation preserves validated links and does not invent anchors or alter the index; exact-source navigation remains a corpus metadata improvement.

## Browser verification

The script scripts/chat_experience_browser_e2e.py passed against a temporary account that was removed in finally cleanup. It checked:

- Password toggle show/hide and value preservation; unknown-account forgot-password confirmation; invalid and valid login.
- A real, non-synthetic RAG response; user/Satell sides; clean citation card; copy response and citation.
- Follow-up and title stability; rename; Markdown/TXT/JSON export.
- Read-only sharing in a separate unauthenticated browser context, noindex and revocation; lock/unlock; delete confirmation.
- Mobile width, theme control, logout/login history persistence, and absence of browser-visible service credentials.

The first browser attempts exposed test selector issues and one application issue. The harness initially selected both the password field and its labeled button, then clicked a hidden mobile sidebar control. After those selector fixes, it ran through. The share-create response had also applied Referrer-Policy no-referrer to the owner’s page, suppressing same-origin referrer context; that header was removed from the owner response. The public share page retains no-referrer. CSRF-protected share creation/revocation and browser revocation now pass.

The verified simple-question browser response rendered as one paragraph and zero list items, with title “FastAPI Path Parameter,” one citation, and verified status. Browser query latency was 2,025.02 ms.

Detailed scenario evidence: docs/academic_project/evidence/chat_experience_browser_results.json.

## 30-question live evaluation

Dataset: evaluation/satell_chat_quality_questions_20261119.jsonl. Expectations cover direct, conceptual, comparison, multi-part, implementation, version-specific, cross-source and insufficient-evidence questions. Every expectation is marked heuristic; none is expert-reviewed ground truth.

Run path: real Chrome → Django session/CSRF/views → authenticated FastAPI → existing authorization and Qdrant/Ollama pipeline → PostgreSQL persistence → rendered response. The script rejected synthetic responses. The temporary user and test conversations were deleted after the run.

| Outcome | Count |
|---|---:|
| Verified | 13 |
| Partially verified | 6 |
| Safe abstention | 4 |
| Failed / rejected | 7 |
| Non-synthetic responses with citations | 19 of 30 |

Browser end-to-end latency: minimum 486.54 ms, p50 4,768.02 ms, p95 6,484.96 ms, maximum 7,202.05 ms. Short deterministic abstentions account for the minimum. These timings are one local run, not an SLO or capacity result.

Expected abstention behavior matched for SAT-25 and SAT-28. SAT-16 and SAT-19 abstained despite being marked answerable. SAT-26 (secret request) and SAT-27 (future-version question) failed/rejected instead of returning the expected explicit safe abstention. Five answerable prompts also failed/rejected: SAT-04, SAT-05, SAT-10, SAT-11 and SAT-23. Partial answers occurred for SAT-02, SAT-06, SAT-12, SAT-13, SAT-18 and SAT-21.

The run records status, citation count and labels, response length and browser latency. It does not label factual correctness, retrieval relevance, citation entailment or completeness automatically. Citation presence and verifier status are not correctness proofs. Raw generated answers were not put into the result artifact; a human reviewer must inspect cited source passages and investigate failed queries before claiming improved answer quality.

Machine-readable results: evaluation/results/satell_chat_quality_live_20261119.json.

### Failure-stage evidence from selected rechecks

The selected recheck artifact is `evaluation/results/satell_chat_quality_failure_diagnostics_20261119.json`. It records bounded stage metadata, not raw generations or full evidence text. These diagnoses are limited to the telemetry available:

| Query | Observed path and failure reason | Interpretation |
|---|---|---|
| SAT-04 | Eight Docker candidates admitted; citation validation rejected an uncited claim before claim verification. | Generation/citation-format failure, not an authorization or context-admission failure. The raw claim text is unavailable. |
| SAT-05 | Eight PostgreSQL candidates retrieved; 3 admitted and 5 excluded by context budget; uncited claim rejected before verifier. | Context exclusion may have reduced evidence coverage, and generation also failed citation format. Causality cannot be separated without the raw answer. |
| SAT-10 | Eight Python candidates retrieved; 3 admitted and 5 context-budget exclusions; citation validation passed but verifier/consistency rejected the answer. | Verification-stage rejection is established; exact rejected claim and verifier reason were not retained. |
| SAT-11 | Eight candidates were mostly PyTorch with some Transformers; 6 admitted and 2 excluded by budget; an uncited claim was rejected before verifier. | Ranking/topic coverage and citation-format concerns; no evidence of authorization filtering. |
| SAT-16 | Eight PostgreSQL candidates, one context chunk admitted; the comparison-evidence completeness guard abstained before generation. | Safe abstention because requested cross-source evidence was unavailable; the answerable heuristic label needs review. |
| SAT-19 | Eight Qdrant candidates and no PostgreSQL source; 7 context chunks admitted; comparison completeness guard abstained before generation. | Retrieval did not cover both sides of the question; safe abstention rather than a generated unsupported comparison. |
| SAT-23 | Eight PostgreSQL candidates; 3 admitted and 5 context-budget exclusions; an uncited claim was rejected before verifier. | Context narrowing and generation citation formatting interact; exact raw claim/evidence is unavailable. |
| SAT-26 | Top results were irrelevant Docker material; 6 context chunks admitted and the uncited answer was rejected before verifier. | Retrieval was off-topic and generation failed citation format. No answer was delivered as grounded; UI reported a failed response rather than a clear explicit abstention. |
| SAT-27 | Python documentation retrieved; 6 context chunks admitted, with budget/duplicate-passage exclusions; uncited claim rejected before verifier. | Citation-format rejection prevented an unsupported answer; UI status was failed rather than explicit abstention. |

These traces establish stage outcomes, not semantic relevance of every passage. The original generated answers and exact rejected claims were not captured, so do not infer more specific root causes. The best-supported overall diagnosis is multiple interacting stages: retrieval coverage/ranking, context budgeting, generation citation formatting, and verifier consistency. Authorization did not appear as the rejection cause in these selected rechecks.

This task's final consolidation reran a representative live question twice directly through the Django-container HTTP client. One non-synthetic request returned `failed` with zero citations (2,672.45 ms); the following request returned `verified` with two citations (3,696.64 ms), preserving correlation in both. This confirms live integration and response variability. It was not a browser workflow rerun and is not a query-quality benchmark.

## Tests and runtime checks

- RAG/unit/API/security suite: 263 tests ran, 262 passed, 1 skipped (Windows symlink creation unavailable).
- Django/PostgreSQL with live and synthetic integration opt-ins: 65 passed.
- Django/SQLite with the same opt-ins: 65 passed.
- manage.py check passed with the expected accounts.W001 warning because SMTP is unset.
- makemigrations --check --dry-run reported no changes.
- compileall passed.
- Host virtual-environment pip check reported no broken requirements.
- Compose configuration is valid.
- Authenticated FastAPI /ready from the Django container returned HTTP 200 and ready=true; /health returned HTTP 200.
- PostgreSQL application counts before and after temporary test accounts: 1 user, 2 conversations, 10 messages, 14 citations.
- Qdrant rag_docs_v2 remained green with 58,856 points before and after.
- Conversation migration 0003_conversation_locked_at_conversation_share_expires_at_and_more is applied. This task added no schema fields or migration.

## Changed files

- Account recovery: django_app/accounts/forms.py, views.py, urls.py, tests.py, checks.py, apps.py; django_app/config/settings.py; django_app/compose.yaml; django_app/.env.example; reset/login templates.
- Conversation/chat behavior: django_app/conversations/views.py, tests.py, title_utils.py, templates/conversations/shared.html, conversations/templatetags/citation_display.py; Django chat templates and static styles/scripts.
- Answer formatting: src/rag_pipeline/generation/ollama.py and tests/test_generation.py.
- Browser/evaluation: scripts/chat_experience_browser_e2e.py, scripts/run_satell_chat_quality_evaluation.py, scripts/phase5_browser_e2e.py, evaluation/satell_chat_quality_questions_20261119.jsonl, evaluation/results/satell_chat_quality_live_20261119.json and the browser result above.
- Documentation: this report and updates to the academic project handbook and test/known-limitations pages.

No historical migration was edited. No new migration was required. Raw corpus, source approvals, legal status, manifest, Qdrant data and existing user/conversation/message records were not changed.

## Remaining blockers

1. Configure and verify a real SMTP account before enabling recovery outside the test backend.
2. Human-review the 30 expectations and cited evidence; investigate seven failed responses and two unexpected abstentions.
3. Review citation deep-link availability, particularly repository-root references.
4. Keep Satell classified as a supervised local academic demo. Legal reviews remain pending and production authorization is not enabled.
5. Production still lacks a complete privacy/retention policy, independent security review, tested backup/restore, monitoring/SLO, deployment TLS/rollback and capacity evidence.

## Reproduction commands

    docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml build django rag-api
    docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --no-deps django rag-api
    docker exec django_app-django-1 python manage.py check
    docker exec django_app-django-1 python manage.py makemigrations --check --dry-run
    docker exec -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test --keepdb
    docker exec -e DJANGO_DB_ENGINE=sqlite -e DJANGO_SQLITE_PATH=/tmp/satell-chat-experience-tests.sqlite3 -e SATELL_LIVE_RAG_E2E=1 -e RUN_SYNTHETIC_RAG_HTTP_TESTS=1 django_app-django-1 python manage.py test
    .\.venv\Scripts\python.exe -m unittest discover -s tests

Browser and evaluation scripts require a temporary operator-provisioned test account supplied only through SATELL_E2E_USERNAME and SATELL_E2E_PASSWORD. They do not create or print service credentials.
