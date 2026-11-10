"""`new`, `show`, `check`, `build`, `dimension`, `units`, `water`: the project file and
the edits that have a command of their own.

An edit writes the file back in place (plan D8); `--out` writes elsewhere and `--dry-run`
writes nothing. A `.py` script is only read: an edit of one needs `--out` (plan D6).
"""

from __future__ import annotations

import json

import pytest

from core import session
from core.model.schemas import Deck
from core.model.templates import blank_project


# ── new ─────────────────────────────────────────────────────────────────────

def test_new_writes_an_empty_site(cli, tmp_path):
    path = tmp_path / "site.json"

    ran = cli("new", path)

    assert ran.code == 0, ran.err
    project = session.load(path)
    assert (project.dimension, project.layers, project.water) == (2, [], None)
    assert "site.json" in ran.out


def test_new_takes_the_dimension_the_units_and_the_name(cli, tmp_path):
    path = tmp_path / "site.json"

    assert cli("new", path, "--dim", "3", "--units", "kN", "--name", "Pit A").code == 0

    project = session.load(path)
    assert (project.dimension, project.unit_system, project.name) == (3, "kN", "Pit A")


def test_new_can_start_from_the_demo_model(cli, tmp_path):
    path = tmp_path / "demo.json"

    assert cli("new", path, "--demo").code == 0

    assert [layer.id for layer in session.load(path).layers] == ["L1", "L2"]


def test_new_does_not_overwrite_a_file_unless_told_to(cli, site):
    before = site.read_bytes()

    ran = cli("new", site)

    assert ran.code == 1
    assert "--force" in ran.err
    assert site.read_bytes() == before
    assert cli("new", site, "--force").code == 0
    assert session.load(site).layers == []


# ── show, check ─────────────────────────────────────────────────────────────

def test_show_says_what_the_model_is(cli, site):
    ran = cli("show", site)

    assert ran.code == 0
    for word in ("Deep excavation", "2D", "SI", "L1", "L2", "soil_L1"):
        assert word in ran.out
    assert "borehole" not in ran.out


def _structures_line(cli, site) -> str:
    line = next(line for line in cli("show", site).out.splitlines() if "structures" in line)
    return line.split(None, 1)[1]


def test_show_counts_one_structure_in_the_singular(cli, site):
    assert cli("beam", site, "add", "--points", "5", "0", "5", "-10").code == 0

    assert _structures_line(cli, site) == "1 beam, 2 loads"


def test_show_leaves_out_the_structures_the_model_has_none_of(cli, site):
    for load in session.load(site).loads:
        assert cli("load", site, "remove", load.id).code == 0

    assert _structures_line(cli, site) == "none"


def test_show_as_json_is_a_summary_a_script_can_read(cli, site):
    answer = cli("--json", "show", site).json()

    assert answer["dimension"] == 2
    assert answer["layers"] == ["L1", "L2"]
    assert answer["parts"] == session.load(site).part_keys()
    assert answer["stages"] == []


def test_check_passes_a_model_that_can_be_meshed_and_staged(cli, site):
    ran = cli("check", site)

    assert ran.code == 0
    assert "ok" in ran.out.lower()


def test_check_refuses_a_model_with_nothing_to_mesh(cli, tmp_path):
    """A model with no soil layer and no solid validates, but meshes to 0 nodes: `check`
    says so before `export` writes an empty deck."""
    path = session.save(blank_project(), tmp_path / "empty.json")

    ran = cli("check", path)

    assert ran.code == 1
    assert "nothing to mesh" in ran.err and "layer add" in ran.err


def test_check_refuses_mesh_settings_for_a_part_the_model_does_not_have(cli, site):
    payload = json.loads(site.read_text(encoding="utf-8"))
    payload["mesh"]["body_sizes"] = {"removed_body": 1.25}
    site.write_text(json.dumps(payload), encoding="utf-8")

    ran = cli("check", site)

    assert ran.code == 1
    assert "mesh settings name objects this model does not have: removed_body" in ran.err


def test_check_refuses_stages_that_branch(cli, site):
    """The schema accepts a branching tree (an editor has to be able to hold one); a
    deck cannot run it, and `check` is where that is said."""
    payload = json.loads(site.read_text(encoding="utf-8"))
    payload["stages"] = [
        {"id": "initial", "name": "Initial stage"},
        {"id": "a", "name": "A", "parent": "initial"},
        {"id": "b", "name": "B", "parent": "initial"},
    ]
    site.write_text(json.dumps(payload), encoding="utf-8")

    ran = cli("check", site)

    assert ran.code == 1
    assert "'a'" in ran.err and "'b'" in ran.err


def test_check_refuses_flow_and_deformation_stages_mixed(cli, site):
    """The groundwater flow refusals of the export (`condition_checks.flow_refusal`),
    said before meshing, in the export's words."""
    payload = json.loads(site.read_text(encoding="utf-8"))
    payload["stages"] = [
        {"id": "initial", "name": "Initial stage", "calculation": "K0 procedure"},
        {"id": "flow", "name": "Flow", "parent": "initial",
         "calculation": "Groundwater flow"},
    ]
    site.write_text(json.dumps(payload), encoding="utf-8")

    ran = cli("check", site)

    assert ran.code == 1
    assert ("cannot mix groundwater flow stages ('Flow') with deformation stages "
            "('Initial stage')") in ran.err


