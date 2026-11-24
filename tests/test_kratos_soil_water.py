"""The water of each soil: the phreatic line, a head line, or interpolated.

A stage has one phreatic line on at most. On the whole soil or drawn on a line, it is
every soil's water, unless the soil takes another (`Project.soil_water`): a head line --
a sloping polyline, the head of an aquifer -- which acts only on the soils that take it,
or `interpolate`, which writes Kratos' `Interpolate_Line` on the soil so it takes the
pressure of the soils above and below it, interpolated -- an aquitard between two waters.
"""

from __future__ import annotations

import json

import pytest

from core import session
from core.geometry import solid_model
from core.kratos import condition_checks, writer
from core.model import migration
from core.model.schemas import (INTERPOLATE, ConditionsUpdate, MeshRequest, Project,
                                WaterPressureCondition)
from core.model.templates import seed_project
from core.session import EditRefused

MESH = MeshRequest(element_size=3.0, order=1)

PHREATIC = {"id": "phreatic", "name": "Phreatic line", "kind": "water_pressure",
            "on": "domain", "fluid_pressure_type": "Phreatic_Multi_Line",
            "x_coordinates": [0.0, 25.0], "y_coordinates": [-1.0, -1.0]}
HEAD = {"id": "head", "name": "Aquifer head", "kind": "water_pressure", "on": "domain",
        "fluid_pressure_type": "Head_Line", "x_coordinates": [0.0, 25.0],
        "y_coordinates": [1.0, 3.0]}
LEVEL = {"id": "level", "name": "Level", "kind": "water_pressure", "on": "domain",
         "fluid_pressure_type": "Hydrostatic", "reference_coordinate": -3.0}


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


def layered(conditions=(PHREATIC, HEAD), soil_water=None, **changes) -> Project:
    """A 2D section of sand over clay over an aquifer, 25 m wide, held by its supports,
    with `conditions` and each soil's water."""
    p = seed_project().model_dump()
    mat = p["layers"][0]["mat"]
    p.update({"dimension": 2, "section_offset": 12.5, **changes})
    p["layers"] = [
        {"id": "L1", "name": "Sand", "mat": mat, "top": 0, "bottom": -5},
        {"id": "L2", "name": "Clay", "mat": mat, "top": -5, "bottom": -10},
        {"id": "L3", "name": "Aquifer", "mat": mat, "top": -10, "bottom": -25},
    ]
    p["boundary_conditions"] = [c for c in p["boundary_conditions"]
                                if c["kind"] == "displacement"] + [dict(c) for c in conditions]
    p["soil_water"] = soil_water or {}
    return Project.model_validate(p)


def aquifer(**changes) -> Project:
    """The aquifer on its own head, the clay interpolated between it and the sand."""
    return layered(soil_water={"soil_L3": "head", "soil_L2": INTERPOLATE}, **changes)


def water(export: dict, stage: str | None = None) -> list[dict]:
    doc = json.loads(export["project_parameters"])
    stage = stage or next(iter(doc["stages"]))
    processes = doc["stages"][stage]["stage_settings"]["processes"]
    return [p["Parameters"] for p in processes["constraints_process_list"]
            if p["Parameters"].get("variable_name") == "WATER_PRESSURE"]


# ── The project ──────────────────────────────────────────────────────────────

def test_a_stage_has_one_phreatic_line():
    second = dict(PHREATIC, id="second", name="Second", y_coordinates=[-3.0, -3.0])
    with pytest.raises(ValueError, match="'Phreatic line' and 'Second' are both on in "
                                         "this model, which has no stages"):
        layered((PHREATIC, second))
    with pytest.raises(ValueError, match="both on in stage 'First'"):
        layered((PHREATIC, second),
                stages=[{"id": "s1", "name": "First"},
                        {"id": "s2", "name": "Second", "parent": "s1"}])


