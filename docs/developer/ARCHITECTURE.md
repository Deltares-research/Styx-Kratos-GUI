# Architecture reference

This page lists the parts of Styx: the libraries, the steps from a model to its results,
the modules of the engine, the server, the command line and the browser app, and the HTTP
API. It is for developers who change Styx. For the big picture, read the
[developer guide](README.md) first.

Related pages: [FEATURES.md](../FEATURES.md) (what works),
[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) (code size), [TESTING.md](TESTING.md) (how to run
the tests).

## Libraries and runtime

### Server and engine

| Part | What |
|---|---|
| Web framework | FastAPI 0.143.0 and Uvicorn 0.34.0 |
| Validation | Pydantic 2.14.2. `Project` in `core/model/schemas.py` is the one description of a model. |
| Geometry and mesh | Gmsh 4.13.1 (OpenCASCADE kernel) |
| Numerics | NumPy 2.2.6 (Python 3.10), 2.3.5 (Python 3.11 to 3.14) or 2.5.4 (Python 3.15 and newer) |
| State | One project in memory (`backend/store.py`). No database and no login. Runs are folders on disk. |
| Processes | Gmsh in a `ProcessPoolExecutor(max_workers=1)` (`core/gmsh_worker.py`). Kratos in a new subprocess for each run (`core/analysis/calculation.py`). |
| Solver | Kratos Multiphysics GeoMechanicsApplication. The launcher does not install it. Styx finds it through `kratos.local.json` or `KRATOS_GUI_PYTHON` and `KRATOS_GUI_KRATOS`. |

The versions are the fixed versions in [requirements.txt](../../requirements.txt).

### Browser app

| Part | What |
|---|---|
| 3D view | three.js, in `frontend/vendor/`. It is the only dependency. |
| Build | None: no npm, no bundler, no transpiler |
| Code style | ES5 modules (immediately invoked functions) on a global `App` object, loaded by `<script>` tags in `frontend/index.html` |
| Renderer without WebGL | A CPU painter (`frontend/js/canvas-renderer.js`) |
| HTTP | A `fetch` wrapper (`frontend/js/api.js`) |

## From a model to its results

Module paths are relative to `core/`.

| Step | Module | What happens |
|---|---|---|
| 1. Edit | `model/schemas.py`, `session.py` | Each edit goes through one path (`session._edited`): it drops the mesh size of a body the edit took away, then checks the full project again |
| 2. Build | `geometry/solid_model.py` | A solid for each soil piece (`model/regions.py` finds the pieces), then a boolean fragment, then the structures embedded. 2D sections and 3D solids. |
| 3. Draw | `geometry/tessellation.py` | A fast surface triangulation (about 0.1 s) for the view only. It is not a finite-element mesh. |
| 4. Mesh | `geometry/meshing.py` | The finite-element mesh, made again from the geometry each time |
| 5. Split | `kratos/interfaces.py` | Duplicates the nodes along a wall and writes zero-thickness contact elements |
| 6. Stages | `model/stages.py` | Makes the stage tree into the list of Kratos stages |
| 7. Export | `kratos/writer.py`, `kratos/materials.py`, `kratos/parameters.py` | Writes the `.mdpa`, `MaterialParameters.json` and `ProjectParameters.json` (one Kratos stage for each stage, with GiD and JSON output) |
| 8. Solve | `analysis/calculation.py` → `analysis/kratos_main.py` | Runs the Kratos orchestrator in a subprocess, in a new run folder (`~/KratosGUI/runs/<deck>_<time>/`) |
| 9. Read | `results/catalog.py` → `results/gid_reader.py`, `results/fields.py`, `results/mesh.py`, `results/parts.py` | Reads the GiD ASCII files (`.post.msh`, `.post.res`) into fields for each stage, and joins them to the parts of the deck |
| 10. Members | `results/members.py` | Reads the `<stage>__output_<member>.json` files into curves along the wall and its interface |

Steps 2 to 5 run in the Gmsh worker process. Only step 8 needs Kratos. Steps 9 and 10 only
read files, so you can open an old run, or a run from a different computer.

## Ways into the model

