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

## JavaScript coverage only

To run just the browser JavaScript suite and print its per-module coverage table,
use this command from the repository folder in PowerShell:

```powershell
$env:KRATOS_GUI_TEST_BROWSER_CHANNEL = "bundled"
.\.venv-windows\Scripts\python.exe -m pytest tests\browser\test_js_unit_suite.py --js-coverage -q -s
```

This selects Playwright's Chromium rather than the separately installed Google Chrome.
If Chromium is missing, install it with the same virtual environment:

```powershell
.\.venv-windows\Scripts\python.exe -m playwright install chromium
```

The report in `htmlcov-js/summary.json` lists each loaded `frontend/js` module's
function count, covered count, percentage, and `missed` functions. This is function
coverage, not line or branch coverage; it excludes `frontend/base/js`, vendor scripts,
and modules the suite did not load. The report is written even when JavaScript
assertions or the coverage threshold fail. With `--js-coverage`, every reported live
module must reach at least **95% function coverage**; the overall average alone is
not sufficient.

Add pure-logic cases to the existing `frontend/tests/test-*.js` suites. Browser-only
form and event tests belong in the browser suite; register new test files in
`frontend/tests/index.html`. Do not add DOM-dependent files to the headless runner.

When reviewing missed functions, test observable behavior rather than calling callbacks
only to increase the percentage. Cover accepted and refused edits, retry after server
errors, cancellation without writes, and cleanup of temporary UI. Await asynchronous
work before restoring mocks, and check that the harness reports no uncaught errors as
well as no failed assertions. Function coverage alone does not prove those paths work.
For action wiring, assert each button's destination and arguments independently.
For scene visibility, inspect the drawable group's visibility, not only its eye flag;
for stage edits, check ordering and parent links as well as stage counts.

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
