"""The edits a project can be given, whoever gives them.

Two front ends edit one model: the browser, through the HTTP routes (`backend/routes/`),
and the terminal, through the command line (`cli/`, plan/active/cli-plan.md). Every edit
is made here, once, so the two cannot come to different answers for the same change. A
route is this module plus the HTTP around it -- reading the store, writing it back, and
turning a refusal into a status code (`backend.routes.common.refusals`).

Each edit takes a `Project` and returns a new one; the project it was given is never
changed. An edit is validated as a whole project before it is returned, so a change
that would leave the model inconsistent is refused field by field (a pydantic
`ValidationError`) rather than made. The refusals that are not about one field are this
module's own: `EditRefused`, and `UnknownPart` and `DeckReadOnly` under it. A phase
sequence that cannot run is `core.model.phases.PhaseError`.

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
from pathlib import Path

from core import scripting
from core.kratos import materials
from core.model import drafts, phases, units
from core.model.load_translation import translate as translate_loads
from core.model.schemas import (CustomPart, DimensionUpdate, LayersUpdate, MaterialsUpdate,
                                MeshRequest, PhasesUpdate, Project, StructuresUpdate,
                                UnitsUpdate, WaterLevel, WaterUpdate)
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
    return Project.model_validate(value)


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
    folder = path.parent if str(path.parent) else Path(".")
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            file.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return path


# ── Soil, water, materials, structures ──────────────────────────────────────

def replace_layers(project: Project, update: LayersUpdate) -> Project:
    """The soil stack, and whatever of its context the update carries.

    The layer objects validate individually in the update; validating the project adds
    material references, borehole coverage and stack continuity.
    """
    payload = project.model_dump()
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
    return Project.model_validate(payload)


def set_water(project: Project, update: WaterUpdate) -> Project:
    """The project's water level, or none with `water=None` -- the one water edit
    `replace_layers` cannot express, since there an omitted `water` means "leave it"."""
    payload = project.model_dump()
    payload["water"] = update.water.model_dump() if update.water is not None else None
    return Project.model_validate(payload)


def set_water_level(project: Project, level: float | None) -> Project:
    """What `water <level>` and `water off` do: move the level, or remove it.

    Everything else about an existing level -- its specific weight above all -- is the
    user's and is kept; a new level takes the schema's defaults. A level outside the
    model describes nothing, so it is refused within the domain's own bounds, as the
    GUI's `water` command does (frontend/js/water-command.js).
    """
    if level is None:
        return set_water(project, WaterUpdate(water=None))
    domain = project.domain
    if not domain.y_bottom < level < domain.y_top:
        raise EditRefused(f"The water level must lie between {domain.y_bottom:.2f} and "
                          f"{domain.y_top:.2f} m.")
    water = (project.water.model_copy(update={"y": level}) if project.water is not None
             else WaterLevel(y=level))
    return set_water(project, WaterUpdate(water=water))


def replace_materials(project: Project, update: MaterialsUpdate) -> Project:
    """The material library. Validating the whole project is the point: it is what
    refuses a material a layer still points at."""
    payload = project.model_dump()
    payload["materials"] = [material.model_dump() for material in update.materials]
    return Project.model_validate(payload)


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
    return Project.model_validate(payload)


# ── Phases ──────────────────────────────────────────────────────────────────

def replace_phases(project: Project, update: PhasesUpdate) -> Project:
    """The construction sequence.

    Two validations, and they are different things. The schema's own checks run first
    -- one root, no cycles, no part both activated and deactivated in one phase, every
    key a key the model has. Then the tree has to *linearise*: Kratos runs one flat
    `execution_list`, so two phases starting from the same parent have no order to run
    in, and that is `phases.PhaseError`, naming the phases that branch.

    `linearise` is deliberately not a schema validator: a branch is a legitimate thing
    to have half-built in an editor, and refusing it in `Project` would make it
    impossible to type. It is refused here, at the edit, rather than at export, because
    this is where whoever made it can still see what they did.
    """
    _phases_of_a_deck_are_read_only(project)
    payload = project.model_dump()
    payload["phases"] = [phase.model_dump() for phase in update.phases]
    edited = Project.model_validate(payload)
    phases.linearise(edited)
    return edited


def default_phases(project: Project) -> Project:
    """The initial stage, then the null step (`phases.default_phases` is the authority).

    It replaces whatever is there rather than refusing when phases already exist: it is
    the way back out of a sequence that has been broken.
    """
    _phases_of_a_deck_are_read_only(project)
    payload = project.model_dump()
    payload["phases"] = [phase.model_dump() for phase in phases.default_phases(project)]
    return Project.model_validate(payload)


def _phases_of_a_deck_are_read_only(project: Project) -> None:
    """A deck's phases are its stages, read from it (`core.kratos.external_deck`); the
    deck is what is calculated, so an edit made here would change nothing that is."""
    if project.deck is not None:
        raise DeckReadOnly(
            f"The phases of {project.name} are the stages of its Kratos deck "
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
    return Project.model_validate(payload), notes


def set_units(project: Project, update: UnitsUpdate) -> tuple[Project, list[str]]:
    """Re-express the whole project in another unit system (`core/model/units.py`).

    The one place values are converted. A variable whose dimension is not known is kept
    as typed and named in the notes, for the user to convert.
    """
    payload, notes = units.convert_project(project.model_dump(mode="json"),
                                           update.unit_system)
    return Project.model_validate(payload), notes


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


def with_imported_part(project: Project, filename: str | None,
                       built: dict) -> tuple[Project, CustomPart]:
    """`project` with the solid read from a CAD file, and the part it became.

    `built` is what `core.gmsh_worker.import_job` answered. The key follows the highest
    import key in use, not the count: a deleted imported_0 must not let the next import
    take a key that imported_1 still holds.
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
        # gmsh measured it while the part was open; kept so `Project.extent` can say
        # how far the model reaches without reopening every .brep.
        bbox=tuple(built["bbox"]),
    )
    edited.custom_parts.append(part)
    return edited, part


