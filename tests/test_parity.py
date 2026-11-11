"""Anti-drift guard: the Python seed project must agree with the base UI's sample data
in frontend/base/js/data.js.
"""

from core.model.templates import seed_project
from tests import frozen


def test_layers_match_frozen_data_js():
    """The seed's layers are the mockup's at its first borehole, the levels its geometry
    was built from. The mockup's other boreholes have no counterpart: the project has no
    boreholes."""
    first = frozen.boreholes()[0]["id"]
    expected = [{"id": layer["id"], "name": layer["name"], "mat": layer["mat"],
                 "top": layer["tops"][first], "bottom": layer["bots"][first]}
                for layer in frozen.layers()]
    assert expected, "frozen LAYERS parsed as empty -- the guard would pass vacuously"
    assert [layer.model_dump() for layer in seed_project(simple=False).layers] == expected


def test_materials_match_frozen_data_js():
    """Compared on the fields the mockup actually defines, the way the layers test above
    already is.

    `js/data.js` is frozen in the strong sense -- one commit, never edited since -- so a
    solver input it never carried is backend-only by construction rather than drift for
    this guard to catch. `k0_nc` is the first of those: it exists for the initial stage's
    k0 procedure (plan/outdated/staged-construction-plan.md sec C4), which postdates the mockup
    entirely. Every field the mockup *does* define is still pinned.
    """
    from core.model import migration, templates
    expected = frozen.materials()
    assert expected, "frozen MATERIALS parsed as empty -- the guard would pass vacuously"
    demo = [{k: v for k, v in m.items() if k in expected[0]} for m in templates._DEMO_MATERIALS]
    assert demo == expected
    # And the seed is that table, as every project in that shape is converted.
    project = seed_project(simple=False)
    assert [m.model_dump() for m in project.materials] == [
        templates.Material.model_validate(
            migration.without_water(migration.material(m, project.dimension))).model_dump()
        for m in templates._DEMO_MATERIALS]


def test_seed_layers_reach_the_domain_floor():
    project = seed_project(simple=False)
    deepest = min(layer.bottom for layer in project.layers)
    assert deepest == project.domain.y_bottom
