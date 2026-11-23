# Django Application Foundation Report

**Project:** `E:\RAG_Project`  
**Milestone:** Django application foundation  
**Date:** 2026-11-17

## Summary

A separate Django project now lives under `django_app/`. It owns browser authentication, conversation/message persistence, citation snapshots, and generation metadata. It calls the existing RAG service only through an HTTP client boundary. The Django code has no import or direct access to `LocalRAGService`, Qdrant, Ollama, or the sparse index.

The default adapter is an explicitly synthetic mock so the UI can be exercised locally without depending on the real index. The HTTP adapter is opt-in. It keeps the FastAPI bearer token in server-side Django settings, uses bounded requests and typed errors, and stores only the verified answer and citation metadata returned by the API. It does not store raw retrieved evidence or internal prompts.

This is an application-development milestone, not production deployment. The RAG API still rejects the current `operator_authorized_unreviewed` corpus; this work does not alter that behavior or any RAG data or approval state.

## Architecture

```text
Browser
  └─ Django session authentication + CSRF-protected HTML forms
       ├─ accounts: built-in Django login and POST logout
       ├─ conversations: owner-scoped conversation reads/create/delete
       ├─ chat: message validation, persistence, and answer orchestration
       └─ rag_client: HTTP boundary or explicit synthetic mock
            └─ Existing FastAPI /v1/query (opt-in, server-to-server only)
                 └─ Existing RAG service and persistent infrastructure (unchanged)

Django relational database: PostgreSQL by default
SQLite: explicit development/test choice only
```

The four Django apps are registered independently in `django_app/config/settings.py`. Django's built-in authentication model is used; there is no new password or identity store. Conversation data uses the selected Django database. The RAG client uses the existing HTTP API contract and does not import RAG implementation code.

### Main flow

1. A user signs in through Django's `LoginView`; state-changing forms require CSRF tokens.
2. Conversation queries include `user=request.user` in the database lookup. A foreign user's guessed UUID resolves to 404. The conversation relationship cascades to messages, citations, and generation metadata on owner deletion.
3. `chat.views.message_create` validates a message of 1–2,000 characters, persists the user message and a pending assistant message, then invokes the configured server-side adapter.
4. `RAG_ADAPTER=mock` returns an explicitly labelled synthetic answer/citation. `RAG_ADAPTER=http` calls the separate FastAPI service with a server-only bearer token and a request correlation header.
5. The client validates the response structure and citation metadata, removes query strings/fragments from source references, and rejects malformed responses. The Django view persists the assistant answer, structured citation snapshots, and generation metadata. It does not represent a mock as verified real output.
6. Typed timeout/upstream/configuration failures are shown to the user generically and persisted as a failed assistant message with a failed metadata status. Internal exception detail and credentials are not sent to the browser.

The current FastAPI API is one-shot and does not accept conversation history. Django displays its own conversation history but does not send previous turns to the RAG service. Multi-turn retrieval semantics remain future integration work.

## Models and persistence

Models are in `django_app/conversations/models.py`, with the initial schema migration at `django_app/conversations/migrations/0001_initial.py`.

| Model | Stored fields and constraints |
|---|---|
| `Conversation` | UUID primary key; Django user FK with `CASCADE`; title; created/updated timestamps; index on user and descending update time. |
| `Message` | UUID; conversation FK with `CASCADE`; role (`user` or `assistant`); content; status (`pending`, `complete`, `failed`); timestamp; DB check constraints for role/status and index on conversation/time. |
| `CitationSnapshot` | UUID; message FK with `CASCADE`; citation/source/document/chunk IDs; title; JSON page references; section; sanitized URL; unique citation ID per message and document index. Raw passage/evidence text is not stored. |
| `GenerationMetadata` | UUID; message FK with `CASCADE`; request ID; retrieval mode; optional model/index version; JSON stage timings; verification status; unique metadata row per message and request-ID index. |

`verification_status` distinguishes `synthetic`, `not_reported`, and `failed`. The current FastAPI response does not provide model version, index version, or a verifier status field, so those values are left unset or marked `not_reported` unless explicitly configured. The Django client does not infer verification from the answer text.

PostgreSQL is the default backend. Connection parameters are environment-driven. SQLite must be explicitly selected with `DJANGO_DB_ENGINE=sqlite`; tests use an in-memory SQLite database. No database server was started and no PostgreSQL connection/migration was performed in this milestone.

## Authentication, ownership, and CSRF

