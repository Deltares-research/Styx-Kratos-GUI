"""What a calculation left behind, found again.

`core.analysis.calculation` writes a run into a directory of its own and then forgets it: the route
returns the path, the command log prints it, and that is the last the application knows
about it. This module is the other half -- it walks `calculation.runs_root()` and describes
what is there, so a run can be opened again a week later, from a different session, of a
server that has been restarted since.

Three things shape it:

*   **A run directory is whatever is on disk, not what this code expects.** The oldest
    run on a machine was written by a version of the exporter that no longer exists, and
    nothing ever cleans up, so a directory may be truncated, hand-edited, or missing its
    deck entirely. Every reader here has a fallback and none of them raises on a
    directory it does not recognise -- the run is described as far as it can be and the
    gaps are reported as gaps.
*   **The deck names its own output.** Each stage's `problem_name` in
    `ProjectParameters.json` is exactly the base name the GiD writer was given, so the
    output files are found by asking the deck rather than by rebuilding a filename from
    `core.kratos.parameters.stage_name` and hoping the two agree. The rebuild survives only as
    the fallback for a deck that cannot be read.
*   **This module serves files the caller names.** It is the first place in the project
    that does, so `file_path` is deliberately narrow: one flat directory, one plain
    filename, no separators of either kind, checked again after resolution. See
    `UnsafeName`.
*   **A run is named one of two ways** (`Run`). A `str` is a run id: one directory
    directly under the runs root, which is what a URL carries and all the routes ever
    pass, so `run_directory`'s checks stand between a request and the disk. A `Path` is
    a run directory wherever it is -- copied off another machine, or run in its own deck
    folder -- which is what `kratos-cli results` reads (`plan/active/cli-plan.md` D12).
    A `str` is never read as a path.

Nothing here parses a result. Finding the files is this milestone; reading them is the
next one (`plan/active/postprocessing-plan.md`, P1).
"""

from __future__ import annotations

import io
import json
import re
import threading
import zipfile
from collections import OrderedDict
from pathlib import Path, PureWindowsPath
from typing import Any

from core.kratos import deck_files
from core.analysis import calculation

RUN_NAME = re.compile(
    r"^(?P<deck>.+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<hour>\d{2})-(?P<minute>\d{2})"
    r"(?:_(?P<repeat>\d+))?$")
"""A run directory's name, as `calculation.new_run_directory` builds it: the deck, the
minute it started, and -- for the second run inside one minute -- a counter.

`deck` is greedy on purpose. A deck may itself end in something that looks like a date,
and the stamp is always last, so the *rightmost* match is the right split."""

STAGE_NUMBER = re.compile(r"^(\d+)_")
"""The index `core.kratos.parameters.stage_name` puts in front of every stage name. Stages are
ordered by it in the fallback path, because the filenames themselves sort lexically and
that puts a ten-stage deck's stage 10 between 1 and 2."""

Run = str | Path
"""A run id, or a run directory: see the module docstring."""

RESULTS_SUFFIX = ".post.res"
MESH_SUFFIX = ".post.msh"


class ResultsError(Exception):
    """Something was asked for that this run cannot answer. Surfaced as 4xx."""


class UnknownRun(ResultsError):
    """No such run, no such file in it, or a run id that is not one."""


class UnsafeName(ResultsError):
    """A filename that tried to leave the run directory.

    Its own class, and refused before anything is opened rather than being allowed to
    fail as a missing file: a traversal that happens to name something real would
    otherwise succeed, and the difference between the two is the whole point.
    """


# ── Finding runs ────────────────────────────────────────────────────────────

def runs() -> list[dict]:
    """Every run on this machine, newest first.

    Ordered by the stamp in the directory's own name rather than by mtime: a run's
    files keep being touched -- copied, opened, synced -- long after it finished, and
    the name is what the user reads in the listing anyway.
    """
    root = calculation.runs_root()
    if not root.is_dir():
        # A machine that has never calculated has no runs directory. That is the
        # normal state of a fresh checkout, not a fault to report.
        return []
    found = []
    for path in root.iterdir():
        match = RUN_NAME.match(path.name) if path.is_dir() else None
        if match:
            found.append(_summary(path, match))
    return sorted(found, key=lambda run: (run["started"], run["repeat"]), reverse=True)


