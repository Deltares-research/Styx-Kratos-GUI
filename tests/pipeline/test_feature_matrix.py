"""Features one at a time, and the pairs that interact (plan alpha 2.3).

The base is the test model stripped to its soil. Each case adds features back -- a
pile, its interfaces, the strut, the loads, the water, the phases -- in the form the
test model carries them, so every combination is one a valid project can hold. Each deck must pass
`check_deck` (conftest runs it on every export) and show the feature in the file: the
element or condition it should have written, on the parts it should be on.
"""

from __future__ import annotations

import json

import pytest

from core import build, kratos
from tests.models import excavation
from core.schemas import MeshRequest, Project
from tests import mdpa
from tests.pipeline.deck_invariants import check_deck

FEATURES = ("pile", "interfaces", "strut", "loads", "normal_loads", "water", "phases")


def project_with(*features) -> Project:
    full = excavation.excavation_project(staged=True).model_dump(mode="json")
    base = dict(full)
    base.update(beams=[], anchors=[], interfaces=[], loads=[], normal_loads=[],
                phases=[], water=None)
    if "pile" in features:
        base["beams"] = full["beams"]
    if "interfaces" in features:
        base["interfaces"] = full["interfaces"]
    if "strut" in features:
        base["anchors"] = full["anchors"]
    if "loads" in features:
        base["loads"] = full["loads"]
    if "water" in features:
        base["water"] = full["water"]
    if "normal_loads" in features:
        base["normal_loads"] = full["normal_loads"]
    if "phases" in features:
        # The phases name the test model's parts; a part left out is taken out of them too, the
        # edit a user makes before deleting it (finding F3 refuses the delete otherwise).
        present = set(Project.model_validate(base).stageable_keys())
        base["phases"] = [dict(phase,
                               activate=[k for k in phase.get("activate", []) if k in present],
                               deactivate=[k for k in phase.get("deactivate", []) if k in present])
                          for phase in full["phases"]]
    return Project.model_validate(base)


def export_of(*features, order=2):
    with build.session():
        export = kratos.export_project(project_with(*features),
                                       MeshRequest(element_size=8.0, order=order))
    assert check_deck(export) == []
    return export, mdpa.parse(export["mdpa"])


def classes(deck) -> set[str]:
    return {b.name for b in deck.elements + deck.conditions}


def test_bare_soil_is_soil_and_nothing_else():
    _, deck = export_of()
    assert classes(deck) == {"SmallStrainUPwDiffOrderElement2D6N"}


def test_a_pile_writes_beam_elements_on_its_own_part():
    _, deck = export_of("pile")
    assert "LinearTimoshenkoCurvedBeamElement2D3N" in classes(deck)
    assert deck.parts["SheetPileWall"].elements


def test_interfaces_split_the_nodes_along_the_pile():
    _, bonded = export_of("pile")
    _, split = export_of("pile", "interfaces")
    assert any("Interface" in name for name in classes(split))
    assert len(split.nodes) > len(bonded.nodes), "each soil side gets its own copy"


def test_the_strut_shares_its_head_node_with_the_pile():
    _, deck = export_of("pile", "strut")
    truss = next(b for b in deck.elements if "Truss" in b.name)
    beam_nodes = {n for b in deck.elements if "Beam" in b.name
                  for c in b.entries.values() for n in c}
    heads = [c[0] for c in truss.entries.values()] + [c[1] for c in truss.entries.values()]
    assert any(n in beam_nodes for n in heads)


def test_a_line_load_lands_on_the_ground_surface():
    export, deck = export_of("loads")
    condition = next(b for b in deck.conditions if "LineLoad" in b.name)
    top = max(xyz[1] for xyz in deck.nodes.values())
    loaded = {n for c in condition.entries.values() for n in c}
    assert all(abs(deck.nodes[n][1] - top) < 1e-9 for n in loaded)


def test_a_hydrostatic_normal_load_needs_and_uses_the_water_level():
    with pytest.raises(Exception):
        project_with("pile", "normal_loads")       # hydrostatic, no water: refused
    _, deck = export_of("pile", "water", "normal_loads")
    assert any("NormalLoad" in name for name in classes(deck))


def test_water_writes_the_pore_pressure_field():
    export, _ = export_of("water")
    first = next(iter(json.loads(export["project_parameters"])["stages"].values()))
    processes = [p.get("python_module") for group in
                 first["stage_settings"]["processes"].values() for p in group]
    assert "apply_scalar_constraint_table_process" in processes


def test_phases_become_one_stage_each():
    export, _ = export_of("pile", "interfaces", "strut", "loads", "water", "normal_loads",
                          "phases")
    params = json.loads(export["project_parameters"])
    assert len(params["orchestrator"]["settings"]["execution_list"]) == \
        len(excavation.excavation_project(staged=True).phases)


@pytest.mark.parametrize("features", [(), ("pile",), ("pile", "interfaces"),
                                      ("pile", "strut", "loads")])
def test_order_1_and_order_2_write_the_same_parts(features):
    _, linear = export_of(*features, order=1)
    _, quadratic = export_of(*features, order=2)
    assert set(linear.parts) == set(quadratic.parts)
    assert len(linear.nodes) < len(quadratic.nodes), "mid-side nodes in the quadratic one"


@pytest.mark.parametrize("left_out", FEATURES)
def test_any_one_feature_left_out_still_exports(left_out):
    wanted = [f for f in FEATURES if f != left_out]
    if left_out == "pile":
        wanted = [f for f in wanted if f not in ("interfaces", "strut")]
    if left_out == "water":
        wanted = [f for f in wanted if f != "normal_loads"]
    export_of(*wanted)
