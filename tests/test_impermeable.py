"""An impermeable line: a screen in the soil no water flows through.

A groundwater flow deck cuts its mesh along the line (`writer._impermeable_cut`): the soil
on each side gets nodes of its own there, and where the line stops in the soil the two
sides meet in one node again. No Kratos run here: the flow over the cut is measured by
solving Darcy's law on the deck's own mesh, which is what the flow elements do with it.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.geometry import solid_model
from core.kratos import condition_checks, writer
from core.kratos.writer import ExportError
from core.model import drafts
from core.model.schemas import (FluxCondition, ImpermeableCondition, Stage,
                                standard_conditions)
from tests import mdpa
from tests.models.muskat import HEADS, HEIGHT, LEFT_LEVEL, RIGHT_LEVEL, WIDTH, muskat

MIDDLE = WIDTH / 2


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


def screen(*points: tuple[float, float], id: str = "screen") -> ImpermeableCondition:
    return ImpermeableCondition(id=id, name=id.capitalize(), points=list(points))


def heads(deck: mdpa.Deck) -> dict[int, float]:
    """The steady head at each node of `deck`'s soil, isotropic and homogeneous, with the
    head of the left and the right face held at the Muskat levels: Darcy's law solved on
    the corner nodes of the deck's own triangles."""
    rows = [row[:3] for block in deck.elements for row in block.entries.values()]
    nodes = sorted({n for row in rows for n in row})
    at = {n: i for i, n in enumerate(nodes)}
    k = np.zeros((len(nodes), len(nodes)))
    for row in rows:
        xy = np.array([deck.nodes[n][:2] for n in row])
        b = np.array([xy[1, 1] - xy[2, 1], xy[2, 1] - xy[0, 1], xy[0, 1] - xy[1, 1]])
        c = np.array([xy[2, 0] - xy[1, 0], xy[0, 0] - xy[2, 0], xy[1, 0] - xy[0, 0]])
        area = abs(b[0] * c[1] - b[1] * c[0]) / 2
        local = (np.outer(b, b) + np.outer(c, c)) / (4 * area)
        index = [at[n] for n in row]
        k[np.ix_(index, index)] += local
    held = {at[n]: LEFT_LEVEL if deck.nodes[n][0] < 1e-9 else RIGHT_LEVEL
            for n in nodes if deck.nodes[n][0] < 1e-9 or deck.nodes[n][0] > WIDTH - 1e-9}
    rhs = np.zeros(len(nodes))
    for i, value in held.items():
        k[i, :] = 0.0
        k[i, i] = 1.0
        rhs[i] = value
    solved = np.linalg.solve(k, rhs)
    return {n: float(solved[at[n]]) for n in nodes}


def deck_of(conditions, order: int = 1) -> mdpa.Deck:
    export = writer.export_project(muskat(conditions=conditions, order=order))
    return mdpa.parse(export["mdpa"])


# ── The record ───────────────────────────────────────────────────────────────

def test_an_impermeable_line_is_a_line_of_two_points_or_more():
    assert screen((0.0, 0.0), (1.0, 0.0)).on == "line"
    with pytest.raises(ValueError, match="needs points"):
        ImpermeableCondition(id="s", name="S")
    with pytest.raises(ValueError, match="at least two points"):
        screen((0.0, 0.0))


def test_a_new_impermeable_line_goes_down_the_middle():
    project = muskat()
    made = drafts.impermeable_condition(project)
    assert made.id == "impermeable_1" and made.name == "Impermeable line 1"
    assert made.points == [(MIDDLE, HEIGHT), (MIDDLE, HEIGHT / 2)]
    with pytest.raises(drafts.DraftError, match="switch to 2D"):
        drafts.impermeable_condition(project.model_copy(update={"dimension": 3}))


def test_no_stage_switches_an_impermeable_line():
    assert "screen" not in muskat(conditions=[*HEADS, screen((MIDDLE, HEIGHT),
                                                             (MIDDLE, 1.0))]).stageable_keys()


def test_an_impermeable_line_outside_flow_is_left_out_and_said():
    project = muskat(conditions=[*standard_conditions(), *HEADS,
                                 screen((MIDDLE, HEIGHT), (MIDDLE, 1.0))],
                     stages=[Stage(id="p", name="P", stress_initialisation="gravity")])
    assert any("impermeable condition 'Screen' is left out: an impermeable line belongs "
               "to a groundwater flow calculation" in w
               for w in condition_checks.warnings(project))


