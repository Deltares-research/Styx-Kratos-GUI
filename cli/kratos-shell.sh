#!/usr/bin/env bash
# kratos-shell: open the kratos-cli shell in a folder of your own, with its runs there too.
# Asks for the folder, or takes it as the first argument; the folder is made if it is not there.
#   ./kratos-shell.sh                  # asks
#   ./kratos-shell.sh ~/my_dike        # or C:\..., C:/..., /c/... in Git Bash
set -euo pipefail

# The repository root: the first folder up from this script that holds kratos-cli.sh.
ROOT="$(cd "$(dirname "$0")" && pwd)"
while [ ! -f "$ROOT/kratos-cli.sh" ]; do
    if [ "$ROOT" = "$(dirname "$ROOT")" ]; then
        echo "kratos-cli.sh was not found above $(dirname "$0")." >&2
        exit 1
    fi
    ROOT="$(dirname "$ROOT")"
done

FOLDER="${1:-}"
if [ -z "$FOLDER" ]; then
    read -r -p "Folder for the model and its runs: " FOLDER
fi
if [ -z "$FOLDER" ]; then
    echo "No folder given." >&2
    exit 1
fi
FOLDER="${FOLDER/#\~/$HOME}"
# Git Bash on Windows: accept a Windows path (C:\Users\you\my_dike) as typed.
if command -v cygpath >/dev/null 2>&1; then
    FOLDER="$(cygpath -u "$FOLDER")"
fi

mkdir -p "$FOLDER"
cd "$FOLDER"

# Runs go into this folder too. Python on Windows needs the Windows form of the path.
if command -v cygpath >/dev/null 2>&1; then
    export KRATOS_GUI_RUNS="$(cygpath -w "$PWD")"
else
    export KRATOS_GUI_RUNS="$PWD"
fi

exec "$ROOT/kratos-cli.sh" shell
