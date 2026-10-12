"""The Decks routes: a Kratos deck out (export, calculate) and back in (import)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend import store
from backend.routes.common import check_mesh_keys, not_for_a_deck, read_upload, run_mesh_job
from core import gmsh_worker
from core.analysis import calculation
from core.geometry.solid_model import GeometryError
from core.kratos.writer import ExportError
from core.geometry.meshing import MeshingError
from core.model.schemas import ExportRequest, Project

router = APIRouter()


@router.post("/api/export/mdpa")
async def export_mdpa(settings: ExportRequest) -> dict:
    """Mesh the project and return a Kratos deck as text, ready to be saved.

    Both files come back in one response so the client can write them side by side and
    put the exporter's warnings in the command log; gzip already covers the size.
    """
    project = store.get()
    not_for_a_deck(project, "exported")
    check_mesh_keys(project, settings)
    return await run_mesh_job(gmsh_worker.export_job, project, settings,
                              (GeometryError, MeshingError, ExportError))


@router.post("/api/calculate")
async def calculate_project(settings: ExportRequest) -> dict:
    """Mesh the project, write its deck to a directory of its own, and run it.

    The deck is exported here rather than taken from whatever the client last
    downloaded: an export is the only thing that knows the mesh it was made from, and a
    calculation run against a stale one would answer a question nobody asked. The
    materials file is written whatever `include_materials` says -- Kratos cannot solve
    without it, and this is not a download.

    The run happens in a thread because it is a blocking wait on a subprocess that owns
    the machine for as long as it takes; the event loop stays free, so the rest of the
    app keeps answering while a solver works. A model Kratos rejects comes back 200 with
    `ok` false and its reason: that is an answer about the model, not a broken server.

    A project that is a deck already (`core.kratos.external_deck`) skips the export: its own files are
    copied into the run directory and run as they are.
    """
    project = store.get()
    if project.deck is not None:
        return await _calculate_deck(project)
    check_mesh_keys(project, settings)
    export = await run_mesh_job(gmsh_worker.export_job, project,
                                settings.model_copy(update={"include_materials": True}),
                                (GeometryError, MeshingError, ExportError))

    try:
        result = await asyncio.to_thread(calculation.run, export)
    except calculation.Busy as busy:
        raise HTTPException(status_code=409, detail=str(busy)) from busy
    except calculation.CalculationError as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure

    # The mesh the run was made from, said in the same breath as the run: the deck was
    # exported here, so this is the only place that can report both. `run` is the
    # directory's bare name, which is the id every `/api/results` route takes -- sent
    # rather than left to the client to split off the path, because the two platforms
    # spell a path separator differently and the client would have to know which.
    return result | {"stats": export["stats"], "warnings": export["warnings"],
                     "run": Path(result["directory"]).name}


async def _calculate_deck(project: Project) -> dict:
    from core.kratos import external_deck

    try:
        stats = external_deck.stats(project.deck)
        result = await asyncio.to_thread(calculation.run_deck, project.deck)
    except external_deck.DeckError as failure:
        raise HTTPException(status_code=400, detail=str(failure)) from failure
    except calculation.Busy as busy:
        raise HTTPException(status_code=409, detail=str(busy)) from busy
    except calculation.CalculationError as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure
    return result | {"stats": stats, "warnings": [],
                     "run": Path(result["directory"]).name}


@router.post("/api/import/mdpa")
async def import_mdpa(file: UploadFile = File(...)) -> dict:
    """Read a `.mdpa` deck's mesh back: nodes, typed elements/conditions, and named
    sub-model-part groupings, classified as a body, load, boundary, support or group.

    Pure text parsing, no gmsh worker involved. This recovers the mesh a deck contains,
    not the parametric project that produced it -- that information is discarded on
    export and cannot be reconstructed from the deck alone.

    A 2D deck carries Kratos plane coordinates with no memory of which plane it was cut
    from, so it is stood up on the open project's own section plane: that is where the
    app's 2D view looks, and it is the plane an export of this project would have
    flattened.
    """
    from core.kratos.mdpa_reader import ImportError_, import_mdpa as parse

    ext = Path(file.filename or "").suffix.lower()
    if ext != ".mdpa":
        raise HTTPException(status_code=422, detail="Unsupported file extension. Use .mdpa.")

    text = (await read_upload(file)).decode("utf-8", errors="replace")

    # A deck's node table is already the world frame in either dimension -- a 2D deck
    # is the x-y plane at z = 0, which is where a 2D model lives -- so nothing about
    # the open project is needed to place it.
    #
    # `node_parts` is what lets the preview answer "which SubModelParts is this node
    # in" when a node is clicked (frontend/js/node-parts.js).
    from core.kratos import node_parts

    def preview() -> dict:
        model = parse(text)
        return {**model.to_dict(), "node_parts": node_parts.of_model(model)}

    try:
        # Off the event loop: a real deck is megabytes, seconds of parsing.
        return await asyncio.to_thread(preview)
    except ImportError_ as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
