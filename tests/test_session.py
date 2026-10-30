"""`core.session`: the edits a project can be given, whoever gives them.

The HTTP routes and the command line (`cli/`, plan/active/cli-plan.md) are two front ends
on one model, and this is the one place an edit is made. Each function takes a `Project`
and returns a new one; the routes add only the HTTP around it. So these tests are about
the edit itself, and `tests/test_api.py` keeps checking what the routes answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from core import session
from core.model import stages
from core.model.schemas import (FULL_BUILD_BLOCKS, Deck, DimensionUpdate, LayersUpdate,
                                MaterialsUpdate, MeshRequest, Stage, StagesUpdate, Project, StructuresUpdate, UnitsUpdate,
                                WaterLevel, WaterUpdate)
from core.model.templates import blank_project, seed_project
from tests.models.excavation import excavation_project

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "projects"

BRICK = {"brep_path": "drawn.brep", "bbox": [0, 0, 0, 1, 1, 1]}
"""What the gmsh worker answers for a created or imported part: where the solid is, and
how far it reaches. The tests here never run gmsh; that is the worker's business."""


def staged() -> Project:
    """The seed with a pit dug in three lifts, so there is something to stage."""
    payload = seed_project(simple=False).model_dump()
    payload["excavation"] = {k: v for k, v in payload["excavation"].items() if k != "floor_y"}
    payload["excavation"] |= {"levels": [-3.0, -5.0, -7.0]}
    return Project.model_validate(payload)


def a_deck() -> Project:
    return blank_project().model_copy(update={"deck": Deck(directory="C:/decks/dike")})


def box(**extra) -> dict:
    return {"kind": "box", "origin": [0, 0, 0], "size": [1, 1, 1], **extra}


def with_box(project: Project, **extra) -> Project:
    built, _ = session.with_created_part(project, box(**extra), BRICK)
    return built


# ── Files ───────────────────────────────────────────────────────────────────

def test_a_saved_project_loads_back_the_same(tmp_path):
    project = seed_project()
    path = tmp_path / "site.json"

    session.save(project, path)

    assert session.load(path) == project


def test_a_saved_file_is_the_json_the_gui_saves(tmp_path):
    """The GUI's Save writes `GET /api/project` with `JSON.stringify(project, null, 2)`:
    indented, UTF-8, the name's dash as itself rather than as an escape."""
    path = tmp_path / "site.json"

    session.save(seed_project(), path)

    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == seed_project().model_dump(mode="json")
    assert "\n  \"name\": \"Deep excavation — Rotterdam Zuid\"" in text


def test_a_saved_file_leaves_out_the_blocks_a_model_does_not_have(tmp_path):
    path = session.save(blank_project(), tmp_path / "new.json")

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert not set(saved) & set(FULL_BUILD_BLOCKS)
    assert session.load(path) == blank_project()


def test_a_file_in_the_old_shape_is_migrated_on_load():
    """Loading goes through the schema, which converts a project saved before the
    Kratos-native inputs (`core.model.migration`) -- the same path the GUI's Open takes."""
    old = FIXTURES / "every_field_2d_v1.json"

    loaded = session.load(old)

    assert loaded == Project.model_validate(json.loads(old.read_text(encoding="utf-8")))
    assert loaded.unit_system == "SI"


def test_a_script_loads_as_the_project_it_describes(tmp_path):
    script = tmp_path / "model.py"
    script.write_text("from core.model.templates import seed_project\n"
                      "PROJECT = seed_project()\n", encoding="utf-8")

    assert session.load(script) == seed_project()


def test_a_missing_file_is_refused_by_name(tmp_path):
    with pytest.raises(session.ProjectFileError, match="nope.json"):
        session.load(tmp_path / "nope.json")


