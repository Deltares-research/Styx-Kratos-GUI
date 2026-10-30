"""Focused tests for Kratos deck helpers and their refusal/reporting paths."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.analysis import kratos_main
from core.geometry import solid_model
from core.kratos import (condition_checks, external_deck, interfaces, materials,
                         mdpa_reader, parameters, writer)
from core.model.schemas import InterfaceSection, Stage
from core.model.templates import seed_project
from tests.models.muskat import HEADS, muskat


def test_kratos_main_rejects_missing_or_extra_arguments(capsys):
    assert kratos_main.main(["kratos_main.py"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: python -m core.analysis.kratos_main" in captured.err

    assert kratos_main.main(["kratos_main.py", "project.json", "extra"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_announcing_orchestrator_marks_each_stage_around_base_hooks(capsys):
    class Orchestrator:
        def __init__(self, _project):
            self.events = []

        def GetNumberOfStages(self):
            return 2

        def RunCurrentStagePreprocess(self, name, data=None):
            self.events.append(("pre", name, data))

        def RunCurrentStagePostprocess(self, name, data=None):
            self.events.append(("post", name, data))

    announced = kratos_main.announcing(Orchestrator)("project")
    announced.RunCurrentStagePreprocess("Initial", {"id": 1})
    announced.RunCurrentStagePostprocess("Initial", {"id": 2})

    assert announced.events == [("pre", "Initial", {"id": 1}),
                                ("post", "Initial", {"id": 2})]
    assert capsys.readouterr().out.splitlines() == [
        "[kratos-gui] stage begin 1/2 Initial",
        "[kratos-gui] stage end 1/2 Initial",
    ]


def test_external_deck_stages_follow_execution_order_and_keep_only_changes():
    parameters_doc = {
        "orchestrator": {"settings": {"execution_list": ["1_Initial", "2_Install", "missing"]}},
        "stages": {
            "1_Initial": {"stage_settings": {
                "solver_settings": {"problem_domain_sub_model_part_list": ["PorousDomain.Soil"]},
            }},
            "2_Install": {"stage_settings": {
                "solver_settings": {"problem_domain_sub_model_part_list":
                                    ["PorousDomain.Soil", "PorousDomain.Wall"]},
            }},
        },
    }

    stages = external_deck.styx_stages(parameters_doc)

    assert [stage.id for stage in stages] == ["1_Initial", "2_Install"]
    assert stages[0].name == "Initial"
    assert stages[0].parent is None
    assert stages[0].activate == []
    assert stages[0].deactivate == ["Wall"]
    assert stages[1].parent == "1_Initial"
    assert stages[1].activate == ["Wall"]
    assert stages[1].deactivate == []


def test_kratos_coordinate_conversion_refuses_nodes_off_the_section_plane():
    world = {1: (1.0, 2.0, 0.0), 2: (3.0, 4.0, 1e-3)}

    with pytest.raises(ValueError, match="1 node\\(s\\).*off the z = 0 plane"):
        writer._kratos_coordinates(world, 2)

    assert writer._kratos_coordinates({1: (1.0, 2.0, 0.0)}, 2) == {
        1: (1.0, 2.0, 0.0),
    }


def test_drawn_order_is_consistent_across_a_bent_polyline():
    world = {
        1: (2.0, 0.0, 0.0), 2: (0.0, 0.0, 0.0),
        3: (2.0, 2.0, 0.0), 4: (2.0, 1.0, 0.0),
    }

    assert writer._drawn_order([[1, 2], [3, 4]], [(0.0, 0.0), (2.0, 0.0),
                                                  (2.0, 2.0)], world) == [
        [2, 1], [4, 3],
    ]


def test_number_conditions_uses_its_own_ids_and_deduplicates_part_nodes():
    numbered, parts = writer._number_conditions(
        [("load", "LineLoadCondition2D2N", [[8, 3], [3, 5]])],
        {"load": "Load"},
        {3: 30, 5: 50, 8: 80},
    )

    assert numbered == [("LineLoadCondition2D2N", [(1, 0, [80, 30]),
                                                     (2, 0, [30, 50])])]
    assert parts == [("Load", [30, 50, 80], [], [1, 2])]


def test_seepage_iteration_warning_counts_unique_face_nodes():
    project = SimpleNamespace(stages=[SimpleNamespace(name="Short step", max_iterations=2)])

    warning = writer._seepage_iterations(
        project, [("water", "LineSeepageCondition2D2N", [[1, 2], [2, 3]])],
    )

    assert len(warning) == 1
    assert "allows 2 iterations" in warning[0]
    assert "faces have 3 nodes" in warning[0]
    assert writer._seepage_iterations(
        SimpleNamespace(stages=[SimpleNamespace(name="Long step", max_iterations=3)]),
        [("water", "LineSeepageCondition2D2N", [[1, 2], [2, 3]])],
    ) == []


def test_coupled_soil_warns_when_a_stage_has_no_fixed_water_pressure():
    project = muskat(
        conditions=HEADS,
        stages=[Stage(id="dry", name="Dry", calculation="Plastic",
                      deactivate=["left_head", "right_head"])],
    )

    warnings = condition_checks.warnings(project)

    assert any("in stage 'Dry' no fixed water pressure condition is on" in warning
               for warning in warnings)
    assert any("self weight builds up pressures" in warning for warning in warnings)


def test_interfaces_without_specs_leave_rows_untouched_and_bad_element_shapes_are_refused():
    rows = [[1, 2, 3]]
    split = interfaces.split_mesh([], rows, {})

    assert rows == [[1, 2, 3]]
    assert split.renamed == [{}]
    with pytest.raises(interfaces.InterfaceError, match="5-node element"):
        interfaces._edges_of([1, 2, 3, 4, 5])


def test_interface_segment_is_reversed_to_follow_the_drawn_path():
    spec = interfaces.Spec("contact", [(0.0, 0.0), (2.0, 0.0)], [[2, 1]], True, "both")

    assert interfaces._facing(spec, [2, 1, 9], {
        1: (0.0, 0.0, 0.0), 2: (2.0, 0.0, 0.0),
    }) == [1, 2, 9]
    with pytest.raises(interfaces.InterfaceError, match="at least two points"):
        interfaces._nearest_leg((0.0, 0.0), [(0.0, 0.0)])


def test_interface_materials_preserve_user_values_and_refuse_unresolvable_stiffness():
    project = seed_project()
    section = InterfaceSection(
        id="contact", name="Contact", variables={
            "INTERFACE_NORMAL_STIFFNESS": 900.0,
            "INTERFACE_SHEAR_STIFFNESS": 90.0,
        },
    )
    warnings = []
    derived = []

    variables = materials._interface_variables(
        section, project, warnings, adjacent=None, derived=derived,
    )

    assert variables["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
    assert variables["INTERFACE_NORMAL_STIFFNESS"] == 900.0
    assert variables["INTERFACE_SHEAR_STIFFNESS"] == 90.0
    assert derived == ["interface section 'Contact': GEO_DRAINAGE_TYPE"]
    assert warnings == []

    with pytest.raises(materials.MaterialError, match="neither a soil material"):
        materials._interface_variables(
            InterfaceSection(id="missing", name="Missing"), project, [], None, [],
        )


def test_gid_flow_output_includes_hydraulic_results_and_optional_seepage_rate():
    output = parameters._gid_output("flow-results", gravity=False, flow=True, seepage=True)
    configuration = output["Parameters"]["postprocess_parameters"]["result_file_configuration"]

    assert output["Parameters"]["output_name"] == "flow-results"
    assert "WATER_PRESSURE" in configuration["nodal_results"]
    assert "FLUID_FLUX_VECTOR" in configuration["nodal_results"]
    assert "NODAL_WATER_FLOW_RATE" in configuration["nodal_results"]
    assert "HYDRAULIC_HEAD" not in configuration["gauss_point_results"]


def test_mdpa_element_labels_skip_undefined_nodes_and_order_by_element_id():
    labels = mdpa_reader._element_labels(
        {1: (0.0, 0.0, 0.0), 2: (2.0, 0.0, 0.0), 3: (0.0, 2.0, 0.0)},
        [(8, [99]), (4, [1, 2, 3])],
    )

    assert labels == [[4, 2 / 3, 2 / 3, 0.0]]


def test_external_deck_parameters_fail_with_a_user_facing_missing_file_message(tmp_path):
    deck = SimpleNamespace(directory=str(tmp_path), parameters="missing.json")

    with pytest.raises(external_deck.DeckError, match="no deck parameters"):
        external_deck._parameters(deck)


def test_solid_model_reentrant_session_does_not_finalize_a_caller_owned_gmsh():
    import gmsh

    with solid_model.session():
        with solid_model.session():
            assert gmsh.isInitialized()
        assert gmsh.isInitialized()


def test_kratos_main_runs_the_requested_parameter_file(monkeypatch):
    seen = []
    monkeypatch.setattr(kratos_main, "run", seen.append)

    assert kratos_main.main(["kratos_main.py", "project.json"]) == 0
    assert seen == [Path("project.json")]


def test_external_deck_rejects_json_without_a_stages_object(tmp_path):
    (tmp_path / "parameters.json").write_text('{"problem_data": {}}', encoding="utf-8")
    deck = SimpleNamespace(directory=str(tmp_path), parameters="parameters.json")

    with pytest.raises(external_deck.DeckError, match='no "stages" to run'):
        external_deck._parameters(deck)


def test_external_deck_reports_unreadable_parameter_json(tmp_path):
    (tmp_path / "parameters.json").write_text("{", encoding="utf-8")
    deck = SimpleNamespace(directory=str(tmp_path), parameters="parameters.json")

    with pytest.raises(external_deck.DeckError, match="could not be read"):
        external_deck._parameters(deck)


def test_structural_materials_refuse_missing_required_properties():
    prop = SimpleNamespace(
        constitutive_law=materials.BEAM_LAW,
        variables={},
        number=lambda _name: None,
    )

    with pytest.raises(materials.MaterialError, match="YOUNG_MODULUS.*I33"):
        materials._check(prop, "section 'missing'")


@pytest.mark.parametrize("dimension, row, coordinates, expected", [
    (2, [1, 3, 2],
     {1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0)}, [1, 2, 3]),
    (2, [1, 3, 2, 6, 5, 4],
     {1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0)},
     [1, 2, 3, 4, 5, 6]),
    (3, [2, 1, 3, 4],
     {1: (0, 0, 0), 2: (1, 0, 0), 3: (0, 1, 0), 4: (0, 0, 1)},
     [1, 2, 3, 4]),
])
def test_writer_repairs_negative_jacobians_without_losing_midside_order(
        dimension, row, coordinates, expected):
    original = list(row)

    fixed = writer._oriented([row], coordinates, dimension)

    assert fixed == [expected]
    assert writer._signed_measure(
        [coordinates[tag] for tag in fixed[0][:dimension + 1]], dimension) > 0
    assert row == original
    assert writer._oriented(fixed, coordinates, dimension) == fixed


def test_interface_export_refuses_a_contact_without_mesh():
    from tests.test_kratos_interfaces import interfaced_project

    project = interfaced_project()

    with pytest.raises(writer.ExportError, match="Wall contact.*no mesh along its line"):
        writer._interface_elements(project, 2, [], [], [], {}, {}, [])


def test_interface_export_translates_topology_failures(monkeypatch):
    from tests.test_kratos_interfaces import interfaced_project

    project = interfaced_project(side="left", structure=None, points=[[0, 0], [1, 0]])
    monkeypatch.setattr(writer, "_tagged", lambda _: {"interface_1": [10]})
    monkeypatch.setattr(writer, "_segments", lambda _: [[1, 2]])

    def broken_split(*_args):
        raise interfaces.InterfaceError("contact crosses an unsupported junction")

    monkeypatch.setattr(interfaces, "split_mesh", broken_split)

    with pytest.raises(writer.ExportError, match="contact crosses an unsupported junction"):
        writer._interface_elements(project, 2, [], [], [], {}, {}, [])


def test_contact_grouping_excludes_structures_and_faces_with_no_common_soil_owner():
    held = [1, 2, 4, 5]
    unheld = [1, 2, 5, 6]
    blocks = [
        ("wall", "Beam", [[4, 5, 6]]),
        ("soil_a", "Triangle", [[4, 5, 7]]),
        ("soil_b", "Triangle", [[6, 8, 9]]),
    ]

    assert writer._interface_by_body(
        [held, unheld], 2, blocks, frozenset({"soil_a", "soil_b"})) == [
            ("soil_a", [held]),
        ]


def test_a_condition_without_an_owning_soil_element_is_not_relocated():
    rows = [[1, 9]]
    split = interfaces.Split(duplicates={4: 1}, renamed=[{1: 4}])

    writer._follow_the_soil([("load", "LineLoad", rows)], [[1, 2, 3]], split)

    assert rows == [[1, 9]]


@pytest.mark.parametrize("missing", ["head", "tail"])
def test_anchor_export_refuses_a_missing_endpoint_mesh_node(monkeypatch, missing):
    from tests.models.excavation import excavation_project

    project = excavation_project(staged=False)
    anchor = project.plane_anchors[0]
    anchor = anchor.model_copy(update={"name": "Test anchor"})
    project = project.model_copy(update={"anchors": [anchor]})
    head = (*anchor.head, 0.0)
    tail = (*anchor.tail, 0.0)
    world = {1: head} if missing == "tail" else {2: tail}
    monkeypatch.setattr(writer, "_tagged", lambda _: {})
    monkeypatch.setattr(writer, "_harvest",
                        lambda *_args, **_kwargs: [("wall", "Beam", [[1]])])

    with pytest.raises(writer.ExportError, match=f"Test anchor.*no mesh node at its {missing}"):
        writer._anchor_ties(project, 2, world)


def test_anchor_node_lookup_never_selects_a_coincident_nonstructural_node():
    project = seed_project()
    world = {1: (1, 2, 0), 2: (1, 2, 0)}

    assert writer._node_at((1, 2), project, world, {2}) == 2
    assert writer._node_at((1, 2), project, world, set()) is None


def test_panel_lookup_selects_the_named_panel():
    from core.model.schemas import Panel
    from core.model.templates import blank_project

    panel = Panel(id="panel", name="Panel", section="shell",
                  footprint=[(0, 0), (1, 0)], y_top=0, y_toe=-2)
    project = blank_project().model_copy(update={"beams": [panel]})

    assert writer._panel_of(project, "panel") is panel


@pytest.mark.parametrize("rows, message", [
    ([], "River load.*no mesh along its line"),
    ([[1, 2, 3, 4]], "no Kratos condition is mapped.*4 nodes"),
])
def test_normal_load_export_refuses_missing_or_unsupported_mesh(monkeypatch, rows, message):
    from tests.test_kratos_normal_loads import normal_load_project

    monkeypatch.setattr(writer, "_tagged", lambda _: {"normal_1": [10]})
    monkeypatch.setattr(writer, "_segments", lambda _: rows)

    with pytest.raises(writer.ExportError, match=message):
        writer._normal_load_conditions(normal_load_project(), 2, [])


def test_export_names_collapse_repeated_separators_and_refuse_numeric_prefixes():
    assert writer._sanitise("  Wall / contact___A  ") == "Wall_contact_A"
    assert writer._sanitise("123 wall") == ""


def test_seepage_export_refuses_a_drawn_line_without_mesh(monkeypatch):
    from core.model.schemas import SeepageCondition
    from core.model.templates import blank_project

    condition = SeepageCondition(id="drain", name="Drain", on="line",
                                points=[(0, 0), (1, 0)])
    project = blank_project().model_copy(update={"boundary_conditions": [condition]})
    monkeypatch.setattr(writer, "_tagged", lambda _: {})

    with pytest.raises(writer.ExportError, match="Drain.*no mesh along its line"):
        writer._seepage_conditions(project, [], {}, [])


def test_seepage_export_warns_when_no_edge_lies_on_the_selected_face():
    from core.model.schemas import SeepageCondition
    from core.model.templates import blank_project

    condition = SeepageCondition(id="drain", name="Drain", on="face", face="left")
    project = blank_project().model_copy(update={"boundary_conditions": [condition]})
    world = {1: (0, 0, 0), 2: (1, 0, 0), 3: (1, -1, 0)}
    warnings = []

    assert writer._seepage_conditions(
        project, [("soil", "Triangle", [[1, 2, 3]])], world, warnings) == []
    assert len(warnings) == 1
    assert "Drain" in warnings[0]
    assert "left face, which has no soil edge" in warnings[0]


def test_a_condition_on_an_absent_soil_body_is_omitted_with_a_warning(monkeypatch):
    from core.model.schemas import WaterPressureCondition
    from core.model.templates import blank_project

    condition = WaterPressureCondition(id="water", name="Water", on="part",
                                      part="soil_missing", fluid_pressure_type="Uniform")
    project = blank_project().model_copy(update={"boundary_conditions": [condition]})
    monkeypatch.setattr(writer, "_tagged", lambda _: {})
    warnings = []

    assert writer._condition_targets(project, 2, [], {}, {}, {}, {}, warnings) == ([], [])
    assert len(warnings) == 1
    assert "soil_missing" in warnings[0]
    assert "has no soil" in warnings[0]


@pytest.mark.parametrize("on, points", [
    ("line", [(0, 0), (1, 0)]),
    ("point", [(0, 0)]),
])
def test_drawn_water_conditions_without_mesh_are_refused(monkeypatch, on, points):
    from core.model.schemas import WaterPressureCondition
    from core.model.templates import blank_project

    condition = WaterPressureCondition(id="water", name="Water", on=on,
                                      points=points, fluid_pressure_type="Uniform")
    project = blank_project().model_copy(update={"boundary_conditions": [condition]})
    monkeypatch.setattr(writer, "_tagged", lambda _: {})

    with pytest.raises(writer.ExportError, match=f"Water.*no mesh at its {on}"):
        writer._condition_targets(project, 2, [], {}, {}, {}, {}, [])
