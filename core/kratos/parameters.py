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

`stage_settings.solver_settings` and `.problem_data` carry a *default* analysis (see
`SOLVER`), not one the project chose. Solver type, time stepping and the linear solver
are real engineering decisions with no home in `Project` today, so nothing here can say
what analysis the user meant. What it can say is that a deck with both blocks empty
cannot be run at all -- Kratos rejects it before it reads a single node -- and the
Calculate button needs something to hand the orchestrator. So they are filled from one
documented reference analysis, and the parts of them the project really does determine
(dimension, the sub-model part lists, whether anything has rotations) are derived from
the export rather than defaulted. When those fields do grow a home in `Project`, this
is where they replace `SOLVER`.

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
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from core.kratos.deck_files import MATERIALS_NAME
from core.model import units

ORCHESTRATOR = "Orchestrators.KratosMultiphysics.SequentialOrchestrator"
ANALYSIS_STAGE = "Stages.KratosMultiphysics.GeoMechanicsApplication.GeoMechanicsAnalysis"
STAGE_NAME = "1_Stage"
INITIAL_STAGE_NAME = "1_Initial_stage"
WALL_INSTALLATION_STAGE_NAME = "2_Wall_installation"

# The part GeoMechanics' solver assembles for itself out of the lists below; named here
# because two things address it rather than a body: the tie process and the GiD output.
COMPUTATIONAL_MODEL_PART = "porous_computational_model_part"
TIME_STEP = 1.0
"""Seconds, and the length of a stage: one step per stage. A static analysis has no
real clock -- time here only orders the stages -- so one step is one stage, and stage
*n* runs from *n* to *n+1*."""

ECHO_LEVEL = 1
"""Kratos' own progress lines. Kept on: they are the log the run writes beside the deck,
and the only account of a failure a user ever sees."""

NODAL_RESULTS = ("DISPLACEMENT", "TOTAL_DISPLACEMENT", "WATER_PRESSURE")
GAUSS_POINT_RESULTS = ("CAUCHY_STRESS_TENSOR",)

SOLVER = {
    "solver_type": "U_Pw",
    "model_part_name": "PorousDomain",
    "solution_type": "static",
    "scheme_type": "Newmark",
    "strategy_type": "newton_raphson",
    "convergence_criterion": "residual_criterion",
    "residual_relative_tolerance": 1e-4,
    "residual_absolute_tolerance": 1e-9,
    "min_iterations": 6,
    "max_iterations": 15,
    "number_cycles": 1,
    "reduction_factor": 0.5,
    "increase_factor": 2.0,
    "time_stepping": {"time_step": TIME_STEP},
    "buffer_size": 2,
    "echo_level": ECHO_LEVEL,
    "reset_totals": False,
    "clear_storage": False,
    "compute_reactions": True,
    "move_mesh_flag": False,
    "reform_dofs_at_each_step": False,
    "block_builder": True,
    "linear_solver_settings": {"solver_type": "skyline_lu_factorization", "scaling": True},
}
"""The default analysis -- see this module's docstring for what it is and is not.

Copied field for field from GeoMechanicsApplication's own
`tests/test_interface_prestress/ProjectParameters_stage1.json`: a single-step drained
static U_Pw analysis solved by Newton-Raphson on a residual criterion, with a direct
linear solver. Direct rather than the iterative `amgcl` the repo's `test/` decks use:
it is slower on a large mesh but cannot fail to converge on a small or ill-conditioned
one, which is the wrong first impression for a button that either works or does not.
Everything a project genuinely decides -- dimension, sub-model parts, rotations --
is filled in around this by `_solver_settings` rather than being listed here."""

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
"""See `_json_output`: a shade under one stage, so it writes once."""


