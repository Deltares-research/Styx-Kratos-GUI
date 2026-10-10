"""CROW with Mohr-Coulomb soils and Coulomb contacts, held to Kratos' own case
(`crow_validation/mohr_coulomb_clay-sand/`, distilled into `fixtures/crow_mc/` by
`make_crow_mc_fixture.py`). The live run against its wall curves is
`tests/kratos/test_live_crow_mc.py`.

A soil being a Kratos property set (app/schemas.py `KratosPropertySet`) is what makes
this case writable at all: the laws are named, not mapped, and the variables are the
reference's own. What the application still decides is checked here -- which file each
stage reads, and which soil each stretch of contact takes its strength from.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app import build, crow, kratos
from app.schemas import MeshRequest, Project

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "crow_mc"
REFERENCE = json.loads((FIXTURE / "MaterialParameters.json").read_text(encoding="utf-8"))

PAIRS = [
    # our part -> the reference's property set (1-based), as test_crow_reference pairs them
    ("Soil_Top", 1), ("Soil_Middle", 1), ("Soil_Bottom", 2),
    ("Interface_Soil_Top", 3), ("Interface_Soil_Bottom", 4),
    ("SheetPileWall", 5), ("Strut", 6),
]

ABSENT_FROM_OURS = {
    # The wall: the same stiffness under the other beam law's names (test_crow_reference).
    5: {"THICKNESS", "THICKNESS_EFFECTIVE_Y"},
}


@pytest.fixture(scope="module")
def export() -> dict:
    project = crow.crow_mohr_coulomb_project(staged=True)
    with build.session():
        return kratos.export_project(project, MeshRequest(**project.mesh.model_dump()))


def sets(text: str) -> dict[str, dict]:
    return {entry["model_part_name"].split(".", 1)[1]: entry["Material"]
            for entry in json.loads(text)["properties"]}


def reference(index: int) -> dict:
    return REFERENCE["properties"][index - 1]["Material"]


@pytest.mark.parametrize("part, index", PAIRS)
def test_each_set_uses_the_reference_law_after_the_k0_stage(export, part, index):
    ours = sets(export["materials"])[part]["constitutive_law"]["name"]
    theirs = reference(index)["constitutive_law"]["name"]
    if index == 5:      # the wall's law is ours on purpose (test_crow_reference)
        assert ours == "TimoshenkoBeamElasticConstitutiveLaw"
    else:
        assert ours == theirs


@pytest.mark.parametrize("part, index", PAIRS)
def test_every_shared_variable_carries_the_reference_number(export, part, index):
    ours = sets(export["materials"])[part]["Variables"]
    theirs = reference(index)["Variables"]
    differing = {k: (ours[k], theirs[k]) for k in set(ours) & set(theirs)
                 if not (ours[k] == theirs[k] or (
                     isinstance(theirs[k], float) and not isinstance(theirs[k], bool)
                     and math.isclose(ours[k], theirs[k], rel_tol=1e-4, abs_tol=1e-12)))}
    assert differing == {}


@pytest.mark.parametrize("part, index", PAIRS)
def test_nothing_the_reference_writes_is_missing(export, part, index):
    ours = sets(export["materials"])[part]["Variables"]
    theirs = reference(index)["Variables"]
    assert set(theirs) - set(ours) == ABSENT_FROM_OURS.get(index, set())


def test_the_k0_stage_is_elastic_whatever_the_model(export):
    """Kratos' own MC case runs stage 1 on the elastic `common/initial_materials.json`:
    the K0 procedure settles an elastic stress field, and the plastic law takes over
    from stage 2. So the K0 stage's file names the elastic counterparts, and only it."""
    initial = sets(export["initial_materials"])
    assert initial["Soil_Top"]["constitutive_law"]["name"] == "GeoLinearElasticPlaneStrain2DLaw"
    assert initial["Interface_Soil_Top"]["constitutive_law"]["name"] == \
        "GeoIncrementalLinearElasticInterfaceLaw"
    assert initial["Soil_Top"]["Variables"]["K0_NC"] == 0.62
    later = sets(export["materials"])
    assert later["Soil_Top"]["constitutive_law"]["name"] == "GeoMohrCoulombLawPlaneStrain"


def test_each_contact_takes_the_strength_reduction_of_the_soil_it_runs_against(export):
    """The reference reduces the clay's strength by 0.48 and the sand's by 0.57 -- each
    soil's own Rinter. A contact section that names no Rinter takes
    the soil's (Material.r_inter)."""
    later = sets(export["materials"])
    clay, sand = later["Interface_Soil_Top"]["Variables"], later["Interface_Soil_Bottom"]["Variables"]
    assert clay["GEO_COHESION"] == pytest.approx(1440.65, rel=1e-5)
    assert clay["GEO_FRICTION_ANGLE"] == pytest.approx(11.25, rel=1e-6)
    assert sand["GEO_FRICTION_ANGLE"] == pytest.approx(20.0, rel=1e-6)


def test_the_elastic_crow_is_unchanged_by_any_of_this():
    """A contact section that does name an Rinter still uses it everywhere."""
    project = crow.crow_project(staged=True)
    assert project.interface_sections[0].r_inter == 0.7


def test_the_mc_project_is_an_ordinary_project():
    project = crow.crow_mohr_coulomb_project(staged=True)
    assert Project.model_validate(project.model_dump(mode="json")) == project
    assert {m.constitutive_law for m in project.materials} == {"GeoMohrCoulombLawPlaneStrain"}


SOLVER = {
    # Kratos' common stage deck, which both CROW cases run: the plastic stages are given
    # more iterations, and the last two their own tolerances.
    "4_First_excavation": (1e-3, 500),
    "6_Second_excavation": (1e-4, 300),
    "7_Third_excavation": (1e-2, 300),
}


@pytest.mark.parametrize("stage, expected", sorted(SOLVER.items()))
def test_the_plastic_stages_get_the_reference_iterations_and_tolerance(export, stage, expected):
    """A Mohr-Coulomb stage converges slowly; with the elastic case's 150 iterations the
    first excavation stops at a residual ratio of 1.07e-3 against 1e-3. The phases carry
    the reference's own numbers, as a user would type them per phase."""
    solver = json.loads(export["project_parameters"])["stages"][stage]["stage_settings"][
        "solver_settings"]
    assert (solver["residual_relative_tolerance"], solver["max_iterations"]) == expected


def test_the_script_writes_the_mohr_coulomb_deck(tmp_path):
    """`python examples/crow/crow_mohr_coulomb.py --out <dir>` goes through here."""
    assert crow.main(["crow", "--mohr-coulomb", "--out", str(tmp_path)]) == 0
    written = sorted(p.name for p in tmp_path.iterdir())
    assert "initial_materials.json" in written and "ProjectParameters.json" in written
    laws = {e["Material"]["constitutive_law"]["name"] for e in json.loads(
        (tmp_path / "MaterialParameters.json").read_text(encoding="utf-8"))["properties"]}
    assert "GeoMohrCoulombLawPlaneStrain" in laws
