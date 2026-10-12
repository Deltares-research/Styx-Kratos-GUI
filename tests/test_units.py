"""The project unit system (core/model/units.py): Kratos has no units, only a consistent set, so
the project picks one and every number -- input, deck and result -- is in it."""

from __future__ import annotations

import math

import pytest

from core.model import units


def test_the_systems_on_offer_and_the_default():
    assert units.DEFAULT == "SI"
    assert set(units.SYSTEMS) == {"SI", "kN"}


@pytest.mark.parametrize("system", ["SI", "kN"])
def test_gravity_is_the_same_number_in_every_system(system):
    """Length is metres and time seconds in both, so 9.81 m/s2 needs no conversion --
    which is what lets the deck carry the project's numbers verbatim."""
    assert units.gravity(system) == 9.81


@pytest.mark.parametrize("quantity, si, kn", [
    (units.STRESS, 150_000.0, 150.0),
    (units.FORCE, 2_000.0, 2.0),
    (units.LINE_FORCE, 10_000.0, 10.0),
    (units.DENSITY, 1834.86, 1.83486),
    (units.SPECIFIC_WEIGHT, 10_000.0, 10.0),
    (units.STIFFNESS_PER_AREA, 3.0e7, 3.0e4),
    (units.VISCOSITY, 1.0e-3, 1.0e-6),
    (units.AREA, 0.01, 0.01),
    (units.INERTIA, 1e-4, 1e-4),
    (units.LENGTH, 0.5, 0.5),
    (units.DIMENSIONLESS, 0.3, 0.3),
    (units.ANGLE, 30.0, 30.0),
])
def test_a_value_converts_between_the_systems_and_back(quantity, si, kn):
    assert units.convert(si, quantity, "SI", "kN") == pytest.approx(kn)
    assert units.convert(kn, quantity, "kN", "SI") == pytest.approx(si)
    assert units.convert(si, quantity, "SI", "SI") == si


def test_the_kn_system_is_consistent_force_is_mass_times_acceleration():
    """kN = t * m / s2: a density in t/m3 times gravity is a specific weight in kN/m3."""
    density_si = 2000.0
    density_kn = units.convert(density_si, units.DENSITY, "SI", "kN")
    weight_kn = density_kn * units.gravity("kN")
    assert weight_kn == pytest.approx(units.convert(density_si * 9.81,
                                                    units.SPECIFIC_WEIGHT, "SI", "kN"))


@pytest.mark.parametrize("quantity, si, kn", [
    (units.STRESS, "Pa", "kPa"),
    (units.FORCE, "N", "kN"),
    (units.LINE_FORCE, "N/m", "kN/m"),
    (units.MOMENT_PER_LENGTH, "N·m/m", "kN·m/m"),
    (units.DENSITY, "kg/m³", "t/m³"),
    (units.SPECIFIC_WEIGHT, "N/m³", "kN/m³"),
    (units.STIFFNESS_PER_AREA, "N/m³", "kN/m³"),
    (units.AREA, "m²", "m²"),
    (units.DIMENSIONLESS, "", ""),
])
def test_labels(quantity, si, kn):
    assert units.label(quantity, "SI") == si
    assert units.label(quantity, "kN") == kn


@pytest.mark.parametrize("name, quantity", [
    ("YOUNG_MODULUS", units.STRESS), ("GEO_COHESION", units.STRESS),
    ("BULK_MODULUS_SOLID", units.STRESS), ("TRUSS_PRESTRESS_PK2", units.STRESS),
    ("DENSITY_SOLID", units.DENSITY), ("DENSITY_WATER", units.DENSITY),
    ("DENSITY", units.DENSITY), ("DYNAMIC_VISCOSITY", units.VISCOSITY),
    ("INTERFACE_NORMAL_STIFFNESS", units.STIFFNESS_PER_AREA),
    ("CROSS_AREA", units.AREA), ("I33", units.INERTIA), ("THICKNESS", units.LENGTH),
    ("POISSON_RATIO", units.DIMENSIONLESS), ("POROSITY", units.DIMENSIONLESS),
    ("GEO_FRICTION_ANGLE", units.ANGLE), ("PERMEABILITY_XX", units.PERMEABILITY),
])
def test_the_dimension_of_a_kratos_variable(name, quantity):
    assert units.VARIABLES[name] is quantity


def test_converting_a_variables_block_names_what_it_could_not():
    block = {"YOUNG_MODULUS": 3.0e7, "POISSON_RATIO": 0.3, "DENSITY_SOLID": 2000.0,
             "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "UDSM_PARAMETERS": [1.0, 2.0],
             "MY_OWN_STIFFNESS": 5.0, "IS_FORTRAN_UDSM": True}
    converted, unknown = units.convert_variables(block, "SI", "kN")
    assert converted == {"YOUNG_MODULUS": 3.0e4, "POISSON_RATIO": 0.3,
                         "DENSITY_SOLID": 2.0, "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
                         "UDSM_PARAMETERS": [1.0, 2.0], "MY_OWN_STIFFNESS": 5.0,
                         "IS_FORTRAN_UDSM": True}
    assert unknown == ["UDSM_PARAMETERS", "MY_OWN_STIFFNESS"]
    assert list(converted) == list(block)          # order kept: it is the deck's order


def test_an_unknown_system_is_refused():
    with pytest.raises(ValueError, match="unit system"):
        units.convert(1.0, units.STRESS, "SI", "imperial")


def test_converting_keeps_finite_values_finite():
    assert math.isfinite(units.convert(1e300, units.STRESS, "kN", "SI"))
