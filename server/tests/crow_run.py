"""The committed CROW run, expanded into something the application can read.

`tests/fixtures/crow_run/` holds a real calculation, distilled and gzipped
(`make_crow_fixture.py`). Nothing in `app` knows about gzip -- the registry walks a
directory, the parser reads text -- so the fixture is expanded once per session into a
temporary directory whose name is a run id, and `runs_root()` can then be pointed at its
parent. What the code under test sees is a run directory, indistinguishable from one a
calculation wrote a week ago, which is the only way these tests say anything.

Two entry points, and the difference matters:

*   `run_directory()` -- the committed two-stage fixture. Always available, so tests that
    use it never skip.
*   `whole_run()` -- all seven stages of GiD output, which are 2.5 MB and are not
    committed. Found through `$CROW_RUN`, or as the newest complete CROW run under the
    runs root, and **skips** when there is none. Only the sequence-level assertions need
    it.
"""

from __future__ import annotations

import atexit
import functools
import gzip
import json
import os
import pathlib
import shutil
import tempfile

import pytest

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "crow_run"
RUN_FILES = FIXTURE / "run"
EXPECTED_WALL = FIXTURE / "expected_wall"
EXPECTED_MEMBERS = FIXTURE / "expected_members"
"""Kratos' own CROW run along the wall and its interface, per stage, keyed by y -- the
orange line of Kratos' comparison plots. See `make_crow_fixture.write_expected_members`."""

MEMBER_STAGES = ["3_SheetPileWall_installation", "4_First_excavation",
                 "5_Strut_installation", "6_Second_excavation", "7_Third_excavation"]
"""Every stage with a wall, and so with member output committed for it."""

RUN_ID = "CROW_excavation_wall_2026-09-22_16-28"
"""The expanded directory's name. It has to parse as a run id (`results.RUN_NAME`), and
it is the id the fixture was made from -- so a failure names the run somebody can go and
look at rather than a temporary path that will not exist by the time they read it."""

DECK_NAME = "CROW_excavation_wall"
WALL_PART = "SheetPileWall"

STAGES = ["1_Initial_stage", "2_Null_step", "3_SheetPileWall_installation",
          "4_First_excavation", "5_Strut_installation", "6_Second_excavation",
          "7_Third_excavation"]
"""The seven stages, in execution order, as the deck names them."""

GID_STAGES = ["1_Initial_stage", "7_Third_excavation"]
"""The two whose `.post.msh`/`.post.res` are committed."""

WALL_OUTPUT_STAGES = ["3_SheetPileWall_installation", "4_First_excavation",
                      "6_Second_excavation", "7_Third_excavation"]
"""The four whose member output is committed -- the four Kratos' own validation checks."""


@functools.cache
def manifest() -> dict:
    return json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))


@functools.cache
def runs_root() -> pathlib.Path:
    """A directory holding the expanded fixture run, as `calculate.runs_root()` would.

    Expanded once per session and removed at exit. Cached rather than made a pytest
    fixture so that a test can ask for it from anywhere without threading a fixture
    through, and so the ~2 MB of text is expanded once however many modules use it.
    """
    root = pathlib.Path(tempfile.mkdtemp(prefix="crow-fixture-"))
    atexit.register(shutil.rmtree, root, True)

    run = root / RUN_ID
    run.mkdir()
    for source in sorted(RUN_FILES.iterdir()):
        if source.suffix == ".gz":
            (run / source.stem).write_bytes(gzip.decompress(source.read_bytes()))
        else:
            shutil.copyfile(source, run / source.name)
    return root


def run_directory() -> pathlib.Path:
    return runs_root() / RUN_ID


def use_fixture_runs(monkeypatch) -> pathlib.Path:
    """Point `calculate.runs_root()` at the fixture, and return the run directory.

    Through the environment variable rather than by patching the function, because that
    is what a user has, and a test that patched the function would not notice if the
    variable stopped being read.
    """
    from app import calculate, results

    monkeypatch.setenv(calculate.RUNS_ENV, str(runs_root()))
    results.forget_cache()
    return run_directory()


def deck_text() -> str:
    """The run's own `.mdpa`, as text."""
    return (run_directory() / f"{DECK_NAME}.mdpa").read_text(encoding="utf-8")


def member_output(stage: str, member: str = "wall") -> dict:
    """One `<stage>__output_<member>.json`, as Kratos' json_output process wrote it."""
    path = run_directory() / f"{stage}__output_{member}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── The whole run, when it is on this machine ───────────────────────────────

def _complete(directory: pathlib.Path) -> bool:
    return all((directory / f"{DECK_NAME}_{stage}.post.res").exists()
               for stage in STAGES)


def _machine_runs_root() -> pathlib.Path:
    """Where this machine keeps its runs, read once at import.

    Read here rather than when it is wanted, because the tests that want it have
    already pointed `$KRATOS_GUI_RUNS` at the expanded fixture -- asking then would find
    the fixture, decide the whole run is missing, and skip on every machine including
    the ones that have it.
    """
    from app import calculate

    return calculate.runs_root()


MACHINE_RUNS = _machine_runs_root()


@functools.cache
def _whole_run() -> pathlib.Path | None:
    named = os.environ.get("CROW_RUN")
    if named:
        directory = pathlib.Path(named)
        return directory if _complete(directory) else None

    root = MACHINE_RUNS
    if not root.is_dir():
        return None
    candidates = sorted(path for path in root.glob(f"{DECK_NAME}_*")
                        if path.is_dir() and _complete(path))
    return candidates[-1] if candidates else None


def whole_run() -> pathlib.Path:
    """A run directory with all seven stages of GiD output, or skip.

    Not committed: the five middle stages are 2.5 MB of text that say nothing the two
    committed ones do not, except in the handful of cases that are *about* the sequence.
    """
    directory = _whole_run()
    if directory is None:
        pytest.skip("no complete CROW run on this machine; set $CROW_RUN to one "
                    "(the committed fixture carries only stages 1 and 7)")
    return directory
