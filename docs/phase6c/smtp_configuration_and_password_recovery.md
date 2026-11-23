# SMTP configuration and password recovery

## Current state

Django already uses its configured mail backend for time-limited, single-use password reset tokens. Requests use a generic confirmation page, rate limits fail closed when the cache is unavailable, and delivery failures are logged without identifiers, reset links, or provider exception text. SMTP credentials are environment variables only. The current local compose environment has no usable SMTP host configured, so delivery is **BLOCKED / NOT_TESTED**. A locmem or console backend test does not prove mail delivery.

## Environment values

Set these in the ignored `django_app/.env`, never in source control:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SMTP_HOST=smtp.provider.example
SMTP_PORT=587
SMTP_USERNAME=account-or-service-user
SMTP_PASSWORD=provider-app-password
SMTP_USE_TLS=1
SMTP_USE_SSL=0
SMTP_FROM_NAME=Satell
SMTP_FROM_EMAIL=verified-sender@example.org
SMTP_TIMEOUT_SECONDS=10
PUBLIC_APP_BASE_URL=https://chat.example.org
```

TLS and SSL are mutually exclusive. The timeout is bounded to 1–60 seconds. `PUBLIC_APP_BASE_URL` must be an absolute HTTP(S) URL without credentials or query data; production deployment must use HTTPS.

For Gmail, use an app password only when the account's security settings and organization policy allow it. Microsoft 365 SMTP AUTH may be disabled by the tenant; ask the tenant administrator to verify SMTP AUTH and use an approved mailbox/service account. Other providers should supply their documented SMTP host, port, TLS mode, and sender verification requirements. Do not paste credentials into chat or logs.

## Safe check and end-to-end validation

After configuring the values, rebuild/recreate only Django so Compose loads its environment, then run:

```powershell
docker compose --env-file django_app/.env -f django_app/compose.rag.yaml -f django_app/compose.yaml exec django python manage.py check_smtp
```

This opens and closes an authenticated SMTP connection but sends no email. To prove delivery, use the Forgot Password UI with a controlled test account and mailbox, open the received HTTPS reset link, change the password, verify the old password fails and the new password works, then verify token reuse fails. Do not report delivery as operational until that mailbox test succeeds.

The public response does not reveal whether an account exists. SMTP delivery errors return the same public confirmation and produce only a safe generic server log entry. Staff may see a generic configuration notice; logs never include the recipient, reset token, SMTP password, or raw exception details.
