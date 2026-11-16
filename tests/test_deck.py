"""A model that *is* a Kratos deck: opened with `run <file.py>`, shown as its own mesh,
and calculated as the files it already is.

A real case is the reason: a deck of twenty stages, three material sets, phreatic
multi-lines and a constitutive-law switch, none of which the parametric `Project` can
express -- and none of which it needs to, because the deck is already written and
validated. These tests use a two-stage stand-in for one, so they run on any clone.
"""

import json
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from core import scripting
from core.kratos import external_deck
from core.analysis import calculation
from core.results import catalog
from backend.main import app
from core.model.schemas import Project

MODEL_SCRIPT = Path(__file__).resolve().parent / "models" / "excavation.py"

MDPA = """\
Begin Properties 1
End Properties

Begin Nodes
  1  0.0  -10.0  0.0
  2  20.0 -10.0  0.0
  3  20.0   2.5  0.0
  4  0.0    2.5  0.0
End Nodes

Begin Elements UPwSmallStrainElement2D4N
  1  1  1 2 3 4
End Elements

Begin SubModelPart soil
  Begin SubModelPartNodes
    1
    2
    3
    4
  End SubModelPartNodes
  Begin SubModelPartElements
    1
  End SubModelPartElements
End SubModelPart

Begin SubModelPart bottom
  Begin SubModelPartNodes
    1
    2
  End SubModelPartNodes
End SubModelPart
"""


def gid_output(name: str) -> dict:
    return {"gid_output": [{
        "python_module": "gid_output_process",
        "kratos_module": "KratosMultiphysics",
        "process_name": "GiDOutputProcess",
        "Parameters": {"model_part_name": "PorousDomain.porous_computational_model_part",
                       "output_name": name},
    }]}


def stage(problem: str, materials: str, output: str, first: bool = False) -> dict:
    body = {"stage_settings": {
        "problem_data": {"problem_name": problem},
        "solver_settings": {
            "model_import_settings": {"input_type": "use_input_model_part"},
            "material_import_settings": {"materials_filename": materials},
        },
        "output_processes": gid_output(output),
    }}
    if first:
        body["stage_preprocess"] = {"modelers": [{
            "name": "Modelers.KratosMultiphysics.ImportMDPAModeler",
            "Parameters": {"input_filename": "dike", "model_part_name": "PorousDomain"},
        }]}
    return body


PARAMETERS = {
    "orchestrator": {"name": "Orchestrators.KratosMultiphysics.SequentialOrchestrator",
                     "settings": {"execution_list": ["1_Initial", "2_Load"]}},
    "stages": {
        "1_Initial": stage("1_Initial", "materials_a.json", "gid_output/1_Initial",
                           first=True),
        # Its own output name, unlike its problem name: the file the writer makes is
        # named by `output_name`, and that is the one results has to look for.
        "2_Load": stage("2_Load", "materials_b.json", "gid_output/second"),
    },
}


@pytest.fixture
def deck_dir(tmp_path):
    directory = tmp_path / "dike_case"
    directory.mkdir()
    (directory / "dike.mdpa").write_text(MDPA, encoding="utf-8")
    (directory / "dike.json").write_text(json.dumps(PARAMETERS, indent=2), encoding="utf-8")
    (directory / "materials_a.json").write_text('{"properties": []}', encoding="utf-8")
    (directory / "materials_b.json").write_text('{"properties": [1]}', encoding="utf-8")
    # Not part of the deck: results of some earlier run, a README, a picture.
    (directory / "README.md").write_text("notes", encoding="utf-8")
    return directory


@pytest.fixture
def project(deck_dir):
    return external_deck.deck_project(deck_dir, "dike.json", name="Dike")


# ── The project ─────────────────────────────────────────────────────────────

def test_a_deck_project_points_at_its_deck(project, deck_dir):
    assert isinstance(project, Project)
    assert project.name == "Dike"
    assert Path(project.deck.directory) == deck_dir.resolve()
    assert project.deck.parameters == "dike.json"


def test_a_deck_project_takes_its_dimension_and_extent_from_the_mesh(project):
    """A plane-strain deck opens in 2D, and the camera frames the mesh rather than a
    default site that has nothing to do with it."""
    assert project.dimension == 2
    assert (project.domain.x0, project.domain.x1) == (0.0, 20.0)
    assert (project.domain.y_bottom, project.domain.y_top) == (-10.0, 2.5)


