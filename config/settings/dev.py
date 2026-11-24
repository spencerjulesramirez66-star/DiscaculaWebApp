"""Local development: debug on, SQLite, emails printed to the terminal."""

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True

# Tunnels (share this PC's server with a public https link): ngrok, Cloudflare quick tunnels,
# localtunnel. Their addresses change every time, so allow the whole tunnel domain in dev.
# Login and every button need CSRF_TRUSTED_ORIGINS, because the browser is on https while
# Django sees plain http behind the tunnel. See docs/14-hosting.md.
TUNNEL_DOMAINS = [
    ".ngrok-free.app",
    ".ngrok-free.dev",
    ".ngrok.app",
    ".ngrok.dev",
    ".ngrok.io",
    ".trycloudflare.com",
    ".loca.lt",
]
ALLOWED_HOSTS = [*ALLOWED_HOSTS, *TUNNEL_DOMAINS]
CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, *(f"https://*{d}" for d in TUNNEL_DOMAINS)]

# Django Debug Toolbar: the developer panel on the right edge of every page (the green tab
# when hidden). Only shown to requests from this computer (INTERNAL_IPS), never to students on
# other devices. Turn it off with DEBUG_TOOLBAR=False in .env, then restart runserver.
DEBUG_TOOLBAR = env.bool("DEBUG_TOOLBAR", default=True)
if DEBUG_TOOLBAR:
    INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
    INTERNAL_IPS = ["127.0.0.1"]