# ── The cut ──────────────────────────────────────────────────────────────────

def test_a_line_across_the_soil_stops_all_flow_over_it(gmsh_session):
    """Top to bottom, the cut leaves each side at its own face's head: nothing flows
    from one to the other. Without it the head falls across the soil."""
    open_heads = heads(deck_of(HEADS))
    assert min(open_heads.values()) < LEFT_LEVEL - 0.1
    deck = deck_of([*HEADS, screen((MIDDLE, HEIGHT), (MIDDLE, 0.0))])
    cut = heads(deck)
    left = [h for n, h in cut.items() if deck.nodes[n][0] < MIDDLE - 1e-9]
    right = [h for n, h in cut.items() if deck.nodes[n][0] > MIDDLE + 1e-9]
    assert left and right
    assert left == pytest.approx([LEFT_LEVEL] * len(left), abs=1e-9)
    assert right == pytest.approx([RIGHT_LEVEL] * len(right), abs=1e-9)


def test_a_line_that_stops_in_the_soil_lets_the_water_round_its_end(gmsh_session):
    deck = deck_of([*HEADS, screen((MIDDLE, HEIGHT), (MIDDLE, 1.0))])
    on_line = {}
    for n, (x, y, _) in deck.nodes.items():
        if abs(x - MIDDLE) < 1e-9 and y >= 1.0 - 1e-9:
            on_line.setdefault(round(y, 9), []).append(n)
    assert len(on_line[1.0]) == 1, "the tip is one node: the soil closes round it"
    assert all(len(nodes) == 2 for y, nodes in on_line.items() if y > 1.0)
    cut = heads(deck)
    right = [h for n, h in cut.items() if MIDDLE + 1e-9 < deck.nodes[n][0] < WIDTH - 1e-9]
    assert max(right) > RIGHT_LEVEL + 0.1, "water reaches the right side, under the tip"


def test_a_quadratic_mesh_is_cut_at_its_midside_nodes_too(gmsh_session):
    deck = deck_of([*HEADS, screen((MIDDLE, HEIGHT), (MIDDLE, 1.0))], order=2)
    heights: dict[float, int] = {}
    for x, y, _ in deck.nodes.values():
        if abs(x - MIDDLE) < 1e-9 and y > 1.0 + 1e-9:
            heights[round(y, 9)] = heights.get(round(y, 9), 0) + 1
    assert heights and set(heights.values()) == {2}


def test_a_line_along_the_outer_boundary_cuts_nothing_and_says_so(gmsh_session):
    export = writer.export_project(muskat(conditions=[*HEADS, screen((0.2, HEIGHT),
                                                                     (1.2, HEIGHT))]))
    assert any("'Screen' runs along the soil's outer boundary only" in w
               for w in export["warnings"])
    places = [xyz for xyz in mdpa.parse(export["mdpa"]).nodes.values()]
    assert len(set(places)) == len(places), "no node has a copy"


def test_a_line_outside_the_soil_is_refused(gmsh_session):
    with pytest.raises(ExportError, match="'Screen' has no mesh along its line"):
        writer.export_project(muskat(conditions=[*HEADS, screen((0.2, HEIGHT + 1),
                                                                (1.2, HEIGHT + 1))]))


def test_the_line_is_no_part_of_the_deck(gmsh_session):
    deck = deck_of([*HEADS, screen((MIDDLE, HEIGHT), (MIDDLE, 1.0))])
    assert "Screen" not in deck.parts


def test_a_condition_on_the_cut_follows_its_own_soil(gmsh_session):
    """A flux on the ground the screen comes up through: each of its edges is on one
    side of the cut, and stands on the nodes of the soil it is the edge of."""
    rain = FluxCondition(id="rain", name="Rain", on="face", face="top", value=1e-6)
    deck = deck_of([*HEADS, rain, screen((MIDDLE, HEIGHT), (MIDDLE, 1.0))])
    elements = [set(row) for block in deck.elements for row in block.entries.values()]
    rows = [row for block in deck.conditions for row in block.entries.values()]
    assert rows and all(any(set(row) <= element for element in elements) for row in rows)
