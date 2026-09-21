"""Running an exported deck through Kratos.

Kratos itself is not exercised here: it is a separate interpreter with a compiled build
behind it, present on the machine that runs analyses and not on one that only runs the
tests. What is exercised is everything around it -- the directory a run gets, the files
written into it, the command and environment the interpreter is handed, and what comes
back from a run that worked and one that did not -- with a stand-in interpreter (this
one, running a one-line script) in Kratos' place.
"""

import json
import sys
from pathlib import Path

import pytest

from app import calculate

DECK = {
    "deck_name": "Test_model",
    "mdpa": "Begin Properties 0\nEnd Properties\n",
    "materials": json.dumps({"properties": []}),
    "project_parameters": json.dumps({"orchestrator": {}, "stages": {}}),
    "stats": {"nodes": 3, "elements": 1},
    "warnings": [],
}


@pytest.fixture(autouse=True)
def unconfigured_machine(tmp_path, monkeypatch):
    """No machine's own settings, whichever machine this is.

    `server/kratos.local.json` is real on a machine that runs analyses, and it would
    otherwise reach into every case below -- putting a Kratos build on the stand-in
    interpreter's path and making failures here depend on whose checkout is running.
    """
    monkeypatch.setattr(calculate, "SETTINGS_FILE", tmp_path / "no-settings.json")
    monkeypatch.delenv(calculate.PYTHON_ENV, raising=False)
    monkeypatch.delenv(calculate.KRATOS_ENV, raising=False)


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setenv(calculate.RUNS_ENV, str(tmp_path / "runs"))
    return tmp_path / "runs"


# ── Where a run lands ───────────────────────────────────────────────────────

def test_the_runs_root_can_be_pointed_somewhere_else(runs):
    assert calculate.runs_root() == runs


def test_two_runs_of_one_project_never_share_a_directory(runs):
    first = calculate.new_run_directory("Test_model")
    second = calculate.new_run_directory("Test_model")

    assert first != second
    assert first.parent == runs and first.is_dir() and second.is_dir()
    assert first.name.startswith("Test_model")


# ── The files it writes ─────────────────────────────────────────────────────

def test_the_three_input_files_are_written_under_the_deck_name(tmp_path):
    written = calculate.write_deck(DECK, tmp_path)

    assert written == ["Test_model.mdpa", "MaterialParameters.json",
                       "ProjectParameters.json"]
    assert (tmp_path / "Test_model.mdpa").read_text(encoding="utf-8") == DECK["mdpa"]
    assert json.loads((tmp_path / "ProjectParameters.json").read_text(encoding="utf-8"))


def test_the_mdpa_is_named_exactly_what_the_parameters_ask_kratos_for(tmp_path):
    """`model_import_settings.input_filename` plus `.mdpa` is how Kratos finds the
    mesh; a file named anything else is a run that stops on its first line."""
    deck = dict(DECK, project_parameters=json.dumps({
        "stages": {"1_Stage": {"stage_settings": {"solver_settings": {
            "model_import_settings": {"input_type": "mdpa",
                                      "input_filename": "Test_model"}}}}},
    }))
    calculate.write_deck(deck, tmp_path)

    assert (tmp_path / "Test_model.mdpa").exists()


# ── The interpreter it hands them to ────────────────────────────────────────

def test_the_kratos_build_is_put_on_both_paths(monkeypatch, tmp_path):
    """Kratos is two halves: python packages under the build directory, and the DLLs
    they load beside them in `libs`. One on PYTHONPATH, the other on PATH, or the
    import fails on the compiled half with the python half in hand."""
    build = tmp_path / "bin" / "Release"
    (build / "libs").mkdir(parents=True)
    monkeypatch.setenv(calculate.KRATOS_ENV, str(build))

    _, environment = calculate.interpreter()

    assert str(build) in environment["PYTHONPATH"].split(";")
    assert str(build / "libs") in environment["PATH"].split(";")


def test_the_server_is_on_the_path_so_the_runner_can_be_imported(monkeypatch):
    """The runner is `app.kratos_runner`, run by an interpreter that has never heard of
    this project."""
    monkeypatch.delenv(calculate.KRATOS_ENV, raising=False)

    _, environment = calculate.interpreter()

    assert str(calculate.SERVER) in environment["PYTHONPATH"].split(";")


