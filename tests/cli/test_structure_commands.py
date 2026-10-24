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
    """The test model's ground, wall, strut and contact, with no phases: something to
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
    assert cli("interface", pit, "add", "back", "--structure", "sheetpile",
               "--side", "right").code == 0
    assert cli("interface", pit, "add", "slip", "--points", "10", "0", "20", "-10").code == 0

    back, slip = session.load(pit).interfaces[-2:]
    assert (back.structure, back.side) == ("sheetpile", "right")
    assert (slip.structure, slip.points, slip.side) == (None, [(10.0, 0.0), (20.0, -10.0)],
                                                        "left")


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
