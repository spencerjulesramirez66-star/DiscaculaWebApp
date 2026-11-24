"""Production / hosted (e.g. Render): debug off, HTTPS, WhiteNoise for static files.

Everything comes from environment variables (Render → Environment). See docs/14-hosting.md.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, MIDDLEWARE, SECRET_KEY, env

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("change-me"):
    raise ImproperlyConfigured("Set a real SECRET_KEY in the environment for production.")

# --- Host name -------------------------------------------------------------------------
# Render sets RENDER_EXTERNAL_HOSTNAME (e.g. myapp.onrender.com) automatically.
_render_host = env("RENDER_EXTERNAL_HOSTNAME", default="")
if _render_host:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, _render_host]
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, f"https://{_render_host}"]

# --- HTTPS (the host terminates TLS and tells us via X-Forwarded-Proto) ---------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)  # raise once the domain is final
SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Static files: WhiteNoise serves CSS/JS/images straight from Django ----------------
MIDDLEWARE = [
    MIDDLEWARE[0],  # SecurityMiddleware first
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Compressed, not hashed: game modules import each other by plain relative paths.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --- Uploaded files (teacher videos) ---------------------------------------------------
# Free hosts usually wipe the disk on every restart, so uploads are temporary there.
# SERVE_MEDIA=True lets Django serve them (fine for a demo; use cloud storage for real use).
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=True)

# --- Errors go to the host's log --------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
