# Developer guide

This part of the documentation is for people who change Styx: what the pieces are, how a
model becomes a Kratos deck and results, and where each step lives in the code. Read this
page first, then [ARCHITECTURE.md](ARCHITECTURE.md) for the detail.

Using Styx, rather than changing it, is covered by the user guides one folder up:
[INSTALLATION.md](../INSTALLATION.md), [KRATOS_SETUP.md](../KRATOS_SETUP.md),
[USAGE.md](../USAGE.md), [CLI.md](../CLI.md) and [FEATURES.md](../FEATURES.md).

## The developer documents

| Document | Contents |
|---|---|
| This page | The big picture: who does what, from a drawn model to results |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The modules, the HTTP API, the browser modules and Results mode, step by step |
| [TESTING.md](TESTING.md) | The test tiers and how to run them |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Code size per module |
| [code-map/](code-map/GRAPH_REPORT.md) | A generated map of the code: the central classes, what belongs together, a clickable tree of files and functions |
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | Setting up, test-first changes, and the checks CI runs |

## The big picture

Styx is a geotechnical modeller. You describe the soil, the pit, the walls and the
construction phases. **Gmsh** turns that into solids and a finite-element mesh. **Styx**
writes the mesh, materials and phases as a Kratos GeoMechanics deck. **Kratos** solves it
stage by stage, and Styx reads the results back for contours and wall plots.

![Swimlane diagram: the model flows from you to the Styx project, into Gmsh for solids and mesh, back to Styx to split interfaces, stage phases and write the deck, into Kratos to solve, and back to Styx to read the results](pipeline.svg)

Each lane is who does the work. Gmsh appears twice: once to build the solids (also
tessellated for the 3D view, dashed) and once to mesh them. Everything between the mesh and
Kratos, and everything after Kratos, is Styx's own Python. The diagram is
[pipeline.svg](pipeline.svg); edit it as text.

## Who does what

| | Styx | Gmsh | Kratos |
|---|---|---|---|
| Role | The model and every translation | Geometry and mesh | The solver |
| Does | Holds the project as one validated `Project`, and every edit re-checks the whole model. Resolves the phase tree into stages. Splits the mesh along walls and writes interface elements. Writes the deck, starts Kratos, reads the results | Builds real solids with the OpenCASCADE kernel: boxes, booleans, the pit cut out. Embeds walls, piles and anchors so the mesh follows them. Generates the finite-element mesh with the sizes and refinements asked for | GeoMechanicsApplication, run by its own orchestrator over the deck's stages. Coupled soil and water (UPw elements), K0 initial stresses, staged activation. Writes GiD results and JSON curves for walls and interfaces |
| Runs in | The server's or the CLI's Python | A dedicated worker process | A separate Python, the one Kratos was built for |

## What Gmsh contributes

Gmsh is used for three separate jobs. All three run in a dedicated worker process
([core/gmsh_worker.py](../../core/gmsh_worker.py)), because Gmsh keeps one global model per
process and an OpenCASCADE crash on a thin solid must not take the app down.

1. **Build the solids** ([core/geometry/solid_model.py](../../core/geometry/solid_model.py)).
   Soil layers become boxes, which are fragmented against each other so neighbours share
   faces. The excavation lifts are cut out, load footprints imprinted, and walls and anchors
   embedded. Every body is tagged with its part key, which later becomes its name in the deck.
2. **Draw them** ([core/geometry/tessellation.py](../../core/geometry/tessellation.py)). A
   fast surface triangulation, about a tenth of a second, sent to the browser's 3D view. It
   is for display only and is never used for analysis.
3. **Mesh them** ([core/geometry/meshing.py](../../core/geometry/meshing.py)). The real
   mesh: triangles in a 2D plane-strain section, tetrahedra in 3D, linear or quadratic. Size
   per body and per wall, box and cylinder refinement zones, a choice of algorithm, optional
   Netgen optimisation.

### Where Gmsh stops

Gmsh produces a conformal mesh: soil and wall share every node. The Kratos-specific work is
Styx's:

- Along a wall that has an interface, it duplicates the nodes and writes zero-thickness
  contact elements across the gap
  ([core/kratos/interfaces.py](../../core/kratos/interfaces.py)).
- It reorders Gmsh's quadratic tetrahedron nodes to Kratos' convention, and maps a 2D
  section onto Kratos' X/Y plane ([core/kratos/writer.py](../../core/kratos/writer.py)).

## What makes the deck

Export meshes the project and writes a deck directory. Kratos is started on
`ProjectParameters.json`.

| File | Holds | Built from |
|---|---|---|
| `<deck>.mdpa` | One node table, one element block per soil body and structure, load conditions, and a SubModelPart per part | The Gmsh mesh, the interface split and the part keys (`kratos/writer.py`, `kratos/interfaces.py`) |
| `MaterialParameters.json` | A constitutive law and Kratos variables per material: soil, beams, anchors, interfaces | The project's property sets as they stand, plus derived values the user left out (K0 from Jaky, permeabilities, interface strength from its soil). 2D piles are spread over their spacing (`kratos/materials.py`) |
| `ProjectParameters.json` | One stage per phase: what is active, water, constraints, loads, solver settings, output processes | The phase tree, linearised into stages with Activate/Deactivate steps. The solver block is a documented default analysis (`model/phases.py`, `kratos/parameters.py`) |
| `initial_materials.json` | The materials plus the K0 variables | Written only when the first stage runs the K0 procedure (`kratos/deck_files.py`) |

Module paths are relative to `core/`.

## Run and read back

