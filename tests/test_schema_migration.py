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
    # One level dug nothing in a layered model, so the pit goes.
    assert old["excavation"] and project.excavation is None
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
    from core.model import templates
    from core.model.schemas import Stage
    project = templates.blank_project()
    project = project.model_copy(update={"stages": [Stage(id="initial", name="Initial stage", stress_initialisation="K0"),
                  Stage(id="null_step", name="Null step", parent="initial")]})
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
    from core.model import templates
    from core.model.schemas import Stage
    project = templates.blank_project()
    copied = project.model_copy(update={"phases": [Stage(id="initial", name="Initial stage", stress_initialisation="K0"),
                  Stage(id="null_step", name="Null step", parent="initial")]})
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


def test_gravity_off_is_noted_where_it_has_no_equivalent():
    """`migration.notes`: gravity off becomes an initial stage that initialises no
    stresses (`migration.drop_gravity`), which a project with no stages and a flow
    sequence do not have, so opening one says what it loses."""
    from core.model import migration
    from tests.models import muskat
    from tests.models.excavation import excavation_project
    staged = excavation_project().model_dump(mode="json")
    flow = muskat.muskat().model_dump(mode="json")
    assert migration.notes({**staged, "gravity": False}) == []
    assert migration.notes({**staged, "gravity": True}) == []
    assert migration.notes(staged) == []
    [unstaged] = migration.notes({**staged, "stages": [], "gravity": False})
    assert "no stages" in unstaged
    old = [{**stage, "calculation": "Groundwater flow"} for stage in flow["stages"]]
    for stages in (flow["stages"], old):
        [flowing] = migration.notes({**flow, "stages": stages, "gravity": False})
        assert "flow calculation" in flowing


def test_an_old_van_genuchten_flow_stage_keeps_its_absolute_tolerance():
    """`migration.flow_tolerance`: an old flow stage was written with the tolerance of
    the deck its strategy came from, 1e-15 for Newton-Raphson; with a seepage face, or
    in the current shape, the stage has its criterion's default."""
    from tests.models import muskat
    document = muskat.van_genuchten().model_dump(mode="json")
    old = [{key: value for key, value in stage.items() if key != "absolute_tolerance"}
           | {"calculation": "Groundwater flow"} for stage in document["stages"]]
    [stage] = Project.model_validate({**document, "stages": old}).stages
    assert stage.absolute_tolerance == 1e-15
    current = [{key: value for key, value in stage.items() if key != "absolute_tolerance"}
               for stage in document["stages"]]
    assert Project.model_validate({**document, "stages": current}).stages[0] \
        .absolute_tolerance == 1e-9
    seepage = muskat.seepage().model_dump(mode="json")
    old = [{key: value for key, value in stage.items() if key != "absolute_tolerance"}
           | {"calculation": "Groundwater flow"} for stage in seepage["stages"]]
    assert Project.model_validate({**seepage, "stages": old}).stages[0] \
        .absolute_tolerance == 1e-9


def test_an_old_van_genuchten_flow_stage_keeps_its_tolerance_with_gravity_off():
    """`migration.drop_gravity` leaves an old flow stage as it was saved, so that
    `migration.flow_tolerance` still knows it."""
    from tests.models import muskat
    document = muskat.van_genuchten().model_dump(mode="json")
    old = [{key: value for key, value in stage.items()
            if key not in ("absolute_tolerance", "convergence_criterion")}
           | {"calculation": "Groundwater flow"} for stage in document["stages"]]
    for gravity in (True, False):
        [stage] = Project.model_validate({**document, "stages": old,
                                          "gravity": gravity}).stages
        assert (stage.calculation, stage.convergence_criterion,
                stage.absolute_tolerance) == ("flow", "residual_criterion", 1e-15), gravity


def test_an_old_later_k0_procedure_can_be_set_to_none_and_then_edited():
    """An old project whose later stage was a K0 procedure opens with a later stage
    initialised by K0, which every stage edit is refused with until it is none
    (`stages.check_settings`). The Stages window's edit sets it to none."""
    from core import session
    from core.model import stages
    from core.model.schemas import StagesUpdate
    document = json.loads((FIXTURES / "staged_v1.json").read_text(encoding="utf-8"))
    document["phases"][1]["calculation"] = "K0 procedure"
    project = Project.model_validate(document)
    later = project.stages[1]
    assert later.parent is not None and later.stress_initialisation == "K0"

    def replaced(listed):
        return session.replace_stages(project, StagesUpdate.model_validate(
            {"stages": [stage.model_dump() for stage in listed]}))

    with pytest.raises(stages.StageError, match="only the initial stage"):
        replaced(stages.edited(project, later.id, "name", "renamed"))
    project = replaced(stages.edited(project, later.id, "stress_initialisation", "none"))
    project = replaced(stages.edited(project, later.id, "name", "renamed"))
    assert (project.stages[1].name, project.stages[1].stress_initialisation) == \
        ("renamed", "none")


