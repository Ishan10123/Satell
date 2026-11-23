# Resource and concurrency benchmark

## Workload and host

The browser benchmark ran the same 20-question Phase 5 set against the actual path: Chrome → Django/Gunicorn → authenticated FastAPI → Qdrant and Ollama → PostgreSQL. The set was sequential. Samples were taken every two seconds from `docker stats` and `nvidia-smi`. Hardware observed: Intel Core i7-13645HX (14 cores / 20 logical processors), 15.7 GiB system RAM, NVIDIA GeForce RTX 5050 Laptop GPU with 8,151 MiB reported VRAM, driver 610.74. The running Ollama process had 22.3 MiB working set at a post-run snapshot; this is not a peak measurement.

## Results

| Metric | Result |
|---|---:|
| Browser end-to-end minimum | 626 ms |
| p50 | 6,253 ms |
| p95 | 9,755 ms |
| maximum | 15,961 ms |
| Verification outcomes | 12 verified, 4 partial, 1 abstained, 3 failed |
| Responses with citations | 16 of 20 |
| Resource samples | 31 |
| Peak sampled GPU utilization | 100% |
| Peak sampled GPU memory | 4,415 / 8,151 MiB |

Sampled per-container peaks: Django 21.58% CPU / 88.14 MiB RAM; FastAPI 50.58% / 215.5 MiB; Qdrant 29.81% / 561.1 MiB; PostgreSQL 5.77% / 46.34 MiB. Docker's configured memory denominator was 7.611 GiB. These are maxima of periodic samples, not continuous peaks. Host CPU utilization and Ollama peak system RAM were not collected; report those as unmeasured.

Two- and three-request browser bursts completed with HTTP 200 and complete persisted assistant messages. The app ran one synchronous Gunicorn worker, so requests were queued and Ollama generation was serialized at the Django boundary. Two-request wall time was 13,328 ms; three-request wall time was 5,639 ms on a warm model. These are only one observation per workload and are not concurrency capacity guarantees. Results are in `concurrency_probe_results.json`.

The 20-query outcome still contains three failures. The system is suitable only for controlled local demo use; no tuning or context-window increase was performed.
