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

*   `staged_excavation_stages` -- a whole sequence a model script can give a project.
*   `added`, `inserted`, `removed`, `copied`, `set_active` -- the edits the GUI's
    Stages toolbar and Model explorer make to a list, for the command line to make
    the same way.

Pure model logic: no gmsh, no Kratos, no meshing. It works on part *keys*, the model's
own namespace (`Project.stageable_keys`), not on deck part names -- one drawn
`Interface` here is eight parts in the deck, and making that mapping is export's job
(`core/kratos/writer.py:_interface_by_body`).
"""

from __future__ import annotations

from core.model.schemas import Stage, Project


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


# -- a whole sequence ----------------------------------------------------

_ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
             "Eighth", "Ninth", "Tenth")


def _ordinal(n: int) -> str:
    return _ORDINALS[n - 1] if n <= len(_ORDINALS) else f"#{n}"


def staged_excavation_stages(project: Project) -> list[Stage]:
    """A whole staged-excavation sequence, built from the model.

    What a staged model script gives its model. Shaped like the reference deck,
    because the reference deck is a normal excavation
    and the shape generalises: settle the ground, build the wall, then alternate digging
    with propping. For the reference deck it reproduces all seven
    stages exactly (`tests/test_stages.py`).

        1  initial            K0 stresses; everything not yet built is switched off
        2  null_step          the same model, solved again, to settle the K0 stresses
        3  install_<beam>     one per drawn beam: the beam and its interfaces, plus the
                              surface loads, which the reference brings in here too
        4  dig_<n>            one per excavation level: that lift's soil bodies out,
                              and that lift's water load in as the previous one leaves
           install_<anchor>   after the lift that digs past the anchor's head

    This is a starting point, not a constraint: every field of every stage is editable
    afterwards, and the only thing that has to hold is that the result validates and
    linearises. The solver numbers are the reference's own, which is the nearest thing
    to a worked example there is -- they are not derived from anything.
    """
    made: list[Stage] = []
    parent: str | None = None

    def add(id_: str, name: str, **kw) -> None:
        nonlocal parent
        made.append(Stage(id=id_, name=name, parent=parent, **kw))
        parent = id_

    structures = ([beam.id for beam in project.beams]
                  + [anchor.id for anchor in project.anchors])
    interfaces = [each.id for each in project.interfaces]
    surface_loads = [load.id for load in project.loads]

    # One water load per lift, paired in order: the reference's `WaterLoad_StageN`
    # arrives with excavation N and replaces N-1. Only hydrostatic loads are paired --
    # a uniform normal load is a surcharge on a face, not a water table, and has no
    # reason to follow the digging -- and only as far as the lifts go; anything left
    # over stays active throughout, which is what it does today.
    levels = project.pit_levels()
    water = [load.id for load in project.normal_loads
             if load.fluid_pressure_type == "Hydrostatic"][:len(levels)]

    not_yet_built = structures + interfaces + surface_loads + water
    add("initial", "Initial stage", stress_initialisation="K0",
        deactivate=not_yet_built)
    add("null_step", "Null step", max_iterations=150)

    # The beams, each with the interfaces drawn against it. The first one carries the
    # surface loads and the displacement reset: the reference resets at the wall so the
    # wall's deflection is measured from the ground it was built into, not from the
    # undisturbed state.
    first_build = True
    for beam in project.beams:
        add(f"install_{beam.id}", f"{beam.name} installation",
            activate=([beam.id]
                      + [i.id for i in project.interfaces if i.structure == beam.id]
                      + (surface_loads if first_build else [])),
            reset_displacements=first_build, max_iterations=150, tolerated_error=1e-3)
        first_build = False

    # Anchors go in after the lift that digs past their head. Before any of that, an
    # anchor head is still buried, and there is nothing to fix a strut to.
    pending = {anchor.id: anchor.head[1] for anchor in project.anchors}

    for n, level in enumerate(levels, start=1):
        lift = [key for key, _, _, inside in project.soil_bodies()
                if inside and key.endswith(f"__lift{n}")]
        add(f"dig_{n}", f"{_ordinal(n)} excavation",
            deactivate=lift + ([water[n - 2]] if n >= 2 and n - 1 <= len(water) else []),
            activate=[water[n - 1]] if n <= len(water) else [],
            max_iterations=150, tolerated_error=1e-3)
        exposed = [id_ for id_, head_y in pending.items() if head_y >= level]
        for id_ in exposed:
            anchor = next(a for a in project.anchors if a.id == id_)
            add(f"install_{id_}", f"{anchor.name} installation", activate=[id_],
                max_iterations=150, tolerated_error=1e-3)
            del pending[id_]

    # Anything still buried when the digging stops goes in at the end rather than being
    # dropped: a part that exists in the model and in no stage is invisible in the deck.
    for id_ in list(pending):
        anchor = next(a for a in project.anchors if a.id == id_)
        add(f"install_{id_}", f"{anchor.name} installation", activate=[id_],
            max_iterations=150, tolerated_error=1e-3)

    return made


# -- editing ------------------------------------------------------------------
#
# What the Stages toolbar's buttons and the Model explorer's checkbox do to the list
# (`frontend/js/stages.js`: `added`, `inserted`, `removed`, `copied`, `setActive`), so
# the command line edits a sequence the way the GUI does. Each returns a new list and
# leaves the project alone; `core.session` stores it the way `PATCH /api/project/stages`
# does. `tests/test_stage_parity.py` holds the two sides to the same answers.

def _fresh_id(project: Project, stem: str) -> str:
    taken = {stage.id for stage in project.stages}
    number = 1
    while f"{stem}_{number}" in taken:
        number += 1
    return f"{stem}_{number}"


def _copies(project: Project) -> list[Stage]:
    return [stage.model_copy(deep=True) for stage in project.stages]


def _last(project: Project) -> Stage | None:
    try:
        sequence = linearise(project)
    except StageError:
        sequence = list(project.stages)
    return sequence[-1] if sequence else None


def added(project: Project) -> list[Stage]:
    """Add: a blank stage at the end of the sequence, starting from the last one."""
    listed = _copies(project)
    tail = _last(project)
    listed.append(Stage(id=_fresh_id(project, "stage"), name=f"Stage {len(listed) + 1}",
                        parent=tail.id if tail else None))
    return listed


def inserted(project: Project, id: str) -> list[Stage]:
    """Insert: a blank stage between `id` and the stage it starts from -- `id` then
    starts from the new one, or the tree would branch."""
    listed = _copies(project)
    at = next((n for n, stage in enumerate(listed) if stage.id == id), None)
    if at is None:
        return listed
    made = Stage(id=_fresh_id(project, "stage"), name="New stage", parent=listed[at].parent)
    listed[at].parent = made.id
    listed.insert(at, made)
    return listed


def removed(project: Project, id: str) -> list[Stage]:
    """Delete: the stage gone and the chain healed -- its children start from its
    parent, and a deleted root promotes its child."""
    target = next((stage for stage in project.stages if stage.id == id), None)
    if target is None:
        return _copies(project)
    listed = [stage for stage in _copies(project) if stage.id != id]
    for stage in listed:
        if stage.parent == id:
            stage.parent = target.parent
    return listed


def copied(project: Project, id: str) -> list[Stage]:
    """Copy: the same solver settings, spliced in after the original, without its parts
    -- a copy repeats a step with other parts, and the same switches twice would be
    no-ops."""
    listed = _copies(project)
    at = next((n for n, stage in enumerate(listed) if stage.id == id), None)
    if at is None:
        return listed
    original = listed[at]
    made = Stage(id=_fresh_id(project, "stage"), name=f"{original.name} (copy)",
                 parent=original.id, calculation=original.calculation,
                 stress_initialisation=original.stress_initialisation,
                 time_integration=original.time_integration,
                 reset_displacements=original.reset_displacements,
                 max_iterations=original.max_iterations,
                 tolerated_error=original.tolerated_error,
                 time_interval=original.time_interval)
    for stage in listed:
        if stage.parent == id:
            stage.parent = made.id
    listed.insert(at + 1, made)
    return listed


def set_active(project: Project, id: str, keys: list[str], wanted: bool) -> list[Stage]:
    """Make each of `keys` in the model (`wanted`) or out of it during stage `id`, with
    the smallest instruction that does it: none when the stages before already give that
    state, and never both lists for one part. Only stage `id` changes; the ones after
    inherit the new state until one of them says otherwise."""
    listed = _copies(project)
    if not any(stage.id == id for stage in listed):
        return listed
    before = _chain_to(project, id)[:-1]

    def inherited(key: str) -> bool:
        active = True       # everything starts in the model
        for stage in before:
            if key in stage.deactivate:
                active = False
            if key in stage.activate:
                active = True
        return active

    for stage in listed:
        if stage.id != id:
            continue
        for key in keys:
            stage.activate = [k for k in stage.activate if k != key]
            stage.deactivate = [k for k in stage.deactivate if k != key]
            if wanted != inherited(key):
                (stage.activate if wanted else stage.deactivate).append(key)
    return listed
