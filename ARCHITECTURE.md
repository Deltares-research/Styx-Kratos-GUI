# Architecture

Styx is a Deltares/Kratos-branded geotechnical modeller. You build a soil and excavation
model, mesh it with Gmsh, export it as a Kratos GeoMechanics deck, run it in construction
phases, and read the results back in its Results mode. It is a FastAPI server
holding one project, plus a build-free browser front end.

See also: [FEATURES.md](FEATURES.md) (what works, per Kratos feature),
[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) (code size per module),
[README.md](README.md) (install, run, configure Kratos).

## At a glance

### Backend

| Layer | What |
|---|---|
| Framework | FastAPI 0.115.6 + Uvicorn 0.34.0 |
| Validation | Pydantic 2.10.4. `Project` (`server/app/schemas.py`) is the single source of truth |
| Geometry/mesh | Gmsh 4.13.1 (OpenCASCADE kernel) |
| Numerics | NumPy 2.2.1 |
| State | One project in memory (`server/app/store.py`). No database, no auth. Run results live on disk |
| Concurrency | Gmsh in a `ProcessPoolExecutor(max_workers=1)` (`gmsh_worker.py`). Kratos in a subprocess per run (`calculate.py`) |
| Solver | Kratos MultiPhysics GeoMechanicsApplication. Not installed by the launcher; found through `KRATOS_GUI_PYTHON` / `KRATOS_GUI_KRATOS` or `server/kratos.local.json` |
| Tests | pytest 8.3.4 + httpx `TestClient`, 1273 cases. `python -m pytest -q` from `server/`, with an interpreter that has gmsh |

### Frontend

| Layer | What |
|---|---|
| 3D | three.js (vendored), the only dependency |
| Build | **None.** No npm, no bundler, no transpiler |
| Style | ES5 IIFE modules on a global `App` namespace, 44 `<script>` tags in `live/index.html` |
| Fallback renderer | Hand-written CPU painter (`live/js/canvas-renderer.js`) when there is no WebGL |
| HTTP | `fetch` wrapper (`live/js/api.js`) |
| Tests | ~90-line browser harness (`live/tests/index.html`, 36 test files). The DOM-free suites also run headless under quickjs: `python live/tests/run_headless.py`, 302 cases in 9 suites. `python live/tests/syntax_check.py` parses every JS file |

## How a model flows

| Step | Module | Note |
|---|---|---|
| 1. Edit | `schemas.py` | Every PATCH re-validates the *whole* project |
| 2. Build | `build.py` | Boxes → boolean fragment → cut pit → embed structures; 2D sections and 3D solids |
| 3. Draw | `tessellate.py` | OCC `importStl()`, ~0.1 s, for display only (not an FE mesh) |
| 4. Mesh | `meshing.py` | Real tet/tri mesh, re-derived from the geometry each time |
| 5. Split | `interfaces.py` | Duplicate nodes along a wall, zero-thickness contact elements |
| 6. Phase | `phases.py` | The phase tree resolved into the sequence of stages Kratos runs: what is active, water, loads |
| 7. Export | `kratos.py`, `kratos_materials.py`, `kratos_processes.py` | `.mdpa` + `MaterialParameters.json` + `ProjectParameters.json` (one stage per phase, with GiD and JSON output processes) |
| 8. Solve | `calculate.py` → `kratos_runner.py` | Kratos' orchestrator in a subprocess, writing into a run directory of its own (`~/KratosGUI/runs/<deck>_<stamp>/`) |
| 9. Read back | `results.py` → `gid_results.py`, `result_fields.py`, `result_mesh.py`, `result_parts.py` | The run's GiD ASCII (`.post.msh` / `.post.res`) parsed into fields per stage, joined to the deck's parts |
| 10. Members | `result_members.py` | The deck's `<stage>__output_<member>.json` turned into curves along the wall and its interface |

Steps 2–5 run in the gmsh worker process. Step 8 is the only step that needs Kratos. Steps 9–10
read files only, so a run from last week, or a run on another machine, can be opened
again.

## Ways in

The command box is the primary interface. Menus, rails and panels build the same command
strings and hand them to the same handlers.

| Entry | What it does | Code |
|---|---|---|
| The GUI | Draw soil, structures, loads, water, phases; mesh; Calculate (F9) | `live/js/*`, `patches.js` |
| Command box | `mesh`, `water`, `phases`, `node <id>`, `colour <part>`, `results …`, `results plot …` | each module's `handleCommand` |
| `run <file.py>` | Builds the open model by running a Python file that defines a `Project` (e.g. `run app/crow.py`) | `script.py`, `POST /api/project/script` |
| A finished deck | A Kratos deck written elsewhere, shown as its own mesh and run as its own files (e.g. `run app/eemdijk.py`) | `deck.py`, `live/js/deck.js` |
| Import mesh | Read an `.mdpa` back into mesh data | `mdpa_import.py`, `POST /api/import/mdpa` |
| Export | Write the deck without running it | `POST /api/export/mdpa`, `live/js/export.js` |

