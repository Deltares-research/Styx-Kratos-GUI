"""`section`, `beam`, `wall`, `member`, `anchor`, `interface`, `load`, `normal-load`: the
structures of a model, built in the terminal (plan/active/cli-plan.md M3).

Each new one starts where the Structure mode's tool puts it (`core.model.drafts`, held
to the JavaScript by tests/test_draft_parity.py), and each edit is `core.session`'s. The
acceptance test at the bottom builds the structures of `tests/models/excavation.py` with
commands alone and checks they are the ones that script builds.
"""

from __future__ import annotations

import pytest

from core import session
from core.model import drafts
from tests.models import excavation

STRUCTURES = ("beam_sections", "panel_sections", "beams", "anchor_sections", "anchors",
              "interface_sections", "interfaces", "loads", "normal_loads")


@pytest.fixture
def pit(tmp_path):
    """The test model's ground, wall, strut and contact, with no stages: something to
    hang structures on and take them off again."""
    return session.save(excavation.excavation_project(staged=False), tmp_path / "pit.json")


@pytest.fixture
def solid(cli, site):
    """The demo site as the solid model."""
    assert cli("dimension", site, "3d").code == 0
    return site


# ── section ─────────────────────────────────────────────────────────────────

def test_section_add_starts_from_the_gui_s_profile_and_takes_variables(cli, site):
    ran = cli("section", site, "add", "beam", "az26", "--name", "AZ 26", "--spacing", "1.2",
              "I33=6e-4")

    assert ran.code == 0, ran.err
    az26 = session.load(site).beam_sections[0]
    assert (az26.name, az26.spacing, az26.variables["I33"]) == ("AZ 26", 1.2, 6e-4)
    assert az26.variables["CROSS_AREA"] == drafts.SECTION_DEFAULTS_SI["beam"]["variables"][
        "CROSS_AREA"]


def test_section_set_unset_list_and_remove(cli, pit):
    assert cli("section", pit, "set", "strand", "--tension-limit", "5e5",
               "--unset", "DENSITY", "CROSS_AREA=3e-3").code == 0
    strand = session.load(pit).anchor_sections[0]
    assert (strand.tension_limit, strand.variables["CROSS_AREA"]) == (5e5, 3e-3)
    assert "DENSITY" not in strand.variables

    listed = cli("section", pit, "list").out
    assert "sheetpile" in listed and "strand" in listed and "contact" in listed

    ran = cli("section", pit, "remove", "strand")     # the strut is built with it
    assert ran.code == 1 and "strut" in ran.err


def test_a_section_field_its_kind_does_not_have_is_refused(cli, site):
    ran = cli("section", site, "add", "panel", "w1", "--spacing", "2")

    assert ran.code == 1
    assert "--spacing" in ran.err and "panel" in ran.err


def test_a_coulomb_contact_against_a_linear_elastic_soil_gets_a_strength_of_its_own(cli, site):
    """As the GUI's contact editor gives it (`App.Interfaces.setOwnStrength`): the soil
    has none to give, so the contact starts from the Mohr-Coulomb defaults, keeps what it
    was given, and the command says so."""
    ran = cli("section", site, "add", "interface", "c1", "--law",
              "GeoInterfaceCoulombLawPlaneStrain", "--material", "m1", "GEO_FRICTION_ANGLE=20")

    assert ran.code == 0, ran.err
    c1 = session.load(site).interface_sections[0]
    assert (c1.variables["GEO_COHESION"], c1.variables["GEO_FRICTION_ANGLE"]) == (1000.0, 20)
    assert ("Fill is linear elastic and has no strength to give: the contact has a strength "
            "of its own now. Set its GEO_COHESION and GEO_FRICTION_ANGLE.") in ran.out

    assert cli("section", site, "add", "interface", "c2", "--law",
               "GeoInterfaceCoulombLawPlaneStrain", "--material", "none").code == 0
    assert "GEO_COHESION" not in session.load(site).interface_sections[1].variables, \
        "against the soil on each side, which only the export knows"
    assert "strength of its own" not in cli("section", site, "set", "c1",
                                            "GEO_COHESION=500").out


