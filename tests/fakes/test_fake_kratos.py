"""The fake Kratos produces a run the real results reader takes for a finished one."""

from __future__ import annotations

from core.kratos import writer
from core.analysis import calculation
from core.results import catalog
from tests.models import excavation
from tests.fakes import fake_kratos


def test_a_fake_run_reads_as_a_complete_run_with_member_curves(tmp_path, monkeypatch):
    monkeypatch.setenv(calculation.RUNS_ENV, str(tmp_path))
    catalog.forget_cache()
    outcome = fake_kratos.fake_run(writer.export_project(excavation.excavation_project(staged=True)))

    run_id = outcome["directory"].replace("\\", "/").rsplit("/", 1)[1]
    described = catalog.describe(run_id)
    assert outcome["ok"] and described["complete"] and described["failed_at"] is None
    assert [m["name"] for m in catalog.stage_members(run_id)["members"]] == [
        "interface_left", "interface_right", "wall"]
    profile = catalog.member_profiles(run_id, "wall", "M")
    assert profile["stages"], "the wall can be plotted"
    catalog.forget_cache()
