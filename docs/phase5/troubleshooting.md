# Troubleshooting

## Django container is unhealthy

Inspect `docker logs --tail 100 django_app-django-1`. The startup wrapper prints only which dependency is pending; it does not print credentials or exception details. Verify the existing PostgreSQL container is healthy and the app networks remain present. Verify FastAPI `/health` and authenticated `/ready` separately.

## Login page works but sign-in fails

Use `http://127.0.0.1:8001` consistently. Confirm the browser returns the CSRF cookie and the login form contains its hidden token. Do not disable `CsrfViewMiddleware`. A session signed with a previous Django key expires after a key rotation; log in again.

## RAG response unavailable

Check FastAPI container health, then authenticated `/ready` from Django. Check that Windows Ollama is running and `qwen3.5:4b` plus `nomic-embed-text:v1.5` are available locally. Do not switch to mock mode to hide an outage. The UI shows a generic service error; detailed classifications are stored in bounded metadata, not the page.

## Citations absent or answer withheld

This can be correct fail-closed behavior when retrieved evidence is insufficient, citation syntax/mapping is invalid, verifier output is malformed, or version consistency is uncertain. Shorten or clarify the question and check source references. Do not relax evidence or citation thresholds.

## Static styles missing

The local development server uses Django `--insecure` staticfiles serving with `DEBUG=0`; verify `/static/chat/app.css` and `/static/chat/favicon.svg` return 200. This is a local demonstration configuration, not a production static-file strategy.