def _summary(directory: Path, match: re.Match | None) -> dict:
    """The listing row for one run: what it is, when, how big, and how far it got.

    Without a `match` -- a directory not named the way `calculation` names a run, read
    by its path -- the deck is the one its `.mdpa` names, and when it started is unknown.

    Deliberately cheap -- one directory walk, `st_size`, and nothing opened. "How far
    it got" is the number of stages that wrote results, which is a count of filenames;
    *whether that is all of them* needs the deck's execution list, and *why it stopped*
    needs the log, so both of those wait for `describe` and one run at a time. A
    listing that parsed a 150 KB deck and a 180 KB log per run would make opening the
    list cost more than opening a run.
    """
    files = _files(directory)
    if match is None:
        mdpa = next((entry["name"] for entry in files if entry["name"].endswith(".mdpa")),
                    None)
        deck, started, repeat = (mdpa[:-len(".mdpa")] if mdpa else directory.name), None, 1
    else:
        deck = match["deck"]
        started = f"{match['date']}T{match['hour']}:{match['minute']}"
        repeat = int(match["repeat"] or 1)
    return {
        "id": directory.name,
        "deck": deck,
        "started": started,
        "repeat": repeat,
        "results": sum(1 for entry in files
                       if entry["name"].endswith(RESULTS_SUFFIX)),
        "files": len(files),
        "bytes": sum(entry["bytes"] for entry in files),
    }


def run_directory(run_id: str) -> Path:
    """The directory `run_id` names, or `UnknownRun`.

    Matching `RUN_NAME` is not enough on its own: its `deck` group is `.+`, so
    `..\\secret_2026-01-01_00-00` matches, and on Windows that backslash is a separator.
    A run id is one directory name directly under the runs root and nothing else, so
    both separators are refused outright -- the same rule `file_path` applies, for the
    same reason. Without one it is a single component, and ending in a timestamp it
    cannot be `..` itself, so a deck called `model..v2` keeps its runs. The resolved
    directory is checked against the runs root afterwards anyway.
    """
    if (not RUN_NAME.match(run_id or "")
            or "/" in run_id or "\\" in run_id
            or PureWindowsPath(run_id).drive):
        raise UnknownRun(f"{run_id!r} is not a run.")
    root = calculation.runs_root()
    directory = root / run_id
    if directory.resolve().parent != root.resolve():
        raise UnknownRun(f"{run_id!r} is not a run.")
    if not directory.is_dir():
        raise UnknownRun(f"There is no run called {run_id!r}.")
    return directory

def directory_of(run: Run) -> Path:
    """The directory `run` names: a run id under the runs root (`run_directory`), or a
    `Path` to a run directory anywhere. See this module's docstring."""
    if isinstance(run, Path):
        if not run.is_dir():
            raise UnknownRun(f"There is no run directory {run}.")
        return run
    return run_directory(run)


def _named(run: Run) -> str:
    """A run as a message names it: its id quoted, or its directory."""
    return str(run) if isinstance(run, Path) else repr(run)


# ── Describing one ──────────────────────────────────────────────────────────

def run_unit_system(run: Run) -> str:
    """The unit system a run's numbers are in: what its deck recorded beside it
    (`deck_files.UNITS_NAME`), or SI for a run without the record -- a deck case, or a
    run older than the unit system, both of which are SI decks."""
    from core.model import units

    path = directory_of(run) / deck_files.UNITS_NAME
    try:
        system = json.loads(path.read_text(encoding="utf-8")).get("unit_system")
    except (OSError, ValueError, AttributeError):
        return units.DEFAULT
    return system if system in units.SYSTEMS else units.DEFAULT


