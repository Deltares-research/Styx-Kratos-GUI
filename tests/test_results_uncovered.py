"""Results that are incomplete, or have less metadata than our own exporter writes."""

import json

import pytest

from core.kratos import deck_files
from core.results import catalog, fields, gid_reader, members


@pytest.mark.parametrize("text", [
    "",
    'Result "TOTAL_DISPLACEMENT" "Kratos" 1 Vector OnNodes\nValues\nEnd Values\n',
])
def test_a_stage_without_displacements_has_no_deformed_shape(text):
    assert fields.displacement(gid_reader.read_results(text)) == {
        "source": None, "ids": [], "values": [],
    }


@pytest.mark.parametrize("text", [
    "",
    'Result "WATER_PRESSURE" "Kratos" 1 Scalar OnNodes\nValues\nEnd Values\n',
])
def test_a_known_field_without_values_names_the_missing_solver_variable(text):
    with pytest.raises(fields.UnknownField, match="needs WATER_PRESSURE"):
        fields.values(gid_reader.read_results(text), gid_reader.GidMesh(), "pw")


def test_inspecting_a_node_outside_the_stage_reports_its_id():
    with pytest.raises(fields.UnknownField, match="no node 42"):
        fields.at_node(gid_reader.Results(), gid_reader.GidMesh(), 42)


def test_a_node_in_an_excavated_body_keeps_the_field_rows_with_missing_values():
    mesh = gid_reader.GidMesh(nodes={1: (0, 0, 0), 2: (1, 0, 0)})
    results = gid_reader.read_results(
        'Result "WATER_PRESSURE" "Kratos" 1 Scalar OnNodes\n'
        'Values\n1 -5000\nEnd Values\n')

    inspected = fields.at_node(results, mesh, 2, system="kN")

    assert inspected["at"] == [1, 0, 0]
    assert inspected["values"] == [{
        "group": "Groundwater", "field": "pw", "label": "Pore pressure",
        "unit": "kPa", "value": None,
    }]


def test_a_deck_without_output_basenames_recovers_files_by_stage_name(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Initial", "2_Dig"]}},
        "stages": {},
    }), encoding="utf-8")
    (tmp_path / "old_1_Initial.post.res").write_text("", encoding="utf-8")
    (tmp_path / "old_1_Initial.post.msh").write_text("", encoding="utf-8")

    stages = catalog.stage_list(tmp_path)

    assert [stage["name"] for stage in stages] == ["1_Initial", "2_Dig"]
    assert stages[0]["base"] == "old_1_Initial"
    assert stages[0]["mesh_file"] == "old_1_Initial.post.msh"
    assert stages[0]["results_file"] == "old_1_Initial.post.res"
    assert stages[1]["base"] is None
    assert stages[1]["results"] is False


def test_an_external_decks_gid_output_name_takes_priority_over_problem_name(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Load"]}},
        "stages": {"1_Load": {"stage_settings": {
            "problem_data": {"problem_name": "not_the_output"},
            "output_processes": {"gid_output": [{
                "Parameters": {"output_name": r"C:\solver\outputs\actual"},
            }]},
        }}},
    }), encoding="utf-8")
    (tmp_path / "actual.post.res").write_text("", encoding="utf-8")

    stage = catalog.stage_list(tmp_path)[0]

    assert stage["base"] == "actual"
    assert stage["results_file"] == "actual.post.res"


def test_a_stage_declared_but_not_reached_reports_why_it_has_no_results(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Initial"]}},
        "stages": {},
    }), encoding="utf-8")

    with pytest.raises(catalog.UnknownRun, match="wrote no results.*stopped before"):
        catalog.stage_results(tmp_path, 1)
    with pytest.raises(catalog.UnknownRun, match="wrote no mesh file"):
        catalog.stage_mesh(tmp_path, 1)
    with pytest.raises(catalog.UnknownRun, match="has no stage 2; it has 1"):
        catalog.stage_record(tmp_path, 2)


@pytest.mark.parametrize("read, message", [
    (catalog.stage_geometry, "mesh cannot be named"),
    (catalog.stage_parts, "parts cannot be named"),
])
def test_output_without_the_original_mdpa_explains_the_missing_part_names(
        tmp_path, read, message):
    with pytest.raises(catalog.UnknownRun, match=message):
        read(tmp_path, 1)


def test_a_run_path_that_was_removed_reports_the_missing_directory(tmp_path):
    missing = tmp_path / "removed-run"

    with pytest.raises(catalog.UnknownRun, match="no run directory"):
        catalog.describe(missing)


@pytest.mark.parametrize("parameters", [
    [],
    {"orchestrator": {"settings": {"execution_list": "not-a-list"}}},
])
def test_unusable_deck_metadata_does_not_hide_existing_stage_output(tmp_path, parameters):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(
        json.dumps(parameters), encoding="utf-8")
    (tmp_path / "model_1_Initial.post.res").write_text("", encoding="utf-8")

    stages = catalog.stage_list(tmp_path)

    assert len(stages) == 1
    assert stages[0]["name"] == "1_Initial"
    assert stages[0]["results_file"] == "model_1_Initial.post.res"


def test_nonstring_execution_entries_do_not_create_spurious_stages(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": [None, 42, "1_Initial"]}},
        "stages": {},
    }), encoding="utf-8")

    assert [stage["name"] for stage in catalog.stage_list(tmp_path)] == ["1_Initial"]


def test_member_output_without_an_mdpa_explains_why_it_cannot_be_placed(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Initial"]}},
        "stages": {},
    }), encoding="utf-8")
    (tmp_path / "1_Initial__output_wall.json").write_text(json.dumps({
        "NODE_1": {"BENDING_MOMENT": [1000]},
    }), encoding="utf-8")

    with pytest.raises(catalog.UnknownRun, match="has no .mdpa.*members cannot be placed"):
        catalog.member_profiles(tmp_path, "wall", "M")


@pytest.mark.parametrize("raw", [None, "bad", True, [], [1], [1, False], [1, "bad"]])
def test_invalid_member_values_leave_a_gap_in_the_profile_instead_of_zero(raw):
    output = {1: {"GEO_EFFECTIVE_TRACTION_VECTOR": raw},
              2: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-10, 5]}}
    coordinates = {1: (0, 0, 0), 2: (0, -1, 0)}

    profile = members.profile(output, coordinates, members.quantity("ts"))

    assert profile["nodes"] == [2]
    assert profile["points"] == [[5.0, -1]]


def test_a_point_element_is_not_drawn_as_a_line():
    from core.results.mesh import edges_of

    assert edges_of([7], 1, "Point") == []
