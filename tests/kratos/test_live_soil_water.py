"""Each soil's water, run in Kratos. Opt-in: `pytest --run-kratos`.

What running it found, 2026-11-17, Kratos 10.4.4: sand over clay over an aquifer, the
phreatic line at -1 and the aquifer's head line sloping from +1 to +3, both drawn on
lines as the GUI draws them. The sand is hydrostatic below the phreatic line, the aquifer
below its head line, and the clay between them -- interpolated (`Interpolate_Line`) -- is
linear from the sand's pressure at its top to the aquifer's at its bottom, at every node,
the domain's sides included.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import MeshRequest
from core.results import catalog
from tests import mdpa
from tests.results_run import require_kratos
from core.model.schemas import INTERPOLATE
from tests.test_kratos_soil_water import HEAD, PHREATIC, drawn, layered

pytestmark = pytest.mark.kratos

GAMMA = 10_000.0


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("soil-water-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def expected(x: float, y: float) -> float:
    """The pressure at (`x`, `y`), Kratos' sign: compression negative."""
    head = 1.0 + 2.0 * x / 25.0
    sand_bottom = -GAMMA * (-1.0 + 5.0)
    aquifer_top = -GAMMA * (head + 10.0)
    if y >= -5.0:
        return -GAMMA * max(-1.0 - y, 0.0)
    if y <= -10.0:
        return -GAMMA * (head - y)
    return sand_bottom + (aquifer_top - sand_bottom) * (-5.0 - y) / 5.0


def test_the_clay_is_interpolated_between_the_sand_and_the_aquifer():
    with solid_model.session():
        project = layered((drawn(PHREATIC), drawn(HEAD)),
                          soil_water={"soil_L3": "head", "soil_L2": INTERPOLATE})
        deck = writer.export_project(project, MeshRequest(element_size=1.5, order=1))
    outcome = calculation.run(deck)
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])

    nodes = mdpa.parse(deck["mdpa"]).nodes
    field = catalog.stage_results(Path(outcome["directory"]).name, 1).field(
        "WATER_PRESSURE")
    pressures = {node: value[0] if isinstance(value, list) else value
                 for node, value in field.values.items()}
    clay = [node for node in pressures if -10.0 < nodes[node][1] < -5.0]
    assert clay
    for node, pressure in pressures.items():
        x, y = nodes[node][:2]
        assert pressure == pytest.approx(expected(x, y), abs=1.0), nodes[node]
