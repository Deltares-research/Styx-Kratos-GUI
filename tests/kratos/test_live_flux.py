"""A prescribed flux, run in Kratos: the Muskat column of case A (`tests/models/muskat.py`)
with its left head replaced by the water that head lets in. Opt-in: `pytest --run-kratos`.

In case A the head falls linearly from the left face to the right one, and the same
horizontal flux crosses the whole column (`muskat.EXACT_FLUX`). Prescribing that flux
into the soil on the left face, and keeping the right head, has the same exact answer:
the elements hold it exactly, so every node's water pressure is checked to within what
the result files print. A flux written with the wrong sign takes the water out instead,
and the head then rises to the right, far from the answer -- so this run proves the
process that sets `NORMAL_FLUID_FLUX` and `parameters.FLUX_INTO_SOIL` both (register
row R17).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import FluxCondition
from core.results import catalog
from tests.models import muskat
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos

PRESSURE_TOLERANCE = 0.5
"""Pa, as `test_live_flow`: the result files print about six digits of a pressure."""


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("flux-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def test_the_water_a_flux_lets_in_gives_case_a_s_heads():
    inflow = FluxCondition(id="inflow", name="Inflow", on="face", face="left",
                           value=muskat.EXACT_FLUX)
    project = muskat.muskat(conditions=[muskat.HEADS[1], inflow])
    with solid_model.session():
        deck = writer.export_project(project)
    outcome = calculation.run(deck)
    assert outcome["ok"], outcome
    values = catalog.stage_results(Path(outcome["directory"]).name, 1).field(
        "WATER_PRESSURE").values
    worst = max(abs(values[int(node)][0] - muskat.exact_water_pressure(x, y))
                for node, x, y, _ in deck["nodes"])
    assert worst < PRESSURE_TOLERANCE
