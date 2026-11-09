"""`results`: what a run left behind, read in the terminal (plan/active/cli-plan.md M5).

Every answer is `core.results.catalog`'s, which the GUI's Results mode reads through
`/api/results/...`, so `--json` here is held equal to what those routes answer for the
same run. The run is the test model through the fake Kratos (`tests/results_run.py`):
seven stages, a wall and its interface, analytic fields, on any machine.
"""

from __future__ import annotations

import shutil
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from core.analysis import calculation
from tests import results_run


@pytest.fixture
def run(monkeypatch):
    """The fake run's id, with the runs root pointed at it."""
    return results_run.use(monkeypatch, results_run.fake_run())


@pytest.fixture
def client(run):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def copied(run, tmp_path):
    """The same run copied out of the runs root, under a name that is not a run's."""
    root, _ = results_run.fake_run()
    return shutil.copytree(root / run, tmp_path / "from the cluster")


def _route(client, path):
    answer = client.get(f"/api/results/runs/{path}")
    assert answer.status_code == 200, answer.text
    return answer.json()


# ── Same numbers as the routes ──────────────────────────────────────────────

def test_stages_are_the_run_s_stages(cli, client, run):
    ran = cli("--json", "results", "stages", run)

    assert ran.code == 0, ran.err
    assert ran.json() == _route(client, run)["stages"]
    assert "Third excavation" in cli("results", "stages", run).out


def test_fields_are_the_stage_s_field_menu(cli, client, run):
    assert (cli("--json", "results", "fields", run, "--stage", "4").json()
            == _route(client, f"{run}/stages/4/fields"))


def test_a_field_is_the_route_s_field(cli, client, run):
    ran = cli("--json", "results", "field", run, "syy", "--stage", "5",
              "--location", "elements")

    assert ran.code == 0, ran.err
    assert ran.json() == _route(client, f"{run}/stages/5/field/syy?location=elements")


def test_at_is_every_field_at_one_node(cli, client, run):
    assert (cli("--json", "results", "at", run, "12", "--stage", "6").json()
            == _route(client, f"{run}/stages/6/at/12"))


def test_members_are_what_the_run_wrote_curves_for(cli, client, run):
    assert cli("--json", "results", "members", run).json() == _route(client, f"{run}/members")
    assert "wall" in cli("results", "members", run).out


def test_a_long_member_name_keeps_its_own_column(cli, run, monkeypatch):
    """A wall without a pit has a member per face, `interface_left`, longer than the
    name column was: it ran into the stages."""
    from core.results import catalog

    quantities = [{"name": "tn"}, {"name": "ts"}]
    monkeypatch.setattr(catalog, "stage_members", lambda _: {"members": [
        {"name": "interface_right", "stages": [3, 4], "quantities": quantities},
        {"name": "wall", "stages": [3, 4], "quantities": [{"name": "M"}]}]})
    lines = cli("results", "members", run).out.splitlines()[1:3]

    assert [line.index("stages") for line in lines] == [len("  interface_right  ")] * 2


def test_a_profile_is_the_plot_route_s_curves(cli, client, run):
    ran = cli("--json", "results", "profile", run, "wall", "M")

    assert ran.code == 0, ran.err
    assert ran.json() == _route(client, f"{run}/members/wall/M")


# ── Choosing a stage ────────────────────────────────────────────────────────

def test_without_a_stage_the_last_one_with_results_is_read(cli, run):
    last = cli("--json", "results", "field", run, "uy").json()

    assert last == cli("--json", "results", "field", run, "uy", "--stage", "7").json()
    assert "stage 7" in cli("results", "field", run, "uy").out


def test_a_stage_can_be_named_by_its_stage(cli, run):
    by_name = cli("--json", "results", "fields", run, "--stage", "first excavation").json()

    assert by_name["stage"]["index"] == 4


def test_a_stage_that_is_not_there_is_refused_with_the_stages(cli, run):
    ran = cli("results", "fields", run, "--stage", "dewatering")

    assert ran.code == 1
    assert "no stage matches 'dewatering'" in ran.err and "Third excavation" in ran.err


# ── What a person reads ─────────────────────────────────────────────────────

def test_a_field_says_its_range_and_where_it_is_reached(cli, run):
    ran = cli("results", "field", run, "uy", "--stage", "7")

    assert ran.code == 0, ran.err
    assert ran.out.startswith("u_y (m), stage 7 (Third excavation): ")
    assert "min" in ran.out and "max" in ran.out and "at node" in ran.out


def test_a_field_the_stage_does_not_carry_is_refused(cli, run):
    ran = cli("results", "field", run, "temperature")

    assert ran.code == 1
    assert "no field called 'temperature'" in ran.err


def test_at_lists_the_fields_group_by_group(cli, run):
    ran = cli("results", "at", run, "12")

    assert ran.code == 0, ran.err
    assert ran.out.startswith("Node 12 at (") and "Deformations" in ran.out


