"""Reading GiD's ASCII post files.

`app.gid_results` is a format reader and nothing else: it turns `.post.msh` and
`.post.res` text into tables, and has no opinion about what the numbers mean. What they
mean -- which of them a user can ask for, in what unit, with which sign -- is
`app.result_fields`, and is tested next door.

The cases below are written against small literal files, because that is the only way to
pin the parts of the format that the runs on this machine happen not to exercise. The
real files are then read at the end of the module as a second, blunter check: a parser
that agrees with a hand-written fixture and chokes on 500 KB of the real thing has
learned the wrong format.
"""

import textwrap

import pytest

from pathlib import Path

from app import gid_results

REFERENCE = Path(__file__).resolve().parents[2] / "test"
"""The GeoMechanicsApplication's own 1D consolidation deck and its eleven stages of
output, copied into the repository root's `test/`. Gitignored, like `examples/` -- so
every case that reads it skips when it is not there."""


def reference_stage(n: int) -> tuple[Path, Path]:
    mesh = REFERENCE / f"1D-Consolidationtest_stage{n}.post.msh"
    res = REFERENCE / f"1D-Consolidationtest_stage{n}.post.res"
    if not mesh.is_file() or not res.is_file():
        pytest.skip(f"{mesh.name} is not present; the reference output is kept out of "
                    "the repository")
    return mesh, res


def dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


# ── The mesh ────────────────────────────────────────────────────────────────

MESH = dedent("""
    MESH "Kratos_Triangle2D6_Mesh_1" dimension 2 ElemType Triangle Nnode 6
    Coordinates
    1 0.1 0 0
    2 0.1 -1 0
    3 0 -1 0
    End Coordinates
    Elements
    11 1 2 3 4 5 6 3
    12 3 2 1 6 5 4 3
    End Elements
    MESH "Kratos_Triangle2D6_Mesh_2" dimension 2 ElemType Triangle Nnode 6
    Elements
    13 1 2 3 4 5 6 7
    End Elements
    """)


def test_nodes_are_read_once_however_many_blocks_follow():
    mesh = gid_results.read_mesh(MESH)

    assert mesh.nodes[1] == (0.1, 0.0, 0.0)
    assert mesh.nodes[3] == (0.0, -1.0, 0.0)
    assert len(mesh.nodes) == 3


def test_a_block_carries_its_element_type_and_node_count():
    mesh = gid_results.read_mesh(MESH)

    assert [block.element_type for block in mesh.blocks] == ["Triangle", "Triangle"]
    assert [block.nnode for block in mesh.blocks] == [6, 6]
    assert mesh.blocks[0].name == "Kratos_Triangle2D6_Mesh_1"


def test_connectivity_stops_before_the_property_id():
    """The last number on an element row is its Properties id, not a node. Read as a
    node it would be a silent corruption -- a plausible id pointing at real
    coordinates somewhere else in the mesh."""
    mesh = gid_results.read_mesh(MESH)

    assert mesh.blocks[0].elements[11] == [1, 2, 3, 4, 5, 6]
    assert mesh.blocks[0].properties[11] == 3
    assert mesh.blocks[1].properties[13] == 7


def test_a_block_with_no_coordinates_of_its_own_still_reads():
    """Only the first block in a Kratos file carries `Coordinates`; the rest reference
    the same global node table."""
    mesh = gid_results.read_mesh(MESH)

    assert list(mesh.blocks[1].elements) == [13]


def test_an_empty_element_block_is_a_block_with_no_elements():
    """What a body deactivated in this phase looks like. It is not an error and not an
    absent block: the part is still declared, and it has nothing in it."""
    text = dedent("""
        MESH "Kratos_Triangle2D6_Mesh_4" dimension 2 ElemType Triangle Nnode 6
        Elements
        End Elements
        """)

    mesh = gid_results.read_mesh(text)

    assert len(mesh.blocks) == 1
    assert mesh.blocks[0].elements == {}


