"""Resolving a stage tree into the sequence Kratos runs.

A `Stage` stores a *diff* against its parent -- what this stage switches on and off --
because that is what the reference deck's `stage_preprocess` is and because absolute
state would have to be rewritten in every later stage whenever a part is added to the
model (see `schemas.Stage`). This module is the only place that walks the parent chain,
and it turns that tree into the three things the exporter needs:

*   `linearise` -- the order the stages run in, or a refusal.
*   `active_parts` -- what is in the model during a given stage, which becomes each
    stage's `problem_domain_sub_model_part_list`.
*   `transitions` -- per stage, what changes, which becomes its `stage_preprocess`
    Activate/Deactivate operations.

and two that are not about export at all:

*   `initial_stage` -- the stage a new project starts with.
*   `initial` and `check_settings` -- the initial stage, which chooses the calculation
    type and the stress initialisation for the whole sequence, and the refusal of a
    sequence that chooses them anywhere else.
*   `added`, `inserted`, `removed`, `copied`, `set_active` -- the edits the GUI's
    Stages toolbar and Model explorer make to a list, for the command line to make
    the same way.

Pure model logic: no gmsh, no Kratos, no meshing. It works on part *keys*, the model's
own namespace (`Project.stageable_keys`), not on deck part names -- one drawn
`Interface` here is eight parts in the deck, and making that mapping is export's job
(`core/kratos/writer.py:_interface_by_body`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.model.schemas import (CONVERGENCE_CRITERIA, DRY, INTERPOLATE, PHREATIC,
                                STAGED_CONDITIONS, AnyCondition, Stage, Project,
                                WaterPressureCondition, followed_tolerance)


class StageError(Exception):
    """A stage tree that cannot become the one sequence Kratos runs.

    Not a `ValidationError`: the schema deliberately accepts trees it cannot run, so
    that a branch can be half-built in the editor, and this is where that becomes a
    problem -- at export, with a message about what to do.
    """


def linearise(project: Project) -> list[Stage]:
    """The stages in execution order, or raise.

    Depth first in creation order, which for a chain is just the chain. Kratos'
    `SequentialOrchestrator` takes one flat `execution_list`, so a tree that branches
    has no execution order and this refuses it by name. A branch would
    mean two runs to compare, which is not supported, and saying which stages branch is
    the difference between a message the user can act on and one they cannot.
    """
    if not project.stages:
        return []

    children: dict[str | None, list[Stage]] = {}
    for stage in project.stages:
        children.setdefault(stage.parent, []).append(stage)

    for parent, siblings in children.items():
        if parent is not None and len(siblings) > 1:
            names = ", ".join(repr(stage.id) for stage in siblings)
            raise StageError(
                f"stages {names} all start from {parent!r}, so there is no single "
                "order to run them in. Kratos runs one sequence of stages: give each "
                "of them a different stage to start from, or delete all but one."
            )

    order: list[Stage] = []
    stack = list(reversed(children.get(None, [])))
    while stack:
        stage = stack.pop()
        order.append(stage)
        stack.extend(reversed(children.get(stage.id, [])))

    # The schema guarantees one root and no cycles, so every stage is reachable. If that
    # ever stops being true, losing stages silently would be the worst way to find out.
    if len(order) != len(project.stages):
        missing = sorted({p.id for p in project.stages} - {p.id for p in order})
        raise StageError(f"stages unreachable from the first one: {', '.join(missing)}")
    return order


FLOW = "flow"
"""The calculation type of a groundwater flow stage (`schemas.Stage.calculation`)."""


def groundwater_flow(project: Project) -> bool:
    """Whether the project is a groundwater flow calculation: it has stages, and every
    one of them is a flow stage. Raises `StageError` when some are and some are not.

    One type for the whole sequence, because the element type is in the .mdpa and every
    stage reads that one file: a flow stage needs water pressure elements, a mechanical
    stage the coupled ones. A project without stages is one mechanical stage, as it
    always was.
    """
    flow = [stage for stage in project.stages if stage.calculation == FLOW]
    if not flow:
        return False
    other = [stage for stage in project.stages if stage.calculation != FLOW]
    if other:
        def named(stages: list[Stage]) -> str:
            return ", ".join(repr(stage.name) for stage in stages)
        raise StageError(
            f"one calculation cannot mix flow stages ({named(flow)}) with "
            f"mechanical stages ({named(other)}): a flow stage solves the water "
            "pressure alone, on elements a mechanical stage cannot use. Give every "
            "stage the same calculation type.")
    return True


def initial(project: Project) -> Stage | None:
    """The initial stage: the one that starts from the model as built (`parent` None).
    The schema allows one, so there is one unless there are no stages at all."""
    return next((stage for stage in project.stages if stage.parent is None), None)


def check_settings(project: Project) -> None:
    """Raise `StageError` unless the initial stage alone chooses the calculation type
    and the stress initialisation.

    The calculation type is one for the whole sequence -- the element type is in the
    .mdpa, which every stage reads -- so it is chosen once, in the initial stage, and
    every later stage has it. The stresses are initialised once, before anything is
    built, so a later stage has no stress initialisation. Checked where stages are
    edited (`core.session.replace_stages`) rather than by the schema, so that a project
    saved before either rule still opens, and can be put right.
    """
    first = initial(project)
    if first is None:
        return

    def named(stages: list[Stage]) -> str:
        names = ", ".join(repr(stage.name) for stage in stages)
        return f"stage {names} is" if len(stages) == 1 else f"stages {names} are"

    other = [stage for stage in project.stages if stage.calculation != first.calculation]
    if other:
        raise StageError(
            f"{named(other)} not {first.calculation}, as the initial stage "
            f"{first.name!r} is: the calculation type is chosen in the initial stage, and "
            "every later stage has it. Change it there.")
    later = [stage for stage in project.stages
             if stage is not first and stage.stress_initialisation != "none"]
    if later:
        raise StageError(
            f"{named(later)} given a stress initialisation, which only the initial stage "
            f"{first.name!r} has: set it to none.")


def gravity(project: Project) -> bool:
    """Whether the self weight acts in the calculation, in every stage of it.

    A mechanical sequence has it when its initial stage initialises the stresses from it
    -- by the K0 procedure or by gravity loading -- and not at all when the initial stage
    initialises none. Then it is the weight of every body: the soil, and the sheet piles,
    walls and anchors with their `DENSITY` (`core.kratos.parameters._gravity`). A flow
    sequence, which has no stresses to initialise, and a project with no stages have it
    as before. It is the one switch for the self weight: a model loaded by its boundary
    conditions alone has an initial stage that initialises no stresses.
    """
    first = initial(project)
    if first is None or first.calculation != "mechanical":
        return True
    return first.stress_initialisation != "none"


def _chain_to(project: Project, stage: Stage | str) -> list[Stage]:
    """The stages from the root down to `stage`, inclusive.

    Follows parents rather than the execution order, so it resolves a branch too. The
    editor needs that: a half-built branch still has to be able to say what is in it.
    """
    by_id = {each.id: each for each in project.stages}
    at: Stage | None = by_id[stage] if isinstance(stage, str) else stage
    chain: list[Stage] = []
    while at is not None:
        chain.append(at)
        at = by_id[at.parent] if at.parent is not None else None
    return list(reversed(chain))


def start_of(project: Project, stage: Stage | str) -> float:
    """When `stage` starts, in the project's unit of time: the initial stage's
    `start_time` plus the durations of the stages before it along its chain -- the deck's
    `start_time` for it (`core.kratos.writer._sequenced_stages`; `App.Stages.startOf`)."""
    chain = _chain_to(project, stage)
    return chain[0].start_time + sum(each.duration for each in chain[:-1])


def active_parts(project: Project, stage: Stage | str) -> set[str]:
    """Which parts are in the model during `stage`.

    Everything starts active: the mesh carries every part, and the first stage's job is
    to switch off what has not been built yet. That is what the reference's stage 1
    does -- it deactivates the wall, the anchor and all eight interfaces before solving
    for the initial stresses of ground that has nothing in it.
    """
    active = set(project.stageable_keys())
    for each in _chain_to(project, stage):
        # `Stage` forbids a part in both lists, so the order within a stage is moot.
        active -= set(each.deactivate)
        active |= set(each.activate)
    return active


# -- the water of a stage ----------------------------------------------------

@dataclass(frozen=True)
class StageWater:
    """The water of one stage, or of the model as built, resolved: what the deck writes
    in it and the Flow conditions and Staged construction tabs draw for it.

    `conditions` is every boundary condition on in the stage, by id, with the values
    the stage gives it (`Stage.condition_values`). Of the water lines among them
    (`Project.water_lines`), `phreatic` is the phreatic line -- the water of every soil
    that takes no other -- typed `Phreatic_Multi_Line` whatever its record says, and
    every other one is a head line, typed `Head_Line` (`head_lines`), for the soils that
    take it. `soil_water` is each soil part key (`Project.soil_part_keys`) that takes a
    water of its own, to a head line's id, `INTERPOLATE` or `DRY`: an entry naming a line
    not on in the stage, or the phreatic line itself, is the phreatic line, and so is no
    entry."""
    phreatic: WaterPressureCondition | None
    soil_water: dict[str, str] = field(default_factory=dict)
    conditions: dict[str, AnyCondition] = field(default_factory=dict)

    def head_lines(self) -> list[WaterPressureCondition]:
        """The water lines on in the stage that are not its phreatic line."""
        return [c for c in self.conditions.values()
                if isinstance(c, WaterPressureCondition) and c.on in ("domain", "line")
                and c.fluid_pressure_type == "Head_Line"]

    def water_of_bodies(self, project: Project) -> dict[str, str]:
        """Each soil body that takes a water of its own, as `Project.water_of_bodies`
        reads `soil_water`: a body's own entry, else its layer's."""
        return _of_bodies(project, self.soil_water)


def _of_bodies(project: Project, chosen: dict[str, str]) -> dict[str, str]:
    bodies = [key for key, *_ in project.soil_bodies()]
    bodies += [part.key for part in project.custom_parts if part.mat is not None]
    out = {}
    for key in bodies:
        water = chosen.get(key, chosen.get(key.partition("__")[0]))
        if water is not None:
            out[key] = water
    return out


def stage_values(project: Project, stage: Stage | str | None) -> dict[str, dict]:
    """Each condition's values in `stage` that are not its own: the stage's
    `condition_values` over those of the stages before it, field by field."""
    values: dict[str, dict] = {}
    for each in _chain_to(project, stage) if stage is not None else []:
        for id, fields in each.condition_values.items():
            values[id] = {**values.get(id, {}), **fields}
    return values


def with_values(condition: AnyCondition, fields: dict | None) -> AnyCondition:
    """`condition` with the values `fields` gives it, checked as a record of its own is:
    a phreatic line a stage moves still needs its x to increase."""
    if not fields:
        return condition
    return type(condition).model_validate({**condition.model_dump(), **fields})


def water_in(project: Project, stage: Stage | str | None) -> StageWater:
    """The water of `stage`, or of the model as built for None: the model that the Flow
    conditions tab shows and an unstaged project exports (`StageWater`).

    The phreatic line is the one the nearest stage along the chain names
    (`Stage.phreatic_line`); when none does, it is the line typed `Phreatic_Multi_Line`
    that is on -- the model as built's, or the one a stage switched on in place of
    another, the way the phreatic line was switched before a stage could name it. The
    soils' water is `Project.soil_water` with each stage's `soil_water` over it, in
    order."""
    chain = _chain_to(project, stage) if stage is not None else []
    on = active_parts(project, chain[-1]) if chain else None
    values = stage_values(project, stage)
    named: str | None = None
    chosen = dict(project.soil_water)
    for each in chain:
        if each.phreatic_line is not None:
            named = each.phreatic_line
        chosen.update(each.soil_water)

    conditions: dict[str, AnyCondition] = {}
    for condition in project.boundary_conditions:
        if not condition.active:
            continue
        if on is not None and condition.kind in STAGED_CONDITIONS and condition.id not in on:
            continue
        conditions[condition.id] = with_values(condition, values.get(condition.id))

    lines = [found for line in project.water_lines()
             if isinstance(found := conditions.get(line.id), WaterPressureCondition)]
    if named is not None:
        phreatic_id = named if any(line.id == named for line in lines) else None
    else:
        phreatic_id = next((line.id for line in lines
                            if line.fluid_pressure_type == "Phreatic_Multi_Line"), None)
    phreatic: WaterPressureCondition | None = None
    for line in lines:
        role = "Phreatic_Multi_Line" if line.id == phreatic_id else "Head_Line"
        if line.fluid_pressure_type != role:
            line = line.model_copy(update={"fluid_pressure_type": role})
            conditions[line.id] = line
        if line.id == phreatic_id:
            phreatic = line

    heads = {line.id for line in lines if line.id != phreatic_id}
    soil_water = {key: water for key, water in chosen.items()
                  if water in (INTERPOLATE, DRY) or water in heads}
    return StageWater(phreatic=phreatic, soil_water=soil_water, conditions=conditions)


SATURATED = "SaturatedLaw"
"""Kratos' retention law when a material names none: a soil saturated whatever its water
pressure, whose flow is linear in it."""


def seepage(project: Project) -> bool:
    """Whether the project has a seepage face a flow deck writes: one, in a 2D section --
    Kratos' seepage conditions are line conditions (`core.kratos.writer`)."""
    return project.dimension == 2 and any(
        condition.kind == "seepage" for condition in project.boundary_conditions)


