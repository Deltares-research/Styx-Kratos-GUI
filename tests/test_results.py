"""The runs registry: finding what a calculation left behind, and handing it back.

No Kratos and no parsing here. `core.results.catalog` in this milestone only *finds* things --
which runs exist, which stages each one got through, and which files are in it -- and
serves a named file out of a run directory. Reading the results themselves is P1.

Every case below builds its run directory by hand rather than calculating one, because
the point of the module is that it can describe a directory nobody in this process made:
runs outlive the server that wrote them, and the oldest one on a machine was written by
a version of this code that no longer exists.
"""

import json
import shutil
import zipfile

import pytest
from fastapi.testclient import TestClient

from core.analysis import calculation
from core.kratos import deck_files
from core.results import catalog
from backend.main import app


EXECUTION = ["1_Initial_stage", "2_Excavation", "3_Strut"]


def parameters(deck: str, stages: list[str]) -> str:
    """A `ProjectParameters.json` with just the parts the registry reads.

    `problem_name` is what makes the join to the output files exact: it is the base
    name the GiD writer was given, so the registry never has to rebuild a filename.
    """
    return json.dumps({
        "orchestrator": {
            "name": "Orchestrators.KratosMultiphysics.SequentialOrchestrator",
            "settings": {"execution_list": list(stages)},
        },
        "stages": {
            name: {"stage_settings": {"problem_data": {"problem_name": f"{deck}_{name}"}}}
            for name in stages
        },
    })


def make_run(root, name: str, deck: str = "Test_model",
             stages: list[str] | None = None, through: int | None = None,
             log: str | None = None):
    """A run directory as `core.analysis.calculation` would have left it.

    `through` is how many stages wrote their pair of output files -- `None` for all of
    them, which is what a run that finished looks like.
    """
    stages = EXECUTION if stages is None else stages
    directory = root / name
    directory.mkdir(parents=True)
    (directory / f"{deck}.mdpa").write_text("Begin Properties 0\nEnd Properties\n",
                                            encoding="utf-8")
    (directory / calculation.PARAMETERS_NAME).write_text(parameters(deck, stages),
                                                       encoding="utf-8")
    (directory / calculation.MATERIALS_NAME).write_text('{"properties": []}',
                                                      encoding="utf-8")
    for index, stage in enumerate(stages[:len(stages) if through is None else through]):
        (directory / f"{deck}_{stage}.post.msh").write_text("MESH\n", encoding="utf-8")
        (directory / f"{deck}_{stage}.post.res").write_text("GiD Post Results File 1.2\n",
                                                            encoding="utf-8")
    if log is not None:
        (directory / calculation.LOG_NAME).write_text(log, encoding="utf-8")
    return directory


def finished_log(stages: list[str] | None = None) -> str:
    stages = EXECUTION if stages is None else stages
    lines = []
    for index, stage in enumerate(stages, start=1):
        lines.append(f"{calculation.STAGE_MARKER} begin {index}/{len(stages)} {stage}")
        lines.append(f"{calculation.STAGE_MARKER} end {index}/{len(stages)} {stage}")
    return "\n".join(lines) + "\n"


def failed_log(at: int, stages: list[str] | None = None) -> str:
    """A log that reaches stage `at` (1-based) and dies in it."""
    stages = EXECUTION if stages is None else stages
    lines = []
    for index, stage in enumerate(stages[:at], start=1):
        lines.append(f"{calculation.STAGE_MARKER} begin {index}/{len(stages)} {stage}")
        if index < at:
            lines.append(f"{calculation.STAGE_MARKER} end {index}/{len(stages)} {stage}")
    lines.append("Error: the solver did not converge")
    return "\n".join(lines) + "\n"


@pytest.fixture
def runs_root(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setenv(calculation.RUNS_ENV, str(root))
    return root


@pytest.fixture
def client(runs_root):
    # Not module-scoped: every case needs the runs root this case's fixture made, and
    # `runs_root()` is read per request, so the client may not outlive it.
    with TestClient(app) as c:
        yield c


# ── Finding runs ────────────────────────────────────────────────────────────

def test_an_absent_runs_root_is_no_runs_rather_than_an_error(tmp_path, monkeypatch):
    """A machine that has never calculated has no runs directory at all. That is the
    normal state of a fresh checkout, not something to report as broken."""
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "never-calculated"))

    assert catalog.runs() == []


