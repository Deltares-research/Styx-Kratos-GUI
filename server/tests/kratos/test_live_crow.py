"""CROW through real Kratos, checked against Kratos' own answer and against physics
(plan sec 7, sec 8.1). Opt-in: `pytest --run-kratos`, or `tools/test.py kratos`.

The deck is exported exactly as Calculate exports it and run through `calculate.run`,
the same runner the GUI uses -- about five seconds on the owner's machine. Then:

* **Against Kratos' validated CROW case** -- bending moment, shear force, normal force
  and horizontal displacement at every wall node of the four stages Kratos checks, with
  the comparison and the tolerances of `tests/test_crow_wall_forces.py`, which does the
  same against a frozen run. Here it is today's exporter and today's Kratos.
* **Against physics**, at every node or element of every stage, no reference needed:
  hydrostatic pore pressure below the water table and none above it (V-HYD); a null
  step that moves nothing (V-NULL); `reset_totals` restarting the totals (V-RESET);
  sigma'xx = K0 sigma'yy after the K0 stage (V-K0); compression everywhere at rest
  (V-SIGN).
* **That this tier can fail**: the same deck with the interfaces' drainage type removed
  -- one of the six defects that only a run ever found -- must not pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app import calculate, crow, gid_results, kratos, results
from tests import mdpa
from tests.test_crow_wall_forces import (FIELDS, NEAR_JUMP_TOLERANCE, delta,
                                         expected_curve, interpolate, near_discontinuity)

pytestmark = pytest.mark.kratos

WALL_STAGES = ["3_SheetPileWall_installation", "4_First_excavation",
               "6_Second_excavation", "7_Third_excavation"]


def _require_kratos():
    try:
        calculate.interpreter()
    except calculate.CalculationError as failure:
        pytest.skip(f"no Kratos configured: {failure}")


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    _require_kratos()
    root = tmp_path_factory.mktemp("live-runs")
    previous = os.environ.get(calculate.RUNS_ENV)
    os.environ[calculate.RUNS_ENV] = str(root)
    results.forget_cache()
    try:
        project = crow.crow_project(staged=True)
        export = crow.export(project)
        outcome = calculate.run(export)
        assert outcome["ok"], outcome["error"]
        directory = Path(outcome["directory"])
        yield {"project": project, "export": export, "directory": directory,
               "run": directory.name, "deck": mdpa.parse(export["mdpa"])}
    finally:
        if previous is None:
            os.environ.pop(calculate.RUNS_ENV, None)
        else:
            os.environ[calculate.RUNS_ENV] = previous
        results.forget_cache()


def stage_results(live, index):
    return results.stage_results(live["run"], index)


def wall_output(live, stage):
    from app import result_members
    text = (live["directory"] / f"{stage}__output_wall.json").read_text(encoding="utf-8")
    return result_members.read_output(text)


def compare_wall(live, stage, field, region="all"):
    deck = live["deck"]
    y_by_node = {n: deck.nodes[n][1] for n in deck.parts["SheetPileWall"].nodes}
    output = wall_output(live, stage)
    curve = expected_curve(stage, field)
    largest = max(abs(v) for _, v in curve)
    failures, compared = [], 0
    for node, y in sorted(y_by_node.items()):
        variables = output.get(node, {})
        if FIELDS[field] not in variables:
            continue
        if region == "away" and near_discontinuity(y):
            continue
        if region == "near" and not near_discontinuity(y):
            continue
        compared += 1
        want = interpolate(curve, y)
        allowed = NEAR_JUMP_TOLERANCE * largest if region == "near" else delta(want, largest)
        if abs(variables[FIELDS[field]] - want) > allowed:
            failures.append(f"y={y:.3f}: {variables[FIELDS[field]]:.6g} vs {want:.6g}")
    assert compared >= 10, f"only {compared} wall nodes compared in {stage}"
    assert not failures, f"{field} in {stage}: " + "; ".join(failures[:8])


# ── The run itself ──────────────────────────────────────────────────────────

def test_every_stage_ran_and_wrote_results(live):
    described = results.describe(live["run"])
    assert described["complete"] and described["failed_at"] is None
    assert len(described["stages"]) == 7


# ── Against Kratos' validated case ──────────────────────────────────────────

@pytest.mark.parametrize("stage", WALL_STAGES)
@pytest.mark.parametrize("field", ["bending_moment", "normal_force",
                                   "horizontal_total_displacement"])
def test_the_wall_matches_the_crow_reference(live, stage, field):
    compare_wall(live, stage, field)


@pytest.mark.parametrize("stage", WALL_STAGES)
def test_the_shear_matches_the_crow_reference(live, stage):
    compare_wall(live, stage, "shear_force", region="away")
    compare_wall(live, stage, "shear_force", region="near")


# ── Against physics ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("index", range(1, 8))
def test_v_hyd_the_pore_pressure_is_hydrostatic_at_every_node(live, index):
    water = live["project"].water
    gamma = live["project"].water_specific_weight        # N/m3: the project is SI
    mesh = results.stage_mesh(live["run"], index)
    field = stage_results(live, index).field("WATER_PRESSURE")
    assert field is not None and field.values
    worst = 0.0
    for node, (value,) in ((n, v[:1]) for n, v in field.values.items()):
        y = mesh.nodes[node][1]
        expected = -gamma * max(0.0, water.y - y)
        # GiD's ASCII output carries six significant figures: 0.5 Pa at 1e5 Pa.
        worst = max(worst, abs(value - expected) / max(1.0, 1e-5 * abs(expected)))
    assert worst <= 1.0, f"worst departure {worst:.3g} x the file's own precision"


def test_the_phase_displacement_is_the_stage_s_own_increment(live):
    """`DISPLACEMENT` -- "Phase deformations" in the field menu -- is what one stage did:
    in every stage without a reset it is the change in TOTAL_DISPLACEMENT since the
    stage before, to the file's precision. Measured, so the menu's label is a fact."""
    params = json.loads(live["export"]["project_parameters"])
    order = params["orchestrator"]["settings"]["execution_list"]
    for index in range(2, 8):
        if params["stages"][order[index - 1]]["stage_settings"]["solver_settings"].get(
                "reset_totals"):
            continue
        now, before = stage_results(live, index), stage_results(live, index - 1)
        total, prior = now.field("TOTAL_DISPLACEMENT").values, before.field(
            "TOTAL_DISPLACEMENT").values
        phase = now.field("DISPLACEMENT").values
        worst = max(abs(phase[n][k] - (total[n][k] - prior[n][k]))
                    for n in phase if n in prior for k in (0, 1))
        assert worst < 2e-5, f"stage {index}: {worst:.3g} m"


def test_v_null_the_null_step_only_settles_what_k0_left_out_of_balance(live):
    """A null step adds no load; it lets the K0 stresses, which are
    not exactly in equilibrium near layer boundaries and the pit, settle. So it moves
    the ground a little rather than not at all: 6.0 mm at worst, measured 2026-10-10,
    against metres of elastic settlement in the K0 stage itself. Held as a bound."""
    field = stage_results(live, 2).field("DISPLACEMENT")
    largest = max(abs(c) for v in field.values.values() for c in v[:2])
    assert largest < 0.01, f"the null step moved a node {largest:.3g} m"


def test_v_reset_totals_restart_where_the_deck_asks(live):
    params = json.loads(live["export"]["project_parameters"])
    order = params["orchestrator"]["settings"]["execution_list"]
    resets = [i for i, name in enumerate(order, start=1)
              if params["stages"][name]["stage_settings"]["solver_settings"].get("reset_totals")]
    assert resets, "CROW resets the totals when the wall goes in"
    for index in resets:
        stage = stage_results(live, index)
        total, phase = stage.field("TOTAL_DISPLACEMENT"), stage.field("DISPLACEMENT")
        worst = max(abs(a - b) for n in phase.values
                    for a, b in zip(total.values[n][:2], phase.values[n][:2]))
        assert worst < 1e-9, f"stage {index}: totals differ from the phase by {worst:.3g} m"


def test_v_k0_horizontal_stress_is_k0_times_vertical_after_the_k0_stage(live):
    deck = live["deck"]
    initial = json.loads(live["export"]["initial_materials"])["properties"]
    k0_of_part = {e["model_part_name"].split(".", 1)[1]: e["Material"]["Variables"]["K0_NC"]
                  for e in initial if "K0_NC" in e["Material"]["Variables"]}
    part_of_element = {e: name for name, part in deck.parts.items() if name in k0_of_part
                       for e in part.elements}
    stress = stage_results(live, 1).field("CAUCHY_STRESS_TENSOR")
    ratios_off, checked = [], 0
    for element, points in stress.values.items():
        part = part_of_element.get(element)
        if part is None:
            continue
        for s in points:
            if s[1] < -1.0:                                # at depth, not at the surface
                checked += 1
                if abs(s[0] / s[1] - k0_of_part[part]) > 0.01 * k0_of_part[part]:
                    ratios_off.append((element, s[0] / s[1], k0_of_part[part]))
    assert checked > 100
    assert len(ratios_off) <= 0.05 * checked, ratios_off[:5]


def test_v_sign_the_ground_is_in_compression_at_rest(live):
    stress = stage_results(live, 1).field("CAUCHY_STRESS_TENSOR")
    tensile = [(e, s) for e, points in stress.values.items() for s in points
               if (s[0] + s[1] + s[2]) / 3 > 1.0]
    assert tensile == [], tensile[:3]


# ── The tier can fail ───────────────────────────────────────────────────────

def test_a_deck_without_the_interface_drainage_type_does_not_pass(live, tmp_path):
    """Kratos defaults a missing GEO_DRAINAGE_TYPE to FULLY_COUPLED, and the CROW
    interfaces then diverge (a defect this exporter once had, found only by running).
    The tier has to see it: the run fails, or its pore pressure stops being hydrostatic."""
    broken = dict(live["export"])
    for key in ("materials", "initial_materials"):
        document = json.loads(broken[key])
        for entry in document["properties"]:
            if "Interface" in entry["model_part_name"]:
                entry["Material"]["Variables"].pop("GEO_DRAINAGE_TYPE", None)
        broken[key] = json.dumps(document)
    outcome = calculate.run(broken)
    if not outcome["ok"]:
        return
    directory = Path(outcome["directory"])
    last = sorted(directory.glob("*7_Third_excavation.post.res"))
    assert not last, "a broken deck ran to the end and wrote a final stage"