- Django's built-in session authentication is used with standard password validators.
- Sign-in uses Django's `LoginView`; sign-out is POST-only.
- All conversation list/detail/delete and message endpoints require authentication.
- Detail, delete, and send operations perform a user-filtered database lookup before acting. There is no API to update another user's conversation or message.
- Django's CSRF middleware is enabled; all state-changing templates include `{% csrf_token %}`.
- Session and CSRF cookies are HttpOnly and SameSite=Lax. Secure-cookie and HTTPS redirect settings are available through environment flags for deployment.
- Tenant/principal scope is not accepted from browser forms. The initial FastAPI API still has one static server-side principal; an issuer-backed identity bridge is required before multi-user RAG authorization.
- `RAG_API_TOKEN` is read only by Django server configuration and the HTTP client. It is not included in templates, forms, JavaScript, browser responses, or exception messages.
- No sign-up or password-reset workflow is implemented; users can initially be managed by an operator through Django admin or a management command.

## RAG client contract

`django_app/rag_client/client.py` defines a `RAGClient` protocol and immutable `RAGResponse`/`CitationMetadata` value objects.

The synchronous contract is `query(query, top_k, correlation_id) -> RAGResponse`. It validates answer length, request ID, retrieval mode, citation IDs and metadata, page references, and finite non-negative timing values. `FastAPIRAGClient` calls `POST /v1/query`, maps timeouts, transport failures, HTTP failures, and malformed responses to typed application errors, disables redirects, and requires HTTPS for non-loopback URLs. Component timeout is configured by `RAG_API_TIMEOUT_SECONDS`.

`MockRAGClient` returns a fixed synthetic answer, synthetic citation identifiers, and `retrieval_mode="synthetic_mock"`; `RAGResponse.synthetic` is true. It is not a RAG simulation and makes no claim about retrieval quality. The chat template displays an explicit mock-mode notice. `RAG_ADAPTER` defaults to `mock`; real HTTP mode requires explicit environment configuration and a 32-character-or-longer token.

There is no raw token streaming. The current API returns only after generation and claim verification. Django submits a normal synchronous request, bounded by its HTTP timeout.

## Django routes

| Method and path | Behavior |
|---|---|
| `GET, POST /accounts/login/` | Django session login. |
| `POST /accounts/logout/` | CSRF-protected logout. |
| `GET /` | Authenticated user's conversation list. |
| `POST /conversations/new/` | Create an owned conversation. |
| `GET /conversations/{uuid}/` | Read an owned conversation with messages/citations. |
| `POST /conversations/{uuid}/messages/` | Validate/persist user input, invoke RAG adapter, persist result. |
| `POST /conversations/{uuid}/delete/` | Delete an owned conversation and its cascaded records. |
| `/admin/` | Django admin for operator-managed accounts/configuration. |

Cross-user conversation IDs return 404. The browser submits only message content and a conversation UUID; it cannot submit tenant/principal scope, API URL, or RAG credentials.

## Environment configuration

Important settings are read from process environment, not committed `.env` files. The default timezone is `Asia/Kolkata`, recognized by the Linux image and equivalent for this application to the legacy Windows alias:

| Variable | Purpose/default |
|---|---|
| `DJANGO_SECRET_KEY` | Django signing secret; development fallback only. Required when `DJANGO_DEBUG=0`. |
| `DJANGO_DEBUG` | Development mode; defaults to true for this local milestone. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts; defaults to `127.0.0.1,localhost`. |
| `DJANGO_DB_ENGINE` | `postgresql` by default; set to `sqlite` explicitly for tests/local fallback. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | PostgreSQL connection settings. Database defaults to `rag_application` on loopback. |
| `RAG_ADAPTER` | `mock` by default; set to `http` to use FastAPI. |
| `RAG_API_BASE_URL` | FastAPI base URL; defaults to loopback `http://127.0.0.1:8000`. Non-loopback URLs require HTTPS. |
| `RAG_API_TOKEN` | Server-only bearer token for HTTP mode. Never expose to browser code. |
| `RAG_API_TIMEOUT_SECONDS`, `RAG_API_TOP_K` | Client timeout and retrieval count (1–20). |
| `RAG_MODEL_VERSION`, `RAG_INDEX_VERSION` | Optional operator-supplied snapshot labels; not inferred from current API response. |

The Django project sets CSRF middleware, upload limits, content-type sniffing protection, and frame denial. The local defaults are not a production deployment profile: configure a secret key, `DEBUG=0`, allowed hosts, HTTPS, secure cookies, PostgreSQL credentials, and an appropriate trusted-origin list before deployment.

