"""Read asset manifests so code never hard-codes asset paths (ADR-0008).

Each replaceable asset folder under static/assets/ has a manifest.json.
See docs/10-assets-guide.md for the format.
"""

import json
from functools import lru_cache

from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static


class ManifestNotFound(LookupError):
    pass


@lru_cache(maxsize=32)
def _load(area: str) -> dict:
    path = finders.find(f"assets/{area}/manifest.json")
    if not path:
        raise ManifestNotFound(f"No manifest for asset area '{area}'")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_manifest(area: str) -> dict:
    """Parsed manifest for e.g. 'games/fruit_blender' or 'avatars/default'.

    Cached in production; re-read on every call while DEBUG is on so you can
    edit manifests without restarting the server.
    """
    if settings.DEBUG:
        _load.cache_clear()
    return _load(area)


def asset_url(area: str, src: str) -> str:
    """Public URL for a file listed in an area's manifest (src is relative to the area)."""
    return static(f"assets/{area}/{src}")


def avatar_manifest() -> dict:
    return load_manifest(f"avatars/{settings.AVATAR_PACK}")
