"""Write the parts of the Kratos GeoMechanics ProjectParameters.json this exporter can
derive without inventing solver behaviour.

Kratos GeoMechanics decks are run by an orchestrator over a dict of named stages, even
when there is only one: see staged_construction.json (a real multi-stage benchmark
deck) for the shape this follows. A project with no sheet pile exports one stage --
nothing in it has an installation moment, so there is nothing to sequence. A sheet pile
does not exist before it is installed, so a project with one exports two: `1_Initial_stage`
(the pile and the interface(s) tying it to the soil deactivated, everything else as
before) then `2_Wall_installation` (the same parts activated). Both stages carry the
same constraints and loads -- nothing in `Project` says a boundary condition starts
partway through construction, and the reference deck itself repeats a load's process
block unchanged across the stages it stays active in rather than inventing a start
time for it.

`stage_settings.solver_settings` and `.problem_data` start from a reference analysis
(see `SOLVER`), because a deck with both blocks empty cannot be run at all -- Kratos
rejects it before it reads a single node. What a stage chooses replaces it: the
settings on the stage panel (`schemas.Stage`), and the expert settings behind them --
the strategy, the linear solver, the time step control, the time scheme, the assembly
-- which `core.model.solver` resolves to the stage's own choices and its defaults, and
writes only where they apply. A stage that changes none of them is written as the
reference deck is. The parts of the analysis the project really does determine
(dimension, the sub-model part lists, whether anything has rotations) are derived from
the export rather than defaulted.

A flow stage (calculation type "flow") is solved by a second reference
analysis, `FLOW_SOLVER`, read off Kratos' own `tests/Muskat` decks, by default with the
strategy its model calls for (`core.model.stages.model_strategy`). It writes its own
results (`FLOW_NODAL_RESULTS`):
its elements carry the water pressure alone, so there is no displacement or stress to
write. A stage with a seepage face adds one `ApplySeepageBoundaryProcess` per face to its
`loads_process_list`, as Kratos' `tests/seepage_tests` decks do, and writes the nodal
water flow rate the seepage strategy computes.

`stage_settings.processes.constraints_process_list` and `.loads_process_list` are
filled in, because both are fully determined by the project already exported to the
.mdpa: the domain boundaries and their sub-model parts, and each load's own components
(see `core.kratos.writer._load_variable`).

Confidence note: constraints and loads both use GeoMechanicsApplication's
apply_vector_constraint_table_process / ApplyVectorConstraintTableProcess -- the same
process either way, distinguished only by the presence of `is_fixed` (a constraint) and
by which process list it sits in (a load has none). Confirmed against a real staged
GeoMechanics benchmark deck (a sheet-pile-wall excavation with a LINE_LOAD surcharge),
not merely inferred from Kratos source. The orchestrator name, the stage keys, the
`analysis_stage` and the Activate/DeactivateModelPartOperation shape are all read off
that same deck.

`master_slave` adds one `AssignMasterSlaveConstraintsToNeighboursUtility` process per
staged interface to `1_Initial_stage` only. Deactivating a sheet pile's interface (via
`staged_parts`) removes its own contact stiffness but does nothing to reconnect the two
soil copies `core.kratos.interfaces` split apart for it, so without this the initial stage --
meant to be undisturbed ground -- models two mechanically disconnected halves. Not
inferred from a reference GeoMechanics deck (none at hand carries a sheet pile that
is *not yet* installed); read instead off Deltares/FEA-Tools'
`MiscellaneousTools/InterfaceInserter/master_slave_inserter.py`, a working tool built
for the same Kratos process, and off the process's own Kratos source
(`assign_master_slave_constraints_to_neighbours_process.py`) for what its parameters do.
See `_master_slave_constraint` for the one deliberate difference from that reference.

`normal_loads` adds one `ApplyNormalLoadTableProcess` per `NormalLoad` (core/model/schemas.py)
to `loads_process_list`, in every stage the same way an ordinary load is -- nothing
about a normal load ties it to wall installation. The `"Hydrostatic"` shape (a staged
excavation's `WaterLoad_StageN` arrangement) is copied verbatim from a real working
example, Deltares/FEA-Tools' `MiscellaneousTools/InterfaceInserter/
test_project_parameters.json`, whose `River_load` process this reproduces field for
field. The `"Uniform"` shape is not backed by a working example the way that one is; it
follows the same process's own Kratos source
(`GeoMechanicsApplication/custom_processes/apply_normal_load_table_process.cpp`) for
which fields that branch reads, but check it against the first real run.

One process here is not Kratos' own, and it is temporary: `_exclude_prestress`. It works
around Kratos counting an anchor's prestress twice when the anchor's stress is carried
into the next stage. It is written only for prestressed anchors, and it is removed once
Kratos is fixed (`core/kratos/prestress_workaround.py`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from core.kratos.deck_files import MATERIALS_NAME, PRESTRESS_WORKAROUND_MODULE
from core.model import solver, units

ORCHESTRATOR = "Orchestrators.KratosMultiphysics.SequentialOrchestrator"
ANALYSIS_STAGE = "Stages.KratosMultiphysics.GeoMechanicsApplication.GeoMechanicsAnalysis"
STAGE_NAME = "1_Stage"
INITIAL_STAGE_NAME = "1_Initial_stage"
WALL_INSTALLATION_STAGE_NAME = "2_Wall_installation"

# The part GeoMechanics' solver assembles for itself out of the lists below; named here
# because two things address it rather than a body: the tie process and the GiD output.
COMPUTATIONAL_MODEL_PART = "porous_computational_model_part"
DURATION = solver.STAGE_DEFAULTS["duration"]
TIME_STEP = solver.STAGE_DEFAULTS["time_step"]
"""Seconds: the length of a stage and its step when the project says neither -- an
unstaged deck, or a stage left at `schemas.Stage`'s defaults, which are these. A static
analysis has no real clock, so a stage lasts one second, solved in one step, and
stage *n* runs from *n* to *n+1*."""

ECHO_LEVEL = 1
"""Kratos' own progress lines. Kept on: they are the log the run writes beside the deck,
and the only account of a failure a user ever sees."""

NODAL_RESULTS = ("DISPLACEMENT", "TOTAL_DISPLACEMENT", "WATER_PRESSURE")
GAUSS_POINT_RESULTS = ("CAUCHY_STRESS_TENSOR", "HYDRAULIC_HEAD")
"""`HYDRAULIC_HEAD` is the soil element's own: at each integration point, the head of
its nodes -- the height against gravity minus the water pressure over the water weight
(`DENSITY_WATER` times g) -- interpolated. With no gravity there is no water weight and
Kratos writes 0, so a deck with gravity off does not ask for it (`_gid_output`)."""

FLOW_NODAL_RESULTS = ("WATER_PRESSURE", "EFFECTIVE_SATURATION", "FLUID_FLUX_VECTOR")
FLOW_GAUSS_POINT_RESULTS = ("HYDRAULIC_HEAD",)
SEEPAGE_NODAL_RESULTS = ("NODAL_WATER_FLOW_RATE",)
"""What a groundwater flow stage writes: the reference decks' nodal list, the saturation
and the flux made nodal by the extrapolation process the stage carries
(`core.kratos.writer.FLOW_EXTRAPOLATED`), and the head as a mechanical stage writes
it, which the water pressure elements compute too (`Pw_element.cpp`). A stage with a
seepage face also writes `SEEPAGE_NODAL_RESULTS`: the water each node takes in or lets
out, which the seepage strategy works out to decide where the face is open (as Kratos'
`tests/seepage_tests` decks write it)."""

SOLVER = {
    "solver_type": "U_Pw",
    "model_part_name": "PorousDomain",
    "solution_type": "static",
    "convergence_criterion": "residual_criterion",
    "residual_relative_tolerance": 1e-4,
    "residual_absolute_tolerance": 1e-9,
    "max_iterations": 15,
    "time_stepping": {"time_step": TIME_STEP},
    "buffer_size": 2,
    "echo_level": ECHO_LEVEL,
    "reset_totals": False,
    "clear_storage": False,
}
"""The reference analysis -- see this module's docstring for what it is and is not.

