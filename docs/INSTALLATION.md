# Installation

The launcher installs everything the modeller needs into a private virtual environment the
first time it runs. You only need Python and an internet connection. Kratos, the solver, is a
separate install. You only need it for **Calculate**: you can build, mesh and export models
without it. [KRATOS_SETUP.md](KRATOS_SETUP.md) explains how to set it up.

## Prerequisites

You need **Python 3.10 or newer, 64-bit**, and an internet connection for the first run.

### Windows 10/11

1. Install Python from [python.org](https://www.python.org/downloads/windows/), or run
   `winget install Python.Python.3.12`. The python.org installer also installs the `py`
   launcher, which `run.bat` uses.
2. Optional: install [Git](https://git-scm.com/download/win) to clone the repository.

Check the version (3.10 or newer):

```powershell
py --version
# Or:
python --version
```

### Linux (Ubuntu/Debian, Fedora, and others)

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

### macOS

The `python3` that comes with the Xcode command line tools is often too old. Install a
current one from [python.org](https://www.python.org/downloads/macos/), or with Homebrew:

```bash
brew install python@3.12 git
```

Check that `python3 --version` prints 3.10 or newer.

## Get the code

```bash
git clone https://github.com/Deltares-research/Styx-Kratos-GUI.git
cd Styx-Kratos-GUI
```

You can also download the ZIP from GitHub and unpack it.

## Run the app

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
automatically, as soon as the server is ready. Leave the terminal window open while you work, and press <kbd>Ctrl</kbd>+<kbd>C</kbd>
in it to stop the server.

What the launcher does:

1. It creates a virtual environment in the repository folder. Each operating system gets its
   own: `.venv-windows`, `.venv-linux` or `.venv-macos`. This means one checkout can be shared
   between systems, for example through WSL or a network drive.
2. It installs the pinned packages from [requirements.txt](../requirements.txt), and installs
   them again whenever that file changes.
3. It starts the server on port 8000.

To update, run `git pull` and start the launcher again.

## Launcher options

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

## Build the wheel

The package server gets Styx as a wheel. To build it, run this in the repository folder:

```bash
uv build --wheel
```

The wheel goes into `dist/`, as `dist/deltaresstyx-<version>-py3-none-any.whl`. Its
version is `VERSION` in `core/version.py`. The wheel holds the Python code and the browser
app, and it gives the commands `deltaresstyx` and `kratos-cli`. Kratos is a package of its
own, and since the names of the packages on Nexus and PyPI are not consistent yet, it is not
added as a dependency in the wheel.

## Next steps

- To run models with **Calculate**, install Kratos and connect it to Styx:
  [KRATOS_SETUP.md](KRATOS_SETUP.md).
- To learn how to build a model and read its results in the app: [USAGE.md](USAGE.md).
- To use Styx in a terminal, without the browser: [CLI.md](CLI.md) lists the commands, and
  the [CLI tutorials](cli_tutorials/README.md) build full models.