## Dependencies

Added to the root `requirements.txt`:

- `Django==5.2.13`
- `psycopg[binary]==3.3.9`

The selected Django LTS release documents Python 3.13 support; Psycopg documents Windows support and binary installation. References: [Django 5.2 release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/) and [Psycopg installation guide](https://www.psycopg.org/psycopg3/docs/basic/install.html).

The existing `httpx` dependency is reused for the server-side RAG client. No DRF, Celery, Redis, paid service, or external model API was added.

## Tests and checks

Added tests in `django_app/conversations/tests.py` and `django_app/rag_client/tests.py` covering:

- Authentication-required behavior and successful login.
- User-filtered conversation listing and cross-user read/send/delete rejection.
- Owner deletion cascading through messages, citations, and generation metadata.
- Message persistence and invalid role rejection by the database constraint.
- Citation snapshot and generation metadata persistence from the synthetic mock.
- Safe failure persistence when the RAG client times out.
- CSRF rejection for a state-changing request without a token.
- Mock response validation and explicit synthetic status.
- HTTP response parsing, sanitized citation URL persistence, typed timeout/error handling, malformed citations, and no credential leakage into errors/browser output.

Verified on 2026-11-17 in the project virtual environment:

```powershell
$env:DJANGO_DB_ENGINE = "sqlite"
$env:DJANGO_SQLITE_PATH = ":memory:"
cd E:\RAG_Project\django_app
..\.venv\Scripts\python.exe manage.py test accounts conversations chat rag_client --verbosity 1
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe -m compileall -q .
```

Results at this foundation milestone: **15 Django tests passed** on in-memory SQLite; migration checks, the SQLite-configured Django system check, `compileall`, and `pip check` passed. A native Windows PostgreSQL check could not load the Psycopg binary DLL because of the host's Application Control policy. This native Windows limitation was resolved for the Docker integration milestone using the Linux Psycopg wheel: migrations and all 15 tests have now passed against the existing PostgreSQL container. See `docs/docker_django_postgres_implementation_report.md` for the Docker build, migration, PostgreSQL test, and resource-preservation record. The existing RAG test suite and live RAG readiness were not run for the Django-only milestone.

## Changed files

- Root `requirements.txt` — Django and Psycopg pins.
- `django_app/manage.py`, `django_app/config/{settings,urls,wsgi,asgi}.py` — project and environment/database/security configuration.
- `django_app/accounts/{apps,urls,views}.py` — session login/logout integration.
- `django_app/conversations/{apps,models,urls,views}.py` and `migrations/0001_initial.py` — persistence schema and owner-scoped conversation operations.
- `django_app/chat/{apps,forms,views}.py` — bounded message validation and RAG orchestration.
- `django_app/rag_client/{apps,client}.py` — HTTP contract, typed errors, response validation, synthetic adapter.
- `django_app/templates/{base.html,accounts/login.html,conversations/list.html,conversations/detail.html}` — server-rendered UI with CSRF forms and a synthetic-mode notice.
- `django_app/conversations/tests.py`, `django_app/rag_client/tests.py` — foundation tests.
- `docs/django_application_foundation_report.md` — this report.

No existing RAG source code, tests, approvals, index manifests, Qdrant collections/volumes, or raw documents were modified. No ingestion or indexing was started.

## Remaining integration work

1. Define production backup, retention, and deletion policies for the Django PostgreSQL database.
2. Create/manage real Django users and configure production secret, host, HTTPS, cookie, CSRF-origin and process settings.
3. Keep `RAG_ADAPTER=mock` for UI development. Before using `http`, complete source/document review and create a reviewed index; the present FastAPI API will continue to reject `operator_authorized_unreviewed`.
4. Replace the current shared-token/static-principal API boundary with trusted user/tenant identity propagation before multi-user authorization. Do not accept scope from browser data.
5. Define history semantics. The current FastAPI query endpoint is stateless and Django history is not sent to it.
6. Decide whether model/index version labels should be returned by FastAPI and extend its response contract in a separate, explicitly authorized task.
7. Add integration tests against the FastAPI API when an approved index becomes available. Preserve the current citation/claim verification behavior.
8. Add rate limits and inference concurrency/admission controls before exposing the app to multiple users. Do not implement raw token streaming; any later stream must preserve verified-answer semantics.

There is no public sign-up, password reset, edit-message endpoint, conversation history API separate from the HTML detail page, WebSocket/SSE endpoint, or multi-user RAG identity bridge in this milestone.