def describe(run: Run) -> dict:
    """One run in full: its stages, its files, and whether it finished."""
    directory = directory_of(run)
    match = RUN_NAME.match(directory.name)
    stages = stage_list(directory)
    failed = failed_at(directory)
    return {
        **_summary(directory, match),
        "stages": stages,
        "files": _files(directory),
        # "Every stage wrote its results" rather than "the log looks happy": a log
        # says what Kratos said, and the files say what is there to look at. The
        # second is the question a postprocessor is actually asking.
        "complete": bool(stages) and all(stage["results"] for stage in stages),
        "unit_system": run_unit_system(run),
        "failed_at": failed,
        "log": calculation.LOG_NAME if (directory / calculation.LOG_NAME).is_file() else None,
    }


def failed_at(directory: Path) -> dict | None:
    """The stage this run died in, read off the log it left.

    `calculation.failed_stage` is imported rather than reimplemented: it already knows
    how to read the markers `core.analysis.kratos_main` prints, including that they arrive
    interleaved with Kratos' own C++ output. The only difference here is where the text
    comes from -- a file on disk instead of a subprocess' pipe -- which is what lets a
    run from last week still say where it stopped.
    """
    log = directory / calculation.LOG_NAME
    if not log.is_file():
        return None
    stage = calculation.failed_stage(log.read_text(encoding="utf-8", errors="replace"))
    if stage is None:
        return None
    index, total, name = stage
    return {"index": index, "of": total, "name": name}


def stage_list(directory: Path) -> list[dict]:
    """The run's stages, in run order, each with the output files it wrote.

    The deck is asked first: its `execution_list` is already ordered, and its
    `problem_name` per stage is the exact base name the GiD writer was handed. A deck
    that cannot be read falls back to the output files themselves.
    """
    stages = _stages_from_deck(directory) or _stages_from_files(directory)
    return [_stage(directory, index, name, base)
            for index, (name, base) in enumerate(stages, start=1)]


