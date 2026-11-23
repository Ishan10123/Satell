# Phase 5 browser and live evaluation report

## Interactive workflow

Executed with installed Google Chrome through Playwright at `http://127.0.0.1:8001` using a temporary account, removed at the end. The user database returned to its original counts afterward.

| Scenario | Result |
|---|---|
| Unauthenticated application load | HTTP 200 login page; protected route redirected to login |
| Invalid and valid login | Invalid rejected; valid reached workspace |
| Conversation creation | Passed |
| Real RAG answer | Completed, one citation, real/non-synthetic |
| Citation and verification display | Passed |
| Conversation history/reopen | Passed |
| Mobile viewport/navigation | Passed; no horizontal overflow |
| Missing-CSRF POST | HTTP 403 as expected |
| Service-secret question | No secret disclosed; safe refusal/fail-closed status displayed |
| Logout/protected route | Passed |
| Browser credential check | RAG bearer token absent from browser page |

The safe refusal said that the local academic-demo sources could not answer the secret question. The status was `failed` at the verifier boundary and the generic safe answer was shown; the test does not treat this as a grounded RAG answer.

The browser emitted one expected console error from the deliberate CSRF 403 and no page JavaScript errors. Headless Chrome did not provide clipboard permissions, so copy was not verified end to end.

## 20-query browser evaluation

The first 20 questions in `docs/phase4_evaluation_questions.json` were run sequentially through the browser form. The evaluation labels are topic/source heuristics, not human relevance judgments. The artifact `live_evaluation_results.json` records query IDs, categories, outcome, citations, browser latency, Django persistence timing, and bounded GPU/Docker samples; it does not retain model answers.

| Outcome | Count |
|---|---:|
| Verified | 12 |
| Partially verified | 4 |
| Safely abstained | 1 |
| Failed closed | 3 |
| Responses with citations | 16 of 20 |
| Completed/persisted assistant responses | 20 of 20 |

Browser end-to-end duration: minimum 779 ms, p50 6,303 ms, p95 9,824 ms, maximum 15,101 ms. The very fast abstention is included. The run was sequential and used the real Django HTTP adapter, FastAPI, Qdrant, Ollama, verifier, citation validation, and PostgreSQL persistence. This small evaluation does not establish general factual accuracy.

## Operational note

An initial evaluation harness version waited for the assistant-card count to increase. At 50 rendered messages the page's history pagination kept that count constant, so the harness timed out despite successful previous requests. The run was discarded. The corrected harness waits for the form navigation and final message status; the reported 20-query run uses the corrected implementation.
