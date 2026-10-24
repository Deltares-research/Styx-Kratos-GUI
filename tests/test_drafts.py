"""`core.model.drafts`: what a new record starts as, the way the GUI starts it.

The command line adds layers, materials and soil volumes without the GUI's
dialogs, so what those dialogs fill in for a new one has to exist in Python as well. The
numbers are the GUI's own -- `frontend/js/property-sets.js` and `material-library.js` --
and `tests/test_draft_parity.py` holds the two to one document.
"""

from __future__ import annotations

import math

import pytest

from core import session
from core.model import drafts, units
from core.model.schemas import (SOIL_LAW_PAIRS, Anchor, AnchorSection, Beam, BeamSection,
                                DimensionUpdate, Interface, InterfaceSection, LineLoad,
                                Material, Member, NormalLoad, Panel, PanelSection, PointLoad,
                                SpaceAnchor, SurfaceLoad)
from core.model.templates import blank_project, seed_project
from tests.models.excavation import excavation_project


def test_a_new_soil_takes_the_linear_elastic_law_of_the_dimension():
    for dimension in (2, 3):
        law = drafts.SOIL_LAWS[dimension]
        assert SOIL_LAW_PAIRS[law][0] == dimension


def test_a_new_soil_is_a_loose_drained_sand_in_the_project_s_units():
    project = blank_project()

    material, notes = drafts.soil(project, "sand")

    assert isinstance(material, Material)
    assert material.constitutive_law == drafts.SOIL_LAWS[2]
    assert material.variables == drafts.SOIL_DEFAULTS_SI
    assert (material.id, material.name, material.color) == ("sand", "sand", drafts.SOIL_COLOR)
    assert notes == []


def test_a_new_soil_in_a_kn_project_is_stated_in_kn():
    project = blank_project().model_copy(update={"unit_system": "kN"})

    material, _ = drafts.soil(project, "sand")

    expected, _ = units.convert_variables(drafts.SOIL_DEFAULTS_SI, "SI", "kN")
    assert material.variables == expected
    assert material.variables["YOUNG_MODULUS"] == pytest.approx(1.0e4)


def test_a_soil_can_start_from_a_library_preset():
    material, _ = drafts.soil(blank_project(), "clay", preset="m3")

    preset = drafts.preset("m3")
    assert material.name == preset["name"]
    assert material.color == preset["color"]
    assert material.variables == preset["variables"]
    assert (material.r_inter, material.interface_permeability) == (0.5, "Impermeable")


def test_an_unknown_preset_says_which_there_are():
    with pytest.raises(drafts.DraftError, match="m1, m2, m3, m4, m5, m6"):
        drafts.soil(blank_project(), "clay", preset="m9")


def test_the_library_is_the_gui_s_six_soils_in_si():
    assert [p["id"] for p in drafts.LIBRARY] == ["m1", "m2", "m3", "m4", "m5", "m6"]
    assert drafts.preset("m6")["variables"]["YOUNG_MODULUS"] == 2.0e9


def test_a_new_layer_goes_below_the_last_one():
    project = seed_project()

    layer = drafts.layer(project, "L3", "m1", thickness=5.0)

    assert layer.top == project.layers[-1].bottom
    assert layer.bottom == layer.top - 5.0
    assert layer.name == "L3"


def test_the_first_layer_starts_at_the_top_of_the_domain():
    project = blank_project()

    layer = drafts.layer(project, "L1", "m1", bottom=-6.0)

    assert (layer.top, layer.bottom) == (project.domain.y_top, -6.0)


def test_the_first_layer_of_a_raised_domain_starts_at_its_top():
    project = blank_project()
    project = project.model_copy(update={"domain": project.domain.model_copy(
        update={"y_top": 10.0, "y_bottom": 0.0})})

    layer = drafts.layer(project, "L1", "m1")

    assert (layer.top, layer.bottom) == (10.0, 5.0)


def test_a_section_outline_is_swept_across_the_whole_model():
    """`soil-volume-dialog.js` `prismFor`: a 2D body is an outline in the x-y plane,
    swept along z across the domain, so every section plane cuts it."""
    project = blank_project()
    domain = project.domain

    recipe = drafts.section_prism(project, [(0, 0), (3, 2), (6, 0)])

    assert recipe["kind"] == "polygon_extrude"
    assert recipe["vertices"] == [[0, 0, domain.z0], [3, 2, domain.z0], [6, 0, domain.z0]]
    assert recipe["extrusion"] == [0, 0, domain.z1 - domain.z0]


def test_a_free_id_is_the_first_number_not_taken():
    assert drafts.free_id(["L1", "L2", "L4"], "L") == "L3"
    assert drafts.free_id([], "L") == "L1"


