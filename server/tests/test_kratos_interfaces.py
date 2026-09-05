"""Interfaces in the exported deck: the node split, the contact elements, the materials.

Everything asserted here about the *shape* of the output is read off
examples/crow_case.mdpa, which contains the arrangement this feature reproduces:

    Begin Elements Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N
      22434 0  4639 4624 4633  4771 4765 4769
      12434 0  4624 4639 4633  4710 4716 4713

Two elements over one segment of sheet pile. The first three nodes are the pile's own,
which appear in no soil element; the last three are coincident copies belonging to the
soil on one face. The two faces carry opposite node orders, which is how each element's
normal points at the ground it holds.
"""

from __future__ import annotations

import json

import pytest

from app import build, kratos
from app.schemas import MeshRequest, Project
from app.seed import seed_project
from tests import mdpa
from tests.test_kratos import BEAM_SECTION, deck_of

SECTION = {"id": "steel_soil", "name": "Steel against sand", "material": "mat_sand",
           "r_inter": 0.67, "virtual_thickness": 0.01}


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


def interfaced_project(side: str = "both", active: bool = True, dimension: int = 2,
                       structure: str | None = "sheetpile_1", points=None,
                       section: dict | None = None) -> Project:
    payload = seed_project().model_dump()
    payload.update(dimension=dimension, section_plane="xz", section_offset=20.0)
    payload["beam_sections"] = [BEAM_SECTION]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    material = payload["materials"][0]["id"]
    payload["interface_sections"] = [{**SECTION, **(section or {}), "material": material}]
    payload["interfaces"] = [{"id": "interface_1", "name": "Wall contact",
                              "section": SECTION["id"], "structure": structure,
                              "points": points, "side": side, "active": active}]
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def contacted(session):
    """A quadratic section: one sheet pile with soil unglued from both its faces."""
    return kratos.export_project(interfaced_project(), MeshRequest(element_size=3.0, order=2))


def interface_block(deck: mdpa.Deck) -> mdpa.Block:
    return next(b for b in deck.elements if "Interface" in b.name)


def soil_nodes(deck: mdpa.Deck) -> set[int]:
    return {n for block in deck.elements if block.name.startswith("SmallStrainUPw")
            for nodes in block.entries.values() for n in nodes}


def beam_nodes(deck: mdpa.Deck) -> set[int]:
    return {n for block in deck.elements if "Beam" in block.name
            for nodes in block.entries.values() for n in nodes}


# ── The element ─────────────────────────────────────────────────────────────

def test_a_quadratic_section_writes_the_reference_deck_s_interface_class(contacted):
    names = {block.name for block in deck_of(contacted).elements}
    assert "Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N" in names


def test_a_first_order_deck_writes_the_four_node_interface(session):
    export = kratos.export_project(interfaced_project(),
                                   MeshRequest(element_size=3.0, order=1))
    block = interface_block(deck_of(export))
    assert block.name == "Geo_UPwLineInterfacePlaneStrainElement2Plus2N"
    assert all(len(nodes) == 4 for nodes in block.entries.values())


def test_interface_elements_keep_property_zero_like_every_other_element(contacted):
    assert set(interface_block(deck_of(contacted)).properties.values()) == {0}


def test_the_two_halves_of_an_element_are_coincident(contacted):
    """Zero thickness: node i and node i+half sit on exactly the same point."""
    deck = deck_of(contacted)
    for nodes in interface_block(deck).entries.values():
        half = len(nodes) // 2
        for first, second in zip(nodes[:half], nodes[half:]):
            assert deck.nodes[first] == pytest.approx(deck.nodes[second], abs=1e-9)
            assert first != second


def test_the_first_half_is_the_pile_and_the_second_half_is_the_soil(contacted):
    deck = deck_of(contacted)
    piles, soils = beam_nodes(deck), soil_nodes(deck)
    for nodes in interface_block(deck).entries.values():
        half = len(nodes) // 2
        assert set(nodes[:half]) <= piles
        assert set(nodes[half:]) <= soils


def test_the_pile_is_no_longer_welded_to_the_soil(contacted):
    """The whole point of the interface, and crow_case.mdpa's own arrangement: with a
    contact on both faces the wall shares no node with the ground."""
    deck = deck_of(contacted)
    assert not beam_nodes(deck) & soil_nodes(deck)


