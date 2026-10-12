"""A sheet pile, translated into the wall panel it is in the solid model.

A 2D sheet pile is an `(x, z)` polyline with no out-of-plane extent at all, so the
solid model could only sweep it a nominal strip wide and there was nothing to edit: the
Selection explorer showed x and z and no y. A wall in 3D is a `Panel` -- a plan
footprint swept between two levels -- and that is what the pile becomes on the switch.

The pairing is the one `core/model/load_translation.py` already uses for a surface load and a line load:
both records are kept, linked by `derived_from`, and the dimension being left is the
one that wins. Keeping both is what lets the footprint the user drew in plan survive a
trip through the section, which has no y to remember it by.

Only a vertical pile has a panel form -- a panel *is* a vertical sweep. A raking or
stepped pile keeps the swept strip and says so.
"""

import pytest

from core.model import wall_translation
from core.model.schemas import Project
from core.model.templates import seed_project


PILE_X, PILE_TOP, PILE_TOE = 10.0, 0.0, -7.5

SECTION = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
           "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}
PILE = {"id": "beam_1", "name": "Sheet pile 1", "kind": "beam", "section": "az26",
        "points": [[PILE_X, PILE_TOP], [PILE_X, PILE_TOE]], "active": True}
RAKING = {"id": "beam_2", "name": "Sheet pile 2", "kind": "beam", "section": "az26",
          "points": [[6.0, 0.0], [9.0, -7.5]], "active": True}


def project_with(beams: list[dict], dimension: int = 2,
                 panel_sections: list[dict] | None = None) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
    payload["beam_sections"] = [SECTION]
    payload["panel_sections"] = panel_sections or []
    payload["beams"] = beams
    return Project.model_validate(payload)


def applied(project: Project, dimension: int) -> Project:
    """`project` after the switch, as the API stores it."""
    beams, sections = wall_translation.translate(project, dimension)
    payload = project.model_dump() | {"dimension": dimension}
    payload["beams"] = [b.model_dump() for b in beams]
    payload["panel_sections"] = [s.model_dump() for s in sections]
    if dimension == 3:
        payload["section_offset"] = None
    return Project.model_validate(payload)


def panel_of(project: Project):
    return next(b for b in project.beams if b.kind == "panel")


# ── Into the solid model ────────────────────────────────────────────────────

def test_a_sheet_pile_gains_a_wall_panel_in_3d():
    """The fix: in 3D the pile is a wall, and a wall has a plan footprint to edit."""
    solid = applied(project_with([PILE]), 3)

    assert sorted(b.kind for b in solid.beams) == ["beam", "panel"]


def test_the_wall_spans_the_full_out_of_plane_width_to_begin_with():
    """All the pile can say: it carries no y. The user narrows it from here."""
    solid = applied(project_with([PILE]), 3)
    panel = panel_of(solid)

    assert [point[1] for point in panel.footprint] == [solid.domain.z0, solid.domain.z1]
    assert {point[0] for point in panel.footprint} == {PILE_X}


def test_the_wall_takes_its_levels_from_the_piles_polyline():
    panel = panel_of(applied(project_with([PILE]), 3))

    assert (panel.y_top, panel.y_toe) == (PILE_TOP, PILE_TOE)


def test_the_wall_points_back_at_the_pile_and_is_named_for_its_own_kind():
    panel = panel_of(applied(project_with([PILE]), 3))

    assert panel.derived_from == "beam_1"
    assert panel.name == "Wall 1"


def test_the_wall_gets_a_section_whose_thickness_is_the_profiles_area():
    """`area` is m2 per metre run, which is a thickness in metres -- the same reduction
    `writer._shell_section_of` already writes into the deck."""
    solid = applied(project_with([PILE]), 3)
    section = solid.panel_section(panel_of(solid).section)

    pile = solid.beam_section(SECTION["id"]).variables
    assert section.variables["THICKNESS"] == pytest.approx(pile["CROSS_AREA"])
    assert [section.variables[k] for k in ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY")] \
        == [pile[k] for k in ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY")]


def test_the_pile_record_survives_the_switch():
    solid = applied(project_with([PILE]), 3)

    assert any(b.id == "beam_1" and b.kind == "beam" for b in solid.beams)


# ── Back into the section, and the round trip ───────────────────────────────

def test_a_footprint_narrowed_in_3d_survives_a_trip_through_the_section():
    """The reason both records are kept: a line in the section has no y to remember."""
    solid = applied(project_with([PILE]), 3)
    narrowed = solid.model_dump()
    for beam in narrowed["beams"]:
        if beam["kind"] == "panel":
            beam["footprint"] = [[PILE_X, 5.0], [PILE_X, 12.0]]
    solid = Project.model_validate(narrowed)

    there_and_back = applied(applied(solid, 2), 3)

    assert [p[1] for p in panel_of(there_and_back).footprint] == [5.0, 12.0]


