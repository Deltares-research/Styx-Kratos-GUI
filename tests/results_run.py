"""Runs of the test model for the tests that read results back.

Nothing about a run is committed. Two kinds are made on demand, once per session, each in
a temporary runs root of its own:

*   `real_run()` -- the test model (`tests/models/excavation.py`) calculated by Kratos,
    when Kratos is installed on this machine, and a skip when it is not. The regression
    check on real solver output: what Kratos writes, read back through `core.results`.
*   `fake_run()` -- the same model through `tests/fakes/fake_kratos.py`: synthetic,
    analytic output in the files a real run leaves, made on any machine. For tests about
    the shape of what the results routes answer rather than about the numbers.

`use(monkeypatch, run_id)` points `calculate.runs_root()` at the run's root, through the
environment variable a user has, and returns the id.
"""

from __future__ import annotations

import atexit
import functools
import os
import pathlib
import shutil
import subprocess
import tempfile

import pytest

PROBE = "import KratosMultiphysics, KratosMultiphysics.GeoMechanicsApplication"
"""What "Kratos is installed" means: the interpreter a calculation would use can import
the application the deck runs in, with the environment a calculation would give it."""

PROBE_TIMEOUT = 120.0


@functools.cache
def kratos_missing() -> str | None:
    """Why this machine cannot run Kratos, or None when it can. Asked once per session.

    `calculate.interpreter()` succeeding is not enough: with nothing configured it falls
    back to the server's own Python, which exists and has no Kratos, and a test trusting
    it would run a calculation and fail rather than skip.
    """
    from core import calculate

    try:
        python, environment = calculate.interpreter()
    except calculate.CalculationError as failure:
        return f"no Kratos configured: {failure}"
    try:
        probe = subprocess.run([python, "-c", PROBE], env=environment, capture_output=True,
                               text=True, timeout=PROBE_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as failure:
        return f"{python} could not be asked for Kratos: {failure}"
    if probe.returncode != 0:
        last = (probe.stderr.strip().splitlines() or ["no output"])[-1]
        return f"Kratos is not installed for {python}: {last}"
    return None


def require_kratos() -> None:
    reason = kratos_missing()
    if reason:
        pytest.skip(reason)


def _new_root(prefix: str) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix=prefix))
    atexit.register(shutil.rmtree, root, True)
    return root


def _in_root(root: pathlib.Path, make):
    """Run `make()` with the runs root pointed at `root`, and put it back after."""
    from core import calculate, results

    previous = os.environ.get(calculate.RUNS_ENV)
    os.environ[calculate.RUNS_ENV] = str(root)
    results.forget_cache()
    try:
        return make()
    finally:
        if previous is None:
            os.environ.pop(calculate.RUNS_ENV, None)
        else:
            os.environ[calculate.RUNS_ENV] = previous
        results.forget_cache()


def model():
    """The model every run here is made from."""
    from tests.models import excavation

    return excavation.excavation_project(staged=True)


@functools.cache
def _real() -> tuple[pathlib.Path, str]:
    from core import calculate, kratos

    root = _new_root("kratos-run-")
    outcome = _in_root(root, lambda: calculate.run(kratos.export_project(model())))
    # A model Kratos rejects is a failure of this suite, not a reason to skip it.
    assert outcome["ok"], f"Kratos did not finish the test model: {outcome.get('error')}"
    return root, pathlib.Path(outcome["directory"]).name


def real_run() -> tuple[pathlib.Path, str]:
    """(runs root, run id) of the test model calculated by Kratos, or skip."""
    require_kratos()
    return _real()


@functools.cache
def fake_run() -> tuple[pathlib.Path, str]:
    """(runs root, run id) of the test model through the fake Kratos."""
    from core import kratos
    from tests.fakes import fake_kratos

    root = _new_root("fake-run-")
    outcome = _in_root(root, lambda: fake_kratos.fake_run(kratos.export_project(model())))
    return root, pathlib.Path(outcome["directory"]).name


def use(monkeypatch, run: tuple[pathlib.Path, str]) -> str:
    """Point `calculate.runs_root()` at the run's root, and return the run id."""
    from core import calculate, results

    root, run_id = run
    monkeypatch.setenv(calculate.RUNS_ENV, str(root))
    results.forget_cache()
    return run_id


def deck_text(run: tuple[pathlib.Path, str]) -> str:
    """The run's own `.mdpa`, as text."""
    root, run_id = run
    directory = root / run_id
    return next(directory.glob("*.mdpa")).read_text(encoding="utf-8")
