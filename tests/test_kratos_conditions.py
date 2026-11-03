"""Displacement conditions: the supports the user lists, and no others, in the deck.

A `DisplacementCondition` (core/model/schemas.py) holds the displacement at zero on a face
of the domain, a soil part, a drawn line or a point, in the components its `fixed` names.
Nothing else puts a support in the deck: the bottom fixed and the sides on rollers that
the export always wrote are now the standard set of records a project starts with
(`schemas.standard_conditions`), which a project saved before the conditions existed opens
with, so its deck does not change.
"""

from __future__ import annotations

import json

import pytest

from core import session
from core.geometry import solid_model
from core.kratos import condition_checks, writer
from core.model import drafts, script_writer
from core.model.schemas import (DisplacementCondition, MeshRequest, Project,
                                standard_conditions)
from core.model.templates import blank_project, seed_project
from tests import mdpa

MESH = MeshRequest(element_size=3.0, order=1)


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


def section(conditions: list[dict] | None, **changes) -> Project:
    """The seed's ground as a 2D section, with exactly `conditions` (the standard set
    when None)."""
    payload = seed_project().model_dump()
    payload.update({"dimension": 2, "section_offset": 20.0, **changes})
    if conditions is None:
        del payload["boundary_conditions"]
    else:
        payload["boundary_conditions"] = conditions
    return Project.model_validate(payload)


def held(id: str, on: str = "face", fixed=(True, True, True), **fields) -> dict:
    return {"id": id, "name": id, "kind": "displacement", "on": on, "fixed": fixed, **fields}


def supports(export: dict, stage: str = "1_Stage") -> list[tuple[str, list[bool]]]:
    doc = json.loads(export["project_parameters"])
    processes = doc["stages"][stage]["stage_settings"]["processes"]
    return [(p["Parameters"]["model_part_name"].removeprefix("PorousDomain."),
             p["Parameters"]["is_fixed"])
            for p in processes["constraints_process_list"]
            if p["Parameters"].get("variable_name") == "DISPLACEMENT"]


# ── The schema ──────────────────────────────────────────────────────────────

def test_a_new_project_starts_with_the_standard_supports():
    assert blank_project().boundary_conditions == standard_conditions()
    assert [(c.face, c.fixed) for c in standard_conditions()] == [
        ("bottom", (True, True, True)), ("left", (True, False, False)),
        ("right", (True, False, False)), ("front", (False, False, True)),
        ("back", (False, False, True))]


def test_a_project_saved_before_the_conditions_existed_gets_them_too():
    assert section(None).boundary_conditions == standard_conditions()


def test_an_empty_list_is_kept_as_it_is():
    assert section([]).boundary_conditions == []


@pytest.mark.parametrize("fields, message", [
    (dict(on="domain"), "which would hold the whole model still"),
    (dict(face="left", fixed=(False, False, False)), "holds no component"),
    (dict(on="line", points=[[0, 0]]), "needs at least two points"),
    (dict(face="left", part="soil_L1"), "which takes no part"),
])
def test_an_unusable_displacement_condition_is_refused(fields, message):
    record = held("d", **{"face": "left", **fields}) if "on" not in fields else \
        held("d", **fields)
    with pytest.raises(ValueError, match=message):
        section([record])


def test_the_kind_picks_the_record():
    project = section([held("d", face="left"),
                       {"id": "w", "name": "w", "kind": "water_pressure", "on": "domain",
                        "reference_coordinate": -1.0}])
    assert [type(c).__name__ for c in project.boundary_conditions] == [
        "DisplacementCondition", "WaterPressureCondition"]


# ── Drafts and session ──────────────────────────────────────────────────────

def test_a_roller_holds_the_normal_of_its_face_or_line():
    project = section([])
    assert drafts.displacement_condition(project, "face", face="bottom",
                                         roller=True).fixed == (False, True, False)
    assert drafts.displacement_condition(project, "face", face="back",
                                         roller=True).fixed == (False, False, True)
    assert drafts.displacement_condition(project, "line", points=[(5, 0), (5, -5)],
                                         roller=True).fixed == (True, False, False)
    assert drafts.displacement_condition(project, "line", points=[(0, -5), (5, -5)],
                                         roller=True).fixed == (False, True, False)
    with pytest.raises(drafts.DraftError, match="sloping line"):
        drafts.displacement_condition(project, "line", points=[(0, 0), (5, -5)],
                                      roller=True)
    with pytest.raises(drafts.DraftError, match="no normal"):
        drafts.displacement_condition(project, "point", roller=True)


def test_a_draft_is_fixed_in_every_component_with_a_free_id():
    record = drafts.displacement_condition(section([]), "face", face="left")
    assert (record.id, record.name, record.fixed) == ("displacement_1", "Displacement 1",
                                                      (True, True, True))
    with pytest.raises(drafts.DraftError, match="whole model still"):
        drafts.displacement_condition(section([]), "domain")
    with pytest.raises(drafts.DraftError, match="2D section"):
        drafts.displacement_condition(section([], dimension=3), "line")


