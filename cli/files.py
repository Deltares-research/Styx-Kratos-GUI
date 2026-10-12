"""The project file a command reads, and where an edited model is written.

An edit is written back to the file it was read from (plan D8). `--out` writes it
somewhere else instead and leaves the original as it was; `--dry-run` makes the edit,
validates it, says what it did, and writes nothing. A `.py` model script is read, never
written: an edit of one needs `--out` (plan D6).
"""

from __future__ import annotations

import argparse
import os
from contextlib import contextmanager
from pathlib import Path

from cli.output import CommandError
from core import session
from core.analysis import calculation
from core.model.schemas import Project


def add_project(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project", type=Path,
                        help="the project file (.json), or a model script (.py) to read")


def add_writing(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", type=Path, metavar="FILE",
                        help="write the edited model here instead of back into PROJECT")
    parser.add_argument("--dry-run", action="store_true",
                        help="make and check the edit, but write nothing")


def written(args: argparse.Namespace, project: Project) -> tuple[Path | None, str]:
    """Write `project` where the command line says, and the line that says where."""
    if args.dry_run:
        return None, "not written (--dry-run)"
    target = args.out or args.project
    if args.out is None and target.suffix.lower() == ".py":
        raise CommandError(
            f"{target.name} is a model script, which is read but never written. Give "
            "--out <file>.json to keep the edited model, or --dry-run to only check it.")
    session.save(project, target)
    return target, f"wrote {target}"


def add_runs_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runs-dir", type=Path, metavar="DIR",
                        help="where runs are kept (default: $KRATOS_GUI_RUNS, or "
                             "~/KratosGUI/runs, which the GUI reads too)")


@contextmanager
def environment(args: argparse.Namespace):
    """The run settings given on the command line, for the length of the command.

    `core.analysis.calculation` reads them from the environment at the moment it runs,
    which is what lets a settings change take without a restart; set here and put back
    after, so a command run in-process (the tests) leaves nothing behind.
    """
    values = {}
    if getattr(args, "runs_dir", None) is not None:
        values[calculation.RUNS_ENV] = str(args.runs_dir.resolve())
    if getattr(args, "timeout", None) is not None:
        values[calculation.TIMEOUT_ENV] = str(args.timeout)
    saved = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