def test_a_later_stage_may_lower_the_phreatic_line():
    """A pit pumped dry: the second line comes on as the first goes off."""
    second = drawn(dict(PHREATIC, id="second", name="Second", y_coordinates=[-3.0, -3.0]))
    project = layered((PHREATIC, second),
                      stages=[{"id": "s1", "name": "First", "deactivate": ["second"]},
                              {"id": "s2", "name": "Second", "parent": "s1",
                               "activate": ["second"], "deactivate": ["phreatic"]}])
    assert [line.id for line in project.phreatic_lines()] == ["phreatic", "second"]
    assert all(project.on_the_whole_soil(line) for line in project.phreatic_lines())


def test_a_phreatic_line_comes_with_the_stages_that_switch_it():
    """Made in a later stage: neither the line nor the stages alone is a project, so the
    GUI sends both in one edit."""
    stages = [{"id": "s1", "name": "First"}, {"id": "s2", "name": "Second", "parent": "s1"}]
    project = layered((PHREATIC,), stages=stages)
    second = drawn(dict(PHREATIC, id="second", name="Second", y_coordinates=[-3.0, -3.0]))
    lines = project.model_dump()["boundary_conditions"] + [second]
    with pytest.raises(ValueError, match="both on in stage 'First'"):
        session.replace_conditions(project, ConditionsUpdate(boundary_conditions=lines))
    switched = [dict(stages[0], deactivate=["second"]),
                dict(stages[1], activate=["second"], deactivate=["phreatic"])]
    edited = session.replace_conditions(project, ConditionsUpdate(boundary_conditions=lines,
                                                                  stages=switched))
    assert [line.id for line in edited.phreatic_lines()] == ["phreatic", "second"]
    assert edited.stages[1].deactivate == ["phreatic"]
    with pytest.raises(EditRefused, match="cannot remove a condition that a stage still"):
        session.replace_conditions(edited, ConditionsUpdate(
            boundary_conditions=lines[:-1]))
    dropped = session.replace_conditions(edited, ConditionsUpdate(
        boundary_conditions=lines[:-1], stages=stages))
    assert [line.id for line in dropped.phreatic_lines()] == ["phreatic"]


def test_a_phreatic_multi_line_on_a_face_is_not_a_second_phreatic_line():
    """A start phreatic line on the soil and a fixed one on a face, as on main."""
    face = dict(PHREATIC, id="face", name="Face", on="face", face="left")
    project = layered((dict(PHREATIC, is_fixed=False), face))
    assert [line.id for line in project.phreatic_lines()] == ["phreatic"]


def test_a_condition_cannot_be_called_interpolate():
    with pytest.raises(ValueError, match="cannot be called 'interpolate'"):
        layered((PHREATIC, dict(HEAD, id=INTERPOLATE)))


def test_a_soil_takes_a_water_line_and_nothing_else_of_its_own():
    """Any water line, the phreatic one too: a stage may make another line its phreatic
    line (`Stage.phreatic_line`), and this one a head line there, which the soil then
    takes. Where it is the phreatic line, the soil takes it as every soil does."""
    p = layered((PHREATIC, HEAD, LEVEL)).model_dump()
    p["soil_water"] = {"soil_L1": "phreatic", "soil_L2": "level", "soil_L3": "head"}
    assert Project.model_validate(p).soil_water == {"soil_L1": "phreatic",
                                                    "soil_L3": "head"}


def drawn(record: dict) -> dict:
    """`record` drawn on a line along its own points, as the GUI draws it."""
    points = [list(p) for p in zip(record["x_coordinates"], record["y_coordinates"])]
    return dict(record, on="line", points=points)


def test_the_water_lines_are_the_phreatic_and_head_lines_on_the_soil_or_drawn():
    uniform = {"id": "dry", "name": "Dry", "kind": "water_pressure", "on": "domain",
               "fluid_pressure_type": "Uniform", "value": 0.0}
    face = dict(HEAD, id="left", name="Left", on="face", face="left")
    second = drawn(dict(HEAD, id="second", name="Second"))
    project = layered((PHREATIC, HEAD, LEVEL, uniform, face, second))
    assert [line.id for line in project.water_lines()] == ["phreatic", "head", "second"]
    assert [line.id for line in project.phreatic_lines()] == ["phreatic"]
    assert [line.id for line in project.head_lines()] == ["head", "second"]


