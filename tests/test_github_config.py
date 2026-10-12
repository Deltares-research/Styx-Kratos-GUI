"""The repository's other GitHub automation, next to the test workflow
(`test_ci_workflow.py`). None of it runs locally, so what each piece must do is pinned
here: the launcher smoke test on every platform the README promises, the linter, the
security scan, and the dependency updates and review."""

import pathlib
import re
import tomllib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"


def load(relative: str) -> dict:
    path = GITHUB / relative
    assert path.is_file(), f"{relative} is missing"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def triggers(workflow: dict) -> dict:
    found = workflow.get("on", workflow.get(True))         # YAML 1.1 reads a bare `on` as True
    return found if isinstance(found, dict) else {name: None for name in found}


def commands(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def uses(job: dict) -> list[str]:
    return [str(step.get("uses", "")) for step in job["steps"]]


# ── The launcher, the way a new user starts it ──────────────────────────────

@pytest.fixture(scope="module")
def launcher():
    workflow = load("workflows/launcher.yml")
    (only,) = workflow["jobs"].values()
    return workflow, only


def test_the_launcher_is_checked_on_every_push_and_pull_request(launcher):
    workflow, _ = launcher
    assert {"push", "pull_request"} <= set(triggers(workflow))


def test_the_launcher_is_checked_on_all_three_platforms_the_readme_names(launcher):
    _, job = launcher
    assert set(job["strategy"]["matrix"]["os"]) == {"windows-latest", "ubuntu-latest", "macos-latest"}
    assert job["strategy"]["fail-fast"] is False, "one platform failing must not hide the others"


def test_the_launcher_is_checked_on_the_oldest_python_the_readme_allows(launcher):
    _, job = launcher
    assert "3.10" in [str(v) for v in job["strategy"]["matrix"]["python"]]


def test_each_platform_runs_its_own_launcher_with_check(launcher):
    _, job = launcher
    steps = {step.get("run", "").strip(): step for step in job["steps"] if "run" in step}
    windows = steps.get("run.bat --check")
    posix = steps.get("./run.sh --check")
    assert windows and "windows" in windows["if"].lower() and windows["shell"] == "cmd"
    assert posix and "windows" in posix["if"].lower() and "!=" in posix["if"]
    for name in ("run.bat", "run.sh"):
        assert (ROOT / name).is_file(), name


def test_linux_gets_the_libraries_the_install_guide_tells_users_to_install(launcher):
    _, job = launcher
    guide = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
    for library in ("libglu1-mesa", "libxcursor1", "libxinerama1", "libxft2", "libxrender1"):
        assert library in commands(job) and library in guide, library


# ── Lint ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def lint():
    workflow = load("workflows/lint.yml")
    return workflow, workflow["jobs"]["ruff"]


def pinned_ruff() -> str | None:
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    match = re.search(r"^ruff==(\S+)", text, re.MULTILINE)
    return match.group(1) if match else None


def test_lint_runs_on_every_push_and_pull_request(lint):
    workflow, _ = lint
    assert {"push", "pull_request"} <= set(triggers(workflow))


def test_lint_runs_ruff_against_the_repository_config(lint):
    _, job = lint
    assert "ruff check" in commands(job)
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["ruff"]["lint"]["select"]


def test_ruff_is_pinned_once_and_ci_installs_that_pin(lint):
    """One version, in requirements-dev.txt, so a contributor's local check and CI agree
    and Dependabot has one place to bump it."""
    _, job = lint
    assert pinned_ruff(), "ruff must be pinned in requirements-dev.txt"
    assert "requirements-dev.txt" in commands(job)


# ── Security scan ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def codeql():
    workflow = load("workflows/codeql.yml")
    return workflow, workflow["jobs"]["analyze"]


def test_codeql_scans_pushes_pull_requests_and_a_weekly_schedule(codeql):
    workflow, _ = codeql
    assert {"push", "pull_request", "schedule"} <= set(triggers(workflow))


def test_codeql_covers_both_languages_of_the_app(codeql):
    _, job = codeql
    assert set(job["strategy"]["matrix"]["language"]) == {"python", "javascript-typescript"}
    assert "github/codeql-action/init@v3" in uses(job)
    assert "github/codeql-action/analyze@v3" in uses(job)


def test_codeql_may_write_its_findings_and_nothing_else(codeql):
    workflow, job = codeql
    permissions = job.get("permissions") or workflow.get("permissions")
    assert permissions["security-events"] == "write"
    assert set(permissions.values()) <= {"read", "write"}
    assert [k for k, v in permissions.items() if v == "write"] == ["security-events"]


def test_codeql_leaves_the_vendored_library_alone():
    config = load("codeql/codeql-config.yml")
    assert "frontend/vendor" in config["paths-ignore"]


# ── Dependencies ────────────────────────────────────────────────────────────

def test_dependabot_updates_the_pinned_packages_and_the_actions():
    config = load("dependabot.yml")
    assert config["version"] == 2
    watched = {(update["package-ecosystem"], update["directory"]) for update in config["updates"]}
    assert {("pip", "/"), ("github-actions", "/")} <= watched
    for update in config["updates"]:
        assert update["schedule"]["interval"] in {"daily", "weekly", "monthly"}


def test_pull_requests_are_reviewed_for_vulnerable_dependencies():
    workflow = load("workflows/dependency-review.yml")
    assert set(triggers(workflow)) == {"pull_request"}
    (job,) = workflow["jobs"].values()
    assert any(action.startswith("actions/dependency-review-action@") for action in uses(job))