@dataclass(frozen=True)
class Stage:
    """One entry of the deck's `stages`, as the project has already decided it.

    This module renders; it does not derive. Which parts are active in a stage, which
    processes a stage wants and what it solves with are all questions about the
    *project* -- they need the phase tree and the mapping from model keys to deck part
    names, and both live in `core.kratos.writer`. So a `Stage` arrives with the answers.

    `active` is the deck part names live during this stage, and it drives the process
    filter: a process is emitted only where every part it names is active (plan sec
    C3). `None` means "no opinion" -- the unphased deck says nothing about what a stage
    contains, so nothing is filtered out of it, which is exactly how it exported before
    staged construction existed.

    `max_iterations` and `tolerated_error` are `None` for "whatever `SOLVER` says",
    rather than being defaulted to its values here, so that the deck of a project with
    no phases cannot drift from `SOLVER` by way of a copy made in this file.
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
    extrapolate: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = ()
    json_output: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    reset_displacements: bool = False
    max_iterations: int | None = None
    tolerated_error: float | None = None
    materials_filename: str = MATERIALS_NAME


def stage_name(index: int, phase_name: str) -> str:
    """`1_Initial_stage`: the position in the sequence, then the phase's own name.

    The reference deck's own shape, and not only cosmetic -- every result file a stage
    writes is named after it, so the name has to survive being part of a filename on
    any platform. Anything that is not a letter, a digit or an underscore becomes one,
    runs collapse, and a phase named entirely in punctuation still gets a stage.
    """
    cleaned = re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", phase_name)).strip("_")
    return f"{index + 1}_{cleaned or 'Stage'}"


def project_parameters(
    constraints: list[tuple[str, list[bool]]],
    loads: list[tuple[str, str, list[bool], list[float]]],
    stages: list[Stage],
    normal_loads: list[tuple[str, str, float, float, float]] = (),
    *,
    water: tuple[float, float] = (0.0, 10.0),
    deck_name: str = "model",
    domain_size: int = 2,
    body_parts: list[str] = (),
    rotation_dofs: bool = False,
) -> str:
    """`constraints` is (sub-model part name, DISPLACEMENT is_fixed per axis).
    `loads` is (sub-model part name, Kratos variable, active per axis, value).
    `stages` is the deck's stages in execution order -- see `Stage`, and `core.kratos.writer`
    for where they come from. There is always at least one.
    `normal_loads` is (sub-model part name, fluid_pressure_type, pressure, water level,
    water specific weight) -- one per active `NormalLoad`; the last three are read only
    for the mode `fluid_pressure_type` names (see `_normal_load`).
    `water` is (phreatic level, specific weight) from `Project.water`, which every stage
    fixes the pore pressure about (see `_pore_pressure`). The same two numbers a
    hydrostatic entry of `normal_loads` carries, passed once because the field exists
    whether or not any load stands in it.

    The keyword arguments are what the analysis block needs and the process lists do
    not: `deck_name` is the .mdpa's name without its extension (Kratos appends it) and
    the stem every result file is named after, `domain_size` is 2 or 3, `body_parts`
    names every element-carrying sub-model part, and `rotation_dofs` says whether
    anything in the deck has rotations -- a beam or a shell does, soil does not."""
    rendered: dict[str, dict] = {}
    for index, stage in enumerate(stages):
        live = stage.active
        keep = (lambda name: True) if live is None else (lambda name: name in live)

        # Gravity first, and in every stage of every deck: it is what gives the
        # continuum elements their self weight, and it is not filtered because the part
        # it names is the one the solver assembles out of whatever is active.
        loads_processes = [_gravity()]
        # In the project's units, which are the deck's: written as they stand.
        loads_processes += [_load(name, variable, active, list(value))
                            for name, variable, active, value in loads if keep(name)]
        loads_processes += [
            _normal_load(name, fluid_pressure_type, pressure, water_y, specific_weight)
            for name, fluid_pressure_type, pressure, water_y, specific_weight
            in normal_loads if keep(name)
        ]
        constraint_processes = [_constraint(name, is_fixed)
                                for name, is_fixed in constraints if keep(name)]
        # The water table, in every stage of every deck and filtered by nothing: it is a
        # property of the ground rather than of anything a phase switches on and off.
        constraint_processes.append(_pore_pressure(*water))
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
                                      loads_processes, auxiliary, solver, deck_name)

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
    """
    out: list[dict] = []
    if stage.k0_parts:
        out.append(_k0_procedure(stage.k0_parts))
    if stage.final_stresses:
        out.append(_apply_final_stresses(stage.final_stresses))
    if stage.find_neighbours:
        out.append(_find_neighbours_of_interfaces(stage.find_neighbours))
    for parts, variables in stage.extrapolate:
        out.append(_extrapolate_to_nodes(parts, variables))
    return out


