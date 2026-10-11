"""Interfaces in the exported deck: the node split, the contact elements, the materials.

Everything asserted here about the *shape* of the output is read off a real Kratos
deck with a contact on both faces of a sheet pile, the arrangement this feature
reproduces:

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

from core import build, kratos
KILO = 1000.0  # kN -> N: these tests write old-style projects, converted on load (core/legacy.py)
from core.schemas import MeshRequest, Project
from core.seed import seed_project
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
    payload.update(dimension=dimension, section_offset=20.0)
    payload["beam_sections"] = [BEAM_SECTION]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    material = payload["materials"][0]["id"]
    # `material` first, so an override of it -- including to None, which asks for the
    # per-adjacent-body derivation -- actually takes.
    payload["interface_sections"] = [{**SECTION, "material": material, **(section or {})}]
    payload["interfaces"] = [{"id": "interface_1", "name": "Wall contact",
                              "section": SECTION["id"], "structure": structure,
                              "points": points, "side": side, "active": active}]
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def contacted(session):
    """A quadratic section: one sheet pile with soil unglued from both its faces."""
    return kratos.export_project(interfaced_project(), MeshRequest(element_size=3.0, order=2))


def interface_block(deck: mdpa.Deck) -> mdpa.Block:
    """Every contact element in the deck, as one block.

    The deck writes one block per soil body the contact runs against, so a lift can be
    deactivated together with the interface along it (`kratos._interface_by_body`).
    Tests about the contact as a whole want all of them; the split itself is what
    `test_the_contact_is_split_per_soil_body_it_runs_against` checks.
    """
    blocks = [b for b in deck.elements if "Interface" in b.name]
    merged = mdpa.Block(name=blocks[0].name)
    for block in blocks:
        merged.entries.update(block.entries)
        merged.properties.update(block.properties)
    return merged


def interface_material(export: dict) -> dict:
    """The contact's material variables.

    One entry per sub-model part, so one per soil body the contact runs against, and
    they are the same property set under different names -- the section is the
    interface's, not the body's. Any of them answers what the section became.
    """
    entries = [e for e in entries_of(export)
               if e["model_part_name"].startswith("PorousDomain.Wall_contact")]
    assert entries, "the contact has no material entry"
    variables = [e["Material"]["Variables"] for e in entries]
    assert all(v == variables[0] for v in variables),         "a section naming a material cannot become two different property sets"
    return variables[0]


def interface_parts(deck: mdpa.Deck) -> dict[str, mdpa.Part]:
    """The contact's sub-model parts, one per soil body it holds."""
    return {name: part for name, part in deck.parts.items()
            if name.startswith("Wall_contact") and not name.endswith(("_Master", "_Slave"))}


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
    """The whole point of the interface, and a real deck's own arrangement: with a
    contact on both faces the wall shares no node with the ground."""
    deck = deck_of(contacted)
    assert not beam_nodes(deck) & soil_nodes(deck)


# ── Wall installation staging ────────────────────────────────────────────────

def test_the_contact_is_installed_together_with_its_pile(contacted):
    """A wall's interface does not exist before the wall does either: both parts are
    deactivated in the initial stage and activated together in wall installation."""
    doc = json.loads(contacted["project_parameters"])
    assert doc["orchestrator"]["settings"]["execution_list"] == \
        ["1_Initial_stage", "2_Wall_installation"]

    installed = set(doc["stages"]["2_Wall_installation"]["stage_preprocess"]
                    ["operations"][0]["Parameters"]["model_part_name_list"])
    assert installed == {"PorousDomain.Sheet_pile_1"} | {
        f"PorousDomain.{name}" for name in interface_parts(deck_of(contacted))}


