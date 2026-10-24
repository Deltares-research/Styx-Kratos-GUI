"""Kratos' own Muskat tests, and the part of a deck the Muskat tests compare.

`deck_view` is what Kratos reads of a deck, with the names left out: the solver, the
processes, the results asked for, the materials and the mesh. The names follow the
project (its name, its layer's name), so one model built two ways -- by its model script
`tests/models/muskat.py`, by `kratos-cli`, in the GUI -- gives two equal views when
Kratos would calculate the same thing.

`checkout()` is `GeoMechanicsApplication/tests/Muskat` in the Kratos source beside the
configured build, or a skip. `reference_view(case)` is its deck for `case`
("saturated_hydrostatic", "van_genuchten_hydrostatic") in the same view, less the mesh,
and `expected(case)` the values its `test_Muskat.py` asserts: by node, the node's (x, y)
in its `common/column.mdpa`, and the values there, as `tests/models/muskat.KRATOS_A`
holds them.
"""

from __future__ import annotations

import ast
import json
import os
from functools import cache
from pathlib import Path

import pytest

from core.analysis import calculation
from tests import mdpa

NAMES = ("model_part_name",)
"""A process's own part: named after the condition or the layer."""

SOLVER_FILES = ("model_import_settings", "material_import_settings",
                "problem_domain_sub_model_part_list", "processes_sub_model_part_list",
                "body_domain_sub_model_part_list")
"""The solver settings that name the deck's files and parts."""

GROUPS = ("constraints_process_list", "loads_process_list", "auxiliary_process_list")


def _process(process: dict) -> dict:
    return {"process_name": process["process_name"],
            **{key: value for key, value in process["Parameters"].items()
               if key not in NAMES}}


def _stage(settings: dict) -> dict:
    solver = {key: value for key, value in settings["solver_settings"].items()
              if key not in SOLVER_FILES}
    processes = settings["processes"]
    output = settings["output_processes"]["gid_output"][0]["Parameters"]
    results = output["postprocess_parameters"]["result_file_configuration"]
    return {"solver": solver,
            **{group: [_process(p) for p in processes.get(group, [])] for group in GROUPS},
            "nodal_results": results["nodal_results"],
            "gauss_point_results": results.get("gauss_point_results", [])}


def _materials(text: str) -> list:
    """Each soil's law and variables. A whole number is the same value to Kratos written
    either way (2290 typed on the command line, 2290.0 in a script)."""
    def value(given):
        return float(given) if type(given) is int else given
    return [(p["Material"]["constitutive_law"]["name"],
             {key: value(given) for key, given in p["Material"]["Variables"].items()})
            for p in json.loads(text)["properties"]]


def _mesh(text: str) -> dict:
    deck = mdpa.parse(text)
    return {"nodes": deck.nodes,
            "elements": [(block.name, block.entries) for block in deck.elements],
            "conditions": [(block.name, block.entries) for block in deck.conditions],
            "parts": sorted((sorted(part.nodes), sorted(part.elements),
                             sorted(part.conditions)) for part in deck.parts.values())}


def deck_view(export: dict) -> dict:
    """`export` is what `writer.export_project` answers, or `read_deck` of a folder."""
    parameters = json.loads(export["project_parameters"])
    order = parameters["orchestrator"]["settings"]["execution_list"]
    return {"stages": [_stage(parameters["stages"][name]["stage_settings"])
                       for name in order],
            "materials": _materials(export["materials"]),
            "mesh": _mesh(export["mdpa"])}


def read_deck(folder: Path) -> dict:
    """The deck `kratos-cli export` wrote into `folder`, as `export_project` answers it."""
    from core.kratos import deck_files

    (mesh,) = folder.glob("*.mdpa")
    return {"mdpa": mesh.read_text(encoding="utf-8"),
            "project_parameters": (folder / deck_files.PARAMETERS_NAME).read_text(
                encoding="utf-8"),
            "materials": (folder / deck_files.MATERIALS_NAME).read_text(encoding="utf-8")}


# ── Kratos' own tests/Muskat ───────────────────────────────────────────────

def checkout() -> Path:
    build = os.environ.get(calculation.KRATOS_ENV) or calculation._settings().get("kratos")
    folder = (Path(build).parents[1] / "applications" / "GeoMechanicsApplication"
              / "tests" / "Muskat") if build else None
    if folder is None or not (folder / "common" / "column.mdpa").is_file():
        pytest.skip(f"no Kratos source with tests/Muskat beside the build {build!r}")
    return folder


def reference_view(case: str) -> dict:
    """The reference deck of `case`: its one stage and its materials."""
    folder = checkout() / case
    parameters = json.loads((folder / "ProjectParameters.json").read_text(encoding="utf-8"))
    materials = parameters["solver_settings"]["material_import_settings"]["materials_filename"]
    return {"stages": [_stage(parameters)],
            "materials": _materials((folder / materials).read_text(encoding="utf-8"))}


def reference_elements() -> set[str]:
    """The element names of the reference decks' mesh, `common/column.mdpa`."""
    return {block.name for block in _column().elements}


@cache
def _column() -> mdpa.Deck:
    return mdpa.parse((checkout() / "common" / "column.mdpa").read_text(encoding="utf-8"))


def expected(case: str) -> dict:
    """What `test_Muskat.py`'s `test_muskat_<case>` asserts, read off its source: by node,
    the node's (x, y) and the values, a vector as its x and y."""
    source = (checkout().parent / "test_Muskat.py").read_text(encoding="utf-8")
    test = next(node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.FunctionDef) and node.name == f"test_muskat_{case}")
    table = next(node.value for node in ast.walk(test)
                 if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict))
    nodes = _column().nodes
    out: dict[int, tuple[tuple[float, float], dict]] = {}
    for variable, results in zip(table.keys, table.values):
        assert isinstance(variable, ast.Constant) and isinstance(results, ast.List)
        for result in results.elts:
            assert isinstance(result, ast.Call)
            given = {word.arg: ast.literal_eval(word.value) for word in result.keywords}
            node, value = given["node_id"], given["value"]
            x, y, _ = nodes[node]
            out.setdefault(node, ((x, y), {}))[1][variable.value] = (
                tuple(value[:2]) if isinstance(value, list) else value)
    return out
