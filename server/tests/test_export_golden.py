"""The paired golden export: soil, a line load, a sheet pile and an anchor at once.

Every other export test exercises one structure kind on its own. This file is the one
that puts all four in a single deck, because the risks the three steps introduce are at
their seams rather than inside any one of them:

*   one property-id space shared by soil layers, a pile section and a tendon,
*   one node table, in which the anchor head must be a pile node *and* every pile node
    must be a soil node at the same time,
*   one sub-model part namespace, holding bodies, boundaries, a load and a support.

The two files are parsed and cross-checked against each other rather than diffed against
a stored blob: a golden file compared byte for byte fails on every whitespace change and
says nothing about whether the deck means anything. The invariants below are from
plan/structure-mode-implementation-plan.md, "Export-wide invariants".
"""

import json
import re

import pytest

from app import build, kratos
from app.schemas import MeshRequest, Project
from app.seed import seed_project
from tests import mdpa

# A wall retaining ground on its +x side: the anchor rakes back into that soil and the
# surcharge sits on it, so the model reads as one structure rather than three fixtures
# that happen to share a domain.
LINE_LOAD = {"id": "load_1", "name": "Surcharge", "kind": "line",
             "x0": 14.0, "x1": 22.0, "z": 0.0, "thickness": 0.15,
             "components": [0.0, -20.0], "distribution": "Uniform", "active": True}
PILE_SECTION = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
                "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}
PILE = {"id": "pile_1", "name": "Sheet pile 1", "section": "az26",
        "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}
TENDON = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
          "density": 7850.0, "spacing": 2.5, "tension_limit": 900.0,
          "compression_limit": None}
ANCHOR = {"id": "anchor_1", "name": "Anchor 1", "kind": "anchor", "section": "strand",
          "head": [12.0, -2.0], "tail": [20.0, -8.0], "prestress": 250.0, "active": True}

KRATOS_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def golden_project(**overrides) -> Project:
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_plane="xz", section_offset=20.0)
    payload.update(loads=[LINE_LOAD], beam_sections=[PILE_SECTION], beams=[PILE],
                   anchor_sections=[TENDON], anchors=[ANCHOR])
    payload.update(overrides)
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


@pytest.fixture(scope="module")
def golden(session):
    return kratos.export_project(golden_project(), MeshRequest(element_size=4.0, order=2))


@pytest.fixture(scope="module")
def deck(golden):
    return mdpa.parse(golden["mdpa"])


@pytest.fixture(scope="module")
def materials(golden):
    return json.loads(golden["materials"])["properties"]


# ── The model is all there ──────────────────────────────────────────────────

def test_one_deck_carries_soil_a_load_a_pile_and_an_anchor(deck):
    assert {block.name for block in deck.elements} == {
        "SmallStrainUPwDiffOrderElement2D6N",
        "LinearTimoshenkoCurvedBeamElement2D3N",
        "LinearTrussElement2D2N",
    }
    assert {block.name for block in deck.conditions} == {"LineLoadDiffOrderCondition2D3N"}
    for name in ("Soil_1", "Soil_2", "Sheet_pile_1", "Anchor_1", "Surcharge",
                 "Anchor_1_Support"):
        assert name in deck.parts, name


def test_the_structures_are_one_connected_model_not_three_beside_each_other(deck):
    """The seam the three steps meet at: pile bonded to soil, anchor hung off the pile."""
    soil = {n for b in deck.elements if b.name.startswith("SmallStrain")
            for nodes in b.entries.values() for n in nodes}
    pile = {n for b in deck.elements if "Beam" in b.name
            for nodes in b.entries.values() for n in nodes}
    head, tail = next(iter(next(b for b in deck.elements if "Truss" in b.name)
                           .entries.values()))

    assert pile <= soil, "every sheet-pile node is a soil node"
    assert head in pile, "the anchor head is a node the pile owns"
    assert tail not in soil and tail not in pile, "the tail is held by a support alone"


def test_the_load_sits_on_the_ground_surface_between_its_own_ends(deck):
    part = deck.parts["Surcharge"]
    xs = [deck.nodes[n][0] for n in part.nodes]

    assert min(xs) == pytest.approx(14.0) and max(xs) == pytest.approx(22.0)
    assert all(deck.nodes[n][1] == pytest.approx(0.0) for n in part.nodes)


# ── Export-wide invariants ──────────────────────────────────────────────────

def test_both_files_come_from_one_mesh_operation(session):
    """Same project in, byte-identical pair out: nothing in the deck is order- or
    run-dependent, which is what lets the two files be trusted against each other."""
    first = kratos.export_project(golden_project(), MeshRequest(element_size=4.0, order=2))
    second = kratos.export_project(golden_project(), MeshRequest(element_size=4.0, order=2))

    assert first["mdpa"] == second["mdpa"]
    assert first["materials"] == second["materials"]
    assert first["project_parameters"] == second["project_parameters"]