| Entry | What it does | Code |
|---|---|---|
| The GUI | Draw soil, structures, loads, water and stages; mesh; Calculate (F9) | `frontend/js/*`, `patches.js` |
| Command box | `mesh`, `calculate`, `water`, `units`, `stages`, `node <id>`, `colour <part>`, `results …`, `results plot …` | `patches.js` (`App.Command.run`) and the `command` or `handleCommand` function of each module |
| `run <file.py>` | Runs a Python file that returns a `Project` (for example `run tests/models/excavation.py`) | `core/scripting.py`, `POST /api/project/script` |
| Existing deck | Shows a Kratos deck that was written somewhere else as its own mesh, and runs its own files. A script names it with `external_deck.deck_project`. | `core/kratos/external_deck.py`, `frontend/js/deck.js` |
| Import mesh | Reads an `.mdpa` file back into mesh data, for view only | `core/kratos/mdpa_reader.py`, `POST /api/import/mdpa` |
| Export | Writes the deck without running it | `POST /api/export/mdpa`, `frontend/js/export.js` |
| `kratos-cli` | The terminal, without a browser or a server ([CLI.md](../CLI.md)). It changes the project file through `core/session.py`, as the routes do, and runs Gmsh in its own process (`gmsh_worker.run_here`). | `cli/`, `kratos-cli.bat`, `kratos-cli.sh` |

The Results menu and the Results panel build `results …` command strings and give them to
the same handler as the command box. So each results action has one implementation.

## Engine modules (`core/`)

`core/` is the engine, in plain Python, without a web framework. Each of its five packages
is one step of the pipeline:

| Package | Modules |
|---|---|
| `core/model/` | `schemas.py` (the `Project`), `units.py` (unit systems), `soil_models.py` (the soil models a material can be: law, parameters, defaults), `regions.py` (the pieces lines and sheet piles cut a layer into), `migration.py` (old project files), `templates.py` (empty and demo projects), `drafts.py` (where a new structure goes, as the GUI tools put it), `stages.py` (stage tree → Kratos stages), `script_writer.py` (the model as a Python script), `wall_translation.py` and `load_translation.py` (2D ↔ 3D) |
| `core/geometry/` | `solid_model.py` (OpenCASCADE solids), `tessellation.py` (view), `meshing.py` (finite-element mesh), `cad_import.py` (CAD files), `primitives.py` (recipes for drawn solids) |
| `core/kratos/` | `writer.py` (the deck), `materials.py` (`MaterialParameters.json`), `parameters.py` (`ProjectParameters.json`: stages, solver, output), `condition_checks.py` (the boundary condition warnings the export and `check` share), `interfaces.py` (split nodes along walls), `deck_files.py` (file names of the deck), `external_deck.py` (existing decks), `mdpa_reader.py`, `node_parts.py` |
| `core/analysis/` | `calculation.py` (run folder, subprocess, failure messages), `kratos_main.py` (runs inside the Python of Kratos) |
| `core/results/` | `catalog.py` (list of runs, file access, cache), `gid_reader.py` (GiD ASCII), `fields.py` (quantities, units, invariants), `mesh.py` (buffers for the view), `parts.py`, `members.py` (curves along walls and interfaces) |
| `core/` | `session.py` (each edit of a project, and the project file: the HTTP routes and the command line both use it), `gmsh_worker.py` (the Gmsh process), `scripting.py` (`run <file.py>`). They send work to several packages, so they are above all five. |

### Import rule

Imports go in one direction: **model ← geometry ← kratos ← analysis ← results**. A package
can import from itself or from a package to its left, never from a package to its right.
`tests/test_layout.py` checks this rule, with no exceptions.

If a lower package and a higher package need the same answer, the lower package gives it.
For example, `geometry/meshing.py` (`loaded_elements`) selects the edges that a load acts
on, and both the mesh preview and the export read them from there.

Each `__init__.py` in `core/` is empty, because Kratos starts `core.analysis.kratos_main`
with `-m` in a Python that has no pydantic and no Gmsh.

## Server modules (`backend/`)

