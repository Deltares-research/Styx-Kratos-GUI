# CROW GUI tutorial with screenshots that update themselves

**Status:** approved. Nothing in it is built yet.

## The goal

A user learns the GUI from a tutorial that builds the CROW excavation wall step by step,
with a screenshot for each step. When the GUI changes, the screenshots change with it,
without anyone taking them again by hand. Users read the tutorial on a public website,
which always shows the GUI of `main`.

## The decisions

| Question | Decision |
|---|---|
| Where users read it | A website |
| Who can read it | Anyone: a public site |
| When it updates | On each merge to `main`. CI makes the screenshots and publishes the site. The screenshots are not committed to git. |
| What is on the site | Only the new CROW GUI tutorial. The other documents stay where they are. |
| How deep | Build the model from scratch, every window: soils, layers, pit, wall, strut, interface, loads, mesh, stages, calculate, results. The same steps as Way 1 of [the CLI tutorial](../../cli_tutorials/CROW_case.md). |
| Results screenshots | From one real Kratos run of CROW, recorded once and committed. It is recorded again by hand when the deck changes. |
| A deck that no longer matches the recorded run | A warning on a pull request. A failure only when the site is published from `main`. |
| A GUI change that breaks the tutorial | Found in the pull request, by a required check. The pull request cannot be merged until the tutorial works again. |

## Approaches

**A. MkDocs with the Material theme (recommended).** One `mkdocs.yml` and Markdown pages.
`mkdocs build --strict` fails on a link or an image that is not there, so a screenshot
that the script no longer makes shows up as a failed check. GitHub Pages hosts the output.
The team already writes Markdown. Check the maintenance status of Material for MkDocs
before the plan: its authors announced a successor, Zensical, which reads the same
`mkdocs.yml`. If Material is no longer maintained, use Zensical. The pages do not change.

**B. Sphinx with MyST Markdown.** Strong for API reference and versioned documents, but
more setup, and this site has one tutorial and no API pages.

**C. Markdown in the repository, with screenshots that a bot commits.** No website, and
binary files in every pull request. This does not fit the decision for a public site with
screenshots outside git.

## The design

### The parts

| Part | Where | What it does |
|---|---|---|
| The tutorial | `docs/gui_tutorials/CROW_case.md` | The text. Each step shows its screenshot with `![…](images/<name>.png)`. |
| Site settings | `mkdocs.yml` (repository root) | `docs_dir: docs/gui_tutorials`, the theme, and the navigation. Only this folder goes on the site. |
| The tutorial script | `tests/e2e/test_crow_tutorial.py` | Builds CROW in the GUI through its windows, step by step, as the tutorial says. With `--doc-screenshots DIR` it saves a screenshot at each step. |
| The run replay | `tests/fakes/replay_kratos.py` | Takes the place of `calculation.run`, as `tests/fakes/fake_kratos.py` does. It writes the deck, checks it against the recorded deck, and copies the recorded output into the new run directory. |
| The recorded run | `tests/fixtures/crow_run/` | The deck, the output that Results mode reads, and the answer of `calculation.run`, from one real Kratos run |
| The recorder | `tools/record_crow_run.py` | On a computer with Kratos: runs the tutorial script with `--run-kratos` and writes the run to `tests/fixtures/crow_run/` |
| The workflow | `.github/workflows/docs-site.yml` | Makes the screenshots, builds the site, and publishes it from `main` |

`tests/`, `tools/` and `.github/` are already left out of a release download
(`.gitattributes`), so a user's download does not get the recorded run.

### The tutorial script

- It uses the `app_page` and `live_server` fixtures of `tests/e2e/conftest.py`. It is an
  end-to-end test, so it is marked `e2e` and runs in the existing `e2e` tier on all four
  test jobs. These are required checks already, so a pull request that breaks a step
  cannot be merged.
- One function for each step of the tutorial. The docstring names the step number and the
  heading in `CROW_case.md`, so the text and the script are easy to keep together.