def _stages_from_deck(directory: Path) -> list[tuple[str, str | None]]:
    """`(stage name, output base name)` per stage, from `ProjectParameters.json`.

    Every lookup is defensive. This file is written by us, but the directory it sits in
    is not owned by anyone: it can be a deck from an older exporter, truncated, or
    edited by hand after the fact, and none of those should take the listing down.
    """
    try:
        deck = json.loads((directory / deck_files.PARAMETERS_NAME)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(deck, dict):
        return []
    settings = deck.get("orchestrator", {})
    order = settings.get("settings", {}).get("execution_list", []) \
        if isinstance(settings, dict) else []
    if not isinstance(order, list):
        return []

    stages = deck.get("stages", {})
    out = []
    for name in order:
        if not isinstance(name, str):
            continue
        stage = stages.get(name, {}) if isinstance(stages, dict) else {}
        base = _gid_output_name(stage) or ((stage.get("stage_settings", {})
                                            .get("problem_data", {})
                                            .get("problem_name"))
                                           if isinstance(stage, dict) else None)
        out.append((name, base if isinstance(base, str) and base else None))
    return out


def _gid_output_name(stage: Any) -> str | None:
    """The base name the GiD writer was handed, which is what its files are called.

    Our own decks give it the stage's `problem_name`, so the two never differed until a
    deck written elsewhere was run (`core.kratos.external_deck`): there they can, and the file on disk is
    named by this one. Only the last path component, because a run directory is flat --
    `external_deck.stage` cuts any directory off before the run.
    """
    try:
        processes = stage["stage_settings"]["output_processes"]["gid_output"]
        name = processes[0]["Parameters"]["output_name"]
    except (KeyError, IndexError, TypeError):
        return None
    return PureWindowsPath(name).name if isinstance(name, str) and name else None


def _stages_from_files(directory: Path) -> list[tuple[str, str | None]]:
    """The fallback: every `*.post.res` in the directory, ordered by stage number.

    A stage's output is named `<deck>_<index>_<phase>`, and the deck name is the one
    thing here that is not recoverable from the file alone -- so the stage name is
    taken to start at the first `<digits>_` group, which is what `stage_name` writes
    and no deck name produced by `calculation.new_run_directory` can contain.
    """
    found = []
    for path in directory.glob(f"*{RESULTS_SUFFIX}"):
        base = path.name[:-len(RESULTS_SUFFIX)]
        match = re.search(r"_((\d+)_.*)$", base)
        if match:
            found.append((int(match[2]), match[1], base))
    return [(name, base) for _, name, base in sorted(found)]


def _stage(directory: Path, index: int, name: str, base: str | None) -> dict:
    """One stage row. `base` is the deck's own `problem_name`; without it the output
    files are found by looking for a name ending in this stage's name, which is what a
    deck too old or too broken to read leaves us with."""
    if base is None:
        base = _base_for(directory, name)
    mesh = (directory / f"{base}{MESH_SUFFIX}") if base else None
    res = (directory / f"{base}{RESULTS_SUFFIX}") if base else None
    return {
        "index": index,
        "name": name,
        # The phase as the user typed it, as far as `stage_name` left it recoverable:
        # it replaced every run of non-alphanumerics with one underscore, so the
        # spaces come back and nothing else does.
        "phase": STAGE_NUMBER.sub("", name).replace("_", " "),
        "base": base,
        "mesh_file": mesh.name if mesh and mesh.is_file() else None,
        "results_file": res.name if res and res.is_file() else None,
        "results": bool(res and res.is_file()),
        "json": sorted(path.name for path in directory.glob(f"{name}__*.json")),
    }


def _base_for(directory: Path, name: str) -> str | None:
    for path in directory.glob(f"*_{name}{RESULTS_SUFFIX}"):
        return path.name[:-len(RESULTS_SUFFIX)]
    return None


# ── Files ───────────────────────────────────────────────────────────────────

def _files(directory: Path) -> list[dict]:
    entries = []
    for path in sorted(directory.iterdir()):
        if path.is_file():
            entries.append({"name": path.name, "bytes": path.stat().st_size})
    return entries


def file_path(run: Run, name: str) -> Path:
    """One file of one run, by name.

    A run directory is flat -- `calculation` writes into it and Kratos writes beside that
    -- so a legal name here is a plain filename and nothing else. That is checked
    directly rather than by resolving and comparing, because the two platforms disagree
    about what a separator is: `..\\x` is one path component on Linux and two on
    Windows, and a check that relies on `Path` would refuse it on one and admit it on
    the other. Both separators are rejected on both, and the resolved path is checked
    against the run directory afterwards anyway.
    """
    directory = directory_of(run)
    if (not name or name in {".", ".."}
            or "/" in name or "\\" in name
            or PureWindowsPath(name).drive):
        raise UnsafeName(f"{name!r} is not a file in this run.")
    path = directory / name
    if path.resolve().parent != directory.resolve():
        raise UnsafeName(f"{name!r} is not a file in this run.")
    if not path.is_file():
        raise UnknownRun(f"{_named(run)} has no file called {name!r}.")
    return path


# ── Reading one stage ───────────────────────────────────────────────────────

_cache: OrderedDict[tuple, object] = OrderedDict()
"""Parsed files, keyed by path and what the filesystem says about it, least recently
used first.

A stage is half a megabyte to several of ASCII and the viewer asks for one field at a
time, so without this every change of field would re-parse the same files. The key
carries size and mtime, so a run that is overwritten -- which `calculation` never does,
but a user copying files in might -- is re-read rather than served stale.

The working set is a whole run, not one stage: `stage_parts` reads every stage's mesh
(see there), so a 20-stage run is the deck, twenty meshes and whichever results files are
being looked at. It used to be capped at 8 entries and cleared whole, which a 7-stage run
overflowed on every phase switch. Now it is bounded by the size of what it parsed
(`CACHE_BYTES`), dropping the least recently used first.
"""

CACHE_BYTES = 96 * 2**20
"""Budget in bytes of *source file*. A 20-stage dike run is ~13 MB of meshes and ~4 MB
per stage of results, so this holds a run's meshes and a dozen stages of results; the
parsed objects are a few times larger than their text."""

_cache_lock = threading.Lock()
"""The routes run on worker threads (they are plain `def` so parsing stays off the event
loop), so two requests can reach the cache at once."""


def _parsed(path: Path, parse):
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size, parse.__name__)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    # Parsed outside the lock: a slow stage must not hold up a request for another one.
    # Two requests for the same new file may both parse it; the second simply wins.
    value = parse(path.read_text(encoding="utf-8", errors="replace"))
    with _cache_lock:
        _cache[key] = value
        _cache.move_to_end(key)
        while len(_cache) > 1 and sum(k[2] for k in _cache) > CACHE_BYTES:
            _cache.popitem(last=False)
    return value


