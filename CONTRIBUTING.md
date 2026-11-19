# Contributing to Styx

Thank you for helping. Bug reports, feature requests, documentation fixes and code are all
welcome. This guide covers how to set up, how changes are made and checked, and what CI
expects from a pull request.

For a security problem, do not open an issue. Follow [SECURITY.md](SECURITY.md) instead.

## Reporting a bug or asking for a feature

Open an issue and pick **Bug report** or **Feature request**. For a bug, the most useful
things to include are:

- the steps that reproduce it, from starting the app;
- the version you ran: **Help > About** in the GUI, or `kratos-cli --version`;
- your operating system, your Python version, and your Kratos version if the bug is in
  Calculate or Results;
- the error text from the terminal or from the browser's developer console.

## Setting up

Install Styx as [INSTALLATION.md](docs/INSTALLATION.md) describes. The first start of
`run.bat` (Windows) or `./run.sh` (Linux, macOS) creates a virtual environment (venv) for the
app. Then add the test tools to that venv:

```bash
# Windows
.venv-windows\Scripts\python.exe -m pip install -r requirements-dev.txt
# Linux (use .venv-macos on macOS)
.venv-linux/bin/python -m pip install -r requirements-dev.txt
```

[TESTING.md](docs/developer/TESTING.md) lists the test tiers and what each one needs. The
[developer guide](docs/developer/README.md) explains how the pieces fit together.

## Making a change

1. Create a branch from `main`, for example `git checkout -b fix/stage-order`.
2. **Write a failing test first, then make it pass.** The project follows test-driven
   development. A logic change comes with an automated test, not with a manual check in the
   browser.
3. Keep the frontend build-free. It is plain ES5 browser JavaScript: do not add npm, a bundler or
   a transpiler. Logic that does not need the DOM goes into a module with no DOM in it, so
   the headless suites can test it.
4. Run the checks below before you push.

### The checks CI runs, and how to run them locally

