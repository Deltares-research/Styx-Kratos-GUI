# How to run the tests

This page tells you how to run the tests of Styx on your computer, and which tests CI runs.
For the test-first way of work, see [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Before you start

Install the test tools into the virtual environment of Styx. Run this command once, in the
repository folder:

```bash
# Windows
.venv-windows\Scripts\python.exe -m pip install -r requirements-dev.txt
# Linux (on macOS, use .venv-macos)
.venv-linux/bin/python -m pip install -r requirements-dev.txt
```

If the virtual environment does not exist yet, start `run.bat --check` or
`./run.sh --check` first.

## Run a test tier

In the repository folder, run `tools/test.py` with a tier. Any Python 3.10 or newer can
start it: it always runs pytest in the virtual environment of Styx.

| Command | What it runs |
|---|---|
| `python tools/test.py quick` | The JavaScript syntax check, the JavaScript tests without a browser, and pytest without the browser tests |
| `python tools/test.py browser` | `quick`, plus the JavaScript tests in a browser (`frontend/tests/index.html`, through Playwright) |
| `python tools/test.py e2e` | `browser`, plus the end-to-end tests of the GUI |
| `python tools/test.py kratos` | The tests that run Kratos. Kratos must be set up: see [KRATOS_SETUP.md](../KRATOS_SETUP.md). |
| `python tools/test.py bench` | The Kratos benchmark cases in `benchmarks/` |
| `python tools/test.py perf` | The performance tests |
| `python tools/test.py all` | All tests that this computer can run, and a list of the skipped steps with the reason |

At the end, the script lists each step as passed, failed or skipped. A step is skipped, not
failed, when something that it needs is missing: quickjs, Kratos or a browser.

## Options

- **Select tests:** the arguments after the tier go to pytest. For example,
  `python tools/test.py quick -k stages -x` runs the tests with "stages" in their name, and
  stops at the first failure.
- **JavaScript tests without a browser:** these need the `quickjs` package. If it does not
  install in the virtual environment, set `KRATOS_GUI_QUICKJS_PYTHON` to a Python that has
  it.
- **No Chrome:** the browser tests use the Chrome on your computer. Without Chrome, run
  `python -m playwright install chromium` and set `KRATOS_GUI_TEST_BROWSER_CHANNEL=bundled`.
- **Coverage:** add `--cov=core --cov=backend --cov=cli --cov-report=html --js-coverage` to
  a tier that runs the browser tests. The Python report goes to `htmlcov/`, and the
  JavaScript function coverage to `htmlcov-js/summary.json`.

## Tests that keep the GUI and the command line together

Some rules run twice: on the server, which the command line and the export use, and in
the browser, which needs the answer while the user edits. These tests hold the two to
one generated file. Each runs in the `quick` tier: the pytest side checks that the file
is up to date with the Python, and the JavaScript side, in
`frontend/tests/run_headless.py` and the browser suite, checks that the browser gives
the same answers.

| Test | What it holds together | The generated files |
|---|---|---|
| `tests/test_stage_parity.py` | The stage tree and the edits of the Stages window: `core/model/stages.py` and `App.Stages` | `frontend/tests/fixtures/stage-cases.js` |
| `tests/test_solver_parity.py` | A stage's expert solver settings, which apply and their defaults, and the stage's convergence criteria and defaults: `core/model/solver.py` and `App.Stages.solverRows` | `frontend/js/solver-settings.js`, `frontend/tests/fixtures/solver-cases.js` |
| `tests/test_draft_parity.py` | What a new soil, structure or load starts as: `core/model/drafts.py` and the GUI's drafts | `frontend/tests/fixtures/drafts.js` |
| `tests/test_soil_model_table.py` | The soil models and their parameters: `core/model/soil_models.py` | `frontend/js/soil-model-table.js` |
| `tests/test_unit_table.py` | The unit systems: `core/model/units.py` | `frontend/js/unit-table.js` |

After a deliberate change to one of these rules, run the test with `--write` to rewrite
its files, for example:

```bash
python tests/test_solver_parity.py --write
```

The rewritten files are part of the change. Read their diff, and check that each changed
line is wanted.

## What CI runs

For each pull request and each push to `main`, CI runs the `e2e` tier on Windows and
Ubuntu with Python 3.11, and on Windows with Python 3.13
([.github/workflows/tests.yml](../../.github/workflows/tests.yml)). If the Python line
coverage is less than 95 %, the run fails.

The `kratos` tier and the benchmarks need Kratos, which the GitHub runners do not have. A
self-hosted runner with Kratos runs the `kratos` tier every night and the benchmarks every
Saturday ([.github/workflows/kratos.yml](../../.github/workflows/kratos.yml)). These jobs
run only when the repository variable `KRATOS_RUNNER` is `true`.

[CONTRIBUTING.md](../../CONTRIBUTING.md) lists the other checks of CI.
