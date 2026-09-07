"""Kratos .mdpa export: node tables, element blocks, sub-model parts and materials."""

import json
from pathlib import Path

import pytest

from app import build, kratos
from app.schemas import LineLoad, MeshRequest, PointLoad
from app.seed import seed_project
from tests import mdpa

REFERENCE = Path(__file__).resolve().parents[2] / "examples" / "simple_embankment.mdpa"

# Kratos' own node ordering for the quadratic simplices, as (midside index -> corners).
# Asserting the midside node really is the midpoint of that edge is what catches a
# wrong permutation of gmsh's ordering, which differs for the tetrahedron.
MIDSIDES = {
    6: {3: (0, 1), 4: (1, 2), 5: (2, 0)},
    10: {4: (0, 1), 5: (1, 2), 6: (0, 2), 7: (0, 3), 8: (1, 3), 9: (2, 3)},
}


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


@pytest.fixture(scope="module")
def solid(session):
    """The 3D model: quadratic tetrahedra."""
    project = seed_project()
    return kratos.export_project(project, MeshRequest(element_size=6.0, order=2))


@pytest.fixture(scope="module")
def section(session):
    """A plane-strain elevation with its own dimension-native line load."""
    project = seed_project()
    project.dimension = 2
    project.section_plane = "xz"
    project.section_offset = 20.0
    project.loads = [LineLoad(
        id="load_line", name="LineLoad_1", x0=1.0, x1=10.0,
        z=project.domain.z_top, thickness=0.25, components=(0.0, -20.0),
    )]
    return kratos.export_project(project, MeshRequest(element_size=6.0, order=2))


def deck_of(export: dict) -> mdpa.Deck:
    return mdpa.parse(export["mdpa"])


def _load_process(export: dict, part_name: str) -> dict:
    doc = json.loads(export["project_parameters"])
    return next(p["Parameters"] for p in doc["processes"]["loads_process_list"]
                if p["Parameters"]["model_part_name"] == f"PorousDomain.{part_name}")


# ── Shape of the deck ───────────────────────────────────────────────────────

def test_the_solid_model_is_written_as_quadratic_tetrahedra(solid):
    deck = deck_of(solid)
    assert deck.properties[0] == 0
    assert all(property_id > 0 for property_id in deck.properties[1:])
    assert deck.nodes
    assert {block.name for block in deck.elements} == {"SmallStrainUPwDiffOrderElement3D10N"}
    assert all(len(nodes) == 10 for block in deck.elements for nodes in block.entries.values())


def test_the_section_is_written_as_quadratic_triangles(section):
    deck = deck_of(section)
    assert {block.name for block in deck.elements} == {"SmallStrainUPwDiffOrderElement2D6N"}
    assert all(len(nodes) == 6 for block in deck.elements for nodes in block.entries.values())


def test_first_order_writes_linear_elements(session):
    export = kratos.export_project(seed_project(), MeshRequest(element_size=8.0, order=1))
    deck = deck_of(export)
    assert {block.name for block in deck.elements} == {"UPwSmallStrainElement3D4N"}


def test_one_element_block_and_one_sub_model_part_per_soil_layer(solid):
    deck = deck_of(solid)
    # The seeded example is two stacked layers, named in seed.py.
    assert [part for part in deck.parts if part in ("Soil_1", "Soil_2")] == ["Soil_1", "Soil_2"]
    assert len(deck.elements) == 2


# ── Geometric correctness ───────────────────────────────────────────────────

def midside_failures(deck: mdpa.Deck) -> list[tuple[int, int]]:
    bad = []
    for block in deck.elements:
        for element_id, nodes in block.entries.items():
            edges = MIDSIDES.get(len(nodes))
            if edges is None:
                continue
            for index, (first, second) in edges.items():
                a, b = deck.nodes[nodes[first]], deck.nodes[nodes[second]]
                middle = deck.nodes[nodes[index]]
                if any(abs((a[k] + b[k]) / 2 - middle[k]) > 1e-6 for k in range(3)):
                    bad.append((element_id, index))
    return bad


def test_every_midside_node_of_a_tetrahedron_is_its_edge_midpoint(solid):
    """gmsh orders the last two midside nodes of a tet10 the other way round from
    Kratos. Without the permutation the deck parses fine and computes nonsense."""
    assert midside_failures(deck_of(solid)) == []


