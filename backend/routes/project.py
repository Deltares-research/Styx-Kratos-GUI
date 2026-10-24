"""The Project routes: the open model, and every edit made to it.

The edits themselves are `core.session`'s, the same functions the command line makes
them with; a route reads the store, makes the edit, and stores what comes back. A change
that would leave the model inconsistent is refused field by field rather than stored
(`common.refusals`). Each answer names what the frontend has to refresh (`invalidates`).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError

from backend import store
from backend.routes.common import refusals
from core import session
from core.model import phases
from core.model.schemas import (BoreholeCreate, ConditionsUpdate, DimensionUpdate, LayersUpdate,
                                MaterialsUpdate, PhasesUpdate, Project, StructuresUpdate,
                                UnitsUpdate, WaterUpdate)

router = APIRouter()


@router.get("/api/project")
async def get_project() -> Project:
    return store.get()


@router.put("/api/project")
async def put_project(project: Project) -> Project:
    return store.put(project)


@router.post("/api/project/reset")
async def reset_project() -> dict:
    """Restore the seed (demo) model."""
    project = store.reset()
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.post("/api/project/script")
def run_script(request: dict) -> dict:
    """Build the model by running a Python file: the command line's `run <file.py>`.

    The file is executed here, in the server's own interpreter, and whatever `Project`
    it describes becomes the open model. See `core.scripting` for the three ways a script
    can hand one back, and for why this route is local-only by construction.
    """
    from core import scripting

    from core.kratos import external_deck

    path = (request or {}).get("path")
    if not path:
        raise HTTPException(status_code=422, detail="run needs a path to a .py file")
    try:
        project = scripting.load_project(path)
        # A deck case comes with its mesh -- there is nothing to generate -- so it goes
        # back in the same answer, and the client shows it instead of meshing.
        mesh = external_deck.preview(project.deck) if project.deck else None
    except (scripting.ScriptError, external_deck.DeckError) as failure:
        # 400, not 500: the file is the caller's, and every one of these messages is
        # written to be read by whoever typed the command.
        raise HTTPException(status_code=400, detail=str(failure)) from failure
    store.put(project)
    return {"project": project, "path": str(path), "mesh": mesh,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.post("/api/project/script/save")
def save_script(request: dict) -> dict:
    """Write the open model as a model script: the command line's `script <file.py>`.

    The file builds the model again (`core.model.script_writer`): `run <file.py>` opens
    it, and `python <file.py> --out deck/` writes its deck. A file that is there is
    replaced only with `force`. Local-only for the same reason `run` is: it writes where
    it is told to, with the user's own privileges.
    """
    path = (request or {}).get("path")
    if not path:
        raise HTTPException(status_code=422, detail="script needs a path to a .py file")
    with refusals():
        written = session.write_script(store.get(), path, force=bool(request.get("force")))
    return {"path": str(written)}


# There is no endpoint that opens one particular model. A model is opened the way any
# model is -- `run <file.py>` in the command box, through `/api/project/script` -- which works for every model rather than for the one somebody
# wired an endpoint to.


@router.post("/api/project/new")
async def new_project() -> dict:
    """Start over from an empty site -- what the toolbar's "New project" does.

    An empty project, not the demo model: what the server itself opens on. It lives
    here, not in the browser, so a client-side copy is not a second definition to keep
    in step with `core.model.templates.blank_project`.
    """
    project = store.new()
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/layers")
async def patch_layers(update: LayersUpdate) -> dict:
    with refusals():
        project = session.replace_layers(store.get(), update)
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.post("/api/project/boreholes")
async def add_borehole(new: BoreholeCreate) -> dict:
    """Add one borehole, with every layer's levels there copied from the last one.

    `session.add_borehole` makes it, the same function `kratos-cli borehole add` calls,
    so the GUI's Create borehole and its `borehole` command give the borehole the
    terminal would: the same id, name, position and levels. The new one is the last in
    `project.boreholes`.
    """
    with refusals():
        project = session.add_borehole(store.get(), **new.model_dump())
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.put("/api/project/water")
async def put_water(update: WaterUpdate) -> dict:
    """Set the project's water level, or remove it with `{"water": null}`.

    Its own route because removing is the one edit `PATCH /api/project/layers` cannot
    express: there, an omitted `water` means "leave it alone". What the `water` command
    calls (frontend/js/patches.js).
    """
    with refusals():
        project = session.set_water(store.get(), update)
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/materials")
async def patch_materials(update: MaterialsUpdate) -> dict:
    """Replace the material library; a material a layer still points at is refused."""
    with refusals():
        project = session.replace_materials(store.get(), update)
    store.put(project)
    # Soil colour comes from the assigned material (`_colors_by_volume` in
    # core/geometry/tessellation.py), so the geometry has to be re-tessellated even though
    # no shape changed.
    return {"project": project, "invalidates": ["project", "tree", "geometry"]}


@router.patch("/api/project/structures")
async def patch_structures(update: StructuresUpdate) -> dict:
    """Replace Structure-mode objects as one validated project transaction
    (`session.replace_structures`)."""
    with refusals():
        project = session.replace_structures(store.get(), update)
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/conditions")
async def patch_conditions(update: ConditionsUpdate) -> dict:
    """Replace the boundary conditions as one list, and set gravity
    (`session.replace_conditions`); a field left out stays as it is. What the GUI's
    boundary conditions dialog, its explorer rows and the `boundary` and `gravity`
    commands send (frontend/js/boundary-conditions.js)."""
    with refusals():
        project = session.replace_conditions(store.get(), update)
    store.put(project)
    # A condition on a drawn line or point is embedded in the section, so the mesh
    # changes with it.
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/phases")
async def patch_phases(update: PhasesUpdate) -> dict:
    """Replace the construction sequence (`session.replace_phases`).

    A tree that does not linearise is answered like a field that does not validate --
    a 422 on `phases`, naming the phases that branch -- because to the editor it is
    one: the sequence it sent cannot be stored.

    Only `project` is invalidated. A phase list changes the deck and the panel, not the
    geometry or the mesh: every part it names already exists, which is what makes a
    key valid in the first place.
    """
    try:
        with refusals():
            project = session.replace_phases(store.get(), update)
    except phases.PhaseError as failure:
        raise RequestValidationError([{
            "type": "value_error", "loc": ("body", "phases"), "msg": str(failure),
            "input": [phase.model_dump() for phase in update.phases],
        }]) from failure
    store.put(project)
    return {"project": project, "invalidates": ["project"]}


@router.post("/api/project/phases/defaults")
async def seed_default_phases() -> dict:
    """What "Create default phases" gives: the initial stage, then the null step.

    `session.default_phases` makes it; this endpoint is only the way the GUI reaches it.
    It replaces whatever is there: it is the way back out of a broken sequence.
    """
    with refusals():
        project = session.default_phases(store.get())
    store.put(project)
    return {"project": project, "invalidates": ["project"]}


@router.patch("/api/project/dimension")
async def patch_dimension(update: DimensionUpdate) -> dict:
    """Switch between the solid model and the plane-strain x-y section.

    Everything downstream is invalidated, the model tree included: a part that does not
    cross the section plane is not in a 2D model at all, so the explorer has to be
    rebuilt rather than left showing rows that select nothing.
    """
    with refusals():
        project, notes = session.set_dimension(store.get(), update)
    store.put(project)
    # `notes` is what the command log says about the loads that changed shape; the
    # frontend prints them under the mode-switch line (frontend/js/patches.js).
    return {"project": project, "notes": notes,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/units")
def patch_units(update: UnitsUpdate) -> dict:
    """Re-express the whole project in another unit system (`session.set_units`).

    A variable whose dimension is not known is kept as typed and named in `notes`, for
    the user to convert.
    """
    with refusals():
        project, notes = session.set_units(store.get(), update)
    store.put(project)
    return {"project": project, "notes": notes, "invalidates": ["project", "tree"]}
