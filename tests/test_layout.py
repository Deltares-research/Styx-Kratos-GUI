"""The repository's layout: `core/`, `backend/`, `frontend/`, and what each may depend on.

core is the engine -- model, geometry, mesh, Kratos deck, running Kratos, reading
results -- in plain Python with no web framework. backend is the FastAPI server around
it. frontend is the browser app the backend serves. The split existed in the code before
the folders said so; these tests keep it visible and keep it from eroding:

* the three folders exist, and the two they replace, `server/` and `live/`, are gone;
* nothing in core imports the web framework or the backend;
* core is five packages, one per stage of the pipeline -- `model`, `geometry`, `kratos`,
  `run`, `results` -- and imports between them go one way, down that list;
* every `__init__.py` in core is empty and `core/run/runner.py` needs only the standard
  library, because Kratos' own interpreter imports the `core` package to run a deck and
  has neither pydantic nor gmsh;
* no file in the repository still points into the old folders, names the old `app`
  package, or names a core module by the flat name it had before the packages, dotted
  (`core.kratos_runner`) or alone in prose (`kratos_runner`);
* everything the browser loads comes from `frontend/`, so a checkout runs the same
  without the old, untracked copies of the shell some machines keep at the root
  (`css/`, `js/`).

The command Kratos is started with, and the path it is started on, are pinned beside the
code that builds them, in test_calculate.py.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import sys
import tokenize
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
FRONTEND = ROOT / "frontend"
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


ROOT_FILES = {
    ".gitattributes", ".gitignore", ".gitleaksignore",     # git and gitleaks look only here
    "README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md",
    "run.bat", "run.sh",                                    # what a user double-clicks
    "requirements.txt", "requirements-dev.txt",             # the launcher and Dependabot
    "pyproject.toml",                                       # pytest, coverage, mypy, ruff
    "eslint.config.mjs",                                    # its globs are root-relative
}
"""The files the repository keeps at its root. Anything else has a folder: documents in
`docs/`, CI settings in `.github/`, a Python tool's settings in `pyproject.toml`."""


def test_the_root_holds_only_what_has_to_be_there():
    extra = sorted(name for name in repository_files()
                   if "/" not in name and name not in ROOT_FILES)
    assert not extra, (
        f"new files at the root: {extra}. Put them in a folder (docs/, .github/, tools/), "
        "or add them to ROOT_FILES with the reason they cannot move.")


@pytest.mark.parametrize("name", [".coveragerc", "mypy.ini", "pytest.ini", "ruff.toml"])
def test_the_python_tools_read_their_settings_from_pyproject(name):
    assert not (ROOT / name).exists(), f"{name} overrides pyproject.toml; merge it there"


@pytest.mark.parametrize("name", ["ARCHITECTURE.md", "FEATURES.md", "PROJECT_OVERVIEW.md",
                                  "INSTALLATION.md", "KRATOS_SETUP.md", "USAGE.md",
                                  "TESTING.md"])
def test_the_documents_are_in_docs_and_linked_from_the_readme(name):
    assert (ROOT / "docs" / name).is_file(), name
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"(docs/{name})" in readme, f"the README's table of documents misses {name}"


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


# ── The packages inside core ────────────────────────────────────────────────

LAYERS = {"model": 0, "geometry": 1, "kratos": 2, "run": 3, "results": 4}
"""core's packages, in the order the data goes through them: the project the user edits,
its geometry and mesh, the Kratos deck written from both, the run of that deck, and what
the run left behind. A package may import from its own rank or below, never above."""

TOP_LEVEL = {"__init__.py", "script.py", "gmsh_worker.py"}
"""What stays at core's top level: the two modules that send work into several packages
(`run <file.py>`, and the gmsh process pool). They are outside the ranking."""

ALLOWED: dict[tuple[str, str], str] = {}
"""The imports that go up anyway, `(file, module): reason`. None now: the last, the mesh
preview asking the exporter which edges a load is on, went when that selection moved
down into `core.geometry.meshing.loaded_elements`. An entry that no longer happens fails
too, so the list cannot go stale."""


def test_each_package_of_core_exists():
    """One test, not one per package: a parameter named `kratos` would be read as the
    `kratos` marker (tests/conftest.py) and skipped without Kratos."""
    missing = [f"core/{package}/" for package in sorted(LAYERS)
               if not (CORE / package / "__init__.py").is_file()]
    assert not missing, f"missing: {missing}"


