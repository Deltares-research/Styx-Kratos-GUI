"""Run an exported deck through Kratos and say where the results went.

The one thing that shapes this whole module: **Kratos does not run in this process.**
A Kratos build is a set of compiled extensions bound to the exact Python it was built
for -- 3.11 for the build this was developed against -- while the server runs on
whatever interpreter has FastAPI and gmsh in it. Those are, on a normal machine, two
different interpreters, and no amount of `sys.path` makes one import the other's DLLs.
So a calculation is a *subprocess*: a different python, given the deck's directory as
its working directory and `app.kratos_runner` to run (`app/kratos_runner.py`, which
imports nothing of the server).

That leaves the machine to say which interpreter, and where its Kratos is. Either can be
given as an environment variable or written in `server/kratos.local.json` (see
`SETTINGS_FILE`), and both are read fresh on every run, so a machine can be set up and
the button pressed again without restarting anything:

| Variable | `kratos.local.json` | What |
|---|---|---|
| `KRATOS_GUI_PYTHON` | `python` | The interpreter Kratos was built for. Defaults to this one, which is right only when the server itself can import Kratos. |
| `KRATOS_GUI_KRATOS` | `kratos` | The build directory -- the one holding `KratosMultiphysics/` and `libs/`, typically `<kratos>/bin/Release`. Left alone when the interpreter already finds Kratos on its own. |
| `KRATOS_GUI_RUNS` | | Where run directories are made. Defaults to `~/KratosGUI/runs`. |
| `KRATOS_GUI_TIMEOUT` | | Seconds before a run is given up on. Defaults to an hour. |

Each run gets a directory of its own, named after the deck and the minute it started,
holding the three input files, the log, and whatever Kratos wrote. Nothing is ever
overwritten and nothing is cleaned up: a result the user cannot find again is not a
result, and which of them are worth keeping is theirs to decide.

`run` is synchronous and blocking -- it is a subprocess and a wait. The route calls it
off the event loop (`asyncio.to_thread`), which is also what keeps the rest of the app
answering while a solver has the machine.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
import sys

PYTHON_ENV = "KRATOS_GUI_PYTHON"
KRATOS_ENV = "KRATOS_GUI_KRATOS"
RUNS_ENV = "KRATOS_GUI_RUNS"
TIMEOUT_ENV = "KRATOS_GUI_TIMEOUT"

SERVER = Path(__file__).resolve().parents[1]
"""The directory `app` lives in, put on the subprocess' PYTHONPATH: the interpreter that
runs Kratos has never heard of this project and could not import the runner otherwise."""

SETTINGS_FILE = SERVER / "kratos.local.json"
"""Where the same two settings can be written down instead of exported, as
`{"python": "...", "kratos": "..."}`. It exists because of how this server is started:
by double-clicking `run.bat`, which inherits no shell anyone set variables in, so a
machine configured through the environment is configured again every time. This file is
set once. It is machine-specific and git-ignored, the environment still wins over it,
and it is optional in every direction -- absent, empty or malformed, the run falls back
to this interpreter, which is right whenever the server itself can import Kratos."""

COMMAND = ["-m", "app.kratos_runner", "ProjectParameters.json"]
"""What the interpreter is asked to do, after its own path. A module rather than a file
path so it is read the same way wherever the server is installed."""

PARAMETERS_NAME = "ProjectParameters.json"
MATERIALS_NAME = "MaterialParameters.json"
INITIAL_MATERIALS_NAME = "initial_materials.json"
"""The K0 stage's own materials file. Written only when the deck has a stage that
reads it; the name matches `kratos_processes.INITIAL_MATERIALS_FILENAME`."""
LOG_NAME = "kratos.log"

# Imported rather than restated: `kratos_runner` prints these markers and this
# parses them, so there is one spelling in one place. Safe to import from here --
# the runner is a script that imports Kratos only inside `run()`, which is what
# lets the server read its constants without a Kratos build (see its docstring).
from app.kratos_runner import STAGE_MARKER

_STAGE_LINE = re.compile(
    re.escape(STAGE_MARKER) + r" (begin|end) (\d+)/(\d+) (.*?)\s*$", re.MULTILINE)
"""One stage marker.

The name runs to the end of the line because `Stage.name` comes from `Phase.name`,
which the user types and may well put a space in. Not anchored at the start,
because Kratos writes from C++ and from Python into the same pipe and the two
interleave -- a marker can arrive with someone else's half-line in front of it."""

DEFAULT_TIMEOUT = 3600.0

UNLOADABLE_KRATOS = ("Unable to find KratosCore", "No module named 'Kratos'")
MISSING_KRATOS = "No module named 'KratosMultiphysics'"

# Both messages name `SETTINGS_FILE`, so both are built when they are needed rather than
# at import: the file is what the reader has to go and edit, and a message carrying a
# stale copy of its path would send them to the wrong one.

