"""`run` and `calculate`: a Kratos deck through Kratos.

`run` takes a deck directory -- one `export` wrote, or anyone's -- and runs it in a copy
of its own under the runs root (plan D11), so the deck stays as it was and the GUI's
Results mode sees the run. `calculate` is `export` and `run` in one step, as the GUI's
Calculate button is. Either way it is `core.analysis.calculation` that runs it, with this
machine's Kratos (`kratos.local.json`, or `KRATOS_GUI_PYTHON` and `KRATOS_GUI_KRATOS`).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands.meshing import exported
from cli.terminal.files import add_project, add_runs_dir, environment, read
from cli.terminal.output import Answer, CommandError
from core.analysis import calculation
from core.kratos import deck_files, external_deck


def register(commands, common: argparse.ArgumentParser) -> None:
    run = commands.add_parser(
        "run", parents=[common], help="run a Kratos deck directory",
        description="Run the Kratos deck in DECK (a directory, or its "
                    f"{deck_files.PARAMETERS_NAME}) in a copy under the runs root.")
    run.add_argument("deck", type=Path, help="the deck's directory, or its parameters file")
    _run_options(run)
    run.set_defaults(handler=run_deck)

    calculate = commands.add_parser(
        "calculate", parents=[common], help="export the model's deck and run it",
        description="Mesh the model, write its deck into a run directory, and run it.")
    add_project(calculate)
    _run_options(calculate)
    calculate.set_defaults(handler=calculate_model)


def _run_options(parser: argparse.ArgumentParser) -> None:
    add_runs_dir(parser)
    parser.add_argument("--timeout", type=float, metavar="SECONDS",
                        help="give the run up after this long (default: "
                             "$KRATOS_GUI_TIMEOUT, or an hour)")


def run_deck(args: argparse.Namespace) -> Answer:
    if args.deck.is_file():
        directory, parameters = args.deck.parent, args.deck.name
    elif args.deck.is_dir():
        directory, parameters = args.deck, deck_files.PARAMETERS_NAME
    else:
        raise CommandError(f"no such deck: {args.deck}")
    deck = external_deck.deck_project(directory, parameters).deck
    with environment(args):
        result = calculation.run_deck(deck)
    return _ran(result)


def calculate_model(args: argparse.Namespace) -> Answer:
    project = read(args)
    if project.deck is not None:
        with environment(args):
            return _ran(calculation.run_deck(project.deck))
    export = exported(project)
    with environment(args):
        result = calculation.run(export)
    return _ran(result | {"stats": export["stats"]}, warnings=export["warnings"],
                notes=export.get("notes", []))


def _ran(result: dict, warnings: list[str] | None = None,
         notes: list[str] | None = None) -> Answer:
    run = Path(result["directory"]).name
    data = result | {"run": run}
    if result["ok"]:
        lines = [f"run {run} finished in {result['seconds']:g} s: "
                 f"{len(result['outputs'])} files in {result['directory']}",
                 f"next: kratos-cli results show {run}"]
        return Answer(data=data, lines=lines, warnings=warnings or [], notes=notes or [])
    stage = result.get("stage")
    where = f" in stage {stage['index']} of {stage['of']} ({stage['name']})" if stage else ""
    lines = [f"run {run} stopped{where}; Kratos' own output is in "
             f"{Path(result['directory']) / result['log']}"]
    return Answer(data=data, lines=lines, warnings=warnings or [], notes=notes or [],
                  error=result.get("error") or "Kratos did not finish the run.")
