"""Performance against a committed baseline (plan alpha 6). Opt-in: `pytest --run-perf`.

Each measurement is the median of a few repetitions, compared with `baseline.json` and
failed above `SLOWDOWN` times it. Timings are the owner's machine's: on another machine,
regenerate the baseline (`--update-snapshots`) before reading anything into a failure.
What is measured is what a user waits for:

* meshing and exporting CROW (Calculate's first half, and Export);
* reading one stage of a run back -- the CROW fixture's final stage, and a synthetic
  20-stage Eemdijk-sized run, cold (finding F10's cache is what keeps the warm case cheap);
* in the page, the time from `results phase <n>` to that phase drawn (tests/e2e).
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pytest

from app import build, calculate, crow, kratos, results
from app.schemas import MeshRequest
from tests import crow_run

pytestmark = pytest.mark.perf

BASELINE = Path(__file__).with_name("baseline.json")
SLOWDOWN = 1.5
measured: dict[str, float] = {}


def median_seconds(action, repeat: int = 3) -> float:
    times = []
    for _ in range(repeat):
        started = time.perf_counter()
        action()
        times.append(time.perf_counter() - started)
    return statistics.median(times)


def check(name: str, seconds: float, request) -> None:
    measured[name] = round(seconds, 4)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    if request.config.getoption("--update-snapshots") or name not in baseline:
        baseline[name] = round(seconds, 4)
        BASELINE.write_text(json.dumps(baseline, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
        return
    assert seconds <= SLOWDOWN * baseline[name], (
        f"{name}: {seconds:.3f} s against a baseline of {baseline[name]:.3f} s")


def test_meshing_and_exporting_crow(request):
    project = crow.crow_project(staged=True)
    settings = MeshRequest(**project.mesh.model_dump())

    def export():
        with build.session():
            kratos.export_project(project, settings)
    check("export_crow_s", median_seconds(export), request)


def test_reading_the_final_stage_of_a_run_cold(request, monkeypatch):
    crow_run.use_fixture_runs(monkeypatch)

    def read():
        results.forget_cache()
        results.stage_fields(crow_run.RUN_ID, 7)
        results.stage_geometry(crow_run.RUN_ID, 7)
        results.stage_field(crow_run.RUN_ID, 7, "p")
    check("read_crow_stage_cold_s", median_seconds(read), request)


def test_opening_a_twenty_stage_run_and_stepping_through_it(request, tmp_path, monkeypatch):
    """Eemdijk's size: 20 stages. The parts listing reads every stage's mesh once; after
    that, stepping through the phases must cost a field, not a re-parse (F10)."""
    from tests.fakes import gid_writer

    project = crow.crow_project(staged=True)
    with build.session():
        export = kratos.export_project(project, MeshRequest(element_size=2.0, order=2))
    params = json.loads(export["project_parameters"])
    order = params["orchestrator"]["settings"]["execution_list"]
    params["orchestrator"]["settings"]["execution_list"] = [
        name for _ in range(3) for name in order][:20]
    export = dict(export, project_parameters=json.dumps(params))
    run = "Big_2026-01-01_00-00"
    gid_writer.write_run(export, tmp_path / run,
                         nodal={"TOTAL_DISPLACEMENT": lambda x, y, z, s: (x, y, 0.0)},
                         gauss={"CAUCHY_STRESS_TENSOR": lambda x, y, z, s: (y,) * 3 + (0.0,) * 3})
    monkeypatch.setenv(calculate.RUNS_ENV, str(tmp_path))

    def open_and_step():
        results.forget_cache()
        results.stage_parts(run, 1)
        for index in range(1, 8):
            results.stage_field(run, index, "uy")
    check("open_and_step_20_stages_s", median_seconds(open_and_step, repeat=2), request)
    results.forget_cache()