def forget_cache() -> None:
    """Drop everything parsed. For tests, and for a caller that knows better."""
    with _cache_lock:
        _cache.clear()


def stage_record(run: Run, index: int) -> dict:
    """One stage of one run, by its 1-based position in the execution list."""
    stages = stage_list(directory_of(run))
    for stage in stages:
        if stage["index"] == index:
            return stage
    raise UnknownRun(f"{_named(run)} has no stage {index}; it has {len(stages)}.")


def stage_mesh(run: Run, index: int):
    from core.results import gid_reader

    stage = stage_record(run, index)
    if not stage["mesh_file"]:
        raise UnknownRun(f"Stage {index} of {_named(run)} wrote no mesh file.")
    return _parsed(directory_of(run) / stage["mesh_file"], gid_reader.read_mesh)


def stage_results(run: Run, index: int):
    from core.results import gid_reader

    stage = stage_record(run, index)
    if not stage["results_file"]:
        raise UnknownRun(
            f"Stage {index} of {_named(run)} wrote no results. "
            "The run stopped before reaching it, or is still going.")
    return _parsed(directory_of(run) / stage["results_file"],
                   gid_reader.read_results)


def stage_geometry(run: Run, index: int) -> dict:
    """This stage's mesh as buffers the viewport can draw and colour.

    The deck is read for the part names and element classes -- neither is in the GiD
    mesh, where a beam and an interface are both `Linear` and every block is called
    `Kratos_Triangle2D6_Mesh_2`. Both files are cached, so switching stage costs one
    parse and switching field costs none.
    """
    from core.kratos import mdpa_reader
    from core.results import mesh

    directory = directory_of(run)
    deck = next((path for path in directory.glob("*.mdpa")), None)
    if deck is None:
        raise UnknownRun(f"{_named(run)} has no .mdpa, so its mesh cannot be named.")
    return mesh.stage_sections(_parsed(deck, mdpa_reader.import_mdpa),
                                      stage_mesh(run, index))


def stage_fields(run: Run, index: int) -> dict:
    """The field menu for one stage, derived from what that stage actually wrote."""
    from core.results import fields

    stage = stage_record(run, index)
    return {"stage": stage,
            "groups": fields.catalogue(stage_results(run, index),
                                              run_unit_system(run))}


def stage_field(run: Run, index: int, name: str, location: str = "nodes") -> dict:
    """One field of one stage: the ids it is defined on, the numbers, and the range."""
    from core.results import fields

    return fields.values(stage_results(run, index),
                                stage_mesh(run, index), name, location,
                                run_unit_system(run))


def stage_displacement(run: Run, index: int) -> dict:
    """The displacement vectors of one stage -- what a deformed mesh is drawn with."""
    from core.results import fields

    return fields.displacement(stage_results(run, index))


def stage_at_node(run: Run, index: int, node: int) -> dict:
    """Every field of one stage, at one node -- what `results at <id>` prints."""
    from core.results import fields

    return fields.at_node(stage_results(run, index),
                                 stage_mesh(run, index), node, run_unit_system(run))