def test_every_midside_node_of_a_triangle_is_its_edge_midpoint(section):
    assert midside_failures(deck_of(section)) == []


def test_every_tetrahedron_has_positive_volume(solid):
    deck = deck_of(solid)
    for block in deck.elements:
        for element_id, nodes in block.entries.items():
            a, b, c, d = (deck.nodes[n] for n in nodes[:4])
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            w = [d[i] - a[i] for i in range(3)]
            cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                     u[0] * v[1] - u[1] * v[0])
            assert sum(cross[i] * w[i] for i in range(3)) > 0, element_id


def test_every_triangle_is_counter_clockwise(section):
    deck = deck_of(section)
    for block in deck.elements:
        for element_id, nodes in block.entries.items():
            (x1, y1, _), (x2, y2, _), (x3, y3, _) = (deck.nodes[n] for n in nodes[:3])
            assert (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1) > 0, element_id


def test_the_section_is_written_in_the_kratos_xy_plane(section):
    """A section on xz lives at a constant y in the model, but Kratos plane strain
    reads X and Y. The in-plane axes must be remapped, not passed through."""
    deck = deck_of(section)
    assert all(z == 0.0 for _, _, z in deck.nodes.values())
    domain = seed_project().domain
    xs = [x for x, _, _ in deck.nodes.values()]
    ys = [y for _, y, _ in deck.nodes.values()]
    assert min(xs) == pytest.approx(domain.x0) and max(xs) == pytest.approx(domain.x1)
    assert min(ys) == pytest.approx(domain.z_bottom) and max(ys) == pytest.approx(domain.z_top)


# ── Bookkeeping invariants ──────────────────────────────────────────────────

def test_node_ids_are_contiguous_from_one_and_every_node_is_used(solid):
    deck = deck_of(solid)
    assert sorted(deck.nodes) == list(range(1, len(deck.nodes) + 1))
    used = {n for block in deck.elements for nodes in block.entries.values() for n in nodes}
    used |= {n for block in deck.conditions for nodes in block.entries.values() for n in nodes}
    assert used == set(deck.nodes)


def test_elements_and_conditions_share_one_ascending_id_space(section):
    deck = deck_of(section)
    ids = deck.element_ids() + deck.condition_ids()
    assert len(set(ids)) == len(ids)
    assert sorted(ids) == list(range(1, len(ids) + 1))


def test_a_sub_model_part_lists_exactly_the_nodes_of_its_elements(solid):
    """The invariant every part of the GiD reference deck satisfies."""
    deck = deck_of(solid)
    for name, part in deck.parts.items():
        if not part.elements:
            continue
        expected = sorted({n for e in part.elements for n in deck.element(e)})
        assert part.nodes == expected, name
        assert part.elements == sorted(part.elements), name


def test_the_element_count_matches_the_reported_mesh_statistics(solid):
    assert len(deck_of(solid).element_ids()) == solid["stats"]["elements"]


# ── Boundary groups and loads ───────────────────────────────────────────────

def test_boundary_groups_lie_on_their_domain_plane(solid):
    deck = deck_of(solid)
    domain = seed_project().domain
    planes = {"Bottom_Fixed": (2, domain.z_bottom), "Top_Surface": (2, domain.z_top),
              "Left_Edge": (0, domain.x0), "Right_Edge": (0, domain.x1),
              "Front_Edge": (1, domain.y0), "Back_Edge": (1, domain.y1)}
    for name, (axis, value) in planes.items():
        assert name in deck.parts, name
        assert deck.parts[name].nodes
        for node in deck.parts[name].nodes:
            assert deck.nodes[node][axis] == pytest.approx(value), name


def test_the_section_has_no_out_of_plane_boundary_groups(section):
    deck = deck_of(section)
    assert "Front_Edge" not in deck.parts and "Back_Edge" not in deck.parts
    assert deck.parts["Bottom_Fixed"].nodes


