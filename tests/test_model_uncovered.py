"""User-facing model edits that are not exercised by the usual excavation."""

import pytest
from pydantic import ValidationError

from core.model import drafts, soil_models, stages
from core.model.schemas import (
    AnchorSection, BeamSection, Excavation, PanelSection, Project, Stage,
)
from core.model.templates import blank_project, seed_project
from tests.models.excavation import excavation_project


@pytest.mark.parametrize("kind, coordinates, dimension", [
    ("sheet_pile", [(5, 0)], 2),
    ("wall", [(5, 0)], 3),
    ("member", [(5, 0, 0)], 3),
])
def test_a_structure_draft_needs_a_line_not_a_single_click(kind, coordinates, dimension):
    project = blank_project().model_copy(update={"dimension": dimension})

    with pytest.raises(drafts.DraftError, match="at least two points"):
        getattr(drafts, kind)(project, coordinates)


@pytest.mark.parametrize("kind", ["wall", "member"])
def test_a_spatial_structure_draft_explains_how_to_leave_2d(kind):
    with pytest.raises(drafts.DraftError, match="switch to 3D"):
        getattr(drafts, kind)(blank_project())


@pytest.mark.parametrize("kind, coordinates", [
    ("wall", [(10, 0), (10, 11)]),
    ("member", [(10, 0, 0), (10, -5, 11)]),
])
def test_a_spatial_structure_cannot_extend_outside_the_site(kind, coordinates):
    project = blank_project().model_copy(update={"dimension": 3})

    with pytest.raises(drafts.DraftError, match="inside the model domain"):
        getattr(drafts, kind)(project, coordinates)


def test_an_anchor_needs_coordinates_in_the_projects_dimension():
    project = excavation_project(staged=False)

    with pytest.raises(drafts.DraftError, match="2 coordinates each"):
        drafts.anchor(project, head=(6, -2, 0), tail=(8, -4, 0))


def test_an_anchor_cannot_collapse_when_its_head_snaps_onto_the_wall():
    project = excavation_project(staged=False)

    with pytest.raises(drafts.DraftError, match="non-zero length"):
        drafts.anchor(project, head=(6.2, -2), tail=(6, -2))


def test_an_anchor_in_an_empty_3d_site_asks_for_a_wall_or_member():
    with pytest.raises(drafts.DraftError, match="wall or a member; create one first"):
        drafts.anchor(seed_project())


def test_an_interface_cannot_follow_a_pile_that_was_switched_off():
    project = excavation_project(staged=False)
    project = project.model_copy(update={
        "beams": [project.beams[0].model_copy(update={"active": False})],
    })

    with pytest.raises(drafts.DraftError, match="only follow a live sheet pile"):
        drafts.interface(project, structure="sheetpile")


def test_an_interface_on_its_own_line_cannot_take_a_pile_stretch():
    with pytest.raises(drafts.DraftError, match="own points runs its whole line"):
        drafts.interface(blank_project(), points=[(5, 0), (5, -5)],
                         stretch_from=(5, -1))


@pytest.mark.parametrize("kind", ["normal_load", "interface"])
def test_plane_strain_contact_and_pressure_drafts_are_refused_in_3d(kind):
    with pytest.raises(drafts.DraftError, match="plane-strain object"):
        getattr(drafts, kind)(seed_project())


def test_a_displacement_draft_names_all_three_components():
    with pytest.raises(drafts.DraftError, match="give three values"):
        drafts.displacement_condition(blank_project(), "face", face="bottom",
                                      fixed=(True, False))


def test_a_point_support_starts_at_the_centre_of_the_section():
    condition = drafts.displacement_condition(blank_project(), "point")

    assert condition.points == [(10, -7.5)]
    assert condition.fixed == (True, True, True)


@pytest.mark.parametrize("interval, message", [
    ((5, 5), "non-zero width"),
    ((-1, 5), "inside the model domain"),
])
def test_a_line_load_draft_refuses_an_unusable_interval(interval, message):
    with pytest.raises(drafts.DraftError, match=message):
        drafts.line_load(blank_project(), interval)


def test_a_line_load_draft_in_3d_explains_the_dimension_mismatch():
    with pytest.raises(drafts.DraftError, match="only in 2D"):
        drafts.line_load(seed_project())


@pytest.mark.parametrize("x, z, message", [
    ((2, 2), (2, 5), "non-zero width"),
    ((2, 5), (2, 2), "non-zero width"),
    ((-1, 5), (2, 5), "inside the model domain"),
    ((2, 5), (2, 30), "inside the model domain"),
])
def test_a_surface_load_draft_refuses_an_unusable_footprint(x, z, message):
    with pytest.raises(drafts.DraftError, match=message):
        drafts.surface_load(seed_project(), x, z)


def test_a_named_load_keeps_its_id_and_an_untyped_line_load_gets_a_usable_span():
    project = blank_project()

    point = drafts.point_load(project, id="crane")
    line = drafts.line_load(project)

    assert (point.id, point.name) == ("crane", "crane")
    assert (line.x0, line.x1, line.y) == (8, 12, 0)


