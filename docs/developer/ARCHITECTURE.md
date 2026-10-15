# Architecture

Styx is a Deltares/Kratos-branded geotechnical modeller. You build a soil and excavation
model, mesh it with Gmsh, export it as a Kratos GeoMechanics deck, run it in construction
phases, and read the results back in its Results mode. It is a FastAPI server
holding one project, plus a build-free browser front end.

See also: the [developer guide](README.md) (the big picture, start there),
[FEATURES.md](../FEATURES.md) (what works, per Kratos feature),
[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) (code size per module),
[INSTALLATION.md](../INSTALLATION.md) (install and run),
[KRATOS_SETUP.md](../KRATOS_SETUP.md) (configure Kratos).

## At a glance

### Backend

| Layer | What |
|---|---|
| Framework | FastAPI 0.115.6 + Uvicorn 0.34.0 |
| Validation | Pydantic 2.10.4. `Project` (`core/model/schemas.py`) is the single source of truth |
| Geometry/mesh | Gmsh 4.13.1 (OpenCASCADE kernel) |
| Numerics | NumPy 2.2.1 |
| State | One project in memory (`backend/store.py`). No database, no auth. Run results live on disk |
| Concurrency | Gmsh in a `ProcessPoolExecutor(max_workers=1)` (`core/gmsh_worker.py`). Kratos in a subprocess per run (`core/analysis/calculation.py`) |
| Solver | Kratos MultiPhysics GeoMechanicsApplication. Not installed by the launcher; found through `KRATOS_GUI_PYTHON` / `KRATOS_GUI_KRATOS` or `kratos.local.json` |
| Tests | pytest 8.3.4 + httpx `TestClient`, 1273 cases. `python -m pytest -q` from the repository root, with an interpreter that has gmsh |

### Frontend

| Layer | What |
|---|---|
| 3D | three.js (vendored), the only dependency |
| Build | **None.** No npm, no bundler, no transpiler |
| Style | ES5 IIFE modules on a global `App` namespace, 44 `<script>` tags in `frontend/index.html` |
| Fallback renderer | Hand-written CPU painter (`frontend/js/canvas-renderer.js`) when there is no WebGL |
| HTTP | `fetch` wrapper (`frontend/js/api.js`) |
| Tests | ~90-line browser harness (`frontend/tests/index.html`, 36 test files). The DOM-free suites also run headless under quickjs: `python frontend/tests/run_headless.py`, 302 cases in 9 suites. `python frontend/tests/syntax_check.py` parses every JS file |

## How a model flows

Module paths are relative to `core/`.

| Step | Module | Note |
|---|---|---|
| 1. Edit | `model/schemas.py` | Every PATCH re-validates the *whole* project |
| 2. Build | `geometry/solid_model.py` | Boxes → boolean fragment → cut pit → embed structures; 2D sections and 3D solids |
| 3. Draw | `geometry/tessellation.py` | OCC `importStl()`, ~0.1 s, for display only (not an FE mesh) |
| 4. Mesh | `geometry/meshing.py` | Real tet/tri mesh, re-derived from the geometry each time |
| 5. Split | `kratos/interfaces.py` | Duplicate nodes along a wall, zero-thickness contact elements |
| 6. Phase | `model/phases.py` | The phase tree resolved into the sequence of stages Kratos runs: what is active, water, loads |
| 7. Export | `kratos/writer.py`, `kratos/materials.py`, `kratos/parameters.py` | `.mdpa` + `MaterialParameters.json` + `ProjectParameters.json` (one stage per phase, with GiD and JSON output processes) |
| 8. Solve | `analysis/calculation.py` → `analysis/kratos_main.py` | Kratos' orchestrator in a subprocess, writing into a run directory of its own (`~/KratosGUI/runs/<deck>_<stamp>/`) |
| 9. Read back | `results/catalog.py` → `results/gid_reader.py`, `results/fields.py`, `results/mesh.py`, `results/parts.py` | The run's GiD ASCII (`.post.msh` / `.post.res`) parsed into fields per stage, joined to the deck's parts |
| 10. Members | `results/members.py` | The deck's `<stage>__output_<member>.json` turned into curves along the wall and its interface |

Steps 2–5 run in the gmsh worker process. Step 8 is the only step that needs Kratos. Steps 9–10
read files only, so a run from last week, or a run on another machine, can be opened
again.

## Ways in

The command box is the primary interface. Menus, rails and panels build the same command
strings and hand them to the same handlers.

