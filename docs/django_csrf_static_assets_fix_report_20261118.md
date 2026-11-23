# Django Login CSRF and Admin Static Assets Diagnosis

**Date:** 2026-11-18  
**Application:** `E:\RAG_Project\django_app`  
**Validation URL:** `http://127.0.0.1:8001`

## Findings

### Login CSRF

The login implementation already has the standard CSRF protections:

- `accounts/urls.py` uses Django's built-in `LoginView`.
- `templates/accounts/login.html` submits with `method="post"` and contains `{% csrf_token %}`. It has no `action`, so the browser posts back to the current login URL and origin.
- `CsrfViewMiddleware` is enabled in `config/settings.py`.
- The running container has `ALLOWED_HOSTS=['localhost', '127.0.0.1']`, `CSRF_TRUSTED_ORIGINS=[]`, `CSRF_COOKIE_SECURE=False`, `SESSION_COOKIE_SECURE=False`, `CSRF_COOKIE_HTTPONLY=True`, and `CSRF_COOKIE_SAMESITE='Lax'`. These are consistent with same-origin HTTP on the loopback-only local Compose port. HttpOnly prevents JavaScript access to the CSRF cookie; it does not prevent the browser from sending the cookie with the form request.
- The login form and cookie were both present on a fresh GET to `127.0.0.1:8001`.

**Conclusion:** there is no missing form token, wrong method, or disabled middleware in the current application. With a current token and cookie from `127.0.0.1:8001`, a same-origin POST passed CSRF and reached `LoginView` (the live probe deliberately used a nonexistent account, so it returned the login form rather than authenticating). Missing and invalid tokens returned 403. A valid token paired with a different `Origin` (`http://127.0.0.1:8000`) also returned 403, as Django is expected to reject a cross-origin login POST.

This establishes the failure condition: the browser request must carry a current matching CSRF cookie/token and use the same origin as the form. The exact failed browser request could not be inspected: the computer-use helper could not determine the current browser URL, and the application logs contained no CSRF rejection reason. The attached images were treated as desired visual references, not as evidence of the actual failed request. Therefore, the specific mismatch in the user's browser (stale page/cookie versus a different origin) cannot be distinguished from available evidence. No trusted origin was added and no CSRF setting was relaxed.

For a browser retry, open a fresh `http://127.0.0.1:8001/accounts/login/` page and submit it without switching to `localhost`, another port, or an older tab. If a 403 persists, capture the failed request's `Origin`, `Host`, `Referer`, and whether the `csrftoken` cookie and hidden `csrfmiddlewaretoken` field were sent; do not include the token values in a report.

### Admin static assets

The Admin assets were installed in the image; `findstatic` located `admin/css/base.css` and `admin/js/nav_sidebar.js` under Django's installed `django.contrib.admin` package. Runtime settings had `DEBUG=False`, `django.contrib.staticfiles` installed, `STATIC_URL='/static/'`, no `STATIC_ROOT`, and no `STATICFILES_DIRS`. The Dockerfile ran Django's `runserver` without a static-serving override. Consequently, `/static/admin/css/base.css` and `/static/admin/js/nav_sidebar.js` returned 404 even though the files existed in the container. There was no static volume mount hiding them.

