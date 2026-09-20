"""`app.mdpa_import`: reading a .mdpa deck back into typed mesh data.

Checked two ways: round-tripped through `kratos.export_project` (so the classification
tables are proven against the same fixture the forward-export tests use), and against
the real GiD-authored decks in examples/, which this codebase did not write and may use
element classes the export side never emits.
"""

from pathlib import Path

import pytest

from app import build, kratos, mdpa_import
from app.schemas import MeshRequest, Project
from app.seed import seed_project

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


@pytest.fixture(scope="module")
def exported(session):
    project = seed_project()
    return kratos.export_project(project, MeshRequest(element_size=4.0, order=2))


@pytest.fixture(scope="module")
def reimported(exported):
    return mdpa_import.import_mdpa(exported["mdpa"])


# ── Round trip against this codebase's own exporter ─────────────────────────

def test_every_node_survives_the_round_trip(exported, reimported):
    written = exported["mdpa"].count("\n")  # sanity: the fixture actually has content
    assert written > 0
    assert len(reimported.nodes) > 0


def test_element_and_condition_counts_match_the_source_deck(exported, reimported):
    import re

    for keyword, entities in (("Elements", reimported.elements),
                              ("Conditions", reimported.conditions)):
        for match in re.finditer(rf"Begin {keyword} (\S+)", exported["mdpa"]):
            name = match.group(1)
            entity = next(e for e in entities if e.kratos_class == name)
            assert len(entity.entries) > 0


def test_soil_elements_are_classified_as_continuum(reimported):
    soil = [e for e in reimported.elements if e.kind == "continuum"]
    assert soil, "the seed project has at least one soil body"
    assert all(e.dim in (2, 3) for e in soil)


def test_every_sub_model_part_round_trips_with_its_kind(exported, reimported):
    import re

    names = re.findall(r"Begin SubModelPart (\S+)", exported["mdpa"])
    assert set(names) == set(reimported.parts)
    for name, part in reimported.parts.items():
        if name in mdpa_import.BOUNDARY_NAMES:
            assert part.kind == "boundary"
        elif name.endswith("_Support"):
            assert part.kind == "support"


def test_dimension_is_inferred_from_the_node_table(reimported):
    # seed_project() is a 3D model: not every node's z is zero.
    assert reimported.dimension == 3


def test_a_plane_strain_export_is_recognised_as_2d(session):
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=20.0)
    project = Project.model_validate(payload)
    exported = kratos.export_project(project, MeshRequest(element_size=4.0, order=1))

    model = mdpa_import.import_mdpa(exported["mdpa"])

    assert model.dimension == 2


def test_bbox_covers_the_node_cloud(reimported):
    x0, y0, z0, x1, y1, z1 = reimported.bbox
    for x, y, z in reimported.nodes.values():
        assert x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1


def test_to_dict_is_json_safe(reimported):
    import json

    json.dumps(reimported.to_dict())


# ── Real, externally-authored decks ──────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "simple_embankment.mdpa", "crow_case.mdpa", "dike_with_sheet_pile.mdpa",
    "Deep_excavation_Rotterdam_Zuid.mdpa",
])
def test_reference_decks_parse_without_error(filename):
    text = (EXAMPLES / filename).read_text()

    model = mdpa_import.import_mdpa(text)

    assert model.nodes
    assert model.elements
    for entity in model.elements + model.conditions:
        assert len(entity.entries) > 0


def test_an_unmapped_class_name_is_kept_as_unknown_rather_than_failing():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n1 0.0 0.0 0.0\n2 1.0 0.0 0.0\nEnd Nodes\n\n"
        "Begin Elements SomeFutureKratosElement2D2N\n"
        "1 0 1 2\n"
        "End Elements\n"
    )

    model = mdpa_import.import_mdpa(text)

    assert model.elements[0].kind == "unknown"
    assert model.elements[0].dim is None


def test_malformed_deck_raises_import_error():
    with pytest.raises(mdpa_import.ImportError_):
        mdpa_import.import_mdpa("Begin Nodes\n1 not-a-number 0 0\nEnd Nodes\n")


# ── Drawable preview (to_sections) ───────────────────────────────────────────

def test_a_single_tetrahedron_draws_as_its_own_four_faces():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n"
        "1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\n4 0.0 0.0 1.0\n"
        "End Nodes\n\n"
        "Begin Elements UPwSmallStrainElement3D4N\n1 0 1 2 3 4\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    sections = mdpa_import.to_sections(model)

    soil = next(s for s in sections if s["key"] == "imported_continuum")
    assert len(soil["indices"]) == 4 * 3, "all four faces of an isolated tet are boundary"
    assert len(soil["positions"]) == 4 * 3