Copied from GeoMechanicsApplication's own
`tests/test_interface_prestress/ProjectParameters_stage1.json`: a single-step drained
static U_Pw analysis on a residual criterion. A stage chooses its own criterion,
iterations and tolerances (`schemas.Stage`), and its expert settings -- the strategy,
the linear solver, the time step control, the assembly -- are `core.model.solver`'s,
whose defaults are the rest of that deck: Newton-Raphson, but with a scaled Sparse LU
where the deck has Skyline LU.
Everything a project genuinely decides -- dimension, sub-model parts, rotations -- is
filled in around this by `_solver_settings` rather than being listed here."""

FLOW_SOLVER = {
    "solver_type": "Pw",
    "model_part_name": "PorousDomain",
    "solution_type": "Steady_State_Groundwater_Flow",
    "convergence_criterion": "residual_criterion",
    "residual_relative_tolerance": 1e-4,
    "residual_absolute_tolerance": 1e-9,
    "max_iterations": 15,
    "time_stepping": {"time_step": TIME_STEP},
    "buffer_size": 2,
    "echo_level": ECHO_LEVEL,
    "clear_storage": False,
    "move_mesh_flag": False,
}
"""The groundwater flow analysis: a steady state of the water pressure alone, read off
Kratos' `tests/Muskat/saturated_hydrostatic/ProjectParameters.json` and
`van_genuchten_hydrostatic`, on their residual criterion, whose tolerances a stage's
replace as in a mechanical one. The
strategy is the one the stage's model calls for unless it says otherwise
(`core.model.stages.model_strategy`): linear for a saturated soil, Newton-Raphson for one
whose permeability depends on the water pressure, Newton-Raphson with seepage for a
seepage face, which Kratos refuses more than one cycle for. The expert settings and
their flow defaults -- the rest of those decks -- are `core.model.solver`'s. Nothing in
it moves, so its mesh does not either. What the project decides is filled in by
`_solver_settings`, as for `SOLVER`."""

CONVERGENCE_TOLERANCES: dict[str, str] = {
    "residual_criterion": "residual",
    "displacement_criterion": "displacement",
    "water_pressure_criterion": "water_pressure",
}
"""What each convergence criterion (`schemas.CONVERGENCE_CRITERIA`) measures: Kratos
reads its tolerances as `<quantity>_relative_tolerance` and `<quantity>_absolute_tolerance`
(`geomechanics_U_Pw_solver.py`, `geomechanics_Pw_solver.py`)."""

SOLVERS: dict[str, dict[str, Any]] = {"mechanical": SOLVER, "flow": FLOW_SOLVER}
"""The reference analysis of each calculation type (`schemas.Stage.calculation`): the
coupled `U_Pw` solver for a mechanical stage, the `Pw` solver for a flow stage. A new
calculation type is a new entry here and in `SOLUTION_TYPES`."""

QUASI_STATIC = "quasi_static"
"""The `solution_type` of a dynamic mechanical stage integrated by Backward Euler: in
time, without inertia, the only U-Pw solution Kratos builds that scheme for."""

SOLUTION_TYPES = {
    "mechanical": {"static": SOLVER["solution_type"], "dynamic": "Dynamic"},
    "flow": {"static": FLOW_SOLVER["solution_type"],
             "dynamic": "Transient_Groundwater_Flow"},
}
"""Kratos' `solution_type` for each calculation type and time integration
(`schemas.Stage.time_integration`).

A static mechanical stage is the reference's `static`, which Kratos solves with its
`GeoStaticScheme`; a dynamic one is `Dynamic`, the Newmark scheme with inertia
(`geomechanics_U_Pw_solver.py`). Spelt with the capital: the solver lower-cases the name
to choose the scheme, but adds the velocity and acceleration degrees of freedom only
when it reads exactly `Dynamic`. A static flow stage is the steady state of the Muskat
decks; a dynamic one a transient flow, which the `Pw` solver solves with the same
Newmark scheme (`geomechanics_Pw_solver.py`)."""

# Metres, and a *step*, not a tolerance. The master and slave nodes of a tie are copies
# of the same source node -- `core.kratos.writer` gives each duplicate its original's exact
# coordinates -- so this was 1e-6: enough to clear floating-point noise from the .mdpa's
# 10-decimal node table and nothing more, on the reasoning that a wider radius could only
# net a neighbour belonging to someone else.
#
# That was wrong, and only running the deck showed it.
# `assign_master_slave_constraints_to_neighbours_utility.cpp` does not use this as a
# tolerance: it *grows* the search radius in increments of it until it has found
# `minimum_number_of_neighbouring_nodes` neighbours. At 1e-6, reaching a node a few
# centimetres away takes on the order of 10,000 iterations. 0.01 is the value the
# reference deck carries, and it reaches a real neighbour in a few steps.
MASTER_SLAVE_SEARCH_RADIUS = 0.01

MASTER_SLAVE_NEIGHBOURS = 2
"""How many master nodes the tie interpolates a slave from.

