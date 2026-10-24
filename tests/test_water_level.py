"""The water level is the project's own, not a default every model is born with.

It used to be required, and the blank project -- what the server opens on and what New
project gives -- carried `WaterLevel(y=-1.5)`: a phreatic level nobody asked for, in
every model. Now `Project.water` is optional. A model that has one (the test model, a
file saved with one) keeps it; a new one has none until the user sets it (`PUT /api/project/water`, or `water <level>` on the command line).

The level fixes no pressure by itself, and no water pressure condition reads it: a
condition carries its own level (`WaterPressureCondition.reference_coordinate`), which a
new one is given from the project's (`core.model.drafts`). Moving or removing the level
afterwards leaves the condition where it is. A dry model of the seed's soil needs no
condition at all, because that soil's pressure stays as it starts (`CONSTANT_PW_FIELD`).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend import store
from core.geometry import solid_model, meshing
from core.kratos import writer
from backend.main import app
from core.model.schemas import MeshRequest, Project
from tests.models import excavation
from tests.models.excavation import excavation_project
from core.model.templates import blank_project, seed_project


@pytest.fixture(scope="module")
def session():
    with solid_model.session():
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


def test_the_test_model_keeps_its_own():
    assert excavation_project().water.y == excavation.WATER_Y


def test_a_project_saved_with_a_water_level_still_opens_with_it():
    payload = seed_project().model_dump()
    assert Project.model_validate(payload).water.y == payload["water"]["y"]


def test_a_hydrostatic_water_load_saved_without_a_level_needs_a_water_level():
    """Its pressure is derived from `Project.water`; with none there is nothing to derive
    it from, and a silent zero would be a wall with no water on it."""
    payload = excavation_project().model_dump()
    for load in payload["normal_loads"]:
        load["reference_coordinate"] = None
    payload["water"] = None
    with pytest.raises(ValueError, match="water level"):
        Project.model_validate(payload)


# ── The deck ────────────────────────────────────────────────────────────────

def test_removing_the_water_level_leaves_the_condition_s_own_level(session):
    project = dry(seed_project())
    exported = writer.export_project(project, MeshRequest(element_size=6.0, order=1))
    parameters = pressure_process(exported)
    assert parameters["fluid_pressure_type"] == "Hydrostatic"
    assert parameters["is_fixed"] is True
    assert parameters["reference_coordinate"] == -1.5
    assert parameters["specific_weight"] == 10_000.0


def test_moving_the_water_level_does_not_move_the_condition(session):
    project = seed_project()
    project.water.y = -4.25
    exported = writer.export_project(project, MeshRequest(element_size=6.0, order=1))
    assert pressure_process(exported)["reference_coordinate"] == -1.5


def test_a_dry_model_builds_no_water_slab(session):
    project = dry(seed_project(simple=False))
    built = solid_model.build_geometry(project)
    assert not built.volumes.get("water")


# ── The mesh ────────────────────────────────────────────────────────────────

def test_the_water_level_is_a_line_part_of_the_mesh(session):
    """So the Model explorer's colour toggle can draw it on the mesh, in Mesh mode, like
    any other part: across the domain and the slab's overhang, at the level."""
    project = excavation_project()
    mesh = meshing.mesh_project(project)
    (water,) = [part for part in mesh.parts if part.key == "water"]
    assert not water.indices
    xs = water.edges[0::3]
    ys = water.edges[1::3]
    assert set(ys) == {excavation.WATER_Y}
    margin = project.water.margin
    assert min(xs) == pytest.approx(project.domain.x0 - margin)
    assert max(xs) == pytest.approx(project.domain.x1 + margin)


def test_a_dry_model_has_no_water_part(session):
    payload = excavation_project().model_dump()
    payload["water"] = None
    payload["normal_loads"] = []
    payload["stages"] = []
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
    """One saved without a level of its own, which reads the project's."""
    payload = excavation_project().model_dump()
    for load in payload["normal_loads"]:
        load["reference_coordinate"] = None
    store.put(Project.model_validate(payload))
    response = client.put("/api/project/water", json={"water": None})
    assert response.status_code == 422
    assert "water level" in response.text