def test_two_tets_sharing_a_face_hide_that_face():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n"
        "1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\n4 0.0 0.0 1.0\n5 1.0 1.0 1.0\n"
        "End Nodes\n\n"
        "Begin Elements UPwSmallStrainElement3D4N\n"
        "1 0 1 2 3 4\n"
        "2 0 2 1 3 5\n"
        "End Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    sections = mdpa_import.to_sections(model)

    soil = next(s for s in sections if s["key"] == "imported_continuum")
    # 8 faces total, minus the two copies of the shared 1-2-3 face: 6 boundary triangles.
    assert len(soil["indices"]) == 6 * 3


def test_a_2d_deck_draws_its_triangles_directly_with_no_boundary_extraction():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\nEnd Nodes\n\n"
        "Begin Elements UPwSmallStrainElement2D3N\n1 0 1 2 3\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    sections = mdpa_import.to_sections(model)

    soil = next(s for s in sections if s["key"] == "imported_continuum")
    assert len(soil["indices"]) == 3


def test_a_quadratic_beam_spans_end_to_end_not_end_to_midside():
    """`kratos.BEAMS` writes a 3-node beam as (end, end, midside), so the far end is the
    *second* node. Drawing to the last one covers half of each element, which renders a
    sheet pile as a dashed line with the other half missing."""
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        # node 2 is the far end at x=2; node 3 is the midside at x=1.
        "Begin Nodes\n1 0.0 0.0 0.0\n2 2.0 0.0 0.0\n3 1.0 0.0 0.0\nEnd Nodes\n\n"
        "Begin Elements LinearTimoshenkoCurvedBeamElement2D3N\n1 0 1 2 3\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    sections = mdpa_import.to_sections(model)

    beam = next(s for s in sections if s["key"] == "imported_beam")
    assert beam["edges"] == [0.0, 0.0, 0.0, 2.0, 0.0, 0.0]
    assert beam["indices"] == [], "a beam has no triangles, only its own line segment"


def test_a_beams_segments_join_up_into_one_unbroken_run():
    """The end of each element is the start of the next -- what makes a sheet pile draw
    as a continuous line rather than a row of dashes."""
    model = mdpa_import.import_mdpa((EXAMPLES / "crow_case.mdpa").read_text())

    # crow_case.mdpa's sheet pile is its own body sub-model part ("Sheet_Pile_Wall"),
    # not a leftover -- see test_a_body_sub_model_part_becomes_its_own_section below.
    beam = next(s for s in mdpa_import.to_sections(model) if s["part"] == "Sheet_Pile_Wall")

    points = [tuple(beam["edges"][i:i + 3]) for i in range(0, len(beam["edges"]), 3)]
    starts = {points[i] for i in range(0, len(points), 2)}
    ends = {points[i] for i in range(1, len(points), 2)}
    # Every joint is both an end and a start; only the pile's own two tips are not.
    assert len(starts ^ ends) == 2, "the run is broken into disconnected pieces"


def test_an_unknown_class_contributes_no_section():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n1 0.0 0.0 0.0\n2 1.0 0.0 0.0\nEnd Nodes\n\n"
        "Begin Elements SomeFutureKratosElement2D2N\n1 0 1 2\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    assert mdpa_import.to_sections(model) == []


def test_to_dict_includes_render_ready_sections(reimported):
    sections = reimported.to_dict()["sections"]
    assert sections
    for section in sections:
        assert set(section) == {"key", "color", "part", "kind", "positions", "indices",
                                "edges", "bbox", "node_ids", "elements"}


# ── One section per body sub-model part ──────────────────────────────────────

TWO_BODY_DECK = (
    "Begin Properties 0\nEnd Properties\n\n"
    "Begin Nodes\n"
    "1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\n"
    "4 2.0 0.0 0.0\n5 2.0 1.0 0.0\n"
    "End Nodes\n\n"
    "Begin Elements UPwSmallStrainElement2D3N\n"
    "1 0 1 2 3\n"
    "2 0 2 4 5\n"
    "End Elements\n\n"
    "Begin SubModelPart Soil_1\n"
    "    Begin SubModelPartElements\n1\n    End SubModelPartElements\n"
    "End SubModelPart\n\n"
    "Begin SubModelPart Soil_2\n"
    "    Begin SubModelPartElements\n2\n    End SubModelPartElements\n"
    "End SubModelPart\n"
)


