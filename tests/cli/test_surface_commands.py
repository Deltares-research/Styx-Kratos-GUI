"""`kratos-cli surface`: the soil surfaces of a 2D model, as Soil > Create soil surface… draws
them, and the lines that cut them (issue #125)."""

from __future__ import annotations

import pytest

from core import session


@pytest.fixture
def empty(cli, tmp_path):
    """A new 2D project with two materials and no layers: the start of the issue's steps."""
    path = tmp_path / "surface.json"
    for command in (("new", path), ("material", path, "add", "sand"),
                    ("material", path, "add", "clay")):
        assert cli(*command).code == 0
    return path


def square(cli, path, *extra):
    return cli("surface", path, "add", "--points", "0", "0", "3", "0", "3", "3", "0", "3",
               "--material", "sand", *extra)


def test_a_surface_is_the_part_the_gui_window_draws(cli, empty):
    ran = square(cli, empty, "--label", "Bank")
    assert ran.code == 0
    assert "added soil surface drawn_0 (Bank" in ran.out
    part, = session.load(empty).custom_parts
    assert (part.label, part.mat, part.recipe["kind"]) == ("Bank", "sand", "polygon_extrude")
    assert part.recipe["extrusion"][:2] == [0, 0]
    assert "drawn_0  Bank  ·  " in cli("surface", empty, "list").out


def test_a_surface_with_no_label_is_called_as_the_gui_calls_it(cli, empty):
    assert square(cli, empty).code == 0
    assert session.load(empty).custom_parts[0].label == "Soil surface"


def test_a_line_across_a_surface_cuts_it_into_soil_bodies(cli, empty):
    """The steps of the issue."""
    assert square(cli, empty).code == 0
    ran = cli("line", empty, "add", "--points", "1", "3", "1", "0")
    assert ran.code == 0 and "splits no soil" not in ran.out
    assert session.load(empty).soil_body_keys == ["drawn_0__part1", "drawn_0__part2"]
    assert "(cut into drawn_0__part1, drawn_0__part2)" in cli("surface", empty, "list").out
    assert "drawn_0__part1  Soil surface · Part 1  ·" in cli("body", empty, "list").out
    assert cli("body", empty, "set", "drawn_0__part1", "--name", "Core").code == 0
    assert session.load(empty).soil_body_labels["drawn_0__part1"] == "Core"


def test_a_new_material_for_a_cut_surface_goes_to_every_body(cli, empty):
    assert square(cli, empty).code == 0
    assert cli("line", empty, "add", "--points", "1", "3", "1", "0").code == 0
    assert cli("surface", empty, "set", "drawn_0", "--material", "clay").code == 0
    assert set(session.load(empty).soil_body_materials.values()) == {"clay"}


def test_new_corners_keep_the_key_and_the_cut(cli, empty):
    assert square(cli, empty).code == 0
    assert cli("line", empty, "add", "--points", "1", "3", "1", "0").code == 0
    assert cli("surface", empty, "set", "drawn_0", "--points", "0", "0", "4", "0", "4", "3",
               "0", "3").code == 0
    project = session.load(empty)
    assert [part.key for part in project.custom_parts] == ["drawn_0"]
    assert project.soil_body_keys == ["drawn_0__part1", "drawn_0__part2"]


def test_a_surface_can_be_removed_with_its_bodies(cli, empty):
    assert square(cli, empty).code == 0
    assert cli("line", empty, "add", "--points", "1", "3", "1", "0").code == 0
    assert cli("surface", empty, "remove", "drawn_0").code == 0
    project = session.load(empty)
    assert project.custom_parts == [] and project.bodies == []
    assert "No soil surfaces yet." in cli("surface", empty, "list").out


def test_a_surface_that_is_not_there_is_refused(cli, empty):
    ran = cli("surface", empty, "remove", "drawn_7")
    assert ran.code != 0 and "no soil surface 'drawn_7'" in ran.err


def test_a_3d_model_has_volumes_not_surfaces(cli, tmp_path):
    path = tmp_path / "solid.json"
    assert cli("new", path, "--dim", "3").code == 0
    assert "`volume list`" in cli("surface", path, "list").out
    ran = square(cli, path)
    assert ran.code != 0 and "volume add polygon" in ran.err
