"""Resolving a phase tree into the sequence Kratos runs.

A `Phase` stores a *diff* against its parent -- what this phase switches on and off --
because that is what the reference deck's `stage_preprocess` is and because absolute
state would have to be rewritten in every later phase whenever a part is added to the
model (see `schemas.Phase`). This module is the only place that walks the parent chain,
and it turns that tree into the three things the exporter needs:

*   `linearise` -- the order the stages run in, or a refusal.
*   `active_parts` -- what is in the model during a given phase, which becomes each
    stage's `problem_domain_sub_model_part_list`.
*   `transitions` -- per phase, what changes, which becomes its `stage_preprocess`
    Activate/Deactivate operations.

and one more that is not about export at all:

*   `default_phases` -- the sequence a project gets the first time staged mode is
    opened, shaped like the reference's seven stages, so the phase editor opens on
    something that already runs rather than on an empty list.

Pure model logic: no gmsh, no Kratos, no meshing. It works on part *keys*, the model's
own namespace (`Project.stageable_keys`), not on deck part names -- one drawn
`Interface` here is eight parts in the deck, and making that mapping is export's job
(`app/kratos.py:_interface_by_body`).
"""

from __future__ import annotations

from app.schemas import Phase, Project


class PhaseError(Exception):
    """A phase tree that cannot become the one sequence Kratos runs.

    Not a `ValidationError`: the schema deliberately accepts trees it cannot run, so
    that a branch can be half-built in the editor, and this is where that becomes a
    problem -- at export, with a message about what to do.
    """


def linearise(project: Project) -> list[Phase]:
    """The phases in execution order, or raise.

    Depth first in creation order, which for a chain is just the chain. Kratos'
    `SequentialOrchestrator` takes one flat `execution_list`, so a tree that branches
    has no execution order and this refuses it by name. Plaxis allows the branch (it
    runs both and lets you compare them); we do not, and saying which phases branch is
    the difference between a message the user can act on and one they cannot.
    """
    if not project.phases:
        return []

    children: dict[str | None, list[Phase]] = {}
    for phase in project.phases:
        children.setdefault(phase.parent, []).append(phase)

    for parent, siblings in children.items():
        if parent is not None and len(siblings) > 1:
            names = ", ".join(repr(phase.id) for phase in siblings)
            raise PhaseError(
                f"phases {names} all start from {parent!r}, so there is no single "
                "order to run them in. Kratos runs one sequence of stages: give each "
                "of them a different phase to start from, or delete all but one."
            )

    order: list[Phase] = []
    stack = list(reversed(children.get(None, [])))
    while stack:
        phase = stack.pop()
        order.append(phase)
        stack.extend(reversed(children.get(phase.id, [])))

    # The schema guarantees one root and no cycles, so every phase is reachable. If that
    # ever stops being true, losing phases silently would be the worst way to find out.
    if len(order) != len(project.phases):
        missing = sorted({p.id for p in project.phases} - {p.id for p in order})
        raise PhaseError(f"phases unreachable from the first one: {', '.join(missing)}")
    return order


def _chain_to(project: Project, phase: Phase | str) -> list[Phase]:
    """The phases from the root down to `phase`, inclusive.

    Follows parents rather than the execution order, so it resolves a branch too. The
    editor needs that: a half-built branch still has to be able to say what is in it.
    """
    by_id = {each.id: each for each in project.phases}
    at = by_id[phase] if isinstance(phase, str) else phase
    chain: list[Phase] = []
    while at is not None:
        chain.append(at)
        at = by_id[at.parent] if at.parent is not None else None
    return list(reversed(chain))


def active_parts(project: Project, phase: Phase | str) -> set[str]:
    """Which parts are in the model during `phase`.

    Everything starts active: the mesh carries every part, and the first phase's job is
    to switch off what has not been built yet. That is what the reference's stage 1
    does -- it deactivates the wall, the anchor and all eight interfaces before solving
    for the initial stresses of ground that has nothing in it.
    """
    active = set(project.stageable_keys())
    for each in _chain_to(project, phase):
        # `Phase` forbids a part in both lists, so the order within a phase is moot.
        active -= set(each.deactivate)
        active |= set(each.activate)
    return active


