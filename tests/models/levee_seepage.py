"""Seepage under and through a clay levee: a steady-state groundwater flow, as the GUI
tutorial (`docs/gui_tutorials/levee_seepage_case.md`) builds it.

A section 90 m wide, from y = -22 m up to the crest at 6 m: a sand aquifer from -22 to
-2 m and a clay cover from -2 to 0 m, both soil layers across the section, and on the
cover a clay levee drawn as two polygons, a core that reaches 0.5 m into the cover and an
outer layer around it. The river, at 5.0 m, holds the left side, the foreland and the
outer slope; the right side is held at the polder level, -0.5 m. The inner slope and the
polder surface are a seepage face; the crest and the bottom are closed. One stage of the
type Flow (Pw), started from a phreatic line that drops through the levee.

The soils carry what the Soil materials window lists for a fully coupled linear elastic
soil with a Van Genuchten retention law, and nothing else. The water is the project's:
its bulk modulus and viscosity are set under Water in that window, and its unit weight
is water's own, 10 kN/m3. A conductivity of 1 m/day is an intrinsic permeability of
K mu / gamma_w = 1.157e-12 m2.

The supports a new project has stay: a Flow (Pw) stage does not read them. The drawn
parts carry a recipe and no .brep; `project()` builds them, as a model script does:

    run tests/models/levee_seepage.py
"""

from __future__ import annotations

from core import scripting
from core.model.schemas import (CustomPart, Domain, Fluid, Material, MeshSettings, Project,
                                SeepageCondition, SoilLayer, Stage, WaterPressureCondition,
                                standard_conditions)

NAME = "levee_seepage"
"""The project's name, which also names the deck's files (`levee_seepage.mdpa`)."""

LEFT_X, RIGHT_X = -36.0, 54.0
BOTTOM_Y, GROUND_Y, CREST_Y = -22.0, 0.0, 6.0
AQUIFER_TOP_Y = -2.0
Z0, Z1 = -10.0, 10.0
"""A new project's out-of-plane extent: a drawn polygon is swept over all of it."""

CORE = [(-14.0, 0.0), (0.0, 4.5), (4.0, 4.5), (18.0, 0.0), (4.0, -0.5), (0.0, -0.5)]
OUTER_LAYER = [(-18.0, 0.0), (0.0, CREST_Y), (4.0, CREST_Y), (22.0, 0.0), (18.0, 0.0),
               (4.0, 4.5), (0.0, 4.5), (-14.0, 0.0)]

RIVER_LEVEL, POLDER_LEVEL = 5.0, -0.5
CUT_OFF = 1.0e5
"""Pa: the most suction a water pressure condition gives above its level."""
START_PHREATIC_LINE = [(LEFT_X, RIVER_LEVEL), (-2.0, RIVER_LEVEL), (15.0, POLDER_LEVEL),
                       (RIGHT_X, POLDER_LEVEL)]

PERMEABILITY = 1.1574074074074074e-12
"""m2: 1 m/day, with a viscosity of 1e-3 Pa s and a water unit weight of 10 kN/m3."""
WATER = Fluid(bulk_modulus=1.0e20, dynamic_viscosity=1.0e-3)

SOIL = {
    # In the order the Soil materials window asks for them: a choice first, as it lists
    # the fields that follow from it.
    "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
    "RETENTION_LAW": "VanGenuchtenLaw",
    "YOUNG_MODULUS": 1.0e4,
    "POISSON_RATIO": 0.3,
    "DENSITY_SOLID": 2650.0,
    "POROSITY": 0.3333,
    "SATURATED_SATURATION": 1.0,
    "RESIDUAL_SATURATION": 0.0620347394540943,
    "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": 2610.9660574412533,
    "VAN_GENUCHTEN_GN": 1.3774,
    "PERMEABILITY_XX": PERMEABILITY,
    "PERMEABILITY_YY": PERMEABILITY,
    "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-4,
    "VAN_GENUCHTEN_GL": 1.25,
    "BULK_MODULUS_SOLID": 1.0e20,
    "BIOT_COEFFICIENT": 1.0,
}
"""The variables of both soils, SI."""


