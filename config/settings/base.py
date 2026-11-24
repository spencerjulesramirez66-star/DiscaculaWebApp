"""Settings shared by every environment. See docs/03-architecture.md and ADR-0007.

Environment-specific overrides live in dev.py / test.py / prod.py.
Secrets and machine-specific values come from the .env file.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Branding — the ONE place the site name is defined. Templates use {{ SITE_NAME }}
# (via apps.core.context_processors.site); Python code uses settings.SITE_NAME.
# ---------------------------------------------------------------------------
SITE_NAME = "Web App for Dyscalculia"

SECRET_KEY = env("SECRET_KEY", default="")  # required; prod.py refuses to start without it
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
# The app's base address (room-code screen, login cards). Change in .env when it moves.
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000").rstrip("/")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.classrooms",
    "apps.games",
    "apps.content",
]
INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth — custom user model must exist before the first migration (ADR-0004).
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrUsernameBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:after_login"
LOGOUT_REDIRECT_URL = "core:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# "Remember me" keeps a login for this long (ACC-07).
REMEMBER_ME_DAYS = 30
SESSION_COOKIE_AGE = 60 * 60 * 24 * REMEMBER_ME_DAYS

# One-time codes (ACC-02, ACC-08)
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60

# ---------------------------------------------------------------------------
# Internationalisation — English now, strings wrapped for translation (GEN-05).
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media — replaceable assets live in static/assets (docs/10-assets-guide.md).
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

AVATAR_PACK = env("AVATAR_PACK", default="default")
MAX_VIDEO_UPLOAD_MB = env.int("MAX_VIDEO_UPLOAD_MB", default=50)
SESSION_EXPIRY_HOURS = env.int("SESSION_EXPIRY_HOURS", default=3)

# ---------------------------------------------------------------------------
# Email — Django 6.1 MAILERS format. Dev default prints to the terminal.
# ---------------------------------------------------------------------------
EMAIL_BACKEND_PATH = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
if EMAIL_BACKEND_PATH.endswith("smtp.EmailBackend"):
    MAILERS = {
        "default": {
            "BACKEND": EMAIL_BACKEND_PATH,
            "OPTIONS": {
                "host": env("EMAIL_HOST"),
                "port": env.int("EMAIL_PORT", default=587),
                "username": env("EMAIL_HOST_USER", default=""),
                "password": env("EMAIL_HOST_PASSWORD", default=""),
                "use_tls": env.bool("EMAIL_USE_TLS", default=True),
            },
        }
    }
else:
    MAILERS = {"default": {"BACKEND": EMAIL_BACKEND_PATH}}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@localhost")