def test_boundary_groups_follow_a_drawn_body_that_does_not_fill_the_domain():
    """A drawn soil is not held to the borehole box. Read off `project.domain`, the
    faces it never reaches came out empty and the deck lost `Right_Edge` and
    `Bottom_Fixed` -- the bug this guards."""
    project = seed_project()  # domain x 0..25, z -25..0
    # A 5 x 3 block in the domain's top-left corner, one node per corner.
    world = {1: (0.0, 0.0, 0.0), 2: (5.0, 0.0, 0.0),
             3: (5.0, 0.0, -3.0), 4: (0.0, 0.0, -3.0)}
    node_id = {tag: tag for tag in world}
    boundaries = dict((name, nodes) for name, _, nodes in
                      kratos._boundary_nodes(project, 2, world, node_id, set(world)))
    assert boundaries["Left_Edge"] == [1, 4]
    assert boundaries["Right_Edge"] == [2, 3]
    assert boundaries["Top_Surface"] == [1, 2]
    assert boundaries["Bottom_Fixed"] == [3, 4]


def test_a_structure_standing_proud_of_the_soil_does_not_become_the_top_surface():
    """The faces are measured from the soil body; a sheet pile above ground still joins
    whichever face it touches, but never defines one."""
    project = seed_project()
    world = {1: (0.0, 0.0, 0.0), 2: (5.0, 0.0, 0.0), 3: (5.0, 0.0, -3.0),
             4: (0.0, 0.0, -3.0), 5: (2.0, 0.0, 2.0), 6: (2.0, 0.0, 0.0)}
    node_id = {tag: tag for tag in world}
    boundaries = dict((name, nodes) for name, _, nodes in
                      kratos._boundary_nodes(project, 2, world, node_id, {1, 2, 3, 4}))
    assert boundaries["Top_Surface"] == [1, 2, 6]


def test_the_2d_line_load_becomes_conditions_inside_its_interval(section):
    deck = deck_of(section)
    load = LineLoad(
        id="load_line", name="LineLoad_1", x0=1.0, x1=10.0,
        z=seed_project().domain.z_top, thickness=0.25, components=(0.0, -20.0),
    )
    assert deck.conditions and deck.conditions[0].name == "LineLoadDiffOrderCondition2D3N"
    part = deck.parts["LineLoad_1"]
    assert part.conditions == sorted(deck.condition_ids())
    assert not part.elements
    assert part.nodes == sorted({n for c in part.conditions
                                 for n in deck.conditions[0].entries[c]})
    top = seed_project().domain.z_top
    for nodes in deck.conditions[0].entries.values():
        # The boundary is split at the pad's ends, so a condition is wholly under it.
        corners = [deck.nodes[n] for n in nodes[:2]]
        assert all(load.x0 <= x <= load.x1 for x, _, _ in corners)
        assert all(y == pytest.approx(top) for _, y, _ in (deck.nodes[n] for n in nodes))


def test_load_conditions_keep_property_zero_like_a_gid_deck(section):
    """Every real Kratos GeoMechanics deck in examples/ (crow_case.mdpa,
    dike_with_sheet_pile.mdpa) writes 0 here: the load's magnitude is applied by a
    ProjectParameters.json process against the sub-model part, not read off a
    Properties block, so a condition never gets a property of its own."""
    deck = deck_of(section)
    load_part = deck.parts["LineLoad_1"]
    condition_properties = {
        block.properties[condition_id]
        for block in deck.conditions
        for condition_id in load_part.conditions
    }
    assert condition_properties == {0}
    assert deck.properties == [0]


def test_the_2d_line_load_value_reaches_the_process_file(section):
    """The .mdpa names the part and its conditions; the magnitude is a process against
    that part, which is the only place a Kratos GeoMechanics deck reads it from."""
    assert _load_process(section, "LineLoad_1")["value"] == [0.0, -20.0, 0.0]


def test_line_load_has_no_material_parameters_entry(section):
    """LINE_LOAD is a condition/process value, never a constitutive material -- no
    real Kratos deck defines it in MaterialParameters.json."""
    entries = json.loads(section["materials"])["properties"]
    assert all(entry["model_part_name"] != "PorousDomain.LineLoad_1" for entry in entries)


