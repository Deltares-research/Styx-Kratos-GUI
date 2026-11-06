"""The edits a project can be given, whoever gives them.

Two front ends edit one model: the browser, through the HTTP routes (`backend/routes/`),
and the terminal, through the command line (`cli/`, plan/active/cli-plan.md). Every edit
is made here, once, so the two cannot come to different answers for the same change. A
route is this module plus the HTTP around it -- reading the store, writing it back, and
turning a refusal into a status code (`backend.routes.common.refusals`).

Each edit takes a `Project` and returns a new one; the project it was given is never
changed. An edit is validated as a whole project before it is returned (`_edited`), so a
change that would leave the model inconsistent is refused field by field (a pydantic
`ValidationError`) rather than made, and a body the edit takes away takes its mesh size
with it. The refusals that are not about one field are this
module's own: `EditRefused`, and `UnknownPart` and `DeckReadOnly` under it. A stage
sequence that cannot run is `core.model.stages.StageError`.

What is *not* here is anything slow. Building a solid or reading a CAD file is gmsh's
work, in the worker (`core.gmsh_worker`); the edit that adds the part takes what gmsh
answered (`with_created_part`, `with_imported_part`), so this module can be called from
an event loop and tested without gmsh.

The project file is here too (`load`, `save`): the same JSON the GUI's Save writes and
its Open reads, so a file goes from one front end to the other unchanged.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from core import scripting
from core.kratos import materials
from core.model import drafts, soil_models, stages, units
from core.model.load_translation import translate as translate_loads
from core.model.schemas import (ConditionsUpdate, CustomPart, DimensionUpdate, LayersUpdate,
                                Line, LinesUpdate,
                                MaterialsUpdate, MeshRequest, Panel, StagesUpdate, Project,
                                StructuresUpdate,
                                UnitsUpdate, WaterLevel, WaterUpdate, point_on_panel,
                                point_on_polyline)
from core.model.wall_translation import translate as translate_walls


class ProjectFileError(Exception):
    """A project file that could not be read or written. The message names the file and
    is meant to be read by whoever gave it -- there is no stack trace on screen."""


class EditRefused(ValueError):
    """An edit that would leave the model in a state it must not be in, for a reason that
    is about the model rather than one field. The HTTP routes answer 422."""


class UnknownPart(EditRefused):
    """An edit names a custom part the project does not have. The HTTP routes answer 404."""


class DeckReadOnly(EditRefused):
    """An edit of something a Kratos deck owns (`core.kratos.external_deck`)."""


class PathError(EditRefused):
    """A field path (`value_at` and the edits beside it) that names nothing in the
    project. The message says what is there instead."""


# ── The project file ────────────────────────────────────────────────────────

def load(path: str | Path) -> Project:
    """The project in `path`: a `.json` project file, or a `.py` model script.

    A file is read through the schema, which also converts a project saved in an older
    shape (`core.model.migration`) -- the path the GUI's Open takes. A script is run the
    way `run <file.py>` runs it (`core.scripting`), so a script can stand in for a
    project file wherever the model is only read.
    """
    path = Path(path)
    if path.suffix.lower() == ".py":
        try:
            return scripting.load_project(path)
        except scripting.ScriptError as failure:
            raise ProjectFileError(str(failure)) from failure
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as failure:
        raise ProjectFileError(f"no such file: {path}") from failure
    except OSError as failure:
        raise ProjectFileError(f"{path} could not be read: {failure}") from failure
    try:
        value = json.loads(text)
    except ValueError as failure:
        raise ProjectFileError(f"{path} is not valid JSON: {failure}") from failure
    if not isinstance(value, dict):
        raise ProjectFileError(f"{path} is not a project file -- expected the JSON the "
                               "GUI's Save writes.")
    # A drawn part's .brep is a path on the computer it was drawn on: built again from
    # its recipe here, so the file is the same model wherever it is opened.
    return scripting.with_solids(Project.model_validate(value), strict=False)


def save(project: Project, path: str | Path) -> Path:
    """Write `project` to `path` as the GUI's Save does: indented JSON, UTF-8.

    Written beside the target and moved over it in one step, so a save that fails --
    a full disk, a value that will not serialise -- leaves the previous file as it was.
    Edits are made in place (plan D8), and losing the model to a failed write would
    make that a trap.
    """
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ProjectFileError(f"a project is saved as a .json file, not as {path.name}. "
                               "Give a path ending in .json.")
    text = json.dumps(project.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"
    return _write(path, text)


def write_script(project: Project, path: str | Path, *, force: bool = False,
                 source: str | Path | None = None) -> Path:
    """Write `project` as a model script (`core.model.script_writer`): the Python file
    that builds it again, which `run`, `kratos-cli` and `python <file> --out deck/` take.

    `source` is the project file it came from, which the file names. A file that is
    there already is replaced only with `force`: a script may have been edited by hand.
    """
    from core.model import script_writer

    path = Path(path)
    if path.suffix.lower() != ".py":
        raise EditRefused(f"a model script is a .py file, not {path.name}. "
                          "Give a path ending in .py.")
    if path.exists() and not force:
        raise EditRefused(f"{path} is there already, and may have been edited by hand: "
                          "give --force to replace it.")
    return _write(path, script_writer.script(project, source=source, name=path.name,
                                             folder=path.parent))


def _write(path: Path, text: str) -> Path:
    """`text` into `path`, UTF-8: written beside it and moved over it in one step."""
    folder = path.parent if str(path.parent) else Path(".")
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            file.write(text)
        _replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


REPLACE_TRIES = 20
REPLACE_WAIT = 0.05
"""How long a save waits for a file another program holds open: a second in all."""


def _replace(temporary: str, path: Path) -> None:
    """Move the written file over `path`, waiting out a program that has it open.

    Windows will not replace a file another program holds -- a virus scanner reading
    the file a command has just written, an indexer -- and says "Access is denied".
    The hold lasts milliseconds, and the next command's save is the one that meets it,
    so a save tries again for a moment before it gives up.
    """
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise ProjectFileError(
                    f"{path} could not be written: another program holds it open. "
                    "Close it there, and try again.") from None
            time.sleep(REPLACE_WAIT)


# ── Every edit ──────────────────────────────────────────────────────────────

def _edited(project: Project, payload: dict) -> Project:
    """`payload`, an edit of `project`, validated as a whole project.

    The one way an edit here makes its result, so a rule every edit keeps is kept once:
    a size belongs to its body, so an edit that takes a body away takes its size too --
    a layer removed or split, a level moved past a lift, a structure deleted -- whichever
    front end made the edit and however it was sent. A size for a body the model never
    had is kept: `unknown_mesh_keys` names it as the mistake it is.
    """
    edited = Project.model_validate(payload)
    sizes = edited.mesh.body_sizes
    if not sizes:
        return edited
    # A layer's key stays good when a line cuts the layer: it names each of the pieces.
    orphans = set(sizes) - set(edited.part_keys()) - {f"soil_{layer.id}"
                                                      for layer in edited.layers}
    lost = orphans & set(project.part_keys()) if orphans else set()
    if not lost:
        return edited
    kept = {key: size for key, size in sizes.items() if key not in lost}
    return edited.model_copy(update={"mesh": edited.mesh.model_copy(
        update={"body_sizes": kept})})


def removed_sizes(before: Project, after: Project) -> list[str]:
    """The note on the mesh sizes an edit took away with their bodies (`_edited`), or none.

    A body can come back -- a level moved back, a layer split again -- but its size does
    not, so the user is told which sizes went and what they were. A size the user removed
    on purpose, or one for a body the model never had, is not named. kratos-cli prints
    the note after its answer and the GUI shows it in its Session log.
    """
    gone = set(before.mesh.body_sizes) - set(after.mesh.body_sizes)
    if gone:
        gone &= set(before.part_keys()) - set(after.part_keys())
    if not gone:
        return []
    sizes = ", ".join(f"{key} ({before.mesh.body_sizes[key]:g})" for key in sorted(gone))
    if len(gone) == 1:
        return [f"Removed the mesh size of {sizes}: the edit took that body away. If it "
                "comes back, set its size again."]
    return [f"Removed the mesh sizes of {sizes}: the edit took those bodies away. If they "
            "come back, set their sizes again."]


# ── Soil, water, materials, structures ──────────────────────────────────────

def replace_layers(project: Project, update: LayersUpdate) -> Project:
    """The soil stack, and whatever of its context the update carries.

    The layer objects validate individually in the update; validating the project adds
    material references and stack continuity.
    """
    payload = project.model_dump()
    payload["layers"] = [layer.model_dump() for layer in update.layers]
    if update.materials is not None:
        payload["materials"] = [material.model_dump() for material in update.materials]
    if update.domain is not None:
        payload["domain"] = update.domain.model_dump()
    if update.water is not None:
        payload["water"] = update.water.model_dump()
    if update.custom_parts is not None:
        payload["custom_parts"] = [part.model_dump() for part in update.custom_parts]
    _domain_from_layers(payload)
    return _edited(project, payload)


def set_water(project: Project, update: WaterUpdate) -> Project:
    """The project's water level, or none with `water=None` -- the one water edit
    `replace_layers` cannot express, since there an omitted `water` means "leave it"."""
    payload = project.model_dump()
    payload["water"] = update.water.model_dump() if update.water is not None else None
    return _edited(project, payload)


def set_water_level(project: Project, level: float | None) -> Project:
    """What `water <level>` and `water off` do: move the level, or remove it.

    Everything else about an existing level -- its specific weight above all -- is the
    user's and is kept; a new level takes the schema's defaults. A level outside the
    model describes nothing, so it is refused outside the model's reach -- the layers
    and any drawn soil above them (`Project.extent`) -- as the GUI's `water` command
    refuses it (frontend/js/water-command.js).
    """
    if level is None:
        return set_water(project, WaterUpdate(water=None))
    reach = project.extent()
    if not reach.y_bottom < level < reach.y_top:
        raise EditRefused(f"The water level must lie between {reach.y_bottom:.2f} and "
                          f"{reach.y_top:.2f} m.")
    water = (project.water.model_copy(update={"y": level}) if project.water is not None
             else WaterLevel(y=level))
    return set_water(project, WaterUpdate(water=water))


def replace_materials(project: Project, update: MaterialsUpdate) -> Project:
    """The material library. Validating the whole project is the point: it is what
    refuses a material a layer still points at."""
    payload = project.model_dump()
    payload["materials"] = [material.model_dump() for material in update.materials]
    return _edited(project, payload)


def replace_structures(project: Project, update: StructuresUpdate) -> Project:
    """Structure-mode objects as one validated transaction.

    One edit for every structure kind, so a sheet pile and the section it points at
    arrive together: made separately, the project would pass through a state where the
    beam references a section that does not exist yet. A kind the update omits is left
    as it is; `loads` is always replaced.
    """
    payload = project.model_dump()
    payload["loads"] = [load.model_dump() for load in update.loads]
    for kind in ("beam_sections", "panel_sections", "beams", "anchor_sections", "anchors",
                 "interface_sections", "interfaces", "normal_loads"):
        records = getattr(update, kind)
        if records is not None:
            payload[kind] = [record.model_dump() for record in records]
    return _edited(project, payload)


# ── Stages ──────────────────────────────────────────────────────────────────

def replace_stages(project: Project, update: StagesUpdate) -> Project:
    """The construction sequence.

    Two validations, and they are different things. The schema's own checks run first
    -- one root, no cycles, no part both activated and deactivated in one stage, every
    key a key the model has. Then the tree has to *linearise*: Kratos runs one flat
    `execution_list`, so two stages starting from the same parent have no order to run
    in, and that is `stages.StageError`, naming the stages that branch.

    `linearise` is deliberately not a schema validator: a branch is a legitimate thing
    to have half-built in an editor, and refusing it in `Project` would make it
    impossible to type. It is refused here, at the edit, rather than at export, because
    this is where whoever made it can still see what they did.
    """
    _stages_of_a_deck_are_read_only(project)
    payload = project.model_dump()
    payload["stages"] = [stage.model_dump() for stage in update.stages]
    edited = _edited(project, payload)
    stages.linearise(edited)
    return edited


def default_stages(project: Project) -> Project:
    """The initial stage, then the null step (`stages.default_stages` is the authority).

    It replaces whatever is there rather than refusing when stages already exist: it is
    the way back out of a sequence that has been broken.
    """
    _stages_of_a_deck_are_read_only(project)
    payload = project.model_dump()
    payload["stages"] = [stage.model_dump() for stage in stages.default_stages(project)]
    return _edited(project, payload)


def _stages_of_a_deck_are_read_only(project: Project) -> None:
    """A deck's stages are its stages, read from it (`core.kratos.external_deck`); the
    deck is what is calculated, so an edit made here would change nothing that is."""
    if project.deck is not None:
        raise DeckReadOnly(
            f"The stages of {project.name} are the stages of its Kratos deck "
            f"({project.deck.parameters} in {project.deck.directory}), shown as they "
            f"are. Edit the deck to change them, then run its script again.")


# ── Dimension and units ─────────────────────────────────────────────────────

def set_dimension(project: Project, update: DimensionUpdate) -> tuple[Project, list[str]]:
    """Switch between the solid model and the plane-strain x-y section.

    Returns the project and the notes on what changed shape on the way, which are the
    caller's to show. An explicit `section_offset` replaces the stored one; omitted,
    going to 2D lets the `Project` validator resolve the midpoint.
    """
    payload = project.model_dump()
    payload["dimension"] = update.dimension
    payload["section_offset"] = update.section_offset
    notes: list[str] = []
    # A load is the one thing that changes shape with the dimension: a pressure over a
    # footprint in the solid model is a pressure per metre run in the cut. Translated
    # here, at the single point the mode changes, so the tree, the geometry and the
    # deck all see the same pair. See core/model/load_translation.py for what is and is not translatable.
    payload["loads"] = [load.model_dump()
                        for load in translate_loads(project, update.dimension, notes,
                                                    update.section_offset)]
    # A wall changes shape with the dimension the same way: a sheet pile in the section
    # is a panel swept between two levels in the solid model, which is what gives it a
    # plan footprint to edit. See core/model/wall_translation.py for what is and is not translatable.
    beams, panel_sections = translate_walls(project, update.dimension, notes)
    payload["beams"] = [beam.model_dump() for beam in beams]
    payload["panel_sections"] = [section.model_dump() for section in panel_sections]
    # A soil law is written for one dimension; the pairs this application knows go
    # across with the model, and any other is left as the user typed it, said out loud.
    payload["materials"] = materials.translate_laws(payload["materials"], update.dimension,
                                                    notes)
    return _edited(project, payload), notes


def set_units(project: Project, update: UnitsUpdate) -> tuple[Project, list[str]]:
    """Re-express the whole project in another unit system (`core/model/units.py`).

    The one place values are converted. A variable whose dimension is not known is kept
    as typed and named in the notes, for the user to convert.
    """
    payload, notes = units.convert_project(project.model_dump(mode="json"),
                                           update.unit_system)
    return _edited(project, payload), notes


# ── Custom parts ────────────────────────────────────────────────────────────

RECIPE_OPTIONS = ("label", "material", "replace", "insert_before")
"""The keys of a creation recipe that say what to do with the solid, not what it is."""


def check_recipe(project: Project, recipe: dict) -> None:
    """Refuse a creation recipe before gmsh is asked to build it.

    `replace` and `insert_before` name a part that has to exist; a solid exactly where
    another one already is cannot be meshed alongside it; a `material` has to be in the
    library. Each is the caller's to fix, so each is refused with its reason.
    """
    for option in ("insert_before", "replace"):
        key = recipe.get(option)
        if key is not None and not any(p.key == key for p in project.custom_parts):
            raise UnknownPart(f"no custom part with key {key!r}")
    replace = recipe.get("replace")
    shape = _shape(recipe)
    for existing in project.custom_parts:
        if existing.key == replace:
            continue  # its own former shape is not a clash
        if existing.recipe and _shape(existing.recipe) == shape:
            raise EditRefused(
                f"{existing.label!r} already occupies exactly this space. Two solids in "
                "the same place cannot both be meshed — move or resize this one.")
    material = recipe.get("material")
    if material is not None and not any(m.id == material for m in project.materials):
        raise EditRefused(f"Unknown material {material!r}")


def _shape(recipe: dict) -> dict:
    return {k: v for k, v in recipe.items() if k not in RECIPE_OPTIONS}


def with_created_part(project: Project, recipe: dict,
                      built: dict) -> tuple[Project, CustomPart]:
    """`project` with the solid gmsh built from `recipe`, and the part it became.

    `built` is what `core.gmsh_worker.create_job` answered: the .brep it wrote and the
    box the solid fills. `replace` rebuilds an existing part in place, keeping its key
    -- so its mesh size, tree position and any selection survive a change of shape;
    `insert_before` puts the new part ahead of another. A `material` turns the solid
    into soil: it takes that material's colour and is meshed as a soil body.
    """
    check_recipe(project, recipe)
    edited = project.model_copy(deep=True)
    replace = recipe.get("replace")
    insert_before = recipe.get("insert_before")
    if replace is not None:
        key = replace
    else:
        # A key must be unique for the life of the project: counting the existing
        # drawn_ parts would reuse a key after a delete.
        used = {p.key for p in edited.custom_parts}
        index = len(edited.custom_parts)
        while f"drawn_{index}" in used:
            index += 1
        key = f"drawn_{index}"

    material = recipe.get("material")
    part = CustomPart(
        key=key,
        label=recipe.get("label", key),
        source="gui",
        source_file=built["brep_path"],
        recipe=recipe,
        mat=material,
        color=edited.material(material).color if material is not None else "#888888",
        bbox=tuple(built["bbox"]),
    )
    if replace is not None:
        at = next(i for i, p in enumerate(edited.custom_parts) if p.key == replace)
        edited.custom_parts[at] = part
    elif insert_before is not None:
        at = next(i for i, p in enumerate(edited.custom_parts) if p.key == insert_before)
        edited.custom_parts.insert(at, part)
    else:
        edited.custom_parts.append(part)
    return edited, part


def with_imported_part(project: Project, filename: str | None, built: dict,
                       source: str | Path | None = None) -> tuple[Project, CustomPart]:
    """`project` with the solid read from a CAD file, and the part it became.

    `built` is what `core.gmsh_worker.import_job` answered. `source` is the file it was
    read from, when the caller knows it, kept so a model script can read it again. The
    key follows the highest import key in use, not the count: a deleted imported_0 must
    not let the next import take a key that imported_1 still holds.
    """
    edited = project.model_copy(deep=True)
    taken = [int(p.key.split("_", 1)[1]) for p in edited.custom_parts
             if p.key.startswith("imported_") and p.key.split("_", 1)[1].isdigit()]
    key = f"imported_{max(taken, default=-1) + 1}"
    part = CustomPart(
        key=key,
        label=filename or key,
        source="import",
        source_file=built["brep_path"],
        imported_from=str(Path(source).resolve()) if source is not None else None,
        # gmsh measured it while the part was open; kept so `Project.extent` can say
        # how far the model reaches without reopening every .brep.
        bbox=tuple(built["bbox"]),
    )
    edited.custom_parts.append(part)
    return edited, part


def without_custom_parts(project: Project, keys: list[str]) -> Project:
    """`project` minus the custom parts `keys`, validated like any other edit.

    A part a stage still names is refused, not quietly unstaged: which stages should
    lose it is a modelling decision. Left to validation instead, the project would be
    one every later edit fails on with "names no such part". A mesh size for the part
    goes with it -- it describes nothing else.
    """
    gone = set(keys)
    users = [(stage.id, sorted(gone & set(stage.activate + stage.deactivate)))
             for stage in project.stages]
    users = [(stage, named) for stage, named in users if named]
    if users:
        listed = "; ".join(f"stage {stage!r} names {', '.join(named)}"
                           for stage, named in users)
        raise EditRefused(f"cannot delete a part that a stage still uses ({listed}); take "
                          "it out of those stages first")
    payload = project.model_dump()
    payload["custom_parts"] = [p for p in payload["custom_parts"] if p["key"] not in gone]
    return _edited(project, payload)


def without_custom_part(project: Project, key: str) -> Project:
    """`project` minus the one custom part `key`, which has to be there."""
    if not any(p.key == key for p in project.custom_parts):
        raise UnknownPart(f"no custom part with key {key!r}")
    return without_custom_parts(project, [key])


def edit_notes(before: Project, after: Project) -> list[str]:
    """What to tell the user about an edit besides that it was done: the mesh sizes it took
    away (`removed_sizes`), and each line it made or moved that splits no soil. kratos-cli
    prints these after its answer and the GUI shows them in its Session log."""
    was = {line.id: line for line in before.lines}
    idle = after.idle_lines()
    return removed_sizes(before, after) + [
        f"Line {line.name} splits no soil: a line has to cross a soil layer from one edge "
        "to another."
        for line in after.lines if line.id in idle and was.get(line.id) != line]


# ── Meshing ─────────────────────────────────────────────────────────────────

def unknown_mesh_keys(project: Project, settings: MeshRequest) -> list[str]:
    """The bodies `settings` names -- to mesh, or to size -- that this project does not
    have, sorted. Empty when every one is the project's own."""
    named = project.expand_body_keys([*(settings.volume_keys or []), *settings.body_sizes])
    return sorted(set(named) - set(project.part_keys()))