def test_the_name_defaults_to_the_mesh_file(deck_dir):
    assert external_deck.deck_project(deck_dir, "dike.json").name == "dike"


def test_a_deck_project_survives_the_round_trip_through_json(project):
    """The browser holds the project and sends it back; the deck has to come with it."""
    again = Project.model_validate_json(project.model_dump_json())
    assert again.deck == project.deck


def test_a_missing_parameters_file_is_named(deck_dir):
    with pytest.raises(external_deck.DeckError, match="nope.json"):
        external_deck.deck_project(deck_dir, "nope.json")


def test_a_missing_materials_file_is_named(deck_dir):
    (deck_dir / "materials_b.json").unlink()
    with pytest.raises(external_deck.DeckError, match="materials_b.json"):
        external_deck.deck_project(deck_dir, "dike.json")


def test_a_missing_mesh_is_named(deck_dir):
    (deck_dir / "dike.mdpa").unlink()
    with pytest.raises(external_deck.DeckError, match="dike.mdpa"):
        external_deck.deck_project(deck_dir, "dike.json")


# ── What the deck is made of ────────────────────────────────────────────────

def test_the_deck_is_the_files_its_parameters_name(project):
    """Read off the parameters, not globbed: a case directory also holds READMEs, old
    results and pictures, and none of those belong in a run."""
    assert external_deck.input_files(project.deck) == [
        "dike.json", "dike.mdpa", "materials_a.json", "materials_b.json"]


def test_the_deck_name_is_the_mesh_file(project):
    assert external_deck.deck_name(project.deck) == "dike"


def test_the_preview_is_the_mesh_with_its_parts(project):
    preview = external_deck.preview(project.deck)
    assert preview["dimension"] == 2
    assert [section["part"] for section in preview["sections"]] == ["soil"]
    assert {part["name"] for part in preview["parts"]} == {"soil", "bottom"}
    assert "node_parts" in preview


# ── Staging it into a run directory ─────────────────────────────────────────

def test_staging_copies_the_deck_and_nothing_else(project, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    written = external_deck.stage(project.deck, run)

    assert sorted(written) == sorted([calculation.PARAMETERS_NAME, "dike.mdpa",
                                      "materials_a.json", "materials_b.json"])
    assert sorted(path.name for path in run.iterdir()) == sorted(written)
    assert (run / "materials_b.json").read_text(encoding="utf-8") == '{"properties": [1]}'


def with_own_process(deck_dir, module: str, ship: bool = True) -> Project:
    """The dike deck with a process of its own in the second stage: a `python_module`
    with no `kratos_module`, such as the temporary prestress workaround."""
    parameters = json.loads((deck_dir / "dike.json").read_text(encoding="utf-8"))
    parameters["stages"]["2_Load"]["stage_settings"]["processes"] = {
        "auxiliary_process_list": [
            {"python_module": module, "process_name": "Own",
             "Parameters": {"model_part_name_list": ["PorousDomain.soil"]}},
            {"python_module": "apply_final_stresses_of_previous_stage_to_initial_state",
             "kratos_module": "KratosMultiphysics.GeoMechanicsApplication",
             "Parameters": {"model_part_name_list": ["PorousDomain.soil"]}},
        ]}
    (deck_dir / "dike.json").write_text(json.dumps(parameters), encoding="utf-8")
    if ship:
        (deck_dir / f"{module}.py").write_text("def Factory(s, m): pass\n", encoding="utf-8")
    return external_deck.deck_project(deck_dir, "dike.json", name="Dike")


def test_a_process_module_beside_the_deck_is_staged_with_it(deck_dir, tmp_path):
    """Kratos imports it from the directory the run happens in, so a run directory
    without it is a deck that stops at the stage that runs it."""
    project = with_own_process(deck_dir, "kratos_gui_prestress_workaround")
    assert external_deck.input_files(project.deck)[-1] == \
        "kratos_gui_prestress_workaround.py"
    run = tmp_path / "run"
    run.mkdir()
    external_deck.stage(project.deck, run)
    assert (run / "kratos_gui_prestress_workaround.py").read_text(encoding="utf-8") == \
        "def Factory(s, m): pass\n"


def test_a_process_module_not_beside_the_deck_is_left_where_it_is_installed(deck_dir):
    project = with_own_process(deck_dir, "installed_elsewhere", ship=False)
    assert external_deck.input_files(project.deck) == [
        "dike.json", "dike.mdpa", "materials_a.json", "materials_b.json"]


def test_staging_writes_the_output_beside_the_deck(project, tmp_path):
    """A run directory is flat -- `catalog.file_path` serves nothing else -- so an
    output name with a directory in it is cut down to its last component."""
    run = tmp_path / "run"
    run.mkdir()
    external_deck.stage(project.deck, run)

    staged = json.loads((run / calculation.PARAMETERS_NAME).read_text(encoding="utf-8"))
    names = [process["Parameters"]["output_name"]
             for stage_ in staged["stages"].values()
             for process in stage_["stage_settings"]["output_processes"]["gid_output"]]
    assert names == ["1_Initial", "second"]


def test_staging_leaves_the_original_deck_alone(project, deck_dir, tmp_path):
    before = (deck_dir / "dike.json").read_text(encoding="utf-8")
    run = tmp_path / "run"
    run.mkdir()
    external_deck.stage(project.deck, run)
    assert (deck_dir / "dike.json").read_text(encoding="utf-8") == before


# ── Results find a deck's output by the name it was written under ───────────

def test_results_find_a_stage_by_its_output_name(project, tmp_path, monkeypatch):
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    run = calculation.new_run_directory("dike")
    external_deck.stage(project.deck, run)
    (run / "second.post.res").write_text("", encoding="utf-8")
    (run / "second.post.msh").write_text("", encoding="utf-8")

    stages = catalog.stage_list(run)
    assert [s["name"] for s in stages] == ["1_Initial", "2_Load"]
    assert stages[1]["results_file"] == "second.post.res"
    assert stages[1]["mesh_file"] == "second.post.msh"


# ── Calculating it ──────────────────────────────────────────────────────────

@pytest.fixture
def stand_in(tmp_path, monkeypatch):
    """This interpreter in Kratos' place, as in `test_calculate`."""
    monkeypatch.setattr(calculation, "SETTINGS_FILE", tmp_path / "no-settings.json")
    monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)
    monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    monkeypatch.setattr(calculation, "COMMAND",
                        ["-c", "open('1_Initial.post.res', 'w').close()"])


