<a id="readme-top"></a>

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
    <a href="https://github.com/Deltares-research/Kratos-GUI/actions/workflows/tests.yml"><img src="https://github.com/Deltares-research/Kratos-GUI/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey" alt="Windows | Linux | macOS">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green" alt="License: Apache-2.0"></a>
  </p>

  <p>
    <a href="#getting-started">Getting started</a> ·
    <a href="#setting-up-kratos-for-calculate">Set up Kratos</a> ·
    <a href="#usage">Usage</a> ·
    <a href="https://github.com/Deltares-research/Kratos-GUI/issues">Report a bug</a> ·
    <a href="https://github.com/Deltares-research/Kratos-GUI/issues">Request a feature</a>
  </p>
</div>

<details>
  <summary>Table of contents</summary>

1. [About the project](#about-the-project)
   - [Features](#features)
   - [Built with](#built-with)
2. [Getting started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Get the code](#get-the-code)
   - [Run the app](#run-the-app)
   - [Launcher options](#launcher-options)
3. [Setting up Kratos (for Calculate)](#setting-up-kratos-for-calculate)
   - [Step 1: Install Kratos](#step-1-install-kratos)
   - [Step 2: Tell Styx where Kratos is](#step-2-tell-styx-where-kratos-is)
   - [Step 3: Check it works](#step-3-check-it-works)
   - [Troubleshooting](#troubleshooting)
4. [Usage](#usage)
5. [Running the tests](#running-the-tests)
6. [Project layout](#project-layout)
7. [Contributing](#contributing)
8. [License](#license)
9. [Contact](#contact)
10. [Acknowledgments](#acknowledgments)

</details>

## About the project

Styx is a single-user modeller for staged geotechnical analyses such as excavations and sheet
pile walls. It runs as a small local web server, and you use it in your browser. The model is
built from real OpenCASCADE solids and meshed with [Gmsh](https://gmsh.info/). The app writes
a Kratos GeoMechanics input deck (`.mdpa`, `MaterialParameters.json` and
`ProjectParameters.json`) and runs it. It then shows the results in a Results mode similar to
Plaxis.

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

See [FEATURES.md](FEATURES.md) for the full list with the status of each feature, and its
**Main gaps** section for what is planned next.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built with

| Part | Technology |
|---|---|
| Backend | [Python](https://www.python.org/) 3.10+, [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [Pydantic](https://docs.pydantic.dev/) |
| Geometry and mesh | [Gmsh](https://gmsh.info/) 4.13 (OpenCASCADE kernel), [NumPy](https://numpy.org/) |
| Frontend | Plain JavaScript and [three.js](https://threejs.org/), with no build step and no npm |
| Solver | [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) GeoMechanicsApplication (installed separately, see [below](#setting-up-kratos-for-calculate)) |

[ARCHITECTURE.md](ARCHITECTURE.md) explains how the pieces fit together.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting started

The launcher installs everything the modeller needs into a private virtual environment the
first time it runs. You only need Python and an internet connection. Kratos, the solver, is a
separate install. You only need it for **Calculate**: you can build, mesh and export models
without it.

### Prerequisites

You need **Python 3.10 or newer, 64-bit**, and an internet connection for the first run.

<details open>
<summary><b>Windows 10/11</b></summary>

1. Install Python from [python.org](https://www.python.org/downloads/windows/), or run
   `winget install Python.Python.3.12`. The python.org installer also installs the `py`
   launcher, which `run.bat` uses.
2. Optional: install [Git](https://git-scm.com/download/win) to clone the repository.

</details>

<details open>
<summary><b>Linux (Ubuntu/Debian, Fedora, and others)</b></summary>

Python, the `venv` module, and the system libraries the Gmsh wheel loads:

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install python3 python3-venv git \
    libglu1-mesa libxcursor1 libxinerama1 libxft2 libxrender1

# Fedora
sudo dnf install python3 git mesa-libGLU libXcursor libXinerama libXft libXrender
```

Check that `python3 --version` prints 3.10 or newer.

</details>

<details open>
<summary><b>macOS</b></summary>

The `python3` that comes with the Xcode command line tools is often too old. Install a
current one from [python.org](https://www.python.org/downloads/macos/), or with Homebrew:

```bash
brew install python@3.12 git
```

Check that `python3 --version` prints 3.10 or newer.

</details>

### Get the code

```bash
git clone https://github.com/Deltares-research/Kratos-GUI.git
cd Kratos-GUI
```

You can also download the ZIP from GitHub and unpack it.

### Run the app

The first start takes a few minutes while the dependencies are installed. Later starts take a
few seconds.

**Windows**: double-click `run.bat` in the repository folder, or run it from a terminal:

```powershell
.\run.bat
```

**Linux and macOS**:

```bash
./run.sh
```

If you get `Permission denied` (this can happen after unpacking a ZIP), run `bash run.sh`
instead.

Then open **<http://127.0.0.1:8000/>** in your browser. On Windows this happens
automatically. Leave the terminal window open while you work, and press <kbd>Ctrl</kbd>+<kbd>C</kbd>
in it to stop the server.

What the launcher does:

1. It creates a virtual environment in the repository folder. Each operating system gets its
   own: `.venv-windows`, `.venv-linux` or `.venv-macos`. This means one checkout can be shared
   between systems, for example through WSL or a network drive.
2. It installs the pinned packages from [requirements.txt](requirements.txt), and installs
   them again whenever that file changes.
3. It starts the server on port 8000.

To update, run `git pull` and start the launcher again.

### Launcher options

Pass these to `run.bat` or `run.sh` in the same way:

| Option | What it does |
|---|---|
| `--check` | Installs and checks the dependencies, then exits without starting the server. Use it to test a new machine. |
| `--port 8080` | Uses a different port, if 8000 is already in use. |
| `--host <name>` | Binds to another address. The default is `127.0.0.1`, which only this computer can reach. |

> [!WARNING]
> Styx has no login, and its `run <file.py>` command runs Python code with your user's
> permissions. Keep the default `127.0.0.1` unless you trust everyone on the network. If you
> do bind to another address, list the host names the server may answer to in
> `KRATOS_GUI_ALLOWED_HOSTS`, separated by commas.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Setting up Kratos (for Calculate)

**Calculate** needs [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) with
its **GeoMechanicsApplication**. The launcher does not install it. This is deliberate: Kratos'
compiled modules only load in the exact Python version they were built for, and that is often
not the Python that runs the server. So Styx runs every calculation as a separate process,
using a Python interpreter that you choose.

Setup has three steps: install Kratos, tell Styx which Python has it, and check that it works.

### Step 1: Install Kratos

#### Option A: Install from PyPI (Windows and Linux, recommended)

Kratos publishes ready-made packages for 64-bit Windows and Linux (glibc 2.28 or newer, for
example Ubuntu 20.04+ or RHEL 8+). Installing `KratosGeoMechanicsApplication` also installs
`KratosMultiphysics`, `KratosStructuralMechanicsApplication` and
`KratosLinearSolversApplication`, which it depends on.

Install it into a virtual environment of its own, kept apart from the app's:

**Windows (PowerShell)**

```powershell
py -3.12 -m venv C:\Kratos\.venv
C:\Kratos\.venv\Scripts\python.exe -m pip install --upgrade pip
C:\Kratos\.venv\Scripts\python.exe -m pip install KratosGeoMechanicsApplication
```

**Linux**

```bash
python3 -m venv ~/kratos/.venv
~/kratos/.venv/bin/python -m pip install --upgrade pip
~/kratos/.venv/bin/python -m pip install KratosGeoMechanicsApplication
```

Any Python from 3.10 to 3.14 works for this environment. Version 10.4.4 was the latest
release when this was written. Pin it (`KratosGeoMechanicsApplication==10.4.4`) if you want
every machine to run the same solver.

#### Option B: Build from source (macOS, or a development build)

There are no PyPI packages for macOS. On macOS, or if you need an unreleased Kratos version,
build Kratos yourself. Follow the official
[Kratos installation guide](https://github.com/KratosMultiphysics/Kratos/blob/master/INSTALL.md),
and enable these three applications in your configure script (`standard_configure.bat`,
`standard_configure.sh` or `standard_configure_mac.sh`):

```bash
add_app ${KRATOS_APP_DIR}/LinearSolversApplication
add_app ${KRATOS_APP_DIR}/StructuralMechanicsApplication
add_app ${KRATOS_APP_DIR}/GeoMechanicsApplication
```

The build puts its output in `<kratos>/bin/Release`, which contains a `KratosMultiphysics/`
folder and a `libs/` folder. You will need two things in step 2: that folder, and the exact
Python interpreter you built against.

> [!NOTE]
> The maintainers have not tested Kratos source builds on macOS. If you get it working,
> please share your steps in an issue.

### Step 2: Tell Styx where Kratos is

Create a file called **`kratos.local.json`** in the repository root, next to `run.bat`. The
file belongs to this one machine, so Git ignores it.

| Key | Value |
|---|---|
| `python` | **Required.** The full path to the Python interpreter that has Kratos: the venv's Python for option A, or the Python you built against for option B. |
| `kratos` | **Option B only.** The build folder that contains `KratosMultiphysics/` and `libs/`, usually `<kratos>/bin/Release`. Leave it out if that Python can already import Kratos on its own, as it can after a pip install. |

Use forward slashes in the paths, even on Windows. If you use backslashes, write each one twice
(`\\`). JSON does not expand `~`, so write the full home folder path.

**Windows, PyPI install**

```json
{
    "python": "C:/Kratos/.venv/Scripts/python.exe"
}
```

**Linux, PyPI install**

```json
{
    "python": "/home/<you>/kratos/.venv/bin/python"
}
```

**Source build (any OS)**

```json
{
    "python": "C:/Kratos/.venv/Scripts/python.exe",
    "kratos": "C:/Kratos/bin/Release"
}
```

To find the exact interpreter path, activate that environment and run
`python -c "import sys; print(sys.executable)"`.

Styx reads the file again on every run, so you do not need to restart the server after editing
it. Just press **Calculate** again.

<details>
<summary>Prefer environment variables? (for CI, or shells you start yourself)</summary>

An environment variable takes precedence over the same setting in `kratos.local.json`.
Remember that double-clicking `run.bat` starts a fresh shell that does not see variables you
set in another terminal. That is why the file is usually the easier option.

| Variable | What | Default |
|---|---|---|
| `KRATOS_GUI_PYTHON` | Same as `python` above. | The server's own interpreter |
| `KRATOS_GUI_KRATOS` | Same as `kratos` above. | Not set |
| `KRATOS_GUI_RUNS` | The folder where run folders are created. | `~/KratosGUI/runs` |
| `KRATOS_GUI_TIMEOUT` | Seconds before a run is stopped. | `3600` |

```powershell
# Windows (PowerShell), then start .\run.bat from the same window
$env:KRATOS_GUI_PYTHON = "C:\Kratos\.venv\Scripts\python.exe"
```

```bash
# Linux / macOS, then ./run.sh from the same shell
export KRATOS_GUI_PYTHON="$HOME/kratos/.venv/bin/python"
```

</details>

### Step 3: Check it works

1. Check that the interpreter can load Kratos on its own:

   ```bash
   <your kratos python> -c "import KratosMultiphysics.GeoMechanicsApplication; print('Kratos OK')"
   ```

   For option B, add the build folder to `PYTHONPATH` first, as described in the Kratos
   installation guide.
2. Start Styx, build or open a model, and press **Calculate**. The command log shows each
   stage as it runs. At the end it says whether the run succeeded and where the files are, and
   the app switches to **Results**.

### Troubleshooting

| The command log says | What to do |
|---|---|
| *Kratos was not found by the interpreter that ran the deck* | `python` is missing or points to a Python without Kratos. Check `kratos.local.json` and repeat step 3.1. |
| *Kratos was found but could not be loaded* | The Python version does not match the build. A build's `libs/` folder holds a file named like `Kratos.cp311-win_amd64.pyd`, and `cp311` means Python 3.11. Point `python` at that version. The other cause is a `kratos` folder that has no `libs/` folder next to `KratosMultiphysics/`. |
| *The python to run Kratos with … does not exist* / *is a directory* | `python` must be the full path to the interpreter file (`python.exe`, or `bin/python` in a venv), not a folder. |
| *A calculation is already running* | Only one run happens at a time. Wait for it to finish. |

The deck is always written, even when Kratos cannot be found. You can open its folder and run
it by hand.

On a Linux source build, if Kratos' libraries are not found, run
`export LD_LIBRARY_PATH=<kratos>/bin/Release/libs:$LD_LIBRARY_PATH` before `./run.sh`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

A typical session works through the modes from left to right: **Soil → Structures → Mesh →
Staged construction → Calculate → Results**.

### Building a model

- **Soil**: open **Modify soil layers**. **OK** checks the layers and rebuilds the geometry;
  **Cancel** restores the previous layers.
- **Material sets**: pick Fill, loose or dense sand, soft or stiff clay, or Bedrock from the
  **Default library** and click **Add to project**. You can edit each copy separately in
  **Properties…**. Interface presets apply strength reduction and permeability to the selected
  soil material. **OK** saves the project materials; **Cancel** discards your edits.
- **Structures**: **Create interface** adds a zero-thickness contact to the first sheet pile,
  so the wall can slide against the soil instead of being fixed to it. In the Selection
  explorer, the **Side** row chooses which faces get the interface (usually both, for a
  retaining wall). The **Contact** rows set the soil whose strength `R_inter` reduces, the
  virtual thickness, and the permeability. If the model has no sheet pile, the tool draws a
  free interface line through the soil instead. Interfaces are plane strain only, so the tool
  is not available in 3D.

### Meshing

Click **Mesh** to open the Gmsh properties: size, order, 3D algorithm, optimisation,
smoothing, curvature sampling and minimum size. Then choose **Apply and generate**.
<kbd>F9</kbd> meshes again with the saved settings. Check every soil layer you want to include
and give each one its own target size. The checked layers are meshed together, so their shared
surfaces use common nodes. **Refine**, **Coarsen** and **Reset local refinement** adjust the
mesh locally before it is generated.

### Calculating

**Calculate** (in the toolbar, or <kbd>F9</kbd> outside Mesh mode) meshes the project, writes
the deck into a new folder under `~/KratosGUI/runs`, and runs it with Kratos. Every run gets
its own folder. Nothing is overwritten and nothing is deleted. This needs Kratos, so see
[Setting up Kratos](#setting-up-kratos-for-calculate) first.

### Results

The **Results** tab reads a run back from its folder, so you can also open runs from earlier
sessions (`results runs`, then `results open <n>`).

- **Contours**: choose a phase and a field in the Results panel or the **Choose results**
  window. You can switch between bands and smooth shading, choose a colour map, show the
  deformed mesh, and set **Limits** for the legend's minimum and maximum
  (`results range <min> <max>`).
- **Plot along the wall**: **Plot wall…** or `results plot` shows the bending moment, shear
  force, normal force, displacements and interface tractions against depth, with one panel
  per phase. **Save SVG** and **Save CSV** export the figure or its numbers.
- `results at <node>` prints every field at one node, `results csv` saves the field on screen,
  and `results zip` downloads the whole run folder.

### Scripting

Type commands in the command box at the bottom of the window. `run <file.py>` runs a Python
file that returns a `Project` and loads the result into the viewport. For an example, try
`run tests/models/excavation.py`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Running the tests

Run these commands from the repository root, with any Python 3.10+. The runner always runs
pytest in the app's own venv. First install the test-only tools into that venv:

```bash
# Windows
.venv-windows\Scripts\python.exe -m pip install -r requirements-dev.txt
# Linux (use .venv-macos on macOS)
.venv-linux/bin/python -m pip install -r requirements-dev.txt
```

| Command | What it runs |
|---|---|
| `python tools/test.py quick` | The JS syntax check, the headless JS suites, and pytest without the browser |
| `python tools/test.py browser` | Everything in `quick`, plus the browser unit suite (`frontend/tests/index.html`) through Playwright |
| `python tools/test.py e2e` | Everything in `browser`, plus the GUI end-to-end tests |
| `python tools/test.py kratos` | The tests that run Kratos (needs [Kratos to be set up](#setting-up-kratos-for-calculate)) |
| `python tools/test.py bench` | The Kratos benchmark runner |
| `python tools/test.py perf` | The performance tests |
| `python tools/test.py all` | Everything this machine can run, with a list of what was skipped and why |

- Any arguments after the tier are passed to pytest, for example
  `python tools/test.py quick -k phases -x`.
- If a step's prerequisite is missing (quickjs, Kratos, or a browser), the step is reported as
  skipped, not as failed.
- The headless JS suites need `quickjs`. If it does not install in the venv, set
  `KRATOS_GUI_QUICKJS_PYTHON` to a Python that has it.
- The browser tests use your installed Chrome. If you do not have Chrome, run
  `python -m playwright install chromium` and set `KRATOS_GUI_TEST_BROWSER_CHANNEL=bundled`.
- For coverage, add `--cov=core --cov=backend --cov-report=html --js-coverage` to a tier that
  runs the browser suite. The Python report is written to `htmlcov/`, and the JS function
  coverage to `htmlcov-js/summary.json`.

CI runs the `e2e` tier on Windows and Ubuntu for every pull request and every push to `main`
(see [.github/workflows/tests.yml](.github/workflows/tests.yml)). Line coverage below 95 %
fails the run. [CONTRIBUTING.md](CONTRIBUTING.md) lists the other checks CI runs.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Project layout

```text
core/          the engine: schemas, geometry, Gmsh meshing, the Kratos deck writer, results reader
backend/       the FastAPI app, the in-memory project store, and the launcher
frontend/      the browser app (index.html, js/, css/, three.js), with its own tests in frontend/tests/
tests/         pytest suites: unit, API, browser, end-to-end, Kratos and performance
benchmarks/    Kratos benchmark cases and runner
tools/test.py  the tier runner
run.bat        launcher for Windows
run.sh         launcher for Linux and macOS
```

| Document | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | How a model flows from the browser to Kratos and back |
| [FEATURES.md](FEATURES.md) | What works, feature by feature, and where the code is |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Code size per module |

## Contributing

Contributions are welcome: bug reports, feature requests, documentation fixes and code.
[CONTRIBUTING.md](CONTRIBUTING.md) explains how to set up, how changes are made (tests
first), and what CI checks on every pull request.

In short:

1. Create a branch, and write a failing test before the code that makes it pass.
2. Run `python tools/test.py quick` (or `browser` if you changed the frontend), and
   `ruff check .`.
3. Open a pull request that explains what changed and why.

The frontend is deliberately build-free ES5. Please do not add npm, a bundler or a transpiler.

To report a security problem, do not open an issue. Follow [SECURITY.md](SECURITY.md)
instead.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Styx is distributed under the [Apache License 2.0](LICENSE). You may use, modify and
redistribute it, including commercially, provided you keep the license and copyright notices
and state the changes you made.

Styx relies on third-party software under its own licenses. Note that Gmsh, which the launcher
installs from PyPI, is licensed under the GNU GPL v2 or later. three.js (bundled in
`frontend/vendor/`) is MIT-licensed, and Kratos Multiphysics, installed separately, is
BSD-licensed.

## Contact

Use [GitHub issues](https://github.com/Deltares-research/Kratos-GUI/issues) for questions, bug
reports and ideas.

Project link: <https://github.com/Deltares-research/Kratos-GUI>

## Acknowledgments

- [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) and its
  GeoMechanicsApplication, the solver behind Calculate
- [Deltares](https://www.deltares.nl/)
- [Gmsh](https://gmsh.info/), for geometry and meshing
- [three.js](https://threejs.org/), for the 3D viewport
- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/)
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template), the structure
  of this README

<p align="right">(<a href="#readme-top">back to top</a>)</p>