def nothing_to_mesh(project: Project) -> str | None:
    """Why `project` would mesh to nothing, or None: a model with no soil body and no
    solid of its own has nothing for gmsh to fill, and its deck would hold no nodes.

    One rule for every way in -- `POST /api/calculate`, `kratos-cli check`, `mesh`,
    `export` and `calculate`, and the GUI's Calculate button, which applies the same
    test to the project it was sent (`App.Calculate.state`). Each adds its own hint on
    what to do about it, because the fix is a different command in each place.
    """
    if project.soil_bodies() or project.custom_parts:
        return None
    return "the model has nothing to mesh: no soil layer and no solid."


def require_parametric(project: Project, what: str) -> None:
    """Refuse to mesh or export a project that is a deck already (`core.kratos.external_deck`).

    Everything but its deck is the empty site the schema requires, so going ahead would
    mesh nothing and answer as though that were the model.
    """
    if project.deck is not None:
        raise DeckReadOnly(
            f"{project.name} is a Kratos deck ({project.deck.parameters} in "
            f"{project.deck.directory}), so it is not {what} here: its mesh is the "
            f"deck's own. Calculate runs it as it is.")


# ── Any field, by path ──────────────────────────────────────────────────────
#
# What the command line's `get`, `set`, `add` and `remove` reach every field with, so a
# field nobody wrote a command for is still one command away. A path is the project's
# JSON as the GUI saves it, walked by field name: `mesh.element_size`. A record in a list
# is picked in brackets by its `id` -- `key` for a custom part -- so the path still names
# the same record after the list is reordered: `layers[L2].mat`. A list without ids takes
# an index from 0, `mesh.refinements[0].size`, and a mapping takes its key either way:
# `materials[m1].variables[YOUNG_MODULUS]` or `materials[m1].variables.YOUNG_MODULUS`.

