"""Groundwater flow: a project whose phases are all "Groundwater flow" exports Kratos'
steady-state flow of the water alone.

The deck is held to Kratos' own `tests/Muskat/saturated_hydrostatic` (case A of
plan/active/groundwater-flow-plan.md), process for process: its solver block, the two
fixed heads, gravity, the extrapolation of the saturation and the flux, and the results
it writes. The reference values are copied here, as the other deck tests copy theirs, so
the quick tier needs no Kratos checkout.

The rest is what a flow project is: water pressure elements and nothing that acts on a
displacement, a stage per phase, and the export's refusals -- a mix of flow and
deformation phases, a 3D model, a soil with no permeability, a phase with no fixed
head.
"""

from __future__ import annotations

import json

import pytest

from core.geometry import solid_model
from core.kratos import condition_checks, external_deck, materials, writer
from core.model import phases
from core.model.schemas import (Beam, BeamSection, DisplacementCondition, Phase,
                                WaterPressureCondition, standard_conditions)
from tests import mdpa
from tests.models.muskat import FLOW, HEADS, HEIGHT, VAN_GENUCHTEN, head, muskat
from tests.models.muskat import SOIL as REFERENCE_SOIL

# ── Kratos' tests/Muskat/saturated_hydrostatic, copied ──────────────────────

REFERENCE_SOLVER = {
    "solver_type": "Pw",
    "model_part_name": "PorousDomain",
    "domain_size": 2,
    "time_stepping": {"time_step": 1.0, "max_delta_time_factor": 1.0e+03},
    "buffer_size": 2,
    "echo_level": 1,
    "clear_storage": False,
    "compute_reactions": True,
    "move_mesh_flag": False,
    "reform_dofs_at_each_step": True,
    "block_builder": True,
    "solution_type": "Steady_State_Groundwater_Flow",
    "strategy_type": "linear",
    "linear_solver_settings": {"solver_type": "LinearSolversApplication.sparse_lu",
                               "scaling": True},
}
"""Its `solver_settings`, less what names its own mesh and files."""

REFERENCE_HEADS = [
    {"variable_name": "WATER_PRESSURE", "is_fixed": True,
     "fluid_pressure_type": "Hydrostatic", "gravity_direction": 1,
     "reference_coordinate": level, "table": 0, "pressure_tension_cut_off": 1.0e+05,
     "specific_weight": 1.0e+04}
    for level in (3.0, 1.6)
]
"""Its `constraints_process_list`, left then right, less the part names."""

REFERENCE_GRAVITY = {"variable_name": "VOLUME_ACCELERATION", "active": [False, True, False],
                     "value": [0.0, -9.81, 0.0], "table": [0, 0, 0]}
REFERENCE_EXTRAPOLATED = ["EFFECTIVE_SATURATION", "FLUID_FLUX_VECTOR"]
REFERENCE_NODAL_RESULTS = ["WATER_PRESSURE", "EFFECTIVE_SATURATION", "FLUID_FLUX_VECTOR"]
"""The soil is `tests.models.muskat.SOIL`, copied from the same deck."""


# ── The model is tests/models/muskat.py ─────────────────────────────────────

@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


@pytest.fixture(scope="module")
def case_a(gmsh_session):
    return writer.export_project(muskat(order=2))


def stages(export: dict) -> dict:
    return json.loads(export["project_parameters"])["stages"]


def settings(export: dict, stage: str = "1_Flow") -> dict:
    return stages(export)[stage]["stage_settings"]


def without_part(parameters: dict) -> dict:
    return {key: value for key, value in parameters.items() if key != "model_part_name"}


# ── Case A, process for process ─────────────────────────────────────────────

def test_the_solver_is_the_reference_one(case_a):
    solver = settings(case_a)["solver_settings"]
    assert {key: solver[key] for key in REFERENCE_SOLVER} == REFERENCE_SOLVER
    # Nothing a deformation analysis adds: no displacements to reset, no iterations.
    for key in ("reset_totals", "max_iterations", "convergence_criterion", "scheme_type"):
        assert key not in solver
    assert solver["rotation_dofs"] is False


def test_the_heads_are_the_reference_ones(case_a):
    constraints = settings(case_a)["processes"]["constraints_process_list"]
    assert [without_part(p["Parameters"]) for p in constraints] == REFERENCE_HEADS
    assert [p["Parameters"]["model_part_name"] for p in constraints] == [
        "PorousDomain.Left_Edge", "PorousDomain.Right_Edge"]


def test_gravity_is_the_reference_one(case_a):
    loads = settings(case_a)["processes"]["loads_process_list"]
    assert [without_part(p["Parameters"]) for p in loads] == [REFERENCE_GRAVITY]


