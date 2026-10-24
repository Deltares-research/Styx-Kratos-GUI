"""`domain`, `borehole`, `layer`, `material`, `excavation`, `volume`, `parts`: the full
geometry of a model, built in the terminal (plan/active/cli-plan.md M2).

Each command makes its edit through `core.session`, the way the GUI's soil dialogs make
it, and starts a new record from `core.model.drafts`, the way those dialogs start one.
The acceptance test at the bottom builds the ground of `tests/models/excavation.py`
with commands alone and checks it is the ground that script builds.
"""

from __future__ import annotations

import pytest

from core import session
from core.geometry import cad_import, primitives
from core.model import drafts
from tests.models import excavation
from tests.test_importer import obj_text


@pytest.fixture(autouse=True)
def solids_in_this_test_s_folder(tmp_path, monkeypatch):
    """A drawn or imported solid is written as a .brep under `.data`; here, under the
    test's own folder instead of the repository's."""
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cad_import, "DATA_DIR", tmp_path / "data")


@pytest.fixture
def empty(cli, tmp_path):
    """A new, empty plane-strain site, as `kratos-cli new` writes it."""
    path = tmp_path / "empty.json"
    assert cli("new", path).code == 0
    return path


# ── domain ──────────────────────────────────────────────────────────────────

def test_domain_sets_the_extents_given_and_shows_them(cli, empty):
    assert cli("domain", empty, "--x", "0", "60", "--y", "-40", "0").code == 0

    domain = session.load(empty).domain
    assert (domain.x0, domain.x1, domain.y_bottom, domain.y_top) == (0, 60, -40, 0)
    assert "60" in cli("domain", empty).out


def test_a_2d_domain_names_its_section_not_its_z_range(cli, empty):
    """A 2D model is the cut at one z; the z range is kept for the switch to 3D, and
    printed only there."""
    ran = cli("domain", empty, "--x", "0", "20", "--y", "0", "10")

    assert ran.code == 0
    assert "domain x 0 .. 20, y 0 .. 10 (2D section at z = 0)" in ran.out
    assert "z -10 .. 10" not in ran.out and "z -10 .. 10" not in cli("show", empty).out

    assert cli("dimension", empty, "3").code == 0
    assert "z -10 .. 10" in cli("domain", empty).out
    assert "z -10 .. 10" in cli("show", empty).out


def test_domain_says_when_it_moves_the_section(cli, empty):
    ran = cli("domain", empty, "--z", "0", "4")

    assert ran.code == 0
    assert "section" in ran.out
    assert session.load(empty).section_offset == 2.0


# ── borehole ────────────────────────────────────────────────────────────────

def test_borehole_add_list_set_and_remove(cli, site):
    assert cli("borehole", site, "add", "bh4", "--x", "40").code == 0
    assert "bh4" in cli("borehole", site, "list").out

    assert cli("borehole", site, "set", "bh4", "--water", "-3").code == 0
    assert session.load(site).boreholes[-1].water == -3.0

    assert cli("borehole", site, "remove", "bh4").code == 0
    assert "bh4" not in [b.id for b in session.load(site).boreholes]


def test_a_borehole_that_is_not_there_is_named(cli, site):
    ran = cli("borehole", site, "set", "bh9", "--x", "1")

    assert ran.code == 1
    assert "no borehole 'bh9'" in ran.err and "bh1" in ran.err


# ── material ────────────────────────────────────────────────────────────────

def test_material_presets_lists_the_library(cli, site):
    ran = cli("material", site, "presets")

    assert ran.code == 0
    for entry in drafts.LIBRARY:
        assert entry["id"] in ran.out and entry["name"] in ran.out


