# Building and Installing as a Wheel

This repository can now be built and distributed as a Python wheel (`.whl`) file for easy installation.

## Building the Wheel

To create a `.whl` distribution file:

```bash
# Install build tools if not already installed
pip install build

# Build the wheel
python -m build --wheel
```

This generates a `.whl` file in the `dist/` directory, e.g., `kratos_gui-0.1.0-py3-none-any.whl`.

## Installing the Wheel

To install the package from the wheel:

```bash
# Install in the current environment
pip install dist/kratos_gui-0.1.0-py3-none-any.whl

# Or from a package index after uploading
pip install kratos-gui
```

## Running the Application

After installation, the application can be run using the `kratos-gui` command:

```bash
# Start the server with default settings (host=127.0.0.1, port=8000, open browser)
kratos-gui

# Start the server on a specific host/port
kratos-gui --host 0.0.0.0 --port 8080

# Validate dependencies without starting the server
kratos-gui --check
```

This is equivalent to running `run.bat` on Windows or `run.sh` on Linux/macOS.

## What's Included

The wheel includes:
- All Python modules from `backend/`, `core/`, and `cli/` packages
- All frontend assets from the `frontend/` directory (HTML, CSS, JavaScript, images)
- All runtime dependencies (FastAPI, Uvicorn, Gmsh, NumPy, Pydantic, etc.)

## Development vs. Installed Mode

The launcher (`backend/launcher.py`) automatically detects whether it's running from:
- A **development checkout**: Sets up a local virtual environment and installs dependencies from `requirements.txt`
- An **installed wheel**: Uses the Python environment where the package is installed

In both cases, the `backend.main` module correctly locates frontend assets.

## Version Updates

To update the version when building a new wheel, edit the `version` field in `pyproject.toml`:

```toml
[project]
name = "kratos-gui"
version = "0.2.0"  # Change this
```

Then rebuild the wheel.