UNLOADABLE_KRATOS_ADVICE = (
    "Kratos was found but could not be loaded: its python half imported and its "
    "compiled half did not. Nearly always the interpreter is the wrong version for the "
    "build -- check which Python the build was made for (its libs/ holds a file named "
    'like Kratos.cp311-win_amd64.pyd, so cp311 means Python 3.11) and point "python" '
    'in {settings} at one. The other cause is "kratos" naming a directory without '
    "libs/ beside KratosMultiphysics/."
)

MISSING_KRATOS_ADVICE = (
    "Kratos was not found by the interpreter that ran the deck. Write "
    '{{"python": "<python your Kratos build was made for>", "kratos": "<build '
    'directory holding KratosMultiphysics/ and libs/, usually ...\\bin\\Release>"}} '
    "into {settings} (or set {python_env} and {kratos_env}), then press Calculate "
    "again -- no restart needed. The deck itself was written and is still there."
)

_running = False
"""One calculation at a time. A solver takes the machine's cores and an unknown amount
of time, so a second press is refused with a message rather than queued invisibly
behind the first."""


class CalculationError(RuntimeError):
    """The calculation could not be started. Surfaced to the command log."""


class Busy(CalculationError):
    """A calculation is already running. Its own class so the route can answer 409 --
    try again later -- rather than 500, which reads as something being broken."""


# ── Where it happens ────────────────────────────────────────────────────────

def runs_root() -> Path:
    configured = os.environ.get(RUNS_ENV)
    return Path(configured) if configured else Path.home() / "KratosGUI" / "runs"


def new_run_directory(deck_name: str) -> Path:
    """A directory of this run's own, named for the deck and when it started.

    The minute is enough to tell two runs apart in a listing and short enough to read;
    the counter is for the second run within one minute, which is common enough while
    someone is trying something out.
    """
    root = runs_root()
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    candidate, suffix = root / f"{deck_name}_{stamp}", 2
    while candidate.exists():
        candidate, suffix = root / f"{deck_name}_{stamp}_{suffix}", suffix + 1
    candidate.mkdir(parents=True)
    return candidate


def write_deck(export: dict, directory: Path) -> list[str]:
    """The three files of the deck, written where Kratos will look for them.

    The .mdpa's name is not a choice made here: `app.kratos.deck_name` decided it, the
    parameters file already names it in `model_import_settings.input_filename`, and
    Kratos appends `.mdpa` to that. The other two are named by the parameters too -- the
    materials file by `material_import_settings`, and the parameters file by the command
    line -- so all three names come from one place and cannot drift apart.
    """
    name = export["deck_name"]
    written = [f"{name}.mdpa"]
    _write(directory / f"{name}.mdpa", export["mdpa"])
    if export.get("materials"):
        _write(directory / MATERIALS_NAME, export["materials"])
        written.append(MATERIALS_NAME)
    if export.get("initial_materials"):
        _write(directory / INITIAL_MATERIALS_NAME, export["initial_materials"])
        written.append(INITIAL_MATERIALS_NAME)
    _write(directory / PARAMETERS_NAME, export["project_parameters"])
    written.append(PARAMETERS_NAME)
    return written


