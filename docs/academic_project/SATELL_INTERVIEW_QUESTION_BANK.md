# Satell interview question bank (160 Q&A)

Answers are deliberately scoped to the implementation at the 2026-11-19 snapshot. “Proposed” answers describe future design, not existing features.

## Project overview

1. **What is Satell?** A local-first documentation chat workspace with Django UI and a private FastAPI RAG service; it is a supervised academic demo, not production-cleared.
2. **What problem does it solve?** It searches a documentation corpus and returns model answers with mapped citations and post-generation checks.
3. **What makes it more than a basic RAG demo?** It includes ingestion provenance, authorization gates, persistent conversations, citation validation, claim verification, tests and operational reports.
4. **What is the main trust boundary?** Browser-to-Django identity, Django-to-FastAPI service authentication, then FastAPI authorization before retrieval.
5. **What is the active answer path?** Django → authenticated FastAPI → signed demo scope → dense Qdrant → bounded context → Ollama → verifier/citation validator → Django persistence.
6. **What is deliberately not active?** BM25/RRF hybrid fusion and ONNX reranking are implemented or benchmarked but inactive in the live dense strategy.
7. **What is the current corpus state?** Snapshot: 6,565 indexed documents, 58,856 chunks/points, with production authorization still unreviewed.
8. **What is the biggest unresolved blocker?** Human source/document license review and a reviewed production authorization manifest.
9. **What does “local-first” mean here?** Data and inference run in local Docker/host services without paid external model APIs in the query path.
10. **What would you improve first?** Close legal authorization and establish production scope, then evidence-backed security/operations readiness.

## Python and service design

11. **Why Python?** The project benefits from a mature ML, parsing, HTTP and web ecosystem; runtime behavior is verified in the Python 3.13 environment.
12. **How is modularity used?** Parsing, retrieval, authorization, generation, verification and API concerns are kept in separate packages.
13. **How do you handle malformed inputs?** Typed request validation and parser-specific safe failure paths reject invalid inputs rather than inventing structure.
14. **Why use type/schema validation?** It catches invalid requests at boundaries and documents the service contract.
15. **Does Python guarantee concurrency here?** No. Django’s current synchronous worker serializes long requests; async-capable packages do not make the request path concurrent automatically.
16. **How would you add a new parser?** Add a registry-backed extractor with size/depth limits, provenance-preserving output and malformed-input tests.
17. **Why not dynamically execute documents?** Input documents are untrusted; parsing should be data-only and never execute source content.
18. **How are exceptions exposed?** Typed application errors become bounded HTTP errors; internal secrets and raw exception details should not reach users.
19. **Is the dependency graph fully locked?** No. Direct requirements are pinned, but a complete transitive lock/SBOM is not established.
20. **What is a Python risk in production?** Unbounded work, dependency drift and accidental sensitive logging; constrain resources and maintain a scanned lock.

## Django

21. **Why Django?** It supplies authentication, sessions, CSRF, ORM, migrations and admin for the application layer.
22. **What data does Django own?** Users, conversations, messages, citation snapshots and generation metadata.
23. **How is conversation ownership enforced?** Views query conversations through the authenticated user’s relation and apply ownership-scoped lookup.
24. **What prevents CSRF?** Django middleware and form tokens; the browser uses the same loopback origin.
25. **Does Django call Qdrant?** No. It calls FastAPI through the RAG HTTP client.
26. **Does Django call Ollama?** No. Ollama is behind FastAPI.
27. **Where is the RAG token?** Server-side environment/configuration, never exposed to browser JavaScript.
28. **Are conversation follow-ups contextual?** Not fully; chat history is persisted but is not sent as dialogue context to RAG, so the query is standalone.
29. **Does the UI stream tokens?** No. It waits for a complete structured response.
30. **How would Django scale?** Add measured worker capacity and database pooling, but inference queuing/backpressure must be designed before increasing workers.

## FastAPI and HTTP contracts

31. **Why FastAPI?** It provides a typed HTTP boundary and Pydantic request validation while keeping the RAG engine independent of Django.
32. **How is API access authenticated?** A bearer service token is required for protected query/readiness calls.
33. **What is `/health`?** Liveness: process responds; it does not establish index or dependency readiness.
34. **What is `/ready`?** Authenticated checks for required index/registry and model/vector dependencies.
35. **What is the query limit?** Request query is bounded to 5,000 characters, top-k to 1–20, with a 64 KiB body cap.
36. **Is rate limiting distributed?** No. The current fixed-window limit is process-local.
37. **Does FastAPI publish a host port?** Not in the observed Compose setup; Django reaches it on a private network.
38. **Are endpoints asynchronous?** The actual handlers are synchronous; installed async libraries do not imply async execution.
39. **How are timeouts handled?** HTTP/model calls use configured bounded timeouts and errors propagate as safe failures; end-to-end deadline propagation is not a complete distributed cancellation system.
40. **What API docs are exposed?** OpenAPI/docs endpoints are disabled in the observed service configuration.

