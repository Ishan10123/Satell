from django.conf import settings
from django.core.checks import Warning, register
from urllib.parse import urlsplit


@register()
def password_reset_email_configuration(app_configs, **kwargs):
    issues = []
    if (settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
            and not settings.EMAIL_HOST):
        issues.append(Warning(
            "SMTP_HOST is empty; password-reset requests will receive a generic confirmation but no email can be delivered.",
            hint="Configure SMTP_HOST and sender settings in the environment before enabling account recovery.",
            id="accounts.W001",
        ))
    if not settings.DEBUG and urlsplit(settings.PUBLIC_APP_BASE_URL).scheme != "https":
        issues.append(Warning(
            "PUBLIC_APP_BASE_URL is not HTTPS; password-reset links must use HTTPS for deployed environments.",
            hint="Set PUBLIC_APP_BASE_URL to the deployed HTTPS origin before exposing account recovery.",
            id="accounts.W002",
        ))
    return issues
