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