def without_custom_parts(project: Project, keys: list[str]) -> Project:
    """`project` minus the custom parts `keys`, validated like any other edit.

    A part a phase still names is refused, not quietly unstaged: which phases should
    lose it is a modelling decision. Left to validation instead, the project would be
    one every later edit fails on with "names no such part". A mesh size for the part
    goes with it -- it describes nothing else.
    """
    gone = set(keys)
    users = [(phase.id, sorted(gone & set(phase.activate + phase.deactivate)))
             for phase in project.phases]
    users = [(phase, named) for phase, named in users if named]
    if users:
        listed = "; ".join(f"phase {phase!r} names {', '.join(named)}"
                           for phase, named in users)
        raise EditRefused(f"cannot delete a part that a phase still uses ({listed}); take "
                          "it out of those phases first")
    payload = project.model_dump()
    payload["custom_parts"] = [p for p in payload["custom_parts"] if p["key"] not in gone]
    payload["mesh"]["body_sizes"] = {k: v for k, v in payload["mesh"]["body_sizes"].items()
                                     if k not in gone}
    return Project.model_validate(payload)


def without_custom_part(project: Project, key: str) -> Project:
    """`project` minus the one custom part `key`, which has to be there."""
    if not any(p.key == key for p in project.custom_parts):
        raise UnknownPart(f"no custom part with key {key!r}")
    return without_custom_parts(project, [key])


# ── Meshing ─────────────────────────────────────────────────────────────────

def unknown_mesh_keys(project: Project, settings: MeshRequest) -> list[str]:
    """The bodies `settings` names -- to mesh, or to size -- that this project does not
    have, sorted. Empty when every one is the project's own."""
    named = set(settings.volume_keys or []) | set(settings.body_sizes)
    return sorted(named - set(project.part_keys()))


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
# `layers[L1].tops[bh1]` or `layers[L1].tops.bh1`.

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

    A custom part goes the way `without_custom_part` takes it -- refused while a phase
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
    """The edited payload as a project. An edit inside the phases is one of the phases,
    so it has to linearise as well, and a deck's are not edited at all."""
    if tokens[0][1] == "phases":
        return replace_phases(project, PhasesUpdate(phases=payload["phases"]))
    return Project.model_validate(payload)


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


# ── The ground: domain, boreholes, layers, materials, excavation ─────────────
#
# The edits the GUI's soil dialogs make in the browser (frontend/base/js/dialogs.js), so
# the command line makes them the same way: a borehole brings levels for every layer, a
# moved level moves its neighbour's, a deleted layer's neighbour closes the gap, and an
# edit that would cross a neighbour is refused rather than made.

class UnknownRecord(EditRefused):
    """An edit names a borehole, layer or material the project does not have."""