def test_a_node_the_stage_does_not_have_is_refused(cli, run):
    ran = cli("results", "at", run, "999999")

    assert ran.code == 1
    assert "no node 999999" in ran.err


def test_a_profile_says_each_stage_s_extremes(cli, run):
    ran = cli("results", "profile", run, "wall", "M")

    assert ran.code == 0, ran.err
    assert "Bending moment" in ran.out and "Third excavation" in ran.out
    assert ran.out.count("min ") == 5


def test_a_profile_takes_a_quantity_by_a_word_of_its_label(cli, run):
    by_word = cli("--json", "results", "profile", run, "interface", "normal").json()

    assert by_word["quantity"] == "tn"


def test_a_profile_without_a_quantity_is_the_bending_moment(cli, run):
    assert cli("--json", "results", "profile", run, "wall").json()["quantity"] == "M"


def test_a_profile_can_be_narrowed_to_one_stage(cli, run):
    one = cli("--json", "results", "profile", run, "wall", "M", "--stage", "4").json()

    assert [stage["index"] for stage in one["stages"]] == [4]


def test_a_profile_refuses_a_stage_without_member_output(cli, run):
    from core.results import catalog

    members = catalog.stage_members(run)["members"]
    wall = next(member for member in members if member["name"] == "wall")
    stages = catalog.describe(run)["stages"]
    index = next(stage["index"] for stage in stages
                 if stage["index"] not in wall["stages"])

    ran = cli("results", "profile", run, "wall", "M", "--stage", str(index))

    assert ran.code == 1
    assert "has no output in stage" in ran.err
    assert "it has stages" in ran.err


def test_a_member_the_run_has_no_output_for_is_refused_with_the_ones_it_has(cli, run):
    ran = cli("results", "profile", run, "strut", "N")

    assert ran.code == 1
    assert "strut" in ran.err and "interface, wall" in ran.err


def test_a_quantity_the_member_does_not_carry_is_refused(cli, run):
    ran = cli("results", "profile", run, "wall", "tn")

    assert ran.code == 1
    assert "no 'tn'" in ran.err and "M, Q, N" in ran.err


def test_files_lists_the_run_s_files_with_their_sizes(cli, run):
    ran = cli("results", "files", run)

    assert ran.code == 0, ran.err
    assert "ProjectParameters.json" in ran.out and "KB" in ran.out


def test_files_keeps_a_long_name_apart_from_its_size(cli, run):
    """The sizes line up after the longest name, however long a deck's stage names are."""
    import re

    rows = cli("results", "files", run).out.splitlines()[1:-1]

    found = [re.fullmatch(r"  \S+ {2,}(\S+ \S+)", row) for row in rows]
    assert rows and all(found), [row for row, match in zip(rows, found) if not match]
    assert len({match.start(1) for match in found}) == 1


# ── CSV ─────────────────────────────────────────────────────────────────────

def test_a_field_as_csv_is_the_gui_s_csv(cli, run):
    """The file the GUI's `results csv` saves (`ResultsRender.csv`): id and value, with
    the run and the stage in the header."""
    field = cli("--json", "results", "field", run, "uy", "--stage", "7").json()

    ran = cli("results", "field", run, "uy", "--stage", "7", "--csv")

    assert ran.code == 0, ran.err
    lines = ran.out.splitlines()
    assert lines[0] == f"node,uy [m],# {run} / Third excavation"
    assert len(lines) == 1 + len(field["ids"])
    first = lines[1].split(",")
    assert int(first[0]) == field["ids"][0] and float(first[1]) == field["values"][0]


def test_a_profile_as_csv_is_the_gui_s_plot_csv(cli, run):
    """The file the plot window's `results plot csv` saves (`ResultsPlot.csv`)."""
    plot = cli("--json", "results", "profile", run, "wall", "M").json()

    ran = cli("results", "profile", run, "wall", "M", "--csv")

    assert ran.code == 0, ran.err
    lines = ran.out.splitlines()
    assert lines[0] == "stage,name,node,y [m],M [N·m/m]"
    assert len(lines) == 1 + sum(len(stage["points"]) for stage in plot["stages"])
    stage = plot["stages"][0]
    index, name, node, y, value = lines[1].split(",")
    assert (int(index), name, int(node), [float(value), float(y)]) == (
        stage["index"], stage["stage"], stage["nodes"][0], stage["points"][0])


def test_csv_and_json_together_are_a_usage_error(cli, run):
    assert cli("--json", "results", "field", run, "uy", "--csv").code == 2


# ── Files out of a run ──────────────────────────────────────────────────────