def test_a_deck_runs_as_it_is(project, stand_in):
    result = calculation.run_deck(project.deck)

    assert result["ok"] is True
    directory = Path(result["directory"])
    assert directory.name.startswith("dike_")
    assert calculation.PARAMETERS_NAME in result["inputs"]
    assert result["outputs"] == ["1_Initial.post.res"]


def test_a_deck_run_is_refused_while_another_runs(project, stand_in, monkeypatch):
    monkeypatch.setattr(calculation, "_running", True)
    with pytest.raises(calculation.Busy):
        calculation.run_deck(project.deck)


def test_two_deck_presses_at_the_same_moment_start_one_run(
        project, stand_in, monkeypatch, tmp_path):
    """As `test_calculate`'s export twin: the claim has to come before the copying, or
    both presses get past the check while the first is still staging its files."""
    import threading
    both_inside = threading.Barrier(2, timeout=2)
    stage_files = external_deck.stage

    def slow_stage(source, directory):
        try:
            both_inside.wait()
        except threading.BrokenBarrierError:
            pass
        return stage_files(source, directory)

    monkeypatch.setattr(external_deck, "stage", slow_stage)
    outcomes = []

    def press():
        try:
            outcomes.append(calculation.run_deck(project.deck)["ok"])
        except calculation.Busy:
            outcomes.append("busy")

    threads = [threading.Thread(target=press) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes, key=str) == [True, "busy"]
    assert len(list((tmp_path / "runs").iterdir())) == 1


def test_a_deck_file_gone_since_opening_is_reported_not_crashed_on(
        project, stand_in, deck_dir):
    """The deck is read when it is opened and copied when Calculate is pressed; a file
    deleted in between is a message naming it, and the button is free again."""
    (deck_dir / "materials_b.json").unlink()

    with pytest.raises(calculation.CalculationError, match="materials_b.json"):
        calculation.run_deck(project.deck)
    assert calculation._running is False


# ── `run <file.py>` ─────────────────────────────────────────────────────────

def deck_script(tmp_path, deck_dir) -> Path:
    path = tmp_path / "dike_case.py"
    path.write_text(textwrap.dedent(f"""
        from core.kratos.external_deck import deck_project

        def dike_project():
            return deck_project({str(deck_dir)!r}, "dike.json", name="Dike")
    """), encoding="utf-8")
    return path