def test_every_element_can_be_found_without_knowing_its_block():
    mesh = gid_results.read_mesh(MESH)

    assert mesh.connectivity(13) == [1, 2, 3, 4, 5, 6]
    assert mesh.connectivity(999) is None


def test_the_dimension_is_read_from_the_block_header():
    mesh = gid_results.read_mesh(MESH)

    assert mesh.dimension == 2


# ── The results ─────────────────────────────────────────────────────────────

RES = dedent("""
    GiD Post Results File 1.2
    GaussPoints "lin2_element_gp" ElemType Linear
    Number Of Gauss Points: 2
      Nodes not included
    Natural Coordinates: Internal
    End GaussPoints
    GaussPoints "tri3_element_gp" ElemType Triangle
    Number Of Gauss Points: 3
    Natural Coordinates: Given
    0.166667 0.166667
    0.666667 0.166667
    0.166667 0.666667
    End GaussPoints
    Result "DISPLACEMENT" "Kratos" 2 Vector OnNodes
    Values
    1 0 0.0477245 0
    2 -0.00308939 0.0623976 0
    End Values
    Result "WATER_PRESSURE" "Kratos" 2 Scalar OnNodes
    Values
    1 -105000
    2 -35000
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 2 Matrix OnGaussPoints "tri3_element_gp"
    Values
    11 -44314.5 -85354.7 -45373.9 -702.893 0 0
     -44110.3 -84816.3 -45029.7 -587.065 0 0
     -40413.7 -78864.8 -41333.5 -473.357 0 0
    12 -44173.8 -78590.9 -44758 -5401.51 0 0
     -44132.1 -77457.7 -44432.9 -5631.06 0 0
     -46019 -80410.2 -46284.4 -5424.89 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 2 Matrix OnGaussPoints "lin2_element_gp"
    Values
    End Values
    """)


def test_gauss_point_sets_are_read_with_their_counts():
    """The count is what makes the Gauss blocks readable at all -- see the
    continuation-line case below."""
    out = gid_results.read_results(RES)

    assert out.gauss_sets["tri3_element_gp"].count == 3
    assert out.gauss_sets["tri3_element_gp"].element_type == "Triangle"
    assert out.gauss_sets["lin2_element_gp"].count == 2


def test_a_nodal_vector_comes_back_per_node():
    out = gid_results.read_results(RES)
    field = out.field("DISPLACEMENT")

    assert field.kind == "vector"
    assert field.location == "nodes"
    assert field.values[1] == [0.0, 0.0477245, 0.0]
    assert field.values[2] == [-0.00308939, 0.0623976, 0.0]


def test_a_nodal_scalar_is_still_a_list_of_one():
    """One shape for every field, so nothing downstream has to branch on arity."""
    out = gid_results.read_results(RES)

    assert out.field("WATER_PRESSURE").values[1] == [-105000.0]


def test_the_time_is_read_and_is_the_stage_it_belongs_to():
    out = gid_results.read_results(RES)

    assert out.field("DISPLACEMENT").time == 2.0


def test_gauss_values_are_grouped_by_element_across_continuation_lines():
    """The one genuinely awkward thing in the format. A Gauss row is
    `elem_id v...` and is followed by one bare `v...` line per remaining Gauss point,
    with no id on it -- so a reader that takes the first token as an id gets three
    elements numbered -44110, -40413 and 12."""
    out = gid_results.read_results(RES)
    field = out.field("CAUCHY_STRESS_TENSOR")

    assert field.location == "gauss"
    assert sorted(field.values) == [11, 12]
    assert len(field.values[11]) == 3, "three Gauss points per tri3 element"
    assert field.values[11][0] == [-44314.5, -85354.7, -45373.9, -702.893, 0.0, 0.0]
    assert field.values[11][2][0] == -40413.7
    assert field.values[12][1][3] == -5631.06


def test_an_empty_gauss_block_is_read_as_a_field_with_nothing_in_it():
    """Not a parse failure and not an absent field. The beam element does not
    implement CAUCHY_STRESS_TENSOR on its integration points, so Kratos writes the
    block and puts nothing in it -- which is how `app.result_fields` learns that
    stresses are not available on the wall."""
    out = gid_results.read_results(RES)

    beam = out.field("CAUCHY_STRESS_TENSOR", gauss_set="lin2_element_gp")
    assert beam is not None
    assert beam.values == {}