One is what the pairing needs: `core.kratos.writer._split_ties` knows exactly which copy belongs
to which original, so every slave has one true master at zero distance and a second can
only be an unrelated node. This asked for 1 on that reasoning, and the reasoning was
wrong -- not about the geometry, which still holds, but about what Kratos does with it.

With a cloud of one node, `rbf_shape_functions_utility.cpp` derives its shape parameter
from the distance to the *nearest other* point in the cloud. With one point the inner
loop never runs, that distance stays `DBL_MAX`, the shape parameter comes out as
`1/(0.815*DBL_MAX)`, and the guard rejects it: "Reference distance close to zero". The
utility needs two points to interpolate between whether or not the second one adds
anything, so it gets two."""

GRAVITY = units.GRAVITY_SI
"""m/s2 -- and the same number in every unit system the project can be in, since all of
them measure length in metres and time in seconds (`core/model/units.py`). The loads, pressures
and specific weights below are the project's own numbers, written as they stand."""

JSON_OUTPUT_FREQUENCY = 0.9999999999
"""See `_json_output`: a shade under one stage's duration, so it writes once."""


@dataclass(frozen=True)
class Stage:
    """One entry of the deck's `stages`, as the project has already decided it.

    This module renders; it does not derive. Which parts are active in a stage, which
    processes a stage wants and what it solves with are all questions about the
    *project* -- they need the stage tree and the mapping from model keys to deck part
    names, and both live in `core.kratos.writer`. So a `Stage` arrives with the answers.

    `active` is the deck part names live during this stage, and it drives the process
    filter: a process is emitted only where every part it names is active (plan sec
    C3). `None` means "no opinion" -- the unstaged deck says nothing about what a stage
    contains, so nothing is filtered out of it, which is exactly how it exported before
    staged construction existed.

    `conditions` is the boundary conditions on in this stage -- water pressures and
    supports -- by id: a condition a stage switched off is not written in it. `None`
    writes every one, as an unstaged deck does.

    `convergence_criterion`, `max_iterations`, `tolerated_error` and
    `absolute_tolerance` are `None` for "whatever `SOLVER` says",
    rather than being defaulted to its values here, so that the deck of a project with
    no stages cannot drift from `SOLVER` by way of a copy made in this file.

    `calculation` is the stage's calculation type (`schemas.Stage.calculation`).
    `model_strategy` is the strategy its model calls for (`core.model.stages.
    model_strategy`): a flow stage's default, and the only one a flow stage with a
    seepage face can have; `None` for a mechanical stage.
    `solver_settings` is the expert settings the stage changed (`schemas.Stage`), as
    (name, value) pairs. `time_integration` picks the stage's `SOLUTION_TYPES` entry.
    `seepage` is the parts of the seepage faces it has, each with its own
    `ApplySeepageBoundaryProcess`.

    `start_time`, `duration` and `time_step` are in the project's unit of time, which
    is the deck's: the stage runs from `start_time` to `start_time + duration` in steps
    of `time_step`.

    `prestressed` is the anchors in `final_stresses` that have a prestress. The temporary
    prestress workaround runs for them (`_exclude_prestress`).
    """
    name: str
    activate: tuple[str, ...] = ()
    deactivate: tuple[str, ...] = ()
    active: frozenset[str] | None = None
    bodies: tuple[str, ...] | None = None
    start_time: float = 0.0
    modeler: bool = False
    ties: tuple[tuple[str, str], ...] = ()
    k0_parts: tuple[str, ...] = ()
    find_neighbours: tuple[str, ...] = ()
    final_stresses: tuple[str, ...] = ()
    prestressed: tuple[str, ...] = ()
    extrapolate: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = ()
    json_output: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    reset_displacements: bool = False
    convergence_criterion: str | None = None
    max_iterations: int | None = None
    tolerated_error: float | None = None
    absolute_tolerance: float | None = None
    materials_filename: str = MATERIALS_NAME
    conditions: frozenset[str] | None = None
    calculation: str = "mechanical"
    model_strategy: str | None = None
    solver_settings: tuple[tuple[str, Any], ...] = ()
    seepage: tuple[str, ...] = ()
    time_integration: str = "static"
    duration: float = DURATION
    time_step: float = TIME_STEP


PhreaticLine = tuple[tuple[float, float], tuple[float, float]]
"""Two (x, y) points of a straight phreatic line, at different x (`_normal_load`)."""


@dataclass(frozen=True)
class WaterPressure:
    """One `WaterPressureCondition` (core/model/schemas.py) on one deck part, resolved.

    `part` is the sub-model part it acts on, or `None` for the whole porous domain. A
    condition on a face the excavation splits arrives as one entry per segment, so each
    one goes with its lift (`Stage.active`), and so does one on a staged part, one entry
    per body. `reference_coordinate` is the record's own level, and `condition` the
    record's id, which a stage switches (`Stage.conditions`)."""
    part: str | None
    fluid_pressure_type: str
    is_fixed: bool
    value: float
    reference_coordinate: float
    x_coordinates: tuple[float, ...]
    y_coordinates: tuple[float, ...]
    z_coordinates: tuple[float, ...]
    pressure_tension_cut_off: float
    specific_weight: float
    condition: str = ""


def stage_name(index: int, label: str) -> str:
    """`1_Initial_stage`: the position in the sequence, then the stage's own name.

    The reference deck's own shape, and not only cosmetic -- every result file a stage
    writes is named after it, so the name has to survive being part of a filename on
    any platform. Anything that is not a letter, a digit or an underscore becomes one,
    runs collapse, and a stage named entirely in punctuation still gets a stage.
    """
    cleaned = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", label)).strip("_")
    return f"{index + 1}_{cleaned or 'Stage'}"


