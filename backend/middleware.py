"""The HTTP middleware: what every request goes through before any route runs.

`only_this_browser_tab` is the security boundary (`tests/api/test_security.py`), and
`do_not_cache_sources` keeps a browser from mixing old and new frontend files.
`backend/main.py` registers both, and the order it registers them in is the order they run.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse

from backend.launcher import ALLOWED_HOSTS_ENV

# Sources the app is built from, as opposed to assets that never change.
SOURCE_SUFFIXES = (".js", ".css", ".html")


async def do_not_cache_sources(request, call_next):
    """Serve the frontend sources with no-store.

    This frontend is edited constantly and reloaded in a browser perfectly willing to
    keep an old copy of one file and not another. A half-stale mix -- a new patches.js
    against an old viewport.js -- breaks in ways that read as model bugs rather than as
    caching, and costs far more to diagnose than the bytes cost to re-send. Vendored
    assets (the pinned three.js, the logo) keep their normal caching.
    """
    response = await call_next(request)
    path = request.url.path
    if (path == "/" or path.endswith(SOURCE_SUFFIXES)) and not path.startswith("/vendor/"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def allowed_hosts() -> set[str]:
    """The names this server answers to: loopback, plus `ALLOWED_HOSTS_ENV` -- read per
    request, so it can be set without a code change and tested without a restart."""
    extra = os.environ.get(ALLOWED_HOSTS_ENV, "")
    return set(LOOPBACK_HOSTS) | {h.strip().lower() for h in extra.split(",") if h.strip()}


def host_name(netloc: str) -> str:
    """`host[:port]` or `[v6]:port`, without the port, lower-cased."""
    netloc = netloc.strip().lower()
    if netloc.startswith("["):
        return netloc[1:netloc.find("]")] if "]" in netloc else netloc
    return netloc.rsplit(":", 1)[0] if netloc.count(":") == 1 else netloc


async def only_this_browser_tab(request, call_next):
    """Refuse requests that did not come from a page this server served.

    The server listens on loopback, but any site the user has open can still try to
    reach it, and `/api/project/script` runs Python. Two ways in, two checks, both
    before any route runs:

    * **DNS rebinding** -- an attacker's name made to resolve to 127.0.0.1 -- arrives
      with the attacker's name in `Host`. Refused unless it is a loopback name or one
      listed in `KRATOS_GUI_ALLOWED_HOSTS` (which `--host <name>` sets).
    * **A cross-site request** -- a form or fetch from another page -- carries that
      page's `Origin`. Refused unless it is this server's own. A request with no
      `Origin` (a same-origin GET, curl, a test client) is not a browser crossing sites.
    """
    allowed = allowed_hosts()
    if host_name(request.headers.get("host", "")) not in allowed:
        return JSONResponse(status_code=400, content={"detail": (
            f"Refused: this server answers to {', '.join(sorted(allowed))} as its host, "
            f"not {request.headers.get('host', '')!r}. To serve it under another name, "
            f"list that name in {ALLOWED_HOSTS_ENV}.")})
    origin = request.headers.get("origin")
    if origin is not None:
        parsed = urlsplit(origin)
        if not parsed.scheme or host_name(parsed.netloc) not in allowed:
            return JSONResponse(status_code=403, content={"detail": (
                f"Refused: a request from another site (origin {origin!r}) may not use "
                "this server.")})
    return await call_next(request)
