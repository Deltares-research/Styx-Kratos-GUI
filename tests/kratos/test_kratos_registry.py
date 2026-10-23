"""Every Kratos name the exporter can write exists in the Kratos it runs on (plan sec 8.3).

The exporter's element, condition and law names live in tables in `core.kratos.writer` and
`core.kratos.materials`, several of them marked "check against the first real run". A name
Kratos does not know fails only when Kratos reads the deck -- a first-order section with
a sheet pile stopped at `LinearTimoshenkoCurvedBeamElement2D2N is not registered` while
every structural test passed. So every name in those tables is looked up in the
registrations of the configured build's own source (`KRATOS_REGISTER_ELEMENT`,
`..._CONDITION`, `..._CONSTITUTIVE_LAW` -- or the Python class for a law registered from
Python), which takes seconds and needs no run.

Opt-in (`--run-kratos`): it needs the Kratos checkout `kratos.local.json` points at.
A name that is known not to exist is listed in `KNOWN_MISSING` with the reason and what
fails because of it, so the gap is visible and the list can only shrink.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from core.kratos import writer, materials
from core.analysis import calculation

pytestmark = pytest.mark.kratos

KNOWN_MISSING = {
    # There is no linear U-Pw line interface; only the quadratic DiffOrder 3Plus3N one, a
    # displacement-only Geo_ULineInterfacePlaneStrainElement2Plus2N and the older
    # UPwSmallStrainInterfaceElement2D4N. Which replaces it is a modelling decision, so a
    # first-order section with an interface still cannot be run.
    "Geo_UPwLineInterfacePlaneStrainElement2Plus2N",
}


def checkout() -> Path:
    try:
        calculation.interpreter()
    except calculation.CalculationError as failure:
        pytest.skip(f"no Kratos configured: {failure}")
    build = calculation._settings().get("kratos") or ""
    root = Path(build).parents[1] if build else None
    if root is None or not (root / "applications").is_dir():
        pytest.skip(f"no Kratos source beside the build {build!r}")
    return root


@cache
def registered(root: Path) -> set[str]:
    names: set[str] = set()
    pattern = re.compile(r'KRATOS_REGISTER_(?:ELEMENT|CONDITION|CONSTITUTIVE_LAW)\(\s*"([^"]+)"')
    for folder in (root / "kratos", root / "applications"):
        for source in folder.rglob("*.cpp"):
            try:
                names |= set(pattern.findall(source.read_text(encoding="utf-8",
                                                              errors="ignore")))
            except OSError:
                continue
    return names


def exporter_names() -> dict[str, str]:
    """name -> where in the exporter it comes from."""
    out = {}
    for table in ("ELEMENTS", "FLOW_ELEMENTS", "BEAMS", "SHELLS", "CONDITIONS"):
        for key, (name, _) in getattr(writer, table).items():
            out[name] = f"writer.{table}[{key}]"
    for table in ("INTERFACES", "NORMAL_LOAD_CONDITIONS", "TRUSSES"):
        for key, name in getattr(writer, table).items():
            out[name] = f"writer.{table}[{key}]"
    for law in (*materials.LINEAR_ELASTIC, materials.ANCHOR_LAW,
                materials.PANEL_LAW, materials.INTERFACE_LAW,
                materials.BEAM_LAW):
        out[law] = "materials law"
    # Laws are typed into property sets now; the ones the test model's Mohr-Coulomb
    # variant types are held to the registry the same way.
    from tests.models import excavation
    for law in (excavation.MOHR_COULOMB, excavation.COULOMB_CONTACT):
        out[law] = "tests.models.excavation Mohr-Coulomb variant"
    return out


@pytest.mark.parametrize("name", sorted(exporter_names()))
def test_the_name_is_registered_in_kratos(name):
    known = registered(checkout())
    if name in KNOWN_MISSING:
        assert name not in known, f"{name} is registered now: take it off KNOWN_MISSING"
        pytest.xfail(f"{name} ({exporter_names()[name]}) is not registered in this Kratos")
    assert name in known, f"{name} ({exporter_names()[name]}) is not registered in Kratos"


def test_the_scan_found_the_registry():
    assert len(registered(checkout())) > 200
