"""Groundwater flow: a project whose stages are all flow stages exports Kratos'
steady-state flow of the water alone.

The deck is held to Kratos' own `tests/Muskat/saturated_hydrostatic` (case A of
plan/done/groundwater-flow-plan.md), process for process: its solver block, the two
fixed heads, gravity, the extrapolation of the saturation and the flux, and the results
it writes. Case B, `tests/Muskat/van_genuchten_hydrostatic`, is held to its deck the same
way: the Newton-Raphson block, the initial phreatic line and the Van Genuchten soil. The
reference values are copied here, as the other deck tests copy theirs, so the quick tier
needs no Kratos checkout.

The rest is what a flow project is: water pressure elements and nothing that acts on a
displacement, a stage per stage, and the export's refusals -- a mix of flow and
deformation stages, a 3D model, a soil with no permeability, a stage with no fixed
head.
"""

from __future__ import annotations

import json

import pytest

from core.geometry import solid_model
from core.kratos import condition_checks, external_deck, materials, writer
from core.model import stages
from core.model.schemas import (Beam, BeamSection, DisplacementCondition, Stage,
                                SeepageCondition, WaterPressureCondition,
                                standard_conditions)
from tests import mdpa
from tests.models import muskat as muskat_model
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

# ── Kratos' tests/Muskat/van_genuchten_hydrostatic, copied ──────────────────

REFERENCE_SOLVER_B = {
    **{key: value for key, value in REFERENCE_SOLVER.items() if key != "strategy_type"},
    "strategy_type": "newton_raphson",
    "convergence_criterion": "residual_criterion",
    "residual_relative_tolerance": 1.0e-03,
    "residual_absolute_tolerance": 1.0e-15,
    "min_iterations": 6,
    "max_iterations": 100,
    "number_cycles": 1,
    "reduction_factor": 1.0,
    "increase_factor": 1.0,
}
"""Its `solver_settings`, less what names its own mesh and files."""


def as_written(reference: dict) -> dict:
    """A reference deck's solver block as this exporter writes it: where it iterates,
    with Kratos' own smallest step written out, 1e-4 of the stage (`core.model.solver`),
    which the deck leaves to Kratos."""
    out = dict(reference)
    if "number_cycles" in out and "time_stepping" in out:
        out["time_stepping"] = {**out["time_stepping"], "minimum_allowable_value": 1e-4}
    return out


REFERENCE_CONSTRAINTS_B = [
    {"variable_name": "WATER_PRESSURE", "is_fixed": False, "table": [0, 0, 0, 0],
     "fluid_pressure_type": "Phreatic_Multi_Line", "gravity_direction": 1,
     "out_of_plane_direction": 2, "x_coordinates": [-0.25, 5.0e-02, 1.6, 1.7],
     "y_coordinates": [3.22, 3.22, 0.48, 0.48], "z_coordinates": [0.0, 0.0, 0.0, 0.0],
     "specific_weight": 1.0e+04},
    *({"variable_name": "WATER_PRESSURE", "is_fixed": True,
       "fluid_pressure_type": "Hydrostatic", "gravity_direction": 1,
       "reference_coordinate": level, "table": 0, "pressure_tension_cut_off": 1.0e+05,
       "specific_weight": 1.0e+04}
      for level in (3.0, 1.62)),
]
"""Its `constraints_process_list`, less the part names: the phreatic start values on the
whole soil first, then the left and right heads."""

REFERENCE_SOIL_B = {
    "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
    "YOUNG_MODULUS": 1.0e+04,
    "POISSON_RATIO": 0.4,
    "DENSITY_SOLID": 2.29e+03,
    "DENSITY_WATER": 1.01937e+03,
    "POROSITY": 0.3333,
    "BULK_MODULUS_SOLID": 6.7e+19,
    "BULK_MODULUS_FLUID": 1.0e+20,
    "PERMEABILITY_XX": 6.9444e-13,
    "PERMEABILITY_YY": 6.9444e-13,
    "PERMEABILITY_XY": 0.0,
    "DYNAMIC_VISCOSITY": 1.0e-03,
    "BIOT_COEFFICIENT": 1.0,
    "RETENTION_LAW": "VanGenuchtenLaw",
    "SATURATED_SATURATION": 0.403,
    "RESIDUAL_SATURATION": 2.5e-02,
    "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": 2.611e+03,
    "VAN_GENUCHTEN_GN": 1.377,
    "VAN_GENUCHTEN_GL": 1.25,
    "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-05,
}
"""Its MaterialParametersNonLinear.json `Variables`."""
"""The soil is `tests.models.muskat.SOIL`, copied from the same deck."""


