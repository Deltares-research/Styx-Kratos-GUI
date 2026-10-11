"""Anti-drift guard: the Python seed project must agree with the base UI's sample data
in live/base/js/data.js.
"""

from app.seed import seed_project
from tests import frozen


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
    """Compared on the fields the mockup actually defines, the way the layers test above
    already is.

    `js/data.js` is frozen in the strong sense -- one commit, never edited since -- so a
    solver input it never carried is backend-only by construction rather than drift for
    this guard to catch. `k0_nc` is the first of those: it exists for the initial stage's
    k0 procedure (plan/outdated/staged-construction-plan.md sec C4), which postdates the mockup
    entirely. Every field the mockup *does* define is still pinned.
    """
    from app import legacy, seed
    expected = frozen.materials()
    assert expected, "frozen MATERIALS parsed as empty -- the guard would pass vacuously"
    demo = [{k: v for k, v in m.items() if k in expected[0]} for m in seed._DEMO_MATERIALS]
    assert demo == expected
    # And the seed is that table, as every project in that shape is converted.
    project = seed_project(simple=False)
    assert [m.model_dump() for m in project.materials] == [
        seed.Material.model_validate(legacy.material(m, project.dimension)).model_dump()
        for m in seed._DEMO_MATERIALS]


def test_seed_layers_reach_the_domain_floor():
    project = seed_project(simple=False)
    deepest = min(layer.bots["bh1"] for layer in project.layers)
    assert deepest == project.domain.y_bottom