def test_the_machine_can_be_configured_in_a_file_instead_of_the_environment(
        monkeypatch, tmp_path):
    """Environment variables are set per shell, and this server is started by
    double-clicking run.bat. A settings file beside it is set once and stays set."""
    build = tmp_path / "bin" / "Release"
    (build / "libs").mkdir(parents=True)
    python = tmp_path / "python.exe"
    python.touch()
    settings = tmp_path / "kratos.local.json"
    settings.write_text(json.dumps({"python": str(python), "kratos": str(build)}),
                        encoding="utf-8")
    monkeypatch.setattr(calculate, "SETTINGS_FILE", settings)
    monkeypatch.delenv(calculate.PYTHON_ENV, raising=False)
    monkeypatch.delenv(calculate.KRATOS_ENV, raising=False)

    interpreter, environment = calculate.interpreter()

    assert interpreter == str(python)
    assert str(build) in environment["PYTHONPATH"].split(";")


def test_the_environment_still_wins_over_the_file(monkeypatch, tmp_path):
    settings = tmp_path / "kratos.local.json"
    settings.write_text(json.dumps({"python": "C:/nowhere/python.exe"}), encoding="utf-8")
    monkeypatch.setattr(calculate, "SETTINGS_FILE", settings)
    monkeypatch.setenv(calculate.PYTHON_ENV, sys.executable)

    assert calculate.interpreter()[0] == sys.executable


def test_a_settings_file_that_is_missing_or_broken_is_not_fatal(monkeypatch, tmp_path):
    """It is optional, and an interpreter that can import Kratos itself needs none of
    it. A typo in it must not take the button down with it."""
    broken = tmp_path / "kratos.local.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(calculate, "SETTINGS_FILE", broken)
    monkeypatch.delenv(calculate.PYTHON_ENV, raising=False)

    assert calculate.interpreter()[0] == sys.executable

    monkeypatch.setattr(calculate, "SETTINGS_FILE", tmp_path / "absent.json")
    assert calculate.interpreter()[0] == sys.executable


def test_a_configured_interpreter_that_is_not_there_is_reported_not_guessed(monkeypatch):
    monkeypatch.setenv(calculate.PYTHON_ENV, "C:/nowhere/python.exe")

    with pytest.raises(calculate.CalculationError) as failure:
        calculate.interpreter()

    assert calculate.PYTHON_ENV in str(failure.value)


# ── A run, with this interpreter standing in for Kratos ─────────────────────

def stand_in(monkeypatch, script: str) -> None:
    """Run `script` in place of the Kratos runner, in the deck's own directory."""
    monkeypatch.setattr(calculate, "COMMAND", ["-c", script])
    monkeypatch.setenv(calculate.PYTHON_ENV, sys.executable)


def test_a_run_that_works_reports_where_the_results_are(runs, monkeypatch):
    stand_in(monkeypatch, "open('Test_model_1_Stage.post.res', 'w').close()")

    result = calculate.run(DECK)

    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "Test_model_1_Stage.post.res" in result["outputs"]
    assert Path(result["directory"]).is_dir()
    assert (Path(result["directory"]) / calculate.LOG_NAME).exists()


def test_the_inputs_are_not_reported_as_results(runs, monkeypatch):
    """`outputs` is what the run produced, so that the message can say where the
    results went without naming the three files the user already has."""
    stand_in(monkeypatch, "open('Test_model_1_Stage.post.res', 'w').close()")

    result = calculate.run(DECK)

    assert set(result["inputs"]).isdisjoint(result["outputs"])
    assert calculate.LOG_NAME not in result["outputs"]


def test_a_failed_run_comes_back_with_what_kratos_said(runs, monkeypatch):
    stand_in(monkeypatch, "import sys; print('Error: no such sub model part'); "
                          "sys.exit(1)")

    result = calculate.run(DECK)

    assert result["ok"] is False
    assert result["returncode"] == 1
    assert "no such sub model part" in result["error"]
    log = (Path(result["directory"]) / calculate.LOG_NAME).read_text(encoding="utf-8")
    assert "no such sub model part" in log


def test_a_missing_kratos_is_explained_rather_than_left_as_a_traceback(
        runs, monkeypatch):
    """The one failure that is configuration rather than modelling, and the one a
    traceback about an import is least likely to tell someone how to fix."""
    stand_in(monkeypatch, "import KratosMultiphysics")

    result = calculate.run(DECK)

    assert result["ok"] is False
    assert calculate.SETTINGS_FILE.name in result["error"]


def test_a_kratos_the_interpreter_cannot_load_is_explained_too(runs, monkeypatch):
    """Half-configured is its own failure, and the likelier one: the build directory is
    right, so `KratosMultiphysics` imports, and then its compiled half does not load --
    an interpreter of the wrong version, or `libs` missing from PATH. Kratos says
    "Unable to find KratosCore", which names neither cause."""
    stand_in(monkeypatch, "import sys; "
                          "print('Unable to find KratosCore.'); sys.exit(1)")

    result = calculate.run(DECK)

    assert result["ok"] is False
    assert "version" in result["error"], "the likeliest cause is named"
    assert calculate.SETTINGS_FILE.name in result["error"]


