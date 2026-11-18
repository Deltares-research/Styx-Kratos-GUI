"""The stage list: one deck stage per stage, and what each one carries.

Checked against the seven-stage ProjectParameters of Kratos' own staged-construction
reference deck. See plan/outdated/staged-construction-plan.md sec C1, C2, C5.

The compatibility contract runs through this file: a project with no stages must export
exactly the deck it exported before staged construction existed. `test_export_golden.py`
holds that to the letter; the first test here states it.
"""

import json

import pytest

from core.model import stages, schemas
from tests.models import excavation
from core.geometry.solid_model import session
from core.model.schemas import MeshRequest
from core.kratos import writer


@pytest.fixture(scope="module")
def staged_doc() -> dict:
    """The test model with its default seven stages, exported."""
    with session():
        result = writer.export_project(excavation.excavation_project(staged=True),
                                       MeshRequest(**excavation.excavation_project().mesh.model_dump()))
    return json.loads(result["project_parameters"])


@pytest.fixture(scope="module")
def unstaged_doc() -> dict:
    project = excavation.excavation_project(staged=False)
    with session():
        result = writer.export_project(project,
                                       MeshRequest(**project.mesh.model_dump()))
    return json.loads(result["project_parameters"])


def stage_names(doc: dict) -> list[str]:
    return doc["orchestrator"]["settings"]["execution_list"]


def preprocess(doc: dict, name: str) -> dict:
    return doc["stages"][name].get("stage_preprocess", {})


def operation(doc: dict, name: str, kind: str) -> list[str]:
    """The parts named by the Activate/Deactivate operation of `kind`, or []."""
    for op in preprocess(doc, name).get("operations", []):
        if op["name"].endswith(f"{kind}ModelPartOperation"):
            return op["Parameters"]["model_part_name_list"]
    return []


# -- the compatibility contract ----------------------------------------------

def test_a_project_with_no_stages_exports_the_two_stage_deck_it_always_did(unstaged_doc):
    """Nothing about the deck of an unstaged project may change. The stage machinery is
    reached only by a project that has stages; everything written before staged
    construction existed still exports as it did."""
    assert stage_names(unstaged_doc) == ["1_Initial_stage", "2_Wall_installation"]


# -- C1: one stage per stage -------------------------------------------------

def test_a_staged_project_exports_one_stage_per_stage(staged_doc):
    assert stage_names(staged_doc) == [
        "1_Initial_stage", "2_Null_step", "3_SheetPileWall_installation",
        "4_First_excavation", "5_Strut_installation", "6_Second_excavation",
        "7_Third_excavation",
    ]
    assert list(staged_doc["stages"]) == stage_names(staged_doc)


def test_a_stage_is_numbered_and_its_stage_name_sanitised():
    """`1_Initial_stage`, the reference's own shape: the position in the sequence, then
    the stage's name with anything that cannot sit in a filename replaced."""
    from core.kratos.parameters import stage_name
    assert stage_name(0, "Initial stage") == "1_Initial_stage"
    assert stage_name(6, "Third excavation") == "7_Third_excavation"
    assert stage_name(2, "Dig / prop  (2)") == "3_Dig_prop_2"
    assert stage_name(0, "") == "1_Stage"


def test_only_the_first_stage_imports_the_mdpa(staged_doc):
    """A stage's solver imports the mesh after `stage_preprocess` runs, so the modeler
    is what puts the model there in time for stage 1's own deactivation to find it.
    Re-importing later would throw away everything the stages before it did."""
    names = stage_names(staged_doc)
    assert preprocess(staged_doc, names[0])["modelers"]
    for name in names[1:]:
        assert "modelers" not in preprocess(staged_doc, name)


def test_each_stage_carries_its_transition_as_operations(staged_doc):
    """`stage_preprocess` is the stage diff, nothing more: the reference's stage 4
    deactivates the first lift and its interface and says nothing else."""
    names = stage_names(staged_doc)
    assert operation(staged_doc, names[0], "Activate") == []
    off = operation(staged_doc, names[0], "Deactivate")
    assert "PorousDomain.SheetPileWall" in off and "PorousDomain.Strut" in off

    on = operation(staged_doc, names[2], "Activate")
    assert "PorousDomain.SheetPileWall" in on
    assert operation(staged_doc, names[2], "Deactivate") == []


