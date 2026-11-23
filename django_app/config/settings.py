"""Environment-driven settings for the Django presentation/application layer."""

import os
from pathlib import Path
from urllib.parse import urlsplit
from email.utils import formataddr, parseaddr


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
DEBUG = env_bool("DJANGO_DEBUG", True)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be configured in every environment.")

ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend").strip()
EMAIL_HOST = os.environ.get("SMTP_HOST", "").strip()
EMAIL_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("SMTP_USERNAME", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_USE_TLS = env_bool("SMTP_USE_TLS", True)
EMAIL_USE_SSL = env_bool("SMTP_USE_SSL", False)
EMAIL_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT_SECONDS", "10"))
_sender_name, _sender_address = parseaddr(os.environ.get("SMTP_FROM_EMAIL", "no-reply@example.invalid").strip())
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "").strip() or _sender_name or "Satell"
SMTP_FROM_ADDRESS = _sender_address or os.environ.get("SMTP_FROM_EMAIL", "no-reply@example.invalid").strip()
if any(character in SMTP_FROM_NAME + SMTP_FROM_ADDRESS for character in "\r\n"):
    raise RuntimeError("SMTP sender values cannot contain line breaks.")
DEFAULT_FROM_EMAIL = formataddr((SMTP_FROM_NAME, SMTP_FROM_ADDRESS))
PUBLIC_APP_BASE_URL = os.environ.get("PUBLIC_APP_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT_SECONDS", "3600"))
PASSWORD_RESET_RATE_LIMIT = int(os.environ.get("PASSWORD_RESET_RATE_LIMIT", "5"))
PASSWORD_RESET_RATE_WINDOW_SECONDS = int(os.environ.get("PASSWORD_RESET_RATE_WINDOW_SECONDS", "3600"))

_public_url = urlsplit(PUBLIC_APP_BASE_URL)
if (_public_url.scheme not in {"http", "https"} or not _public_url.hostname
        or _public_url.username or _public_url.password or _public_url.query or _public_url.fragment):
    raise RuntimeError("PUBLIC_APP_BASE_URL must be a valid absolute HTTP(S) URL without credentials or query data.")
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise RuntimeError("SMTP TLS and SSL modes cannot both be enabled.")
if not 1 <= EMAIL_TIMEOUT <= 60:
    raise RuntimeError("SMTP_TIMEOUT_SECONDS must be between 1 and 60.")
if (not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend"):
    raise RuntimeError("Console email backend is allowed only in explicit development mode.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "conversations.apps.ConversationsConfig",
    "chat.apps.ChatConfig",
    "rag_client.apps.RagClientConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.DatabaseAvailabilityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "accounts.context_processors.user_preferences",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DB_ENGINE = os.environ.get("DJANGO_DB_ENGINE", "postgresql").strip().lower()
if DB_ENGINE == "sqlite":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_SQLITE_PATH", str(BASE_DIR / "development.sqlite3")),
    }}
elif DB_ENGINE == "postgresql":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "rag_application"),
        "USER": os.environ.get("POSTGRES_USER", "rag_application"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": int(os.environ.get("POSTGRES_CONNECT_TIMEOUT", "5"))},
        "TEST": {"NAME": os.environ.get("POSTGRES_TEST_DB") or None},
    }}
else:
    raise RuntimeError("DJANGO_DB_ENGINE must be 'postgresql' or 'sqlite'.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles"))).resolve()
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 65_536
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "conversations:list"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", False)

# The HTTP adapter runs only in the Django server process. These values are never
# put in templates, page context, browser forms, or JavaScript.
RAG_ADAPTER = os.environ.get("RAG_ADAPTER", "mock").strip().lower()
RAG_API_BASE_URL = os.environ.get("RAG_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RAG_API_TOKEN = os.environ.get("RAG_API_TOKEN", "")
RAG_API_TIMEOUT_SECONDS = float(os.environ.get("RAG_API_TIMEOUT_SECONDS", "15"))
RAG_API_TOP_K = int(os.environ.get("RAG_API_TOP_K", "8"))
RAG_MODEL_VERSION = os.environ.get("RAG_MODEL_VERSION") or None
RAG_INDEX_VERSION = os.environ.get("RAG_INDEX_VERSION") or None
