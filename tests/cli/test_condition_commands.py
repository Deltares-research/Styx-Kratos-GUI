"""`boundary`: the conditions on the model's boundaries and soil, in the terminal
(plan/done/boundary-conditions-plan.md, 2.7).

Each new record is `core.model.drafts`' and each edit `core.session`'s, so the command
line makes what the GUI's dialog makes. A support holds the components it is given; a
hydrostatic water pressure with no level of its own takes the project's water level and
says so; `standard` puts the standard supports back; `show` lists the conditions and
`check` says what the export will warn about them.
"""

from __future__ import annotations

import pytest

from core import session
from core.model.schemas import Project


@pytest.fixture
def dry(site):
    """The demo section with no water level and no condition."""
    payload = session.load(site).model_dump()
    payload.update(water=None, boundary_conditions=[])
    return session.save(Project.model_validate(payload), site)


def conditions(path):
    return session.load(path).boundary_conditions


# ── boundary add ────────────────────────────────────────────────────────────

def test_a_hydrostatic_pressure_takes_the_water_level_and_says_so(cli, dry):
    assert cli("water", dry, "-2").code == 0
    ran = cli("boundary", dry, "add", "--domain", "--water-pressure", "Hydrostatic")

    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert (record.id, record.on, record.fluid_pressure_type, record.is_fixed,
            record.reference_coordinate) == ("waterpressure_1", "domain", "Hydrostatic",
                                             True, -2.0)
    assert "its level is the project's water level, -2 m" in ran.out


def test_with_no_water_level_a_hydrostatic_pressure_needs_its_own(cli, dry):
    ran = cli("boundary", dry, "add", "--domain", "--water-pressure", "Hydrostatic")

    assert ran.code == 1
    assert "needs the level where its pressure is zero" in ran.err
    assert "Uniform one with value 0" in ran.err
    assert cli("boundary", dry, "add", "--domain", "--water-pressure", "Hydrostatic",
               "--reference-coordinate", "-1.5").code == 0
    assert conditions(dry)[0].reference_coordinate == -1.5


@pytest.mark.parametrize("argv, expected", [
    (["--face", "left"], {"on": "face", "face": "left"}),
    (["--part", "soil_L2"], {"on": "part", "part": "soil_L2"}),
    (["--line", "5", "-2", "5", "-8"], {"on": "line", "points": [(5.0, -2.0), (5.0, -8.0)]}),
    (["--point", "10", "-10"], {"on": "point", "points": [(10.0, -10.0)]}),
])
def test_each_target_option_fills_on_and_its_field(cli, dry, argv, expected):
    ran = cli("boundary", dry, "add", "wp", *argv, "--water-pressure", "Uniform",
              "--value", "-5000")

    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert {field: getattr(record, field) for field in expected} == expected
    assert (record.fluid_pressure_type, record.value) == ("Uniform", -5000.0)


def test_a_phreatic_line_is_stored_as_its_coordinates(cli, dry):
    ran = cli("boundary", dry, "add", "initial", "--domain", "--water-pressure",
              "Phreatic_Multi_Line", "--phreatic-line", "0", "-1", "25", "-3", "--initial",
              "--pressure-tension-cut-off", "1e5")

    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert (record.x_coordinates, record.y_coordinates) == ([0.0, 25.0], [-1.0, -3.0])
    assert (record.is_fixed, record.pressure_tension_cut_off) == (False, 1e5)
    assert "phreatic line (0, -1) -> (25, -3), cut-off 100000, initial" in ran.out


def test_a_condition_given_only_a_name_takes_it_as_its_id(cli, dry):
    ran = cli("boundary", dry, "add", "--name", "base", "--face", "bottom", "--fixed")

    assert ran.code == 0, ran.err
    assert [record.id for record in conditions(dry)] == ["base"]


@pytest.mark.parametrize("argv, message", [
    (["--domain"], "--water-pressure"),
    (["--water-pressure", "Uniform"], "say where it acts"),
    (["--domain", "--water-pressure", "Phreatic_Multi_Line"], "--phreatic-line"),
    (["--point", "1", "2", "3", "4", "--water-pressure", "Uniform"], "one point"),
    (["--part", "soil_nowhere", "--water-pressure", "Uniform"], "not a soil part"),
])
def test_an_incomplete_condition_is_refused(cli, dry, argv, message):
    ran = cli("boundary", dry, "add", *argv)

    assert ran.code == 1
    assert message in ran.err
    assert conditions(dry) == []


