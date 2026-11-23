# Generation, verification and citation production plan

## Live configuration

`configs/generation.json`: Ollama `qwen3.5:4b`, Q4_K_M, configured 8,192 context, 1,024 output reservation, 512 input safety reserve, temperature 0, thinking disabled, one configured retry and 120-second model request timeout. `nomic-embed-text:v1.5` is 768 dimensions. The same local Qwen family is used for generation and claim verification. The configured budget uses conservative estimation, not the exact Qwen tokenizer.

## Implemented controls

`src/rag_pipeline/generation/ollama.py` orchestrates generation and claim checks. `citation_validation.py` parses citation syntax, checks IDs/mappings and claim coverage. `claim_verifier.py` requires structured claim outcomes and fails closed on incomplete/malformed verifier output. `claim_consistency.py` has narrow contradiction/version rules. `src/rag_pipeline/service.py` suppresses invalid generated output and records stage diagnostics without passage text in ordinary API responses. Citations are reconstructed from admitted context. These controls reduce risk; they do not prove factual correctness or semantic entailment.

## Gaps and recommendations

- Separate model family does not guarantee independent truth; benchmark deterministic claim-to-evidence heuristics and candidate local verifier models offline before changing default.
- Version conflict detection and broad contradiction detection are incomplete.
- Citation navigation often points to source roots; improve source metadata only through verified canonical page/heading/PDF-page provenance.
- Preserve exact failure classification internally while keeping user errors safe. User-facing statuses should distinguish insufficient/OOD, unauthorized, invalid citation, verifier rejection, generation failure and dependency failure.
- Version prompts/config with digest; model replacement requires a fixed human-reviewed evaluation set and rollback plan.
- Measure full claim/citation entailment with human labels; LLM-as-judge remains a separate automated signal.

## Acceptance boundary

No model, prompt, token window, output budget, citation threshold or verifier rule was changed. No new RAG model call was introduced. The current 30-query evaluation remains heuristic and shows variable outcomes; production quality gate is blocked pending reviewed labels and human acceptance criteria.