def _soil(id_: str, name: str, color: str) -> Material:
    return Material(id=id_, name=name, color=color,
                    constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables=dict(SOIL))


def _drawn(key: str, label: str, material: str,
           corners: list[tuple[float, float]]) -> CustomPart:
    """A polygon drawn in the section, swept over the model's depth as the GUI does."""
    return CustomPart(
        key=key, label=label, source="gui", mat=material,
        recipe={"kind": "polygon_extrude", "label": label, "material": material,
                "vertices": [[x, y, Z0] for x, y in corners],
                "extrusion": [0.0, 0.0, Z1 - Z0]})


CONDITIONS = [
    WaterPressureCondition(id="river_head", name="River head", on="line",
                           points=[(LEFT_X, BOTTOM_Y), (LEFT_X, GROUND_Y), (-18.0, GROUND_Y),
                                   (0.0, CREST_Y)],
                           fluid_pressure_type="Hydrostatic",
                           reference_coordinate=RIVER_LEVEL, pressure_tension_cut_off=CUT_OFF),
    WaterPressureCondition(id="polder_head", name="Polder head", on="line",
                           points=[(RIGHT_X, GROUND_Y), (RIGHT_X, BOTTOM_Y)],
                           fluid_pressure_type="Hydrostatic",
                           reference_coordinate=POLDER_LEVEL, pressure_tension_cut_off=CUT_OFF),
    SeepageCondition(id="seepage_face", name="Seepage face", on="line",
                     points=[(4.0, CREST_Y), (22.0, GROUND_Y), (RIGHT_X, GROUND_Y)]),
    WaterPressureCondition(id="start", name="Start values", on="domain",
                           fluid_pressure_type="Phreatic_Multi_Line", is_fixed=False,
                           x_coordinates=[x for x, _ in START_PHREATIC_LINE],
                           y_coordinates=[y for _, y in START_PHREATIC_LINE],
                           pressure_tension_cut_off=CUT_OFF),
]
"""The water conditions, in the order the tutorial makes them."""

STAGE = Stage(id="initial", name="Flow", calculation="flow",
              convergence_criterion="residual_criterion", absolute_tolerance=1e-9,
              max_iterations=300, tolerated_error=1e-4)
"""A new project's initial stage, made a flow stage that converges on the residual, as
Kratos' seepage decks do. The seepage strategy opens or closes one node of the face per
iteration, and the face has about 55 nodes at 1 m: 300 iterations leave room for all."""


def levee_project() -> Project:
    """The model, its drawn parts without their solids."""
    sand = _soil("sand", "Sand", "#e6c86e")
    clay = _soil("clay", "Clay", "#8fa37a")
    return Project(
        name=NAME,
        dimension=2,
        domain=Domain(x0=LEFT_X, x1=RIGHT_X, z0=Z0, z1=Z1, y_top=GROUND_Y,
                      y_bottom=BOTTOM_Y),
        materials=[sand, clay],
        fluid=WATER,
        layers=[SoilLayer(id="cover", name="Cover", mat=clay.id, top=GROUND_Y,
                          bottom=AQUIFER_TOP_Y),
                SoilLayer(id="aquifer", name="Aquifer", mat=sand.id, top=AQUIFER_TOP_Y,
                          bottom=BOTTOM_Y)],
        custom_parts=[_drawn("levee_core", "Levee core", clay.id, CORE),
                      _drawn("levee_outer", "Levee outer layer", clay.id, OUTER_LAYER)],
        boundary_conditions=[*standard_conditions(), *CONDITIONS],
        mesh=MeshSettings(element_size=1.0, order=1),
        stages=[STAGE],
    )


def project() -> Project:
    """`run tests/models/levee_seepage.py`: the model with its drawn parts built."""
    return scripting.with_solids(levee_project())