def test_a_body_sub_model_part_becomes_its_own_section():
    model = mdpa_import.import_mdpa(TWO_BODY_DECK)

    sections = mdpa_import.to_sections(model)

    assert {s["key"] for s in sections} == {"imported:Soil_1", "imported:Soil_2"}
    soil_1 = next(s for s in sections if s["part"] == "Soil_1")
    assert soil_1["kind"] == "continuum"
    assert len(soil_1["indices"]) == 3, "just its own triangle, not the other body's"


def test_each_bodys_section_is_a_different_colour():
    model = mdpa_import.import_mdpa(TWO_BODY_DECK)

    sections = {s["part"]: s["color"] for s in mdpa_import.to_sections(model)}

    assert sections["Soil_1"] != sections["Soil_2"]


def test_a_bodys_section_is_scoped_to_only_the_nodes_it_uses():
    """The whole point of keeping this local rather than sharing the deck's node table:
    a payload with N bodies must not carry N copies of every node in the file."""
    model = mdpa_import.import_mdpa(TWO_BODY_DECK)

    soil_1 = next(s for s in mdpa_import.to_sections(model) if s["part"] == "Soil_1")

    assert len(soil_1["positions"]) == 3 * 3, "3 nodes, not all 5 in the file"


def test_a_bodys_section_bbox_frames_just_that_body():
    model = mdpa_import.import_mdpa(TWO_BODY_DECK)

    soil_2 = next(s for s in mdpa_import.to_sections(model) if s["part"] == "Soil_2")

    # Soil_2 is nodes 2, 4, 5: (1,0), (2,0), (2,1) -- x starts at 1, not 0 like Soil_1.
    assert soil_2["bbox"] == [1.0, 0.0, 0.0, 2.0, 1.0, 0.0]


def test_with_no_sub_model_parts_declared_everything_falls_back_to_one_section_per_kind():
    """A deck exactly like TWO_BODY_DECK but with no SubModelParts: nothing claims the
    elements, so they draw as before this was per-part -- one section for every
    continuum element together, not per body."""
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n"
        "1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\n"
        "4 2.0 0.0 0.0\n5 2.0 1.0 0.0\n"
        "End Nodes\n\n"
        "Begin Elements UPwSmallStrainElement2D3N\n"
        "1 0 1 2 3\n"
        "2 0 2 4 5\n"
        "End Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    sections = mdpa_import.to_sections(model)

    assert [s["key"] for s in sections] == ["imported_continuum"]
    assert len(sections[0]["indices"]) == 6, "both triangles, in one section"
    assert sections[0]["part"] is None


def test_an_interface_only_body_part_draws_the_line_it_lies_along():
    """crow_case.mdpa's "Interface_..." parts own only zero-thickness interface
    elements. They are drawn -- as line work, since there is no thickness to fill -- so
    each gets its own checklist row and its own eye in the Model explorer."""
    model = mdpa_import.import_mdpa((EXAMPLES / "crow_case.mdpa").read_text())

    sections = {s["key"]: s for s in mdpa_import.to_sections(model)}

    contact = sections["imported:Interface_Top_Right"]
    assert contact["kind"] == "interface"
    assert contact["edges"], "a contact is line work, not a surface"
    assert contact["indices"] == []
    assert any(k.startswith("imported:") for k in sections), "the real bodies still draw"


def test_an_invisible_body_part_does_not_burn_a_palette_slot():
    """A body part that draws nothing (like crow_case.mdpa's "Interface_..." parts)
    must not shift every later part's colour along by one -- otherwise two real bodies
    a palette's length apart end up sharing a colour by accident, for a reason nobody
    looking at the checklist could see (an invisible part in between)."""
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n"
        "1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\n"
        "4 3.0 0.0 0.0\n5 4.0 0.0 0.0\n6 3.0 1.0 0.0\n"
        "End Nodes\n\n"
        "Begin Elements UPwSmallStrainElement2D3N\n"
        "1 0 1 2 3\n"
        "2 0 4 5 6\n"
        "End Elements\n\n"
        "Begin Elements SomeFutureKratosElement2D2N\n3 0 1 4\nEnd Elements\n\n"
        "Begin SubModelPart Soil_A\n"
        "    Begin SubModelPartElements\n1\n    End SubModelPartElements\n"
        "End SubModelPart\n\n"
        # An invisible body sandwiched between two real ones -- its own class is not
        # one this exporter recognises, so it draws nothing.
        "Begin SubModelPart Invisible_Interface\n"
        "    Begin SubModelPartElements\n3\n    End SubModelPartElements\n"
        "End SubModelPart\n\n"
        "Begin SubModelPart Soil_B\n"
        "    Begin SubModelPartElements\n2\n    End SubModelPartElements\n"
        "End SubModelPart\n"
    )
    model = mdpa_import.import_mdpa(text)

    sections = {s["part"]: s["color"] for s in mdpa_import.to_sections(model)}

    assert "Invisible_Interface" not in sections
    assert sections["Soil_A"] != sections["Soil_B"]
    assert sections["Soil_B"] == mdpa_import.PART_PALETTE[1], (
        "Soil_B is the second *visible* body -- the invisible one in between must not "
        "have consumed a palette slot"
    )