def test_a_script_can_hand_back_a_deck(tmp_path, deck_dir):
    loaded = scripting.load_project(deck_script(tmp_path, deck_dir))
    assert loaded.deck is not None and loaded.name == "Dike"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/project/reset")


def test_running_a_deck_script_sends_its_mesh_along(client, tmp_path, deck_dir):
    """What lets the command line go straight to the mesh: there is nothing to
    generate, so the mesh comes back with the model that owns it."""
    body = client.post("/api/project/script",
                       json={"path": str(deck_script(tmp_path, deck_dir))}).json()
    assert body["project"]["deck"]["parameters"] == "dike.json"
    assert [s["part"] for s in body["mesh"]["sections"]] == ["soil"]


def test_a_parametric_script_sends_no_mesh(client):
    """A model built from layers is meshed by the client after it loads, as before."""
    body = client.post("/api/project/script", json={"path": str(MODEL_SCRIPT)}).json()
    assert body["mesh"] is None


def test_a_deck_is_not_remeshed(client, project):
    """Its mesh is the deck's own. Generating one would mesh the empty site the
    project carries for the schema's sake, and quietly show nothing."""
    client.put("/api/project", json=project.model_dump(mode="json"))
    response = client.post("/api/mesh", json={"element_size": 2.0})
    assert response.status_code == 422
    assert "deck" in response.json()["detail"]


def test_calculate_runs_the_deck_rather_than_exporting(client, project, monkeypatch):
    ran = {}

    def fake_run_deck(source):
        ran["deck"] = source
        return {"ok": True, "returncode": 0, "stage": None, "seconds": 0.1,
                "directory": str(Path("runs") / "dike_2026-10-09_12-00"),
                "inputs": [], "outputs": [], "log": calculation.LOG_NAME, "error": None}

    monkeypatch.setattr(calculation, "run_deck", fake_run_deck)
    client.put("/api/project", json=project.model_dump(mode="json"))
    body = client.post("/api/calculate", json={"element_size": 2.0}).json()

    assert ran["deck"] == project.deck
    assert body["run"] == "dike_2026-10-09_12-00"
    assert body["stats"] == {"nodes": 4, "elements": 1}
    assert body["warnings"] == []


# ── The stages, as stages ───────────────────────────────────────────────────
# A deck says which parts each stage computes on (`problem_domain_sub_model_part_list`)
# and which it loads (`loads_process_list`). The difference between one stage and the
# next is exactly what a `Stage` stores, so the Stage explorer can list the deck's own
# sequence -- and draw, for each, the parts it has.

STAGED_MDPA = """\
Begin Nodes
  1  0.0  -10.0  0.0
  2  20.0 -10.0  0.0
  3  20.0   0.0  0.0
  4  0.0    0.0  0.0
  5  20.0   2.0  0.0
  6  0.0    2.0  0.0
End Nodes

Begin Elements UPwSmallStrainElement2D4N
  1  1  1 2 3 4
  2  1  4 3 5 6
End Elements

Begin SubModelPart soil
  Begin SubModelPartElements
    1
  End SubModelPartElements
End SubModelPart

Begin SubModelPart fill
  Begin SubModelPartElements
    2
  End SubModelPartElements
End SubModelPart

Begin SubModelPart crane
  Begin SubModelPartNodes
    5
    6
  End SubModelPartNodes
End SubModelPart

Begin SubModelPart Bottom
  Begin SubModelPartNodes
    1
    2
  End SubModelPartNodes
End SubModelPart
"""


def staged_stage(name: str, domain: list[str], loads: tuple = (), *,
                 k0: bool = False, reset: bool = False, days: float = 0.0,
                 start: float = 0.0) -> dict:
    body = stage(name, "materials_a.json", name, first=(name == "1_Initial_stage"))
    body["stage_settings"]["problem_data"].update(
        {"start_time": start, "end_time": start + (days * 86400.0 if days else 1.0)})
    solver = body["stage_settings"]["solver_settings"]
    solver.update({"problem_domain_sub_model_part_list": domain,
                   "reset_displacements": reset, "max_iterations": 50,
                   "convergence_criterion": "residual_criterion",
                   "residual_relative_tolerance": 0.01})
    processes = {
        "loads_process_list": [
            {"python_module": "apply_vector_constraint_table_process",
             "Parameters": {"model_part_name":
                            "PorousDomain.porous_computational_model_part"}},
        ] + [{"python_module": "apply_vector_constraint_table_process",
              "Parameters": {"model_part_name": f"PorousDomain.{part}"}}
             for part in loads],
        "constraints_process_list": [
            {"python_module": "apply_vector_constraint_table_process",
             "Parameters": {"model_part_name": "PorousDomain.Bottom"}}],
    }
    if k0:
        processes["auxiliary_process_list"] = [
            {"python_module": "apply_k0_procedure_process", "Parameters": {}}]
    body["stage_settings"]["processes"] = processes
    return body