def test_a_section_number_must_be_a_number_or_none(cli, site):
    ran = cli("section", site, "add", "beam", "az26", "--spacing", "often")

    assert ran.code == 1
    assert "--spacing takes a number, or none" in ran.err
    assert session.load(site).beam_sections == []


def test_none_clears_an_optional_section_field(cli, pit):
    assert cli("section", pit, "set", "contact", "--r-inter", "none").code == 0

    assert session.load(pit).interface_sections[0].r_inter is None


# ── beam, wall, member ──────────────────────────────────────────────────────

def test_a_first_sheet_pile_brings_the_default_profile(cli, site):
    ran = cli("beam", site, "add", "--points", "10", "0", "10", "-8")

    assert ran.code == 0, ran.err
    project = session.load(site)
    assert project.beams[0].points == [(10.0, 0.0), (10.0, -8.0)]
    assert [s.id for s in project.beam_sections] == ["beamsection_1"]
    assert "beamsection_1" in ran.out


def test_a_sheet_pile_with_no_points_runs_down_the_middle(cli, site):
    assert cli("beam", site, "add", "front").code == 0

    pile = session.load(site).beams[0]
    assert (pile.id, pile.name) == ("front", "front")
    assert pile.points == drafts.sheet_pile(session.load(site)).points


def test_an_id_another_part_has_is_refused(cli, site):
    ran = cli("beam", site, "add", "wall")      # the demo's own wall

    assert ran.code == 1
    assert "already a part 'wall'" in ran.err


def test_a_section_that_is_not_there_is_refused_with_how_to_add_one(cli, site):
    ran = cli("beam", site, "add", "--section", "az99")

    assert ran.code == 1
    assert "no beam section 'az99'" in ran.err and "section" in ran.err


def test_beam_set_list_and_remove(cli, pit):
    assert cli("beam", pit, "add", "kingpost", "--points", "30", "0", "30", "-5").code == 0
    assert cli("beam", pit, "set", "kingpost", "--points", "31", "0", "31", "-6",
               "--inactive").code == 0

    post = session.load(pit).beams[-1]
    assert (post.points, post.active) == ([(31.0, 0.0), (31.0, -6.0)], False)
    assert "kingpost" in cli("beam", pit, "list").out and "inactive" in cli(
        "beam", pit, "list").out

    assert cli("beam", pit, "remove", "kingpost").code == 0
    ran = cli("beam", pit, "remove", "sheetpile")     # the strut hangs from it
    assert ran.code == 1 and "strut" in ran.err


@pytest.mark.parametrize("noun, id, message", [
    ("beam", "strut", "strut is an anchor; use `kratos-cli anchor`"),
    ("anchor", "sheetpile", "sheetpile is a sheet pile; use `kratos-cli beam`"),
])
def test_a_structure_command_names_the_command_for_the_record_kind(cli, pit, noun, id, message):
    ran = cli(noun, pit, "set", id, "--name", "Wrong command")

    assert ran.code == 1
    assert message in ran.err


def test_a_wall_is_a_3d_structure(cli, site, solid):
    ran = cli("wall", solid, "add", "--footprint", "5", "5", "5", "20", "--toe", "-10")

    assert ran.code == 0, ran.err
    wall = session.load(solid).beams[0]
    assert (wall.footprint, wall.y_top, wall.y_toe) == ([(5.0, 5.0), (5.0, 20.0)], 0.0, -10.0)
    assert session.load(solid).panel_sections[0].id == "panelsection_1"


def test_a_wall_in_a_section_is_refused(cli, site):
    ran = cli("wall", site, "add")

    assert ran.code == 1
    assert "3D model" in ran.err


def test_a_member_stands_in_the_solid_model(cli, solid):
    assert cli("member", solid, "add", "--points", "3", "0", "3", "3", "-10", "3").code == 0

    assert session.load(solid).beams[0].points == [(3.0, 0.0, 3.0), (3.0, -10.0, 3.0)]


# ── anchor ──────────────────────────────────────────────────────────────────

