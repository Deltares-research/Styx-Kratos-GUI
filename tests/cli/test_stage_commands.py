"""`phases`, `node`, `deck show`: the construction sequence built in the terminal, and the
deck looked into (plan/active/cli-plan.md M4).

Each phase edit is the list transform the GUI's Phases toolbar makes (`core.model.phases`,
held to `App.Phases` by tests/test_phase_parity.py), stored the way
`PATCH /api/project/phases` stores it. The acceptance test at the bottom types the
staged sequence of `tests/models/excavation.py` and checks it is the one that script
derives.
"""

from __future__ import annotations

import pytest

from core import session
from tests.models import excavation


@pytest.fixture
def pit(tmp_path):
    """The test model with its seven phases."""
    return session.save(excavation.excavation_project(), tmp_path / "pit.json")


@pytest.fixture
def unstaged(tmp_path):
    return session.save(excavation.excavation_project(staged=False), tmp_path / "pit.json")


def _phase(path, id):
    return next(phase for phase in session.load(path).phases if phase.id == id)


# ── phases ──────────────────────────────────────────────────────────────────

def test_phases_with_no_action_lists_them(cli, pit):
    ran = cli("phases", pit)

    assert ran.code == 0
    assert "install_strut" in ran.out and "dig_3" in ran.out


def test_staged_excavation_derives_the_whole_sequence(cli, unstaged):
    ran = cli("phases", unstaged, "staged-excavation")

    assert ran.code == 0, ran.err
    assert session.load(unstaged).phases == excavation.excavation_project().phases


def test_add_puts_a_phase_at_the_end_with_its_settings_and_parts(cli, pit):
    ran = cli("phases", pit, "add", "unload", "--name", "Unload", "--calculation",
              "plastic", "--deactivate", "surcharge", "--max-iterations", "60",
              "--tolerance", "1e-3")

    assert ran.code == 0, ran.err
    unload = _phase(pit, "unload")
    assert (unload.parent, unload.name, unload.deactivate, unload.max_iterations,
            unload.tolerated_error) == ("dig_3", "Unload", ["surcharge"], 60, 1e-3)


def test_add_before_inserts_a_phase_into_the_chain(cli, pit):
    assert cli("phases", pit, "add", "prep", "--before", "dig_1").code == 0

    assert (_phase(pit, "prep").parent, _phase(pit, "dig_1").parent) == (
        "install_sheetpile", "prep")


def test_copy_repeats_a_phase_s_solver_settings(cli, pit):
    ran = cli("phases", pit, "copy", "install_sheetpile", "--id", "again")

    assert ran.code == 0, ran.err
    again = _phase(pit, "again")
    assert (again.parent, again.reset_displacements, again.activate) == (
        "install_sheetpile", True, [])


def test_set_changes_a_phase_s_fields(cli, pit):
    assert cli("phases", pit, "set", "dig_1", "--name", "Dig to -2", "--keep-displacements",
               "--time-interval", "2").code == 0

    dig = _phase(pit, "dig_1")
    assert (dig.name, dig.reset_displacements, dig.time_interval) == ("Dig to -2", False, 2.0)


def test_activate_and_deactivate_switch_parts_from_a_phase_on(cli, pit):
    assert cli("phases", pit, "activate", "dig_1", "strut").code == 0
    assert _phase(pit, "dig_1").activate == ["water_1", "strut"]

    assert cli("phases", pit, "deactivate", "dig_1", "strut").code == 0
    assert _phase(pit, "dig_1").activate == ["water_1"]


def test_a_part_the_model_does_not_have_is_refused(cli, pit):
    ran = cli("phases", pit, "activate", "dig_1", "stru")

    assert ran.code == 1
    assert "no part 'stru'" in ran.err and "kratos-cli parts" in ran.err


def test_remove_heals_the_chain(cli, pit):
    assert cli("phases", pit, "remove", "install_strut").code == 0

    assert _phase(pit, "dig_2").parent == "dig_1"


def test_show_says_what_is_in_the_model_during_a_phase(cli, pit):
    ran = cli("phases", pit, "show", "dig_1")

    assert ran.code == 0
    assert "soil_L_top__lift1" not in ran.out.split("in the model:")[1].split("\n")[0]
    assert "sheetpile" in ran.out and "water_1" in ran.out
    data = cli("--json", "phases", pit, "show", "dig_1").json()
    assert "strut" not in data["active"] and "sheetpile" in data["active"]


def test_a_phase_that_is_not_there_is_named(cli, pit):
    ran = cli("phases", pit, "set", "dig_9", "--name", "x")

    assert ran.code == 1
    assert "no phase 'dig_9'" in ran.err


def test_a_calculation_type_that_is_not_one_is_refused(cli, pit):
    ran = cli("phases", pit, "set", "dig_1", "--calculation", "elastic")

    assert ran.code == 2
    assert "use k0, plastic, null or flow" in ran.err


