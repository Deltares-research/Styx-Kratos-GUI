"""`material udsm`, and `material add|set --udsm` with a UDSM model's KEY=VALUE words:
the UDSM models of the libraries that come with Styx, in the terminal as in the material
window. The models come from `tests/fakes/udsm.py`, so these run on every system."""

from __future__ import annotations

import pytest

from core import session
from core.model import udsm
from tests.fakes import udsm as fakes


@pytest.fixture(autouse=True)
def the_mohr_coulomb_library():
    with udsm.using([fakes.mohr_coulomb()]):
        yield


def test_material_udsm_lists_each_model_with_its_keys_and_start_values(cli, site):
    ran = cli("material", site, "udsm")

    assert ran.code == 0, ran.err
    assert "MohrCoulomb64:1  Mohr-Coulomb  (MohrCoulomb64.dll, UDSM_NUMBER 1)" in ran.out
    assert "  E = 1e+07 Pa  (E)" in ran.out
    assert "  phi_peak = 30 °  (φ_peak)" in ran.out
    assert "  yield_function = 1  (yield function (MC=1; DP=2; MNC=3; MN=4))" in ran.out


def test_material_udsm_states_the_start_values_in_the_project_s_units(cli, site):
    assert cli("units", site, "kN").code == 0

    assert "  c = 1 kPa  (c')" in cli("material", site, "udsm").out


def test_material_udsm_says_when_no_library_runs_here(cli, site):
    with udsm.using([]):
        ran = cli("material", site, "udsm")
    assert ran.code == 0 and "No UDSM models on this system." in ran.out


def test_material_add_of_a_udsm_model_with_its_parameters(cli, site):
    ran = cli("material", site, "add", "clay", "--udsm", "MohrCoulomb64:1", "E=3e7",
              "phi_peak=33", "DENSITY_SOLID=1800", "POROSITY=0.3")

    assert ran.code == 0, ran.err
    clay = session.load(site).material("clay")
    assert clay.constitutive_law == "SmallStrainUDSM2DPlaneStrainLaw"
    assert clay.variables["UDSM_NAME"] == "MohrCoulomb64.dll"
    assert clay.variables["UMAT_PARAMETERS"] == [3.0e7, 0.3, 1000.0, 33.0, 0.0, 1000.0, 1.0,
                                                 0.0]
    assert "Still to fill in" not in ran.out
    assert ("clay  clay  User-defined (UDSM) Mohr-Coulomb (MohrCoulomb64:1) "
            "(SmallStrainUDSM2DPlaneStrainLaw)") in cli("material", site, "list").out


def test_material_add_of_the_udsm_model_takes_the_first_library_model(cli, site):
    ran = cli("material", site, "add", "clay", "--model", "udsm")

    assert ran.code == 0, ran.err
    assert session.load(site).material("clay").variables["UDSM_NUMBER"] == 1
    assert "Still to fill in before a calculation: DENSITY_SOLID, POROSITY" in ran.out


def test_material_set_changes_a_udsm_parameter_by_its_key(cli, site):
    assert cli("material", site, "add", "clay", "--udsm", "MohrCoulomb64:1").code == 0

    ran = cli("material", site, "set", "clay", "c=2500")

    assert ran.code == 0, ran.err
    assert session.load(site).material("clay").variables["UMAT_PARAMETERS"][2] == 2500.0


def test_material_set_refuses_an_unknown_udsm_model_and_a_value_that_is_no_number(cli, site):
    assert cli("material", site, "add", "clay", "--udsm", "MohrCoulomb64:1").code == 0

    unknown = cli("material", site, "set", "clay", "--udsm", "Creep:1")
    text = cli("material", site, "set", "clay", "c=soft")

    assert unknown.code != 0 and "there is no UDSM model 'Creep:1'" in unknown.err
    assert text.code != 0 and "c must be a number" in text.err