def test_an_anchor_head_is_snapped_onto_the_pile(cli, pit):
    ran = cli("anchor", pit, "add", "tie", "--head", "6.4", "-2", "--tail", "20", "-8",
              "--prestress", "1e5")

    assert ran.code == 0, ran.err
    tie = session.load(pit).anchors[-1]
    assert (tie.head, tie.tail, tie.prestress, tie.section) == ((6.0, -2.0), (20.0, -8.0),
                                                               1e5, "strand")


def test_an_anchor_with_no_tail_rakes_back(cli, pit):
    assert cli("anchor", pit, "add", "--head", "6", "-2").code == 0

    project = session.load(pit)
    assert project.anchors[-1].tail == drafts.anchor(project, head=(6, -2)).tail


def test_an_anchor_head_far_from_the_pile_is_refused(cli, pit):
    ran = cli("anchor", pit, "add", "--head", "10", "-2", "--tail", "20", "-8")

    assert ran.code == 1
    assert "on a sheet pile" in ran.err


def test_anchor_set_moves_the_head_onto_the_pile_and_list_shows_it(cli, pit):
    assert cli("anchor", pit, "set", "strut", "--head", "6.2", "-1.5").code == 0

    assert session.load(pit).anchors[0].head == (6.0, -1.5)
    assert "strut" in cli("anchor", pit, "list").out


def test_an_anchor_hangs_from_a_wall_in_3d(cli, solid):
    cli("wall", solid, "add")

    ran = cli("anchor", solid, "add")

    assert ran.code == 0, ran.err
    assert session.load(solid).anchors[0].kind == "anchor3d"


# ── interface ───────────────────────────────────────────────────────────────

def test_an_interface_follows_a_pile_or_runs_its_own_line(cli, pit):
    # The pit's own contact holds both faces; one face is left for a second one.
    assert cli("interface", pit, "set", "wall_contact", "--side", "left").code == 0
    assert cli("interface", pit, "add", "back", "--structure", "sheetpile",
               "--side", "right").code == 0
    assert cli("interface", pit, "add", "slip", "--points", "10", "0", "20", "-10").code == 0

    back, slip = session.load(pit).interfaces[-2:]
    assert (back.structure, back.side) == ("sheetpile", "right")
    assert (slip.structure, slip.points, slip.side) == (None, [(10.0, 0.0), (20.0, -10.0)],
                                                        "left")


def test_an_interface_holds_a_part_of_its_pile_between_from_and_to(cli, pit):
    assert cli("interface", pit, "set", "wall_contact", "--side", "right").code == 0
    added = cli("interface", pit, "add", "upper", "--structure", "sheetpile", "--side",
                "left", "--from", "6.2", "0", "--to", "6", "-4")
    assert added.code == 0, added.err

    upper = session.load(pit).interfaces[-1]
    assert upper.stretch == ((6.0, 0.0), (6.0, -4.0)), "From is moved onto the pile"
    listed = cli("interface", pit, "list").out
    assert "upper  upper  along sheetpile from (6, 0) to (6, -4), left" in listed

    assert cli("interface", pit, "set", "upper", "--to", "6", "-8").code == 0
    assert session.load(pit).interfaces[-1].stretch == ((6.0, 0.0), (6.0, -8.0))
    assert cli("interface", pit, "set", "upper", "--whole-pile").code == 0
    assert session.load(pit).interfaces[-1].stretch is None


def test_an_interface_part_is_refused_as_in_the_window(cli, pit):
    far = cli("interface", pit, "add", "--structure", "sheetpile", "--from", "7.2", "-2")
    assert far.code != 0 and "From is 1.2 m from SheetPileWall" in far.err

    twice = cli("interface", pit, "add", "--structure", "sheetpile", "--side", "left",
                "--from", "6", "-2", "--to", "6", "-6")
    assert twice.code != 0
    assert "both hold the left face of SheetPileWall between y -2 and y -6" in twice.err

    free = cli("interface", pit, "add", "slip", "--points", "10", "0", "20", "-10")
    assert free.code == 0
    assert "Give --structure too" in cli("interface", pit, "set", "slip", "--from", "6",
                                          "-2").err