def test_a_stage_that_changes_nothing_writes_no_operations(staged_doc):
    """The null step: the same model, solved again. An empty operations list would be
    noise, and an Activate naming nothing is a process Kratos still has to run."""
    assert preprocess(staged_doc, "2_Null_step") == {}


def test_deactivating_a_soil_body_takes_its_interface_with_it(staged_doc):
    """One drawn `Interface` is eight deck parts, one per soil body it runs against
    (`core/kratos/writer.py:_interface_by_body`). The stage model knows only the one key, so
    export is what pairs the interface with the body: digging out a lift must remove the
    contact against it, or the deck holds a contact element against nothing."""
    off = operation(staged_doc, "4_First_excavation", "Deactivate")
    bodies = [name for name in off if not name.startswith("PorousDomain.Interface")]
    assert len(bodies) == 1
    (body,) = bodies
    assert f"PorousDomain.Interface_{body.split('.')[1]}" in off


# -- C2: per-stage derived lists ---------------------------------------------

def domains(doc: dict, name: str) -> list[str]:
    return doc["stages"][name]["stage_settings"]["solver_settings"][
        "problem_domain_sub_model_part_list"]


def test_the_domain_list_shrinks_as_the_pit_is_dug(staged_doc):
    """`problem_domain_sub_model_part_list` is the active element-carrying parts of that
    stage. In the reference it loses one soil body and one interface per excavation."""
    # One soil body and one interface leave at each of the three excavations, and
    # nothing else does: the list is not monotone overall, because the wall and the
    # strut join it, so the excavations are compared to each other.
    dug = [len(domains(staged_doc, name)) for name in
           ("3_SheetPileWall_installation", "4_First_excavation",
            "6_Second_excavation", "7_Third_excavation")]
    assert dug == [15, 13, 12, 10]
    # The three lifts and their interfaces are gone by the end; the ground under the pit
    # is not -- it is on the dug side of the wall but is never dug.
    assert not [name for name in domains(staged_doc, "7_Third_excavation")
                if "lift" in name]
    assert len([name for name in domains(staged_doc, "1_Initial_stage")
                if "lift" in name]) == 3


def test_the_initial_stage_holds_only_soil(staged_doc):
    """The reference's stage 1 lists its eight soil bodies and nothing else: the wall,
    the anchor and every interface are deactivated before it solves."""
    settled = domains(staged_doc, "1_Initial_stage")
    assert not [name for name in settled if "Interface" in name]
    assert "SheetPileWall" not in settled and "Strut" not in settled


def test_the_wall_joins_the_domain_list_when_it_is_installed(staged_doc):
    assert "SheetPileWall" in domains(staged_doc, "3_SheetPileWall_installation")
    assert "SheetPileWall" not in domains(staged_doc, "2_Null_step")


def test_the_body_domain_list_is_the_domain_list(staged_doc):
    for name in stage_names(staged_doc):
        settings = staged_doc["stages"][name]["stage_settings"]["solver_settings"]
        assert settings["body_domain_sub_model_part_list"] == \
            settings["problem_domain_sub_model_part_list"]


# -- C1: time ----------------------------------------------------------------

def test_the_first_stage_starts_at_time_zero(staged_doc):
    """The K0 stage and the null step included: the clock starts at 0, not at negative
    time as in the reference deck."""
    times = [(staged_doc["stages"][name]["stage_settings"]["problem_data"]["start_time"],
              staged_doc["stages"][name]["stage_settings"]["problem_data"]["end_time"])
             for name in stage_names(staged_doc)]
    assert times == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0),
                     (4.0, 5.0), (5.0, 6.0), (6.0, 7.0)]


