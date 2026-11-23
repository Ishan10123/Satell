# Final security review

## Verified controls

- Django uses its authentication/session/CSRF protections; missing CSRF stayed HTTP 403 and unauthenticated browser routes redirect to login.
- Conversation access remains ownership-scoped. The Django regression suite covers cross-user conversation/message/citation access, and all ownership tests passed.
- Django sends the FastAPI bearer token server-side; the browser page did not contain `RAG_API_TOKEN`. Invalid bearer auth returned 401.
- Django and PostgreSQL/Qdrant published host ports were bound to `127.0.0.1`; FastAPI had no published host binding. FastAPI and Django communicate over the existing private networks. Authenticated FastAPI `/ready` passed and checks the index, embedding, Qdrant, and Ollama components.
- Legal source statuses remain 14 pending; all inventory license statuses remain pending. The production index manifest remains `operator_authorized_unreviewed`; local academic demo policy remains a separate explicit policy.
- Django runtime is non-root, read-only except tmpfs, drops all capabilities, and uses `no-new-privileges`. Static assets are collected into the image and served by WhiteNoise.
- Citation cards/copy omit internal document identifiers; diagnostic artifact and API protections remain covered by RAG regression tests.

## Scan and gaps

A redacted source/config scan excluding `.env` reported six secret-like literals, all located in Django tests and named synthetic/local-demo test credentials. The actual `.env` was not read into output, and the Docker image config was checked without printing environment values; no runtime secret value is baked into the image. `.dockerignore` excludes `django_app/.env`. One build-only placeholder is used solely to let Django run `collectstatic`; it is not a deployed credential.

There is no TLS termination for the loopback local UI. No authenticated external/public deployment, distributed rate limiting, production monitoring/alerting, tested multi-user tenant boundary, scheduled backup policy, disaster recovery exercise, or comprehensive audit-log retention policy is demonstrated. Physical dependency outages were not injected into shared services. Legal approval remains pending. Therefore private and public production readiness are false.
