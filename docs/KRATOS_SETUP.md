# Setting up Kratos (for Calculate)

**Calculate** needs [Kratos Multiphysics](https://github.com/KratosMultiphysics/Kratos) with
its **GeoMechanicsApplication**. The launcher does not install it. This is deliberate: Kratos'
compiled modules only load in the exact Python version they were built for, and that is often
not the Python that runs the server. So Styx runs every calculation as a separate process,
using a Python interpreter that you choose.

Setup has three steps: install Kratos, tell Styx which Python has it, and check that it works.

## Step 1: Install Kratos

### Option A: Install from PyPI (Windows and Linux, recommended)

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
release when this was written, and it has no packages for Python 3.15. If the app runs on
Python 3.15, keep this environment on 3.14 or older. Pin it (`KratosGeoMechanicsApplication==10.4.4`) if you want
every machine to run the same solver.

### Option B: Build from source (macOS, or a development build)

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

## Step 2: Tell Styx where Kratos is

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

### Environment variables

Environment variables suit CI, or shells you start yourself. An environment variable takes
precedence over the same setting in `kratos.local.json`. Remember that double-clicking
`run.bat` starts a fresh shell that does not see variables you set in another terminal. That
is why the file is usually the easier option.

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

## Step 3: Check it works

1. Check that the interpreter can load Kratos on its own:

   ```bash
   <your kratos python> -c "import KratosMultiphysics.GeoMechanicsApplication; print('Kratos OK')"
   ```

   For option B, add the build folder to `PYTHONPATH` first, as described in the Kratos
   installation guide.
2. Start Styx, build or open a model, and press **Calculate**. The command log shows each
   stage as it runs. At the end it says whether the run succeeded and where the files are, and
   the app switches to **Results**.

## Troubleshooting

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