# ── A saved pit opens as lines ──────────────────────────────────────────────

def _saved_pit(**pit) -> dict:
    """A layered project as it was saved with a pit: soil_top is 0..-8, soil_bottom the
    rest of the domain, which is 0..40 wide."""
    return {
        "name": "Saved pit", "layered_soil": True, "dimension": 2,
        "domain": {"x0": 0.0, "x1": 40.0, "z0": 0.0, "z1": 10.0,
                   "y_top": 0.0, "y_bottom": -30.0},
        "materials": [{"id": "m", "name": "Clay", "color": "#c4a86a", "constitutive_law":
                       "GeoLinearElasticPlaneStrain2DLaw", "variables": {}}],
        "layers": [{"id": "top", "name": "Top", "mat": "m", "top": 0.0, "bottom": -8.0},
                   {"id": "bottom", "name": "Bottom", "mat": "m", "top": -8.0, "bottom": -30.0}],
        "excavation": {"x0": 0.0, "x1": 5.0, "z0": 0.0, "z1": 10.0, "levels": [-2.0, -8.0]}
        | pit,
    }


def test_a_saved_pit_opens_as_lines_with_the_keys_and_names_it_had():
    project = Project.model_validate(_saved_pit())

    assert project.excavation is None
    # The second level is the boundary between the layers, so it needs no line.
    assert [line.id for line in project.lines] == ["pit_side", "pit_level_1"]
    assert project.soil_body_labels == {
        "soil_top__lift1": "Top · lift 1", "soil_top__lift2": "Top · lift 2",
        "soil_top__outside": "Top · outside the pit",
        "soil_bottom__pit": "Bottom · below the pit",
        "soil_bottom__outside": "Bottom · outside the pit"}


def test_a_saved_pit_keeps_what_its_stages_switch():
    """A lift keeps its key. The ground outside the pit had the layer's plain key, which a
    cut layer does not have any more."""
    project = Project.model_validate(_saved_pit() | {"stages": [
        {"id": "first", "name": "First", "deactivate": ["soil_top"]},
        {"id": "dig", "name": "Dig", "parent": "first", "activate": ["soil_top"],
         "deactivate": ["soil_top__lift1"]}]})

    assert project.stages[0].deactivate == ["soil_top__outside"]
    assert project.stages[1].activate == ["soil_top__outside"]
    assert project.stages[1].deactivate == ["soil_top__lift1"]


def test_a_saved_pit_in_the_middle_of_the_model_has_ground_on_both_sides():
    project = Project.model_validate(_saved_pit(x0=10.0, x1=20.0) | {"stages": [
        {"id": "first", "name": "First", "deactivate": ["soil_top"]}]})

    assert [line.id for line in project.lines] == ["pit_side", "pit_side_left", "pit_level_1"]
    assert set(project.stages[0].deactivate) == {"soil_top__outside_left",
                                                 "soil_top__outside_right"}


def test_a_saved_pit_is_saved_as_lines_and_opens_the_same_again():
    project = Project.model_validate(_saved_pit())
    saved = project.model_dump(mode="json")

    assert "excavation" not in saved
    assert Project.model_validate(saved).model_dump(mode="json") == saved


def test_a_saved_pit_of_one_level_dug_nothing_so_it_just_goes():
    project = Project.model_validate(_saved_pit(levels=[-2.0]))

    assert project.excavation is None and project.lines == []
    assert project.soil_body_keys == ["soil_top", "soil_bottom"]


def test_a_saved_3d_pit_narrower_than_the_model_is_refused():
    with pytest.raises(ValueError, match="a line cuts across the whole domain"):
        Project.model_validate(_saved_pit(z0=2.0, z1=8.0) | {"dimension": 3})


def test_a_model_script_that_still_passes_a_pit_gets_lines_too():
    from core.model.schemas import Excavation
    payload = Project.model_validate(_saved_pit()).model_dump() | {"lines": [], "bodies": []}
    project = Project(**payload | {
        "excavation": Excavation(x0=0.0, x1=5.0, z0=0.0, z1=10.0, levels=[-2.0, -8.0])})

    assert project.excavation is None and "soil_top__lift1" in project.soil_body_keys