def test_the_standard_set_replaces_the_face_supports_only():
    project = section([
        held("bottom_roller", face="bottom", fixed=(False, True, False)),
        held("strip", on="line", points=[[0.0, -5.0], [5.0, -5.0]]),
        {"id": "w", "name": "w", "kind": "water_pressure", "on": "domain",
         "reference_coordinate": -1.0}])
    standard = session.standard_conditions(project)
    assert [c.id for c in standard.boundary_conditions] == [
        "fixed_bottom", "roller_left", "roller_right", "roller_front", "roller_back",
        "strip", "w"]


def test_the_standard_set_takes_free_ids():
    project = section([held("fixed_bottom", on="line", points=[[0.0, -5.0], [5.0, -5.0]])])
    ids = [c.id for c in session.standard_conditions(project).boundary_conditions]
    assert ids[0] != "fixed_bottom" and ids[0].startswith("fixed_bottom_")
    assert len(set(ids)) == len(ids)


def test_a_model_script_writes_every_condition_out():
    text = script_writer.script(section(None))
    assert text.count("DisplacementCondition(") == 5
    empty = script_writer.script(section([]))
    assert "BOUNDARY_CONDITIONS = []" in empty


# ── The deck ────────────────────────────────────────────────────────────────

def test_the_standard_set_is_the_old_bucket(gmsh_session):
    """Pinned at the bottom, x held on the sides, no z in a section, nothing on top."""
    assert supports(writer.export_project(section(None), MESH)) == [
        ("Bottom_Fixed", [True, True, False]), ("Left_Edge", [True, False, False]),
        ("Right_Edge", [True, False, False])]


def test_the_standard_set_in_3d_holds_z_on_the_front_and_back(gmsh_session):
    project = section(None, dimension=3)
    assert supports(writer.export_project(project, MeshRequest(element_size=8.0,
                                                               order=1))) == [
        ("Bottom_Fixed", [True, True, True]), ("Left_Edge", [True, False, False]),
        ("Right_Edge", [True, False, False]), ("Front_Edge", [False, False, True]),
        ("Back_Edge", [False, False, True])]


def test_front_and_back_supports_are_left_out_of_a_section_without_a_word():
    assert not any("face" in w for w in condition_checks.warnings(section(None)))


def test_a_roller_bottom_and_a_support_on_top(gmsh_session):
    export = writer.export_project(section([
        held("bottom", face="bottom", fixed=(False, True, False)),
        held("left", face="left", fixed=(True, False, False)),
        held("top", face="top", fixed=(True, False, False))]), MESH)
    assert supports(export) == [("Bottom_Fixed", [False, True, False]),
                                ("Left_Edge", [True, False, False]),
                                ("Top_Surface", [True, False, False])]


def test_no_support_is_written_without_a_condition_and_the_export_says_so(gmsh_session):
    export = writer.export_project(section([]), MESH)
    assert supports(export) == []
    assert any("can move as a rigid body" in w for w in export["warnings"])


def test_an_anchor_holds_the_model_too():
    from tests.models.excavation import excavation_project
    payload = excavation_project(staged=False).model_dump()
    payload["boundary_conditions"] = []
    assert not any("rigid body" in w for w in condition_checks.warnings(
        Project.model_validate(payload)))


def test_a_support_along_a_line_holds_the_nodes_on_that_line(gmsh_session):
    export = writer.export_project(section([
        *[c.model_dump() for c in standard_conditions()],
        held("strip", on="line", points=[[5.0, -10.0], [15.0, -10.0]],
             fixed=(False, True, False))]), MESH)
    assert supports(export)[-1] == ("strip", [False, True, False])
    deck = mdpa.parse(export["mdpa"])
    nodes = deck.parts["strip"].nodes
    assert len(nodes) >= 3
    assert all(abs(deck.nodes[n][1] + 10.0) < 1e-6 for n in nodes)


def test_a_support_at_a_point_and_on_a_part(gmsh_session):
    export = writer.export_project(section([
        held("pin", on="point", points=[[10.0, -20.0]]),
        held("deep", on="part", part="soil_L2")]), MESH)
    names = writer._part_names(section([]))
    assert supports(export) == [("pin", [True, True, False]),
                                (names["soil_L2"], [True, True, False])]
    deck = mdpa.parse(export["mdpa"])
    [node] = deck.parts["pin"].nodes
    assert deck.nodes[node][:2] == pytest.approx((10.0, -20.0))


