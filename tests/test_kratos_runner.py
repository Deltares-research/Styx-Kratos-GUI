"""`core.analysis.kratos_main` end to end, against a stand-in Kratos.

`test_calculate.py` covers the orchestrator wrapper in isolation. This runs the real
entry point -- `python -m core.analysis.kratos_main ProjectParameters.json`, in the deck's own
directory, with `calculation.interpreter()`'s environment -- against
`tests/fakes/kratos_stub`, a `KratosMultiphysics` whose `SequentialOrchestrator` keeps
the real one's loop order. What that proves and the wrapper tests cannot: the registry
lookup, the import of the module it names, reading the deck relative to the working
directory, the exit code, and that the markers survive a process that dies.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.kratos import parameters
from core.analysis import calculation
from core.analysis.kratos_main import STAGE_MARKER

STUB = Path(__file__).resolve().parent / "fakes" / "kratos_stub"


def deck(directory: Path, stages: list[str], fail: dict[str, str] | None = None) -> Path:
    """A ProjectParameters.json the way `parameters` writes one, minus everything
    the stand-in does not read. `fail` maps a stage to where it should fail."""
    settings = {
        "orchestrator": {
            "name": parameters.ORCHESTRATOR,
            "settings": {"echo_level": 0, "execution_list": stages,
                         "load_from_checkpoint": None, "stage_checkpoints": False},
        },
        "stages": {name: {"analysis_stage": parameters.ANALYSIS_STAGE,
                          **({"stub_fail": fail[name]} if fail and name in fail else {})}
                   for name in stages},
    }
    path = directory / "ProjectParameters.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    return path


def run_runner(directory: Path, *args: str, stub: bool = True,
               monkeypatch: pytest.MonkeyPatch | None = None):
    """The runner the way `calculation.run` starts it: same command, same environment
    builder, the deck's directory as working directory."""
    if monkeypatch is not None:
        monkeypatch.setattr(calculation, "SETTINGS_FILE", directory / "no-settings.json")
        monkeypatch.setenv(calculation.PYTHON_ENV, sys.executable)
        if stub:
            monkeypatch.setenv(calculation.KRATOS_ENV, str(STUB))
        else:
            monkeypatch.delenv(calculation.KRATOS_ENV, raising=False)
    python, environment = calculation.interpreter()
    command = [python, *(calculation.COMMAND if not args else [*calculation.COMMAND[:-1],
                                                             *args])]
    return subprocess.run(command, cwd=directory, env=environment,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", timeout=60)


def markers(output: str) -> list[str]:
    return [line[len(STAGE_MARKER) + 1:] for line in output.splitlines()
            if line.startswith(STAGE_MARKER)]


STAGES = ["1_Initial_stage", "2_Null_step", "3_Excavation"]


def test_every_stage_is_announced_in_execution_order(tmp_path, monkeypatch):
    deck(tmp_path, STAGES)

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode == 0, completed.stdout
    assert markers(completed.stdout) == [
        "begin 1/3 1_Initial_stage", "end 1/3 1_Initial_stage",
        "begin 2/3 2_Null_step", "end 2/3 2_Null_step",
        "begin 3/3 3_Excavation", "end 3/3 3_Excavation",
    ]


def test_the_execution_list_decides_the_order_not_the_stages_dict(tmp_path, monkeypatch):
    path = deck(tmp_path, STAGES)
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["orchestrator"]["settings"]["execution_list"] = ["2_Null_step",
                                                              "1_Initial_stage"]
    path.write_text(json.dumps(settings), encoding="utf-8")

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode == 0, completed.stdout
    assert markers(completed.stdout) == [
        "begin 1/2 2_Null_step", "end 1/2 2_Null_step",
        "begin 2/2 1_Initial_stage", "end 2/2 1_Initial_stage",
    ]


def test_the_stages_really_ran_between_their_markers(tmp_path, monkeypatch):
    """Announcing around the hooks, not instead of them: the stand-in prints when each
    stage's preprocess, solve and postprocess run, and they sit inside the markers."""
    deck(tmp_path, STAGES[:1])

    lines = [line for line in run_runner(tmp_path, monkeypatch=monkeypatch)
             .stdout.splitlines() if line.strip()]

    begin = lines.index(f"{STAGE_MARKER} begin 1/1 1_Initial_stage")
    end = lines.index(f"{STAGE_MARKER} end 1/1 1_Initial_stage")
    assert lines[begin + 1:end] == ["stub: preprocess 1_Initial_stage",
                                    "stub: solve 1_Initial_stage",
                                    "stub: postprocess 1_Initial_stage"]


@pytest.mark.parametrize("where", ["preprocess", "solve", "postprocess"])
def test_a_stage_that_raises_begins_and_never_ends(tmp_path, monkeypatch, where):
    deck(tmp_path, STAGES, fail={"2_Null_step": where})

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode != 0
    assert markers(completed.stdout) == [
        "begin 1/3 1_Initial_stage", "end 1/3 1_Initial_stage",
        "begin 2/3 2_Null_step",
    ]
    # The traceback is the message: no try/except swallows it on the way out.
    assert f"stub failure in {where} of 2_Null_step" in completed.stdout
    assert "Traceback" in completed.stdout
    assert calculation.failed_stage(completed.stdout) == (2, 3, "2_Null_step")


def test_the_begin_marker_survives_a_process_that_dies_without_unwinding(
        tmp_path, monkeypatch):
    """A crash in compiled code takes the interpreter down with no traceback and no
    buffer flush. The marker is flushed as it is printed, so it is already out."""
    deck(tmp_path, STAGES, fail={"3_Excavation": "abort"})

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode != 0
    assert calculation.failed_stage(completed.stdout) == (3, 3, "3_Excavation")


def test_the_deck_is_read_from_the_working_directory(tmp_path, monkeypatch):
    """Kratos resolves every path in a deck against the working directory, so
    `calculation` runs the runner there and passes the bare file name."""
    deck(tmp_path, STAGES[:1])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    from_deck = run_runner(tmp_path, monkeypatch=monkeypatch)
    from_elsewhere = run_runner(elsewhere, monkeypatch=monkeypatch)

    assert from_deck.returncode == 0, from_deck.stdout
    assert from_elsewhere.returncode != 0
    assert "ProjectParameters.json" in from_elsewhere.stdout


def test_an_orchestrator_the_registry_does_not_know_fails_before_any_stage(
        tmp_path, monkeypatch):
    path = deck(tmp_path, STAGES)
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings["orchestrator"]["name"] = "Orchestrators.KratosMultiphysics.NoSuch"
    path.write_text(json.dumps(settings), encoding="utf-8")

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode != 0
    assert markers(completed.stdout) == []
    assert calculation.failed_stage(completed.stdout) is None
    assert "NoSuch" in completed.stdout


def test_the_wrong_number_of_arguments_is_a_usage_error(tmp_path, monkeypatch):
    completed = run_runner(tmp_path, "a.json", "b.json", monkeypatch=monkeypatch)

    assert completed.returncode == 2
    assert "usage" in completed.stdout


def test_without_kratos_the_runner_fails_the_way_calculate_explains(
        tmp_path, monkeypatch):
    """The import is the first thing `run` does, so `calculation._explain` sees the
    ModuleNotFoundError it turns into "configure the Kratos build"."""
    deck(tmp_path, STAGES[:1])

    completed = run_runner(tmp_path, stub=False, monkeypatch=monkeypatch)

    assert completed.returncode != 0
    assert "No module named 'KratosMultiphysics'" in completed.stdout
    assert calculation.SETTINGS_FILE.name in calculation._explain(completed.stdout)


def test_the_runner_does_not_import_the_server(tmp_path, monkeypatch):
    """Kratos' interpreter has none of FastAPI, pydantic or gmsh. `-m core.analysis.kratos_main`
    imports `core` first, so neither it nor the runner may pull any of them in."""
    deck(tmp_path, STAGES[:1])
    (tmp_path / "sitecustomize.py").write_text(
        "import atexit, sys\n"
        "def _report():\n"
        "    heavy = sorted(m for m in ('fastapi', 'pydantic', 'gmsh', 'numpy')\n"
        "                   if m in sys.modules)\n"
        "    print('stub: heavy modules', heavy, flush=True)\n"
        "atexit.register(_report)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode == 0, completed.stdout
    assert "stub: heavy modules []" in completed.stdout


def test_a_real_export_runs_through_the_stand_in(tmp_path, monkeypatch):
    """Not a hand-written deck: what the server exports for the staged test model, so
    the orchestrator name and execution list are the ones Kratos will really be given."""
    from core.kratos import writer
    from core.geometry.solid_model import session
    from core.model.schemas import MeshRequest
    from tests.models import excavation
    project = excavation.excavation_project(staged=True)
    with session():
        export = writer.export_project(project, MeshRequest(**project.mesh.model_dump()))
    (tmp_path / "ProjectParameters.json").write_text(export["project_parameters"],
                                                     encoding="utf-8")
    execution = json.loads(export["project_parameters"])[
        "orchestrator"]["settings"]["execution_list"]
    assert len(execution) == 7

    completed = run_runner(tmp_path, monkeypatch=monkeypatch)

    assert completed.returncode == 0, completed.stdout
    total = len(execution)
    assert markers(completed.stdout) == [
        f"{event} {index}/{total} {name}"
        for index, name in enumerate(execution, start=1) for event in ("begin", "end")
    ]


# ── In-process: the same entry points, for coverage of the runner itself ────

@pytest.fixture
def stub_on_path(monkeypatch):
    monkeypatch.syspath_prepend(str(STUB))
    for name in [m for m in sys.modules if m == "KratosMultiphysics"
                 or m.startswith("KratosMultiphysics.")]:
        monkeypatch.delitem(sys.modules, name)


def test_main_returns_zero_after_a_run_that_worked(tmp_path, monkeypatch, capsys,
                                                    stub_on_path):
    from core.analysis import kratos_main
    deck(tmp_path, STAGES[:2])
    monkeypatch.chdir(tmp_path)

    assert kratos_main.main(["kratos_main.py", "ProjectParameters.json"]) == 0
    assert markers(capsys.readouterr().out) == [
        "begin 1/2 1_Initial_stage", "end 1/2 1_Initial_stage",
        "begin 2/2 2_Null_step", "end 2/2 2_Null_step",
    ]


def test_main_lets_a_stage_failure_through(tmp_path, monkeypatch, stub_on_path):
    from core.analysis import kratos_main
    deck(tmp_path, STAGES[:1], fail={"1_Initial_stage": "solve"})
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="stub failure in solve"):
        kratos_main.main(["kratos_main.py", "ProjectParameters.json"])


def test_main_with_no_deck_named_is_a_usage_error(capsys):
    from core.analysis import kratos_main

    assert kratos_main.main(["kratos_main.py"]) == 2
    assert "usage" in capsys.readouterr().err