def test_3d_surface_load_condition_keeps_property_zero(solid):
    deck = deck_of(solid)
    part = deck.parts["SurfaceLoad_1"]
    property_ids = {
        block.properties[condition_id]
        for block in deck.conditions
        for condition_id in part.conditions
    }
    assert property_ids == {0}


def test_the_3d_surface_load_value_reaches_the_process_file(solid):
    assert _load_process(solid, "SurfaceLoad_1")["value"] == [0.0, 0.0, -20.0]


def test_surface_load_has_no_material_parameters_entry(solid):
    entries = json.loads(solid["materials"])["properties"]
    assert all(entry["model_part_name"] != "PorousDomain.SurfaceLoad_1" for entry in entries)


def test_a_2d_point_load_is_exported_as_a_3d_point_condition(session):
    """A point load has no surface form to be translated into (`app/loads.py`), so the
    solid model carries it at the section plane -- and a node is a node in either
    dimension, so the deck can apply it there. It still has no material entry: a load
    is a condition, not a property set."""
    project = seed_project()
    project.loads = [
        PointLoad(
            id="load_crane", name="Crane reaction", kind="point",
            x=5.0, z=0.0, thickness=0.25,
            components=(15.0, -120.0), active=True,
        )
    ]
    exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    deck = deck_of(exported)
    assert "Crane_reaction" in deck.parts
    assert _load_process(exported, "Crane_reaction")["value"] == [15.0, -120.0]
    assert all(item["model_part_name"] != "PorousDomain.Crane_reaction"
               for item in json.loads(exported["materials"])["properties"])


def test_point_load_coordinates_export_in_a_2d_section(session):
    project = seed_project()
    project.dimension = 2
    project.section_plane = "xz"
    project.section_offset = 12.0
    project.loads = [PointLoad(
        id="load_jack", name="Jack", x=5.0, z=-4.0,
        components=(15.0, -120.0),
    )]
    exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    deck = deck_of(exported)

    assert any(block.name == "PointLoadCondition2D1N" for block in deck.conditions)
    assert _load_process(exported, "Jack")["value"] == [15.0, -120.0, 0.0]
    assert all(item["model_part_name"] != "PorousDomain.Jack"
               for item in json.loads(exported["materials"])["properties"])


def test_inactive_load_is_kept_in_the_project_but_not_exported(session):
    project = seed_project()
    project.loads[0].active = False
    exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    deck = deck_of(exported)

    assert deck.conditions == []
    assert "SurfaceLoad_1" not in deck.parts
    assert all(entry["model_part_name"] != "PorousDomain.SurfaceLoad_1"
               for entry in json.loads(exported["materials"])["properties"])


def test_a_saved_3d_surface_load_is_not_exported_in_2d(session):
    project = seed_project()
    project.dimension = 2
    project.section_offset = 20.0
    deck = deck_of(kratos.export_project(project, MeshRequest(element_size=8.0, order=2)))
    assert deck.conditions == []
    assert "SurfaceLoad_1" not in deck.parts


# ── Materials ───────────────────────────────────────────────────────────────

def test_material_parameters_carries_one_entry_per_soil_body(solid):
    materials = json.loads(solid["materials"])["properties"]
    deck = deck_of(solid)
    names = [entry["model_part_name"] for entry in materials
             if "constitutive_law" in entry["Material"]]
    assert names == ["PorousDomain.Soil_1", "PorousDomain.Soil_2"]
    assert all(entry["model_part_name"].split(".", 1)[1] in deck.parts for entry in materials)
    ids = [entry["properties_id"] for entry in materials]
    assert len(set(ids)) == len(ids)


def test_material_variables_come_from_the_project_material(solid):
    entry = json.loads(solid["materials"])["properties"][0]
    project = seed_project()
    material = project.material(project.layers[0].mat)
    variables = entry["Material"]["Variables"]
    assert entry["Material"]["constitutive_law"]["name"]
    assert variables["YOUNG_MODULUS"] == pytest.approx(material.E)
    assert variables["POISSON_RATIO"] == pytest.approx(material.nu)


def test_a_material_without_a_kratos_law_is_reported_not_silently_substituted(solid):
    """Hardening Soil and Soft Soil have no direct Kratos GeoMechanics equivalent
    here; the deck still exports, but the substitution is named in the response."""
    assert any("Hardening Soil" in warning for warning in solid["warnings"])


