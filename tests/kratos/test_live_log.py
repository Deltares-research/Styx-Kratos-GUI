"""Kratos' log, as the convergence plot reads it: live, and in order. Opt-in:
`pytest --run-kratos`.

`core.analysis.kratos_main.unbuffer_output` turns the C runtime's stdout buffer off
before Kratos is imported. Without it, Kratos' C++ lines reach the pipe in blocks, after
the stage markers Python printed in between, and markers land inside other lines. This
runs the staged test model (`tests/models/excavation.py`) and checks both: every stage
reads begin, `Analysis -START-`, its residuals, end; and the residual lines arrive in the
log one at a time while the run goes on.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import MeshRequest
from core.results import catalog
from tests.models import excavation
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos

RESIDUAL = "Obtained ratio"


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("log-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


@pytest.fixture(scope="module")
def staged_run():
    """The staged test model, run once, with how many residual lines the log held
    each time a watcher saw it change."""
    project = excavation.excavation_project()
    with solid_model.session():
        deck = writer.export_project(project, MeshRequest(**project.mesh.model_dump()))
    counts: list[int] = []
    done = threading.Event()

    def watch() -> None:
        while not done.is_set():
            directory = calculation.current_run()
            log = directory / calculation.LOG_NAME if directory else None
            try:
                count = log.read_text(encoding="utf-8").count(RESIDUAL) if log else 0
            except OSError:
                count = 0
            if count and (not counts or counts[-1] != count):
                counts.append(count)
            time.sleep(0.005)

    watcher = threading.Thread(target=watch)
    watcher.start()
    try:
        outcome = calculation.run(deck)
    finally:
        done.set()
        watcher.join()
    log = (Path(outcome["directory"]) / calculation.LOG_NAME).read_text(encoding="utf-8")
    return outcome, log, counts


def test_every_stage_reads_begin_start_residuals_end(staged_run):
    outcome, log, _ = staged_run
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])

    order: list[str] = []
    for line in log.splitlines():
        if line.startswith(calculation.STAGE_MARKER):
            order.append(line.split()[2])
        elif "Analysis -START-" in line:
            order.append("start")
        elif RESIDUAL in line and order[-1] != "residuals":
            order.append("residuals")

    stages = len(excavation.excavation_project().stages)
    assert order == ["begin", "start", "residuals", "end"] * stages


def test_no_marker_is_cut_into_another_line(staged_run):
    _, log, _ = staged_run
    inside = [line for line in log.splitlines()
              if calculation.STAGE_MARKER in line
              and not line.startswith(calculation.STAGE_MARKER)]
    assert inside == []
    assert calculation.UNBUFFERED_NOTE not in log, "the buffer was turned off"


def test_the_residuals_arrive_in_the_log_one_by_one(staged_run):
    """In blocks, the watcher would see the count jump; one by one, it sees most of
    the counts on the way. Not all: a fast iteration can still fall between two looks."""
    _, log, counts = staged_run
    total = log.count(RESIDUAL)
    assert counts[-1] == total
    assert len(counts) >= total // 2, counts
