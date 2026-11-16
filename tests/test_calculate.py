"""Running an exported deck through Kratos.

Kratos itself is not exercised here: it is a separate interpreter with a compiled build
behind it, present on the machine that runs analyses and not on one that only runs the
tests. What is exercised is everything around it -- the directory a run gets, the files
written into it, the command and environment the interpreter is handed, and what comes
back from a run that worked and one that did not -- with a stand-in interpreter (this
one, running a one-line script) in Kratos' place.
"""

import json
import os
import sys
from pathlib import Path

import pytest

from core.kratos import writer, mdpa_reader
from core.analysis import calculation

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

    `kratos.local.json` is real on a machine that runs analyses, and it would
    otherwise reach into every case below -- putting a Kratos build on the stand-in
    interpreter's path and making failures here depend on whose checkout is running.
    """
    monkeypatch.setattr(calculation, "SETTINGS_FILE", tmp_path / "no-settings.json")
    monkeypatch.delenv(calculation.PYTHON_ENV, raising=False)
    monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path / "runs"))
    return tmp_path / "runs"


# ── Where a run lands ───────────────────────────────────────────────────────

def test_the_runs_root_can_be_pointed_somewhere_else(runs):
    assert calculation.runs_root() == runs


def test_two_runs_of_one_project_never_share_a_directory(runs):
    first = calculation.new_run_directory("Test_model")
    second = calculation.new_run_directory("Test_model")

    assert first != second
    assert first.parent == runs and first.is_dir() and second.is_dir()
    assert first.name.startswith("Test_model")


# ── The files it writes ─────────────────────────────────────────────────────

def test_the_three_input_files_are_written_under_the_deck_name(tmp_path):
    written = calculation.write_deck(DECK, tmp_path)

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
    calculation.write_deck(deck, tmp_path)

    assert (tmp_path / "Test_model.mdpa").exists()


def test_the_deck_lands_on_disk_as_the_bytes_it_was_rendered_as(tmp_path):
    r"""An .mdpa is written with CRLF endings on purpose -- `writer.LINE_END` keeps the
    deck byte-comparable with the GiD-authored references it is checked against.
    Writing it in text mode on Windows then translates the "\n" of each of those pairs
    a second time, and every line lands as "\r\r\n".

    Kratos tolerates it, which is why seven real runs went green over a malformed deck;
    nothing else does. `core.kratos.mdpa_reader` reads every second line as blank, and a file
    that cannot be read back by the program that wrote it is a bug whether or not the
    solver minded.
    """
    body = "Begin Nodes" + writer.LINE_END + "    1 0.0 0.0 0.0" + writer.LINE_END \
           + "End Nodes" + writer.LINE_END

    calculation.write_deck(dict(DECK, mdpa=body), tmp_path)

    written = (tmp_path / "Test_model.mdpa").read_bytes()
    assert b"\r\r\n" not in written
    assert written == body.encode("utf-8")


def test_a_written_deck_can_be_read_back_by_this_project(tmp_path):
    """The end-to-end form of the case above, and the one that actually bit: the
    postprocessor reads the .mdpa beside the results to learn which elements belong to
    which part, and it could not read one this project had written."""
    mdpa = writer.LINE_END.join([
        "Begin Properties 0", "End Properties", "",
        "Begin Nodes", "    1   0.0   0.0   0.0", "    2   1.0   0.0   0.0",
        "    3   0.0   1.0   0.0", "End Nodes", "",
        "Begin Elements UPwSmallStrainElement2D3N", "    1  1  1  2  3",
        "End Elements", "",
        "Begin SubModelPart Soil_Top", "    Begin SubModelPartElements", "    1",
        "    End SubModelPartElements", "End SubModelPart", "",
    ])
    calculation.write_deck(dict(DECK, mdpa=mdpa), tmp_path)

    model = mdpa_reader.import_mdpa(
        (tmp_path / "Test_model.mdpa").read_text(encoding="utf-8"))

    assert len(model.nodes) == 3
    assert model.parts["Soil_Top"].elements == [1]


# ── The interpreter it hands them to ────────────────────────────────────────

def test_the_kratos_build_is_put_on_both_paths(monkeypatch, tmp_path):
    """Kratos is two halves: python packages under the build directory, and the DLLs
    they load beside them in `libs`. One on PYTHONPATH, the other on PATH, or the
    import fails on the compiled half with the python half in hand."""
    build = tmp_path / "bin" / "Release"
    (build / "libs").mkdir(parents=True)
    monkeypatch.setenv(calculation.KRATOS_ENV, str(build))

    _, environment = calculation.interpreter()

    assert str(build) in environment["PYTHONPATH"].split(os.pathsep)
    assert str(build / "libs") in environment["PATH"].split(os.pathsep)


def repository_root() -> Path:
    """The checkout's root, the folder `tools/test.py` is in: found by walking up, so it
    is the same answer wherever this file sits."""
    here = Path(__file__).resolve()
    return next(folder for folder in here.parents
                if (folder / "tools" / "test.py").is_file())


def test_the_runner_is_named_as_a_module_of_core():
    """A module name rather than a file path, so it reads the same wherever the
    repository is checked out. `core` is the package Kratos' interpreter imports."""
    assert calculation.COMMAND == ["-m", "core.analysis.kratos_main", "ProjectParameters.json"]


