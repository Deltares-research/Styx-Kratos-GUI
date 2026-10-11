"""The fake Kratos produces a run the real results reader takes for a finished one."""

from __future__ import annotations

from app import calculate, kratos, results
from tests.models import excavation
from tests.fakes import fake_kratos


def test_a_fake_run_reads_as_a_complete_run_with_member_curves(tmp_path, monkeypatch):
    monkeypatch.setenv(calculate.RUNS_ENV, str(tmp_path))
    results.forget_cache()
    outcome = fake_kratos.fake_run(kratos.export_project(excavation.excavation_project(staged=True)))

    run_id = outcome["directory"].replace("\\", "/").rsplit("/", 1)[1]
    described = results.describe(run_id)
    assert outcome["ok"] and described["complete"] and described["failed_at"] is None
    assert [m["name"] for m in results.stage_members(run_id)["members"]] == ["interface", "wall"]
    profile = results.member_profiles(run_id, "wall", "M")
    assert profile["stages"], "the wall can be plotted"
    results.forget_cache()