DEDICATED = {
    "dimension": ("dimension", "switching it translates the loads, walls and soil laws "
                               "with it"),
    "section_offset": ("dimension", "the section moves with the dimension"),
    "unit_system": ("units", "switching it converts every value in the project"),
    "deck": (None, "it is what a deck case opens with, and its files are what is "
                   "calculated"),
}
"""The fields with an edit of their own (`set_dimension`, `set_units`): set bare, the rest
of the model would be left in the old dimension or the old units. Each with the command
that makes the edit, and why."""

_TOKEN = re.compile(r"\[([^\[\]]*)\]|(?:^|\.)([^.\[\]]+)")


def value_at(project: Project, path: str) -> object:
    """The value at `path`, as the project's JSON has it; the whole project for ""."""
    payload = project.model_dump(mode="json")
    if not path:
        return payload
    parent, key, _, _ = _locate(payload, path)
    return parent[key]


def with_value(project: Project, path: str, value: object) -> Project:
    """`project` with `value` at `path`. A mapping takes a new key this way; a model's
    field it does not have is refused by the schema, by name."""
    payload = project.model_dump(mode="json")
    parent, key, _, tokens = _locate(payload, path, may_create=True)
    _refuse_dedicated(tokens)
    parent[key] = value
    return _validated_edit(project, payload, tokens)