def test_every_element_and_condition_references_a_declared_property(deck):
    declared = set(deck.properties)

    assert declared, "the deck has to declare its properties"
    for block in deck.elements + deck.conditions:
        assert set(block.properties.values()) <= declared, block.name


def test_every_material_entry_names_a_part_the_deck_actually_has(materials, deck):
    for entry in materials:
        root, _, part = entry["model_part_name"].partition(".")
        assert root == "PorousDomain"
        assert part in deck.parts, entry["model_part_name"]


def test_property_ids_are_unique_across_soil_steel_and_tendon(materials):
    """Distinct property sets must never accidentally share an id.

    One entry per sub-model part, so two piles on one profile get two ids carrying the
    same numbers -- Kratos binds a Properties object to a model part by name, and the
    soil layers have always been written the same way.
    """
    ids = [entry["properties_id"] for entry in materials]

    assert len(set(ids)) == len(ids)
    assert all(isinstance(i, int) and i > 0 for i in ids)
    assert len(materials) == 4, "two soil layers, one pile, one anchor"


def test_sub_model_part_names_are_unique_and_legal_kratos_identifiers(golden, deck):
    names = re.findall(r"Begin SubModelPart (\S+)", golden["mdpa"])

    assert len(names) == len(set(names)) == len(deck.parts)
    for name in names:
        assert KRATOS_IDENTIFIER.fullmatch(name), name


def test_every_part_lists_exactly_the_nodes_its_own_entities_use(deck):
    blocks = deck.elements + deck.conditions
    for name, part in deck.parts.items():
        owned = set(part.elements) | set(part.conditions)
        if not owned:
            continue        # a boundary or support group is nodes by definition
        expected = {n for block in blocks
                    for entry, nodes in block.entries.items() if entry in owned
                    for n in nodes}
        assert part.nodes == sorted(expected), name


def test_an_unsupported_element_type_fails_loudly_before_anything_is_written():
    """The deck must refuse a shape it cannot express rather than write a broken one."""
    with pytest.raises(kratos.ExportError, match="no Kratos element is mapped"):
        kratos._lookup(kratos.ELEMENTS, 2, 3)      # gmsh type 3 is a 4-node quad


def test_an_unmapped_constitutive_law_is_named_in_the_warnings(golden):
    """Not a hard failure, deliberately: the seeded materials use models with no
    drop-in GeoMechanics law, so the export still runs and says what it substituted."""
    assert any("constitutive law" in warning for warning in golden["warnings"])


def test_a_soil_only_export_is_unchanged_by_any_of_this(session):
    """Backward compatibility: a project with no structures exports as it always did."""
    plain = kratos.export_project(
        golden_project(loads=[], beams=[], beam_sections=[],
                       anchors=[], anchor_sections=[]),
        MeshRequest(element_size=4.0, order=2),
    )
    bare = mdpa.parse(plain["mdpa"])

    assert {b.name for b in bare.elements} == {"SmallStrainUPwDiffOrderElement2D6N"}
    assert bare.conditions == []
    assert {e["model_part_name"] for e in json.loads(plain["materials"])["properties"]} \
        == {"PorousDomain.Soil_1", "PorousDomain.Soil_2"}
    assert not any(name.endswith("_Support") for name in bare.parts)


# ── Cross-file agreement ────────────────────────────────────────────────────

def test_the_pile_and_tendon_values_survive_into_the_material_file(materials):
    pile = next(e for e in materials if e["model_part_name"] == "PorousDomain.Sheet_pile_1")
    anchor = next(e for e in materials if e["model_part_name"] == "PorousDomain.Anchor_1")

    assert pile["Material"]["Variables"]["YOUNG_MODULUS"] == pytest.approx(PILE_SECTION["E"])
    assert pile["Material"]["Variables"]["I33"] == pytest.approx(PILE_SECTION["inertia"])
    # Both smeared over their out-of-plane spacing: the pile is continuous, the anchor
    # stands every 2.5 m, so only the anchor's numbers are divided down.
    assert anchor["Material"]["Variables"]["CROSS_AREA"] == pytest.approx(
        TENDON["area"] / TENDON["spacing"])
    assert anchor["Material"]["Variables"]["TRUSS_PRESTRESS_PK2"] == pytest.approx(
        ANCHOR["prestress"] / TENDON["spacing"])


def test_the_load_value_and_the_anchor_support_reach_the_process_file(golden, deck):
    doc = json.loads(golden["project_parameters"])
    loads = {p["Parameters"]["model_part_name"]: p["Parameters"]
             for p in doc["processes"]["loads_process_list"]}
    constraints = {p["Parameters"]["model_part_name"]
                   for p in doc["processes"]["constraints_process_list"]}

    assert loads["PorousDomain.Surcharge"]["value"] == [0.0, -20.0, 0.0]
    assert "PorousDomain.Anchor_1_Support" in constraints
    for name in set(loads) | constraints:
        assert name.partition(".")[2] in deck.parts, name