def test_check_refuses_a_flow_stage_with_no_fixed_head(cli, site):
    payload = json.loads(site.read_text(encoding="utf-8"))
    payload["stages"] = [{"id": "flow", "name": "Flow", "calculation": "Groundwater flow"}]
    payload["boundary_conditions"] = []
    for material in payload["materials"]:
        material["variables"]["PERMEABILITY_XX"] = 1e-12
    site.write_text(json.dumps(payload), encoding="utf-8")

    ran = cli("check", site)

    assert ran.code == 1
    assert "in stage 'Flow' no fixed water pressure condition is on" in ran.err


# ── build ───────────────────────────────────────────────────────────────────

def test_build_writes_the_project_a_script_describes(cli, tmp_path):
    script = tmp_path / "model.py"
    script.write_text("from core.model.templates import seed_project\n"
                      "PROJECT = seed_project()\n", encoding="utf-8")

    ran = cli("build", script, "--out", tmp_path / "site.json")

    assert ran.code == 0, ran.err
    assert [layer.id for layer in session.load(tmp_path / "site.json").layers] == ["L1", "L2"]


# ── dimension, units, water ─────────────────────────────────────────────────

def test_dimension_switches_the_model_and_writes_it_back(cli, site):
    ran = cli("dimension", site, "3d")

    assert ran.code == 0, ran.err
    assert session.load(site).dimension == 3


def test_units_converts_the_project(cli, site):
    assert cli("units", site, "kN").code == 0

    assert session.load(site).unit_system == "kN"


def test_units_without_a_system_says_which_it_is(cli, site):
    ran = cli("units", site)

    assert ran.code == 0
    assert "SI" in ran.out


def test_water_sets_shows_and_removes_the_level(cli, site):
    assert cli("water", site, "-2").code == 0
    assert session.load(site).water.y == -2.0
    assert "-2.00" in cli("water", site).out

    assert cli("water", site, "off").code == 0
    assert session.load(site).water is None


def test_a_water_level_outside_the_model_is_refused(cli, site):
    before = site.read_bytes()

    ran = cli("water", site, "5")

    assert ran.code == 1
    assert "between" in ran.err
    assert site.read_bytes() == before


# ── Where an edit is written ───────────────────────────────────────────────

def test_dry_run_checks_an_edit_and_writes_nothing(cli, site):
    before = site.read_bytes()

    ran = cli("water", site, "-2", "--dry-run")

    assert ran.code == 0
    assert site.read_bytes() == before
    assert "not written" in ran.out


def test_out_writes_the_edited_model_elsewhere(cli, site, tmp_path):
    before = site.read_bytes()

    assert cli("water", site, "-2", "--out", tmp_path / "wet.json").code == 0

    assert site.read_bytes() == before
    assert session.load(tmp_path / "wet.json").water.y == -2.0


def test_a_script_is_not_edited_in_place(cli, tmp_path):
    script = tmp_path / "model.py"
    script.write_text("from core.model.templates import seed_project\n"
                      "PROJECT = seed_project()\n", encoding="utf-8")
    before = script.read_bytes()

    ran = cli("water", script, "-2")

    assert ran.code == 1
    assert "--out" in ran.err
    assert script.read_bytes() == before
    assert cli("water", script, "-2", "--out", tmp_path / "wet.json").code == 0


def test_an_edit_of_a_deck_s_stages_is_refused(cli, tmp_path):
    path = session.save(blank_project().model_copy(update={
        "deck": Deck(directory=str(tmp_path))}), tmp_path / "deck.json")
    before = path.read_bytes()

    ran = cli("stages", path, "defaults")

    assert ran.code == 1
    assert "Edit the deck" in ran.err
    assert path.read_bytes() == before


# ── The refusals around the edges ──────────────────────────────────────────

def test_a_water_level_that_is_not_a_number_is_refused(cli, site):
    ran = cli("water", site, "deep")

    assert ran.code == 1
    assert "'deep' is not a water level" in ran.err


def test_build_takes_only_a_model_script(cli, site, tmp_path):
    ran = cli("build", site, "--out", tmp_path / "copy.json")

    assert ran.code == 1
    assert "not a model script" in ran.err


def test_a_fault_in_this_program_is_raised_not_dressed_up_as_a_refusal(cli, site, monkeypatch):
    """Only the failures that are answers -- the model, a file or Kratos said no -- become
    `error:` lines. A bug keeps its traceback, or nobody would find it."""
    from cli.commands import project as commands

    def broken(_project):
        raise KeyError("a bug")

    monkeypatch.setattr(commands, "summary", broken)
    with pytest.raises(KeyError, match="a bug"):
        cli("show", site)
