"""Water pressure conditions: the user's, and no other, in the exported deck.

A `WaterPressureCondition` (core/model/schemas.py) prescribes `WATER_PRESSURE` on the whole
soil, a soil part, a face of the domain, a drawn line or a point, as Kratos'
`ApplyScalarConstraintTableProcess` with the fields named as that process names them
(core/kratos/parameters.py:_water_pressure). A project without one fixes no water pressure
at all, whatever its water level, and each condition carries its own level: the project's
is only the default a new one is given.

The three process shapes are each held to the working Kratos deck they were copied from:
the staged excavation reference for a hydrostatic pressure on the whole soil, Kratos'
`tests/Muskat` for one on a boundary part with a tension cut-off and for a phreatic
multi-line, and `tests/seepage_tests` for a uniform one.
"""

from __future__ import annotations

import json

import pytest

from core import session
from core.geometry import solid_model
from core.kratos import parameters, writer
from core.model import drafts, script_writer, units
from core.model.schemas import MeshRequest, Project
from core.model.templates import blank_project, seed_project
from tests import mdpa

MESH = MeshRequest(element_size=3.0, order=1)


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


def section(conditions: list[dict], water: float | None = -3.5, **changes) -> Project:
    """The seed's ground as a 2D section, with exactly `conditions`."""
    payload = seed_project().model_dump()
    payload.update({"dimension": 2, "section_offset": 20.0,
                    "boundary_conditions": conditions, **changes})
    payload["water"] = None if water is None else {"y": water, "specific_weight": 10_000.0}
    return Project.model_validate(payload)


def condition(id: str = "wp", on: str = "domain", **fields) -> dict:
    """A hydrostatic record about -3.5 m unless `fields` say otherwise."""
    if fields.get("fluid_pressure_type", "Hydrostatic") == "Hydrostatic":
        fields.setdefault("reference_coordinate", -3.5)
    return {"id": id, "name": id, "kind": "water_pressure", "on": on, **fields}


def face(id: str, name: str, **fields) -> dict:
    return condition(id, on="face", face=name, **fields)


def stage_processes(export: dict, stage: str = "1_Stage") -> list[dict]:
    doc = json.loads(export["project_parameters"])
    return doc["stages"][stage]["stage_settings"]["processes"]["constraints_process_list"]


def water_processes(export: dict, stage: str = "1_Stage") -> list[dict]:
    return [p["Parameters"] for p in stage_processes(export, stage)
            if p["Parameters"].get("variable_name") == "WATER_PRESSURE"]


# ── The schema ──────────────────────────────────────────────────────────────

def test_a_project_saved_before_the_conditions_existed_has_none():
    payload = seed_project().model_dump()
    del payload["boundary_conditions"]
    assert not any(c.kind == "water_pressure"
                   for c in Project.model_validate(payload).boundary_conditions)


def test_a_new_project_has_no_water_pressure_condition():
    assert not any(c.kind == "water_pressure" for c in blank_project().boundary_conditions)


