"""Turning a stage's mesh into something that can be drawn and coloured.

The buffers here are the same shape `core.kratos.mdpa_reader.to_sections` already produces for
an imported deck -- positions, indices, edges, and `node_ids` giving the deck's own node
number per vertex -- because the viewport has a path for those and a second one would be
a second thing to keep working.

The one real difference, and the reason this module exists at all, is **quadratic
subdivision**. The soil elements this project exports are six-node triangles. Drawn as
one flat triangle through the corners, a contour across them is piecewise linear on the
wrong mesh: the mid-side nodes carry their own values and those values simply do not
appear. Splitting each element into four sub-triangles puts every node the solver
actually used onto the screen.
"""

import textwrap

import pytest

from core.kratos import mdpa_reader
from core.results import gid_reader, mesh


def dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


MDPA = dedent("""
    Begin Properties 0
    End Properties

    Begin Nodes
    1 0.0 0.0 0.0
    2 2.0 0.0 0.0
    3 0.0 2.0 0.0
    4 1.0 0.0 0.0
    5 1.0 1.0 0.0
    6 0.0 1.0 0.0
    7 4.0 0.0 0.0
    8 3.0 0.0 0.0
    End Nodes

    Begin Elements SmallStrainUPwDiffOrderElement2D6N
    1 1 1 2 3 4 5 6
    End Elements

    Begin Elements LinearTimoshenkoCurvedBeamElement2D3N
    2 2 2 7 8
    End Elements

    Begin SubModelPart Soil_Top
        Begin SubModelPartElements
        1
        End SubModelPartElements
    End SubModelPart

    Begin SubModelPart SheetPileWall
        Begin SubModelPartElements
        2
        End SubModelPartElements
    End SubModelPart
    """)

MSH = dedent("""
    MESH "Kratos_Triangle2D6_Mesh_1" dimension 2 ElemType Triangle Nnode 6
    Coordinates
    1 0 0 0
    2 2 0 0
    3 0 2 0
    4 1 0 0
    5 1 1 0
    6 0 1 0
    7 4 0 0
    8 3 0 0
    End Coordinates
    Elements
    1 1 2 3 4 5 6 1
    End Elements
    MESH "Kratos_Line2D3_Mesh_2" dimension 2 ElemType Linear Nnode 3
    Elements
    2 2 7 8 2
    End Elements
    """)


@pytest.fixture
def stage():
    return (mdpa_reader.import_mdpa(MDPA), gid_reader.read_mesh(MSH))


def section_of(payload, name):
    return next(s for s in payload["sections"] if s["part"] == name)


# ── Subdivision ─────────────────────────────────────────────────────────────

def test_a_six_node_triangle_becomes_four_drawable_triangles(stage):
    """Not one. A contour drawn over a single flat triangle through the corners
    discards the three mid-side values the solver computed, which on a quadratic mesh
    is half the information in the field."""
    payload = mesh.stage_sections(*stage)

    soil = section_of(payload, "Soil_Top")
    assert len(soil["indices"]) == 4 * 3


def test_the_sub_triangles_are_the_four_a_quadratic_triangle_splits_into(stage):
    """Corners 1,2,3 and mid-sides 4=(1,2), 5=(2,3), 6=(3,1). The three corner
    triangles and the middle one. Asserted in the deck's own node numbers so the
    expectation does not depend on how the vertices happen to be ordered."""
    payload = mesh.stage_sections(*stage)
    soil = section_of(payload, "Soil_Top")

    ids = soil["node_ids"]
    triangles = {frozenset(ids[i] for i in soil["indices"][n:n + 3])
                 for n in range(0, len(soil["indices"]), 3)}

    assert triangles == {
        frozenset({1, 4, 6}), frozenset({4, 2, 5}),
        frozenset({6, 5, 3}), frozenset({4, 5, 6}),
    }


