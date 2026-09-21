"""The FastAPI app.

Two things it deliberately does not do:

*   It does not copy the frozen mockup. `kratos-GUI/css`, `js`, `assets` and `vendor` are
    mounted where they already live, so the served app and the one that opens straight
    off `file://` are the same bytes and cannot drift apart.
*   It does not modify them. The backend-connected frontend lives in `live/`, loads the
    frozen scripts verbatim, and replaces exactly two: `js/viewport.js`, the one module
    that invents geometry, and `js/orbit.js`, which is hard-wired to a Z-up world the
    model no longer uses. The orbit controller is *overridden* rather than dropped --
    `App.Orbit` is a plain global assignment, so the frozen file is still loaded and
    `live/js/orbit.js` after it wins.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
import os
import tempfile

from app import calculate, gmsh_worker, store
from app.loads import translate as translate_loads
from app.walls import translate as translate_walls
from app.build import GeometryError
from app.kratos import ExportError
from app.meshing import MeshingError
from app.schemas import (DimensionUpdate, ExportRequest, LayersUpdate, MaterialsUpdate,
                         MeshRequest, Project, StructuresUpdate)

FROZEN = Path(__file__).resolve().parents[2]
LIVE = FROZEN / "live"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Start the gmsh worker eagerly. On Windows the pool spawns a fresh interpreter and
    # imports gmsh in it, which takes a second or two -- better spent now than charged
    # to whoever asks for geometry first.
    await gmsh_worker.run(gmsh_worker.version_job)
    yield
    gmsh_worker.shutdown()


app = FastAPI(title="kratos-GUI backend", lifespan=lifespan)

# The geometry payload is flat arrays of decimal digits: highly repetitive, and roughly
# an order of magnitude smaller gzipped. This is what makes JSON the right format here.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Sources the app is built from, as opposed to assets that never change.
SOURCE_SUFFIXES = (".js", ".css", ".html")


@app.middleware("http")
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


# ── API ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict:
    """Proves the worker subprocess is up and gmsh loaded inside it."""
    return {"ok": True, "gmsh_version": await gmsh_worker.run(gmsh_worker.version_job)}


@app.get("/api/project")
async def get_project() -> Project:
    return store.get()


@app.put("/api/project")
async def put_project(project: Project) -> Project:
    return store.put(project)


@app.post("/api/project/reset")
async def reset_project() -> dict:
    """Restore the seed (demo) model."""
    project = store.reset()
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.post("/api/project/script")
async def run_script(request: dict) -> dict:
    """Build the model by running a Python file: the command line's `run <file.py>`.

    The file is executed here, in the server's own interpreter, and whatever `Project`
    it describes becomes the open model. See `app.script` for the three ways a script
    can hand one back, and for why this route is local-only by construction.
    """
    from app import script as script_module

    path = (request or {}).get("path")
    if not path:
        raise HTTPException(status_code=422, detail="run needs a path to a .py file")
    try:
        project = store.put(script_module.load_project(path))
    except script_module.ScriptError as failure:
        # 400, not 500: the file is the caller's, and every one of these messages is
        # written to be read by whoever typed the command.
        raise HTTPException(status_code=400, detail=str(failure)) from failure
    return {"project": project, "path": str(path),
            "invalidates": ["project", "tree", "geometry", "mesh"]}


# There is no `/api/project/crow`. It opened the CROW staged-excavation case, back when
# a File menu item asked for it; both are gone. An example model is opened the way any
# model is -- `run examples/crow/crow.py` in the command box, through
# `/api/project/script` -- which works for every model rather than for the one somebody
# wired an endpoint to.


@app.post("/api/project/new")
async def new_project() -> dict:
    """Start over from an empty site -- what the toolbar's "New project" does.

    An empty project, not the demo model: what the server itself opens on. It lives
    here, not in the browser, so a client-side copy is not a second definition to keep
    in step with `app.seed.blank_project`.
    """
    project = store.new()
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.patch("/api/project/layers")
async def patch_layers(update: LayersUpdate) -> dict:
    current = store.get()
    payload = current.model_dump()
    payload["layers"] = [layer.model_dump() for layer in update.layers]
    if update.materials is not None:
        payload["materials"] = [material.model_dump() for material in update.materials]
    if update.boreholes is not None:
        payload["boreholes"] = [borehole.model_dump() for borehole in update.boreholes]
    if update.domain is not None:
        payload["domain"] = update.domain.model_dump()
    if update.custom_parts is not None:
        payload["custom_parts"] = [part.model_dump() for part in update.custom_parts]
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        # The layer objects validate individually in the request model; project-level
        # checks add material references, borehole coverage and stack continuity.
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.patch("/api/project/materials")
async def patch_materials(update: MaterialsUpdate) -> dict:
    """Replace the material library.

    Validating the whole project is the point: it is what refuses a material a
    layer still points at, so a delete in the editor cannot leave the model
    referencing something that no longer exists.
    """
    current = store.get()
    payload = current.model_dump()
    payload["materials"] = [material.model_dump() for material in update.materials]
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    # Soil colour comes from the assigned material (app/tessellate.py:129), so the
    # geometry has to be re-tessellated even though no shape changed.
    return {"project": project, "invalidates": ["project", "tree", "geometry"]}


@app.patch("/api/project/structures")
async def patch_structures(update: StructuresUpdate) -> dict:
    """Replace Structure-mode objects as one validated project transaction.

    One endpoint for every structure kind, so a sheet pile and the section it points at
    land in the same validated write: sending them separately would put the project
    through a state where the beam references a section that does not exist yet.
    """
    current = store.get()
    payload = current.model_dump()
    notes: list[str] = []
    payload["loads"] = [load.model_dump() for load in update.loads]
    if update.beam_sections is not None:
        payload["beam_sections"] = [s.model_dump() for s in update.beam_sections]
    if update.panel_sections is not None:
        payload["panel_sections"] = [s.model_dump() for s in update.panel_sections]
    if update.beams is not None:
        payload["beams"] = [beam.model_dump() for beam in update.beams]
    if update.anchor_sections is not None:
        payload["anchor_sections"] = [s.model_dump() for s in update.anchor_sections]
    if update.anchors is not None:
        payload["anchors"] = [anchor.model_dump() for anchor in update.anchors]
    if update.interface_sections is not None:
        payload["interface_sections"] = [s.model_dump() for s in update.interface_sections]
    if update.interfaces is not None:
        payload["interfaces"] = [i.model_dump() for i in update.interfaces]
    if update.normal_loads is not None:
        payload["normal_loads"] = [n.model_dump() for n in update.normal_loads]
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.patch("/api/project/dimension")
async def patch_dimension(update: DimensionUpdate) -> dict:
    """Switch between the solid model and the plane-strain x-y section.

    Everything downstream is invalidated, the model tree included: a part that does not
    cross the section plane is not in a 2D model at all, so the explorer has to be
    rebuilt rather than left showing rows that select nothing.
    """
    current = store.get()
    payload = current.model_dump()
    payload["dimension"] = update.dimension
    # An explicit offset replaces the stored one; omitted, going to 2D lets the Project
    # validator resolve the midpoint.
    payload["section_offset"] = update.section_offset
    # A load is the one thing that changes shape with the dimension: a pressure over a
    # footprint in the solid model is a pressure per metre run in the cut. Translated
    # here, at the single point the mode changes, so the tree, the geometry and the
    # deck all see the same pair. See app/loads.py for what is and is not translatable.
    notes: list[str] = []
    payload["loads"] = [load.model_dump()
                        for load in translate_loads(current, update.dimension, notes)]
    # A wall changes shape with the dimension the same way: a sheet pile in the section
    # is a panel swept between two levels in the solid model, which is what gives it a
    # plan footprint to edit. See app/walls.py for what is and is not translatable.
    beams, panel_sections = translate_walls(current, update.dimension, notes)
    payload["beams"] = [beam.model_dump() for beam in beams]
    payload["panel_sections"] = [section.model_dump() for section in panel_sections]
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    # `notes` is what the command log says about the loads that changed shape; the
    # frontend prints them under the mode-switch line (live/js/patches.js).
    return {"project": project, "notes": notes,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.delete("/api/project/custom_parts")
async def clear_custom_parts() -> dict:
    project = store.get()
    project.custom_parts = []
    store.put(project)
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.delete("/api/geometry/parts/{key}")
async def delete_geometry_part(key: str) -> dict:
    project = store.get()
    remaining = [p for p in project.custom_parts if p.key != key]
    if len(remaining) == len(project.custom_parts):
        raise HTTPException(status_code=404, detail=f"no custom part with key {key!r}")
    project.custom_parts = remaining
    store.put(project)
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}

@app.get("/api/geometry")
async def get_geometry() -> dict:
    project = store.get()
    try:
        return await gmsh_worker.run(gmsh_worker.geometry_job, project.model_dump_json())
    except GeometryError as failure:
        # Surfaced so the frontend can put it in the command log. An empty model would
        # otherwise be indistinguishable from a rendering bug.
        raise HTTPException(status_code=500, detail=str(failure)) from failure


@app.post("/api/geometry/import")
async def import_geometry(file: UploadFile = File(...)) -> dict:
    from app.schemas import CustomPart
    
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".step", ".stp", ".iges", ".igs", ".brep", ".stl", ".obj"):
        raise HTTPException(status_code=422, detail="Unsupported file extension. Use .step, .iges, .brep, .stl, or .obj.")
        
    fd, path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await file.read())
            
        res = await gmsh_worker.run(gmsh_worker.import_job, path, ext)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if os.path.exists(path):
            os.remove(path)
            
    project = store.get()
    
    idx = len([p for p in project.custom_parts if p.key.startswith("imported_")])
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

@app.post("/api/geometry/create")
async def create_geometry(recipe: dict) -> dict:
    from app.schemas import CustomPart
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

@app.post("/api/mesh")
async def generate_mesh(settings: MeshRequest) -> dict:
    project = store.get()
    unknown = sorted((set(settings.volume_keys or []) | set(settings.body_sizes))
                     - set(project.part_keys()))
    if unknown:
        raise HTTPException(status_code=422, detail="unknown mesh body key(s): " + ", ".join(unknown))
    try:
        return await gmsh_worker.run(
            gmsh_worker.mesh_job,
            project.model_dump_json(), settings.model_dump_json(),
        )
    except (GeometryError, MeshingError) as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure


@app.post("/api/mesh/labels")
async def mesh_labels(settings: MeshRequest) -> dict:
    """The node and element tables -- Kratos ID and where to draw it -- of the deck this
    project exports. A node's point is itself; an element's is its centroid.

    What the viewport's "Show labels" overlay draws from. Deliberately a route of its own
    rather than a field on `POST /api/mesh`: the numbering costs a full export pass
    (interface splitting included), and a mesh is generated far more often than its
    numbers are looked at.
    """
    project = store.get()
    unknown = sorted((set(settings.volume_keys or []) | set(settings.body_sizes))
                     - set(project.part_keys()))
    if unknown:
        raise HTTPException(status_code=422, detail="unknown mesh body key(s): " + ", ".join(unknown))
    try:
        return await gmsh_worker.run(
            gmsh_worker.mesh_labels_job,
            project.model_dump_json(), settings.model_dump_json(),
        )
    except (GeometryError, MeshingError, ExportError) as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure


@app.post("/api/export/mdpa")
async def export_mdpa(settings: ExportRequest) -> dict:
    """Mesh the project and return a Kratos deck as text, ready to be saved.

    Both files come back in one response so the client can write them side by side and
    put the exporter's warnings in the command log; gzip already covers the size.
    """
    project = store.get()
    unknown = sorted((set(settings.volume_keys or []) | set(settings.body_sizes))
                     - set(project.part_keys()))
    if unknown:
        raise HTTPException(status_code=422, detail="unknown mesh body key(s): " + ", ".join(unknown))
    try:
        return await gmsh_worker.run(
            gmsh_worker.export_job,
            project.model_dump_json(), settings.model_dump_json(),
        )
    except (GeometryError, MeshingError, ExportError) as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure


@app.post("/api/calculate")
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
    """
    project = store.get()
    unknown = sorted((set(settings.volume_keys or []) | set(settings.body_sizes))
                     - set(project.part_keys()))
    if unknown:
        raise HTTPException(status_code=422, detail="unknown mesh body key(s): " + ", ".join(unknown))
    try:
        export = await gmsh_worker.run(
            gmsh_worker.export_job,
            project.model_dump_json(),
            settings.model_copy(update={"include_materials": True}).model_dump_json(),
        )
    except (GeometryError, MeshingError, ExportError) as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure

    try:
        result = await asyncio.to_thread(calculate.run, export)
    except calculate.Busy as busy:
        raise HTTPException(status_code=409, detail=str(busy)) from busy
    except calculate.CalculationError as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure

    # The mesh the run was made from, said in the same breath as the run: the deck was
    # exported here, so this is the only place that can report both.
    return result | {"stats": export["stats"], "warnings": export["warnings"]}


@app.post("/api/import/mdpa")
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
    from app.mdpa_import import ImportError_, import_mdpa as parse

    ext = Path(file.filename or "").suffix.lower()
    if ext != ".mdpa":
        raise HTTPException(status_code=422, detail="Unsupported file extension. Use .mdpa.")

    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        model = parse(text)
    except ImportError_ as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure

    # A deck's node table is already the world frame in either dimension -- a 2D deck
    # is the x-y plane at z = 0, which is where a 2D model lives -- so nothing about
    # the open project is needed to place it.
    return model.to_dict()


# ── Static ──────────────────────────────────────────────────────────────────

@app.get("/")
async def index() -> FileResponse:
    live_index = LIVE / "index.html"
    return FileResponse(live_index if live_index.exists() else FROZEN / "index.html")


for folder in ("css", "js", "assets", "vendor"):
    app.mount(f"/{folder}", StaticFiles(directory=FROZEN / folder), name=folder)

if LIVE.exists():
    app.mount("/live", StaticFiles(directory=LIVE), name="live")
