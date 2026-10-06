"""Opt-in test tiers (plan/alpha-test-plan.md sec 2.2).

The default `pytest -q` stays fast and needs neither Kratos nor a browser. Everything
slower or with an outside dependency is marked and skipped, with the flag that runs it
named in the skip reason. A test under `tests/e2e/` is an end-to-end test by where it
lives, so it needs no marker of its own.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

E2E_DIR = pathlib.Path(__file__).resolve().parent / "e2e"

OPT_IN = {
    "e2e": ("--run-e2e", "GUI end-to-end test"),
    "kratos": ("--run-kratos", "needs Kratos"),
    "benchmark": ("--run-benchmarks", "Kratos benchmark"),
    "perf": ("--run-perf", "performance benchmark"),
    "slow": ("--run-slow", "slow test"),
}


def pytest_addoption(parser):
    for marker, (flag, what) in OPT_IN.items():
        parser.addoption(flag, action="store_true", default=False,
                         help=f"run tests marked {marker} ({what})")
    # Here rather than in tests/browser/conftest.py: options are only read from conftests loaded at startup.
    parser.addoption("--js-coverage", action="store_true", default=False,
                     help="collect function coverage of live/js in the browser unit suite "
                          "(written to htmlcov-js/summary.json)")


def _enabled(config, marker: str) -> bool:
    if marker == "kratos" and config.getoption("--run-benchmarks"):
        return True
    return bool(config.getoption(OPT_IN[marker][0]))


def _in_e2e_folder(item) -> bool:
    return E2E_DIR in pathlib.Path(str(item.fspath)).resolve().parents


def pytest_collection_modifyitems(config, items):
    playwright_missing = importlib.util.find_spec("playwright") is None
    for item in items:
        # A `pytestmark` in a conftest does not reach the tests, so the folder decides.
        if _in_e2e_folder(item):
            item.add_marker(pytest.mark.e2e)
        for marker, (flag, what) in OPT_IN.items():
            if marker in item.keywords and not _enabled(config, marker):
                item.add_marker(pytest.mark.skip(reason=f"{what}; pass {flag}"))
        if playwright_missing and ("browser" in item.keywords or "e2e" in item.keywords):
            item.add_marker(pytest.mark.skip(
                reason="playwright is not installed: pip install -r requirements-dev.txt"))