def project_parameters(
    constraints: Sequence[tuple[str, list[bool]] | tuple[str, list[bool], str]],
    loads: list[tuple[str, str, list[bool], list[float]]],
    stages: list[Stage],
    normal_loads: Sequence[tuple[str, str, float, float, float]
                           | tuple[str, str, float, float, float, PhreaticLine]] = (),
    *,
    water_pressures: Sequence[WaterPressure] = (),
    deck_name: str = "model",
    domain_size: int = 2,
    body_parts: Sequence[str] = (),
    rotation_dofs: bool = False,
    gravity: bool = True,
    gravity_acceleration: float = GRAVITY,
) -> str:
    """`constraints` is (sub-model part name, DISPLACEMENT is_fixed per axis), with
    optionally the id of the support it comes from, which a stage switches
    (`Stage.conditions`); an empty or missing id is in every stage its part is.
    `loads` is (sub-model part name, Kratos variable, active per axis, value).
    `stages` is the deck's stages in execution order -- see `Stage`, and `core.kratos.writer`
    for where they come from. There is always at least one.
    `normal_loads` is (sub-model part name, fluid_pressure_type, pressure, water level,
    water specific weight) -- one per active `NormalLoad`; the last three are read only
    for the mode `fluid_pressure_type` names (see `_normal_load`). A `"Phreatic_Line"`
    entry carries its line's two points as a sixth item: the water on the ground that
    the writer adds itself (`core.kratos.writer._water_surface_loads`). Written in the
    order given, which matters there: a later process on a node sets its value again.
    `water_pressures` is the user's water pressure conditions, in the order they are
    written: start values first, so that where a fixed value acts on the same node it is
    the one that stays (see `_water_pressure`). Nothing else fixes a water pressure.

    The keyword arguments are what the analysis block needs and the process lists do
    not: `deck_name` is the .mdpa's name without its extension (Kratos appends it) and
    the stem every result file is named after, `domain_size` is 2 or 3, `body_parts`
    names every element-carrying sub-model part, and `rotation_dofs` says whether
    anything in the deck has rotations -- a beam or a shell does, soil does not.
    `gravity` is `core.model.stages.gravity`: off, no stage has the self weight
    process. `gravity_acceleration` is `Project.gravity_acceleration`, the self weight's
    g."""
    rendered: dict[str, dict] = {}
    for index, stage in enumerate(stages):
        live = stage.active
        keep = (lambda name: True) if live is None else (lambda name: name in live)

        # Gravity first, and in every stage of a deck that has it: it is what gives the
        # continuum elements their self weight, and it is not filtered because the part
        # it names is the one the solver assembles out of whatever is active.
        loads_processes = [_gravity(gravity_acceleration)] if gravity else []
        # In the project's units, which are the deck's: written as they stand.
        loads_processes += [_load(name, variable, active, list(value))
                            for name, variable, active, value in loads if keep(name)]
        loads_processes += [
            _normal_load(name, fluid_pressure_type, pressure, water_y, specific_weight,
                         line[0] if line else None)
            for name, fluid_pressure_type, pressure, water_y, specific_weight, *line
            in normal_loads if keep(name)
        ]
        loads_processes += [_seepage(name) for name in stage.seepage]
        constraint_processes = [_constraint(name, is_fixed)
                                for name, is_fixed, *of in constraints
                                if keep(name) and _switched_on(stage, of)]
        # On the whole soil a condition is filtered by nothing, as the soil is the porous
        # domain itself; on a face or a part it goes with the stretch or body it names.
        # And it is in the stages whose stage has it switched on.
        constraint_processes += [_water_pressure(pressure) for pressure in water_pressures
                                 if (pressure.part is None or keep(pressure.part))
                                 and (stage.conditions is None
                                      or pressure.condition in stage.conditions)]
        constraint_processes += [_master_slave_constraint(master, slave)
                                 for master, slave in stage.ties]
        auxiliary = _auxiliary(stage)

        bodies = list(body_parts if stage.bodies is None else stage.bodies)
        process_parts = _process_parts(constraint_processes + loads_processes,
                                       stage.ties)
        solver = _solver_settings(deck_name, domain_size, bodies, process_parts,
                                  rotation_dofs, imported=stage.modeler or index > 0,
                                  stage=stage)
        rendered[stage.name] = _stage(stage, index, constraint_processes,
                                      loads_processes, auxiliary, solver, deck_name,
                                      gravity=gravity,
                                      flow=stage.calculation == "flow")

    return json.dumps({
        "orchestrator": {
            "name": ORCHESTRATOR,
            "settings": {
                "echo_level": 0,
                "execution_list": [stage.name for stage in stages],
                "load_from_checkpoint": None,
                "stage_checkpoints": False,
            },
        },
        "stages": rendered,
    }, indent=4)


def _switched_on(stage: Stage, of: list[str]) -> bool:
    """Whether the support a constraint comes from (`of`, its id or nothing) is on in
    `stage`. A constraint no support owns -- an anchor's pinned end -- always is."""
    condition = of[0] if of else ""
    return not condition or stage.conditions is None or condition in stage.conditions


def _preprocess(stage: Stage, deck_name: str) -> dict | None:
    """`stage_preprocess`: the modeler, then this stage's own switching.

    The first stage reads the .mdpa itself, before its own operations run, and every
    later stage inherits the model rather than re-reading it. Both halves of that are
    load-bearing, and neither is decoration:

    *   a stage's solver imports the mesh *after* `stage_preprocess`, so a deactivation
        asked for here would name a sub-model part that does not exist yet -- Kratos
        says so and stops. The modeler is what puts the mesh in the model early enough
        for the operation beside it to find it.
    *   re-importing in a later stage would replace the model, and with it everything
        the stages before it did to it: the wall would arrive activated on top of
        undisturbed ground rather than on the ground the initial stage settled.

    Both are read off Kratos' own staged excavation benchmark, and hold in
    `staged_construction_for_generated_mesh.json` too.

    A stage that switches nothing and imports nothing has no preprocess block at all
    rather than an empty one: an Activate operation naming no parts is still a process
    Kratos constructs and runs.
    """
    block: dict = {}
    if stage.modeler:
        block["modelers"] = [_import_mdpa(deck_name)]
    operations = []
    if stage.deactivate:
        operations.append(_deactivate([f"PorousDomain.{name}"
                                       for name in stage.deactivate]))
    if stage.activate:
        operations.append(_activate([f"PorousDomain.{name}"
                                     for name in stage.activate]))
    if operations:
        block["operations"] = operations
    return block or None