| Entry | What it does | Code |
|---|---|---|
| The GUI | Draw soil, structures, loads, water, phases; mesh; Calculate (F9) | `frontend/js/*`, `patches.js` |
| Command box | `mesh`, `water`, `phases`, `node <id>`, `colour <part>`, `results …`, `results plot …` | each module's `handleCommand` |
| `run <file.py>` | Builds the open model by running a Python file that defines a `Project` (e.g. `run tests/models/excavation.py`) | `core/scripting.py`, `POST /api/project/script` |
| A finished deck | A Kratos deck written elsewhere, shown as its own mesh and run as its own files, from a script that names it (`external_deck.deck_project`) | `core/kratos/external_deck.py`, `frontend/js/deck.js` |
| Import mesh | Read an `.mdpa` back into mesh data | `core/kratos/mdpa_reader.py`, `POST /api/import/mdpa` |
| Export | Write the deck without running it | `POST /api/export/mdpa`, `frontend/js/export.js` |
| `kratos-cli` | The terminal, without the browser or the server: new, edit any field by path, mesh, phases, export, run a deck, results ([CLI.md](../CLI.md)). It edits the project file through `core/session.py`, as the routes do, and runs gmsh in its own process (`gmsh_worker.run_here`) | `cli/`, `kratos-cli.bat`, `kratos-cli.sh` |

## Server modules

`backend/` is the FastAPI server: `main.py` (assembles the app), `middleware.py`
(Host/Origin check, no-cache), `routes/` (one module per API group, below), `store.py`
(the one project), `launcher.py` (portable setup).

`core/` is the engine, in plain Python with no web framework. Each of its five packages
is one stage of the pipeline the data goes through:

