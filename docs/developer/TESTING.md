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

### Select tests

The arguments after the tier go to pytest. For example,
`python tools/test.py quick -k stages -x` runs the tests with "stages" in their name, and
stops at the first failure.

### JavaScript tests without a browser

These need the `quickjs` package. If it does not install in the virtual environment, set
`KRATOS_GUI_QUICKJS_PYTHON` to a Python that has it.

### No Chrome

The browser tests use the Chrome on your computer. Without Chrome, run
`python -m playwright install chromium` and set `KRATOS_GUI_TEST_BROWSER_CHANNEL=bundled`.

### Coverage

Add `--cov=core --cov=backend --cov=cli --cov-report=html --js-coverage` to a tier that
runs the browser tests. The Python report goes to `htmlcov/`, and JavaScript function
coverage to `htmlcov-js/summary.json`.

### JavaScript coverage only

Run the browser tier with JavaScript coverage from the repository folder:

```bash
python tools/test.py browser --js-coverage
```

This runs the browser tier (including the quick checks) and prints the per-module
JavaScript coverage table. If Chrome is unavailable, see [No Chrome](#no-chrome). To add
Python coverage to the report as well, see [Coverage](#coverage).

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

Test observable behavior and meaningful failure paths, not just coverage. Await
asynchronous work before restoring mocks, and check for both failed assertions and
uncaught errors.

## Tests that keep the GUI and the command line together

The GUI and `kratos-cli` save the same project file, but each makes an edit in its own
way. These tests fail when the two drift apart. After a deliberate change, rebuild the
generated file or snapshot with the command in the last column, and review the diff.

| Test | What it checks | After a deliberate change |
|---|---|---|
| `tests/cli/test_edit_parity.py`, `frontend/tests/test-edits.js` | Each Delete the GUI offers, found in its code, sends a request that makes the same project as `kratos-cli ... remove` | `python tests/cli/test_edit_parity.py --write` |
| `tests/cli/test_soil_line_commands.py` | A line or a soil body edit through the GUI's route and through `kratos-cli` makes the same project | Fix the side that changed |
| `tests/test_draft_parity.py`, `frontend/tests/test-drafts.js` | A new record starts the same in both | `python tests/test_draft_parity.py --write` |
| `tests/test_stage_parity.py` | The stages read the same in both | `python tests/test_stage_parity.py --write` |
| `tests/cli/test_gui_commands.py` | The GUI's command box knows the words of `kratos-cli` | Add or remove the row in "The GUI's command box, in the terminal" in `docs/CLI.md` |
| `tests/cli/test_documented_commands.py` | Every `kratos-cli` line in the docs is valid, and the shell tutorials run as written | Fix the page, or the command |
| `tests/cli/test_handover.py`, `tests/e2e/test_handover_flows.py` | A project file goes from one front end to the other unchanged | — |
| `tests/cli/test_json_contract.py` | The keys of the `--json` answers | `pytest tests/cli/test_json_contract.py --update-snapshots` |

`tests/e2e/test_handover_flows.py` runs only with `--run-e2e`, as in the `e2e` tier.
`frontend/tests/test-drafts.js` and the Structure-mode cases of
`frontend/tests/test-edits.js` run in the JavaScript tests without a browser, so they need
the `quickjs` package: see [Options](#options). The other cases of `test-edits.js` drive
a window, the stage list, the model tree or the command box, so they run in the browser
suite only (the `browser` tier and up).

## Tests that keep the server and the browser together

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

## The GUI tutorials

The pages in `docs/gui_tutorials/` are written by hand. Their screenshots are made by a
script that plays each step in the real GUI, so they always show the GUI as it is. The
same script is a test:

| Part | Where |
|---|---|
| The steps of a tutorial, and the model it builds | `tests/e2e/tutorials/<name>.py` (`STEPS`, `MODEL`, `PAGE`) |
| Clicks, windows, screenshots and the orange outline | `tests/e2e/tutorials/harness.py` |
| The test: play the steps, hold the deck to `MODEL`, hold the page to the screenshots | `tests/e2e/test_gui_tutorials.py` (`e2e` tier) |
| The page names only screenshots of its steps, and is on the site | `tests/test_gui_tutorial_pages.py` (`quick` tier) |
| A recorded Kratos run, and its replay | `tests/fixtures/tutorial_runs/<name>/`, `tests/fakes/replay_kratos.py` |
| The site settings, and the pages on the site | `mkdocs.yml`, built with Zensical (`requirements-docs.txt`) |
| Copy the pages, and build the site | `tools/docs_site.py`, checked by `tests/test_docs_site.py` (`quick` tier) |

Make the screenshots and the site on your computer, for a preview:

```bash
pip install -r requirements-docs.txt         # once, in the server's venv
python tools/gui_tutorial.py                 # every tutorial, then the site
python tools/gui_tutorial.py NAME --headed   # one tutorial; watch the browser play the steps
```

The screenshots go in `docs/gui_tutorials/images/<name>/` and the site in
`build/docs_site/site/`. Neither is committed. CI makes both for every pull request
(the artifact `docs-site` of the [docs site](../../.github/workflows/docs-site.yml)
run) and publishes the site from `main`. To look at the site of a pull request, download
the artifact from the **Artifacts** list at the bottom of the run's summary page, unzip
it, and open `index.html`. It needs no web server; only the search box does not work.

### How CI makes the site

The [docs site](../../.github/workflows/docs-site.yml) workflow makes the screenshots and
the site. These events start it:

| Event | Result |
|---|---|
| A pull request is opened or gets new commits | The site as the artifact `docs-site`, kept for 14 days |
| A push to `main`, for example a merge | The same artifact, and the job `publish` puts the site on GitHub Pages |
| **Run workflow** on the workflow's page in the **Actions** tab | The site as the artifact |

The workflow runs on Windows, because the recorded runs were made on Windows. The deck
compare then meets the same Gmsh build, and the screenshots get the fonts of a local
preview on Windows. The job does these steps:

1. It installs Python 3.11, the packages of `requirements.txt`, `requirements-dev.txt` and
   `requirements-docs.txt`, and the Chromium browser of Playwright.
2. It runs `python tools/gui_tutorial.py`. On a push to `main`, it adds `--strict-deck`.
3. The script runs `tests/e2e/test_gui_tutorials.py` with
   `--doc-screenshots docs/gui_tutorials/images`. The test starts the server on a free
   port and opens the GUI in Chromium.
4. The test plays the steps of each tutorial. At each `tour.picture(...)` in a step, it
   saves a PNG, with an orange outline on the control to use.
5. Calculate replays the recorded run, so the Results screenshots show real Kratos
   results. If the deck differs from the recorded deck, a pull request gets a warning and
   a push to `main` fails.
6. The script calls `tools/docs_site.py`, which copies the pages of the site into
   `build/docs_site/pages/` and checks that each picture a page shows exists. Then it
   runs `zensical build --strict --clean -f mkdocs.yml`, which writes the site to
   `build/docs_site/site/`.
7. The workflow uploads that folder as the artifact. On `main`, the job `publish` gives the
   artifact to GitHub Pages.

> [!NOTE]
> The job `publish` works only if GitHub Pages is on for the repository, with
> **Settings > Pages > Source** set to **GitHub Actions**.

The tools that make the site:

| Tool | What it does |
|---|---|
| GitHub Actions | Runs the workflow |
| Playwright and pytest | Play the steps in Chromium, take the screenshots, and fail the run if a step breaks |
| Zensical (`requirements-docs.txt`) | Makes HTML pages from the Markdown pages and the screenshots. It reads `mkdocs.yml`. |
| Material theme | The look of the site |
| GitHub Pages | Holds the published site |

### The pages on the site

The site holds all the documentation, not only the GUI tutorials: the README as the home
page, the guides in `docs/`, the `kratos-cli` tutorials, the pages of the example models
and the developer guide. The `nav` of `mkdocs.yml` lists each page, as a path from the
repository root. A page that is not in the `nav` is not on the site.

The pages stay where they are in the repository, so they also read well on GitHub. Zensical
reads one folder only, so `tools/docs_site.py` copies the pages of the `nav`, and the
pictures they show, into `build/docs_site/pages/` at the same paths. Links between pages
then work on GitHub and on the site. On the way, the copy changes what only works on
GitHub:

| On GitHub | On the site |
|---|---|
| A link to a file that is not on the site: code, a project file, a folder | A link to that file on GitHub |
| A link in HTML to a page, such as `<a href="docs/USAGE.md">` | A link to the HTML page |
| A picture in two versions, for the light and the dark mode | The light version only, as the site has a light theme only |
| A picture from the repository's GitHub pages, such as a workflow's status badge | Left out, as the site cannot show it while the repository is private |
| A GitHub alert, such as `> [!NOTE]` | A box of the same kind |

To add a page, write it where it belongs and add it to the `nav`. To look at the site
without making the screenshots again, run `python tools/docs_site.py`: it uses the
screenshots in `docs/gui_tutorials/images/`, and stops if one that a page shows is
missing. The strict build also stops on a link to a page or a heading that is not there.

**When you change the GUI.** If a tutorial step breaks, the `e2e` tier fails with the step
and the reason. Fix the step in `tests/e2e/tutorials/<name>.py`, and the page if the reader
must do something else. A new or removed screenshot must be added to or removed from
the page in the same pull request.

**When the deck of a tutorial changes.** The GitHub runners have no Kratos, so Calculate
replays the recorded run. If the deck differs from the recorded deck, the test warns on a
pull request, and the site build on `main` fails, so the site never shows results of
another model. On a computer with Kratos, record the run again and commit it:

```bash
python tools/gui_tutorial.py NAME --record   # about 5 minutes; writes tests/fixtures/tutorial_runs/NAME/
```

## What CI runs

For each pull request and each push to `main`, CI runs the `e2e` tier on Windows and
Ubuntu with Python 3.11, and on Windows with Python 3.15
([.github/workflows/tests.yml](../../.github/workflows/tests.yml)). If the Python line
coverage is less than 95 %, or any live JavaScript module has less than 95 % function
coverage, the run fails.

The `kratos` tier and the benchmarks need Kratos, which the GitHub runners do not have. A
self-hosted runner with Kratos runs the `kratos` tier every night and the benchmarks every
Saturday ([.github/workflows/kratos.yml](../../.github/workflows/kratos.yml)). These jobs
run only when the repository variable `KRATOS_RUNNER` is `true`.

The [docs site](../../.github/workflows/docs-site.yml) workflow plays the GUI tutorials on
Windows, makes their screenshots and builds the documentation site (see
[The GUI tutorials](#the-gui-tutorials)).

[CONTRIBUTING.md](../../CONTRIBUTING.md) lists the other checks of CI.