def test_two_targets_cannot_be_given(cli, dry):
    assert cli("boundary", dry, "add", "--domain", "--face", "left", "--water-pressure",
               "Uniform").code == 2


def test_a_condition_cannot_take_a_part_s_id(cli, dry):
    ran = cli("boundary", dry, "add", "soil_L1", "--domain", "--water-pressure", "Uniform")

    assert ran.code == 1
    assert "already a part" in ran.err


# ── boundary set, list, remove ──────────────────────────────────────────────

def test_set_changes_the_fields_given_and_a_new_target_replaces_the_old(cli, dry):
    assert cli("boundary", dry, "add", "wp", "--face", "left", "--water-pressure",
               "Uniform").code == 0
    ran = cli("boundary", dry, "set", "wp", "--part", "soil_L1", "--water-pressure",
              "Hydrostatic", "--reference-coordinate", "-4", "--initial", "--inactive",
              "--name", "Head")

    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert (record.name, record.on, record.face, record.part) == ("Head", "part", None,
                                                                  "soil_L1")
    assert (record.fluid_pressure_type, record.reference_coordinate, record.is_fixed,
            record.active) == ("Hydrostatic", -4.0, False, False)


def test_set_to_hydrostatic_copies_the_water_level_in(cli, dry):
    assert cli("boundary", dry, "add", "wp", "--domain", "--water-pressure",
               "Uniform").code == 0
    ran = cli("boundary", dry, "set", "wp", "--water-pressure", "Hydrostatic")
    assert ran.code == 1 and "--reference-coordinate" in ran.err

    assert cli("water", dry, "-3").code == 0
    assert cli("boundary", dry, "set", "wp", "--water-pressure", "Hydrostatic").code == 0
    assert conditions(dry)[0].reference_coordinate == -3.0


def test_set_cannot_change_a_water_pressure_into_a_seepage_face_or_support(cli, dry):
    assert cli("boundary", dry, "add", "wp", "--domain", "--water-pressure", "Uniform").code \
        == 0

    seepage = cli("boundary", dry, "set", "wp", "--seepage")
    support = cli("boundary", dry, "set", "wp", "--roller")

    assert seepage.code == 1 and "remove it and add a seepage face instead" in seepage.err
    assert support.code == 1 and "a support's" in support.err
    assert conditions(dry)[0].kind == "water_pressure"


def test_list_and_remove(cli, dry):
    assert cli("boundary", dry, "list").out.strip() == "No boundary conditions yet."
    assert cli("boundary", dry, "add", "wp", "--face", "right", "--water-pressure",
               "Hydrostatic", "--reference-coordinate", "-1").code == 0

    listed = cli("boundary", dry, "list")
    assert "wp  wp  water pressure on the right face; hydrostatic about " \
           "-1 m, fixed" in listed.out
    assert cli("boundary", dry, "--json", "list").json()[0]["on"] == "face"

    assert cli("boundary", dry, "remove", "wp").code == 0
    assert conditions(dry) == []
    ran = cli("boundary", dry, "remove", "wp")
    assert ran.code == 1 and "no boundary condition" in ran.err


# ── water, show, check ──────────────────────────────────────────────────────

def test_a_water_level_alone_says_it_fixes_no_pressure(cli, dry):
    ran = cli("water", dry, "-2")

    assert "fixes no pressure by itself" in ran.out
    assert cli("boundary", dry, "add", "--domain", "--water-pressure",
               "Hydrostatic").code == 0
    assert "fixes no pressure" not in cli("water", dry, "-2.5").out


def test_show_lists_the_conditions(cli, dry):
    assert cli("boundary", dry, "add", "wp", "--face", "left", "--water-pressure",
               "Uniform").code == 0

    assert "conditions  wp (water pressure on the left face)" in cli("show", dry).out
    assert cli("show", dry, "--json").json()["boundary_conditions"] == [
        {"id": "wp", "kind": "water_pressure", "on": "the left face", "active": True}]


def test_check_says_what_the_export_will_warn_about(cli, dry):
    assert cli("water", dry, "-2").code == 0
    ran = cli("check", dry)

    assert ran.code == 0
    assert "warning: the water level (-2 m) fixes no pressure by itself" in ran.err
    assert cli("boundary", dry, "add", "--face", "front", "--water-pressure",
               "Hydrostatic").code == 0
    ran = cli("check", dry)
    assert "is on the front face, which this 2D model does not have" in ran.err
    assert "fixes no pressure" in ran.err
    assert cli("check", dry, "--json").json()["warnings"]


# ── normal-load --reference-coordinate ──────────────────────────────────────

