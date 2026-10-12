"""The decks' structure, frozen (plan alpha 2.5).

For three fixed models, a normalised summary of the deck -- part names, element and
condition classes with their counts, per stage the processes and the parts switched off
and on, and every material's variables -- is compared with a committed snapshot. Node
coordinates and ids are left out, so a gmsh upgrade does not churn it; counts, which a
mesher may shift slightly, are held to 2 %, everything else exactly.

A deliberate change: `pytest tests/pipeline/test_deck_snapshot.py --update-snapshots`,
then review the diff of `deck_snapshots/*.json` like any other change. A difference in a
material value or a process list is exactly what this exists to put in front of a
reviewer -- the six defects only a Kratos run found were all of that kind.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import MeshRequest
from core.model.templates import seed_project
from tests import mdpa
from tests.models import excavation

SNAPSHOTS = Path(__file__).with_name("deck_snapshots")
COUNT_TOLERANCE = 0.02

MODELS = {
    "excavation_staged": (lambda: excavation.excavation_project(staged=True),
                          MeshRequest(element_size=8.0, order=2)),
    "excavation_unstaged": (lambda: excavation.excavation_project(staged=False),
                            MeshRequest(element_size=8.0, order=1)),
    "seed_3d": (lambda: seed_project(), MeshRequest(element_size=12.0, order=1)),
}


def summary(export: dict) -> dict:
    deck = mdpa.parse(export["mdpa"])
    params = json.loads(export["project_parameters"])
    stages = {}
    for name in params["orchestrator"]["settings"]["execution_list"]:
        body = params["stages"][name]
        settings = body["stage_settings"]
        operations = {}
        for op in (body.get("stage_preprocess") or {}).get("operations") or []:
            operations.setdefault(op["name"].rsplit(".", 1)[-1], []).extend(
                sorted((op.get("Parameters") or {}).get("model_part_name_list") or []))
        stages[name] = {
            "processes": sorted(Counter(p.get("python_module") for group in
                                        settings["processes"].values() for p in group).items()),
            "operations": operations,
            "problem_domain": sorted(settings["solver_settings"]
                                     ["problem_domain_sub_model_part_list"]),
            "materials": settings["solver_settings"]["material_import_settings"]
            ["materials_filename"],
            "reset_totals": settings["solver_settings"].get("reset_totals"),
        }
    materials = {}
    for key in ("materials", "initial_materials"):
        if export.get(key):
            for entry in json.loads(export[key])["properties"]:
                material = entry["Material"]
                materials[f"{key}:{entry['model_part_name']}"] = {
                    "law": material["constitutive_law"]["name"],
                    "variables": {k: v for k, v in sorted(material.get("Variables", {}).items())},
                }
    return {
        "parts": sorted(deck.parts),
        "elements": dict(sorted(Counter({b.name: len(b.entries) for b in deck.elements}).items())),
        "conditions": dict(sorted(Counter({b.name: len(b.entries) for b in deck.conditions}).items())),
        "nodes": len(deck.nodes),
        "stages": stages,
        "materials": materials,
    }


def _close(a, b) -> bool:
    return abs(a - b) <= COUNT_TOLERANCE * max(abs(a), abs(b), 1)


def differences(current: dict, committed: dict) -> list[str]:
    out = []
    for key in ("parts", "stages", "materials"):
        if current[key] != committed[key]:
            out.append(f"{key} changed")
    for key in ("elements", "conditions"):
        if set(current[key]) != set(committed[key]):
            out.append(f"{key}: classes {sorted(current[key])} != {sorted(committed[key])}")
        else:
            out += [f"{key}: {name} {current[key][name]} vs {committed[key][name]}"
                    for name in current[key]
                    if not _close(current[key][name], committed[key][name])]
    if not _close(current["nodes"], committed["nodes"]):
        out.append(f"nodes {current['nodes']} vs {committed['nodes']}")
    return out


@pytest.mark.parametrize("name", sorted(MODELS))
def test_the_deck_structure_matches_its_snapshot(name, request):
    build_project, settings = MODELS[name]
    with solid_model.session():
        current = summary(writer.export_project(build_project(), settings))
    path = SNAPSHOTS / f"{name}.json"
    if request.config.getoption("--update-snapshots") or not path.exists():
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    committed = json.loads(path.read_text(encoding="utf-8"))
    # Round-tripped through JSON so tuples and lists compare alike.
    current = json.loads(json.dumps(current))

    assert differences(current, committed) == [], (
        "the deck's structure changed; if deliberate, rerun with --update-snapshots and "
        f"review the diff of {path.name}")


def test_a_count_within_two_percent_is_not_a_change():
    base = {"parts": [], "stages": {}, "materials": {}, "nodes": 1000,
            "elements": {"E": 500}, "conditions": {}}
    assert differences(dict(base, nodes=1015, elements={"E": 505}), base) == []
    assert differences(dict(base, nodes=1100), base) != []
    assert differences(dict(base, materials={"m": 1}), base) == ["materials changed"]