# ── Structures: what beams.js, anchors.js, interfaces.js, loads.js and
#    normal-loads.js start a new one as ─────────────────────────────────────────

def _plane_strain():
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    return project


def test_a_new_beam_section_is_an_az26_profile_per_metre_run():
    section = drafts.section(blank_project(), "beam", "az26")

    assert isinstance(section, BeamSection)
    assert (section.id, section.name, section.spacing) == ("az26", "Sheet pile section", 1.0)
    assert section.constitutive_law == "TimoshenkoBeamElasticConstitutiveLaw"
    assert section.variables == drafts.SECTION_DEFAULTS_SI["beam"]["variables"]


def test_a_new_tendon_states_its_working_limit_in_the_project_s_force_unit():
    project = blank_project().model_copy(update={"unit_system": "kN"})

    tendon = drafts.section(project, "anchor", "tendon")

    assert isinstance(tendon, AnchorSection)
    assert (tendon.spacing, tendon.tension_limit, tendon.compression_limit) == (2.5, 900.0, None)
    assert tendon.variables["DENSITY"] == pytest.approx(7.85)


def test_a_new_interface_section_reduces_the_first_soil():
    project = seed_project()

    contact = drafts.section(project, "interface", "contact")

    assert isinstance(contact, InterfaceSection)
    assert contact.material == project.materials[0].id
    assert (contact.r_inter, contact.virtual_thickness) == (0.7, 0.01)


def test_a_new_wall_section_is_a_shell_of_forty_centimetres():
    section = drafts.section(blank_project(), "panel", "wall")

    assert isinstance(section, PanelSection)
    assert section.variables["THICKNESS"] == 0.4


def test_a_section_kind_that_is_not_there_says_which_there_are():
    with pytest.raises(drafts.DraftError, match="beam, panel, anchor, interface"):
        drafts.section(blank_project(), "strut", "s1")


def test_a_new_sheet_pile_runs_down_the_middle_to_half_the_depth():
    project = _plane_strain()
    d = project.domain

    pile = drafts.sheet_pile(project)

    assert isinstance(pile, Beam)
    assert pile.points == [(12.5, d.y_top), (12.5, -12.5)]
    assert (pile.id, pile.name, pile.section) == ("beam_1", "Sheet pile 1", "beamsection_1")


def test_a_sheet_pile_takes_the_first_profile_there_is():
    project = excavation_project(staged=False)

    pile = drafts.sheet_pile(project, [(20, 0), (20, -6)])

    assert (pile.section, pile.id) == ("sheetpile", "beam_1")


def test_a_sheet_pile_outside_the_model_or_in_3d_is_refused():
    with pytest.raises(drafts.DraftError, match="inside the model domain"):
        drafts.sheet_pile(_plane_strain(), [(12, 0), (12, -40)])
    with pytest.raises(drafts.DraftError, match="2D section object"):
        drafts.sheet_pile(seed_project())
    with pytest.raises(drafts.DraftError, match="same point twice"):
        drafts.sheet_pile(_plane_strain(), [(12, 0), (12, 0)])
    with pytest.raises(drafts.DraftError, match="part of it has to be in the soil"):
        drafts.sheet_pile(_plane_strain(), [(12, 5), (12, 0)])


def test_a_sheet_pile_may_stand_out_above_the_ground():
    pile = drafts.sheet_pile(_plane_strain(), [(12, 5), (12, -7.5)])

    assert pile.points == [(12, 5), (12, -7.5)]


def test_a_point_load_above_the_ground_snaps_onto_a_pile_or_is_refused():
    project = _plane_strain()
    pile = drafts.sheet_pile(project, [(12, 5), (12, -7.5)])
    project = project.model_copy(update={
        "beams": [pile], "beam_sections": [drafts.section_for(project, pile)]})

    load = drafts.point_load(project, (12.4, 4.8))

    assert (load.x, load.y) == (12, 4.8)
    with pytest.raises(drafts.DraftError, match="or be on a sheet pile"):
        drafts.point_load(project, (20, 5))


def test_a_new_wall_is_swept_from_the_ground_to_half_the_depth():
    project = seed_project()

    wall = drafts.wall(project)

    assert isinstance(wall, Panel)
    assert wall.footprint == [(12.5, 6.25), (12.5, 18.75)]
    assert (wall.y_top, wall.y_toe) == (0.0, -12.5)
    assert (wall.id, wall.name, wall.section) == ("panel_1", "Wall 1", "panelsection_1")


def test_a_new_member_stands_vertical_in_the_middle_of_the_site():
    member = drafts.member(seed_project())

    assert isinstance(member, Member)
    assert member.points == [(12.5, 0.0, 12.5), (12.5, -12.5, 12.5)]
    assert (member.id, member.section) == ("member_1", "beamsection_1")