@pytest.mark.parametrize("fields, message", [
    (dict(on="line"), "which needs points"),
    (dict(on="line", points=[[0, 0]]), "needs at least two points"),
    (dict(on="point", points=[[0, 0], [1, 0]]), "which is one point, not 2"),
    (dict(on="face"), "which needs face"),
    (dict(on="face", face="up"), "Input should be"),
    (dict(on="part"), "which needs part"),
    (dict(on="part", part="soil_nowhere"),
     "not a soil part of this project; the soil parts are soil_L1, soil_L2"),
    (dict(face="left"), "on 'domain', which takes no face"),
    (dict(on="face", face="left", points=[[0, 0], [0, -1]]), "which takes no points"),
    (dict(on="line", points=[[1, 0], [1, 0], [1, -2]]), "repeats the point"),
    (dict(reference_coordinate=None), "needs its water level"),
    (dict(fluid_pressure_type="Phreatic_Multi_Line"), "needs the points of the line"),
    (dict(x_coordinates=[0.0, 1.0]), "both x_coordinates and y_coordinates"),
    (dict(z_coordinates=[0.0, 0.0]), "z_coordinates but no x_coordinates"),
    (dict(fluid_pressure_type="Phreatic_Multi_Line", x_coordinates=[0.0, 1.0],
          y_coordinates=[1.0]), "as many x as y"),
    (dict(fluid_pressure_type="Phreatic_Multi_Line", x_coordinates=[0.0, 1.0],
          y_coordinates=[1.0, 1.0], z_coordinates=[0.0]), "and z"),
    (dict(fluid_pressure_type="Phreatic_Multi_Line", x_coordinates=[1.0, 0.0],
          y_coordinates=[1.0, 1.0]), "must increase"),
    (dict(pressure_tension_cut_off=-1.0), "greater than or equal to 0"),
])
def test_an_unusable_condition_is_refused(fields, message):
    with pytest.raises(ValueError, match=message):
        section([condition(**fields)])


def test_two_conditions_cannot_share_an_id():
    with pytest.raises(ValueError, match="duplicate boundary condition id"):
        section([condition("a"), face("a", "left")])


def test_a_condition_cannot_take_a_part_s_id():
    taken = seed_project().part_keys()[0]
    with pytest.raises(ValueError, match="collides with an existing model part key"):
        section([condition(taken)])


def test_a_hydrostatic_normal_load_with_its_own_level_needs_no_project_water():
    load = {"id": "n1", "name": "n1", "kind": "normal",
            "points": [[8.0, 0.0], [8.0, -5.0]], "fluid_pressure_type": "Hydrostatic",
            "reference_coordinate": -2.0}
    assert section([], water=None, normal_loads=[load]).normal_loads[0] \
        .reference_coordinate == -2.0
    with pytest.raises(ValueError, match="needs a water level"):
        section([], water=None, normal_loads=[{**load, "reference_coordinate": None}])


def test_the_stresses_convert_with_the_units():
    project = section([condition(fluid_pressure_type="Uniform", value=-20_000.0,
                                 pressure_tension_cut_off=1e5)])
    converted, _ = units.convert_project(project.model_dump(), "kN")
    record = converted["boundary_conditions"][0]
    assert record["value"] == pytest.approx(-20.0)
    assert record["pressure_tension_cut_off"] == pytest.approx(100.0)


# ── Drafts, session and script ───────────────────────────────────────────────

def test_a_draft_is_hydrostatic_and_fixed_and_copies_the_water_level_in():
    record = drafts.water_pressure_condition(section([]), "domain")
    assert (record.id, record.name) == ("waterpressure_1", "Water pressure 1")
    assert (record.fluid_pressure_type, record.is_fixed, record.reference_coordinate) \
        == ("Hydrostatic", True, -3.5)
    assert drafts.water_pressure_condition(
        section([]), "domain", reference_coordinate=-1.0).reference_coordinate == -1.0


def test_a_hydrostatic_draft_with_no_level_anywhere_is_refused():
    with pytest.raises(drafts.DraftError, match="needs the level where its pressure is zero"):
        drafts.water_pressure_condition(section([], water=None), "domain")
    uniform = drafts.water_pressure_condition(section([], water=None), "domain",
                                              fluid_pressure_type="Uniform")
    assert uniform.reference_coordinate is None


def test_drafted_lines_and_points_start_in_the_section_and_only_in_2d():
    project = section([])
    assert len(drafts.water_pressure_condition(project, "line").points) == 2
    assert drafts.water_pressure_condition(project, "point").points == [(12.5, -12.5)]
    for on in ("line", "point"):
        with pytest.raises(drafts.DraftError, match="2D section"):
            drafts.water_pressure_condition(section([], dimension=3), on)


