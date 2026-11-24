"""Small shared helpers."""

from django.conf import settings


def absolute_url(request, path: str) -> str:
    """Full address for `path` that other devices can open.

    Uses SITE_URL from .env when set (e.g. http://192.168.1.20:8000), so a teacher on
    localhost still shows students the Wi-Fi address; otherwise the current request's host.
    """
    if settings.SITE_URL:
        return settings.SITE_URL + path
    return request.build_absolute_uri(path)