def transitions(project: Project) -> list[tuple[Phase, set[str], set[str]]]:
    """Per phase in execution order: what genuinely switches on, and what switches off.

    Filtered against the state each phase lands on, so an instruction that changes
    nothing is dropped. Phases accumulate no-ops through ordinary editing -- delete a
    lift, add it back -- and Kratos tolerates deactivating an already inactive part, so
    nothing would break; the deck would just stop being readable, and a deck nobody can
    read is a deck nobody can check.
    """
    result: list[tuple[Phase, set[str], set[str]]] = []
    active = set(project.stageable_keys())
    for phase in linearise(project):
        switched_on = {key for key in phase.activate if key not in active}
        switched_off = {key for key in phase.deactivate if key in active}
        active = (active - switched_off) | switched_on
        result.append((phase, switched_on, switched_off))
    return result


# -- the default sequence ----------------------------------------------------

_ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
             "Eighth", "Ninth", "Tenth")


def _ordinal(n: int) -> str:
    return _ORDINALS[n - 1] if n <= len(_ORDINALS) else f"#{n}"


def default_phases(project: Project) -> list[Phase]:
    """What "Create default phases" gives: the initial stage, then the null step.

    Nothing more. Every further phase -- installing a wall, digging a lift -- is the
    user's to add, the way a Plaxis project starts from its initial phase. This used to
    be the whole reference-shaped sequence (`staged_excavation_phases`), and on a new
    model that produced a "First excavation" which dug nothing: the blank project's
    placeholder excavation has a level but no soil to remove.

    Nothing is switched off. There is no later phase to switch it back on, and a part
    that is off in every phase is missing from the deck altogether. `project` is taken
    for symmetry with `staged_excavation_phases`; the two phases do not depend on it.
    """
    return [
        Phase(id="initial", name="Initial stage", calculation="K0 procedure"),
        Phase(id="null_step", name="Null step", parent="initial",
              calculation="Null step", max_iterations=150),
    ]


def staged_excavation_phases(project: Project) -> list[Phase]:
    """A whole staged-excavation sequence, built from the model: the CROW case's.

    What `app.crow` gives its model, and what `default_phases` used to give every
    model. Shaped like the reference deck, because the reference deck is a normal excavation
    and the shape generalises: settle the ground, build the wall, then alternate digging
    with propping. For CROW it reproduces all seven stages exactly
    (`tests/test_phases.py`).

        1  initial            K0 procedure; everything not yet built is switched off
        2  null_step          the same model, solved again, to settle the K0 stresses
        3  install_<beam>     one per drawn beam: the beam and its interfaces, plus the
                              surface loads, which the reference brings in here too
        4  dig_<n>            one per excavation level: that lift's soil bodies out,
                              and that lift's water load in as the previous one leaves
           install_<anchor>   after the lift that digs past the anchor's head

    This is a starting point, not a constraint: every field of every phase is editable
    afterwards, and the only thing that has to hold is that the result validates and
    linearises. The solver numbers are the reference's own, which is the nearest thing
    to a worked example there is -- they are not derived from anything.
    """
    made: list[Phase] = []
    parent: str | None = None

    def add(id_: str, name: str, **kw) -> None:
        nonlocal parent
        made.append(Phase(id=id_, name=name, parent=parent, **kw))
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
    levels = list(project.excavation.levels)
    water = [load.id for load in project.normal_loads
             if load.fluid_pressure_type == "Hydrostatic"][:len(levels)]

    not_yet_built = structures + interfaces + surface_loads + water
    add("initial", "Initial stage", calculation="K0 procedure",
        deactivate=not_yet_built)
    add("null_step", "Null step", calculation="Null step", max_iterations=150)

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
    # dropped: a part that exists in the model and in no phase is invisible in the deck.
    for id_ in list(pending):
        anchor = next(a for a in project.anchors if a.id == id_)
        add(f"install_{id_}", f"{anchor.name} installation", activate=[id_],
            max_iterations=150, tolerated_error=1e-3)

    return made
