<div align="center">
  <img src="frontend/assets/logo.png" alt="Styx logo" width="96" height="96">

  <h1>Styx</h1>

  <p>
    A browser-based geotechnical modeller for the
    <a href="https://github.com/KratosMultiphysics/Kratos">Kratos Multiphysics</a>
    GeoMechanicsApplication.
    <br>
    Build a soil and excavation model, mesh it with Gmsh, run it in construction phases, and
    read the results back.
  </p>

  <p>
    <a href="https://github.com/Deltares-research/Styx-Kratos-GUI/actions/workflows/tests.yml"><img src="https://github.com/Deltares-research/Styx-Kratos-GUI/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey" alt="Windows | Linux | macOS">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-to%20be%20decided-lightgrey" alt="License: to be decided"></a>
  </p>

  <p>
    <a href="#getting-started">Getting started</a> ·
    <a href="docs/KRATOS_SETUP.md">Set up Kratos</a> ·
    <a href="docs/USAGE.md">Usage</a> ·
    <a href="https://github.com/Deltares-research/Styx-Kratos-GUI/issues">Report a bug</a> ·
    <a href="https://github.com/Deltares-research/Styx-Kratos-GUI/issues">Request a feature</a>
  </p>
</div>

## About the project

Styx is a single-user modeller for staged geotechnical analyses such as excavations and sheet
pile walls. It runs as a small local web server, and you use it in your browser. The model is
built from real OpenCASCADE solids and meshed with [Gmsh](https://gmsh.info/). The app writes
a Kratos GeoMechanics input deck (`.mdpa`, `MaterialParameters.json` and
`ProjectParameters.json`) and runs it. It then shows the results in a Results mode in the
browser.

### Features

- **Geometry**: soil layers, excavations, sheet pile walls, anchors, struts and interfaces, in
  2D plane strain and 3D.
- **Materials**: Kratos constitutive laws and their parameters, entered directly in SI or kN
  units. A default library covers sand, clay, fill and bedrock.
- **Meshing**: Gmsh, with element size, element order, algorithm and optimisation settings,
  and local refinement.
- **Construction phases**: activate and deactivate parts phase by phase, with a K0 initial
  stage.
- **Calculate**: one click writes the deck and runs it through Kratos' multistage
  orchestrator.
- **Results**: contour plots per phase, a deformed mesh, values at a node, plots along the
  wall (bending moment, shear force, normal force and displacements), and CSV, SVG and ZIP
  export.
- **Scripting**: a command line in the app, plus `run <file.py>` to build a model from a
  Python script.
- **Command line**: `kratos-cli` builds, meshes, stages, exports, runs and reads a model in
  the terminal, without the browser, on the same project file the GUI saves.

See [FEATURES.md](docs/FEATURES.md) for the full list with the status of each feature, and its
**Main gaps** section for what is planned next.

### Built with

| Part | Technology |
|---|---|
| Backend | [Python](https://www.python.org/) 3.10+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [Pydantic](https://docs.pydantic.dev/) |
| Geometry and mesh | [Gmsh](https://gmsh.info/) 4.13 (OpenCASCADE kernel), [NumPy](https://numpy.org/) |
| Frontend | Plain JavaScript and [three.js](https://threejs.org/), with no build step and no npm |
| Solver | [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) GeoMechanicsApplication (installed separately, see [KRATOS_SETUP.md](docs/KRATOS_SETUP.md)) |

[ARCHITECTURE.md](docs/ARCHITECTURE.md) explains how the pieces fit together.

## Getting started

You need **Python 3.10 or newer, 64-bit**, and an internet connection for the first run. On
Linux, a few system libraries for Gmsh are needed too; [INSTALLATION.md](docs/INSTALLATION.md)
lists them for each platform.

```bash
git clone https://github.com/Deltares-research/Styx-Kratos-GUI.git
cd Styx-Kratos-GUI
./run.sh          # Linux and macOS
.\run.bat         # Windows, or double-click run.bat
```

The first start installs the dependencies into a private virtual environment and takes a few
minutes. Then open **<http://127.0.0.1:8000/>** in your browser (on Windows this happens
automatically). Press <kbd>Ctrl</kbd>+<kbd>C</kbd> in the terminal to stop the server.

[INSTALLATION.md](docs/INSTALLATION.md) covers the details: per-platform prerequisites, what
the launcher does, and its `--check`, `--port` and `--host` options.

### Kratos, for Calculate

You can build, mesh and export models without Kratos. To run them with **Calculate**, install
the solver into a Python of its own and point Styx at it with a `kratos.local.json` file in the
repository root:

```json
{
    "python": "C:/Kratos/.venv/Scripts/python.exe"
}
```

[KRATOS_SETUP.md](docs/KRATOS_SETUP.md) walks through installing Kratos (PyPI or a source
build), the configuration options, and troubleshooting.

### The command line

Everything from a new model to its results also works in a terminal, with no browser:

```bash
./kratos-cli.sh new site.json --demo --dim 2     # Windows: kratos-cli.bat
./kratos-cli.sh mesh site.json
./kratos-cli.sh phases site.json defaults
./kratos-cli.sh export site.json --out deck/      # the .mdpa and the two JSON files
./kratos-cli.sh run deck/
./kratos-cli.sh results show 1
./kratos-cli.sh results field 1 uy                # a field's range; --csv FILE for every value
./kratos-cli.sh script site.json --out site.py    # the whole model, as a Python file
./kratos-cli.sh shell site.json                   # or type the commands one after another
```

[CLI.md](docs/CLI.md) lists every command.

## Documentation

| Document | Contents |
|---|---|
| [INSTALLATION.md](docs/INSTALLATION.md) | Prerequisites per platform, the launcher and its options |
| [KRATOS_SETUP.md](docs/KRATOS_SETUP.md) | Installing Kratos and connecting it to Styx, with troubleshooting |
| [USAGE.md](docs/USAGE.md) | A walk through the modes: building, meshing, calculating, results and scripting |
| [CLI.md](docs/CLI.md) | `kratos-cli`: every step of a model in the terminal, command by command |
| [TESTING.md](docs/TESTING.md) | The test tiers and how to run them |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | How a model flows from the browser to Kratos and back |
| [FEATURES.md](docs/FEATURES.md) | What works, feature by feature, and where the code is |
| [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Code size per module |

## Project layout

```text
core/          the engine, one package per stage: model/, geometry/ (Gmsh), kratos/ (the deck), analysis/, results/
backend/       the FastAPI app, the in-memory project store, and the launcher
cli/           kratos-cli, the command line beside the GUI
frontend/      the browser app (index.html, js/, css/, three.js), with its own tests in frontend/tests/
tests/         pytest suites: unit, API, browser, end-to-end, Kratos and performance
benchmarks/    Kratos benchmark cases and runner
tools/test.py  the tier runner
docs/          user guides and design documents
run.bat        launcher for Windows
run.sh         launcher for Linux and macOS
kratos-cli.bat the command line, for Windows
kratos-cli.sh  the command line, for Linux and macOS
```

## Contributing

Contributions are welcome: bug reports, feature requests, documentation fixes and code.
[CONTRIBUTING.md](CONTRIBUTING.md) explains how to set up, how changes are made (tests
first), and what CI checks on every pull request. [TESTING.md](docs/TESTING.md) lists the
test tiers.

To report a security problem, do not open an issue. Follow [SECURITY.md](SECURITY.md)
instead.

## License

The license of Styx is still under consideration and has not been decided yet. Until it is,
no license is granted, as [LICENSE](LICENSE) says: copying, modifying or redistributing Styx
needs permission.

Styx relies on third-party software under its own licenses. Note that Gmsh, which the launcher
installs from PyPI, is licensed under the GNU GPL v2 or later. three.js (bundled in
`frontend/vendor/`) is MIT-licensed, and Kratos Multiphysics, installed separately, is
BSD-licensed.

## Contact

Use [GitHub issues](https://github.com/Deltares-research/Styx-Kratos-GUI/issues) for questions, bug
reports and ideas.

Project link: <https://github.com/Deltares-research/Styx-Kratos-GUI>

## Authors

Styx was designed and developed by **Marjan Fathian** ([@indigocoral](https://github.com/indigocoral)),
Deltares. It started on 2026-09-05 at <https://github.com/indigocoral/Kratos-GUI> and moved to
Deltares-research with its full history: the commits, issues and pull requests from before the
move are all still here.

To cite Styx, use [CITATION.cff](CITATION.cff), or **Cite this repository** on the GitHub page.

## Acknowledgments

- [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) and its
  GeoMechanicsApplication, the solver behind Calculate
- [Deltares](https://www.deltares.nl/)
- [Gmsh](https://gmsh.info/), for geometry and meshing
- [three.js](https://threejs.org/), for the 3D viewport
- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/)
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template), the structure
  of this README
