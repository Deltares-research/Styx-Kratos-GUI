"""How the solver converged, read off a run's Kratos log.

Kratos prints one line per nonlinear iteration: the relative and the absolute residual,
and the target of each. This module reads those lines back, with the steps and stages
around them, into plain data that the GUI's convergence plot (`frontend/js/convergence-
plot.js`) and `kratos-cli results convergence` both use. The CSV both write is built
from that data on each side (`App.ConvergencePlot.csv` and
`cli.terminal.tables.convergence_csv`), held equal by `tests/test_convergence_parity.py`. It reads a finished log and a
log that is still growing (`core.analysis.calculation` writes each line as Kratos prints
it), so the plot can follow a run live.

The patterns are ported from the ConvergencePlotter in Deltares' FEA-Tools repository
(`MiscellaneousTools/ConvergencePlotter/kratos_log_parser.py`), with its test samples.
This port differs in five ways:

*   A stage marker of `core.analysis.kratos_main` that landed inside another line is
    taken out, and the two halves of the cut line are joined again. Logs written before
    Kratos' output was unbuffered (before 2026-11) have many of these; dropping the cut
    lines would lose iterations.
*   The stage names come from those markers. The Nth `begin` marker names the Nth
    `Analysis -START-`, because in the same old logs the two can be out of order.
*   Only complete lines are read from a growing log, so a half-written number is never
    read.
*   `nan` and `inf` are values, so a run that blows up shows it. They come back as the
    strings "nan", "inf" and "-inf", because JSON has no number for them.
*   It also reads the step cut-backs (`Down-scaling with factor`) and the steps that hit
    the iteration limit (`ATTENTION: max iterations`), which are what a user most wants
    to see.

One known limit, kept from the original: a deck with two convergence criteria prints two
lines per iteration, and both are counted as iterations. Decks written by this program
use one criterion.

Nothing here imports Kratos or the server.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from core.analysis import calculation
from core.analysis.kratos_main import STAGE_MARKER

_NUMBER = r"([-+]?(?:nan(?:\([a-z]*\))?|inf(?:inity)?|\d+\.?\d*(?:e[-+]?\d+)?|\.\d+(?:e[-+]?\d+)?))"

_ITERATION = (
    # GeoMechanics' residual criterion.
    re.compile(r"Obtained ratio = " + _NUMBER + r".*?Expected ratio = " + _NUMBER
               + r".*?Absolute norm = " + _NUMBER + r".*?Expected norm =\s*" + _NUMBER,
               re.IGNORECASE),
    # Kratos' displacement and water-pressure criteria.
    re.compile(r" ratio = " + _NUMBER + r".*?exp\.ratio = " + _NUMBER
               + r".*?abs = " + _NUMBER + r".*?exp\.abs =\s*" + _NUMBER, re.IGNORECASE),
)
_TIME = re.compile(r"\bTIME\s*:\s*" + _NUMBER, re.IGNORECASE)
_TIME_STEP_EXECUTOR = re.compile(r"Running time step at time\s*" + _NUMBER, re.IGNORECASE)
_CYCLE = re.compile(r"\bcycle:\s*(\d+)")
_CUT_BACK = re.compile(r"Down-scaling with factor:\s*" + _NUMBER, re.IGNORECASE)
_MAX_ITERATIONS = re.compile(r"ATTENTION: max iterations \(\s*(\d+)\s*\) exceeded")
_FRACTION = re.compile(r"Fraction of unbalance:\s*" + _NUMBER, re.IGNORECASE)
_MARKER = re.compile(re.escape(STAGE_MARKER) + r" (begin|end) (\d+)/(\d+) (.*?)\s*$")

NO_RESIDUALS = ("Kratos printed no residuals. Is the solver's echo_level 0 in this deck?")
"""What to say about a log with no iteration in it, once Kratos has started solving."""


def number(text: str) -> float | str:
    """A number as Kratos printed it: a float, or "nan", "inf" or "-inf".

    The C runtime prints a NaN as `nan`, `-nan` or `-nan(ind)`; all mean the same."""
    lowered = text.lower()
    if "nan" in lowered:
        return "nan"
    if "inf" in lowered:
        return "-inf" if lowered.startswith("-") else "inf"
    value = float(text)
    if math.isfinite(value):
        return value
    return "inf" if value > 0 else "-inf"


def repaired_lines(text: str, growing: bool = False) -> list[str]:
    """The log's lines, with every stage marker on a line of its own.

    A marker that landed inside a line cut that line in two: the first half is in front
    of the marker, and the second half is the next line that is not a marker. The
    halves are joined again. With `growing`, a last line with no newline is not read
    yet: Kratos may be in the middle of printing it.
    """
    lines = text.split("\n")
    if growing or (lines and lines[-1] == ""):
        lines.pop()  # the part after the last newline: empty, or not complete yet
    out: list[str] = []
    held = ""
    for line in lines:
        line = line.rstrip("\r")
        at = line.find(STAGE_MARKER)
        if at < 0:
            out.append(held + line)
            held = ""
        else:
            held += line[:at]
            out.append(line[at:])
    if held:
        out.append(held)
    return out


def parse(text: str, growing: bool = False) -> dict:
    """The convergence data of one Kratos log. See this module's docstring.

    Every `at` is a number of iterations: the step, stage, event or fraction comes
    after that many iterations of the whole run. So a stage with `at` 4 starts with the
    fifth iteration, and an event with `at` 50 belongs to the 50th.
    """
    iterations: list[dict] = []
    steps: list[dict] = []
    stage_starts: list[int] = []
    names: list[tuple[int, int, str]] = []
    events: list[dict] = []
    fractions: list[dict] = []
    cycle: int | None = None
    current: dict | None = None

    for line in repaired_lines(text, growing):
        marker = _MARKER.match(line)
        if marker:
            event, index, total, name = marker.groups()
            if event == "begin":
                names.append((int(index), int(total), name))
                current = {"index": int(index), "of": int(total), "name": name,
                           "ended": False}
            elif current is not None and current["index"] == int(index):
                current["ended"] = True
            continue

        for pattern in _ITERATION:
            found = pattern.search(line)
            if found:
                relative, relative_target, absolute, absolute_target = (
                    number(value) for value in found.groups())
                iterations.append({"relative": relative, "relative_target": relative_target,
                                   "absolute": absolute, "absolute_target": absolute_target,
                                   "met": False})
                break
        else:
            if "convergence is achieved" in line.lower():
                if iterations:
                    iterations[-1]["met"] = True
                continue
            if "Analysis -START-" in line or "About to run a stage" in line:
                stage_starts.append(len(iterations))
                continue
            found = _CYCLE.search(line)
            if found:
                cycle = int(found.group(1))
                continue
            found = _TIME_STEP_EXECUTOR.search(line) or (
                _TIME.search(line) if " TIME " in line else None)
            if found:
                time = number(found.group(1))
                steps.append({"at": len(iterations), "time": time, "cycle": cycle})
                cycle = None
                continue
            found = _CUT_BACK.search(line)
            if found:
                events.append({"at": len(iterations), "kind": "cut_back",
                               "factor": number(found.group(1))})
                continue
            found = _MAX_ITERATIONS.search(line)
            if found:
                events.append({"at": len(iterations), "kind": "max_iterations",
                               "limit": int(found.group(1))})
                continue
            found = _FRACTION.search(line)
            if found:
                fractions.append({"at": len(iterations), "value": number(found.group(1))})

    stages = []
    for order, at in enumerate(stage_starts):
        if order < len(names):
            index, total, name = names[order]
        else:
            index, total, name = order + 1, (names[-1][1] if names else None), None
        stages.append({"at": at, "index": index, "of": total, "name": name})

    _place(iterations, steps, stages)
    return {"iterations": iterations, "steps": steps, "stages": stages,
            "events": events, "fractions": fractions,
            "stage": None if current is None else {
                key: current[key] for key in ("index", "of", "name", "ended")}}


def _place(iterations: list[dict], steps: list[dict], stages: list[dict]) -> None:
    """Give each iteration its stage's index and its step, counted from 1 in its stage,
    so a reader -- the plot's tooltip, a CSV row -- needs no bookkeeping of its own.

    A step line comes before the step's first iteration, so a step with the same `at`
    as a stage start is that stage's. Null where there is no stage line or no step line.
    """
    stage_at = step_at = -1
    stage = step = None
    count = 0
    for number_, iteration in enumerate(iterations):
        while stage_at + 1 < len(stages) and stages[stage_at + 1]["at"] <= number_:
            stage_at += 1
            stage, count = stages[stage_at], 0
        start = stage["at"] if stage else 0
        while step_at + 1 < len(steps) and steps[step_at + 1]["at"] <= number_:
            step_at += 1
            if steps[step_at]["at"] >= start:
                step, count = steps[step_at], count + 1
        if step is not None and step["at"] < start:
            step = None  # the last step line was the stage before's
        iteration["stage"] = stage["index"] if stage else None
        iteration["step"] = count if step is not None else None
        iteration["time"] = step["time"] if step is not None else None
        iteration["cycle"] = step["cycle"] if step is not None else None


def read_log(path: Path, growing: bool = False) -> dict:
    """`parse` of the log at `path`; an empty result when there is no log."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return parse(text, growing=growing)


