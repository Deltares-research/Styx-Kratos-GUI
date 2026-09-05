"""Write the parts of the Kratos GeoMechanics ProjectParameters.json this exporter can
derive without inventing solver behaviour.

`solver_settings` and `problem_data` are left `{}`. Neither can be filled honestly yet:
solver type, time stepping and the linear solver are real engineering decisions with no
home in `Project` today, and guessing at them would silently pick an analysis for the
user rather than exporting the one they built. They stay empty until those fields exist.

`processes.constraints_process_list` and `processes.loads_process_list` are filled in,
because both are fully determined by the project already exported to the .mdpa: the
domain boundaries and their sub-model parts, and each load's own components (see
`app.kratos._load_variable`).

Confidence note: `python_module`/`process_name` below follow Kratos GeoMechanics-
Application's own apply_vector_constraint_table_process / apply_load_by_table_process
convention. Unlike the .mdpa property-id fix, this has not been checked against a real
solver-generated ProjectParameters.json -- there is none in examples/ yet. Diff the
first real run's file against this before trusting it for a solve.
"""

from __future__ import annotations

import json


def project_parameters(
    constraints: list[tuple[str, list[bool]]],
    loads: list[tuple[str, str, list[bool], list[float]]],
) -> str:
    """`constraints` is (sub-model part name, DISPLACEMENT is_fixed per axis).
    `loads` is (sub-model part name, Kratos variable, active per axis, value)."""
    return json.dumps({
        "problem_data": {},
        "solver_settings": {},
        "processes": {
            "constraints_process_list": [_constraint(name, is_fixed)
                                         for name, is_fixed in constraints],
            "loads_process_list": [_load(name, variable, active, value)
                                   for name, variable, active, value in loads],
        },
    }, indent=4)


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


def _load(part_name: str, variable: str, active: list[bool], value: list[float]) -> dict:
    return {
        "python_module": "apply_load_by_table_process",
        "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
        "process_name": "ApplyLoadByTableProcess",
        "Parameters": {
            "model_part_name": f"PorousDomain.{part_name}",
            "variable_name": variable,
            "active": list(active),
            "value": list(value),
            "table": [0, 0, 0],
        },
    }