# ── Parity with the GiD reference deck ──────────────────────────────────────

@pytest.mark.skipif(not REFERENCE.exists(), reason="reference deck is not checked in")
def test_the_reference_deck_parses_to_the_same_grammar_we_write(section):
    reference = mdpa.parse(REFERENCE.read_text())
    ours = deck_of(section)
    assert reference.properties == [0]
    assert ours.properties[0] == 0
    assert {block.name for block in reference.elements} == {
        block.name for block in ours.elements
    }
    for deck in (reference, ours):
        for name, part in deck.parts.items():
            if part.elements:
                assert part.nodes == sorted({n for e in part.elements for n in deck.element(e)})


# ── Load footprint conformance ──────────────────────────────────────────────

def test_2d_line_load_conditions_span_its_interval_exactly(section):
    """The FE boundary is split at the load ends, so no condition straddles an edge."""
    deck = deck_of(section)
    part = deck.parts["LineLoad_1"]
    xs = [deck.nodes[node][0] for node in part.nodes]

    assert min(xs) == pytest.approx(1.0)
    assert max(xs) == pytest.approx(10.0)
    for nodes in deck.conditions[0].entries.values():
        for node in nodes:
            assert 1.0 - 1e-6 <= deck.nodes[node][0] <= 10.0 + 1e-6


def test_2d_load_conditions_are_written_in_their_element_edge_order(section):
    """Kratos matches a 2D condition to its element by exact node-id sequence: its
    NeighbouringElementFinder rotates faces only, and reverse search is off. A condition
    holding the right nodes in any other order has no neighbour element, and the run
    stops in FindNeighbourElementsOfConditionsProcess before the first step."""
    deck = deck_of(section)
    edges = {tuple(nodes[index] for index in order)
             for block in deck.elements if block.name.startswith("SmallStrain")
             for nodes in block.entries.values()
             for order in kratos.EDGES[len(nodes)]}

    rows = [tuple(nodes) for block in deck.conditions
            for nodes in block.entries.values()]
    assert rows
    assert all(row in edges for row in rows)


def test_3d_surface_load_conditions_cover_its_footprint_exactly(solid):
    deck = deck_of(solid)
    part = deck.parts["SurfaceLoad_1"]
    corners = [deck.nodes[node] for node in part.nodes]

    assert min(x for x, _, _ in corners) == pytest.approx(1.0)
    assert max(x for x, _, _ in corners) == pytest.approx(10.0)
    # The seeded pad overhangs the 25 m domain, and the overhang is not boundary.
    assert min(y for _, y, _ in corners) == pytest.approx(14.0)
    assert max(y for _, y, _ in corners) == pytest.approx(seed_project().domain.y1)
    for x, y, _ in corners:
        assert 1.0 - 1e-6 <= x <= 10.0 + 1e-6
        assert 14.0 - 1e-6 <= y <= 26.0 + 1e-6


# ── ProjectParameters.json (partial) ────────────────────────────────────────
#
# solver_settings and problem_data stay empty until the project schema carries a
# solver type, time stepping and linear-solver choice -- see the "Later" plan note.
# The constraints/loads process shapes follow Kratos GeoMechanicsApplication's own
# apply_vector_constraint_table_process / apply_load_by_table_process convention, but
# unlike the .mdpa property-id fix there is no real solver-generated
# ProjectParameters.json in examples/ to check them against yet.

def test_solver_settings_and_problem_data_are_left_empty_for_now(section):
    doc = json.loads(section["project_parameters"])
    assert doc["solver_settings"] == {}
    assert doc["problem_data"] == {}


def test_the_top_surface_is_never_constrained(section):
    """It is the free/loaded surface, not a fixed boundary."""
    doc = json.loads(section["project_parameters"])
    names = [p["Parameters"]["model_part_name"]
             for p in doc["processes"]["constraints_process_list"]]
    assert "PorousDomain.Top_Surface" not in names