def of_run(run) -> dict:
    """The convergence data of one run, finished or still running.

    `run` is a run id or a run directory, as in `core.results.catalog`. On top of
    `parse`, it says which run, whether Kratos is still working in it, and where a run
    that stopped failed (`catalog.failed_at`).
    """
    from core.results import catalog

    directory = catalog.directory_of(run)
    running = calculation.is_current(directory)
    data = read_log(directory / calculation.LOG_NAME, growing=running)
    return {"run": directory.name, "running": running,
            "failed_at": catalog.failed_at(directory),
            "log": (directory / calculation.LOG_NAME).is_file(), **data}


# ── A summary, for a table ──────────────────────────────────────────────────

def _stage_of(data: dict, iteration: int) -> dict | None:
    """The stage iteration `iteration` (from 0) belongs to."""
    found = None
    for stage in data["stages"]:
        if stage["at"] <= iteration:
            found = stage
        else:
            break
    return found


def stage_rows(data: dict) -> list[dict]:
    """One row per stage: how many iterations and steps, the last residuals, and how
    many cut-backs and steps that hit the iteration limit."""
    rows = []
    total = len(data["iterations"])
    # A log with iterations and no `Analysis -START-` (a deck from elsewhere, say) is
    # one stage with no name.
    stages = data["stages"] or ([{"at": 0, "index": None, "of": None, "name": None}]
                                if total else [])
    data = {**data, "stages": stages}
    for order, stage in enumerate(stages):
        last_stage = order + 1 == len(stages)
        end = total if last_stage else stages[order + 1]["at"]
        mine = data["iterations"][stage["at"]:end]
        # A step starts before its first iteration, so a step at `end` is the next
        # stage's -- unless there is no next stage.
        in_stage = [step for step in data["steps"]
                    if stage["at"] <= step["at"] and (step["at"] < end or last_stage)]
        # An event comes after its iteration, so one at `at` belongs to iteration at - 1.
        events = [event for event in data["events"]
                  if _stage_of(data, max(event["at"] - 1, 0)) is stage]
        last = mine[-1] if mine else None
        rows.append({
            "index": stage["index"], "of": stage["of"], "name": stage["name"],
            "iterations": len(mine), "steps": len(in_stage),
            "relative": last["relative"] if last else None,
            "relative_target": last["relative_target"] if last else None,
            "absolute": last["absolute"] if last else None,
            "absolute_target": last["absolute_target"] if last else None,
            "met": bool(last and last["met"]),
            "cut_backs": sum(1 for event in events if event["kind"] == "cut_back"),
            "max_iterations": sum(1 for event in events
                                  if event["kind"] == "max_iterations"),
        })
    return rows


def event_text(event: dict) -> str:
    """An event in words, as `kratos-cli` says it (`eventText` in the GUI's
    `convergence-plot.js` says the same)."""
    if event["kind"] == "cut_back":
        return f"step cut back, factor {event['factor']}"
    if event["kind"] == "max_iterations":
        return f"step reached the iteration limit of {event['limit']}"
    return event["kind"]