| Module | What |
|---|---|
| `main.py` | Makes the FastAPI app and mounts the browser files |
| `middleware.py` | Checks the Host and Origin headers, and switches off the browser cache for the app files |
| `routes/` | One module for each group of the HTTP API (see below). `routes/common.py` has what they share: the upload limit (256 MB), the answer to a refused edit, the answer to a stored edit (the project, and in `edit_notes` the mesh sizes the edit removed), and the mesh jobs. |
| `store.py` | The one open project |
| `launcher.py` | Makes the virtual environment and starts the server (`run.bat`, `run.sh`) |

A route that changes the project does the change through `core/session.py`, and only adds
the HTTP parts.

## HTTP API

| Group | Module | Routes |
|---|---|---|
| Project | `routes/project.py` | `GET`/`PUT /api/project`; `POST /api/project/new`, `/reset`, `/script`, `/script/save`, `/stages/defaults`; `PATCH /api/project/layers`, `/materials`, `/lines`, `/bodies/{key}`, `/structures`, `/conditions`, `/stages`, `/dimension`, `/units`; `PUT /api/project/water`; `DELETE /api/project/custom_parts` |
| Geometry | `routes/geometry.py` | `GET /api/geometry`; `POST /api/geometry/create`, `/import`; `DELETE /api/geometry/parts/{key}` |
| Mesh | `routes/mesh.py` | `POST /api/mesh`, `/api/mesh/labels`, `/api/mesh/node-parts` |
| Decks | `routes/decks.py` | `POST /api/export/mdpa`, `/api/import/mdpa`, `/api/calculate` |
| Runs | `routes/results.py` | `GET /api/results/runs`, `/runs/{run}`, `/runs/{run}/files/{name}`, `/runs/{run}/archive` |
| Results of a stage | `routes/results.py` | `GET /api/results/runs/{run}/stages/{n}/fields`, `/mesh`, `/field/{name}`, `/displacement`, `/at/{node}`, `/parts` |
| Results of a member | `routes/results.py` | `GET /api/results/runs/{run}/members`, `/members/{member}/{quantity}` |
| Health | `main.py` | `GET /api/health` |

## Command-line modules (`cli/`)

| Module | What |
|---|---|
| `cli/terminal/main.py` | The parser and the entry point of `kratos-cli` |
| `cli/terminal/shell.py` | `kratos-cli shell`: commands one after the other in one process, with undo and redo |
| `cli/terminal/files.py` | The project file that a command reads, and where an edit is written |
| `cli/terminal/output.py`, `style.py`, `tables.py` | The answer of a command: text, JSON, colour, CSV |
| `cli/terminal/words.py` | How the words of a command line become a command and its values |
| `cli/commands/project.py` | `new`, `show`, `check`, `build`, `script`, `dimension`, `units`, `water` |
| `cli/commands/edit.py` | `get`, `set`, `add`, `remove` |
| `cli/commands/ground.py`, `volumes.py` | `domain`, `material`, `layer`, `line`, `body`, `parts`; `volume` |
| `cli/commands/structures.py` | `section`, `beam`, `wall`, `member`, `anchor`, `interface`, `load`, `normal-load` |
| `cli/commands/conditions.py` | `boundary`, `gravity` |
| `cli/commands/meshing.py`, `stages.py` | `mesh`, `export`; `stages` |
| `cli/commands/inspection.py`, `analysis.py`, `results.py` | `node`, `deck show`; `run`, `calculate`; `results` |
| `cli/commands/interactive.py` | `shell` |
| `cli/kratos-shell.*`, `cli/kratos-init-powershell.bat` | Helper scripts for the tutorials |

## Browser modules (`frontend/`)

The browser app has two layers. `frontend/base/` is the UI of the first design (menus,
tool bars, explorer, dialogs, command box). It stays unchanged, and the server serves it at
`/js` and `/css`. `frontend/js/` is the live layer: `patches.js` connects it to the frozen
shell. Only the camera of `base/js/orbit.js` is replaced; all other behaviour is wrapped by
`patches.js`.

