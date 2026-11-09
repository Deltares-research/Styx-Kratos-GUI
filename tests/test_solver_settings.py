"""A stage's expert solver settings (`core.model.solver`): their defaults, which apply,
what is fixed, what a stage may store, and the deck they write.

The browser resolves the same catalogue; `tests/test_solver_parity.py` holds the two
together. This module says what the answers are."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from core.kratos import external_deck, parameters
from core.model import solver, stages
from core.model.schemas import Project, Stage
from tests.models import muskat as muskat_model


def values(rows: list[dict]) -> dict:
    return {row["key"]: row["value"] for row in rows}


def row(rows: list[dict], key: str) -> dict:
    return next(each for each in rows if each["key"] == key)


# ── Defaults, by calculation type and time integration ──────────────────────

def test_a_mechanical_stage_is_solved_as_the_reference_deck_is():
    """Newton-Raphson with a scaled Skyline LU, one attempt per step: the reference
    deck's, so a stage that changes nothing is written as it was before these settings
    could be chosen."""
    rows = solver.resolve("mechanical", "static")
    assert values(rows)["strategy_type"] == solver.NEWTON_RAPHSON
    linear = row(rows, "linear_solver_type")
    assert (linear["value"], linear["locked"]) == (solver.SKYLINE_LU, None)
    assert values(rows)["linear_solver_scaling"] is True
    assert values(rows)["number_cycles"] == 1


def test_the_linear_solver_cannot_be_changed_under_quasi_newton():
    rows = solver.resolve("mechanical", "static", {"strategy_type": "quasi_newton",
                                                  "linear_solver_type": "amgcl"})
    assert values(rows)["linear_solver_type"] == solver.SPARSE_LU
    assert "quasi-Newton" in row(rows, "linear_solver_type")["locked"]
    assert not row(rows, "linear_solver_type")["overridden"]
    # The quasi-Newton strategy uses no other linear solver, so nothing of one is shown.
    assert not {"linear_solver_scaling", "linear_solver_tolerance"} & set(values(rows))


def test_another_strategy_offers_the_reference_linear_solver_and_its_settings():
    rows = values(solver.resolve("mechanical", "static",
                                 {"strategy_type": "newton_raphson"}))
    assert rows["linear_solver_type"] == solver.SKYLINE_LU
    assert rows["linear_solver_scaling"] is True
    assert "quasi_newton_type" not in rows


def test_each_linear_solver_has_only_its_own_settings():
    amgcl = values(solver.resolve("mechanical", "static", {
        "strategy_type": "newton_raphson", "linear_solver_type": "amgcl"}))
    assert amgcl["linear_solver_smoother_type"] == "ilu0"
    assert amgcl["linear_solver_gmres_krylov_space_dimension"] == 100
    assert amgcl["linear_solver_scaling"] is False
    assert "linear_solver_preconditioner_type" not in amgcl
    bicgstab = values(solver.resolve("mechanical", "static", {
        "strategy_type": "newton_raphson", "linear_solver_type": "bicgstab"}))
    assert bicgstab["linear_solver_preconditioner_type"] == "ilu0"
    assert bicgstab["linear_solver_max_iteration"] == 200
    assert "linear_solver_smoother_type" not in bicgstab
    # A Krylov method that does not restart has no restart length.
    plain = values(solver.resolve("mechanical", "static", {
        "strategy_type": "newton_raphson", "linear_solver_type": "amgcl",
        "linear_solver_krylov_type": "bicgstab"}))
    assert "linear_solver_gmres_krylov_space_dimension" not in plain


def test_a_dynamic_stage_has_a_time_scheme_and_a_static_one_has_none():
    static = values(solver.resolve("mechanical", "static"))
    assert not {"scheme_type", "newmark_beta", "rayleigh_m"} & set(static)
    dynamic = solver.resolve("mechanical", "dynamic")
    assert values(dynamic)["scheme_type"] == "newmark"
    assert values(dynamic)["newmark_beta"] == 0.25
    assert values(dynamic)["rayleigh_k"] == 0.0
    assert not row(dynamic, "scheme_type")["locked"]


def test_rayleigh_damping_is_a_stage_setting_not_an_expert_one():
    assert {solver.BY_KEY[key].get("panel") for key in ("rayleigh_m", "rayleigh_k")}         == {"stage"}
    assert all("panel" not in setting for setting in solver.SETTINGS
               if not setting["key"].startswith("rayleigh_"))


def test_backward_euler_in_a_mechanical_stage_has_no_newmark_or_damping():
    rows = values(solver.resolve("mechanical", "dynamic", {"scheme_type": "backward_euler"}))
    assert not {"newmark_beta", "newmark_gamma", "newmark_theta", "rayleigh_m"} & set(rows)


def test_a_transient_flow_chooses_its_scheme_and_backward_euler_has_no_theta():
    newmark = values(solver.resolve("flow", "dynamic", {}, "linear"))
    assert newmark["newmark_theta"] == 0.5
    assert "newmark_beta" not in newmark, "a flow stage has no inertia"
    euler = values(solver.resolve("flow", "dynamic", {"scheme_type": "backward_euler"},
                                  "linear"))
    assert "newmark_theta" not in euler


def test_a_flow_stage_has_its_models_strategy_and_the_flow_defaults():
    rows = values(solver.resolve("flow", "static", {}, "newton_raphson"))
    assert rows["strategy_type"] == "newton_raphson"
    assert rows["linear_solver_type"] == solver.SPARSE_LU
    assert (rows["reduction_factor"], rows["increase_factor"]) == (1.0, 1.0)
    assert rows["reform_dofs_at_each_step"] is True
    assert "move_mesh_flag" not in rows, "nothing in a flow stage moves"


def test_a_seepage_face_fixes_the_strategy_and_one_attempt_per_step():
    rows = solver.resolve("flow", "static", {"strategy_type": "quasi_newton",
                                            "number_cycles": 4},
                          "newton_raphson_with_seepage")
    assert values(rows)["strategy_type"] == "newton_raphson_with_seepage"
    assert row(rows, "strategy_type")["locked"]
    assert values(rows)["number_cycles"] == 1
    assert row(rows, "number_cycles")["locked"]


def test_the_linear_strategy_has_no_iterations_to_control():
    rows = solver.resolve("mechanical", "static", {"strategy_type": "linear"})
    assert not solver.iterates(rows)
    assert not {"min_iterations", "number_cycles", "reduction_factor"} & set(values(rows))
    assert solver.iterates(solver.resolve("mechanical", "static"))


def test_a_setting_that_does_not_apply_is_kept_but_not_shown():
    overrides = {"strategy_type": "quasi_newton", "min_alpha": 0.3}
    assert "min_alpha" not in values(solver.resolve("mechanical", "static", overrides))
    back = {**overrides, "strategy_type": "line_search"}
    assert values(solver.resolve("mechanical", "static", back))["min_alpha"] == 0.3


# ── What a stage may store ──────────────────────────────────────────────────

def test_a_stage_stores_only_what_it_changed():
    assert Stage(id="s", name="S").solver_settings == {}


@pytest.mark.parametrize("settings, words", [
    ({"no_such_setting": 1}, "no solver setting 'no_such_setting'"),
    ({"strategy_type": "newton_raphson_with_seepage"}, "must be one of"),
    ({"block_builder": 1}, "true or false"),
    ({"linear_solver_tolerance": 0}, "must be more than 0"),
    ({"quasi_newton_max_rank": 2.5}, "whole number"),
    ({"reduction_factor": 1.5}, "at most 1"),
    ({"min_alpha": float("inf")}, "must be a number"),
])
def test_a_setting_a_stage_cannot_have_is_refused_by_name(settings, words):
    with pytest.raises(ValidationError, match=words):
        Stage(id="s", name="S", solver_settings=settings)


def test_numbers_are_stored_as_kratos_reads_them():
    stage = Stage(id="s", name="S", solver_settings={"reduction_factor": 1,
                                                     "min_iterations": 4.0})
    assert stage.solver_settings == {"reduction_factor": 1.0, "min_iterations": 4}
    assert isinstance(stage.solver_settings["min_iterations"], int)


# ── The deck ────────────────────────────────────────────────────────────────

def solver_settings(stage: parameters.Stage) -> dict:
    deck = json.loads(parameters.project_parameters([], [], [stage]))
    return deck["stages"][stage.name]["stage_settings"]["solver_settings"]


def test_a_mechanical_stage_writes_the_reference_decks_strategy_and_linear_solver():
    written = solver_settings(parameters.Stage(name="1_Stage"))
    assert written["strategy_type"] == "newton_raphson"
    assert written["linear_solver_settings"] == {"solver_type": solver.SKYLINE_LU,
                                                 "scaling": True}
    assert (written["number_cycles"], written["time_stepping"]["time_step"]) == (1, 1.0)
    assert written["residual_absolute_tolerance"] == 1e-9
    assert written["time_stepping"]["max_delta_time_factor"] == 1000.0
    assert "newmark_beta" not in written and "scheme_type" not in written
    assert "quasi_newton_type" not in written


def test_a_quasi_newton_stage_writes_its_update_and_the_sparse_lu_it_uses():
    written = solver_settings(parameters.Stage(
        name="1_Stage", solver_settings=(("strategy_type", "quasi_newton"),)))
    assert written["strategy_type"] == "quasi_newton"
    assert (written["quasi_newton_type"], written["quasi_newton_max_rank"],
            written["quasi_newton_restart_interval"]) == ("lbfgs", 10, 100)
    assert written["linear_solver_settings"] == {"solver_type": solver.SPARSE_LU}


def test_a_stages_own_settings_are_written_and_the_ones_that_do_not_apply_are_not():
    written = solver_settings(parameters.Stage(name="1_Stage", solver_settings=(
        ("strategy_type", "newton_raphson"), ("linear_solver_type", "amgcl"),
        ("linear_solver_tolerance", 1e-8), ("quasi_newton_max_rank", 4))))
    assert written["strategy_type"] == "newton_raphson"
    assert written["linear_solver_settings"]["solver_type"] == "amgcl"
    assert written["linear_solver_settings"]["tolerance"] == 1e-8
    assert written["linear_solver_settings"]["verbosity"] == 0, "AMGCL is told to be quiet"
    assert "quasi_newton_max_rank" not in written


def test_a_dynamic_stage_writes_its_newmark_coefficients():
    written = solver_settings(parameters.Stage(
        name="1_Stage", time_integration="dynamic",
        solver_settings=(("rayleigh_k", 0.002),)))
    assert written["solution_type"] == "Dynamic"
    assert written["scheme_type"] == "newmark"
    assert (written["newmark_beta"], written["rayleigh_k"]) == (0.25, 0.002)


def test_a_mechanical_stage_on_backward_euler_is_kratos_quasi_static_one():
    written = solver_settings(parameters.Stage(
        name="1_Stage", time_integration="dynamic",
        solver_settings=(("scheme_type", "backward_euler"),)))
    assert written["solution_type"] == "quasi_static"
    assert written["scheme_type"] == "backward_euler"
    assert "newmark_beta" not in written and "rayleigh_m" not in written


def test_the_smallest_step_is_written_as_a_time_and_never_more_than_the_step():
    default = solver_settings(parameters.Stage(name="1_Stage", duration=2.0,
                                               time_step=0.5))
    assert default["time_stepping"]["minimum_allowable_value"] == pytest.approx(2e-4)
    coarse = solver_settings(parameters.Stage(
        name="1_Stage", duration=2.0, time_step=0.5,
        solver_settings=(("minimum_step_fraction", 0.5),)))
    assert coarse["time_stepping"]["minimum_allowable_value"] == 0.5
    linear = solver_settings(parameters.Stage(
        name="1_Stage", solver_settings=(("strategy_type", "linear"),)))
    assert "minimum_allowable_value" not in linear["time_stepping"]


def test_one_attempt_per_step_as_the_reference_decks_make_and_more_but_with_seepage():
    assert values(solver.resolve("mechanical", "static"))["number_cycles"] == 1
    assert values(solver.resolve("flow", "static", {}, "newton_raphson"))[
        "number_cycles"] == 1
    assert values(solver.resolve("mechanical", "static", {"number_cycles": 5}))[
        "number_cycles"] == 5
    seepage = solver.resolve("flow", "static", {"number_cycles": 5},
                             "newton_raphson_with_seepage")
    assert values(seepage)["number_cycles"] == 1


def test_cg_is_preconditioned_on_its_diagonal():
    rows = values(solver.resolve("flow", "static", {
        "strategy_type": "newton_raphson", "linear_solver_type": "cg"}, "linear"))
    assert rows["linear_solver_preconditioner_type"] == "diagonal"
    assert rows["linear_solver_max_iteration"] == 200


def test_a_linear_stage_writes_no_convergence_criterion():
    written = solver_settings(parameters.Stage(
        name="1_Stage", solver_settings=(("strategy_type", "linear"),)))
    assert written["strategy_type"] == "linear"
    assert not [key for key in written
                if key in ("convergence_criterion", "max_iterations", "min_iterations")
                or key.endswith("_tolerance")]


def test_a_flow_stage_writes_its_models_strategy():
    written = solver_settings(parameters.Stage(name="1_Flow", calculation="flow",
                                               model_strategy="linear"))
    assert written["solver_type"] == "Pw"
    assert written["strategy_type"] == "linear"
    assert written["linear_solver_settings"] == {"solver_type": solver.SPARSE_LU,
                                                 "scaling": True}
    assert "convergence_criterion" not in written


# ── The flow strategy a model calls for ─────────────────────────────────────

def test_the_model_decides_a_flow_stages_default_strategy():
    saturated = muskat_model.muskat()
    assert set(saturated.model_strategies.values()) == {"linear"}
    unsaturated = muskat_model.muskat(soil=muskat_model.VAN_GENUCHTEN)
    assert set(unsaturated.model_strategies.values()) == {"newton_raphson"}
    face = muskat_model.muskat(conditions=[*muskat_model.HEADS,
                                           muskat_model.SEEPAGE_FACE])
    assert set(face.model_strategies.values()) == {"newton_raphson_with_seepage"}


def test_the_model_strategies_are_published_not_accepted():
    project = muskat_model.muskat()
    echoed = Project.model_validate(project.model_dump(mode="json"))
    assert echoed.model_strategies == project.model_strategies


def test_a_seepage_face_leaves_a_mechanical_stages_strategy_alone():
    """A mechanical deck leaves a seepage face out (`condition_checks`), so its stages
    keep the strategy they would have without it."""
    payload = muskat_model.muskat(conditions=[*muskat_model.HEADS,
                                              muskat_model.SEEPAGE_FACE]
                                  ).model_dump(mode="json")
    payload["stages"] = [{"id": "initial", "name": "Initial stage",
                          "stress_initialisation": "gravity"}]
    assert Project.model_validate(payload).model_strategies == {}


def test_a_mechanical_project_publishes_no_model_strategy():
    payload = muskat_model.muskat().model_dump(mode="json")
    payload["stages"] = [{"id": "initial", "name": "Initial stage"}]
    assert Project.model_validate(payload).model_strategies == {}


# ── Editing ─────────────────────────────────────────────────────────────────

def staged() -> Project:
    payload = muskat_model.muskat().model_dump(mode="json")
    payload["stages"] = [
        {"id": "initial", "name": "Initial stage", "stress_initialisation": "gravity"},
        {"id": "next", "name": "Next", "parent": "initial",
         "solver_settings": {"strategy_type": "newton_raphson"}}]
    return Project.model_validate(payload)


def test_an_edit_sets_one_setting_and_none_puts_its_default_back():
    project = staged()
    listed = stages.edited_solver(project, "next", "linear_solver_type", "amgcl")
    assert listed[1].solver_settings == {"strategy_type": "newton_raphson",
                                         "linear_solver_type": "amgcl"}
    reset = stages.edited_solver(project, "next", "strategy_type", None)
    assert reset[1].solver_settings == {}


def test_a_copy_carries_the_expert_settings():
    listed = stages.copied(staged(), "next")
    assert listed[-1].solver_settings == {"strategy_type": "newton_raphson"}


def test_another_calculation_type_starts_from_its_own_defaults():
    listed = stages.edited(staged(), "initial", "calculation", "flow")
    assert all(stage.solver_settings == {} for stage in listed)


# ── A deck case ─────────────────────────────────────────────────────────────

def test_a_decks_own_settings_are_read_where_they_differ_from_the_defaults():
    found = solver.from_deck({
        "strategy_type": "line_search", "scheme_type": "Newmark",
        "linear_solver_settings": {"solver_type": "amgcl", "tolerance": 1e-7},
        "max_line_search_iterations": 3, "move_mesh_flag": False})
    assert found["strategy_type"] == "line_search"
    assert found["scheme_type"] == "newmark", "Kratos reads it in any case"
    assert found["linear_solver_tolerance"] == 1e-7
    stage = external_deck._styx_stage("1_Stage", {"stage_settings": {
        "solver_settings": {"solution_type": "static", "strategy_type": "line_search",
                            "move_mesh_flag": False,
                            "linear_solver_settings": {"solver_type": "amgcl"}}}},
        None, activate=[], deactivate=[])
    # The deck's line search and AMGCL, and not its default-valued mesh flag.
    assert stage.solver_settings == {"strategy_type": "line_search",
                                     "linear_solver_type": "amgcl"}