def test_a_head_line_needs_its_points():
    with pytest.raises(ValueError, match="Head_Line, which needs the points"):
        layered((PHREATIC, {k: v for k, v in HEAD.items() if "coordinates" not in k}))


def test_the_phreatic_line_is_the_whole_soil_s_wherever_it_was_drawn():
    for phreatic in (PHREATIC, drawn(PHREATIC)):
        project = layered((phreatic, HEAD, LEVEL))
        line, head, level = project.boundary_conditions[-3:]
        assert project.on_the_whole_soil(line)
        assert not project.on_the_whole_soil(head)
        assert project.on_the_whole_soil(level), "a hydrostatic level is as it was"


def test_a_body_takes_its_own_water_else_its_layer_s():
    p = layered().model_dump()
    p["lines"] = [{"id": "cut", "name": "Cut", "points": [[10, 0], [10, -5]]}]
    p["soil_water"] = {"soil_L1": "head"}
    project = Project.model_validate(p)
    left, right = (key for key, *_ in project.soil_bodies() if key.startswith("soil_L1__"))
    assert project.water_of_bodies() == {left: "head", right: "head"}

    p["soil_water"] = {"soil_L1": "head", right: INTERPOLATE}
    assert Project.model_validate(p).water_of_bodies() == {left: "head",
                                                            right: INTERPOLATE}


def test_a_soil_s_water_goes_with_its_line_or_its_soil():
    project = aquifer()
    p = project.model_dump()
    p["boundary_conditions"] = [c for c in p["boundary_conditions"] if c["id"] != "head"]
    assert Project.model_validate(p).soil_water == {"soil_L2": INTERPOLATE}
    p = project.model_dump()
    p["layers"] = p["layers"][:2]
    p["layers"][1]["bottom"] = -25
    assert Project.model_validate(p).soil_water == {"soil_L2": INTERPOLATE}


def test_a_line_that_is_no_longer_a_line_is_let_go():
    p = aquifer().model_dump()
    head = next(c for c in p["boundary_conditions"] if c["id"] == "head")
    head.update(fluid_pressure_type="Hydrostatic", reference_coordinate=2.0)
    assert Project.model_validate(p).soil_water == {"soil_L2": INTERPOLATE}


def test_the_soil_water_round_trips():
    project = aquifer()
    again = Project.model_validate(json.loads(project.model_dump_json()))
    assert again.soil_water == {"soil_L3": "head", "soil_L2": INTERPOLATE}


# ── Editing it ───────────────────────────────────────────────────────────────

def test_the_conditions_patch_sets_the_soils_water():
    project = session.replace_conditions(
        layered(), ConditionsUpdate(soil_water={"soil_L3": "head"}))
    assert project.soil_water == {"soil_L3": "head"}
    # Left out, it stays.
    project = session.replace_conditions(project, ConditionsUpdate(gravity_acceleration=9.8))
    assert project.soil_water == {"soil_L3": "head"}


@pytest.mark.parametrize("asked, said", [
    ({"soil_L9": "head"}, "not a soil of this project"),
    ({"soil_L3": "nowhere"}, "not a head line"),
])
def test_a_soil_s_water_asked_for_by_name_must_exist(asked, said):
    with pytest.raises(EditRefused, match=said):
        session.replace_conditions(layered(), ConditionsUpdate(soil_water=asked))


def test_one_soil_s_water_is_set_and_cleared():
    project = session.set_soil_water(layered(), "soil_L2", INTERPOLATE)
    assert project.soil_water == {"soil_L2": INTERPOLATE}
    assert session.set_soil_water(project, "soil_L2", None).soil_water == {}


