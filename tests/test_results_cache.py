"""The parsed-file cache and the event loop (finding F10).

Opening a run asks for every stage's mesh (`stage_parts` reads them all to tell a part a
phase removed from one the writer never emits) plus the deck, and switching phase asks
for the next stage's results. The cache used to hold 8 entries and clear itself whole
when full, so a 7-stage run -- one deck plus seven meshes -- overflowed on every phase
switch and everything was parsed again. And the routes were `async def` doing that
parsing on the event loop, so one slow stage stalled every other request.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from core.kratos import mdpa_import
from core.results import gid as gid_results, runs as results
from backend.main import app
from tests.test_results import make_run

STAGES = [f"{n}_Stage" for n in range(1, 8)]
RUN = "Big_model_2026-01-01_00-00"


@pytest.fixture
def seven_stages(runs_root):
    results.forget_cache()
    make_run(runs_root, RUN, deck="Big_model", stages=STAGES)
    yield RUN
    results.forget_cache()


@pytest.fixture
def runs_root(tmp_path, monkeypatch):
    from core.run import calculate

    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setenv(calculate.RUNS_ENV, str(root))
    return root


def counting(monkeypatch, module, name):
    """Wrap `module.name` so each call is counted by the path it parsed."""
    calls: list[str] = []
    real = getattr(module, name)

    def wrapper(text):
        calls.append(name)
        return real(text)

    wrapper.__name__ = real.__name__
    monkeypatch.setattr(module, name, wrapper)
    return calls


def test_each_file_of_a_run_is_parsed_once_however_often_it_is_asked_for(
        seven_stages, monkeypatch):
    meshes = counting(monkeypatch, gid_results, "read_mesh")
    decks = counting(monkeypatch, mdpa_import, "import_mdpa")
    res = counting(monkeypatch, gid_results, "read_results")

    for _ in range(2):
        for index in range(1, len(STAGES) + 1):
            results.stage_parts(seven_stages, index)
            results.stage_fields(seven_stages, index)

    assert len(meshes) == len(STAGES)
    assert len(decks) == 1
    assert len(res) == len(STAGES)


def test_the_cache_is_bounded_by_size_not_unbounded(seven_stages, monkeypatch):
    """Bounded it must still be: a budget in bytes of source, oldest out first."""
    monkeypatch.setattr(results, "CACHE_BYTES", 1)
    for index in range(1, len(STAGES) + 1):
        results.stage_fields(seven_stages, index)

    assert len(results._cache) == 1


def test_health_answers_while_a_stage_is_being_parsed(seven_stages, monkeypatch):
    """A results request parsing a big stage must not hold up anything else."""
    real = gid_results.read_results
    started = threading.Event()

    def slow(text):
        started.set()
        time.sleep(1.5)
        return real(text)

    slow.__name__ = real.__name__
    monkeypatch.setattr(gid_results, "read_results", slow)

    with TestClient(app) as client:
        worker = threading.Thread(target=lambda: client.get(
            f"/api/results/runs/{seven_stages}/stages/1/fields"))
        worker.start()
        assert started.wait(5), "the slow parse never started"
        began = time.monotonic()
        response = client.get("/api/health")
        waited = time.monotonic() - began
        worker.join(10)

    assert response.status_code == 200
    assert waited < 0.5, f"/api/health waited {waited:.2f} s behind a parse"
