"""A project written as one Python file that builds it again: `kratos-cli script`, and
`script <file.py>` in the GUI's command box (plan/active/cli-plan.md, MS).

The file is a model script like any other (`core.scripting`): it hands back its model
from `project()`, so `run model.py` opens it in the GUI and every `kratos-cli` command
that reads a model takes it. Its `main()` writes the Kratos deck itself, through
`kratos-cli export`, so the deck is the one `kratos-cli export` writes for the project.

**What it holds.** The model's values, typed out: one constructor per record, grouped as
a hand-written model script is (`GROUPS`), Kratos' variable names as the keys, and
nothing that is a field's default. It says `x0=6.0`, not why; it is plain Python, so
constants can be put in by hand afterwards.

**It walks the schema.** Nothing here names a record type or a field it writes: a
`Project` field no group lists is written under "Other", and a record is its class
called with its fields. A new field or record type is written without this changing.

A drawn or imported solid is a .brep under `.data/`, which is not part of the project;
the script asks `core.scripting.with_solids` for it, which builds it again from its recipe
or its source file when it is not there. A deck case is the `deck_project(...)` call it
was opened with.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

from pydantic import BaseModel

from core.model.schemas import Deck, Project

ROOT = Path(__file__).resolve().parents[2]
"""The checkout: where `core` is, for a script run as `python model.py`."""

WIDTH = 92
"""A value longer than this, at its indentation, is spread over lines."""

GROUPS: dict[str, tuple[str, ...]] = {
    "The site": ("domain",),
    "The soil": ("materials", "layers", "excavation", "water"),
    "The structures": ("beam_sections", "panel_sections", "beams", "anchor_sections",
                       "anchors", "interface_sections", "interfaces"),
    "The loads": ("loads", "normal_loads"),
    "The boundary conditions": ("boundary_conditions",),
    "Drawn and imported solids": ("custom_parts",),
    "The seeded demo pit": ("wall", "struts", "anchor_rows", "piles", "wells"),
    "The mesh": ("mesh",),
    "The construction stages": ("stages",),
}
"""`Project` fields, under the heading they are written beneath, in this order. A field
with a record or a list for its value that is in no group goes under "Other"."""

NOTES = {
    "The seeded demo pit": "The demo's own wall ring, struts, anchors, piles and wells, "
                           "which the full build\n# (layered_soil=False) raises. A layered "
                           "model leaves them out.",
    "Drawn and imported solids": "Each a .brep under .data/; `scripting.with_solids` builds "
                                 "one again from its recipe or\n# its source file when it "
                                 "is not there.",
}


def script(project: Project, source: str | Path | None = None,
           written: datetime.date | None = None, name: str = "model.py",
           folder: str | Path | None = None) -> str:
    """The Python file that builds `project`, to be saved as `name` in `folder`. `source`
    is the project file it came from, named in the file's docstring with the day it was
    `written`."""
    head = _docstring(project, source, written, name)
    preamble = _preamble(folder)
    if project.deck is not None:
        return _deck_script(project, project.deck, head, preamble)
    written_fields = dict(_fields(project))
    inline = {name: value for name, value in written_fields.items() if not _record(value)}
    groups = _grouped([name for name in written_fields if name not in inline])
    classes = sorted({type(model).__name__ for model in _models(project)})

    body = [head, preamble,
            _imports("core.model.schemas", classes)]
    if project.custom_parts:
        body.append("from core import scripting  # noqa: E402\n")
    for heading, names in groups.items():
        body.append(_heading(heading))
        for name in names:
            constant = f"{name.upper()} = "
            body.append(constant + _code(written_fields[name], 0, len(constant)) + "\n")
    call = ",\n".join([f"        {name}={_code(value, 8, 8 + len(name) + 1)}"
                       for name, value in inline.items()]
                      + [f"        {name}={name.upper()}"
                         for names in groups.values() for name in names])
    built = f"Project(\n{call},\n    )"
    if project.custom_parts:
        built = f"scripting.with_solids({built})"
    body.append(f'\ndef project() -> Project:\n    """The model, as one Project."""\n'
                f"    return {built}\n")
    body.append(MAIN)
    return "\n".join(body)


# ── The file around the model ───────────────────────────────────────────────

PREAMBLE = '''from __future__ import annotations

import sys
from pathlib import Path


def checkout() -> Path:
    """The checkout, where `core` is: a folder above this file, or the one the Python
    that runs it is in (.venv-windows and the others sit in the checkout's root){also}."""
    here = Path(__file__).resolve().parent
    for folder in [here, *here.parents, Path(sys.prefix).resolve().parent{written}]:
        if (folder / "core" / "model" / "schemas.py").is_file():
            return folder
    if "core" in sys.modules:                       # opened inside Styx, which has it
        return Path(sys.modules["core"].__file__).resolve().parents[1]
    sys.exit(f"{{Path(__file__).name}}: no Styx checkout found; run it with the Python "
             "that kratos-cli uses")


ROOT = checkout()
"""`python <this file>` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
'''


def _preamble(folder: str | Path | None) -> str:
    """The lines that find the checkout. A file saved outside it also keeps the checkout
    it was written from, as the last place to look. One saved inside it does not: the
    folders above it find the checkout, and no path of one computer is committed."""
    if folder is not None and Path(folder).resolve().is_relative_to(ROOT):
        return PREAMBLE.format(also="", written="")
    return PREAMBLE.format(also=",\n    or else the one it was written from",
                           written=f",\n                   Path({json.dumps(ROOT.as_posix())})")

MAIN = '''
def main(argv: list[str] | None = None) -> int:
    """`--out DIR` writes the Kratos deck; `--calculate` runs it, as Calculate does."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, metavar="DIR",
                        help="write the Kratos deck into DIR")
    parser.add_argument("--calculate", action="store_true",
                        help="run the deck (the one written into --out, when given)")
    args = parser.parse_args(argv)
    if args.out is None and not args.calculate:
        parser.error("give --out DIR to write the deck, --calculate to run it, or both")
    from cli.terminal.main import main as kratos_cli

    if args.out is None:
        return kratos_cli(["calculate", __file__])
    code = kratos_cli(["export", __file__, "--out", str(args.out)])
    return kratos_cli(["run", str(args.out)]) if code == 0 and args.calculate else code