def test_the_repository_root_is_on_the_path_so_the_runner_can_be_imported(monkeypatch):
    """The runner is `core.analysis.kratos_main`, run by an interpreter that has never heard of
    this project. `core` is a folder at the repository's root, so the root is what
    has to be on its path."""
    monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)

    _, environment = calculation.interpreter()

    assert str(repository_root()) in environment["PYTHONPATH"].split(os.pathsep)


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
    monkeypatch.setattr(calculation, "SETTINGS_FILE", settings)
    monkeypatch.delenv(calculation.PYTHON_ENV, raising=False)
    monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)

    interpreter, environment = calculation.interpreter()

    assert interpreter == str(python)
    assert str(build) in environment["PYTHONPATH"].split(os.pathsep)


def test_the_environment_still_wins_over_the_file(monkeypatch, tmp_path):
    settings = tmp_path / "kratos.local.json"
    settings.write_text(json.dumps({"python": "C:/nowhere/python.exe"}), encoding="utf-8")
    monkeypatch.setattr(calculation, "SETTINGS_FILE", settings)
    monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)

    assert calculation.interpreter()[0] == sys.executable


def test_a_settings_file_that_is_missing_or_broken_is_not_fatal(monkeypatch, tmp_path):
    """It is optional, and an interpreter that can import Kratos itself needs none of
    it. A typo in it must not take the button down with it."""
    broken = tmp_path / "kratos.local.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(calculation, "SETTINGS_FILE", broken)
    monkeypatch.delenv(calculation.PYTHON_ENV, raising=False)

    assert calculation.interpreter()[0] == sys.executable

    monkeypatch.setattr(calculation, "SETTINGS_FILE", tmp_path / "absent.json")
    assert calculation.interpreter()[0] == sys.executable


def test_a_configured_interpreter_that_is_not_there_is_reported_not_guessed(monkeypatch):
    monkeypatch.setenv(calculation.PYTHON_ENV, "C:/nowhere/python.exe")

    with pytest.raises(calculation.CalculationError) as failure:
        calculation.interpreter()

    assert calculation.PYTHON_ENV in str(failure.value)


# ── A run, with this interpreter standing in for Kratos ─────────────────────

def stand_in(monkeypatch, script: str) -> None:
    """Run `script` in place of the Kratos runner, in the deck's own directory."""
    monkeypatch.setattr(calculation, "COMMAND", ["-c", script])
    monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)


def test_a_run_that_works_reports_where_the_results_are(runs, monkeypatch):
    stand_in(monkeypatch, "open('Test_model_1_Stage.post.res', 'w').close()")

    result = calculation.run(DECK)

    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "Test_model_1_Stage.post.res" in result["outputs"]
    assert Path(result["directory"]).is_dir()
    assert (Path(result["directory"]) / calculation.LOG_NAME).exists()


def test_the_inputs_are_not_reported_as_results(runs, monkeypatch):
    """`outputs` is what the run produced, so that the message can say where the
    results went without naming the three files the user already has."""
    stand_in(monkeypatch, "open('Test_model_1_Stage.post.res', 'w').close()")

    result = calculation.run(DECK)

    assert set(result["inputs"]).isdisjoint(result["outputs"])
    assert calculation.LOG_NAME not in result["outputs"]


