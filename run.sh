#!/usr/bin/env bash
# Same setup path as run.bat, for macOS and Linux.
set -euo pipefail

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    exec python3 -m backend.launcher "$@"
elif command -v python >/dev/null 2>&1; then
    exec python -m backend.launcher "$@"
fi

echo "Python 3.10+ was not found on PATH." >&2
exit 1
