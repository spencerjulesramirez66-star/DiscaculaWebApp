"""Used by pytest (see pyproject.toml). Fast and isolated."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-only-secret-key"  # noqa: S105
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
# Fast hashing so tests that create users don't crawl.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