if __name__ == "__main__":
    sys.exit(main())
'''


def _docstring(project: Project, source, written, name: str) -> str:
    day = (written or datetime.date.today()).isoformat()
    origin = f" from {Path(source).name}" if source else ""
    title = project.name.replace('"' * 3, "'" * 3).replace("\\", "/")
    usage = [(f"run {name}", "in the GUI's command box: open it there"),
             (f"kratos-cli show {name}", "and every kratos-cli command that reads a model"),
             (f"python {name} --out deck/", "write its Kratos deck: ProjectParameters.json,"),
             ("", "MaterialParameters.json and the .mdpa"),
             (f"python {name} --calculate", "write the deck and run it, as Calculate does")]
    width = max(len(command) for command, _ in usage) + 4
    lines = "\n".join(f"    {command:<{width}}{what}" for command, what in usage)
    return (f'"""{title}, as a model script.\n\n'
            f"Written by kratos-cli{origin} on {day}. Every value is the model's own,\n"
            f"typed out; constants and loops can be put in by hand.\n\n{lines}\n\n"
            "`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, "
            '...).\n"""\n')


def _deck_script(project: Project, deck: Deck, head: str, preamble: str) -> str:
    arguments = [_flat(deck.directory), _flat(deck.parameters), f"name={_flat(project.name)}"]
    return "\n".join([
        head, preamble,
        _imports("core.kratos.external_deck", ["deck_project"]),
        "from core.model.schemas import Project  # noqa: E402\n",
        _heading("The deck"),
        "# A Kratos deck that is already written: opened with its own mesh and stages, and",
        "# calculated as the files it is.",
        f'\n\ndef project() -> Project:\n    """The model, as one Project."""\n'
        f"    return deck_project({', '.join(arguments)})\n",
        MAIN])


def _imports(module: str, names: list[str]) -> str:
    line = f"from {module} import {', '.join(names)}  # noqa: E402"
    if len(line) <= WIDTH:
        return line + "\n"
    wrapped, current = [], "    "
    for name in names:
        piece = f"{name}, "
        if len(current) + len(piece) > WIDTH:
            wrapped.append(current.rstrip())
            current = "    "
        current += piece
    wrapped.append(current.rstrip().rstrip(","))
    return f"from {module} import (  # noqa: E402\n" + "\n".join(wrapped) + ")\n"


def _heading(heading: str) -> str:
    line = f"\n# ── {heading} " + "─" * max(4, WIDTH - 6 - len(heading))
    note = NOTES.get(heading)
    return line + (f"\n# {note}\n" if note else "\n")


def _grouped(names: list[str]) -> dict[str, list[str]]:
    grouped = {heading: [name for name in fields if name in names]
               for heading, fields in GROUPS.items()}
    known = {name for fields in GROUPS.values() for name in fields}
    grouped["Other"] = [name for name in names if name not in known]
    return {heading: fields for heading, fields in grouped.items() if fields}


# ── Values as code ──────────────────────────────────────────────────────────

FIRST = ("id", "key", "name", "label")
"""Written first in a record, whatever the schema's order: what the record is called."""


ALWAYS = {"boundary_conditions"}
"""Fields written even at their default: a reader sees every condition the model has,
also the standard supports a project starts with."""


def _fields(model: BaseModel):
    """`(name, value)` for every field a constructor call needs: the required ones, those
    in `ALWAYS`, and those that differ from their default. What names the record comes
    first (`FIRST`)."""
    fields = type(model).model_fields
    order = [name for name in FIRST if name in fields] + [
        name for name in fields if name not in FIRST]
    for name in order:
        info = fields[name]
        value = getattr(model, name)
        if (info.is_required() or name in ALWAYS
                or value != info.get_default(call_default_factory=True)):
            yield name, value


def _record(value: object) -> bool:
    return isinstance(value, (BaseModel, list, dict))


def _models(value: object):
    if isinstance(value, BaseModel):
        yield value
        for _, field in _fields(value):
            yield from _models(field)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _models(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _models(item)


def _code(value: object, indent: int, start: int | None = None) -> str:
    """`value` as a Python expression starting at column `start`, on one line when it
    fits there; spread over lines indented from `indent`, the line's own, when not."""
    flat = _flat(value)
    start = indent if start is None else start
    # + 1: the comma after it, in a list or a call.
    if len(flat) + start + 1 <= WIDTH or not _record(value) and not isinstance(value, tuple):
        return flat
    inner, deeper = " " * (indent + 4), indent + 4
    if isinstance(value, BaseModel):
        lines = [f"{inner}{name}={_code(field, deeper, deeper + len(name) + 1)}"
                 for name, field in _fields(value)]
        return f"{type(value).__name__}(\n" + ",\n".join(lines) + f",\n{' ' * indent})"
    if isinstance(value, dict):
        lines = [f"{inner}{_flat(key)}: {_code(item, deeper, deeper + len(_flat(key)) + 2)}"
                 for key, item in value.items()]
        return "{\n" + ",\n".join(lines) + f",\n{' ' * indent}}}"
    if not isinstance(value, (list, tuple)):    # every other kind was flat above
        return flat
    opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
    lines = [f"{inner}{_code(item, deeper)}" for item in value]
    return opening + "\n" + ",\n".join(lines) + f",\n{' ' * indent}{closing}"


def _flat(value: object) -> str:
    if isinstance(value, BaseModel):
        return (f"{type(value).__name__}("
                + ", ".join(f"{name}={_flat(field)}" for name, field in _fields(value)) + ")")
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_flat(k)}: {_flat(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_flat(item) for item in value) + "]"
    if isinstance(value, tuple):
        items = [_flat(item) for item in value]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float) and not math.isfinite(value):
        return f'float("{value}")'
    return repr(value)
