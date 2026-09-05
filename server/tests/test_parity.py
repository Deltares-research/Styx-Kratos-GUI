"""Anti-drift guard: the Python seed project must agree with the frozen mockup.

Context — the mockup already contains exactly the kind of drift this catches. Geometry
lives in js/viewport.js while descriptions of it live in js/data.js, and they disagree:
anchors are 11 m in 3D (js/viewport.js:141) but "12.000 m" in the property grid
(js/data.js:418); the load pad is 9x12 = 108 m2 in 3D (js/viewport.js:180) but
"60.000 m2" in the grid (js/data.js:428); the tree claims 6 anchors and 3 beams
(js/data.js:532,536) where the viewport builds 8 and 6.

Once the backend owns geometry, that whole class of bug goes away — but during the
transition both definitions are live, so this test pins them together.
"""

import pytest

from app.seed import seed_project
from tests import frozen


@pytest.fixture(scope="module")
def vp() -> dict[str, float]:
    return frozen.viewport_constants()


def test_the_frozen_constant_block_is_still_where_we_think_it_is(vp):
    """If js/viewport.js is ever restructured, fail loudly here rather than silently
    parsing nothing and passing every other test in this file."""
    assert {"X0", "X1", "Y0", "Y1", "ZTOP", "ZBOT", "PX0", "PX1", "PY0", "PY1",
            "Z_PIT", "Z_WALL_TOE", "Z_WALL_TOP", "Z_WATER", "Z_STRUT"} <= vp.keys()


def test_domain_matches_frozen_viewport(vp):
    d = seed_project(simple=False).domain
    assert (d.x0, d.x1) == (vp["X0"], vp["X1"])
    assert (d.y0, d.y1) == (vp["Y0"], vp["Y1"])
    assert (d.z_top, d.z_bottom) == (vp["ZTOP"], vp["ZBOT"])


def test_excavation_matches_frozen_viewport(vp):
    e = seed_project(simple=False).excavation
    assert (e.x0, e.x1) == (vp["PX0"], vp["PX1"])
    assert (e.y0, e.y1) == (vp["PY0"], vp["PY1"])
    assert e.floor_z == vp["Z_PIT"]


def test_wall_matches_frozen_viewport(vp):
    w = seed_project(simple=False).wall
    assert w.toe_z == vp["Z_WALL_TOE"]
    assert w.top_z == vp["Z_WALL_TOP"]
    assert w.thickness == 0.8  # js/viewport.js:109, `var t = 0.8`


def test_struts_match_frozen_viewport(vp):
    s = seed_project(simple=False).struts
    assert s.z == vp["Z_STRUT"]
    assert s.xs == [14.0, 20.0, 26.0, 32.0]  # js/viewport.js:120
    assert s.radius == 0.28


def test_water_level_matches_frozen_viewport(vp):
    assert seed_project(simple=False).water.z == vp["Z_WATER"]


def test_boreholes_match_frozen_data_js():
    got = [b.model_dump() for b in seed_project(simple=False).boreholes]
    assert got == frozen.boreholes()


def test_layers_match_frozen_data_js():
    got = [
        {k: v for k, v in layer.model_dump().items() if k in {"id", "name", "mat", "tops", "bots"}}
        for layer in seed_project(simple=False).layers
    ]
    assert got == frozen.layers()


def test_materials_match_frozen_data_js():
    got = [m.model_dump() for m in seed_project(simple=False).materials]
    assert got == frozen.materials()


def test_seed_layers_reach_the_domain_floor(vp):
    """js/viewport.js:75 extrudes soil from layer.tops.bh1/bots.bh1 only, so the deepest
    bh1 bottom is what actually defines the 3D block depth."""
    deepest = min(layer.bots["bh1"] for layer in seed_project(simple=False).layers)
    assert deepest == vp["ZBOT"]