def model_strategy(project: Project, stage: Stage | str) -> str | None:
    """The strategy a flow stage's model calls for: its default strategy
    (`core.model.solver`), and the one strategy it can have with a seepage face. `None`
    for a mechanical stage, which is Newton-Raphson unless it says otherwise, and
    whose deck leaves a seepage face out (`core.kratos.condition_checks`).

    Newton-Raphson with seepage where the stage has a seepage face on, as that strategy
    is what opens and closes the face node by node. A stage that switches its seepage
    faces off is solved as if the project had none. Newton-Raphson where a soil in the
    stage has a retention law that makes its permeability depend on the water pressure
    (Kratos' `tests/Muskat/van_genuchten_hydrostatic`). One linear solve otherwise, as a
    saturated soil's flow is linear in it (`saturated_hydrostatic`).
    """
    if isinstance(stage, str):
        stage = next(each for each in project.stages if each.id == stage)
    if stage.calculation != FLOW:
        return None
    active = active_parts(project, stage)
    if seepage(project) and any(condition.kind == "seepage" and condition.id in active
                                for condition in project.boundary_conditions):
        return "newton_raphson_with_seepage"
    # Keyed by body, as `core.kratos.writer._part_materials` is: a lift is still the
    # layer it was dug out of.
    material_of = {f"soil_{layer.id}": layer.mat for layer in project.layers}
    material_of.update({key: material_of[key.partition("__")[0]]
                        for key, *_ in project.soil_bodies()
                        if key.partition("__")[0] in material_of})
    material_of.update({part.key: part.mat for part in project.custom_parts if part.mat})
    known = {material.id: material for material in project.materials}
    for key in active:
        material = known.get(material_of.get(key, ""))
        if material and material.variables.get("RETENTION_LAW", SATURATED) != SATURATED:
            return "newton_raphson"
    return "linear"


