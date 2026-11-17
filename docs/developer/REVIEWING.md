# How to review a pull request

This page is the review method of Styx. Every reviewer uses it: a person, or an agent
that a person starts. All reviewers do the same checks in the same order and write the
report in the same shape. Then two reviews of one pull request can be compared, and the
author knows what to expect.

A review answers six questions:

1. Does the change do what the issue asks?
2. Is the change correct?
3. Does it fit the design of Styx?
4. Does it keep the way open for 3D and the other planned work?
5. Is it tested well?
6. Is it documented well?

Read [ARCHITECTURE.md](ARCHITECTURE.md) and the limits in [FEATURES.md](../FEATURES.md)
once before your first review. The checks below refer to them.

## 1. Collect what you need

Get these items before you read the code:

- **The issue.** Find the issue that the pull request closes ("Closes #123" in the
  description). Read it with `gh issue view 123`, including its comments. If there is no
  issue, use the pull request description as the request, and say so in the report.
- **The pull request.** `gh pr view <number>` gives the description and the labels.
  `gh pr checks <number>` gives the CI results.
- **The diff.** Compare with the merge base of `main`:

  ```bash
  git fetch origin
  git diff origin/main...HEAD --stat
  git diff origin/main...HEAD
  ```

- **The code around the diff.** Open each changed file and read the functions that call
  the changed code and the functions that it calls. A change can look correct alone and
  still be wrong in its place.

## 2. The checks

Do the checks in this order. Each check gives one row in the report (section 4).

### A. The issue

- Does the change do everything that the issue asks? Make a list of what the issue asks,
  and find each item in the diff.
- Does the change do more than the issue asks? Unrelated changes belong in their own pull
  request. One topic per pull request: a refactor and a fix are reviewed apart.
- If the issue is unclear, or the change chose one of several possible readings, say
  which reading the change took. Ask the author if the choice is not obvious.
- Does the pull request have one label (`bug`, `enhancement`, `documentation`,
  `breaking-change` or `dependencies`)? Is it the correct one?

### B. Correctness

- Check the edge cases that often break Styx code:
  - both dimensions, 2D and 3D (see check D);
  - linear and quadratic elements;
  - the unit systems of the project (`core/model/units.py`);
  - a model with no stage, one stage, and many stages;
  - a part that is switched off in a stage;
  - an old project file. Old `.json` files must still load, through
    `core/model/migration.py`.
- If the change touches the deck (`core/kratos/`), write the decks of the examples and of
  `tests/models/` before and after the change, and compare them.
  `writer.export_project(scripting.load_project(path))` gives the `.mdpa`, the
  `ProjectParameters.json` and the `MaterialParameters.json`. Only the decks that the
  issue wants to change may change.
- If a choice depends on how Kratos behaves, check it in the Kratos source
  (GeoMechanicsApplication) or in a Kratos run. Do not guess. If Kratos forces a choice,
  the code must say so where the choice is made.
- Errors: a refused input must give a message that tells the user what to do. Look for
  errors that are caught and hidden.

### C. The design of Styx

Each rule below is in [ARCHITECTURE.md](ARCHITECTURE.md). The change must keep all of
them.

- **One model.** `Project` in `core/model/schemas.py` is the one description of a model.
  The full project is checked again at each edit. A new field has a validator where a
  wrong value is possible.
- **One path for edits.** An edit goes through `core/session.py`. An HTTP route only adds
  the HTTP parts. `kratos-cli` uses the same session functions.
- **The import rule.** Imports go one way: model ← geometry ← kratos ← analysis ←
  results. Each `__init__.py` in `core/` stays empty, because Kratos starts
  `core.analysis.kratos_main` in a Python that has no pydantic and no Gmsh.
- **One answer in one place.** If two parts need the same answer, the lower package gives
  it. Look for logic that is copied into a second place instead of shared. Examples:
  `kratos/condition_checks.py` gives the export and `check` the same warnings;
  `geometry/meshing.py` gives the mesh preview and the export the same loaded edges.
- **Processes.** Gmsh runs in its worker process (`core/gmsh_worker.py`). Kratos runs in a
  subprocess. Neither is imported into the server.
- **Results come from files.** Styx reads only what the deck makes Kratos write: the GiD
  files and the JSON output.
- **The browser app.** Plain ES5 on the global `App` object: no npm, no bundler, no
  transpiler, no `class`, no arrow functions. `frontend/base/` stays frozen; new
  behaviour goes in `frontend/js/` and is connected through `patches.js`. Logic that does
  not need the page goes in a module without `document`, so that the headless tests can
  run it.
- **Generated files.** A generated file is made again, never edited by hand. For example,
  `frontend/js/soil-model-table.js` comes from `core/model/soil_models.py`.
- **Catalogues for choices.** A list of choices (soil models, laws and their defaults)
  lives in one catalogue in Python, and the browser gets a generated copy. A new choice
  is a new catalogue entry, not a new `if` in several places.
