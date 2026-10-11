"""`tools/test.py`, the one command per test tier (plan/active/alpha-test-plan.md Task 0.4).

The steps are checked as data, and a run is checked with a stand-in for `subprocess.call`,
so nothing here starts a browser, Kratos or a second pytest."""

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def runner():
    # Loaded by path: as a module named `test` it would shadow Python's own `test` package.
    spec = importlib.util.spec_from_file_location("tier_runner", ROOT / "tools" / "test.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module      # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def names(steps):
    return [step.name for step in steps]


def pytest_args(steps):
    return next(step.command for step in steps if step.name == "pytest")


def test_quick_is_the_js_checks_and_pytest_without_the_browser(runner):
    steps = runner.plan("quick")
    assert names(steps) == ["syntax", "headless", "pytest"]
    assert pytest_args(steps)[-2:] == ["-m", "not browser"]


def test_browser_is_quick_with_the_browser_suite_in(runner):
    steps = runner.plan("browser")
    assert names(steps) == ["syntax", "headless", "pytest"]
    assert "not browser" not in pytest_args(steps)


@pytest.mark.parametrize("tier, flags", [
    ("e2e", ["--run-e2e"]),
    ("kratos", ["-m", "kratos", "--run-kratos"]),
    ("perf", ["-m", "perf", "--run-perf"]),
    ("all", ["--run-e2e", "--run-kratos", "--run-benchmarks", "--run-perf", "--run-slow"]),
])
def test_each_tier_passes_its_opt_in_flags(runner, tier, flags):
    command = pytest_args(runner.plan(tier))
    assert all(flag in command for flag in flags), command


def test_pytest_runs_from_server_with_the_server_interpreter(runner):
    step = next(s for s in runner.plan("quick") if s.name == "pytest")
    assert step.cwd == ROOT / "server"
    assert step.command[:3] == [str(runner.server_python()), "-m", "pytest"]


def test_extra_arguments_go_to_pytest_only(runner):
    steps = runner.plan("quick", ["-k", "phases", "-x"])
    assert pytest_args(steps)[-3:] == ["-k", "phases", "-x"]
    assert all("-x" not in (s.command or []) for s in steps if s.name != "pytest")


def test_the_venv_interpreter_is_preferred_when_it_exists(runner, tmp_path):
    from app.launcher import platform_venv_name, venv_python
    expected = venv_python(tmp_path / platform_venv_name())
    expected.parent.mkdir(parents=True)
    expected.write_text("", encoding="utf-8")
    assert runner.server_python(tmp_path) == expected


def test_without_a_venv_the_current_interpreter_runs_pytest(runner, tmp_path):
    assert runner.server_python(tmp_path) == pathlib.Path(sys.executable)


def test_the_quickjs_interpreter_can_be_named(runner, monkeypatch):
    monkeypatch.setenv("KRATOS_GUI_QUICKJS_PYTHON", "C:/somewhere/python.exe")
    assert runner.headless_python(has_quickjs=lambda python: False) == "C:/somewhere/python.exe"


def test_the_first_interpreter_with_quickjs_runs_the_headless_suites(runner, monkeypatch):
    monkeypatch.delenv("KRATOS_GUI_QUICKJS_PYTHON", raising=False)
    found = runner.headless_python(has_quickjs=lambda python: python == sys.executable)
    assert found == sys.executable


def test_with_no_quickjs_anywhere_the_headless_step_is_a_skip(runner, monkeypatch):
    monkeypatch.delenv("KRATOS_GUI_QUICKJS_PYTHON", raising=False)
    steps = runner.plan("quick", has_quickjs=lambda python: False)
    headless = next(s for s in steps if s.name == "headless")
    assert headless.command is None
    assert "quickjs" in headless.unavailable


def test_bench_is_unavailable_until_the_framework_exists(runner, tmp_path):
    (step,) = runner.plan("bench", root=tmp_path)
    assert step.command is None
    assert "Task 4.1" in step.unavailable


def test_an_unknown_tier_is_refused(runner, capsys):
    assert runner.main(["test.py", "nightly"]) == 2
    assert "quick" in capsys.readouterr().err


def run_with(runner, codes, tier="quick", **kwargs):
    calls = []

    def execute(command, cwd):
        calls.append(command)
        return codes.get(len(calls), 0)

    status = runner.main(["test.py", tier], execute=execute, **kwargs)
    return status, calls


def test_every_step_runs_and_a_clean_run_exits_zero(runner, capsys):
    status, calls = run_with(runner, {}, has_quickjs=lambda python: True)
    assert status == 0
    assert len(calls) == 3
    assert "failed" not in capsys.readouterr().out.lower()


def test_a_failing_step_fails_the_tier_but_the_rest_still_run(runner, capsys):
    status, calls = run_with(runner, {1: 1}, has_quickjs=lambda python: True)
    assert status == 1
    assert len(calls) == 3, "a syntax error should not hide the pytest result"
    assert "syntax" in capsys.readouterr().out


def test_the_headless_runners_missing_quickjs_code_is_a_skip_not_a_failure(runner, capsys):
    status, _ = run_with(runner, {2: 3}, has_quickjs=lambda python: True)
    assert status == 0
    assert "skipped" in capsys.readouterr().out


def test_an_unavailable_step_is_reported_and_not_run(runner, capsys, monkeypatch):
    monkeypatch.delenv("KRATOS_GUI_QUICKJS_PYTHON", raising=False)
    status, calls = run_with(runner, {}, has_quickjs=lambda python: False)
    assert status == 0
    assert len(calls) == 2
    assert "pip install quickjs" in capsys.readouterr().out