## PostgreSQL and persistence

41. **Why PostgreSQL?** Relational constraints and transactions fit user-owned conversations and messages.
42. **Why not SQLite in production?** SQLite is useful for tests; PostgreSQL better supports concurrent multi-user writes and operational deployment.
43. **What does a citation snapshot store?** Citation/source/document/chunk IDs and sanitized title/page/section/reference metadata.
44. **Are raw evidence passages stored in Django?** They are not intended to be; citations preserve references and identifiers.
45. **What are foreign keys for?** Enforce message-to-conversation and citation-to-message relationships and defined cascade behavior.
46. **Are backups proven?** A recovery guide exists, but a current successful restore drill and RPO/RTO are not established.
47. **Can a failed RAG call leave a user message?** Persistence follows the view’s transaction/error logic; inspect the current view when changing behavior and test both outcomes.
48. **How prevent cross-user reads?** Owner-scoped queryset access, with tests for unauthorized access.
49. **Is DB pooling configured?** Do not assume from the driver; current deployment uses a small local setup and has no demonstrated scale tuning.
50. **What must production add?** Backup/restore proof, retention policy, monitoring, migration/rollback process and capacity validation.

## Qdrant and storage

51. **Why Qdrant?** It supplies vector similarity retrieval and payload filtering for the embedding corpus.
52. **What is a point?** A vector, point ID and payload representing an indexed chunk.
53. **What is `rag_docs_v2`?** The existing collection holding 58,856 points at the snapshot.
54. **Is Qdrant public?** It is loopback-published for local operator access and private on Docker networking in the inspected deployment.
55. **Are points rebuilt for this documentation task?** No. Existing data is preserved.
56. **What filters apply?** Tenant/principal/source/license and authorization-derived document scope are applied in retrieval and checked during context assembly.
57. **Is Qdrant authentication proven?** No independent Qdrant credential boundary was demonstrated; isolation relies on network controls in this local deployment.
58. **How should Qdrant be backed up?** Use a tested snapshot/restore procedure and verify point counts/collection metadata after restore.
59. **Why not put vectors in PostgreSQL?** Qdrant separates vector workloads and offers purpose-built search; pgvector is a valid alternative with fewer services.
60. **What is the Qdrant failure behavior?** Readiness/query should fail safely; unit fault tests exist, but shared-service outage/recovery was not injected.

## RAG and embeddings

61. **What does RAG do?** Retrieves external evidence and conditions generation on it rather than relying only on model parameters.
62. **Which embedding model is used?** `nomic-embed-text:v1.5`, with 768 dimensions.
63. **Can the embedding model be changed in place?** No; vector dimensions and semantic space require a controlled re-embedding/migration plan.
64. **What is chunking for?** It bounds evidence units for retrieval and model context; chunk size/overlap affect recall and context duplication.
65. **How is document identity handled?** Canonical IDs represent content/path identity while provenance records preserve source/path distinctions.
66. **What is a retrieval candidate?** A matching point returned by vector search before context admission and generation.
67. **What is context assembly?** The stage that filters candidates, deduplicates and fits evidence under configured token budget.
68. **Does retrieval guarantee relevance?** No; it ranks by similarity and metadata filters, with quality requiring evaluation.
69. **Why keep provenance?** It lets a result trace back to source, document, path, hash and chunk.
70. **What happens if no useful evidence exists?** The system may abstain or reject rather than fabricate a sourced answer.

## Retrieval, ranking, evaluation

71. **What retrieval strategy is live?** Dense Qdrant search.
72. **Is BM25 active?** No; SQLite FTS5 BM25 is implemented but inactive in the live path.
73. **What is RRF?** A rank-based method that combines lists without requiring calibrated raw scores.
74. **Why benchmark RRF?** To test whether lexical and dense candidates improve ranking on project queries.
75. **Is reranking active?** No. The local ONNX cross-encoder was benchmarked but is not enabled for live queries.
76. **Why not enable the best Recall@8 result?** The benchmark was small and heuristic; latency/precision trade-offs did not justify changing the active path.
77. **What is Recall@k?** The fraction of known relevant items retrieved within the top k.
78. **What is MRR?** The reciprocal rank of the first relevant result, averaged across queries.
79. **What is nDCG?** A normalized ranking metric that accounts for graded relevance and position.
80. **What is missing from evaluation?** Larger expert-labeled datasets, query categories, confidence intervals and ongoing regression thresholds.

