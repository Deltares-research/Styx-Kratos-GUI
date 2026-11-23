"""The water of the Flow conditions tab and of each stage, in the terminal.

`boundary water-line` draws a water line on the whole soil -- the phreatic line first,
head lines after it -- and `boundary phreatic` makes one the phreatic line; `boundary add
--flux` puts a flux on a face or a line, and `boundary soil-water ... dry` makes a soil
dry. `stages water`, `stages soil-water` and `stages value` give one stage its phreatic
line, a soil's water and a condition's value, as the Staged construction tab does: each
the stage's alone, as `stages activate` is.
"""

from __future__ import annotations

import pytest

from core import session
from core.model import stages
from core.model.schemas import Project


@pytest.fixture
def staged(cli, site):
    """The demo section with no water, in two stages."""
    payload = session.load(site).model_dump()
    payload.update(water=None, boundary_conditions=[
        c for c in payload["boundary_conditions"] if c["kind"] == "displacement"],
        stages=[{"id": "initial", "name": "Initial stage"},
                {"id": "later", "name": "Later", "parent": "initial"},
                {"id": "last", "name": "Last", "parent": "later"}])
    return session.save(Project.model_validate(payload), site)


def lines_of(path) -> list:
    return session.load(path).water_lines()


def test_the_first_water_line_is_the_phreatic_line_and_the_next_a_head_line(cli, staged):
    ran = cli("boundary", staged, "water-line", "25", "-1", "0", "-1")
    assert ran.code == 0, ran.err
    assert "the phreatic line" in ran.out
    ran = cli("boundary", staged, "water-line", "0", "1", "25", "3", "--id", "aquifer")
    assert ran.code == 0, ran.err
    assert "a head line" in ran.out
    first, second = lines_of(staged)
    assert (first.fluid_pressure_type, first.on, first.x_coordinates) == (
        "Phreatic_Multi_Line", "domain", [0.0, 25.0])
    assert (second.id, second.fluid_pressure_type) == ("aquifer", "Head_Line")


def test_a_water_line_has_one_level_at_each_x(cli, staged):
    ran = cli("boundary", staged, "water-line", "5", "-1", "5", "-3")
    assert ran.code == 1
    assert "different x coordinates" in ran.err


def test_any_water_line_can_be_made_the_phreatic_line(cli, staged):
    cli("boundary", staged, "water-line", "0", "-1", "25", "-1", "--id", "first")
    cli("boundary", staged, "water-line", "0", "1", "25", "3", "--id", "second")
    ran = cli("boundary", staged, "phreatic", "second")
    assert ran.code == 0, ran.err
    assert {line.id: line.fluid_pressure_type for line in lines_of(staged)} == {
        "first": "Head_Line", "second": "Phreatic_Multi_Line"}
    ran = cli("boundary", staged, "phreatic", "fixed_bottom")
    assert ran.code == 1 and "not a water line" in ran.err


def test_a_soil_can_be_dry(cli, staged):
    ran = cli("boundary", staged, "soil-water", "soil_L1", "dry")
    assert ran.code == 0, ran.err
    assert "soil_L1  dry" in ran.out
    assert session.load(staged).soil_water == {"soil_L1": "dry"}


def test_a_flux_is_added_on_a_face_and_listed(cli, staged):
    ran = cli("boundary", staged, "add", "rain", "--face", "top", "--flux", "2e-6")
    assert ran.code == 0, ran.err
    assert "flux on the top face; 2e-06 into the soil" in ran.out
    assert cli("boundary", staged, "set", "rain", "--flux", "-1e-6").code == 0
    [rain] = [c for c in session.load(staged).boundary_conditions if c.id == "rain"]
    assert (rain.kind, rain.value) == ("flux", -1e-6)


@pytest.mark.parametrize("argv, said", [
    (["--part", "soil_L1"], "a flux is on --face FACE or --line"),
    (["--face", "top", "--water-pressure", "Uniform"], "do not belong to a flux"),
    (["--face", "top", "--seepage"], "do not belong to a seepage face"),
])
def test_a_flux_is_on_a_face_or_a_line_and_nothing_else(cli, staged, argv, said):
    ran = cli("boundary", staged, "add", "--flux", "1e-6", *argv)
    assert ran.code == 1
    assert said in ran.err


def test_a_stage_names_its_phreatic_line_and_the_stages_after_keep_theirs(cli, staged):
    cli("boundary", staged, "water-line", "0", "-1", "25", "-1", "--id", "high")
    cli("boundary", staged, "water-line", "0", "-4", "25", "-4", "--id", "low")
    ran = cli("stages", staged, "water", "later", "--phreatic-line", "low")
    assert ran.code == 0, ran.err
    assert "phreatic line: low (low) *" in ran.out
    assert "head lines: high (high)" in ran.out
    project = session.load(staged)
    assert [stages.water_in(project, stage).phreatic.id
            for stage in ("initial", "later", "last")] == ["high", "low", "high"]
    assert cli("stages", staged, "water", "later", "--phreatic-line", "inherit").code == 0
    assert session.load(staged).stages[1].phreatic_line is None


def test_a_stage_gives_a_soil_its_water(cli, staged):
    cli("boundary", staged, "water-line", "0", "-1", "25", "-1")
    ran = cli("stages", staged, "soil-water", "later", "soil_L1", "dry")
    assert ran.code == 0, ran.err
    assert "soil soil_L1: dry *" in ran.out
    project = session.load(staged)
    assert stages.water_in(project, "later").soil_water == {"soil_L1": "dry"}
    assert stages.water_in(project, "last").soil_water == {}
    assert cli("stages", staged, "soil-water", "later", "soil_L1", "inherit").code == 0
    assert session.load(staged).stages[1].soil_water == {}


def test_a_stage_gives_a_condition_its_value(cli, staged):
    cli("boundary", staged, "add", "clay", "--part", "soil_L2", "--water-pressure",
        "Uniform", "--value", "-10")
    ran = cli("stages", staged, "value", "later", "clay", "--value", "-25")
    assert ran.code == 0, ran.err
    assert "clay: value = -25.0 *" in ran.out
    project = session.load(staged)
    assert [stages.water_in(project, stage).conditions["clay"].value
            for stage in ("initial", "later", "last")] == [-10.0, -25.0, -10.0]
    assert cli("stages", staged, "value", "later", "clay", "--inherit").code == 0
    assert session.load(staged).stages[1].condition_values == {}


@pytest.mark.parametrize("argv, said", [
    (["clay"], "give a value, or --inherit"),
    (["clay", "--value", "1", "--inherit"], "give no value with it"),
    (["fixed_bottom", "--value", "1"], "switch it on or off in the stage instead"),
    (["clay", "--reference-coordinate", "1"], "cannot change reference_coordinate"),
])
def test_a_stage_value_must_be_one_the_condition_has(cli, staged, argv, said):
    """`clay` is a flux here, which has a value and no level."""
    cli("boundary", staged, "add", "clay", "--face", "top", "--flux", "1e-6")
    ran = cli("stages", staged, "value", "later", *argv)
    assert ran.code == 1
    assert said in ran.err