def test_the_saturation_and_the_flux_are_made_nodal_over_the_soil(case_a):
    auxiliary = settings(case_a)["processes"]["auxiliary_process_list"]
    assert [p["process_name"] for p in auxiliary] == [
        "GeoExtrapolateIntegrationPointValuesToNodesProcess"]
    assert auxiliary[0]["Parameters"] == {"model_part_name": "PorousDomain.soil",
                                          "list_of_variables": REFERENCE_EXTRAPOLATED}


def test_it_writes_the_reference_results_and_the_head(case_a):
    output = settings(case_a)["output_processes"]["gid_output"][0]["Parameters"]
    results = output["postprocess_parameters"]["result_file_configuration"]
    assert results["nodal_results"] == REFERENCE_NODAL_RESULTS
    assert results["gauss_point_results"] == ["HYDRAULIC_HEAD"]


def test_the_soil_is_water_pressure_elements_and_nothing_else(case_a):
    deck = mdpa.parse(case_a["mdpa"])
    assert {block.name for block in deck.elements} == {"SteadyStatePwElement2D6N"}
    assert not deck.conditions


def test_the_material_is_written_as_given(case_a):
    soil = json.loads(case_a["materials"])["properties"][0]["Material"]["Variables"]
    assert soil == REFERENCE_SOIL


def test_a_linear_mesh_gets_the_linear_element(gmsh_session):
    deck = mdpa.parse(writer.export_project(muskat())["mdpa"])
    assert {block.name for block in deck.elements} == {"SteadyStatePwElement2D3N"}


# ── What a flow deck leaves out ─────────────────────────────────────────────

def test_no_displacement_is_fixed_and_the_supports_are_not_warned_about(gmsh_session):
    """Every new project has the standard supports, and a support does nothing to the
    flow: a warning about them would be said in nearly every flow project."""
    supports = [DisplacementCondition(id="bottom", name="Fixed bottom", on="face",
                                      face="bottom", fixed=(True, True, True))]
    export = writer.export_project(muskat(conditions=[*HEADS, *supports]))
    constraints = settings(export)["processes"]["constraints_process_list"]
    assert {p["Parameters"]["variable_name"] for p in constraints} == {"WATER_PRESSURE"}
    assert not any("Fixed bottom" in w for w in export["warnings"])
    # And the rigid-body warning of a deformation model is not said: nothing moves.
    assert not any("rigid body" in w for w in export["warnings"])


def test_the_standard_supports_give_a_flow_project_no_warning():
    project = muskat(conditions=[*standard_conditions(), *HEADS])
    assert condition_checks.warnings(project) == []


def test_a_sheet_pile_is_left_out_and_said(gmsh_session):
    section = BeamSection(id="pile", name="Pile", variables={
        "YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.0, "DENSITY": 7850.0,
        "CROSS_AREA": 0.01, "I33": 1e-4})
    export = writer.export_project(muskat(
        beam_sections=[section],
        beams=[Beam(id="sheetpile", name="Wall", section="pile",
                    points=[(0.8, HEIGHT), (0.8, 2.0)])]))
    deck = mdpa.parse(export["mdpa"])
    assert {block.name for block in deck.elements} == {"SteadyStatePwElement2D3N"}
    assert any("the structures 'Wall' are left out" in w for w in export["warnings"])


def test_a_fixed_pressure_on_the_whole_soil_is_said():
    everywhere = WaterPressureCondition(id="all", name="All", on="domain",
                                        reference_coordinate=3.0)
    warnings = condition_checks.warnings(muskat(conditions=[*HEADS, everywhere]))
    assert any("fixes the water pressure at every node" in w for w in warnings)


def test_gravity_off_is_said():
    warnings = condition_checks.warnings(muskat(gravity=False))
    assert any("gravity is off, so the water has no weight" in w for w in warnings)


# ── Stages ──────────────────────────────────────────────────────────────────

def test_each_phase_is_a_steady_state_with_its_own_heads(gmsh_session):
    low = head("low_right", "right", 1.0)
    export = writer.export_project(muskat(
        conditions=[*HEADS, low],
        phases=[Phase(id="high", name="High", calculation="Groundwater flow",
                      deactivate=["low_right"]),
                Phase(id="low", name="Low", parent="high", calculation="Groundwater flow",
                      activate=["low_right"], deactivate=["right_head"])]))
    deck = stages(export)
    assert list(deck) == ["1_High", "2_Low"]
    levels = [[p["Parameters"]["reference_coordinate"]
               for p in deck[name]["stage_settings"]["processes"]["constraints_process_list"]]
              for name in deck]
    assert levels == [[3.0, 1.6], [3.0, 1.0]]
    for name, start in (("1_High", 0.0), ("2_Low", 1.0)):
        stage = deck[name]["stage_settings"]
        assert stage["solver_settings"]["solver_type"] == "Pw"
        assert stage["problem_data"]["start_time"] == start