@pytest.fixture(scope="module")
def timed_doc() -> dict:
    """The staged model with its stages given durations and time steps of their own."""
    project = excavation.excavation_project(staged=True)
    timing = [(10.0, 10.0), (5.0, 1.0)] + [(100.0, 25.0)] * (len(project.stages) - 2)
    project = project.model_copy(update={"stages": [
        stage.model_copy(update={"duration": duration, "time_step": step})
        for stage, (duration, step) in zip(project.stages, timing)]})
    with session():
        result = writer.export_project(project, MeshRequest(**project.mesh.model_dump()))
    return json.loads(result["project_parameters"])


def test_each_stage_lasts_its_own_duration_and_starts_where_the_last_ended(timed_doc):
    times = [(timed_doc["stages"][name]["stage_settings"]["problem_data"]["start_time"],
              timed_doc["stages"][name]["stage_settings"]["problem_data"]["end_time"])
             for name in stage_names(timed_doc)]
    assert times == [(0.0, 10.0), (10.0, 15.0), (15.0, 115.0), (115.0, 215.0),
                     (215.0, 315.0), (315.0, 415.0), (415.0, 515.0)]


def test_the_initial_stage_sets_the_start_time_of_the_calculation():
    """0 unless the initial stage says otherwise; the rest follow on from it."""
    project = excavation.excavation_project(staged=True)
    first, *rest = project.stages
    project = project.model_copy(update={"stages": [
        first.model_copy(update={"start_time": -2.0}), *rest]})
    with session():
        result = writer.export_project(project, MeshRequest(**project.mesh.model_dump()))
    doc = json.loads(result["project_parameters"])
    starts = [doc["stages"][name]["stage_settings"]["problem_data"]["start_time"]
              for name in stage_names(doc)]
    assert starts == [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0]


def test_a_stage_starts_at_zero_unless_told_otherwise():
    assert schemas.Stage(id="s", name="S").start_time == 0.0


def test_each_stage_is_solved_in_its_own_time_step(timed_doc):
    steps = [solver(timed_doc, name)["time_stepping"]["time_step"]
             for name in stage_names(timed_doc)]
    assert steps == [10.0, 1.0] + [25.0] * 5


def test_a_stage_writes_its_json_output_once_however_long_it_lasts(timed_doc):
    """A shade under the stage's duration, as the reference's is a shade under its one
    second (`parameters._json_output`)."""
    for name in stage_names(timed_doc)[2:]:
        for process in timed_doc["stages"][name]["stage_settings"]["processes"].get(
                "json_output", []):
            assert 99.9 < process["Parameters"]["time_frequency"] < 100.0


def test_a_time_step_longer_than_its_stage_is_refused():
    with pytest.raises(ValueError, match="time step"):
        schemas.Stage(id="s", name="S", duration=1.0, time_step=2.0)


def test_a_stage_saved_with_a_time_interval_in_days_lasts_it_in_seconds():
    """Before 2026-11 a stage had a time interval in days, which no deck read. A zero
    one -- every stage the GUI made -- is the default stage, of 1 s in one step; any
    other one is its seconds, in one step, as it always ran."""
    assert (schemas.Stage(id="s", name="S", time_interval=0.0).duration,
            schemas.Stage(id="s", name="S", time_interval=0.0).time_step) == (1.0, 1.0)
    old = schemas.Stage(id="s", name="S", time_interval=2.0)
    assert (old.duration, old.time_step) == (2 * 86400.0, 2 * 86400.0)


def test_an_unstaged_deck_still_starts_at_zero(unstaged_doc):
    first = unstaged_doc["stages"]["1_Initial_stage"]["stage_settings"]["problem_data"]
    assert (first["start_time"], first["end_time"]) == (0.0, 1.0)


# -- C5: per-stage solver settings -------------------------------------------

def solver(doc: dict, name: str) -> dict:
    return doc["stages"][name]["stage_settings"]["solver_settings"]


def test_each_stage_solves_with_its_own_stages_numbers(staged_doc):
    """The reference varies exactly three things between stages. They come off the stage
    record rather than being hardcoded here."""
    assert solver(staged_doc, "1_Initial_stage")["max_iterations"] == 15
    assert solver(staged_doc, "2_Null_step")["max_iterations"] == 150
    assert solver(staged_doc, "4_First_excavation")[
        "residual_relative_tolerance"] == 1e-3


