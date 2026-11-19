"""The wet surface under the phreatic line, run in Kratos. Opt-in: `pytest --run-kratos`.

A phreatic line as start values gives the soil its initial pressure. Where the line
stands above the ground, the deck fixes the pressure on the soil surface under its
water (`core.kratos.writer._wet_surface`), which is the boundary a flow calculation
needs. Kratos keeps a node that a phreatic process fixed fixed after the stage ends, so
a stage that leaves the surface dry has to free it again.

The column of `tests.models.muskat`, ground at 4 m, in two flow stages. In the first,
the water stands at 5 m and nothing else fixes the pressure, so the column is
hydrostatic about 5 m. In the second, the left face is held at 3 m, and the open water
is either switched off or replaced by a line at 3 m, below the ground. Either way the
top is freed, so the column settles to hydrostatic about 3 m. If the top stayed fixed
at the first stage's pressure, the water would flow from the top to the left face
instead, which is what a deck without the freeing does when the water is switched off
(a new line's start values free every node by themselves).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import condition_checks, writer
from core.model.schemas import MeshRequest, Stage, WaterPressureCondition
from core.results import catalog
from tests import mdpa
from tests.models.muskat import HEIGHT, WIDTH, head, muskat
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos

GAMMA = 10_000.0


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("wet-surface-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def line(id: str, level: float) -> WaterPressureCondition:
    return WaterPressureCondition(
        id=id, name=id, on="domain", is_fixed=False,
        fluid_pressure_type="Phreatic_Multi_Line", x_coordinates=[0.0, WIDTH],
        y_coordinates=[level, level])


@pytest.mark.parametrize("lowered", [False, True], ids=["switched off", "lowered"])
def test_the_wet_surface_holds_the_flow_and_lets_go_when_the_water_drops(lowered):
    low = ["low"] if lowered else []
    project = muskat(
        conditions=[line("high", 5.0), line("low", 3.0), head("left", "left", 3.0)],
        stages=[Stage(id="high_water", name="High water", calculation="flow",
                      deactivate=["low", "left"]),
                Stage(id="low_water", name="Low water", calculation="flow",
                      parent="high_water", activate=[*low, "left"],
                      deactivate=["high"] + ([] if lowered else ["low"]))])
    assert condition_checks.flow_refusal(project) is None
    with solid_model.session():
        deck = writer.export_project(project, MeshRequest(element_size=0.4, order=1))
    outcome = calculation.run(deck)
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])

    nodes = mdpa.parse(deck["mdpa"]).nodes
    run = Path(outcome["directory"]).name

    def pressures(stage: int) -> dict[int, float]:
        field = catalog.stage_results(run, stage).field("WATER_PRESSURE")
        return {node: value[0] if isinstance(value, list) else value
                for node, value in field.values.items()}

    top = [node for node, xyz in nodes.items() if abs(xyz[1] - HEIGHT) < 1e-9]
    assert top
    for stage, level in ((1, 5.0), (2, 3.0)):
        for node, pressure in pressures(stage).items():
            expected = -GAMMA * (level - nodes[node][1])
            assert pressure == pytest.approx(expected, abs=50.0), (stage, nodes[node])
    # Freed: above the water now, where the first stage held it at 1 m of water.
    assert all(pressures(2)[node] > 0.0 for node in top)