STAGED = {
    "orchestrator": {"name": "Orchestrators.KratosMultiphysics.SequentialOrchestrator",
                     "settings": {"execution_list": [
                         "1_Initial_stage", "2_Null_step", "3_Fill", "4_Crane",
                         "5_Crane_off", "6_Dig"]}},
    "stages": {
        "1_Initial_stage": staged_stage("1_Initial_stage", ["soil"], k0=True, start=-2.0),
        "2_Null_step": staged_stage("2_Null_step", ["soil"], start=-1.0),
        "3_Fill": staged_stage("3_Fill", ["soil", "fill"], reset=True, days=17.0),
        "4_Crane": staged_stage("4_Crane", ["soil", "fill"], ("crane",), days=1.0),
        "5_Crane_off": staged_stage("5_Crane_off", ["soil", "fill"], days=1.0),
        "6_Dig": staged_stage("6_Dig", ["soil"], days=2.0),
    },
}


@pytest.fixture
def staged(tmp_path):
    directory = tmp_path / "staged_case"
    directory.mkdir()
    (directory / "dike.mdpa").write_text(STAGED_MDPA, encoding="utf-8")
    (directory / "dike.json").write_text(json.dumps(STAGED, indent=2), encoding="utf-8")
    (directory / "materials_a.json").write_text('{"properties": []}', encoding="utf-8")
    return external_deck.deck_project(directory, "dike.json", name="Staged dike")


def test_every_stage_becomes_a_stage_in_run_order(staged):
    assert [stage.id for stage in staged.stages] == [
        "1_Initial_stage", "2_Null_step", "3_Fill", "4_Crane", "5_Crane_off", "6_Dig"]
    assert [stage.parent for stage in staged.stages] == [
        None, "1_Initial_stage", "2_Null_step", "3_Fill", "4_Crane", "5_Crane_off"]


def test_a_stage_is_named_the_way_results_name_its_stage(staged):
    """`results` calls a stage by its name without the number in front, spaces for
    underscores -- the Stage explorer numbers its rows itself."""
    assert [stage.name for stage in staged.stages] == [
        "Initial stage", "Null step", "Fill", "Crane", "Crane off", "Dig"]


def test_what_a_stage_may_switch_is_what_the_stages_compute_on_or_load(staged):
    """Not every part of the mdpa: `Bottom` is a boundary every stage constrains,
    never something a stage builds or removes."""
    assert staged.deck.parts == ["soil", "fill", "crane"]
    assert staged.stageable_keys() == ["soil", "fill", "crane"]


def test_each_stage_stores_what_its_stage_changes(staged):
    by_id = {stage.id: stage for stage in staged.stages}
    # The first starts from "everything is there", so it removes what it lacks.
    assert by_id["1_Initial_stage"].deactivate == ["fill", "crane"]
    assert by_id["1_Initial_stage"].activate == []
    assert (by_id["2_Null_step"].activate, by_id["2_Null_step"].deactivate) == ([], [])
    assert by_id["3_Fill"].activate == ["fill"]
    assert by_id["4_Crane"].activate == ["crane"]
    assert by_id["5_Crane_off"].deactivate == ["crane"]
    assert by_id["6_Dig"].deactivate == ["fill"]


def test_the_resolved_stages_are_the_stages_own_part_lists(staged):
    from core.model import stages
    assert stages.active_parts(staged, "4_Crane") == {"soil", "fill", "crane"}
    assert stages.active_parts(staged, "6_Dig") == {"soil"}