def set_domain(project: Project, *, x: tuple[float, float] | None = None,
               y: tuple[float, float] | None = None,
               z: tuple[float, float] | None = None) -> tuple[Project, list[str]]:
    """The model's extents, on the axes given: `x` and `z` as (from, to), `y` as
    (bottom, top). A section cut outside the new extents is moved to their middle, and
    the notes say so."""
    payload = project.model_dump()
    domain = payload["domain"]
    if x is not None:
        domain["x0"], domain["x1"] = x
    if y is not None:
        domain["y_bottom"], domain["y_top"] = y
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
    return Project.model_validate(payload), notes


def add_borehole(project: Project, **fields) -> Project:
    """A borehole (`drafts.borehole`), with every layer's levels there copied from the
    last borehole, so the stack stays whole -- what `App.addBorehole` does."""
    if fields.get("id") is not None:
        _refuse_taken(fields["id"], [b.id for b in project.boreholes], "borehole")
    new = drafts.borehole(project, **fields)
    payload = project.model_dump()
    payload["boreholes"].append(new.model_dump())
    if project.boreholes:
        last = project.boreholes[-1].id
        for layer in payload["layers"]:
            layer["tops"][new.id] = layer["tops"][last]
            layer["bots"][new.id] = layer["bots"][last]
    return Project.model_validate(payload)


def update_borehole(project: Project, id: str, **fields) -> Project:
    """The borehole `id` with the fields given (`name`, `x`, `y`, `head`, `water`)."""
    payload = project.model_dump()
    record = payload["boreholes"][_index(project.boreholes, id, "borehole")]
    record.update({name: value for name, value in fields.items() if value is not None})
    return Project.model_validate(payload)


def remove_borehole(project: Project, id: str) -> Project:
    """The project without borehole `id` and its levels in every layer. The last one
    stays: the layered build reads its levels."""
    at = _index(project.boreholes, id, "borehole")
    if len(project.boreholes) == 1:
        raise EditRefused(f"{id} is the only borehole, and a model keeps at least one "
                          "borehole: the soil stack is read off it.")
    payload = project.model_dump()
    del payload["boreholes"][at]
    for layer in payload["layers"]:
        layer["tops"].pop(id, None)
        layer["bots"].pop(id, None)
    return Project.model_validate(payload)


def add_layer(project: Project, id: str, material: str, *, name: str | None = None,
              bottom: float | None = None, thickness: float | None = None) -> Project:
    """A layer under the stack (`drafts.layer`): from the last layer's bottom -- the
    ground, for the first -- down to `bottom`, or `thickness` below that."""
    _refuse_taken(id, [layer.id for layer in project.layers], "layer")
    new = drafts.layer(project, id, material, name=name, bottom=bottom, thickness=thickness)
    payload = project.model_dump()
    payload["layers"].append(new.model_dump())
    return Project.model_validate(payload)


def update_layer(project: Project, id: str, *, material: str | None = None,
                 name: str | None = None, top: float | None = None,
                 bottom: float | None = None, at: str | None = None) -> Project:
    """The layer `id` with a new material, name, top or bottom.

    A level is moved at the borehole `at`, or at every borehole, and it moves the
    neighbour's with it: a top is the bottom of the layer above, a bottom the top of the
    layer below. A level that would cross a neighbour's other face is refused, as the
    soil dialog refuses it.
    """
    index = _index(project.layers, id, "layer")
    boreholes = [b.id for b in project.boreholes]
    if at is not None and at not in boreholes:
        raise UnknownRecord(f"there is no borehole {at!r}; there are: {', '.join(boreholes)}")
    payload = project.model_dump()
    layers = payload["layers"]
    layer = layers[index]
    if material is not None:
        layer["mat"] = material
    if name is not None:
        layer["name"] = name
    for bh in ([at] if at else boreholes):
        if top is not None:
            if top < layer["bots"][bh]:
                raise EditRefused(f"{id}: the top must be at or above its bottom "
                                  f"({layer['bots'][bh]:g} at {bh}).")
            if index > 0 and top > layers[index - 1]["tops"][bh]:
                raise EditRefused(f"{id}: the top cannot rise above the top of the layer "
                                  f"above ({layers[index - 1]['tops'][bh]:g} at {bh}).")
            layer["tops"][bh] = top
            if index > 0:
                layers[index - 1]["bots"][bh] = top
        if bottom is not None:
            if bottom > layer["tops"][bh]:
                raise EditRefused(f"{id}: the bottom must be at or below its top "
                                  f"({layer['tops'][bh]:g} at {bh}).")
            if index < len(layers) - 1 and bottom < layers[index + 1]["bots"][bh]:
                raise EditRefused(f"{id}: the bottom cannot drop below the bottom of the "
                                  f"layer below ({layers[index + 1]['bots'][bh]:g} at {bh}).")
            layer["bots"][bh] = bottom
            if index < len(layers) - 1:
                layers[index + 1]["tops"][bh] = bottom
    return Project.model_validate(payload)


