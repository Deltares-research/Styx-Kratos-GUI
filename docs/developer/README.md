# Developer guide

This guide is for developers who change Styx. It explains what the parts of Styx do, how a
model becomes a Kratos deck and then results, and where each step is in the code. Read
this page first, then [ARCHITECTURE.md](ARCHITECTURE.md) for the details.

To use Styx, see the user guides: [INSTALLATION.md](../INSTALLATION.md),
[KRATOS_SETUP.md](../KRATOS_SETUP.md), [USAGE.md](../USAGE.md), [CLI.md](../CLI.md) and
[FEATURES.md](../FEATURES.md).

## The developer documents

| Document | Contents |
|---|---|
| This page | The big picture: who does what, from a drawn model to its results |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The libraries, the modules, the HTTP API, the browser modules and Results mode |
| [TESTING.md](TESTING.md) | How to run the tests, and what CI runs |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | The size of the code in each module |
| [code-map/](code-map/GRAPH_REPORT.md) | A generated map of the code: the central classes, the groups of code that belong together, and a tree of files and functions that you can click |
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | How to set up, how to make a change (test first), and the checks of CI |

## The big picture

Styx is a geotechnical modeller. You describe the soil, the pit, the walls and the
construction stages. Three programs then do the work:

1. **Gmsh** makes solids and a finite-element mesh from the model.
2. **Styx** writes the mesh, the materials and the stages as a Kratos GeoMechanics deck: a
   set of input files for Kratos.
3. **Kratos** calculates the deck stage by stage. Styx then reads the results for the
   contours and the plots along the wall.

![Swimlane diagram: the model goes from you to the Styx project, to Gmsh for the solids and the mesh, back to Styx to split the interfaces, make the stages and write the deck, to Kratos for the calculation, and back to Styx to read the results](pipeline.svg)

Each lane of the diagram is the program that does the work. Gmsh is in the diagram two
times: first to build the solids (and a surface view for the 3D display, dashed), then to
make the mesh. All work between the mesh and Kratos, and all work after Kratos, is Python
code of Styx. [pipeline.svg](pipeline.svg) is a text file that you can edit.

## Who does what

| | Styx | Gmsh | Kratos |
|---|---|---|---|
| Role | The model and each translation | Geometry and mesh | The solver |
| Work | Keeps the project as one checked `Project`, and checks the full model again at each edit. Makes the stage tree into Kratos stages. Splits the mesh along walls and writes interface elements. Writes the deck, starts Kratos, reads the results. | Builds solids with the OpenCASCADE kernel: boxes, boolean operations, the pit cut out. Embeds walls, piles and anchors, so that the mesh follows them. Makes the finite-element mesh with the sizes and refinements that the model asks for. | GeoMechanicsApplication, run by its own orchestrator over the stages of the deck. Coupled soil and water (U-Pw elements), K0 initial stresses, parts switched on and off in stages. Writes GiD results and JSON curves for walls and interfaces. |
| Runs in | The Python of the server or of `kratos-cli` | A separate worker process | A separate Python: the one that Kratos was built for |

## What Gmsh does

Gmsh does three separate jobs. All three run in a separate worker process
([core/gmsh_worker.py](../../core/gmsh_worker.py)), because Gmsh keeps one global model in
each process, and an OpenCASCADE crash on a thin solid must not stop the app.

1. **Build the solids** ([core/geometry/solid_model.py](../../core/geometry/solid_model.py)).
   Soil layers become boxes. Gmsh fragments the boxes against each other, so that
   neighbours share their faces. Then it cuts out the excavation lifts, imprints the load
   areas, and embeds the walls and anchors. Each body gets its part key, which later
   becomes its name in the deck.
2. **Draw them** ([core/geometry/tessellation.py](../../core/geometry/tessellation.py)). A
   fast surface triangulation (about 0.1 s) for the 3D view in the browser. It is for the
   display only, never for the analysis.
