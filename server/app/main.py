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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
import os
import tempfile
from urllib.parse import urlsplit

from app import (calculate, gmsh_worker, kratos_materials, phases as phase_model, results,
                 store, units)
from app.loads import translate as translate_loads
from app.walls import translate as translate_walls
from app.build import GeometryError
from app.importer import ImportRefused
from app.kratos import ExportError
from app.launcher import ALLOWED_HOSTS_ENV
from app.meshing import MeshingError
from app.schemas import (DimensionUpdate, ExportRequest, LayersUpdate, MaterialsUpdate, UnitsUpdate,
                         MeshRequest, PhasesUpdate, Project, StructuresUpdate,
                         WaterUpdate)

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


@app.exception_handler(gmsh_worker.WorkerCrashed)
async def worker_crashed(_request, failure: gmsh_worker.WorkerCrashed):
    """Any route that reaches gmsh: the request that crashed the worker fails with a reason
    the command log can show, and the worker is already being replaced for the next one."""
    return JSONResponse(status_code=500, content={"detail": str(failure)})

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


LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def allowed_hosts() -> set[str]:
    """The names this server answers to: loopback, plus `ALLOWED_HOSTS_ENV` -- read per
    request, so it can be set without a code change and tested without a restart."""
    extra = os.environ.get(ALLOWED_HOSTS_ENV, "")
    return set(LOOPBACK_HOSTS) | {h.strip().lower() for h in extra.split(",") if h.strip()}


def _host_name(netloc: str) -> str:
    """`host[:port]` or `[v6]:port`, without the port, lower-cased."""
    netloc = netloc.strip().lower()
    if netloc.startswith("["):
        return netloc[1:netloc.find("]")] if "]" in netloc else netloc
    return netloc.rsplit(":", 1)[0] if netloc.count(":") == 1 else netloc


@app.middleware("http")
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
    if _host_name(request.headers.get("host", "")) not in allowed:
        return JSONResponse(status_code=400, content={"detail": (
            f"Refused: this server answers to {', '.join(sorted(allowed))} as its host, "
            f"not {request.headers.get('host', '')!r}. To serve it under another name, "
            f"list that name in {ALLOWED_HOSTS_ENV}.")})
    origin = request.headers.get("origin")
    if origin is not None:
        parsed = urlsplit(origin)
        if not parsed.scheme or _host_name(parsed.netloc) not in allowed:
            return JSONResponse(status_code=403, content={"detail": (
                f"Refused: a request from another site (origin {origin!r}) may not use "
                "this server.")})
    return await call_next(request)