def test_a_linear_triangle_stays_one_triangle():
    mdpa = MDPA.replace("SmallStrainUPwDiffOrderElement2D6N", "UPwSmallStrainElement2D3N")
    mdpa = mdpa.replace("1 1 1 2 3 4 5 6", "1 1 1 2 3")
    msh = MSH.replace("ElemType Triangle Nnode 6", "ElemType Triangle Nnode 3")
    msh = msh.replace("1 1 2 3 4 5 6 1", "1 1 2 3 1")

    payload = mesh.stage_sections(mdpa_reader.import_mdpa(mdpa),
                                         gid_reader.read_mesh(msh))

    assert len(section_of(payload, "Soil_Top")["indices"]) == 3


def test_every_node_of_a_quadratic_element_reaches_the_buffer(stage):
    """The point of the whole exercise: all six nodes are drawable, so all six values
    can be coloured."""
    payload = mesh.stage_sections(*stage)

    assert set(section_of(payload, "Soil_Top")["node_ids"]) == {1, 2, 3, 4, 5, 6}


# ── Line elements ───────────────────────────────────────────────────────────

def test_a_quadratic_beam_is_drawn_through_its_midside_node(stage):
    """Two segments, end-to-middle and middle-to-end, rather than one straight line
    from end to end. On an undeformed mesh the two look the same; on a deformed one the
    single segment draws a bending wall as a straight stick."""
    payload = mesh.stage_sections(*stage)

    wall = section_of(payload, "SheetPileWall")
    assert wall["indices"] == []
    assert len(wall["edges"]) == 2 * 2 * 3, "two segments, two ends, three coordinates"
    assert set(wall["node_ids"]) == {2, 7, 8}


def test_line_work_carries_vertex_indices_as_well_as_coordinates(stage):
    """A result's line work has to take a vertex colour and shift with the deformation
    factor, and raw coordinates have lost which node they came from. The coordinates
    stay beside them so nothing that already reads a section breaks."""
    payload = mesh.stage_sections(*stage)
    wall = section_of(payload, "SheetPileWall")

    ids = wall["node_ids"]
    segments = [tuple(ids[i] for i in wall["edge_indices"][n:n + 2])
                for n in range(0, len(wall["edge_indices"]), 2)]

    # (end, end, middle) in Kratos' ordering, so the two segments are 2-8 and 8-7.
    assert segments == [(2, 8), (8, 7)]
    assert all(0 <= i < len(ids) for i in wall["edge_indices"])


def test_a_surface_section_has_no_line_work(stage):
    payload = mesh.stage_sections(*stage)

    assert section_of(payload, "Soil_Top")["edge_indices"] == []


# ── Grouping and framing ────────────────────────────────────────────────────

def test_a_section_is_made_per_named_part(stage):
    payload = mesh.stage_sections(*stage)

    assert {s["part"] for s in payload["sections"]} == {"Soil_Top", "SheetPileWall"}


def test_a_part_this_stage_deactivated_produces_no_section(stage):
    """Nothing to draw, so nothing is sent. The part still appears in
    `/stages/{n}/parts`, which is where the explorer learns it exists and is off."""
    model, gid_mesh = stage
    gid_mesh.blocks[0].elements.clear()

    payload = mesh.stage_sections(model, gid_mesh)

    assert {s["part"] for s in payload["sections"]} == {"SheetPileWall"}


def test_the_payload_carries_a_bbox_to_frame_the_camera_on(stage):
    payload = mesh.stage_sections(*stage)

    assert payload["bbox"] == [0.0, 0.0, 0.0, 4.0, 2.0, 0.0]
    assert payload["dimension"] == 2


def test_positions_and_node_ids_line_up(stage):
    """The contract the whole colouring path rests on: vertex i is node `node_ids[i]`,
    and its coordinates are `positions[3i .. 3i+2]`."""
    payload = mesh.stage_sections(*stage)

    for section in payload["sections"]:
        assert len(section["positions"]) == 3 * len(section["node_ids"])
    soil = section_of(payload, "Soil_Top")
    at = soil["node_ids"].index(2)
    assert soil["positions"][3 * at:3 * at + 3] == [2.0, 0.0, 0.0]


