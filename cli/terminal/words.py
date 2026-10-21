"""How the words of a command line become a command and its values.

The pieces the record commands share: a noun with its actions (`borehole add`,
`beam set`), the options a command was given, the answer an edit gives, `NAME=VALUE`
variables, and coordinates typed as plain numbers or read from a file.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
from pathlib import Path

from cli.terminal.files import add_project, add_writing, written
from cli.terminal.output import Answer, CommandError
from core.model.schemas import Project
from core.session import EditRefused

NEW_ID = "its id, which other commands and the phases refer to it by"
"""The start of the help of every `add` command's id; `id_help` says the rest."""


def noun(commands, common, name: str, help: str):
    """The command `name`, which takes a project and then one of its actions."""
    parser = commands.add_parser(name, parents=[common], help=help)
    add_project(parser)
    return parser.add_subparsers(dest="action", metavar="<action>", required=True)


def action(actions, common, name: str, handler, *, writes: bool = True,
           variables: bool = False, help: str | None = None) -> argparse.ArgumentParser:
    """The action `name` of a noun, run by `handler`; `writes` gives it --out and
    --dry-run, and `variables` lets it take NAME=VALUE words."""
    parser = actions.add_parser(name, parents=[common], help=help)
    if writes:
        add_writing(parser)
    parser.set_defaults(handler=handler)
    if variables:
        # `NAME=VALUE` words anywhere on the line; `cli.terminal.main` gives this command the
        # words no option took, since argparse cannot take them between options.
        parser.set_defaults(variables=[])
    return parser


def existing(parser: argparse.ArgumentParser, noun: str, command: str | None = None) -> None:
    """The `id` of a record that is already there, with where its ids are listed."""
    parser.add_argument("id", help=f"the {noun}'s id, as `{command or noun} list` shows it")


def id_help(otherwise: str | None = None) -> str:
    """The help of a new record's id: its --name when no id is typed, and else
    `otherwise`, the default its command numbers, if it has one."""
    return (f"{NEW_ID} (default: its --name"
            + (f", or else {otherwise})" if otherwise else ")"))


def named_ids(required: bool = False):
    """The handler of a command that adds a record, with the record's --name as its id
    when no id is typed: then the name the user gave is also the word other commands and
    the phases take. A `required` id is refused when neither is given; otherwise the
    command numbers one, as the GUI does."""
    def wrap(handler):
        @functools.wraps(handler)
        def adding(args: argparse.Namespace) -> Answer:
            if args.id is not None:
                return handler(args)
            if args.name is None:
                if required:
                    raise CommandError("give it an id, or a --name, which then is its id "
                                       "too")
                return handler(args)
            args.id = args.name
            try:
                return handler(args)
            except EditRefused as refusal:
                if repr(args.id) not in str(refusal):
                    raise
                raise CommandError(f"{refusal} The id came from --name {args.name!r}: give "
                                   "another name, or an id of its own.") from None
        return adding
    return wrap


def id_and_name(record) -> str:
    """Both, labelled: other commands and phases take the id, and an id such as `load`
    next to a name reads as one word without the labels."""
    return f"id {record.id}, name {record.name}"


def given(args: argparse.Namespace, *names: str) -> dict:
    """The options among `names` the command line gave, by name."""
    return {name: getattr(args, name) for name in names if getattr(args, name) is not None}


def edited(args: argparse.Namespace, project: Project, did: str) -> Answer:
    """Write the edited `project` and say what was done, and where it went."""
    target, where = written(args, project)
    return Answer(data={"file": file_of(target)}, lines=[f"{did}; {where}"])


def file_of(target) -> str | None:
    return str(target) if target is not None else None


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


def assignments(words: list[str]) -> dict:
    """`NAME=VALUE` words as variables. A value is JSON when it reads as JSON and text
    otherwise, as `kratos-cli set` takes it: `YOUNG_MODULUS=2e7`,
    `GEO_DRAINAGE_TYPE=FULLY_COUPLED`."""
    out = {}
    for word in words:
        name, equals, value = word.partition("=")
        if not equals or not name:
            raise CommandError(f"{word!r} is not a variable: give variables as NAME=VALUE, "
                               "e.g. YOUNG_MODULUS=2e7")
        out[name] = parsed([value])
    return out


def coordinates(words: list[str] | None, size: int,
                option: str = "--points") -> list[tuple[float, ...]]:
    """`--points` as points of `size` coordinates: plain numbers, or `@file` with one
    point per line (commas, semicolons or spaces between numbers; a header line that is
    not numbers is passed over)."""
    if not words:
        raise CommandError(f"give the points with {option}")
    if len(words) == 1 and words[0].startswith("@"):
        numbers = _numbers_in(Path(words[0][1:]), size)
    else:
        try:
            numbers = [float(word) for word in words]
        except ValueError:
            raise CommandError(f"{option} takes plain numbers, e.g. {option} 0 0 6 0 3 2, "
                               "or @file") from None
    what = {2: "pairs (x y)", 3: "triples (x y z)"}[size]
    if len(numbers) % size:
        raise CommandError(f"{option} takes {what} of numbers; {len(numbers)} numbers do "
                           f"not make whole {what.split()[0]}.")
    return [tuple(numbers[i:i + size]) for i in range(0, len(numbers), size)]


def _numbers_in(path: Path, size: int) -> list[float]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CommandError(f"no such file: {path}") from None
    numbers: list[float] = []
    for line in text.splitlines():
        fields = [field for field in re.split(r"[,;\s]+", line.strip()) if field]
        try:
            values = [float(field) for field in fields]
        except ValueError:
            continue            # a header, or a comment
        if values and len(values) != size:
            raise CommandError(f"{path.name}: {line.strip()!r} is not a point of {size} "
                               "numbers")
        numbers += values
    return numbers