def test_the_section_pins_the_bottom_and_rolls_the_sides(section):
    doc = json.loads(section["project_parameters"])
    constraints = {p["Parameters"]["model_part_name"]: p["Parameters"]
                   for p in doc["processes"]["constraints_process_list"]}

    bottom = constraints["PorousDomain.Bottom_Fixed"]
    assert bottom["variable_name"] == "DISPLACEMENT"
    # 2D section on the xz plane: Kratos X = world x, Kratos Y = world z, Z unused.
    assert bottom["is_fixed"] == [True, True, False]
    assert bottom["is_fixed"] == bottom["active"]

    left = constraints["PorousDomain.Left_Edge"]
    assert left["is_fixed"] == [True, False, False], "a roller: only the normal axis"


def test_the_3d_model_pins_the_bottom_and_rolls_all_four_sides(solid):
    doc = json.loads(solid["project_parameters"])
    constraints = {p["Parameters"]["model_part_name"]: p["Parameters"]
                   for p in doc["processes"]["constraints_process_list"]}

    assert constraints["PorousDomain.Bottom_Fixed"]["is_fixed"] == [True, True, True]
    assert constraints["PorousDomain.Left_Edge"]["is_fixed"] == [True, False, False]
    assert constraints["PorousDomain.Right_Edge"]["is_fixed"] == [True, False, False]
    assert constraints["PorousDomain.Front_Edge"]["is_fixed"] == [False, True, False]
    assert constraints["PorousDomain.Back_Edge"]["is_fixed"] == [False, True, False]


def test_the_active_load_becomes_a_load_process(section):
    doc = json.loads(section["project_parameters"])
    loads = {p["Parameters"]["model_part_name"]: p["Parameters"]
             for p in doc["processes"]["loads_process_list"]}

    load = loads["PorousDomain.LineLoad_1"]
    assert load["variable_name"] == "LINE_LOAD"
    assert load["value"] == [0.0, -20.0, 0.0]
    assert load["active"] == [True, True, False]
    assert load["table"] == [0, 0, 0]


def test_the_3d_surface_load_process_is_fully_active(solid):
    doc = json.loads(solid["project_parameters"])
    loads = {p["Parameters"]["model_part_name"]: p["Parameters"]
             for p in doc["processes"]["loads_process_list"]}
    load = loads["PorousDomain.SurfaceLoad_1"]
    assert load["value"] == [0.0, 0.0, -20.0]
    assert load["active"] == [True, True, True]


def test_an_inactive_load_gets_no_process(session):
    project = seed_project()
    project.loads[0].active = False
    exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    doc = json.loads(exported["project_parameters"])
    assert doc["processes"]["loads_process_list"] == []


# ── Sheet piles as beam elements ────────────────────────────────────────────
#
# The classes, their connectivity order and the property id are all taken from the
# reference decks in examples/: dike_with_sheet_pile.mdpa writes the linear beam,
# crow_case.mdpa the quadratic one, and both write property 0 and share every beam
# node with the soil mesh.

BEAM_SECTION = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
                "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}


def piled_project(order: int = 2, active: bool = True, dimension: int = 2):
    payload = seed_project().model_dump()
    payload.update(dimension=dimension, section_plane="xz", section_offset=20.0)
    payload["beam_sections"] = [BEAM_SECTION]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": active}]
    from app.schemas import Project
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def piled(session):
    """A plane-strain section with one quadratic sheet pile."""
    return kratos.export_project(piled_project(), MeshRequest(element_size=3.0, order=2))


def test_the_sheet_pile_is_written_as_the_quadratic_timoshenko_beam(piled):
    deck = deck_of(piled)
    names = {block.name for block in deck.elements}

    assert "LinearTimoshenkoCurvedBeamElement2D3N" in names
    assert "SmallStrainUPwDiffOrderElement2D6N" in names, "the soil is still there"


def test_a_first_order_deck_writes_the_two_node_beam(session):
    export = kratos.export_project(piled_project(order=1),
                                   MeshRequest(element_size=3.0, order=1))
    names = {block.name for block in deck_of(export).elements}

    assert "LinearTimoshenkoCurvedBeamElement2D2N" in names