| Package | Modules |
|---|---|
| `core/model/` | `schemas.py` (the `Project`), `units.py` (unit systems), `migration.py` (old project files), `templates.py` (blank and starting projects), `phases.py` (phase tree → stages), `wall_translation.py`, `load_translation.py` (section ↔ solid translation) |
| `core/geometry/` | `solid_model.py` (OCC solids), `tessellation.py` (display), `meshing.py` (FE mesh), `cad_import.py` (CAD import), `primitives.py` (geometry recipes) |
| `core/kratos/` | `writer.py` (the deck), `materials.py` (MaterialParameters.json), `parameters.py` (ProjectParameters.json: stages, solver, output), `interfaces.py` (split nodes along walls), `deck_files.py` (the deck's file names), `external_deck.py` (finished decks), `mdpa_reader.py`, `node_parts.py` |
| `core/analysis/` | `calculation.py` (run directory, subprocess, failure reading), `kratos_main.py` (runs inside Kratos' Python) |
| `core/results/` | `catalog.py` (runs registry, file access, cache), `gid_reader.py` (GiD ASCII), `fields.py` (catalogue, units, invariants), `mesh.py` (drawable buffers), `parts.py`, `members.py` (wall and interface curves) |
| `core/` | `scripting.py` (`run <file.py>`), `gmsh_worker.py` (the gmsh process pool) and `session.py` (every edit of a project, and the project file: the HTTP routes and the command line make their edits through it). They send work into several packages, so they stay at the top |

Imports go one way: **model ← geometry ← kratos ← analysis ← results**. A package may import
from its own package or one to its left, never to its right. `tests/test_layout.py`
holds the code to it, with no exceptions. Where a lower package and a higher one need
the same answer, the lower one gives it: the edges a load is applied on are chosen in
`geometry/meshing.py` (`loaded_elements`), and both the mesh preview and the exporter's
load conditions read them from there.

Every `__init__.py` in `core/` is empty. Kratos is started with
`-m core.analysis.kratos_main`, and its interpreter has neither pydantic nor gmsh.

## HTTP API

Each group is one module in `backend/routes/`; what they share (upload limit, the
answer to a refused edit, mesh jobs) is in `backend/routes/common.py`. A route that edits
the project makes the edit through `core/session.py` and only adds the HTTP around it.

| Group | Module | Routes |
|---|---|---|
| Project | `routes/project.py` | `GET/PUT /api/project`, `POST /api/project/new`, `/reset`, `/script`; `PATCH /api/project/layers`, `/materials`, `/structures`, `/phases`, `/dimension`, `/units`; `PUT /api/project/water`; `POST /api/project/phases/defaults` |
| Geometry | `routes/geometry.py` | `GET /api/geometry`, `POST /api/geometry/create`, `/import`, `DELETE /api/geometry/parts/{key}`, `DELETE /api/project/custom_parts` |
| Mesh | `routes/mesh.py` | `POST /api/mesh`, `/api/mesh/labels`, `/api/mesh/node-parts` |
| Decks | `routes/decks.py` | `POST /api/export/mdpa`, `/api/import/mdpa`, `/api/calculate` |
| Results | `routes/results.py` | `GET /api/results/runs`, `/runs/{run}`, `/runs/{run}/files/{name}`, `/runs/{run}/archive` |
| Results per stage | `routes/results.py` | `GET /api/results/runs/{run}/stages/{n}/fields`, `/mesh`, `/field/{name}`, `/displacement`, `/at/{node}`, `/parts` |
| Results per member | `routes/results.py` | `GET /api/results/runs/{run}/members`, `/members/{member}/{quantity}` |
| Health | `main.py` | `GET /api/health` |

## Browser modules

| Role | Modules |
|---|---|
| Shell (frozen) | `frontend/base/js` and `frontend/base/css`, the original mockup's UI, served unchanged at `/js` and `/css`: menus, toolbars, explorer, dialogs, command box |
| Glue | `patches.js` wires the live behaviour into the frozen shell: menu actions, rails, panels, windows |
| Data | `api.js`, `model.js` (server project → shape the shell expects), `buffers.js`, `history.js` (undo/redo) |
| View | `viewport.js` (three.js), `orbit.js` (Y-up camera, replaces the base one), `canvas-renderer.js`, `ruler.js`, `mesh-labels.js`, `part-colors.js`, `node-parts.js` |
| Modelling tools | `draw-input.js`, `beams.js`, `anchors.js`, `interfaces.js`, `loads.js`, `normal-loads.js`, `water-command.js`, `soil-volume-dialog.js`, `material-library.js` |
| Mesh and phases | `mesh-settings.js`, `phases.js` |
| Files | `export.js`, `import-dialog.js`, `mdpa-import-dialog.js`, `download.js`, `zip.js`, `deck.js` |
| Calculate and results | `calculate.js`, `results.js` (the `results …` commands), `results-render.js` (colours, legend, CSV), `results-view.js` (the contour on screen), `results-plot.js` (`results plot …` and its SVG figure) |

## Results mode

```
run directory (~/KratosGUI/runs/<deck>_<stamp>/)
  <deck>.mdpa, ProjectParameters.json           → part names, stage order, output names
  <deck>_<stage>.post.msh / .post.res           → results/gid_reader → results/fields, mesh, parts
  <stage>__output_wall.json, __output_interface → results/members
        │
        ▼  results/catalog.py (finds files, parses once, caches by size + mtime)
  /api/results/... routes
        │
        ▼
  results.js         `results open | phase | field | range | csv …`   (DOM-free, tested)
  results-render.js  colours, bands, legend ticks, CSV                 (DOM-free, tested)
  results-plot.js    `results plot …`, the per-phase SVG figure        (DOM-free, tested)
  results-view.js    contoured mesh and legend in the viewport          (DOM)
  patches.js         Results panel, Choose results window, plot window  (DOM)
```

- **Results are read from what the deck already writes**: GiD ASCII and the JSON output
  processes. There is no second writer. Interface elements are absent from the GiD output,
  so interface tractions come only from the JSON files.
- **Contours.** A field is chosen per phase, with banded or smooth colours, a choice of
  colour maps, deformed mesh, editable legend limits (`results range`), a value-at-node
  probe and CSV export.
- **Plot along the wall.** Bending moment, shear force, normal force, displacements and
  interface tractions against the level y, one panel per phase. It follows Kratos' own
  staged-excavation validation figure, with Kratos' sign convention. The window is modeless and can
  save SVG or CSV.

## Testing

| Suite | How to run | What it covers |
|---|---|---|
| Server | `python -m pytest -q` from the repository root (1273 cases, ~70 s) | Schema, geometry, meshing, export (golden decks), phases, API, results parsing |
| Live Kratos regression | Part of the server suite; skipped where Kratos is not installed | The staged test model (`tests/models/excavation.py`) run through Kratos once per session and checked for invariants any correct run holds: every stage has output, parts and stages agree with the deck, hydrostatic pore pressure, signs, wall curves (`tests/test_results_regression.py`) |
| Headless JS | `python frontend/tests/run_headless.py` (302 cases) | Every DOM-free module: phases, results, results-render, results-plot, part colours, water, node parts, mesh settings, deck |
| JS syntax | `python frontend/tests/syntax_check.py` | Every `frontend/base/js`, `frontend/js` and test file parses. One syntax error silently disables the whole live layer |
| Browser | open `frontend/tests/index.html` | Everything, including DOM, three.js and real events |

No recorded Kratos run is kept in the repository. Without Kratos, the results pipeline
is exercised on synthetic GiD output from `tests/fakes/` (a fake runner and
`gid_writer.py`), built from the same test model.

## Ideas that carry the design

| Idea | Why |
|---|---|
| Gmsh in a 1-worker subprocess | It is a process-global singleton, and the subprocess also contains OCC hard crashes |
| Kratos in a subprocess, configured by path | Its compiled extensions are bound to the Python they were built for, which is usually not the server's |
| Frozen `frontend/base/` + live `frontend/js/` | The server mounts the base files in place. Only the camera in `orbit.js` is replaced; the rest is wrapped by `patches.js` |
| Part keys | One string is the gmsh physical group, `userData.key`, tree `obj:` and `OBJECT_PROPS` key |
| The command line is the feature | Every button builds a command string. One implementation per action, and every model can be scripted (`run <file.py>`) |
| DOM-free logic, thin DOM | Anything decidable without a page goes in a module with no `document`, so the headless runner can test it. `patches.js` and `results-view.js` only host it |
| Runs are directories, results are files | A run never changes after it finishes and is read back from disk, so results survive server restarts and can be zipped and shared |