# ── The model is tests/models/muskat.py ─────────────────────────────────────

@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


@pytest.fixture(scope="module")
def case_a(gmsh_session):
    return writer.export_project(muskat(order=2))


def deck_stages(export: dict) -> dict:
    return json.loads(export["project_parameters"])["stages"]


def settings(export: dict, stage: str = "1_Flow") -> dict:
    return deck_stages(export)[stage]["stage_settings"]


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


# ── Stages ──────────────────────────────────────────────────────────────────

def test_each_stage_is_a_steady_state_with_its_own_heads(gmsh_session):
    low = head("low_right", "right", 1.0)
    export = writer.export_project(muskat(
        conditions=[*HEADS, low],
        stages=[Stage(id="high", name="High", calculation="flow",
                      deactivate=["low_right"]),
                Stage(id="low", name="Low", parent="high", calculation="flow",
                      activate=["low_right"], deactivate=["right_head"])]))
    deck = deck_stages(export)
    assert list(deck) == ["1_High", "2_Low"]
    levels = [[p["Parameters"]["reference_coordinate"]
               for p in deck[name]["stage_settings"]["processes"]["constraints_process_list"]]
              for name in deck]
    assert levels == [[3.0, 1.6], [3.0, 1.0]]
    for name, start in (("1_High", 0.0), ("2_Low", 1.0)):
        stage = deck[name]["stage_settings"]
        assert stage["solver_settings"]["solver_type"] == "Pw"
        assert stage["problem_data"]["start_time"] == start


# ── Case B: a Van Genuchten soil ────────────────────────────────────────────

@pytest.fixture(scope="module")
def case_b(gmsh_session):
    """Meshed at 0.4 m: the deck does not depend on the size."""
    return writer.export_project(muskat_model.van_genuchten(size=0.4))


def test_a_soil_whose_permeability_follows_the_pressure_is_solved_by_newton(case_b):
    """The reference Newton-Raphson block, with the stage's 100 iterations and its
    tolerance of 1e-3."""
    solver = settings(case_b)["solver_settings"]
    expected = as_written(REFERENCE_SOLVER_B)
    assert {key: solver.get(key) for key in expected} == expected
    assert "reset_totals" not in solver


def test_the_phreatic_start_comes_first_and_the_heads_replace_it(case_b):
    """The project lists the phreatic line last; the deck writes start values before the
    fixed ones, as the reference does, so the heads have the last word on the faces."""
    constraints = settings(case_b)["processes"]["constraints_process_list"]
    assert [without_part(p["Parameters"]) for p in constraints] == REFERENCE_CONSTRAINTS_B
    assert [p["Parameters"]["model_part_name"] for p in constraints] == [
        "PorousDomain", "PorousDomain.Left_Edge", "PorousDomain.Right_Edge"]


def test_the_van_genuchten_soil_is_the_reference_one(case_b):
    soil = json.loads(case_b["materials"])["properties"][0]["Material"]["Variables"]
    assert soil == REFERENCE_SOIL_B
    assert not case_b["warnings"]


def test_a_stage_s_iterations_are_its_own(gmsh_session):
    soil = {**REFERENCE_SOIL, **VAN_GENUCHTEN}
    export = writer.export_project(muskat(soil=soil, stages=[
        Stage(id="flow", name="Flow", calculation="flow",
              max_iterations=40, tolerated_error=1e-5)]))
    solver = settings(export)["solver_settings"]
    assert (solver["max_iterations"], solver["residual_relative_tolerance"]) == (40, 1e-5)


def test_a_dynamic_flow_stage_is_a_transient_flow(gmsh_session):
    export = writer.export_project(muskat(stages=[
        Stage(id="flow", name="Flow", calculation="flow", time_integration="dynamic")]))
    assert settings(export)["solver_settings"]["solution_type"] ==         "Transient_Groundwater_Flow"


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


# ── Case C: a seepage face ──────────────────────────────────────────────────