def _auxiliary(stage: Stage) -> list[dict]:
    """`auxiliary_process_list`: the stage's own bookkeeping, in the reference's order.

    Every one of these is switched on by `core.kratos.writer` for the stages it belongs in and
    absent otherwise -- see `Stage`. The order matches
    `staged_construction_for_generated_mesh.json`: K0 or the stress carry-over first,
    then the interface neighbour search, then the extrapolations that read what they
    set up.

    The temporary prestress workaround comes directly before the stress carry-over. It
    has to: it hides the prestress in its `ExecuteInitialize`, and the carry-over stores
    the stresses in its own `ExecuteInitialize`, which Kratos runs next.
    """
    out: list[dict] = []
    if stage.k0_parts:
        out.append(_k0_procedure(stage.k0_parts))
    if stage.final_stresses:
        if stage.prestressed:
            out.append(_exclude_prestress(stage.prestressed))
        out.append(_apply_final_stresses(stage.final_stresses))
    if stage.find_neighbours:
        out.append(_find_neighbours_of_interfaces(stage.find_neighbours))
    for parts, variables in stage.extrapolate:
        out.append(_extrapolate_to_nodes(parts, variables))
    return out


def _stage(stage: Stage, index: int, constraint_processes: list[dict],
           loads_processes: list[dict], auxiliary: list[dict],
           solver: dict, deck_name: str, gravity: bool = True,
           flow: bool = False) -> dict:
    """One entry of `stages`. Each stage occupies its own interval of time -- from
    `start_time` to `start_time + duration` -- because the orchestrator runs them one
    after another over a single model: a second stage starting where the first did
    would re-solve the same instant and overwrite it."""
    processes = {
        "constraints_process_list": constraint_processes,
        "loads_process_list": loads_processes,
    }
    if auxiliary:
        processes["auxiliary_process_list"] = auxiliary
    if stage.json_output:
        processes["json_output"] = [
            _json_output(part, f"{stage.name}__{suffix}.json", variables, stage.duration)
            for part, suffix, variables in stage.json_output
        ]
    rendered = {
        "stage_settings": {
            "analysis_stage": ANALYSIS_STAGE,
            "problem_data": {
                "problem_name": f"{deck_name}_{stage.name}",
                "start_time": stage.start_time,
                "end_time": stage.start_time + stage.duration,
                "echo_level": ECHO_LEVEL,
                "parallel_type": "OpenMP",
                "number_of_threads": 1,
            },
            "solver_settings": dict(solver),
            "processes": processes,
            "output_processes": {
                "gid_output": [_gid_output(f"{deck_name}_{stage.name}", gravity,
                                           flow, seepage=bool(stage.seepage))]},
        },
    }
    preprocess = _preprocess(stage, deck_name)
    if preprocess is None:
        return rendered
    return {"stage_preprocess": preprocess, **rendered}


def _process_parts(processes: list[dict],
                   master_slave: tuple[tuple[str, str], ...]) -> list[str]:
    """The sub-model part names the processes act on, in a stable order.

    A master/slave process names the *computational* model part in `model_part_name`
    and its two real parts in keys of its own, so those are read off the pairs instead.
    """
    names: list[str] = []
    for process in processes:
        name = process.get("Parameters", {}).get("model_part_name", "").partition(".")[2]
        if name and name != COMPUTATIONAL_MODEL_PART and name not in names:
            names.append(name)
    for master, slave in master_slave:
        for name in (master, slave):
            if name not in names:
                names.append(name)
    return names


# -- the staged auxiliary processes ------------------------------------------
# All four are read field for field off `staged_construction_for_generated_mesh.json`,
# Kratos' own staged-excavation reference deck. Which stages each belongs in is `core.kratos.writer`'s decision and
# is documented there; what the parameters mean is here.

def _k0_procedure(parts: tuple[str, ...]) -> dict:
    """Set the initial stress state from K0 rather than by solving for it.

    Runs in the K0 stage only, over the soil bodies active in it -- it reads `K0_NC`
    and `K0_MAIN_DIRECTION` off each body's material, which is why the initial stage
    reads a materials file of its own (`core.kratos.materials`, plan sec C4).
    """
    return {
        "python_module": "apply_k0_procedure_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "apply_k0_procedure_process",
        "Parameters": {
            "model_part_name_list": [f"PorousDomain.{name}" for name in parts],
            "use_standard_procedure": True,
        },
    }


def _find_neighbours_of_interfaces(parts: tuple[str, ...]) -> dict:
    """Tell each interface element which continuum elements it sits between.

    Runs in the stage that activates the interfaces: before that they are not in the
    model, and afterwards the neighbours it found are still recorded.
    """
    return {
        "python_module": "find_neighbours_of_interfaces_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "FindNeighboursOfInterfacesProcess",
        "Parameters": {
            "model_part_name_list": [f"PorousDomain.{name}" for name in parts],
            "model_part_name_for_neighbouring_elements":
                f"PorousDomain.{COMPUTATIONAL_MODEL_PART}",
        },
    }


def _apply_final_stresses(parts: tuple[str, ...]) -> dict:
    """Carry each part's stress at the end of the previous stage into this one's
    initial state, so a structure is not re-stressed from zero every stage.

    Named for the parts that were already in the model *and* still are: a part being
    installed in this stage has no previous stress to carry, and the reference leaves
    it out for exactly that stage and includes it thereafter.
    """
    return {
        "python_module": "apply_final_stresses_of_previous_stage_to_initial_state",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyFinalStressesOfPreviousStageToInitialState",
        "Parameters": {
            "model_part_name_list": [f"PorousDomain.{name}" for name in parts],
        },
    }


PRESTRESS_WORKAROUND_PROCESS = "ExcludePrestressFromCarriedStress"


def _exclude_prestress(parts: tuple[str, ...]) -> dict:
    """TEMPORARY WORKAROUND for a Kratos limitation. Remove it when Kratos is fixed.

    `ApplyFinalStressesOfPreviousStageToInitialState` carries an anchor's stress *with*
    its prestress, and the truss element then adds the prestress again. Without this,
    every stage after the anchor's installation adds the full prestress to the anchor
    once more. This process hides the prestress while Kratos stores the stresses.
    `core/kratos/prestress_workaround.py` explains how, and what to delete once Kratos
    counts the prestress once.

    This is a user-defined process: there is no `kratos_module`, so Kratos imports
    `python_module` as it is, from the deck's own directory. The exporter ships the file
    with the deck (`deck_files.PRESTRESS_WORKAROUND_NAME`).
    """
    return {
        "python_module": PRESTRESS_WORKAROUND_MODULE,
        "process_name": PRESTRESS_WORKAROUND_PROCESS,
        "Parameters": {
            "model_part_name_list": [f"PorousDomain.{name}" for name in parts],
        },
    }


