"""What a calculation left behind, found again.

`app.calculate` writes a run into a directory of its own and then forgets it: the route
returns the path, the command log prints it, and that is the last the application knows
about it. This module is the other half -- it walks `calculate.runs_root()` and describes
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
    `kratos_processes.stage_name` and hoping the two agree. The rebuild survives only as
    the fallback for a deck that cannot be read.
*   **This module serves files the caller names.** It is the first place in the project
    that does, so `file_path` is deliberately narrow: one flat directory, one plain
    filename, no separators of either kind, checked again after resolution. See
    `UnsafeName`.

Nothing here parses a result. Finding the files is this milestone; reading them is the
next one (`plan/postprocessing-plan.md`, P1).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path, PureWindowsPath

from app import calculate

RUN_NAME = re.compile(
    r"^(?P<deck>.+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<hour>\d{2})-(?P<minute>\d{2})"
    r"(?:_(?P<repeat>\d+))?$")
"""A run directory's name, as `calculate.new_run_directory` builds it: the deck, the
minute it started, and -- for the second run inside one minute -- a counter.

`deck` is greedy on purpose. A deck may itself end in something that looks like a date,
and the stamp is always last, so the *rightmost* match is the right split."""

STAGE_NUMBER = re.compile(r"^(\d+)_")
"""The index `kratos_processes.stage_name` puts in front of every stage name. Stages are
ordered by it in the fallback path, because the filenames themselves sort lexically and
that puts a ten-stage deck's stage 10 between 1 and 2."""

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
    root = calculate.runs_root()
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


def _summary(directory: Path, match: re.Match) -> dict:
    """The listing row for one run: what it is, when, how big, and how far it got.

    Deliberately cheap -- one directory walk, `st_size`, and nothing opened. "How far
    it got" is the number of stages that wrote results, which is a count of filenames;
    *whether that is all of them* needs the deck's execution list, and *why it stopped*
    needs the log, so both of those wait for `describe` and one run at a time. A
    listing that parsed a 150 KB deck and a 180 KB log per run would make opening the
    list cost more than opening a run.
    """
    files = _files(directory)
    return {
        "id": directory.name,
        "deck": match["deck"],
        "started": f"{match['date']}T{match['hour']}:{match['minute']}",
        "repeat": int(match["repeat"] or 1),
        "results": sum(1 for entry in files
                       if entry["name"].endswith(RESULTS_SUFFIX)),
        "files": len(files),
        "bytes": sum(entry["bytes"] for entry in files),
    }


def run_directory(run_id: str) -> Path:
    """The directory `run_id` names, or `UnknownRun`.

    The name is matched against `RUN_NAME` before it is used as a path component, which
    is what makes `..` and an absolute path impossible rather than merely unlikely --
    neither can match a pattern that ends in a timestamp.
    """
    if not RUN_NAME.match(run_id or ""):
        raise UnknownRun(f"{run_id!r} is not a run.")
    directory = calculate.runs_root() / run_id
    if not directory.is_dir():
        raise UnknownRun(f"There is no run called {run_id!r}.")
    return directory


# ── Describing one ──────────────────────────────────────────────────────────

def describe(run_id: str) -> dict:
    """One run in full: its stages, its files, and whether it finished."""
    directory = run_directory(run_id)
    match = RUN_NAME.match(run_id)
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
        "failed_at": failed,
        "log": calculate.LOG_NAME if (directory / calculate.LOG_NAME).is_file() else None,
    }


def failed_at(directory: Path) -> dict | None:
    """The stage this run died in, read off the log it left.

    `calculate.failed_stage` is imported rather than reimplemented: it already knows
    how to read the markers `kratos_runner` prints, including that they arrive
    interleaved with Kratos' own C++ output. The only difference here is where the text
    comes from -- a file on disk instead of a subprocess' pipe -- which is what lets a
    run from last week still say where it stopped.
    """
    log = directory / calculate.LOG_NAME
    if not log.is_file():
        return None
    stage = calculate.failed_stage(log.read_text(encoding="utf-8", errors="replace"))
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