def test_only_one_calculation_runs_at_a_time(runs, monkeypatch):
    """One gmsh worker, one machine, and a solver that wants the cores. A second press
    is refused rather than queued behind a run whose length nobody knows."""
    stand_in(monkeypatch, "pass")
    monkeypatch.setattr(calculate, "_running", True)

    with pytest.raises(calculate.CalculationError):
        calculate.run(DECK)


# ── Which stage failed ──────────────────────────────────────────────────────
# "It failed" and "phase 5 failed" are a very different message on a seven-stage deck,
# and the deck has no stage banner of its own to read: `SequentialOrchestrator.Run`
# loops over the execution list printing nothing that names the stage. Checked against
# Kratos' own source and against a real seven-stage run log, not inferred -- see
# plan sec 7.8 for why that distinction is written down.
#
# So the markers are ours. `kratos_runner` subclasses the orchestrator and announces
# each stage from the two public per-stage hooks; everything below parses what it
# prints, which is why none of it needs Kratos.

def marker(event: str, index: int, total: int, name: str) -> str:
    return f"{calculate.STAGE_MARKER} {event} {index}/{total} {name}"


def test_no_markers_means_nothing_to_say():
    """Every deck written before this existed, and every failure before the first
    stage was reached -- a deck Kratos could not even read."""
    assert calculate.failed_stage("Error: something went wrong") is None
    assert calculate.failed_stage("") is None


def test_the_stage_that_began_and_never_ended_is_the_one_that_failed():
    output = "\n".join([
        marker("begin", 1, 7, "1_Initial_stage"),
        marker("end", 1, 7, "1_Initial_stage"),
        marker("begin", 2, 7, "2_Null_step"),
        marker("end", 2, 7, "2_Null_step"),
        marker("begin", 3, 7, "3_SheetPileWall_installation"),
        "RuntimeError: Error: Reference distance close to zero.",
    ])
    assert calculate.failed_stage(output) == (3, 7, "3_SheetPileWall_installation")


def test_a_run_where_every_stage_ended_blames_none_of_them():
    """The deck finished. Whatever went wrong after that is not a stage's fault, and
    naming the last one would be a lie."""
    output = "\n".join([marker("begin", 1, 2, "a"), marker("end", 1, 2, "a"),
                        marker("begin", 2, 2, "b"), marker("end", 2, 2, "b")])
    assert calculate.failed_stage(output) is None


def test_a_failure_in_the_very_first_stage_is_named(): 
    output = marker("begin", 1, 7, "1_Initial_stage") + "\nboom"
    assert calculate.failed_stage(output) == (1, 7, "1_Initial_stage")


def test_a_stage_name_may_contain_spaces():
    """`Stage.name` comes from `Phase.name`, which the user types."""
    output = marker("begin", 2, 3, "Dig to -4.5 m")
    assert calculate.failed_stage(output) == (2, 3, "Dig to -4.5 m")


def test_the_markers_do_not_have_to_be_alone_on_their_line():
    """Kratos writes from C++ and from Python into the same pipe, and the two
    interleave -- a marker can arrive with someone else's half-line in front of it."""
    output = "BuilderAndSolver: Clear Function called " + marker("begin", 2, 3, "b")
    assert calculate.failed_stage(output) == (2, 3, "b")


def test_the_failure_explanation_names_the_stage(runs, monkeypatch):
    """The whole point of the exercise, end to end through `run`."""
    script = (
        "import sys;"
        f"print({marker('begin', 1, 2, '1_Initial_stage')!r});"
        f"print({marker('end', 1, 2, '1_Initial_stage')!r});"
        f"print({marker('begin', 2, 2, '2_Dig')!r});"
        "print('Error: Reference distance close to zero.');"
        "sys.exit(1)"
    )
    stand_in(monkeypatch, script)

    result = calculate.run(DECK)

    assert result["ok"] is False
    assert result["stage"] == {"index": 2, "of": 2, "name": "2_Dig"}
    assert "2_Dig" in result["error"]
    assert "stage 2 of 2" in result["error"]
    # Kratos' own reason survives; the stage is added in front of it, not instead.
    assert "Reference distance close to zero" in result["error"]