def transitions(project: Project) -> list[tuple[Stage, set[str], set[str]]]:
    """Per stage in execution order: what genuinely switches on, and what switches off.

    Filtered against the state each stage lands on, so an instruction that changes
    nothing is dropped. Stages accumulate no-ops through ordinary editing -- delete a
    lift, add it back -- and Kratos tolerates deactivating an already inactive part, so
    nothing would break; the deck would just stop being readable, and a deck nobody can
    read is a deck nobody can check.
    """
    result: list[tuple[Stage, set[str], set[str]]] = []
    active = set(project.stageable_keys())
    for stage in linearise(project):
        switched_on = {key for key in stage.activate if key not in active}
        switched_off = {key for key in stage.deactivate if key in active}
        active = (active - switched_off) | switched_on
        result.append((stage, switched_on, switched_off))
    return result


# -- the initial stage -------------------------------------------------------

INITIAL_ID = "initial"
INITIAL_NAME = "Initial stage"


def initial_stage() -> Stage:
    """The stage a new project starts with, and the first one added to a project with
    none: "Initial stage", a mechanical stage whose stresses come from gravity loading.
    Gravity loading rather than the K0 procedure because it runs with any soil: the K0
    procedure needs each soil's K0 (`K0_NC`, or a friction angle to derive it from). It
    switches nothing off: a part drawn later is in the model until a stage says
    otherwise."""
    return Stage(id=INITIAL_ID, name=INITIAL_NAME, stress_initialisation="gravity")