def test_the_beam_midside_node_is_the_midpoint_of_its_ends(piled):
    """The reference deck's own convention: connectivity is (end, end, midside)."""
    deck = deck_of(piled)
    block = next(b for b in deck.elements if b.name.endswith("Beam" "Element2D3N"))

    for nodes in block.entries.values():
        assert len(nodes) == 3
        first, second, mid = (deck.nodes[n] for n in nodes)
        expected = [(a + b) / 2 for a, b in zip(first, second)]
        assert list(mid) == pytest.approx(expected, abs=1e-6)


def test_beam_elements_keep_property_zero_like_the_reference_decks(piled):
    deck = deck_of(piled)
    block = next(b for b in deck.elements if "Beam" in b.name)

    assert set(block.properties.values()) == {0}


def test_the_sheet_pile_gets_its_own_sub_model_part(piled):
    deck = deck_of(piled)
    part = deck.parts["Sheet_pile_1"]
    block = next(b for b in deck.elements if "Beam" in b.name)

    assert set(part.elements) == set(block.entries)
    assert not part.conditions
    assert part.nodes == sorted({n for e in part.elements for n in block.entries[e]})


def test_every_beam_node_is_a_soil_node_in_the_written_deck(piled):
    """Conformity, asserted on the file rather than on the mesh in memory."""
    deck = deck_of(piled)
    beam = next(b for b in deck.elements if "Beam" in b.name)
    soil = [b for b in deck.elements if "Beam" not in b.name]

    beam_nodes = {n for nodes in beam.entries.values() for n in nodes}
    soil_nodes = {n for b in soil for nodes in b.entries.values() for n in nodes}
    assert beam_nodes <= soil_nodes


def test_the_beam_section_becomes_a_material_entry_mapped_to_its_part(piled):
    entries = json.loads(piled["materials"])["properties"]
    entry = next(e for e in entries
                 if e["model_part_name"] == "PorousDomain.Sheet_pile_1")
    variables = entry["Material"]["Variables"]

    assert entry["Material"]["constitutive_law"]["name"]
    assert variables["YOUNG_MODULUS"] == pytest.approx(2.1e8)
    assert variables["POISSON_RATIO"] == pytest.approx(0.3)
    assert variables["CROSS_AREA"] == pytest.approx(0.0198)
    assert variables["I33"] == pytest.approx(5.52e-4)
    assert variables["DENSITY"] == pytest.approx(7850.0)


def test_the_beam_property_id_is_unique_and_non_zero_in_the_material_file(piled):
    """Property ids live in MaterialParameters.json, which binds them by part name --
    the .mdpa rows stay 0. They still have to be unique across soil and steel."""
    entries = json.loads(piled["materials"])["properties"]
    ids = [entry["properties_id"] for entry in entries]

    assert len(set(ids)) == len(ids)
    assert all(i > 0 for i in ids)


def test_an_inactive_sheet_pile_is_not_exported(session):
    export = kratos.export_project(piled_project(active=False),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)

    assert not any("Beam" in block.name for block in deck.elements)
    assert "Sheet_pile_1" not in deck.parts
    assert all(e["model_part_name"] != "PorousDomain.Sheet_pile_1"
               for e in json.loads(export["materials"])["properties"])


def test_a_sheet_pile_saved_in_a_3d_project_is_not_exported(session):
    export = kratos.export_project(piled_project(dimension=3),
                                   MeshRequest(element_size=6.0, order=2))

    assert not any("Beam" in block.name for block in deck_of(export).elements)


# ── Anchors as two-node ties ────────────────────────────────────────────────
#
# examples/crow_case.mdpa is the whole specification: one LinearTrussElement2D2N with
# property 0, its head node shared with the beam (it sits in two beam elements there),
# its tail node in no element at all and alone in a one-node support group.

TENDON = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
          "density": 7850.0, "spacing": 2.5, "tension_limit": 900.0,
          "compression_limit": None}


def anchored_project(order: int = 2, active: bool = True, dimension: int = 2):
    from app.schemas import Project
    payload = piled_project(dimension=dimension).model_dump()
    payload["anchor_sections"] = [TENDON]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": [12.0, -2.0],
                           "tail": [20.0, -8.0], "prestress": 250.0, "active": active}]
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def anchored(session):
    return kratos.export_project(anchored_project(), MeshRequest(element_size=3.0, order=2))


def truss_of(deck):
    return next(b for b in deck.elements if b.name == "LinearTrussElement2D2N")


