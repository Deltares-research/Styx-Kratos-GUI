"""The Muskat column against Kratos' own `GeoMechanicsApplication/tests/Muskat`, read from
the Kratos source beside the configured build. Opt-in: `pytest --run-kratos`.

The quick tier holds the decks of `tests/models/muskat.py` to copies of the reference
decks (`tests/test_kratos_flow.py`), and the runs to copies of the values `test_Muskat.py`
asserts (`KRATOS_A`, `KRATOS_B`). Here the copies are held to the files themselves, so
neither drifts from Kratos when Kratos changes its test.
"""

from __future__ import annotations

import pytest

from core.geometry import solid_model
from core.kratos import writer
from tests import muskat_reference as reference
from tests.models import muskat

pytestmark = pytest.mark.kratos

CASES = {"saturated_hydrostatic": (lambda: muskat.muskat(order=2), muskat.KRATOS_A),
         "van_genuchten_hydrostatic": (muskat.van_genuchten, muskat.KRATOS_B)}
"""Kratos' case -> the model of it, and the values its run is held to."""


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


@pytest.mark.parametrize("case", CASES)
def test_the_values_a_run_is_held_to_are_kratos_own(case):
    assert reference.expected(case) == CASES[case][1]


def without_water_density(materials: list) -> list:
    """The materials, each without its `DENSITY_WATER`: the project's is 10 kN/m3 over g
    to the last digit, where Kratos' deck rounds it to six."""
    return [(law, {k: v for k, v in variables.items() if k != "DENSITY_WATER"})
            for law, variables in materials]


@pytest.mark.parametrize("case", CASES)
def test_the_deck_is_kratos_own(gmsh_session, case):
    ours = reference.deck_view(writer.export_project(CASES[case][0]()))
    theirs = reference.reference_view(case)
    (stage,), (wanted,) = ours["stages"], theirs["stages"]

    assert {key: stage["solver"].get(key) for key in wanted["solver"]} == wanted["solver"]
    for group in reference.GROUPS:
        assert stage[group] == wanted[group], group
    assert stage["nodal_results"] == wanted["nodal_results"]
    assert without_water_density(ours["materials"]) == without_water_density(
        theirs["materials"])
    for (_, mine), (_, kratos) in zip(ours["materials"], theirs["materials"]):
        assert mine["DENSITY_WATER"] == pytest.approx(kratos["DENSITY_WATER"], rel=1e-5)
    assert {name for name, _ in ours["mesh"]["elements"]} == reference.reference_elements()
    assert not ours["mesh"]["conditions"]
