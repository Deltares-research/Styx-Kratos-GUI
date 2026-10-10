"""The same model in two unit systems, through real Kratos (plan/kratos-native-inputs-plan.md
phase C). Opt-in: `pytest --run-kratos`.

Kratos has no units: give it a consistent set and every number comes back in it. That is
the premise the project's unit system rests on -- the deck is written in whatever system
the project is in, with nothing converted -- and it is a premise about Kratos, so it is
checked by running Kratos: CROW in SI and CROW in kN, the second's forces, stresses and
pressures a thousand times smaller and its displacements identical.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import calculate, crow, results, units
from app.schemas import Project
from tests.kratos.test_live_crow import _require_kratos

pytestmark = pytest.mark.kratos

STAGES = ["3_SheetPileWall_installation", "4_First_excavation", "6_Second_excavation",
          "7_Third_excavation"]


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    _require_kratos()
    root = tmp_path_factory.mktemp("unit-runs")
    previous = os.environ.get(calculate.RUNS_ENV)
    os.environ[calculate.RUNS_ENV] = str(root)
    results.forget_cache()
    try:
        si = crow.crow_project(staged=True)
        payload, notes = units.convert_project(si.model_dump(mode="json"), "kN")
        assert notes == []
        kn = Project.model_validate(payload)
        out = {}
        for name, project in (("SI", si), ("kN", kn)):
            outcome = calculate.run(crow.export(project))
            assert outcome["ok"], outcome["error"]
            out[name] = Path(outcome["directory"])
        yield out
    finally:
        if previous is None:
            os.environ.pop(calculate.RUNS_ENV, None)
        else:
            os.environ[calculate.RUNS_ENV] = previous
        results.forget_cache()


def wall(directory: Path, stage: str) -> dict:
    from app import result_members
    return result_members.read_output(
        (directory / f"{stage}__output_wall.json").read_text(encoding="utf-8"))


def test_the_kn_run_records_its_system(runs):
    assert results.run_unit_system(runs["SI"].name) == "SI"
    assert results.run_unit_system(runs["kN"].name) == "kN"


@pytest.mark.parametrize("stage", STAGES)
def test_wall_forces_are_a_thousand_times_smaller_and_movements_the_same(runs, stage):
    si, kn = wall(runs["SI"], stage), wall(runs["kN"], stage)
    assert set(si) == set(kn)
    largest = {v: max(abs(si[n][v]) for n in si) for v in
               ("BENDING_MOMENT", "SHEAR_FORCE", "AXIAL_FORCE", "TOTAL_DISPLACEMENT_X")}
    for node in si:
        for variable in ("BENDING_MOMENT", "SHEAR_FORCE", "AXIAL_FORCE"):
            assert kn[node][variable] * 1000.0 == pytest.approx(
                si[node][variable], abs=1e-6 * largest[variable]), (node, variable)
        assert kn[node]["TOTAL_DISPLACEMENT_X"] == pytest.approx(
            si[node]["TOTAL_DISPLACEMENT_X"], abs=1e-6 * largest["TOTAL_DISPLACEMENT_X"])


@pytest.mark.parametrize("index", [1, 7])
def test_stresses_and_pore_pressures_scale_and_displacements_do_not(runs, index):
    """Field by field at every node, to the GiD file's six significant figures."""
    for field, scale in (("WATER_PRESSURE", 1000.0), ("TOTAL_DISPLACEMENT", 1.0)):
        a = results.stage_results(runs["SI"].name, index).field(field).values
        b = results.stage_results(runs["kN"].name, index).field(field).values
        peak = max(abs(c) for v in a.values() for c in v[:3])
        for node, values in a.items():
            for x, y in zip(values[:3], b[node][:3]):
                assert y * scale == pytest.approx(x, abs=2e-6 * peak), (field, node)
    a = results.stage_results(runs["SI"].name, index).field("CAUCHY_STRESS_TENSOR").values
    b = results.stage_results(runs["kN"].name, index).field("CAUCHY_STRESS_TENSOR").values
    peak = max(abs(c) for points in a.values() for p in points for c in p)
    for element, points in a.items():
        for p, q in zip(points, b[element]):
            for x, y in zip(p, q):
                assert y * 1000.0 == pytest.approx(x, abs=2e-6 * peak), element


def test_the_kn_results_are_labelled_in_kilopascals(runs):
    field = results.stage_field(runs["kN"].name, 7, "p", "nodes")
    assert field["unit"] == "kPa"
    assert -400.0 < field["min"] < -100.0, "p' in kPa: hundreds, not hundreds of thousands"
