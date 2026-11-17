"""The GUI tutorials in `docs/gui_tutorials/`, played on the real page as a reader follows
them. Opt-in: `--run-e2e`.

Each tutorial is a list of steps in `tests/e2e/tutorials/`. The test plays them one by
one, holds each to its own check, and at the end holds the deck the GUI writes to the deck
of the tutorial's model in `tests/models/`. A changed button, window or default that
breaks a step, or makes the GUI build another model, fails here. The screenshots the steps
take must be the screenshots the tutorial's page shows.

Calculate replays the tutorial's recorded Kratos run (`tests/fakes/replay_kratos.py`), so
the Results steps show real results on a computer without Kratos. A deck that differs from
the recorded one gives a warning, or with `--strict-deck` a failure. With `--run-kratos`,
Kratos itself calculates, and with `--record-run` too, that run becomes the recorded run.

With `--doc-screenshots DIR` the steps also save their screenshots, in `DIR/<tutorial>/`.
`python tools/gui_tutorial.py` runs this for you.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from tests import deck_compare
from tests.e2e import tutorials
from tests.e2e.tutorials.harness import Tour, open_as_started
from tests.fakes import replay_kratos


def gui_deck(page, server) -> dict:
    """The deck the GUI exports for the project the server holds."""
    project = page.request.get(server["url"] + "/api/project").json()
    answer = page.request.post(server["url"] + "/api/export/mdpa", data=project["mesh"])
    assert answer.ok, answer.text()
    return answer.json()


def script_deck(model) -> dict:
    with solid_model.session():
        return writer.export_project(model)


def _calculate_with(name: str, request, monkeypatch) -> tuple:
    """What Calculate runs in this test: Kratos (and what it answered, to record), or the
    replay of the recorded run."""
    if request.config.getoption("--run-kratos"):
        answers: list[dict] = []
        real = calculation.run

        def run_and_keep(export):
            answers.append(real(export))
            return answers[-1]

        monkeypatch.setattr(calculation, "run", run_and_keep)
        return answers, None
    assert not request.config.getoption("--record-run"), "--record-run needs --run-kratos"
    folder = tutorials.RUNS / name
    assert (folder / replay_kratos.ANSWER).exists(), \
        f"no recorded run in {folder}: run `python tools/gui_tutorial.py {name} --record`"
    replay = replay_kratos.Replay(folder, f"python tools/gui_tutorial.py {name} --record")
    monkeypatch.setattr(calculation, "run", replay)
    return None, replay


@pytest.mark.parametrize("name", tutorials.names())
def test_the_tutorial_builds_its_model(name, app_page, live_server, request, monkeypatch):
    tutorial = tutorials.load(name)
    folder = request.config.getoption("--doc-screenshots")
    out = Path(folder) / name if folder else None
    if out is not None:
        for old in out.glob("*.png"):
            old.unlink()
    answers, replay = _calculate_with(name, request, monkeypatch)
    open_as_started(app_page, live_server["url"])
    tour = Tour(app_page, out=out)
    tour.play(tutorial.STEPS)
    if out is not None:
        assert sorted(p.stem for p in out.glob("*.png")) == sorted(tour.pictures)

    got = deck_compare.deck_view(gui_deck(app_page, live_server))
    want = deck_compare.deck_view(script_deck(tutorial.MODEL))
    assert got["materials"] == want["materials"]
    assert got["parameters"] == want["parameters"]
    assert got["mesh"]["nodes"] == want["mesh"]["nodes"]
    assert got["mesh"] == want["mesh"]
    assert app_page.errors == []

    if answers is not None and request.config.getoption("--record-run"):
        assert answers and answers[-1]["ok"], f"the Kratos run failed: {answers[-1:]}"
        replay_kratos.record(answers[-1], tutorials.RUNS / name)
    if replay is not None and replay.problems:
        message = " ".join(replay.problems)
        assert not request.config.getoption("--strict-deck"), message
        replay_kratos.note(message)
        warnings.warn(message, stacklevel=1)
    assert tutorials.page_images(name) == tour.pictures, \
        f"{tutorial.PAGE} must show the screenshots the steps take, in their order"
