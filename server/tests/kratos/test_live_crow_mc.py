"""CROW in Mohr-Coulomb through real Kratos, against Kratos' own Mohr-Coulomb CROW case
(plan/full-test-and-validation-plan.md sec 7.2 V-CROW-MC). Opt-in: `pytest --run-kratos`.

The deck is `crow.crow_mohr_coulomb_project()` exported as Calculate exports it; the
expected curves are `crow_validation/mohr_coulomb_clay-sand/staged_construction/
<stage>__expected_results_wall.csv`, re-keyed to y along the wall
(`tests/make_crow_mc_fixture.py`), compared node by node with Kratos' own 2 % rule --
the same comparison `test_live_crow.py` makes for the elastic case.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from app import calculate, crow, results
from tests import mdpa
from tests.kratos.test_live_crow import _require_kratos
from tests.test_crow_wall_forces import (FIELDS, NEAR_JUMP_TOLERANCE, delta, interpolate,
                                         near_discontinuity)

pytestmark = pytest.mark.kratos

EXPECTED = Path(__file__).resolve().parents[1] / "fixtures" / "crow_mc" / "expected_wall"
STAGES = ["3_SheetPileWall_installation", "4_First_excavation", "6_Second_excavation",
          "7_Third_excavation"]


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    _require_kratos()
    root = tmp_path_factory.mktemp("live-mc")
    previous = os.environ.get(calculate.RUNS_ENV)
    os.environ[calculate.RUNS_ENV] = str(root)
    results.forget_cache()
    try:
        project = crow.crow_mohr_coulomb_project(staged=True)
        export = crow.export(project)
        outcome = calculate.run(export)
        assert outcome["ok"], outcome["error"]
        directory = Path(outcome["directory"])
        yield {"directory": directory, "run": directory.name,
               "deck": mdpa.parse(export["mdpa"])}
    finally:
        if previous is None:
            os.environ.pop(calculate.RUNS_ENV, None)
        else:
            os.environ[calculate.RUNS_ENV] = previous
        results.forget_cache()


def expected_curve(stage: str, field: str) -> list[tuple[float, float]]:
    with open(EXPECTED / f"{stage}.csv", newline="") as handle:
        return sorted((float(row["y"]), float(row[field])) for row in csv.DictReader(handle))


def disagreements(live, stage: str, field: str, region: str = "all") -> tuple[int, list[str]]:
    from app import result_members
    deck = live["deck"]
    y_by_node = {n: deck.nodes[n][1] for n in deck.parts["SheetPileWall"].nodes}
    output = result_members.read_output(
        (live["directory"] / f"{stage}__output_wall.json").read_text(encoding="utf-8"))
    curve = expected_curve(stage, field)
    largest = max(abs(v) for _, v in curve)
    failures, compared = [], 0
    for node, y in sorted(y_by_node.items()):
        value = output.get(node, {}).get(FIELDS[field])
        if value is None:
            continue
        if region == "away" and near_discontinuity(y):
            continue
        if region == "near" and not near_discontinuity(y):
            continue
        compared += 1
        want = interpolate(curve, y)
        allowed = NEAR_JUMP_TOLERANCE * largest if region == "near" else delta(want, largest)
        if abs(value - want) > allowed:
            failures.append(f"y={y:.3f}: {value:.6g} vs {want:.6g} (allowed {allowed:.3g})")
    return compared, failures


def test_every_stage_ran(live):
    described = results.describe(live["run"])
    assert described["complete"] and described["failed_at"] is None
    assert len(described["stages"]) == 7


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("field", ["bending_moment", "normal_force",
                                   "horizontal_total_displacement"])
def test_the_wall_matches_kratos_mohr_coulomb_crow(live, stage, field):
    compared, failures = disagreements(live, stage, field)
    assert compared >= 10
    assert not failures, f"{field} in {stage}: " + "; ".join(failures[:8])


@pytest.mark.parametrize("stage", STAGES)
def test_the_shear_matches_away_from_its_jumps(live, stage):
    for region in ("away", "near"):
        compared, failures = disagreements(live, stage, "shear_force", region)
        assert not failures, f"shear ({region}) in {stage}: " + "; ".join(failures[:8])
