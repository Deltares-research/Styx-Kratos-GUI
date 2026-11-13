"""Reading the solver's convergence off a Kratos log (`core.results.convergence`).

The first three cases are the test samples of the ConvergencePlotter in Deltares'
FEA-Tools repository, which the parser is ported from, with the same expected values.
The fixtures in `tests/fixtures/convergence/` are real logs of this program, trimmed to
the lines the parser reads:

*   `seepage.log`: one flow stage of 20 iterations, one of them cut in two by a stage
    marker, as logs were before Kratos' output was unbuffered;
*   `staged_cut_lines.log`: seven stages of an excavation, one iteration each, with the stage
    markers inside other lines and before the iterations of their own stage;
*   `iteration_limit.log`: a step that hit the limit of 50 iterations, was cut back,
    and ended in a traceback.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from core.analysis import calculation
from core.results import catalog, convergence

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "convergence"
MARKER = calculation.STAGE_MARKER


def residual(relative, absolute, relative_target="0.0001", absolute_target="1e-09"):
    return (f"RESIDUAL CRITERION:  :: [ Obtained ratio = {relative}; Expected ratio = "
            f"{relative_target}; Absolute norm = {absolute}; Expected norm =  "
            f"{absolute_target}]")


def relative(data):
    return [iteration["relative"] for iteration in data["iterations"]]


def absolute(data):
    return [iteration["absolute"] for iteration in data["iterations"]]


def met(data):
    """The iterations where the criterion was met, counted from 1 as the original."""
    return [n for n, iteration in enumerate(data["iterations"], start=1)
            if iteration["met"]]


# ── The original's samples ──────────────────────────────────────────────────

def test_residuals_and_targets_and_incomplete_lines_are_left_out():
    log = "\n".join([
        "GeoMechanics Analysis: Analysis -START-",
        "GeoMechanics Analysis: cycle:  1",
        "GeoMechanics Analysis: STEP      :  1",
        "GeoMechanics Analysis: DELTA_TIME:  0.25",
        "GeoMechanics Analysis: TIME      :  0.25",
        *(residual(r, a, "0.02") for r, a in [
            ("0.655123", "0.784218"), ("0.439526", "0.526137"), ("0.336044", "0.402263"),
            ("0.288272", "0.345078"), ("0.265138", "0.317384"), ("0.254124", "0.304201"),
            ("0.246399", "0.294953"), ("0.240774", "0.28822")]),
        "RESIDUAL CRITERION:  :: [ Obtained ratio = 0.236419; Expected ratio = 0",
        "RESIDUAL CRITERION:  :: [ Obtained ratio = 0",
    ])

    data = convergence.parse(log)

    assert relative(data) == [0.655123, 0.439526, 0.336044, 0.288272, 0.265138,
                              0.254124, 0.246399, 0.240774]
    assert absolute(data) == [0.784218, 0.526137, 0.402263, 0.345078, 0.317384,
                              0.304201, 0.294953, 0.28822]
    assert {i["relative_target"] for i in data["iterations"]} == {0.02}
    assert {i["absolute_target"] for i in data["iterations"]} == {1e-09}
    assert data["steps"] == [{"at": 0, "time": 0.25, "cycle": 1}]
    assert data["stages"] == [{"at": 0, "index": 1, "of": None, "name": None}]


def test_convergence_points():
    step = ["GeoMechanics Analysis: --------------------------------------",
            "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  0.25"]
    achieved = ["RESIDUAL CRITERION: Convergence is achieved",
                "ResidualBasedNewtonRaphsonStrategy: Convergence achieved after 1 / 3 "
                "iterations"]
    log = "\n".join([
        "GeoMechanics Analysis: Analysis -START-",
        *step, residual("9.94729e-13", "8.18637e-10"), *achieved,
        *step, residual("0.239594", "1.9614e-10"), *achieved,
        *step, residual("0.716387", "1.40513e-10"), *achieved,
        *step, *[residual("1.56594", "2.20035e-10")] * 3, *achieved,
        "GeoMechanics Analysis: Analysis -END-",
    ])

    assert met(convergence.parse(log)) == [1, 2, 3, 6]


def test_the_water_pressure_criterion_over_two_steps():
    log = "\n".join([
        "GeoMechanics Analysis: Analysis -START-",
        "GeoMechanics Analysis: TIME      :  0.002",
        "CONVERGENCE CHECK:",
        " WATER_PRESSURE : ratio = 0.05; exp.ratio = 0.0001 abs = 0.07 exp.abs = 1e-09",
        "CONVERGENCE CHECK:",
        " WATER_PRESSURE : ratio = 0.00003; exp.ratio = 0.0001 abs = 0.04 exp.abs = 1e-09",
        "*** CONVERGENCE IS ACHIEVED ***",
        "GeoMechanics Analysis: TIME      :  0.004",
        " WATER_PRESSURE : ratio = 0.00002; exp.ratio = 0.0001 abs = 0.025 exp.abs = 1e-09",
        "*** CONVERGENCE IS ACHIEVED ***",
        "GeoMechanics Analysis: Analysis -END-",
    ])

    data = convergence.parse(log)

    assert relative(data) == [0.05, 0.00003, 0.00002]
    assert absolute(data) == [0.07, 0.04, 0.025]
    assert [step["at"] for step in data["steps"]] == [0, 2]
    assert met(data) == [2, 3]


def test_the_other_step_and_stage_lines_of_the_original():
    log = "\n".join([
        "About to run a stage",
        "TimeStepExecutor: Running time step at time 0.5",
        residual("0.1", "0.2"),
        "About to run a stage",
        "TimeStepExecutor: Running time step at time 1",
        residual("0.01", "0.02"),
    ])

    data = convergence.parse(log)

    assert [(s["at"], s["index"]) for s in data["stages"]] == [(0, 1), (1, 2)]
    assert [(s["at"], s["time"]) for s in data["steps"]] == [(0, 0.5), (1, 1.0)]


# ── Real logs ───────────────────────────────────────────────────────────────

def test_a_residual_line_cut_by_a_marker_is_joined_again():
    """The original parser loses the iteration that the stage marker cut in two."""
    data = convergence.read_log(FIXTURES / "seepage.log")

    assert len(data["iterations"]) == 20
    assert met(data) == list(range(1, 21)), "absolute norm below target every time"
    cut = data["iterations"][11]
    assert (cut["relative"], cut["relative_target"]) == (0.000221256, 0.0001)
    assert (cut["absolute"], cut["absolute_target"]) == (3.10835e-11, 1e-09)
    assert data["stages"] == [{"at": 0, "index": 1, "of": 1, "name": "1_Flow"}]


def test_stages_are_named_in_order_though_the_markers_came_early():
    data = convergence.read_log(FIXTURES / "staged_cut_lines.log")

    assert len(data["iterations"]) == 7
    assert [(s["at"], s["index"], s["of"], s["name"]) for s in data["stages"]] == [
        (0, 1, 7, "1_Initial_stage"), (1, 2, 7, "2_Null_step"),
        (2, 3, 7, "3_SheetPileWall_installation"), (3, 4, 7, "4_First_excavation"),
        (4, 5, 7, "5_Strut_installation"), (5, 6, 7, "6_Second_excavation"),
        (6, 7, 7, "7_Third_excavation")]
    assert data["iterations"][1]["absolute"] == 9.72554e-13, "the cut line"
    assert data["stage"] == {"index": 7, "of": 7, "name": "7_Third_excavation",
                             "ended": True}

    rows = convergence.stage_rows(data)
    assert [row["iterations"] for row in rows] == [1] * 7
    assert [row["steps"] for row in rows] == [1] * 7


def test_a_step_at_the_iteration_limit_and_its_cut_back_are_events():
    data = convergence.read_log(FIXTURES / "iteration_limit.log")

    assert len(data["iterations"]) == 51
    assert data["events"] == [{"at": 51, "kind": "max_iterations", "limit": 50},
                              {"at": 51, "kind": "cut_back", "factor": 0.5}]
    assert data["stage"] == {"index": 2, "of": 2, "name": "2_Push", "ended": False}
    rows = convergence.stage_rows(data)
    assert [(row["name"], row["iterations"], row["met"], row["cut_backs"],
             row["max_iterations"]) for row in rows] == [
        ("1_Initial", 1, True, 0, 0), ("2_Push", 50, False, 1, 1)]


# ── What the port adds ──────────────────────────────────────────────────────

def test_nan_inf_and_zero_are_kept():
    log = "\n".join([
        "GeoMechanics Analysis: Analysis -START-",
        residual("0", "0"),
        residual("nan", "-nan(ind)"),
        residual("inf", "-inf"),
        residual("1e+308", "1.5"),
    ])

    data = convergence.parse(log)

    assert relative(data) == [0.0, "nan", "inf", 1e308]
    assert absolute(data) == [0.0, "nan", "-inf", 1.5]


def test_the_nth_begin_names_the_nth_start_whatever_the_order():
    log = "\n".join([
        f"{MARKER} begin 1/2 1_Dry",
        f"{MARKER} end 1/2 1_Dry",
        f"{MARKER} begin 2/2 2_Wet",
        "GeoMechanics Analysis: Analysis -START-",
        residual("0.1", "1"),
        "GeoMechanics Analysis: Analysis -START-",
        residual("0.2", "2"),
    ])

    data = convergence.parse(log)

    assert [(s["at"], s["name"]) for s in data["stages"]] == [(0, "1_Dry"), (1, "2_Wet")]


def test_a_stage_that_has_begun_but_not_started_solving_is_the_current_stage():
    log = "\n".join([f"{MARKER} begin 1/3 1_Initial", f"{MARKER} end 1/3 1_Initial",
                     f"{MARKER} begin 2/3 2_Dig", ""])

    data = convergence.parse(log, growing=True)

    assert data["stage"] == {"index": 2, "of": 3, "name": "2_Dig", "ended": False}
    assert data["stages"] == [] and data["iterations"] == []


def test_a_cut_back_step_has_the_next_cycle():
    log = "\n".join([
        "GeoMechanics Analysis: Analysis -START-",
        "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  1.0",
        residual("0.5", "1"),
        "ResidualBasedNewtonRaphsonStrategy: ATTENTION: max iterations ( 1 ) exceeded!",
        "GeoMechanics Analysis: Down-scaling with factor:  0.5 ",
        "GeoMechanics Analysis: cycle:  2", "GeoMechanics Analysis: TIME      :  0.5",
        residual("1e-6", "1e-12"),
        "RESIDUAL CRITERION: Convergence is achieved",
    ])

    data = convergence.parse(log)

    assert data["steps"] == [{"at": 0, "time": 1.0, "cycle": 1},
                             {"at": 1, "time": 0.5, "cycle": 2}]
    assert data["events"] == [{"at": 1, "kind": "max_iterations", "limit": 1},
                              {"at": 1, "kind": "cut_back", "factor": 0.5}]


def test_a_fraction_of_unbalance_is_read_when_kratos_prints_one():
    log = "\n".join([residual("0.5", "1"), "Fraction of unbalance: 0.25"])

    assert convergence.parse(log)["fractions"] == [{"at": 1, "value": 0.25}]


def test_a_growing_log_leaves_the_line_kratos_is_still_printing():
    complete = residual("0.5", "1")
    half = "RESIDUAL CRITERION:  :: [ Obtained ratio = 0.25; Expected ratio = 0.0001; " \
           "Absolute norm = 0.5; Expected norm =  1"

    assert len(convergence.parse(complete + "\n" + half, growing=True)["iterations"]) == 1
    assert convergence.parse(complete, growing=True)["iterations"] == []
    assert len(convergence.parse(complete)["iterations"]) == 1, "a finished log is read whole"


def test_an_empty_log_is_empty():
    assert convergence.parse("") == {"iterations": [], "steps": [], "stages": [],
                                     "events": [], "fractions": [], "stage": None}
    assert convergence.stage_rows(convergence.parse("")) == []


def test_iterations_with_no_stage_line_are_one_stage_in_the_table():
    rows = convergence.stage_rows(convergence.parse(residual("0.5", "1")))
    assert [(row["index"], row["iterations"]) for row in rows] == [(None, 1)]


@pytest.mark.parametrize("text,expected", [("1.5", 1.5), ("-2e-3", -2e-3), ("nan", "nan"),
                                           ("-nan(ind)", "nan"), ("inf", "inf"),
                                           ("-inf", "-inf"), ("1e999", "inf")])
def test_numbers(text, expected):
    assert convergence.number(text) == expected


# ── Each iteration's place ──────────────────────────────────────────────────

def test_each_iteration_knows_its_stage_and_its_step_in_that_stage():
    log = "\n".join([
        "GeoMechanics Analysis: Analysis -START-",
        "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  0.5",
        residual("0.5", "1"), residual("0.4", "1"),
        "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  1.0",
        residual("0.3", "1"),
        "GeoMechanics Analysis: Analysis -START-",
        "GeoMechanics Analysis: cycle:  1", "GeoMechanics Analysis: TIME      :  2.0",
        residual("0.2", "1"),
    ])

    data = convergence.parse(log)

    assert [(i["stage"], i["step"], i["time"], i["cycle"]) for i in data["iterations"]] == [
        (1, 1, 0.5, 1), (1, 1, 0.5, 1), (1, 2, 1.0, 1), (2, 1, 2.0, 1)]


def test_an_iteration_with_no_stage_or_step_line_has_none():
    data = convergence.parse(residual("0.5", "1"))
    assert (data["iterations"][0]["stage"], data["iterations"][0]["step"]) == (None, None)


# ── The file ────────────────────────────────────────────────────────────────

def test_the_csv_has_one_row_per_iteration_with_its_stage_step_and_events():
    from cli.terminal import tables

    data = convergence.read_log(FIXTURES / "iteration_limit.log")

    rows = list(csv.DictReader(io.StringIO(tables.convergence_csv(data))))

    assert tuple(rows[0]) == tables.CONVERGENCE_COLUMNS
    assert len(rows) == 51
    assert rows[0] | {} == {
        "iteration": "1", "stage": "1", "stage_name": "1_Initial", "step": "1",
        "time": "0", "cycle": "1", "relative": "1.4968e-13", "relative_target": "0.0001",
        "absolute": "4.03844e-11", "absolute_target": "1e-9", "met": "yes", "events": ""}
    assert rows[-1]["stage_name"] == "2_Push" and rows[-1]["met"] == "no"
    assert rows[-1]["events"] == "max_iterations 50; cut_back 0.5"
    assert len(tables.convergence_csv(data, stage=2).splitlines()) == 1 + 50


def test_the_csv_writes_nan_as_nan():
    from cli.terminal import tables

    text = tables.convergence_csv(convergence.parse(residual("nan", "inf")))
    assert text.splitlines()[1].split(",")[6:10] == ["nan", "0.0001", "inf", "1e-9"]


# ── One run ─────────────────────────────────────────────────────────────────

@pytest.fixture
def runs_root(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    monkeypatch.setenv(calculation.RUNS_ENV, str(root))
    catalog.forget_cache()
    return root


def test_a_run_in_progress_is_read_as_far_as_its_complete_lines(runs_root):
    directory = runs_root / "Test_model_2026-09-22_00-49"
    directory.mkdir(parents=True)
    log = "\n".join([f"{MARKER} begin 1/2 1_Initial",
                     "GeoMechanics Analysis: Analysis -START-",
                     residual("0.5", "1"), residual("0.25", "0.5")[:40]])
    (directory / calculation.LOG_NAME).write_text(log, encoding="utf-8")

    with calculation.in_progress(directory):
        running = convergence.of_run(directory.name)
    finished = convergence.of_run(directory.name)

    assert running["run"] == directory.name
    assert running["running"] is True and running["failed_at"] is None
    assert len(running["iterations"]) == 1
    assert finished["running"] is False
    assert finished["failed_at"] == {"index": 1, "of": 2, "name": "1_Initial"}


def test_a_run_with_no_log_has_no_data(runs_root):
    directory = runs_root / "Test_model_2026-09-22_00-49"
    directory.mkdir(parents=True)

    data = convergence.of_run(directory)

    assert data["log"] is False and data["iterations"] == []


def test_an_unknown_run_is_refused(runs_root):
    with pytest.raises(catalog.UnknownRun):
        convergence.of_run("Nothing_2026-09-22_00-49")


# ── The routes ──────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_the_status_says_which_run_kratos_is_working_in(client, runs_root):
    directory = runs_root / "Test_model_2026-09-22_00-49"
    directory.mkdir(parents=True)

    assert client.get("/api/calculate/status").json() == {"running": False, "run": None}
    with calculation.in_progress(directory):
        assert client.get("/api/calculate/status").json() == {
            "running": True, "run": directory.name}


def test_the_route_sends_nan_and_inf_as_strings(client, runs_root):
    """JSON has no number for them, and a run that blows up is when the plot matters."""
    directory = runs_root / "Test_model_2026-09-22_00-49"
    directory.mkdir(parents=True)
    (directory / calculation.LOG_NAME).write_text(
        "GeoMechanics Analysis: Analysis -START-\n" + residual("nan", "inf") + "\n",
        encoding="utf-8")

    response = client.get(f"/api/results/runs/{directory.name}/convergence")

    assert response.status_code == 200
    assert response.json()["iterations"][0]["relative"] == "nan"
    assert response.json()["iterations"][0]["absolute"] == "inf"


def test_the_route_refuses_a_name_that_is_not_a_run(client, runs_root):
    assert client.get("/api/results/runs/..%5C..%5Cetc/convergence").status_code == 404
