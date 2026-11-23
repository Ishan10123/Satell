# Phase 6C SMTP delivery validation

## Result: BLOCKED / not delivered

The application was inspected and checked, but a real email delivery test was not possible because no SMTP provider host or credentials are configured. No message was sent to an external mailbox, and password-reset delivery must not be represented as validated.

`manage.py check` reports:

- `accounts.W001`: `SMTP_HOST` is empty; reset requests return a generic confirmation but cannot deliver email.
- `accounts.W002`: `PUBLIC_APP_BASE_URL` is HTTP; deployed recovery links require HTTPS.

Required environment configuration is documented by the app: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `SMTP_FROM_NAME`, `SMTP_FROM_EMAIL`, `SMTP_TIMEOUT_SECONDS`, and an HTTPS `PUBLIC_APP_BASE_URL`. Values belong in the ignored environment file or deployment secret store, never source control.

The local email backend tests validate message construction/token semantics only. Next validation: configure a controlled provider/recipient, run `manage.py check_smtp`, request one reset, inspect delivery at the test mailbox, verify the link uses the HTTPS deployment origin, and confirm token expiry. Do not use a real user mailbox until the owner authorizes that test.
