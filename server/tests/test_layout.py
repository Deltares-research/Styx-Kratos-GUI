"""The repository's layout: `core/`, `backend/`, `frontend/`, and what each may depend on.

core is the engine -- model, geometry, mesh, Kratos deck, running Kratos, reading
results -- in plain Python with no web framework. backend is the FastAPI server around
it. frontend is the browser app the backend serves. The split existed in the code before
the folders said so; these tests keep it visible and keep it from eroding:

* the three folders exist, and the two they replace, `server/` and `live/`, are gone;
* nothing in core imports the web framework or the backend;
* `core/__init__.py` is empty and `core/kratos_runner.py` needs only the standard
  library, because Kratos' own interpreter imports the `core` package to run a deck and
  has neither pydantic nor gmsh;
* no file in the repository still points into the old folders or names the old `app`
  package.

The command Kratos is started with, and the path it is started on, are pinned beside the
code that builds them, in test_calculate.py.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """The checkout's root: the folder `tools/test.py` is in. Found by walking up rather
    than by counting levels, so this file reads the same wherever the tests folder sits."""
    here = Path(__file__).resolve()
    for folder in here.parents:
        if (folder / "tools" / "test.py").is_file():
            return folder
    raise RuntimeError(f"no tools/test.py above {here}")


ROOT = _repo_root()
CORE = ROOT / "core"
BACKEND = ROOT / "backend"
THIS = Path(__file__).resolve().relative_to(ROOT).as_posix()


def imports(tree: ast.AST) -> list[tuple[int, str]]:
    """`(line, module)` for every import in `tree`, at any depth: an import inside a
    function counts as much as one at the top.

    `import a.b` and `from a.b import c` both give `a.b`; so do `importlib.import_module`
    and `__import__` called with a literal name. A relative import keeps its dots, so
    `from .x import y` gives `.x`.
    """
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            found.append((node.lineno, "." * node.level + (node.module or "")))
        elif (isinstance(node, ast.Call) and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)
              and (getattr(node.func, "attr", None) == "import_module"
                   or getattr(node.func, "id", None) in ("import_module", "__import__"))):
            found.append((node.lineno, node.args[0].value))
    return sorted(found)


def parsed(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_imports_finds_every_form():
    tree = ast.parse(
        "import os, a.b\n"
        "from c.d import e\n"
        "from . import f\n"
        "from ..g import h\n"
        "def later():\n"
        "    import i\n"
        "    importlib.import_module('j.k')\n"
        "    __import__('l')\n"
        "    importlib.import_module(name)\n")
    assert imports(tree) == [(1, "a.b"), (1, "os"), (2, "c.d"), (3, "."), (4, "..g"),
                             (6, "i"), (7, "j.k"), (8, "l")]


# ── The folders ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("folder", ["core", "backend", "frontend"])
def test_the_three_folders_exist(folder):
    assert (ROOT / folder).is_dir(), f"{folder}/ is missing from {ROOT}"


@pytest.mark.parametrize("folder", ["server", "live"])
def test_the_folders_they_replace_are_gone(folder):
    assert not (ROOT / folder).exists(), (
        f"{folder}/ is still in {ROOT}. Whatever is left in it (a venv, caches, run "
        "data) belongs at the root now, or nowhere.")


# ── The boundary: core knows nothing of the web ─────────────────────────────

WEB = {"fastapi", "starlette", "uvicorn", "backend"}
"""What core may not import. pydantic is not here: the model is pydantic, and that is the
model's business, not the web's."""


def test_core_does_not_import_the_web_framework_or_the_backend():
    files = sorted(CORE.rglob("*.py"))
    assert files, f"no Python files under {CORE}"
    crossings = [f"{path.relative_to(ROOT).as_posix()}:{line} imports {name}"
                 for path in files for line, name in imports(parsed(path))
                 if name.split(".")[0] in WEB]
    assert not crossings, "core reaches into the web layer:\n" + "\n".join(crossings)


# ── What Kratos' interpreter imports ────────────────────────────────────────

def test_the_core_package_itself_is_empty():
    """Kratos is started with `-m core.kratos_runner`, which runs `core/__init__.py`
    first, in an interpreter that has none of this project's dependencies."""
    init = CORE / "__init__.py"
    assert init.is_file(), f"{init} is missing"
    assert init.read_text(encoding="utf-8").strip() == "", f"{init} has to stay empty"


KRATOS = "KratosMultiphysics"


def test_the_kratos_runner_needs_only_the_standard_library():
    """Kratos' interpreter has the standard library and Kratos, and nothing else."""
    runner = CORE / "kratos_runner.py"
    assert runner.is_file(), f"{runner} is missing"
    allowed = set(sys.stdlib_module_names) | {"__future__", KRATOS}
    foreign = [f"line {line}: {name}" for line, name in imports(parsed(runner))
               if name.startswith(".") or name.split(".")[0] not in allowed]
    assert not foreign, (f"{runner.name} imports what Kratos' interpreter does not "
                         "have:\n" + "\n".join(foreign))


