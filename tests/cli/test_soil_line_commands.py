"""`kratos-cli line` and `kratos-cli body`: split the soil, as the GUI's Create line does."""

from __future__ import annotations

import json

import pytest

from core import session


@pytest.fixture
def site(cli, tmp_path):
    """Two layers of one soil, in a 2D section."""
    path = tmp_path / "site.json"
    for command in (("new", path),
                    ("domain", path, "--x", "0", "20", "--y", "-12", "0", "--z", "0", "10"),
                    ("material", path, "add", "sand"),
                    ("material", path, "add", "grout"),
                    ("layer", path, "add", "top", "--material", "sand", "--bottom", "-4"),
                    ("layer", path, "add", "low", "--material", "sand", "--bottom", "-12")):
        assert cli(*command).code == 0
    return path


def test_a_line_splits_the_layer_it_crosses(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    project = session.load(site)
    assert project.soil_body_keys == ["soil_top__part1", "soil_top__part2", "soil_low"]
    assert "soil_top__part1  top · Part 1  ·" in cli("body", site, "list").out
    assert "soil_top__part1" in cli("parts", site).out


def test_a_line_list_says_where_each_is(cli, site):
    assert "No lines yet" in cli("line", site, "list").out
    assert cli("line", site, "add", "side", "--name", "Side", "--points", "5", "0", "5", "-4"
               ).code == 0
    assert "side  Side: 5,0 .. 5,-4" in cli("line", site, "list").out


def test_a_new_line_with_no_points_runs_across_the_section(cli, site):
    assert cli("line", site, "add").code == 0
    line, = session.load(site).lines
    assert (line.id, line.name) == ("line_1", "Line 1")
    assert line.points == [(0.0, -6.0), (20.0, -6.0)]


def test_a_line_that_splits_nothing_gets_a_note(cli, site):
    ran = cli("line", site, "add", "short", "--points", "5", "0", "5", "-2")
    assert ran.code == 0
    assert "splits no soil" in ran.out


def test_a_line_can_be_changed_and_removed(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("line", site, "set", "side", "--name", "New", "--points", "6", "0", "6", "-4"
               ).code == 0
    line, = session.load(site).lines
    assert (line.name, line.points[0]) == ("New", (6.0, 0.0))
    assert cli("line", site, "remove", "side").code == 0
    assert session.load(site).soil_body_keys == ["soil_top", "soil_low"]


def test_a_body_can_be_named_and_given_a_material(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("body", site, "set", "soil_top__part1", "--name", "Pit", "--material", "grout"
               ).code == 0
    project = session.load(site)
    assert project.soil_body_labels["soil_top__part1"] == "Pit"
    assert project.soil_body_materials["soil_top__part1"] == "grout"
    assert cli("body", site, "set", "soil_top__part1", "--material", "layer").code == 0
    assert session.load(site).soil_body_materials["soil_top__part1"] == "sand"


def test_a_layer_given_another_material_gives_it_to_all_its_parts(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("material", site, "add", "clay").code == 0
    assert cli("body", site, "set", "soil_top__part1", "--material", "grout").code == 0
    assert cli("layer", site, "set", "top", "--material", "clay").code == 0
    assert session.load(site).soil_body_materials == {
        "soil_top__part1": "clay", "soil_top__part2": "clay", "soil_low": "sand"}


def test_a_whole_layer_is_not_a_body_to_change(cli, site):
    ran = cli("body", site, "set", "soil_low", "--name", "x")
    assert ran.code != 0
    assert "whole layer" in ran.err


def test_a_name_another_part_of_the_layer_has_is_refused(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    ran = cli("body", site, "set", "soil_top__part1", "--name", "Part 2")
    assert ran.code != 0
    assert ("soil_top__part1 and soil_top__part2 in layer 'top' are both called 'Part 2'"
            in ran.err)
    assert session.load(site).soil_body_labels["soil_top__part1"] == "top · Part 1"


def test_a_stage_can_switch_a_body_off(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("stages", site, "add", "first", "--name", "First").code == 0
    assert cli("stages", site, "add", "dig", "--name", "Dig", "--deactivate", "soil_top__part1"
               ).code == 0
    assert session.load(site).stages[-1].deactivate == ["soil_top__part1"]


def test_removing_a_line_a_stage_needs_is_refused(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("stages", site, "add", "first", "--name", "First").code == 0
    assert cli("stages", site, "add", "dig", "--name", "Dig", "--deactivate", "soil_top__part1"
               ).code == 0
    ran = cli("line", site, "remove", "side")
    assert ran.code != 0
    assert "soil_top__part1" in ran.err
    assert session.load(site).lines


def test_the_gui_route_and_the_command_line_make_the_same_project(cli, site, tmp_path):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend import store

    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    by_command = json.loads(session.load(site).model_dump_json())
    store.put(session.load(site).model_copy(update={"lines": [], "bodies": []}))
    with TestClient(app) as client:
        answer = client.patch("/api/project/lines", json={"lines": by_command["lines"]})
    assert answer.status_code == 200
    assert answer.json()["project"]["soil_body_keys"] == by_command["soil_body_keys"]
    assert answer.json()["project"]["bodies"] == by_command["bodies"]


def test_the_soil_layers_window_and_the_command_line_give_a_layers_parts_its_material(
        cli, site):
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend import store

    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("body", site, "set", "soil_top__part1", "--material", "grout").code == 0
    store.put(session.load(site))
    assert cli("layer", site, "set", "top", "--material", "grout").code == 0
    by_command = json.loads(session.load(site).model_dump_json())
    with TestClient(app) as client:
        answer = client.patch("/api/project/layers", json={"layers": by_command["layers"]})
    assert answer.status_code == 200
    assert answer.json()["project"]["bodies"] == by_command["bodies"]
    assert [body["mat"] for body in by_command["bodies"]] == ["grout", "grout"]


def test_one_body_can_be_removed_and_leaves_the_rest_of_its_layer(cli, site):
    assert cli("line", site, "add", "side", "--points", "5", "0", "5", "-4").code == 0
    assert cli("body", site, "remove", "soil_top__part1").code == 0
    assert session.load(site).soil_body_keys == ["soil_top__part2", "soil_low"]
    ran = cli("body", site, "remove", "soil_top__part2")
    assert ran.code != 0
    assert "last part of soil_top" in ran.err
