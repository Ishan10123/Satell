# Phase 5 observability and performance report

## Observability

Added `python manage.py rag_metrics --limit 200`. It outputs bounded status/error counts and per-stage latency percentiles from `GenerationMetadata`; it excludes message text and request IDs. `django_persistence` is now measured and persisted. Existing FastAPI diagnostics remain private and opt-in/bounded.

The standalone metrics command was exercised. The observed 41-row sample included test fixtures and prior activity, so it is not presented as a production-only error rate. The live evaluation artifact is the source for the measurements below.

## 20 sequential real browser queries

Source: `live_evaluation_results.json`; Chrome form submissions exercised real Django → FastAPI → Qdrant/Ollama → verification/citation validation → PostgreSQL persistence. Hardware: Windows 11 host; NVIDIA GeForce RTX 5050 Laptop GPU, driver 610.74, 8,151 MiB reported GPU memory; model `qwen3.5:4b`; context 8,192, output reservation 1,024, safety reserve 512. No model/context/retrieval settings were changed.

| Measurement | Count | Min | p50 | p95 | Max |
|---|---:|---:|---:|---:|---:|
| Browser end-to-end, ms | 20 | 779 | 6,303 | 9,824 | 15,101 |
| Django-to-FastAPI stage, ms | 20 | 433 | 5,815 | 9,410 | 14,686 |
| Dense Qdrant search, ms | 20 | 31 | 44 | 69 | 85 |
| Embedding, ms | 20 | 25 | 43 | 79 | 97 |
| Context assembly, ms | 20 | 0.7 | 0.9 | 1.4 | 1.5 |
| Generation stage, ms | 16 | 3,004 | 5,658 | 9,357 | 14,298 |
| Claim verification, ms | 16 | 1,694 | 2,861 | 4,939 | 7,544 |
| Django persistence, ms | 20 | 2.8 | 4.8 | 5.9 | 6.0 |

Stage timings are only present when that stage ran; fail-closed/abstention paths can omit generation or verification. End-to-end time includes browser navigation and the full service request. The 20 prompts are a small repeated topic set with heuristic labels, not an independent quality benchmark.

## Resource samples

The evaluation sampler ran at approximately two-second intervals and captured 32 Docker/GPU samples during the sequential run.

- GPU utilization observed: peak 100%.
- GPU memory observed: 4,415 / 8,151 MiB. This was the sampled live workload; it is not per-request allocation attribution.
- Peak sampled container CPU/memory: Django 20.51% / 65.5 MiB; FastAPI 30.7% / 215.4 MiB; Qdrant 31.97% / 495.4 MiB; PostgreSQL 3.62% / 62.5 MiB. Docker CPU percentages are container sampling values, not total host CPU.
- One post-workload Windows host CPU sample was 3.28%; it is not a workload peak.
- Docker metrics cover process/container memory indirectly. A dedicated Windows process-level peak RAM capture was not available in the run, so host/process peak memory is **not measured**.
- No concurrent workload was run. At 100% sampled GPU utilization and an 8 GiB device, concurrency would add unnecessary risk without a bounded baseline test. The application has not been declared concurrency-safe from this sequential run.

Dense retrieval remains active. BM25, RRF, and reranking were not enabled. No evidence justified changing context size, retrieval strategy, or model settings.
