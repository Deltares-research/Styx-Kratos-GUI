"""The CI workflow (plan/active/alpha-test-plan.md Task 0.6, decision D8). It only runs on GitHub, so
what it must do is pinned here: the platforms, the tier it runs through `tools/test.py`, and
the prerequisites that tier needs on a machine with nothing installed."""

import importlib.util
import pathlib
import sys
import tomllib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def job(workflow):
    (only,) = workflow["jobs"].values()
    return only


@pytest.fixture(scope="module")
def commands(job):
    return "\n".join(step.get("run", "") for step in job["steps"])


@pytest.fixture(scope="module")
def tiers():
    spec = importlib.util.spec_from_file_location("tier_runner_ci", ROOT / "tools" / "test.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.TIERS


def test_it_runs_on_every_push_and_pull_request(workflow):
    triggers = workflow.get("on", workflow.get(True))      # YAML 1.1 reads a bare `on` as True
    assert {"push", "pull_request"} <= set(triggers)


def test_it_runs_on_windows_and_linux(job):
    assert {"windows-latest", "ubuntu-latest"} <= set(job["strategy"]["matrix"]["os"])
    assert job["strategy"]["fail-fast"] is False, "one platform failing must not hide the other"


def test_the_python_is_one_quickjs_ships_a_wheel_for(job):
    assert "3.11" in [str(v) for v in job["strategy"]["matrix"]["python"]]


def test_it_installs_the_app_the_test_tools_and_quickjs(commands):
    assert "requirements.txt" in commands
    assert "requirements-dev.txt" in commands
    assert "quickjs" in commands


def test_a_quickjs_that_does_not_build_does_not_fail_the_install(job):
    """`cmd || echo ...` is the fallback, and it only holds in bash: on Windows the default
    shell is PowerShell, which leaves the failed pip's exit code behind and fails the step
    (Python 3.13, where quickjs has no wheel and its build fails)."""
    (install,) = [step for step in job["steps"] if "pip install quickjs" in step.get("run", "")]
    assert "||" in install["run"]
    assert install.get("shell") == "bash"


def test_it_installs_the_requirements_kept_at_the_repository_root(job, commands):
    setup = next(step for step in job["steps"]
                 if str(step.get("uses", "")).startswith("actions/setup-python"))
    cached = setup["with"]["cache-dependency-path"].split()
    assert cached == ["requirements.txt", "requirements-dev.txt"]
    for name in cached:
        assert (ROOT / name).is_file(), name
        assert f"-r {name}" in commands


def test_it_measures_the_core_the_backend_and_the_command_line(commands):
    assert "--cov=core" in commands and "--cov=backend" in commands
    assert "--cov=cli" in commands
    assert "--cov=app" not in commands


def test_coverage_is_taken_over_the_core_the_backend_and_the_command_line():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    run = config["tool"]["coverage"]["run"]
    assert run["source"] == ["core", "backend", "cli"]
    assert run["omit"] == ["backend/launcher.py"]
    assert (ROOT / "backend" / "launcher.py").is_file()


def test_it_installs_playwrights_own_chromium_and_uses_it(job, commands):
    assert "playwright install" in commands and "chromium" in commands
    assert job["env"]["KRATOS_GUI_TEST_BROWSER_CHANNEL"] == "bundled"


def test_it_runs_a_tier_the_runner_knows_and_never_one_that_needs_kratos(commands, tiers):
    runs = [line.split("tools/test.py", 1)[1].split()[0]
            for line in commands.splitlines() if "tools/test.py" in line]
    assert runs, "the workflow must go through tools/test.py"
    assert all(tier in tiers for tier in runs), runs
    assert not {"kratos", "bench", "all"} & set(runs), "Kratos tiers run on the owner's machine (D8)"


def test_a_failure_leaves_its_traces_and_coverage_behind(job):
    uploads = [step for step in job["steps"]
               if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert uploads, "nothing to look at when a run fails"
    assert all("always()" in step.get("if", "") or "failure()" in step.get("if", "")
               for step in uploads)


def test_the_reports_are_kept_from_where_pytest_writes_them(job):
    """`tools/test.py` runs pytest from the repository root, so the traces, the
    coverage report and the JS coverage summary all land there."""
    (upload,) = [step for step in job["steps"]
                 if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert upload["with"]["path"].split() == ["test-results/", "htmlcov/", "htmlcov-js/"]
