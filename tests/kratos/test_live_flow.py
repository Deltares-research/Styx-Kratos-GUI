"""Groundwater flow, run in Kratos: the semi-Muskat column (`tests/models/muskat.py`, case
A of plan/active/groundwater-flow-plan.md) against its exact solution. Opt-in:
`pytest --run-kratos`.

The head falls linearly from the left face to the right one, a field the elements hold
exactly, so the water pressure at every node and the flux everywhere are checked to
within what the result files print, on any mesh.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import Phase, Project
from core.results import catalog
from tests.models import muskat
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos

PRESSURE_TOLERANCE = 0.5
"""Pa: the result files print about six digits of a pressure up to 24 kPa."""


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("flow-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def run(project: Project) -> tuple[dict, str]:
    with solid_model.session():
        deck = writer.export_project(project)
    outcome = calculation.run(deck)
    assert outcome["ok"], outcome
    return deck, Path(outcome["directory"]).name


def worst_pressure(deck: dict, run_id: str, stage: int, right: float) -> float:
    """The largest difference from the exact water pressure, Pa, with the right face held
    at the level `right`."""
    values = catalog.stage_results(run_id, stage).field("WATER_PRESSURE").values
    nodes = {int(row[0]): row[1:] for row in deck["nodes"]}
    level = muskat.LEFT_LEVEL
    worst = 0.0
    for node, (x, y, _) in nodes.items():
        exact = muskat.GAMMA_W * (y - level + (level - right) * x / muskat.WIDTH)
        worst = max(worst, abs(values[node][0] - exact))
    return worst


@pytest.mark.parametrize("order", [1, 2])
def test_the_water_pressure_is_the_exact_one_at_every_node(order):
    deck, run_id = run(muskat.muskat(order=order))

    assert worst_pressure(deck, run_id, 1, muskat.RIGHT_LEVEL) <= PRESSURE_TOLERANCE


def test_the_flux_is_darcy_s_horizontal_flow_and_the_soil_is_saturated():
    deck, run_id = run(muskat.muskat(order=2))
    results = catalog.stage_results(run_id, 1)

    flux = results.field("FLUID_FLUX_VECTOR").values.values()
    assert max(abs(q[0] - muskat.EXACT_FLUX) for q in flux) <= 1e-3 * muskat.EXACT_FLUX
    assert max(abs(q[1]) for q in flux) <= 1e-3 * muskat.EXACT_FLUX
    saturation = results.field("EFFECTIVE_SATURATION").values.values()
    assert all(abs(s[0] - 1.0) <= 1e-9 for s in saturation)
    head = catalog.stage_field(run_id, 1, "head", "elements")["values"]
    assert muskat.RIGHT_LEVEL - 1e-6 <= min(head) and max(head) <= muskat.LEFT_LEVEL + 1e-6


def test_each_phase_is_solved_with_its_own_heads():
    """The second phase lowers the right head: its own condition on, the first one off.
    A switched-off Hydrostatic condition keeps its nodes fixed at their last values, so
    the new one has to replace them for the second stage to be the lower flow."""
    low = muskat.head("low_right", "right", 1.0)
    project = muskat.muskat(
        conditions=[*muskat.HEADS, low], order=2,
        phases=[Phase(id="flow", name="Flow", calculation="Groundwater flow",
                      deactivate=["low_right"]),
                Phase(id="lower", name="Lower", parent="flow",
                      calculation="Groundwater flow",
                      activate=["low_right"], deactivate=["right_head"])])
    deck, run_id = run(project)

    assert worst_pressure(deck, run_id, 1, muskat.RIGHT_LEVEL) <= PRESSURE_TOLERANCE
    assert worst_pressure(deck, run_id, 2, 1.0) <= PRESSURE_TOLERANCE