def _stage(stage: Stage, index: int, constraint_processes: list[dict],
           loads_processes: list[dict], auxiliary: list[dict],
           solver: dict, deck_name: str) -> dict:
    """One entry of `stages`. Each stage occupies its own unit interval of time --
    stage *n* runs from `start_time` to `start_time + 1` -- because the orchestrator
    runs them one after another over a single model: a second stage starting where the
    first did would re-solve the same instant and overwrite it."""
    processes = {
        "constraints_process_list": constraint_processes,
        "loads_process_list": loads_processes,
    }
    if auxiliary:
        processes["auxiliary_process_list"] = auxiliary
    if stage.json_output:
        processes["json_output"] = [
            _json_output(part, f"{stage.name}__{suffix}.json", variables)
            for part, suffix, variables in stage.json_output
        ]
    rendered = {
        "stage_settings": {
            "analysis_stage": ANALYSIS_STAGE,
            "problem_data": {
                "problem_name": f"{deck_name}_{stage.name}",
                "start_time": stage.start_time * TIME_STEP,
                "end_time": (stage.start_time + 1.0) * TIME_STEP,
                "echo_level": ECHO_LEVEL,
                "parallel_type": "OpenMP",
                "number_of_threads": 1,
            },
            "solver_settings": dict(solver),
            "processes": processes,
            "output_processes": {
                "gid_output": [_gid_output(f"{deck_name}_{stage.name}")]},
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

    Runs in the K0 phase only, over the soil bodies active in it -- it reads `K0_NC`
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


def _json_output(part: str, filename: str, variables: tuple[str, ...]) -> dict:
    """Write one part's nodal results to JSON beside the deck, once per stage.

    `time_frequency` is the reference's own `0.9999999999` rather than the stage length
    itself: a stage is one unit of time long, and a frequency of exactly 1.0 lands on
    the boundary of the floating-point comparison the process makes, so it can write
    nothing at all. A shade under one writes exactly once, at the end.
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
            "time_frequency": JSON_OUTPUT_FREQUENCY,
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
    (plan sec C5). They come off the phase record; a stage that says nothing about them
    solves the way `SOLVER` does.
    """
    settings = {
        **SOLVER,
        "domain_size": domain_size,
        "rotation_dofs": rotation_dofs,
        "model_import_settings": ({"input_type": "use_input_model_part"} if imported else
                                  {"input_type": "mdpa", "input_filename": deck_name}),
        "material_import_settings": {"materials_filename": MATERIALS_NAME},
        "problem_domain_sub_model_part_list": list(body_parts),
        "processes_sub_model_part_list": list(process_parts),
        "body_domain_sub_model_part_list": list(body_parts),
    }
    if stage is None:
        return settings
    settings["material_import_settings"] = {
        "materials_filename": stage.materials_filename}
    settings["reset_totals"] = stage.reset_displacements
    if stage.max_iterations is not None:
        settings["max_iterations"] = stage.max_iterations
    if stage.tolerated_error is not None:
        settings["residual_relative_tolerance"] = stage.tolerated_error
    return settings


def _gid_output(output_name: str) -> dict:
    """GiD ASCII results beside the deck, one file per stage.

    The same writer, flags and result list as the reference decks in `test/`, which is
    also what Kratos' own GeoMechanicsApplication test helpers read back when they
    compare two runs.
    """
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
                    "nodal_results": list(NODAL_RESULTS),
                    "gauss_point_results": list(GAUSS_POINT_RESULTS),
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


def _pore_pressure(water_y: float, specific_weight: float) -> dict:
    """Fix `WATER_PRESSURE` hydrostatically about the phreatic level, over the whole
    porous domain.

    Copied field for field from `staged_construction_for_generated_mesh.json`, where it
    appears unchanged in all seven stages, and from ten of the eleven stage files under
    `test/`. Without it the `U_Pw` solver's pressure degrees of freedom are unconstrained
    everywhere.

    Three things worth pointing at:

    *   **`PorousDomain`, not the computational model part.** Gravity acts on what the
        solver assembles, because only elements have weight; the water table is a
        property of the ground itself and is stated over the whole model.
    *   **`table` is a bare `0`, not `[0, 0, 0]`.** This is the *scalar* constraint
        process, and it rejects a list -- the sort of thing only a reference deck
        tells you.
    *   **Both numbers come from `Project.water`**, which is also where a hydrostatic
        `NormalLoad` gets them (`_normal_load`). One source, so a deck cannot carry a
        water load referenced to one level inside ground pressurised about another.

    Kept in step with the GUI note in plan sec 7.2: the eventual water-line tool edits
    `Project.water`, and this process follows it without further work.
    """
    return {
        "python_module": "apply_scalar_constraint_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyScalarConstraintTableProcess",
        "Parameters": {
            "model_part_name": "PorousDomain",
            "variable_name": "WATER_PRESSURE",
            "is_fixed": True,
            "table": 0,
            "fluid_pressure_type": "Hydrostatic",
            "gravity_direction": 1,
            "reference_coordinate": water_y,
            "specific_weight": specific_weight,
        },
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
                 water_y: float, specific_weight: float) -> dict:
    """Apply a pressure normal to a `NormalLoad`'s line (core/model/schemas.py).

    `"Hydrostatic"` is copied field for field from a real working example (see the
    module docstring): the pressure grows with depth below `water_y`, along axis 1 (Y,
    this project's up), at `specific_weight` per metre -- `Project.water`, not a value
    carried on the load record itself.

    `"Uniform"` applies `pressure` everywhere along the line instead, tangential
    component left off (`active` has one entry per component, and only the first is
    set): unlike the hydrostatic case there is no reference deck for this branch to
    match field for field, so check it against the first real run.
    """
    parameters = {
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
    return {
        "python_module": "apply_normal_load_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyNormalLoadTableProcess",
        "Parameters": parameters,
    }


def _gravity() -> dict:
    """Self weight, as a body load on the computational model part.

    Copied field for field from `staged_construction_for_generated_mesh.json`, where it
    appears in all seven stages, and from every staged deck under `test/`. Three things
    about it are deliberate and none is derived from the project:

    *   **The computational model part, not the bodies one by one.** That part is what
        the solver assembles out of the bodies a stage has active, so a body switched
        off in a phase drops out of it without gravity having to be restated -- which is
        why the reference never varies this process between stages.
    *   **Axis 1, always.** Y is up in both dimensions this exporter writes, and it is
        the same axis the constraint and normal-load processes already name as
        `gravity_direction` and the materials file as `K0_MAIN_DIRECTION`.
    *   **Every stage, filtered by nothing.** There is no project in which the ground
        has no weight, so there is no condition to put this behind.
    """
    return _load(COMPUTATIONAL_MODEL_PART, "VOLUME_ACCELERATION",
                 [False, True, False], [0.0, -GRAVITY, 0.0])


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