def test_a_run_that_works_reports_no_failed_stage(runs, monkeypatch):
    stand_in(monkeypatch, f"print({marker('begin', 1, 1, '1_Stage')!r});"
                          f"print({marker('end', 1, 1, '1_Stage')!r})")

    result = calculate.run(DECK)

    assert result["ok"] is True
    assert result["stage"] is None


def test_the_stage_markers_are_kept_out_of_the_tail_shown_to_the_user():
    """They are scaffolding, not output. Thirty lines of them would push Kratos' own
    reason off the end of the message they exist to improve."""
    noise = [marker("begin", n, 40, f"{n}_Stage") for n in range(1, 40)]
    output = "\n".join(noise + ["Error: the thing that actually went wrong"])

    explained = calculate._explain(output)

    assert "the thing that actually went wrong" in explained
    assert calculate.STAGE_MARKER not in explained


# ── The markers at the other end: kratos_runner's orchestrator wrapper ──────
# `app.kratos_runner` is a script for Kratos' interpreter, but it imports Kratos only
# inside `run()`, so the wrapper itself is ordinary Python and testable here against a
# stand-in base class. What the stand-in reproduces is the contract read off Kratos'
# own `Orchestrator`: `RunCurrentStagePreprocess(stage_name, data=None)` before each
# stage, `RunCurrentStagePostprocess(stage_name, data=None)` after it, and
# `GetNumberOfStages()`.

class FakeOrchestrator:
    """Kratos' `Orchestrator`, as far as the wrapper is concerned."""

    def __init__(self, stages):
        self.stages = stages
        self.calls = []

    def GetNumberOfStages(self):
        return len(self.stages)

    def RunCurrentStagePreprocess(self, stage_name, data=None):
        self.calls.append(("pre", stage_name))

    def RunCurrentStagePostprocess(self, stage_name, data=None):
        self.calls.append(("post", stage_name))

    def Run(self):
        for name in self.stages:
            self.RunCurrentStagePreprocess(name)
            self.RunCurrentStagePostprocess(name)


def test_the_wrapper_announces_every_stage_in_order(capsys):
    from app import kratos_runner

    kratos_runner.announcing(FakeOrchestrator)(["a", "b", "c"]).Run()

    printed = capsys.readouterr().out.strip().splitlines()
    assert printed == [
        f"{kratos_runner.STAGE_MARKER} begin 1/3 a",
        f"{kratos_runner.STAGE_MARKER} end 1/3 a",
        f"{kratos_runner.STAGE_MARKER} begin 2/3 b",
        f"{kratos_runner.STAGE_MARKER} end 2/3 b",
        f"{kratos_runner.STAGE_MARKER} begin 3/3 c",
        f"{kratos_runner.STAGE_MARKER} end 3/3 c",
    ]


def test_the_wrapper_still_does_the_base_class_work(capsys):
    """It announces around Kratos' own hooks, it does not replace them. Dropping the
    super() call would silently stop every Activate and Deactivate operation, which is
    the whole of staged construction."""
    from app import kratos_runner

    orchestrator = kratos_runner.announcing(FakeOrchestrator)(["a", "b"])
    orchestrator.Run()

    assert orchestrator.calls == [("pre", "a"), ("post", "a"),
                                  ("pre", "b"), ("post", "b")]


def test_begin_is_printed_before_the_preprocess_runs(capsys):
    """The preprocess is itself a place a deck fails -- it is where the Activate and
    Deactivate operations execute, so a phase naming a part the mdpa does not carry
    throws there. Announced after it, that failure would be blamed on the stage
    before."""
    from app import kratos_runner

    class Exploding(FakeOrchestrator):
        def RunCurrentStagePreprocess(self, stage_name, data=None):
            raise RuntimeError("no such sub model part")

    with pytest.raises(RuntimeError):
        kratos_runner.announcing(Exploding)(["a", "b"]).Run()

    assert f"{kratos_runner.STAGE_MARKER} begin 1/2 a" in capsys.readouterr().out


def test_the_two_ends_agree_on_the_marker(capsys):
    """The round trip: what the runner prints is what `calculate` reads. They share
    the constant, but not the format string, and a change to one is only caught here."""
    from app import kratos_runner

    class Failing(FakeOrchestrator):
        def Run(self):
            self.RunCurrentStagePreprocess("1_Initial")
            self.RunCurrentStagePostprocess("1_Initial")
            self.RunCurrentStagePreprocess("2_Dig to -4.5 m")
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        kratos_runner.announcing(Failing)(["1_Initial", "2_Dig to -4.5 m"]).Run()

    assert calculate.failed_stage(capsys.readouterr().out) == (2, 2, "2_Dig to -4.5 m")
