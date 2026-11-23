# Satell Phase 3 Live Performance Evaluation

Date: 2026-11-18

## Method

Twenty representative prompts were posted through the running Django HTTP application using a disposable account. They traversed Django, the authenticated FastAPI HTTP adapter, dense Qdrant retrieval, context assembly, Ollama, citation validation and (where eligible) claim verification. No mock responses were included. The complete per-request measurement record is [phase3_performance_samples.json](phase3_performance_samples.json).

End-to-end time measures the HTTP workflow through the redirected and rendered conversation detail page. The Django RAG request timing is instrumented around the HTTP client call. Django overhead and FastAPI overhead are residual estimates, not isolated profiler measurements; the FastAPI residual includes network/client parsing and request setup. Stage timings are present only when that stage ran.

## Latency (milliseconds)

Percentiles use linear interpolation over the 20 samples.

| Stage | n | Min | p50 | p95 | Max |
|---|---:|---:|---:|---:|---:|
| End-to-end Django HTTP response | 20 | 553.7 | 6,685.9 | 13,621.0 | 14,855.1 |
| Django RAG HTTP call | 20 | 436.5 | 6,574.5 | 13,498.6 | 14,736.6 |
| Django overhead estimate | 20 | 108.7 | 115.8 | 123.4 | 124.7 |
| FastAPI/request/network residual estimate | 20 | 314.1 | 328.4 | 375.8 | 409.5 |
| Embedding | 20 | 22.7 | 60.3 | 220.8 | 2,663.5 |
| Dense Qdrant search | 20 | 29.9 | 46.5 | 67.2 | 69.8 |
| Context assembly | 20 | 0.7 | 0.9 | 1.3 | 1.3 |
| Ollama answer generation | 19 | 2,033.4 | 3,773.6 | 7,181.6 | 7,687.9 |
| Claim verification | 11 | 2,747.8 | 3,832.4 | 6,139.8 | 7,130.5 |

Generation and verification are conditional stages. One embedding call was a 2.66 second outlier; it warrants continued observation but is not enough evidence to change batching or model settings.

## Outcomes and pipeline configuration

- 20/20 HTTP messages completed; retrieval strategy was `dense` for all 20.
- 11 responses had citations: 8 fully verified and 3 partially verified.
- 6 were rejected for uncited claims, 2 failed citation validation, and 1 comparison question safely abstained because evidence spanning the requested sources was insufficient.
- Citation validation passed on 11, rejected on 8, and was not applicable on the abstention. Claim verification was not run on the 9 rejected/abstained requests.
- The reranker was disabled for every request. BM25 and RRF were not active. Context assembly ran for every query; included chunk count ranged from 2 to 7. Retrieved candidates excluded by the configured context budget are recorded in the JSON artifact.

This is a diagnostic set without labeled relevance judgments; it does not establish retrieval recall, answer accuracy, or general performance SLOs.

## Machine and model configuration

- CPU: Intel 13th Gen Core i7-13645HX, 14 cores / 20 threads.
- RAM: 15.71 GiB.
- GPU: NVIDIA GeForce RTX 5050 Laptop GPU, 8,151 MiB reported; driver 610.74.
- Generation: Ollama `qwen3.5:4b`, Q4_K_M; configured 8,192 context tokens, 1,024 output tokens, 512 safety-reserve tokens, temperature 0, 120-second request timeout.
- Embeddings: Ollama `nomic-embed-text:v1.5`, 768 dimensions.
- Retrieval: dense, top-k 8; reranker disabled. Hybrid BM25/RRF remains benchmark-only and was not used.
- Context token estimation uses the configured conservative UTF-8-byte estimate, not the model's exact tokenizer.

## Interpretation

Qdrant and context assembly are small fractions of the observed response time. Ollama generation and claim verification dominate typical latency. The p95 end-to-end response of 13.6 seconds is appropriate only as a local evaluation observation; the 20-sample test does not establish multi-user capacity or production SLOs.