def test_an_element_no_part_claims_is_still_drawn(stage):
    """A deck the exporter did not write, or one whose grouping is incomplete. The
    mesh is what is on screen, so an unclaimed element goes into a catch-all rather
    than vanishing with no explanation."""
    model, gid_mesh = stage
    del model.parts["Soil_Top"]

    payload = mesh.stage_sections(model, gid_mesh)

    unclaimed = [s for s in payload["sections"] if s["part"] is None]
    assert unclaimed and len(unclaimed[0]["indices"]) == 4 * 3


# ── Against the real run ────────────────────────────────────────────────────

@pytest.fixture
def real_run(monkeypatch):
    """A Kratos run of the test model (`tests/results_run.py`), or a skip without Kratos:
    its directory and its own deck."""
    from tests import results_run

    run = results_run.real_run()
    results_run.use(monkeypatch, run)
    root, run_id = run
    return root / run_id, mdpa_reader.import_mdpa(results_run.deck_text(run))


def test_the_real_stage_builds_and_every_index_is_in_range(real_run):
    """An index past the end of the positions buffer is the failure mode that matters:
    three.js does not check, it reads whatever is next in memory and draws a spike
    across the model."""
    from core.results import catalog

    directory, model = real_run
    for stage in catalog.describe(directory.name)["stages"]:
        gid_mesh = gid_reader.read_mesh(
            (directory / stage["mesh_file"]).read_text(encoding="utf-8"))
        payload = mesh.stage_sections(model, gid_mesh)

        assert payload["sections"], f"stage {stage['index']} draws nothing"
        for section in payload["sections"]:
            vertices = len(section["node_ids"])
            assert all(0 <= i < vertices for i in section["indices"]), \
                f"stage {stage['index']}, {section['part']}"
            assert len(section["positions"]) == 3 * vertices


def test_the_real_stages_show_the_excavation_disappearing(real_run):
    from core.results import catalog

    directory, model = real_run

    def parts_drawn(n):
        stage = catalog.describe(directory.name)["stages"][n - 1]
        gid_mesh = gid_reader.read_mesh(
            (directory / stage["mesh_file"]).read_text(encoding="utf-8"))
        return {s["part"] for s in mesh.stage_sections(model, gid_mesh)["sections"]}

    assert "Soil_Top_lift1" in parts_drawn(1)
    assert "Soil_Top_lift1" not in parts_drawn(4)
    assert "SheetPileWall" not in parts_drawn(1)
    assert "SheetPileWall" in parts_drawn(4)


# ── The mesh drawn over the shading ─────────────────────────────────────────
# `results mesh on` draws each element's outline over the contour. The outline is not
# the triangles the shading is drawn with: a six-node triangle is shaded as four, and
# its outline is still three sides. Through the mid-side nodes, so it bends with the
# deformed mesh the way the shading does.

def segments_of(section, key="wire_indices"):
    ids = section["node_ids"]
    flat = section[key]
    return {frozenset((ids[flat[n]], ids[flat[n + 1]])) for n in range(0, len(flat), 2)}


def test_a_quadratic_triangle_is_outlined_by_its_three_sides(stage):
    soil = section_of(mesh.stage_sections(*stage), "Soil_Top")
    # Corners 1,2,3 and mid-sides 4=(1,2), 5=(2,3), 6=(3,1): six half-sides, and not
    # the inner edges 4-5, 5-6 and 6-4 of the subdivision.
    assert segments_of(soil) == {frozenset(pair) for pair in
                                 ((1, 4), (4, 2), (2, 5), (5, 3), (3, 6), (6, 1))}


def test_every_outline_index_is_a_vertex_of_its_section(stage):
    soil = section_of(mesh.stage_sections(*stage), "Soil_Top")
    assert soil["wire_indices"]
    assert all(0 <= i < len(soil["node_ids"]) for i in soil["wire_indices"])