## Generation and local models

81. **Which generation model is used?** Local `qwen3.5:4b` in the observed configuration.
82. **Why local inference?** Data locality and no paid query API, at the cost of laptop-dependent throughput and capacity.
83. **What context budget is configured?** 8,192 context tokens, 1,024 output reservation and 512 safety reserve.
84. **Why not increase context?** No realistic benchmark evidence justifies it; larger context costs memory and may worsen latency.
85. **What is temperature?** A sampling setting; current configuration is deterministic/low-variance at temperature zero.
86. **Does generation see conversation history?** Not as complete dialogue context in the current request path.
87. **What if Ollama is unavailable?** Readiness or the query fails; do not silently substitute a mock response.
88. **How is model output constrained?** Prompt instructions, structured parsing and downstream verifier/citation checks; output remains untrusted.
89. **Can the same model verify itself?** It can, but shared model biases limit independence; this is a known risk.
90. **What is the hardware bottleneck?** Laptop GPU and one synchronous service worker constrain throughput; benchmark on target hardware.

## Verification and citation

91. **Why verify claims after generation?** To check generated statements against retrieved evidence and reject unsupported output.
92. **What does a valid citation prove?** That a citation ID maps to an admitted source chunk, not that the claim is entailed or true.
93. **Why separate citation validation?** Model text cannot be trusted to invent a valid mapping; deterministic checks enforce IDs and syntax.
94. **What happens with an unknown citation ID?** Validation fails closed or rejects the response.
95. **Can verification guarantee correctness?** No. The verifier can misread, omit contradictions or share model biases.
96. **What is partial verification?** Some claims pass evidence checks while others do not; status must remain explicit.
97. **What is safe abstention?** Returning no asserted answer when support or validation is insufficient.
98. **How handle version conflicts?** Current checks may qualify or reject; broad historical/current consistency remains incomplete.
99. **What would improve contradiction detection?** Deterministic pairwise checks for explicit numeric/temporal conflicts plus conservative rejection and evaluation; an LLM checker alone is insufficient.
100. **Why not show rejected raw generations to users?** It could expose unverified claims; controlled diagnostics are separate and restricted.

## Security and authorization

101. **Authentication vs authorization?** Authentication establishes identity; authorization determines allowed resources/actions.
102. **What is CSRF?** A browser attack that abuses an authenticated session; Django tokens/middleware defend form submissions.
103. **What is XSS?** Script injection into a page; output escaping and safe templates are important, but a full independent audit remains needed.
104. **How does the service token stay private?** It is used server-side by Django and not included in browser responses.
105. **What does fail-closed mean?** Missing or invalid authorization state denies access rather than widening allowed documents.
106. **What is a signed registry?** Integrity-protected policy data; signature does not establish legality or truth.
107. **What is the production authorization state?** `operator_authorized_unreviewed`, so production authorization remains blocked.
108. **What is local demo authorization?** A separate explicit scope for supervised academic evaluation, not legal approval.
109. **Are the 14 sources legally approved?** No; their source decisions remain pending review.
110. **How are prompt injections handled?** Retrieved text is treated as untrusted and layered checks are applied; prevention is not guaranteed.

## Docker and deployment

111. **Why Docker?** It packages services and makes local wiring repeatable while keeping components separated.
112. **Why Compose?** It declares the app services, networks, dependencies and runtime config for local execution.
113. **What is exposed to host?** Django on loopback port 8001; PostgreSQL and Qdrant on loopback; FastAPI is private-only.
114. **Where does Ollama run?** On the Windows host, reached from FastAPI through configured host connectivity.
115. **Why Gunicorn?** It provides a WSGI production-style process manager for Django.
116. **Why WhiteNoise?** It serves collected static files with the Django app in this small deployment.
117. **Can this compose file bootstrap a clean machine?** Not proven; it reuses external data/network and local host model dependencies.
118. **What is wrong with mutable tags?** Rebuilds may pull different bits, harming reproducibility and supply-chain review.
119. **How should deployment be improved?** Pin image digests, create SBOM, manage secrets, validate restore and define rollback.
120. **What must never be run casually?** `docker compose down -v`, volume resets, collection deletion, or corpus reindex commands.

## Testing and quality