def test_a_soil_to_soil_interface_is_not_staged(session):
    """`structure is None` means this interface splits soil from soil -- there is no
    installation moment for it to wait for, so it is not deactivated up front."""
    project = interfaced_project(side="left", structure=None,
                                 points=[[8.0, 0.0], [8.0, -10.0]])
    export = kratos.export_project(project, MeshRequest(element_size=3.0, order=2))
    doc = json.loads(export["project_parameters"])

    assert doc["orchestrator"]["settings"]["execution_list"] == \
        ["1_Initial_stage", "2_Wall_installation"]
    staged = set(doc["stages"]["2_Wall_installation"]["stage_preprocess"]
                ["operations"][0]["Parameters"]["model_part_name_list"])
    assert staged == {"PorousDomain.Sheet_pile_1"}, \
        "the soil-to-soil interface must not be in the staged list, only the pile"


def test_the_split_sides_are_tied_together_before_the_wall_is_installed(contacted):
    """Deactivating the pile and its interface (above) leaves nothing else holding the
    two soil copies the interface split apart -- without a tie the initial stage models
    ground that is silently torn in two along the future wall line."""
    deck = deck_of(contacted)
    master, slave = deck.parts["Wall_contact_Master"], deck.parts["Wall_contact_Slave"]

    assert master.nodes and slave.nodes
    assert not master.elements and not master.conditions
    assert not slave.elements and not slave.conditions
    assert not set(master.nodes) & set(slave.nodes)
    assert len(master.nodes) == len(slave.nodes)
    assert {deck.nodes[n] for n in master.nodes} == {deck.nodes[n] for n in slave.nodes}, \
        "every master node has a slave at the exact same point, and vice versa"


def test_the_toe_does_not_need_a_tie(contacted):
    """Where the ground closes under the pile's toe the two faces already share one
    node (see test_each_face_of_the_wall_gets_its_own_copy_of_the_soil below): it is
    already continuous and must not appear in either tie part."""
    deck = deck_of(contacted)
    block = interface_block(deck)
    by_segment: dict[frozenset[int], list[list[int]]] = {}
    for nodes in block.entries.values():
        half = len(nodes) // 2
        by_segment.setdefault(frozenset(nodes[:half]), []).append(nodes[half:])
    shared = {n for faces in by_segment.values() if len(faces) == 2
              for n in set(faces[0]) & set(faces[1])}
    assert shared, "the fixture's pile has a toe with exactly one shared node"

    tied = (set(deck.parts["Wall_contact_Master"].nodes) |
            set(deck.parts["Wall_contact_Slave"].nodes))
    assert not shared & tied


def test_the_tie_is_only_needed_before_installation(contacted):
    """Once the wall is installed its own interface ties the sides together; asking for
    both would double-constrain the same nodes."""
    doc = json.loads(contacted["project_parameters"])
    initial = (doc["stages"]["1_Initial_stage"]["stage_settings"]["processes"]
              ["constraints_process_list"])
    installed = (doc["stages"]["2_Wall_installation"]["stage_settings"]["processes"]
                ["constraints_process_list"])

    tie = next(p for p in initial
              if p["process_name"] == "AssignMasterSlaveConstraintsToNeighboursUtility")
    assert tie["Parameters"]["master_model_part_name"] == "PorousDomain.Wall_contact_Master"
    assert tie["Parameters"]["slave_model_part_name"] == "PorousDomain.Wall_contact_Slave"
    assert not any(p["process_name"] == "AssignMasterSlaveConstraintsToNeighboursUtility"
                  for p in installed)


def tie_of(export: dict) -> dict:
    doc = json.loads(export["project_parameters"])
    first = next(iter(doc["stages"].values()))["stage_settings"]["processes"]
    return next(p["Parameters"] for p in first["constraints_process_list"]
                if p["process_name"] == "AssignMasterSlaveConstraintsToNeighboursUtility")