- **Style.** The new code reads like the code around it: names, comments, error style.
  Comments say why, not what the line does, and not how the code changed.

### D. The GUI and kratos-cli

- **The GUI comes first.** When a data shape has more than one good answer, the change
  must pick the one that is best for the GUI. Prefer explicit fields that a dialog can
  fill one to one (for example `on="face", face="left"`) over one value that the GUI
  must parse. The `kratos-cli` flags map onto those fields.
- **The two front ends stay the same.** The same quantity has the same name, option and
  convention in the GUI, in the GUI's command box and in `kratos-cli`. This covers what
  they show too: lists, notes, warnings and messages. A new edit in the GUI has a
  `kratos-cli` command in the same pull request, and the reverse. Where the two share a
  rule, it is one function, with a test that holds both to the same result.
- **The parity tests.** If the change alters an edit, a new record, the stages, a command
  word or a `--json` answer, the matching test in
  [TESTING.md](TESTING.md#tests-that-keep-the-gui-and-the-command-line-together) must
  change too. A regenerated fixture is part of the diff: read it and check that each
  changed line is wanted.
- **The user decides the physics.** Styx applies no condition, water pressure or load
  that the user did not ask for. A default (for example the standard supports of a new
  project) is visible in the model and can be changed or switched off, in the GUI and in
  `kratos-cli`.
- **How the GUI shows conditions.** A condition's check box in the Model explorer means
  "active". Symbols are hidden by default and show when the row is selected or with
  **Show**. Symbols are drawn along the soil edges, not along the domain box. A new
  condition kind reuses this behaviour.

### E. The way to 3D and the planned work

Styx is 2D plane strain today, and only 2D is proven in Kratos. 3D exists in the model,
the mesh and the deck, but no 3D model has run in a test yet. 3D work is planned next,
for example 3D piping analyses. A change made for 2D must not make that work harder.

Ask these questions about each change:

- **Does it work in both dimensions?** If it does not, does it refuse clearly in the
  dimension that it does not support? In the GUI the tool is left off the tool rail
  and greyed in the menus (`TWO_D_ONLY`, `THREE_D_ONLY`); `kratos-cli` refuses with the
  same message; the export gives a
  warning. A silent 2D-only assumption is a blocker.
- **Is the data shape good for 3D?** Look for a field that only makes sense in a section:
  an `(x, y)` point where 3D needs `(x, y, z)`, a value "per metre run", a line where 3D
  needs a face, an edge name where 3D has a face. Records are native to their dimension:
  a 2D kind lives beside its 3D kind (a sheet pile beside a wall panel), and the two are
  linked with `derived_from`. The conversion between them is in one place
  (`core/model/wall_translation.py`, `core/model/load_translation.py`).
- **Are dimension choices made in one place?** Element names, condition names and soil
  laws are chosen by the dimension in their tables (the element tables in
  `core/kratos/writer.py`, the laws in `core/model/soil_models.py`). Look for a fixed
  `2`, `"2D"`, `z = 0` or a `...2D3N` name in code that both dimensions use.
- **Geometry in both paths.** The 2D path and the 3D path of
  `core/geometry/solid_model.py` (for example `_embed_beams` and `_embed_3d_structures`)
  must stay in step. A fix in one path needs a look at the other.
- **Is a 2D-only feature recorded?** If the change is 2D only on purpose, the 3D gap is
  written in [FEATURES.md](../FEATURES.md), and in the issue list if it is planned work.

The same question applies to the other planned work. A change must not close the door on
it:

- plastic soil models that need load steps in a stage;
- more soil models and interface laws, added as catalogue entries;
- groundwater flow beyond steady state 2D, and condition lines with their own element
  size;
- supports that a stage can switch on and off, as water conditions already are;
- 3D interfaces, and walls that stand out above the ground in 3D.

### F. Tests

- **Test first.** Styx uses test-driven development. A logic change comes with an
  automated test that fails on the old code and passes on the new code. A check by hand
  in the browser does not replace it. If you are not sure that a test fails on the old
  code, run it on `origin/main`.
- **The right tier.** Each test is in the cheapest tier that can catch the bug:

  | Change | Tier |
  |---|---|
  | Python logic | pytest (`quick`) |
  | Browser logic without the page | headless JavaScript tests (`quick`) |
  | Browser code that needs `document` | a `test-*-dom.js` file (`browser`) |
  | A flow through the GUI | `tests/e2e` (`e2e`) |
  | The deck, the run or the results reader | the `kratos` tier and the benchmarks |

- **Tests that check something.** A test asserts real values, not only that a call did
  not raise. It does not mock the code that it tests. It covers the edge cases of check
  B. Where the feature exists in 2D and 3D, both have a case.
- **Shared models.** Tests use the models in `tests/models/`, never an example model.
  Outside the examples folder, no code, test or document names an example case or a
  path into that folder, except the pages that `tests/test_no_examples.py` allows.
- **Kratos.** If `core/kratos/`, `core/analysis/` or `core/results/` changed, the author
  ran `python tools/test.py kratos` and `python tools/test.py bench` on a computer with
  Kratos, and the pull request says so. GitHub's runners cannot run these tiers.
- **CI.** All required checks pass. Python line coverage must stay at 95 % or more. A
  test that also fails on `main` is not caused by the pull request, but the report names
  it.

### G. Documentation

The documents change in the same pull request as the code. Use this table to find which
documents a change needs:

| The change | Documents |
|---|---|
| A feature, or a limit of a feature | [FEATURES.md](../FEATURES.md): the status (Tested, Limited, Not exported, Not available) |
| A GUI action or dialog | [USAGE.md](../USAGE.md) |
| A `kratos-cli` command or option | [CLI.md](../CLI.md) and the tutorials in [cli_tutorials/](../cli_tutorials/README.md) |
| A module, package, route or design decision | [ARCHITECTURE.md](ARCHITECTURE.md) |
| A test tier or a parity test | [TESTING.md](TESTING.md) |
| Installation, the launcher or the Kratos setup | [INSTALLATION.md](../INSTALLATION.md), [KRATOS_SETUP.md](../KRATOS_SETUP.md) |
| A CI check | [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| An example model | Its `.json` file, made again from its `.py` script |

Check the text too:

- The user documents use easy English: short sentences, common words, complete steps.
  A user with little programming knowledge can follow them.
- Each `kratos-cli` line in the documents must run as written
  (`tests/cli/test_documented_commands.py` checks this).
- Help text explains a convention that differs from the model axes. It does not rename
  the convention in one place only.
- Docstrings and comments describe the code as it is now. They do not tell the history
  of the change or refer to a plan or a review.

### H. Project rules

- Do not name any other geotechnical program, and do not compare Styx with one, in code,
  comments, tests, documents, commit messages or pull request text. Describe each choice
  as Styx's own ("as the stage panel shows it", "as Kratos writes it").
- A workflow in `.github/workflows/` uses only the actions that the organisation allows.
  A third-party tool is downloaded as a release binary with a fixed checksum
  (`tests/test_github_automation.py` checks this).
- No secrets, local paths or personal files in the diff. `kratos.local.json` stays local.
- Commit messages are short, in the conventional style (`fix(cli): ...`,
  `feat(gui): ...`), and say what changed and why.

## 3. Run the checks

Run at least these commands on the branch:

```bash
python tools/test.py quick           # add "browser" or "e2e" if the frontend changed
python frontend/tests/syntax_check.py
ruff check .
python -m mypy
```

If Kratos is set up on your computer and the deck, the run or the results changed, run
`python tools/test.py kratos` and `python tools/test.py bench` too. If you cannot run a
tier, write that in the report, with the reason.

## 4. Write the report

Use this shape, so that all reviews look the same:

```markdown
## Review of #<pull request>: <title>

**Verdict:** Approve | Approve after small fixes | Changes needed

**Summary:** what the change does and which issue it closes, in your own words,
in two to four sentences.

| Check | Result | Note |
|---|---|---|
| A. The issue | OK / Comment / Problem / Not checked | one line |
| B. Correctness | | |
| C. Design | | |
| D. GUI and kratos-cli | | |
| E. 3D and planned work | | |
| F. Tests | | |
| G. Documentation | | |
| H. Project rules | | |

### Findings

1. **[Blocker]** `path/to/file.py:123`: what is wrong, why it matters, and a fix.
2. **[Should fix]** ...
3. **[Suggestion]** ...

### What I ran

- `python tools/test.py quick`: 2809 passed, 2 failed (both also fail on main)
- `python tools/test.py kratos`: not run, no Kratos on this computer

### Questions for the author

- ...
```

Sort the findings from the most serious to the least serious:

| Level | Meaning |
|---|---|
| Blocker | A wrong result, lost data, a broken rule of section C, D, E or H, or a logic change without a test. The pull request cannot be merged. |
| Should fix | A gap that a later change will trip over: a missing document, a weak test, logic copied into a second place. Fix it in this pull request unless the author and reviewer agree on a follow-up issue. |
| Suggestion | A better name, a simpler form, a small clean-up. The author decides. |

Each finding names a file and a line, says what is wrong and why it matters, and proposes
a fix. Do not report a finding that you could not confirm in the code. Put it under
"Questions for the author" instead.

## 5. Notes for an agent that reviews

- Read this whole page before you start, and follow it in order.
- The input is a pull request number, an issue number or a branch. With no input, review
  the current branch against `origin/main`, and find the issue from the pull request of
  the branch.
- Do not change files, commit, push, or post comments on GitHub, unless the person who
  started you asks for it. Give the report to that person.
- Cite `file:line` for each claim. If you could not check something (no Kratos, no issue,
  no network), say so in the report. Do not guess.