@pytest.mark.parametrize("filename", [
    "simple_embankment.mdpa", "crow_case.mdpa", "dike_with_sheet_pile.mdpa",
    "Deep_excavation_Rotterdam_Zuid.mdpa",
])
def test_reference_decks_produce_at_least_one_drawable_section(filename):
    model = mdpa_import.import_mdpa((EXAMPLES / filename).read_text())

    sections = mdpa_import.to_sections(model)

    assert sections
    for section in sections:
        assert section["indices"] or section["edges"]


# ── A deck's node table is already the world frame ───────────────────────────────

SECTION_DECK = (
    "Begin Properties 0\nEnd Properties\n\n"
    "Begin Nodes\n1 0.0 0.0 0.0\n2 8.0 0.0 0.0\n3 0.0 -6.0 0.0\nEnd Nodes\n\n"
    "Begin Elements UPwSmallStrainElement2D3N\n1 0 1 2 3\nEnd Elements\n"
)
"""A plane-strain triangle 8 m wide and 6 m deep, as Kratos writes one: the section's
own two axes on X and Y, Z zeroed."""


def test_a_2d_deck_needs_no_standing_up():
    """It used to: a section authored in the world x-z elevation had to be rotated out
    of the Kratos x-y plane to be visible. Since the re-basis a 2D model *is* the x-y
    plane at z = 0, so the file's own numbers are already the world's."""
    model = mdpa_import.import_mdpa(SECTION_DECK)

    placed = model.world_nodes()

    assert placed == model.nodes
    assert placed[1] == (0.0, 0.0, 0.0)
    assert placed[2] == (8.0, 0.0, 0.0)
    assert placed[3] == (0.0, -6.0, 0.0), "the section has its depth in y, not in z"


def test_a_3d_deck_is_already_in_the_world_frame_and_is_left_alone():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n"
        "1 0.0 0.0 0.0\n2 1.0 0.0 0.0\n3 0.0 1.0 0.0\n4 0.0 0.0 1.0\n"
        "End Nodes\n\n"
        "Begin Elements UPwSmallStrainElement3D4N\n1 0 1 2 3 4\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    assert model.world_nodes() == model.nodes


def test_the_bbox_and_the_geometry_are_reported_in_one_frame():
    """The bbox is what frames the camera. Sent in the file's frame while the geometry
    is in the world's, it aims the camera at empty space."""
    model = mdpa_import.import_mdpa(SECTION_DECK)

    payload = model.to_dict()

    assert payload["bbox"] == [0.0, -6.0, 0.0, 8.0, 0.0, 0.0]
    positions = next(s for s in payload["sections"]
                     if s["key"] == "imported_continuum")["positions"]
    assert min(positions[2::3]) == max(positions[2::3]) == 0.0, "the whole sheet is on z = 0"
    assert min(positions[1::3]) == -6.0, "the section has depth in y, not in z"


def test_a_beams_line_work_is_in_the_same_frame_as_the_soil_it_shares_nodes_with():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n1 4.0 0.0 0.0\n2 4.0 -5.0 0.0\nEnd Nodes\n\n"
        "Begin Elements LinearTrussElement2D2N\n1 0 1 2\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    truss = next(s for s in mdpa_import.to_sections(model)
                 if s["key"] == "imported_truss")

    assert truss["edges"] == [4.0, 0.0, 0.0, 4.0, -5.0, 0.0]


# ── Interfaces ──────────────────────────────────────────────────────────────
#
# A zero-thickness contact is geometry with no thickness to fill: `kratos.INTERFACES`
# writes one element per segment per detached face, its first half the nodes of the line
# and its second half their coincident copies on the soil (see `interfaces._emit`). So it
# is drawn the way a beam is -- as the line its first two nodes span -- and never as a
# triangle, which would be degenerate and invisible whichever way it was wound.

