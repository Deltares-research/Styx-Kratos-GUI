"""Focused tests for Kratos deck helpers and their refusal/reporting paths."""

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