# -- editing ------------------------------------------------------------------
#
# What the Stages toolbar's buttons and the Model explorer's checkbox do to the list
# (`frontend/js/stages.js`: `added`, `inserted`, `removed`, `copied`, `setActive`), so
# the command line edits a sequence the way the GUI does. Each returns a new list and
# leaves the project alone; `core.session` stores it the way `PATCH /api/project/stages`
# does. `tests/test_stage_parity.py` holds the two sides to the same answers.

def _fresh_number(project: Project) -> int:
    """The number N of a new stage: its place in the list (one more than the stages
    there are), raised until both the id `stage_N` and the name `Stage N` are free.
    The id and the name of a new stage then carry the same number (`Stage 3`,
    `stage_3`), not two that count different things (issue #135)."""
    ids = {stage.id for stage in project.stages}
    names = {stage.name for stage in project.stages}
    number = len(project.stages) + 1
    while f"stage_{number}" in ids or f"Stage {number}" in names:
        number += 1
    return number


def _copies(project: Project) -> list[Stage]:
    return [stage.model_copy(deep=True) for stage in project.stages]


def _last(project: Project) -> Stage | None:
    try:
        sequence = linearise(project)
    except StageError:
        sequence = list(project.stages)
    return sequence[-1] if sequence else None


def _later(project: Project, id: str, name: str, parent: str | None) -> Stage:
    """A blank stage after the initial one: the initial stage's calculation type, and
    no stress initialisation."""
    first = initial(project)
    return Stage(id=id, name=name, parent=parent,
                 calculation=first.calculation if first else "mechanical")


