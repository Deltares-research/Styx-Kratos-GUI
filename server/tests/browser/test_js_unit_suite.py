"""The browser unit suite (live/tests/index.html), run the way a person would: open the
page and wait for it. The page publishes its outcome as `window.__TEST_RESULTS__`.

With `--js-coverage`, Chrome's precise coverage is taken over the same run and summarised
per live module into `htmlcov-js/summary.json` (plan/alpha-test-plan.md Task 0.5)."""

import json
import pathlib

import pytest

from tests.browser import js_coverage

ROOT = pathlib.Path(__file__).resolve().parents[3]
SUITE = ROOT / "live" / "tests" / "index.html"
REPORT = ROOT / "server" / "htmlcov-js" / "summary.json"
TARGET = 80.0
"""Per live module, in percent of functions run (plan/full-test-and-validation-plan.md M4).
Enforced whenever the suite runs with --js-coverage."""

pytestmark = pytest.mark.browser


def test_browser_unit_suite_has_no_failures(page, request):
    profiler = None
    if request.config.getoption("--js-coverage"):
        profiler = page.context.new_cdp_session(page)
        profiler.send("Profiler.enable")
        profiler.send("Profiler.startPreciseCoverage", {"callCount": True, "detailed": False})

    uncaught: list[str] = []
    page.on("pageerror", lambda error: uncaught.append(str(error)))
    page.goto(SUITE.as_uri())
    page.wait_for_function("window.__TEST_RESULTS__ !== undefined", timeout=180_000)
    results = page.evaluate("window.__TEST_RESULTS__")

    under = []
    if profiler is not None:
        under = _report(profiler.send("Profiler.takePreciseCoverage")["result"])

    assert not uncaught, "uncaught errors while the suite loaded:\n" + "\n".join(uncaught)
    assert results["total"] > 0
    assert results["failed"] == 0, "\n\n".join(results["failures"])
    assert not under, f"live modules below {TARGET:.0f} % of functions: {', '.join(under)}"


def _report(entries: list[dict]) -> list[str]:
    summary = js_coverage.summarise(entries)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    under = js_coverage.below(summary, TARGET)
    print("\n" + js_coverage.table(summary))
    print(f"\nBelow {TARGET:.0f} % of functions: " + (", ".join(under) or "none"))
    return under
