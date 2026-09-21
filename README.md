# Gmsh-backed geotechnical modeller mockup

The original static demonstration remains available by opening `index.html` directly. The live
version uses FastAPI and Gmsh to build and mesh real OpenCASCADE solids.

## Requirements

- Python 3.10 or newer
- Windows 10/11 (64-bit), or a 64-bit Linux distribution
- Internet access on the first run so pinned Python dependencies can be installed

## Run

On Windows, double-click `server\run.bat` or run it from Command Prompt. It creates
`server\.venv-windows`, starts the server, and opens <http://127.0.0.1:8000/>.

On Linux:

```bash
cd server
./run.sh
```

The Linux launcher creates `server/.venv-linux`. Platform-specific environments are intentionally
separate, so the same checkout can safely move between Windows and Linux. Run `run.bat --check` or
`./run.sh --check` to install and validate dependencies without starting the application.

## Useful interactions

- Click **Mesh** to open Gmsh properties. Configure size, order, 3D algorithm, optimization,
  smoothing, curvature sampling and minimum size, then choose **Apply and generate**. The gear tool
  in the Mesh rail opens the same dialog; **F9** generates again with the saved settings.
- In the Mesh properties panel, check every soil layer to include and assign an independent target
  size to each layer. Checked layers are meshed together so their shared surfaces use common nodes.
- Use **Refine**, **Coarsen**, or **Reset local refinement** before generating the mesh.
- In **Soil**, open **Modify soil layers**. OK validates and rebuilds the geometry; Cancel restores
  the previous layers.
- Open **Material sets** to use the **Default library**. Choose Fill, loose/dense sand,
  soft/stiff clay or Bedrock and click **Add to project**. Each copy is independently editable
  in **Properties…**. Interface presets apply strength reduction and permeability to the
  selected soil material. **OK** saves project materials; **Cancel** discards edits.
  Built-in presets remain available in every project and use the existing sample soil values.
- In **Structures**, **Create interface** puts a zero-thickness contact on the first live
  sheet pile so the wall can slide against the ground instead of being welded to it. The
  Selection explorer's **Side** row chooses which face is unglued -- both is the usual
  answer for a retaining wall -- and the **Contact** rows edit the shared property set:
  the soil whose strength `R_inter` reduces, the virtual thickness the stiffness is
  derived over, and the permeability. With no sheet pile in the model the tool draws a
  free interface line through the soil instead, which splits soil from soil. Interfaces
  are plane strain, so the tool is closed in the 3D model.

## Calculating

**Calculate** (toolbar, or **F9** outside Mesh mode) meshes the project, writes the deck --
`<project>.mdpa`, `MaterialParameters.json`, `ProjectParameters.json` -- into a directory of its
own, and runs it through Kratos' orchestrator. Nothing changes on screen: the command log says
whether the run succeeded and where the files went. Each run gets its own directory and nothing is
cleaned up.

Kratos is not installed by `run.bat`, and its compiled extensions are bound to the exact Python
they were built for, which is usually not the one running the server. So the calculation runs as a
subprocess, and the server has to be told which interpreter to use:

| Variable | What | Example |
|---|---|---|
| `KRATOS_GUI_PYTHON` | The interpreter your Kratos build was made for. Defaults to the server's own. | `C:\Kratos\.venv\Scripts\python.exe` |
| `KRATOS_GUI_KRATOS` | The build directory, holding `KratosMultiphysics\` and `libs\`. Leave unset if the interpreter already finds Kratos. | `C:\Kratos\bin\Release` |
| `KRATOS_GUI_RUNS` | Where run directories are made. | `~/KratosGUI/runs` (default) |
| `KRATOS_GUI_TIMEOUT` | Seconds before a run is given up on. | `3600` (default) |

The first two can also be written down instead of exported, which is usually what you want --
`run.bat` is started by double-clicking it and inherits no shell you set variables in. Create
`server\kratos.local.json`:

```json
{
    "python": "C:\\Kratos\\.venv\\Scripts\\python.exe",
    "kratos": "C:\\Kratos\\bin\\Release"
}
```

That file is machine-specific and git-ignored; an environment variable still wins over it. Both
are read on every run, so a machine can be set up and Calculate pressed again without restarting
the server. If Kratos cannot be found, the command log says exactly what to write where; the deck
is written either way, so it can also just be run by hand.

Run backend tests with `server/.venv-linux/bin/python -m pytest -q` on Linux, or
`server\.venv-windows\Scripts\python.exe -m pytest -q` on Windows. JavaScript logic tests are in
`live/tests/index.html` and require no build step.
