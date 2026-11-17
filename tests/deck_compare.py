"""A Kratos deck as Kratos reads it, without what changes between two exports of one model.

The GUI and a script number the same nodes and elements in another order, and write a
whole number as 2290 or 2290.0. `deck_view` leaves both out, so two decks of the same
model compare equal, and a deck that differs in any value, node or part does not.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.analysis import calculation
from tests import mdpa


def _plain(value):
    """A JSON value as Kratos reads it: -0.0 is 0.0, and a whole number typed as 2290
    is the 2290.0 a script writes."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return float(value) + 0.0


def _point(deck, node: int) -> tuple:
    return tuple(round(c, 9) + 0.0 for c in deck.nodes[node])


def mesh_view(text: str) -> dict:
    """The mesh of an .mdpa, without its numbers."""
    deck = mdpa.parse(text)

    def entries(blocks):
        return sorted((block.name, sorted(tuple(_point(deck, n) for n in nodes)
                                          for nodes in block.entries.values()))
                      for block in blocks)

    def ids_to_points(ids, blocks):
        lookup = {i: nodes for block in blocks for i, nodes in block.entries.items()}
        return sorted(tuple(sorted(_point(deck, n) for n in lookup[i])) for i in ids)

    return {"nodes": sorted(_point(deck, n) for n in deck.nodes),
            "elements": entries(deck.elements),
            "conditions": entries(deck.conditions),
            "parts": {name: (sorted(_point(deck, n) for n in part.nodes),
                             ids_to_points(part.elements, deck.elements),
                             ids_to_points(part.conditions, deck.conditions))
                      for name, part in deck.parts.items()}}


def deck_view(export: dict) -> dict:
    """`export` is what `writer.export_project` answers, or `read_deck` of a folder."""
    return {"parameters": _plain(json.loads(export["project_parameters"])),
            "materials": _plain(json.loads(export["materials"])),
            "mesh": mesh_view(export["mdpa"])}


def read_deck(folder: Path) -> dict:
    """The deck in `folder`, as much of an export as `deck_view` reads."""
    (mdpa_file,) = folder.glob("*.mdpa")
    return {"deck_name": mdpa_file.stem,
            "mdpa": mdpa_file.read_text(encoding="utf-8"),
            "project_parameters": (folder / calculation.PARAMETERS_NAME).read_text(
                encoding="utf-8"),
            "materials": (folder / calculation.MATERIALS_NAME).read_text(encoding="utf-8")}


def differences(got: dict, want: dict) -> list[str]:
    """What differs between two deck views, in words: one line for each part."""
    found = [f"{what} differ" for what in ("parameters", "materials")
             if got[what] != want[what]]
    for what in ("nodes", "elements", "conditions"):
        if got["mesh"][what] != want["mesh"][what]:
            found.append(f"mesh {what} differ ({len(got['mesh'][what])} against "
                         f"{len(want['mesh'][what])})")
    parts = set(got["mesh"]["parts"]) ^ set(want["mesh"]["parts"])
    if parts:
        found.append("parts in one deck only: " + ", ".join(sorted(parts)))
    elif got["mesh"]["parts"] != want["mesh"]["parts"]:
        found.append("parts differ")
    return found