def test_get_copies_one_file_of_the_run(cli, run, tmp_path):
    ran = cli("results", "get", run, "ProjectParameters.json", "--out", tmp_path)

    assert ran.code == 0, ran.err
    root, _ = results_run.fake_run()
    assert ((tmp_path / "ProjectParameters.json").read_bytes()
            == (root / run / "ProjectParameters.json").read_bytes())


def test_get_into_a_folder_that_is_not_there_yet_makes_it(cli, run, tmp_path):
    """`--out logs/`: a path that ends in a separator is a folder, made if need be --
    not a file called `logs`."""
    for name, separator in (("logs", "/"), ("more", "\\")):
        ran = cli("results", "get", run, "kratos.log", "--out", f"{tmp_path / name}{separator}")

        assert ran.code == 0, ran.err
        assert (tmp_path / name / "kratos.log").is_file()


def test_get_does_not_overwrite_a_file_unless_told_to(cli, run, tmp_path):
    (tmp_path / "kratos.log").write_text("mine", encoding="utf-8")

    refused = cli("results", "get", run, "kratos.log", "--out", tmp_path / "kratos.log")
    assert refused.code == 1 and "--force" in refused.err
    assert (tmp_path / "kratos.log").read_text(encoding="utf-8") == "mine"

    assert cli("results", "get", run, "kratos.log", "--out", tmp_path, "--force").code == 0
    assert (tmp_path / "kratos.log").read_text(encoding="utf-8") != "mine"


def test_get_refuses_a_name_that_leaves_the_run(cli, run, tmp_path):
    ran = cli("results", "get", run, "../secret.txt", "--out", tmp_path)

    assert ran.code == 1
    assert "not a file in this run" in ran.err


def test_archive_zips_the_whole_run(cli, run, tmp_path):
    ran = cli("results", "archive", run, "--out", tmp_path)

    assert ran.code == 0, ran.err
    root, _ = results_run.fake_run()
    with zipfile.ZipFile(tmp_path / f"{run}.zip") as archive:
        assert sorted(archive.namelist()) == sorted(
            path.name for path in (root / run).iterdir() if path.is_file())


# ── A run anywhere (D12) ────────────────────────────────────────────────────

def test_a_run_outside_the_runs_root_is_read_by_its_path(cli, run, copied):
    assert cli("results", "show", copied).code == 0
    assert (cli("--json", "results", "field", copied, "uy").json()
            == cli("--json", "results", "field", run, "uy").json())
    assert (cli("--json", "results", "profile", copied, "wall", "M").json()
            == cli("--json", "results", "profile", run, "wall", "M").json())


def test_a_run_by_path_is_named_by_its_folder_and_deck(cli, copied):
    shown = cli("--json", "results", "show", copied).json()

    assert (shown["id"], shown["deck"], shown["started"]) == (
        "from the cluster", "Staged_excavation", None)


def test_a_run_by_its_number_in_the_listing(cli, run):
    assert (cli("--json", "results", "fields", "1").json()
            == cli("--json", "results", "fields", run).json())


def test_a_folder_that_is_not_a_run_is_refused(cli, tmp_path):
    (tmp_path / "empty").mkdir()

    ran = cli("results", "fields", tmp_path / "empty")

    assert ran.code == 1
    assert "wrote no results" in ran.err


def test_a_run_that_is_neither_a_folder_nor_a_run_id_is_refused(cli, run):
    ran = cli("results", "show", "nowhere")

    assert ran.code == 1
    assert "'nowhere' is not a run" in ran.err


@pytest.mark.kratos
def test_results_of_a_real_run_are_read_by_path(cli, tmp_path):
    """Kratos' own output of the test model, copied out of its runs root and read."""
    root, run_id = results_run.real_run()
    copied = shutil.copytree(root / run_id, tmp_path / "real")

    profile = cli("--json", "results", "profile", copied, "wall", "M")
    assert profile.code == 0, profile.err
    assert len(profile.json()["stages"]) == 5
    at = cli("--json", "results", "at", copied, "1")
    assert at.code == 0, at.err


@pytest.mark.parametrize("command", ["fields", "stages", "files", "members"])
def test_a_run_root_given_on_the_command_line_is_used(cli, run, command, monkeypatch):
    root, _ = results_run.fake_run()
    monkeypatch.setenv(calculation.RUNS_ENV, "nowhere at all")

    assert cli("results", command, run, "--runs-dir", root).code == 0


def test_csv_can_go_into_a_file_as_utf8(cli, run, tmp_path):
    """Not through a redirect, which Windows PowerShell 5.1 writes as UTF-16."""
    on_stdout = cli("results", "profile", run, "wall", "M", "--csv").out

    ran = cli("results", "profile", run, "wall", "M", "--csv", tmp_path / "wall_M.csv")

    assert ran.code == 0, ran.err
    assert "wall_M.csv" in ran.out
    written = (tmp_path / "wall_M.csv").read_bytes()
    assert written.decode("utf-8") == on_stdout and b"\r\n" not in written