def added(project: Project) -> list[Stage]:
    """Add: a blank stage at the end of the sequence, starting from the last one. To a
    project with no stages, the initial stage."""
    listed = _copies(project)
    tail = _last(project)
    if tail is None:
        return [initial_stage()]
    number = _fresh_number(project)
    listed.append(_later(project, f"stage_{number}", f"Stage {number}", tail.id))
    return listed


def inserted(project: Project, id: str) -> list[Stage]:
    """Insert: a blank stage between `id` and the stage it starts from -- `id` then
    starts from the new one, or the tree would branch. Nothing goes before the initial
    stage, so before it this changes nothing."""
    listed = _copies(project)
    at = next((n for n, stage in enumerate(listed) if stage.id == id), None)
    if at is None or listed[at].parent is None:
        return listed
    made = _later(project, f"stage_{_fresh_number(project)}", "New stage",
                  listed[at].parent)
    listed[at].parent = made.id
    listed.insert(at, made)
    return listed


def removed(project: Project, id: str) -> list[Stage]:
    """Delete: the stage gone and the chain healed -- its children start from its
    parent. The initial stage is always there, so deleting it changes nothing."""
    target = next((stage for stage in project.stages if stage.id == id), None)
    if target is None or target.parent is None:
        return _copies(project)
    listed = [stage for stage in _copies(project) if stage.id != id]
    for stage in listed:
        if stage.parent == id:
            stage.parent = target.parent
    return listed


def copied(project: Project, id: str) -> list[Stage]:
    """Copy: the same solver settings, spliced in after the original, without its parts
    -- a copy repeats a step with other parts, and the same switches twice would be
    no-ops. A copy comes after the original, so it initialises no stresses."""
    listed = _copies(project)
    at = next((n for n, stage in enumerate(listed) if stage.id == id), None)
    if at is None:
        return listed
    original = listed[at]
    made = Stage(id=f"stage_{_fresh_number(project)}", name=f"{original.name} (copy)",
                 parent=original.id, calculation=original.calculation,
                 time_integration=original.time_integration,
                 reset_displacements=original.reset_displacements,
                 convergence_criterion=original.convergence_criterion,
                 max_iterations=original.max_iterations,
                 tolerated_error=original.tolerated_error,
                 absolute_tolerance=original.absolute_tolerance,
                 duration=original.duration, time_step=original.time_step,
                 solver_settings=dict(original.solver_settings))
    for stage in listed:
        if stage.parent == id:
            stage.parent = made.id
    listed.insert(at + 1, made)
    return listed


