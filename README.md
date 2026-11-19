<div align="center">
  <h1>
    <img src="frontend/assets/STYX-wordmark-transparent-dark.png#gh-light-mode-only" alt="Styx" width="400">
    <img src="frontend/assets/STYX-wordmark-transparent-light.png#gh-dark-mode-only" alt="Styx" width="400">
  </h1>

  <p>
    A browser-based geotechnical modeller for the
    <a href="https://github.com/KratosMultiphysics/Kratos">Kratos Multiphysics</a>
    GeoMechanicsApplication.
    <br>
    Build a soil and excavation model, mesh it with Gmsh, run it in construction stages, and
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
    <a href="docs/CLI.md">Command line</a> ·
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
- **Construction stages**: activate and deactivate parts stage by stage, with a K0 initial
  stage.
- **Calculate**: one click writes the deck and runs it through Kratos' multistage
  orchestrator.
- **Results**: contour plots per stage, a deformed mesh, values at a node, plots along the
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
| Backend | [Python](https://www.python.org/) 3.10+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://uvicorn.dev/), [Pydantic](https://pydantic.dev/docs/) |
| Geometry and mesh | [Gmsh](https://gmsh.info/) 4.13 (OpenCASCADE kernel), [NumPy](https://numpy.org/) |
| Frontend | Plain JavaScript and [three.js](https://threejs.org/), with no build step and no npm |
| Solver | [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) GeoMechanicsApplication (installed separately, see [KRATOS_SETUP.md](docs/KRATOS_SETUP.md)) |

The [developer guide](docs/developer/README.md) explains how the pieces fit together.

## Getting started

Do these steps in this order. Each step has its own guide.

1. Install and start Styx. [INSTALLATION.md](docs/INSTALLATION.md) tells you what to install
   on Windows, Linux or macOS. Then you get the code and start Styx with `run.bat` (Windows)
   or `run.sh` (Linux and macOS). Styx opens in your browser, and you can build, mesh and
   export models.
2. Connect Kratos. Kratos is the program that solves the model, and the **Calculate** button
   needs it. `run.bat` and `run.sh` do not install Kratos. [KRATOS_SETUP.md](docs/KRATOS_SETUP.md)
   shows how to install Kratos and how to tell Styx where it is.
3. Use the command line (optional). `kratos-cli` does the same work as the browser app, from
   a new model to its results, in a terminal. [CLI.md](docs/CLI.md) lists every command. The
   [CLI tutorial](docs/cli_tutorials/README.md) builds a first model, a sheet pile in a soil
   block, from the first command to its results.

## Documentation

### For users

| Document | Contents |
|---|---|
| [INSTALLATION.md](docs/INSTALLATION.md) | What to install on each platform, and how to start Styx with `run.bat` or `run.sh` |
| [KRATOS_SETUP.md](docs/KRATOS_SETUP.md) | How to install Kratos, connect it to Styx, and solve common problems |
| [GUI tutorials](docs/gui_tutorials/index.md) | Build a model in the GUI step by step, with a screenshot of each step: the CROW excavation wall, from an empty project to the bending moment in the wall. The documentation site, with these screenshots and all the other pages, is published from `main` on GitHub Pages; CI also attaches it to each run as `docs-site`. |
| [USAGE.md](docs/USAGE.md) | How to use the app, mode by mode: build a model, mesh it, calculate it, read the results, and use scripts |
| [CLI.md](docs/CLI.md) | Every `kratos-cli` command, with examples |
| [cli_tutorials/README.md](docs/cli_tutorials/README.md) | The `kratos-cli` tutorial: a first model, built, run and read in the terminal |
| [CROW_case.md](docs/cli_tutorials/CROW_case.md) | A second `kratos-cli` tutorial: the CROW excavation wall, a staged sheet-pile excavation, in three ways |
| [Muskat_case.md](docs/cli_tutorials/Muskat_case.md) | A groundwater flow tutorial: the Muskat soil column, saturated, with a Van Genuchten soil, and with a seepage face |
| [FEATURES.md](docs/FEATURES.md) | What works, feature by feature, and where the code is |

### For developers

| Document | Contents |
|---|---|
| [Developer guide](docs/developer/README.md) | Start here. What Styx, Gmsh and Kratos each do, from a drawn model to its results |
| [ARCHITECTURE.md](docs/developer/ARCHITECTURE.md) | How a model flows from the browser to Kratos and back, module by module |
| [TESTING.md](docs/developer/TESTING.md) | The test tiers and how to run them |
| [PROJECT_OVERVIEW.md](docs/developer/PROJECT_OVERVIEW.md) | The size of the code, per module |
| [Code map](docs/developer/code-map/GRAPH_REPORT.md) | A generated map of the code and a clickable tree of files and functions |

## Contributing

Contributions are welcome: bug reports, feature requests, documentation fixes and code.
[CONTRIBUTING.md](CONTRIBUTING.md) explains how to set up, how changes are made (tests
first), and what CI checks on every pull request. [TESTING.md](docs/developer/TESTING.md) lists the
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
Deltares. It started on 2026-09-05 in a private repository, `indigocoral/Kratos-GUI`, and was
published here with its commit history: each commit keeps its original author and date.

### Contributors

These people have contributed directly to Styx:

- Aron Noordam
- Gennady Markelov
- Wijtze Pieter Kikstra
- Richard Faasse

To cite Styx, use [CITATION.cff](CITATION.cff), or **Cite this repository** on the GitHub page.

## Acknowledgments

- [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) and its
  GeoMechanicsApplication, the solver behind Calculate
- [Deltares](https://www.deltares.nl/)
- [Gmsh](https://gmsh.info/), for geometry and meshing
- [three.js](https://threejs.org/), for the 3D viewport
- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://pydantic.dev/docs/)
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template), the structure
  of this README
