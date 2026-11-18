"""The replay of a GUI tutorial's recorded Kratos run (`tests/fakes/replay_kratos.py`): it
gives back the recorded run for the recorded deck, and says so when a deck differs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.analysis import calculation
from tests import deck_compare
from tests.e2e import tutorials
from tests.fakes import replay_kratos


@pytest.fixture
def runs_root(tmp_path, monkeypatch):
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path))
    return tmp_path


def _recorded(name: str) -> tuple:
    folder = tutorials.RUNS / name
    return folder, deck_compare.read_deck(folder)


@pytest.mark.parametrize("name", tutorials.names())
def test_the_recorded_deck_replays_the_recorded_run(name, runs_root):
    folder, export = _recorded(name)
    replay = replay_kratos.Replay(folder, "record it again")
    answer = replay(export)
    assert replay.problems == []
    run = Path(answer["directory"])
    assert run.is_dir() and run.parent == runs_root
    recorded = json.loads((folder / replay_kratos.ANSWER).read_text(encoding="utf-8"))
    assert answer["ok"] and answer["outputs"] == recorded["outputs"]
    for output in recorded["outputs"]:
        assert (run / output).read_bytes() == (folder / output).read_bytes(), output
    # The deck written from `export`: the three files `read_deck` gives of it.
    assert set(answer["inputs"]) <= set(recorded["inputs"])


@pytest.mark.parametrize("name", tutorials.names())
def test_a_changed_deck_is_noted_and_still_replayed(name, runs_root, monkeypatch, tmp_path):
    folder, export = _recorded(name)
    materials = json.loads(export["materials"])
    first = materials["properties"][0]["Material"]["Variables"]
    key = next(k for k, v in first.items() if isinstance(v, float))
    first[key] *= 2
    replay = replay_kratos.Replay(folder, "record it again")
    answer = replay({**export, "materials": json.dumps(materials)})
    assert answer["ok"]
    (problem,) = replay.problems
    assert "materials differ" in problem and "record it again" in problem

    notes = tmp_path / "notes.txt"
    monkeypatch.setenv(replay_kratos.WARNINGS_ENV, str(notes))
    replay_kratos.note(problem)
    assert notes.read_text(encoding="utf-8").strip() == " ".join(problem.split())