## Server modules

| Role | Modules |
|---|---|
| App and state | `main.py` (routes), `store.py` (the one project), `seed.py` (starting project), `launcher.py` (portable setup) |
| Model | `schemas.py` (the `Project`), `walls.py`, `loads.py` (section ↔ solid translation), `phases.py` |
| Geometry and mesh | `build.py`, `tessellate.py`, `meshing.py`, `interfaces.py`, `gmsh_worker.py`, `importer.py`, `creator.py` |
| Kratos export | `kratos.py` (deck), `kratos_materials.py`, `kratos_processes.py` (stages, solver, output) |
| Running | `calculate.py` (run directory, subprocess, failure reading), `kratos_runner.py` (runs inside Kratos' Python) |
| Other inputs | `script.py` (`run <file.py>`), `deck.py` (finished decks), `mdpa_import.py`, `node_parts.py` |
| Results | `results.py` (runs registry, file access, cache), `gid_results.py`, `result_fields.py` (catalogue, units, invariants), `result_mesh.py` (drawable buffers), `result_parts.py`, `result_members.py` (wall and interface curves) |
| Example models | `crow.py` (CROW sheet-pile excavation), `eemdijk.py` (Eemdijk dike deck) |

## HTTP API

| Group | Routes |
|---|---|
| Project | `GET/PUT /api/project`, `POST /api/project/new`, `/reset`, `/script`; `PATCH /api/project/layers`, `/materials`, `/structures`, `/phases`, `/dimension`; `PUT /api/project/water`; `POST /api/project/phases/defaults` |
| Geometry | `GET /api/geometry`, `POST /api/geometry/create`, `/import`, `DELETE /api/geometry/parts/{key}`, `DELETE /api/project/custom_parts` |
| Mesh | `POST /api/mesh`, `/api/mesh/labels`, `/api/mesh/node-parts` |
| Decks | `POST /api/export/mdpa`, `/api/import/mdpa`, `/api/calculate` |
| Results | `GET /api/results/runs`, `/runs/{run}`, `/runs/{run}/files/{name}`, `/runs/{run}/archive` |
| Results per stage | `GET /api/results/runs/{run}/stages/{n}/fields`, `/mesh`, `/field/{name}`, `/displacement`, `/at/{node}`, `/parts` |
| Results per member | `GET /api/results/runs/{run}/members`, `/members/{member}/{quantity}` |
| Health | `GET /api/health` |

## Browser modules

| Role | Modules |
|---|---|
| Shell (frozen) | `live/base/js` and `live/base/css`, the original mockup's UI, served unchanged at `/js` and `/css`: menus, toolbars, explorer, dialogs, command box |
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
  <deck>_<stage>.post.msh / .post.res           → gid_results → result_fields / result_mesh / result_parts
  <stage>__output_wall.json, __output_interface → result_members
        │
        ▼  results.py (finds files, parses once, caches by size + mtime)
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
  CROW validation figure, with Kratos' sign convention. The window is modeless and can
  save SVG or CSV.

## Testing

| Suite | How to run | What it covers |
|---|---|---|
| Server | `python -m pytest -q` from `server/` (1273 cases, ~70 s) | Schema, geometry, meshing, export (golden decks), phases, API, results parsing |
| CROW benchmark | Part of the server suite | A real CROW run (`server/tests/fixtures/crow_run/`) held to Kratos' own validated CROW results: wall forces and displacements, and the plotted curves per stage |
| Headless JS | `python live/tests/run_headless.py` (302 cases) | Every DOM-free module: phases, results, results-render, results-plot, part colours, water, node parts, mesh settings, deck |
| JS syntax | `python live/tests/syntax_check.py` | Every `live/base/js`, `live/js` and test file parses. One syntax error silently disables the whole live layer |
| Browser | open `live/tests/index.html` | Everything, including DOM, three.js and real events |

The CROW fixture is generated, never edited: `python tests/make_crow_fixture.py --write`
distils a run directory plus Kratos' validation case. `--members` adds only the member
output and its reference curves.

## Ideas that carry the design

| Idea | Why |
|---|---|
| Gmsh in a 1-worker subprocess | It is a process-global singleton, and the subprocess also contains OCC hard crashes |
| Kratos in a subprocess, configured by path | Its compiled extensions are bound to the Python they were built for, which is usually not the server's |
| Frozen `live/base/` + live `live/js/` | The server mounts the base files in place. Only the camera in `orbit.js` is replaced; the rest is wrapped by `patches.js` |
| Part keys | One string is the gmsh physical group, `userData.key`, tree `obj:` and `OBJECT_PROPS` key |
| The command line is the feature | Every button builds a command string. One implementation per action, and every model can be scripted (`run <file.py>`) |
| DOM-free logic, thin DOM | Anything decidable without a page goes in a module with no `document`, so the headless runner can test it. `patches.js` and `results-view.js` only host it |
| Runs are directories, results are files | A run never changes after it finishes and is read back from disk, so results survive server restarts and can be zipped and shared |
