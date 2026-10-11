"""Build the open model by running a Python file.

The modeller's command line takes `run <file.py>`, and this is what that runs. The file
is ordinary Python that hands back a `Project`; the server executes it, adopts what it
returns and the model appears in the viewport. `tests/models/excavation.py` is one. A
script of the other kind builds nothing, and names a finished Kratos deck instead (`core.kratos.external_deck.deck_project`), which opens with its own
mesh and is calculated as the files it already is.

A script says what it built in one of three ways, looked for in this order:

1.  a module-level `PROJECT`;
2.  a zero-argument `project()`;
3.  any other zero-argument function whose name ends in `_project` -- which is what lets
    `tests/models/excavation.py` be run as it stands, off its own
    `excavation_project()`.

Nothing else is called. In particular `main()` is left alone: a script written to be run
from a shell usually writes files there, and running a file to *look* at the model it
describes should not put anything on disk. For the same reason the file is executed
under `runpy`'s own module name rather than `"__main__"`, so an `if __name__ ==
"__main__":` block at the bottom does not fire.

**This executes the file.** That is the feature -- it is a scripting interface, the same
one every modeller of this kind has -- but it means `run` is exactly as dangerous as the
file it is pointed at, and the server runs with the user's own privileges. It is
reachable only from this machine's own UI (the app binds to 127.0.0.1 and has no auth,
because it is a single-user desktop-style tool), and it should stay that way: if this
server is ever exposed to a network, this route is the first thing that has to go.
"""

from __future__ import annotations

import contextlib
import runpy
import sys
from pathlib import Path

from core.model.schemas import Project

SEARCH_ROOTS = ("",)
"""Where a relative path is resolved from: the process' working directory, which
`backend.launcher` sets to the repository root. A model script belongs to the project,
and a path from the repository root is how it reads everywhere else, so `run
tests/models/excavation.py` names the same file here as in a shell at the root.

The caller may also give an absolute path, which is what the command line does after
the browser has resolved it."""


OWN_PACKAGES = ("core", "backend")
"""The server's own packages. A module of theirs is never forgotten after a run, even
one the script imported first: a script kept at the repository root sits above both
folders, so where a module's file is cannot be what decides it."""


class ScriptError(RuntimeError):
    """The file could not be run, or did not describe a model. Shown in the command log,
    so the message has to be the whole explanation -- there is no stack trace on screen."""


def load_project(path: str | Path, roots: tuple[str, ...] = SEARCH_ROOTS) -> Project:
    """Run `path` and return the `Project` it describes.

    Raises `ScriptError`, with a message meant to be read by whoever typed the command,
    for every failure this can distinguish: no such file, the file itself raising, and
    the file running fine but describing no model.
    """
    resolved = _resolve(path, roots)
    with _beside(resolved.parent):
        return _run(resolved)


def _run(resolved: Path) -> Project:
    try:
        namespace = runpy.run_path(str(resolved))
    except SystemExit as failure:
        raise _exited(resolved.name, failure) from failure
    except ModuleNotFoundError as failure:
        # By far the most common way a script from elsewhere fails here: it was written
        # against a package this environment does not have. Say which one, because the
        # bare message names the import and not the reason it matters.
        raise ScriptError(
            f"{resolved.name} needs the Python package {failure.name!r}, which is not "
            f"installed in the server's environment. A script run here may import only "
            f"what this server can (`core.model.schemas` and the standard library are always "
            f"available)."
        ) from failure
    except Exception as failure:                       # noqa: BLE001 - reported, not swallowed
        raise ScriptError(
            f"{resolved.name} failed while running{_line_in(failure, resolved)}: "
            f"{type(failure).__name__}: {failure}"
        ) from failure

    project, complaint = _find_project(namespace, resolved)
    if project is None:
        raise ScriptError(
            f"{resolved.name} ran, but describes no model"
            + (f" -- {complaint}" if complaint else "") + ". It has to leave a Project "
            "behind: either a module-level PROJECT, or a function project() -- or any "
            "name ending in _project -- that takes no arguments and returns one."
        )
    return project