def test_the_tie_asks_for_two_neighbours_not_one(contacted):
    """One is what the pairing needs and what Kratos cannot do.

    This asked for 1 on the reasoning that the pairing is already exact -- each slave has
    one true master at zero distance, so a second neighbour could only be an unrelated
    node. Running the deck showed that reasoning to be wrong in a way no amount of
    reading the parameters would have revealed: with a cloud of one node,
    `rbf_shape_functions_utility.cpp` derives its shape parameter from the distance to
    the *nearest other* point in that cloud, the inner loop never runs, the distance
    stays `DBL_MAX`, and the guard throws "Reference distance close to zero". The
    utility needs two points to interpolate between, whether or not the second one adds
    anything.
    """
    assert tie_of(contacted)["minimum_number_of_neighbouring_nodes"] == 2


def test_the_tie_searches_over_a_radius_it_can_reach_a_neighbour_in(contacted):
    """`assign_master_slave_constraints_to_neighbours_utility.cpp` grows the radius in
    steps of `search_radius` until it has enough neighbours. At the 1e-6 this used to
    carry -- chosen to clear floating-point noise and nothing more -- reaching a node a
    few centimetres away takes on the order of 10,000 iterations."""
    assert tie_of(contacted)["search_radius"] == 0.01


def test_a_single_sided_interface_needs_no_tie(session):
    """Soil only exists on one face, so there is nothing on the other to reconnect."""
    export = kratos.export_project(interfaced_project(side="left"),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)
    assert "Wall_contact_Master" not in deck.parts
    assert "Wall_contact_Slave" not in deck.parts

    doc = json.loads(export["project_parameters"])
    initial = (doc["stages"]["1_Initial_stage"]["stage_settings"]["processes"]
              ["constraints_process_list"])
    assert not any(p["process_name"] == "AssignMasterSlaveConstraintsToNeighboursUtility"
                  for p in initial)


def test_a_soil_to_soil_interface_needs_no_tie(session):
    """`structure is None` interfaces are never staged (see
    test_a_soil_to_soil_interface_is_not_staged), so nothing installs later to make a
    tie-back necessary."""
    project = interfaced_project(side="left", structure=None,
                                 points=[[8.0, 0.0], [8.0, -10.0]])
    export = kratos.export_project(project, MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)
    assert not any(name.endswith(("_Master", "_Slave")) for name in deck.parts)


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
        # meet there in one node -- a real deck writes one copy a side fewer than the
        # pile has nodes for exactly this reason.
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
        (x0, z0, _), (x1, z1, _) = deck.nodes[nodes[0]], deck.nodes[nodes[1]]
        normal = (-(z1 - z0), x1 - x0)
        # The soil half's own elements sit on the side the normal points at. Take any
        # soil element holding that node and compare its centre against the line.
        holder = next(n for block in deck.elements
                      if block.name.startswith("SmallStrainUPw")
                      for n in block.entries.values()
                      if set(nodes[half:]) <= set(n))
        centre = [sum(deck.nodes[n][axis] for n in holder[:3]) / 3 for axis in (0, 1)]
        towards = normal[0] * (centre[0] - x0) + normal[1] * (centre[1] - z0)
        assert towards > 0


# ── Where it lands in the deck ──────────────────────────────────────────────

def test_the_interface_gets_its_own_sub_model_parts(contacted):
    deck = deck_of(contacted)
    parts = interface_parts(deck)
    block = interface_block(deck)

    assert {e for part in parts.values() for e in part.elements} == set(block.entries)
    for part in parts.values():
        assert part.nodes == sorted({n for e in part.elements for n in block.entries[e]})
        assert not part.conditions