def edited(project: Project, id: str, field: str, value: object) -> list[Stage]:
    """One field of stage `id` set to `value`, as the Stages window's property grid
    sets it.

    The calculation type is the initial stage's: set there, every stage gets it, a
    stage that is not mechanical goes back to no stress initialisation, and a stage of
    another type goes to the new type's default convergence criterion
    (`schemas.CONVERGENCE_CRITERIA`), as a new stage of that type has. Its expert
    solver settings go back to the new type's defaults, as its criterion does. An
    initial stage that goes back to mechanical with no stress initialisation is
    initialised by gravity loading again, as a new project's is (`initial_stage`):
    otherwise trying flow would lose the self weight (`gravity`). Set on a later stage,
    the calculation type changes nothing. Nor does a stress initialisation on a later
    stage, but for none: a later stage has none (`check_settings`), and one opened with
    another -- an old project's later K0 procedure -- has to be able to go back to it.
    A stage whose criterion changes, either way, keeps its absolute tolerance unless it
    was the old criterion's default, which becomes the new one's
    (`schemas.ABSOLUTE_TOLERANCES`).
    """
    listed = _copies(project)
    first = initial(project)
    target = next((stage for stage in listed if stage.id == id), None)
    if target is None:
        return listed
    is_first = first is not None and id == first.id
    if field == "calculation":
        if not is_first:
            return listed
        for stage in listed:
            allowed = CONVERGENCE_CRITERIA.get(str(value), ())
            if allowed and stage.calculation != value:
                _criterion(stage, allowed[0])
                stage.solver_settings = {}
            was = stage.calculation
            stage.calculation = value  # type: ignore[assignment]
            if value != "mechanical":
                stage.stress_initialisation = "none"
            elif was != "mechanical" and stage.id == id \
                    and stage.stress_initialisation == "none":
                stage.stress_initialisation = initial_stage().stress_initialisation
        return listed
    if field == "stress_initialisation" and not is_first and value != "none":
        return listed
    if field == "convergence_criterion":
        _criterion(target, str(value))
        return listed
    setattr(target, field, value)
    return listed


def _criterion(stage: Stage, criterion: str) -> None:
    """`stage` solved on `criterion`, its absolute tolerance following the default."""
    stage.absolute_tolerance = followed_tolerance(
        stage.absolute_tolerance, stage.convergence_criterion, criterion)
    stage.convergence_criterion = criterion  # type: ignore[assignment]


def edited_solver(project: Project, id: str, key: str, value: object) -> list[Stage]:
    """One expert solver setting of stage `id` (`core.model.solver`) set to `value`, as
    the Stages window's expert settings set it -- or, with `value` None, back to its
    default, which is what the row's reset does."""
    listed = _copies(project)
    target = next((stage for stage in listed if stage.id == id), None)
    if target is None:
        return listed
    settings = {k: v for k, v in target.solver_settings.items() if k != key}
    if value is not None:
        settings[key] = value  # type: ignore[assignment]
    target.solver_settings = settings
    return listed


def set_active(project: Project, id: str, keys: list[str], wanted: bool) -> list[Stage]:
    """Make each of `keys` in the model (`wanted`) or out of it during stage `id`, and
    in that stage only, with the smallest instruction that does it: none when the
    parent already gives that state, and never both lists for one part.

    No other stage's state changes: the stages before are not edited, and each stage
    that starts from `id` is given whatever instruction keeps it as it was -- stored as
    a diff, it would otherwise follow its parent. Grandchildren need nothing, since
    their parent's state is unchanged. A stage made afterwards (`added`, `inserted`,
    `copied`) says nothing of its own, so it starts with its parent's state."""
    listed = _copies(project)
    if not any(stage.id == id for stage in listed):
        return listed
    before = _chain_to(project, id)[:-1]
    # The stages that start from this one, and the chain each had before the edit:
    # their state then is the state they keep.
    children = {stage.id: _chain_to(project, stage.id)
                for stage in project.stages if stage.parent == id and stage.id != id}

    def active_along(chain: list[Stage], key: str) -> bool:
        active = True       # everything starts in the model
        for stage in chain:
            if key in stage.deactivate:
                active = False
            if key in stage.activate:
                active = True
        return active

    def restate(stage: Stage, key: str, want: bool, given: bool) -> None:
        stage.activate = [k for k in stage.activate if k != key]
        stage.deactivate = [k for k in stage.deactivate if k != key]
        if want != given:       # only an instruction the parent does not already give
            (stage.activate if want else stage.deactivate).append(key)

    for stage in listed:
        if stage.id == id:
            for key in keys:
                restate(stage, key, wanted, active_along(before, key))
        elif stage.id in children:
            for key in keys:
                restate(stage, key, active_along(children[stage.id], key), wanted)
    return listed


