"""The Mohr-Coulomb UDSM library as `core/model/udsm_parser.py` reads it, without loading it.

`core/model/udsm_libraries/MohrCoulomb64.dll` loads on Windows only, so a test that needs its models on
any system takes them from here (`udsm.using([mohr_coulomb()])`). The strings are the
library's own, as the parser printed them on 2026-11-19; `tests/test_udsm.py` checks them
against the library on Windows.
"""

from __future__ import annotations

from core.model import udsm

MOHR_COULOMB_READ = {
    "number": 1,
    "name": "Mohr-Coulomb",
    "parameters": [
        {"name": "1. E", "unit": "F/L^2#"},
        {"name": "2. @n#_ur", "unit": "-"},
        {"name": "3. c'", "unit": "F/L^2#"},
        {"name": "4. @f#_peak#", "unit": "deg"},
        {"name": "5. @y#_peak#", "unit": "deg"},
        {"name": "6. |@s#_t, cut-off#|", "unit": "F/L^2#"},
        {"name": "7. yield function (MC=1; DP=2; MNC=3; MN=4)", "unit": "-"},
        {"name": "8. @n#_un# (UMAT)", "unit": "-"},
    ],
}


def mohr_coulomb() -> udsm.Model:
    return udsm.model("MohrCoulomb64.dll", MOHR_COULOMB_READ)


def unknown() -> udsm.Model:
    """A model Styx knows nothing of beyond what its library says: no start values."""
    return udsm.model("Creep.dll", {"number": 2, "name": "Soft clay creep",
                                       "parameters": [{"name": "1. @l#*", "unit": "-"},
                                                      {"name": "2. p_ref", "unit": "F/L^2#"},
                                                      {"name": "3. t_ref", "unit": "T"}]})
