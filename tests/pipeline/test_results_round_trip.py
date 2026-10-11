"""Project -> deck -> (synthetic) run -> results API, end to end without Kratos (alpha 2.4).

The test model is exported as Calculate would export it, and `tests/fakes/gid_writer.py`
writes every stage's GiD output with fields that are analytic functions of the coordinates --
in three sub-steps per stage, so the reader has to take the last one (finding F6). Then
everything is read back through the HTTP routes the Results mode uses, and each number is
compared with the function that wrote it:

    TOTAL_DISPLACEMENT  = stage * (1e-3 x, -1e-3 y, 0)                      [m]
    WATER_PRESSURE      = -9810 (y_w - y) below the water level, 0 above     [Pa]
    CAUCHY_STRESS       = (0.6 s, s, 0.6 s, 0, 0, 0), s = 18000 y            [Pa]

This is the post-processing chain's proof on every machine; the same writer stands in
for Kratos in the GUI end-to-end tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core import build, calculate, kratos, phases, results
from tests.models import excavation
from backend.main import app
from core.schemas import MeshRequest
from tests import mdpa
from tests.fakes import gid_writer

RUN = "Staged_excavation_2026-01-01_00-00"
WATER = None


def u(x, y, z, stage):
    return (stage * 1e-3 * x, -stage * 1e-3 * y, 0.0)


def pw(x, y, z, stage):
    return (-9810.0 * max(0.0, WATER - y),)


def stress(x, y, z, stage):
    s = 18000.0 * y
    return (0.6 * s, s, 0.6 * s, 0.0, 0.0, 0.0)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    global WATER
    project = excavation.excavation_project(staged=True)
    WATER = project.water.y
    with build.session():
        export = kratos.export_project(project, MeshRequest(element_size=8.0, order=2))
    root = tmp_path_factory.mktemp("runs")
    active = gid_writer.write_run(export, root / RUN,
                                  nodal={"TOTAL_DISPLACEMENT": u, "WATER_PRESSURE": pw},
                                  gauss={"CAUCHY_STRESS_TENSOR": stress}, steps=3)
    return {"project": project, "root": root, "deck": mdpa.parse(export["mdpa"]),
            "active": active}


@pytest.fixture
def client(run, monkeypatch):
    monkeypatch.setenv(calculate.RUNS_ENV, str(run["root"]))
    results.forget_cache()
    with TestClient(app) as c:
        yield c
    results.forget_cache()


def nodes_in(run, stage_name) -> dict[int, tuple[float, float, float]]:
    deck = run["deck"]
    used = {n for block in deck.elements if gid_writer.gid_type(block.name)
            for e in block.entries if e in run["active"][stage_name]
            for n in block.entries[e]}
    return {n: deck.nodes[n] for n in used}


def stages(run):
    return list(run["active"])


def test_the_run_is_listed_with_every_stage(client, run):
    described = client.get(f"/api/results/runs/{RUN}").json()
    assert [s["name"] for s in described["stages"]] == stages(run)
    assert described["complete"] is True


@pytest.mark.parametrize("index", range(1, 8))
def test_a_displacement_reads_back_as_the_function_that_wrote_it(client, run, index):
    field = client.get(f"/api/results/runs/{RUN}/stages/{index}/field/uy").json()
    nodes = nodes_in(run, stages(run)[index - 1])
    expected = {n: -index * 1e-3 * xyz[1] for n, xyz in nodes.items()}

    assert sorted(field["ids"]) == sorted(expected)
    for n, value in zip(field["ids"], field["values"]):
        assert value == pytest.approx(expected[n], abs=1e-12)
    assert field["min"] == pytest.approx(min(expected.values()))
    assert field["max"] == pytest.approx(max(expected.values()))


def test_the_last_sub_step_is_the_stage_result_not_the_first(client, run):
    """Each field was written at t = 1/3, 2/3 and 1, scaled by the same fraction."""
    field = client.get(f"/api/results/runs/{RUN}/stages/7/field/ux").json()
    nodes = nodes_in(run, stages(run)[6])
    x_max = max(xyz[0] for xyz in nodes.values())
    assert field["max"] == pytest.approx(7 * 1e-3 * x_max)


def test_the_pore_pressure_is_hydrostatic_in_the_runs_pascals(client, run):
    field = client.get(f"/api/results/runs/{RUN}/stages/1/field/pw").json()
    nodes = nodes_in(run, stages(run)[0])
    for n, value in zip(field["ids"], field["values"]):
        y = nodes[n][1]
        assert value == pytest.approx(-9810.0 * max(0.0, WATER - y), abs=1e-6)


def test_a_gauss_stress_averages_to_its_element_value(client, run):
    field = client.get(f"/api/results/runs/{RUN}/stages/1/field/p?location=elements").json()
    deck = run["deck"]
    for element, value in zip(field["ids"], field["values"]):
        corners = deck.element(element)[:3]
        cy = sum(deck.nodes[n][1] for n in corners) / 3
        assert value == pytest.approx((0.6 + 1 + 0.6) / 3 * 18_000.0 * cy, rel=1e-9, abs=1e-6)


def test_every_field_at_one_node_is_the_function_there(client, run):
    nodes = nodes_in(run, stages(run)[2])
    node, (x, y, z) = next(iter(sorted(nodes.items())))
    at = client.get(f"/api/results/runs/{RUN}/stages/3/at/{node}").json()
    by_field = {row["field"]: row["value"] for row in at["values"]}
    assert by_field["ux"] == pytest.approx(3e-3 * x)
    assert by_field["uy"] == pytest.approx(-3e-3 * y)
    assert by_field["pw"] == pytest.approx(-9810.0 * max(0.0, WATER - y), abs=1e-6)


@pytest.mark.parametrize("index", range(1, 8))
def test_the_parts_alive_in_each_stage_are_the_phase_model_s(client, run, index):
    """The deck's activations (which the writer applied) and the phase model agree."""
    project = run["project"]
    names = kratos._part_names(project)
    parts = {p["name"]: p for p in
             client.get(f"/api/results/runs/{RUN}/stages/{index}/parts").json()["parts"]}
    with_elements = {name for name, p in parts.items() if p["declared"]}
    interfaces = {name for name in with_elements if name.startswith("Interface_")}
    expected = ({names[key] for key in phases.active_parts(project, project.phases[index - 1])}
                & with_elements) - interfaces
    alive = {name for name, p in parts.items() if p["alive"]} - interfaces
    assert alive == expected


def test_a_run_that_stopped_part_way_reads_as_far_as_it_got(run, tmp_path, monkeypatch):
    with build.session():
        export = kratos.export_project(run["project"], MeshRequest(element_size=8.0, order=2))
    gid_writer.write_run(export, tmp_path / RUN, nodal={"TOTAL_DISPLACEMENT": u}, through=4)
    monkeypatch.setenv(calculate.RUNS_ENV, str(tmp_path))
    results.forget_cache()
    described = results.describe(RUN)
    assert [s["results"] for s in described["stages"]] == [True] * 4 + [False] * 3
    assert described["complete"] is False
