"""Opt-in test tiers (plan/active/alpha-test-plan.md sec 2.2).

The default `pytest -q` stays fast and needs neither Kratos nor a browser. Everything
slower or with an outside dependency is marked and skipped, with the flag that runs it
named in the skip reason. A test under `tests/e2e/` is an end-to-end test by where it
lives, so it needs no marker of its own.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib

import pytest

from backend.launcher import ALLOWED_HOSTS_ENV

# Starlette's TestClient sends `Host: testserver`. The server refuses any host that is not
# loopback (backend/middleware.py `only_this_browser_tab`), and `testserver` is allowed for the test
# session only, through the same variable a deliberate LAN setup would use.
os.environ.setdefault(ALLOWED_HOSTS_ENV, "testserver")

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
    parser.addoption("--update-snapshots", action="store_true", default=False,
                     help="rewrite committed snapshots (deck structure, perf baseline) from "
                          "the code, for a deliberate change")
    parser.addoption("--js-coverage", action="store_true", default=False,
                     help="collect function coverage of frontend/js in the browser unit suite "
                          "(written to htmlcov-js/summary.json)")
    parser.addoption("--doc-screenshots", metavar="DIR", default=None,
                     help="save the screenshots of the GUI tutorials in DIR/<tutorial>/ "
                          "(tests/e2e/test_gui_tutorials.py; python tools/gui_tutorial.py "
                          "does this for you)")
    parser.addoption("--record-run", action="store_true", default=False,
                     help="with --run-kratos: keep the real run of each GUI tutorial in "
                          "tests/fixtures/tutorial_runs/<tutorial>/, for the replay")
    parser.addoption("--strict-deck", action="store_true", default=False,
                     help="fail a GUI tutorial whose deck differs from its recorded run, "
                          "instead of warning")


@pytest.fixture(autouse=True, scope="session")
def every_exported_deck_is_sound():
    """Run `check_deck` (tests/pipeline/deck_invariants.py) on every deck any test
    exports in this process, so a change that breaks a structural rule is caught by
    the first test that happens to export such a deck -- not only by the tests written
    about that rule. Exports made inside the gmsh worker (the API routes) are checked by
    the pipeline tests instead.

    Session-scoped, so it is in place before any module- or session-scoped fixture
    exports its deck: pytest builds the widest fixtures first, and a function-scoped
    patch would let every shared fixture's deck through unchecked."""
    from core.kratos import writer
    from tests.pipeline.deck_invariants import check_deck

    real = writer.export_project

    def checked(*args, **kwargs):
        export = real(*args, **kwargs)
        violations = check_deck(export)
        assert not violations, "the exported deck breaks its invariants:\n  " + \
            "\n  ".join(violations)
        return export

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(writer, "export_project", checked)
        yield


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