def test_one_variable_can_appear_on_two_gauss_sets():
    out = gid_results.read_results(RES)

    assert len(out.fields_named("CAUCHY_STRESS_TENSOR")) == 2


def test_the_variables_present_are_reported():
    out = gid_results.read_results(RES)

    assert out.variables() == {"CAUCHY_STRESS_TENSOR", "DISPLACEMENT", "WATER_PRESSURE"}


def test_a_variable_that_is_not_there_is_none_rather_than_a_raise():
    """The field catalogue asks for everything it might offer and keeps what came
    back, so absence is the normal answer and must be cheap."""
    out = gid_results.read_results(RES)

    assert out.field("TOTAL_STRESS_TENSOR") is None


def test_an_empty_file_is_no_fields_rather_than_an_error():
    out = gid_results.read_results("GiD Post Results File 1.2\n")

    assert out.variables() == set()


# ── Against the real thing ──────────────────────────────────────────────────

def test_the_reference_mesh_reads():
    mesh_path, _ = reference_stage(1)

    mesh = gid_results.read_mesh(mesh_path.read_text(encoding="utf-8"))

    assert len(mesh.nodes) > 100
    assert mesh.blocks and mesh.blocks[0].element_type == "Triangle"
    assert mesh.blocks[0].nnode == 6
    # Every element's connectivity is the node count its block declares, and every
    # node it names exists. This is the assertion that would catch the property id
    # being read as a node.
    for block in mesh.blocks:
        for element, conn in block.elements.items():
            assert len(conn) == block.nnode
            assert all(node in mesh.nodes for node in conn)


def test_the_reference_results_read():
    _, res_path = reference_stage(1)

    out = gid_results.read_results(res_path.read_text(encoding="utf-8"))

    assert {"TOTAL_DISPLACEMENT", "WATER_PRESSURE",
            "CAUCHY_STRESS_TENSOR"} <= out.variables()
    assert out.field("TOTAL_DISPLACEMENT").kind == "vector"
    assert out.field("WATER_PRESSURE").kind == "scalar"


def test_every_reference_stage_reads_and_its_results_match_its_mesh():
    """Eleven stages, every one of them. The join is what matters: a Gauss field is
    keyed by element id and a nodal field by node id, and both have to land on things
    the mesh actually contains or nothing downstream can draw them."""
    for n in range(1, 12):
        mesh_path, res_path = reference_stage(n)
        mesh = gid_results.read_mesh(mesh_path.read_text(encoding="utf-8"))
        out = gid_results.read_results(res_path.read_text(encoding="utf-8"))

        elements = {id for block in mesh.blocks for id in block.elements}
        for field in out.all_fields():
            if field.location == "nodes":
                assert set(field.values) <= set(mesh.nodes), f"stage {n}, {field.variable}"
            else:
                assert set(field.values) <= elements, f"stage {n}, {field.variable}"


def test_every_gauss_element_has_the_number_of_points_its_set_declares():
    for n in (1, 6, 11):
        _, res_path = reference_stage(n)
        out = gid_results.read_results(res_path.read_text(encoding="utf-8"))

        for field in out.all_fields():
            if field.location != "gauss":
                continue
            expected = out.gauss_sets[field.gauss_set].count
            for element, points in field.values.items():
                assert len(points) == expected, f"stage {n}, element {element}"


# ── Several steps per stage, several element types per variable (finding F6) ──