def test_each_face_of_the_wall_gets_its_own_copy_of_the_soil(contacted):
    """Two elements per pile segment, whose soil halves are disjoint -- one per face."""
    deck = deck_of(contacted)
    block = interface_block(deck)
    by_segment: dict[frozenset[int], list[list[int]]] = {}
    for nodes in block.entries.values():
        half = len(nodes) // 2
        by_segment.setdefault(frozenset(nodes[:half]), []).append(nodes[half:])

    assert by_segment, "there is at least one segment"
    for faces in by_segment.values():
        assert len(faces) == 2, "one element per face of the wall"
        # Disjoint, save at the toe: the ground closes under the pile, so the two faces
        # meet there in one node -- crow_case.mdpa writes 52 copies a side for 53 pile
        # nodes for exactly this reason.
        assert len(set(faces[0]) & set(faces[1])) <= 1
        assert set(faces[0]) != set(faces[1])


def test_the_two_faces_carry_opposite_node_orders(contacted):
    """22434 runs 4639->4624 where 12434 runs 4624->4639: each element's +90 degree
    normal points at the soil half it holds, so the two faces must disagree."""
    deck = deck_of(contacted)
    block = interface_block(deck)
    pairs: dict[frozenset[int], list[list[int]]] = {}
    for nodes in block.entries.values():
        half = len(nodes) // 2
        pairs.setdefault(frozenset(nodes[:half]), []).append(nodes[:half])

    for first, second in pairs.values():
        assert first[0] == second[1] and first[1] == second[0]


def test_each_element_normal_points_into_the_soil_it_holds(contacted):
    deck = deck_of(contacted)
    for nodes in interface_block(deck).entries.values():
        half = len(nodes) // 2
        (x0, y0, _), (x1, y1, _) = deck.nodes[nodes[0]], deck.nodes[nodes[1]]
        normal = (-(y1 - y0), x1 - x0)
        # The soil half's own elements sit on the side the normal points at. Take any
        # soil element holding that node and compare its centre against the line.
        holder = next(n for block in deck.elements
                      if block.name.startswith("SmallStrainUPw")
                      for n in block.entries.values()
                      if set(nodes[half:]) <= set(n))
        centre = [sum(deck.nodes[n][axis] for n in holder[:3]) / 3 for axis in (0, 1)]
        towards = normal[0] * (centre[0] - x0) + normal[1] * (centre[1] - y0)
        assert towards > 0


# ── Where it lands in the deck ──────────────────────────────────────────────

def test_the_interface_gets_its_own_sub_model_part(contacted):
    deck = deck_of(contacted)
    part = deck.parts["Wall_contact"]
    block = interface_block(deck)

    assert set(part.elements) == set(block.entries)
    assert part.nodes == sorted({n for e in part.elements for n in block.entries[e]})
    assert not part.conditions


def test_the_split_nodes_are_in_the_node_table_and_nothing_is_orphaned(contacted):
    deck = deck_of(contacted)
    used = {n for block in deck.elements for nodes in block.entries.values() for n in nodes}
    used |= {n for block in deck.conditions for nodes in block.entries.values() for n in nodes}

    assert used == set(deck.nodes)
    assert sorted(deck.nodes) == list(range(1, len(deck.nodes) + 1))


def test_every_soil_triangle_is_still_counter_clockwise_after_the_split(contacted):
    deck = deck_of(contacted)
    for block in deck.elements:
        if not block.name.startswith("SmallStrainUPw"):
            continue
        for nodes in block.entries.values():
            (x1, y1, _), (x2, y2, _), (x3, y3, _) = (deck.nodes[n] for n in nodes[:3])
            assert (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1) > 0


def test_a_soil_sub_model_part_still_lists_exactly_its_own_nodes(contacted):
    deck = deck_of(contacted)
    for block in deck.elements:
        if not block.name.startswith("SmallStrainUPw"):
            continue
        part = next(p for p in deck.parts.values() if set(p.elements) == set(block.entries))
        assert part.nodes == sorted({n for e in part.elements for n in block.entries[e]})


def test_a_boundary_group_picks_up_the_copies_that_land_on_it(contacted):
    """A duplicated node inherits its original's position, so a boundary group defined
    by geometry has to hold both or the model is only half restrained there."""
    deck = deck_of(contacted)
    bottom = deck.parts["Bottom_Fixed"]
    lowest = min(z for _, z, _ in (deck.nodes[n] for n in deck.nodes))

    on_plane = {n for n, (_, y, _) in deck.nodes.items() if abs(y - lowest) < 1e-6}
    assert set(bottom.nodes) == on_plane


# ── Which sides, and which interfaces ───────────────────────────────────────

def test_detaching_one_side_leaves_the_other_bonded(session):
    export = kratos.export_project(interfaced_project(side="left"),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)

    assert beam_nodes(deck) & soil_nodes(deck), "the bonded face still shares its nodes"
    block = interface_block(deck)
    per_segment: dict[frozenset[int], int] = {}
    for nodes in block.entries.values():
        per_segment[frozenset(nodes[:3])] = per_segment.get(frozenset(nodes[:3]), 0) + 1
    assert set(per_segment.values()) == {1}