def test_a_failed_run_comes_back_with_what_kratos_said(runs, monkeypatch):
    stand_in(monkeypatch, "import sys; print('Error: no such sub model part'); "
                          "sys.exit(1)")

    result = calculation.run(DECK)

    assert result["ok"] is False
    assert result["returncode"] == 1
    assert "no such sub model part" in result["error"]
    log = (Path(result["directory"]) / calculation.LOG_NAME).read_text(encoding="utf-8")
    assert "no such sub model part" in log


def test_a_missing_kratos_is_explained_rather_than_left_as_a_traceback(
        runs, monkeypatch):
    """The one failure that is configuration rather than modelling, and the one a
    traceback about an import is least likely to tell someone how to fix."""
    stand_in(monkeypatch, "raise ModuleNotFoundError(\"No module named 'KratosMultiphysics'\")")

    result = calculation.run(DECK)

    assert result["ok"] is False
    assert calculation.SETTINGS_FILE.name in result["error"]


def test_a_kratos_the_interpreter_cannot_load_is_explained_too(runs, monkeypatch):
    """Half-configured is its own failure, and the likelier one: the build directory is
    right, so `KratosMultiphysics` imports, and then its compiled half does not load --
    an interpreter of the wrong version, or `libs` missing from PATH. Kratos says
    "Unable to find KratosCore", which names neither cause."""
    stand_in(monkeypatch, "import sys; "
                          "print('Unable to find KratosCore.'); sys.exit(1)")

    result = calculation.run(DECK)

    assert result["ok"] is False
    assert "version" in result["error"], "the likeliest cause is named"
    assert calculation.SETTINGS_FILE.name in result["error"]


def test_only_one_calculation_runs_at_a_time(runs, monkeypatch):
    """One gmsh worker, one machine, and a solver that wants the cores. A second press
    is refused rather than queued behind a run whose length nobody knows."""
    stand_in(monkeypatch, "pass")
    monkeypatch.setattr(calculation, "_running", True)

    with pytest.raises(calculation.CalculationError):
        calculation.run(DECK)


def test_two_presses_at_the_same_moment_start_one_run(runs, monkeypatch):
    """The route runs `run` on a worker thread, so two presses are two threads. Both
    must not get past the check before either has claimed the machine."""
    import threading
    stand_in(monkeypatch, "pass")
    both_inside = threading.Barrier(2, timeout=2)
    write_deck = calculation.write_deck

    def slow_write(export, directory):
        try:
            both_inside.wait()
        except threading.BrokenBarrierError:
            pass
        return write_deck(export, directory)

    monkeypatch.setattr(calculation, "write_deck", slow_write)
    outcomes = []

    def press():
        try:
            outcomes.append(calculation.run(DECK)["ok"])
        except calculation.Busy:
            outcomes.append("busy")

    threads = [threading.Thread(target=press) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes, key=str) == [True, "busy"]
    assert len(list(runs.iterdir())) == 1


# ── Runs that never get going ───────────────────────────────────────────────

def test_an_interpreter_that_is_a_directory_is_reported_not_crashed_on(
        runs, monkeypatch, tmp_path):
    """Pointing "python" at the venv instead of the python.exe inside it is the easy
    mistake. It exists, so it got past the check, and then failed to start as a bare
    OSError -- a 500 that says nothing."""
    monkeypatch.setenv(calculation.PYTHON_ENV, str(tmp_path))

    with pytest.raises(calculation.CalculationError) as failure:
        calculation.run(DECK)

    assert str(tmp_path) in str(failure.value)
    assert calculation.PYTHON_ENV in str(failure.value)


def test_an_interpreter_that_will_not_start_is_reported(runs, monkeypatch, tmp_path):
    not_a_program = tmp_path / "python.txt"
    not_a_program.write_text("not a program", encoding="utf-8")
    monkeypatch.setenv(calculation.PYTHON_ENV, str(not_a_program))

    with pytest.raises(calculation.CalculationError) as failure:
        calculation.run(DECK)

    assert str(not_a_program) in str(failure.value)
    # And the button works again afterwards.
    stand_in(monkeypatch, "pass")
    assert calculation.run(DECK)["ok"] is True


