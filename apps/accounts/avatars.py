"""Layered avatars from manifest-driven packs (STU-01/02, ADR-0008).

An avatar is saved on StudentProfile.avatar as JSON, e.g.
    {"pack": "default", "base": "cat", "color": "blue", "hair": "tuft", "hat": "none"}
Keys are layer keys from static/assets/avatars/<pack>/manifest.json; values are option ids.
"none" (or a missing key) means "no item" for optional layers.

SVG layers are inlined so `currentColor` picks up the chosen colour; PNG layers become <img>.
"""

from functools import lru_cache

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core.assets import ManifestNotFound, asset_url, load_manifest

NONE = "none"


def pack_manifest(pack: str | None = None) -> dict:
    pack = pack or settings.AVATAR_PACK
    try:
        return load_manifest(f"avatars/{pack}")
    except ManifestNotFound:
        return load_manifest(f"avatars/{settings.AVATAR_PACK}")


def default_avatar(manifest: dict | None = None) -> dict:
    manifest = manifest or pack_manifest()
    avatar = {"pack": manifest["id"]}
    for layer in manifest["layers"]:
        avatar[layer["key"]] = layer["options"][0]["id"] if layer.get("required") else NONE
    return avatar


def clean_avatar(data: dict, manifest: dict | None = None) -> dict:
    """Keep only valid choices; fall back to defaults for missing/invalid required layers."""
    manifest = manifest or pack_manifest()
    result = default_avatar(manifest)
    for layer in manifest["layers"]:
        chosen = data.get(layer["key"])
        valid = {o["id"] for o in layer["options"]}
        if chosen in valid or (chosen == NONE and not layer.get("required")):
            result[layer["key"]] = chosen
    return result


@lru_cache(maxsize=256)
def _inline_svg(static_path: str) -> str:
    path = finders.find(static_path)
    if not path:
        return ""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    # Drop any XML prolog; the assets are our own trusted files (see docs/10-assets-guide.md).
    start = text.find("<svg")
    return text[start:] if start >= 0 else ""


def layer_markup(pack: str, option: dict) -> str:
    """Safe HTML for one option of an image layer."""
    src = option.get("src", "")
    if src.lower().endswith(".svg"):
        if settings.DEBUG:
            _inline_svg.cache_clear()  # pick up edited SVGs without a restart
        return mark_safe(_inline_svg(f"assets/avatars/{pack}/{src}"))  # noqa: S308
    return format_html('<img src="{}" alt="">', asset_url(f"avatars/{pack}", src))


def render_parts(avatar: dict | None) -> dict:
    """{'color': '#hex', 'layers': [html, ...] bottom→top, 'label': 'Cat'} for templates."""
    manifest = pack_manifest((avatar or {}).get("pack"))
    avatar = clean_avatar(avatar or {}, manifest)
    color, layers, label = "currentColor", [], ""
    for layer in sorted(manifest["layers"], key=lambda item: item.get("z", 0)):
        choice = avatar.get(layer["key"])
        option = next((o for o in layer["options"] if o["id"] == choice), None)
        if option is None:
            continue
        if layer.get("type") == "color":
            color = option["value"]
            continue
        if layer["key"] == "base":
            label = option.get("label", "")
        layers.append(layer_markup(manifest["id"], option))
    return {"color": color, "layers": layers, "label": label}