def with_added(project: Project, path: str, value: object) -> Project:
    """`project` with `value` appended to the list at `path`."""
    payload = project.model_dump(mode="json")
    parent, key, where, tokens = _locate(payload, path)
    _refuse_dedicated(tokens)
    if not isinstance(parent[key], list):
        raise PathError(f"{where} is not a list, so nothing can be added to it; set it "
                        "instead.")
    parent[key].append(value)
    return _validated_edit(project, payload, tokens)


def without_value(project: Project, path: str) -> Project:
    """`project` without the record or the mapping key at `path`.

    A custom part goes the way `without_custom_part` takes it -- refused while a stage
    uses it, its mesh size with it -- rather than simply being dropped from the list.
    """
    payload = project.model_dump(mode="json")
    parent, key, _, tokens = _locate(payload, path)
    _refuse_dedicated(tokens)
    if tokens[0][1] == "custom_parts" and len(tokens) == 2:
        return without_custom_part(project, parent[key]["key"])
    del parent[key]
    return _validated_edit(project, payload, tokens)


def _validated_edit(project: Project, payload: dict, tokens: list[tuple[str, str]]) -> Project:
    """The edited payload as a project. An edit inside the stages is one of the stages,
    so it has to linearise as well, and a deck's are not edited at all. The height of the
    domain and of the layer stack is one edit, whichever of the two the path names."""
    if tokens[0][1] == "stages":
        return replace_stages(project, StagesUpdate(stages=payload["stages"]))
    if tokens[0][1] == "layers":
        _domain_from_layers(payload)
    elif tokens[0][1] == "domain":
        _layers_from_domain(payload)
    return _edited(project, payload)


def _refuse_dedicated(tokens: list[tuple[str, str]]) -> None:
    field = tokens[0][1]
    if field in DEDICATED:
        command, why = DEDICATED[field]
        instead = (f"Use the `{command}` command." if command
                   else "Open the deck instead.")
        raise EditRefused(f"`{field}` is not set by path: {why}. {instead}")


def _tokens(path: str) -> list[tuple[str, str]]:
    """`path` as `("field", name)` and `("select", id)` steps, in order."""
    tokens, at = [], 0
    while at < len(path):
        match = _TOKEN.match(path, at)
        if not match:
            raise PathError(f"{path!r} is not a path. Name fields with dots and pick a "
                            "record by its id in brackets, e.g. layers[L1].mat.")
        tokens.append(("select", match[1]) if match[1] is not None else ("field", match[2]))
        at = match.end()
    if not tokens:
        raise PathError("give a path, e.g. mesh.element_size")
    if tokens[0] == ("field", "phases"):
        # The field's name before it took Kratos' word; a script that still says it works.
        tokens[0] = ("field", "stages")
    return tokens


def _locate(payload: dict, path: str, *, may_create: bool = False):
    """The container the last step of `path` is in, the key or index it is under there,
    the path as text, and the steps. With `may_create`, the last step may be a key the
    mapping does not have yet."""
    tokens = _tokens(path)
    node, where = payload, ""
    for token in tokens[:-1]:
        key = _step(node, token, where)
        where = _joined(where, token)
        node = node[key]
    last = tokens[-1]
    if may_create and isinstance(node, dict) and last[1] not in node:
        key = last[1]
    else:
        key = _step(node, last, where)
    return node, key, _joined(where, last), tokens


def _step(node: object, token: tuple[str, str], where: str) -> str | int:
    kind, name = token
    if isinstance(node, dict):
        if name in node:
            return name
        raise PathError(f"{where or 'the project'} has no field {name!r}"
                        + _listing(list(node)))
    if isinstance(node, list):
        if kind == "field":
            example = _names(node)[0] if node else "id"
            raise PathError(f"{where} is a list: pick an entry by its id in brackets, "
                            f"e.g. {where}[{example}], or by its place from 0.")
        for index, item in enumerate(node):
            if isinstance(item, dict) and name in (item.get("id"), item.get("key")):
                return index
        if re.fullmatch(r"-?\d+", name) and -len(node) <= int(name) < len(node):
            return int(name) % len(node)
        raise PathError(f"{where} has no entry {name!r}"
                        + (_listing(_names(node)) if node else "; it is empty"))
    raise PathError(f"{where} is {json.dumps(node)}, which has no fields")


def _names(records: list) -> list[str]:
    return [str(item.get("id", item.get("key", index))) if isinstance(item, dict)
            else str(index) for index, item in enumerate(records)]


def _listing(names: list[str]) -> str:
    return "; it has: " + ", ".join(names) if names else ""