REFERENCE_SEEPAGE_STRATEGY = {
    "strategy_type": "newton_raphson_with_seepage",
    "convergence_criterion": "residual_criterion",
    "residual_relative_tolerance": 1.0e-04,
    "residual_absolute_tolerance": 1.0e-09,
    "min_iterations": 6,
    "max_iterations": 50,
    "number_cycles": 1,
    "reduction_factor": 1.0,
    "increase_factor": 1.0,
}
"""Kratos' `tests/seepage_tests/fixed_bottom_boundary`: its strategy settings."""

REFERENCE_SEEPAGE_PROCESS = {
    "python_module": "apply_seepage_boundary_process",
    "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
    "process_name": "ApplySeepageBoundaryProcess",
}
"""The same deck's seepage process, less its part name."""


@pytest.fixture(scope="module")
def case_c(gmsh_session):
    """With the reference deck's 50 iterations, so its strategy block can be compared."""
    return writer.export_project(muskat_model.seepage(max_iterations=50))


def test_a_seepage_face_is_solved_by_the_seepage_strategy(case_c):
    solver = settings(case_c)["solver_settings"]
    assert {key: solver[key] for key in REFERENCE_SEEPAGE_STRATEGY} == \
        REFERENCE_SEEPAGE_STRATEGY
    assert solver["solver_type"] == "Pw"


def test_the_seepage_face_is_one_process_on_its_own_part(case_c):
    loads = settings(case_c)["processes"]["loads_process_list"]
    seepage = [p for p in loads if p["process_name"] == "ApplySeepageBoundaryProcess"]
    assert [{k: v for k, v in p.items() if k != "Parameters"} for p in seepage] == [
        REFERENCE_SEEPAGE_PROCESS]
    assert seepage[0]["Parameters"] == {"model_part_name": "PorousDomain.Seepage_face"}
    assert "Seepage_face" in settings(case_c)["solver_settings"][
        "processes_sub_model_part_list"]


def test_the_deck_is_the_stem_muskat_geometry_s(case_c):
    """What the STEM Muskat test of FEA-Tools' GeometryGenerator holds its mesh to: one
    element type, one condition type, the seepage face a part of nodes and conditions,
    each head a part of nodes alone."""
    deck = mdpa.parse(case_c["mdpa"])
    assert {block.name for block in deck.elements} == {"SteadyStatePwElement2D3N"}
    assert {block.name for block in deck.conditions} == {"GeoSeepageCondition2D2N"}
    face = deck.parts["Seepage_face"]
    assert face.nodes and len(face.conditions) == len(face.nodes) - 1
    assert deck.parts["Tail_water"].nodes and not deck.parts["Tail_water"].conditions
    assert not deck.parts["Left_Edge"].conditions


def test_the_seepage_conditions_run_up_the_right_face_from_the_tail_water(case_c):
    """At 0.04 m along the face: 3.52 m of it, 88 edges."""
    deck = mdpa.parse(case_c["mdpa"])
    nodes = {int(row[0]): row[1:] for row in case_c["nodes"]}
    face = deck.parts["Seepage_face"].nodes
    assert all(nodes[n][0] == pytest.approx(muskat_model.WIDTH) for n in face)
    heights = sorted(nodes[n][1] for n in face)
    assert heights[0] == pytest.approx(muskat_model.TAIL_LEVEL)
    assert heights[-1] == pytest.approx(HEIGHT)
    assert len(deck.parts["Seepage_face"].conditions) == 88


def test_a_seepage_stage_writes_the_nodal_flow_rate(case_c):
    output = settings(case_c)["output_processes"]["gid_output"][0]["Parameters"]
    results = output["postprocess_parameters"]["result_file_configuration"]
    assert results["nodal_results"] == [*REFERENCE_NODAL_RESULTS, "NODAL_WATER_FLOW_RATE"]


def test_too_few_iterations_for_the_seepage_face_are_said(case_c):
    """89 nodes on the face, which the strategy opens one per iteration."""
    assert any("allows 50 iterations, and its seepage faces have 89 nodes" in w
               for w in case_c["warnings"])
    export = writer.export_project(muskat_model.seepage(max_iterations=100))
    assert not any("seepage faces have" in w for w in export["warnings"])


def test_a_quadratic_seepage_face_has_three_node_conditions(gmsh_session):
    deck = mdpa.parse(writer.export_project(muskat_model.seepage(order=2))["mdpa"])
    assert {block.name for block in deck.conditions} == {"GeoSeepageCondition2D3N"}
    for block in deck.conditions:
        assert all(len(row) == 3 for row in block.entries.values())