121. **Why unittest?** It is built into Python and used by the RAG regression suite; Django provides `TestCase`.
122. **Is pytest installed?** Not in the inspected environment; tests should run with documented unittest/Django commands.
123. **What does a synthetic test prove?** Contract behavior with controlled fixtures, not real-corpus quality.
124. **What does a browser test prove?** The exercised browser flow worked under that environment, not full accessibility or production security.
125. **What does a health check prove?** A limited process/dependency condition, not factual correctness or legal clearance.
126. **How many queries were in the latest live quality sample?** Thirty browser queries, with 13 verified, 6 partial, 4 abstentions and 7 failed/rejected; expectations were heuristic and not expert reviewed. An earlier 20-query sample had different outcomes.
127. **Why is that small?** It is an engineering diagnostic, not a statistically robust user evaluation.
128. **What is a regression test for?** Preventing a previously fixed behavior from breaking again under a controlled case.
129. **Why separate unit/integration/E2E?** They validate different boundaries and have different setup, fidelity and failure diagnosis.
130. **What is missing in CI?** A verified CI pipeline and gates are not established in this assessment.

## Performance and reliability

131. **What is measured query p50?** 4.768 seconds in the latest 30-query browser run; the earlier 20-query run measured 6.253 seconds. These are separate small local samples.
132. **What is measured p95?** 6.485 seconds in the latest 30-query sample and 9.755 seconds in the earlier 20-query sample; neither is a contractual SLO.
133. **Why is generation slow?** Local model inference and verification dominate relative to vector retrieval.
134. **What concurrency is supported?** No production concurrency target is established; a single sync worker queues long requests.
135. **What happens under burst load?** Requests may queue and latency rises; sustained load and overload controls need testing.
136. **Are outage recovery paths verified?** Fault-unit tests exist; real shared dependency outages/recovery were not injected.
137. **What is an SLO?** A measurable reliability/latency target agreed for a service and time window.
138. **What is an RPO?** Maximum acceptable data loss measured in time.
139. **What is an RTO?** Target time to restore service after a failure.
140. **How would you handle overload?** Add bounded queueing, deadlines, admission control and load shedding after measurements.

## System design and scenario questions

141. **How scale to 100 users?** Define workloads/SLO, benchmark model capacity, then add bounded worker/queue capacity and monitoring; do not just add web workers.
142. **How scale to 1,000 concurrent users?** Separate web and inference pools, queue GPU work, shard/replicate retrieval carefully, implement distributed rate limits and load test.
143. **What if Qdrant is down?** Query readiness/failure should prevent pretending an answer exists; return a safe service error and recover without reset.
144. **What if a user requests another user’s conversation?** Owner-scoped lookup should reject/not reveal it; regression tests cover cross-user access.
145. **What if a document contains malicious instructions?** Treat it as untrusted evidence, apply injection safeguards and verify output; residual model risk remains.
146. **What if verifier JSON is malformed?** Reject or fail closed; never infer approval from partial output.
147. **What if citation points to unrelated evidence?** ID mapping can validate identity but semantic entailment may fail; verifier/quality checks should reject, and tests need coverage.
148. **What if the model runs out of VRAM?** Generation can fail or time out; surface safe error, preserve data, and adjust capacity only after measurements.
149. **Why trust this answer?** Trust is bounded: inspect citations, source provenance and verification status; no correctness guarantee is offered.
150. **What is the most serious weakness?** Legal production authorization is unresolved; technically, small evaluation and single-worker local capacity are also material.

## Additional interviewer follow-ups

151. **Why is local demo authorization separate from licensing?** It scopes an operator-controlled experiment, whereas license decisions are human legal judgments.
152. **What does a registry HMAC protect?** Detects unauthorized changes if key custody is sound; it does not protect a compromised key or validate content truth.
153. **Why can’t Qdrant point count prove corpus completeness?** Counts only show stored points; they do not show that every intended document is present, relevant or authorized.
154. **What is the risk of deduplicating identical content?** Provenance can be lost unless canonical content and every source/path relationship are preserved.
155. **Why keep document-level decisions?** A source may contain exceptions, third-party assets or individual paper licenses that differ from source-level terms.
156. **What is a token safety reserve?** Space held back for estimation error and prompt overhead; it reduces overflow risk but does not make tokenizer estimates exact.
157. **Why preserve abstention?** A low-confidence unsupported answer is more harmful than a clear refusal in a source-grounded assistant.
158. **What does “ready” mean for the demo?** The local supervised flow can run; it does not imply legal, public, private or commercial readiness.
159. **How handle a source correction?** Preserve provenance, update through reviewed ingestion and a controlled index migration, then validate counts and citations.
160. **What is the responsible next milestone?** Resolve human authorization and production scope, then gather security, recovery and capacity evidence before release implementation.
