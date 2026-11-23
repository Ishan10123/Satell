# Performance and capacity report

**Hardware snapshot:** Windows 11, NVIDIA RTX 5050 Laptop, reported 8,151 MiB VRAM, Intel i7-13645HX, 15.7 GiB host RAM. This is a workstation baseline, not production infrastructure.

## Model/workload baseline

- Generation/verifier: `qwen3.5:4b` Q4_K_M; 8,192 context; 1,024 output; 512 safety; temperature 0; one retry; 120-second request timeout.
- Embeddings: `nomic-embed-text:v1.5`, 768 dimensions.
- Retrieval: dense top-k 8; context/generation path non-streaming.
- Latest browser sample: 30 queries, p50 4,768.02 ms, p95 6,484.96 ms, max 7,202.05 ms, min 486.54 ms; 13 verified, 6 partial, 4 abstained, 7 failed/rejected. Short abstentions lower minimum. This excludes production queueing and has no human quality ground truth.
- Prior resource sampling recorded GPU up to 100% and 4,415/8,151 MiB VRAM; host CPU and Ollama host RAM peak were not measured.
- Latest individual direct request pair varied: first failed/zero citation at 2,672.45 ms, second verified/two citations at 3,696.64 ms. Not a throughput test.
- Django runs one synchronous Gunicorn worker. No approved concurrent-user target, sustained load or p99 capacity model exists.

## Capacity model requirements

For each target, record query mix, input characters, retrieved/admitted chunks, estimated and actual input/output tokens, queue concurrency, embedding/search/generation/verification throughput, cold start/warm behavior, CPU/RAM/VRAM, disk and network. Measure p50/p95/p99, error and timeout rates at increasing bounded concurrency on isolated staging hardware. Include overload/backpressure, cancellation, worker restart, model reload and CPU fallback. Calculate peak capacity with headroom and independent retrieval/GPU scheduling. Do not extrapolate laptop throughput linearly to GPU replicas.

## Decision

No increase to context/output budget, retrieval top-k, worker count, or inference concurrency was made. Do not use the laptop as a public or commercial capacity commitment. SLO and production hardware remain pending human target selection.