def split_layer(project: Project, id: str, new_id: str | None = None) -> Project:
    """The soil dialog's Insert: the layer `id` halved at every borehole, the lower half
    a new layer of the same material."""
    index = _index(project.layers, id, "layer")
    taken = [layer.id for layer in project.layers]
    new_id = new_id if new_id is not None else drafts.free_id(taken, "L")
    _refuse_taken(new_id, taken, "layer")
    payload = project.model_dump()
    upper = payload["layers"][index]
    lower = {"id": new_id, "name": new_id, "mat": upper["mat"], "tops": {}, "bots": {}}
    for bh in upper["tops"]:
        middle = (upper["tops"][bh] + upper["bots"][bh]) / 2
        lower["tops"][bh], lower["bots"][bh] = middle, upper["bots"][bh]
        upper["bots"][bh] = middle
    payload["layers"].insert(index + 1, lower)
    return Project.model_validate(payload)


def remove_layer(project: Project, id: str) -> Project:
    """The project without layer `id`, the gap closed by the layer above -- or, for the
    top layer, by the one below -- as the soil dialog's Delete closes it."""
    index = _index(project.layers, id, "layer")
    payload = project.model_dump()
    layers = payload["layers"]
    removed = layers.pop(index)
    if index > 0:
        layers[index - 1]["bots"] = removed["bots"]
    elif layers:
        layers[0]["tops"] = removed["tops"]
    return Project.model_validate(payload)


def add_material(project: Project, material) -> Project:
    """`project` with the new soil `material` (`drafts.soil` makes one)."""
    _refuse_taken(material.id, [m.id for m in project.materials], "material")
    payload = project.model_dump()
    payload["materials"].append(material.model_dump())
    return Project.model_validate(payload)


def update_material(project: Project, id: str, *, name: str | None = None,
                    color: str | None = None, law: str | None = None,
                    variables: dict | None = None, unset: list[str] = ()) -> Project:
    """The material `id` with the fields and variables given; `unset` names variables to
    leave out, so the export derives them where it can."""
    payload = project.model_dump()
    record = payload["materials"][_index(project.materials, id, "material")]
    for field, value in (("name", name), ("color", color), ("constitutive_law", law)):
        if value is not None:
            record[field] = value
    record["variables"].update(variables or {})
    for variable in unset:
        if variable not in record["variables"]:
            raise EditRefused(f"{id} has no variable {variable}; it has: "
                              + ", ".join(record["variables"]))
        del record["variables"][variable]
    return Project.model_validate(payload)


def remove_material(project: Project, id: str) -> Project:
    """The project without material `id`. A material a layer or a part still uses is
    refused by validation, naming it."""
    at = _index(project.materials, id, "material")
    payload = project.model_dump()
    del payload["materials"][at]
    return Project.model_validate(payload)


def set_excavation(project: Project, *, x: tuple[float, float] | None = None,
                   z: tuple[float, float] | None = None,
                   levels: list[float] | None = None) -> tuple[Project, list[str]]:
    """The pit: its plan outline (`x`, `z` as from, to) and the levels it is dug to,
    shallowest first -- one lift per level, each its own body, deactivated in its own
    phase. The floor is the last level."""
    payload = project.model_dump()
    pit = payload["excavation"]
    if x is not None:
        pit["x0"], pit["x1"] = x
    if z is not None:
        pit["z0"], pit["z1"] = z
    if levels is not None:
        pit["levels"], pit["floor_y"] = list(levels), levels[-1]
    edited = Project.model_validate(payload)
    notes = []
    if edited.layered_soil and len(edited.excavation.levels) < 2:
        notes.append("With one level a layered model digs nothing: its pit is cut only "
                     "when it is dug in two or more levels, one phase per lift.")
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
    return Project.model_validate(payload)


def _index(records: list, id: str, what: str) -> int:
    for index, record in enumerate(records):
        if record.id == id:
            return index
    names = ", ".join(record.id for record in records) or "none"
    raise UnknownRecord(f"there is no {what} {id!r}; there are: {names}")


def _refuse_taken(id: str, taken: list[str], what: str) -> None:
    if id in taken:
        raise EditRefused(f"there is already a {what} {id!r}; give another id.")
