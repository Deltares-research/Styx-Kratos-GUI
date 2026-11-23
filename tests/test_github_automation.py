"""The rest of the repository's GitHub automation, next to `test_ci_workflow.py` (the
tests) and `test_github_config.py` (launcher, ruff, CodeQL, dependencies): when each
workflow runs, the JavaScript lint and the type check, the secret and vulnerability
scans, the coverage floor, the Kratos tier on a self-hosted runner, releases, the link
check, the branch ruleset, and the files a contributor reads first. None of it runs
locally, so what each piece must do is pinned here."""

import itertools
import json
import pathlib
import re
import subprocess
import tomllib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"
WORKFLOWS = GITHUB / "workflows"
SEMVER = r"\d+\.\d+\.\d+"


def load(path: pathlib.Path) -> dict:
    assert path.is_file(), f"{path.relative_to(ROOT)} is missing"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def workflow(name: str) -> dict:
    return load(WORKFLOWS / name)


def triggers(found: dict) -> dict:
    on = found.get("on", found.get(True))                  # YAML 1.1 reads a bare `on` as True
    return on if isinstance(on, dict) else {name: None for name in on}


def commands(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


def uses(job: dict) -> list[str]:
    return [str(step.get("uses", "")) for step in job["steps"]]


def all_workflows() -> dict[str, dict]:
    return {path.name: load(path) for path in sorted(WORKFLOWS.glob("*.yml"))}


def check_names(job_id: str, job: dict) -> set[str]:
    """The names GitHub gives this job's checks: its `name` with the matrix filled in,
    once per combination, or the job id when it has no name."""
    name = str(job.get("name", job_id))
    matrix = dict(job.get("strategy", {}).get("matrix", {}))
    include = matrix.pop("include", [])
    matrix.pop("exclude", None)
    keys = [key for key, values in matrix.items() if isinstance(values, list)]
    combinations = [dict(zip(keys, values))
                    for values in itertools.product(*(matrix[key] for key in keys))]
    for extra in include:
        if not any(all(c.get(k) == v for k, v in extra.items() if k in keys) and
                   all(k in keys for k in extra) for c in combinations):
            combinations.append(dict(extra))
    names = set()
    for combination in combinations or [{}]:
        names.add(re.sub(r"\$\{\{\s*matrix\.(\w+)\s*\}\}",
                         lambda m: str(combination.get(m.group(1), "")), name))
    return names


def pull_request_checks() -> set[str]:
    """Every check a pull request gets, from the workflows `pull_request` triggers."""
    names = set()
    for found in all_workflows().values():
        if "pull_request" in triggers(found):
            for job_id, job in found["jobs"].items():
                names |= check_names(job_id, job)
    return names


# ── When workflows run ──────────────────────────────────────────────────────

def test_the_check_names_are_worked_out_the_way_github_does():
    job = {"name": "${{ matrix.os }} / Python ${{ matrix.python }}",
           "strategy": {"matrix": {"os": ["windows-latest", "ubuntu-latest"], "python": ["3.11"],
                                   "include": [{"os": "windows-latest", "python": "3.13"}]}}}
    assert check_names("tests", job) == {"windows-latest / Python 3.11",
                                         "ubuntu-latest / Python 3.11",
                                         "windows-latest / Python 3.13"}
    assert check_names("review", {"steps": []}) == {"review"}


def test_a_pull_request_runs_each_workflow_once_not_twice():
    """`push` without a branch filter fires for the pull request's own branch as well, so
    every check would run twice. Pushes count only on main, after the merge."""
    for name, found in all_workflows().items():
        on = triggers(found)
        if "pull_request" in on and "push" in on:
            assert on["push"] == {"branches": ["main"]}, name


@pytest.mark.parametrize("script", ["run.sh", "kratos-cli.sh"])
def test_the_shell_scripts_are_executable_in_git(script):
    """`./run.sh --check` (the launcher workflow, the release check) and `./kratos-cli.sh`
    need the bit set in the repository; a checkout made on Windows does not set it by
    itself. A script git does not know yet is added with `git add --chmod=+x`."""
    try:
        listed = subprocess.run(["git", "ls-files", "-s", script], cwd=ROOT,
                                capture_output=True, check=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as failure:
        pytest.skip(f"not a git checkout: {failure}")
    if not listed:
        pytest.skip(f"{script} is not in git yet: git add --chmod=+x {script}")
    assert listed.startswith("100755 "), listed


# ── Lint: JavaScript and types ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def lint():
    return workflow("lint.yml")


def test_eslint_runs_a_pinned_version_without_adding_npm_to_the_project(lint):
    """The frontend is build-free, so ESLint comes through npx in CI only, pinned there,
    and the repository gets no package.json."""
    job = lint["jobs"]["eslint"]
    assert any(action.startswith("actions/setup-node@") for action in uses(job))
    assert re.search(rf"npx --yes eslint@{SEMVER} ", commands(job)), commands(job)
    assert "frontend" in commands(job)
    assert not (ROOT / "package.json").exists()


def test_eslint_leaves_the_vendored_and_the_frozen_code_alone():
    config = (ROOT / "eslint.config.mjs").read_text(encoding="utf-8")
    assert "frontend/vendor/" in config and "frontend/base/" in config
    assert "import " not in config, "a plain npx eslint has no plugins to import"


def test_mypy_fails_the_build_now_its_findings_are_worked_down(lint):
    """It reported without failing while 142 findings stood (2026-10-12); with none
    left, a new one fails the lint workflow."""
    job = lint["jobs"]["mypy"]
    assert not job.get("continue-on-error", False)
    assert "mypy" in commands(job) and "requirements-dev.txt" in commands(job)
    pinned = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert re.search(rf"^mypy=={SEMVER}$", pinned, re.MULTILINE)
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["mypy"]["files"] == ["core", "backend", "cli"]


def test_dependabot_bumps_mypy_with_the_other_test_tools():
    config = load(GITHUB / "dependabot.yml")
    (pip,) = [update for update in config["updates"] if update["package-ecosystem"] == "pip"]
    assert "mypy" in pip["groups"]["test-tools"]["patterns"]


# ── Security ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def security():
    return workflow("security.yml")


def test_security_scans_pull_requests_main_and_a_weekly_schedule(security):
    assert {"push", "pull_request", "schedule"} <= set(triggers(security))
    assert security["permissions"] == {"contents": "read"}


def test_pip_audit_checks_both_requirement_files_at_a_pinned_version(security):
    run = commands(security["jobs"]["pip-audit"])
    assert re.search(rf"pip-audit=={SEMVER}", run)
    assert "-r requirements.txt" in run and "-r requirements-dev.txt" in run


def test_gitleaks_reads_the_whole_history_with_a_verified_binary(security):
    job = security["jobs"]["gitleaks"]
    (checkout,) = [step for step in job["steps"]
                   if str(step.get("uses", "")).startswith("actions/checkout")]
    assert checkout["with"]["fetch-depth"] == 0, "a secret in an old commit is still a leak"
    run = commands(job)
    assert re.fullmatch(SEMVER, job["env"]["GITLEAKS_VERSION"])
    assert re.fullmatch(r"[0-9a-f]{64}", job["env"]["GITLEAKS_SHA256"])
    assert "gitleaks/releases/download/v${GITLEAKS_VERSION}/" in run
    assert "sha256sum --check" in run
    assert "gitleaks git" in run


def test_every_ignored_leak_is_one_fingerprint():
    for line in (ROOT / ".gitleaksignore").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            assert re.fullmatch(r"[0-9a-f]{40}:[^:]+:[\w-]+:\d+", line), line


def test_codeql_runs_only_where_github_offers_code_scanning():
    """A private repository needs GitHub Code Security for it; without that, every run
    would fail. The schedule's event carries no repository, so the check asks the API."""
    found = workflow("codeql.yml")
    analyze = found["jobs"]["analyze"]
    gate = analyze["needs"]
    assert gate in found["jobs"]
    assert f"needs.{gate}.outputs" in analyze["if"]
    run = commands(found["jobs"][gate])
    assert ".private" in run and "CODE_SECURITY" in str(found["jobs"][gate])


def test_dependency_review_runs_only_where_github_offers_it():
    (job,) = workflow("dependency-review.yml")["jobs"].values()
    assert "github.event.repository.private" in job["if"]
    assert "vars.CODE_SECURITY" in job["if"]


# ── Coverage ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tests_job():
    (only,) = workflow("tests.yml")["jobs"].values()
    return only


def test_coverage_below_the_floor_fails_the_tests(tests_job):
    floor = re.search(r"--cov-fail-under=(\d+)", commands(tests_job))
    assert floor and int(floor.group(1)) >= 85, "the floor is what stops coverage sliding"


def test_the_coverage_table_lands_on_the_run_summary(tests_job):
    (step,) = [step for step in tests_job["steps"] if "GITHUB_STEP_SUMMARY" in step.get("run", "")]
    assert "coverage report" in step["run"]
    assert step["shell"] == "bash", "the same line on Windows and Linux"
    assert "always()" in step["if"]


# ── Kratos, on a machine that has it ────────────────────────────────────────

@pytest.fixture(scope="module")
def kratos():
    return workflow("kratos.yml")


def test_the_kratos_tiers_never_run_code_from_a_pull_request(kratos):
    """A self-hosted runner runs whatever it is given, so only the schedule and a
    maintainer's manual start may reach it."""
    assert set(triggers(kratos)) == {"schedule", "workflow_dispatch"}


def test_the_kratos_tiers_wait_for_a_registered_runner(kratos):
    for job in kratos["jobs"].values():
        assert {"self-hosted", "kratos"} <= set(job["runs-on"])
        assert "vars.KRATOS_RUNNER" in job["if"]


def test_the_kratos_workflow_runs_the_tiers_the_runner_knows(kratos):
    run = "\n".join(commands(job) for job in kratos["jobs"].values())
    assert "tools/test.py kratos" in run and "tools/test.py bench" in run


# ── Releases ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def release():
    return workflow("release.yml")


def test_a_version_tag_makes_a_release(release):
    assert triggers(release) == {"push": {"tags": ["v*"]}}
    assert release["permissions"] == {"contents": "read"}


def test_the_archive_is_built_from_the_tag_and_started_before_it_is_published(release):
    build = release["jobs"]["build"]
    assert "git archive" in commands(build)
    assert re.search(r"/run\.sh\"? --check", commands(build)), \
        "a release that does not start is not shipped"


def test_a_tag_that_is_not_the_version_in_the_code_is_not_released(release):
    build = release["jobs"]["build"]
    run = commands(build)
    assert "core.version import VERSION" in run and "GITHUB_REF_NAME" in run
    assert "core.version import describe" in run,         "the unpacked archive has to say the version of its tag"
    checkout = next(step for step in build["steps"]
                    if str(step.get("uses", "")).startswith("actions/checkout"))
    assert checkout.get("with", {}).get("fetch-depth") == 0,         "git archive writes `git describe` into the download, which needs the tag"


def test_git_archive_writes_the_version_into_the_download():
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert any(line.split() == ["core/version.py", "export-subst"] for line in lines)


def test_only_the_publishing_job_may_write(release):
    publish = release["jobs"]["publish"]
    assert publish["needs"] == "build"
    assert publish["permissions"] == {"contents": "write"}
    run = commands(publish)
    assert "gh release create" in run and "--generate-notes" in run and "--verify-tag" in run


def test_the_release_notes_are_sorted_by_label():
    config = load(GITHUB / "release.yml")
    labels = {label for category in config["changelog"]["categories"]
              for label in category["labels"]}
    assert {"bug", "enhancement", "dependencies"} <= labels


def test_the_archive_leaves_out_only_what_a_user_does_not_run():
    ignored = [line.split()[0] for line in
               (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
               if "export-ignore" in line]
    assert ignored
    needed = ("core", "backend", "cli", "frontend/js", "frontend/index.html",
              "requirements.txt", "run.bat", "run.sh", "kratos-cli.bat", "kratos-cli.sh",
              "README.md", "LICENSE", "CITATION.cff")
    for pattern in ignored:
        path = pattern.strip("/")
        assert (ROOT / path).exists(), f"{pattern} names nothing"
        assert not any(keep == path or keep.startswith(path + "/") for keep in needed), pattern


def test_shell_scripts_keep_lf_on_every_checkout():
    """With Git's autocrlf on, as Git for Windows sets it, a checkout writes CRLF, and
    bash reads the CR as part of each command (`set: pipefail\r: invalid option`): a
    clone on Windows could not run `kratos-cli.sh` in Git Bash."""
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert any(line.split()[:3] == ["*.sh", "text", "eol=lf"] for line in lines)
    for script in ("run.sh", "kratos-cli.sh"):
        assert b"\r" not in (ROOT / script).read_bytes(), script


# ── Documentation links ─────────────────────────────────────────────────────

def test_the_links_in_the_documentation_are_checked_with_a_verified_binary():
    found = workflow("docs.yml")
    assert {"push", "pull_request", "schedule"} <= set(triggers(found))
    (job,) = found["jobs"].values()
    assert re.fullmatch(SEMVER, job["env"]["LYCHEE_VERSION"])
    assert re.fullmatch(r"[0-9a-f]{64}", job["env"]["LYCHEE_SHA256"])
    run = commands(job)
    assert "lychee/releases/download/lychee-v${LYCHEE_VERSION}/" in run
    assert "sha256sum --check" in run
    assert "--config .github/lychee.toml" in run
    assert "*.md" in run
    assert (GITHUB / "lychee.toml").is_file()


ALLOWED_OWNERS = {"actions", "github"}
"""Whose actions a workflow may use. The organisation allows GitHub's own and a list of
others, and a workflow naming an action outside it fails at startup, before any job runs
(`lycheeverse/lychee-action` did, on every run). A tool from elsewhere is downloaded as
a release binary and checked against its checksum, as gitleaks and lychee are."""


def test_every_action_a_workflow_uses_is_one_the_organisation_allows():
    found = [f"{name}: {use}" for name, flow in all_workflows().items()
             for job in flow["jobs"].values() for use in uses(job)
             if use and use.split("/")[0] not in ALLOWED_OWNERS]
    assert not found, "actions outside the organisation's list:\n" + "\n".join(found)


def test_the_link_check_settings_are_ones_lychee_accepts():
    """lychee 0.24 refused the old boolean `include_fragments = false` ("wanted string
    or table"): the whole check failed to start."""
    settings = tomllib.loads((GITHUB / "lychee.toml").read_text(encoding="utf-8"))
    assert settings["include_fragments"] in ("none", "anchor-only", "text-only", "full")


# ── Branch ruleset ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ruleset():
    path = GITHUB / "rulesets" / "main.json"
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_ruleset_guards_the_default_branch(ruleset):
    assert ruleset["target"] == "branch" and ruleset["enforcement"] == "active"
    assert ruleset["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    kinds = {rule["type"] for rule in ruleset["rules"]}
    assert {"deletion", "non_fast_forward", "pull_request", "required_status_checks"} <= kinds


def required_checks(ruleset) -> set[str]:
    (rule,) = [rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"]
    return {check["context"] for check in rule["parameters"]["required_status_checks"]}


def test_no_two_jobs_report_under_the_same_check_name():
    """A required check is matched by name alone, so two jobs sharing one would let
    either of them satisfy it."""
    seen: dict[str, str] = {}
    for workflow_name, found in all_workflows().items():
        if "pull_request" not in triggers(found):
            continue
        for job_id, job in found["jobs"].items():
            for name in check_names(job_id, job):
                assert name not in seen, f"{name!r} in {workflow_name} and {seen[name]}"
                seen[name] = workflow_name


def test_every_required_check_is_one_a_pull_request_really_gets(ruleset):
    """A required check no workflow produces blocks every merge for ever."""
    missing = required_checks(ruleset) - pull_request_checks()
    assert not missing, missing


def test_the_tests_lint_launcher_and_scans_are_required(ruleset):
    required = required_checks(ruleset)
    for job_id, job in workflow("tests.yml")["jobs"].items():
        assert check_names(job_id, job) <= required
    for job_id, job in workflow("launcher.yml")["jobs"].items():
        assert check_names(job_id, job) <= required
    assert {"ruff", "eslint", "actionlint", "pip-audit", "gitleaks"} <= required


def test_the_workflows_themselves_are_linted():
    """None of them can run locally; actionlint catches a wrong expression, an unknown
    key or a shell mistake before a run does."""
    run = commands(workflow("lint.yml")["jobs"]["actionlint"])
    assert re.search(rf"rhysd/actionlint:{SEMVER}", run)
    labels = load(GITHUB / "actionlint.yaml")["self-hosted-runner"]["labels"]
    for job in workflow("kratos.yml")["jobs"].values():
        assert set(job["runs-on"]) - {"self-hosted"} <= set(labels)


def test_advisory_and_flaky_checks_are_not_required(ruleset):
    """mypy is not a required check yet; outside links can be down for reasons no pull
    request causes."""
    required = required_checks(ruleset)
    assert "mypy" not in required
    for job_id, job in workflow("docs.yml")["jobs"].items():
        assert not check_names(job_id, job) & required


# ── What a contributor reads first ──────────────────────────────────────────

@pytest.mark.parametrize("name", ["LICENSE", "CITATION.cff", "CONTRIBUTING.md", "SECURITY.md"])
def test_the_community_files_are_there(name):
    assert (ROOT / name).is_file(), name


def test_the_readme_points_to_the_contributing_guide_and_the_security_policy():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "(CONTRIBUTING.md)" in readme and "(SECURITY.md)" in readme


# ── Who made it ─────────────────────────────────────────────────────────────

AUTHOR = "Marjan Fathian"
HOME = "https://github.com/Deltares-research/Styx-Kratos-GUI"
STARTED = "indigocoral/Kratos-GUI"


@pytest.mark.parametrize("name", ["README.md", "docs/INSTALLATION.md", "CITATION.cff"])
def test_the_documents_name_the_repository_by_its_new_name(name):
    """The repository is the public Styx-Kratos-GUI under Deltares-research. A clone made
    from an old link would land in a folder the guides do not name."""
    text = (ROOT / name).read_text(encoding="utf-8")
    assert "Deltares-research/Kratos-GUI" not in text
    assert "Deltares-research/Styx-Kratos-GUI" in text
    assert "cd Kratos-GUI" not in text


def test_the_link_check_skips_only_the_repository_not_yet_published():
    """Deltares-research/Styx-Kratos-GUI answers 404 until the public copy is made, which
    would fail every run. Only that address is skipped: any other GitHub link is checked.
    Once it is published, drop the exclusion and this test with it."""
    excluded = tomllib.loads((GITHUB / "lychee.toml").read_text(encoding="utf-8"))["exclude"]
    github = [pattern for pattern in excluded if "github" in pattern]
    assert github == [r"^https://github\.com/Deltares-research/Styx-Kratos-GUI"]


def test_the_readme_does_not_link_to_the_private_repository():
    """Where the project started is named, not linked: that repository stays private, and
    its link would answer 404 to every reader of the public one."""
    assert f"https://github.com/{STARTED}" not in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_citation_names_the_author():
    """GitHub reads CITATION.cff at the root and shows "Cite this repository" beside the
    code, with these authors, in the order given."""
    citation = load(ROOT / "CITATION.cff")
    assert citation["cff-version"] == "1.2.0"
    assert citation["type"] == "software"
    assert citation["license"] == "MIT"
    assert citation["repository-code"] == HOME
    first = citation["authors"][0]
    assert (first["given-names"], first["family-names"]) == ("Marjan", "Fathian")
    assert first["affiliation"] == "Deltares"
    assert {"title", "message", "abstract"} <= set(citation)


def test_the_license_is_mit():
    """LICENSE holds the plain MIT text, with nothing added, so that GitHub detects it and
    shows "MIT" on the repository page. The third-party licenses are named in the README."""
    license_file = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_file.startswith("MIT License\n\nCopyright (c) 2026 Deltares\n")
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_file
    assert "Gmsh" not in license_file
    assert not (ROOT / "NOTICE").exists(), "a NOTICE file belongs to an Apache license"


def test_every_place_that_names_the_license_says_mit():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "MIT" and project["license-files"] == ["LICENSE"]
    for name in ("README.md", "CONTRIBUTING.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "MIT License" in text and "to be decided" not in text, name
    assert "badge/license-MIT-" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_readme_license_section_names_the_third_party_licenses():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## License", 1)[1].split("\n## ", 1)[0]
    assert "MIT License" in section and "(LICENSE)" in section
    for name in ("Gmsh", "GNU GPL", "three.js", "html2canvas", "Kratos Multiphysics"):
        assert name in section, name


def test_the_readme_names_the_author_and_where_the_project_started():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    authors = readme.split("## Authors", 1)[1].split("\n## ", 1)[0]
    assert AUTHOR in authors and "(CITATION.cff)" in authors
    assert STARTED in authors, "the history before the move is part of the credit"


def test_every_path_has_an_owner():
    lines = [line.split() for line in
             (GITHUB / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    assert any(line[0] == "*" and len(line) > 1 and line[1].startswith("@") for line in lines)


@pytest.mark.parametrize("name", ["bug_report.yml", "feature_request.yml"])
def test_the_issue_forms_are_complete(name):
    form = load(GITHUB / "ISSUE_TEMPLATE" / name)
    assert form["name"] and form["description"] and form["labels"]
    ids = [field["id"] for field in form["body"] if "id" in field]
    assert ids and len(ids) == len(set(ids)), "an id may be used once"
    assert any(field.get("validations", {}).get("required") for field in form["body"])


def test_a_bug_report_asks_for_the_version_where_styx_says_it():
    form = load(GITHUB / "ISSUE_TEMPLATE" / "bug_report.yml")
    field = next(field for field in form["body"] if field.get("id") == "version")
    assert field["validations"]["required"] is True
    assert "kratos-cli --version" in field["attributes"]["description"]
    assert "About" in field["attributes"]["description"]


def test_blank_issues_are_turned_off():
    assert load(GITHUB / "ISSUE_TEMPLATE" / "config.yml")["blank_issues_enabled"] is False


def test_the_pull_request_template_asks_for_the_checks_ci_runs():
    template = (GITHUB / "pull_request_template.md").read_text(encoding="utf-8")
    assert "tools/test.py" in template and "ruff check" in template