| Check | Locally | In CI |
|---|---|---|
| Tests | `python tools/test.py quick`, or `browser` if you changed the frontend | [tests](.github/workflows/tests.yml): the `e2e` tier on Windows and Ubuntu, with a 95 % line-coverage floor |
| JavaScript syntax | `python frontend/tests/syntax_check.py` after any JavaScript change. One syntax error silently disables the whole frontend layer. | Part of the tests |
| Python lint | `ruff check .` | [lint](.github/workflows/lint.yml), `ruff` job |
| JavaScript lint | Needs Node: `npx eslint@10.12.0 frontend` | [lint](.github/workflows/lint.yml), `eslint` job |
| Workflows | [actionlint](https://github.com/rhysd/actionlint), if you changed `.github/workflows/` | [lint](.github/workflows/lint.yml), `actionlint` job |
| Types | `python -m mypy` | [lint](.github/workflows/lint.yml), `mypy` job. A new finding fails it. |
| Launcher | `run.bat --check` or `./run.sh --check` | [launcher](.github/workflows/launcher.yml): Windows, Linux and macOS, on Python 3.10 and 3.15 |
| Vulnerable packages | `pip install pip-audit`, then `pip-audit -r requirements.txt -r requirements-dev.txt -r requirements-docs.txt` | [security](.github/workflows/security.yml), `pip-audit` job, also weekly |
| Secrets in the history | [gitleaks](https://github.com/gitleaks/gitleaks): `gitleaks git .` | [security](.github/workflows/security.yml), `gitleaks` job |
| Documentation site | `python tools/gui_tutorial.py`, if you changed the GUI or `docs/gui_tutorials/`; `python tools/docs_site.py`, if you changed another page or the `nav` of `mkdocs.yml`. See [The GUI tutorials](docs/developer/TESTING.md#the-gui-tutorials). | [docs site](.github/workflows/docs-site.yml): screenshots and site on every pull request, published from `main` |
| Documentation links | [lychee](https://github.com/lycheeverse/lychee): `lychee --config .github/lychee.toml './**/*.md'` | [docs](.github/workflows/docs.yml), also weekly |
| Code scanning | Not run locally | [codeql](.github/workflows/codeql.yml) and [dependency review](.github/workflows/dependency-review.yml), where GitHub offers them |

If gitleaks reports something that is not a secret, add its fingerprint to
[.gitleaksignore](.gitleaksignore), with a comment that says why.

The tests that run Kratos (`python tools/test.py kratos`) and the benchmark cases
(`python tools/test.py bench`) cannot run on GitHub's runners. If your change touches the
deck writer or the results reader, run them on a machine that has Kratos and say so in the
pull request.

## Opening a pull request

- Explain what changed and why, and how you tested it. The pull request template asks for
  this.
- Keep one topic per pull request. A refactor and a fix are easier to review apart.
- Add a label: `bug`, `enhancement`, `documentation`, `breaking-change` or `dependencies`.
  The release notes are grouped by these labels.
- All required checks must pass before the pull request can be merged into `main`.

The project's license is still to be decided (see [LICENSE](LICENSE)). Contributions are
released under the license the project chooses.

## For maintainers

### Releasing

The version number is `VERSION` in [core/version.py](core/version.py). The GUI's
**Help > About** and `kratos-cli --version` show it. To make a release:

1. In a pull request, set `VERSION` to the new number, for example `"1.2.0"`, and merge it.
2. Tag the merge commit on `main` with `v` and the same number, and push the tag:

   ```bash
   git tag -a v1.2.0 -m "Styx 1.2.0"
   git push origin v1.2.0
   ```

[release.yml](.github/workflows/release.yml) stops if the tag is not `v` + `VERSION`. It
builds `.zip` and `.tar.gz` archives from the tag, checks that the unpacked archive starts
and says the version of the tag, and publishes a GitHub release with notes made from the
merged pull requests. A tag with a hyphen, such as `v1.2.0-rc.1`, makes a pre-release.
[.gitattributes](.gitattributes) lists what the archives leave out.

A copy that is not exactly a release adds its commit to the version. For example,
`1.2.0+12.g2408259` is 12 commits after `v1.2.0`, at commit `2408259`. A clone with
changes that are not committed adds `.dirty`.

### Branch protection

[.github/rulesets/main.json](.github/rulesets/main.json) is the ruleset for `main`. It blocks
deletion and force-pushes, requires a pull request, and lists the required checks. To apply
it:

```bash
gh api -X POST repos/{owner}/{repo}/rulesets --input .github/rulesets/main.json
```

Or use **Settings > Rules > Rulesets > New ruleset > Import a ruleset**. Rulesets on a
private repository need GitHub Pro, Team or Enterprise. A public repository has them for
free. When you rename a job or a matrix entry, update the ruleset as well:
`tests/test_github_automation.py` fails if a required check no longer exists.

### Code scanning on a private repository

CodeQL and the dependency review need GitHub Code Security on a private repository, so they
skip themselves there. If the repository has Code Security, set the repository variable
`CODE_SECURITY` to `true` (**Settings > Secrets and variables > Actions > Variables**). On a
public repository they run without it.

### The Kratos runner

[kratos.yml](.github/workflows/kratos.yml) runs the Kratos tier every night, and the
benchmark cases on Saturdays, on a self-hosted runner. To set it up on a machine that has
Kratos:

1. Go to **Settings > Actions > Runners > New self-hosted runner**, follow the steps, and
   add the label `kratos`.
2. In the runner's `.env` file, set `KRATOS_GUI_PYTHON` and `KRATOS_GUI_KRATOS`, as
   described in `core/analysis/calculation.py`. Each run starts from a clean checkout, so
   `kratos.local.json` is not there.
3. Set the repository variable `KRATOS_RUNNER` to `true`.

The workflow runs only on its schedule or when started by hand, never for a pull request,
because a self-hosted runner runs any code it is given.
