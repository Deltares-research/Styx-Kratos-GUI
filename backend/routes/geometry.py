"""The Geometry routes: the tessellated model, and the parts drawn or imported into it."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend import store
from backend.routes.common import read_upload, refusals
from core import gmsh_worker, session
from core.geometry.solid_model import GeometryError
from core.geometry.cad_import import ImportRefused

router = APIRouter()


@router.delete("/api/project/custom_parts")
async def clear_custom_parts() -> dict:
    """Delete every custom part (`session.without_custom_parts`): refused, naming the
    stage, while a stage still uses one of them."""
    project = store.get()
    with refusals():
        project = session.without_custom_parts(project, [p.key for p in project.custom_parts])
    store.put(project)
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.delete("/api/geometry/parts/{key}")
async def delete_geometry_part(key: str) -> dict:
    with refusals():
        project = session.without_custom_part(store.get(), key)
    store.put(project)
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.get("/api/geometry")
async def get_geometry() -> dict:
    project = store.get()
    try:
        return await gmsh_worker.run(gmsh_worker.geometry_job, project.model_dump_json())
    except GeometryError as failure:
        # Surfaced so the frontend can put it in the command log. An empty model would
        # otherwise be indistinguishable from a rendering bug.
        raise HTTPException(status_code=500, detail=str(failure)) from failure


@router.post("/api/geometry/import")
async def import_geometry(file: UploadFile = File(...)) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".step", ".stp", ".iges", ".igs", ".brep", ".stl", ".obj"):
        raise HTTPException(status_code=422, detail="Unsupported file extension. Use .step, .iges, .brep, .stl, or .obj.")
        
    data = await read_upload(file)
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            
        res = await gmsh_worker.run(gmsh_worker.import_job, path, ext)
    except ImportRefused as refused:
        # The file's problem, not the server's: the message says what to change in it.
        raise HTTPException(status_code=422, detail=str(refused)) from refused
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if os.path.exists(path):
            os.remove(path)
            
    project, part = session.with_imported_part(store.get(), file.filename, res)
    store.put(project)

    return {
        "parts": [part.model_dump()],
        "invalidates": ["geometry", "mesh", "tree", "project"]
    }


@router.post("/api/geometry/create")
async def create_geometry(recipe: dict) -> dict:
    """Build a solid from `recipe` in the gmsh worker and add it as a custom part.

    The recipe is checked before gmsh is asked (`session.check_recipe`) -- a part it
    names that is not there, a solid exactly where another one is, an unknown material
    -- so a refusal costs no geometry work. What to do with the solid once built is
    `session.with_created_part`'s.
    """
    import json

    with refusals():
        session.check_recipe(store.get(), recipe)

    try:
        res = await gmsh_worker.run(gmsh_worker.create_job, json.dumps(recipe))
    except ValueError as refused:
        # `core.geometry.primitives` raises ValueError for a recipe it cannot build -- an unknown kind,
        # too few vertices: the caller's to fix, so 422 with its reason, not a 500.
        raise HTTPException(status_code=422, detail=str(refused)) from refused
    except gmsh_worker.WorkerCrashed:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
        
    # Checked again against the project as it is now: gmsh took a while, and the store
    # may have changed under it.
    with refusals():
        project, part = session.with_created_part(store.get(), recipe, res)
    store.put(project)

    return {
        "parts": [part.model_dump()],
        "invalidates": ["geometry", "mesh", "tree", "project"]
    }