def _stages_from_deck(directory: Path) -> list[tuple[str, str]]:
    """`(stage name, output base name)` per stage, from `ProjectParameters.json`.

    Every lookup is defensive. This file is written by us, but the directory it sits in
    is not owned by anyone: it can be a deck from an older exporter, truncated, or
    edited by hand after the fact, and none of those should take the listing down.
    """
    try:
        deck = json.loads((directory / calculate.PARAMETERS_NAME)
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


def _gid_output_name(stage: object) -> str | None:
    """The base name the GiD writer was handed, which is what its files are called.

    Our own decks give it the stage's `problem_name`, so the two never differed until a
    deck written elsewhere was run (`app.deck`): there they can, and the file on disk is
    named by this one. Only the last path component, because a run directory is flat --
    `deck.stage` cuts any directory off before the run.
    """
    try:
        processes = stage["stage_settings"]["output_processes"]["gid_output"]
        name = processes[0]["Parameters"]["output_name"]
    except (KeyError, IndexError, TypeError):
        return None
    return PureWindowsPath(name).name if isinstance(name, str) and name else None


def _stages_from_files(directory: Path) -> list[tuple[str, str]]:
    """The fallback: every `*.post.res` in the directory, ordered by stage number.

    A stage's output is named `<deck>_<index>_<phase>`, and the deck name is the one
    thing here that is not recoverable from the file alone -- so the stage name is
    taken to start at the first `<digits>_` group, which is what `stage_name` writes
    and no deck name produced by `calculate.new_run_directory` can contain.
    """
    found = []
    for path in directory.glob(f"*{RESULTS_SUFFIX}"):
        base = path.name[:-len(RESULTS_SUFFIX)]
        match = re.search(r"_(\d+_.*)$", base)
        if match:
            found.append((int(STAGE_NUMBER.match(match[1])[1]), match[1], base))
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


def file_path(run_id: str, name: str) -> Path:
    """One file of one run, by name.

    A run directory is flat -- `calculate` writes into it and Kratos writes beside that
    -- so a legal name here is a plain filename and nothing else. That is checked
    directly rather than by resolving and comparing, because the two platforms disagree
    about what a separator is: `..\\x` is one path component on Linux and two on
    Windows, and a check that relies on `Path` would refuse it on one and admit it on
    the other. Both separators are rejected on both, and the resolved path is checked
    against the run directory afterwards anyway.
    """
    directory = run_directory(run_id)
    if (not name or name in {".", ".."}
            or "/" in name or "\\" in name
            or PureWindowsPath(name).drive):
        raise UnsafeName(f"{name!r} is not a file in this run.")
    path = directory / name
    if path.resolve().parent != directory.resolve():
        raise UnsafeName(f"{name!r} is not a file in this run.")
    if not path.is_file():
        raise UnknownRun(f"{run_id!r} has no file called {name!r}.")
    return path


# ── Reading one stage ───────────────────────────────────────────────────────

_cache: dict[tuple, object] = {}
"""Parsed files, keyed by path and what the filesystem says about it.

A stage is half a megabyte of ASCII and the viewer asks for one field at a time, so
without this every change of field on the same stage would re-parse the same two files.
The key carries size and mtime, so a run that is overwritten -- which `calculate` never
does, but a user copying files in might -- is re-read rather than served stale.

Bounded by throwing the whole thing away rather than by evicting the oldest: the working
set is one stage, occasionally two while a comparison is being made, and a cache that
needs an eviction policy here would be a cache that is the wrong size.
"""

CACHE_LIMIT = 8


def _parsed(path: Path, parse):
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size, parse.__name__)
    if key not in _cache:
        if len(_cache) >= CACHE_LIMIT:
            _cache.clear()
        _cache[key] = parse(path.read_text(encoding="utf-8", errors="replace"))
    return _cache[key]


def forget_cache() -> None:
    """Drop everything parsed. For tests, and for a caller that knows better."""
    _cache.clear()


def stage_record(run_id: str, index: int) -> dict:
    """One stage of one run, by its 1-based position in the execution list."""
    stages = stage_list(run_directory(run_id))
    for stage in stages:
        if stage["index"] == index:
            return stage
    raise UnknownRun(f"{run_id!r} has no stage {index}; it has {len(stages)}.")


