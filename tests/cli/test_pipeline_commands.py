"""`mesh`, `stages`, `export`, `run`, `calculate`, `results`: from a project file to a
Kratos deck on disk, through Kratos, to the results it left.

The deck on disk is the hand-over point (plan sec 0): `export` writes it, `run` runs a
deck directory -- this project's or anyone's -- in a copy under the runs root (D11), and
`calculate` is the two in one. Kratos itself is stood in for here (`stand_in_kratos`);
`test_a_model_is_calculated_by_kratos` is the real thing, with `--run-kratos`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import session
from core.analysis import calculation
from core.kratos import deck_files
from core.model.schemas import Deck
from core.model.templates import blank_project

ROOT = Path(__file__).resolve().parents[2]


# ── mesh ────────────────────────────────────────────────────────────────────

def test_mesh_says_how_big_the_mesh_is(cli, site):
    ran = cli("--json", "mesh", site)

    assert ran.code == 0, ran.err
    stats = ran.json()["stats"]
    assert stats["nodes"] > 0 and stats["elements"] > 0
    assert "nodes" in cli("mesh", site).out


def test_mesh_settings_given_on_the_command_line_are_kept_in_the_project(cli, site):
    coarse = cli("--json", "mesh", site).json()["stats"]["elements"]

    fine = cli("--json", "mesh", site, "--size", "2.5").json()["stats"]["elements"]

    assert fine > coarse
    assert session.load(site).mesh.element_size == 2.5


def test_a_deck_is_not_meshed(cli, tmp_path):
    path = session.save(blank_project().model_copy(update={
        "deck": Deck(directory=str(tmp_path))}), tmp_path / "deck.json")

    ran = cli("mesh", path)

    assert ran.code == 1
    assert "not meshed here" in ran.err


def test_mesh_refuses_a_size_for_a_part_that_is_not_in_the_model(cli, site):
    payload = json.loads(site.read_text(encoding="utf-8"))
    payload["mesh"]["body_sizes"] = {"gone": 1.0}
    site.write_text(json.dumps(payload), encoding="utf-8")

    ran = cli("mesh", site)

    assert ran.code == 1
    assert "mesh settings name bodies this model does not have: gone" in ran.err


# ── stages ──────────────────────────────────────────────────────────────────

def test_stages_defaults_gives_the_initial_stage_and_the_null_step(cli, site):
    assert cli("stages", site, "defaults").code == 0

    stages = session.load(site).stages
    assert len(stages) == 2 and stages[1].parent == stages[0].id
    listed = cli("stages", site, "list").out
    assert all(stage.id in listed for stage in stages)


def test_stages_list_says_when_there_are_none(cli, site):
    ran = cli("stages", site, "list")

    assert ran.code == 0
    assert "no stages" in ran.out.lower()


# ── export ──────────────────────────────────────────────────────────────────

def test_export_writes_the_kratos_deck(cli, site, tmp_path):
    deck = tmp_path / "deck"

    ran = cli("export", site, "--out", deck)

    assert ran.code == 0, ran.err
    name = session.load(site).name
    mdpa = [p.name for p in deck.glob("*.mdpa")]
    assert len(mdpa) == 1 and mdpa[0].startswith(name.split()[0])
    assert (deck / deck_files.PARAMETERS_NAME).is_file()
    assert (deck / deck_files.MATERIALS_NAME).is_file()
    assert str(deck) in ran.out


def test_export_names_the_mesh_as_asked(cli, site, tmp_path):
    """D10: the deck is named after the project, and `--name` names it otherwise. The
    parameters ask Kratos for that same name."""
    deck = tmp_path / "deck"

    assert cli("export", site, "--out", deck, "--name", "mesh").code == 0

    assert (deck / "mesh.mdpa").is_file()
    parameters = (deck / deck_files.PARAMETERS_NAME).read_text(encoding="utf-8")
    assert '"input_filename": "mesh"' in parameters
    assert session.load(site).name != "mesh", "the project itself keeps its name"


def test_the_deck_is_the_one_the_gui_exports(cli, site, tmp_path):
    """One exporter: the deck written here is the deck `POST /api/export/mdpa` answers
    for the same project and the same mesh settings."""
    from fastapi.testclient import TestClient

    from backend.main import app

    project = session.load(site)
    with TestClient(app) as client:
        client.put("/api/project", json=project.model_dump(mode="json"))
        answer = client.post("/api/export/mdpa",
                             json=project.mesh.model_dump(mode="json")).json()
        client.post("/api/project/reset")

    assert cli("export", site, "--out", tmp_path / "deck").code == 0

    deck = tmp_path / "deck"
    assert (deck / f"{answer['deck_name']}.mdpa").read_bytes() == answer["mdpa"].encode()
    assert json.loads((deck / deck_files.PARAMETERS_NAME).read_text(encoding="utf-8")) \
        == json.loads(answer["project_parameters"])
    assert json.loads((deck / deck_files.MATERIALS_NAME).read_text(encoding="utf-8")) \
        == json.loads(answer["materials"])


def test_a_model_with_nothing_to_mesh_is_not_exported(cli, tmp_path):
    """A model with no soil meshes to 0 nodes; its deck would run and compute nothing,
    so nothing is written and the user is told what is missing."""
    path = session.save(blank_project(), tmp_path / "empty.json")

    ran = cli("export", path, "--out", tmp_path / "out")

    assert ran.code == 1
    assert "nothing to mesh" in ran.err and "layer add" in ran.err
    assert not (tmp_path / "out").exists()


def test_a_model_with_nothing_to_mesh_is_not_meshed(cli, tmp_path):
    path = session.save(blank_project(), tmp_path / "empty.json")

    ran = cli("mesh", path)

    assert ran.code == 1
    assert "nothing to mesh" in ran.err


def test_a_deck_is_not_exported(cli, tmp_path):
    path = session.save(blank_project().model_copy(update={
        "deck": Deck(directory=str(tmp_path))}), tmp_path / "deck.json")

    ran = cli("export", path, "--out", tmp_path / "out")

    assert ran.code == 1
    assert "not exported here" in ran.err


# ── run, calculate ──────────────────────────────────────────────────────────

def test_run_runs_a_deck_directory_in_a_copy_under_the_runs_root(
        cli, site, tmp_path, stand_in_kratos):
    stand_in_kratos()
    deck = tmp_path / "deck"
    cli("export", site, "--out", deck)
    before = sorted(p.name for p in deck.iterdir())

    ran = cli("--json", "run", deck)

    assert ran.code == 0, ran.err
    answer = ran.json()
    run = Path(answer["directory"])
    assert run.parent == calculation.runs_root()
    assert answer["run"] == run.name
    assert (run / deck_files.PARAMETERS_NAME).is_file()
    assert "stand_in.post.res" in answer["outputs"]
    assert sorted(p.name for p in deck.iterdir()) == before, "the deck is left as it was"


def test_run_takes_the_parameters_file_too(cli, site, tmp_path, stand_in_kratos):
    stand_in_kratos()
    cli("export", site, "--out", tmp_path / "deck")

    assert cli("run", tmp_path / "deck" / deck_files.PARAMETERS_NAME).code == 0


def test_run_can_put_the_run_somewhere_else(cli, site, tmp_path, stand_in_kratos):
    stand_in_kratos()
    cli("export", site, "--out", tmp_path / "deck")

    answer = cli("--json", "run", tmp_path / "deck", "--runs-dir", tmp_path / "elsewhere").json()

    assert Path(answer["directory"]).parent == tmp_path / "elsewhere"


def test_a_run_kratos_refuses_is_exit_1_with_what_kratos_said(
        cli, site, tmp_path, stand_in_kratos):
    stand_in_kratos("import sys; print('Error: no such sub model part'); sys.exit(1)")
    cli("export", site, "--out", tmp_path / "deck")

    ran = cli("run", tmp_path / "deck")

    assert ran.code == 1
    assert "no such sub model part" in ran.err


def test_a_directory_that_is_not_a_deck_is_refused(cli, tmp_path):
    (tmp_path / "empty").mkdir()

    ran = cli("run", tmp_path / "empty")

    assert ran.code == 1
    assert deck_files.PARAMETERS_NAME in ran.err


def test_calculate_exports_and_runs_in_one_step(cli, site, stand_in_kratos):
    stand_in_kratos()

    ran = cli("--json", "calculate", site)

    assert ran.code == 0, ran.err
    answer = ran.json()
    run = Path(answer["directory"])
    assert run.parent == calculation.runs_root()
    assert answer["stats"]["nodes"] > 0
    assert list(run.glob("*.mdpa"))


SLOW_RESIDUALS = (
    "import time\n"
    "print('[kratos-gui] stage begin 1/1 1_Flow', flush=True)\n"
    "print('GeoMechanics Analysis: Analysis -START-', flush=True)\n"
    "for n in range(3):\n"
    "    print(f'RESIDUAL CRITERION:  :: [ Obtained ratio = {10.0 ** -n:g}; Expected ratio"
    " = 0.01; Absolute norm = 1; Expected norm =  1e-09]', flush=True)\n"
    "    time.sleep(0.4)\n"
    "print('RESIDUAL CRITERION: Convergence is achieved', flush=True)\n"
    "print('[kratos-gui] stage end 1/1 1_Flow', flush=True)\n")
"""A stand-in that prints three residuals, 0.4 s apart, in one stage."""


def test_follow_prints_each_iteration_on_stderr_and_keeps_stdout_the_answer(
        cli, site, stand_in_kratos):
    stand_in_kratos(SLOW_RESIDUALS)

    ran = cli("--json", "calculate", site, "--follow")

    assert ran.code == 0, ran.err
    assert ran.json()["ok"] is True, "stdout is the JSON answer alone"
    lines = [line.strip() for line in ran.err.splitlines()]
    assert lines[0] == "stage 1 of 1: Flow"
    assert [line.split(":")[0] for line in lines[1:4]] == [
        "iteration 1", "iteration 2", "iteration 3"]
    assert lines[3].endswith("met")
    assert len(lines) == 4, "each line once"


def test_without_follow_nothing_is_printed_during_the_run(cli, site, stand_in_kratos):
    stand_in_kratos(SLOW_RESIDUALS)

    ran = cli("--json", "calculate", site)

    assert "iteration" not in ran.err


# ── results ─────────────────────────────────────────────────────────────────

def test_results_lists_the_runs_newest_first(cli, site, stand_in_kratos):
    stand_in_kratos()
    first = cli("--json", "calculate", site).json()["run"]
    second = cli("--json", "calculate", site).json()["run"]

    runs = cli("--json", "results", "runs").json()

    assert [run["id"] for run in runs] == [second, first]
    assert first in cli("results", "runs").out


def test_results_shows_a_run_by_id_or_by_its_number_in_the_listing(cli, site,
                                                                   stand_in_kratos):
    stand_in_kratos()
    run = cli("--json", "calculate", site).json()["run"]

    by_id = cli("--json", "results", "show", run).json()
    by_number = cli("--json", "results", "show", "1").json()

    assert by_id["id"] == by_number["id"] == run
    assert by_id["stages"] == by_number["stages"]
    assert run in cli("results", "show", run).out


def test_results_of_a_run_that_is_not_there_is_refused(cli):
    ran = cli("results", "show", "7")

    assert ran.code == 1
    assert "no run 7" in ran.err.lower()


# ── The real thing ──────────────────────────────────────────────────────────

@pytest.mark.kratos
def test_a_model_is_calculated_by_kratos(cli):
    """The test model (tests/models/excavation.py), from its script to Kratos' results,
    without the GUI: what the command line is for."""
    from tests.results_run import require_kratos

    require_kratos()
    script = ROOT / "tests" / "models" / "excavation.py"

    ran = cli("--json", "calculate", script)

    assert ran.code == 0, ran.err
    shown = cli("--json", "results", "show", ran.json()["run"]).json()
    assert shown["complete"], shown["stages"]


# ── Around the edges ────────────────────────────────────────────────────────

def test_mesh_order_is_kept_in_the_project(cli, site):
    assert cli("mesh", site, "--order", "1").code == 0

    assert session.load(site).mesh.order == 1


def test_a_deck_that_is_not_there_is_refused(cli, tmp_path):
    ran = cli("run", tmp_path / "nowhere")

    assert ran.code == 1
    assert "no such deck" in ran.err


def test_calculate_runs_a_deck_project_as_the_files_it_is(cli, site, tmp_path,
                                                          stand_in_kratos):
    """A project that is a deck (a script naming a finished deck) is not exported: its
    own files are what is run, as the GUI's Calculate runs them."""
    stand_in_kratos()
    cli("export", site, "--out", tmp_path / "deck")
    path = session.save(blank_project().model_copy(update={
        "deck": Deck(directory=str(tmp_path / "deck"))}), tmp_path / "deck.json")

    ran = cli("--json", "calculate", path)

    assert ran.code == 0, ran.err
    assert (Path(ran.json()["directory"]) / deck_files.PARAMETERS_NAME).is_file()


def test_results_says_when_there_are_no_runs(cli):
    ran = cli("results", "runs")

    assert ran.code == 0
    assert "No runs yet" in ran.out
    assert cli("--json", "results", "runs").json() == []