Kratos runs in a separate Python, the one it was compiled for, which is usually not the
server's. The machine says where it is through `kratos.local.json` or the
`KRATOS_GUI_PYTHON` and `KRATOS_GUI_KRATOS` variables
([core/analysis/calculation.py](../../core/analysis/calculation.py)).

Each run gets its own directory under `~/KratosGUI/runs/<deck>_<stamp>/` with the deck, the
log and everything Kratos wrote. Nothing is overwritten. Styx parses the GiD files
(`.post.msh`, `.post.res`) into fields per stage, and the JSON outputs into curves along each
wall ([core/results/](../../core/results/)). Because results are just files, an old run, or
one from another machine, opens the same way.

## Two ways in, one engine

The browser app and the terminal make the same edits through one module,
[core/session.py](../../core/session.py), and save the same project file. A model can move
between them at any point.

| | GUI | `kratos-cli` |
|---|---|---|
| Runs as | A FastAPI server holding one project, plus a browser app with no build step | A terminal command, or `kratos-cli shell` for many commands in one process |
| Edits through | HTTP routes in `backend/routes/` → `core/session.py` | Command modules in `cli/commands/` → `core/session.py` |
| Gmsh | In the one-worker process pool | In its own process (`gmsh_worker.run_here`) |
| Typical path | Draw, Generate mesh, set phases, Calculate (F9), Results mode | `new`, `layer` / `beam` / `water`, `mesh`, `phases defaults`, `calculate`, `results field` |
| Results | Contours on the mesh, value at a node, plots along the wall | Tables and CSV per stage, coloured terminal output |

## Where it lives in the code

The engine in `core/` is five packages, one per stage of the pipeline, in the order the data
moves through them:

| Package | What |
|---|---|
| `core/model/` | The `Project` schema, units, phases |
| `core/geometry/` | Gmsh solids, the display view, the FE mesh |
| `core/kratos/` | Interfaces and the deck files |
| `core/analysis/` | The run directory and the Kratos subprocess |
| `core/results/` | GiD and JSON readers, fields, wall curves |

Imports go one way: **model ← geometry ← kratos ← analysis ← results**. A package may import
only from itself or a package to its left, and `tests/test_layout.py` enforces it.
`session.py`, `gmsh_worker.py` and `scripting.py` sit above all five because they hand work
to several of them. Beside `core/` are the two front ends, `backend/` (the server) and `cli/`
(the command line), and `frontend/` (the browser app).

The folders and files at the top of the repository:

```text
core/          the engine, one package per stage: model/, geometry/ (Gmsh), kratos/ (the deck), analysis/, results/
backend/       the FastAPI app, the in-memory project store, and the launcher
cli/           kratos-cli, the command line beside the GUI, and the tutorial's helper scripts
               (kratos-shell.bat/.sh, kratos-init-powershell.bat)
examples/      ready-made models for kratos-cli, one folder per model
frontend/      the browser app (index.html, js/, css/, three.js), with its own tests in frontend/tests/
tests/         pytest suites: unit, API, browser, end-to-end, Kratos and performance
benchmarks/    Kratos benchmark cases and the script that runs them
tools/test.py  runs the test tiers (see TESTING.md)
docs/          user guides; docs/cli_tutorials/ for the command-line tutorials, docs/developer/
               for the developer guide and design documents
run.bat        launcher for Windows
run.sh         launcher for Linux and macOS
kratos-cli.bat the command line, for Windows
kratos-cli.sh  the command line, for Linux and macOS
```

## The code map

[code-map/](code-map/) is a map of the code and its tests made by
[graphify](https://github.com/safishamsi/graphify). It parses the source and records which
file defines, imports and calls what, then groups the code that belongs together.
Benchmarks, CI settings and the vendored three.js are left out
([.graphifyignore](../../.graphifyignore)).

| File | How to read it |
|---|---|
| [GRAPH_TREE.html](code-map/GRAPH_TREE.html) | The place to start. A tree of the repository: click a folder to open it, a file to see its classes and functions. Each node shows how many items sit under it |
| [GRAPH_REPORT.md](code-map/GRAPH_REPORT.md) | On GitHub, or in any editor. The most connected classes and functions, the groups of code that belong together (each named after its central file or symbol), and where the documents point into the code |

Open `GRAPH_TREE.html` in a browser from your clone; GitHub does not show it. It loads its
drawing library from d3js.org, so it needs internet.

Read it with two cautions. Edges marked `INFERRED` are matched by name, not proven, so check
one in the code before relying on it. The report's "Suggested Questions" are generated from
the graph's shape: starting points for reading, not review findings.

The map is a snapshot: the report's "Graph Freshness" line names the commit it was built
from. To rebuild it, from the repository root:

```bash
# Windows
.venv-windows\Scripts\python.exe -m pip install graphifyy
.venv-windows\Scripts\graphify.exe update .
.venv-windows\Scripts\graphify.exe tree --root . --label Styx-Kratos-GUI --output docs/developer/code-map/GRAPH_TREE.html
# Linux (use .venv-macos on macOS)
.venv-linux/bin/python -m pip install graphifyy
.venv-linux/bin/graphify update .
.venv-linux/bin/graphify tree --root . --label Styx-Kratos-GUI --output docs/developer/code-map/GRAPH_TREE.html
```

This needs no AI assistant or API key and takes a few seconds. `update` writes to
`graphify-out/`, which is not committed; copy `GRAPH_REPORT.md` from there into
`docs/developer/code-map/`. `tree` writes its page straight into the folder.
`graphify-out/graph.json` answers questions in the terminal too:
`graphify explain "Project"` lists everything connected to `Project`, and
`graphify path "A" "B"` the shortest path between two names.