def _extrapolate_to_nodes(parts: tuple[str, ...], variables: tuple[str, ...]) -> dict:
    """Smear integration-point results onto nodes so they can be written out.

    The reference writes one of these per group that shares a variable list: the wall
    (`AXIAL_FORCE`, `BENDING_MOMENT`, `SHEAR_FORCE`) and the retained-side interfaces
    (`GEO_EFFECTIVE_TRACTION_VECTOR`). A single part is named with `model_part_name`
    and several with `model_part_name_list`, which is how the reference writes them and
    which the process accepts either way.
    """
    named = ({"model_part_name": f"PorousDomain.{parts[0]}"} if len(parts) == 1 else
             {"model_part_name_list": [f"PorousDomain.{name}" for name in parts]})
    return {
        "python_module": "geo_extrapolate_integration_point_values_to_nodes_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "GeoExtrapolateIntegrationPointValuesToNodesProcess",
        "Parameters": {**named, "list_of_variables": list(variables)},
    }


def _json_output(part: str, filename: str, variables: tuple[str, ...],
                 duration: float = DURATION) -> dict:
    """Write one part's nodal results to JSON beside the deck, once per stage.

    `time_frequency` is a shade under the stage's `duration` -- the reference's own
    `0.9999999999` for its one-second stages -- rather than the duration itself: the
    process adds up the steps it has seen and writes once the sum passes the frequency,
    and a frequency of exactly the duration lands on the boundary of that comparison,
    so it can write nothing at all. A shade under writes exactly once, at the end.
    """
    return {
        "python_module": "json_output_process",
        "kratos_module": "KratosMultiphysics",
        "process_name": "JsonOutputProcess",
        "Parameters": {
            "model_part_name": f"PorousDomain.{part}",
            "output_file_name": filename,
            "output_variables": list(variables),
            "gauss_points_output_variables": [],
            "time_frequency": JSON_OUTPUT_FREQUENCY * duration,
        },
    }


def _import_mdpa(deck_name: str) -> dict:
    """Read the .mdpa into the model before a stage's own operations run.

    `input_filename` carries no extension: Kratos appends `.mdpa` itself.
    """
    return {
        "name": "Modelers.KratosMultiphysics.ImportMDPAModeler",
        "Parameters": {"input_filename": deck_name, "model_part_name": "PorousDomain"},
    }


def _solver_settings(deck_name: str, domain_size: int, body_parts: list[str],
                     process_parts: list[str], rotation_dofs: bool,
                     imported: bool = False, stage: Stage | None = None) -> dict:
    """The analysis the deck is solved with: `SOLVER` plus what the project decides.

    Everything the project genuinely determines -- the dimension, which parts are
    bodies, which are acted on by a process, whether anything in the deck has rotations
    -- is filled in here. The rest is `SOLVER`, a default analysis rather than a choice
    the project made; see this module's docstring.

    `imported` says the mesh is already in the model, put there by the modeler on the
    first stage: every stage then works on that one model instead of re-reading the
    file and throwing away what the stage before it did.

    `stage` overrides the three numbers the reference deck actually varies between its
    stages -- iterations, tolerance and whether displacements start again from zero
    (plan sec C5) -- and the time step and the convergence criterion, whose
    tolerances are written for the quantity it measures (`CONVERGENCE_TOLERANCES`).
    They come off the stage record; a stage that says nothing about them solves the way
    `SOLVER` does. Its expert settings (`core.model.solver`) are the ones that apply to
    it, at its own values or their defaults.

    A flow stage starts from `FLOW_SOLVER` instead. It has no displacements to reset.
    Either solves statically or in time, as the stage says (`SOLUTION_TYPES`), and a
    stage solved by the linear strategy has no iterations to count, so no convergence
    criterion, iterations or tolerances either.
    """
    stage = stage if stage is not None else Stage(name=STAGE_NAME)
    calculation = stage.calculation
    rows = solver.resolve(calculation, stage.time_integration, dict(stage.solver_settings),
                          stage.model_strategy)
    chosen = solver.deck_settings(rows)
    base = SOLVERS[calculation]
    settings = {
        **base,
        **{key: value for key, value in chosen.items() if key != "time_stepping"},
        "time_stepping": {**base["time_stepping"], **chosen.get("time_stepping", {}),
                          "time_step": stage.time_step},
        "solution_type": SOLUTION_TYPES[calculation][stage.time_integration],
        "domain_size": domain_size,
        "rotation_dofs": rotation_dofs,
        "model_import_settings": ({"input_type": "use_input_model_part"} if imported else
                                  {"input_type": "mdpa", "input_filename": deck_name}),
        "material_import_settings": {"materials_filename": stage.materials_filename},
        "problem_domain_sub_model_part_list": list(body_parts),
        "processes_sub_model_part_list": list(process_parts),
        "body_domain_sub_model_part_list": list(body_parts),
    }
    if calculation == "mechanical":
        settings["reset_totals"] = stage.reset_displacements
        # Kratos builds Backward Euler for a U-Pw stage only as a quasi-static one,
        # without inertia (`geomechanics_U_Pw_solver.py`).
        if stage.time_integration == "dynamic" and chosen.get("scheme_type") == \
                "backward_euler":
            settings["solution_type"] = QUASI_STATIC
    # The smallest step is a fraction of the stage in the catalogue and a time in the
    # deck -- and never more than the stage's own step, which Kratos would refuse
    # outright: its own default is the same, min(step, 1e-4 of the stage).
    stepping = settings["time_stepping"]
    if "minimum_allowable_value" in stepping:
        stepping["minimum_allowable_value"] = min(
            stepping["minimum_allowable_value"] * stage.duration, stage.time_step)
    if not solver.iterates(rows):
        for key in [key for key in settings if key in ("convergence_criterion",
                                                       "max_iterations")
                    or key.endswith("_tolerance")]:
            del settings[key]
        return settings
    if stage.max_iterations is not None:
        settings["max_iterations"] = stage.max_iterations
    # The reference's tolerances move to the quantity the stage's criterion measures,
    # unless the stage has its own.
    measured = CONVERGENCE_TOLERANCES[settings["convergence_criterion"]]
    relative = settings.pop(f"{measured}_relative_tolerance")
    absolute = settings.pop(f"{measured}_absolute_tolerance")
    if stage.convergence_criterion is not None:
        settings["convergence_criterion"] = stage.convergence_criterion
    measured = CONVERGENCE_TOLERANCES[settings["convergence_criterion"]]
    settings[f"{measured}_relative_tolerance"] = (
        relative if stage.tolerated_error is None else stage.tolerated_error)
    settings[f"{measured}_absolute_tolerance"] = (
        absolute if stage.absolute_tolerance is None else stage.absolute_tolerance)
    return settings


