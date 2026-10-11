"""`results`: the runs on this machine, and what one of them left behind
(`core.results.catalog`, which the GUI's Results mode reads too).

`results runs` lists them newest first, numbered; `results show` takes a run's id or its
number in that listing -- nobody is going to retype `Pit_A_2026-10-12_09-14`.
"""

from __future__ import annotations

import argparse

from cli.files import add_runs_dir, environment
from cli.output import Answer, CommandError
from core.analysis import calculation
from core.results import catalog


def register(commands, common: argparse.ArgumentParser) -> None:
    results = commands.add_parser("results", parents=[common],
                                  help="list the runs, or show what one left behind")
    actions = results.add_subparsers(dest="action", metavar="<action>", required=True)

    runs = actions.add_parser("runs", parents=[common], help="the runs, newest first")
    add_runs_dir(runs)
    runs.set_defaults(handler=list_runs)

    show = actions.add_parser("show", parents=[common],
                              help="a run's stages, files and whether it finished")
    show.add_argument("run", help="the run's id, or its number in `results runs`")
    add_runs_dir(show)
    show.set_defaults(handler=show_run)


def list_runs(args: argparse.Namespace) -> Answer:
    with environment(args):
        runs = catalog.runs()
        root = calculation.runs_root()
    if not runs:
        return Answer(data=[], lines=[f"No runs yet in {root}. `kratos-cli calculate "
                                      "<project>` or `kratos-cli run <deck>` makes one."])
    lines = [f"{len(runs)} run{'s' if len(runs) != 1 else ''} in {root}:"]
    lines += [f"{number:>3}  {run['id']}  {run['results']} stage(s) with results, "
              f"{run['files']} files" for number, run in enumerate(runs, start=1)]
    return Answer(data=runs, lines=lines)


def show_run(args: argparse.Namespace) -> Answer:
    with environment(args):
        run = catalog.describe(_run_id(args.run))
    lines = [f"{run['id']}  (deck {run['deck']}, started {run['started']})",
             f"  {'complete' if run['complete'] else 'not complete'}, "
             f"{run['unit_system']} units, {len(run['files'])} files"]
    for stage in run["stages"]:
        lines.append(f"  {stage['index']:>3}  {stage['name']}  "
                     + ("results" if stage["results"] else "no results"))
    if run["failed_at"]:
        lines.append(f"  stopped at: {run['failed_at']}")
    return Answer(data=run, lines=lines)


def _run_id(given: str) -> str:
    """A run id, or a position in the listing. A run's id always ends in its date and
    time, so a bare number is never one."""
    if not given.isdigit():
        return given
    runs = catalog.runs()
    position = int(given)
    if not 1 <= position <= len(runs):
        raise CommandError(f"There is no run {position}: the listing has {len(runs)} "
                           f"run{'s' if len(runs) != 1 else ''}. `kratos-cli results runs` "
                           "lists them.")
    return runs[position - 1]["id"]