def test_an_edit_made_in_3d_reaches_the_section():
    """What the user last edited wins, the same rule the loads follow."""
    solid = applied(project_with([PILE]), 3)
    moved = solid.model_dump()
    for beam in moved["beams"]:
        if beam["kind"] == "panel":
            beam["footprint"] = [[14.0, 0.0], [14.0, 20.0]]
            beam["y_toe"] = -9.0

    section = applied(Project.model_validate(moved), 2)

    pile = next(b for b in section.beams if b.kind == "beam")
    assert [p[0] for p in pile.points] == [14.0, 14.0]
    assert pile.points[-1][1] == -9.0


def test_an_edit_made_in_the_section_reaches_the_solid_model():
    # Down into the section first: an edit is only "made in 2D" if the project is
    # there, and translate() is a no-op when the dimension has not changed.
    section = applied(applied(project_with([PILE]), 3), 2)
    moved = section.model_dump()
    for beam in moved["beams"]:
        if beam["kind"] == "beam":
            beam["points"] = [[3.0, 0.0], [3.0, -4.0]]

    again = applied(Project.model_validate(moved), 3)
    panel = panel_of(again)

    assert {p[0] for p in panel.footprint} == {3.0}
    assert (panel.y_top, panel.y_toe) == (0.0, -4.0)


# ── The piles with no panel form ────────────────────────────────────────────

def test_a_raking_pile_gets_no_panel_and_says_so():
    """A panel is a vertical sweep; a raking pile is not one, and inventing a footprint
    for it would straighten the wall the user drew."""
    log: list[str] = []
    beams, _ = wall_translation.translate(project_with([RAKING]), 3, log)

    assert [b.kind for b in beams] == ["beam"]
    assert any("Sheet pile 2" in note for note in log), log


# ── What each dimension actually builds ─────────────────────────────────────

def test_a_translated_pair_is_built_once_in_each_dimension():
    solid = applied(project_with([PILE]), 3)

    assert [b.kind for b in solid.structures_for(3)] == ["panel"]
    assert [b.kind for b in solid.structures_for(2)] == ["beam"]


def test_an_untranslated_pile_is_still_built_in_both():
    solid = applied(project_with([RAKING]), 3)

    assert [b.kind for b in solid.structures_for(3)] == ["beam"]
    assert [b.kind for b in solid.structures_for(2)] == ["beam"]


# ── An anchor drawn in the section, on a wall built in plan ─────────────────

def test_a_plane_anchors_head_is_a_node_of_the_translated_wall():
    """The head has to be a node of the wall's *own* mesh or the tie hangs off nothing.

    Checked through the exporter rather than the B-rep, because that is what actually
    demands it: `writer._anchor_ties` resolves the head among structural nodes only,
    and raises if there is none -- a vertex of the anchor's own display line will not do.
    """
    from core.geometry import solid_model
    from core.kratos import writer
    from core.model.schemas import MeshRequest

    payload = project_with([PILE]).model_dump()
    payload["anchor_sections"] = [{"id": "strand", "name": "Strand", "E": 1.95e8,
                                   "area": 0.0006, "density": 7850.0}]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": [PILE_X, -2.0],
                           "tail": [PILE_X - 6.0, -6.0], "active": True}]
    solid = applied(Project.model_validate(payload), 3)

    with solid_model.session():
        export = writer.export_project(solid, MeshRequest(element_size=4.0, order=1))

    assert "Anchor_1" in export["mdpa"]


@pytest.mark.xfail(strict=True, reason=(
    "Known gap (alpha 1.6, plan sec 4.1): a panel narrowed off the section plane still "
    "refreshes its pile, which the section then builds. Loads already leave such a pair "
    "out (`Project.loads_for(2)`); walls need their own design because piles feed "
    "anchors and interfaces. Strict, so this fails loudly the day it is fixed."))
def test_a_panel_narrowed_clear_of_the_section_plane_is_not_built_in_the_section():
    solid = applied(project_with([PILE]), 3)
    narrowed = solid.model_dump()
    for beam in narrowed["beams"]:
        if beam["kind"] == "panel":
            beam["footprint"] = [[PILE_X, 1.0], [PILE_X, 3.0]]
    section = applied(Project.model_validate(narrowed), 2)

    assert section.cut_at() > 3.0, "the default cut is mid-domain, clear of z 1..3"
    assert [b.id for b in section.structures_for(2)] == []
