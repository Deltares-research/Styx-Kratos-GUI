"""Deleting custom parts must never leave the stored project invalid.

Both delete routes used to mutate the stored project in place and skip validation. A
phase that still named the deleted part then made every later validated edit -- layers,
materials, structures, phases -- fail with 422 "phase ... names no such part", and the
only way out was a reset (plan/active/full-test-and-validation-plan.md, finding F3).

The policy pinned here:

* a part a **phase** names is not deleted: 422 naming the phase, nothing changes. Which
  phases should lose the part is a modelling decision the user makes, not this route;
* a part the **mesh settings** name (`body_sizes`) is deleted, and its size entry goes
  with it: a size is a property *of* that part and means nothing without it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.post("/api/project/reset")
        yield c
        c.post("/api/project/reset")


def _box(client, origin=(0, 0, 0), label="Box") -> str:
    response = client.post("/api/geometry/create", json={
        "kind": "box", "origin": list(origin), "size": [1, 1, 1], "label": label,
    })
    assert response.status_code == 200, response.text
    return response.json()["parts"][0]["key"]


def _phase_naming(client, key: str) -> None:
    response = client.patch("/api/project/phases", json={"phases": [
        {"id": "initial", "name": "Initial stage"},
        {"id": "dig_1", "name": "Dig", "parent": "initial", "deactivate": [key]},
    ]})
    assert response.status_code == 200, response.text


def _layers_patch_still_works(client) -> None:
    layers = client.get("/api/project").json()["layers"]
    response = client.patch("/api/project/layers", json={"layers": layers})
    assert response.status_code == 200, response.text


def test_deleting_a_part_a_phase_names_is_refused_naming_the_phase(client):
    key = _box(client)
    _phase_naming(client, key)

    response = client.delete(f"/api/geometry/parts/{key}")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert key in detail and "dig_1" in detail
    assert key in [p["key"] for p in client.get("/api/project").json()["custom_parts"]]
    _layers_patch_still_works(client)


def test_clearing_custom_parts_a_phase_names_is_refused_naming_the_phase(client):
    key = _box(client)
    _box(client, origin=(5, 5, 0), label="Other")
    _phase_naming(client, key)

    response = client.delete("/api/project/custom_parts")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert key in detail and "dig_1" in detail
    assert len(client.get("/api/project").json()["custom_parts"]) == 2
    _layers_patch_still_works(client)


def test_a_part_freed_from_its_phases_can_then_be_deleted(client):
    key = _box(client)
    _phase_naming(client, key)
    client.patch("/api/project/phases", json={"phases": []})

    assert client.delete(f"/api/geometry/parts/{key}").status_code == 200
    _layers_patch_still_works(client)


def test_deleting_a_part_drops_its_mesh_size(client):
    key = _box(client)
    kept = _box(client, origin=(5, 5, 0), label="Other")
    project = client.get("/api/project").json()
    project["mesh"]["body_sizes"] = {key: 0.5, kept: 0.7}
    assert client.put("/api/project", json=project).status_code == 200

    assert client.delete(f"/api/geometry/parts/{key}").status_code == 200

    sizes = client.get("/api/project").json()["mesh"]["body_sizes"]
    assert sizes == {kept: 0.7}


def test_clearing_custom_parts_drops_their_mesh_sizes_only(client):
    project = client.get("/api/project").json()
    soil = project["soil_body_keys"][0]
    key = _box(client)
    project = client.get("/api/project").json()
    project["mesh"]["body_sizes"] = {key: 0.5, soil: 1.5}
    assert client.put("/api/project", json=project).status_code == 200

    assert client.delete("/api/project/custom_parts").status_code == 200

    assert client.get("/api/project").json()["mesh"]["body_sizes"] == {soil: 1.5}


def test_the_stored_project_is_valid_after_every_delete(client):
    """The store must only ever hold a project that validates; whatever a delete leaves
    behind is checked the same way a PUT would be."""
    from app import store
    from app.schemas import Project

    first = _box(client)
    _box(client, origin=(5, 5, 0), label="Other")
    client.delete(f"/api/geometry/parts/{first}")
    Project.model_validate(store.get().model_dump())
    client.delete("/api/project/custom_parts")
    Project.model_validate(store.get().model_dump())
    assert client.get("/api/project").json()["custom_parts"] == []


# ── A recipe that cannot be built is the caller's to fix: 422, not 500 ───────

@pytest.mark.parametrize("recipe,named", [
    ({"kind": "box", "origin": [0, 0, 0], "size": [0, 1, 1]}, "size"),
    ({"kind": "box", "origin": [0, 0, 0]}, "size"),
    ({"kind": "box", "size": [1, 1, 1]}, "origin"),
    ({"kind": "cylinder", "center": [0, 0, 0], "axis": [0, 0, 1], "radius": 0}, "radius"),
    ({"kind": "cylinder", "center": [0, 0, 0], "axis": [0, 0, 0], "radius": 1}, "axis"),
    ({"kind": "polygon_extrude", "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0]],
      "extrusion": [0, 0, 0]}, "extrusion"),
    ({"kind": "polygon", "vertices": [[0, 0, 0], [1, 0, 0], [2, 0, 0]]}, "area"),
])
def test_a_recipe_that_cannot_be_built_is_refused_with_its_reason(client, recipe, named):
    before = client.get("/api/project").json()["custom_parts"]

    response = client.post("/api/geometry/create", json={**recipe, "label": "Bad"})

    assert response.status_code == 422, response.text
    assert named in response.json()["detail"]
    assert client.get("/api/project").json()["custom_parts"] == before
