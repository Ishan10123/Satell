# Durable asynchronous inference architecture

**Status:** design only; no queue, broker or schema migration was introduced.

## Confirmed current limitation

`django_app/chat/views.py::message_create` commits a user message and pending assistant row, performs a synchronous HTTP request, then persists answer/citations/metadata. A process interruption between transactions can leave a pending row. There is no idempotency key, durable queue, cancellation API, or pending-message sweeper. Gunicorn is configured with one synchronous worker; a larger web-worker count could overload one GPU.

## Candidate design

1. Browser submits an idempotency key and message to Django.
2. A transaction creates the user message, pending response and outbox job with unique `(user, conversation, idempotency_key)`; no RAG call occurs inside the transaction.
3. Dispatcher claims jobs with lease/heartbeat and enqueues a signed job envelope. Delivery is at-least-once; worker deduplicates against durable job state.
4. Bounded retrieval workers call FastAPI under a per-tenant service scope. GPU inference is separately semaphore/queue limited; no unbounded parallel generation.
5. Worker persists terminal state and citation metadata transactionally, including request IDs and stage timings.
6. Web polls or uses server-sent status events; raw token streaming is optional and not required initially.
7. Expired leases recover after worker crash; retry budget is finite; permanent failures enter a dead-letter state; user can retry with a new idempotency key.
8. Cancellation marks a job if it has not started; in-flight model cancellation is best-effort and must not lose terminal state.

## Broker choices

| Choice | Benefit | Risk/cost | Decision |
|---|---|---|---|
| PostgreSQL outbox + bounded worker polling | Existing persistent system of record; avoids immediate extra broker | Polling/load coupling, locking/leases, throughput limits | Candidate for small private deployment; validate under staging load. |
| Redis/Celery-like queue | Mature task delivery/retry patterns and independent worker pool | Additional stateful service, operational and recovery burden; requires broker durability configuration | Do not add until deployment target and operator skills are decided. |
| Managed queue | Reduces broker operations | Vendor/cost/data-region and connectivity dependency | Provider decision pending. |

Do not increase Gunicorn workers as a substitute for GPU scheduling. Required tests: duplicate POST, crash after commit, crash after enqueue, lease expiry, repeated delivery, worker shutdown, database/network timeout, deadline propagation, DLQ, retry safety, cancellation, ordering and orphan-pending reconciliation. Run only against staging DB/queue and fake or isolated inference service until acceptance.
