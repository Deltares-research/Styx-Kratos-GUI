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

from core.geometry import solid_model
from core.kratos import interfaces, writer
KILO = 1000.0  # kN -> N: these tests write old-style projects, converted on load (core/model/migration.py)
from core.model.schemas import MeshRequest, Project
from core.model.templates import seed_project
from tests import mdpa
from tests.pipeline.deck_invariants import check_deck
from tests.models import drawn_ground
from tests.test_kratos import BEAM_SECTION, deck_of

SECTION = {"id": "steel_soil", "name": "Steel against sand", "material": "mat_sand",
           "r_inter": 0.67, "virtual_thickness": 0.01}


@pytest.fixture(scope="module")
def session():
    with solid_model.session():
        yield


def interfaced_project(side: str = "both", active: bool = True, dimension: int = 2,
                       structure: str | None = "sheetpile_1", points=None,
                       section: dict | None = None, stretch=None,
                       more: list[dict] | None = None) -> Project:
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
                              "points": points, "side": side, "stretch": stretch,
                              "active": active}] + [
        {"section": SECTION["id"], "structure": "sheetpile_1", "points": None,
         "active": True, **record} for record in more or []]
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def contacted(session):
    """A quadratic section: one sheet pile with soil unglued from both its faces."""
    return writer.export_project(interfaced_project(), MeshRequest(element_size=3.0, order=2))


