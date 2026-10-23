"""The boundary conditions and gravity, run in Kratos
(plan/active/boundary-conditions-plan.md, step A4). Opt-in: `pytest --run-kratos`.

What running them found, 2026-10-23:

* The CROW case and every project that names its conditions write the deck they wrote
  before the conditions existed (compared in tests/test_export_golden.py); the CROW case
  runs all its stages.
* The standard supports typed by hand are the deck a project with no conditions key
  gets, and it runs.
* Gravity off and no load: no displacement at all.
* No support and no anchor: Kratos does not converge, as the rigid-body warning says.
* A dry soil that couples the water pressure (`GEO_DRAINAGE_TYPE` not
  `CONSTANT_PW_FIELD`) with no water pressure condition runs, but the free pressure rises
  to about 1.5 MPa under the self weight and the block settles 8 m instead of 0.65 m. A
  Uniform 0 condition on the whole soil gives the dry answer, which is the one a
  `CONSTANT_PW_FIELD` soil gives with no condition. The export's warning says so.
* Water conditions switched by phases (2026-10-23): each stage has the pressures of the
  conditions its phase has on. A phase with none on keeps the last Hydrostatic values,
  fixed (Kratos does not free them), but a Uniform condition's nodes are freed when its
  phase ends, so a coupled soil's pressure then builds up (1.3 to 1.7 MPa here).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core import scripting
from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import MeshRequest, Project, standard_conditions
from core.results import catalog
from tests.models import excavation
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos

ROOT = Path(__file__).resolve().parents[2]
MESH = MeshRequest(element_size=4.0, order=2)


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("condition-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def export(project: Project, settings: MeshRequest = MESH) -> dict:
    with solid_model.session():
        return writer.export_project(project, settings)


def run(project: Project, settings: MeshRequest = MESH) -> tuple[dict, dict]:
    deck = export(project, settings)
    return deck, calculation.run(deck)


def block(**changes) -> Project:
    """The test model's ground with nothing on it -- no structure, no load, no phase, no
    water -- held by the standard supports alone."""
    p = excavation.excavation_project(staged=False).model_dump(mode="json")
    p.update(beams=[], anchors=[], interfaces=[], loads=[], normal_loads=[], phases=[],
             water=None)
    p["boundary_conditions"] = [c for c in p["boundary_conditions"]
                                if c["kind"] == "displacement"]
    p.update(changes)
    return Project.model_validate(p)


def coupled(project: Project) -> Project:
    p = project.model_dump(mode="json")
    for material in p["materials"]:
        material["variables"]["GEO_DRAINAGE_TYPE"] = "FULLY_COUPLED"
    return Project.model_validate(p)


def results(outcome: dict):
    """The one stage of an unphased deck."""
    return catalog.stage_results(Path(outcome["directory"]).name, 1)


def settlement(outcome: dict) -> float:
    stage = results(outcome)
    u = stage.field("TOTAL_DISPLACEMENT") or stage.field("DISPLACEMENT")
    return max(abs(value[1]) for value in u.values.values())


def water_pressure(outcome: dict) -> float:
    field = results(outcome).field("WATER_PRESSURE")
    return max(abs(value[0] if isinstance(value, list) else value)
               for value in field.values.values())


def test_the_crow_case_runs_every_stage():
    crow = scripting.load_project(str(ROOT / "examples" / "CROW_case" / "crow.py"))
    _, outcome = run(crow, MeshRequest(**crow.mesh.model_dump()))
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])


def test_the_standard_supports_typed_by_hand_are_the_ones_a_project_starts_with():
    typed = block(boundary_conditions=[c.model_dump(mode="json")
                                       for c in standard_conditions()])
    payload = typed.model_dump(mode="json")
    del payload["boundary_conditions"]
    typed_deck, outcome = run(typed)
    assert outcome["ok"], (outcome["error"] or "")[-600:]
    assert export(Project.model_validate(payload))["project_parameters"] \
        == typed_deck["project_parameters"]


def test_with_gravity_off_and_no_load_nothing_moves():
    _, outcome = run(block(gravity=False))
    assert outcome["ok"], (outcome["error"] or "")[-600:]
    assert settlement(outcome) == 0.0


def test_a_model_nothing_holds_does_not_solve_as_the_warning_says():
    deck, outcome = run(block(boundary_conditions=[]))
    assert any("rigid body" in w for w in deck["warnings"])
    assert not outcome["ok"]


def test_a_dry_coupled_soil_needs_its_uniform_zero_as_the_warning_says():
    free_deck, free = run(coupled(block()))
    assert any("couples it to the deformation" in w for w in free_deck["warnings"])
    assert free["ok"], (free["error"] or "")[-600:]
    dry_deck, fixed = run(coupled(block(boundary_conditions=[
        *[c.model_dump(mode="json") for c in standard_conditions()],
        {"id": "dry", "name": "Dry", "kind": "water_pressure", "on": "domain",
         "fluid_pressure_type": "Uniform", "value": 0.0}])))
    assert not any("couples" in w for w in dry_deck["warnings"])
    assert fixed["ok"], (fixed["error"] or "")[-600:]
    _, drained = run(block())                      # CONSTANT_PW_FIELD, no condition
    assert water_pressure(fixed) == 0.0
    assert water_pressure(free) > 1e5
    assert settlement(fixed) == pytest.approx(settlement(drained), rel=1e-6)
    assert settlement(free) > 5 * settlement(fixed)


# ── Water conditions per phase ──────────────────────────────────────────────

def test_the_hydraulic_head_below_the_level_is_the_level():
    """Kratos' own head (`HYDRAULIC_HEAD`, at the integration points): the height minus
    the water pressure over the water weight. Under a hydrostatic level at -1 m it is
    -1 m; an element the level crosses interpolates across the kink at the level."""
    p = block().model_dump(mode="json")
    p["boundary_conditions"].append({"id": "pore", "name": "pore", "kind": "water_pressure",
                                     "on": "domain", "fluid_pressure_type": "Hydrostatic",
                                     "reference_coordinate": -1.0})
    _, outcome = run(Project.model_validate(p))
    run_id = Path(outcome["directory"]).name
    names = [f["name"] for group in catalog.stage_fields(run_id, 1)["groups"]
             for f in group["fields"]]
    assert "head" in names
    per_element = catalog.stage_field(run_id, 1, "head", "elements")["values"]
    at_level = [value for value in per_element if abs(value + 1.0) < 1e-6]
    assert len(at_level) > 0.8 * len(per_element)


def _switched(fluid_pressure_type: str, drainage: str | None = None) -> Project:
    """A 40 m block whose phases switch a high and a low water condition on the whole
    soil: high, low, none, high again."""
    def water(id: str, level: float) -> dict:
        record = {"id": id, "name": id, "kind": "water_pressure", "on": "domain",
                  "fluid_pressure_type": fluid_pressure_type}
        if fluid_pressure_type == "Hydrostatic":
            record["reference_coordinate"] = level
        else:
            record["value"] = level * 10_000.0
        return record

    p = block().model_dump(mode="json")
    if drainage:
        for material in p["materials"]:
            material["variables"]["GEO_DRAINAGE_TYPE"] = drainage
    p["boundary_conditions"] += [water("high", 0.0), water("low", -5.0)]
    p["phases"] = [
        {"id": "p1", "name": "High", "calculation": "K0 procedure", "deactivate": ["low"]},
        {"id": "p2", "name": "Low", "parent": "p1", "activate": ["low"],
         "deactivate": ["high"]},
        {"id": "p3", "name": "None", "parent": "p2", "deactivate": ["low"]},
        {"id": "p4", "name": "High again", "parent": "p3", "activate": ["high"]},
    ]
    return Project.model_validate(p)


def _pressure_range(outcome: dict, stage: int) -> tuple[float, float]:
    field = catalog.stage_results(Path(outcome["directory"]).name, stage).field(
        "WATER_PRESSURE")
    values = [value[0] if isinstance(value, list) else value
              for value in field.values.values()]
    return min(values), max(values)


@pytest.mark.parametrize("drainage", [None, "FULLY_COUPLED"])
def test_a_phase_switches_the_water_and_a_hydrostatic_condition_s_values_stay(drainage):
    """Each phase has the pressures of the condition it switches on. A phase with none
    on keeps the last ones: Kratos leaves a Hydrostatic condition's nodes fixed after
    its phase, in a coupled soil as well."""
    _, outcome = run(_switched("Hydrostatic", drainage))
    lowest = [_pressure_range(outcome, stage)[0] for stage in (1, 2, 3, 4)]
    assert lowest == pytest.approx([-400_000.0, -350_000.0, -350_000.0, -400_000.0])


def test_a_uniform_condition_switched_off_leaves_a_coupled_soil_s_water_free():
    """Kratos frees a Uniform condition's nodes when its phase ends, so with nothing
    switched on the coupled soil's own pressure builds up -- what the export's
    warning says (`condition_checks._free_water_in_phases`)."""
    deck, outcome = run(_switched("Uniform", "FULLY_COUPLED"))
    assert any("phase 'None'" in w and "is free there" in w for w in deck["warnings"])
    assert _pressure_range(outcome, 2) == pytest.approx((-50_000.0, -50_000.0))
    assert _pressure_range(outcome, 3)[1] > 1e6