def test_a_drafted_hydrostatic_normal_load_stores_the_level_it_uses():
    assert drafts.normal_load(section([]), hydrostatic=True).reference_coordinate == -3.5
    assert drafts.normal_load(section([])).reference_coordinate is None


def test_the_session_adds_changes_and_removes_a_condition():
    project = session.add_condition(section([]), drafts.water_pressure_condition(
        section([]), "face", face="left", reference_coordinate=-1.0))
    project = session.update_condition(project, "waterpressure_1",
                                     pressure_tension_cut_off=1e5)
    assert session.find_condition(project, "waterpressure_1").pressure_tension_cut_off == 1e5
    assert session.remove_condition(project, "waterpressure_1").boundary_conditions == []


def test_a_new_target_drops_what_the_old_one_named():
    project = section([face("wp", "left")])
    moved = session.find_condition(
        session.update_condition(project, "wp", on="part", part="soil_L2"), "wp")
    assert (moved.on, moved.face, moved.part) == ("part", None, "soil_L2")


def test_the_session_refuses_an_id_a_part_has():
    project = section([])
    record = drafts.water_pressure_condition(project, "domain", id=project.part_keys()[0])
    with pytest.raises(session.EditRefused, match="already a part"):
        session.add_condition(project, record)


def test_a_model_script_writes_the_conditions_out():
    project = section([face("wp", "right", reference_coordinate=-1.0,
                            pressure_tension_cut_off=1e5)])
    text = script_writer.script(project)
    assert "WaterPressureCondition(" in text and "The boundary conditions" in text


# ── The deck ────────────────────────────────────────────────────────────────

def test_without_a_condition_the_deck_fixes_no_water_pressure(gmsh_session):
    export = writer.export_project(section([]), MESH)
    assert water_processes(export) == []
    assert any("fixes no pressure by itself" in w for w in export["warnings"])


def test_a_hydrostatic_condition_on_the_whole_soil_is_the_reference_process(gmsh_session):
    export = writer.export_project(section([condition()]), MESH)
    assert water_processes(export) == [{
        "model_part_name": "PorousDomain", "variable_name": "WATER_PRESSURE",
        "is_fixed": True, "table": 0, "fluid_pressure_type": "Hydrostatic",
        "gravity_direction": 1, "reference_coordinate": -3.5, "specific_weight": 10_000.0,
    }]
    assert not any("fixes no pressure" in w for w in export["warnings"])


def test_a_condition_s_level_is_its_own_not_the_project_s(gmsh_session):
    export = writer.export_project(
        section([condition(reference_coordinate=-8.0)], water=-2.0), MESH)
    assert water_processes(export)[0]["reference_coordinate"] == -8.0
    dry = writer.export_project(section([condition()], water=None), MESH)
    assert water_processes(dry)[0]["reference_coordinate"] == -3.5


@pytest.fixture(scope="module")
def every_target(gmsh_session):
    """Every shape at once, listed most specific first: a pressure at a point, a uniform
    one along a drawn line, a head on a face, one on a soil part, a start value on the
    whole soil, and a face this section does not have."""
    return writer.export_project(section([
        condition("well", on="point", fluid_pressure_type="Uniform", value=-90_000.0,
                  points=[[10.0, -12.0]]),
        condition("ditch", on="line", fluid_pressure_type="Uniform", value=-5_000.0,
                  points=[[20.0, -2.0], [20.0, -8.0]]),
        face("left_head", "left", reference_coordinate=-1.0,
             pressure_tension_cut_off=1e5),
        condition("deep", on="part", part="soil_L2", reference_coordinate=-6.0),
        condition("initial", fluid_pressure_type="Phreatic_Multi_Line", is_fixed=False,
                  x_coordinates=[-1.0, 20.0, 51.0], y_coordinates=[-1.0, -2.0, -6.0]),
        face("front_head", "front"),
    ]), MESH)