def test_an_inactive_interface_is_kept_in_the_project_but_not_exported(session):
    export = kratos.export_project(interfaced_project(active=False),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)

    assert not any("Interface" in block.name for block in deck.elements)
    assert "Wall_contact" not in deck.parts
    assert beam_nodes(deck) & soil_nodes(deck), "the pile is bonded again"


def test_an_interface_on_a_switched_off_pile_is_not_exported(session):
    project = interfaced_project()
    project.beams[0].active = False
    export = kratos.export_project(project, MeshRequest(element_size=3.0, order=2))

    assert not any("Interface" in block.name for block in deck_of(export).elements)


def test_a_free_interface_splits_soil_from_soil(session):
    """No structure in the middle: one side keeps the original nodes, the other is
    detached, and the contact holds the two soils together."""
    project = interfaced_project(side="left", structure=None,
                                 points=[[8.0, 0.0], [8.0, -10.0]])
    export = kratos.export_project(project, MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)
    block = interface_block(deck)

    assert block.entries
    soils = soil_nodes(deck)
    for nodes in block.entries.values():
        assert set(nodes) <= soils, "both faces are soil"
        half = len(nodes) // 2
        for first, second in zip(nodes[:half], nodes[half:]):
            assert deck.nodes[first] == pytest.approx(deck.nodes[second], abs=1e-9)


def test_a_free_interface_ties_its_own_tip_together(session):
    """Where the line stops inside the soil there is no second face -- the ground is
    continuous around it -- so that one element shares the node between its halves.
    Exactly one element does, and it is the last one."""
    project = interfaced_project(side="left", structure=None,
                                 points=[[8.0, 0.0], [8.0, -10.0]])
    export = kratos.export_project(project, MeshRequest(element_size=3.0, order=2))
    block = interface_block(deck_of(export))

    tips = [nodes for nodes in block.entries.values() if len(set(nodes)) < len(nodes)]
    assert len(tips) == 1


def test_a_3d_project_writes_no_interface_and_says_so(session):
    export = kratos.export_project(interfaced_project(dimension=3),
                                   MeshRequest(element_size=6.0, order=2))

    assert not any("Interface" in block.name for block in deck_of(export).elements)
    assert any("plane-strain only" in warning for warning in export["warnings"])


# ── MaterialParameters.json ─────────────────────────────────────────────────

def entries_of(export: dict) -> list[dict]:
    return json.loads(export["materials"])["properties"]


def test_the_interface_section_becomes_a_material_entry_mapped_to_its_part(contacted):
    entry = next(e for e in entries_of(contacted)
                 if e["model_part_name"] == "PorousDomain.Wall_contact")
    variables = entry["Material"]["Variables"]

    assert entry["Material"]["constitutive_law"]["name"]
    assert variables["INTERFACE_NORMAL_STIFFNESS"] > 0
    assert variables["INTERFACE_SHEAR_STIFFNESS"] > 0


def test_the_stiffness_is_the_soil_s_over_the_virtual_thickness(contacted):
    soil = seed_project().materials[0]
    variables = next(e["Material"]["Variables"] for e in entries_of(contacted)
                     if e["model_part_name"] == "PorousDomain.Wall_contact")

    assert variables["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(soil.E / 0.01)
    assert variables["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(
        soil.E / (2 * (1 + soil.nu) * 0.01))


def test_an_explicit_stiffness_is_used_as_it_stands(session):
    export = kratos.export_project(
        interfaced_project(section={"normal_stiffness": 1.5e6, "shear_stiffness": 5.0e5}),
        MeshRequest(element_size=3.0, order=2))
    variables = next(e["Material"]["Variables"] for e in entries_of(export)
                     if e["model_part_name"] == "PorousDomain.Wall_contact")

    assert variables["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(1.5e6)
    assert variables["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(5.0e5)


def test_the_strength_is_the_soil_s_reduced_by_r_inter(contacted):
    """That is what the factor means: tan(delta) = r_inter * tan(phi), c_i = r_inter * c."""
    import math
    soil = seed_project().materials[0]
    variables = next(e["Material"]["Variables"] for e in entries_of(contacted)
                     if e["model_part_name"] == "PorousDomain.Wall_contact")

    assert variables["GEO_COHESION"] == pytest.approx(soil.c * 0.67)
    assert variables["GEO_FRICTION_ANGLE"] == pytest.approx(
        math.degrees(math.atan(math.tan(math.radians(soil.phi)) * 0.67)))


def test_the_interface_property_id_is_unique_and_non_zero(contacted):
    ids = [entry["properties_id"] for entry in entries_of(contacted)]
    assert len(set(ids)) == len(ids)
    assert all(i > 0 for i in ids)
