"""The Geometry routes: the tessellated model, and the parts drawn or imported into it."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend import store
from backend.routes.common import read_upload, validated
from core import gmsh_worker
from core.geometry.solid_model import GeometryError
from core.geometry.cad_import import ImportRefused
from core.model.schemas import Project

router = APIRouter()


@router.delete("/api/project/custom_parts")
async def clear_custom_parts() -> dict:
    project = store.get()
    store.put(_without_custom_parts(project, [p.key for p in project.custom_parts]))
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.delete("/api/geometry/parts/{key}")
async def delete_geometry_part(key: str) -> dict:
    project = store.get()
    if not any(p.key == key for p in project.custom_parts):
        raise HTTPException(status_code=404, detail=f"no custom part with key {key!r}")
    store.put(_without_custom_parts(project, [key]))
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}


def _without_custom_parts(project: Project, keys: list[str]) -> Project:
    """`project` minus the custom parts `keys`, validated like any other edit.

    A part a phase still names is refused, not quietly unstaged: which phases should
    lose it is a modelling decision. Left to validation instead, the store would hold a
    project every later PATCH fails on with "names no such part", with only a reset as a
    way out. A mesh size for the part goes with it -- it describes nothing else.
    """
    gone = set(keys)
    users = [(phase.id, sorted(gone & set(phase.activate + phase.deactivate)))
             for phase in project.phases]
    users = [(phase, named) for phase, named in users if named]
    if users:
        listed = "; ".join(f"phase {phase!r} names {', '.join(named)}"
                           for phase, named in users)
        raise HTTPException(status_code=422, detail=(
            f"cannot delete a part that a phase still uses ({listed}); take it out of "
            "those phases first"))
    payload = project.model_dump()
    payload["custom_parts"] = [p for p in payload["custom_parts"] if p["key"] not in gone]
    payload["mesh"]["body_sizes"] = {k: v for k, v in payload["mesh"]["body_sizes"].items()
                                     if k not in gone}
    return validated(payload)


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
    from core.model.schemas import CustomPart
    
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
            
    project = store.get()
    
    # After the highest key in use, not the count: a deleted imported_0 must not let the next
    # import take a key that imported_1 still holds.
    taken = [int(p.key.split("_", 1)[1]) for p in project.custom_parts
             if p.key.startswith("imported_") and p.key.split("_", 1)[1].isdigit()]
    idx = max(taken, default=-1) + 1
    key = f"imported_{idx}"
    
    part = CustomPart(
        key=key,
        label=file.filename or key,
        source="import",
        source_file=res["brep_path"],
        # gmsh measured it while the part was open; kept so `Project.extent` can say
        # how far the model reaches without reopening every .brep.
        bbox=tuple(res["bbox"]),
    )
    project.custom_parts.append(part)
    store.put(project)
    
    return {
        "parts": [part.model_dump()],
        "invalidates": ["geometry", "mesh", "tree", "project"]
    }


@router.post("/api/geometry/create")
async def create_geometry(recipe: dict) -> dict:
    from core.model.schemas import CustomPart
    import json
    
    # `replace` rebuilds an existing part in place, keeping its key -- so its mesh
    # size, tree position and any selection survive a change of shape.
    replace = recipe.get("replace")
    insert_before = recipe.get("insert_before")
    if insert_before is not None and not any(p.key == insert_before for p in store.get().custom_parts):
        raise HTTPException(status_code=404, detail=f"no custom part with key {insert_before!r}")
    if replace is not None and not any(p.key == replace for p in store.get().custom_parts):
        raise HTTPException(status_code=404, detail=f"no custom part with key {replace!r}")

    IGNORED = ("label", "material", "replace", "insert_before")
    shape = {k: v for k, v in recipe.items() if k not in IGNORED}
    for existing in store.get().custom_parts:
        if existing.key == replace:
            continue  # its own former shape is not a clash
        if existing.recipe and {
            k: v for k, v in existing.recipe.items() if k not in IGNORED
        } == shape:
            raise HTTPException(
                status_code=422,
                detail=(f"{existing.label!r} already occupies exactly this space. Two solids in "
                        "the same place cannot both be meshed — move or resize this one."),
            )

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
        
    project = store.get()

    if replace is not None:
        key = replace
    else:
        # A key must be unique for the life of the project: counting the existing
        # drawn_ parts would reuse a key after a delete.
        used = {p.key for p in project.custom_parts}
        idx = len(project.custom_parts)
        while f"drawn_{idx}" in used:
            idx += 1
        key = f"drawn_{idx}"

    # `material` turns the solid into soil: it takes that material's colour and is
    # meshed as a soil body. Validated here so a bad id fails the request rather
    # than being stored and rejected later.
    mat = recipe.get("material")
    if mat is not None:
        if any(m.id == mat for m in project.materials):
            color = project.material(mat).color
        else:
            raise HTTPException(status_code=422, detail=f"Unknown material {mat!r}")
    else:
        color = "#888888"

    part = CustomPart(
        key=key,
        label=recipe.get("label", key),
        source="gui",
        source_file=res["brep_path"],
        recipe=recipe,
        mat=mat,
        color=color,
        bbox=tuple(res["bbox"]),
    )
    if replace is not None:
        at = next(i for i, p in enumerate(project.custom_parts) if p.key == replace)
        project.custom_parts[at] = part
    elif insert_before is not None:
        at = next(i for i, p in enumerate(project.custom_parts) if p.key == insert_before)
        project.custom_parts.insert(at, part)
    else:
        project.custom_parts.append(part)
    store.put(project)
    
    return {
        "parts": [part.model_dump()],
        "invalidates": ["geometry", "mesh", "tree", "project"]
    }