@pytest.mark.parametrize("word", ["flow", "Groundwater flow", "groundwater-flow"])
def test_flow_is_the_groundwater_flow_calculation(cli, pit, word):
    """The GUI's "Groundwater flow" in the Calculation type select."""
    assert cli("phases", pit, "add", "seep", "--calculation", word).code == 0

    assert _phase(pit, "seep").calculation == "Groundwater flow"
    assert "calculation: Groundwater flow" in cli("phases", pit).out


def test_a_flow_phase_lists_no_displacement_reset(cli, pit):
    """A phase reset before it became a flow phase keeps the value, greyed out in the
    GUI, and the lists leave it out: a flow phase has no displacements."""
    assert cli("phases", pit, "set", "install_sheetpile", "--calculation", "flow").code == 0

    assert _phase(pit, "install_sheetpile").reset_displacements
    assert "displacements reset" not in cli("phases", pit, "show", "install_sheetpile").out


@pytest.mark.parametrize("option", ["--reset-displacements", "--keep-displacements"])
def test_a_flow_phase_refuses_the_displacement_options(cli, pit, option):
    before = pit.read_text(encoding="utf-8")

    ran = cli("phases", pit, "set", "dig_1", "--calculation", "flow", option)

    assert ran.code == 1
    assert "groundwater flow phase" in ran.err and option in ran.err
    assert pit.read_text(encoding="utf-8") == before
    assert cli("phases", pit, "add", "seep", "--calculation", "flow", option).code == 1


# ── node, deck show ─────────────────────────────────────────────────────────

@pytest.fixture
def deck(cli, pit, tmp_path):
    """The test model's deck, written once per test."""
    assert cli("export", pit, "--out", tmp_path / "deck").code == 0
    return tmp_path / "deck"


def test_node_names_the_parts_a_node_is_in(cli, deck):
    ran = cli("--json", "node", deck, "1")

    assert ran.code == 0, ran.err
    answer = ran.json()[0]
    assert answer["node"] == 1 and len(answer["at"]) == 3 and answer["parts"]


def test_node_of_a_project_reads_the_deck_it_would_export(cli, pit, deck):
    from_project = cli("--json", "node", pit, "1").json()
    from_deck = cli("--json", "node", deck, "1").json()

    assert from_project == from_deck


def test_a_node_split_by_an_interface_names_its_twins(cli, deck):
    nodes = cli("--json", "node", deck, *map(str, range(1, 400))).json()

    split = [answer for answer in nodes if answer["same_position"]]
    assert split, "the wall's interfaces split its nodes"
    twin = split[0]["same_position"][0]
    assert twin["parts"] != split[0]["parts"]


def test_a_node_the_deck_does_not_have_is_refused(cli, deck):
    ran = cli("node", deck, "999999")

    assert ran.code == 1
    assert "not in this deck" in ran.err


def test_deck_show_summarises_the_mesh_and_the_stages(cli, deck):
    ran = cli("deck", "show", deck)

    assert ran.code == 0, ran.err
    assert "nodes" in ran.out and "SheetPileWall" in ran.out
    assert "7 stages" in ran.out and "Third_excavation" in ran.out
    data = cli("--json", "deck", "show", deck).json()
    assert data["dimension"] == 2 and data["nodes"] > 0
    assert any(part["name"] == "SheetPileWall" for part in data["parts"])


def test_deck_show_reads_an_mdpa_on_its_own(cli, deck):
    mdpa = next(deck.glob("*.mdpa"))

    ran = cli("--json", "deck", "show", mdpa)

    assert ran.code == 0 and ran.json()["stages"] == []


# ── The stages of the test model, from commands alone ───────────────────────

def test_the_stages_of_the_test_model_are_built_with_commands_alone(cli, unstaged):
    """The seven phases `phases.staged_excavation_phases` derives for the test model --
    settle, the wall with its contact and the surcharge, three lifts each with its water
    load, the strut after the first -- typed one by one."""
    def run(*argv):
        ran = cli(*argv)
        assert ran.code == 0, (argv, ran.err)

    p = unstaged
    run("phases", p, "defaults")
    run("phases", p, "deactivate", "initial", "sheetpile", "strut", "wall_contact",
        "surcharge", "water_1", "water_2", "water_3")
    solver = ("--max-iterations", "150", "--tolerance", "1e-3")
    run("phases", p, "add", "install_sheetpile", "--name", "SheetPileWall installation",
        "--activate", "sheetpile", "wall_contact", "surcharge", "--reset-displacements",
        *solver)
    run("phases", p, "add", "dig_1", "--name", "First excavation", "--activate", "water_1",
        "--deactivate", "soil_L_top__lift1", *solver)
    run("phases", p, "add", "install_strut", "--name", "Strut installation",
        "--activate", "strut", *solver)
    run("phases", p, "add", "dig_2", "--name", "Second excavation", "--activate", "water_2",
        "--deactivate", "soil_L_top__lift2", "water_1", *solver)
    run("phases", p, "add", "dig_3", "--name", "Third excavation", "--activate", "water_3",
        "--deactivate", "soil_L_top__lift3", "water_2", *solver)

    assert session.load(p).phases == excavation.excavation_project().phases
