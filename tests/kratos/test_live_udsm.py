"""A soil of the Mohr-Coulomb UDSM, run in Kratos against the built-in Mohr-Coulomb law.
Opt-in: `pytest --run-kratos`.

The library is `core/model/udsm_libraries/MohrCoulomb64.dll`, read and copied into the deck as the GUI's
Calculate does. Under the 50 kPa strip load of `test_live_soil_models`, after a K0 stage
that runs both soils elastic, a soil of the library settles as the same soil on
`GeoMohrCoulombLawPlaneStrain`: 0.319924 m each when this was written (2026-11-20), with
E = 2 MPa, nu = 0.3, c = 2 kPa, phi = 25 degrees, no dilatancy, and the library's tension
cut-off at the apex, c / tan(phi), where it cuts nothing off.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from core import session
from core.model import soil_models
from core.model import udsm
from tests.kratos import test_live_conditions as live
from tests.kratos import test_live_soil_models as soils
from tests.kratos.test_live_conditions import runs_root  # noqa: F401  (the fixture)

pytestmark = [pytest.mark.kratos,
              pytest.mark.skipif(sys.platform != "win32",
                                 reason="core/model/udsm_libraries has the Windows library only")]

E, NU, C, PHI = 2.0e6, 0.3, 2000.0, 25.0


def every_soil(model: str, **variables):
    project = live.block(loads=[soils.STRIP], stages=soils.STAGES)
    for material in project.materials:
        project = session.update_material(project, material.id, model=model)
        project = session.update_material(project, material.id, variables=variables)
    return project


def test_the_mohr_coulomb_udsm_settles_as_the_built_in_mohr_coulomb_law():
    assert [m.id for m in udsm.models()] == ["MohrCoulomb64:1"]
    built_in = every_soil(soil_models.MOHR_COULOMB, YOUNG_MODULUS=E, POISSON_RATIO=NU,
                          GEO_COHESION=C, GEO_FRICTION_ANGLE=PHI, GEO_DILATANCY_ANGLE=0.0)
    library_soil = every_soil(soil_models.UDSM, E=E, nu_ur=NU, c=C, phi_peak=PHI, psi_peak=0.0,
                      sigma_t_cut_off=C / math.tan(math.radians(PHI)))

    deck, outcome = live.run(library_soil)
    _, reference = live.run(built_in)

    assert soils.ran(outcome) and soils.ran(reference)
    assert '"UDSM_NAME": "udsm/MohrCoulomb64.dll"' in deck["materials"]
    assert (Path(outcome["directory"]) / "udsm" / "MohrCoulomb64.dll").exists()
    assert soils.settlement(outcome, 2) == pytest.approx(soils.settlement(reference, 2),
                                                         rel=1e-6)