def test_runs_are_listed_newest_first(runs_root):
    make_run(runs_root, "Test_model_2026-09-20_10-00")
    make_run(runs_root, "Test_model_2026-09-22_00-49")
    make_run(runs_root, "Test_model_2026-09-21_18-56")

    assert [run["id"] for run in catalog.runs()] == [
        "Test_model_2026-09-22_00-49",
        "Test_model_2026-09-21_18-56",
        "Test_model_2026-09-20_10-00",
    ]


def test_a_run_is_named_by_its_deck_and_when_it_started(runs_root):
    make_run(runs_root, "Staged_excavation_2026-09-22_00-49", deck="Staged_excavation")

    run = catalog.runs()[0]

    assert run["deck"] == "Staged_excavation"
    assert run["started"] == "2026-09-22T00:49"


def test_the_second_run_of_one_minute_keeps_its_suffix_out_of_the_deck_name(runs_root):
    """`calculation.new_run_directory` appends `_2` to the second run inside one minute.
    That suffix belongs to the directory, not to the deck."""
    make_run(runs_root, "Test_model_2026-09-22_00-49_2")

    run = catalog.runs()[0]

    assert run["deck"] == "Test_model"
    assert run["started"] == "2026-09-22T00:49"
    assert run["id"] == "Test_model_2026-09-22_00-49_2"


def test_the_listing_says_how_far_each_run_got_without_opening_anything(runs_root):
    """A count of result files, not `complete`: the listing is meant to stay cheap,
    and knowing whether that is *all* the stages means parsing the deck. One run at a
    time can afford that; a listing of a hundred cannot."""
    make_run(runs_root, "Test_model_2026-09-22_00-49", through=1)
    make_run(runs_root, "Test_model_2026-09-22_00-50")

    assert [run["results"] for run in catalog.runs()] == [3, 1]