def test_material_add_from_a_preset_with_variables_of_its_own(cli, site):
    ran = cli("material", site, "add", "clay", "--preset", "m3", "YOUNG_MODULUS=5e6",
              "GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD")

    assert ran.code == 0, ran.err
    clay = session.load(site).materials[-1]
    assert (clay.id, clay.name) == ("clay", "Clay, soft")
    assert clay.variables["YOUNG_MODULUS"] == 5e6
    assert clay.variables["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"


def test_material_set_and_unset_variables(cli, site):
    assert cli("material", site, "set", "m1", "K0_NC=0.5", "--unset", "GEO_COHESION",
               "--name", "Fill, wet").code == 0

    m1 = session.load(site).materials[0]
    assert (m1.variables["K0_NC"], m1.name) == (0.5, "Fill, wet")
    assert "GEO_COHESION" not in m1.variables


def test_a_variable_that_is_not_name_equals_value_is_refused(cli, site):
    ran = cli("material", site, "set", "m1", "YOUNG_MODULUS")

    assert ran.code == 1
    assert "NAME=VALUE" in ran.err


def test_material_list_and_remove(cli, site):
    assert "Sand, loose" in cli("material", site, "list").out
    assert cli("material", site, "remove", "m6").code == 0
    assert "m6" not in [m.id for m in session.load(site).materials]

    ran = cli("material", site, "remove", "m2")      # layer L1 is of it
    assert ran.code == 1


# ── layer ───────────────────────────────────────────────────────────────────

def test_layer_add_list_set_split_and_remove(cli, site):
    assert cli("layer", site, "add", "L3", "--material", "m1", "--thickness", "4").code == 0
    assert "L3" in cli("layer", site, "list").out

    assert cli("layer", site, "set", "L1", "--bottom", "-10").code == 0
    layers = session.load(site).layers
    assert layers[1].tops["bh1"] == -10.0

    assert cli("layer", site, "split", "L2", "L2b").code == 0
    assert [layer.id for layer in session.load(site).layers] == ["L1", "L2", "L2b", "L3"]

    assert cli("layer", site, "remove", "L2b").code == 0
    assert [layer.id for layer in session.load(site).layers] == ["L1", "L2", "L3"]


def test_a_layer_level_that_crosses_its_neighbour_is_refused(cli, site):
    before = site.read_bytes()

    ran = cli("layer", site, "set", "L1", "--bottom", "-40")

    assert ran.code == 1
    assert "layer below" in ran.err
    assert site.read_bytes() == before


def test_a_layer_needs_a_bottom_or_a_thickness_or_takes_five_metres(cli, site):
    assert cli("layer", site, "add", "L3", "--material", "m1").code == 0

    layer = session.load(site).layers[-1]
    assert all(layer.tops[bh] - layer.bots[bh] == 5.0 for bh in layer.tops)


# ── excavation ──────────────────────────────────────────────────────────────

def test_excavation_digs_the_pit_in_lifts(cli, site):
    ran = cli("excavation", site, "--x", "2", "8", "--levels", "-2", "-4", "-6")

    assert ran.code == 0, ran.err
    pit = session.load(site).excavation
    assert (pit.x0, pit.x1, pit.levels) == (2.0, 8.0, [-2.0, -4.0, -6.0])
    assert "-6" in cli("excavation", site).out


def test_excavation_with_one_level_says_it_digs_nothing(cli, site):
    ran = cli("excavation", site, "--x", "2", "8", "--levels", "-3")

    assert ran.code == 0
    assert "two or more levels" in ran.out


# ── parts ───────────────────────────────────────────────────────────────────

def test_parts_lists_what_a_stage_can_switch(cli, site):
    cli("excavation", site, "--x", "2", "8", "--levels", "-2", "-4", "-6")

    ran = cli("parts", site)

    assert ran.code == 0
    assert "soil_L1__lift1" in ran.out and "lift 1" in ran.out
    keys = [part["key"] for part in cli("--json", "parts", site).json()]
    assert keys[:2] == ["soil_L1", "soil_L2"]
    assert set(session.load(site).part_keys()) <= set(keys)


# ── volume ──────────────────────────────────────────────────────────────────

def test_a_2d_volume_is_an_outline_swept_across_the_model(cli, site):
    ran = cli("volume", site, "add", "polygon", "--points", "0", "0", "6", "0", "3", "2",
              "--label", "Embankment", "--material", "m1")

    assert ran.code == 0, ran.err
    part = session.load(site).custom_parts[-1]
    project = session.load(site)
    assert part.recipe == drafts.section_prism(project, [(0, 0), (6, 0), (3, 2)]) \
        | {"label": "Embankment", "material": "m1"}
    assert (part.label, part.mat) == ("Embankment", "m1")
    assert "drawn_0" in ran.out


def test_a_3d_volume_takes_points_in_space_and_an_extrusion(cli, site):
    cli("dimension", site, "3d")

    ran = cli("volume", site, "add", "polygon", "--points", "0", "0", "0", "4", "0", "0",
              "4", "0", "4", "--extrude", "0", "-2", "0")

    assert ran.code == 0, ran.err
    assert session.load(site).custom_parts[-1].recipe["extrusion"] == [0, -2, 0]


def test_a_box_and_a_cylinder(cli, site):
    assert cli("volume", site, "add", "box", "--origin", "0", "-5", "0",
               "--size", "2", "2", "2").code == 0
    assert cli("volume", site, "add", "cylinder", "--center", "10", "-5", "0",
               "--axis", "0", "0", "5", "--radius", "1").code == 0

    assert [p.recipe["kind"] for p in session.load(site).custom_parts] == ["box", "cylinder"]


def test_points_that_do_not_pair_up_are_refused(cli, site):
    ran = cli("volume", site, "add", "polygon", "--points", "0", "0", "6")

    assert ran.code == 1
    assert "pairs" in ran.err


def test_points_can_come_from_a_file(cli, site, tmp_path):
    outline = tmp_path / "outline.csv"
    outline.write_text("x,y\n0,0\n6,0\n3,2\n", encoding="utf-8")

    assert cli("volume", site, "add", "polygon", "--points", f"@{outline}").code == 0

    assert len(session.load(site).custom_parts[-1].recipe["vertices"]) == 3


def test_a_cad_file_is_imported_and_given_a_material(cli, site, tmp_path):
    cube = tmp_path / "cube.obj"
    cube.write_text(obj_text(), encoding="utf-8")

    ran = cli("volume", site, "import", cube, "--material", "m2", "--label", "Block")

    assert ran.code == 0, ran.err
    part = session.load(site).custom_parts[-1]
    assert (part.key, part.label, part.source, part.mat) == ("imported_0", "Block",
                                                             "import", "m2")


def test_a_file_that_is_not_cad_is_refused(cli, site, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("hello", encoding="utf-8")

    ran = cli("volume", site, "import", notes)

    assert ran.code == 1
    assert ".step" in ran.err


def test_volume_list_remove_and_clear(cli, site):
    cli("volume", site, "add", "box", "--origin", "0", "-5", "0", "--size", "2", "2", "2")
    cli("volume", site, "add", "box", "--origin", "5", "-5", "0", "--size", "2", "2", "2")
    assert "drawn_1" in cli("volume", site, "list").out

    assert cli("volume", site, "remove", "drawn_0").code == 0
    assert [p.key for p in session.load(site).custom_parts] == ["drawn_1"]

    assert cli("volume", site, "clear").code == 0
    assert session.load(site).custom_parts == []


# ── The ground of the test model, from commands alone ───────────────────────

def test_the_ground_of_the_test_model_is_built_with_commands_alone(cli, tmp_path):
    """Domain, borehole, both soils, three layers, the pit in three lifts, the water:
    everything about the ground `tests/models/excavation.py` builds, typed instead."""
    target = excavation.excavation_project()
    path = tmp_path / "pit.json"

    def run(*argv):
        ran = cli(*argv)
        assert ran.code == 0, (argv, ran.err)

    run("new", path, "--name", target.name)
    run("domain", path, "--x", "0", "60", "--y", "-40", "0", "--z", "0", "10")
    run("borehole", path, "set", "bh1", "--name", "BH1", "--water", "-1")
    for material in target.materials:
        run("material", path, "add", material.id, "--name", material.name,
            "--color", material.color, "--law", material.constitutive_law,
            *(f"{name}={value if isinstance(value, str) else repr(value)}"
              for name, value in material.variables.items()))
    for layer in target.layers:
        run("layer", path, "add", layer.id, "--material", layer.mat, "--name", layer.name,
            "--bottom", repr(layer.bots["bh1"]))
    run("excavation", path, "--x", "0", "6", "--z", "0", "10", "--levels", "-2", "-4.5", "-7")
    run("water", path, "-1")

    built = session.load(path)
    for field in ("name", "dimension", "section_offset", "domain", "boreholes",
                  "materials", "layers", "excavation", "water"):
        assert getattr(built, field) == getattr(target, field), field
    assert built.soil_body_keys == target.soil_body_keys
