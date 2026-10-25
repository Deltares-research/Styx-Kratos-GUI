"""What a command answers, and how it is said.

A command returns an `Answer`: the data a script reads (`--json`), the lines a person
reads, and -- when it did not do what it was asked -- the reason. Exit codes
(plan/active/cli-plan.md D7): 0 done, 1 refused by the model or by Kratos, 2 a command
line argparse could not read. A command with a table answers `--csv` with it too: on
stdout, or into the file `--csv FILE` names (UTF-8, whatever the shell would make of a
redirect -- Windows PowerShell 5.1's `>` writes UTF-16). A refusal goes to stderr as `error: <reason>`; with
`--json` it is the answer on stdout as well, so a script reading stdout always gets JSON.
At a terminal the lines a person reads are in colour (`cli.terminal.style`); JSON and CSV never are.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from cli.terminal import style


class CommandError(Exception):
    """A refusal of the command line's own -- a file that is already there, a value that
    is not one -- rather than of the model. Said the same way."""


@dataclass
class Answer:
    data: object
    """What `--json` prints."""
    lines: list[str]
    """What a person reads, one line each."""
    warnings: list[str] = field(default_factory=list)
    """Said on stderr whichever way the answer goes: the exporter's, above all."""
    notes: list[str] = field(default_factory=list)
    """Said after the answer, as `note:`: what the exporter worked out for the user --
    the numbers an interface took from its soil -- which needs no action."""
    error: str | None = None
    """Set when the command ran but did not do what it was asked -- a run Kratos
    stopped. Exit 1."""
    csv: str | None = None
    """What `--csv` prints, for a command whose answer is a table."""


STDOUT = "-"
"""`--csv` given no file: the table goes to stdout."""


def answered(answer: Answer, as_json: bool, as_csv: str | None = None) -> int:
    if as_json:
        print(_json(answer.data))
    elif as_csv and answer.csv is not None and as_csv == STDOUT:
        sys.stdout.write(answer.csv)
    elif as_csv and answer.csv is not None:
        Path(as_csv).write_text(answer.csv, encoding="utf-8", newline="\n")
        rows = answer.csv.count("\n") - 1
        print_lines(f"wrote {as_csv} ({rows} row{'s' if rows != 1 else ''})")
    else:
        print_lines(*answer.lines)
    if not as_json:
        for message in answer.notes:
            note(message)
    for message in answer.warnings:
        warning(message)
    if answer.error:
        error(answer.error)
        return 1
    return 0


def print_lines(*lines: str) -> None:
    """Print human-readable lines to stdout, styled when output is a terminal."""
    for line in style.answer(list(lines), style.enabled(sys.stdout)):
        print(line)


def error(message: str) -> None:
    """`error: message`, on stderr."""
    _flagged("error:", "bold red", message)


def note(message: str) -> None:
    """`note: message`, on stdout: information, not a problem."""
    on = style.enabled(sys.stdout)
    print(style.paint("note:", "cyan", on), *style.answer([message], on))


def warning(message: str) -> None:
    """`warning: message`, on stderr."""
    _flagged("warning:", "bold yellow", message)


def _flagged(flag: str, colour: str, message: str) -> None:
    sys.stdout.flush()                  # Keep earlier stdout output ahead of this stderr message.
    on = style.enabled(sys.stderr)
    lines = message.split("\n")
    print(style.paint(flag, colour, on), *style.answer(lines[:1], on), file=sys.stderr)
    for line in style.answer(lines[1:], on):
        print(line, file=sys.stderr)


def refused(failure: BaseException, as_json: bool) -> int:
    message = describe(failure)
    if as_json:
        print(_json({"ok": False, "error": message}))
    error(message)
    return 1


def describe(failure: BaseException) -> str:
    """The reason, as a person reads it. A model that does not validate is said field
    by field, each by its path in the project (`layers[0].top`), which is the path
    `kratos-cli get` and `set` take."""
    if isinstance(failure, ValidationError):
        fields = [f"{_where(error['loc'])}: {error['msg']}" for error in failure.errors()]
        return "the model does not validate:\n  " + "\n  ".join(fields)
    return str(failure)


def _where(location: tuple) -> str:
    out = ""
    for step in location:
        out += f"[{step}]" if isinstance(step, int) else (f".{step}" if out else str(step))
    return out or "the project"


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)