def test_a_hydrostatic_normal_load_keeps_its_own_level(cli, dry):
    ran = cli("normal-load", dry, "add", "river", "--hydrostatic", "--points", "8", "0",
              "8", "-5", "--reference-coordinate", "-2")

    assert ran.code == 0, ran.err
    assert session.load(dry).normal_loads[0].reference_coordinate == -2.0
    assert "hydrostatic about -2 m" in cli("normal-load", dry, "list").out


def test_a_normal_load_made_hydrostatic_copies_the_water_level(cli, dry):
    assert cli("normal-load", dry, "add", "push", "--points", "8", "0", "8", "-5",
               "--pressure", "100").code == 0
    ran = cli("normal-load", dry, "set", "push", "--hydrostatic")
    assert ran.code == 1 and "needs a water level" in ran.err

    assert cli("water", dry, "-1").code == 0
    assert cli("normal-load", dry, "set", "push", "--hydrostatic").code == 0
    load = session.load(dry).normal_loads[0]
    assert (load.fluid_pressure_type, load.reference_coordinate) == ("Hydrostatic", -1.0)


# ── Supports ────────────────────────────────────────────────────────────────

def test_a_new_project_lists_the_standard_supports(cli, tmp_path):
    path = tmp_path / "new.json"
    assert cli("new", path).code == 0

    listed = cli("boundary", path, "list").out
    assert "fixed_bottom  Fixed bottom  displacement on the bottom face; fixed in x y z" \
        in listed
    assert "roller_left  Roller left  displacement on the left face; fixed in x" in listed


def test_a_2d_list_leaves_the_front_and_back_supports_out_as_the_gui_does(cli, tmp_path):
    """They stay in the project for the solid model; the GUI's explorer, window and
    command box leave them out too (`App.BoundaryConditions.heldBySection`)."""
    from core.kratos import condition_checks
    path = tmp_path / "new.json"
    assert cli("new", path).code == 0
    listed = cli("boundary", path, "list").out
    assert "roller_front" not in listed and "roller_back" not in listed
    assert listed.strip().endswith(condition_checks.SECTION_NOTE)
    assert "roller_front" not in cli("show", path).out
    assert [c.id for c in conditions(path)][-2:] == ["roller_front", "roller_back"]

    payload = session.load(path).model_dump()
    payload["dimension"] = 3
    session.save(Project.model_validate(payload), path)
    listed = cli("boundary", path, "list").out
    assert "roller_front" in listed and condition_checks.SECTION_NOTE not in listed


def test_a_flow_project_notes_that_its_supports_are_left_out(cli, tmp_path):
    """As the GUI's command box does; its explorer marks each support instead."""
    from core.kratos import condition_checks
    path = tmp_path / "new.json"
    assert cli("new", path).code == 0
    assert condition_checks.FLOW_NOTE not in cli("boundary", path, "list").out
    assert cli("stages", path, "set", "initial", "--calculation", "flow").code == 0
    listed = cli("boundary", path, "list").out
    assert listed.strip().endswith(condition_checks.FLOW_NOTE)
    assert "fixed_bottom" in listed


@pytest.mark.parametrize("name", ["SECTION_NOTE", "FLOW_NOTE"])
def test_the_notes_under_a_list_are_the_gui_s_word_for_word(name):
    import re
    from pathlib import Path
    from core.kratos import condition_checks
    source = (Path(__file__).resolve().parents[2] / "frontend" / "js"
              / "boundary-conditions.js").read_text(encoding="utf-8")
    found = re.search(rf"var {name} = ((?:'[^']*'\s*\+?\s*)+);", source)
    assert found, f"{name} is not in boundary-conditions.js"
    assert "".join(re.findall(r"'([^']*)'", found.group(1))) == getattr(condition_checks,
                                                                         name)


@pytest.mark.parametrize("argv, fixed", [
    (["--face", "bottom", "--fixed"], (True, True, True)),
    (["--face", "bottom", "--roller"], (False, True, False)),
    (["--face", "left", "--fix", "x", "y"], (True, True, False)),
    (["--line", "0", "-5", "10", "-5", "--roller"], (False, True, False)),
    (["--point", "5", "-5", "--fix", "y"], (False, True, False)),
    (["--part", "soil_L2", "--fixed"], (True, True, True)),
])
def test_a_support_holds_the_components_it_is_given(cli, dry, argv, fixed):
    ran = cli("boundary", dry, "add", "s", *argv)

    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert (record.kind, record.fixed) == ("displacement", fixed)