| Role | Modules in `frontend/js/` |
|---|---|
| Connection to the shell | `patches.js`: menu actions, tool rails, panels, windows, the command box |
| Data | `api.js`, `model.js` (server project → shape that the shell needs), `buffers.js`, `history.js` (undo and redo), `units.js`, `unit-table.js` |
| View | `viewport.js` (three.js), `orbit.js` (camera with y up), `canvas-renderer.js`, `ruler.js`, `mesh-labels.js`, `part-colors.js`, `node-parts.js` |
| Modelling tools | `draw-input.js`, `lines.js`, `beams.js`, `anchors.js`, `interfaces.js`, `loads.js`, `normal-loads.js`, `water-command.js`, `soil-volume-dialog.js`, `soil-layers-dialog.js` (the **Modify soil layers** window, in place of the shell's own) |
| Materials | `material-sets.js`, `material-library.js`, `property-sets.js`, `soil-models.js` and `soil-model-table.js` (the soil models, generated from `core/model/soil_models.py`) |
| Mesh and stages | `mesh-settings.js`, `stages.js` |
| Files and scripts | `export.js`, `import-dialog.js`, `mdpa-import-dialog.js`, `download.js`, `zip.js`, `deck.js`, `script-command.js` |
| Calculation and results | `calculate.js`, `results.js` (the `results …` commands), `results-render.js` (colours, legend, CSV), `results-view.js` (the contours on screen), `results-plot.js` (`results plot …` and its SVG figure) |

## Results mode

```text
run folder (~/KratosGUI/runs/<deck>_<time>/)
  <deck>.mdpa, ProjectParameters.json           → part names, stage order, output names
  <deck>_<stage>.post.msh / .post.res           → results/gid_reader → results/fields, mesh, parts
  <stage>__output_wall.json, __output_interface_<face> → results/members
        │
        ▼  results/catalog.py (finds the files, reads each one once, caches by size and time)
  /api/results/... routes
        │
        ▼
  results.js         `results open | stage | field | range | csv …`   (no DOM, tested)
  results-render.js  colours, bands, legend ticks, CSV                 (no DOM, tested)
  results-plot.js    `results plot …`, the SVG figure for each stage   (no DOM, tested)
  results-view.js    contours and legend in the viewport               (DOM)
  patches.js         Results panel, Choose results window, plot window  (DOM)
```

- **One source of results:** Styx reads only what the deck writes, the GiD ASCII files and
  the JSON output. The GiD output has no interface elements, so the interface tractions
  come only from the JSON files.
- **Contours:** one field for each stage, with colour bands or smooth colours, colour maps,
  the deformed mesh, legend limits (`results range`), values at a node, and CSV export.
- **Plot along the wall:** bending moment, shear force, normal force, displacements and
  interface tractions against the level y, one panel for each stage. It follows the Kratos
  staged-excavation validation figure and its sign convention. The window can save SVG or
  CSV.

## Tests

[TESTING.md](TESTING.md) tells you how to run the tests. Two facts about the design of the
tests:

- **No recorded Kratos run is in the repository.** Without Kratos, the results code is
  tested on GiD output that `tests/fakes/` (a fake runner and `gid_writer.py`) makes from
  the test model.
- **One syntax error stops the full live layer** of the browser app, so
  `frontend/tests/syntax_check.py` parses each JavaScript file in each test tier.

## Design decisions

| Decision | Reason |
|---|---|
| Gmsh in one worker process | Gmsh keeps one global model in each process, and the worker process also contains OpenCASCADE crashes |
| Kratos in a subprocess, found by its path | Its compiled modules work only in the Python that they were made for, which is usually not the Python of the server |
| Frozen `frontend/base/` and live `frontend/js/` | The first design stays as it is. The live code wraps it, so the two never mix. |
| Part keys | One string is the Gmsh physical group, the `userData.key` in the view, the `obj:` of the tree, and the `OBJECT_PROPS` key |
| Logic without DOM, thin DOM code | Logic that needs no page goes into a module without `document`, so the tests can run it without a browser. `patches.js` and `results-view.js` only connect it to the page. |
| Runs are folders, results are files | A run never changes after it ends, and Styx reads it from disk. So results survive a restart of the server, and you can share a run as a ZIP file. |