# -- the water a stage gives -------------------------------------------------
#
# Each edits stage `id` alone, as `set_active` does: what it gives is a diff, so the
# stages that start from it would follow it, and each is given whatever keeps it as it
# was instead. A stage made afterwards starts with its parent's water.

def _children_kept(project: Project, id: str, listed: list[Stage], read, pin) -> list[Stage]:
    """`listed` with each stage that starts from `id` given, by `pin(stage, was)`, what
    it read (`read(project, stage_id)`) before the edit, where the edit changed it."""
    children = [stage.id for stage in project.stages if stage.parent == id and stage.id != id]
    was = {child: read(project, child) for child in children}
    after = project.model_copy(update={"stages": listed})
    for stage in listed:
        if stage.id in was and read(after, stage.id) != was[stage.id]:
            pin(stage, was[stage.id])
    return listed


def set_phreatic_line(project: Project, id: str, line: str | None) -> list[Stage]:
    """The water line `line` the phreatic line from stage `id` (None: the stage before's
    again), switched on there if it is off -- a phreatic line is on in its stage."""
    listed = (set_active(project, id, [line], True)
              if line is not None and line not in active_parts(project, id)
              else _copies(project))
    for stage in listed:
        if stage.id == id:
            stage.phreatic_line = line

    def read(p: Project, stage: str) -> str | None:
        found = water_in(p, stage).phreatic
        return found.id if found is not None else None

    def pin(stage: Stage, was: str | None) -> None:
        if was is not None:
            stage.phreatic_line = was

    return _children_kept(project, id, listed, read, pin)


def set_soil_water(project: Project, id: str, soil: str, water: str | None) -> list[Stage]:
    """The soil `soil` takes `water` from stage `id`: a water line's id, `INTERPOLATE`,
    `DRY`, or `PHREATIC` for the phreatic line; None takes the stage before's again."""
    listed = _copies(project)
    for stage in listed:
        if stage.id == id:
            stage.soil_water = dict(stage.soil_water)
            if water is None:
                stage.soil_water.pop(soil, None)
            else:
                stage.soil_water[soil] = water

    def read(p: Project, stage: str) -> str:
        return water_in(p, stage).soil_water.get(soil, PHREATIC)

    def pin(stage: Stage, was: str) -> None:
        stage.soil_water = {**stage.soil_water, soil: was}

    return _children_kept(project, id, listed, read, pin)


def set_values(project: Project, id: str, condition: str,
               fields: dict | None) -> list[Stage]:
    """The condition `condition` with the values `fields` from stage `id`, over the ones
    it gives already; None takes the stage before's values again."""
    listed = _copies(project)
    record = next((c for c in project.boundary_conditions if c.id == condition), None)
    touched = (list(fields) if fields is not None else
               list(next((s.condition_values.get(condition, {}) for s in project.stages
                          if s.id == id), {})))
    for stage in listed:
        if stage.id == id:
            values = dict(stage.condition_values)
            if fields is None:
                values.pop(condition, None)
            else:
                values[condition] = {**values.get(condition, {}), **fields}
            stage.condition_values = values
    own = record.model_dump() if record is not None else {}

    def read(p: Project, stage: str) -> dict:
        given = stage_values(p, stage).get(condition, {})
        return {field: given.get(field, own.get(field)) for field in touched}

    def pin(stage: Stage, was: dict) -> None:
        values = dict(stage.condition_values)
        values[condition] = {**was, **values.get(condition, {})}
        stage.condition_values = values

    return _children_kept(project, id, listed, read, pin)