@pytest.mark.parametrize("argv, message", [
    (["--face", "left"], "--fixed, --roller or --fix"),
    (["--domain", "--fixed"], "whole model still"),
    (["--line", "0", "0", "5", "-5", "--roller"], "sloping line"),
    (["--face", "left", "--fixed", "--value", "3"], "--value belong to a water pressure"),
    (["--face", "left", "--roller", "--water-pressure", "Uniform"], "a support's"),
])
def test_an_unclear_support_is_refused(cli, dry, argv, message):
    ran = cli("boundary", dry, "add", *argv)

    assert ran.code == 1
    assert message in ran.err


def test_set_changes_what_a_support_holds_and_where(cli, dry):
    assert cli("boundary", dry, "add", "s", "--face", "bottom", "--fixed").code == 0
    assert cli("boundary", dry, "set", "s", "--roller").code == 0
    assert conditions(dry)[0].fixed == (False, True, False)

    assert cli("boundary", dry, "set", "s", "--face", "left", "--roller").code == 0
    assert (conditions(dry)[0].face, conditions(dry)[0].fixed) == ("left",
                                                                   (True, False, False))
    assert cli("boundary", dry, "set", "s", "--fix", "y", "--inactive").code == 0
    assert (conditions(dry)[0].fixed, conditions(dry)[0].active) == ((False, True, False),
                                                                     False)
    ran = cli("boundary", dry, "set", "s", "--initial")
    assert ran.code == 1 and "water pressure's" in ran.err


def test_standard_puts_the_supports_back_and_keeps_the_water(cli, dry):
    assert cli("boundary", dry, "add", "s", "--face", "bottom", "--roller").code == 0
    assert cli("boundary", dry, "add", "wp", "--domain", "--water-pressure", "Uniform").code \
        == 0
    ran = cli("boundary", dry, "standard")

    assert ran.code == 0, ran.err
    assert [c.id for c in conditions(dry)] == ["fixed_bottom", "roller_left", "roller_right",
                                               "roller_front", "roller_back", "wp"]
    assert "the bottom fixed, the sides on rollers" in ran.out


def test_check_says_when_nothing_holds_the_model(cli, dry):
    assert "can move as a rigid body" in cli("check", dry).err
    assert cli("boundary", dry, "standard").code == 0
    assert "rigid body" not in cli("check", dry).err


# ── gravity ─────────────────────────────────────────────────────────────────

def test_show_says_whether_the_initial_stage_s_stresses_bring_gravity(cli, dry):
    """No switch of its own: the initial stage's stress initialisation decides it."""
    assert "gravity     on" in cli("show", dry).out
    assert cli("stages", dry, "add").code == 0
    assert cli("show", dry, "--json").json()["gravity"] is True
    assert cli("stages", dry, "set", "initial", "--stress-initialisation", "none").code == 0

    assert "gravity     off" in cli("show", dry).out
    assert cli("show", dry, "--json").json()["gravity"] is False


def test_gravity_sets_g_as_the_project_properties_window_does(cli, dry):
    assert "with g = 9.81 m/s²" in cli("gravity", dry).out
    ran = cli("gravity", dry, "9.80665")

    assert ran.code == 0, ran.err
    assert session.load(dry).gravity_acceleration == 9.80665
    assert "with g = 9.80665 m/s²" in ran.out
    assert "g = 9.80665 m/s²" in cli("show", dry).out
    assert cli("show", dry, "--json").json()["gravity_acceleration"] == 9.80665
    for wrong in ("0", "-9.81", "maybe"):
        refused = cli("gravity", dry, wrong)
        assert refused.code != 0, wrong
    assert session.load(dry).gravity_acceleration == 9.80665


def test_gravity_has_no_switch(cli, dry):
    refused = cli("gravity", dry, "off")
    assert refused.code != 0
    assert "stress initialisation" in refused.err


# ── Seepage faces ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("argv, expected", [
    (["--face", "right"], {"on": "face", "face": "right", "points": None}),
    (["--line", "25", "-1", "25", "-6"],
     {"on": "line", "face": None, "points": [(25.0, -1.0), (25.0, -6.0)]}),
])
def test_seepage_makes_a_seepage_face_on_a_face_or_a_line(cli, dry, argv, expected):
    """`drafts.seepage_condition`, as the GUI's window and its seepage line tool make it."""
    ran = cli("boundary", dry, "add", "--seepage", *argv)

    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert record.kind == "seepage" and record.id == "seepage_1"
    assert {key: getattr(record, key) for key in expected} == expected
    assert "water may leave the soil here" in ran.out


