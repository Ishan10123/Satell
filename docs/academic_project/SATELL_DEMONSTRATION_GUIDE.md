# Satell local demonstration guide

Use only for a supervised local academic demonstration. Local demo authorization is not legal approval. The app is bound to loopback and the corpus scope is limited; do not expose it to a LAN or public network.

## Chat and account recovery

The current UI supports password visibility, username/email reset requests, and owner-only rename/export/share/lock/unlock/delete actions. SMTP is not configured in the current workstation environment, so reset emails cannot be delivered until an operator configures the environment described in [deployment and operations](SATELL_DEPLOYMENT_AND_OPERATIONS.md). A generic reset confirmation is not evidence of delivery.

Conversation share links are optional. Anyone with a live link can read the selected conversation until it expires or is revoked. Do not share sensitive content through a link. Locking is a read-only application control and does not encrypt messages.

## Pre-demo checklist

- [ ] Confirm current signed local demo registry and policy are present; do not edit them during the demo.
- [ ] Confirm existing PostgreSQL and Qdrant containers/volumes are healthy and backed up per the operations procedure.
- [ ] Confirm Ollama is running and `qwen3.5:4b` and `nomic-embed-text:v1.5` are available.
- [ ] Confirm FastAPI `/health` and authenticated `/ready` succeed.
- [ ] Confirm Django returns the login page at `http://127.0.0.1:8001/`.
- [ ] Sign in using an operator-provisioned account; do not put credentials in screenshots or command history.
- [ ] Confirm browser is using the loopback URL, not a host IP.
- [ ] Explain that production and legal approval remain blocked.

## 10–15 minute sequence

1. **Problem (1 min):** documentation is large; retrieval supplies source passages to a local model.
2. **Architecture (2 min):** show this handbook architecture and distinguish Django, FastAPI, PostgreSQL, Qdrant and Ollama.
3. **Login and conversation (1 min):** authenticate and create a conversation.
4. **Verified query (2–3 min):** ask: “In FastAPI, what is a path parameter? Give one concise fact from the documentation.” This exact query returned HTTP 200, one citation, `verification=verified`, preserved correlation, and `synthetic=false` in the recorded live check. Repeat live before presenting; outcomes can vary.
5. **Citation inspection (2 min):** open the citation and explain source/document/chunk provenance and that citation existence is not a truth guarantee.
6. **Follow-up and history (1 min):** show persistence. Clarify each follow-up is currently treated as a standalone query rather than given full prior history.
7. **Safe abstention (1–2 min):** use a question clearly outside the documentation scope; present only the result actually observed. If the model answers without support, explain the verifier/citation gate and do not call it verified.
8. **Authorization and health (2 min):** show readiness status without displaying secrets. State that local demo scope and legal/production approval differ.
9. **Limitations (1 min):** mention small evaluation, one synchronous worker, laptop inference, pending legal decisions and production blockers.

## Startup and health commands

From `E:\RAG_Project` in PowerShell:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml up -d --build rag-api django
docker ps --format "{{.Names}} {{.Status}} {{.Ports}}"
Invoke-WebRequest http://127.0.0.1:8001/accounts/login/ -UseBasicParsing | Select-Object StatusCode
docker inspect django_app-django-1 --format '{{.State.Health.Status}}'
docker inspect django_app-rag-api-1 --format '{{.State.Health.Status}}'
docker exec django_app-django-1 python manage.py shell -c "from django.conf import settings; import httpx; print(httpx.get(settings.RAG_API_BASE_URL + '/ready', headers={'Authorization': 'Bearer ' + settings.RAG_API_TOKEN}, timeout=10).status_code)"
Invoke-RestMethod http://127.0.0.1:6333/collections/rag_docs_v2 | Select-Object status, result
docker exec rag-postgres pg_isready
ollama list
```

The readiness command prints only status, never the token. Safe app logs:

```powershell
docker logs --tail 100 django_app-django-1
docker logs --tail 100 django_app-rag-api-1
```

Do not dump environment variables or enable unrestricted prompt diagnostics during a demo. Run tests via the commands in `SATELL_TESTING_AND_EVALUATION.md`. Stop only application services with the documented compose `stop django rag-api`; never use `down -v`.

## Troubleshooting

- **Login/CSRF:** use the same `127.0.0.1:8001` origin and a fresh browser session; never disable CSRF.
- **FastAPI readiness fails:** inspect health and bounded logs; do not switch to mock silently or bypass authorization.
- **No answer / safe rejection:** preserve status and show the evidence/verification limitation; do not retry with a fabricated answer.
- **Qdrant or PostgreSQL unhealthy:** stop the demo and follow backup/recovery operations. Do not reset containers or volumes.
- **Slow generation:** one synchronous worker queues requests; wait and do not flood the endpoint.