def stage_mesh(run_id: str, index: int):
    from app import gid_results

    stage = stage_record(run_id, index)
    if not stage["mesh_file"]:
        raise UnknownRun(f"Stage {index} of {run_id!r} wrote no mesh file.")
    return _parsed(run_directory(run_id) / stage["mesh_file"], gid_results.read_mesh)


def stage_results(run_id: str, index: int):
    from app import gid_results

    stage = stage_record(run_id, index)
    if not stage["results_file"]:
        raise UnknownRun(
            f"Stage {index} of {run_id!r} wrote no results. "
            "The run stopped before reaching it, or is still going.")
    return _parsed(run_directory(run_id) / stage["results_file"],
                   gid_results.read_results)


def stage_geometry(run_id: str, index: int) -> dict:
    """This stage's mesh as buffers the viewport can draw and colour.

    The deck is read for the part names and element classes -- neither is in the GiD
    mesh, where a beam and an interface are both `Linear` and every block is called
    `Kratos_Triangle2D6_Mesh_2`. Both files are cached, so switching stage costs one
    parse and switching field costs none.
    """
    from app import mdpa_import, result_mesh

    directory = run_directory(run_id)
    deck = next((path for path in directory.glob("*.mdpa")), None)
    if deck is None:
        raise UnknownRun(f"{run_id!r} has no .mdpa, so its mesh cannot be named.")
    return result_mesh.stage_sections(_parsed(deck, mdpa_import.import_mdpa),
                                      stage_mesh(run_id, index))


def stage_fields(run_id: str, index: int) -> dict:
    """The field menu for one stage, derived from what that stage actually wrote."""
    from app import result_fields

    stage = stage_record(run_id, index)
    return {"stage": stage,
            "groups": result_fields.catalogue(stage_results(run_id, index))}


def stage_field(run_id: str, index: int, name: str, location: str = "nodes") -> dict:
    """One field of one stage: the ids it is defined on, the numbers, and the range."""
    from app import result_fields

    return result_fields.values(stage_results(run_id, index),
                                stage_mesh(run_id, index), name, location)


def stage_displacement(run_id: str, index: int) -> dict:
    """The displacement vectors of one stage -- what a deformed mesh is drawn with."""
    from app import result_fields

    return result_fields.displacement(stage_results(run_id, index))


def stage_at_node(run_id: str, index: int, node: int) -> dict:
    """Every field of one stage, at one node -- what `results at <id>` prints."""
    from app import result_fields

    return result_fields.at_node(stage_results(run_id, index),
                                 stage_mesh(run_id, index), node)


def stage_parts(run_id: str, index: int) -> dict:
    """The named parts of the deck as this stage saw them.

    `written` is filled in, which costs reading every stage's mesh once -- the only way
    to tell a part this phase removed from one the GiD writer never emits at all (see
    `app.result_parts`). They are cached, and the alternative is the postprocessor
    reporting the interfaces as having been demolished seven times.
    """
    from app import gid_results, mdpa_import, result_parts

    directory = run_directory(run_id)
    deck = next((path for path in directory.glob("*.mdpa")), None)
    if deck is None:
        raise UnknownRun(f"{run_id!r} has no .mdpa, so its parts cannot be named.")
    model = _parsed(deck, mdpa_import.import_mdpa)

    meshes = [_parsed(directory / stage["mesh_file"], gid_results.read_mesh)
              for stage in stage_list(directory) if stage["mesh_file"]]
    written = result_parts.written_parts(model, meshes)

    parts = result_parts.stage_parts(model, stage_mesh(run_id, index), written=written)
    return {"parts": [
        {"name": part.name, "kind": part.kind, "declared": part.declared,
         "nodes": part.nodes, "elements": len(part.elements),
         "alive": part.alive, "written": part.written}
        for part in parts]}


def archive(run_id: str) -> io.BytesIO:
    """The whole run directory as one zip, in memory.

    In memory because a run is a few megabytes of text that compresses to a fraction of
    that, and because a temporary file here would be one more thing on disk that
    nothing cleans up -- the complaint this module exists to answer.
    """
    directory = run_directory(run_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
        for path in sorted(directory.iterdir()):
            if path.is_file():
                out.write(path, arcname=path.name)
    buffer.seek(0)
    return buffer