def test_an_inactive_support_is_not_written(gmsh_session):
    export = writer.export_project(section([held("left", face="left", active=False),
                                            held("bottom", face="bottom")]), MESH)
    assert supports(export) == [("Bottom_Fixed", [True, True, False])]


def _staged(conditions: list[dict]) -> tuple[dict, list[str]]:
    from tests.models import excavation
    payload = excavation.excavation_project().model_dump()
    payload["boundary_conditions"] = conditions
    export = writer.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=4.0, order=1))
    doc = json.loads(export["project_parameters"])
    return export, doc["orchestrator"]["settings"]["execution_list"]


def test_a_support_on_a_face_goes_with_each_lift_that_reaches_it(gmsh_session):
    export, order = _staged([c.model_dump() for c in standard_conditions()])
    first = {name for name, _ in supports(export, order[0])}
    last = {name for name, _ in supports(export, order[-1])}
    lifts = first - last
    assert "Left_Edge" in last and lifts
    assert all(name.endswith("_Left_Edge") for name in lifts)


def test_a_support_on_the_top_face_is_split_by_the_lifts_too(gmsh_session):
    export, order = _staged([*[c.model_dump() for c in standard_conditions()],
                             held("lid", face="top", fixed=(False, True, False))])
    first = {name for name, _ in supports(export, order[0])}
    last = {name for name, _ in supports(export, order[-1])}
    assert {name for name in first - last if name.endswith("_Top_Surface")}
    assert "Top_Surface" in last


def test_a_displacement_condition_record_round_trips():
    record = DisplacementCondition(id="d", name="d", on="face", face="left",
                                   fixed=(True, False, False))
    assert DisplacementCondition.model_validate(record.model_dump()) == record


# ── Gravity ─────────────────────────────────────────────────────────────────

def loads(export: dict, stage: str = "1_Stage") -> list[str]:
    doc = json.loads(export["project_parameters"])
    processes = doc["stages"][stage]["stage_settings"]["processes"]
    return [p["Parameters"].get("variable_name", "") for p in processes["loads_process_list"]]


def test_gravity_is_on_in_a_new_project_and_in_an_old_file():
    assert blank_project().gravity is True
    payload = seed_project().model_dump()
    del payload["gravity"]
    assert Project.model_validate(payload).gravity is True


def test_with_gravity_off_no_stage_has_the_self_weight(gmsh_session):
    on = writer.export_project(section(None), MESH)
    off = writer.export_project(session.set_gravity(section(None), False), MESH)
    assert "VOLUME_ACCELERATION" in loads(on)
    assert "VOLUME_ACCELERATION" not in loads(off)


def test_the_hydraulic_head_is_written_only_with_gravity(gmsh_session):
    """Kratos computes the head from the water weight, which gravity gives: without it
    every value would be 0."""
    def gauss(export: dict) -> list[str]:
        doc = json.loads(export["project_parameters"])
        stage = doc["stages"]["1_Stage"]["stage_settings"]
        output = stage["output_processes"]["gid_output"][0]["Parameters"]
        return output["postprocess_parameters"]["result_file_configuration"][
            "gauss_point_results"]
    assert gauss(writer.export_project(section(None), MESH)) == [
        "CAUCHY_STRESS_TENSOR", "HYDRAULIC_HEAD"]
    assert gauss(writer.export_project(session.set_gravity(section(None), False), MESH)) == [
        "CAUCHY_STRESS_TENSOR"]


def test_a_k0_stage_with_gravity_off_is_warned_about():
    from tests.models.excavation import excavation_project
    project = session.set_gravity(excavation_project(), False)
    assert any("initialises its stresses by a K0 procedure, whose stresses come from "
               "the self weight" in w for w in condition_checks.warnings(project))
    assert not any("K0 procedure" in w
                   for w in condition_checks.warnings(excavation_project()))


def test_a_gravity_loading_stage_with_gravity_off_is_warned_about():
    from tests.models.excavation import excavation_project
    project = excavation_project()
    first = project.stages[0].model_copy(update={"stress_initialisation": "gravity"})
    project = session.set_gravity(
        project.model_copy(update={"stages": [first, *project.stages[1:]]}), False)
    assert any("initialises its stresses by gravity loading" in w
               for w in condition_checks.warnings(project))


def test_the_conditions_update_changes_only_what_it_names():
    from core.model.schemas import ConditionsUpdate
    project = section(None)
    off = session.replace_conditions(project, ConditionsUpdate(gravity=False))
    assert (off.gravity, off.boundary_conditions) == (False, project.boundary_conditions)
    cleared = session.replace_conditions(project, ConditionsUpdate(boundary_conditions=[]))
    assert (cleared.gravity, cleared.boundary_conditions) == (True, [])


def test_a_model_script_writes_gravity_off_out():
    assert "gravity=False" in script_writer.script(session.set_gravity(section(None), False))
    assert "gravity=" not in script_writer.script(section(None))