For this explicitly local, loopback-only Compose deployment, the smallest fix is to run Django's staticfiles handler with `runserver --insecure` while keeping `DEBUG=False`. No `collectstatic`, `STATIC_ROOT`, extra server, or new package is needed because the staticfiles finders can serve the Admin assets directly from the installed Django package. This option is only for local development; it must not be used as a production static-file server. See Django's [staticfiles `runserver --insecure` documentation](https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/) and [static-file development guidance](https://docs.djangoproject.com/en/5.2/howto/static-files/).

## Changes made

- `django_app/compose.yaml`: the loopback-only Django service command now includes `--insecure`. It remains `DEBUG=False`; PostgreSQL, `rag-postgres`, `rag_postgres_data`, and the existing network configuration are unchanged.
- `django_app/conversations/tests.py`: expanded CSRF coverage for login-page token/cookie rendering, valid-token authentication, missing and invalid tokens, and rejection of an untrusted Origin. Existing ownership tests remain in the suite.
- `docs/django_csrf_static_assets_fix_report_20261118.md`: this report.

No CSRF exemption, middleware disablement, broad trusted origin, credential change, database migration, or RAG change was made.

## Validation results

The Django image was rebuilt and only the Django service was recreated. PostgreSQL and Qdrant were not restarted. The existing `rag-postgres` container remained healthy with `rag_postgres_data` attached; Qdrant remained running.

Live checks after restart:

| Check | Result |
|---|---|
| `GET /accounts/login/` | HTTP 200; hidden CSRF token present; `csrftoken` cookie present. |
| Same-origin POST with current token/cookie and intentionally invalid probe credentials | HTTP 200 from the login view, not a CSRF 403. |
| POST with missing CSRF token | HTTP 403. |
| POST with invalid CSRF token | HTTP 403. |
| `GET /static/admin/css/base.css` | HTTP 200, `text/css`, 22,120 bytes. |
| `GET /static/admin/js/nav_sidebar.js` | HTTP 200, `text/javascript`, 3,063 bytes. |
| Running Django container | Healthy, bound to host loopback port 8001. |
| Existing superuser record | Found by email; active, staff, and superuser flags true; `AdminSite.has_permission()` returned true. This check was read-only and did not create a login session or access the password. |

All **17 Django tests passed against PostgreSQL**:

```text
Found 17 test(s).
System check identified no issues (0 silenced).
Ran 17 tests in 3.843s
OK
Destroying test database for alias 'default' ('rag_django_test_20261118')...
```

The test database was confirmed absent after the test run. The tests include a real authenticated login in the isolated test database with CSRF checks enforced; they also verify that missing, invalid, and untrusted-origin submissions are rejected. Existing authentication and conversation ownership coverage passed.

## Exact PowerShell commands

Load credentials directly from the already-running PostgreSQL and Django containers into the current PowerShell process without printing them:

```powershell
$pg = ConvertFrom-Json -InputObject ((docker inspect --format '{{json .Config.Env}}' rag-postgres) -join '')
foreach ($name in @('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD')) {
    $entry = $pg | Where-Object { $_.StartsWith($name + '=') } | Select-Object -First 1
    if (-not $entry) { throw "Missing $name in rag-postgres." }
    [Environment]::SetEnvironmentVariable($name, $entry.Substring($name.Length + 1), 'Process')
}
$app = ConvertFrom-Json -InputObject ((docker inspect --format '{{json .Config.Env}}' django_app-django-1) -join '')
$key = $app | Where-Object { $_.StartsWith('DJANGO_SECRET_KEY=') } | Select-Object -First 1
if (-not $key) { throw 'Missing the current Django runtime key.' }
$env:DJANGO_SECRET_KEY = $key.Substring('DJANGO_SECRET_KEY='.Length)
$env:DJANGO_DB_ENGINE = 'postgresql'
$env:POSTGRES_HOST = 'postgres'
$env:POSTGRES_PORT = '5432'
$env:POSTGRES_TEST_DB = 'rag_django_test_20261118'
$env:DJANGO_HOST_PORT = '8001'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1'
$env:DJANGO_DEBUG = '0'
$env:RAG_ADAPTER = 'mock'
```

Rebuild and restart only Django, then run the PostgreSQL-backed tests:

```powershell
docker compose -f django_app/compose.yaml build django
docker compose -f django_app/compose.yaml up -d django
docker compose -f django_app/compose.yaml run --rm django python manage.py test accounts conversations chat rag_client --noinput --verbosity 2
docker compose -f django_app/compose.yaml ps
```

Check the login route and Admin assets:

```powershell
(Invoke-WebRequest http://127.0.0.1:8001/accounts/login/ -UseBasicParsing).StatusCode
(Invoke-WebRequest http://127.0.0.1:8001/static/admin/css/base.css -UseBasicParsing).StatusCode
(Invoke-WebRequest http://127.0.0.1:8001/static/admin/js/nav_sidebar.js -UseBasicParsing).StatusCode
```

The Admin permission check can be rerun read-only without logging in or creating a session:

```powershell
docker exec django_app-django-1 python manage.py shell -c "from django.contrib.auth import get_user_model; from django.contrib.admin.sites import AdminSite; from django.test import RequestFactory; U=get_user_model(); u=U.objects.filter(email='ishurbt1@gmail.com').first() or U.objects.filter(username='ishurbt1@gmail.com').first(); r=RequestFactory().get('/admin/'); r.user=u; print(bool(u and u.is_active and u.is_staff and AdminSite().has_permission(r)))"
```

## Remaining limitations

- The original failed browser request cannot be attributed to a specific missing header or stale token because its request headers were unavailable. Current same-origin login behavior passes; use one canonical loopback origin and reload the form before submission.
- `runserver --insecure` is strictly for this local development Compose setup. Production needs a dedicated static-file serving strategy and must not use Django's development server.
- The admin permission check validates the existing superuser's stored flags and Django Admin permission logic. It does not perform a new password login; no password was supplied or entered.
- The RAG adapter remains mock mode. No real RAG request, Qdrant operation, source approval, or authorization change was made.