3. **Mesh them** ([core/geometry/meshing.py](../../core/geometry/meshing.py)). The real
   mesh: triangles in a 2D plane-strain section, tetrahedra in 3D, linear or quadratic.
   A size for each body and each wall, box and cylinder refinement zones, a choice of
   algorithm, and optional Netgen optimisation.

### Where Gmsh stops

Gmsh makes a conformal mesh: the soil and the wall share each node. Styx does the work that
is special to Kratos:

- Along a wall with an interface, Styx duplicates the nodes and writes zero-thickness
  contact elements across the gap
  ([core/kratos/interfaces.py](../../core/kratos/interfaces.py)).
- Styx puts the nodes of a quadratic tetrahedron in the Kratos order, and maps a 2D
  section onto the X-Y plane of Kratos
  ([core/kratos/writer.py](../../core/kratos/writer.py)).

## What is in the deck

The export makes the mesh and writes a deck folder. Kratos starts with
`ProjectParameters.json`. Module paths are relative to `core/`.

| File | Contents | Made from |
|---|---|---|
| `<deck>.mdpa` | One node table, one element block for each soil body and structure, load conditions, and a SubModelPart for each part | The Gmsh mesh, the interface split and the part keys (`kratos/writer.py`, `kratos/interfaces.py`) |
| `MaterialParameters.json` | A constitutive law and its Kratos variables for each material: soil, beams, anchors, interfaces | The property sets of the project as they are, plus the values that the user did not give and that Styx can calculate (K0 from Jaky, permeabilities, interface strength from its soil). In 2D, piles are spread over their spacing (`kratos/materials.py`). |
| `ProjectParameters.json` | One Kratos stage for each stage: what is active, water, constraints, loads, solver settings, output processes | The stage tree, made into a list of Kratos stages with Activate and Deactivate steps. The solver block is a fixed default analysis (`model/stages.py`, `kratos/parameters.py`). |
| `initial_materials.json` | The materials, plus the K0 variables | Written only when the first stage runs the K0 procedure (`kratos/deck_files.py`) |
| `kratos_gui_units.json` | The unit system, for the labels of the results. Kratos does not read it. | The project (`kratos/deck_files.py`) |

## Run Kratos and read the results

Kratos runs in a separate Python, the one that it was compiled for. This is usually not the
Python of the server. Each computer tells Styx where it is, with `kratos.local.json` or the
variables `KRATOS_GUI_PYTHON` and `KRATOS_GUI_KRATOS`
([core/analysis/calculation.py](../../core/analysis/calculation.py)).

Each run gets its own folder, `~/KratosGUI/runs/<deck>_<time>/`, with the deck, the log
and all files that Kratos wrote. Styx never overwrites a run. It reads the GiD files
(`.post.msh`, `.post.res`) into fields for each stage, and the JSON output into curves along
each wall ([core/results/](../../core/results/)). The results are only files, so an old run,
or a run from a different computer, opens in the same way.

## Two front ends, one engine

The browser app and the terminal make the same edits through one module,
[core/session.py](../../core/session.py), and save the same project file. So a model can
go from one to the other at any time.

| | GUI | `kratos-cli` |
|---|---|---|
| Runs as | A FastAPI server with one project, and a browser app with no build step | A terminal command, or `kratos-cli shell` for many commands in one process |
| Edits through | HTTP routes in `backend/routes/` → `core/session.py` | Command modules in `cli/commands/` → `core/session.py` |
| Gmsh | In the process pool with one worker | In its own process (`gmsh_worker.run_here`) |
| Typical steps | Draw, generate the mesh, set the stages, Calculate (F9), Results mode | `new`, `layer` / `beam` / `water`, `mesh`, `stages`, `calculate`, `results field` |
| Results | Contours on the mesh, values at a node, plots along the wall | Tables and CSV files for each stage, in colour in the terminal |

## Where the code is

The engine in `core/` has five packages, one for each step of the pipeline, in the order
that the data goes through them:

| Package | Contents |
|---|---|
| `core/model/` | The `Project` schema, units, stages |
| `core/geometry/` | Gmsh solids, the view, the finite-element mesh |
| `core/kratos/` | Interfaces and the files of the deck |
| `core/analysis/` | The run folder and the Kratos subprocess |
| `core/results/` | GiD and JSON readers, fields, curves along walls |

