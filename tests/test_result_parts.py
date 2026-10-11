"""Which part of the model an element belongs to, and what a phase did to it.

GiD names its mesh blocks `Kratos_Triangle2D6_Mesh_2`, which says nothing about whether
that is the top soil layer or the third excavation lift. The names are in the `.mdpa`
sitting in the same run directory, and the two agree exactly because both carry Kratos'
own element ids -- so the join is a lookup, not a guess.

The second thing here is subtler and is the difference between a postprocessor that can
be trusted and one that cannot: a part with no elements in this stage's mesh may have
been *deactivated by the phase*, or may be one the GiD writer never writes at all. The
interfaces are the second kind -- they are in the deck, they are solved, and they appear
in none of the seven stages of the real run. Reporting them as "removed in this phase"
would be a lie about the model.
"""

import textwrap

import pytest

from core import gid_results, mdpa_import, result_parts


def dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


MDPA = dedent("""
    Begin Properties 0
    End Properties

    Begin Nodes
    1 0.0 0.0 0.0
    2 1.0 0.0 0.0
    3 0.0 1.0 0.0
    4 1.0 1.0 0.0
    End Nodes

    Begin Elements UPwSmallStrainElement2D3N
    1 1 1 2 3
    2 1 2 4 3
    End Elements

    Begin Elements Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N
    9 2 1 2 3 4 1 2
    End Elements

    Begin SubModelPart Soil_Top
        Begin SubModelPartElements
        1
        End SubModelPartElements
    End SubModelPart

    Begin SubModelPart Soil_Top_lift1
        Begin SubModelPartElements
        2
        End SubModelPartElements
    End SubModelPart

    Begin SubModelPart Wall_contact
        Begin SubModelPartElements
        9
        End SubModelPartElements
    End SubModelPart

    Begin SubModelPart Bottom_Support
        Begin SubModelPartNodes
        1
        2
        End SubModelPartNodes
    End SubModelPart
    """)


def stage_mesh(*elements: int) -> gid_results.GidMesh:
    """A stage's `.post.msh` carrying just the elements named.

    The lift is written as its own block so that leaving it out produces the shape a
    real deactivated body has: a declared block with nothing in it.
    """
    rows = {1: "1 1 2 3 1", 2: "2 2 4 3 1"}
    lines = [
        'MESH "Kratos_Triangle2D3_Mesh_1" dimension 2 ElemType Triangle Nnode 3',
        "Coordinates", "1 0 0 0", "2 1 0 0", "3 0 1 0", "4 1 1 0", "End Coordinates",
        "Elements",
    ]
    lines += [rows[e] for e in elements if e in rows]
    lines.append("End Elements")
    return gid_results.read_mesh("\n".join(lines) + "\n")


@pytest.fixture
def model():
    return mdpa_import.import_mdpa(MDPA)


# ── The join ────────────────────────────────────────────────────────────────

def test_an_element_knows_which_part_it_belongs_to(model):
    owner = result_parts.element_owner(model)

    assert owner[1] == "Soil_Top"
    assert owner[2] == "Soil_Top_lift1"
    assert owner[9] == "Wall_contact"


def test_a_part_that_owns_no_elements_owns_no_elements(model):
    """`Bottom_Support` is a node set. It must not claim the elements those nodes
    happen to belong to."""
    owner = result_parts.element_owner(model)

    assert "Bottom_Support" not in owner.values()


def test_an_element_no_part_claims_is_simply_absent(model):
    owner = result_parts.element_owner(model)

    assert 404 not in owner


# ── What the phase did ──────────────────────────────────────────────────────

def test_a_part_whose_elements_are_in_this_stage_is_alive(model):
    parts = {p.name: p for p in result_parts.stage_parts(model, stage_mesh(1, 2))}

    assert parts["Soil_Top"].alive is True
    assert parts["Soil_Top_lift1"].alive is True
    assert parts["Soil_Top"].elements == [1]


def test_a_part_the_phase_deactivated_is_not_alive(model):
    """The excavated lift. Its block is in the stage mesh with nothing in it, and that
    is exactly how a staged result learns what is still standing -- no phase record is
    consulted and none is needed."""
    parts = {p.name: p for p in result_parts.stage_parts(model, stage_mesh(1))}

    assert parts["Soil_Top"].alive is True
    assert parts["Soil_Top_lift1"].alive is False
    assert parts["Soil_Top_lift1"].elements == []
    assert parts["Soil_Top_lift1"].declared == 1


