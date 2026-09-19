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

`stage_settings.solver_settings` and `.problem_data` are left `{}`. Neither can be
filled honestly yet: solver type, time stepping and the linear solver are real
engineering decisions with no home in `Project` today, and guessing at them would
silently pick an analysis for the user rather than exporting the one they built. They
stay empty until those fields exist.

`stage_settings.processes.constraints_process_list` and `.loads_process_list` are
filled in, because both are fully determined by the project already exported to the
.mdpa: the domain boundaries and their sub-model parts, and each load's own components
(see `app.kratos._load_variable`).

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
soil copies `app.interfaces` split apart for it, so without this the initial stage --
meant to be undisturbed ground -- models two mechanically disconnected halves. Not
inferred from a reference GeoMechanics deck (none in examples/ carries a sheet pile that
is *not yet* installed); read instead off Deltares/FEA-Tools'
`MiscellaneousTools/InterfaceInserter/master_slave_inserter.py`, a working tool built
for the same Kratos process, and off the process's own Kratos source
(`assign_master_slave_constraints_to_neighbours_process.py`) for what its parameters do.
See `_master_slave_constraint` for the one deliberate difference from that reference.

`normal_loads` adds one `ApplyNormalLoadTableProcess` per `NormalLoad` (app/schemas.py)
to `loads_process_list`, in every stage the same way an ordinary load is -- nothing
about a normal load ties it to wall installation. The `"Hydrostatic"` shape (the CROW
reference case's `WaterLoad_StageN` arrangement) is copied verbatim from a real working
example, Deltares/FEA-Tools' `MiscellaneousTools/InterfaceInserter/
test_project_parameters.json`, whose `River_load` process this reproduces field for
field. The `"Uniform"` shape is not backed by a working example the way that one is; it
follows the same process's own Kratos source
(`GeoMechanicsApplication/custom_processes/apply_normal_load_table_process.cpp`) for
which fields that branch reads, but check it against the first real run.
"""

from __future__ import annotations

import json

ORCHESTRATOR = "Orchestrators.KratosMultiphysics.SequentialOrchestrator"
ANALYSIS_STAGE = "Stages.KratosMultiphysics.GeoMechanicsApplication.GeoMechanicsAnalysis"
STAGE_NAME = "1_Stage"
INITIAL_STAGE_NAME = "1_Initial_stage"
WALL_INSTALLATION_STAGE_NAME = "2_Wall_installation"

# Metres. The master and slave nodes of a tie are copies of the same source node --
# `app.kratos` gives each duplicate its original's exact coordinates -- so at export time
# they are exactly coincident, not merely nearby. This radius only has to clear floating
# point noise from the .mdpa's 10-decimal node table (`app.kratos._render`), not real mesh
# spacing, so a tiny fixed value is both sufficient and safer than deriving one from
# element size: it can never accidentally net a neighbour that belongs to someone else.
MASTER_SLAVE_SEARCH_RADIUS = 1e-6


def project_parameters(
    constraints: list[tuple[str, list[bool]]],
    loads: list[tuple[str, str, list[bool], list[float]]],
    staged_parts: list[str] = (),
    master_slave: list[tuple[str, str]] = (),
    normal_loads: list[tuple[str, str, float, float, float]] = (),
) -> str:
    """`constraints` is (sub-model part name, DISPLACEMENT is_fixed per axis).
    `loads` is (sub-model part name, Kratos variable, active per axis, value).
    `staged_parts` is the sub-model part names -- a sheet pile and the interface(s)
    tying it to the soil -- that do not exist until wall installation; empty for a
    project with no sheet pile.
    `master_slave` is (master part name, slave part name) pairs -- see the module
    docstring -- one per staged interface with soil split on both sides; empty whenever
    `staged_parts` is.
    `normal_loads` is (sub-model part name, fluid_pressure_type, pressure, water level,
    water specific weight) -- one per active `NormalLoad`; the last three are read only
    for the mode `fluid_pressure_type` names (see `_normal_load`)."""
    loads_processes = [_load(name, variable, active, value)
                       for name, variable, active, value in loads]
    loads_processes += [_normal_load(name, fluid_pressure_type, pressure, water_y,
                                     specific_weight)
                        for name, fluid_pressure_type, pressure, water_y, specific_weight
                        in normal_loads]
    if not staged_parts:
        return json.dumps({
            "orchestrator": {
                "name": ORCHESTRATOR,
                "settings": {
                    "echo_level": 0,
                    "execution_list": [STAGE_NAME],
                    "load_from_checkpoint": None,
                    "stage_checkpoints": False,
                },
            },
            "stages": {
                STAGE_NAME: {
                    "stage_settings": {
                        "analysis_stage": ANALYSIS_STAGE,
                        "problem_data": {},
                        "solver_settings": {},
                        "processes": {
                            "constraints_process_list": [_constraint(name, is_fixed)
                                                         for name, is_fixed in constraints],
                            "loads_process_list": loads_processes,
                        },
                    },
                },
            },
        }, indent=4)

    parts = [f"PorousDomain.{name}" for name in staged_parts]
    initial_constraints = ([_constraint(name, is_fixed) for name, is_fixed in constraints] +
                           [_master_slave_constraint(master, slave)
                            for master, slave in master_slave])
    installed_constraints = [_constraint(name, is_fixed) for name, is_fixed in constraints]
    return json.dumps({
        "orchestrator": {
            "name": ORCHESTRATOR,
            "settings": {
                "echo_level": 0,
                "execution_list": [INITIAL_STAGE_NAME, WALL_INSTALLATION_STAGE_NAME],
                "load_from_checkpoint": None,
                "stage_checkpoints": False,
            },
        },
        "stages": {
            INITIAL_STAGE_NAME: {
                "stage_preprocess": {"operations": [_deactivate(parts)]},
                "stage_settings": {
                    "analysis_stage": ANALYSIS_STAGE,
                    "problem_data": {},
                    "solver_settings": {},
                    "processes": {
                        "constraints_process_list": initial_constraints,
                        "loads_process_list": loads_processes,
                    },
                },
            },
            WALL_INSTALLATION_STAGE_NAME: {
                "stage_preprocess": {"operations": [_activate(parts)]},
                "stage_settings": {
                    "analysis_stage": ANALYSIS_STAGE,
                    "problem_data": {},
                    "solver_settings": {},
                    "processes": {
                        "constraints_process_list": installed_constraints,
                        "loads_process_list": loads_processes,
                    },
                },
            },
        },
    }, indent=4)


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


def _master_slave_constraint(master_part_name: str, slave_part_name: str) -> dict:
    """Tie a slave copy of a split node back to its master copy for a stage in which the
    structure that split them is not installed yet.

    `minimum_number_of_neighbouring_nodes` is 1, not the 2 the FEA-Tools reference tool
    defaults to (see the module docstring). That tool cannot tell which copy pairs with
    which and has to let Kratos discover it by nearest-neighbour search over a mesh whose
    two sides may not even match node-for-node. Here the pairing is exact --
    `app.kratos._split_ties` already knows precisely which copy belongs to which original
    -- so each slave has exactly one true master, at zero distance; asking for a second
    neighbour would only make the search radius expand until it found an unrelated node
    (Kratos' own utility grows the radius, in steps of `search_radius`, until the minimum
    is met)."""
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
            "minimum_number_of_neighbouring_nodes": 1,
            "reform_constraints_at_each_step": True,
        },
    }


def _normal_load(part_name: str, fluid_pressure_type: str, pressure: float,
                 water_y: float, specific_weight: float) -> dict:
    """Apply a pressure normal to a `NormalLoad`'s line (app/schemas.py).

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