@pytest.mark.parametrize("argv, message", [
    (["--domain"], "a seepage face is on --face FACE or --line"),
    (["--point", "1", "-1"], "a seepage face is on --face FACE or --line"),
    (["--face", "top", "--water-pressure", "Uniform"], "--water-pressure do not belong"),
    (["--face", "top", "--roller"], "--roller do not belong"),
    (["--face", "top", "--reference-coordinate", "1"], "--reference-coordinate do not"),
])
def test_a_seepage_face_takes_a_face_or_a_line_and_nothing_else(cli, dry, argv, message):
    ran = cli("boundary", dry, "add", "--seepage", *argv)

    assert ran.code == 1
    assert message in ran.err


def test_set_moves_a_seepage_face_and_keeps_it_one(cli, dry):
    assert cli("boundary", dry, "add", "exit", "--seepage", "--face", "right").code == 0

    ran = cli("boundary", dry, "set", "exit", "--line", "25", "0", "25", "-4",
              "--name", "Exit")
    assert ran.code == 0, ran.err
    [record] = conditions(dry)
    assert (record.kind, record.on, record.face, record.name) == ("seepage", "line", None,
                                                                  "Exit")
    assert cli("boundary", dry, "set", "exit", "--fixed").code == 1
    listed = cli("boundary", dry, "list").out
    assert "exit  Exit  seepage on line (25, 0) -> (25, -4); water may leave the soil here" \
        in listed


def test_check_says_a_seepage_face_needs_a_flow_calculation(cli, dry):
    assert cli("boundary", dry, "add", "--face", "bottom", "--fixed").code == 0
    assert cli("boundary", dry, "add", "--seepage", "--face", "right").code == 0

    ran = cli("check", dry)
    assert "seepage condition 'Seepage face 1' is left out" in ran.err + ran.out


# ── boundary soil-water ─────────────────────────────────────────────────────

@pytest.fixture
def lines(cli, dry):
    """The dry section with a phreatic line on the whole soil and an aquifer's head drawn
    on a line, sloping."""
    assert cli("boundary", dry, "add", "phreatic", "--domain", "--water-pressure",
               "Phreatic_Multi_Line", "--phreatic-line", "0", "-1", "25", "-1").code == 0
    ran = cli("boundary", dry, "add", "head", "--line", "0", "1", "25", "3",
              "--water-pressure", "Head_Line", "--phreatic-line", "0", "1", "25", "3")
    assert ran.code == 0, ran.err
    return dry


def test_each_soil_takes_the_phreatic_line_until_it_is_given_another(cli, lines):
    ran = cli("boundary", lines, "soil-water")
    assert ran.code == 0, ran.err
    assert "soil_L1  the phreatic line phreatic" in ran.out

    ran = cli("boundary", lines, "soil-water", "soil_L2", "head")
    assert ran.code == 0, ran.err
    assert "soil_L2  the head line head (head)" in ran.out
    ran = cli("boundary", lines, "soil-water", "soil_L1", "interpolate")
    assert ran.code == 0, ran.err
    assert session.load(lines).soil_water == {"soil_L2": "head", "soil_L1": "interpolate"}

    assert cli("boundary", lines, "soil-water", "soil_L1", "default").code == 0
    assert session.load(lines).soil_water == {"soil_L2": "head"}


@pytest.mark.parametrize("argv, said", [
    (["soil_L9", "head"], "not a soil of this project"),
    (["soil_L1", "nowhere"], "not a head line"),
    (["soil_L1", "phreatic"], "not a head line"),
    (["soil_L1"], "give the soil's water"),
])
def test_a_soil_s_water_must_name_a_soil_and_a_line(cli, lines, argv, said):
    ran = cli("boundary", lines, "soil-water", *argv)
    assert ran.code == 1
    assert said in ran.err


def test_a_head_line_needs_its_points(cli, lines):
    ran = cli("boundary", lines, "add", "--domain", "--water-pressure", "Head_Line")
    assert ran.code == 1
    assert "a Head_Line needs its points" in ran.err


def test_a_head_line_is_listed_as_one(cli, lines):
    ran = cli("boundary", lines, "list")
    assert "head line (0, 1) -> (25, 3), fixed" in ran.out


def test_a_second_phreatic_line_is_refused(cli, lines):
    ran = cli("boundary", lines, "add", "--face", "left", "--water-pressure",
              "Phreatic_Multi_Line", "--phreatic-line", "0", "-2", "25", "-2")
    assert ran.code == 1
    assert "one phreatic line" in ran.err
