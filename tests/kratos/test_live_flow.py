"""Groundwater flow, run in Kratos: the Muskat column (`tests/models/muskat.py`, cases A, B
and C of plan/done/groundwater-flow-plan.md). Opt-in: `pytest --run-kratos`.

Case A: the head falls linearly from the left face to the right one, a field the
elements hold exactly, so the water pressure at every node and the flux everywhere are
checked to within what the result files print, on any mesh. Kratos' own regression
values of the case are the same exact answer.

Case B, a Van Genuchten soil, has no exact answer. It is checked against Kratos' own
regression values, read off the Styx run at the coordinates of Kratos' nodes, since the
two meshes differ. The tolerances are what the answer moves by between meshes of 0.1 m
and 0.05 m (2026-10-24): 9 Pa of water pressure, 0.015 of saturation, 1 % of the flux
below the phreatic line. One value moves more: the flux at node 1440, 5 cm from the
right face just below the phreatic line, where it changes fast. There it is 23 % above
Kratos' (Kratos' own mesh is not converged there either), and is held to 30 %.

Case C, a seepage face above the tail water, has no Kratos values either. It is held to
what the physics demands: the water that comes in on the left leaves on the right, the
discharge is that of Dupuit and Charny, and the face is open (at zero pressure, letting
water out) from the tail water up to an exit point and closed above it. Both meshes put
the exit point at about 1.85 m (2026-10-24).
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


def at_node(case, kratos: dict, variable: str, node: int) -> list[float]:
    """A run's `variable` at the place of Kratos' `node`, whose (x, y) `kratos` holds."""
    mesh, results = case
    (x, y), _ = kratos[node]
    return muskat.at_point(mesh, results.field(variable).values, x, y)


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


KRATOS_A_TOLERANCE = {"WATER_PRESSURE": 1.0, "EFFECTIVE_SATURATION": 1e-9}
"""Pa, and a fraction of full saturation: both runs give the exact answer, which Kratos'
values keep to about six digits."""


@pytest.fixture(scope="module")
def case_a():
    _, run_id = run(muskat.muskat(order=2))
    return catalog.stage_mesh(run_id, 1), catalog.stage_results(run_id, 1)


@pytest.mark.parametrize("node, variable", [
    (node, variable) for node, (_, values) in muskat.KRATOS_A.items() for variable in values])
def test_case_a_is_kratos_own_answer(case_a, node, variable):
    _, expected = muskat.KRATOS_A[node]
    got = at_node(case_a, muskat.KRATOS_A, variable, node)
    if variable == "FLUID_FLUX_VECTOR":
        assert got[0] == pytest.approx(expected[variable][0], rel=1e-4)
        assert abs(got[1]) <= 1e-9
    else:
        assert got[0] == pytest.approx(expected[variable], abs=KRATOS_A_TOLERANCE[variable])


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


# ── Case B: a Van Genuchten soil ────────────────────────────────────────────

CASE_B_TOLERANCE = {"WATER_PRESSURE": 10.0, "EFFECTIVE_SATURATION": 0.02}
"""Pa, and a fraction of full saturation: just above what the 0.1 m and 0.05 m meshes
differ by."""

FLUX_TOLERANCE = {273: 0.02, 1440: 0.30}
"""Relative, by Kratos node (see the module docstring for 1440)."""

DRY_FLUX = 1e-8
"""m/s: at node 890, high in the dry soil, the flux is a few 1e-9 in both codes."""


@pytest.fixture(scope="module")
def case_b():
    _, run_id = run(muskat.van_genuchten(size=0.05))
    return catalog.stage_mesh(run_id, 1), catalog.stage_results(run_id, 1)


def at(case, variable: str, node: int) -> list[float]:
    return at_node(case, muskat.KRATOS_B, variable, node)


@pytest.mark.parametrize("node, variable", [
    (node, variable) for node, (_, values) in muskat.KRATOS_B.items()
    for variable in values if variable != "FLUID_FLUX_VECTOR"])
def test_case_b_is_kratos_own_answer(case_b, node, variable):
    _, expected = muskat.KRATOS_B[node]
    assert at(case_b, variable, node)[0] == pytest.approx(
        expected[variable], abs=CASE_B_TOLERANCE[variable])


@pytest.mark.parametrize("node", [273, 1440])
def test_case_b_flux_below_the_phreatic_line_is_kratos_own(case_b, node):
    _, expected = muskat.KRATOS_B[node]
    qx, qy = at(case_b, "FLUID_FLUX_VECTOR", node)[:2]
    assert (qx, qy) == pytest.approx(expected["FLUID_FLUX_VECTOR"], rel=FLUX_TOLERANCE[node])


def test_case_b_dry_soil_carries_no_flux(case_b):
    qx, qy = at(case_b, "FLUID_FLUX_VECTOR", 890)[:2]
    assert abs(qx) <= DRY_FLUX and abs(qy) <= DRY_FLUX


# ── Case C: a seepage face ──────────────────────────────────────────────────

@pytest.fixture(scope="module", params=[1, 2], ids=["linear", "quadratic"])
def case_c(request):
    _, run_id = run(muskat.seepage(order=request.param, max_iterations=200))
    return muskat.seepage_outcome(catalog.stage_mesh(run_id, 1),
                                  catalog.stage_results(run_id, 1))


def test_case_c_lets_out_what_comes_in(case_c):
    _, inflow, outflow = case_c
    assert outflow == pytest.approx(-inflow, rel=1e-3)


def test_case_c_discharge_is_dupuit_and_charny_s(case_c):
    """A little above it (0.7 % at this mesh): the Van Genuchten soil lets some water
    through above the phreatic line, which Charny's free surface does not."""
    _, _, outflow = case_c
    assert muskat.CHARNY_DISCHARGE <= outflow <= 1.02 * muskat.CHARNY_DISCHARGE


def test_case_c_water_leaves_the_face_above_the_tail_water(case_c):
    """Open from the tail water up to the exit point (1.84 m linear, 1.86 m quadratic),
    closed above it: no water flows in, and no node keeps a pressure above the
    atmosphere."""
    face, _, _ = case_c
    top = muskat.exit_point(face)
    assert 1.7 <= top <= 2.0
    assert all(rate > 0.0 for y, pressure, rate in face if pressure == 0.0)
    assert all(pressure == 0.0 for y, pressure, _ in face if y <= top)
    assert all(pressure > -1.0 for y, pressure, _ in face if y > top)
