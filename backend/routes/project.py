"""The Project routes: the open model, and every edit made to it.

The edits themselves are `core.session`'s, the same functions the command line makes
them with; a route reads the store, makes the edit, and stores what comes back. A change
that would leave the model inconsistent is refused field by field rather than stored
(`common.refusals`). Each answer names what the frontend has to refresh (`invalidates`).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError

from backend import store
from backend.routes.common import refusals, stored
from core import session
from core.model import migration, stages
from core.model.schemas import (BodyUpdate, ConditionsUpdate, DimensionUpdate, DomainUpdate,
                                LayersUpdate,
                                LinesUpdate, MaterialsUpdate,
                                StagesUpdate, Project, StructuresUpdate, UnitsUpdate,
                                WaterUpdate)

router = APIRouter()


@router.get("/api/project")
async def get_project() -> Project:
    return store.get()


@router.put("/api/project")
async def put_project(project: Project) -> Project:
    """Replace the model with the one the GUI opened or edited. A file opened on another
    computer names .brep files that are not here; its drawn parts are built again from
    their recipes (`scripting.with_solids`), off the event loop."""
    from core import scripting

    return store.put(await asyncio.to_thread(scripting.with_solids, project, False))


@router.post("/api/project/open")
async def open_project(document: dict) -> dict:
    """Open a project file the GUI read: what `PUT /api/project` does with it, and the
    notes on what opening it changes about its calculation (`migration.notes`), for the
    command log. The document is taken as it is in the file, as only the old shape says
    what the conversion loses; it is refused as `PUT` refuses it, field by field."""
    from pydantic import ValidationError

    from core import scripting

    try:
        project = Project.model_validate(document)
    except ValidationError as failure:
        raise RequestValidationError([
            {**error, "loc": ("body", *error["loc"])}
            for error in failure.errors(include_url=False, include_context=False)
        ]) from failure
    project = store.put(await asyncio.to_thread(scripting.with_solids, project, False))
    return {"project": project, "notes": migration.notes(document),
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.post("/api/project/migration-notes")
def migration_notes(document: dict) -> dict:
    """What opening `document`, a project file as saved, changes in its deck
    (`migration.notes`), without opening it. The GUI's Open gets them from
    `/api/project/open` instead, in the same request that takes the file."""
    return {"notes": migration.notes(document)}


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
    return stored(project) | {"invalidates": ["project", "tree", "geometry", "mesh"]}


@router.put("/api/project/water")
async def put_water(update: WaterUpdate) -> dict:
    """Set the project's water level, or remove it with `{"water": null}`.

    Its own route because removing is the one edit `PATCH /api/project/layers` cannot
    express: there, an omitted `water` means "leave it alone". What the `water` command
    calls (frontend/js/patches.js).
    """
    with refusals():
        project = session.set_water(store.get(), update)
    return stored(project) | {"invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/materials")
async def patch_materials(update: MaterialsUpdate) -> dict:
    """Replace the material library; a material a layer still points at is refused."""
    with refusals():
        project = session.replace_materials(store.get(), update)
    # Soil colour comes from the assigned material (`_colors_by_volume` in
    # core/geometry/tessellation.py), so the geometry has to be re-tessellated even though
    # no shape changed.
    return stored(project) | {"invalidates": ["project", "tree", "geometry"]}


@router.patch("/api/project/lines")
async def patch_lines(update: LinesUpdate) -> dict:
    """Replace the lines that split the soil (`session.replace_lines`): what the GUI's Line
    window sends."""
    with refusals():
        project = session.replace_lines(store.get(), update)
    return stored(project) | {"invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/bodies/{key}")
async def patch_body(key: str, update: BodyUpdate) -> dict:
    """A soil body's name or material (`session.update_body`); a field left out stays."""
    fields = {("material" if field == "mat" else field): getattr(update, field)
              for field in update.model_fields_set}
    with refusals():
        project = session.update_body(store.get(), key, **fields)
    return stored(project) | {"invalidates": ["project", "tree", "geometry"]}


@router.delete("/api/project/bodies/{key}")
async def delete_body(key: str) -> dict:
    """Delete one soil body a line cut off (`session.remove_body`): the soil there becomes
    a void, and the rest of its layer or soil surface stays."""
    with refusals():
        project = session.remove_body(store.get(), key)
    return stored(project) | {"invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/structures")
async def patch_structures(update: StructuresUpdate) -> dict:
    """Replace Structure-mode objects as one validated project transaction
    (`session.replace_structures`)."""
    with refusals():
        project = session.replace_structures(store.get(), update)
    return stored(project) | {"invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/conditions")
async def patch_conditions(update: ConditionsUpdate) -> dict:
    """Replace the boundary conditions as one list (`session.replace_conditions`).
    What the GUI's boundary conditions dialog, its explorer rows and the `boundary`
    command send (frontend/js/boundary-conditions.js). The stages may come with them, as
    `patch_stages` takes them."""
    try:
        with refusals():
            project = session.replace_conditions(store.get(), update)
    except stages.StageError as failure:
        raise RequestValidationError([{
            "type": "value_error", "loc": ("body", "stages"), "msg": str(failure),
            "input": [stage.model_dump() for stage in update.stages or []],
        }]) from failure
    # A condition on a drawn line or point is embedded in the section, so the mesh
    # changes with it.
    return stored(project) | {"invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/stages")
@router.patch("/api/project/phases", include_in_schema=False, deprecated=True)
async def patch_stages(update: StagesUpdate) -> dict:
    """Replace the construction sequence (`session.replace_stages`).

    A tree that does not linearise is answered like a field that does not validate --
    a 422 on `stages`, naming the stages that branch -- because to the editor it is
    one: the sequence it sent cannot be stored.

    Only `project` is invalidated. A stage list changes the deck and the panel, not the
    geometry or the mesh: every part it names already exists, which is what makes a
    key valid in the first place.
    """
    try:
        with refusals():
            project = session.replace_stages(store.get(), update)
    except stages.StageError as failure:
        raise RequestValidationError([{
            "type": "value_error", "loc": ("body", "stages"), "msg": str(failure),
            "input": [stage.model_dump() for stage in update.stages],
        }]) from failure
    return stored(project) | {"invalidates": ["project"]}


@router.patch("/api/project/dimension")
async def patch_dimension(update: DimensionUpdate) -> dict:
    """Switch between the solid model and the plane-strain x-y section.

    Everything downstream is invalidated, the model tree included: a part that does not
    cross the section plane is not in a 2D model at all, so the explorer has to be
    rebuilt rather than left showing rows that select nothing.
    """
    with refusals():
        project, notes = session.set_dimension(store.get(), update)
    # `notes` is what the command log says about the loads that changed shape; the
    # frontend prints them under the mode-switch line (frontend/js/patches.js).
    return stored(project) | {"notes": notes,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/domain")
async def patch_domain(update: DomainUpdate) -> dict:
    """The model's extents, as `kratos-cli domain --x --y --z` sets them
    (`session.set_domain`): File > Project properties… in the GUI. A new bottom or top
    moves the bottom of the last layer or the top of the first with it."""
    with refusals():
        project, notes = session.set_domain(store.get(), x=update.x, y=update.y, z=update.z)
    return stored(project) | {"notes": notes,
                              "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/units")
def patch_units(update: UnitsUpdate) -> dict:
    """Re-express the whole project in another unit system (`session.set_units`).

    A variable whose dimension is not known is kept as typed and named in `notes`, for
    the user to convert.
    """
    with refusals():
        project, notes = session.set_units(store.get(), update)
    return stored(project) | {"notes": notes, "invalidates": ["project", "tree"]}