def test_a_runs_directory_that_cannot_be_made_is_reported(monkeypatch, tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv(calculation.RUNS_ENV, str(blocker / "runs"))
    stand_in(monkeypatch, "pass")

    with pytest.raises(calculation.CalculationError) as failure:
        calculation.run(DECK)

    assert calculation.RUNS_ENV in str(failure.value)


def test_a_deck_that_cannot_be_written_frees_the_button(runs, monkeypatch):
    stand_in(monkeypatch, "pass")
    write_deck = calculation.write_deck

    def disk_full(export, directory):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(calculation, "write_deck", disk_full)
    with pytest.raises(calculation.CalculationError, match="No space left"):
        calculation.run(DECK)

    monkeypatch.setattr(calculation, "write_deck", write_deck)
    assert calculation.run(DECK)["ok"] is True


# ── A run that takes too long ───────────────────────────────────────────────

def test_a_run_past_the_timeout_is_given_up_on_and_says_where(runs, monkeypatch):
    monkeypatch.setenv(calculation.TIMEOUT_ENV, "1")
    stand_in(monkeypatch,
             f"import time; print({marker('begin', 1, 2, '1_Initial')!r}, flush=True);"
             "time.sleep(30)")

    result = calculation.run(DECK)

    assert result["ok"] is False
    assert result["returncode"] is None
    assert result["seconds"] < 20
    assert "Given up on after 1 s" in result["error"]
    assert calculation.TIMEOUT_ENV in result["error"]
    assert result["stage"] == {"index": 1, "of": 2, "name": "1_Initial"}
    log = (Path(result["directory"]) / calculation.LOG_NAME).read_text(encoding="utf-8")
    assert "1_Initial" in log and "Given up on" in log

    stand_in(monkeypatch, "pass")
    assert calculation.run(DECK)["ok"] is True, "the button is free again"


def test_a_timeout_keeps_a_half_written_last_line(runs, monkeypatch):
    """What Kratos printed before it was killed is kept, a last line with no newline
    and a letter outside ASCII too: that line is often the one that says why."""
    monkeypatch.setenv(calculation.TIMEOUT_ENV, "1")
    stand_in(monkeypatch,
             "import sys, time;"
             f"print({marker('begin', 2, 3, '2_Dig')!r}, flush=True);"
             "sys.stdout.buffer.write('half a l\\xe9ne'.encode('utf-8'));"
             "sys.stdout.flush(); time.sleep(30)")

    result = calculation.run(DECK)

    assert result["ok"] is False
    assert result["returncode"] is None
    assert result["stage"] == {"index": 2, "of": 3, "name": "2_Dig"}
    assert "half a l\xe9ne" in result["error"]


# ── The log grows while Kratos works ────────────────────────────────────────

GROWING = (
    "import os, time\n"
    "print('first line', flush=True)\n"
    "for _ in range(400):\n"
    "    if os.path.exists('go'): break\n"
    "    time.sleep(0.05)\n"
    "print('last line', flush=True)\n")
"""A stand-in that prints one line, then waits for the test to create `go`."""


def test_the_log_holds_each_line_while_the_run_goes_on(runs, monkeypatch):
    """The convergence plot reads the log during the run, so a line must be in the
    log as soon as Kratos printed it, not when the run ends."""
    import threading
    import time

    stand_in(monkeypatch, GROWING)
    seen: dict = {}

    def watch() -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            directory = calculation.current_run()
            log = directory / calculation.LOG_NAME if directory else None
            if log is not None and log.is_file() and "first line" in log.read_text(
                    encoding="utf-8"):
                seen["log"] = log.read_text(encoding="utf-8")
                seen["running"] = calculation.running()
                seen["current"] = calculation.is_current(directory)
                (directory / "go").write_text("", encoding="utf-8")
                return
            time.sleep(0.02)

    watcher = threading.Thread(target=watch)
    watcher.start()
    result = calculation.run(DECK)
    watcher.join()

    assert result["ok"] is True
    assert "first line" in seen["log"] and "last line" not in seen["log"]
    assert seen["running"] is True and seen["current"] is True
    log = (Path(result["directory"]) / calculation.LOG_NAME).read_text(encoding="utf-8")
    assert log.splitlines() == ["first line", "last line"]
    assert calculation.current_run() is None
    assert calculation.is_current(Path(result["directory"])) is False
    assert calculation.running() is False


def test_no_run_is_in_progress_after_one_that_could_not_start(runs, monkeypatch, tmp_path):
    not_a_program = tmp_path / "python.exe"
    not_a_program.write_text("not a program", encoding="utf-8")
    monkeypatch.setenv(calculation.PYTHON_ENV, str(not_a_program))

    with pytest.raises(calculation.CalculationError):
        calculation.run(DECK)

    assert calculation.current_run() is None
    assert calculation.running() is False


def test_a_timeout_that_is_not_a_number_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv(calculation.TIMEOUT_ENV, "an hour")
    assert calculation.timeout() == calculation.DEFAULT_TIMEOUT


# ── What a run produced ─────────────────────────────────────────────────────

def test_outputs_are_exactly_what_the_run_added(runs, monkeypatch):
    """Including directories (VTK output writes one), and not an input the run
    rewrote: that is still an input."""
    stand_in(monkeypatch,
             "import os, glob;"
             "open('a.post.res', 'w').close();"
             "os.mkdir('vtk_output');"
             "open('vtk_output/b.vtk', 'w').close();"
             "open(glob.glob('*.mdpa')[0], 'a').write('// touched');")

    result = calculation.run(DECK)

    assert result["ok"] is True
    assert result["outputs"] == ["a.post.res", "vtk_output"]
    assert result["inputs"] == ["Test_model.mdpa", calculation.MATERIALS_NAME,
                                calculation.PARAMETERS_NAME]


def test_markers_with_windows_line_endings_are_read(): 
    output = "\r\n".join([marker("begin", 1, 2, "a"), marker("end", 1, 2, "a"),
                          marker("begin", 2, 2, "Dig to -4.5 m"), "boom"]) + "\r\n"
    assert calculation.failed_stage(output) == (2, 2, "Dig to -4.5 m")


# ── Which stage failed ──────────────────────────────────────────────────────
# "It failed" and "stage 5 failed" are a very different message on a seven-stage deck,
# and the deck has no stage banner of its own to read: `SequentialOrchestrator.Run`
# loops over the execution list printing nothing that names the stage. Checked against
# Kratos' own source and against a real seven-stage run log, not inferred -- see
# plan sec 7.8 for why that distinction is written down.
#
# So the markers are ours. `kratos_main` subclasses the orchestrator and announces
# each stage from the two public per-stage hooks; everything below parses what it
# prints, which is why none of it needs Kratos.

def marker(event: str, index: int, total: int, name: str) -> str:
    return f"{calculation.STAGE_MARKER} {event} {index}/{total} {name}"


def test_no_markers_means_nothing_to_say():
    """Every deck written before this existed, and every failure before the first
    stage was reached -- a deck Kratos could not even read."""
    assert calculation.failed_stage("Error: something went wrong") is None
    assert calculation.failed_stage("") is None


def test_the_stage_that_began_and_never_ended_is_the_one_that_failed():
    output = "\n".join([
        marker("begin", 1, 7, "1_Initial_stage"),
        marker("end", 1, 7, "1_Initial_stage"),
        marker("begin", 2, 7, "2_Null_step"),
        marker("end", 2, 7, "2_Null_step"),
        marker("begin", 3, 7, "3_SheetPileWall_installation"),
        "RuntimeError: Error: Reference distance close to zero.",
    ])
    assert calculation.failed_stage(output) == (3, 7, "3_SheetPileWall_installation")


def test_a_run_where_every_stage_ended_blames_none_of_them():
    """The deck finished. Whatever went wrong after that is not a stage's fault, and
    naming the last one would be a lie."""
    output = "\n".join([marker("begin", 1, 2, "a"), marker("end", 1, 2, "a"),
                        marker("begin", 2, 2, "b"), marker("end", 2, 2, "b")])
    assert calculation.failed_stage(output) is None


def test_a_failure_in_the_very_first_stage_is_named(): 
    output = marker("begin", 1, 7, "1_Initial_stage") + "\nboom"
    assert calculation.failed_stage(output) == (1, 7, "1_Initial_stage")


def test_a_stage_name_may_contain_spaces():
    """A Kratos stage's name comes from `Stage.name`, which the user types."""
    output = marker("begin", 2, 3, "Dig to -4.5 m")
    assert calculation.failed_stage(output) == (2, 3, "Dig to -4.5 m")


def test_the_markers_do_not_have_to_be_alone_on_their_line():
    """Kratos writes from C++ and from Python into the same pipe, and the two
    interleave -- a marker can arrive with someone else's half-line in front of it."""
    output = "BuilderAndSolver: Clear Function called " + marker("begin", 2, 3, "b")
    assert calculation.failed_stage(output) == (2, 3, "b")


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

    result = calculation.run(DECK)

    assert result["ok"] is False
    assert result["stage"] == {"index": 2, "of": 2, "name": "2_Dig"}
    assert "2_Dig" in result["error"]
    assert "stage 2 of 2" in result["error"]
    # Kratos' own reason survives; the stage is added in front of it, not instead.
    assert "Reference distance close to zero" in result["error"]


def test_a_run_that_works_reports_no_failed_stage(runs, monkeypatch):
    stand_in(monkeypatch, f"print({marker('begin', 1, 1, '1_Stage')!r});"
                          f"print({marker('end', 1, 1, '1_Stage')!r})")

    result = calculation.run(DECK)

    assert result["ok"] is True
    assert result["stage"] is None


def test_the_stage_markers_are_kept_out_of_the_tail_shown_to_the_user():
    """They are scaffolding, not output. Thirty lines of them would push Kratos' own
    reason off the end of the message they exist to improve."""
    noise = [marker("begin", n, 40, f"{n}_Stage") for n in range(1, 40)]
    output = "\n".join(noise + ["Error: the thing that actually went wrong"])

    explained = calculation._explain(output)

    assert "the thing that actually went wrong" in explained
    assert calculation.STAGE_MARKER not in explained


# ── The markers at the other end: kratos_main's orchestrator wrapper ────────
# `core.analysis.kratos_main` is a script for Kratos' interpreter, but it imports Kratos only
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
    from core.analysis import kratos_main

    kratos_main.announcing(FakeOrchestrator)(["a", "b", "c"]).Run()

    printed = capsys.readouterr().out.strip().splitlines()
    assert printed == [
        f"{kratos_main.STAGE_MARKER} begin 1/3 a",
        f"{kratos_main.STAGE_MARKER} end 1/3 a",
        f"{kratos_main.STAGE_MARKER} begin 2/3 b",
        f"{kratos_main.STAGE_MARKER} end 2/3 b",
        f"{kratos_main.STAGE_MARKER} begin 3/3 c",
        f"{kratos_main.STAGE_MARKER} end 3/3 c",
    ]


def test_the_wrapper_still_does_the_base_class_work(capsys):
    """It announces around Kratos' own hooks, it does not replace them. Dropping the
    super() call would silently stop every Activate and Deactivate operation, which is
    the whole of staged construction."""
    from core.analysis import kratos_main

    orchestrator = kratos_main.announcing(FakeOrchestrator)(["a", "b"])
    orchestrator.Run()

    assert orchestrator.calls == [("pre", "a"), ("post", "a"),
                                  ("pre", "b"), ("post", "b")]


def test_begin_is_printed_before_the_preprocess_runs(capsys):
    """The preprocess is itself a place a deck fails -- it is where the Activate and
    Deactivate operations execute, so a stage naming a part the mdpa does not carry
    throws there. Announced after it, that failure would be blamed on the stage
    before."""
    from core.analysis import kratos_main

    class Exploding(FakeOrchestrator):
        def RunCurrentStagePreprocess(self, stage_name, data=None):
            raise RuntimeError("no such sub model part")

    with pytest.raises(RuntimeError):
        kratos_main.announcing(Exploding)(["a", "b"]).Run()

    assert f"{kratos_main.STAGE_MARKER} begin 1/2 a" in capsys.readouterr().out


def test_the_two_ends_agree_on_the_marker(capsys):
    """The round trip: what the runner prints is what `calculation` reads. They share
    the constant, but not the format string, and a change to one is only caught here."""
    from core.analysis import kratos_main

    class Failing(FakeOrchestrator):
        def Run(self):
            self.RunCurrentStagePreprocess("1_Initial")
            self.RunCurrentStagePostprocess("1_Initial")
            self.RunCurrentStagePreprocess("2_Dig to -4.5 m")
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        kratos_main.announcing(Failing)(["1_Initial", "2_Dig to -4.5 m"]).Run()

    assert calculation.failed_stage(capsys.readouterr().out) == (2, 2, "2_Dig to -4.5 m")