def test_the_anchor_is_written_as_a_single_two_node_truss(anchored):
    """Linear even in a quadratic deck, exactly as the reference has it beside its
    three-node beams."""
    deck = deck_of(anchored)
    block = truss_of(deck)

    assert len(block.entries) == 1
    assert all(len(nodes) == 2 for nodes in block.entries.values())
    assert set(block.properties.values()) == {0}


def test_the_truss_runs_from_the_head_to_the_tail_the_user_drew(anchored):
    deck = deck_of(anchored)
    head, tail = (deck.nodes[n] for n in next(iter(truss_of(deck).entries.values())))

    assert (head[0], head[1]) == pytest.approx((12.0, -2.0), abs=1e-6)
    assert (tail[0], tail[1]) == pytest.approx((20.0, -8.0), abs=1e-6)


def test_the_anchor_head_node_is_the_pile_node(anchored):
    """Shared, not merely coincident: the tie and the beam must be one structure."""
    deck = deck_of(anchored)
    head = next(iter(truss_of(deck).entries.values()))[0]
    beam = next(b for b in deck.elements if "Beam" in b.name)

    assert head in {n for nodes in beam.entries.values() for n in nodes}


def test_the_anchor_tail_node_is_attached_to_nothing_else(anchored):
    deck = deck_of(anchored)
    tail = next(iter(truss_of(deck).entries.values()))[1]
    others = {n for block in deck.elements if block.name != "LinearTrussElement2D2N"
              for nodes in block.entries.values() for n in nodes}

    assert tail not in others


def test_the_anchor_gets_its_own_part_and_a_support_group_for_its_tail(anchored):
    deck = deck_of(anchored)
    block = truss_of(deck)
    part = deck.parts["Anchor_1"]
    support = deck.parts["Anchor_1_Support"]
    head, tail = next(iter(block.entries.values()))

    assert set(part.elements) == set(block.entries)
    assert part.nodes == sorted([head, tail])
    assert support.nodes == [tail], "the far end is held by a boundary condition"
    assert not support.elements and not support.conditions


def test_the_tail_support_is_fixed_in_the_process_file(anchored):
    doc = json.loads(anchored["project_parameters"])
    constraints = {p["Parameters"]["model_part_name"]: p["Parameters"]
                   for p in doc["processes"]["constraints_process_list"]}

    assert constraints["PorousDomain.Anchor_1_Support"]["is_fixed"] == [True, True, False]


def test_the_tendon_becomes_a_material_entry_with_its_prestress(anchored):
    entries = json.loads(anchored["materials"])["properties"]
    entry = next(e for e in entries if e["model_part_name"] == "PorousDomain.Anchor_1")
    variables = entry["Material"]["Variables"]

    assert entry["Material"]["constitutive_law"]["name"]
    assert variables["YOUNG_MODULUS"] == pytest.approx(1.95e8)
    # Per metre run: a tendon every 2.5 m carries 1/2.5 of its steel in plane strain.
    assert variables["CROSS_AREA"] == pytest.approx(0.0006 / 2.5)
    assert variables["TRUSS_PRESTRESS_PK2"] == pytest.approx(250.0 / 2.5)


def test_every_material_property_id_stays_unique_with_soil_pile_and_anchor(anchored):
    entries = json.loads(anchored["materials"])["properties"]
    ids = [e["properties_id"] for e in entries]

    assert len(set(ids)) == len(ids) and all(i > 0 for i in ids)
    assert len(entries) >= 4, "two soil layers, a sheet pile and an anchor"


def test_an_inactive_anchor_is_not_exported(session):
    export = kratos.export_project(anchored_project(active=False),
                                   MeshRequest(element_size=3.0, order=2))
    deck = deck_of(export)

    assert not any(b.name == "LinearTrussElement2D2N" for b in deck.elements)
    assert "Anchor_1" not in deck.parts and "Anchor_1_Support" not in deck.parts


def test_an_anchor_saved_in_a_3d_project_is_not_exported(session):
    export = kratos.export_project(anchored_project(dimension=3),
                                   MeshRequest(element_size=6.0, order=2))

    assert not any(b.name == "LinearTrussElement2D2N" for b in deck_of(export).elements)