def test_an_interface_is_set_and_removed(cli, pit):
    assert cli("interface", pit, "set", "wall_contact", "--side", "left").code == 0
    assert session.load(pit).interfaces[0].side == "left"

    assert cli("interface", pit, "remove", "wall_contact").code == 0
    assert session.load(pit).interfaces == []


# ── load, normal-load ───────────────────────────────────────────────────────

def test_a_line_load_and_a_point_load_in_the_section(cli, site):
    assert cli("load", site, "add", "line", "--x", "2", "8").code == 0
    assert cli("load", site, "add", "point", "kick", "--at", "5", "0",
               "--components", "1000", "-5000").code == 0

    line, kick = session.load(site).loads[-2:]
    assert (line.kind, line.x0, line.x1, line.components) == ("line", 2.0, 8.0,
                                                              (0.0, -20000.0))
    assert (kick.kind, kick.x, kick.components) == ("point", 5.0, (1000.0, -5000.0))


def test_a_new_load_is_reported_with_its_id_and_its_name_apart(cli, pit):
    # `load add line load --name Heavy` makes a load whose id is "load".
    ran = cli("load", pit, "add", "line", "load", "--name", "Heavy", "--x", "10", "20")

    assert ran.code == 0, ran.err
    assert "added line load (id load, name Heavy)" in ran.out


def test_a_load_given_only_a_name_takes_it_as_its_id(cli, pit):
    ran = cli("load", pit, "add", "line", "--name", "Heavy", "--x", "10", "20")

    assert ran.code == 0, ran.err
    assert "added line load (id Heavy, name Heavy)" in ran.out
    assert cli("stages", pit, "add", "--activate", "Heavy").code == 0


def test_a_name_another_part_has_as_its_id_is_refused_with_why(cli, pit):
    ran = cli("load", pit, "add", "line", "--name", "strut", "--x", "10", "20")

    assert ran.code == 1
    assert "already a part 'strut'" in ran.err and "came from --name" in ran.err


def test_a_section_needs_an_id_or_a_name(cli, site):
    assert cli("section", site, "add", "beam", "--name", "AZ 26").code == 0
    assert session.load(site).beam_sections[0].id == "AZ 26"

    ran = cli("section", site, "add", "beam")
    assert ran.code == 1 and "--name" in ran.err


def test_load_list_shows_this_dimension_s_loads(cli, site):
    listed = cli("load", site, "list").out

    assert "load_2d" in listed and "SurfaceLoad_1" not in listed


def test_a_surface_load_is_for_the_solid_model(cli, site, solid):
    assert cli("load", solid, "add", "surface", "--x", "2", "6", "--z", "2", "6").code == 0

    pad = session.load(solid).loads[-1]
    assert (pad.kind, pad.x0, pad.z1) == ("surface", 2.0, 6.0)


def test_a_point_load_in_the_solid_model_is_refused(cli, solid):
    ran = cli("load", solid, "add", "point", "--at", "5", "0")

    assert ran.code == 1 and "2D" in ran.err


def test_load_set_and_remove(cli, site):
    assert cli("load", site, "set", "load_2d", "--components", "0", "-5000",
               "--x", "1", "12").code == 0
    load = next(item for item in session.load(site).loads if item.id == "load_2d")
    assert (load.components, load.x1) == ((0.0, -5000.0), 12.0)

    assert cli("load", site, "remove", "load_2d").code == 0


def test_a_normal_load_is_uniform_unless_it_is_hydrostatic(cli, pit):
    assert cli("normal-load", pit, "add", "push", "--points", "6", "-1", "6", "-3",
               "--pressure", "5000").code == 0
    assert cli("normal-load", pit, "set", "water_1", "--pressure", "1").code == 0

    project = session.load(pit)
    push = project.normal_loads[-1]
    assert (push.fluid_pressure_type, push.pressure) == ("Uniform", 5000.0)
    assert "push" in cli("normal-load", pit, "list").out
    assert cli("normal-load", pit, "remove", "push").code == 0


