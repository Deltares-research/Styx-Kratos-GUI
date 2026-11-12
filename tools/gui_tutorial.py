"""Make the GUI tutorials' screenshots and site on this computer, from the GUI as it is now.

    python tools/gui_tutorial.py                  every tutorial: screenshots, then the site
    python tools/gui_tutorial.py NAME             one tutorial, then the site
    python tools/gui_tutorial.py NAME --headed    the same, and watch the browser do it
    python tools/gui_tutorial.py --no-site        the screenshots only
    python tools/gui_tutorial.py NAME --record    needs Kratos: calculate with Kratos, and keep
                                                  the run for the replay

NAME is a tutorial in `tests/e2e/tutorials/`; `python tools/gui_tutorial.py --help` lists
them. The screenshots go in `docs/gui_tutorials/images/NAME/`, and the site is built from
`docs/gui_tutorials/` into `build/gui_tutorials/site/` (open its `index.html`). Neither is
committed: CI makes both again for every pull request and every merge.

It plays the tutorial's steps in the real GUI, through `tests/e2e/test_gui_tutorials.py
--doc-screenshots`, so it also checks that the steps still work and still build the
tutorial's model. Calculate replays the run recorded in `tests/fixtures/tutorial_runs/NAME/`.
`--strict-deck` fails if the model's deck no longer matches that run; without it, that is a
warning. `--record` replaces the recorded run with a new one; commit it afterwards.

The site needs the packages of `requirements-docs.txt` in the server's venv.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.launcher import platform_venv_name, venv_python  # noqa: E402

TUTORIALS = ROOT / "tests" / "e2e" / "tutorials"
IMAGES = ROOT / "docs" / "gui_tutorials" / "images"
SITE = ROOT / "build" / "gui_tutorials" / "site"
"""Where `mkdocs.yml` (`site_dir`) builds the site."""
WARNINGS = ROOT / "build" / "gui_tutorials" / "deck-warnings.txt"
"""Where the test notes a deck that differs from its recorded run
(`tests/fakes/replay_kratos.py`, `WARNINGS_ENV`)."""
IMAGE = re.compile(r"!\[[^\]]*\]\((images/[^)\s]+)\)")
"""A Markdown image, and its path (as `tests/e2e/tutorials/__init__.py` reads it)."""


def tutorial_names() -> list[str]:
    return sorted(path.stem for path in TUTORIALS.glob("*.py")
                  if path.stem not in ("__init__", "harness"))


def server_python() -> pathlib.Path:
    candidate = venv_python(ROOT / platform_venv_name())
    return candidate if candidate.exists() else pathlib.Path(sys.executable)


def screenshots(python: pathlib.Path, names: list[str], args) -> int:
    command = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rw",
               "--run-e2e", "tests/e2e/test_gui_tutorials.py",
               "-k", " or ".join(names), "--doc-screenshots", str(IMAGES)]
    if args.headed:
        command.append("--headed")
    if args.strict_deck:
        command.append("--strict-deck")
    if args.record:
        command += ["--run-kratos", "--record-run"]
    WARNINGS.parent.mkdir(parents=True, exist_ok=True)
    WARNINGS.unlink(missing_ok=True)
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8",
                   "STYX_TUTORIAL_WARNINGS": str(WARNINGS)}
    code = subprocess.run(command, cwd=ROOT, env=environment).returncode
    if WARNINGS.exists():
        # In GitHub Actions, `::warning::` puts the line on the pull request's page.
        prefix = "::warning title=GUI tutorial run::" if os.environ.get("GITHUB_ACTIONS")             else "warning: "
        for line in WARNINGS.read_text(encoding="utf-8").splitlines():
            print(prefix + line, flush=True)
    if code == 0:
        for name in names:
            folder = IMAGES / name
            print(f"{len(list(folder.glob('*.png')))} screenshots in {folder}")
        if args.record:
            print("recorded in tests/fixtures/tutorial_runs/: commit the new run")
    return code


def missing_images() -> list[str]:
    """The screenshots a page shows that are not in `IMAGES`. Zensical's strict build checks
    the links of a page, but not its images."""
    pages = IMAGES.parent
    return [f"{page.name}: {path}" for page in sorted(pages.glob("*.md"))
            for path in IMAGE.findall(page.read_text(encoding="utf-8"))
            if not (pages / path).is_file()]


def site(python: pathlib.Path) -> int:
    missing = missing_images()
    if missing:
        print("The site was not built: these screenshots are missing:\n  "
              + "\n  ".join(missing), file=sys.stderr)
        return 1
    found = subprocess.run([str(python), "-c", "import zensical"], cwd=ROOT,
                           capture_output=True).returncode == 0
    if not found:
        print(f"The site was not built: {python} has no zensical. Install it with\n"
              f"  {python} -m pip install -r requirements-docs.txt\n"
              "or give --no-site.", file=sys.stderr)
        return 2
    code = subprocess.run([str(python), "-m", "zensical", "build", "--strict", "--clean",
                           "-f", "mkdocs.yml"], cwd=ROOT).returncode
    if code == 0:
        print(f"site in {SITE}: open {SITE / 'index.html'}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", metavar="NAME",
                        help=f"the tutorials (default: all of {', '.join(tutorial_names())})")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    parser.add_argument("--no-site", action="store_true", help="make the screenshots only")
    parser.add_argument("--strict-deck", action="store_true",
                        help="fail if a deck differs from its recorded run")
    parser.add_argument("--record", action="store_true",
                        help="calculate with Kratos and keep the run (needs Kratos)")
    args = parser.parse_args(argv)
    unknown = sorted(set(args.names) - set(tutorial_names()))
    if unknown:
        parser.error(f"no tutorial {', '.join(unknown)}; there are: "
                     f"{', '.join(tutorial_names())}")
    names = args.names or tutorial_names()

    python = server_python()
    code = screenshots(python, names, args)
    if code == 0 and not args.no_site:
        code = site(python)
    return code


if __name__ == "__main__":
    sys.exit(main())