# ── No reference left behind ────────────────────────────────────────────────

SKIPPED = ("plan/", "frontend/base/")
"""`plan/` is history and stays as written. `frontend/base/` is the frozen shell: it is
never edited, so the paths its comments cite stay as they were."""

BINARY = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".gz", ".zip", ".woff", ".woff2",
          ".ttf", ".brep", ".pdf"}


def module_names() -> list[str]:
    """The modules `core` and `backend` hold: each was once `app.<name>`."""
    return sorted(path.stem for folder in (CORE, BACKEND) if folder.is_dir()
                  for path in folder.glob("*.py") if path.stem != "__init__")


def stale_pattern(modules: list[str]) -> re.Pattern:
    """What a reference left over from before the move looks like.

    * A path through `server/` or `live/`, with either separator: `server/app/kratos.py`,
      `live/js/patches.js`, `server\\run.bat`, `../live/tests/`. Not a URL the browser
      loads, which keeps its root-relative `/live/...` (the backend serves `frontend/`
      there), and not a share such as `\\\\server\\share`.
    * An import of the old package: `from app import x`, `from app.x import y`,
      `import app`.
    * One of its modules by dotted name, where a dotted name is unambiguous: after `-m`
      (`-m app.launcher`), or opening a string or code span (`"app.main:app"`,
      `"app.calculate.run"`, `` `app.script` ``). A bare `app.routes` is FastAPI's.
    """
    rules = [
        r"(?<![\w.\\/-])(?:server|live)[\\/]",
        r"(?<=[\w.:-]/)(?:server|live)[\\/]",
        r"(?<![\w.])from\s+app(?:\.\w+)*\s+import\b",
        r"(?<![\w.])import\s+app(?!\w)",
    ]
    if modules:
        rules.append(r"(?:-m\s+|(?<![\w.])[`\"'])app\.(?:" + "|".join(modules) + r")(?!\w)")
    return re.compile("|".join(rules))


def test_the_pattern_finds_old_references_and_leaves_the_rest_alone():
    stale = stale_pattern(["kratos_runner", "launcher", "main", "script"])
    for line in [
        "see server/app/kratos.py",
        "cd server/tests && pytest",
        "(server/app/kratos_processes.py)",
        "double-click `server\\run.bat`",
        "\"server\\\\app\\\\x.py\"",
        "ROOT/live/js/patches.js",
        "<script src=\"../live/tests/harness.js\">",
        "were left checked (app/live/js/model.js's setImportedParts)",
        "file:///D:/Checkouts/Kratos-GUI/live/js/",
        "from app import calculate",
        "    from app.schemas import Project",
        "import app",
        "import app.main",
        "py -3 -m app.launcher --open-browser",
        "[\"-m\", \"app.kratos_runner\", \"ProjectParameters.json\"]",
        "\"app.main:app\"",
        "See `app.script` for the three ways",
    ]:
        assert stale.search(line), line
    for line in [
        "<script src=\"/live/js/unit-table.js\"></script>",
        "client.get(\"/live/js/viewport.js\")",
        "LIVE_DIR = \"/live/js/\"",
        "\"\\\\\\\\server\\\\share\\\\\" + OUTSIDE",
        "T.ok(/server/i.test(err.message), err.message);",
        "the live layer patches the frozen shell",
        "test-viewport-live.js",
        "App.LivePatches",
        "the server and the browser, client/server",
        "data coming from app state",
        "import application",
        "for r in app.routes if isinstance(r, APIRoute)",
        "| `app.js` | 299 |",
        "from core.schemas import Project",
        "-m core.kratos_runner",
    ]:
        assert not stale.search(line), line


def repository_files() -> list[str]:
    """What the next commit would hold: tracked files still on disk, and new files git
    does not ignore."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as failure:
        pytest.skip(f"not a git checkout: {failure}")
    names = dict.fromkeys(name for name in listed.decode("utf-8").split("\0") if name)
    return [name for name in names if (ROOT / name).is_file()]


def test_nothing_points_into_the_old_folders_or_the_old_package():
    stale = stale_pattern(module_names())
    found = []
    for name in repository_files():
        if name == THIS or name.startswith(SKIPPED) or Path(name).suffix.lower() in BINARY:
            continue
        try:
            text = (ROOT / name).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        found += [f"{name}:{number}: {line.strip()[:120]}"
                  for number, line in enumerate(text.splitlines(), start=1)
                  if stale.search(line)]
    shown = "\n".join(found[:60]) + (f"\n... and {len(found) - 60} more" if len(found) > 60 else "")
    assert not found, f"{len(found)} references from before the move:\n{shown}"