def test_section_set_renames_a_section_and_accepts_a_constitutive_law(cli, pit):
    original = session.load(pit).beam_sections[0]
    assert original.constitutive_law != "BeamConstitutiveLaw"
    ran = cli("section", pit, "set", original.id, "--name", "Renamed profile",
              "--law", "BeamConstitutiveLaw")

    assert ran.code == 0, ran.err
    changed = session.load(pit).beam_sections[0]
    assert changed.name == "Renamed profile"
    assert changed.constitutive_law == "BeamConstitutiveLaw"


def test_beam_set_changes_the_section_reference(cli, pit):
    made = cli("section", pit, "add", "beam", "replacement")
    assert made.code == 0, made.err

    changed = cli("beam", pit, "set", "sheetpile", "--section", "replacement")

    assert changed.code == 0, changed.err
    assert session.load(pit).sheet_piles[0].section == "replacement"


def test_wall_set_updates_footprint_and_levels_and_lists_them(cli, solid):
    made = cli("wall", solid, "add", "panel1", "--footprint", "5", "5", "5", "20",
               "--top", "0", "--toe", "-10")
    assert made.code == 0, made.err

    ran = cli("wall", solid, "set", "panel1", "--footprint", "6", "5", "6", "18",
              "--top", "-1", "--toe", "-12")

    assert ran.code == 0, ran.err
    panel = session.load(solid).panels[0]
    assert panel.footprint == [(6, 5), (6, 18)]
    assert (panel.y_top, panel.y_toe) == (-1, -12)
    listed = cli("wall", solid, "list")
    assert listed.code == 0, listed.err
    assert "(6, 5) -> (6, 18), -1 .. -12" in listed.out


def test_anchor_set_updates_tail_and_prestress(cli, pit):
    ran = cli("anchor", pit, "set", "strut", "--tail", "4", "-2", "--prestress", "5000")

    assert ran.code == 0, ran.err
    anchor = session.load(pit).anchors[0]
    assert anchor.tail == (4, -2)
    assert anchor.prestress == 5000


@pytest.mark.parametrize("option", ["--head", "--tail"])
def test_anchor_endpoint_options_refuse_more_than_one_point_without_saving(cli, pit, option):
    before = pit.read_bytes()

    ran = cli("anchor", pit, "set", "strut", option, "6", "-1", "6", "-2")

    assert ran.code == 1
    assert f"{option} takes one point, 2 numbers" in ran.err
    assert pit.read_bytes() == before


def test_interface_set_switches_between_a_free_line_and_a_structure(cli, pit):
    ran = cli("interface", pit, "set", "wall_contact", "--points", "10", "0", "10", "-5",
              "--side", "left")
    assert ran.code == 0, ran.err
    free = session.load(pit).interfaces[0]
    assert free.structure is None
    assert free.points == [(10, 0), (10, -5)]
    assert free.stretch is None
    listed = cli("interface", pit, "list")
    assert listed.code == 0, listed.err
    assert "(10, 0) -> (10, -5)" in listed.out

    ran = cli("interface", pit, "set", "wall_contact", "--structure", "sheetpile",
              "--from", "6", "-2", "--to", "6", "-6")

    assert ran.code == 0, ran.err
    attached = session.load(pit).interfaces[0]
    assert attached.structure == "sheetpile"
    assert attached.points is None
    assert attached.stretch == ((6, -2), (6, -6))


def test_whole_pile_and_partial_stretch_are_mutually_refused_without_saving(cli, pit):
    before = pit.read_bytes()

    ran = cli("interface", pit, "set", "wall_contact", "--whole-pile", "--from", "6", "-2")

    assert ran.code == 1
    assert "leave out --from and --to" in ran.err
    assert pit.read_bytes() == before


def test_normal_load_set_changes_geometry_and_hydraulic_type(cli, pit):
    made = cli("normal-load", pit, "add", "push", "--points", "6", "-1", "6", "-3",
               "--pressure", "5000")
    assert made.code == 0, made.err
    level = session.load(pit).water.y

    ran = cli("normal-load", pit, "set", "push", "--points", "6", "-2", "6", "-4",
              "--hydrostatic")

    assert ran.code == 0, ran.err
    load = session.load(pit).normal_loads[-1]
    assert load.points == [(6, -2), (6, -4)]
    assert load.fluid_pressure_type == "Hydrostatic"
    assert load.reference_coordinate == level