def _joined(where: str, token: tuple[str, str]) -> str:
    kind, name = token
    if kind == "select":
        return f"{where}[{name}]"
    return f"{where}.{name}" if where else name


# ── The ground: domain, layers, materials, excavation ───────────────────────
#
# The edits the GUI's soil layers dialog makes in the browser
# (frontend/js/soil-layers-dialog.js), so the command line makes them the same way: a
# moved level moves its neighbour's, a deleted layer's neighbour closes the gap, and an
# edit that would cross a neighbour is refused rather than made.
#
# The domain's height is the layer stack's: its top is the top of the first layer (the
# ground level, NAP +1.7 m or 0 m as the user has it) and its bottom the bottom of the
# last. A layer edit moves the domain, and `domain --y` moves the stack. A project with
# no layers keeps the height its domain was given.

class UnknownRecord(EditRefused):
    """An edit names a layer or material the project does not have."""


def _domain_from_layers(payload: dict) -> None:
    """The domain's top and bottom, set to the layer stack's in `payload`."""
    layers = payload["layers"]
    if not layers:
        return
    top, bottom = layers[0]["top"], layers[-1]["bottom"]
    if not top > bottom:
        raise EditRefused(f"The layers have no height: the top of the first layer ({top:g}) "
                          f"must be above the bottom of the last ({bottom:g}).")
    payload["domain"]["y_top"], payload["domain"]["y_bottom"] = top, bottom


def _layers_from_domain(payload: dict) -> None:
    """The top of the first layer and the bottom of the last, moved to the domain's
    top and bottom in `payload`; refused when one would cross the layer's other face."""
    layers, domain = payload["layers"], payload["domain"]
    if not layers:
        return
    first, last = layers[0], layers[-1]
    if domain["y_top"] < first["bottom"]:
        raise EditRefused(f"The top {domain['y_top']:g} is below the bottom of the first "
                          f"layer, {first['id']} ({first['bottom']:g}).")
    if domain["y_bottom"] > last["top"]:
        raise EditRefused(f"The bottom {domain['y_bottom']:g} is above the top of the last "
                          f"layer, {last['id']} ({last['top']:g}).")
    first["top"], last["bottom"] = domain["y_top"], domain["y_bottom"]


def set_domain(project: Project, *, x: tuple[float, float] | None = None,
               y: tuple[float, float] | None = None,
               z: tuple[float, float] | None = None) -> tuple[Project, list[str]]:
    """The model's extents, on the axes given: `x` and `z` as (from, to), `y` as
    (bottom, top). A new `y` moves the top of the first layer and the bottom of the last
    with it. A section cut outside the new extents is moved to their middle, and the
    notes say so."""
    payload = project.model_dump()
    domain = payload["domain"]
    if x is not None:
        domain["x0"], domain["x1"] = x
    if y is not None:
        domain["y_bottom"], domain["y_top"] = y
        _layers_from_domain(payload)
    if z is not None:
        domain["z0"], domain["z1"] = z
    notes: list[str] = []
    offset = project.section_offset
    if offset is not None and not domain["z0"] < offset < domain["z1"]:
        payload["section_offset"] = None
        if project.dimension == 2:
            notes.append(f"The section at z = {offset:g} is outside the new domain, so it "
                         f"is cut through its middle, at z = "
                         f"{(domain['z0'] + domain['z1']) / 2:g}.")
    return _edited(project, payload), notes


def add_layer(project: Project, id: str, material: str, *, name: str | None = None,
              bottom: float | None = None, thickness: float | None = None) -> Project:
    """A layer under the stack (`drafts.layer`): from the last layer's bottom -- the
    ground, for the first -- down to `bottom`, or `thickness` below that."""
    _refuse_taken(id, [layer.id for layer in project.layers], "layer")
    new = drafts.layer(project, id, material, name=name, bottom=bottom, thickness=thickness)
    payload = project.model_dump()
    payload["layers"].append(new.model_dump())
    _domain_from_layers(payload)
    return _edited(project, payload)


def update_layer(project: Project, id: str, *, material: str | None = None,
                 name: str | None = None, top: float | None = None,
                 bottom: float | None = None) -> Project:
    """The layer `id` with a new material, name, top or bottom.

    A moved level moves the neighbour's with it: a top is the bottom of the layer above,
    a bottom the top of the layer below. A level that would cross a neighbour's other
    face is refused, as the soil layers dialog refuses it.
    """
    index = _index(project.layers, id, "layer")
    payload = project.model_dump()
    layers = payload["layers"]
    layer = layers[index]
    if material is not None:
        layer["mat"] = material
    if name is not None:
        layer["name"] = name
    if top is not None:
        if top < layer["bottom"]:
            raise EditRefused(f"{id}: the top must be at or above its bottom "
                              f"({layer['bottom']:g}).")
        if index > 0 and top > layers[index - 1]["top"]:
            raise EditRefused(f"{id}: the top cannot rise above the top of the layer "
                              f"above ({layers[index - 1]['top']:g}).")
        layer["top"] = top
        if index > 0:
            layers[index - 1]["bottom"] = top
    if bottom is not None:
        if bottom > layer["top"]:
            raise EditRefused(f"{id}: the bottom must be at or below its top "
                              f"({layer['top']:g}).")
        if index < len(layers) - 1 and bottom < layers[index + 1]["bottom"]:
            raise EditRefused(f"{id}: the bottom cannot drop below the bottom of the "
                              f"layer below ({layers[index + 1]['bottom']:g}).")
        layer["bottom"] = bottom
        if index < len(layers) - 1:
            layers[index + 1]["top"] = bottom
    _domain_from_layers(payload)
    return _edited(project, payload)


def split_layer(project: Project, id: str, new_id: str | None = None) -> Project:
    """The soil layers dialog's Insert: the layer `id` halved, the lower half a new layer
    of the same material."""
    index = _index(project.layers, id, "layer")
    taken = [layer.id for layer in project.layers]
    new_id = new_id if new_id is not None else drafts.free_id(taken, "L")
    _refuse_taken(new_id, taken, "layer")
    payload = project.model_dump()
    upper = payload["layers"][index]
    middle = (upper["top"] + upper["bottom"]) / 2
    lower = {"id": new_id, "name": new_id, "mat": upper["mat"], "top": middle,
             "bottom": upper["bottom"]}
    upper["bottom"] = middle
    payload["layers"].insert(index + 1, lower)
    return _edited(project, payload)


def remove_layer(project: Project, id: str) -> Project:
    """The project without layer `id`, the gap closed by the layer above -- or, for the
    top layer, by the one below -- as the soil layers dialog's Delete closes it."""
    index = _index(project.layers, id, "layer")
    payload = project.model_dump()
    layers = payload["layers"]
    removed = layers.pop(index)
    if index > 0:
        layers[index - 1]["bottom"] = removed["bottom"]
    elif layers:
        layers[0]["top"] = removed["top"]
    _domain_from_layers(payload)
    return _edited(project, payload)


def add_material(project: Project, material) -> Project:
    """`project` with the new soil `material` (`drafts.soil` makes one)."""
    _refuse_taken(material.id, [m.id for m in project.materials], "material")
    payload = project.model_dump()
    payload["materials"].append(material.model_dump())
    return _edited(project, payload)