def interface_block(deck: mdpa.Deck) -> mdpa.Block:
    """Every contact element in the deck, as one block.

    The deck writes one block per soil body the contact runs against, so a lift can be
    deactivated together with the interface along it (`writer._interface_by_body`).
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
            if name.startswith("Wall_contact")
            and not name.endswith(("_Master", "_Slave", "_face"))}


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
    export = writer.export_project(interfaced_project(),
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
    export = writer.export_project(project, MeshRequest(element_size=3.0, order=2))
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


def test_a_one_side_interface_ties_its_copies_to_the_soil_on_the_other_face(session):
    """Before the pile is installed the contact's copies would hang free beside soil
    that is still on the pile's own nodes. Each copy is tied to that original, the copy
    on the left of the screen being the master, as the Kratos-side tool ties a one-side
    contact."""
    for side in ("left", "right"):
        export = writer.export_project(interfaced_project(side=side),
                                       MeshRequest(element_size=3.0, order=2))
        deck = deck_of(export)
        master, slave = deck.parts["Wall_contact_Master"], deck.parts["Wall_contact_Slave"]

        copies = {n for nodes in interface_block(deck).entries.values()
                  for n in nodes[len(nodes) // 2:]}
        assert set(master.nodes if side == "left" else slave.nodes) == copies
        assert {deck.nodes[n] for n in master.nodes} == {deck.nodes[n] for n in slave.nodes}
        sides = soil_side_of_ties(deck, 12.0)
        assert sides == {"Wall_contact_Master": {"-x"}, "Wall_contact_Slave": {"+x"}}, side
        assert tie_of(export)["master_model_part_name"] == "PorousDomain.Wall_contact_Master"


def test_a_soil_to_soil_interface_needs_no_tie(session):
    """`structure is None` interfaces are never staged (see
    test_a_soil_to_soil_interface_is_not_staged), so nothing installs later to make a
    tie-back necessary."""
    project = interfaced_project(side="left", structure=None,
                                 points=[[8.0, 0.0], [8.0, -10.0]])
    export = writer.export_project(project, MeshRequest(element_size=3.0, order=2))
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

    A lift is dug away in its own stage and the contact along that lift has to go with
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
    export = writer.export_project(interfaced_project(side="left"),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)

    assert beam_nodes(deck) & soil_nodes(deck), "the bonded face still shares its nodes"
    copies = {n for nodes in interface_block(deck).entries.values() for n in nodes[3:]}
    assert soil_side_of(deck, copies, 12.0) == {"-x"}, \
        "left is the face toward -x, though the pile was drawn from the top down"
    block = interface_block(deck)
    per_segment: dict[frozenset[int], int] = {}
    for nodes in block.entries.values():
        per_segment[frozenset(nodes[:3])] = per_segment.get(frozenset(nodes[:3]), 0) + 1
    assert set(per_segment.values()) == {1}


def test_an_inactive_interface_is_kept_in_the_project_but_not_exported(session):
    export = writer.export_project(interfaced_project(active=False),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)

    assert not any("Interface" in block.name for block in deck.elements)
    assert "Wall_contact" not in deck.parts
    assert beam_nodes(deck) & soil_nodes(deck), "the pile is bonded again"


def test_an_interface_on_a_switched_off_pile_is_not_exported(session):
    project = interfaced_project()
    project.beams[0].active = False
    export = writer.export_project(project, MeshRequest(element_size=3.0, order=2))

    assert not any("Interface" in block.name for block in deck_of(export).elements)


def test_a_free_interface_splits_soil_from_soil(session):
    """No structure in the middle: one side keeps the original nodes, the other is
    detached, and the contact holds the two soils together."""
    project = interfaced_project(side="left", structure=None,
                                 points=[[8.0, 0.0], [8.0, -10.0]])
    export = writer.export_project(project, MeshRequest(element_size=3.0, order=2))
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
    export = writer.export_project(project, MeshRequest(element_size=3.0, order=2))
    block = interface_block(deck_of(export))

    tips = [nodes for nodes in block.entries.values() if len(set(nodes)) < len(nodes)]
    assert len(tips) == 1


def test_a_3d_project_writes_no_interface_and_says_so(session):
    export = writer.export_project(interfaced_project(dimension=3),
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
    (`core/kratos/writer.py:_interface_by_body`)."""
    project = interfaced_project(section={"material": None, "virtual_thickness": 1.0})
    export = writer.export_project(project, MeshRequest(element_size=3.0, order=2))
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
    export = writer.export_project(
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
    export = writer.export_project(Project.model_validate(undrained),
                                   MeshRequest(element_size=3.0, order=2))
    soils = [e["Material"]["Variables"]["GEO_DRAINAGE_TYPE"] for e in entries_of(export)
             if e["model_part_name"].startswith("PorousDomain.Soil")]
    assert set(soils) == {"FULLY_COUPLED"}, "the soil follows its own drainage type"
    assert interface_material(export)["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"


# ── Drawn soil ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def drawn():
    """A sheet pile through a soil layer and through two drawn fills on top of it,
    one each side (`tests/models/drawn_ground.py`). Built before the module's gmsh
    session: drawing the fills runs gmsh too."""
    project = drawn_ground.project()
    with solid_model.session():
        return project, writer.export_project(project)


def segments_of(deck: mdpa.Deck) -> list[tuple[int, ...]]:
    return [tuple(nodes) for block in deck.elements if "Timoshenko" in block.name
            for nodes in block.entries.values()]


def test_a_contact_holds_drawn_soil_as_well_as_the_soil_layer(drawn):
    """Two contact elements on every pile segment, one per face, also where the pile
    runs through the drawn fill. Grouped by the `soil_` key prefix, only the soil
    layer's stretch had any, and the fill above it was split from the wall and held by
    nothing once the wall was installed."""
    _, export = drawn
    deck = deck_of(export)
    contacts = interface_block(deck)
    on_segment: dict[frozenset[int], int] = {}
    for nodes in contacts.entries.values():
        key = frozenset(nodes[:2])
        on_segment[key] = on_segment.get(key, 0) + 1
    segments = segments_of(deck)
    assert len(segments) == 4
    assert {frozenset(s[:2]): on_segment.get(frozenset(s[:2]), 0) for s in segments} == \
        {frozenset(s[:2]): 2 for s in segments}


def test_each_drawn_part_gets_its_own_contact_part(drawn):
    _, export = drawn
    assert set(interface_parts(deck_of(export))) == {
        "Wall_contact_Ground", "Wall_contact_Fill_left", "Wall_contact_Fill_right"}


def test_a_contact_against_a_drawn_part_takes_that_part_s_soil(drawn):
    project, export = drawn
    variables = {e["model_part_name"]: e["Material"]["Variables"]
                 for e in entries_of(export)
                 if e["model_part_name"].startswith("PorousDomain.Wall_contact")}
    section = project.interface_sections[0]

    def shear_of(material_id):
        soil = project.material(material_id).variables
        return soil["YOUNG_MODULUS"] / (2 * (1 + soil["POISSON_RATIO"])
                                        * section.virtual_thickness)

    for part, material in (("Ground", "m_ground"), ("Fill_left", "m_fill"),
                           ("Fill_right", "m_fill")):
        got = variables[f"PorousDomain.Wall_contact_{part}"]
        assert got["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(shear_of(material)), part
        cohesion = project.material(material).variables["GEO_COHESION"]
        assert got["GEO_COHESION"] == pytest.approx(section.r_inter * cohesion), part


def test_the_contact_along_a_dug_part_goes_with_it(drawn):
    """The trench is the right-hand fill: from the stage that digs it, its contact is
    out of the computation and the left-hand one is still in."""
    _, export = drawn
    doc = json.loads(export["project_parameters"])
    domains = {name: set(stage["stage_settings"]["solver_settings"]
                         ["problem_domain_sub_model_part_list"])
               for name, stage in doc["stages"].items()}
    install, dig = domains["2_Install_wall"], domains["3_Dig_trench"]
    assert {"Wall_contact_Fill_left", "Wall_contact_Fill_right"} <= install
    assert "Wall_contact_Fill_left" in dig and "Wall_contact_Fill_right" not in dig


def test_a_contact_element_no_soil_body_takes_is_refused():
    """The guard behind the bug above: a contact element is only written where there is
    soil on that face, so one that no body takes is an export error, not a silent gap."""
    interface = Project.model_validate(interfaced_project().model_dump()).interfaces[0]
    held, lost = [1, 2, 3, 11, 12, 13], [2, 4, 5, 12, 14, 15]
    coordinates = {n: (0.0, -float(n % 10), 0.0) for n in held + lost}
    with pytest.raises(writer.ExportError, match=r"Wall contact.*y = -5 and -2"):
        writer._check_every_stretch_is_held(interface, [held, lost],
                                            [("soil_a", [held])], 3, coordinates)


# ── A part of a pile, and two interfaces on one pile ────────────────────────

FROM_TO = ((12.0, -3.0), (12.0, -9.0))


def pile_ys(deck: mdpa.Deck, block: mdpa.Block) -> list[float]:
    return sorted({deck.nodes[n][1] for nodes in block.entries.values()
                   for n in nodes[:len(nodes) // 2]})


@pytest.fixture(scope="module")
def part_of_a_pile(session):
    return writer.export_project(interfaced_project(stretch=FROM_TO),
                                 MeshRequest(element_size=3.0, order=2))


def test_an_interface_on_a_part_of_a_pile_holds_only_that_part(part_of_a_pile):
    deck = deck_of(part_of_a_pile)
    ys = pile_ys(deck, interface_block(deck))

    assert (ys[0], ys[-1]) == (-9.0, -3.0), "the mesh has a node at From and at To"
    per_segment: dict[frozenset[int], int] = {}
    for nodes in interface_block(deck).entries.values():
        per_segment[frozenset(nodes[:3])] = per_segment.get(frozenset(nodes[:3]), 0) + 1
    assert set(per_segment.values()) == {2}, "both faces, on every segment of the part"


def test_where_the_pile_goes_on_past_the_part_the_soil_stays_welded_to_it(part_of_a_pile):
    """At From and To the pile goes on. The soil past the end keeps the pile's
    own node; the soil the contact holds has a copy per face there, as along the line."""
    deck = deck_of(part_of_a_pile)
    piles, soils = beam_nodes(deck), soil_nodes(deck)
    for end in FROM_TO:
        here = {n for n in deck.nodes if deck.nodes[n][:2] == end}
        (pile,) = here & piles
        assert pile in soils, "the soil past the end is on the pile's node"
        assert len(here - {pile}) == 2, "one copy per face for the soil that is held"
        held = {n for nodes in interface_block(deck).entries.values()
                for n in nodes[len(nodes) // 2:]}
        assert here - {pile} <= held


def test_the_ties_cover_the_part_of_the_pile_only(part_of_a_pile):
    deck = deck_of(part_of_a_pile)
    tied = deck.parts["Wall_contact_Master"].nodes + deck.parts["Wall_contact_Slave"].nodes
    ys = {deck.nodes[n][1] for n in tied}
    assert (min(ys), max(ys)) == (-9.0, -3.0)


def test_the_faces_of_a_part_of_a_pile_are_curves_over_that_part(session):
    project = drawn_ground.project()
    contact = project.interfaces[0].model_copy(update={
        "stretch": ((drawn_ground.WALL_X, -6.0), (drawn_ground.WALL_X, -1.0))})
    project = project.model_copy(update={"interfaces": [contact]})
    deck = deck_of(writer.export_project(project))

    for face in ("Left", "Right"):
        ys = {deck.nodes[n][1] for n in deck.parts[f"Wall_contact_{face}_face"].nodes}
        assert (min(ys), max(ys)) == (-6.0, -1.0), face


def test_two_interfaces_on_the_two_faces_of_one_pile(session):
    project = interfaced_project(side="left", more=[
        {"id": "interface_2", "name": "Back", "side": "right"}])
    deck = deck_of(writer.export_project(project, MeshRequest(element_size=3.0, order=2)))

    block = interface_block(deck)
    by_interface: dict[str, set[int]] = {}
    for name, part in deck.parts.items():
        if part.elements and set(part.elements) <= set(block.entries):
            by_interface.setdefault(name.partition("_")[0], set()).update(part.elements)
    assert set(by_interface) == {"Wall", "Back"}
    assert not by_interface["Wall"] & by_interface["Back"]
    copies = {stem: {n for e in elements for n in block.entries[e][3:]}
              for stem, elements in by_interface.items()}
    assert soil_side_of(deck, copies["Wall"], 12.0) == {"-x"}
    assert soil_side_of(deck, copies["Back"], 12.0) == {"+x"}
    assert not beam_nodes(deck) & soil_nodes(deck) - {
        n for n in beam_nodes(deck) if deck.nodes[n][1] > -1e-9}, \
        "both faces are detached along the pile"

    slaves = [n for name, part in deck.parts.items() if name.endswith("_Slave")
              for n in part.nodes]
    assert slaves and len(slaves) == len(set(slaves)), "each pair is tied once"


def soil_side_of(deck: mdpa.Deck, nodes: set[int], wall_x: float) -> set[str]:
    """The sides of the wall ("-x", "+x") of the soil elements that use `nodes`."""
    out = set()
    for block in deck.elements:
        if not block.name.startswith("SmallStrainUPw"):
            continue
        for element in block.entries.values():
            if set(element) & nodes:
                x = sum(deck.nodes[n][0] for n in element[:3]) / 3
                out.add("-x" if x < wall_x else "+x")
    return out


# ── Which face holds the masters ────────────────────────────────────────────

def soil_side_of_ties(deck: mdpa.Deck, wall_x: float) -> dict[str, set[str]]:
    """Tie part -> the sides of the wall ("-x", "+x") its nodes' soil elements are on."""
    centroids: dict[int, list[float]] = {}
    for block in deck.elements:
        if not block.name.startswith("SmallStrainUPw"):
            continue
        for nodes in block.entries.values():
            x = sum(deck.nodes[n][0] for n in nodes[:3]) / 3
            for node in nodes:
                centroids.setdefault(node, []).append(x)
    return {name: {"-x" if x < wall_x else "+x"
                   for node in deck.parts[name].nodes for x in centroids[node]}
            for name in deck.parts if name.endswith(("_Master", "_Slave"))}


def test_every_master_is_on_the_left_face_of_a_pile_drawn_up(drawn):
    """Kratos' own master/slave test ties the left body to the right one; the masters
    here follow it. Taking the lower node id put them on whichever face gmsh numbered
    first, so they changed sides along the wall."""
    _, export = drawn
    sides = soil_side_of_ties(deck_of(export), drawn_ground.WALL_X)
    assert sides == {"Wall_contact_Master": {"-x"}, "Wall_contact_Slave": {"+x"}}


def test_every_master_is_on_the_left_face_of_a_pile_drawn_down(contacted):
    """The fixture's pile runs from its head down to its toe, so its own left face is
    the +x one; the masters still go on the left of the screen."""
    sides = soil_side_of_ties(deck_of(contacted), 12.0)
    assert sides == {"Wall_contact_Master": {"-x"}, "Wall_contact_Slave": {"+x"}}


@pytest.mark.parametrize("path, face", [
    ([(0, -8), (0, 3)], "left"),       # up: its left is -x
    ([(0, 3), (0, -8)], "right"),      # down: its right is -x
    ([(0, 0), (10, 1)], "right"),      # flat, towards +x: its right is below
    ([(10, 1), (0, 0)], "left"),       # flat, towards -x: its left is below
])
def test_the_master_face_is_the_left_of_the_screen_or_the_one_below(path, face):
    assert writer._master_face(path) == face


# ── A curve per face ────────────────────────────────────────────────────────

def test_without_a_pit_each_face_of_the_wall_gets_a_curve_of_its_own(drawn):
    """A pile through a dike holds ground on both faces, and the retained-side group of
    a pit model then held both faces' copies of the soil layer and nothing of the
    drawn fill: one curve zig-zagging between two faces, stopping where the fill
    began. Each face is a group of its own now, over every body, read by a json output
    of its own -- `results profile RUN interface_left tn`."""
    _, export = drawn
    deck = deck_of(export)
    centroids: dict[int, list[float]] = {}
    for block in deck.elements:
        if block.name.startswith("SmallStrainUPw"):
            for nodes in block.entries.values():
                x = sum(deck.nodes[n][0] for n in nodes[:3]) / 3
                for node in nodes:
                    centroids.setdefault(node, []).append(x)
    left = set(deck.parts["Wall_contact_Left_face"].nodes)
    right = set(deck.parts["Wall_contact_Right_face"].nodes)
    toe = left & right
    assert len(toe) == 1, "the toe's one copy is on both faces"
    assert all(x < drawn_ground.WALL_X for n in left - toe for x in centroids[n])
    assert all(x > drawn_ground.WALL_X for n in right - toe for x in centroids[n])
    for nodes in (left, right):
        assert max(deck.nodes[n][1] for n in nodes) == 0.0, "up through the drawn fill"
    assert writer.RIGHT_SIDE_PART not in deck.parts

    doc = json.loads(export["project_parameters"])
    written = [p["Parameters"]["output_file_name"]
               for p in doc["stages"]["3_Dig_trench"]["stage_settings"]["processes"]
               ["json_output"]]
    assert written == ["3_Dig_trench__output_wall.json",
                       "3_Dig_trench__output_interface_left.json",
                       "3_Dig_trench__output_interface_right.json"]


@pytest.fixture(scope="module")
def standing():
    """The drawn-ground pile standing 1 m out of the fill (`standing_pile_project`)."""
    project = drawn_ground.standing_pile_project()
    with solid_model.session():
        return project, writer.export_project(project)


def test_a_pile_keeps_the_piece_that_stands_out_of_the_ground(standing):
    """A dike's sheet pile stands above the crest, and that piece was cut off at the
    ground: the deck's pile ended there, and a load at its head had no pile to act on.
    The piece is kept, and its nodes are the pile's alone."""
    _, export = standing
    deck = deck_of(export)
    pile = beam_nodes(deck)
    head = [n for n in pile if deck.nodes[n][1] > 0.0]
    assert max(deck.nodes[n][1] for n in pile) == pytest.approx(drawn_ground.PILE_HEAD_Y)
    assert head and not set(head) & soil_nodes(deck)
    assert check_deck(export) == []


def test_the_contact_stops_where_the_ground_does(standing, drawn):
    """No soil lies against the piece above the ground, so no contact element is
    written there: the contact is the one of the same pile ending at the ground."""
    def contacts(export: dict) -> list[list[int]]:
        deck = deck_of(export)
        return [[deck.nodes[n][1] for n in nodes] for block in deck.elements
                if "Interface" in block.name for nodes in block.entries.values()]

    standing_out, flush = contacts(standing[1]), contacts(drawn[1])
    assert standing_out and max(y for ys in standing_out for y in ys) == 0.0
    assert len(standing_out) == len(flush)


def test_interface_export_refuses_a_contact_without_mesh(session):
    # Drawn 2 m above the ground: no soil around it, so the build clips all of it away.
    project = interfaced_project(side="left", structure=None,
                                 points=[[2.0, 2.0], [10.0, 2.0]])

    with pytest.raises(writer.ExportError, match="Wall contact.*no mesh along its line"):
        writer.export_project(project, MeshRequest(element_size=3.0, order=1))


def test_interface_export_translates_topology_failures(monkeypatch):
    project = interfaced_project(side="left", structure=None, points=[[0, 0], [1, 0]])
    monkeypatch.setattr(writer, "_tagged", lambda _: {"interface_1": [10]})
    monkeypatch.setattr(writer, "_segments", lambda _: [[1, 2]])

    def broken_split(*_args):
        raise interfaces.InterfaceError("contact crosses an unsupported junction")

    monkeypatch.setattr(interfaces, "split_mesh", broken_split)

    with pytest.raises(writer.ExportError, match="contact crosses an unsupported junction"):
        writer._interface_elements(project, 2, [], [], [], {}, {}, [])


def test_contact_grouping_excludes_structures_and_faces_with_no_common_soil_owner():
    held = [1, 2, 4, 5]
    unheld = [1, 2, 5, 6]
    blocks = [
        ("wall", "Beam", [[4, 5, 6]]),
        ("soil_a", "Triangle", [[4, 5, 7]]),
        ("soil_b", "Triangle", [[6, 8, 9]]),
    ]

    assert writer._interface_by_body(
        [held, unheld], 2, blocks, frozenset({"soil_a", "soil_b"})) == [
            ("soil_a", [held]),
        ]


def test_a_condition_without_an_owning_soil_element_is_not_relocated():
    rows = [[1, 9]]
    split = interfaces.Split(duplicates={4: 1}, renamed=[{1: 4}])

    writer._follow_the_soil([("load", "LineLoad", rows)], [[1, 2, 3]], split)

    assert rows == [[1, 9]]