def test_a_seepage_face_on_a_face_is_every_edge_of_it(gmsh_session):
    face = SeepageCondition(id="top", name="Top", on="face", face="top")
    deck = mdpa.parse(writer.export_project(muskat(conditions=[*HEADS, face]))["mdpa"])
    nodes = deck.parts["Top"].nodes
    assert len(deck.parts["Top"].conditions) == len(nodes) - 1
    assert all(deck.nodes[n][1] == pytest.approx(HEIGHT) for n in nodes)


def test_a_seepage_line_through_the_soil_is_refused(gmsh_session):
    inside = SeepageCondition(id="inside", name="Inside", on="line",
                              points=[(0.8, 1.0), (0.8, 3.0)])
    with pytest.raises(writer.ExportError,
                       match="'Inside' runs through the soil: .* mesh edges have soil on "
                             "both sides"):
        writer.export_project(muskat(conditions=[*HEADS, inside]))


def test_a_seepage_face_in_a_deformation_project_is_left_out_and_said(gmsh_session):
    face = SeepageCondition(id="top", name="Top", on="face", face="top")
    project = muskat(conditions=[*standard_conditions(), *HEADS, face],
                     stages=[Stage(id="p", name="P", stress_initialisation="gravity")])
    export = writer.export_project(project)
    assert any("seepage condition 'Top' is left out: a seepage face belongs to a "
               "groundwater flow calculation" in w for w in export["warnings"])
    assert not mdpa.parse(export["mdpa"]).conditions
    solver = deck_stages(export)["1_P"]["stage_settings"]["solver_settings"]
    assert solver["strategy_type"] == "newton_raphson"


def test_a_seepage_condition_takes_a_face_or_a_line_only():
    with pytest.raises(ValueError):
        SeepageCondition(id="s", name="S", on="domain")
    with pytest.raises(ValueError, match="needs face"):
        SeepageCondition(id="s", name="S", on="face")


# ── Refusals ────────────────────────────────────────────────────────────────

def test_flow_and_deformation_stages_cannot_be_mixed():
    project = muskat(stages=[FLOW, Stage(id="load", name="Load", parent="flow")])
    with pytest.raises(stages.StageError, match="cannot mix flow stages"):
        stages.groundwater_flow(project)
    with pytest.raises(writer.ExportError, match=r"\('Flow'\) with mechanical stages "
                                                 r"\('Load'\)"):
        writer.export_project(project)


def test_a_project_without_flow_stages_is_not_a_flow_project():
    assert not stages.groundwater_flow(muskat(stages=[]))
    assert not stages.groundwater_flow(muskat(stages=[Stage(id="p", name="P")]))
    assert condition_checks.flow_refusal(muskat(stages=[])) is None


def test_a_3d_flow_project_is_refused():
    project = muskat()
    project.dimension = 3
    assert "2D only for now" in condition_checks.flow_refusal(project)


def test_a_soil_without_permeability_is_refused():
    soil = {k: v for k, v in REFERENCE_SOIL.items() if not k.startswith("PERMEABILITY")}
    assert "'sand' has no PERMEABILITY_XX" in condition_checks.flow_refusal(muskat(soil=soil))


def test_a_stage_with_no_fixed_head_is_refused():
    start = WaterPressureCondition(id="start", name="Start", on="domain",
                                   reference_coordinate=3.0, is_fixed=False)
    refusal = condition_checks.flow_refusal(muskat(conditions=[start]))
    assert "in stage 'Flow' no fixed water pressure condition is on" in refusal


def test_a_head_kept_from_an_earlier_stage_holds_the_next():
    project = muskat(stages=[
        FLOW, Stage(id="after", name="After", parent="flow",
                    calculation="flow",
                    deactivate=["left_head", "right_head"])])
    assert condition_checks.flow_refusal(project) is None


def test_an_imported_flow_deck_s_stage_is_a_groundwater_flow_stage():
    stage = {"stage_settings": {"solver_settings": {
        "solution_type": "Steady_State_Groundwater_Flow"}}}
    assert external_deck._calculation(stage) == {"calculation": stages.FLOW,
                                                 "time_integration": "static"}
    stage["stage_settings"]["solver_settings"]["solution_type"] = \
        "Transient_Groundwater_Flow"
    assert external_deck._calculation(stage)["time_integration"] == "dynamic"