def test_a_directory_that_is_not_a_run_is_ignored(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49")
    (runs_root / "notes.txt").write_text("hello", encoding="utf-8")
    (runs_root / "scratch").mkdir()

    assert [run["id"] for run in catalog.runs()] == ["Test_model_2026-09-22_00-49"]


# ── Stages ──────────────────────────────────────────────────────────────────

def test_stages_come_from_the_execution_list_in_order(runs_root):
    """Not from a directory listing: the files sort lexically, so a ten-stage deck
    would put stage 10 between 1 and 2. The execution list is already in run order."""
    stages = [f"{n}_Stage" for n in range(1, 12)]
    make_run(runs_root, "Test_model_2026-09-22_00-49", stages=stages)

    names = [stage["name"] for stage in catalog.describe("Test_model_2026-09-22_00-49")["stages"]]

    assert names == stages
    assert names[9] == "10_Stage"


def test_a_stage_reports_the_output_files_it_actually_wrote(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49", through=2)

    stages = catalog.describe("Test_model_2026-09-22_00-49")["stages"]

    assert [stage["results"] for stage in stages] == [True, True, False]
    assert stages[0]["mesh_file"] == "Test_model_1_Initial_stage.post.msh"
    assert stages[0]["results_file"] == "Test_model_1_Initial_stage.post.res"
    assert stages[2]["results_file"] is None


def test_a_run_whose_every_stage_wrote_results_is_complete(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49", log=finished_log())

    run = catalog.describe("Test_model_2026-09-22_00-49")

    assert run["complete"] is True
    assert run["failed_at"] is None


def test_a_run_that_died_names_the_stage_it_died_in(runs_root):
    """The same marker parsing the command log already does, applied to a log on disk
    rather than to a subprocess' pipe -- so a run from last week still says where it
    stopped. `calculation.failed_stage` is imported, not reimplemented."""
    make_run(runs_root, "Test_model_2026-09-22_00-49", through=1, log=failed_log(at=2))

    run = catalog.describe("Test_model_2026-09-22_00-49")

    assert run["complete"] is False
    assert run["failed_at"] == {"index": 2, "of": 3, "name": "2_Excavation"}


def test_a_run_with_no_log_says_nothing_about_why_it_is_incomplete(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49", through=1)

    run = catalog.describe("Test_model_2026-09-22_00-49")

    assert run["complete"] is False
    assert run["failed_at"] is None


def test_stages_fall_back_to_the_output_files_when_the_parameters_are_unreadable(runs_root):
    """A run directory is whatever is on disk, including a deck truncated by a full
    disk or hand-edited afterwards. The output files still name their stages."""
    directory = make_run(runs_root, "Test_model_2026-09-22_00-49")
    (directory / calculation.PARAMETERS_NAME).write_text("{ not json", encoding="utf-8")

    stages = catalog.describe("Test_model_2026-09-22_00-49")["stages"]

    assert [stage["name"] for stage in stages] == EXECUTION


def test_the_fallback_orders_stages_by_their_leading_number(runs_root):
    stages = [f"{n}_Stage" for n in range(1, 12)]
    directory = make_run(runs_root, "Test_model_2026-09-22_00-49", stages=stages)
    (directory / calculation.PARAMETERS_NAME).unlink()

    found = [stage["name"] for stage in catalog.describe("Test_model_2026-09-22_00-49")["stages"]]

    assert found == stages



def test_a_stage_says_whether_it_was_a_flow_or_a_mechanical_calculation(runs_root):
    """Read off each stage's `solution_type`: the Results view draws the zero water
    pressure line by itself after a flow stage, and only on request after a coupled one."""
    directory = make_run(runs_root, "Test_model_2026-09-22_00-49",
                         stages=["1_Flow", "2_Dig", "3_Old"])
    deck = json.loads((directory / calculation.PARAMETERS_NAME).read_text(encoding="utf-8"))
    deck["stages"]["1_Flow"]["stage_settings"]["solver_settings"] = {
        "solution_type": "Steady_State_Groundwater_Flow"}
    deck["stages"]["2_Dig"]["stage_settings"]["solver_settings"] = {
        "solution_type": "Quasi-Static"}
    (directory / calculation.PARAMETERS_NAME).write_text(json.dumps(deck), encoding="utf-8")

    stages = catalog.describe("Test_model_2026-09-22_00-49")["stages"]

    assert [stage["calculation"] for stage in stages] == ["flow", "mechanical", None]


def test_a_stage_from_an_unreadable_deck_has_no_calculation_type(runs_root):
    directory = make_run(runs_root, "Test_model_2026-09-22_00-49")
    (directory / calculation.PARAMETERS_NAME).write_text("{ not json", encoding="utf-8")

    stages = catalog.describe("Test_model_2026-09-22_00-49")["stages"]

    assert [stage["calculation"] for stage in stages] == [None, None, None]

# ── Files ───────────────────────────────────────────────────────────────────

def test_files_are_listed_with_their_sizes(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49", through=1)

    files = {entry["name"]: entry["bytes"]
             for entry in catalog.describe("Test_model_2026-09-22_00-49")["files"]}

    assert "Test_model.mdpa" in files
    assert files["Test_model.mdpa"] > 0
    assert "Test_model_1_Initial_stage.post.res" in files


def test_a_file_is_found_by_name_inside_its_run(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49")

    path = catalog.file_path("Test_model_2026-09-22_00-49", "Test_model.mdpa")

    assert path.read_text(encoding="utf-8").startswith("Begin Properties")


@pytest.mark.parametrize("name", [
    "../Test_model_2026-09-20_10-00/Test_model.mdpa",
    "..\\Test_model.mdpa",
    "/etc/passwd",
    "sub/Test_model.mdpa",
])
def test_a_name_that_leaves_the_run_directory_is_refused(runs_root, name):
    """This is the first endpoint in the project that opens a file the caller named,
    so the refusal is pinned rather than trusted to the router's path matching."""
    make_run(runs_root, "Test_model_2026-09-20_10-00")
    make_run(runs_root, "Test_model_2026-09-22_00-49")

    with pytest.raises(catalog.UnsafeName):
        catalog.file_path("Test_model_2026-09-22_00-49", name)


def test_a_symlink_to_a_file_outside_the_run_directory_is_refused(runs_root):
    run = "Test_model_2026-09-22_00-49"
    directory = make_run(runs_root, run)
    outside = runs_root / "outside.txt"
    outside.write_text("Not a run file\n", encoding="utf-8")
    link = directory / "linked.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Cannot create symbolic links on this system: {error}")

    assert link.is_file()
    assert link.resolve().parent != directory.resolve()
    with pytest.raises(catalog.UnsafeName, match="is not a file in this run"):
        catalog.file_path(run, link.name)


def test_an_unknown_run_is_refused(runs_root):
    with pytest.raises(catalog.UnknownRun):
        catalog.describe("Test_model_1999-01-01_00-00")


def test_a_run_id_cannot_climb_out_of_the_runs_root(runs_root):
    with pytest.raises(catalog.UnknownRun):
        catalog.describe("../..")


def test_a_named_file_that_is_not_there_is_refused(runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49")

    with pytest.raises(catalog.UnknownRun):
        catalog.file_path("Test_model_2026-09-22_00-49", "nothing.json")


# ── The archive ─────────────────────────────────────────────────────────────

def test_the_archive_holds_every_file_of_the_run(runs_root):
    directory = make_run(runs_root, "Test_model_2026-09-22_00-49", log=finished_log())
    expected = sorted(path.name for path in directory.iterdir())

    with zipfile.ZipFile(catalog.archive("Test_model_2026-09-22_00-49")) as archive:
        assert sorted(archive.namelist()) == expected
        assert archive.read("Test_model.mdpa").decode("utf-8").startswith("Begin")


# ── Over HTTP ───────────────────────────────────────────────────────────────

def test_the_runs_endpoint_lists_them(client, runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49", log=finished_log())

    response = client.get("/api/results/runs")

    assert response.status_code == 200
    assert [run["id"] for run in response.json()["runs"]] == [
        "Test_model_2026-09-22_00-49"]


def test_one_run_comes_back_with_its_stages_and_files(client, runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49", log=finished_log())

    run = client.get("/api/results/runs/Test_model_2026-09-22_00-49").json()

    assert len(run["stages"]) == 3
    assert run["complete"] is True
    assert any(entry["name"] == calculation.LOG_NAME for entry in run["files"])


def test_an_unknown_run_is_404_rather_than_500(client, runs_root):
    assert client.get("/api/results/runs/nope_2026-09-22_00-49").status_code == 404


def test_a_file_can_be_downloaded(client, runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49")

    response = client.get(
        "/api/results/runs/Test_model_2026-09-22_00-49/files/Test_model.mdpa")

    assert response.status_code == 200
    assert response.text.startswith("Begin Properties")


def test_a_traversing_download_is_refused_over_http(client, runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49")
    (runs_root / "secret.txt").write_text("no", encoding="utf-8")

    response = client.get(
        "/api/results/runs/Test_model_2026-09-22_00-49/files/..%2Fsecret.txt")

    assert response.status_code in (400, 404)
    assert "no" not in response.text


# ── Reading a stage over HTTP (P1) ──────────────────────────────────────────
#
# The reading itself is `test_gid_results.py` and `test_result_fields.py`; these are
# about the routes -- that a stage can be addressed by its number, and that the three
# ways of asking a wrong question come back as three different answers.

STAGE_MESH = """MESH "K_Mesh_1" dimension 2 ElemType Triangle Nnode 3
Coordinates
1 0 0 0
2 1 0 0
3 0 1 0
End Coordinates
Elements
1 1 2 3 1
End Elements
"""

STAGE_RES = """GiD Post Results File 1.2
GaussPoints "tri1" ElemType Triangle
Number Of Gauss Points: 1
End GaussPoints
Result "TOTAL_DISPLACEMENT" "Kratos" 1 Vector OnNodes
Values
1 0 0 0
2 0.001 -0.002 0
3 0 -0.004 0
End Values
Result "CAUCHY_STRESS_TENSOR" "Kratos" 1 Matrix OnGaussPoints "tri1"
Values
1 -50000 -100000 -50000 0 0 0
End Values
"""


@pytest.fixture
def readable_run(runs_root):
    """A run whose first stage carries real output, small enough to assert on."""
    catalog.forget_cache()
    directory = make_run(runs_root, "Test_model_2026-09-22_00-49", through=0,
                         log=finished_log())
    (directory / "Test_model_1_Initial_stage.post.msh").write_text(
        STAGE_MESH, encoding="utf-8")
    (directory / "Test_model_1_Initial_stage.post.res").write_text(
        STAGE_RES, encoding="utf-8")
    return "Test_model_2026-09-22_00-49"


def test_a_stage_reports_the_fields_it_carries(client, readable_run):
    answer = client.get(f"/api/results/runs/{readable_run}/stages/1/fields").json()

    groups = {group["name"] for group in answer["groups"]}
    assert "Deformations" in groups
    assert "Effective stresses" in groups
    assert answer["stage"]["index"] == 1


def test_one_field_comes_back_with_its_range_and_unit(client, readable_run):
    answer = client.get(
        f"/api/results/runs/{readable_run}/stages/1/field/uy").json()

    assert answer["unit"] == "m"
    assert answer["min"] == pytest.approx(-0.004)
    assert len(answer["ids"]) == len(answer["values"]) == 3


def test_a_gauss_field_can_be_asked_for_per_element_or_per_node(client, readable_run):
    per_element = client.get(
        f"/api/results/runs/{readable_run}/stages/1/field/syy"
        "?location=elements").json()
    per_node = client.get(
        f"/api/results/runs/{readable_run}/stages/1/field/syy?location=nodes").json()

    assert per_element["ids"] == [1]
    assert per_element["values"][0] == pytest.approx(-100_000.0)
    assert per_node["ids"] == [1, 2, 3]


def test_a_field_this_stage_does_not_carry_is_422_not_404(client, readable_run):
    """The run is there and the stage is there; what is wrong is the question. A 404
    would say the stage does not exist, which would send whoever asked looking in the
    wrong place."""
    response = client.get(
        f"/api/results/runs/{readable_run}/stages/1/field/wibble")

    assert response.status_code == 422


def test_a_stage_that_is_not_there_is_404(client, readable_run):
    assert client.get(
        f"/api/results/runs/{readable_run}/stages/9/fields").status_code == 404


def test_a_stage_that_wrote_no_results_says_so(client, runs_root):
    """A run that stopped early. The stage is in the execution list and has no output,
    which is a different thing from a stage that does not exist."""
    catalog.forget_cache()
    make_run(runs_root, "Test_model_2026-09-22_00-49", through=0)

    response = client.get("/api/results/runs/Test_model_2026-09-22_00-49/stages/2/fields")

    assert response.status_code == 404
    assert "no results" in response.json()["detail"]


def test_parsing_is_cached_between_requests(client, readable_run):
    """One stage is half a megabyte of ASCII and the viewer asks for one field at a
    time, so the second request for the same stage must not read it again."""
    catalog.forget_cache()
    client.get(f"/api/results/runs/{readable_run}/stages/1/field/uy")
    before = len(catalog._cache)

    client.get(f"/api/results/runs/{readable_run}/stages/1/field/ux")

    assert len(catalog._cache) == before, "the same two files were parsed twice"


def test_the_archive_endpoint_returns_a_zip(client, runs_root):
    make_run(runs_root, "Test_model_2026-09-22_00-49")

    response = client.get("/api/results/runs/Test_model_2026-09-22_00-49/archive")

    assert response.status_code == 200
    assert response.content[:2] == b"PK"
    assert "Test_model_2026-09-22_00-49.zip" in response.headers["content-disposition"]


# ── A run id that climbs out of the runs root (finding F9) ──────────────────
#
# `RUN_NAME`'s `deck` group is `.+`, so `..\secret_2026-01-01_00-00` matches it. On
# Windows the backslash is a separator, and the "run" resolved outside the runs root.

OUTSIDE = "secret_2026-01-01_00-00"


@pytest.fixture
def outside_run(runs_root):
    """A real run directory beside the runs root, holding something private."""
    directory = make_run(runs_root.parent, OUTSIDE)
    (directory / "private.txt").write_text("do not serve", encoding="utf-8")
    return directory


@pytest.mark.parametrize("run_id", [
    "..\\" + OUTSIDE,
    "../" + OUTSIDE,
    "x\\..\\..\\" + OUTSIDE,
    "C:\\" + OUTSIDE,
    "\\\\server\\share\\" + OUTSIDE,
    ".." + OUTSIDE,
])
def test_a_run_id_with_a_separator_or_dots_is_refused(runs_root, outside_run, run_id):
    with pytest.raises(catalog.UnknownRun):
        catalog.run_directory(run_id)


@pytest.mark.parametrize("encoded", [
    f"..%5C{OUTSIDE}",
    f"..%2F{OUTSIDE}",
    f"x%5C..%5C..%5C{OUTSIDE}",
])
@pytest.mark.parametrize("tail", [
    "", "/archive", "/files/private.txt", "/members", "/members/wall/moment",
    "/stages/1/fields", "/stages/1/mesh", "/stages/1/displacement", "/stages/1/at/1",
    "/stages/1/parts", "/stages/1/field/p",
])
def test_a_traversing_run_id_is_refused_over_http(client, outside_run, encoded, tail):
    response = client.get(f"/api/results/runs/{encoded}{tail}")

    assert response.status_code in (400, 404)
    assert "do not serve" not in response.text
    assert b"private.txt" not in response.content


def test_the_runs_root_itself_is_not_a_run(runs_root):
    with pytest.raises(catalog.UnknownRun):
        catalog.run_directory(".")


def test_a_deck_name_with_two_dots_keeps_its_runs(runs_root):
    """`core.kratos.external_deck.deck_name` is a file's stem, and `model..v2.mdpa` is a legal file."""
    make_run(runs_root, "model..v2_2026-01-01_00-00", deck="model..v2")

    assert catalog.run_directory("model..v2_2026-01-01_00-00").is_dir()


def test_the_listing_ignores_what_is_not_a_run(runs_root):
    """A runs root is a folder people put things in: notes, a zip, a copied deck."""
    make_run(runs_root, "Test_model_2026-09-22_00-49")
    (runs_root / "notes").mkdir()
    (runs_root / "old results.zip").write_bytes(b"PK")
    (runs_root / "Test_model_2026-09-22").mkdir()

    assert [run["id"] for run in catalog.runs()] == ["Test_model_2026-09-22_00-49"]


# ── The run's unit system ───────────────────────────────────────────────────
# Kratos has no units: a run is in its project's system, recorded beside the deck
# (`calculation.UNITS_NAME`), and every label the results carry follows it.

def test_a_run_without_a_record_is_si(readable_run):
    assert catalog.run_unit_system(readable_run) == "SI"
    assert catalog.describe(readable_run)["unit_system"] == "SI"


def test_a_run_says_which_system_its_numbers_are_in(client, runs_root, readable_run):
    (runs_root / readable_run / calculation.UNITS_NAME).write_text(
        json.dumps({"unit_system": "kN"}), encoding="utf-8")
    assert catalog.run_unit_system(readable_run) == "kN"
    answer = client.get(f"/api/results/runs/{readable_run}/stages/1/field/syy"
                        "?location=elements").json()
    assert answer["unit"] == "kPa"
    assert answer["values"][0] == pytest.approx(-100_000.0), "labelled, never scaled"


@pytest.mark.parametrize("text", ["not json", '{"unit_system": "imperial"}', "[]"])
def test_a_record_that_cannot_be_read_is_si(runs_root, readable_run, text):
    (runs_root / readable_run / calculation.UNITS_NAME).write_text(text, encoding="utf-8")
    assert catalog.run_unit_system(readable_run) == "SI"


def test_the_deck_writes_its_system_beside_itself(tmp_path):
    written = calculation.write_deck({"deck_name": "d", "mdpa": "", "project_parameters": "{}",
                                    "unit_system": "kN"}, tmp_path)
    assert calculation.UNITS_NAME in written
    assert json.loads((tmp_path / calculation.UNITS_NAME).read_text()) == {"unit_system": "kN"}


# ── A run anywhere (plan/active/cli-plan.md D12) ────────────────────────────
# A run id names a directory under the runs root, and only that: it is what a URL
# carries. A `Path` names a run directory wherever it is -- copied off a cluster, or
# run in its own deck folder -- which is what `kratos-cli results` reads.

def test_a_run_outside_the_runs_root_is_read_by_its_directory(tmp_path, readable_run,
                                                               runs_root):
    elsewhere = tmp_path / "copied" / readable_run
    shutil.copytree(runs_root / readable_run, elsewhere)

    assert catalog.describe(elsewhere) == catalog.describe(readable_run)
    assert catalog.stage_fields(elsewhere, 1) == catalog.stage_fields(readable_run, 1)
    assert (catalog.stage_field(elsewhere, 1, "syy", "elements")
            == catalog.stage_field(readable_run, 1, "syy", "elements"))
    assert catalog.stage_at_node(elsewhere, 1, 2) == catalog.stage_at_node(readable_run, 1, 2)
    assert catalog.file_path(elsewhere, calculation.PARAMETERS_NAME).is_file()


def test_a_directory_not_named_as_a_run_is_named_by_its_deck(tmp_path):
    directory = make_run(tmp_path, "deck", log=finished_log())

    run = catalog.describe(directory)

    assert (run["id"], run["deck"], run["started"]) == ("deck", "Test_model", None)
    assert run["complete"] and len(run["stages"]) == 3


def test_a_run_id_is_never_read_as_a_path(runs_root, outside_run):
    with pytest.raises(catalog.UnknownRun):
        catalog.describe(str(outside_run))


def test_a_path_that_is_not_a_directory_is_refused(tmp_path):
    with pytest.raises(catalog.UnknownRun, match="no run directory"):
        catalog.describe(tmp_path / "nothing here")


def test_a_deck_without_output_basenames_recovers_files_by_stage_name(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Initial", "2_Dig"]}},
        "stages": {},
    }), encoding="utf-8")
    (tmp_path / "old_1_Initial.post.res").write_text("", encoding="utf-8")
    (tmp_path / "old_1_Initial.post.msh").write_text("", encoding="utf-8")

    stages = catalog.stage_list(tmp_path)

    assert [stage["name"] for stage in stages] == ["1_Initial", "2_Dig"]
    assert stages[0]["base"] == "old_1_Initial"
    assert stages[0]["mesh_file"] == "old_1_Initial.post.msh"
    assert stages[0]["results_file"] == "old_1_Initial.post.res"
    assert stages[1]["base"] is None
    assert stages[1]["results"] is False


def test_an_external_decks_gid_output_name_takes_priority_over_problem_name(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Load"]}},
        "stages": {"1_Load": {"stage_settings": {
            "problem_data": {"problem_name": "not_the_output"},
            "output_processes": {"gid_output": [{
                "Parameters": {"output_name": r"C:\solver\outputs\actual"},
            }]},
        }}},
    }), encoding="utf-8")
    (tmp_path / "actual.post.res").write_text("", encoding="utf-8")

    stage = catalog.stage_list(tmp_path)[0]

    assert stage["base"] == "actual"
    assert stage["results_file"] == "actual.post.res"


def test_a_stage_declared_but_not_reached_reports_why_it_has_no_results(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Initial"]}},
        "stages": {},
    }), encoding="utf-8")

    with pytest.raises(catalog.UnknownRun, match="wrote no results.*stopped before"):
        catalog.stage_results(tmp_path, 1)
    with pytest.raises(catalog.UnknownRun, match="wrote no mesh file"):
        catalog.stage_mesh(tmp_path, 1)
    with pytest.raises(catalog.UnknownRun, match="has no stage 2; it has 1"):
        catalog.stage_record(tmp_path, 2)


@pytest.mark.parametrize("read, message", [
    (catalog.stage_geometry, "mesh cannot be named"),
    (catalog.stage_parts, "parts cannot be named"),
])
def test_output_without_the_original_mdpa_explains_the_missing_part_names(
        tmp_path, read, message):
    with pytest.raises(catalog.UnknownRun, match=message):
        read(tmp_path, 1)


def test_a_run_path_that_was_removed_reports_the_missing_directory(tmp_path):
    missing = tmp_path / "removed-run"

    with pytest.raises(catalog.UnknownRun, match="no run directory"):
        catalog.describe(missing)


@pytest.mark.parametrize("parameters", [
    [],
    {"orchestrator": {"settings": {"execution_list": "not-a-list"}}},
])
def test_unusable_deck_metadata_does_not_hide_existing_stage_output(tmp_path, parameters):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(
        json.dumps(parameters), encoding="utf-8")
    (tmp_path / "model_1_Initial.post.res").write_text("", encoding="utf-8")

    stages = catalog.stage_list(tmp_path)

    assert len(stages) == 1
    assert stages[0]["name"] == "1_Initial"
    assert stages[0]["results_file"] == "model_1_Initial.post.res"


def test_nonstring_execution_entries_do_not_create_spurious_stages(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": [None, 42, "1_Initial"]}},
        "stages": {},
    }), encoding="utf-8")

    assert [stage["name"] for stage in catalog.stage_list(tmp_path)] == ["1_Initial"]


def test_member_output_without_an_mdpa_explains_why_it_cannot_be_placed(tmp_path):
    (tmp_path / deck_files.PARAMETERS_NAME).write_text(json.dumps({
        "orchestrator": {"settings": {"execution_list": ["1_Initial"]}},
        "stages": {},
    }), encoding="utf-8")
    (tmp_path / "1_Initial__output_wall.json").write_text(json.dumps({
        "NODE_1": {"BENDING_MOMENT": [1000]},
    }), encoding="utf-8")

    with pytest.raises(catalog.UnknownRun, match="has no .mdpa.*members cannot be placed"):
        catalog.member_profiles(tmp_path, "wall", "M")