def _write(path: Path, text: str) -> None:
    r"""Write `text` to `path` exactly as it is.

    `newline=""` is the whole of it, and it is not a style choice. `app.kratos` renders
    the deck with CRLF endings on purpose -- `kratos.LINE_END` -- so that what this
    exporter produces stays byte-comparable with the GiD-authored reference decks it is
    checked against. Writing that in Python's default text mode on Windows translates
    the "\n" of every one of those pairs a second time, and each line goes to disk as
    "\r\r\n".

    Kratos never complained, so seven real runs went green over a deck in that state.
    What did complain was this project: `app.mdpa_import` reads a file like that as
    blank-line-separated and used to fail outright on the first one, which meant the
    postprocessor could not open the .mdpa sitting beside the results it was reading.
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


# ── Who runs it ─────────────────────────────────────────────────────────────

def interpreter() -> tuple[str, dict[str, str]]:
    """The python that runs the deck, and the environment it runs in.

    A Kratos build is two halves that have to be found two different ways: the python
    packages under the build directory, which go on PYTHONPATH, and the DLLs they load
    from `libs` beside them, which go on PATH -- Windows resolves a native dependency
    off PATH, not off anything python controls. Setting one without the other fails
    halfway, importing `KratosMultiphysics` and then not finding `Kratos`.
    """
    settings = _settings()
    python = os.environ.get(PYTHON_ENV) or settings.get("python") or sys.executable
    if not Path(python).exists():
        raise CalculationError(
            f"The python to run Kratos with was given as {python}, which does not "
            f"exist. Correct it in {SETTINGS_FILE} or in {PYTHON_ENV}.")

    environment = dict(os.environ)
    paths = [str(SERVER)]
    build = os.environ.get(KRATOS_ENV) or settings.get("kratos")
    if build:
        paths.insert(0, build)
        environment["PATH"] = os.pathsep.join(
            [str(Path(build) / "libs"), environment.get("PATH", "")])
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(paths + ([existing] if existing else []))
    return python, environment


def _settings() -> dict:
    """`SETTINGS_FILE`, or an empty dict for every way it can fail to be one.

    Read on each run rather than at import, so the file can be written -- or corrected
    after a failed run said what was wrong with it -- and the button pressed again
    without restarting the server.
    """
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def timeout() -> float:
    try:
        return float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


# ── The run ─────────────────────────────────────────────────────────────────

def run(export: dict) -> dict:
    """Write `export` into a fresh directory and run it through Kratos.

    Returns what the command log needs to say what happened: whether it worked, the
    directory, the files that went in and the files that came out, and -- when it did
    not work -- the end of Kratos' own output, which is where its reason always is.
    A failed *analysis* is a result, not an exception: only a calculation that could not
    be started at all raises.
    """
    global _running
    if _running:
        raise Busy("A calculation is already running.")

    python, environment = interpreter()
    directory = new_run_directory(export["deck_name"])
    inputs = write_deck(export, directory)
    before = _contents(directory)

    _running = True
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [python, *COMMAND], cwd=directory, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", timeout=timeout(),
        )
        output, returncode = completed.stdout, completed.returncode
    except subprocess.TimeoutExpired as expired:
        output = (expired.output or "") + (
            f"\n\nGiven up on after {timeout():.0f} s. Raise {TIMEOUT_ENV} if the "
            "model is meant to take this long.")
        returncode = None
    finally:
        _running = False

    (directory / LOG_NAME).write_text(output, encoding="utf-8")
    stage = failed_stage(output)
    return {
        "ok": returncode == 0,
        "returncode": returncode,
        # Which stage the run died in, for the command log to name. Null on a run
        # that finished, and on one that never reached a stage at all.
        "stage": None if stage is None else
                 {"index": stage[0], "of": stage[1], "name": stage[2]},
        "seconds": round(time.monotonic() - started, 1),
        "directory": str(directory),
        "inputs": inputs,
        # Read by difference rather than by pattern: every writer Kratos can be asked
        # for -- GiD, VTK, a .lst index, a debug dump -- lands here, and a glob would
        # quietly leave out whichever one nobody thought of.
        "outputs": sorted(_contents(directory) - before - {LOG_NAME}),
        "log": LOG_NAME,
        "error": None if returncode == 0 else _explain(output, stage=stage),
    }


def failed_stage(output: str) -> tuple[int, int, str] | None:
    """The stage that started and never finished, as `(index, of, name)`.

    `None` when there is nothing to blame, which is three different situations and
    all three are right to stay quiet about: a deck with no markers at all (every
    one written before this existed), a run that died before the first stage was
    reached (Kratos missing, the mdpa unreadable), and a run whose every stage
    ended -- if the sequence finished, whatever went wrong afterwards is not a
    stage's fault and naming the last one would be a lie.
    """
    started: tuple[int, int, str] | None = None
    for event, index, total, name in _STAGE_LINE.findall(output):
        if event == "begin":
            started = (int(index), int(total), name)
        else:
            started = None
    return started


def _contents(directory: Path) -> set[str]:
    return {path.name for path in directory.iterdir()}


def _explain(output: str, lines: int = 30,
             stage: tuple[int, int, str] | None = None) -> str:
    """Why the run failed, as far as anything here can tell.

    Kratos puts its reason at the end -- the error line, then the C++ stack that raised
    it -- so the tail is what is worth carrying back. The two cases worth recognising
    are the ones where the deck was never read at all because Kratos is not where this
    was told to look, or is there and unloadable: both are configuration, neither says
    anything about the model, and an import traceback is the least useful possible way
    to learn either.
    """
    if MISSING_KRATOS in output:
        return MISSING_KRATOS_ADVICE.format(settings=SETTINGS_FILE,
                                            python_env=PYTHON_ENV, kratos_env=KRATOS_ENV)
    if any(marker in output for marker in UNLOADABLE_KRATOS):
        return UNLOADABLE_KRATOS_ADVICE.format(settings=SETTINGS_FILE)
    # The stage markers are scaffolding, not output. Left in, forty of them would
    # push Kratos' own reason off the end of the message they exist to improve.
    tail = [line for line in output.strip().splitlines()
            if line.strip() and STAGE_MARKER not in line][-lines:]
    reason = "\n".join(tail) or "Kratos exited without saying why; see the log."
    if stage is None:
        return reason
    # In front of the reason, not instead of it: where it failed and why are both
    # wanted, and Kratos is the only one that knows the second.
    index, total, name = stage
    return f"{name} (stage {index} of {total}) failed:\n{reason}"