@contextlib.contextmanager
def _beside(folder: Path):
    """Let the script import helper modules kept beside it, as `python model.py` would.

    The import path is put back exactly as it was, and helpers loaded from that folder
    are forgotten afterwards: `run` is edit-and-look-again, and a helper cached from the
    previous run would show the old model with nothing to say it is old. The server's
    own packages (`OWN_PACKAGES`) are never forgotten -- a second copy of them would
    mean two `Project` classes.
    """
    saved_path = list(sys.path)
    saved_bytecode = sys.dont_write_bytecode
    loaded = set(sys.modules)
    # A virtual environment may live beside the script (.venv-*); what is
    # installed there is a package, not a helper, and must stay imported.
    installed = {Path(p).resolve() for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)}
    sys.path.insert(0, str(folder))
    # No __pycache__ in the user's folder: looking at a model writes nothing, and a .pyc
    # from a run in the same second as an edit would be read instead of the edit.
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.path[:] = saved_path
        sys.dont_write_bytecode = saved_bytecode
        for name in set(sys.modules) - loaded:
            if name.partition(".")[0] in OWN_PACKAGES:
                continue
            file = getattr(sys.modules[name], "__file__", None)
            if not file:
                continue
            where = Path(file).resolve()
            if where.is_relative_to(folder) and not any(
                    where.is_relative_to(prefix) for prefix in installed):
                del sys.modules[name]


def _exited(name: str, failure: SystemExit) -> ScriptError:
    # SystemExit is not an Exception: uncaught, it would end the request -- or worse.
    # The usual cause is argparse or sys.exit() outside an `if __name__ == "__main__":`.
    return ScriptError(
        f"{name} exited ({failure.code!r}) instead of describing a model. Code that "
        f"parses arguments or calls sys.exit() belongs under "
        f"`if __name__ == \"__main__\":`, which is not run here."
    )


def _line_in(failure: BaseException, script: Path) -> str:
    """" at line N" for the deepest frame of the traceback that is in the script."""
    line = None
    trace = failure.__traceback__
    while trace is not None:
        if Path(trace.tb_frame.f_code.co_filename) == script:
            line = trace.tb_lineno
        trace = trace.tb_next
    return f" at line {line}" if line else ""


def _resolve(path: str | Path, roots: tuple[str, ...]) -> Path:
    candidate = Path(path).expanduser()
    options = ((candidate,) if candidate.is_absolute()
               else tuple(Path(root) / candidate for root in roots))
    for option in options:
        if option.is_file():
            return option.resolve()
    # Absolute in the message even when the caller gave a relative path: "looked in
    # nope.py" tells the reader nothing, and which directory a relative path is taken
    # from is exactly what they cannot see from the command line.
    where = ", ".join(str(option.resolve()) for option in options)
    raise ScriptError(f"no such file: {path} (looked for {where})")


def _find_project(namespace: dict, script: Path) -> tuple[Project | None, str | None]:
    """The three conventions in this module's docstring, in order, and -- when none of
    them yields a Project -- what the first one that was tried left instead.

    A builder that raises is not silently skipped on the way to trying the next one:
    a script whose `project()` is broken should report *that*, not "describes no model",
    which would send the reader looking for a naming mistake they did not make.
    """
    complaint = None
    direct = namespace.get("PROJECT")
    if isinstance(direct, Project):
        return direct, None
    if direct is not None:
        complaint = f"PROJECT is a {type(direct).__name__}, not a Project"

    # Only functions the script itself defines. A script that does
    # `from core.model.templates import seed_project` has imported a name ending in `_project` that
    # builds a perfectly good model -- the wrong one -- and without this it would win
    # over the script's own builder and quietly load the seed instead. `runpy` puts the
    # executed module's name in `__name__`, and a function defined there carries it.
    local = namespace.get("__name__")
    def defined_here(value: object) -> bool:
        return callable(value) and getattr(value, "__module__", None) == local

    builders = [namespace.get("project")] if defined_here(namespace.get("project")) else []
    builders += [value for name, value in namespace.items()
                 if name.endswith("_project") and name != "project"
                 and defined_here(value)]
    for builder in builders:
        if not callable(builder):
            continue
        try:
            built = builder()
        except TypeError as failure:
            # A `*_project` helper that takes arguments is not the entry point; one that
            # takes none and raises TypeError inside is, and has to be reported.
            if "positional argument" in str(failure) or "required" in str(failure):
                continue
            raise ScriptError(
                f"{getattr(builder, '__name__', 'the builder')}() failed"
                f"{_line_in(failure, script)}: {type(failure).__name__}: {failure}"
            ) from failure
        except SystemExit as failure:
            raise _exited(script.name, failure) from failure
        except Exception as failure:                   # noqa: BLE001 - reported, not swallowed
            raise ScriptError(
                f"{getattr(builder, '__name__', 'the builder')}() failed"
                f"{_line_in(failure, script)}: {type(failure).__name__}: {failure}"
            ) from failure
        if isinstance(built, Project):
            return built, None
        complaint = complaint or (f"{getattr(builder, '__name__', 'the builder')}() "
                                  f"returned a {type(built).__name__}, not a Project")

    for value in namespace.values():
        if isinstance(value, Project):
            return value, None
    return None, complaint
