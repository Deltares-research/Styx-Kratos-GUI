"""What a command answers, and how it is said.

A command returns an `Answer`: the data a script reads (`--json`), the lines a person
reads, and -- when it did not do what it was asked -- the reason. Exit codes
(plan/active/cli-plan.md D7): 0 done, 1 refused by the model or by Kratos, 2 a command
line argparse could not read. A refusal goes to stderr as `error: <reason>`; with
`--json` it is the answer on stdout as well, so a script reading stdout always gets JSON.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

from pydantic import ValidationError


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
    error: str | None = None
    """Set when the command ran but did not do what it was asked -- a run Kratos
    stopped. Exit 1."""


def answered(answer: Answer, as_json: bool) -> int:
    if as_json:
        print(_json(answer.data))
    else:
        for line in answer.lines:
            print(line)
    for warning in answer.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if answer.error:
        print(f"error: {answer.error}", file=sys.stderr)
        return 1
    return 0


def refused(failure: BaseException, as_json: bool) -> int:
    message = describe(failure)
    if as_json:
        print(_json({"ok": False, "error": message}))
    print(f"error: {message}", file=sys.stderr)
    return 1


def describe(failure: BaseException) -> str:
    """The reason, as a person reads it. A model that does not validate is said field
    by field, each by its path in the project (`layers[0].tops`), which is the path
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