def test_the_contact_is_split_per_soil_body_it_runs_against(contacted):
    """One part per body, named for it, and every element in exactly one of them.

    A lift is dug away in its own phase and the contact along that lift has to go with
    it -- an interface still holding a face whose soil has been removed would carry
    shear against nothing. The reference deck splits the same way
    (plan/outdated/staged-construction-plan.md sec 0.1).
    """
    deck = deck_of(contacted)
    parts = interface_parts(deck)
    soil = {name for name, part in deck.parts.items()
            if part.elements and name.startswith("Soil")}

    assert len(parts) > 1, "a two-sided contact runs against at least two bodies"
    for name in parts:
        body = name[len("Wall_contact_"):]
        assert body in soil, f"{name} is not named after a soil body"

    owners: dict[int, str] = {}
    for name, part in parts.items():
        for element in part.elements:
            assert element not in owners, f"element {element} is in two contact parts"
            owners[element] = name


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
            (x1, z1, _), (x2, y2, _), (x3, y3, _) = (deck.nodes[n] for n in nodes[:3])
            assert (x2 - x1) * (y3 - z1) - (y2 - z1) * (x3 - x1) > 0


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
    variables = interface_material(contacted)
    entries = [e for e in entries_of(contacted)
               if e["model_part_name"].startswith("PorousDomain.Wall_contact")]

    assert all(e["Material"]["constitutive_law"]["name"] for e in entries)
    assert variables["INTERFACE_NORMAL_STIFFNESS"] > 0
    assert variables["INTERFACE_SHEAR_STIFFNESS"] > 0


def test_the_shear_stiffness_is_the_soils_shear_modulus_over_the_element_size(contacted):
    """`G / t`, with `G = E / 2(1 + nu)` and `t` the element size normal to the contact.

    Verified against `MaterialParameters_for_generated_mesh.json`, whose two interface
    property sets are exactly `G` for its two soils at `t = 1`
    (`tests/test_kratos_units.py`).
    """
    soil = seed_project().materials[0]
    thickness = interfaced_project().interface_sections[0].virtual_thickness
    variables = interface_material(contacted)

    assert variables["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(
        soil.variables["YOUNG_MODULUS"]
        / (2 * (1 + soil.variables["POISSON_RATIO"]) * thickness))


def test_the_normal_stiffness_is_ten_times_the_shear(contacted):
    """A fixed ratio, not a second formula: the reference's two property sets are 10x
    their own shear at two different Poisson ratios (0.2 and 0.3), so nothing about the
    soil's compressibility is in it. It keeps the contact effectively rigid across the
    joint while leaving it free to slip along it."""
    variables = interface_material(contacted)
    assert variables["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(
        10.0 * variables["INTERFACE_SHEAR_STIFFNESS"])


def test_a_contact_takes_the_stiffness_of_each_soil_it_runs_against(session):
    """The reference groups its interfaces by the soil behind them -- one property set
    for the contacts against the clay, another for those against the sand -- because a
    contact's stiffness is a property of the ground it slides on, not of the wall.

    So a section naming no material derives per adjacent body. Which body each contact
    element runs against is already known: the deck writes one part per body
    (`core/kratos.py:_interface_by_body`)."""
    project = interfaced_project(section={"material": None, "virtual_thickness": 1.0})
    export = kratos.export_project(project, MeshRequest(element_size=3.0, order=2))
    variables = [e["Material"]["Variables"] for e in entries_of(export)
                 if e["model_part_name"].startswith("PorousDomain.Wall_contact")]
    shears = {round(v["INTERFACE_SHEAR_STIFFNESS"], 6) for v in variables}

    def shear_of(layer):
        soil = project.material(layer.mat)
        return round(soil.variables["YOUNG_MODULUS"]
                     / (2 * (1 + soil.variables["POISSON_RATIO"])), 6)

    assert shears == {shear_of(layer) for layer in project.layers}
    assert len(shears) == 2, "two layers, two different soils, two stiffnesses"


def test_a_section_that_names_a_material_uses_it_for_the_whole_contact(contacted):
    """The override, and why it stays: a user who has typed an interface material means
    it for that contact, whatever the contact happens to touch."""
    variables = [e["Material"]["Variables"] for e in entries_of(contacted)
                 if e["model_part_name"].startswith("PorousDomain.Wall_contact")]
    assert len({v["INTERFACE_SHEAR_STIFFNESS"] for v in variables}) == 1


