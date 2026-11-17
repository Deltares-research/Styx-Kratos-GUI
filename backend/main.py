"""The FastAPI app, assembled from its parts.

The routes of the HTTP API live in `backend/routes/`, one module per group of the API
table in `docs/developer/ARCHITECTURE.md` (project, geometry, mesh, decks, results, files), and
what they share in `backend/routes/common.py`. The Host/Origin check and the no-cache
headers are `backend/middleware.py`. This module puts them together: the gmsh worker's
lifespan, the handler for a crashed worker, the middleware in the order it runs, the
routers, the health check, and the frontend.

The frontend lives in `frontend/`, and everything the browser loads is served from there.
Its base UI -- menus, toolbars, explorer, dialogs and command box -- is in
`frontend/base/css` and `frontend/base/js`, served at `/css` and `/js`; `frontend/assets`
and `frontend/vendor` at `/assets` and `/vendor`. `frontend/js` builds on the base
scripts without editing them, and replaces the orbit controller: `App.Orbit` is a plain
global assignment, so `frontend/js/orbit.js`, loaded after the base one, wins.
"""

from __future__ import annotations

import asyncio
import html
from contextlib import asynccontextmanager
from pathlib import Path
import importlib.resources

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.middleware import do_not_cache_sources, only_this_browser_tab
from backend.routes import decks, files, geometry, mesh, project, results
from core import gmsh_worker, version

# Try to get frontend path from installed package, fall back to development path
try:
    ROOT = Path(str(importlib.resources.files("backend"))).parents[0]
except (ModuleNotFoundError, TypeError):
    # Development mode: get path relative to this file
    ROOT = Path(__file__).resolve().parents[1]

FRONTEND = ROOT / "frontend"
BASE = FRONTEND / "base"

VERSION_SLOT = '<meta name="styx-version" content="">'
"""Where `index` writes the version into the page, for `frontend/js/version.js`."""


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Start the gmsh worker eagerly. On Windows the pool spawns a fresh interpreter and
    # imports gmsh in it, which takes a second or two -- better spent now than charged
    # to whoever asks for geometry first.
    await gmsh_worker.run(gmsh_worker.version_job)
    # Asks git once, off the event loop; the page and the health check read the answer.
    print(f"Styx {await asyncio.to_thread(version.describe)}", flush=True)
    yield
    gmsh_worker.shutdown()


app = FastAPI(title="kratos-GUI backend", lifespan=lifespan)


@app.exception_handler(gmsh_worker.WorkerCrashed)
async def worker_crashed(_request, failure: gmsh_worker.WorkerCrashed):
    """Any route that reaches gmsh: the request that crashed the worker fails with a reason
    the command log can show, and the worker is already being replaced for the next one."""
    return JSONResponse(status_code=500, content={"detail": str(failure)})

# The geometry payload is flat arrays of decimal digits: highly repetitive, and roughly
# an order of magnitude smaller gzipped. This is what makes JSON the right format here.
app.add_middleware(GZipMiddleware, minimum_size=1024)
# Added last runs first: the Host/Origin check sees every request before anything else
# does, then the no-cache headers, then gzip.
app.middleware("http")(do_not_cache_sources)
app.middleware("http")(only_this_browser_tab)


# ── API ─────────────────────────────────────────────────────────────────────
# One router per group of the HTTP API (docs/developer/ARCHITECTURE.md), in `backend/routes/`.
# Only the app's own health check is declared here.

app.include_router(project.router)
app.include_router(geometry.router)
app.include_router(mesh.router)
app.include_router(decks.router)
app.include_router(results.router)
app.include_router(files.router)


@app.get("/api/health")
async def health() -> dict:
    """Proves the worker subprocess is up and gmsh loaded inside it, and says which
    version of Styx answered."""
    return {"ok": True, "version": version.describe(),
            "gmsh_version": await gmsh_worker.run(gmsh_worker.version_job)}


# ── Static ──────────────────────────────────────────────────────────────────

@app.get("/")
async def index() -> HTMLResponse:
    """The page, with the version of Styx written into it: the title bar and the About
    box need it before the first request could bring it."""
    page = (FRONTEND / "index.html").read_text(encoding="utf-8")
    said = html.escape(version.describe(), quote=True)
    return HTMLResponse(page.replace(VERSION_SLOT, VERSION_SLOT.replace('""', f'"{said}"')))


for folder in ("css", "js"):
    app.mount(f"/{folder}", StaticFiles(directory=BASE / folder), name=folder)
for folder in ("assets", "vendor"):
    app.mount(f"/{folder}", StaticFiles(directory=FRONTEND / folder), name=folder)

# The URL keeps its old name: the pages ask for /live/js/..., and renaming that is a
# change of its own.
app.mount("/live", StaticFiles(directory=FRONTEND), name="live")
