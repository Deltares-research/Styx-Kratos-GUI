"""The Project routes: the open model, and every edit made to it.

An edit is validated as a whole project before it is stored (`common.validated`), so a
change that would leave the model inconsistent is refused field by field rather than
stored. Each answer names what the frontend has to refresh (`invalidates`).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.exceptions import RequestValidationError

from backend import store
from backend.routes.common import validated
from core import kratos_materials, phases as phase_model, units
from core.loads import translate as translate_loads
from core.schemas import (DimensionUpdate, LayersUpdate, MaterialsUpdate, PhasesUpdate, Project,
                          StructuresUpdate, UnitsUpdate, WaterUpdate)
from core.walls import translate as translate_walls

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
    it describes becomes the open model. See `core.script` for the three ways a script
    can hand one back, and for why this route is local-only by construction.
    """
    from core import script as script_module

    from core import deck as decks

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


# There is no endpoint that opens one particular model. A model is opened the way any
# model is -- `run <file.py>` in the command box, through `/api/project/script` -- which works for every model rather than for the one somebody
# wired an endpoint to.


@router.post("/api/project/new")
async def new_project() -> dict:
    """Start over from an empty site -- what the toolbar's "New project" does.

    An empty project, not the demo model: what the server itself opens on. It lives
    here, not in the browser, so a client-side copy is not a second definition to keep
    in step with `core.seed.blank_project`.
    """
    project = store.new()
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/layers")
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
    # The layer objects validate individually in the request model; project-level
    # checks add material references, borehole coverage and stack continuity.
    project = validated(payload)
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.put("/api/project/water")
async def put_water(update: WaterUpdate) -> dict:
    """Set the project's water level, or remove it with `{"water": null}`.

    Its own route because removing is the one edit `PATCH /api/project/layers` cannot
    express: there, an omitted `water` means "leave it alone". What the `water` command
    calls (frontend/js/patches.js).
    """
    payload = store.get().model_dump()
    payload["water"] = update.water.model_dump() if update.water is not None else None
    project = validated(payload)
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/materials")
async def patch_materials(update: MaterialsUpdate) -> dict:
    """Replace the material library.

    Validating the whole project is the point: it is what refuses a material a
    layer still points at, so a delete in the editor cannot leave the model
    referencing something that no longer exists.
    """
    current = store.get()
    payload = current.model_dump()
    payload["materials"] = [material.model_dump() for material in update.materials]
    project = validated(payload)
    store.put(project)
    # Soil colour comes from the assigned material (core/tessellate.py:129), so the
    # geometry has to be re-tessellated even though no shape changed.
    return {"project": project, "invalidates": ["project", "tree", "geometry"]}


@router.patch("/api/project/structures")
async def patch_structures(update: StructuresUpdate) -> dict:
    """Replace Structure-mode objects as one validated project transaction.

    One endpoint for every structure kind, so a sheet pile and the section it points at
    land in the same validated write: sending them separately would put the project
    through a state where the beam references a section that does not exist yet.
    """
    current = store.get()
    payload = current.model_dump()
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
    project = validated(payload)
    store.put(project)
    return {"project": project, "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/phases")
async def patch_phases(update: PhasesUpdate) -> dict:
    """Replace the construction sequence.

    Two validations, and they are different things. The schema's own checks run first
    -- one root, no cycles, no part both activated and deactivated in one phase, every
    key a key the model has -- and reject the payload field by field. Then the tree has
    to *linearise*: Kratos runs one flat `execution_list`, so two phases starting from
    the same parent have no order to run in.

    `linearise` is deliberately not a schema validator (see `core.phases.PhaseError`):
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
    project = validated(payload)
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
    """A deck's phases are its stages, read from it (`core.deck`); the deck is what
    Calculate runs, so an edit made here would show in the panel and change nothing
    that is calculated."""
    if project.deck is not None:
        raise HTTPException(status_code=422, detail=(
            f"The phases of {project.name} are the stages of its Kratos deck "
            f"({project.deck.parameters} in {project.deck.directory}), shown as they "
            f"are. Edit the deck to change them, then run its script again."))


@router.post("/api/project/phases/defaults")
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
    project = validated(payload)
    store.put(project)
    return {"project": project, "invalidates": ["project"]}


@router.patch("/api/project/dimension")
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
    # deck all see the same pair. See core/loads.py for what is and is not translatable.
    notes: list[str] = []
    payload["loads"] = [load.model_dump()
                        for load in translate_loads(current, update.dimension, notes,
                                                    update.section_offset)]
    # A wall changes shape with the dimension the same way: a sheet pile in the section
    # is a panel swept between two levels in the solid model, which is what gives it a
    # plan footprint to edit. See core/walls.py for what is and is not translatable.
    beams, panel_sections = translate_walls(current, update.dimension, notes)
    payload["beams"] = [beam.model_dump() for beam in beams]
    payload["panel_sections"] = [section.model_dump() for section in panel_sections]
    # A soil law is written for one dimension; the pairs this application knows go
    # across with the model, and any other is left as the user typed it, said out loud.
    payload["materials"] = kratos_materials.translate_laws(
        payload["materials"], update.dimension, notes)
    project = validated(payload)
    store.put(project)
    # `notes` is what the command log says about the loads that changed shape; the
    # frontend prints them under the mode-switch line (frontend/js/patches.js).
    return {"project": project, "notes": notes,
            "invalidates": ["project", "tree", "geometry", "mesh"]}


@router.patch("/api/project/units")
def patch_units(update: UnitsUpdate) -> dict:
    """Re-express the whole project in another unit system (`core/units.py`).

    The one place values are converted: from here on the project, its deck and its
    results are all in the new system. A variable whose dimension is not known here is
    kept as typed and named in `notes`, for the user to convert.
    """
    current = store.get()
    payload, notes = units.convert_project(current.model_dump(mode="json"),
                                           update.unit_system)
    project = validated(payload)
    store.put(project)
    return {"project": project, "notes": notes, "invalidates": ["project", "tree"]}