def update_material(project: Project, id: str, *, name: str | None = None,
                    color: str | None = None, law: str | None = None,
                    model: str | None = None, variables: dict | None = None,
                    unset: Sequence[str] = (), notes: list[str] | None = None) -> Project:
    """The material `id` with the fields and variables given; `unset` names variables to
    leave out, so the export derives them where it can.

    `model` makes it that soil model (`core/model/soil_models.py`): its law in the
    project's dimension. What the soil then lists and lacks gets the model's default, as
    the material window fills it (`soil_models.fill`), and `notes` says which."""
    if model is not None and law is not None:
        raise EditRefused("give a soil model or a law, not both")
    if model is not None:
        try:
            law = soil_models.law(model, project.dimension)
        except ValueError as failure:
            raise EditRefused(str(failure)) from None
    payload = project.model_dump()
    record = payload["materials"][_index(project.materials, id, "material")]
    before_law, before = record["constitutive_law"], dict(record["variables"])
    for field, value in (("name", name), ("color", color), ("constitutive_law", law)):
        if value is not None:
            record[field] = value
    record["variables"].update(variables or {})
    for variable in unset:
        if variable not in record["variables"]:
            raise EditRefused(f"{id} has no variable {variable}; it has: "
                              + ", ".join(record["variables"]))
        del record["variables"][variable]
    filled = soil_models.fill(before_law, before, record["constitutive_law"],
                              record["variables"], project.unit_system, skip=tuple(unset))
    note = soil_models.filled_note(soil_models.model_of(record["constitutive_law"]), filled)
    if note and notes is not None:
        notes.append(note)
    return _edited(project, payload)


def remove_material(project: Project, id: str) -> Project:
    """The project without material `id`. A material a layer or a part still uses is
    refused by validation, naming it."""
    at = _index(project.materials, id, "material")
    payload = project.model_dump()
    del payload["materials"][at]
    return _edited(project, payload)


# ── Lines and the soil bodies they make ─────────────────────────────────────

def replace_lines(project: Project, update: LinesUpdate) -> Project:
    """The lines, as one list. The project's validation works out the bodies they make,
    and refuses an edit that takes away a body a stage or a condition still names."""
    payload = project.model_dump()
    payload["lines"] = [line.model_dump() for line in update.lines]
    return _edited(project, payload)


def add_line(project: Project, line: Line) -> Project:
    _refuse_taken(line.id, [each.id for each in project.lines], "line")
    return replace_lines(project, LinesUpdate(lines=[*project.lines, line]))


def update_line(project: Project, id: str, **fields) -> Project:
    """The line `id` with `fields` (`name`, `points`) changed."""
    at = _index(project.lines, id, "line")
    lines = list(project.lines)
    lines[at] = Line.model_validate(lines[at].model_dump() | fields)
    return replace_lines(project, LinesUpdate(lines=lines))


def remove_line(project: Project, id: str) -> Project:
    at = _index(project.lines, id, "line")
    return replace_lines(project, LinesUpdate(lines=[
        line for index, line in enumerate(project.lines) if index != at]))


def update_body(project: Project, key: str, **fields) -> Project:
    """The soil body `key` with its `name` or its `material` changed; `material=None` goes
    back to the layer's. A body that is a whole layer is that layer's to change."""
    payload = project.model_dump()
    for body in payload.get("bodies", []):
        if f"soil_{body['layer']}__{body['id']}" == key:
            if "name" in fields:
                body["name"] = fields["name"]
            if "material" in fields:
                body["mat"] = fields["material"]
            return _edited(project, payload)
    if any(f"soil_{layer.id}" == key for layer in project.layers):
        raise UnknownPart(f"{key} is a whole layer, not a part cut off by a line: change it "
                          "as a layer")
    raise UnknownPart(f"no soil body with key {key!r}")


def set_excavation(project: Project, *, x: tuple[float, float] | None = None,
                   z: tuple[float, float] | None = None,
                   levels: list[float] | None = None) -> tuple[Project, list[str]]:
    """The pit: its plan outline (`x`, `z` as from, to) and the levels it is dug to,
    shallowest first -- one lift per level, each its own body, deactivated in its own
    stage. The floor is the last level.

    A project without a pit gets one when `x`, `z` and `levels` are all given. A 2D
    model is one cut through z, so its pit spans the domain's z range unless `z` says
    otherwise."""
    payload = project.model_dump()
    pit = payload.get("excavation")
    if pit is None:
        if z is None and project.dimension == 2:
            z = (project.domain.z0, project.domain.z1)
        missing = [name for name, value in (("x", x), ("z", z), ("levels", levels))
                   if value is None]
        if missing:
            raise EditRefused(f"the project has no excavation yet; give "
                              f"{', '.join(missing)} to make one")
        pit = payload["excavation"] = {}
    if x is not None:
        pit["x0"], pit["x1"] = x
    if z is not None:
        pit["z0"], pit["z1"] = z
    if levels is not None:
        pit["levels"], pit["floor_y"] = list(levels), levels[-1]
    edited = _edited(project, payload)
    notes = []
    if edited.layered_soil and len(edited.pit_levels()) < 2:
        notes.append("With one level a layered model digs nothing: its pit is cut only "
                     "when it is dug in two or more levels, one stage per lift.")
    return edited, notes


def assign_part_material(project: Project, key: str, material: str) -> Project:
    """The custom part `key` made soil of `material`: it takes the material's colour and
    is meshed as a soil body, as a part drawn with a material is."""
    if not any(p.key == key for p in project.custom_parts):
        raise UnknownPart(f"no custom part with key {key!r}")
    if not any(m.id == material for m in project.materials):
        raise EditRefused(f"Unknown material {material!r}")
    payload = project.model_dump()
    for part in payload["custom_parts"]:
        if part["key"] == key:
            part["mat"], part["color"] = material, project.material(material).color
    return _edited(project, payload)


def _index(records: list, id: str, what: str) -> int:
    for index, record in enumerate(records):
        if record.id == id:
            return index
    names = ", ".join(record.id for record in records) or "none"
    raise UnknownRecord(f"there is no {what} {id!r}; there are: {names}")


def _refuse_taken(id: str, taken: list[str], what: str) -> None:
    if id in taken:
        raise EditRefused(f"there is already a {what} {id!r}; give another id.")


# ── Structures, one at a time ───────────────────────────────────────────────
#
# What the Structure mode's tools save one record at a time through
# `PATCH /api/project/structures` (`replace_structures` above): a sheet pile, wall or
# member, an anchor, an interface, a normal load or a load, each with the section it is
# built with when the project has none by that id yet (`drafts.section_for`). The
# collections share one namespace with the soil bodies -- the keys a stage switches --
# so an id is refused that any part already has.

STRUCTURES = ("beams", "anchors", "interfaces", "normal_loads", "loads")
"""The project lists a structure is kept in."""

RESERVED = {"excavation", "wall", "struts", "anchors", "piles", "water", "wells"}
"""The keys of the demo's own pit furniture, which no structure may take
(`Project._cross_references`)."""


def _collection(record) -> str:
    kind = getattr(record, "kind", None)
    for field, kinds in (("beams", ("beam", "panel", "member")),
                         ("anchors", ("anchor", "anchor3d")), ("interfaces", ("interface",)),
                         ("normal_loads", ("normal",)),
                         ("loads", ("point", "line", "surface"))):
        if kind in kinds:
            return field
    raise EditRefused(f"{type(record).__name__} is not a structure")