def test_an_anchor_below_the_last_lift_is_installed_after_digging_not_lost():
    project = excavation_project(staged=False)
    payload = project.model_dump()
    payload["anchors"][0].update(head=(6, -9), tail=(5, -9))
    project = Project.model_validate(payload)

    sequence = stages.staged_excavation_stages(project)
    staged = Project.model_validate(project.model_dump() | {"stages": sequence})

    assert sequence[-1].id == "install_strut"
    assert sequence[-1].parent == "dig_3"
    assert sequence[-1].activate == ["strut"]
    assert "strut" not in stages.active_parts(staged, "dig_3")
    assert "strut" in stages.active_parts(staged, "install_strut")


def test_adding_a_stage_to_an_unresolved_branch_uses_the_last_stored_stage():
    project = blank_project().model_copy(update={"stages": [
        Stage(id="initial", name="Initial"),
        Stage(id="wet", name="Wet", parent="initial"),
        Stage(id="dry", name="Dry", parent="initial"),
    ]})

    added = stages.added(project)

    assert added[-1].parent == "dry"
    assert [stage.id for stage in project.stages] == ["initial", "wet", "dry"]
    assert all(new is not old for new, old in zip(added, project.stages))


def test_adding_a_stage_reuses_the_first_free_number_without_duplicating_an_id():
    project = blank_project().model_copy(update={"stages": [
        Stage(id="stage_1", name="Initial"),
        Stage(id="stage_3", name="Dig", parent="stage_1"),
    ]})

    added = stages.added(project)

    assert added[-1].id == "stage_2"
    assert added[-1].parent == "stage_3"
    assert len({stage.id for stage in added}) == len(added)


def test_interfaces_on_different_piles_may_hold_the_same_depth_range():
    payload = excavation_project(staged=False).model_dump()
    payload["beams"].append({
        **payload["beams"][0], "id": "second_pile", "name": "Second pile",
        "points": [(12, 0), (12, -12)],
    })
    payload["interfaces"].append({
        **payload["interfaces"][0], "id": "second_contact", "name": "Second contact",
        "structure": "second_pile",
    })

    project = Project.model_validate(payload)

    assert len(project.active_interfaces) == 2
    assert project.interface_path(project.interfaces[0]) == [(6, 0), (6, -12)]
    assert project.interface_path(project.interfaces[1]) == [(12, 0), (12, -12)]


def test_an_anchor_id_cannot_overwrite_a_load_in_the_part_namespace():
    payload = excavation_project(staged=False).model_dump()
    payload["anchors"][0]["id"] = "surcharge"

    with pytest.raises(ValidationError, match="anchor id collides.*surcharge"):
        Project.model_validate(payload)


@pytest.mark.parametrize("section_type, old, variable, expected", [
    (BeamSection, {"E": 200000000, "nu": 0.3, "density": 7850,
                   "area": 0.02, "inertia": 0.001, "spacing": 2},
     "YOUNG_MODULUS", 2e11),
    (AnchorSection, {"E": 200000000, "density": 7850, "area": 0.002,
                     "spacing": 2, "tension_limit": 900},
     "YOUNG_MODULUS", 2e11),
    (PanelSection, {"E": 30000000, "nu": 0.2, "density": 2400, "thickness": 0.4},
     "THICKNESS", 0.4),
])
def test_old_script_section_constructors_migrate_and_round_trip(
        section_type, old, variable, expected):
    section = section_type.model_validate({"id": "profile", "name": "Profile", **old})

    assert section.variables[variable] == expected
    assert section_type.model_validate(section.model_dump()) == section
    if isinstance(section, AnchorSection):
        assert section.tension_limit == 900000
    if not isinstance(section, PanelSection):
        assert section.spacing == 2


@pytest.mark.parametrize("levels, message", [
    ([-2, -2], "levels must descend"),
    ([-4, -2], "levels must descend"),
    ([-2, float("-inf")], "levels must all be finite"),
])
def test_excavation_lifts_must_represent_successively_deeper_finite_floors(levels, message):
    with pytest.raises(ValidationError, match=message):
        Excavation(x0=0, x1=5, z0=0, z1=5, levels=levels)


@pytest.mark.parametrize("law, dimension", [
    ("GeoMohrCoulombWithTensionCutOff2D", 2),
    ("GeoMohrCoulombWithTensionCutOff3D", 3),
    ("UserSuppliedSoilLaw", None),
])
def test_soil_law_dimension_recognises_retired_names_without_guessing_custom_laws(
        law, dimension):
    assert soil_models.law_dimension(law) == dimension


def test_an_unknown_soil_model_lists_the_supported_choices():
    with pytest.raises(ValueError, match="there is no soil model 'unknown'; there are:"):
        soil_models.law("unknown", 2)
