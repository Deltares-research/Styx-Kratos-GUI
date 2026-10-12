#!/usr/bin/env bash
# kratos-cli: build, mesh, stage, export, run and read a model in the terminal.
# kratos-cli.bat on Windows, where this one also runs in Git Bash. Runs in your own
# folder, so the paths you type are yours.
# Uses the environment run.sh makes, and makes it first when it is not there yet.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
case "$(uname -s)" in
    Linux)  PYTHON="$ROOT/.venv-linux/bin/python" ;;
    Darwin) PYTHON="$ROOT/.venv-macos/bin/python" ;;
    # Git Bash on Windows: the environment run.bat makes.
    MINGW*|MSYS*|CYGWIN*) PYTHON="$ROOT/.venv-windows/Scripts/python.exe" ;;
    *)      PYTHON="$ROOT/.venv-$(uname -s | tr '[:upper:]' '[:lower:]')/bin/python" ;;
esac

if [ ! -x "$PYTHON" ]; then
    echo "Setting up the Python environment first, once..." >&2
    # On Windows, the py launcher first, as run.bat: python3 there may be the Store's stub.
    if [ "${PYTHON%.exe}" != "$PYTHON" ] && command -v py >/dev/null 2>&1; then
        (cd "$ROOT" && py -3 -m backend.launcher --check) >&2
    elif command -v python3 >/dev/null 2>&1; then
        (cd "$ROOT" && python3 -m backend.launcher --check) >&2
    elif command -v python >/dev/null 2>&1; then
        (cd "$ROOT" && python -m backend.launcher --check) >&2
    else
        echo "Python 3.10+ was not found on PATH." >&2
        exit 1
    fi
fi

exec "$PYTHON" "$ROOT/cli/__main__.py" "$@"
