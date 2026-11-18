"""`run` and `calculate`: a Kratos deck through Kratos.

`run` takes a deck directory -- one `export` wrote, or anyone's -- and runs it in a copy
of its own under the runs root (plan D11), so the deck stays as it was and the GUI's
Results mode sees the run. `calculate` is `export` and `run` in one step, as the GUI's
Calculate button is. Either way it is `core.analysis.calculation` that runs it, with this
machine's Kratos (`kratos.local.json`, or `KRATOS_GUI_PYTHON` and `KRATOS_GUI_KRATOS`).

Ctrl+C stops the run, as the GUI's Stop button does: Kratos is killed, and the run
directory keeps what the stages that finished wrote.

`--follow` prints each solver iteration on stderr while Kratos works, read off the
growing log the way the GUI's convergence window reads it (`core.results.convergence`).
stdout, and so `--json`, stays the answer alone.
"""

from __future__ import annotations

import argparse
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from cli.commands.meshing import exported
from cli.terminal import tables
from cli.terminal.files import add_project, add_runs_dir, environment, read
from cli.terminal.output import Answer, CommandError
from core.analysis import calculation
from core.kratos import deck_files, external_deck
from core.results import convergence

FOLLOW_SECONDS = 0.25
"""How often `--follow` reads the log."""


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
    parser.add_argument("--follow", action="store_true",
                        help="print each solver iteration on stderr while Kratos runs")


def run_deck(args: argparse.Namespace) -> Answer:
    if args.deck.is_file():
        directory, parameters = args.deck.parent, args.deck.name
    elif args.deck.is_dir():
        directory, parameters = args.deck, deck_files.PARAMETERS_NAME
    else:
        raise CommandError(f"no such deck: {args.deck}")
    deck = external_deck.deck_project(directory, parameters).deck
    with environment(args), _following(args.follow):
        result = calculation.run_deck(deck)
    return _ran(result)


def calculate_model(args: argparse.Namespace) -> Answer:
    project = read(args)
    if project.deck is not None:
        with environment(args), _following(args.follow):
            return _ran(calculation.run_deck(project.deck))
    export = exported(project)
    with environment(args), _following(args.follow):
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
    if result.get("stopped"):
        lines = [f"run {run} stopped by the user{where}; what it wrote is in "
                 f"{result['directory']}"]
        return Answer(data=data, lines=lines, warnings=warnings or [], notes=notes or [],
                      error=result.get("error") or calculation.STOPPED_NOTE + ".")
    lines = [f"run {run} stopped{where}; Kratos' own output is in "
             f"{Path(result['directory']) / result['log']}"]
    return Answer(data=data, lines=lines, warnings=warnings or [], notes=notes or [],
                  error=result.get("error") or "Kratos did not finish the run.")


# ── --follow ────────────────────────────────────────────────────────────────

@contextmanager
def _following(enabled: bool):
    """While the block runs, print the run's new iterations on stderr."""
    if not enabled:
        yield
        return
    follower = Follower()
    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(FOLLOW_SECONDS):
            follower.look()

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        follower.look(final=True)


class Follower:
    """What `--follow` has printed so far, and what it prints next.

    Each look reads the whole log again: 5 ms for the largest log measured, and the
    same reading the GUI's window does. A line per new stage, per new iteration and per
    cut-back or iteration limit.

    The newest iteration waits for one more look before it is printed: Kratos prints
    "Convergence is achieved" on the line after the residuals, and the line may not be
    in the log yet.
    """

    def __init__(self, write=None) -> None:
        self.write = write or (lambda line: print(line, file=sys.stderr, flush=True))
        self.directory: Path | None = None
        self.iterations = 0
        self.events = 0
        self.stage: tuple | None = None
        self.seen = 0

    def look(self, final: bool = False) -> None:
        current = calculation.current_run()
        if current is not None and current != self.directory:
            self.directory, self.iterations, self.events, self.stage = current, 0, 0, None
            self.seen = 0
        if self.directory is None:
            return
        data = convergence.read_log(self.directory / calculation.LOG_NAME,
                                    growing=current is not None and not final)
        count = len(data["iterations"])
        # Print the newest one only when it was already there at the last look.
        ready = count if final or count == self.seen else count - 1
        self.seen = count
        for at in range(self.iterations, ready):
            self._stage(data, at)
            iteration = data["iterations"][at]
            self.write(f"  iteration {at + 1}: relative "
                       f"{_shown(iteration['relative'])} (target "
                       f"{_shown(iteration['relative_target'])}), absolute "
                       f"{_shown(iteration['absolute'])} (target "
                       f"{_shown(iteration['absolute_target'])})"
                       + ("  met" if iteration["met"] else ""))
            for event in data["events"][self.events:]:
                if event["at"] > at + 1:
                    break
                self.write(f"  {convergence.event_text(event)}")
                self.events += 1
        self.iterations = max(self.iterations, ready)
        for event in data["events"][self.events:]:
            if event["at"] > self.iterations:
                break
            self.write(f"  {convergence.event_text(event)}")
            self.events += 1
        # A stage that has begun and not printed an iteration yet: said at once, so a
        # long preparation is not read as nothing happening.
        if data["stage"] is not None and not data["stage"]["ended"]:
            self._announce((data["stage"]["index"], data["stage"]["of"],
                            data["stage"]["name"]))

    def _stage(self, data: dict, at: int) -> None:
        found = None
        for stage in data["stages"]:
            if stage["at"] <= at:
                found = stage
        if found is not None:
            self._announce((found["index"], found["of"], found["name"]))

    def _announce(self, stage: tuple) -> None:
        if stage == self.stage:
            return
        self.stage = stage
        index, total, name = stage
        words = (name or "").split("_", 1)[-1].replace("_", " ") if name else ""
        self.write(f"stage {index}" + (f" of {total}" if total else "")
                   + (f": {words}" if words else ""))


def _shown(value) -> str:
    return value if isinstance(value, str) else tables.shown(value)