def test_displacements_reset_in_the_stage_that_installs_the_wall(staged_doc):
    resetting = [name for name in stage_names(staged_doc)
                 if solver(staged_doc, name)["reset_totals"]]
    assert resetting == ["3_SheetPileWall_installation"]


def test_a_stages_solver_settings_reach_the_deck():
    """Not through the defaults: a number typed into the stage editor has to arrive."""
    project = excavation.excavation_project(staged=True)
    edited = [ph.model_dump() for ph in project.stages]
    edited[3] |= {"max_iterations": 321, "tolerated_error": 2e-3}
    project = schemas.Project.model_validate(project.model_dump() | {"stages": edited})
    with session():
        doc = json.loads(writer.export_project(
            project, MeshRequest(**project.mesh.model_dump()))["project_parameters"])
    assert solver(doc, "4_First_excavation")["max_iterations"] == 321
    assert solver(doc, "4_First_excavation")["residual_relative_tolerance"] == 2e-3


@pytest.mark.parametrize("criterion, measured", [
    ("residual_criterion", "residual"), ("displacement_criterion", "displacement")])
def test_a_stages_convergence_criterion_reaches_the_deck(criterion, measured):
    """The criterion the stage chose, and its two tolerances on the quantity the
    criterion measures -- and no tolerance of a quantity it does not."""
    project = excavation.excavation_project(staged=True)
    edited = [ph.model_dump() for ph in project.stages]
    edited[3] |= {"convergence_criterion": criterion, "tolerated_error": 2e-3,
                  "absolute_tolerance": 1e-7}
    project = schemas.Project.model_validate(project.model_dump() | {"stages": edited})
    with session():
        doc = json.loads(writer.export_project(
            project, MeshRequest(**project.mesh.model_dump()))["project_parameters"])
    settings = solver(doc, "4_First_excavation")
    assert settings["convergence_criterion"] == criterion
    tolerances = {key: value for key, value in settings.items()
                  if key.endswith(("_relative_tolerance", "_absolute_tolerance"))}
    assert tolerances == {f"{measured}_relative_tolerance": 2e-3,
                          f"{measured}_absolute_tolerance": 1e-7}
    # The stages around it keep the default.
    assert solver(doc, "1_Initial_stage")["convergence_criterion"] == "residual_criterion"


# -- refusals ----------------------------------------------------------------

def test_a_branching_stage_tree_is_refused_at_export():
    """Kratos runs one sequence. The schema accepts the branch so it can be half-built
    in the editor; this is where it stops."""
    project = excavation.excavation_project(staged=True)
    records = [ph.model_dump() for ph in project.stages]
    records.append(dict(records[-1], id="alternative", parent=records[2]["id"]))
    project = schemas.Project.model_validate(project.model_dump() | {"stages": records})
    with pytest.raises(stages.StageError, match="alternative"):
        with session():
            writer.export_project(project, MeshRequest(**project.mesh.model_dump()))


def test_a_project_with_one_stage_imports_its_mesh_once():
    """The first stage of a staged deck reads the .mdpa through its modeler; its solver
    must then use that model, not read the file again -- even when it is the only stage.
    It used to say `input_type: "mdpa"` whenever there was a single stage, so a one-stage
    project (a K0 column) imported every element twice and Kratos stopped at element 1."""
    import json as _json

    from core.geometry import solid_model
    from core.kratos import writer
    from core.model.schemas import MeshRequest
    from benchmarks import models

    project = models.project()
    with solid_model.session():
        export = writer.export_project(project, MeshRequest(element_size=1.0, order=1))
    (stage,) = _json.loads(export["project_parameters"])["stages"].values()
    modelers = stage.get("stage_preprocess", {}).get("modelers", [])
    reads = len(modelers) + (stage["stage_settings"]["solver_settings"]
                             ["model_import_settings"]["input_type"] == "mdpa")
    assert reads == 1