def test_a_line_element_has_no_outline_of_its_own(stage):
    """It is line work already, drawn as `edge_indices`."""
    wall = section_of(mesh.stage_sections(*stage), "SheetPileWall")
    assert wall["wire_indices"] == []


def test_a_linear_triangle_is_outlined_corner_to_corner():
    assert mesh.outline_of([1, 2, 3], 3, "Triangle") == [(1, 2), (2, 3), (3, 1)]


def test_a_quadrilateral_is_outlined_by_its_four_sides_not_its_diagonal():
    """It is shaded as two triangles across a diagonal; the diagonal is not an edge."""
    assert mesh.outline_of([1, 2, 3, 4], 4, "Quadrilateral") == [
        (1, 2), (2, 3), (3, 4), (4, 1)]


def test_an_eight_node_quadrilateral_is_outlined_through_its_midsides():
    # Corners 1-4, then mid-sides 5=(1,2), 6=(2,3), 7=(3,4), 8=(4,1), as Kratos orders them.
    assert mesh.outline_of([1, 2, 3, 4, 5, 6, 7, 8], 8, "Quadrilateral") == [
        (1, 5), (5, 2), (2, 6), (6, 3), (3, 7), (7, 4), (4, 8), (8, 1)]


def test_an_edge_two_elements_share_is_drawn_once():
    mdpa = dedent("""
        Begin Nodes
        1 0.0 0.0 0.0
        2 1.0 0.0 0.0
        3 1.0 1.0 0.0
        4 0.0 1.0 0.0
        5 2.0 0.0 0.0
        6 2.0 1.0 0.0
        End Nodes

        Begin Elements UPwSmallStrainElement2D4N
        1 1 1 2 3 4
        2 1 2 5 6 3
        End Elements

        Begin SubModelPart Soil
            Begin SubModelPartElements
            1
            2
            End SubModelPartElements
        End SubModelPart
        """)
    msh = dedent("""
        MESH "Kratos_Quadrilateral2D4_Mesh_1" dimension 2 ElemType Quadrilateral Nnode 4
        Coordinates
        1 0 0 0
        2 1 0 0
        3 1 1 0
        4 0 1 0
        5 2 0 0
        6 2 1 0
        End Coordinates
        Elements
        1 1 2 3 4 1
        2 2 5 6 3 1
        End Elements
        """)
    soil = section_of(mesh.stage_sections(mdpa_reader.import_mdpa(mdpa),
                                                 gid_reader.read_mesh(msh)), "Soil")
    assert len(soil["wire_indices"]) == 7 * 2, "seven edges, the shared 2-3 once"
    assert frozenset((2, 3)) in segments_of(soil)


# ── Quadratic quadrilaterals ────────────────────────────────────────────────
# A deck from elsewhere is often mostly eight-node quadrilaterals. Shaded through the
# corners alone, their
# four mid-side values never reach the screen -- and the mesh outline, which runs
# through those mid-side nodes, has no vertex to be drawn from.

def test_an_eight_node_quadrilateral_is_shaded_through_every_node():
    made = mesh.triangles_of([1, 2, 3, 4, 5, 6, 7, 8], 8, "Quadrilateral", 2)
    assert {frozenset(t) for t in made} == {
        frozenset({1, 5, 8}), frozenset({5, 2, 6}), frozenset({6, 3, 7}),
        frozenset({8, 7, 4}), frozenset({5, 6, 7}), frozenset({5, 7, 8})}
    assert {node for t in made for node in t} == set(range(1, 9))


def test_a_nine_node_quadrilateral_is_shaded_around_its_centre():
    made = mesh.triangles_of([1, 2, 3, 4, 5, 6, 7, 8, 9], 9, "Quadrilateral", 2)
    assert len(made) == 8
    assert all(9 in t for t in made)
    assert {node for t in made for node in t} == set(range(1, 10))