def test_start_values_come_first_then_the_least_specific_target(every_target):
    """Kratos keeps the value written last on a node, so the point wins over the line,
    the line over the face, the face over the part."""
    names = writer._part_names(section([]))
    assert [(p["is_fixed"], p["model_part_name"])
            for p in water_processes(every_target)] == [
        (False, "PorousDomain"), (True, f"PorousDomain.{names['soil_L2']}"),
        (True, "PorousDomain.Left_Edge"), (True, "PorousDomain.ditch"),
        (True, "PorousDomain.well")]


def test_a_pressure_on_a_part_is_measured_from_its_own_level(every_target):
    deep = water_processes(every_target)[1]
    assert (deep["fluid_pressure_type"], deep["reference_coordinate"]) == ("Hydrostatic", -6.0)


def test_a_head_on_a_face_names_the_face_part_and_its_cut_off(every_target):
    head = water_processes(every_target)[2]
    assert head["model_part_name"] == "PorousDomain.Left_Edge"
    assert (head["reference_coordinate"], head["pressure_tension_cut_off"]) == (-1.0, 1e5)


def test_a_phreatic_multi_line_is_the_muskat_deck_s_process(every_target):
    initial = water_processes(every_target)[0]
    assert initial == {
        "model_part_name": "PorousDomain", "variable_name": "WATER_PRESSURE",
        "is_fixed": False, "table": [0, 0, 0], "fluid_pressure_type": "Phreatic_Multi_Line",
        "gravity_direction": 1, "out_of_plane_direction": 2,
        "x_coordinates": [-1.0, 20.0, 51.0], "y_coordinates": [-1.0, -2.0, -6.0],
        "z_coordinates": [0.0, 0.0, 0.0], "specific_weight": 10_000.0,
    }


def test_a_uniform_pressure_on_a_line_holds_the_nodes_on_that_line(every_target):
    uniform = water_processes(every_target)[3]
    assert uniform == {"model_part_name": "PorousDomain.ditch",
                       "variable_name": "WATER_PRESSURE", "is_fixed": True,
                       "value": -5_000.0, "table": 0}
    deck = mdpa.parse(every_target["mdpa"])
    nodes = deck.parts["ditch"].nodes
    assert len(nodes) >= 3
    assert all(abs(deck.nodes[n][0] - 20.0) < 1e-6 and -8.0 - 1e-6 <= deck.nodes[n][1]
               <= -2.0 + 1e-6 for n in nodes)


def test_a_pressure_at_a_point_holds_the_one_node_there(every_target):
    assert water_processes(every_target)[4]["value"] == -90_000.0
    deck = mdpa.parse(every_target["mdpa"])
    [node] = deck.parts["well"].nodes
    assert deck.nodes[node][:2] == pytest.approx((10.0, -12.0))


def test_a_face_the_section_does_not_have_is_left_out_with_a_warning(every_target):
    assert len(water_processes(every_target)) == 5
    assert any("'front_head' is on the front face" in w
               for w in every_target["warnings"])


def test_targets_of_different_kinds_overlap_without_a_warning(every_target):
    assert not any("shared node" in w for w in every_target["warnings"])


def test_two_fixed_conditions_of_one_kind_on_shared_nodes_are_warned_about(gmsh_session):
    """Two layers meet along a line of nodes; on those the later record wins."""
    export = writer.export_project(section([
        condition("upper", on="part", part="soil_L1", reference_coordinate=-1.0),
        condition("lower", on="part", part="soil_L2", reference_coordinate=-6.0),
    ]), MESH)
    assert any("'upper' and 'lower' both fix the pressure" in w
               and "keeps 'lower''s value" in w for w in export["warnings"])


def test_a_phreatic_line_s_own_z_coordinates_are_written(gmsh_session):
    export = writer.export_project(section([condition(
        fluid_pressure_type="Phreatic_Multi_Line", x_coordinates=[0.0, 25.0],
        y_coordinates=[-1.0, -2.0], z_coordinates=[5.0, 5.0])]), MESH)
    assert water_processes(export)[0]["z_coordinates"] == [5.0, 5.0]


