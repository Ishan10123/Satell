# Satell data flow and request lifecycle

## Browser query, in order

1. An unauthenticated `GET /` is redirected to Django login. Login uses Django forms, password validation, session auth and CSRF middleware.
2. Authenticated browser requests enter Django `conversations.urls`; the request is an HTML form POST, not a JSON SPA API.
3. `chat.views.message_create` requires login and POST, then queries `Conversation.objects.filter(user=request.user)` before accepting the conversation UUID. A foreign user's UUID returns 404.
4. `MessageForm` strips and validates nonempty text with 5,000-character max. The Django `DATA_UPLOAD_MAX_MEMORY_SIZE` is 65,536 bytes.
5. In one database transaction, Django writes the user message and a pending assistant record, updates the conversation timestamp, and commits. It then makes the RAG call outside that transaction, so a long model request does not hold the transaction open.
6. `rag_client.get_rag_client()` selects the server-configured adapter. Current Compose sets `RAG_ADAPTER=http`; the browser never receives the bearer credential. `FastAPIRAGClient.query` sends query/top-k plus `X-Correlation-ID` and bearer auth, with configured timeout and no retry.
7. FastAPI middleware assigns/preserves a bounded correlation ID and checks request content length. Pydantic rejects extra request fields, blank/oversize query and top-k outside 1–20. Errors are generic and do not echo prompt text.
8. `HTTPBearer` authenticates. FastAPI uses server-side tenant/principal and does not accept scope from browser payload.
9. For local demo, FastAPI verifies the manifest, category policy, source registry and document registry HMACs and inventory binding. Otherwise production requires reviewed source+document manifest authorization. `/ready` performs these checks plus dependency health.
10. `DenseRetriever` obtains an Ollama embedding. The current request path calls Qdrant dense cosine query with source IDs, tenant ID, ACL principal and operator-authorization status. The local demo requires documentation source/category and the 6,458-document allowlist; papers are excluded.
11. `ContextAssembler` rechecks authorization and document identity/hash, drops duplicates/invalid chunks, preserves passage boundaries, builds citations, escapes document text inside explicit untrusted-data delimiters and enforces a prompt-aware budget.
12. `OllamaGenerator` sends one non-streaming chat request with the system prompt, query and assembled references. Retrieved passages are explicitly untrusted. The model uses temperature 0, `think=false`, configured context/output budgets and timeout.
13. Claim extraction identifies factual sentences/bullets. Citation validation verifies marker syntax, mapped IDs and coverage. The claim verifier asks the local Qwen model for one structured verdict per claim. Deterministic consistency checks apply narrow version/contradiction rules.
14. If validation fails, no unvalidated answer is returned. Depending on the error, the service abstains or returns a generic 503 classification. Insufficient context and incomplete multi-source comparison can abstain before generation.
15. FastAPI returns answer, citation metadata, request ID, strategy, timings, verification status and bounded diagnostics. `synthetic=false` for real responses.
16. Django validates the response shape and citation metadata. In a second transaction it persists the assistant response, citation snapshots and generation metadata, then redirects to the conversation page.
17. The Django template escapes text. Client-side Markdown rendering builds DOM nodes; citations show title, section/pages and sanitized source link. Internal source/document/chunk IDs remain stored in PostgreSQL but are not displayed/copied. There is no token-by-token stream.

## Persistence/failure boundaries

- If the RAG HTTP client fails, Django marks the assistant message `failed`, stores only safe failure metadata, displays a generic message and preserves the user's original question.
- If the Django process is killed after the first transaction but before the second, the pending assistant row can remain. There is no background sweeper/retry queue.
- If the user retries manually, a new message/correlation ID is generated; no idempotency key deduplicates submissions.
- PostgreSQL stores the question, answer, citation metadata, diagnostic IDs and timings. It does not store the assembled evidence passages in normal operation. Opt-in FastAPI evaluation artifacts can store question/raw answer/claims and must be protected.
- Conversation history is not sent to the RAG endpoint. Follow-up questions do not have conversational context except what the user repeats.

## FastAPI endpoints