def test_a_second_phreatic_line_is_refused_with_what_to_do():
    second = WaterPressureCondition(**dict(PHREATIC, id="second", name="Second"))
    with pytest.raises(ValueError, match="switch one off there, or make it a head line"):
        session.add_condition(layered((PHREATIC,)), second)


# ── What the export says ─────────────────────────────────────────────────────

def test_a_head_line_no_soil_takes_is_said_to_act_nowhere():
    said = condition_checks.warnings(layered())
    assert any("'Aquifer head'" in line and "no soil does" in line for line in said)
    assert not any("no soil does" in line for line in condition_checks.warnings(aquifer()))


def test_an_interpolated_soil_in_3d_is_said_to_take_the_whole_soil_s_water():
    project = aquifer(dimension=3)
    assert any("interpolated" in line and "soil_L2" in line
               for line in condition_checks.warnings(project))


# ── The deck ─────────────────────────────────────────────────────────────────

def test_each_soil_takes_its_own_water(gmsh_session):
    """The phreatic line on the whole soil, then the aquifer's head on the aquifer -- a
    phreatic multi-line to Kratos -- then the clay interpolated: the order Kratos sets
    them in."""
    processes = water(writer.export_project(aquifer(), MESH))
    assert [(p["model_part_name"], p["fluid_pressure_type"]) for p in processes] == [
        ("PorousDomain", "Phreatic_Multi_Line"),
        ("PorousDomain.Aquifer", "Phreatic_Multi_Line"),
        ("PorousDomain.Clay", "Interpolate_Line"),
    ]
    assert (processes[1]["x_coordinates"], processes[1]["y_coordinates"]) == (
        [0.0, 25.0], [1.0, 3.0])


def test_lines_drawn_on_lines_act_as_on_the_whole_soil(gmsh_session):
    """Drawn, the phreatic line is still every soil's water and the head line still the
    aquifer's: neither is written on its line's nodes alone."""
    project = layered((drawn(PHREATIC), drawn(HEAD)),
                      soil_water={"soil_L3": "head", "soil_L2": INTERPOLATE})
    processes = water(writer.export_project(project, MESH))
    assert [p["model_part_name"] for p in processes] == [
        "PorousDomain", "PorousDomain.Aquifer", "PorousDomain.Clay"]


def test_an_interpolated_soil_has_kratos_own_keys_and_no_others(gmsh_session):
    interpolated = water(writer.export_project(aquifer(), MESH))[-1]
    assert interpolated == {
        "model_part_name": "PorousDomain.Clay", "variable_name": "WATER_PRESSURE",
        "is_fixed": True, "table": 0, "fluid_pressure_type": "Interpolate_Line",
        "gravity_direction": 1, "out_of_plane_direction": 2,
    }


def test_a_head_line_no_soil_takes_is_not_written(gmsh_session):
    export = writer.export_project(layered(), MESH)
    assert [p["fluid_pressure_type"] for p in water(export)] == ["Phreatic_Multi_Line"]
    assert any("no soil does" in line for line in export["warnings"])


def test_a_hydrostatic_level_on_the_whole_soil_is_as_it_was(gmsh_session):
    """On all of the soil, beside the phreatic line; a soil that takes a head line has
    it written over both."""
    processes = water(writer.export_project(
        layered((PHREATIC, LEVEL, HEAD), soil_water={"soil_L3": "head"}), MESH))
    assert [(p["model_part_name"], p["fluid_pressure_type"]) for p in processes] == [
        ("PorousDomain", "Phreatic_Multi_Line"), ("PorousDomain", "Hydrostatic"),
        ("PorousDomain.Aquifer", "Phreatic_Multi_Line")]


def test_a_face_still_beats_the_soil_s_own_line(gmsh_session):
    left = dict(LEVEL, id="left", name="Left", on="face", face="left")
    processes = water(writer.export_project(
        layered((PHREATIC, HEAD, left), soil_water={"soil_L3": "head"}), MESH))
    assert [p["model_part_name"] for p in processes][-1].startswith("PorousDomain.Left")


