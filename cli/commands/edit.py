"""`get`, `set`, `add`, `remove`: any field of the project, by path (`core.session`).

A path walks the project's JSON by field name, and picks a record by its id in
brackets: `mesh.element_size`, `layers[L2].mat`, `materials[clay].variables.YOUNG_MODULUS`.
A value is JSON when it reads as JSON -- `1.5`, `true`, `null`, `[0, 1]`, `{"y": -2}` --
and text otherwise, so `set site.json name Pit A` needs no quotes (a number meant as text
does: `'"12"'`). `@file.json` takes the value from a file, which is how a whole record is
given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cli.terminal.files import add_project, add_writing, written
from cli.terminal.output import Answer, CommandError
from core import session

PATHS = ("a field path: names joined by dots, a record picked by its id in brackets, "
         "e.g. layers[L1].mat")
VALUES = "the value: JSON, plain text, or @file.json"


def register(commands, common: argparse.ArgumentParser) -> None:
    get = commands.add_parser("get", parents=[common], help="print a field, as JSON")
    add_project(get)
    get.add_argument("path", nargs="?", default="", help=PATHS + " (default: everything)")
    get.set_defaults(handler=get_value)

    put = commands.add_parser("set", parents=[common], help="set a field")
    add_project(put)
    put.add_argument("path", help=PATHS)
    put.add_argument("value", nargs="+", help=VALUES)
    add_writing(put)
    put.set_defaults(handler=set_value)

    add = commands.add_parser("add", parents=[common], help="add a record to a list")
    add_project(add)
    add.add_argument("path", help="the list, e.g. materials")
    add.add_argument("value", nargs="+", help=VALUES)
    add_writing(add)
    add.set_defaults(handler=add_value)

    remove = commands.add_parser("remove", parents=[common],
                                 help="remove a record, or a key of a mapping")
    add_project(remove)
    remove.add_argument("path", help="what to remove, e.g. materials[clay2]")
    add_writing(remove)
    remove.set_defaults(handler=remove_value)


def get_value(args: argparse.Namespace) -> Answer:
    value = session.value_at(session.load(args.project), args.path)
    return Answer(data=value, lines=[json.dumps(value, indent=2, ensure_ascii=False)])


def set_value(args: argparse.Namespace) -> Answer:
    value = parsed(args.value)
    project = session.with_value(session.load(args.project), args.path, value)
    return _edited(args, project, f"{args.path} = {_short(value)}", value)


def add_value(args: argparse.Namespace) -> Answer:
    value = parsed(args.value)
    project = session.with_added(session.load(args.project), args.path, value)
    return _edited(args, project, f"added {_short(value)} to {args.path}", value)


def remove_value(args: argparse.Namespace) -> Answer:
    project = session.without_value(session.load(args.project), args.path)
    return _edited(args, project, f"removed {args.path}")


def parsed(words: list[str]) -> object:
    """The value the words on the command line give. Several words are one text --
    `set site.json name Pit A` -- since a shell has already split them."""
    text = " ".join(words)
    if text.startswith("@"):
        path = Path(text[1:])
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise CommandError(f"no such file: {path}") from None
        try:
            return json.loads(text)
        except ValueError as failure:
            raise CommandError(f"{path} is not valid JSON: {failure}") from None
    try:
        return json.loads(text)
    except ValueError:
        return text


def _edited(args: argparse.Namespace, project, did: str, value: object = None) -> Answer:
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None, "path": args.path,
                        "value": value},
                  lines=[f"{did}; {where}"])


def _short(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 60 else text[:57] + "..."