def stage_parts(run: Run, index: int) -> dict:
    """The named parts of the deck as this stage saw them.

    `written` is filled in, which costs reading every stage's mesh once -- the only way
    to tell a part this phase removed from one the GiD writer never emits at all (see
    `core.results.parts`). They are cached, and the alternative is the postprocessor
    reporting the interfaces as having been demolished seven times.
    """
    from core.kratos import mdpa_reader
    from core.results import gid_reader, parts

    directory = directory_of(run)
    deck = next((path for path in directory.glob("*.mdpa")), None)
    if deck is None:
        raise UnknownRun(f"{_named(run)} has no .mdpa, so its parts cannot be named.")
    model = _parsed(deck, mdpa_reader.import_mdpa)

    meshes = [_parsed(directory / stage["mesh_file"], gid_reader.read_mesh)
              for stage in stage_list(directory) if stage["mesh_file"]]
    written = parts.written_parts(model, meshes)

    staged = parts.stage_parts(model, stage_mesh(run, index), written=written)
    return {"parts": [
        {"name": part.name, "kind": part.kind, "declared": part.declared,
         "nodes": part.nodes, "elements": len(part.elements),
         "alive": part.alive, "written": part.written}
        for part in staged]}


# ── Structural members ──────────────────────────────────────────────────────

def _member_files(run: Run) -> dict[str, list[tuple[dict, Path]]]:
    """{member: [(stage row, its json_output file), ...]}, in stage order."""
    from core.results import members

    directory = directory_of(run)
    found: dict[str, list[tuple[dict, Path]]] = {}
    for stage in stage_list(directory):
        for filename in stage["json"]:
            member = members.member_name(filename, stage["name"])
            if member:
                found.setdefault(member, []).append((stage, directory / filename))
    return found


def _member_output(path: Path) -> dict:
    from core.results import members

    return _parsed(path, members.read_output)


def stage_members(run: Run) -> dict:
    """The members this run wrote curves for, the stages each has, and what each offers.

    Read off the files rather than the deck: a member is plottable because its output is
    there, and a quantity is offered because the file carries it.
    """
    from core.results import members

    listed = []
    for name, found in sorted(_member_files(run).items()):
        outputs = [_member_output(path) for _, path in found]
        listed.append({
            "name": name,
            "stages": [stage["index"] for stage, _ in found],
            "quantities": [entry.summary(run_unit_system(run))
                           for entry in members.available(outputs)],
        })
    return {"members": listed}


def member_profiles(run: Run, member: str, quantity: str) -> dict:
    """One quantity along one member, a panel per stage that wrote it.

    The y of each node comes from the run's own `.mdpa`, undeformed -- the level on the
    wall, which is what the vertical axis of this plot means.
    """
    from core.kratos import mdpa_reader
    from core.results import members

    files = _member_files(run)
    if member not in files:
        raise UnknownRun(f"{_named(run)} wrote no output for a member called {member!r}; "
                         f"it has {', '.join(sorted(files)) or 'none'}.")
    entry = members.quantity(quantity)
    outputs = [(stage, _member_output(path)) for stage, path in files[member]]
    if entry not in members.available(output for _, output in outputs):
        raise members.UnknownQuantity(
            f"The {member} output carries no {entry.label.lower()} ({quantity}).")

    directory = directory_of(run)
    deck = next((path for path in directory.glob("*.mdpa")), None)
    if deck is None:
        raise UnknownRun(f"{_named(run)} has no .mdpa, so its members cannot be placed.")
    coordinates = _parsed(deck, mdpa_reader.import_mdpa).nodes

    return {
        "member": member,
        "quantity": entry.name,
        "label": entry.label,
        "unit": entry.unit(run_unit_system(run)),
        "stages": [{"index": stage["index"], "name": stage["name"],
                    "phase": stage["phase"]}
                   | members.profile(output, coordinates, entry)
                   for stage, output in outputs],
    }


def archive(run: Run) -> io.BytesIO:
    """The whole run directory as one zip, in memory.

    In memory because a run is a few megabytes of text that compresses to a fraction of
    that, and because a temporary file here would be one more thing on disk that
    nothing cleans up -- the complaint this module exists to answer.
    """
    directory = directory_of(run)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for path in sorted(directory.iterdir()):
            if path.is_file():
                out.write(path, arcname=path.name)
    buffer.seek(0)
    return buffer