def _gid_output(output_name: str, gravity: bool = True, flow: bool = False,
                seepage: bool = False) -> dict:
    """GiD ASCII results beside the deck, one file per stage.

    The same writer, flags and result list as the reference decks in `test/`, which is
    also what Kratos' own GeoMechanicsApplication test helpers read back when they
    compare two runs. Without gravity the hydraulic head is left out: it would be 0.
    A groundwater flow stage writes the flow results (`FLOW_NODAL_RESULTS`), and the
    nodal water flow rate when it has a seepage face (`SEEPAGE_NODAL_RESULTS`).
    """
    nodal = (FLOW_NODAL_RESULTS + (SEEPAGE_NODAL_RESULTS if seepage else ())) if flow         else NODAL_RESULTS
    gauss = [name for name in (FLOW_GAUSS_POINT_RESULTS if flow else GAUSS_POINT_RESULTS)
             if gravity or name != "HYDRAULIC_HEAD"]
    return {
        "python_module": "gid_output_process",
        "kratos_module": "KratosMultiphysics",
        "process_name": "GiDOutputProcess",
        "Parameters": {
            "model_part_name": f"PorousDomain.{COMPUTATIONAL_MODEL_PART}",
            "output_name": output_name,
            "postprocess_parameters": {
                "result_file_configuration": {
                    "gidpost_flags": {
                        "WriteDeformedMeshFlag": "WriteUndeformed",
                        "WriteConditionsFlag": "WriteElementsOnly",
                        "GiDPostMode": "GiD_PostAscii",
                        "MultiFileFlag": "SingleFile",
                    },
                    "file_label": "step",
                    "output_control_type": "step",
                    "body_output": True,
                    "node_output": False,
                    "skin_output": False,
                    "plane_output": [],
                    "nodal_results": list(nodal),
                    "gauss_point_results": gauss,
                },
                "point_data_configuration": [],
            },
        },
    }


def _activate(parts: list[str]) -> dict:
    return {
        "name": "Operations.KratosMultiphysics.GeoMechanicsApplication.ActivateModelPartOperation",
        "Parameters": {"model_part_name_list": list(parts)},
    }


def _deactivate(parts: list[str]) -> dict:
    return {
        "name": "Operations.KratosMultiphysics.GeoMechanicsApplication.DeactivateModelPartOperation",
        "Parameters": {"model_part_name_list": list(parts)},
    }


def _constraint(part_name: str, is_fixed: list[bool]) -> dict:
    """A pinned or roller boundary: fixed on exactly the axes it constrains."""
    return {
        "python_module": "apply_vector_constraint_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyVectorConstraintTableProcess",
        "Parameters": {
            "model_part_name": f"PorousDomain.{part_name}",
            "variable_name": "DISPLACEMENT",
            "active": list(is_fixed),
            "is_fixed": list(is_fixed),
            "value": [0.0, 0.0, 0.0],
            "table": [0, 0, 0],
        },
    }


def _water_pressure(pressure: WaterPressure) -> dict:
    """Prescribe `WATER_PRESSURE` on one part, or on the whole porous domain.

    The three shapes are each copied field for field from a working deck:

    *   `"Hydrostatic"` on the whole domain from `staged_construction_for_generated_mesh.json`,
        where it appears unchanged in all seven stages, and on a boundary part from
        Kratos' `tests/Muskat/saturated_hydrostatic`, which adds
        `pressure_tension_cut_off`. The key is written only when it is not Kratos'
        default 0, so the staged reference is matched exactly.
    *   `"Uniform"` from Kratos' `tests/seepage_tests/fixed_bottom_boundary`: `value` and
        no `fluid_pressure_type` at all, which is how the process is told to apply one
        value everywhere.
    *   `"Phreatic_Multi_Line"` from Kratos' `tests/Muskat/van_genuchten_hydrostatic`,
        with one `table` entry per point of the line.

    Two things worth pointing at:

    *   **`PorousDomain`, not the computational model part**, for the whole soil.
        Gravity acts on what the solver assembles, because only elements have weight;
        the water table is a property of the ground itself and is stated over the whole
        model.
    *   **`table` is a bare `0`, not `[0, 0, 0]`**, except for the multi-line. This is
        the *scalar* constraint process, and it rejects a list -- the sort of thing only
        a reference deck tells you.
    """
    parameters: dict[str, Any] = {
        "model_part_name": ("PorousDomain" if pressure.part is None
                            else f"PorousDomain.{pressure.part}"),
        "variable_name": "WATER_PRESSURE",
        "is_fixed": pressure.is_fixed,
    }
    if pressure.fluid_pressure_type == "Uniform":
        parameters.update({"value": pressure.value, "table": 0})
    elif pressure.fluid_pressure_type == "Hydrostatic":
        parameters.update({
            "table": 0,
            "fluid_pressure_type": "Hydrostatic",
            "gravity_direction": 1,
            "reference_coordinate": pressure.reference_coordinate,
            "specific_weight": pressure.specific_weight,
        })
    else:
        points = len(pressure.x_coordinates)
        parameters.update({
            "table": [0] * points,
            "fluid_pressure_type": pressure.fluid_pressure_type,
            "gravity_direction": 1,
            "out_of_plane_direction": 2,
            "x_coordinates": list(pressure.x_coordinates),
            "y_coordinates": list(pressure.y_coordinates),
            "z_coordinates": list(pressure.z_coordinates),
            "specific_weight": pressure.specific_weight,
        })
    if pressure.fluid_pressure_type != "Uniform" and pressure.pressure_tension_cut_off:
        parameters["pressure_tension_cut_off"] = pressure.pressure_tension_cut_off
    return {
        "python_module": "apply_scalar_constraint_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyScalarConstraintTableProcess",
        "Parameters": parameters,
    }