STEPPED = dedent("""
    GiD Post Results File 1.0
    GaussPoints "tri_gp" ElemType Triangle
    Number Of Gauss Points: 1
    Natural Coordinates: Internal
    End GaussPoints
    GaussPoints "quad_gp" ElemType Quadrilateral
    Number Of Gauss Points: 2
    Natural Coordinates: Internal
    End GaussPoints
    Result "DISPLACEMENT" "Kratos" 0.25 Vector OnNodes
    Values
    1 0.001 0 0
    2 0.002 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 0.25 Matrix OnGaussPoints "tri_gp"
    Values
    11 -1 -1 -1 0 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 0.25 Matrix OnGaussPoints "quad_gp"
    Values
    21 -5 -5 -5 0 0 0
     -5 -5 -5 0 0 0
    End Values
    Result "DISPLACEMENT" "Kratos" 0.5 Vector OnNodes
    Values
    1 0.01 0 0
    2 0.02 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 0.5 Matrix OnGaussPoints "tri_gp"
    Values
    11 -2 -2 -2 0 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 0.5 Matrix OnGaussPoints "quad_gp"
    Values
    21 -6 -6 -6 0 0 0
     -6 -6 -6 0 0 0
    End Values
    Result "DISPLACEMENT" "Kratos" 1 Vector OnNodes
    Values
    1 0.1 0 0
    2 0.2 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 1 Matrix OnGaussPoints "tri_gp"
    Values
    11 -3 -3 -3 0 0 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 1 Matrix OnGaussPoints "quad_gp"
    Values
    21 -7 -7 -7 0 0 0
     -7 -7 -7 0 0 0
    End Values
    """)


def test_a_stage_written_in_several_steps_reads_as_its_last_step():
    """A step cut on non-convergence makes Kratos write a block per step. The stage's
    result is where it ended, not the first sub-step."""
    results = gid_results.read_results(STEPPED)

    field = results.field("DISPLACEMENT")

    assert field.time == 1.0
    assert field.values == {1: [0.1, 0.0, 0.0], 2: [0.2, 0.0, 0.0]}


def test_a_gauss_variable_of_two_element_types_keeps_both():
    """Soil and interface (or two continuum types) both write CAUCHY_STRESS_TENSOR, one
    block per Gauss set. Asking for the variable must give every element, each with its
    own points -- not whichever block came first."""
    results = gid_results.read_results(STEPPED)

    field = results.field("CAUCHY_STRESS_TENSOR")

    assert set(field.values) == {11, 21}
    assert field.values[11] == [[-3.0] * 3 + [0.0] * 3]
    assert field.values[21] == [[-7.0] * 3 + [0.0] * 3] * 2


def test_one_gauss_set_can_still_be_asked_for_alone():
    results = gid_results.read_results(STEPPED)

    field = results.field("CAUCHY_STRESS_TENSOR", gauss_set="quad_gp")

    assert set(field.values) == {21}
    assert field.values[21][0][0] == -7.0


def test_an_empty_last_step_of_one_set_does_not_hide_the_other():
    """The beam's empty `lin2_element_gp` block is written at every step; it must still
    lose to the soil's block of the same step."""
    text = STEPPED + dedent("""
        GaussPoints "lin2_element_gp" ElemType Linear
        Number Of Gauss Points: 2
        Natural Coordinates: Internal
        End GaussPoints
        Result "CAUCHY_STRESS_TENSOR" "Kratos" 1 Matrix OnGaussPoints "lin2_element_gp"
        Values
        End Values
        """)
    field = gid_results.read_results(text).field("CAUCHY_STRESS_TENSOR")

    assert set(field.values) == {11, 21}


def test_a_results_file_cut_off_mid_write_reads_what_is_there():
    """A run killed while writing leaves a file that stops mid-block. The stage is still
    worth looking at, so the reader keeps what it read rather than refusing all of it."""
    whole = STEPPED.split('Result "CAUCHY_STRESS_TENSOR" "Kratos" 1 Matrix')[0]
    cut = whole + 'Result "DISPLACEMENT" "Kratos" 2 Vector OnNodes\nValues\n1 0.5 0'

    results = gid_results.read_results(cut)

    # The step cut off before its first full row is empty; the last *complete* step is
    # what there is to see, not nothing.
    assert results.field("DISPLACEMENT").time == 1.0
    assert results.field("DISPLACEMENT").values[1] == [0.1, 0.0, 0.0]
    assert results.field("CAUCHY_STRESS_TENSOR").time == 0.5