def test_a_four_node_quadrilateral_is_still_two_triangles():
    assert len(mesh.triangles_of([1, 2, 3, 4], 4, "Quadrilateral", 2)) == 2


def test_an_eight_node_quadrilateral_section_is_outlined_through_its_midsides():
    mdpa = dedent("""
        Begin Nodes
        1 0.0 0.0 0.0
        2 2.0 0.0 0.0
        3 2.0 2.0 0.0
        4 0.0 2.0 0.0
        5 1.0 0.0 0.0
        6 2.0 1.0 0.0
        7 1.0 2.0 0.0
        8 0.0 1.0 0.0
        End Nodes

        Begin Elements SmallStrainUPwDiffOrderElement2D8N
        1 1 1 2 3 4 5 6 7 8
        End Elements

        Begin SubModelPart Soil
            Begin SubModelPartElements
            1
            End SubModelPartElements
        End SubModelPart
        """)
    msh = dedent("""
        MESH "Kratos_Quadrilateral2D8_Mesh_1" dimension 2 ElemType Quadrilateral Nnode 8
        Coordinates
        1 0 0 0
        2 2 0 0
        3 2 2 0
        4 0 2 0
        5 1 0 0
        6 2 1 0
        7 1 2 0
        8 0 1 0
        End Coordinates
        Elements
        1 1 2 3 4 5 6 7 8 1
        End Elements
        """)
    soil = section_of(mesh.stage_sections(mdpa_reader.import_mdpa(mdpa),
                                                 gid_reader.read_mesh(msh)), "Soil")
    assert set(soil["node_ids"]) == set(range(1, 9))
    assert segments_of(soil) == {frozenset(pair) for pair in
                                 ((1, 5), (5, 2), (2, 6), (6, 3),
                                  (3, 7), (7, 4), (4, 8), (8, 1))}


# ── A 3D stage: each part drawn as its outer skin ───────────────────────────

MDPA_3D = dedent("""
    Begin Properties 1
    End Properties
    Begin Nodes
    1 0 0 0
    2 1 0 0
    3 0 1 0
    4 0 0 1
    5 1 1 1
    End Nodes
    Begin Elements UPwSmallStrainElement3D4N
    1 1 1 2 3 4
    2 1 2 3 4 5
    End Elements
    Begin SubModelPart Soil
     Begin SubModelPartNodes
     1
     2
     3
     4
     5
     End SubModelPartNodes
     Begin SubModelPartElements
     1
     2
     End SubModelPartElements
    End SubModelPart
    """)

MESH_3D = dedent("""
    MESH "Kratos_Tetrahedra3D4_Mesh_1" dimension 3 ElemType Tetrahedra Nnode 4
    Coordinates
    1 0 0 0
    2 1 0 0
    3 0 1 0
    4 0 0 1
    5 1 1 1
    End Coordinates
    Elements
    1 1 2 3 4 1
    2 2 3 4 5 1
    End Elements
    """)


def test_a_3d_part_is_drawn_as_its_skin_without_the_shared_face():
    """Two tetrahedra glued on face 2-3-4: eight faces, the shared one inside, six drawn."""
    sections = mesh.stage_sections(mdpa_reader.import_mdpa(MDPA_3D),
                                          gid_reader.read_mesh(MESH_3D))["sections"]

    (soil,) = [s for s in sections if s["part"] == "Soil"]
    triangles = [tuple(sorted(soil["node_ids"][i] for i in soil["indices"][k:k + 3]))
                 for k in range(0, len(soil["indices"]), 3)]
    assert len(triangles) == 6
    assert (2, 3, 4) not in triangles


def test_a_3d_skin_offers_no_per_element_colouring():
    """A skin face belongs to no single element, so the viewer falls back to nodes."""
    sections = mesh.stage_sections(mdpa_reader.import_mdpa(MDPA_3D),
                                          gid_reader.read_mesh(MESH_3D))["sections"]

    (soil,) = [s for s in sections if s["part"] == "Soil"]
    assert not soil.get("triangle_elements")