def _master_slave_constraint(master_part_name: str, slave_part_name: str) -> dict:
    """Tie a slave copy of a split node back to its master copy for a stage in which the
    structure that split them is not installed yet.

    `search_radius` and `minimum_number_of_neighbouring_nodes` are the FEA-Tools
    reference tool's own values, and both of them were once something else here on
    reasoning that reading the parameters could not have corrected -- see
    `MASTER_SLAVE_SEARCH_RADIUS` and `MASTER_SLAVE_NEIGHBOURS` for what each one turned
    out to mean and how the deck failed. The general lesson is written down in
    plan/outdated/staged-construction-plan.md sec 7: a parameter whose meaning was inferred is a
    guess until a run says otherwise, however good the inference looked."""
    return {
        "python_module": "assign_master_slave_constraints_to_neighbours_process",
        "kratos_module": "KratosMultiphysics",
        "process_name": "AssignMasterSlaveConstraintsToNeighboursUtility",
        "Parameters": {
            "model_part_name": "PorousDomain.porous_computational_model_part",
            "master_model_part_name": f"PorousDomain.{master_part_name}",
            "slave_model_part_name": f"PorousDomain.{slave_part_name}",
            "variable_names": ["DISPLACEMENT", "WATER_PRESSURE"],
            "search_radius": MASTER_SLAVE_SEARCH_RADIUS,
            "minimum_number_of_neighbouring_nodes": MASTER_SLAVE_NEIGHBOURS,
            "reform_constraints_at_each_step": True,
        },
    }


def _normal_load(part_name: str, fluid_pressure_type: str, pressure: float,
                 water_y: float, specific_weight: float,
                 line: PhreaticLine | None = None) -> dict:
    """Apply a pressure normal to a `NormalLoad`'s line (core/model/schemas.py).

    `"Hydrostatic"` is copied field for field from a real working example (see the
    module docstring): the pressure grows with depth below `water_y`, along axis 1 (Y,
    this project's up), at `specific_weight` per metre -- `Project.water`, not a value
    carried on the load record itself.

    `"Uniform"` applies `pressure` everywhere along the line instead, tangential
    component left off (`active` has one entry per component, and only the first is
    set): unlike the hydrostatic case there is no reference deck for this branch to
    match field for field, so check it against the first real run.

    `"Phreatic_Line"` is hydrostatic below the straight line through `line`'s two
    points, and level with each end beyond it. The keys are the ones the process copies
    for that branch (`apply_normal_load_table_process.cpp`), read by
    `ApplyConstantBoundaryPhreaticLinePressureProcess`, which needs the two points at
    different x. Kratos has no multi-line normal load, so the water the writer puts on
    the ground under a phreatic multi-line is one of these per stretch of the line.
    """
    parameters: dict[str, Any] = {
        "model_part_name": f"PorousDomain.{part_name}",
        "variable_name": "NORMAL_CONTACT_STRESS",
        "active": [True, False],
        "fluid_pressure_type": fluid_pressure_type,
        # Written whichever mode this is. The uniform branch reads it; the hydrostatic
        # one derives its pressure from the water level and leaves it alone, but a
        # magnitude the user typed belongs in the deck either way rather than being
        # dropped on the way out. Both branches share one parameter set, so the key is
        # one the process already declares -- it is not an invention that would trip
        # Kratos' validation against its own defaults.
        "value": [pressure, 0.0],
        "table": [0, 0],
    }
    if fluid_pressure_type == "Hydrostatic":
        parameters.update({
            "gravity_direction": 1,
            "reference_coordinate": water_y,
            "specific_weight": specific_weight,
        })
    elif fluid_pressure_type == "Phreatic_Line":
        if line is None:
            raise ValueError(f"the Phreatic_Line normal load on {part_name!r} needs its "
                             "line's two points")
        (x1, y1), (x2, y2) = line
        parameters.update({
            "gravity_direction": 1,
            "out_of_plane_direction": 2,
            "first_reference_coordinate": [x1, y1, 0.0],
            "second_reference_coordinate": [x2, y2, 0.0],
            "specific_weight": specific_weight,
        })
    return {
        "python_module": "apply_normal_load_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyNormalLoadTableProcess",
        "Parameters": parameters,
    }


def _seepage(part_name: str) -> dict:
    """A seepage face: Kratos' `ApplySeepageBoundaryProcess`, which names the part of
    `GeoSeepageCondition`s and nothing else. The strategy does the work
    (`core.model.stages.model_strategy`); copied from Kratos' `tests/seepage_tests`
    decks."""
    return {
        "python_module": "apply_seepage_boundary_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplySeepageBoundaryProcess",
        "Parameters": {"model_part_name": f"PorousDomain.{part_name}"},
    }


def _gravity(acceleration: float = GRAVITY) -> dict:
    """Self weight, as a body load on the computational model part.

    Copied field for field from `staged_construction_for_generated_mesh.json`, where it
    appears in all seven stages, and from every staged deck under `test/`. Three things
    about it are deliberate and none is derived from the project:

    *   **The computational model part, not the bodies one by one.** That part is what
        the solver assembles out of the bodies a stage has active, so a body switched
        off in a stage drops out of it without gravity having to be restated -- which is
        why the reference never varies this process between stages.
    *   **Axis 1, always.** Y is up in both dimensions this exporter writes, and it is
        the same axis the constraint and normal-load processes already name as
        `gravity_direction` and the materials file as `K0_MAIN_DIRECTION`.
    *   **Every stage, filtered by nothing.** The ground has its weight in every stage
        or in none: the initial stage's stress initialisation decides it for the whole
        sequence (`core.model.stages.gravity`).
    *   **Every body, the structures too.** Kratos builds the computational model part
        out of the nodes of every part in `problem_domain_sub_model_part_list`
        (`check_and_prepare_model_process_geo.py`), which lists the beams, shells and
        trusses as well as the soil, and their elements read the nodal
        `VOLUME_ACCELERATION` with their own `DENSITY` (`GetBodyForce`). So one process
        gives every body its self weight.

    `acceleration` is `Project.gravity_acceleration`, 9.81 m/s2 unless the user sets
    another.
    """
    return _load(COMPUTATIONAL_MODEL_PART, "VOLUME_ACCELERATION",
                 [False, True, False], [0.0, -acceleration, 0.0])


def _load(part_name: str, variable: str, active: list[bool], value: list[float]) -> dict:
    """A load carries no `is_fixed`: that key is what marks a constraint, not the
    python_module, which is the same apply_vector_constraint_table_process either way."""
    return {
        "python_module": "apply_vector_constraint_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyVectorConstraintTableProcess",
        "Parameters": {
            "model_part_name": f"PorousDomain.{part_name}",
            "variable_name": variable,
            "active": list(active),
            "value": list(value),
            "table": [0, 0, 0],
        },
    }
