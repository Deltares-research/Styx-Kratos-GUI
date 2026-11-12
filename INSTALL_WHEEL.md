# Installing and Running Kratos GUI from a Wheel

This document provides step-by-step instructions for installing and running the Kratos GUI application from a `.whl` (wheel) package.

## Prerequisites

- Python 3.10 or newer
- pip (Python package manager) **or** [uv](https://docs.astral.sh/uv/) (a fast alternative to pip; every `pip` command below has a `uv` equivalent)

## Step 1: Build the Wheel (if needed)

If you don't already have a `.whl` file, build it from the source:

```bash
# Install the build tool
pip install build

# Build the wheel
python -m build --wheel
```

Or with uv (no separate build tool install needed):

```bash
uv build --wheel
```

The wheel file will be created in the `dist/` directory as `kratos_gui-0.1.0-py3-none-any.whl`.

## Step 2: Install the Wheel

### Option A: Install in the current Python environment

```bash
pip install dist/kratos_gui-0.1.0-py3-none-any.whl
```

Or with uv:

```bash
uv pip install dist/kratos_gui-0.1.0-py3-none-any.whl
```

### Option B: Install in a fresh virtual environment (Recommended)

Creating a virtual environment isolates the installation and avoids conflicts:

```bash
# Create a virtual environment
python -m venv kratos_env

# Activate it
# On Windows:
kratos_env\Scripts\activate
# On Linux/macOS:
source kratos_env/bin/activate

# Install the wheel
pip install dist/kratos_gui-0.1.0-py3-none-any.whl
```

Or with uv:

```bash
# Create a virtual environment
uv venv kratos_env

# Activate it
# On Windows:
kratos_env\Scripts\activate
# On Linux/macOS:
source kratos_env/bin/activate

# Install the wheel
uv pip install dist/kratos_gui-0.1.0-py3-none-any.whl
```

Alternatively, `uv tool` installs the application into its own isolated environment and puts `kratos-gui` on your PATH, without manual activation:

```bash
uv tool install dist/kratos_gui-0.1.0-py3-none-any.whl
```

### Option C: Install from PyPI (after uploading)

Once the package is published to PyPI:

```bash
pip install kratos-gui
# or
uv pip install kratos-gui
# or
uv tool install kratos-gui
```

## Step 3: Verify Installation

Verify that the installation was successful:

```bash
kratos-gui --check
```

You should see output like:
```
Environment OK: gmsh 4.13.1
```

## Step 4: Run the Application

### Basic usage (opens browser automatically)

```bash
kratos-gui
```

The server will start at `http://127.0.0.1:8000` and your default browser will open automatically.

### Advanced options

**Run on a different host or port:**

```bash
# Run on all network interfaces
kratos-gui --host 0.0.0.0 --port 8080
```

**Run without opening the browser:**

```bash
kratos-gui --host 127.0.0.1 --port 8000
```

Then manually open `http://127.0.0.1:8000` in your browser.

**Get help:**

```bash
kratos-gui --help
```

## Uninstalling

To remove the application:

```bash
pip uninstall kratos-gui
# or, with uv
uv pip uninstall kratos-gui
# or, if installed via uv tool
uv tool uninstall kratos-gui
```

If you created a virtual environment, you can also delete it entirely:

```bash
# On Windows:
rmdir /s kratos_env

# On Linux/macOS:
rm -rf kratos_env
```

## Troubleshooting

### Command not found: `kratos-gui`

This means the wheel wasn't installed in your active Python environment. Verify:

```bash
# Check which Python is active
python --version

# Check if the package is installed
pip list | grep kratos
# or, with uv
uv pip list | grep kratos
```

If using a virtual environment, make sure it's activated.

### Port already in use

If port 8000 is already in use, run on a different port:

```bash
kratos-gui --port 8001
```

### Import errors after installation

If you encounter import errors, try reinstalling:

```bash
pip uninstall kratos-gui
pip install dist/kratos_gui-0.1.0-py3-none-any.whl --force-reinstall
# or, with uv
uv pip install dist/kratos_gui-0.1.0-py3-none-any.whl --reinstall
```

## Differences from `run.bat` / `run.sh`

The wheel-based installation provides several advantages:

| Feature | run.bat/run.sh | kratos-gui wheel |
|---------|---|---|
| Setup | Creates local venv on first run | Installs dependencies globally |
| Portability | Ties venv to checkout location | Can be installed anywhere |
| Distribution | Requires full repository | Single .whl file (~50-100 MB) |
| Updates | Pull changes from git | pip install --upgrade (or uv pip install --upgrade) |
| Multi-instance | Creates separate venvs per platform | Shares dependencies |

Both methods run the same application code and offer identical functionality.
