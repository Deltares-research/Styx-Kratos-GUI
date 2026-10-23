"""The semi-Muskat column: a steady-state groundwater flow between two fixed heads.

Kratos' own `tests/Muskat/saturated_hydrostatic` (case A of
plan/active/groundwater-flow-plan.md), as a project: a 1.62 m by 4 m column of saturated
soil, the water held at a level of 3.0 m on the left face and 1.6 m on the right, one
"Groundwater flow" phase. The soil and the heads are the reference deck's, value for
value. No support: a flow calculation leaves them out.

The head is linear in x between the faces, so the answer is known exactly
(`exact_water_pressure`, `EXACT_FLUX`), on any mesh.

It is also a script the GUI can open:

    run tests/models/muskat.py
"""

from __future__ import annotations

from core.model.schemas import (AnchorRows, Borehole, Domain, Excavation, Material,
                                MeshSettings, Phase, Piles, Project, SoilLayer, Struts,
                                Wall, WaterPressureCondition, Wells)

NAME = "Semi-Muskat, saturated"

WIDTH, HEIGHT = 1.62, 4.0
LEFT_LEVEL, RIGHT_LEVEL = 3.0, 1.6
CUT_OFF = 1.0e5
"""The heads' `pressure_tension_cut_off`, in Pa: a suction the condition never exceeds."""

GAMMA_W = 1.0e4
"""The specific weight of the water the heads are written with, N/m3."""

SOIL = {
    "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
    "YOUNG_MODULUS": 1.0e+04,
    "POISSON_RATIO": 0.4,
    "DENSITY_SOLID": 2.29e+03,
    "DENSITY_WATER": 1.01937e+03,
    "POROSITY": 0.3333,
    "BULK_MODULUS_SOLID": 6.7e+19,
    "BULK_MODULUS_FLUID": 1.0e+20,
    "PERMEABILITY_XX": 6.9444e-13,
    "PERMEABILITY_YY": 6.9444e-13,
    "PERMEABILITY_XY": 0.0,
    "DYNAMIC_VISCOSITY": 1.0e-03,
    "BIOT_COEFFICIENT": 1.0,
    "RETENTION_LAW": "SaturatedLaw",
    "SATURATED_SATURATION": 0.403,
}
"""The reference deck's MaterialParameters.json `Variables`."""

VAN_GENUCHTEN = {
    "RETENTION_LAW": "VanGenuchtenLaw",
    "RESIDUAL_SATURATION": 2.5e-02,
    "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": 2.611e+03,
    "VAN_GENUCHTEN_GN": 1.377,
    "VAN_GENUCHTEN_GL": 1.25,
    "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-05,
}
"""What Kratos' `tests/Muskat/van_genuchten_hydrostatic` changes in the material."""

FLOW = Phase(id="flow", name="Flow", calculation="Groundwater flow")

CONDUCTIVITY = SOIL["PERMEABILITY_XX"] * SOIL["DENSITY_WATER"] * 9.81 / SOIL["DYNAMIC_VISCOSITY"]
"""K = k rho_w g / mu, m/s: the hydraulic conductivity Kratos' flow element uses."""

EXACT_FLUX = CONDUCTIVITY * (LEFT_LEVEL - RIGHT_LEVEL) / WIDTH
"""Darcy: the horizontal flux, m/s, the same everywhere. About 6.00e-6."""


def exact_water_pressure(x: float, y: float) -> float:
    """The water pressure at (x, y), Pa, in Kratos' sign (suction positive): the head falls
    linearly from the left level to the right one, and the cut-off bounds the suction."""
    level = LEFT_LEVEL - (LEFT_LEVEL - RIGHT_LEVEL) * x / WIDTH
    return min(GAMMA_W * (y - level), CUT_OFF)


def head(id: str, face: str, level: float, **fields) -> WaterPressureCondition:
    """A fixed hydrostatic water pressure on `face`, about `level`."""
    return WaterPressureCondition(id=id, name=id, on="face", face=face,
                                  reference_coordinate=level,
                                  pressure_tension_cut_off=CUT_OFF, **fields)


HEADS = [head("left_head", "left", LEFT_LEVEL), head("right_head", "right", RIGHT_LEVEL)]


def muskat(conditions: list | None = None, phases: list[Phase] | None = None,
           soil: dict | None = None, order: int = 1, **changes) -> Project:
    """The column, meshed at 0.4 m: `conditions` in place of the two heads, `phases` in
    place of the one flow phase, `soil` in place of the material's variables, and any
    other `Project` field in `changes`."""
    material = Material(id="sand", name="sand", color="#c4a86a",
                        constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                        variables=SOIL if soil is None else soil)
    fields = dict(
        name=NAME,
        layered_soil=True,
        dimension=2,
        domain=Domain(x0=0.0, x1=WIDTH, z0=0.0, z1=1.0, y_top=HEIGHT, y_bottom=0.0),
        boreholes=[Borehole(id="bh1", name="BH1", x=0.0, y=0.0, head=HEIGHT, water=0.0)],
        materials=[material],
        layers=[SoilLayer(id="soil", name="soil", mat=material.id,
                          tops={"bh1": HEIGHT}, bots={"bh1": 0.0})],
        boundary_conditions=HEADS if conditions is None else conditions,
        phases=[FLOW] if phases is None else phases,
        mesh=MeshSettings(element_size=0.4, order=order),
        # Required by the schema. A layered model with one excavation level cuts no pit
        # and builds none of the 3D demo structures.
        excavation=Excavation(x0=0.0, x1=1.0, z0=0.0, z1=1.0, levels=[HEIGHT - 1.0]),
        wall=Wall(thickness=0.5, top_y=HEIGHT, toe_y=HEIGHT - 1.0),
        struts=Struts(xs=[], y=HEIGHT, radius=0.1),
        anchor_rows=AnchorRows(xs=[], head_y=HEIGHT, length=1.0, inclination_deg=45.0,
                               radius=0.1),
        piles=Piles(xs=[], zs=[], radius=0.1, length=1.0, top_y=HEIGHT),
        wells=Wells(positions=[], radius=0.1, top_y=HEIGHT, length=1.0),
    )
    fields.update(changes)
    return Project(**fields)


def project() -> Project:
    """`run tests/models/muskat.py` opens the column, quadratic."""
    return muskat(order=2)
