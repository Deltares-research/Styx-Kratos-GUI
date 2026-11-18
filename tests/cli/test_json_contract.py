"""What `kratos-cli --json` answers: its shape, held to a snapshot.

`--json` is the command line's interface for programs: a script reads the keys and the
kinds of value, not the sentences. A renamed key breaks such a script without a word, so
the shape of each read-only answer -- its keys, and the kind of value each holds, two
levels deep -- is kept in `json_shapes.json` beside this file. The values are the
model's, and other tests hold them.

A deliberate change: `pytest tests/cli/test_json_contract.py --update-snapshots`, then
review the diff of `json_shapes.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli.terminal.main import parser
from cli.terminal.shell import _subcommands
from core import session
from tests.models.excavation import excavation_project

SNAPSHOT = Path(__file__).resolve().parent / "json_shapes.json"

LISTS = ("anchor", "beam", "body", "boundary", "interface", "layer", "line", "load", "material",
         "member", "normal-load", "phases", "section", "stages", "volume", "wall")
"""Every command with a `list`."""

READS = {
    **{f"{group} list": (group, "FILE", "list") for group in LISTS},
    "show": ("show", "FILE"),
    "parts": ("parts", "FILE"),
    "check": ("check", "FILE"),
    "material presets": ("material", "FILE", "presets"),
    "material models": ("material", "FILE", "models"),
}
"""The read-only answers, `FILE` standing for the project file."""


def kind(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "array" if isinstance(value, list) else "object"


def merged(shapes: list):
    """One shape for the items of a list: every key any of them has, with every kind
    it takes."""
    if shapes and all(isinstance(shape, dict) for shape in shapes):
        keys = sorted({key for shape in shapes for key in shape})
        return {key: merged([shape[key] for shape in shapes if key in shape]) for key in keys}
    kinds = sorted({shape if isinstance(shape, str) else json.dumps(shape, sort_keys=True)
                    for shape in shapes})
    return "|".join(kinds)


def shape(value, depth: int = 2):
    """The keys of `value` and the kind of each, `depth` levels down."""
    if depth == 0 or not isinstance(value, (dict, list)):
        return kind(value)
    if isinstance(value, dict):
        return {key: shape(item, depth - 1) for key, item in sorted(value.items())}
    return [merged([shape(item, depth - 1) for item in value])] if value else []


def test_the_json_answers_keep_their_shape(cli, tmp_path, request):
    path = session.save(excavation_project(staged=True), tmp_path / "model.json")
    current = {}
    for title, words in READS.items():
        ran = cli("--json", *(path if word == "FILE" else word for word in words))
        assert ran.code == 0, (title, ran.err)
        current[title] = shape(ran.json())

    if request.config.getoption("--update-snapshots"):
        SNAPSHOT.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
    assert SNAPSHOT.exists(), (
        f"{SNAPSHOT.name} is missing; it is committed with this test. Write it with "
        "--update-snapshots and review it")
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert current == committed, (
        "a --json answer changed shape; if deliberate, rerun with --update-snapshots and "
        "review the diff of json_shapes.json")


def test_every_command_with_a_list_is_read():
    """A command that gains `list` gains a JSON answer a script may read."""
    commands = _subcommands(parser())
    assert {name for name, command in commands.items()
            if "list" in _subcommands(command)} == set(LISTS)