MAX_UPLOAD_BYTES = 256 * 2**20
"""The largest file an upload route reads. A real deck is a few megabytes (Eemdijk's mesh is
about 3 MB); this exists so a runaway file is a refusal, not an out-of-memory server."""


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=(
            f"{file.filename} is larger than the {MAX_UPLOAD_BYTES / 2**20:g} MB this "
            "server reads in one upload."))
    return data


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
def run_script(request: dict) -> dict:
    """Build the model by running a Python file: the command line's `run <file.py>`.

    The file is executed here, in the server's own interpreter, and whatever `Project`
    it describes becomes the open model. See `app.script` for the three ways a script
    can hand one back, and for why this route is local-only by construction.
    """
    from app import script as script_module

    from app import deck as decks

    path = (request or {}).get("path")
    if not path:
        raise HTTPException(status_code=422, detail="run needs a path to a .py file")
    try:
        project = script_module.load_project(path)
        # A deck case comes with its mesh -- there is nothing to generate -- so it goes
        # back in the same answer, and the client shows it instead of meshing.
        mesh = decks.preview(project.deck) if project.deck else None
    except (script_module.ScriptError, decks.DeckError) as failure:
        # 400, not 500: the file is the caller's, and every one of these messages is
        # written to be read by whoever typed the command.
        raise HTTPException(status_code=400, detail=str(failure)) from failure
    store.put(project)
    return {"project": project, "path": str(path), "mesh": mesh,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


def _not_for_a_deck(project: Project, what: str) -> None:
    """Refuse to mesh or export a project that is a deck already (`app.deck`).

    Everything but its deck is the empty site the schema requires, so going ahead would
    mesh nothing and answer as though that were the model.
    """
    if project.deck is not None:
        raise HTTPException(status_code=422, detail=(
            f"{project.name} is a Kratos deck ({project.deck.parameters} in "
            f"{project.deck.directory}), so it is not {what} here: its mesh is the "
            f"deck's own. Calculate runs it as it is."))


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
    if update.water is not None:
        payload["water"] = update.water.model_dump()
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


@app.put("/api/project/water")
async def put_water(update: WaterUpdate) -> dict:
    """Set the project's water level, or remove it with `{"water": null}`.

    Its own route because removing is the one edit `PATCH /api/project/layers` cannot
    express: there, an omitted `water` means "leave it alone". What the `water` command
    calls (live/js/patches.js).
    """
    payload = store.get().model_dump()
    payload["water"] = update.water.model_dump() if update.water is not None else None
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
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


@app.patch("/api/project/phases")
async def patch_phases(update: PhasesUpdate) -> dict:
    """Replace the construction sequence.

    Two validations, and they are different things. The schema's own checks run first
    -- one root, no cycles, no part both activated and deactivated in one phase, every
    key a key the model has -- and reject the payload field by field. Then the tree has
    to *linearise*: Kratos runs one flat `execution_list`, so two phases starting from
    the same parent have no order to run in.

    `linearise` is deliberately not a schema validator (see `app.phases.PhaseError`):
    a branch is a legitimate thing to have half-built in an editor, and refusing it in
    `Project` would make it impossible to type. It is refused *here* instead of at
    export because this is where the user can still see what they did -- the message
    names the phases that branch.

    Only `project` is invalidated. A phase list changes the deck and the panel, not the
    geometry or the mesh: every part it names already exists, which is what makes a
    key valid in the first place.
    """
    _phases_of_a_deck_are_read_only(store.get())
    payload = store.get().model_dump()
    payload["phases"] = [phase.model_dump() for phase in update.phases]
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    try:
        phase_model.linearise(project)
    except phase_model.PhaseError as failure:
        raise RequestValidationError([{
            "type": "value_error", "loc": ("body", "phases"), "msg": str(failure),
            "input": payload["phases"],
        }]) from failure
    store.put(project)
    return {"project": project, "invalidates": ["project"]}


def _phases_of_a_deck_are_read_only(project: Project) -> None:
    """A deck's phases are its stages, read from it (`app.deck`); the deck is what
    Calculate runs, so an edit made here would show in the panel and change nothing
    that is calculated."""
    if project.deck is not None:
        raise HTTPException(status_code=422, detail=(
            f"The phases of {project.name} are the stages of its Kratos deck "
            f"({project.deck.parameters} in {project.deck.directory}), shown as they "
            f"are. Edit the deck to change them, then run its script again."))


@app.post("/api/project/phases/defaults")
async def seed_default_phases() -> dict:
    """What "Create default phases" gives: the initial stage, then the null step.

    `phases.default_phases` is the authority on it; every further phase is the user's to
    add. This endpoint is only the way the GUI reaches it.

    It replaces whatever is there rather than refusing when phases already exist. That
    is the point: it is the way back out of a sequence the user has broken, and a
    "reset to defaults" that declines to reset is not one.
    """
    current = store.get()
    _phases_of_a_deck_are_read_only(current)
    payload = current.model_dump()
    payload["phases"] = [phase.model_dump()
                         for phase in phase_model.default_phases(current)]
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    return {"project": project, "invalidates": ["project"]}


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
                        for load in translate_loads(current, update.dimension, notes,
                                                    update.section_offset)]
    # A wall changes shape with the dimension the same way: a sheet pile in the section
    # is a panel swept between two levels in the solid model, which is what gives it a
    # plan footprint to edit. See app/walls.py for what is and is not translatable.
    beams, panel_sections = translate_walls(current, update.dimension, notes)
    payload["beams"] = [beam.model_dump() for beam in beams]
    payload["panel_sections"] = [section.model_dump() for section in panel_sections]
    # A soil law is written for one dimension; the pairs this application knows go
    # across with the model, and any other is left as the user typed it, said out loud.
    payload["materials"] = kratos_materials.translate_laws(
        payload["materials"], update.dimension, notes)
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    # `notes` is what the command log says about the loads that changed shape; the
    # frontend prints them under the mode-switch line (live/js/patches.js).
    return {"project": project, "notes": notes,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.patch("/api/project/units")
def patch_units(update: UnitsUpdate) -> dict:
    """Re-express the whole project in another unit system (`app/units.py`).

    The one place values are converted: from here on the project, its deck and its
    results are all in the new system. A variable whose dimension is not known here is
    kept as typed and named in `notes`, for the user to convert.
    """
    current = store.get()
    payload, notes = units.convert_project(current.model_dump(mode="json"),
                                           update.unit_system)
    try:
        project = Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure
    store.put(project)
    return {"project": project, "notes": notes, "invalidates": ["project", "tree"]}


@app.delete("/api/project/custom_parts")
async def clear_custom_parts() -> dict:
    project = store.get()
    store.put(_without_custom_parts(project, [p.key for p in project.custom_parts]))
    return {"ok": True, "invalidates": ["project", "tree", "geometry", "mesh"]}


@app.delete("/api/geometry/parts/{key}")
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
    try:
        return Project.model_validate(payload)
    except ValidationError as failure:
        raise RequestValidationError(failure.errors()) from failure

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
        
    data = await _read_upload(file)
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
    except ValueError as refused:
        # `app.creator` raises ValueError for a recipe it cannot build -- an unknown kind,
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

@app.post("/api/mesh")
async def generate_mesh(settings: MeshRequest) -> dict:
    project = store.get()
    _not_for_a_deck(project, "meshed")
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
    _not_for_a_deck(project, "meshed")
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


@app.post("/api/mesh/node-parts")
async def mesh_node_parts(settings: MeshRequest) -> dict:
    """Which SubModelParts each node of this project's deck is in: the node table and,
    per part, the nodes it names -- in the same Kratos numbering `/api/mesh/labels`
    puts on the mesh. What `node <id>` and the viewport's node inspection read
    (live/js/node-parts.js). A route of its own for the reason the labels have one: it
    costs a full export pass, and is asked for far less often than a mesh.
    """
    project = store.get()
    _not_for_a_deck(project, "meshed")
    unknown = sorted((set(settings.volume_keys or []) | set(settings.body_sizes))
                     - set(project.part_keys()))
    if unknown:
        raise HTTPException(status_code=422, detail="unknown mesh body key(s): " + ", ".join(unknown))
    try:
        return await gmsh_worker.run(
            gmsh_worker.node_parts_job,
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
    _not_for_a_deck(project, "exported")
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

    A project that is a deck already (`app.deck`) skips the export: its own files are
    copied into the run directory and run as they are.
    """
    project = store.get()
    if project.deck is not None:
        return await _calculate_deck(project)
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
    # exported here, so this is the only place that can report both. `run` is the
    # directory's bare name, which is the id every `/api/results` route takes -- sent
    # rather than left to the client to split off the path, because the two platforms
    # spell a path separator differently and the client would have to know which.
    return result | {"stats": export["stats"], "warnings": export["warnings"],
                     "run": Path(result["directory"]).name}


async def _calculate_deck(project: Project) -> dict:
    from app import deck as decks

    try:
        stats = decks.stats(project.deck)
        result = await asyncio.to_thread(calculate.run_deck, project.deck)
    except decks.DeckError as failure:
        raise HTTPException(status_code=400, detail=str(failure)) from failure
    except calculate.Busy as busy:
        raise HTTPException(status_code=409, detail=str(busy)) from busy
    except calculate.CalculationError as failure:
        raise HTTPException(status_code=500, detail=str(failure)) from failure
    return result | {"stats": stats, "warnings": [],
                     "run": Path(result["directory"]).name}


# ── Results ─────────────────────────────────────────────────────────────────
#
# Reading back what a calculation left behind. The registry only *finds* things in
# this milestone -- which runs exist, which stages each got through, which files are
# in it; parsing a result is the next one (`plan/postprocessing-plan.md`, P1).


def _results_error(failure: results.ResultsError) -> HTTPException:
    """404 for something that is not there, 400 for something that may not be asked.

    The distinction matters for exactly one case: a filename that tries to climb out
    of the run directory is refused as a bad request whether or not it names something
    real, so the answer cannot be used to find out what is on the machine.
    """
    status = 400 if isinstance(failure, results.UnsafeName) else 404
    return HTTPException(status_code=status, detail=str(failure))


@app.get("/api/results/runs")
def results_runs() -> dict:
    """Every run on this machine, newest first. Cheap: names and sizes, no parsing."""
    return {"runs": results.runs(), "root": str(calculate.runs_root())}


@app.get("/api/results/runs/{run_id}")
def results_run(run_id: str) -> dict:
    try:
        return results.describe(run_id)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/stages/{index}/fields")
def results_stage_fields(run_id: str, index: int) -> dict:
    """What this stage can be asked to show.

    Derived from the file, never from a list in the source: a variable Kratos declined
    to write -- or wrote an empty block for, because the element does not implement it
    -- costs one missing menu entry and breaks nothing. See `app.result_fields`.
    """
    try:
        return results.stage_fields(run_id, index)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/stages/{index}/mesh")
def results_stage_mesh(run_id: str, index: int) -> dict:
    """The stage's mesh as drawable buffers, one section per named part.

    Vertex *i* of a section is the deck's node `node_ids[i]`, at
    `positions[3i..3i+2]`. That correspondence is what lets a field -- which comes back
    keyed by node id -- become a vertex-colour buffer without a second request.
    """
    try:
        return results.stage_geometry(run_id, index)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/stages/{index}/displacement")
def results_stage_displacement(run_id: str, index: int) -> dict:
    """The displacement vectors this stage's mesh is deformed by.

    Its own route because it is the one quantity the viewer needs all three components
    of; everything in the field catalogue derives a single number.
    """
    try:
        return results.stage_displacement(run_id, index)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/stages/{index}/at/{node}")
def results_stage_at(run_id: str, index: int, node: int) -> dict:
    """Every field of this stage at one node, in one request.

    `results at <id>` is how a number gets checked against a hand calculation without
    leaving the app, and doing it a field at a time would be twenty-odd round trips.
    """
    from app import result_fields

    try:
        return results.stage_at_node(run_id, index, node)
    except result_fields.UnknownField as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/stages/{index}/parts")
def results_stage_parts(run_id: str, index: int) -> dict:
    """The deck's named parts as this stage saw them, and which were live in it."""
    try:
        return results.stage_parts(run_id, index)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/stages/{index}/field/{name}")
def results_stage_field(run_id: str, index: int, name: str,
                              location: str = "nodes") -> dict:
    """One field: the ids it is defined on, the numbers on them, and their range.

    The range travels with the values so that a colour legend and the colours it
    explains can never be computed from two different things.
    """
    from app import result_fields

    try:
        return results.stage_field(run_id, index, name, location)
    except result_fields.UnknownField as failure:
        # 422 rather than 404: the run and the stage are both there, and what is wrong
        # is the question -- a field this stage does not carry, or a location it
        # cannot be drawn at.
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/members")
def results_members(run_id: str) -> dict:
    """The structural members this run wrote curves for -- the wall, its interface --
    with the stages each has and the quantities each can be plotted for."""
    try:
        return results.stage_members(run_id)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/members/{member}/{quantity}")
def results_member_plot(run_id: str, member: str, quantity: str) -> dict:
    """One quantity along one member, a curve per stage: what the plot window draws.

    422 for a quantity this member does not carry, like an unknown field: the run and
    the member are there, and what is wrong is the question.
    """
    from app import result_members

    try:
        return results.member_profiles(run_id, member, quantity)
    except result_members.UnknownQuantity as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure
    except results.ResultsError as failure:
        raise _results_error(failure) from failure


@app.get("/api/results/runs/{run_id}/files/{name}")
def results_file(run_id: str, name: str) -> FileResponse:
    """One file of one run, as a download.

    The first route in this project that opens a file the caller named. Every check
    is in `results.file_path`, which refuses anything that is not a plain filename in
    that one flat directory -- see its docstring for why the check is spelled out
    rather than left to `Path`.
    """
    try:
        path = results.file_path(run_id, name)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure
    # `media_type` is not sniffed: a .post.res is text and a .mdpa is text, but both
    # are megabytes nobody wants rendered in a tab. Everything here is a download.
    return FileResponse(path, filename=path.name,
                        media_type="application/octet-stream")


@app.get("/api/results/runs/{run_id}/archive")
def results_archive(run_id: str) -> Response:
    """The whole run directory as one zip -- the deck, the results and the log.

    Server-side rather than zipped in the browser from `live/js/zip.js`: the client
    would have to fetch every file first, which is the same megabytes twice over and
    one request per file, to produce an archive of what the server already has laid
    out in a directory.
    """
    try:
        buffer = results.archive(run_id)
    except results.ResultsError as failure:
        raise _results_error(failure) from failure
    return Response(
        content=buffer.getvalue(), media_type="application/zip",
        headers={"content-disposition": f'attachment; filename="{run_id}.zip"'})


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

    text = (await _read_upload(file)).decode("utf-8", errors="replace")

    # A deck's node table is already the world frame in either dimension -- a 2D deck
    # is the x-y plane at z = 0, which is where a 2D model lives -- so nothing about
    # the open project is needed to place it.
    #
    # `node_parts` is what lets the preview answer "which SubModelParts is this node
    # in" when a node is clicked (live/js/node-parts.js).
    from app import node_parts

    def preview() -> dict:
        model = parse(text)
        return {**model.to_dict(), "node_parts": node_parts.of_model(model)}

    try:
        # Off the event loop: a real deck is megabytes, seconds of parsing.
        return await asyncio.to_thread(preview)
    except ImportError_ as failure:
        raise HTTPException(status_code=422, detail=str(failure)) from failure


# ── Static ──────────────────────────────────────────────────────────────────

@app.get("/")
async def index() -> FileResponse:
    live_index = LIVE / "index.html"
    return FileResponse(live_index if live_index.exists() else FROZEN / "index.html")


for folder in ("css", "js", "assets", "vendor"):
    app.mount(f"/{folder}", StaticFiles(directory=FROZEN / folder), name=folder)

if LIVE.exists():
    app.mount("/live", StaticFiles(directory=LIVE), name="live")