- It works the way a user does: menus, tool rail, windows, buttons, by their visible
  names. It does not open `crow.json` or run `crow.py`. At the end, it compares the
  model with `examples/CROW_case/crow.json`, so a step that silently goes wrong fails.
- `shot(page, name, target=None)` saves `name.png`: the whole window, or only one window
  or panel when `target` is a locator. It does nothing without `--doc-screenshots`.
- Same screenshots on each run: a 1600 × 1000 viewport, a device scale factor of 1,
  `animations="disabled"`, and a fixed theme. Parts that change on each run, such as the
  cursor coordinates in the status bar, are masked.
- **Calculate** runs with the replay instead of Kratos, so the Results steps show the
  recorded real run.

### The replay and a deck that changes

The replay compares the deck that the GUI writes with the recorded deck, without the names
that change from run to run, as `tests/muskat_reference.deck_view` does. What happens when
they differ depends on the `--strict-deck` option of the tutorial script:

- **Without `--strict-deck`** (the e2e tier, and the site build of a pull request): the
  test passes and gives a warning. In GitHub Actions, the warning is also a `::warning::`
  annotation on the pull request. The replay still copies the recorded output, so the
  Results screenshots of the pull request show the old run.
- **With `--strict-deck`** (only the site build of a push to `main`): the test fails. The
  site is not published and keeps its last version.

Both messages tell you to run `tools/record_crow_run.py` on a computer with Kratos and
commit the new run. A contributor without Kratos can merge, and someone with Kratos records
the run afterwards. The site never shows results from a model that is not the one in the
tutorial.

### The workflow

`docs-site.yml` has two jobs.

1. **build** runs on each pull request and each push to `main`, on `ubuntu-latest`, with
   the browser that the e2e tier uses:
   - `python tools/test.py e2e -k crow_tutorial --doc-screenshots docs/gui_tutorials/images`,
     with `--strict-deck` added on a push to `main`
   - `mkdocs build --strict`
   - Uploads the built site as an artifact, so a reviewer can look at the new screenshots
     of a pull request.
2. **deploy** runs only on a push to `main`, after **build**. It publishes the artifact
   with `actions/upload-pages-artifact` and `actions/deploy-pages`.

The `build` check is added to the required checks in `.github/rulesets/main.json`.
If the publish fails, the site keeps its last version.

### Changes to files that exist

- `.gitignore`: `docs/gui_tutorials/images/` and `site/` (the MkDocs output).
- `.github/lychee.toml`: leave out links to `docs/gui_tutorials/images/`. These files exist
  only in CI, and `mkdocs build --strict` checks them.
- `requirements-dev.txt`: MkDocs and its theme.
- `README.md`: a link to the site under *For users*.
- `docs/developer/TESTING.md`: the `--doc-screenshots` option, and how to record the run.

## Before the work starts

- An organisation admin turns on GitHub Pages for the repository, with the source
  *GitHub Actions*. A public site from a private repository needs a paid GitHub plan.
- `actions/upload-pages-artifact`, `actions/deploy-pages` and `actions/configure-pages`
  must be on the organisation's list of allowed actions.
- One real CROW run, recorded with `tools/record_crow_run.py`. Commit only the files
  that Results mode reads. If they are larger than a few MB, decide about Git LFS first.

## Risks

- **No Kratos on the GitHub runners.** After a pull request that changes the deck is
  merged, the site is not published until someone with Kratos records the run again. The
  red run on `main` shows this. The self-hosted Kratos runner could record the run, but
  that is not part of this design.
- **Screenshots that differ by font or browser version.** All screenshots are made on one
  operating system in CI, never on a contributor's computer.
- **The build takes time.** The script builds the whole model through windows, and that
  takes minutes. It runs in the e2e tier, which is already the slowest.

## Not part of this design

- Screenshots in `USAGE.md` or the other documents.
- Versions of the site for each release.
- The other example cases (Muskat, simple dike).
