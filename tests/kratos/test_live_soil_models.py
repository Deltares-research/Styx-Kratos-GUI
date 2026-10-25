"""A Mohr-Coulomb soil, run in Kratos. Opt-in: `pytest --run-kratos`.

Each soil here is made Mohr-Coulomb the way the material window makes it: the soil model
chosen, its defaults filled in for what the soil lacks (`core.model.soil_models`), the
values it was typed with kept.

What running them found, 2026-10-25:

* The test model's Mohr-Coulomb variant (`tests.models.excavation.mohr_coulomb_project`,
  the laws and variables typed by hand) runs all seven stages, the K0 stage elastic.
* A Mohr-Coulomb soil that cannot yield (a cohesion of 1 GPa) settles under its own weight
  exactly as the linear elastic soil does: the law is elastic inside its yield surface.
* Under a 50 kPa strip load, after a K0 stage, the default soil settles a little more
  than the elastic one (0.1757 m against 0.1750 m): it yields under the load's edge. At
  100 kPa the stage does not converge: a stage applies its load in one step, and that
  step is too large for the plastic iterations (`parameters.SOLVER`, one cycle).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import session
from core.analysis import calculation
from core.model import soil_models
from core.model.schemas import MeshRequest, Project
from core.results import catalog
from tests.kratos import test_live_conditions as live
from tests.kratos.test_live_conditions import runs_root  # noqa: F401  (the fixture)
from tests.models import excavation

pytestmark = pytest.mark.kratos

STRIP = {"kind": "line", "id": "strip", "name": "Strip", "x0": 0.0, "x1": 4.0, "y": 0.0,
         "components": [0.0, -50_000.0]}
"""A 50 kPa strip load, 8 m wide about the block's symmetry plane."""

STAGES = [{"id": "k0", "name": "Initial", "calculation": "K0 procedure",
           "deactivate": ["strip"]},
          {"id": "load", "name": "Load", "parent": "k0", "activate": ["strip"],
           "reset_displacements": True, "max_iterations": 100, "tolerated_error": 1e-3}]


def mohr_coulomb(project: Project, **variables) -> Project:
    """Every soil of `project` made Mohr-Coulomb, then given `variables`."""
    for material in project.materials:
        project = session.update_material(project, material.id,
                                          model=soil_models.MOHR_COULOMB)
        if variables:
            project = session.update_material(project, material.id, variables=variables)
    return project


def settlement(outcome: dict, stage: int) -> float:
    results = catalog.stage_results(Path(outcome["directory"]).name, stage)
    u = results.field("TOTAL_DISPLACEMENT") or results.field("DISPLACEMENT")
    return max(abs(value[1]) for value in u.values.values())


def ran(outcome: dict) -> bool:
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])
    return True


def test_the_test_model_s_mohr_coulomb_variant_runs_every_stage():
    project = excavation.mohr_coulomb_project()
    deck = live.export(project, MeshRequest(**project.mesh.model_dump()))
    assert ran(calculation.run(deck))


def test_a_mohr_coulomb_soil_that_cannot_yield_settles_as_the_elastic_one():
    _, elastic = live.run(live.block())
    _, strong = live.run(mohr_coulomb(live.block(), GEO_COHESION=1.0e9))

    assert ran(elastic) and ran(strong)
    assert live.settlement(strong) == pytest.approx(live.settlement(elastic), rel=1e-6)


def test_a_default_mohr_coulomb_soil_runs_under_its_own_weight():
    deck, outcome = live.run(mohr_coulomb(live.block()))

    assert '"name": "GeoMohrCoulombLawPlaneStrain"' in deck["materials"]
    assert ran(outcome)


def test_a_mohr_coulomb_soil_yields_under_a_strip_load():
    _, elastic = live.run(live.block(loads=[STRIP], stages=STAGES))
    _, plastic = live.run(mohr_coulomb(live.block(loads=[STRIP], stages=STAGES)))

    assert ran(elastic) and ran(plastic)
    assert settlement(elastic, 2) < settlement(plastic, 2) < 1.1 * settlement(elastic, 2)