def test_a_soil_whose_permeability_follows_the_pressure_is_solved_by_newton(gmsh_session):
    soil = {**REFERENCE_SOIL, **VAN_GENUCHTEN}
    export = writer.export_project(muskat(soil=soil, phases=[
        Phase(id="flow", name="Flow", calculation="Groundwater flow",
              max_iterations=100, tolerated_error=1e-3)]))
    solver = settings(export)["solver_settings"]
    assert {key: solver[key] for key in (
        "strategy_type", "convergence_criterion", "residual_relative_tolerance",
        "residual_absolute_tolerance", "min_iterations", "max_iterations",
        "number_cycles", "reduction_factor", "increase_factor")} == {
        "strategy_type": "newton_raphson", "convergence_criterion": "residual_criterion",
        "residual_relative_tolerance": 1e-3, "residual_absolute_tolerance": 1e-15,
        "min_iterations": 6, "max_iterations": 100, "number_cycles": 1,
        "reduction_factor": 1.0, "increase_factor": 1.0}


def test_a_phase_s_iterations_are_its_own(gmsh_session):
    soil = {**REFERENCE_SOIL, **VAN_GENUCHTEN}
    export = writer.export_project(muskat(soil=soil, phases=[
        Phase(id="flow", name="Flow", calculation="Groundwater flow",
              max_iterations=40, tolerated_error=1e-5)]))
    solver = settings(export)["solver_settings"]
    assert (solver["max_iterations"], solver["residual_relative_tolerance"]) == (40, 1e-5)


def test_a_missing_biot_coefficient_is_derived(gmsh_session):
    soil = {k: v for k, v in REFERENCE_SOIL.items() if k != "BIOT_COEFFICIENT"}
    export = writer.export_project(muskat(soil=soil))
    written = json.loads(export["materials"])["properties"][0]["Material"]["Variables"]
    assert written["BIOT_COEFFICIENT"] == pytest.approx(materials.biot(soil))
    assert any("BIOT_COEFFICIENT" in w for w in export["warnings"])


def test_the_biot_coefficient_is_kratos_own_rule():
    # K = E / (3 (1 - 2 nu)) = 1e7 / 1.2, so 1 - K / K_s with K_s = 1e9.
    assert materials.biot({"YOUNG_MODULUS": 1e7, "POISSON_RATIO": 0.3,
                           "BULK_MODULUS_SOLID": 1e9}) == pytest.approx(1 - 1e7 / 1.2 / 1e9)
    assert materials.biot({}) == 1.0


# ── Refusals ────────────────────────────────────────────────────────────────

def test_flow_and_deformation_phases_cannot_be_mixed():
    project = muskat(phases=[FLOW, Phase(id="load", name="Load", parent="flow")])
    with pytest.raises(phases.PhaseError, match="cannot mix groundwater flow phases"):
        phases.groundwater_flow(project)
    with pytest.raises(writer.ExportError, match=r"\('Flow'\) with deformation phases "
                                                 r"\('Load'\)"):
        writer.export_project(project)


def test_a_project_without_flow_phases_is_not_a_flow_project():
    assert not phases.groundwater_flow(muskat(phases=[]))
    assert not phases.groundwater_flow(muskat(phases=[Phase(id="p", name="P")]))
    assert condition_checks.flow_refusal(muskat(phases=[])) is None


def test_a_3d_flow_project_is_refused():
    project = muskat()
    project.dimension = 3
    assert "2D only for now" in condition_checks.flow_refusal(project)


def test_a_soil_without_permeability_is_refused():
    soil = {k: v for k, v in REFERENCE_SOIL.items() if not k.startswith("PERMEABILITY")}
    assert "'sand' has no PERMEABILITY_XX" in condition_checks.flow_refusal(muskat(soil=soil))


def test_a_phase_with_no_fixed_head_is_refused():
    start = WaterPressureCondition(id="start", name="Start", on="domain",
                                   reference_coordinate=3.0, is_fixed=False)
    refusal = condition_checks.flow_refusal(muskat(conditions=[start]))
    assert "in phase 'Flow' no fixed water pressure condition is on" in refusal


def test_a_head_kept_from_an_earlier_phase_holds_the_next():
    project = muskat(phases=[
        FLOW, Phase(id="after", name="After", parent="flow",
                    calculation="Groundwater flow",
                    deactivate=["left_head", "right_head"])])
    assert condition_checks.flow_refusal(project) is None


def test_an_imported_flow_deck_s_stage_is_a_groundwater_flow_phase():
    stage = {"stage_settings": {"solver_settings": {
        "solution_type": "Steady_State_Groundwater_Flow"}}}
    assert external_deck._calculation(stage, "stage 1") == phases.GROUNDWATER_FLOW