def test_a_new_anchor_rakes_back_from_a_quarter_down_the_pile():
    """anchors.js `draft`: 10 m at 35 degrees, into the longer side of the domain."""
    project = excavation_project(staged=False)

    anchor = drafts.anchor(project)

    assert isinstance(anchor, Anchor)
    assert anchor.head == (6.0, -3.0)
    assert anchor.tail == pytest.approx((6 + 10 * math.cos(math.radians(35)),
                                         -3 - 10 * math.sin(math.radians(35))), abs=1e-6)
    assert (anchor.id, anchor.section) == ("anchor_1", "strand")


def test_an_anchor_head_near_a_pile_is_snapped_onto_it():
    anchor = drafts.anchor(excavation_project(staged=False), head=(6.4, -2.0),
                           tail=(20.0, -8.0))

    assert anchor.head == (6.0, -2.0)
    assert anchor.tail == (20.0, -8.0)


def test_an_anchor_head_given_alone_takes_the_usual_rake():
    anchor = drafts.anchor(excavation_project(staged=False), head=(6.0, -2.0))

    assert anchor.tail == pytest.approx((6 + 10 * math.cos(math.radians(35)),
                                         -2 - 10 * math.sin(math.radians(35))), abs=1e-6)


def test_an_anchor_head_far_from_any_pile_or_with_no_pile_is_refused():
    with pytest.raises(drafts.DraftError, match="placed on a sheet pile"):
        drafts.anchor(excavation_project(staged=False), head=(10.0, -2.0), tail=(20, -8))
    with pytest.raises(drafts.DraftError, match="create one first"):
        drafts.anchor(_plane_strain())


def test_a_3d_anchor_hangs_from_a_wall():
    project = seed_project()
    wall = drafts.wall(project)
    project = project.model_copy(update={"beams": [wall],
                                         "panel_sections": [drafts.section(project, "panel",
                                                                           wall.section)]})

    anchor = drafts.anchor(project)

    assert isinstance(anchor, SpaceAnchor)
    assert anchor.head == (12.5, -3.125, 12.5)


def test_a_new_interface_follows_the_first_live_pile_on_both_sides():
    interface = drafts.interface(excavation_project(staged=False))

    assert isinstance(interface, Interface)
    assert (interface.structure, interface.points, interface.side) == ("sheetpile", None, "both")
    assert (interface.id, interface.section) == ("interface_1", "contact")


def test_with_no_pile_a_new_interface_is_a_free_line_detaching_its_left():
    interface = drafts.interface(_plane_strain())

    assert interface.structure is None
    assert interface.points == [(12.5, 0.0), (12.5, -12.5)]
    assert (interface.side, interface.section) == ("left", "interfacesection_1")


def test_a_new_normal_load_is_a_uniform_zero_pressure_down_the_middle():
    load = drafts.normal_load(_plane_strain())

    assert isinstance(load, NormalLoad)
    assert load.points == [(12.5, 0.0), (12.5, -12.5)]
    assert (load.fluid_pressure_type, load.pressure) == ("Uniform", 0.0)
    assert (load.id, load.name) == ("normalload_1", "Normal load 1")


def test_new_loads_are_twenty_kilonewtons_down_in_the_project_s_units():
    project = _plane_strain()

    point = drafts.point_load(project, (5.0, 0.0))
    line = drafts.line_load(project, (2.0, 8.0))
    surface = drafts.surface_load(seed_project().model_copy(update={"unit_system": "kN"}))

    assert isinstance(point, PointLoad) and point.components == (0, -20000.0)
    assert isinstance(line, LineLoad) and (line.x0, line.x1, line.y) == (2.0, 8.0, 0.0)
    assert line.components == (0, -20000.0)
    assert isinstance(surface, SurfaceLoad) and surface.components == (0, -20.0, 0)
    assert (point.id, line.id) == ("load_1", "load_1")
    assert (point.name, line.name) == ("PointLoad_1", "LineLoad_1")


def test_a_load_of_the_other_dimension_is_refused():
    with pytest.raises(drafts.DraftError, match="2D point load"):
        drafts.point_load(seed_project(), (5.0, 0.0))
    with pytest.raises(drafts.DraftError, match="3D model domain"):
        drafts.surface_load(_plane_strain())


def test_a_structure_brings_its_default_section_when_its_library_lacks_it():
    project = _plane_strain()
    pile = drafts.sheet_pile(project)

    section = drafts.section_for(project, pile)

    assert isinstance(section, BeamSection) and section.id == "beamsection_1"
    assert drafts.section_for(excavation_project(staged=False),
                              drafts.sheet_pile(excavation_project(staged=False))) is None