def find_structure(project: Project, id: str):
    """The structure `id` -- sheet pile, wall, member, anchor, interface or load."""
    for field in STRUCTURES:
        for record in getattr(project, field):
            if record.id == id:
                return record
    names = [r.id for field in STRUCTURES for r in getattr(project, field)]
    raise UnknownRecord(f"there is no structure {id!r}; there are: "
                        + (", ".join(names) or "none"))


def add_structure(project: Project, record, section=None) -> Project:
    """`project` with the structure `record`, and with `section` -- the default one it
    brings, `drafts.section_for` -- added to its library."""
    taken = set(project.part_keys()) | set(project.stageable_keys())
    taken |= {r.id for field in STRUCTURES for r in getattr(project, field)} | RESERVED
    if record.id in taken:
        raise EditRefused(f"there is already a part {record.id!r}; give another id. A "
                          "stage names a part by its id, so no two parts share one.")
    payload = project.model_dump()
    if section is not None:
        kind = drafts.section_kind(record)
        if kind is None:
            raise EditRefused(f"{record.id!r} is built with no section")
        field = drafts.SECTION_FIELDS[kind]
        _refuse_taken(section.id, [s["id"] for s in payload[field]], "section")
        payload[field].append(section.model_dump())
    payload[_collection(record)].append(record.model_dump())
    return _edited(project, payload)


def update_structure(project: Project, id: str, **fields) -> Project:
    """The structure `id` with the fields given, by their schema names."""
    field = _collection(find_structure(project, id))
    payload = project.model_dump()
    record = next(r for r in payload[field] if r["id"] == id)
    record.update(fields)
    return _edited(project, payload)


def remove_structure(project: Project, id: str) -> Project:
    """The project without the structure `id`, and without its mesh size.

    Refused while a stage names it -- which stages should lose it is a modelling decision,
    as for a custom part (`without_custom_parts`) -- and, for a pile, while an anchor
    hangs from it or an interface follows it: those would be left on nothing.
    """
    record = find_structure(project, id)
    users = [stage.id for stage in project.stages
             if id in stage.activate or id in stage.deactivate]
    if users:
        raise EditRefused("cannot remove a structure a stage still uses ("
                          + "; ".join(f"stage {stage!r} names {id}" for stage in users)
                          + "); take it out of those stages first")
    if _collection(record) == "beams":
        hanging = [a.id for a in project.anchors if _hangs_from(a, record)]
        hanging += [i.id for i in project.interfaces if i.structure == id]
        hanging += [load.id for load in project.loads if _stands_on(load, record, project)]
        if hanging:
            raise EditRefused(f"{id} carries {', '.join(hanging)}; remove or move them "
                              "first")
    payload = project.model_dump()
    field = _collection(record)
    payload[field] = [r for r in payload[field] if r["id"] != id]
    return _edited(project, payload)


def _hangs_from(anchor, structure) -> bool:
    """Whether the head of `anchor` is on `structure`, the test `Project` holds it to."""
    if len(anchor.head) == 3 and isinstance(structure, Panel):
        return point_on_panel(anchor.head, structure)
    points = getattr(structure, "points", None)
    if points is None or len(points[0]) != len(anchor.head):
        return False
    return point_on_polyline(anchor.head, points)


def _stands_on(load, structure, project: Project) -> bool:
    """Whether `load` is a point load above the ground that only `structure` holds up:
    off the model, on the pile (the test `Project` holds it to)."""
    points = getattr(structure, "points", None)
    if load.kind != "point" or points is None or len(points[0]) != 2:
        return False
    extent = project.extent()
    inside = (extent.x0 <= load.x <= extent.x1
              and extent.y_bottom <= load.y <= extent.y_top)
    return not inside and point_on_polyline((load.x, load.y), points)


def find_section(project: Project, id: str, kind: str | None = None) -> tuple[str, object]:
    """The section `id` and its kind, which `kind` names when two libraries share the id."""
    kinds = [k for k, field in drafts.SECTION_FIELDS.items()
             if (kind is None or k == kind) and any(s.id == id for s in getattr(project, field))]
    if not kinds:
        where = f"{kind} section" if kind else "section"
        names = [s.id for k, field in drafts.SECTION_FIELDS.items()
                 if kind is None or k == kind for s in getattr(project, field)]
        raise UnknownRecord(f"there is no {where} {id!r}; there are: "
                            + (", ".join(names) or "none"))
    if len(kinds) > 1:
        raise EditRefused(f"{id} is both a {' and an '.join(kinds)} section; say which "
                          "with its kind")
    field = drafts.SECTION_FIELDS[kinds[0]]
    return kinds[0], next(s for s in getattr(project, field) if s.id == id)


def add_section(project: Project, kind: str, section) -> Project:
    """`project` with the new `kind` section `section` (`drafts.section` makes one)."""
    field = drafts.SECTION_FIELDS[kind]
    _refuse_taken(section.id, [s.id for s in getattr(project, field)], f"{kind} section")
    payload = project.model_dump()
    payload[field].append(section.model_dump())
    return _edited(project, payload)


def update_section(project: Project, id: str, *, kind: str | None = None,
                   variables: dict | None = None, unset: Sequence[str] = (),
                   **fields) -> Project:
    """The section `id` with the fields given by their schema names, the variables
    given, and without the variables `unset` names."""
    field = drafts.SECTION_FIELDS[find_section(project, id, kind)[0]]
    payload = project.model_dump()
    record = next(s for s in payload[field] if s["id"] == id)
    record.update(fields)
    record["variables"].update(variables or {})
    for variable in unset:
        if variable not in record["variables"]:
            raise EditRefused(f"{id} has no variable {variable}; it has: "
                              + (", ".join(record["variables"]) or "none"))
        del record["variables"][variable]
    return _edited(project, payload)


def remove_section(project: Project, id: str, kind: str | None = None) -> Project:
    """The project without the section `id`, refused while a structure is built with it."""
    kind, _ = find_section(project, id, kind)
    users = [r.id for field in STRUCTURES for r in getattr(project, field)
             if drafts.section_kind(r) == kind and r.section == id]
    if users:
        raise EditRefused(f"the {kind} section {id} is used by {', '.join(users)}; give "
                          "them another section first")
    payload = project.model_dump()
    field = drafts.SECTION_FIELDS[kind]
    payload[field] = [s for s in payload[field] if s["id"] != id]
    return _edited(project, payload)


# ── Boundary conditions ─────────────────────────────────────────────────────
#
# What `kratos-cli boundary` and the GUI's boundary conditions dialog edit. A condition
# on a line or a point is a gmsh physical group named by its id, so an id is refused
# that any part or structure already has, as for a structure.

def _refuse_staged_conditions(project: Project, kept: set[str]) -> None:
    """Refuse to remove a water pressure condition a stage still switches: which stages
    should lose it is a modelling decision, as for a structure (`remove_structure`)."""
    gone = {c.id for c in project.boundary_conditions if c.id not in kept}
    users = [(stage.id, sorted(gone & set(stage.activate + stage.deactivate)))
             for stage in project.stages]
    users = [(stage, named) for stage, named in users if named]
    if users:
        listed = "; ".join(f"stage {stage!r} names {', '.join(named)}"
                           for stage, named in users)
        raise EditRefused(f"cannot remove a condition that a stage still switches "
                          f"({listed}); take it out of those stages first")


