"""Build the open model by running a Python file.

The modeller's command line takes `run <file.py>`, and this is what that runs. The file
is ordinary Python that hands back a `Project`; the server executes it, adopts what it
returns and the model appears in the viewport. `examples/crow/crow.py` is one, and is the worked
example to copy. `examples/eemdijk/eemdijk.py` is the other kind: it builds nothing, and
names a finished Kratos deck instead (`app.deck.deck_project`), which opens with its own
mesh and is calculated as the files it already is.

A script says what it built in one of three ways, looked for in this order:

1.  a module-level `PROJECT`;
2.  a zero-argument `project()`;
3.  any other zero-argument function whose name ends in `_project` -- which is what lets
    `examples/crow/crow.py` be run as it stands, off its own `crow_project()`.

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

import runpy
from pathlib import Path

from app.schemas import Project

SEARCH_ROOTS = ("", "..")
"""Where a relative path is resolved from, in order: the process' working directory --
the server's own, which `app.launcher` sets to `server/` -- and then the repository root
above it.

The root is searched because a model script belongs to the project rather than to the
server's own directory. `examples/crow/crow.py` is how that path reads everywhere else,
and typing `run ../examples/crow/crow.py` to reach it would only be explicable to
somebody who already knew where the server was started from. Nearest first, so a file
beside the server still wins.

The caller may also give an absolute path, which is what the command line does after
the browser has resolved it."""


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
    try:
        namespace = runpy.run_path(str(resolved))
    except ModuleNotFoundError as failure:
        # By far the most common way a script from elsewhere fails here: it was written
        # against a package this environment does not have. Say which one, because the
        # bare message names the import and not the reason it matters.
        raise ScriptError(
            f"{resolved.name} needs the Python package {failure.name!r}, which is not "
            f"installed in the server's environment. A script run here may import only "
            f"what this server can (`app.schemas` and the standard library are always "
            f"available); see examples/crow/crow.py for one that does."
        ) from failure
    except Exception as failure:                       # noqa: BLE001 - reported, not swallowed
        raise ScriptError(
            f"{resolved.name} failed while running: "
            f"{type(failure).__name__}: {failure}"
        ) from failure

    project = _find_project(namespace)
    if project is None:
        raise ScriptError(
            f"{resolved.name} ran, but describes no model. It has to leave a Project "
            f"behind: either a module-level PROJECT, or a function project() -- or any "
            f"name ending in _project -- that takes no arguments and returns one. "
            f"examples/crow/crow.py is a worked example."
        )
    return project


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


def _find_project(namespace: dict) -> Project | None:
    """The three conventions in this module's docstring, in order.

    A builder that raises is not silently skipped on the way to trying the next one:
    a script whose `project()` is broken should report *that*, not "describes no model",
    which would send the reader looking for a naming mistake they did not make.
    """
    direct = namespace.get("PROJECT")
    if isinstance(direct, Project):
        return direct

    # Only functions the script itself defines. A script that does
    # `from app.seed import seed_project` has imported a name ending in `_project` that
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
                f"{getattr(builder, '__name__', 'the builder')}() failed: "
                f"{type(failure).__name__}: {failure}"
            ) from failure
        except Exception as failure:                   # noqa: BLE001 - reported, not swallowed
            raise ScriptError(
                f"{getattr(builder, '__name__', 'the builder')}() failed: "
                f"{type(failure).__name__}: {failure}"
            ) from failure
        if isinstance(built, Project):
            return built

    for value in namespace.values():
        if isinstance(value, Project):
            return value
    return None
