"""The temporary prestress workaround, proven by running it, and the check that says when
it can go (core/kratos/prestress_workaround.py). Opt-in: `pytest --run-kratos`.

Kratos carries a truss's stress into the next stage with its prestress, and the truss
then adds the prestress again. The test is a null stage: a stage that changes nothing.
If the stresses are carried correctly, nothing moves in it. Without the workaround,
each null stage after a prestressed strut's installation moved the wall by 0.28 mm in
this model. With the workaround, the movement was about 1e-13 m.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import deck_files, writer
from core.model.schemas import Project, Stage
from core.results import catalog
from tests.models import excavation
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos

PRESTRESS = 5.0e7
"""Pa: 100 kN on the strut's 2e-3 m2 of steel."""

SOLVED = {"max_iterations": 150, "tolerated_error": 1e-6}
"""Tight, so that a null stage of a linear elastic model moves by round-off only."""

STILL = 1e-9
"""Metres: how far a null stage may move and still count as not moving at all."""

NULL_STAGES = (6, 8)
"""The null stage after the strut's installation, and the one after the second lift."""


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("prestress-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def prestressed_project() -> Project:
    """The staged excavation up to the second lift, with a prestressed strut and a null
    stage after the strut's installation and after the second lift."""
    data = excavation.excavation_project(staged=True).model_dump()
    data["anchors"][0]["prestress"] = PRESTRESS
    stages = [s for s in data["stages"] if s["id"] != "dig_3"]
    for stage in stages:
        if stage["calculation"] == "Plastic":
            stage.update(SOLVED)
    after_strut = Stage(id="null_after_strut", name="Null after strut",
                        parent="install_strut", **SOLVED).model_dump()
    after_dig = Stage(id="null_after_dig2", name="Null after second lift",
                      parent="dig_2", **SOLVED).model_dump()
    index = [s["id"] for s in stages].index("dig_2")
    stages[index]["parent"] = "null_after_strut"
    stages[index:index] = [after_strut]
    stages.append(after_dig)
    data["stages"] = stages
    return Project.model_validate(data)


@pytest.fixture(scope="module")
def export() -> dict:
    with solid_model.session():
        return writer.export_project(prestressed_project())


def without_the_workaround(export: dict) -> dict:
    """The same deck as Kratos would run it if the exporter wrote no workaround."""
    doc = json.loads(export["project_parameters"])
    for stage in doc["stages"].values():
        processes = stage["stage_settings"]["processes"]
        if "auxiliary_process_list" in processes:
            processes["auxiliary_process_list"] = [
                p for p in processes["auxiliary_process_list"]
                if p["python_module"] != deck_files.PRESTRESS_WORKAROUND_MODULE]
    return dict(export, project_parameters=json.dumps(doc, indent=4), process_files={})


def movement(export: dict) -> dict[int, float]:
    """The largest displacement of each null stage, in metres."""
    outcome = calculation.run(export)
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])
    run_id = Path(outcome["directory"]).name
    return {stage: max(max(abs(c) for c in u) for u in
                       catalog.stage_results(run_id, stage).field("DISPLACEMENT")
                       .values.values())
            for stage in NULL_STAGES}


def test_the_deck_runs_the_workaround(export):
    assert list(export["process_files"]) == [deck_files.PRESTRESS_WORKAROUND_NAME]


def test_a_prestressed_anchor_is_prestressed_once(export):
    moved = movement(export)
    assert all(value < STILL for value in moved.values()), moved


def test_kratos_still_counts_the_prestress_twice(export):
    """The canary. Kratos without the workaround still pre-stresses the strut again in
    every stage, so a null stage moves.

    When this fails, Kratos counts the prestress once, and the workaround has to go:
    delete what `core/kratos/prestress_workaround.py` lists, and this test with it.
    """
    moved = movement(without_the_workaround(export))
    assert all(value > 1e-5 for value in moved.values()), moved