| Method/path | Auth | Request / output | Errors and notes |
|---|---|---|---|
| `GET /health` | No | Liveness JSON | Does not prove index/model readiness. |
| `GET /ready` | Bearer | Readiness JSON | 503 if manifest/registry/model/Qdrant/embedding checks fail. |
| `POST /v1/query` | Bearer | `QueryRequest(query: str 1..5000, top_k: int 1..20)` → `QueryResponse` | 400, 401, 411, 413, 422, 429, 503. 64 KiB body boundary. Correlation headers. |
| OpenAPI/docs | Disabled | Not served | `docs_url`, `redoc_url`, and `openapi_url` are `None`. |

`QueryResponse` in `src/rag_pipeline/api/app.py` contains `answer: str`, `citations: tuple[dict, ...]`, `request_id: str`, `retrieval_mode: str`, `timings_ms: dict[str,float]`, `verification_status` (`verified`, `partially_verified`, `abstained`, `failed`, or `not_reported`), bounded `diagnostics: dict`, and `synthetic: bool`. The request uses `X-Correlation-ID`; FastAPI echoes the accepted/generated ID as both `X-Request-ID` and `X-Correlation-ID`. The Django HTTP client validates the JSON shape and citation fields in `django_app/rag_client/client.py`; it maps connection, timeout, HTTP, oversized-input and malformed-response errors into typed `RAGClientError` subclasses. The client makes one synchronous attempt (no retry). Django stores safe failure codes/status in generation metadata and displays a generic service failure; successful responses persist citations and stage metadata. Raw HTTP error bodies and request prompts are not shown to users.

## Django endpoints

| Method/path | Access and validation | Effect / failure boundary |
|---|---|---|
| `GET /` | Login required; anonymous requests redirect to login | Owner-scoped conversation dashboard. |
| `GET/POST /accounts/login/` | Public page; POST uses Django CSRF and auth | Login; invalid credentials do not authenticate. |
| `POST /accounts/logout/` | Authenticated + CSRF | Invalidates the session. |
| `GET/POST /accounts/password-reset/` | Public; POST validates/throttles and returns generic result | Starts recovery only for resolved registered accounts; external SMTP delivery is currently unavailable. |
| `GET /accounts/password-reset/sent/` | Public | Generic confirmation page. |
| `GET/POST /accounts/password-reset/<uidb64>/<token>/` | Public opaque expiring token; POST uses CSRF and Django password validators | One-time password change; invalid/expired tokens fail through Django's reset flow. |
| `GET /accounts/password-reset/complete/` | Public | Completion page. |
| `POST /conversations/new/` | Authenticated + CSRF | Creates a conversation for `request.user`. |
| `GET /conversations/<uuid>/` | Authenticated; owner-scoped | Paginated conversation, messages and citation snapshots; non-owner gets 404. |
| `POST /conversations/<uuid>/messages/` | Owner + CSRF + non-locked conversation | Persists user prompt, calls server-side RAG client, persists assistant response/citations/metadata. |
| `POST /conversations/<uuid>/delete/` | Owner + CSRF; locked conversations cannot be deleted | Deletes owned conversation and cascaded dependent records. |
| `POST /conversations/<uuid>/rename/` | Owner + CSRF; title length validated | Changes title and protects manual title from auto-replacement. |
| `POST /conversations/<uuid>/lock/`, `POST .../unlock/` | Owner + CSRF | Toggles application read-only state. |
| `GET /conversations/<uuid>/export/<format>/` | Owner-scoped; format allowlisted | Downloads Markdown, text or JSON without internal prompts/credentials. |
| `POST /conversations/<uuid>/share/`, `POST .../share/revoke/` | Owner + CSRF | Creates/revokes optional read-only capability link; token stored as a hash. |
| `GET /shared/<token>/` | Unauthenticated capability URL; rate-limited, no-store/noindex | Reads only the selected shared conversation until expiry/revocation. Anyone holding the link can read it. |
| `/admin/` | Django staff/superuser authorization; normal CSRF | Django administration. |

Protected routes generally redirect anonymous users to authentication; CSRF failure returns 403; method restrictions return 405; cross-owner lookups return 404. Form/input errors remain within the view/form contract. Exact RAG failure classes are mapped by `django_app/rag_client/client.py` and the chat view to safe user-visible outcomes. This is not a public JSON API; Django owns server-rendered pages and form POSTs.

These route definitions were inspected in `django_app/accounts/urls.py`, `django_app/conversations/urls.py` and `django_app/config/urls.py`.