def test_a_point_is_left_out_of_a_3d_deck(gmsh_session):
    export = writer.export_project(section([
        condition("well", on="point", fluid_pressure_type="Uniform",
                  points=[[10.0, -12.0]]),
    ], dimension=3), MeshRequest(element_size=8.0, order=1))
    assert water_processes(export) == []
    assert any("'well' is on a point, which is drawn in the 2D section" in w
               for w in export["warnings"])


def test_an_inactive_condition_is_not_written(gmsh_session):
    export = writer.export_project(section([condition(active=False)]), MESH)
    assert water_processes(export) == []


def _staged(conditions: list[dict]) -> tuple[dict, list[str]]:
    from tests.models import excavation
    payload = excavation.excavation_project().model_dump()
    payload["boundary_conditions"] = conditions
    export = writer.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=4.0, order=1))
    doc = json.loads(export["project_parameters"])
    return export, doc["orchestrator"]["settings"]["execution_list"]


def test_a_head_on_a_face_goes_with_each_lift_that_reaches_it(gmsh_session):
    """The excavation splits the left face into one segment per lift; each segment's
    pressure leaves the deck in the stage its lift is dug out in."""
    export, order = _staged([face("wp", "left", reference_coordinate=-1.5)])
    named = {stage: {p["model_part_name"] for p in water_processes(export, stage)}
             for stage in (order[0], order[-1])}
    assert "PorousDomain.Left_Edge" in named[order[0]]
    assert "PorousDomain.Left_Edge" in named[order[-1]]
    lifts = named[order[0]] - named[order[-1]]
    assert lifts and all(name.endswith("_Left_Edge") for name in lifts)


def test_a_pressure_on_a_staged_layer_goes_with_each_of_its_lifts(gmsh_session):
    """A layer is every body dug out of it: the retained side stays, and each lift
    leaves with its own stage."""
    export, order = _staged([condition("top", on="part", part="soil_L_top",
                                       reference_coordinate=-1.5)])
    first = {p["model_part_name"] for p in water_processes(export, order[0])}
    last = {p["model_part_name"] for p in water_processes(export, order[-1])}
    assert len(first) == 4 and len(last) == 1 and last < first


def test_a_coupled_soil_with_no_condition_is_warned_about(gmsh_session):
    project = section([])
    payload = project.model_dump()
    for material in payload["materials"]:
        material["variables"]["GEO_DRAINAGE_TYPE"] = "FULLY_COUPLED"
    export = writer.export_project(Project.model_validate(payload), MESH)
    assert any("couples it to the deformation" in w for w in export["warnings"])


def test_a_normal_load_s_own_level_is_the_one_its_process_reads(gmsh_session):
    load = {"id": "n1", "name": "River", "kind": "normal",
            "points": [[8.0, 0.0], [8.0, -5.0]], "fluid_pressure_type": "Hydrostatic",
            "reference_coordinate": -2.0}
    export = writer.export_project(section([], normal_loads=[load]), MESH)
    doc = json.loads(export["project_parameters"])
    loads = doc["stages"]["1_Stage"]["stage_settings"]["processes"]["loads_process_list"]
    process = next(p for p in loads if p["process_name"] == "ApplyNormalLoadTableProcess")
    assert process["Parameters"]["reference_coordinate"] == -2.0


def test_the_water_pressure_entry_is_what_the_process_is_written_from():
    entry = parameters.WaterPressure(
        part="Right_Edge", fluid_pressure_type="Hydrostatic", is_fixed=True, value=0.0,
        reference_coordinate=1.6, x_coordinates=(), y_coordinates=(), z_coordinates=(),
        pressure_tension_cut_off=1e5, specific_weight=1e4)
    assert parameters._water_pressure(entry)["Parameters"] == {
        "model_part_name": "PorousDomain.Right_Edge", "variable_name": "WATER_PRESSURE",
        "is_fixed": True, "table": 0, "fluid_pressure_type": "Hydrostatic",
        "gravity_direction": 1, "reference_coordinate": 1.6, "specific_weight": 1e4,
        "pressure_tension_cut_off": 1e5,
    }


