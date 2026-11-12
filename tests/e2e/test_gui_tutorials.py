"""The GUI tutorials in `docs/gui_tutorials/`, played on the real page as a reader follows
them. Opt-in: `--run-e2e`; with `--run-kratos` too, Kratos itself calculates.

Each tutorial is a list of steps in `tests/e2e/tutorials/`. The test plays them one by
one, holds each to its own check, and at the end holds the deck the GUI writes to the deck
of the tutorial's model in `tests/models/`. A changed button, window or default that
breaks a step, or makes the GUI build another model, fails here.
"""

from __future__ import annotations

import json

from core.geometry import solid_model
from core.kratos import writer
from tests import mdpa
from tests.e2e.tutorials import crow as crow_tutorial
from tests.e2e.tutorials.harness import Tour


def gui_deck(page, server) -> dict:
    """The deck the GUI exports for the project the server holds."""
    project = page.request.get(server["url"] + "/api/project").json()
    answer = page.request.post(server["url"] + "/api/export/mdpa", data=project["mesh"])
    assert answer.ok, answer.text()
    return answer.json()


def script_deck(model) -> dict:
    with solid_model.session():
        return writer.export_project(model)


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
    """The mesh, without its numbers: the GUI and a script number the same nodes and
    elements in another order."""
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
    return {"parameters": _plain(json.loads(export["project_parameters"])),
            "materials": _plain(json.loads(export["materials"])),
            "mesh": mesh_view(export["mdpa"])}


def test_the_crow_tutorial_builds_the_crow_model(app_page, live_server):
    tour = Tour(app_page)
    tour.play(crow_tutorial.STEPS)

    got, want = deck_view(gui_deck(app_page, live_server)), \
        deck_view(script_deck(crow_tutorial.MODEL))
    assert got["materials"] == want["materials"]
    assert got["parameters"] == want["parameters"]
    assert got["mesh"]["nodes"] == want["mesh"]["nodes"]
    assert got["mesh"] == want["mesh"]
    assert app_page.errors == []