def test_a_file_that_is_not_a_project_is_refused(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(session.ProjectFileError, match="not a project file"):
        session.load(path)


def test_an_unreadable_json_file_is_refused_with_where(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{\"name\": ", encoding="utf-8")

    with pytest.raises(session.ProjectFileError, match="broken.json"):
        session.load(path)


def test_a_project_is_never_saved_into_a_script(tmp_path):
    with pytest.raises(session.ProjectFileError, match=r"\.json"):
        session.save(seed_project(), tmp_path / "model.py")


def test_a_failed_save_leaves_the_old_file_as_it_was(tmp_path, monkeypatch):
    path = tmp_path / "site.json"
    session.save(seed_project(), path)
    before = path.read_bytes()

    def broken(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(session.os, "replace", broken)
    with pytest.raises(OSError):
        session.save(blank_project(), path)

    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["site.json"]


def test_a_save_waits_out_a_file_another_program_holds_for_a_moment(tmp_path, monkeypatch):
    """Windows refuses to replace a file another program has open -- a virus scanner
    reading the file just written, an indexer -- with "Access is denied". That lasts
    milliseconds, and the save tries again rather than failing the edit."""
    path = tmp_path / "site.json"
    session.save(seed_project(), path)
    real, refusals = session.os.replace, []

    def held(source, target):
        if len(refusals) < 2:
            refusals.append(target)
            raise PermissionError(13, "Access is denied")
        real(source, target)

    monkeypatch.setattr(session.os, "replace", held)
    monkeypatch.setattr(session, "REPLACE_WAIT", 0.0)
    session.save(blank_project(), path)

    assert len(refusals) == 2
    assert session.load(path) == blank_project()


def test_a_file_held_for_good_is_refused_by_name(tmp_path, monkeypatch):
    path = tmp_path / "site.json"
    session.save(seed_project(), path)

    def held(source, target):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(session.os, "replace", held)
    monkeypatch.setattr(session, "REPLACE_WAIT", 0.0)
    with pytest.raises(session.ProjectFileError, match="site.json.*another program"):
        session.save(blank_project(), path)
    assert [p.name for p in tmp_path.iterdir()] == ["site.json"]


# ── Soil, water, materials, structures ──────────────────────────────────────

def test_replacing_layers_leaves_what_the_update_omits():
    project = seed_project()
    renamed = [project.layers[0].model_copy(update={"name": "Top"}), *project.layers[1:]]

    edited = session.replace_layers(project, LayersUpdate(layers=renamed))

    assert edited.layers[0].name == "Top"
    assert edited.materials == project.materials
    assert edited.domain == project.domain


def test_an_edit_never_changes_the_project_it_was_given():
    project = seed_project()
    before = project.model_copy(deep=True)

    session.set_water(project, WaterUpdate(water=None))
    session.with_created_part(project, box(), BRICK)

    assert project == before


def test_water_is_set_and_removed():
    project = session.set_water(blank_project(), WaterUpdate(water=WaterLevel(y=-2.0)))
    assert project.water.y == -2.0

    assert session.set_water(project, WaterUpdate(water=None)).water is None


def test_a_material_a_layer_uses_cannot_be_removed():
    project = seed_project()
    used = project.layers[0].mat
    remaining = [m for m in project.materials if m.id != used]

    with pytest.raises(ValidationError):
        session.replace_materials(project, MaterialsUpdate(materials=remaining))


def test_structures_replace_only_the_kinds_given():
    project = seed_project()

    edited = session.replace_structures(project, StructuresUpdate(loads=[]))

    assert edited.loads == []
    assert edited.beams == project.beams


# ── Stages ──────────────────────────────────────────────────────────────────

def test_stages_are_stored():
    sequence = [Stage(id="initial", name="Initial stage"),
                Stage(id="dig", name="Dig", parent="initial")]

    edited = session.replace_stages(staged(), StagesUpdate(stages=sequence))

    assert [p.id for p in edited.stages] == ["initial", "dig"]


def test_stages_that_branch_are_refused_naming_the_branches():
    sequence = [Stage(id="initial", name="Initial stage"),
                Stage(id="a", name="A", parent="initial"),
                Stage(id="b", name="B", parent="initial")]

    with pytest.raises(stages.StageError, match="'a'.*'b'|'b'.*'a'"):
        session.replace_stages(staged(), StagesUpdate(stages=sequence))


def test_the_default_stages_are_the_model_s_own():
    project = staged()

    assert session.default_stages(project).stages == stages.default_stages(project)


@pytest.mark.parametrize("edit", [
    lambda p: session.replace_stages(p, StagesUpdate(stages=[])),
    session.default_stages,
], ids=["replace", "defaults"])
def test_the_stages_of_a_deck_are_read_only(edit):
    with pytest.raises(session.DeckReadOnly, match="Edit the deck"):
        edit(a_deck())


# ── Dimension and units ─────────────────────────────────────────────────────

def test_switching_dimension_says_what_changed_shape():
    project = seed_project()

    edited, notes = session.set_dimension(project, DimensionUpdate(dimension=2))

    assert edited.dimension == 2
    assert isinstance(notes, list)


def test_switching_units_converts_the_project():
    project = seed_project()
    other = "SI" if project.unit_system == "kN" else "kN"

    edited, notes = session.set_units(project, UnitsUpdate(unit_system=other))

    assert edited.unit_system == other
    assert isinstance(notes, list)


# ── Custom parts ────────────────────────────────────────────────────────────

def test_a_created_part_gets_the_next_free_drawn_key():
    project = with_box(with_box(seed_project()), origin=[5, 5, 0])

    assert [p.key for p in project.custom_parts] == ["drawn_0", "drawn_1"]


def test_a_drawn_key_is_never_reused_after_a_delete():
    project = with_box(with_box(seed_project()), origin=[5, 5, 0])
    project = session.without_custom_part(project, "drawn_0")

    project = with_box(project, origin=[9, 9, 0])

    assert [p.key for p in project.custom_parts] == ["drawn_1", "drawn_2"]


def test_a_part_with_a_material_takes_its_colour():
    project = seed_project()
    material = project.materials[0]

    _, part = session.with_created_part(project, box(material=material.id), BRICK)

    assert (part.mat, part.color) == (material.id, material.color)


def test_a_part_with_an_unknown_material_is_refused():
    with pytest.raises(session.EditRefused, match="Unknown material 'nope'"):
        session.check_recipe(seed_project(), box(material="nope"))
    with pytest.raises(session.EditRefused, match="Unknown material 'nope'"):
        session.with_created_part(seed_project(), box(material="nope"), BRICK)


def test_a_part_in_exactly_the_space_of_another_is_refused():
    project = with_box(seed_project(), label="First")

    with pytest.raises(session.EditRefused, match="'First' already occupies"):
        session.check_recipe(project, box(label="Second"))


def test_a_replaced_part_keeps_its_key_and_place():
    project = with_box(with_box(seed_project()), origin=[5, 5, 0])
    recipe = box(origin=[2, 2, 0], replace="drawn_0")
    session.check_recipe(project, recipe)

    edited, part = session.with_created_part(project, recipe, BRICK)

    assert part.key == "drawn_0"
    assert [p.key for p in edited.custom_parts] == ["drawn_0", "drawn_1"]
    assert edited.custom_parts[0].recipe["origin"] == [2, 2, 0]


def test_a_part_can_be_put_before_another():
    project = with_box(seed_project())

    edited, part = session.with_created_part(
        project, box(origin=[5, 5, 0], insert_before="drawn_0"), BRICK)

    assert [p.key for p in edited.custom_parts] == [part.key, "drawn_0"]


@pytest.mark.parametrize("field", ["replace", "insert_before"])
def test_a_recipe_naming_a_part_that_is_not_there_is_refused(field):
    with pytest.raises(session.UnknownPart, match="'drawn_9'"):
        session.check_recipe(seed_project(), box(**{field: "drawn_9"}))


def test_an_imported_part_is_keyed_after_the_highest_import():
    project = seed_project()
    project, first = session.with_imported_part(project, "a.step", BRICK)
    project, second = session.with_imported_part(project, "b.step", BRICK)
    project = session.without_custom_part(project, first.key)

    project, third = session.with_imported_part(project, "c.step", BRICK)

    assert (first.key, second.key, third.key) == ("imported_0", "imported_1", "imported_2")
    assert (third.label, third.source, third.source_file) == ("c.step", "import", "drawn.brep")


def test_removing_a_part_takes_its_mesh_size_with_it():
    project = with_box(seed_project())
    payload = project.model_dump()
    payload["mesh"]["body_sizes"] = {"drawn_0": 0.5}
    project = Project.model_validate(payload)

    assert session.without_custom_part(project, "drawn_0").mesh.body_sizes == {}


def test_a_part_a_stage_uses_is_not_removed():
    project = with_box(seed_project())
    project = session.replace_stages(project, StagesUpdate(stages=[
        Stage(id="initial", name="Initial stage"),
        Stage(id="dig_1", name="Dig", parent="initial", deactivate=["drawn_0"])]))

    with pytest.raises(session.EditRefused, match="dig_1.*drawn_0"):
        session.without_custom_parts(project, ["drawn_0"])


def test_removing_a_part_that_is_not_there_is_refused():
    with pytest.raises(session.UnknownPart, match="'drawn_9'"):
        session.without_custom_part(seed_project(), "drawn_9")


# ── Any field, by path ──────────────────────────────────────────────────────
#
# What `kratos-cli get/set/add/remove` reach every field with. A record in a list is
# picked by its id (`key` for a custom part) rather than by its place, so a path still
# names the same record after the list is reordered; a list without ids takes an index.

def test_a_value_is_read_by_its_path():
    project = seed_project()

    assert session.value_at(project, "domain.y_bottom") == -25.0
    assert session.value_at(project, "layers[L2].mat") == project.layers[1].mat
    assert session.value_at(project, "layers[1].id") == "L2"
    assert session.value_at(project, "layers[L1].top") == project.layers[0].top
    young = project.materials[0].variables["YOUNG_MODULUS"]
    assert session.value_at(project, "materials[m1].variables[YOUNG_MODULUS]") == young
    assert session.value_at(project, "materials[m1].variables.YOUNG_MODULUS") == young
    assert session.value_at(project, "") == project.model_dump(mode="json")


def test_a_path_may_still_say_phases():
    project = session.default_stages(seed_project())

    assert session.value_at(project, "phases") == session.value_at(project, "stages")
    renamed = session.with_value(project, f"phases[{project.stages[0].id}].name", "First")
    assert renamed.stages[0].name == "First"


def test_a_path_that_names_nothing_says_what_is_there():
    with pytest.raises(session.PathError, match="no entry 'nope'.*L1, L2"):
        session.value_at(seed_project(), "layers[nope]")
    with pytest.raises(session.PathError, match="domain has no field 'depth'"):
        session.value_at(seed_project(), "domain.depth")
    with pytest.raises(session.PathError, match="layers is a list"):
        session.value_at(seed_project(), "layers.mat")
    with pytest.raises(session.PathError, match="not a path"):
        session.value_at(seed_project(), "layers[L1")


def test_a_value_is_set_by_its_path_and_validated():
    project = session.with_value(seed_project(), "mesh.element_size", 1.5)
    assert project.mesh.element_size == 1.5

    with pytest.raises(ValidationError):
        session.with_value(project, "mesh.element_size", -1)


def test_a_record_is_added_to_a_list_and_removed_by_id():
    project = seed_project()
    clay = project.materials[0].model_dump(mode="json") | {"id": "clay2", "name": "Clay 2"}

    added = session.with_added(project, "materials", clay)
    assert added.materials[-1].id == "clay2"

    assert [m.id for m in session.without_value(added, "materials[clay2]").materials] \
        == [m.id for m in project.materials]


def test_adding_to_something_that_is_not_a_list_is_refused():
    with pytest.raises(session.PathError, match="domain is not a list"):
        session.with_added(seed_project(), "domain", {"x0": 1})


def test_a_key_of_a_mapping_is_removed():
    project = with_box(seed_project())
    project = session.with_value(project, "mesh.body_sizes[drawn_0]", 0.5)

    assert session.without_value(project, "mesh.body_sizes[drawn_0]").mesh.body_sizes == {}


@pytest.mark.parametrize("path", ["dimension", "section_offset", "unit_system", "deck"])
def test_the_fields_with_an_edit_of_their_own_are_not_set_directly(path):
    """Switching the dimension translates loads, walls and laws; switching units converts
    every value. Setting either bare would leave the rest of the model behind."""
    with pytest.raises(session.EditRefused, match=path):
        session.with_value(seed_project(), path, 2)


def test_stages_set_by_path_still_have_to_run_in_one_order():
    project = session.with_value(staged(), "stages", [
        {"id": "initial", "name": "Initial stage"},
        {"id": "a", "name": "A", "parent": "initial"},
    ])
    with pytest.raises(stages.StageError):
        session.with_added(project, "stages", {"id": "b", "name": "B", "parent": "initial"})


def test_a_custom_part_removed_by_path_is_checked_against_the_stages():
    project = with_box(seed_project())
    project = session.replace_stages(project, StagesUpdate(stages=[
        Stage(id="initial", name="Initial stage"),
        Stage(id="dig_1", name="Dig", parent="initial", deactivate=["drawn_0"])]))

    with pytest.raises(session.EditRefused, match="dig_1"):
        session.without_value(project, "custom_parts[drawn_0]")


# ── The water level, as the `water` command sets it ─────────────────────────

def test_a_water_level_keeps_the_rest_of_an_existing_one():
    project = session.set_water(seed_project(), WaterUpdate(
        water=WaterLevel(y=-2.0, specific_weight=9.81)))

    moved = session.set_water_level(project, -4.0)

    assert (moved.water.y, moved.water.specific_weight) == (-4.0, 9.81)
    assert session.set_water_level(moved, None).water is None


def test_a_water_level_outside_the_model_is_refused():
    """The `water` command's own bounds (frontend/js/water-command.js): a level outside
    the model describes nothing."""
    with pytest.raises(session.EditRefused, match="between -25.00 and 0.00"):
        session.set_water_level(seed_project(), 3.0)


# ── What meshing needs ──────────────────────────────────────────────────────

def test_mesh_settings_naming_a_body_the_model_lacks_are_found():
    from core.model.schemas import MeshRequest

    settings = MeshRequest(body_sizes={"soil_L1": 1.0, "zz": 1.0, "aa": 2.0})

    assert session.unknown_mesh_keys(seed_project(), settings) == ["aa", "zz"]


def test_a_deck_is_not_meshed_here():
    session.require_parametric(seed_project(), "meshed")
    with pytest.raises(session.DeckReadOnly, match="not meshed here"):
        session.require_parametric(a_deck(), "meshed")


# ── The ground: domain, layers, materials, excavation ───────────────────────
#
# The edits the GUI's soil layers dialog makes in the browser, made here so the command
# line makes them the same way: the stack stays gap-free, a moved level moves its
# neighbour's, a deleted layer's neighbour closes the gap.

def test_the_domain_is_set_on_the_axes_given():
    project, notes = session.set_domain(seed_project(), x=(0.0, 40.0), y=(-30.0, 0.0))

    assert (project.domain.x0, project.domain.x1) == (0.0, 40.0)
    assert (project.domain.y_bottom, project.domain.y_top) == (-30.0, 0.0)
    assert (project.domain.z0, project.domain.z1) == (seed_project().domain.z0,
                                                      seed_project().domain.z1)
    assert notes == []


def test_a_section_left_outside_a_new_domain_is_cut_through_its_middle():
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    assert project.section_offset == 12.5

    project, notes = session.set_domain(project, z=(0.0, 10.0))

    assert project.section_offset == 5.0
    assert any("section" in note for note in notes)


def test_a_layer_is_added_below_the_stack():
    project = session.add_layer(seed_project(), "L3", "m1", bottom=-30.0)

    # The seed's stack ends at the domain's floor; a layer below it is still a layer.
    assert [layer.id for layer in project.layers] == ["L1", "L2", "L3"]
    assert project.layers[2].top == project.layers[1].bottom == -25.0
    assert project.layers[2].bottom == -30.0


def test_the_first_layer_starts_at_the_top_of_the_domain():
    project = session.add_material(blank_project(), seed_project().materials[0])
    project = session.add_layer(project, "L1", project.materials[0].id)

    assert (project.layers[0].top, project.layers[0].bottom) == (
        project.domain.y_top, project.domain.y_top - 5.0)


def test_a_layer_needs_a_material_the_model_has():
    with pytest.raises(ValidationError):
        session.add_layer(seed_project(), "L3", "nope", thickness=2.0)


def test_a_layer_id_that_is_taken_is_refused():
    with pytest.raises(session.EditRefused, match="already a layer 'L1'"):
        session.add_layer(seed_project(), "L1", "m1", thickness=2.0)


def test_a_bottom_moved_moves_the_top_of_the_layer_below():
    project = session.update_layer(seed_project(), "L1", bottom=-10.0)

    assert project.layers[0].bottom == project.layers[1].top == -10.0


def test_a_top_moved_moves_the_bottom_of_the_layer_above():
    project = session.update_layer(seed_project(), "L2", top=-6.0)

    assert project.layers[0].bottom == project.layers[1].top == -6.0


def test_a_bottom_cannot_cross_the_layer_below():
    with pytest.raises(session.EditRefused, match="below the bottom of the layer below"):
        session.update_layer(seed_project(), "L1", bottom=-30.0)


def test_a_top_cannot_rise_above_the_layer_above():
    with pytest.raises(session.EditRefused, match="above the top of the layer above"):
        session.update_layer(seed_project(), "L2", top=5.0)


def test_a_layer_takes_another_material():
    project = session.update_layer(seed_project(), "L1", material="m1", name="Fill")

    assert (project.layers[0].mat, project.layers[0].name) == ("m1", "Fill")


def test_a_split_layer_is_two_layers_meeting_halfway():
    """The dialog's Insert: the layer is halved and the new one goes below it."""
    before = seed_project()

    project = session.split_layer(before, "L1", "L1b")

    upper, lower = project.layers[0], project.layers[1]
    assert lower.id == "L1b" and lower.mat == upper.mat
    middle = (before.layers[0].top + before.layers[0].bottom) / 2
    assert upper.bottom == lower.top == middle
    assert lower.bottom == before.layers[0].bottom


def test_a_removed_layer_is_closed_by_the_one_above():
    project = session.remove_layer(seed_project(), "L2")

    assert [layer.id for layer in project.layers] == ["L1"]
    assert project.layers[0].bottom == seed_project().layers[1].bottom


def test_a_removed_top_layer_is_closed_by_the_one_below():
    project = session.remove_layer(seed_project(), "L1")

    assert project.layers[0].top == seed_project().layers[0].top


# The domain's height is the layer stack's: the top of the first layer is the ground
# level, NAP +1.7 m or 0 m as the user has it, and the domain follows it.

def heights(project: Project) -> tuple:
    d = project.domain
    return (d.y_top, d.y_bottom), (project.layers[0].top, project.layers[-1].bottom)


def test_a_ground_level_moved_moves_the_top_of_the_domain():
    project = session.update_layer(seed_project(), "L1", top=1.7)

    assert heights(project) == ((1.7, -25.0), (1.7, -25.0))


def test_a_layer_added_below_the_stack_deepens_the_domain():
    project = session.add_layer(seed_project(), "L3", "m1", bottom=-30.0)

    assert heights(project) == ((0.0, -30.0), (0.0, -30.0))


def test_the_domain_s_height_moves_the_first_and_the_last_layer():
    project, _ = session.set_domain(seed_project(), y=(-40.0, 1.7))

    assert heights(project) == ((1.7, -40.0), (1.7, -40.0))
    assert project.layers[0].bottom == seed_project().layers[0].bottom


def test_a_domain_height_that_crosses_a_layer_is_refused():
    with pytest.raises(session.EditRefused, match="below the bottom of the first layer"):
        session.set_domain(seed_project(), y=(-25.0, -9.0))
    with pytest.raises(session.EditRefused, match="above the top of the last layer"):
        session.set_domain(seed_project(), y=(-7.0, 0.0))


def test_the_height_is_one_edit_by_path_too():
    assert heights(session.with_value(seed_project(), "layers[L1].top", 2.0)) == (
        (2.0, -25.0), (2.0, -25.0))
    assert heights(session.with_value(seed_project(), "domain.y_bottom", -31.0)) == (
        (0.0, -31.0), (0.0, -31.0))


def test_the_gui_s_layers_set_the_domain_s_height_whatever_domain_comes_with_them():
    """The Selection explorer sends the domain it holds with every layer edit."""
    project = seed_project()
    raised = [project.layers[0].model_copy(update={"top": 1.7}), *project.layers[1:]]

    edited = session.replace_layers(project, LayersUpdate(layers=raised,
                                                          domain=project.domain))

    assert heights(edited) == ((1.7, -25.0), (1.7, -25.0))


def test_a_stack_with_no_height_is_refused():
    with pytest.raises(session.EditRefused, match="no height"):
        session.update_layer(session.remove_layer(seed_project(), "L2"), "L1", bottom=0.0)


def test_a_model_with_no_layers_keeps_the_height_its_domain_was_given():
    project, _ = session.set_domain(blank_project(), y=(-30.0, 1.7))

    assert (project.domain.y_bottom, project.domain.y_top) == (-30.0, 1.7)


def test_a_water_level_may_stand_in_drawn_soil_above_the_layers():
    """The domain is the layers' height, so a dike drawn on them reaches above it; the
    water bounds are the model's reach (`Project.extent`), not the domain."""
    project, _ = session.with_created_part(seed_project(), box(),
                                           {"brep_path": "dike.brep",
                                            "bbox": [0, 0, 0, 10, 3, 10]})

    assert session.set_water_level(project, 2.0).water.y == 2.0
    with pytest.raises(session.EditRefused, match="between -25.00 and 3.00"):
        session.set_water_level(project, 4.0)


def test_a_material_is_added_and_its_id_must_be_free():
    from core.model import drafts

    clay, _ = drafts.soil(seed_project(), "clay", preset="m3")
    project = session.add_material(seed_project(), clay)
    assert project.materials[-1].id == "clay"

    with pytest.raises(session.EditRefused, match="already a material 'clay'"):
        session.add_material(project, clay)


def test_a_material_is_changed_variable_by_variable():
    project = session.update_material(seed_project(), "m1",
                                      variables={"YOUNG_MODULUS": 3.0e7, "K0_NC": 0.5},
                                      unset=["GEO_COHESION"], name="Fill, stiff")

    material = project.materials[0]
    assert material.variables["YOUNG_MODULUS"] == 3.0e7
    assert material.variables["K0_NC"] == 0.5
    assert "GEO_COHESION" not in material.variables
    assert material.name == "Fill, stiff"


def test_unsetting_a_variable_the_material_does_not_have_is_refused():
    with pytest.raises(session.EditRefused, match="NOPE"):
        session.update_material(seed_project(), "m1", unset=["NOPE"])


def test_a_material_a_layer_uses_is_not_removed():
    with pytest.raises(ValidationError):
        session.remove_material(seed_project(), "m2")
    assert "m1" not in [m.id for m in session.remove_material(seed_project(), "m1").materials]


def test_the_excavation_is_dug_in_the_levels_given():
    project, notes = session.set_excavation(seed_project(), x=(2.0, 8.0),
                                            levels=[-2.0, -4.0, -6.0])

    pit = project.excavation
    assert (pit.x0, pit.x1, pit.levels, pit.floor_y) == (2.0, 8.0, [-2.0, -4.0, -6.0], -6.0)
    assert any("__lift1" in key for key in project.part_keys())
    assert notes == []


def test_one_level_says_that_a_layered_model_digs_nothing():
    """In a layered model the pit is only dug when it is staged
    (`Project.layered_soil`): one level would leave the ground whole, silently."""
    _, notes = session.set_excavation(seed_project(), x=(2.0, 8.0), levels=[-3.0])

    assert any("two or more levels" in note for note in notes)


def test_a_project_without_a_pit_gets_one():
    """A new project has no excavation. In 2D the pit spans the domain's z range, the
    one cut the section is."""
    blank = blank_project()
    assert blank.excavation is None

    project, _ = session.set_excavation(blank, x=(2.0, 8.0), levels=[-2.0, -4.0])

    pit = project.excavation
    assert pit is not None
    assert (pit.x0, pit.x1, pit.z0, pit.z1) == (2.0, 8.0, blank.domain.z0, blank.domain.z1)
    assert pit.levels == [-2.0, -4.0]


def test_a_pit_made_from_nothing_needs_its_outline_and_levels():
    with pytest.raises(session.EditRefused, match="give levels"):
        session.set_excavation(blank_project(), x=(2.0, 8.0))
    solid = blank_project().model_copy(update={"dimension": 3})
    with pytest.raises(session.EditRefused, match="give z, levels"):
        session.set_excavation(solid, x=(2.0, 8.0))


def test_a_part_given_a_material_takes_its_colour():
    project = with_box(seed_project())
    material = project.materials[2]

    project = session.assign_part_material(project, "drawn_0", material.id)

    part = project.custom_parts[0]
    assert (part.mat, part.color) == (material.id, material.color)


def test_a_part_given_a_material_the_model_lacks_is_refused():
    with pytest.raises(session.EditRefused, match="Unknown material 'nope'"):
        session.assign_part_material(with_box(seed_project()), "drawn_0", "nope")


# ── Structures and their sections ────────────────────────────────────────────

def plane_strain() -> Project:
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    return project


def test_a_first_sheet_pile_brings_its_default_profile():
    from core.model import drafts
    project = plane_strain()
    pile = drafts.sheet_pile(project)

    edited = session.add_structure(project, pile, drafts.section_for(project, pile))

    assert [b.id for b in edited.beams] == ["beam_1"]
    assert [s.id for s in edited.beam_sections] == ["beamsection_1"]


def test_a_structure_needs_an_id_no_other_part_has():
    from core.model import drafts
    project = excavation_project(staged=False)
    anchor = drafts.anchor(project, id="sheetpile")

    with pytest.raises(session.EditRefused, match="already a part 'sheetpile'"):
        session.add_structure(project, anchor)


def test_a_structure_is_changed_field_by_field():
    project = session.update_structure(excavation_project(staged=False), "strut",
                                       prestress=1.0e5, name="Prop")

    strut = project.anchors[0]
    assert (strut.prestress, strut.name) == (1.0e5, "Prop")


def test_an_anchor_moved_off_its_pile_is_refused():
    with pytest.raises(ValidationError, match="not on a sheet pile"):
        session.update_structure(excavation_project(staged=False), "strut",
                                 head=(10.0, -1.0))


def test_a_structure_that_is_not_there_is_named_with_those_that_are():
    with pytest.raises(session.UnknownRecord, match="no structure 'wall9'.*sheetpile"):
        session.update_structure(excavation_project(staged=False), "wall9", name="x")


def test_a_pile_carrying_an_anchor_or_an_interface_is_not_removed():
    project = excavation_project(staged=False)

    with pytest.raises(session.EditRefused, match="strut, wall_contact"):
        session.remove_structure(project, "sheetpile")


def test_a_structure_a_stage_names_is_not_removed():
    with pytest.raises(session.EditRefused, match="stage 'install_strut' names strut"):
        session.remove_structure(excavation_project(), "strut")


def test_a_removed_structure_takes_its_mesh_size_with_it():
    project = excavation_project(staged=False)
    for dependent in ("strut", "wall_contact"):
        project = session.remove_structure(project, dependent)

    edited = session.remove_structure(project, "sheetpile")

    assert edited.beams == []
    assert "sheetpile" not in edited.mesh.body_sizes


# ── A size goes with its body ───────────────────────────────────────────────

SIZED = {"sheetpile": 0.5, "strut": 0.5, "wall_contact": 0.5, "water_1": 0.5,
         "soil_L_mid": 1.0, "soil_L_mid__pit": 1.0, "soil_L_top__lift3": 1.0}
"""An element size on each body an edit below takes away."""


def _sized(project: Project, **extra: float) -> Project:
    sizes = {key: size for key, size in SIZED.items() if key in project.part_keys()}
    mesh = project.mesh.model_copy(update={"body_sizes": {**sizes, **extra}})
    return project.model_copy(update={"mesh": mesh})


def _structures(project: Project, **lists) -> StructuresUpdate:
    """What the GUI's Structure mode sends: the loads, and the lists it changed."""
    return StructuresUpdate.model_validate(
        {"loads": project.model_dump(mode="json")["loads"], **lists})


def _without(project: Project, field: str, id: str) -> list[dict]:
    return [r for r in project.model_dump(mode="json")[field] if r["id"] != id]


def _stack_without(project: Project, id: str) -> LayersUpdate:
    """What the soil layers window sends after its Delete (`SoilLayersDialog.remove`)."""
    payload = project.model_dump(mode="json")
    layers = payload["layers"]
    index = [layer["id"] for layer in layers].index(id)
    gone = layers.pop(index)
    if index > 0:
        layers[index - 1]["bottom"] = gone["bottom"]
    else:
        layers[0]["top"] = gone["top"]
    return LayersUpdate.model_validate({"layers": layers, "materials": payload["materials"]})


EDITS_THAT_TAKE_A_BODY = {
    "kratos-cli layer remove": lambda p: session.remove_layer(p, "L_mid"),
    "kratos-cli excavation --levels": lambda p: session.set_excavation(
        p, levels=[-2.0, -4.5])[0],
    "the GUI deletes a layer": lambda p: session.replace_layers(p, _stack_without(p, "L_mid")),
    "the GUI deletes an anchor": lambda p: session.replace_structures(
        p, _structures(p, anchors=_without(p, "anchors", "strut"))),
    "the GUI deletes an interface": lambda p: session.replace_structures(
        p, _structures(p, interfaces=_without(p, "interfaces", "wall_contact"))),
    "the GUI deletes a normal load": lambda p: session.replace_structures(
        p, _structures(p, normal_loads=_without(p, "normal_loads", "water_1"))),
    "the GUI deletes a sheet pile and what hangs from it": lambda p: session.replace_structures(
        p, _structures(p, beams=[], anchors=[], interfaces=[])),
}
"""Each edit that takes a body away, made the way each front end makes it. The GUI does
not call `remove_structure`: it sends the whole list."""


@pytest.mark.parametrize("edit", sorted(EDITS_THAT_TAKE_A_BODY))
def test_a_body_an_edit_takes_away_takes_its_mesh_size_with_it(edit):
    """Or `kratos-cli check` and `mesh` refuse the saved project: "the mesh settings
    name bodies this model does not have"."""
    project = _sized(excavation_project(staged=False))

    edited = EDITS_THAT_TAKE_A_BODY[edit](project)

    gone = set(project.part_keys()) - set(edited.part_keys())
    assert gone & set(project.mesh.body_sizes), "the edit takes no sized body away"
    assert edited.mesh.body_sizes == {key: size for key, size
                                      in project.mesh.body_sizes.items() if key not in gone}


def test_a_size_for_a_body_the_model_never_had_is_left_for_check_to_name():
    project = _sized(excavation_project(staged=False), soil_typo=1.0)

    edited = session.remove_layer(project, "L_mid")

    assert edited.mesh.body_sizes["soil_typo"] == 1.0
    settings = MeshRequest.model_validate(edited.mesh.model_dump())
    assert session.unknown_mesh_keys(edited, settings) == ["soil_typo"]


def test_a_section_is_added_changed_and_removed():
    from core.model import drafts
    project = plane_strain()

    project = session.add_section(project, "beam", drafts.section(project, "beam", "az26"))
    project = session.update_section(project, "az26", spacing=1.5, name="AZ 26",
                                     variables={"I33": 6.0e-4}, unset=["POISSON_RATIO"])
    az26 = project.beam_sections[0]
    assert (az26.spacing, az26.name, az26.variables["I33"]) == (1.5, "AZ 26", 6.0e-4)
    assert "POISSON_RATIO" not in az26.variables

    assert session.remove_section(project, "az26").beam_sections == []


def test_a_section_a_structure_uses_is_not_removed():
    with pytest.raises(session.EditRefused, match="sheetpile"):
        session.remove_section(excavation_project(staged=False), "sheetpile")


def test_a_section_id_two_kinds_share_needs_its_kind():
    from core.model import drafts
    project = excavation_project(staged=False)
    project = session.add_section(project, "anchor",
                                  drafts.section(project, "anchor", "sheetpile"))

    with pytest.raises(session.EditRefused, match="beam and an anchor section"):
        session.update_section(project, "sheetpile", name="x")
    assert session.update_section(project, "sheetpile", kind="anchor",
                                  name="x").anchor_sections[-1].name == "x"


# ── Stages, one at a time ────────────────────────────────────────────────────

def test_a_stage_is_added_at_the_end_with_the_id_and_settings_given():
    project, stage = session.add_stage(excavation_project(), id="dig_4", name="Dig 4",
                                       calculation="Plastic", max_iterations=50)

    assert project.stages[-1] == stage
    assert (stage.id, stage.name, stage.parent, stage.max_iterations) == (
        "dig_4", "Dig 4", "dig_3", 50)


def test_a_stage_inserted_before_another_takes_its_place_in_the_chain():
    project, stage = session.add_stage(excavation_project(), before="dig_1", id="prep")

    by_id = {p.id: p for p in project.stages}
    assert (by_id["prep"].parent, by_id["dig_1"].parent) == ("install_sheetpile", "prep")


def test_a_copied_stage_follows_its_original():
    project, stage = session.add_stage(excavation_project(), copy_of="dig_1")

    assert (stage.id, stage.parent, stage.max_iterations) == ("stage_1", "dig_1", 150)
    assert {p.id: p for p in project.stages}["install_strut"].parent == "stage_1"


def test_a_stage_id_that_is_taken_is_refused():
    with pytest.raises(session.EditRefused, match="already a stage 'dig_1'"):
        session.add_stage(excavation_project(), id="dig_1")


def test_a_stage_is_changed_and_removed():
    project = session.update_stage(excavation_project(), "dig_1", name="Dig one",
                                   tolerated_error=1e-5)
    assert {p.id: p for p in project.stages}["dig_1"].tolerated_error == 1e-5

    project = session.remove_stage(project, "install_strut")
    assert {p.id: p for p in project.stages}["dig_2"].parent == "dig_1"


def test_a_stage_that_is_not_there_is_named_with_those_that_are():
    with pytest.raises(session.UnknownRecord, match="no stage 'dig_9'.*dig_1"):
        session.update_stage(excavation_project(), "dig_9", name="x")


def test_parts_are_switched_with_the_smallest_instruction():
    project = session.switch_parts(excavation_project(), "dig_1", ["strut"], True)

    assert {p.id: p for p in project.stages}["dig_1"].activate == ["water_1", "strut"]


def test_a_part_the_model_does_not_have_is_not_switched():
    with pytest.raises(session.EditRefused, match="no part 'stru'"):
        session.switch_parts(excavation_project(), "dig_1", ["stru"], True)


def test_a_part_switched_by_its_name_is_refused_with_its_id():
    # The surcharge is called "Load"; a stage takes its id.
    with pytest.raises(session.EditRefused, match="name of the part with id surcharge"):
        session.switch_parts(excavation_project(), "dig_1", ["load"], True)


def test_the_staged_excavation_sequence_is_derived_from_the_model():
    project = session.staged_excavation_stages(excavation_project(staged=False))

    assert project.stages == excavation_project().stages


# ── A project file opened on another computer ──────────────────────────────

def test_a_project_file_from_another_computer_keeps_its_drawn_parts(tmp_path):
    """The file names each drawn part's .brep by the path it had where it was drawn.
    Opened anywhere else that path is not there, and the mesher left the part out
    without a word: the deck had no levee. Its recipe is in the file, so it is built
    again, and the deck is the one its author exported."""
    from core.geometry import solid_model
    from core.kratos import writer
    from tests.models import drawn_ground

    here = drawn_ground.project()
    elsewhere = here.model_dump(mode="json")
    for part in elsewhere["custom_parts"]:
        part["source_file"] = "C:/Checkouts/Someone-else/.data/" + Path(part["source_file"]).name
    path = tmp_path / "dike.json"
    path.write_text(json.dumps(elsewhere), encoding="utf-8")

    opened = session.load(path)
    assert all(Path(part.source_file).is_file() for part in opened.custom_parts)
    assert session.load(path).custom_parts == opened.custom_parts, \
        "the second read reuses what the first one built"
    with solid_model.session():
        assert writer.export_project(opened)["mdpa"] == writer.export_project(here)["mdpa"]


def test_a_part_that_cannot_be_built_again_is_said_to_be_missing(tmp_path):
    from core.geometry import solid_model
    from core.kratos import writer
    from tests.models import drawn_ground

    data = drawn_ground.project().model_dump(mode="json")
    data.update(interfaces=[], stages=[])
    data["custom_parts"][1].update(source_file="C:/nowhere/gone.brep", recipe=None,
                                   source="import")
    path = tmp_path / "dike.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    project = session.load(path)
    with solid_model.session():
        export = writer.export_project(project)
    assert any("Fill right (drawn_1) is not in the model" in w for w in export["warnings"])