Imports go in one direction: **model ← geometry ← kratos ← analysis ← results**. A package
can import only from itself or from a package to its left, and `tests/test_layout.py`
checks this. `session.py`, `gmsh_worker.py` and `scripting.py` are above all five, because
they give work to several of them. Next to `core/` are the two front ends, `backend/` (the
server) and `cli/` (the command line), and `frontend/` (the browser app).

The folders and files at the top of the repository:

```text
core/          the engine, one package for each step: model/, geometry/ (Gmsh), kratos/ (the deck), analysis/, results/
backend/       the FastAPI app, the project in memory, and the launcher
cli/           kratos-cli, the command line, and the helper scripts of the tutorials
               (kratos-shell.bat/.sh, kratos-init-powershell.bat)
examples/      ready-made models for kratos-cli, one folder for each model
frontend/      the browser app (index.html, js/, css/, three.js), with its tests in frontend/tests/
tests/         pytest tests: unit, API, browser, end-to-end, Kratos and performance
benchmarks/    the Kratos benchmark cases and the script that runs them
tools/test.py  runs the test tiers (see TESTING.md)
docs/          the user guides; docs/cli_tutorials/ for the kratos-cli tutorials,
               docs/developer/ for this guide
run.bat        the launcher for Windows
run.sh         the launcher for Linux and macOS
kratos-cli.bat the command line for Windows
kratos-cli.sh  the command line for Linux and macOS
```

The `examples/` folder is only for people to read and run. No code or test may use it, and
`tests/test_no_examples.py` checks this.

## The code map

[code-map/](code-map/) is a map of the code and its tests, made by
[graphify](https://github.com/safishamsi/graphify). Graphify reads the source, records which
file defines, imports and calls what, and then groups the code that belongs together. The
benchmarks, the CI settings and the vendored three.js are not in the map
([.graphifyignore](../../.graphifyignore)).

| File | How to read it |
|---|---|
| [GRAPH_TREE.html](code-map/GRAPH_TREE.html) | Start here. A tree of the repository: click a folder to open it, and a file to see its classes and functions. Each node shows how many items are below it. |
| [GRAPH_REPORT.md](code-map/GRAPH_REPORT.md) | On GitHub or in an editor. The classes and functions with the most connections, the groups of code that belong together (each with the name of its central file or symbol), and where the documents point into the code. |

GitHub does not show `GRAPH_TREE.html`. Open it in a browser from your clone. It loads its
drawing library from d3js.org, so it needs an internet connection.

> [!NOTE]
> Edges marked `INFERRED` are matched by name and can be wrong. Check one in the code
> before you rely on it. The "Suggested Questions" of the report come from the shape of the
> graph: they are places to start to read, not review findings.

The map is a snapshot. The "Graph Freshness" line of the report gives the commit that it was
made from.

### Rebuild the code map

1. In the repository folder, install graphify into the virtual environment of Styx:

   ```bash
   .venv-windows\Scripts\python.exe -m pip install graphifyy    # Windows
   .venv-linux/bin/python -m pip install graphifyy              # Linux (.venv-macos on macOS)
   ```

2. Update the graph. It writes into `graphify-out/`, which is not committed:

   ```bash
   .venv-windows\Scripts\graphify.exe update .                  # Windows
   .venv-linux/bin/graphify update .                            # Linux
   ```

3. Copy `graphify-out/GRAPH_REPORT.md` into `docs/developer/code-map/`.
4. Write the tree page directly into the folder:

   ```bash
   .venv-windows\Scripts\graphify.exe tree --root . --label Styx-Kratos-GUI --output docs/developer/code-map/GRAPH_TREE.html
   ```

   On Linux, use `.venv-linux/bin/graphify` in the same command.

This takes a few seconds and needs no API key. `graphify-out/graph.json` also answers
questions in the terminal: `graphify explain "Project"` lists all items connected to
`Project`, and `graphify path "A" "B"` gives the shortest path between two names.
