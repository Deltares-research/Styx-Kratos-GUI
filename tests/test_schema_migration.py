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

from core.geometry import solid_model
from core.kratos import writer
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
    # kN/m2 then, Pa now: the project is converted into SI on load (core/model/migration.py).
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
    with solid_model.session():
        export = writer.export_project(project, MeshRequest(element_size=8.0, order=1))

    assert len(export["nodes"]) > 0 and len(export["elements"]) > 0
    assert "Begin Nodes" in export["mdpa"] and "Begin Elements" in export["mdpa"]

# -- "phases" became "stages" (2026-10): Kratos' word for the construction sequence --

def test_rename_phases_moves_the_key():
    from core.model import migration
    old = {"name": "x", "phases": [{"id": "phase_1", "name": "Initial"}]}
    assert migration.rename_phases(old) == {
        "name": "x", "stages": [{"id": "phase_1", "name": "Initial"}]}


def test_rename_phases_leaves_a_current_document_alone():
    from core.model import migration
    new = {"stages": []}
    assert migration.rename_phases(new) is new


def test_old_code_overriding_a_new_dump_keeps_working():
    from core.model import migration
    merged = {"stages": [{"id": "b"}]} | {"phases": [{"id": "a"}]}
    assert migration.rename_phases(merged) == {"stages": [{"id": "a"}]}


def test_a_project_saved_with_phases_opens_with_stages():
    from core.model import stages, templates
    project = templates.blank_project()
    project = project.model_copy(update={"stages": stages.default_stages(project)})
    doc = project.model_dump(mode="json")
    doc["phases"] = doc.pop("stages")
    opened = Project.model_validate(doc)
    assert [s.id for s in opened.stages] == ["initial", "null_step"]
    assert "phases" not in opened.model_dump(mode="json")


def test_the_old_names_still_resolve():
    from core.model import templates
    from core.model.schemas import Phase, Stage
    assert Phase is Stage
    project = templates.blank_project()
    assert project.phases is project.stages


def test_an_old_model_copy_with_phases_still_sets_the_stages():
    from core.model import stages, templates
    project = templates.blank_project()
    copied = project.model_copy(update={"phases": stages.default_stages(project)})
    assert [s.id for s in copied.stages] == ["initial", "null_step"]


# ── Boreholes, removed on 2026-10-24 ────────────────────────────────────────

@pytest.mark.parametrize("path", SAVED, ids=lambda p: p.stem)
def test_a_project_saved_with_boreholes_takes_the_first_boreholes_levels(path):
    """Every saved file here has boreholes. Each layer opens with the levels of the
    first borehole, the only levels the geometry ever read, so the mesh and the deck stay
    the same."""
    old = json.loads(path.read_text(encoding="utf-8"))
    first = old["boreholes"][0]["id"]

    project = Project.model_validate(old)

    assert [(layer.id, layer.top, layer.bottom) for layer in project.layers] == [
        (layer["id"], layer["tops"][first], layer["bots"][first]) for layer in old["layers"]]
    assert "boreholes" not in project.model_dump(mode="json")


def _with_boreholes(order: list[str]) -> dict:
    """The seed in the shape saved between the unit system and 2026-10-24: three
    boreholes, in `order`, each layer with different levels at each."""
    from core.model.templates import seed_project
    doc = seed_project().model_dump(mode="json")
    levels = {"bh1": [(0.0, -8.0), (-8.0, -25.0)],
              "bh2": [(-0.4, -9.2), (-9.2, -25.0)],
              "bh3": [(0.2, -7.2), (-7.2, -25.0)]}
    doc["boreholes"] = [{"id": bh, "name": bh.upper(), "x": 0.0, "y": 0.0, "head": 0.0,
                         "water": -1.5} for bh in order]
    for index, layer in enumerate(doc["layers"]):
        del layer["top"], layer["bottom"]
        layer["tops"] = {bh: levels[bh][index][0] for bh in order}
        layer["bots"] = {bh: levels[bh][index][1] for bh in order}
    return doc


def test_a_layer_with_different_levels_at_two_boreholes_takes_the_first():
    assert [(layer.top, layer.bottom) for layer in Project.model_validate(
        _with_boreholes(["bh1", "bh2", "bh3"])).layers] == [(0.0, -8.0), (-8.0, -25.0)]
    assert [(layer.top, layer.bottom) for layer in Project.model_validate(
        _with_boreholes(["bh2", "bh1", "bh3"])).layers] == [(-0.4, -9.2), (-9.2, -25.0)]


def test_a_current_shape_project_with_boreholes_keeps_its_deck():
    """Not a legacy file: the migration of boreholes runs on its own, and the deck is
    the deck of the same model with the first borehole's levels."""
    from core.model import migration
    from core.model.templates import seed_project
    doc = _with_boreholes(["bh1", "bh2", "bh3"])
    assert not migration.is_legacy(doc)

    deck = writer.export_project(Project.model_validate(doc))

    assert deck["mdpa"] == writer.export_project(seed_project())["mdpa"]


def test_a_layer_already_in_the_new_shape_is_left_alone():
    from core.model import migration
    doc = {"boreholes": [{"id": "bh1"}],
           "layers": [{"id": "L1", "name": "L1", "mat": "m", "top": 1.0, "bottom": 0.0}]}
    assert migration.drop_boreholes(doc) == {
        "layers": [{"id": "L1", "name": "L1", "mat": "m", "top": 1.0, "bottom": 0.0}]}