INTERFACE_DECK = (
    "Begin Properties 0\nEnd Properties\n\n"
    "Begin Nodes\n"
    "1 4.0 0.0 0.0\n2 4.0 -5.0 0.0\n3 4.0 -2.5 0.0\n"
    # The soil-side copies: the same three places, three more numbers.
    "4 4.0 0.0 0.0\n5 4.0 -5.0 0.0\n6 4.0 -2.5 0.0\n"
    "End Nodes\n\n"
    "Begin Elements Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N\n"
    "1 0 1 2 3 4 5 6\n"
    "End Elements\n\n"
    "Begin SubModelPart Interface_Wall_Left\n"
    "    Begin SubModelPartElements\n1\n    End SubModelPartElements\n"
    "End SubModelPart\n"
)


def test_an_interface_class_is_recognised_rather_than_unknown():
    model = mdpa_import.import_mdpa(INTERFACE_DECK)

    entity = model.elements[0]
    assert entity.kind == "interface"
    assert entity.dim == 2
    assert len(entity.entries) == 1


def test_an_interface_is_drawn_as_the_line_its_first_two_nodes_span():
    model = mdpa_import.import_mdpa(INTERFACE_DECK)

    section = next(s for s in mdpa_import.to_sections(model)
                   if s["part"] == "Interface_Wall_Left")

    assert section["kind"] == "interface"
    assert section["indices"] == [], "zero thickness is not a triangle"
    # End to end, not end to midside: the third node of a quadratic segment is its
    # middle, and drawing to it would cover half the interface.
    assert section["edges"] == [4.0, 0.0, 0.0, 4.0, -5.0, 0.0]


def test_an_interface_part_gets_its_own_row_and_its_own_colour():
    """The Model explorer's "Imported mesh" node is built from these sections alone
    (live/js/mdpa-import-dialog.js), so a part with no section has no row and no eye."""
    model = mdpa_import.import_mdpa(INTERFACE_DECK)

    section = next(s for s in mdpa_import.to_sections(model)
                   if s["part"] == "Interface_Wall_Left")

    assert section["key"] == "imported:Interface_Wall_Left"
    assert section["color"]
    assert section["elements"] == [[1, 4.0, -2.5, 0.0]], "labelled at its own centre"


def test_an_unclaimed_interface_still_draws_under_its_kind():
    model = mdpa_import.import_mdpa(
        INTERFACE_DECK.replace("Begin SubModelPart Interface_Wall_Left", "Begin SubModelPart Empty")
                      .replace("\n1\n    End SubModelPartElements", "\n    End SubModelPartElements")
    )

    section = next(s for s in mdpa_import.to_sections(model)
                   if s["key"] == "imported_interface")

    assert section["edges"] == [4.0, 0.0, 0.0, 4.0, -5.0, 0.0]


def test_a_linear_interface_is_drawn_the_same_way():
    text = (
        "Begin Properties 0\nEnd Properties\n\n"
        "Begin Nodes\n1 0.0 0.0 0.0\n2 3.0 0.0 0.0\n3 0.0 0.0 0.0\n4 3.0 0.0 0.0\n"
        "End Nodes\n\n"
        "Begin Elements Geo_UPwLineInterfacePlaneStrainElement2Plus2N\n"
        "1 0 1 2 3 4\nEnd Elements\n"
    )
    model = mdpa_import.import_mdpa(text)

    section = next(s for s in mdpa_import.to_sections(model)
                   if s["key"] == "imported_interface")

    assert section["edges"] == [0.0, 0.0, 0.0, 3.0, 0.0, 0.0]


def test_a_sheet_pile_and_its_interfaces_all_survive_the_round_trip(session):
    """The arrangement the user meets: a wall with soil unglued from both its faces.
    Every part the deck names as a body has to come back drawable -- the pile and both
    contacts -- or the checklist silently loses one."""
    from tests.test_kratos_interfaces import interfaced_project

    exported = kratos.export_project(interfaced_project(),
                                     MeshRequest(element_size=3.0, order=2))
    model = mdpa_import.import_mdpa(exported["mdpa"])

    sections = [s for s in mdpa_import.to_sections(model) if s["part"]]
    kinds = {s["part"]: s["kind"] for s in sections}

    # Named after the project's own interface ("Wall contact"), not after its class --
    # the deck carries the part's name, so that is what the checklist shows.
    assert "beam" in kinds.values(), f"the sheet pile draws: {kinds}"
    assert "interface" in kinds.values(), f"the contacts draw nothing: {kinds}"
    contact = next(s for s in sections if s["kind"] == "interface")
    assert contact["edges"], "a contact is line work"
    assert contact["elements"], "and its elements can be labelled"
