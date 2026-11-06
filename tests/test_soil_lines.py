"""Lines and sheet piles split the soil layers into bodies (`Project.soil_bodies`)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core import scripting, session
from core.geometry import solid_model
from core.kratos import writer
from core.model import drafts, script_writer
from core.model.schemas import (Beam, BeamSection, Domain, Line, Material, Project, SoilBody,
                                SoilLayer, Stage)

DOMAIN = Domain(x0=0.0, x1=20.0, z0=0.0, z1=10.0, y_top=0.0, y_bottom=-12.0)

PIT_SIDE = Line(id="pit_side", name="Pit side", points=[(5.0, 0.0), (5.0, -4.0)])
FLOOR = Line(id="floor", name="Floor", points=[(0.0, -2.0), (5.0, -2.0)])


def material(id: str) -> Material:
    return Material(id=id, name=f"Soil {id}", constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables={"YOUNG_MODULUS": 1e6, "POISSON_RATIO": 0.3, "DENSITY_SOLID": 2000.0,
                               "POROSITY": 0.0, "PERMEABILITY_XX": 1e-5, "PERMEABILITY_YY": 1e-5,
                               "PERMEABILITY_XY": 0.0, "DENSITY_WATER": 1000.0,
                               "BULK_MODULUS_SOLID": 1e10, "BULK_MODULUS_FLUID": 2e9,
                               "DYNAMIC_VISCOSITY": 0.001},
                    color="#c4a86a")


def model(**fields) -> Project:
    return Project(**{
        "name": "Lines", "dimension": 2, "domain": DOMAIN,
        "materials": [material("sand"), material("grout")],
        "layers": [SoilLayer(id="top", name="Top", mat="sand", top=0.0, bottom=-4.0),
                   SoilLayer(id="low", name="Low", mat="sand", top=-4.0, bottom=-12.0)],
        **fields})


def wall(points=((5.0, 0.0), (5.0, -6.0)), **fields) -> dict:
    return {"beam_sections": [BeamSection(id="s", name="S", variables={
        "YOUNG_MODULUS": 2e11, "POISSON_RATIO": 0.0, "DENSITY": 7850.0, "CROSS_AREA": 0.01,
        "I33": 1e-4, "AREA_EFFECTIVE_Y": 0.01})],
            "beams": [Beam(id="pile", name="Pile", section="s", points=list(points), **fields)]}


def edited(project: Project, **fields) -> Project:
    """The project after an edit, as every edit makes one: dumped, changed and validated."""
    payload = project.model_dump()
    payload.update(fields)
    return Project.model_validate(payload)


# ── Which bodies ─────────────────────────────────────────────────────────────────


def test_a_model_without_lines_keeps_one_body_per_layer():
    project = model()
    assert project.soil_body_keys == ["soil_top", "soil_low"]
    assert project.bodies == []
    assert "lines" not in project.model_dump() and "bodies" not in project.model_dump()


def test_a_line_across_a_layer_gives_every_piece_a_new_key_and_name():
    project = model(lines=[PIT_SIDE])
    assert project.soil_body_keys == ["soil_top__part1", "soil_top__part2", "soil_low"]
    assert project.soil_body_labels == {"soil_top__part1": "Top · Part 1",
                                        "soil_top__part2": "Top · Part 2",
                                        "soil_low": "Low"}
    assert [(b.layer, b.id, b.name) for b in project.bodies] == [
        ("top", "part1", "Part 1"), ("top", "part2", "Part 2")]
    assert "soil_top" not in project.part_keys()
    assert "soil_top" in project.soil_part_keys()     # the whole layer, for a condition


def test_a_line_crossing_two_layers_cuts_both():
    line = Line(id="l", name="L", points=[(5.0, 0.0), (5.0, -12.0)])
    assert model(lines=[line]).soil_body_keys == [
        "soil_top__part1", "soil_top__part2", "soil_low__part1", "soil_low__part2"]


def test_a_line_that_stops_in_the_soil_cuts_nothing():
    project = model(lines=[Line(id="l", name="L", points=[(5.0, 0.0), (5.0, -3.0)])])
    assert project.soil_body_keys == ["soil_top", "soil_low"]
    assert project.idle_lines() == ["l"]


def test_a_line_that_cuts_is_not_idle():
    assert model(lines=[PIT_SIDE]).idle_lines() == []


def test_a_sheet_pile_cuts_the_layer_it_crosses_and_not_the_one_it_ends_in():
    assert model(**wall()).soil_body_keys == ["soil_top__part1", "soil_top__part2", "soil_low"]


def test_a_sheet_pile_that_is_switched_off_still_cuts_so_keys_stay():
    assert model(**wall(active=False)).soil_body_keys == model(**wall()).soil_body_keys


def test_a_pile_and_two_lines_make_the_three_lifts_of_a_pit():
    project = model(**wall(), lines=[
        Line(id="floor_1", name="F1", points=[(0.0, -1.0), (5.0, -1.0)]),
        Line(id="floor_2", name="F2", points=[(0.0, -2.0), (5.0, -2.0)])])
    assert len([k for k in project.soil_body_keys if k.startswith("soil_top__")]) == 4
    assert "soil_low" in project.soil_body_keys


# ── Keys stay when lines change ──────────────────────────────────────────────────


def test_another_line_leaves_the_keys_there_are():
    before = model(lines=[PIT_SIDE])
    points = {b.id: tuple(b.point) for b in before.bodies}
    after = edited(before, lines=[PIT_SIDE.model_dump(), FLOOR.model_dump()])
    assert set(before.soil_body_keys) < set(after.soil_body_keys)
    assert len(after.soil_body_keys) == len(before.soil_body_keys) + 1
    for body in after.bodies:
        if body.id in points:
            assert tuple(body.point) == points[body.id]


def test_a_renamed_body_keeps_its_name_when_another_line_comes():
    before = model(lines=[PIT_SIDE])
    named = [{**b.model_dump(), "name": "Pit" if b.id == "part1" else b.name}
             for b in before.bodies]
    after = edited(before, bodies=named, lines=[PIT_SIDE.model_dump(), FLOOR.model_dump()])
    assert "Top · Pit" in after.soil_body_labels.values()


def test_a_save_and_a_load_give_the_same_bodies():
    project = model(lines=[PIT_SIDE, FLOOR])
    again = Project.model_validate(project.model_dump(mode="json"))
    assert again.soil_body_keys == project.soil_body_keys
    assert again.bodies == project.bodies


def test_a_stage_naming_a_layer_names_each_of_its_pieces_when_it_is_cut():
    stage = Stage(id="s", name="S", deactivate=["soil_top"])
    project = edited(model(stages=[stage]), lines=[PIT_SIDE.model_dump()])
    assert project.stages[0].deactivate == ["soil_top__part1", "soil_top__part2"]
    assert stage.deactivate == ["soil_top"]


def test_removing_the_last_cut_gives_the_layer_its_key_back():
    project = edited(model(lines=[PIT_SIDE]), lines=[])
    assert project.soil_body_keys == ["soil_top", "soil_low"]
    assert project.bodies == []


def test_removing_a_line_a_stage_needs_is_refused_and_names_the_part():
    project = model(lines=[PIT_SIDE], stages=[
        Stage(id="s", name="S", deactivate=["soil_top__part1"])])
    with pytest.raises(ValidationError, match="soil_top__part1"):
        edited(project, lines=[])


def test_two_pieces_that_merge_keep_the_first_record():
    project = model(lines=[PIT_SIDE, FLOOR])
    assert len(project.bodies) == 3
    merged = edited(project, lines=[PIT_SIDE.model_dump()])
    assert len(merged.bodies) == 2


def test_a_record_can_name_a_body_in_a_script():
    project = model(lines=[PIT_SIDE], bodies=[
        SoilBody(id="pit", name="The pit", layer="top", point=(2.5, -2.0))])
    assert "soil_top__pit" in project.soil_body_keys
    assert project.soil_body_labels["soil_top__pit"] == "Top · The pit"
    assert len(project.soil_body_keys) == 3


def test_a_body_id_with_the_key_separator_is_refused():
    with pytest.raises(ValidationError, match="__"):
        SoilBody(id="a__b", name="A", layer="top", point=(1.0, -1.0))


def test_a_line_needs_two_different_points():
    with pytest.raises(ValidationError, match="two points"):
        Line(id="l", name="L", points=[(0.0, 0.0)])
    with pytest.raises(ValidationError, match="repeats"):
        Line(id="l", name="L", points=[(0.0, 0.0), (0.0, 0.0)])


def test_a_duplicate_line_id_is_refused():
    with pytest.raises(ValidationError, match="duplicate"):
        model(lines=[PIT_SIDE, PIT_SIDE])


# ── A body's material ────────────────────────────────────────────────────────────


def test_a_body_takes_its_layers_material_until_it_is_given_one():
    project = model(lines=[PIT_SIDE])
    assert project.soil_body_materials == {"soil_top__part1": "sand", "soil_top__part2": "sand",
                                           "soil_low": "sand"}


def test_a_body_can_have_its_own_material():
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", material="grout")
    assert project.soil_body_materials["soil_top__part1"] == "grout"
    assert project.soil_body_materials["soil_top__part2"] == "sand"
    back = session.update_body(project, "soil_top__part1", material=None)
    assert back.soil_body_materials["soil_top__part1"] == "sand"


def test_a_body_with_an_unknown_material_is_refused():
    with pytest.raises(ValidationError, match="nothing"):
        model(lines=[PIT_SIDE], bodies=[
            SoilBody(id="pit", name="P", layer="top", point=(2.5, -2.0), mat="nothing")])


def test_a_material_a_body_uses_cannot_be_removed():
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", material="grout")
    with pytest.raises(ValidationError, match="grout"):
        session.remove_material(project, "grout")


# ── The edits ────────────────────────────────────────────────────────────────────


def test_a_new_line_starts_as_the_gui_starts_one():
    line = drafts.line(model(), [(0.0, -2.0), (20.0, -2.0)])
    assert (line.id, line.name) == ("line_1", "Line 1")
    assert drafts.line(model(lines=[line])).id == "line_2"


def test_a_line_can_be_added_changed_and_removed():
    project = session.add_line(model(), PIT_SIDE)
    assert len(project.soil_body_keys) == 3
    project = session.update_line(project, "pit_side", name="The side",
                                  points=[(6.0, 0.0), (6.0, -4.0)])
    assert project.lines[0].name == "The side"
    assert session.remove_line(project, "pit_side").soil_body_keys == ["soil_top", "soil_low"]


def test_an_edit_on_a_line_there_is_not_is_refused():
    with pytest.raises(session.UnknownRecord):
        session.remove_line(model(), "nothing")
    with pytest.raises(session.EditRefused, match="pit_side"):
        session.add_line(model(lines=[PIT_SIDE]), PIT_SIDE)


def test_a_line_that_splits_nothing_gets_a_note():
    idle = Line(id="idle", name="Idle", points=[(5.0, 0.0), (5.0, -3.0)])
    project = session.add_line(model(), idle)
    assert session.edit_notes(model(), project) == [
        "Line Idle splits no soil: a line has to cross a soil layer from one edge to another."]
    assert session.edit_notes(project, project) == []


def test_a_body_can_be_renamed():
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", name="Pit")
    assert project.soil_body_labels["soil_top__part1"] == "Top · Pit"


def test_a_body_that_is_not_there_cannot_be_edited():
    with pytest.raises(session.UnknownPart):
        session.update_body(model(), "soil_top__part1", name="Pit")


# ── The deck ─────────────────────────────────────────────────────────────────────


def deck_of(project: Project) -> dict:
    return writer.export_project(project)


def test_each_body_is_a_sub_model_part_named_after_its_layer_and_name():
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", name="The pit")
    mdpa = deck_of(project)["mdpa"]
    assert "Begin SubModelPart Top_The_pit" in mdpa
    assert "Begin SubModelPart Top_Part_2" in mdpa
    assert "Begin SubModelPart Low" in mdpa
    assert "Begin SubModelPart Top\n" not in mdpa


def test_a_body_writes_its_own_material():
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", material="grout",
                                  name="Grouted")
    deck = deck_of(project)
    assert "Top_Grouted" in deck["materials"]
    assert "Top_Part_2" in deck["materials"]


def test_a_body_with_its_own_material_is_drawn_in_its_colour():
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", material="grout")
    assert project.material(project.soil_body_materials["soil_top__part1"]).id == "grout"


# ── The geometry ─────────────────────────────────────────────────────────────────


def test_each_piece_is_its_own_face_with_its_own_area():
    project = model(lines=[PIT_SIDE, FLOOR])
    with solid_model.session():
        built = solid_model.build_geometry(project)
    assert built.dim == 2
    areas = {key: built.mass[key] for key in project.soil_body_keys}
    assert sum(areas.values()) == pytest.approx(20.0 * 12.0)
    assert sorted(round(area) for key, area in areas.items() if key != "soil_low") == [10, 10, 60]


def test_a_solid_model_has_the_same_bodies_swept_across_the_domain():
    project = model(lines=[PIT_SIDE, FLOOR], dimension=3)
    with solid_model.session():
        built = solid_model.build_geometry(project)
    assert built.dim == 3
    assert {key: bool(built.volumes[key]) for key in project.soil_body_keys} == {
        key: True for key in project.soil_body_keys}
    assert sum(built.mass[key] for key in project.soil_body_keys) == pytest.approx(
        20.0 * 12.0 * 10.0)


def test_a_closed_line_inside_a_layer_is_a_lens_with_soil_around_it():
    lens = Line(id="lens", name="Lens", points=[(2.0, -5.0), (4.0, -5.0), (4.0, -7.0), (2.0, -7.0),
                                                (2.0, -5.0)])
    project = model(lines=[lens])
    with solid_model.session():
        built = solid_model.build_geometry(project)
    areas = sorted(built.mass[key] for key in project.soil_body_keys if key != "soil_top")
    assert areas == [pytest.approx(4.0), pytest.approx(156.0)]


def test_a_mesh_size_on_a_layer_stays_when_a_line_cuts_it():
    sized = edited(model(), mesh={"element_size": 2.0, "body_sizes": {"soil_top": 0.5}})
    assert session.add_line(sized, PIT_SIDE).mesh.body_sizes == {"soil_top": 0.5}


# ── The stages and the deck together ─────────────────────────────────────────────


def staged() -> Project:
    project = model(lines=[PIT_SIDE, FLOOR])
    lift = next(key for key, _, top, _ in project.soil_bodies() if top == 0.0
                and project.split_soil()[0].key == key)
    return edited(project, stages=[
        Stage(id="first", name="First").model_dump(),
        Stage(id="dig", name="Dig", parent="first", deactivate=[lift]).model_dump()])


def test_a_body_a_stage_switches_off_takes_its_stretch_of_the_edge_with_it():
    project = staged()
    lift = project.stages[1].deactivate[0]
    name = writer._part_names(project)[lift]
    assert f"Begin SubModelPart {name}_Left_Edge" in deck_of(project)["mdpa"]


def test_a_body_no_stage_switches_off_leaves_the_edge_whole():
    project = model(lines=[PIT_SIDE, FLOOR])
    assert "Left_Edge" in deck_of(project)["mdpa"]
    assert "Part_1_Left_Edge" not in deck_of(project)["mdpa"]


# ── A model script ───────────────────────────────────────────────────────────────


def test_a_model_script_writes_the_lines_and_the_bodies(tmp_path):
    project = session.update_body(model(lines=[PIT_SIDE]), "soil_top__part1", name="The pit")
    path = tmp_path / "model.py"
    path.write_text(script_writer.script(project, folder=tmp_path), encoding="utf-8")
    again = scripting.load_project(path)
    assert again.soil_body_labels == project.soil_body_labels
    assert again.lines == project.lines
