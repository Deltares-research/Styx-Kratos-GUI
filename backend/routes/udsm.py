"""The UDSM routes: the soil models in the UDSM libraries that come with Styx
(`core/model/udsm.py`), for the material window, and the library files, for a deck the
browser downloads.

The page loads the models as a script, before the scripts that read them
(`frontend/index.html`): `App.UDSM_LIBRARY`, as `App.SOIL_MODEL_TABLE` is the soil
models' table. Each library is read once per server, in a process of its own.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from core.model import udsm

router = APIRouter()


@router.get("/api/udsm/library")
def udsm_library() -> dict:
    """Every UDSM model this system can run, with its parameters, and why a library
    is left out."""
    return udsm.table()


@router.get("/api/udsm/library.js")
def udsm_library_script() -> Response:
    return Response("App.UDSM_LIBRARY = " + json.dumps(udsm.table()) + ";\n",
                    media_type="text/javascript")


@router.get("/api/udsm/files/{name}")
def udsm_file(name: str) -> FileResponse:
    """A library a deck uses, by its file name (`udsm/<name>` in the deck)."""
    for path in udsm.files():
        for candidate in (path, path.with_suffix(".so")):
            if candidate.name == name and candidate.exists():
                return FileResponse(candidate, media_type="application/octet-stream",
                                    filename=name)
    raise HTTPException(404, f"there is no UDSM library {name!r}")
