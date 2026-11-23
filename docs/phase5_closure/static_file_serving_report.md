# Django static-file serving

**Passed for the local Docker deployment.** Django now runs Gunicorn (`config.wsgi:application`) instead of `runserver --insecure`. `collectstatic` runs during the image build; 130 files were copied and 390 post-processed. WhiteNoise middleware follows `SecurityMiddleware`; `STATIC_ROOT` is `/app/staticfiles`, and `CompressedManifestStaticFilesStorage` serves hashed production assets. Gunicorn uses one synchronous worker, request timeout 135 seconds, and graceful timeout 125 seconds.

Runtime checks after the final image build:

| Asset | HTTP |
|---|---:|
| `/static/admin/css/base.css` | 200 |
| `/static/admin/js/nav_sidebar.js` | 200 |
| `/static/chat/app.css` | 200 |
| `/static/chat/app.js` | 200 |

`/app/staticfiles/admin/css/base.css` exists in the container. There is no static-volume mount hiding image-collected files. The compose health request timeout is 20 seconds and its Docker timeout is 22 seconds. The original 2-second probe timed out while the sole synchronous worker was generating an answer; the longer liveness timeout resolved the false unhealthy status without increasing inference concurrency.

Relevant changes: `django_app/config/settings.py`, `django_app/Dockerfile`, `django_app/requirements-docker.txt`, and `django_app/compose.yaml`.