def test_only_the_cross_cutting_modules_stay_at_the_top_of_core():
    top = {path.name for path in CORE.glob("*.py")}
    assert top == TOP_LEVEL, (
        f"at core's top level: {sorted(top - TOP_LEVEL)} should be in a package, "
        f"{sorted(TOP_LEVEL - top)} are missing")


def layer(module: str) -> int | None:
    """The rank of a dotted module name in `LAYERS`, or None outside the packages."""
    parts = module.split(".")
    return LAYERS.get(parts[1]) if parts[0] == "core" and len(parts) > 1 else None


def core_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """`imports(tree)`, with `from core.x import y` also named `core.x.y` where `y` is a
    module or a package, so `from core.kratos import export` reads as the module it
    imports and `from core import results` as the package."""
    found = imports(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module \
                and node.module.split(".")[0] == "core":
            folder = ROOT.joinpath(*node.module.split("."))
            found += [(node.lineno, f"{node.module}.{alias.name}") for alias in node.names
                      if (folder / f"{alias.name}.py").is_file()
                      or (folder / alias.name / "__init__.py").is_file()]
    return sorted(found)


def upward(tree: ast.AST, own: int) -> list[tuple[int, str]]:
    """The imports in `tree` of a package ranked above `own`, in any form: `import
    core.results`, `from core import results`, `from core.results import runs`, `from
    core.results.runs import x`."""
    return [(line, name) for line, name in core_imports(tree)
            if (rank := layer(name)) is not None and rank > own]


def upward_imports() -> dict[tuple[str, str], list[int]]:
    found: dict[tuple[str, str], list[int]] = {}
    for path in sorted(CORE.rglob("*.py")):
        relative = path.relative_to(ROOT)
        own = LAYERS.get(relative.parts[1]) if len(relative.parts) > 2 else None
        if own is None:
            continue
        for line, name in upward(parsed(path), own):
            found.setdefault((relative.as_posix(), name), []).append(line)
    return found


def test_layer_reads_the_package_of_a_dotted_name():
    assert layer("core.model.schemas") == 0
    assert layer("core.results.runs") == 4
    assert layer("core.results") == 4
    assert layer("core.gmsh_worker") is None
    assert layer("core") is None
    assert layer("gmsh") is None


def test_an_upward_import_is_found_in_every_form():
    tree = ast.parse(
        "import core.kratos\n"
        "from core import results\n"
        "from core.run import calculate\n"
        "from core.results.runs import run_directory\n"
        "def later():\n"
        "    from core.kratos import export as kratos\n"
        "from core.model import schemas\n"
        "from core import geometry, gmsh_worker\n"
        "import core.geometry.build\n")
    found = upward(tree, LAYERS["geometry"])
    assert sorted({line for line, _ in found}) == [1, 2, 3, 4, 6], found


def test_imports_inside_core_go_one_way():
    """model <- geometry <- kratos <- run <- results, lazy imports included."""
    found = upward_imports()
    upward = [f"{file}:{lines[0]} imports {name} (rank {layer(name)})"
              for (file, name), lines in sorted(found.items()) if (file, name) not in ALLOWED]
    stale = [f"{file} no longer imports {name}" for file, name in sorted(ALLOWED)
             if (file, name) not in found]
    assert not upward, "an import goes up the pipeline:\n" + "\n".join(upward)
    assert not stale, "ALLOWED names an import that is gone; remove it:\n" + "\n".join(stale)


def test_the_paths_found_from_file_point_at_the_repository():
    """These are found from `__file__`, so each goes one level deeper when its module
    moves into a package; left as it was, it would point inside `core/` and still work
    -- on the wrong folder."""
    from core.geometry import creator, importer
    from core.run import calculate

    assert calculate.ROOT == ROOT
    assert creator.DATA_DIR == ROOT / ".data"
    assert importer.DATA_DIR == ROOT / ".data"


# ── What Kratos' interpreter imports ────────────────────────────────────────

def test_every_package_in_core_is_empty():
    """Kratos is started with `-m core.run.runner`, which runs `core/__init__.py` and
    `core/run/__init__.py` first, in an interpreter that has none of this project's
    dependencies. The other packages' are held to the same rule: one rule, not two."""
    inits = sorted(CORE.rglob("__init__.py"))
    assert CORE / "__init__.py" in inits, f"{CORE / '__init__.py'} is missing"
    full = [init.relative_to(ROOT).as_posix() for init in inits
            if init.read_text(encoding="utf-8").strip()]
    assert not full, f"these have to stay empty: {full}"


KRATOS = "KratosMultiphysics"


def test_the_kratos_runner_needs_only_the_standard_library():
    """Kratos' interpreter has the standard library and Kratos, and nothing else."""
    runner = CORE / "run" / "runner.py"
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
    """The modules the old `app` package held, each once `app.<name>`: core's under the
    flat names they had then, and backend's top level."""
    return sorted({*MOVED, *(path.stem for folder in (CORE, BACKEND) if folder.is_dir()
                             for path in folder.glob("*.py") if path.stem != "__init__")})


def stale_pattern(modules: list[str]) -> re.Pattern:
    """What a reference left over from before the move looks like.

    * A path through `server/` or `live/`, with either separator: `server/app/kratos.py`,
      `live/js/patches.js`, `server\\run.bat`, `../live/tests/`. Not a URL the browser
      loads, which keeps its root-relative `/live/...` (the backend serves `frontend/`
      there), and not a share such as `\\\\server\\share`.
    * An import of the old package: `from app import x`, `from app.x import y`,
      `import app` (as a statement, not `from backend.main import app`, which is
      FastAPI's object).
    * One of its modules by dotted name, where a dotted name is unambiguous: after `-m`
      (`-m app.launcher`), or opening a string or code span (`"app.main:app"`,
      `"app.calculate.run"`, `` `app.script` ``). A bare `app.routes` is FastAPI's.
    """
    rules = [
        r"(?<![\w.\\/-])(?:server|live)[\\/]",
        r"(?<=[\w.:-]/)(?:server|live)[\\/]",
        r"(?<![\w.])from\s+app(?:\.\w+)*\s+import\b",
        r"(?:^|[;`])\s*import\s+app(?!\w)",
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
        "    import app",
        "so `import app` must not pull the server in",
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
        "from core.model.schemas import Project",
        "from backend.main import app",
        "    from backend.main import app",
        "\"from backend.main import app; \"",
        "-m core.run.runner",
    ]:
        assert not stale.search(line), line


MOVED = {
    "schemas": "model.schemas", "units": "model.units", "legacy": "model.legacy",
    "seed": "model.seed", "phases": "model.phases", "loads": "model.loads",
    "walls": "model.walls",
    "build": "geometry.build", "tessellate": "geometry.tessellate",
    "meshing": "geometry.meshing", "importer": "geometry.importer",
    "creator": "geometry.creator",
    "kratos": "kratos.export", "kratos_materials": "kratos.materials",
    "kratos_processes": "kratos.processes", "interfaces": "kratos.interfaces",
    "mdpa_import": "kratos.mdpa_import", "node_parts": "kratos.node_parts",
    "deck": "kratos.deck",
    "calculate": "run.calculate", "kratos_runner": "run.runner",
    "results": "results.runs", "gid_results": "results.gid",
    "result_fields": "results.fields", "result_mesh": "results.mesh",
    "result_parts": "results.parts", "result_members": "results.members",
}
"""Each module core held side by side, and where it went when core became packages."""

ADDED = {"kratos": {"files"}}
"""Modules a package has that no flat module became."""


def old_core_pattern() -> re.Pattern:
    """What a reference to a core module by its flat name looks like.

    * A dotted name: `core.schemas`, `-m core.kratos_runner`, `core.result_fields.x`.
      `kratos` and `results` are packages now, so `core.kratos` and `core.results` alone
      are fine, and so is a module in them (`core.kratos.export`); only an attribute of
      the old module is stale (`core.kratos.export_project`, `core.results.run_directory`).
    * A path to the file: `core/result_fields.py`, `core\\kratos.py`.
    * `from core import x` naming one of the flat modules.
    """
    flat = sorted((old for old in MOVED if old not in LAYERS), key=len, reverse=True)
    rules = [r"(?<![\w.])core\.(?:" + "|".join(flat) + r")(?!\w)"]
    for package in sorted(set(MOVED) & set(LAYERS)):
        inside = sorted({new.split(".")[1] for new in MOVED.values()
                         if new.startswith(package + ".")} | ADDED.get(package, set()))
        rules.append(rf"(?<![\w.])core\.{package}\.(?!(?:" + "|".join(inside) + r")(?!\w))\w")
    rules.append(r"(?<!\w)core[\\/](?:" + "|".join(sorted(MOVED, key=len, reverse=True))
                 + r")\.py(?!\w)")
    rules.append(r"(?<![\w.])from\s+core\s+import\s+(?:\w+(?:\s+as\s+\w+)?\s*,\s*)*(?:"
                 + "|".join(sorted(MOVED, key=len, reverse=True)) + r")(?!\w)")
    return re.compile("|".join(rules))


def test_the_old_core_pattern_finds_flat_names_and_leaves_the_packages_alone():
    stale = old_core_pattern()
    for line in [
        "from core.schemas import Project",
        "    from core.result_fields import field",
        "from core import calculate",
        "from core import gmsh_worker, kratos_materials",
        "from core import seed as s",
        "[\"-m\", \"core.kratos_runner\", \"ProjectParameters.json\"]",
        "see core/result_fields.py",
        "(core/kratos.py:_interface_by_body)",
        "core\\results.py",
        "`core.kratos.export_project`",
        "read by `core.results.run_directory`",
        "{\"where\": \"core.units / the whole deck\"}",
        "__import__(\"core.units\", fromlist=[\"units\"])",
        "# Generated from core/units.py",
    ]:
        assert stale.search(line), line
    for line in [
        "from core.model.schemas import Project",
        "from core.kratos import export as kratos",
        "from core.results import fields as result_fields",
        "from core import gmsh_worker",
        "from core import script",
        "-m core.run.runner",
        "the core.kratos package",
        "is in core.kratos.",
        "core.kratos.export.export_project",
        "core.kratos.files.PARAMETERS_NAME",
        "core.results.runs.run_directory",
        "see core/kratos/export.py and core/results/",
        "core/gmsh_worker.py",
        "core.model.units",
        "frontend/js/kratos.js",
        "server.core.units",
        "score.units",
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


def lines_matching(pattern: re.Pattern) -> list[str]:
    """`file:line: text` for each line of the next commit's text files that `pattern`
    finds something in."""
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
                  if pattern.search(line)]
    return found


def shown(found: list[str], most: int = 60) -> str:
    more = f"\n... and {len(found) - most} more" if len(found) > most else ""
    return "\n".join(found[:most]) + more


def test_nothing_points_into_the_old_folders_or_the_old_package():
    found = lines_matching(stale_pattern(module_names()))
    assert not found, f"{len(found)} references from before the move:\n{shown(found)}"


def test_no_core_module_is_named_by_its_flat_name():
    found = lines_matching(old_core_pattern())
    assert not found, f"{len(found)} references to core's flat modules:\n{shown(found)}"


RENAMED = sorted(old for old, new in MOVED.items() if new.split(".")[1] != old)
"""The flat modules whose own name did not survive the move: `kratos` is `export` now,
`results` is `runs`, `kratos_runner` is `runner`. A file that imports one under its old
name (`from core.kratos import export as kratos`) may go on calling it that; anywhere
else the old name is a module that is gone."""

NOT_ATTRIBUTES = ("py", "js", "json", "log", "yml", "local", "post", "res", "md")
"""What follows `kratos.` or `results.` in a file name rather than a module's attribute:
`kratos.log`, `kratos.local.json`, `results.js`, `results.post.res`."""

PROSE = {tokenize.COMMENT, tokenize.STRING} | (
    {tokenize.FSTRING_MIDDLE} if hasattr(tokenize, "FSTRING_MIDDLE") else set())


def renamed_pattern() -> re.Pattern:
    """A renamed module, named in prose without its package: `kratos_runner`, or
    `kratos.X` / `results.X` with X an attribute -- those two alone are also words. A
    dotted name inside core (`core.kratos.export.X`) is not one, nor is a file name."""
    joined = [old for old in RENAMED if "_" in old]
    words = [old for old in RENAMED if "_" not in old]
    return re.compile(r"(?<![\w./\\-])(?:(" + "|".join(joined) + r")(?!\w)|("
                      + "|".join(words) + r")\.(?!(?:" + "|".join(NOT_ATTRIBUTES)
                      + r")\b)[A-Za-z_]\w*)")


def test_the_renamed_pattern_finds_old_names_and_leaves_words_and_files_alone():
    pattern = renamed_pattern()
    for line in [
        "how to read the markers `kratos_runner` prints",
        "(see kratos_processes' module docstring)",
        "the CRLF endings -- `kratos.LINE_END` --",
        "(`results.run_unit_system`)",
        "gid_results takes the last step",
    ]:
        assert pattern.search(line), line
    for line in [
        "written in `kratos.local.json`",
        "the log, kratos.log",
        ".github/workflows/kratos.yml",
        "frontend/js/results.js",
        "core.kratos.export.LINE_END",
        "core.results.runs.run_directory",
        "tests/test_kratos_runner.py",
        "and read the results. Then",
        "Kratos.Parameters(handle.read())",
    ]:
        assert not pattern.search(line), line


def renamed_names_in_prose() -> list[str]:
    """`file:line: name` for each renamed module a comment, docstring or string names,
    in a Python file that does not import it under that name. In JavaScript and Markdown
    only the joined names count: there `results.x` is as likely a variable."""
    pattern = renamed_pattern()
    found = []
    for name in repository_files():
        suffix = Path(name).suffix
        if name == THIS or name.startswith(SKIPPED) or suffix not in {".py", ".js", ".md"}:
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        if suffix == ".py":
            tree = ast.parse(text, filename=name)
            bound = {alias.asname or alias.name.split(".")[0] for node in ast.walk(tree)
                     if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
            spans = [(token.start[0], token.string) for token in
                     tokenize.generate_tokens(io.StringIO(text).readline)
                     if token.type in PROSE]
        else:
            bound = set()
            spans = list(enumerate(text.splitlines(), start=1))
        for first, span in spans:
            for match in pattern.finditer(span):
                module = match.group(1) or match.group(2)
                if module in bound or (suffix != ".py" and match.group(2)):
                    continue
                line = first + span.count("\n", 0, match.start())
                found.append(f"{name}:{line}: {match.group(0)}")
    return found


def test_no_file_names_a_renamed_module_it_does_not_import():
    """`old_core_pattern` finds `core.kratos_runner`; this finds `kratos_runner` alone,
    the way a docstring cites a neighbour, once the neighbour is called something else."""
    found = renamed_names_in_prose()
    assert not found, f"{len(found)} old module names in prose:\n{shown(found)}"


# ── Served from frontend/ only ──────────────────────────────────────────────

SERVED_URL = re.compile(r"[\"'(`](/(?:assets|vendor|css|js|live)/[^\"'()?#\s`$]+)")
"""A root-relative URL of one of the static mounts, as a page, a stylesheet or a script
names it. One built from a template (`${...}`) is left out: it names no single file."""


def static_mounts() -> dict[str, Path]:
    from fastapi.staticfiles import StaticFiles
    from starlette.routing import Mount

    from backend.main import app
    return {route.path: Path(route.app.directory).resolve() for route in app.routes
            if isinstance(route, Mount) and isinstance(route.app, StaticFiles)}


def served_file(url: str, mounts: dict[str, Path]) -> Path | None:
    prefix = max((p for p in mounts if url.startswith(p + "/")), key=len, default=None)
    return None if prefix is None else (mounts[prefix] / url[len(prefix) + 1:]).resolve()


def test_every_static_mount_is_inside_frontend():
    mounts = static_mounts()
    assert {"/css", "/js", "/assets", "/vendor", "/live"} <= set(mounts)
    outside = {path: str(folder) for path, folder in mounts.items()
               if not folder.is_relative_to(FRONTEND.resolve())}
    assert not outside, outside


def test_every_file_the_app_asks_for_is_in_frontend():
    """Each URL the page, the shell and the live layer name resolves, through the
    mounts, to a file that exists in `frontend/` -- whatever else sits at the root."""
    mounts = static_mounts()
    sources = [FRONTEND / "index.html", *sorted(FRONTEND.glob("base/*/*.*")),
               *sorted(FRONTEND.glob("js/*.js")), *sorted(FRONTEND.glob("css/*.css"))]
    asked, missing = 0, []
    for source in sources:
        for url in SERVED_URL.findall(source.read_text(encoding="utf-8")):
            asked += 1
            file = served_file(url, mounts)
            if file is None or not file.is_file() or not file.is_relative_to(FRONTEND.resolve()):
                missing.append(f"{source.relative_to(ROOT).as_posix()}: {url}")
    assert asked > 40, asked
    assert not missing, "\n".join(missing)


def test_the_js_test_page_loads_only_from_frontend():
    page = FRONTEND / "tests" / "index.html"
    named = re.findall(r'(?:src|href)="([^"]+)"', page.read_text(encoding="utf-8"))
    assert len(named) > 40, len(named)
    wrong = [ref for ref in named if "://" not in ref and not (
        (page.parent / ref).resolve().is_file()
        and (page.parent / ref).resolve().is_relative_to(FRONTEND.resolve()))]
    assert not wrong, wrong
