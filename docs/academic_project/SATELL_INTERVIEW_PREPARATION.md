# Interview preparation

## 90-second project explanation

Satell is a local-first documentation chat application. Django owns browser sessions, users, conversations and citation snapshots. It calls a private FastAPI service, which applies a signed, explicitly limited local-demo allowlist before dense retrieval from Qdrant. Evidence is assembled under a token budget, a local Ollama model generates an answer, and separate claim and citation checks can reject unsupported output. The system is useful for supervised academic demonstration; it is not production-cleared: source licenses remain pending and the production manifest is still unreviewed.

## Explain the architecture in order

1. Browser requests are authenticated and CSRF protected by Django.
2. Django scopes every conversation lookup to the current user, persists the user message and calls RAG server-to-server.
3. FastAPI authenticates the service request, validates size/schema and checks readiness.
4. The RAG service validates the local-demo registry, embeds the query and filters Qdrant candidates by scope and metadata.
5. Context assembly applies evidence admission and budgets; Ollama returns generated text.
6. Claim verification and citation validation determine whether the response is verified, partial, rejected or abstained.
7. Django stores response/citation metadata and returns the page.

## Explain the hard trade-offs

- Dense retrieval is the active baseline; hybrid search/reranking are not enabled because benchmark improvement was not decisive against latency and precision trade-offs.
- Verification is a risk reduction layer, not a proof: verifier and generator use the same local model family.
- Local inference improves data locality and avoids paid APIs but constrains latency and concurrency to laptop hardware.
- Local demo authorization enables controlled testing while legal and production approvals remain pending.
- Rejection is a feature when evidence/citations fail validation, but over-rejection and incomplete evidence reduce usability.

## Difficult questions: answer honestly

**Can you guarantee the answer is correct?** No. The system checks evidence and citations and abstains on failures, but retrieved sources may be incomplete, stale or ambiguous, and the verifier can err.

**Is it production ready?** No. There are production-grade components, but unresolved legal authorization, missing production document registry, no independent security assessment, limited operations/DR, and unproven capacity prevent that claim.

**What is your strongest evidence?** Current local health/readiness, real non-synthetic Django-to-FastAPI query, persistent citation behavior, regression suites, browser E2E, and preserved Qdrant/DB counts. Each proves a bounded property only.

**What is the weakest technical layer?** Quality assurance at semantic level: small evaluations, incomplete contradiction/version handling and verifier independence. Operationally, one synchronous worker and laptop inference constrain capacity.

**Why separate citation validation from generation?** Model-generated references are untrusted. A deterministic validator can verify that IDs exist and map to admitted evidence; it cannot prove the text is entailed.

**What would you do next?** Resolve human license decisions and complete production authorization first; then define a production target, threat model, SBOM/security review, backup/restore, monitoring/SLO and isolated reliability testing before release work.

## Preparation drill

For each answer, be ready to state the source code/config file, the test or runtime evidence, the limitation, and whether a statement is current or proposed. Use the question bank and demonstration guide; never present a benchmark-only component as active.
