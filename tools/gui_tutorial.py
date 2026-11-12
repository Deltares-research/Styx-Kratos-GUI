"""Make the screenshots of a GUI tutorial on this computer, from the GUI as it is now.

    python tools/gui_tutorial.py NAME              screenshots in build/gui_tutorials/images/NAME/
    python tools/gui_tutorial.py NAME --headed     the same, and watch the browser do it
    python tools/gui_tutorial.py NAME --out DIR    screenshots in DIR/images/NAME/

NAME is a tutorial in `tests/e2e/tutorials/`; `python tools/gui_tutorial.py --help` lists
them. It plays the tutorial's steps (`tests/e2e/tutorials/<name>.py`) in the real GUI, through
`tests/e2e/test_gui_tutorials.py --doc-screenshots`, so it also checks that the steps still
work and still build the tutorial's model. Calculate uses the fake Kratos of the tests.

The site shows screenshots that CI makes; these are for a preview while you write or change
a tutorial. Old screenshots of the tutorial in the folder are removed first.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.launcher import platform_venv_name, venv_python  # noqa: E402

TUTORIALS = ROOT / "tests" / "e2e" / "tutorials"


def tutorial_names() -> list[str]:
    return sorted(path.stem for path in TUTORIALS.glob("*.py")
                  if path.stem not in ("__init__", "harness"))


def server_python() -> pathlib.Path:
    candidate = venv_python(ROOT / platform_venv_name())
    return candidate if candidate.exists() else pathlib.Path(sys.executable)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", choices=tutorial_names(), help="the tutorial")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "build" / "gui_tutorials",
                        help="the folder for images/<name>/ (default: build/gui_tutorials)")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    args = parser.parse_args(argv)

    images = args.out.resolve() / "images"
    command = [str(server_python()), "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--run-e2e", "tests/e2e/test_gui_tutorials.py", "-k", args.name,
               "--doc-screenshots", str(images)]
    if args.headed:
        command.append("--headed")
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    code = subprocess.run(command, cwd=ROOT, env=environment).returncode
    folder = images / args.name
    if code == 0:
        print(f"{len(list(folder.glob('*.png')))} screenshots in {folder}")
    return code


if __name__ == "__main__":
    sys.exit(main())