# ── Water conditions per phase ──────────────────────────────────────────────

def _phased(conditions: list[dict], phases: list[dict], **changes) -> Project:
    return section(conditions, phases=phases, **changes)


HIGH_THEN_LOW = [
    {"id": "p1", "name": "High water", "deactivate": ["low"]},
    {"id": "p2", "name": "Low water", "parent": "p1", "activate": ["low"],
     "deactivate": ["high"]},
    {"id": "p3", "name": "Dry", "parent": "p2", "deactivate": ["low"]},
]


def test_a_water_condition_is_a_key_a_phase_switches_and_a_support_is_not():
    project = section([condition("pore"), {"id": "fix", "name": "fix",
                                           "kind": "displacement", "on": "face",
                                           "face": "bottom", "fixed": [True, True, True]}])
    assert "pore" in project.stageable_keys()
    assert "pore" in project.stageable_parts
    assert "fix" not in project.stageable_keys()


def test_each_stage_writes_the_water_conditions_its_phase_has_on(gmsh_session):
    export = writer.export_project(_phased(
        [condition("high", reference_coordinate=0.0),
         condition("low", reference_coordinate=-5.0)], HIGH_THEN_LOW), MESH)
    levels = [[p["reference_coordinate"] for p in water_processes(export, stage)]
              for stage in ("1_High_water", "2_Low_water", "3_Dry")]
    assert levels == [[0.0], [-5.0], []]


def test_two_conditions_no_phase_has_on_together_are_not_warned_about(gmsh_session):
    export = writer.export_project(_phased(
        [condition("high", reference_coordinate=0.0),
         condition("low", reference_coordinate=-5.0)], HIGH_THEN_LOW), MESH)
    assert not any("both fix the pressure" in w for w in export["warnings"])


def test_a_condition_a_phase_switches_cannot_be_removed():
    project = _phased([condition("high", reference_coordinate=0.0),
                       condition("low", reference_coordinate=-5.0)], HIGH_THEN_LOW)
    with pytest.raises(session.EditRefused, match="phase 'p1' names low"):
        session.remove_condition(project, "low")
    from core.model.schemas import ConditionsUpdate
    with pytest.raises(session.EditRefused, match="take it out of those phases first"):
        session.replace_conditions(project, ConditionsUpdate(
            boundary_conditions=[project.boundary_conditions[0]]))


def _coupled(project: Project) -> Project:
    payload = project.model_dump()
    for material in payload["materials"]:
        material["variables"]["GEO_DRAINAGE_TYPE"] = "FULLY_COUPLED"
    return Project.model_validate(payload)


def test_a_phase_that_leaves_a_coupled_soil_s_water_free_is_warned_about():
    """A Hydrostatic condition keeps its nodes fixed after its phase, a Uniform one does
    not (tests/kratos/test_live_conditions.py)."""
    from core.kratos import condition_checks
    kept = _coupled(_phased([condition("high", reference_coordinate=0.0),
                             condition("low", reference_coordinate=-5.0)], HIGH_THEN_LOW))
    assert not any("is free there" in w for w in condition_checks.warnings(kept))
    freed = _coupled(_phased(
        [condition("high", fluid_pressure_type="Uniform", value=0.0),
         condition("low", fluid_pressure_type="Uniform", value=-50.0)], HIGH_THEN_LOW))
    assert [w for w in condition_checks.warnings(freed) if "is free there" in w] == [
        next(w for w in condition_checks.warnings(freed) if "phase 'Dry'" in w)]
