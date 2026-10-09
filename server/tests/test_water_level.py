"""The water level is the project's own, not a default every model is born with.

It used to be required, and the blank project -- what the server opens on and what New
project gives -- carried `WaterLevel(y=-1.5)`: a phreatic level nobody asked for, at
the CROW case's depth, in every model. Now `Project.water` is optional. A model that
has one (CROW, a file saved with one) keeps it; a new one has none until the user sets
it (`PUT /api/project/water`, or `water <level>` on the command line).

A dry model still has to say something about pore pressure: the `U_Pw` elements' pressure
degrees of freedom are unconstrained without it, which is one of the defects only a run
found (memory: run-the-deck-reading-it-is-not-enough). It keeps the very same process
the validated decks use, referenced to the bottom of the model. That is zero everywhere
and still fixed, because Kratos' `ApplyConstantHydrostaticPressureProcess` writes
`min(-gamma * (ref - y), pressure_tension_cut_off)` and the cut-off defaults to 0 --
read from applications/GeoMechanicsApplication/custom_processes/
apply_constant_hydrostatic_pressure_process.cpp, and borne out by a real run in
`test_crow_results.py::test_pore_pressure_is_hydrostatic_below_the_water_table_and_zero_above_it`.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import build, kratos, meshing, store
from app.crow import crow_project
from app.main import app
from app.schemas import MeshRequest, Project
from app.seed import blank_project, seed_project


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


def dry(project: Project) -> Project:
    payload = project.model_dump()
    payload["water"] = None
    return Project.model_validate(payload)


def pressure_process(export: dict) -> dict:
    doc = json.loads(export["project_parameters"])
    stage = next(iter(doc["stages"].values()))
    (process,) = [p for p in stage["stage_settings"]["processes"]["constraints_process_list"]
                  if p["python_module"] == "apply_scalar_constraint_table_process"]
    return process["Parameters"]


# ── The project ─────────────────────────────────────────────────────────────

def test_a_new_project_has_no_water_level():
    assert blank_project().water is None


def test_the_crow_case_keeps_its_own():
    assert crow_project().water.y == -1.5


def test_a_project_saved_with_a_water_level_still_opens_with_it():
    payload = seed_project().model_dump()
    assert Project.model_validate(payload).water.y == payload["water"]["y"]


def test_a_hydrostatic_water_load_needs_a_water_level():
    """Its pressure is derived from `Project.water`; with none there is nothing to derive
    it from, and a silent zero would be a wall with no water on it."""
    payload = crow_project().model_dump()
    payload["water"] = None
    with pytest.raises(ValueError, match="water level"):
        Project.model_validate(payload)


# ── The deck ────────────────────────────────────────────────────────────────

def test_a_dry_model_still_fixes_its_pore_pressure_at_zero(session):
    project = dry(seed_project())
    exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    parameters = pressure_process(exported)
    assert parameters["fluid_pressure_type"] == "Hydrostatic"
    assert parameters["is_fixed"] is True
    # The bottom of the model: every node is at or above it, so every pressure is
    # clamped to the zero cut-off.
    assert parameters["reference_coordinate"] == project.domain.y_bottom
    assert parameters["specific_weight"] == 10_000.0


def test_a_wet_model_is_unchanged(session):
    project = seed_project()
    project.water.y = -4.25
    exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    assert pressure_process(exported)["reference_coordinate"] == -4.25


def test_a_dry_model_builds_no_water_slab(session):
    project = dry(seed_project(simple=False))
    built = build.build_geometry(project)
    assert not built.volumes.get("water")


# ── The mesh ────────────────────────────────────────────────────────────────

def test_the_water_level_is_a_line_part_of_the_mesh(session):
    """So the Model explorer's colour toggle can draw it on the mesh, in Mesh mode, like
    any other part: across the domain and the slab's overhang, at the level."""
    project = crow_project()
    mesh = meshing.mesh_project(project)
    (water,) = [part for part in mesh.parts if part.key == "water"]
    assert not water.indices
    xs = water.edges[0::3]
    ys = water.edges[1::3]
    assert set(ys) == {-1.5}
    margin = project.water.margin
    assert min(xs) == pytest.approx(project.domain.x0 - margin)
    assert max(xs) == pytest.approx(project.domain.x1 + margin)


def test_a_dry_model_has_no_water_part(session):
    payload = crow_project().model_dump()
    payload["water"] = None
    payload["normal_loads"] = []
    payload["phases"] = []
    mesh = meshing.mesh_project(Project.model_validate(payload))
    assert "water" not in {part.key for part in mesh.parts}


# ── Setting and removing it ─────────────────────────────────────────────────

@pytest.fixture
def client():
    store.reset()
    with TestClient(app) as test_client:
        yield test_client
    store.reset()


def test_the_water_level_can_be_set_and_removed(client):
    client.post("/api/project/new")
    assert client.get("/api/project").json()["water"] is None

    response = client.put("/api/project/water", json={"water": {"y": -2.0}})
    assert response.status_code == 200, response.text
    assert response.json()["project"]["water"]["y"] == -2.0
    assert client.get("/api/project").json()["water"]["y"] == -2.0

    response = client.put("/api/project/water", json={"water": None})
    assert response.status_code == 200, response.text
    assert client.get("/api/project").json()["water"] is None


def test_a_water_level_cannot_be_removed_from_under_a_hydrostatic_load(client):
    store.put(crow_project())
    response = client.put("/api/project/water", json={"water": None})
    assert response.status_code == 422
    assert "water level" in response.text
