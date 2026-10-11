"""Constructs the exporter writes by convention rather than off a reference deck, closed
-- or found broken -- by running them (plan sec 8.3; the register is
tests/kratos/register.py). Opt-in: `pytest --run-kratos`.

What running them found, 2026-10-10 (all fixed unless marked xfail below):

* `LinearTimoshenkoCurvedBeamElement2D2N`, `LinearTimoshenkoBeamElement3D3N`,
  `LineNormalLoadCondition2D2N` and `GeoLinearElastic3DLaw` do not exist in Kratos
  (test_kratos_registry.py). No first-order section with a pile or a normal load, and no
  3D model at all, had ever loaded.
* 3D load faces were written reversed against their tetrahedra, which Kratos never
  matches ("found without any corresponding element"). Deck rule 13 now catches it.
* xfail: no linear U-Pw line interface exists, so a first-order section with an
  interface still cannot run -- a modelling decision for the owner.
* xfail: in 3D, a stage with both a surface load (face conditions) and a strut or beam
  (line elements) stops in Kratos' own neighbour search, which asks every element for its
  faces and a line has none. The 3D test model runs all seven stages without its
  surcharge.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import build, calculate, kratos, result_members, results, seed
from tests.models import excavation
from app.schemas import MeshRequest, Project
from tests import mdpa
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculate.RUNS_ENV)
    os.environ[calculate.RUNS_ENV] = str(tmp_path_factory.mktemp("construct-runs"))
    results.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculate.RUNS_ENV, None)
    else:
        os.environ[calculate.RUNS_ENV] = previous
    results.forget_cache()


def run(project: Project, order: int = 2, size: float = 4.0, ok: bool = True):
    with build.session():
        export = kratos.export_project(project, MeshRequest(element_size=size, order=order))
    outcome = calculate.run(export)
    if ok:
        assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])
    return export, outcome


def without(project: Project, **emptied) -> Project:
    """`project` with some collections emptied, and its phases told about it."""
    data = project.model_dump(mode="json")
    gone = set()
    for key in emptied:
        gone |= {item.get("id") or item.get("key") for item in data.get(key, [])}
        data[key] = []
    data["phases"] = [dict(p, activate=[k for k in p.get("activate", []) if k not in gone],
                           deactivate=[k for k in p.get("deactivate", []) if k not in gone])
                      for p in data.get("phases", [])]
    return Project.model_validate(data)


# ── The "Uniform" normal load, at both orders ────────────────────────────────

def soil_block(load_points=None, pressure: float = 50_000.0) -> Project:
    p = excavation.excavation_project(staged=False).model_dump(mode="json")
    p.update(beams=[], anchors=[], interfaces=[], loads=[], normal_loads=[], phases=[],
             water=None)
    if load_points:
        p["normal_loads"] = [{"id": "surcharge", "name": "Surcharge", "points": load_points,
                              "fluid_pressure_type": "Uniform", "pressure": pressure}]  # Pa
    return Project.model_validate(p)


def nodes_block(export: dict) -> str:
    mdpa = export["mdpa"]
    return mdpa[mdpa.index("Begin Nodes"):mdpa.index("End Nodes")]


def deep_vertical_stress(directory: Path, stage: int = 1) -> float:
    run_id = directory.name
    stress = results.stage_results(run_id, stage).field("CAUCHY_STRESS_TENSOR")
    mesh = results.stage_mesh(run_id, stage)
    values = []
    for element, points in stress.values.items():
        corners = mesh.connectivity(element)[:3]
        cx = sum(mesh.nodes[c][0] for c in corners) / 3
        cy = sum(mesh.nodes[c][1] for c in corners) / 3
        if -20 < cy < -10 and 20 < cx < 40:       # deep, clear of the side boundaries
            values.append(sum(p[1] for p in points) / len(points))
    assert len(values) > 10
    return sum(values) / len(values)


@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("direction", ["left to right", "right to left"])
def test_a_uniform_normal_load_adds_its_pressure_at_depth(order, direction):
    """The unloaded run carries the same line at zero pressure. The line is part of the
    geometry, so without it gmsh meshes the block differently, and the two window
    averages then sit at different mean depths: in the test model's sand, 0.47 m
    apart in one column, which gravity turns into 9 kPa of the 'surcharge'."""
    d = soil_block().domain
    line = [(d.x0, d.y_top), (d.x1, d.y_top)]
    if direction == "right to left":
        line.reverse()
    unloaded_export, unloaded = run(soil_block(line, pressure=0.0), order=order)
    loaded_export, loaded = run(soil_block(line), order=order)
    assert nodes_block(loaded_export) == nodes_block(unloaded_export), "not the same mesh"
    change = (deep_vertical_stress(Path(loaded["directory"]))
              - deep_vertical_stress(Path(unloaded["directory"])))
    assert change == pytest.approx(-50_000.0, rel=0.01), (
        f"{change:.0f} Pa: 50 kPa of surcharge, compression negative in Kratos")


# ── First order ─────────────────────────────────────────────────────────────

def peak_moment(export: dict, outcome: dict, stage: str) -> tuple[float, float]:
    directory = Path(outcome["directory"])
    output = result_members.read_output(
        (directory / f"{stage}__output_wall.json").read_text(encoding="utf-8"))
    deck = mdpa.parse(export["mdpa"])
    moments = {deck.nodes[n][1]: v["BENDING_MOMENT"] for n, v in output.items()
               if "BENDING_MOMENT" in v}
    return max(moments.items(), key=lambda item: abs(item[1]))


def test_a_first_order_section_with_a_pile_bends_it_like_second_order():
    """The straight 2-node beam (the curved one does not exist), without interfaces:
    both orders of the same model must tell the same story about the wall."""
    project = without(excavation.excavation_project(staged=True), interfaces=[])
    settings = project.mesh.model_dump()
    linear = run(project, order=1, size=settings["element_size"])
    quadratic = run(project, order=2, size=settings["element_size"])
    y1, m1 = peak_moment(*linear, "7_Third_excavation")
    y2, m2 = peak_moment(*quadratic, "7_Third_excavation")
    assert "LinearTimoshenkoBeamElement2D2N" in linear[0]["mdpa"]
    assert abs(m1) == pytest.approx(abs(m2), rel=0.15)
    assert abs(y1 - y2) <= 1.0


@pytest.mark.xfail(strict=True, reason=(
    "Kratos has no linear U-Pw line interface (test_kratos_registry KNOWN_MISSING); "
    "which element replaces it is the owner's modelling decision"))
def test_a_first_order_section_with_interfaces_runs():
    project = excavation.excavation_project(staged=True)
    run(project, order=1, size=project.mesh.element_size)


# ── 3D ──────────────────────────────────────────────────────────────────────

def solid_excavation() -> Project:
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        try:
            client.put("/api/project", json=excavation.excavation_project(staged=True).model_dump(mode="json"))
            assert client.patch("/api/project/dimension", json={"dimension": 3}).status_code == 200
            return Project.model_validate(client.get("/api/project").json())
        finally:
            client.post("/api/project/reset")


def test_the_3d_seed_with_its_surface_load_runs_and_settles():
    export, outcome = run(seed.seed_project(), order=1, size=10.0)
    run_id = Path(outcome["directory"]).name
    stages = results.describe(run_id)["stages"]
    u = results.stage_results(run_id, len(stages)).field("TOTAL_DISPLACEMENT")
    assert min(v[1] for v in u.values.values()) < 0.0, "the ground settles under its weight"


@pytest.mark.parametrize("order", [1, 2])
def test_3d_excavation_runs_every_stage_without_its_surcharge(order):
    solid = solid_excavation()
    run(without(solid, loads=[]), order=order, size=10.0 if order == 1 else 12.0)


@pytest.mark.xfail(strict=True, reason=(
    "Kratos' FindNeighbourElementsOfConditions asks every element for its faces when a "
    "stage has face conditions, and the strut (a line) has none: Geometry::GenerateFaces "
    "throws in stage 5. A Kratos limitation or a condition-class choice -- owner's call"))
def test_3d_excavation_with_its_surcharge_runs_every_stage():
    run(solid_excavation(), order=1, size=10.0)
