"""Production: debug off, secure cookies, HTTPS. Not deployed yet (local-only for now)."""

from .base import *  # noqa: F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Later: add WhiteNoise for static files and a real DATABASE_URL (PostgreSQL).

from django.core.exceptions import ImproperlyConfigured  # noqa: E402

if not SECRET_KEY or SECRET_KEY.startswith("change-me"):  # noqa: F405
    raise ImproperlyConfigured("Set a real SECRET_KEY in the environment for production.")