def test_a_part_gid_never_writes_is_told_apart_from_one_that_was_removed(model):
    """The interfaces are solved and are in the deck, and the GiD writer has no
    geometry for them, so they are in none of the run's stages. Calling that
    "deactivated" would be a statement about the model, and a false one."""
    written = result_parts.written_parts(model, [stage_mesh(1, 2), stage_mesh(1)])

    parts = {p.name: p for p in result_parts.stage_parts(model, stage_mesh(1),
                                                         written=written)}

    assert parts["Soil_Top_lift1"].written is True
    assert parts["Soil_Top_lift1"].alive is False, "removed by this phase"
    assert parts["Wall_contact"].written is False, "never written by the GiD output"
    assert parts["Wall_contact"].alive is False


def test_without_the_run_wide_check_nothing_claims_to_know(model):
    """`written` is a fact about the whole run, so a single stage may not assert it.
    None, not False: the difference between "no" and "not asked"."""
    parts = {p.name: p for p in result_parts.stage_parts(model, stage_mesh(1))}

    assert parts["Wall_contact"].written is None


def test_a_node_only_part_is_carried_but_never_called_dead(model):
    """A support or a boundary owns no elements, so "alive" is not a question about
    it. It is reported so the explorer can list it, and its aliveness is None."""
    parts = {p.name: p for p in result_parts.stage_parts(model, stage_mesh(1, 2))}

    assert parts["Bottom_Support"].kind == "support"
    assert parts["Bottom_Support"].alive is None
    assert parts["Bottom_Support"].nodes == 2


def test_a_part_with_no_elements_is_not_reported_as_unwritten(model):
    """`written` is about whether the GiD writer has a geometry for this part's element
    type. A part with no elements has nothing to write either way, so the question does
    not apply -- and answering False would put every support and boundary in the deck
    in the same bucket as the interfaces, which is the one distinction this field
    exists to make."""
    written = result_parts.written_parts(model, [stage_mesh(1, 2)])

    parts = {p.name: p for p in result_parts.stage_parts(model, stage_mesh(1, 2),
                                                         written=written)}

    assert parts["Bottom_Support"].written is None
    assert parts["Wall_contact"].written is False, "this one really is unwritten"


def test_parts_keep_the_order_the_deck_declares_them_in(model):
    names = [p.name for p in result_parts.stage_parts(model, stage_mesh(1, 2))]

    assert names == ["Soil_Top", "Soil_Top_lift1", "Wall_contact", "Bottom_Support"]


# ── Against the real run ────────────────────────────────────────────────────

def test_the_real_run_reads_its_construction_sequence_out_of_the_files(monkeypatch):
    """The end-to-end claim of this task, against a seven-stage Kratos run of the test
    model (skipped without Kratos): the phases a staged model went through are
    recoverable from its output alone.

    The excavation lifts leave one at a time, the wall arrives when it is installed and
    the strut after it, and the interfaces are absent throughout -- which the run-wide
    check reports as "not written" rather than as seven deactivations.
    """
    from core import results
    from tests import results_run

    run = results_run.real_run()
    results_run.use(monkeypatch, run)
    root, run_id = run
    directory = root / run_id
    model = mdpa_import.import_mdpa(results_run.deck_text(run))
    meshes = [gid_results.read_mesh(
                  (directory / stage["mesh_file"]).read_text(encoding="utf-8"))
              for stage in results.describe(directory.name)["stages"]]
    written = result_parts.written_parts(model, meshes)

    def alive(name):
        return [{p.name: p.alive for p in result_parts.stage_parts(model, mesh)}[name]
                for mesh in meshes]

    assert alive("Soil_Top_lift1") == [True, True, True, False, False, False, False]
    assert alive("Soil_Top_lift2") == [True, True, True, True, True, False, False]
    assert alive("Soil_Top_lift3") == [True, True, True, True, True, True, False]
    assert alive("SheetPileWall") == [False, False, True, True, True, True, True]
    assert alive("Strut") == [False, False, False, False, True, True, True]
    assert alive("Soil_Bottom") == [True] * 7

    assert "SheetPileWall" in written and "Strut" in written
    assert not any(name.startswith("Interface_") for name in written), \
        "GiD writes no interface elements; they must not read as written"