def test_point_and_line_load_edits_persist_and_are_listed(cli, site):
    made = cli("load", site, "add", "point", "kick", "--at", "5", "0")
    assert made.code == 0, made.err
    ran = cli("load", site, "set", "kick", "--at", "6", "-1",
              "--components", "100", "-200")
    assert ran.code == 0, ran.err
    point = next(load for load in session.load(site).loads if load.id == "kick")
    assert (point.x, point.y, point.components) == (6, -1, (100, -200))
    ran = cli("load", site, "set", "load_2d", "--y", "-1")
    assert ran.code == 0, ran.err
    line = next(load for load in session.load(site).loads if load.id == "load_2d")
    assert line.y == -1
    listed = cli("load", site, "list")
    assert listed.code == 0, listed.err
    assert "at (6, -1)" in listed.out
    assert "at y -1" in listed.out


def test_surface_load_set_updates_the_plan_extent_and_lists_it(cli, solid):
    made = cli("load", solid, "add", "surface", "pad", "--x", "2", "6", "--z", "2", "6")
    assert made.code == 0, made.err

    ran = cli("load", solid, "set", "pad", "--z", "8", "3")

    assert ran.code == 0, ran.err
    pad = next(load for load in session.load(solid).loads if load.id == "pad")
    assert (pad.z0, pad.z1) == (3, 8)
    listed = cli("load", solid, "list")
    assert listed.code == 0, listed.err
    assert "x 2 .. 6, z 3 .. 8" in listed.out


def test_load_components_require_the_dimension_of_the_load(cli, site):
    before = site.read_bytes()

    ran = cli("load", site, "set", "load_2d", "--components", "1", "2", "3")

    assert ran.code == 1
    assert "--components takes 2 numbers here: x y" in ran.err
    assert site.read_bytes() == before


# ── The structures of the test model, from commands alone ───────────────────

def test_the_structures_of_the_test_model_are_built_with_commands_alone(cli, tmp_path):
    """The wall, its profile, the strut and its tendon, the contact on both faces, the
    surcharge and one water load per lift: every structure `tests/models/excavation.py`
    builds, typed on top of its ground."""
    target = excavation.excavation_project(staged=False)
    ground = target.model_dump()
    for field in STRUCTURES:
        ground[field] = []
    path = session.save(type(target).model_validate(ground), tmp_path / "pit.json")

    def run(*argv):
        ran = cli(*argv)
        assert ran.code == 0, (argv, ran.err)

    def variables(section):
        return [f"{name}={value!r}" for name, value in section.variables.items()]

    profile, tendon = target.beam_sections[0], target.anchor_sections[0]
    contact = target.interface_sections[0]
    run("section", path, "add", "beam", profile.id, "--name", profile.name,
        *variables(profile))
    run("section", path, "add", "anchor", tendon.id, "--name", tendon.name, "--spacing",
        repr(tendon.spacing), "--tension-limit", "none", *variables(tendon))
    run("section", path, "add", "interface", contact.id, "--name", contact.name,
        "--material", "none", "--r-inter", repr(contact.r_inter),
        "--virtual-thickness", repr(contact.virtual_thickness))
    run("beam", path, "add", "sheetpile", "--name", "SheetPileWall", "--points",
        "6", "0", "6", "-12")
    run("anchor", path, "add", "strut", "--name", "Strut", "--head", "6", "-1",
        "--tail", "5", "-1")
    run("interface", path, "add", "wall_contact", "--name", "Interface",
        "--structure", "sheetpile", "--side", "both")
    run("load", path, "add", "line", "surcharge", "--name", "Load", "--x", "6", "60",
        "--components", "0", "-10000")
    for index, level in enumerate(excavation.LIFTS, start=1):
        run("normal-load", path, "add", f"water_{index}", "--name",
            f"WaterLoad_Stage{index}", "--hydrostatic", "--points",
            "0", repr(level), "6", repr(level), "6", "-1")

    built = session.load(path)
    for field in STRUCTURES:
        assert getattr(built, field) == getattr(target, field), field
