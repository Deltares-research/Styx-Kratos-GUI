"""Saved projects from older versions still open, and re-save stably (plan alpha 1.9).

A saved project is the one thing this application cannot re-derive, so every shape it
has ever written must keep loading. `tests/fixtures/projects/` holds real files saved by
earlier versions:

* `single_load_2d.json` -- the oldest shape here: one `load` with a `magnitude`, the
  anchor rows as a dict under `anchors`, an excavation with only `floor_y`, and the
  `simple_example` key before it became `layered_soil`. No phases, interfaces, normal
  loads, panels or deck at all.
* `simple_example_3d.json` -- the 3D seed as saved before the `layered_soil` rename.

Each must (1) load, (2) mean what it meant -- the migrated fields carry the old values --
(3) re-save as a fixed point: loading what was saved gives back the same document, so
opening and saving a file never drifts it, and (4) still mesh and export.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.geometry import build
from core.kratos import export as kratos
from core.model.schemas import MeshRequest, Project

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "projects"
SAVED = sorted(FIXTURES.glob("*.json"))


def raw(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_there_are_saved_projects_to_check():
    assert len(SAVED) >= 2


@pytest.mark.parametrize("path", SAVED, ids=lambda p: p.stem)
def test_an_old_project_loads_and_resaves_as_a_fixed_point(path):
    first = Project.model_validate(json.loads(path.read_text(encoding="utf-8")))
    saved = first.model_dump(mode="json")
    again = Project.model_validate(saved).model_dump(mode="json")

    assert again == saved


def test_the_oldest_shape_keeps_its_meaning():
    old = raw("single_load_2d.json")
    project = Project.model_validate(old)

    assert project.dimension == 2
    assert project.excavation.levels == [old["excavation"]["floor_y"]]
    assert project.excavation.floor_y == old["excavation"]["floor_y"]
    assert project.layered_soil == old["simple_example"]
    assert project.anchors == []
    assert project.anchor_rows.model_dump() == {**project.anchor_rows.model_dump(),
                                                **old["anchors"]}
    assert len(project.loads) >= 1
    assert project.phases == [] and project.interfaces == [] and project.deck is None


def test_the_single_load_keeps_its_magnitude_and_footprint():
    old = raw("single_load_2d.json")["load"]
    project = Project.model_validate(raw("single_load_2d.json"))

    magnitudes = [abs(c) for load in project.loads for c in load.components if c]
    # kN/m2 then, Pa now: the project is converted into SI on load (core/model/legacy.py).
    assert old["magnitude"] * 1000 in magnitudes
    assert any(getattr(load, "x0", None) == old["x0"] and getattr(load, "x1", None) == old["x1"]
               for load in project.loads)


@pytest.mark.parametrize("path", SAVED, ids=lambda p: p.stem)
def test_an_old_project_goes_through_the_api_unchanged(path):
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        try:
            put = client.put("/api/project", json=json.loads(path.read_text(encoding="utf-8")))
            assert put.status_code == 200, put.text[:300]
            echoed = client.get("/api/project").json()
            assert client.put("/api/project", json=echoed).status_code == 200
            assert client.get("/api/project").json() == echoed
        finally:
            client.post("/api/project/reset")


@pytest.mark.parametrize("path", SAVED, ids=lambda p: p.stem)
def test_an_old_project_still_meshes_and_exports(path):
    project = Project.model_validate(json.loads(path.read_text(encoding="utf-8")))
    with build.session():
        export = kratos.export_project(project, MeshRequest(element_size=8.0, order=1))

    assert len(export["nodes"]) > 0 and len(export["elements"]) > 0
    assert "Begin Nodes" in export["mdpa"] and "Begin Elements" in export["mdpa"]
