"""The seed project — a faithful port of the frozen mockup's hard-coded model.

Every number here is traceable to the frozen demo, and tests/test_parity.py proves it
stays that way -- by name only, because the frame changed and the names with it: the
mockup is Z-up, this model is X across, Y up and Z out of plane. The values are the
same. Sources:

  domain, excavation, wall, strut, water levels   js/viewport.js:12-16
  wall thickness                                  js/viewport.js:109
  strut / anchor / pile / load / well geometry    js/viewport.js:118-229
  layers (the BH-1 levels), materials             js/data.js:313-355
  surface load magnitude                          js/data.js:426
"""

from core.model import migration
from core.model.schemas import (
    AnchorRows,
    Domain,
    Excavation,
    Material,
    MeshSettings,
    Piles,
    Project,
    SoilLayer,
    Struts,
    SurfaceLoad,
    Wall,
    WaterLevel,
    WaterPressureCondition,
    Wells,
    standard_conditions,
)

_DEMO_MATERIALS = [
    dict(id="m1", name="Fill", model="Mohr-Coulomb", type="Drained", color="#d8c48a",
         g_unsat=17.0, g_sat=20.0, E=15000, nu=0.30, c=1.0, phi=30.0, k=1.0,
         r_inter=0.70, interface_permeability="Neutral"),
    dict(id="m2", name="Sand, loose", model="Hardening Soil", type="Drained", color="#c4a86a",
         g_unsat=18.0, g_sat=20.5, E=25000, nu=0.28, c=0.5, phi=32.0, k=1.5,
         r_inter=0.70, interface_permeability="Neutral"),
    dict(id="m3", name="Clay, soft", model="Soft Soil", type="Undrained (A)", color="#8fa86b",
         g_unsat=15.0, g_sat=16.0, E=4000, nu=0.35, c=5.0, phi=22.0, k=0.0001,
         r_inter=0.50, interface_permeability="Impermeable"),
    dict(id="m4", name="Clay, stiff", model="Mohr-Coulomb", type="Undrained (A)", color="#6f8fa8",
         g_unsat=17.5, g_sat=18.5, E=12000, nu=0.33, c=15.0, phi=25.0, k=0.0005,
         r_inter=0.55, interface_permeability="Impermeable"),
    dict(id="m5", name="Sand, dense", model="Hardening Soil", type="Drained", color="#b08a6a",
         g_unsat=19.0, g_sat=21.0, E=45000, nu=0.25, c=0.0, phi=36.0, k=5.0,
         r_inter=0.75, interface_permeability="Neutral"),
    dict(id="m6", name="Bedrock", model="Linear Elastic", type="Non-porous", color="#8d8d99",
         g_unsat=24.0, g_sat=24.0, E=2.0e6, nu=0.20, c=None, phi=None, k=0.0,
         r_inter=1.00, interface_permeability="Impermeable"),
]
"""The frozen demo's material table, as js/data.js writes it (kN/m3, kN/m2, m/day). The
project holds Kratos property sets, so the seed converts these the way every project
saved in that shape is converted (`core/model/migration.py`)."""


def _materials(dim: int) -> list[Material]:
    return [Material.model_validate(migration.without_water(migration.material(m, dim)))
            for m in _DEMO_MATERIALS]


_LAYERS = [
    SoilLayer(id="L1", name="Soil_1", mat="m2", top=0.00, bottom=-8.00),
    SoilLayer(id="L2", name="Soil_2", mat="m4", top=-8.00, bottom=-25.00),
]
"""The demo's layers at its first borehole, BH-1: the levels its geometry was built from."""


def blank_project() -> Project:
    """What the server starts with: no soil, no structures -- an empty site.

    Plane strain, because that is what this app is for: the document opens as the
    x-y section, and the client comes up in it rather than drawing the solid model
    first and replacing it once the project arrives.

    None of the seeded demo's structures: a model has them when its author adds them.
    """
    return Project(
        name="Untitled project",
        layered_soil=True,
        dimension=2,
        # Centred on z = 0, so the 2D section is cut there: a section has to lie strictly
        # inside the z extent, and the middle is where a new one goes.
        domain=Domain(x0=0.0, x1=20.0, z0=-10.0, z1=10.0, y_top=0.0, y_bottom=-15.0),
        materials=[],
        layers=[],
        # No water level: a new model has none until its author sets one.
        mesh=MeshSettings(),
    )


def seed_project(simple: bool = True) -> Project:
    """A fresh, independently-mutable copy of the demo model.

    `simple` is the layered model, which raises none of the demo's pit, wall ring, struts,
    anchor rows, piles and wells, so it has none of them; the full build has them all.
    """
    demo = {} if simple else _demo_structures()
    return Project(
        name="Deep excavation — Rotterdam Zuid",
        layered_soil=simple,
        domain=(Domain(x0=0.0, x1=25.0, z0=0.0, z1=25.0, y_top=0.0, y_bottom=-25.0)
                if simple else
                Domain(x0=0.0, x1=50.0, z0=0.0, z1=40.0, y_top=0.0, y_bottom=-25.0)),
        materials=_materials(3),
        layers=[l.model_copy(deep=True) for l in _LAYERS],
        # js/viewport.js:180 — 9 x 12 m pad centred at (5.5, 20); magnitude js/data.js:426,
        # 20 kN/m2 there, in Pa here: the project is SI.
        loads=[SurfaceLoad(
            id="load", name="SurfaceLoad_1",
            x0=1.0, x1=10.0, z0=14.0, z1=26.0, thickness=0.25,
            components=(0.0, -20_000.0, 0.0),
        )],
        water=WaterLevel(y=-1.5),
        # The demo's ground is under water: hydrostatic about the level, fixed.
        boundary_conditions=[*standard_conditions(), WaterPressureCondition(
            id="pore_pressure", name="Pore pressure", on="domain",
            reference_coordinate=-1.5)],
        mesh=MeshSettings(element_size=2.5, order=2),
        **demo,
    )


def _demo_structures() -> dict:
    """The full build's own structures, which only `seed_project(simple=False)` has."""
    return {
        "excavation": Excavation(x0=12.0, x1=38.0, z0=10.0, z1=30.0, floor_y=-7.0),
        "wall": Wall(thickness=0.8, top_y=0.6, toe_y=-14.0),
        # js/viewport.js:120 — length PY1-PY0+1.6, i.e. 0.8 m past each pit face.
        "struts": Struts(xs=[14.0, 20.0, 26.0, 32.0], y=-3.0, radius=0.28, overhang=0.8,
                         waler_width=0.5, waler_height=0.6),
        # js/viewport.js:141-155 — two rows, outward and downward at 35 degrees.
        "anchor_rows": AnchorRows(xs=[15.0, 21.0, 27.0, 33.0], head_y=-4.5, length=11.0,
                                  inclination_deg=35.0, radius=0.11),
        # js/viewport.js:166-171 — 4x3 grid hanging from the pit floor.
        "piles": Piles(xs=[16.0, 22.0, 28.0, 34.0], zs=[14.0, 20.0, 26.0],
                       radius=0.3, length=9.0, top_y=-7.0),
        # js/viewport.js:215-227 — 15 m pipes hanging from the surface.
        "wells": Wells(positions=[(18.0, 15.0), (32.0, 25.0)], radius=0.35, top_y=0.0,
                       length=15.0),
    }
