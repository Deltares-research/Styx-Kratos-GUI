"""The opt-in test tiers (plan/active/alpha-test-plan.md Task 0.2): what runs by default, and what
waits for a flag. Each case runs a small pytest session in a scratch directory with a copy
of the real `conftest.py`, so the rules are exercised exactly as a test file meets them."""

import importlib.util
import pathlib

import pytest

pytest_plugins = ["pytester"]

CONFTEST = pathlib.Path(__file__).with_name("conftest.py")

TIERS = [("e2e", "--run-e2e"), ("kratos", "--run-kratos"),
         ("benchmark", "--run-benchmarks"), ("perf", "--run-perf"), ("slow", "--run-slow")]

MARKED = """
import pytest

@pytest.mark.{marker}
def test_marked():
    pass
"""


@pytest.fixture
def session(pytester):
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    return pytester


def run(session, *args):
    # The inner session tests our conftest, not Playwright; its plugin cannot load twice in one process.
    return session.runpytest("-p", "no:playwright", *args)


@pytest.fixture
def with_playwright(session):
    # An importable stand-in, so the browser rule is tested whether or not it is installed.
    session.mkpydir("playwright")
    session.syspathinsert()
    return session


@pytest.fixture
def without_playwright(session, monkeypatch):
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name == "playwright" else real(name, *a, **k))
    return session


@pytest.mark.parametrize("marker, flag", TIERS)
def test_a_tier_is_skipped_without_its_flag(with_playwright, marker, flag):
    with_playwright.makepyfile(MARKED.format(marker=marker))
    result = run(with_playwright, "-rs")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines([f"*pass {flag}*"])


@pytest.mark.parametrize("marker, flag", TIERS)
def test_a_tier_runs_with_its_flag(with_playwright, marker, flag):
    with_playwright.makepyfile(MARKED.format(marker=marker))
    run(with_playwright, flag).assert_outcomes(passed=1)


def test_running_the_benchmarks_also_runs_the_kratos_tests(session):
    session.makepyfile(MARKED.format(marker="kratos"))
    run(session, "--run-benchmarks").assert_outcomes(passed=1)


def test_an_unmarked_test_always_runs(session):
    session.makepyfile("def test_plain():\n    pass\n")
    run(session).assert_outcomes(passed=1)


def test_a_test_in_the_e2e_folder_is_e2e_without_saying_so(with_playwright):
    folder = with_playwright.mkdir("e2e")
    (folder / "test_flow.py").write_text("def test_flow():\n    pass\n", encoding="utf-8")
    run(with_playwright).assert_outcomes(skipped=1)
    run(with_playwright, "--run-e2e").assert_outcomes(passed=1)


def test_a_browser_test_runs_by_default_when_playwright_is_there(with_playwright):
    with_playwright.makepyfile(MARKED.format(marker="browser"))
    run(with_playwright).assert_outcomes(passed=1)


@pytest.mark.parametrize("marker, flags", [("browser", []), ("e2e", ["--run-e2e"])])
def test_without_playwright_browser_tests_skip_and_say_how_to_get_it(without_playwright, marker,
                                                                       flags):
    without_playwright.makepyfile(MARKED.format(marker=marker))
    result = run(without_playwright, "-rs", *flags)
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*requirements-dev.txt*"])


def test_every_marker_is_registered(request):
    registered = {line.split(":")[0].split("(")[0] for line in request.config.getini("markers")}
    assert {"browser", "e2e", "kratos", "benchmark", "perf", "slow", "covers"} <= registered