def replace_conditions(project: Project, update: ConditionsUpdate) -> Project:
    """The boundary conditions, as one list, and gravity: what
    `PATCH /api/project/conditions` sends. A field the update leaves out stays."""
    payload = project.model_dump()
    if update.boundary_conditions is not None:
        _refuse_staged_conditions(project, {c.id for c in update.boundary_conditions})
        payload["boundary_conditions"] = [c.model_dump()
                                          for c in update.boundary_conditions]
    if update.gravity is not None:
        payload["gravity"] = update.gravity
    return _edited(project, payload)


def find_condition(project: Project, id: str):
    """The boundary condition `id`."""
    return project.boundary_conditions[
        _index(project.boundary_conditions, id, "boundary condition")]


def add_condition(project: Project, record) -> Project:
    """`project` with the boundary condition `record` (`drafts.water_pressure_condition`,
    `drafts.displacement_condition`)."""
    taken = set(project.part_keys()) | set(project.stageable_keys()) | RESERVED
    taken |= {r.id for field in STRUCTURES for r in getattr(project, field)}
    taken |= {c.id for c in project.boundary_conditions}
    if record.id in taken:
        raise EditRefused(f"there is already a part or a condition {record.id!r}; give "
                          "another id.")
    payload = project.model_dump()
    payload["boundary_conditions"].append(record.model_dump())
    return _edited(project, payload)


def update_condition(project: Project, id: str, **fields) -> Project:
    """The boundary condition `id` with the fields given, by their schema names.

    A new `on` drops what the old target named (`face`, `part`, `points`) unless it is
    given too, as the dialog does when its first question gets another answer."""
    find_condition(project, id)
    payload = project.model_dump()
    record = next(c for c in payload["boundary_conditions"] if c["id"] == id)
    if "on" in fields and fields["on"] != record["on"]:
        record.update({"face": None, "part": None, "points": None})
    record.update(fields)
    return _edited(project, payload)


def standard_conditions(project: Project) -> Project:
    """The standard supports put back: the bottom fixed, the sides on rollers
    (`schemas.standard_conditions`), in place of every displacement condition on a face.
    The water pressure conditions and the conditions on parts, lines and points stay, so
    the button and `kratos-cli boundary standard` undo only what they replace."""
    payload = project.model_dump()
    kept = [c for c in payload["boundary_conditions"]
            if not (c["kind"] == "displacement" and c["on"] == "face")]
    payload["boundary_conditions"] = kept
    standard = drafts.standard_conditions(_edited(project, payload))
    payload["boundary_conditions"] = [c.model_dump() for c in standard] + kept
    return _edited(project, payload)


def set_gravity(project: Project, on: bool) -> Project:
    """`project` with gravity on or off (`kratos-cli gravity`, the explorer's check box)."""
    return _edited(project, {**project.model_dump(), "gravity": on})


def remove_condition(project: Project, id: str) -> Project:
    """The project without the boundary condition `id`."""
    find_condition(project, id)
    _refuse_staged_conditions(project, {c.id for c in project.boundary_conditions} - {id})
    payload = project.model_dump()
    payload["boundary_conditions"] = [c for c in payload["boundary_conditions"]
                                      if c["id"] != id]
    return _edited(project, payload)


# ── Stages, one at a time ───────────────────────────────────────────────────
#
# The Stages toolbar's Add, Insert, Copy and Delete, the stage panel's fields and the
# Model explorer's checkbox in Staged construction mode, each made with the list
# transform the GUI makes (`stages.added` ... `stages.set_active`) and stored the way
# `PATCH /api/project/stages` stores a list (`replace_stages`).

def find_stage(project: Project, id: str):
    """The stage `id`."""
    return project.stages[_index(project.stages, id, "stage")]


def add_stage(project: Project, *, before: str | None = None, copy_of: str | None = None,
              id: str | None = None, **fields) -> tuple[Project, object]:
    """A new stage -- at the end of the sequence, `before` a stage (Insert), or after
    `copy_of` with its solver settings (Copy) -- with the id and the fields given.
    Returns the project and the stage."""
    for named in (before, copy_of):
        if named is not None:
            _index(project.stages, named, "stage")
    if id is not None:
        _refuse_taken(id, [stage.id for stage in project.stages], "stage")
    if before is not None:
        listed = stages.inserted(project, before)
    elif copy_of is not None:
        listed = stages.copied(project, copy_of)
    else:
        listed = stages.added(project)
    fresh = next(stage.id for stage in listed
                 if stage.id not in {p.id for p in project.stages})
    payload = [stage.model_dump() for stage in listed]
    for stage in payload:
        if stage["id"] == fresh:
            stage.update(fields, id=id or fresh)
        if id is not None and stage["parent"] == fresh:
            stage["parent"] = id
    edited = replace_stages(project, StagesUpdate.model_validate({"stages": payload}))
    return edited, next(stage for stage in edited.stages if stage.id == (id or fresh))


def update_stage(project: Project, id: str, **fields) -> Project:
    """The stage `id` with the fields given, by their schema names."""
    _index(project.stages, id, "stage")
    payload = [stage.model_dump() for stage in project.stages]
    next(stage for stage in payload if stage["id"] == id).update(fields)
    return replace_stages(project, StagesUpdate.model_validate({"stages": payload}))


def remove_stage(project: Project, id: str) -> Project:
    """The project without stage `id`, its children starting from its parent."""
    _index(project.stages, id, "stage")
    return replace_stages(project, StagesUpdate(stages=stages.removed(project, id)))


def switch_parts(project: Project, id: str, keys: list[str], active: bool) -> Project:
    """The parts `keys` in the model (`active`) or out of it from stage `id` on, as the
    Model explorer's checkbox switches them in Staged construction mode."""
    _index(project.stages, id, "stage")
    stageable = project.stageable_keys()
    for key in keys:
        if key not in stageable:
            raise EditRefused(_no_part(project, key, stageable))
    return replace_stages(project, StagesUpdate(
        stages=stages.set_active(project, id, list(keys), active)))


def part_names(project: Project) -> dict[str, str]:
    """What each part is called, keyed by its id: a layer's name for its soil, a drawn
    solid's label, and the name a structure, load or condition was given with --name."""
    names = dict(project.soil_body_labels)
    names.update((part.key, part.label) for part in project.custom_parts)
    for record in (*project.beams, *project.anchors, *project.interfaces,
                   *project.normal_loads, *project.loads, *project.boundary_conditions):
        names.setdefault(record.id, record.name)
    return names


def _no_part(project: Project, word: str, stageable: list[str]) -> str:
    """Why `word` is not a part a stage can switch. A stage takes a part's id, and the
    word most often typed instead is the name given with --name, so a part called
    `word` is named with the id to type."""
    named = [key for key, name in part_names(project).items()
             if key in stageable and name.casefold() == word.casefold()]
    if not named:
        return (f"there is no part {word!r} to switch; `kratos-cli parts` lists the parts "
                "a stage can switch")
    ids = " or ".join(named)
    return (f"there is no part {word!r} to switch: {word!r} is the name of the part with "
            f"id {ids}, and a stage switches a part by its id. Use {ids}.")


def staged_excavation_stages(project: Project) -> Project:
    """The whole staged-excavation sequence derived from the model -- settle, build the
    wall, then dig and prop lift by lift (`stages.staged_excavation_stages`) -- replacing
    whatever is there."""
    return replace_stages(project, StagesUpdate(
        stages=stages.staged_excavation_stages(project)))