def test_a_3d_deck_interpolates_nothing(gmsh_session):
    export = writer.export_project(aquifer(dimension=3),
                                   MeshRequest(element_size=8.0, order=1))
    assert "Interpolate_Line" not in [p.get("fluid_pressure_type") for p in water(export)]


def staged(**stage_changes) -> Project:
    """The aquifer in two stages, the second with what `stage_changes` switches."""
    p = aquifer().model_dump()
    p["stages"] = [{"id": "s1", "name": "First"},
                   {"id": "s2", "name": "Second", "parent": "s1", **stage_changes}]
    return Project.model_validate(p)


def test_a_line_switched_off_leaves_its_soil_the_phreatic_line(gmsh_session):
    export = writer.export_project(staged(deactivate=["head"]), MESH)
    second = [p["model_part_name"] for p in water(export, "2_Second")]
    assert second == ["PorousDomain", "PorousDomain.Clay"]


def test_an_interpolated_soil_is_off_when_all_the_water_is(gmsh_session):
    export = writer.export_project(staged(deactivate=["head", "phreatic"]), MESH)
    assert water(export, "2_Second") == []
    assert len(water(export, "1_First")) == 3


# ── Files saved when a drawn phreatic line was a pressure on that line only ──

def old_file(*conditions: dict) -> dict:
    """`layered(conditions)` as a document saved before 2026-11-18."""
    payload = json.loads(layered(()).model_dump_json())
    del payload["drawn_phreatic_lines"]
    payload["boundary_conditions"] += [dict(c) for c in conditions]
    return payload


def test_an_old_level_line_drawn_on_a_line_is_hydrostatic_on_that_line():
    """The same pressure on the same nodes, and nothing else, as on main."""
    bank = drawn(dict(PHREATIC, id="bank", name="Bank", y_coordinates=[-2.0, -2.0]))
    payload = old_file(PHREATIC, bank)
    project = Project.model_validate(payload)
    record = project.boundary_conditions[-1]
    assert (record.on, record.fluid_pressure_type, record.reference_coordinate) == (
        "line", "Hydrostatic", -2.0)
    assert [list(p) for p in record.points] == bank["points"]
    assert [line.id for line in project.phreatic_lines()] == ["phreatic"]
    (note,) = migration.notes(payload)
    assert "'Bank'" in note and "Hydrostatic at -2 m now, on the same line" in note
    again = Project.model_validate(project.model_dump())
    assert again.boundary_conditions[-1].fluid_pressure_type == "Hydrostatic"
    assert migration.notes(project.model_dump()) == [], "converted once only"


def test_an_old_sloping_line_drawn_on_a_line_is_the_whole_soil_s_water_and_said():
    sloping = drawn(dict(PHREATIC, id="slope", name="Slope", y_coordinates=[-1.0, -3.0]))
    payload = old_file(sloping)
    project = Project.model_validate(payload)
    assert [line.id for line in project.phreatic_lines()] == ["slope"]
    (note,) = migration.notes(payload)
    assert "now the water of the whole soil" in note and "use a Hydrostatic" in note


def test_an_old_sloping_line_beside_a_phreatic_line_is_a_head_line():
    """Two phreatic lines a stage cannot have on: the file still opens."""
    sloping = drawn(dict(PHREATIC, id="slope", name="Slope", y_coordinates=[-1.0, -3.0]))
    payload = old_file(PHREATIC, sloping)
    project = Project.model_validate(payload)
    assert [line.id for line in project.head_lines()] == ["slope"]
    (note,) = migration.notes(payload)
    assert "it is a head line now" in note


def test_a_new_line_drawn_on_a_line_is_left_as_it_is():
    payload = json.loads(layered((drawn(PHREATIC),)).model_dump_json())
    assert payload["drawn_phreatic_lines"] == "whole_soil"
    project = Project.model_validate(payload)
    assert project.boundary_conditions[-1].fluid_pressure_type == "Phreatic_Multi_Line"
    assert migration.notes(payload) == []
