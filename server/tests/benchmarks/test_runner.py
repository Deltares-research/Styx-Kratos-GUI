"""The benchmark runner's own logic, without Kratos: what status a case earns, and which
cases a request for one case runs. The benchmarks themselves are test_benchmarks.py."""

from __future__ import annotations

import pytest

from benchmarks import runner
from benchmarks.cases import BY_ID, CASES
from benchmarks.runner import Case, Outcome


@pytest.fixture
def calculated(monkeypatch, tmp_path):
    """`run_case` with the server's calculation answered by a fake directory."""
    class Response:
        status_code = 200

        def __init__(self, payload=None):
            self.payload = payload or {}
            self.text = ""

        def json(self):
            return self.payload

    class Client:
        def __init__(self, app):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def put(self, *a, **k):
            return Response()

        def post(self, url, **k):
            return Response({"ok": True, "run": "r", "directory": str(tmp_path)})

    import fastapi.testclient
    monkeypatch.setattr(fastapi.testclient, "TestClient", Client)


def case(passed: bool, **fields) -> Case:
    from benchmarks import models
    return Case("X", "x", "-", build=models.project,
                checks=[lambda ctx: Outcome("c", passed, "-", "-")], **fields)


@pytest.mark.parametrize("passed, fields, status", [
    (True, {}, "PASS"),
    (False, {}, "FAIL"),
    (True, {"deviation": "coarser"}, "PASS-DEV"),
    (False, {"deviation": "coarser"}, "FAIL"),
    (False, {"known_defect": "F0"}, "KNOWN"),
    (True, {"known_defect": "F0"}, "FAIL"),
])
def test_the_status_a_case_earns(calculated, tmp_path, passed, fields, status):
    assert runner.run_case(case(passed, **fields), tmp_path).status == status


def test_a_known_defect_that_no_longer_shows_says_so(calculated, tmp_path):
    result = runner.run_case(case(True, known_defect="F0"), tmp_path)
    assert "remove `known_defect`" in result.detail


def test_a_blocked_case_is_not_run(tmp_path):
    result = runner.run_case(Case("X", "x", "-", blocked="needs MF-01"), tmp_path)
    assert (result.status, result.detail) == ("BLOCKED", "needs MF-01")


def test_a_case_asked_for_alone_brings_what_it_needs():
    chosen = runner.with_needs([BY_ID["BM-2D3D-01"]], BY_ID)
    assert [c.id for c in chosen] == ["BM-EXC-01", "BM-2D3D-01"]
    assert runner.with_needs(CASES, BY_ID) == CASES


def test_every_case_needs_only_cases_listed_before_it():
    seen = set()
    for c in CASES:
        assert set(c.needs) <= seen, c.id
        seen.add(c.id)


def test_every_case_that_runs_has_checks_and_every_other_says_why():
    for c in CASES:
        assert (c.build and c.checks) or c.blocked, c.id


def test_the_report_carries_every_status(tmp_path):
    results = [runner.Result(c, "BLOCKED", detail=c.blocked or "") for c in CASES]
    path = runner.write_report(results, tmp_path, "abc")
    text = path.read_text(encoding="utf-8")
    assert "Kratos: `abc`" in text and all(c.id in text for c in CASES)
    assert (tmp_path / "report.json").exists()


def test_the_richardson_ratio_of_three_heaves(monkeypatch):
    from benchmarks import cases
    monkeypatch.setattr(cases, "_heave", {"a": 0.7084, "b": 0.71079, "c": 0.71177})
    outcome = cases.richardson("a", "b", "c")(None)
    assert outcome.passed and outcome.measured.startswith("2.44")
    monkeypatch.setattr(cases, "_heave", {"a": 0.70, "b": 0.71, "c": 0.70})
    assert not cases.richardson("a", "b", "c")(None).passed      # not converging
    monkeypatch.setattr(cases, "_heave", {"a": 0.70})
    assert "no run for" in cases.richardson("a", "b", "c")(None).measured


def test_the_floor_heave_is_the_highest_remaining_point_on_the_axis():
    from types import SimpleNamespace

    from benchmarks import cases
    mesh = SimpleNamespace(nodes={1: (40.0, -5.0, 0.0), 2: (40.0, -60.0, 0.0),
                                  3: (41.0, -5.0, 0.0)})
    u = {1: (0.0, 0.7, 0.0), 2: (0.0, 0.0, 0.0), 3: (0.0, 0.9, 0.0)}
    assert cases._floor_heave(u, mesh, 40.0) == 0.7


def test_the_overburden_splits_a_layer_at_the_water():
    from benchmarks import cases
    m = {"g_unsat": 18.0, "g_sat": 20.0}
    assert cases._wet_and_dry(0.0, -10.0, m, None) == [(0.0, -10.0, 18.0)]
    assert cases._wet_and_dry(0.0, -10.0, m, -4.0) == [(0.0, -4.0, 18.0), (-4.0, -10.0, 20.0)]
    assert cases._wet_and_dry(0.0, -10.0, m, 1.0) == [(0.0, -10.0, 20.0)]
