"""`python -m cli` from the repository root, the file `kratos-cli.bat` and
`kratos-cli.sh` start from anywhere else, and `run` is the `kratos-cli` command of an
installed wheel (`pyproject.toml`).

Started as a file, Python puts this folder first on its path; the repository root goes
there instead. Not the user's folder: the command runs in it, so the paths typed are
theirs, but a `core/` or `cli/` of theirs must not stand in for the repository's.
"""

import sys
from pathlib import Path

if not __package__:
    sys.path[0] = str(Path(__file__).resolve().parents[1])

from cli.terminal.main import main  # noqa: E402


def run() -> int:
    # What is printed is UTF-8 wherever it goes: a project's name may hold any character,
    # and a pipe on Windows would otherwise take the console's code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    return main()


if __name__ == "__main__":
    sys.exit(run())