def test_an_explicit_stiffness_is_used_as_it_stands(session):
    export = kratos.export_project(
        interfaced_project(section={"normal_stiffness": 1.5e6, "shear_stiffness": 5.0e5}),
        MeshRequest(element_size=3.0, order=2))
    variables = interface_material(export)

    assert variables["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(1.5e6 * KILO)
    assert variables["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(5.0e5 * KILO)
    # Not 10x the shear: an explicit pair is used as it stands, both of them.
    assert variables["INTERFACE_NORMAL_STIFFNESS"] != pytest.approx(
        10.0 * variables["INTERFACE_SHEAR_STIFFNESS"])


def test_the_strength_is_the_soil_s_reduced_by_r_inter(contacted):
    """That is what the factor means: tan(delta) = r_inter * tan(phi), c_i = r_inter * c."""
    import math
    soil = seed_project().materials[0]
    variables = interface_material(contacted)

    assert variables["GEO_COHESION"] == pytest.approx(soil.variables["GEO_COHESION"] * 0.67)
    assert variables["GEO_FRICTION_ANGLE"] == pytest.approx(math.degrees(math.atan(
        math.tan(math.radians(soil.variables["GEO_FRICTION_ANGLE"])) * 0.67)))


def test_the_interface_property_id_is_unique_and_non_zero(contacted):
    ids = [entry["properties_id"] for entry in entries_of(contacted)]
    assert len(set(ids)) == len(ids)
    assert all(i > 0 for i in ids)


# ── Drainage ────────────────────────────────────────────────────────────────

def test_an_interface_says_how_it_drains(contacted):
    """Without it Kratos defaults a material to `FULLY_COUPLED`, with a deprecation
    warning and nothing else to say what went wrong.

    That default is fatal here. A fully coupled element evaluates the poro-elastic
    coupling terms, and a zero-thickness interface carries none of what they need -- no
    `BULK_MODULUS_FLUID`, `BULK_MODULUS_SOLID`, `POROSITY`, `BIOT_COEFFICIENT`,
    `DYNAMIC_VISCOSITY` or permeability. They default to zero, the water-pressure block
    divides zero by zero, and the stage that installs the wall fails to converge on NaN.
    Found by running the deck, not by reading it: the eight warnings are the only sign.
    """
    assert interface_material(contacted)["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"


def test_every_interface_property_set_says_it(contacted):
    """One drawn interface becomes one deck part per soil body it runs against, and the
    warning fires once per property set."""
    entries = [e for e in entries_of(contacted)
               if e["model_part_name"].startswith("PorousDomain.Wall_contact")]
    assert entries
    for entry in entries:
        assert "GEO_DRAINAGE_TYPE" in entry["Material"]["Variables"], \
            entry["model_part_name"]


def test_an_interface_drains_as_a_constant_field_whatever_the_soil_does(session):
    """Not inherited from the adjacent soil, unlike its stiffness and its strength.

    A `FULLY_COUPLED` interface would need the fluid-storage properties an interface
    section does not carry, so the value is fixed by what is written rather than chosen:
    if interfaces ever gain those properties this can follow the soil, and until then
    following it would only reproduce the NaN above for an undrained model.
    """
    project = interfaced_project()
    undrained = project.model_dump()
    for material in undrained["materials"]:
        material["variables"]["GEO_DRAINAGE_TYPE"] = "FULLY_COUPLED"
    export = kratos.export_project(Project.model_validate(undrained),
                                   MeshRequest(element_size=3.0, order=2))
    soils = [e["Material"]["Variables"]["GEO_DRAINAGE_TYPE"] for e in entries_of(export)
             if e["model_part_name"].startswith("PorousDomain.Soil")]
    assert set(soils) == {"FULLY_COUPLED"}, "the soil follows its own drainage type"
    assert interface_material(export)["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