def test_a_stage_carries_its_stage_settings(staged):
    by_id = {stage.id: stage for stage in staged.stages}
    assert by_id["1_Initial_stage"].stress_initialisation == "K0"
    assert by_id["2_Null_step"].stress_initialisation == "none"
    assert all(stage.calculation == "mechanical" for stage in staged.stages)
    assert all(stage.time_integration == "static" for stage in staged.stages)
    assert by_id["3_Fill"].stress_initialisation == "none"
    assert by_id["3_Fill"].reset_displacements is True
    assert by_id["4_Crane"].reset_displacements is False
    assert by_id["3_Fill"].max_iterations == 50
    assert by_id["3_Fill"].convergence_criterion == "residual_criterion"
    assert by_id["3_Fill"].tolerated_error == 0.01
    # The deck's own seconds, which are the project's. Its solver names no step, so
    # each stage is one step, as Kratos would run it.
    assert (by_id["3_Fill"].duration, by_id["3_Fill"].time_step) == (17 * 86400.0,) * 2
    assert (by_id["1_Initial_stage"].duration, by_id["1_Initial_stage"].time_step) == (1.0, 1.0)


def test_a_deck_without_part_lists_has_stages_that_change_nothing(project):
    """The two-stage stand-in above names no parts per stage: its stages still list,
    and switch nothing on or off."""
    assert [stage.id for stage in project.stages] == ["1_Initial", "2_Load"]
    assert all(not stage.activate and not stage.deactivate for stage in project.stages)


def test_a_decks_stages_are_not_edited_here(client, staged):
    """They are read from the deck, and the deck is what runs: an edit made here would
    change nothing that is calculated."""
    client.put("/api/project", json=staged.model_dump(mode="json"))
    response = client.patch("/api/project/stages",
                            json={"stages": [p.model_dump() for p in staged.stages[:2]]})
    assert response.status_code == 422
    assert "deck" in response.json()["detail"]


def test_staging_brings_the_units_record_when_the_deck_has_one(project, deck_dir, tmp_path):
    """A deck this application exported records its unit system beside itself; opened
    again as a deck case, the record goes into the run so its results are labelled in
    that system (`catalog.run_unit_system`). A deck from elsewhere has none, and is SI."""
    from core.analysis import calculation
    (deck_dir / calculation.UNITS_NAME).write_text('{"unit_system": "kN"}', encoding="utf-8")
    written = external_deck.stage(project.deck, tmp_path)
    assert calculation.UNITS_NAME in written
    assert (tmp_path / calculation.UNITS_NAME).read_text(encoding="utf-8") == '{"unit_system": "kN"}'


def test_external_deck_stages_follow_execution_order_and_keep_only_changes():
    parameters_doc = {
        "orchestrator": {"settings": {"execution_list": ["1_Initial", "2_Install", "missing"]}},
        "stages": {
            "1_Initial": {"stage_settings": {
                "solver_settings": {"problem_domain_sub_model_part_list": ["PorousDomain.Soil"]},
            }},
            "2_Install": {"stage_settings": {
                "solver_settings": {"problem_domain_sub_model_part_list":
                                    ["PorousDomain.Soil", "PorousDomain.Wall"]},
            }},
        },
    }

    stages = external_deck.styx_stages(parameters_doc)

    assert [stage.id for stage in stages] == ["1_Initial", "2_Install"]
    assert stages[0].name == "Initial"
    assert stages[0].parent is None
    assert stages[0].activate == []
    assert stages[0].deactivate == ["Wall"]
    assert stages[1].parent == "1_Initial"
    assert stages[1].activate == ["Wall"]
    assert stages[1].deactivate == []


def test_external_deck_parameters_fail_with_a_user_facing_missing_file_message(tmp_path):
    deck = SimpleNamespace(directory=str(tmp_path), parameters="missing.json")

    with pytest.raises(external_deck.DeckError, match="no deck parameters"):
        external_deck._parameters(deck)


def test_external_deck_rejects_json_without_a_stages_object(tmp_path):
    (tmp_path / "parameters.json").write_text('{"problem_data": {}}', encoding="utf-8")
    deck = SimpleNamespace(directory=str(tmp_path), parameters="parameters.json")

    with pytest.raises(external_deck.DeckError, match='no "stages" to run'):
        external_deck._parameters(deck)


def test_external_deck_reports_unreadable_parameter_json(tmp_path):
    (tmp_path / "parameters.json").write_text("{", encoding="utf-8")
    deck = SimpleNamespace(directory=str(tmp_path), parameters="parameters.json")

    with pytest.raises(external_deck.DeckError, match="could not be read"):
        external_deck._parameters(deck)
