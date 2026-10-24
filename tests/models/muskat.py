"""The semi-Muskat column: a steady-state groundwater flow between two fixed heads.

Kratos' own `tests/Muskat/saturated_hydrostatic` (case A of
plan/done/groundwater-flow-plan.md), as a project: a 1.62 m by 4 m column of saturated
soil, the water held at a level of 3.0 m on the left face and 1.6 m on the right, one
"Groundwater flow" phase. The soil and the heads are the reference deck's, value for
value. No support: a flow calculation leaves them out.

The head is linear in x between the faces, so the answer is known exactly
(`exact_water_pressure`, `EXACT_FLUX`), on any mesh. `KRATOS_A` holds Kratos' own
regression values.

`van_genuchten` is case B, Kratos' `tests/Muskat/van_genuchten_hydrostatic`: the same
column of a Van Genuchten soil, the right face at 1.62 m, started from a phreatic line.
It has no exact answer; `KRATOS_B` holds Kratos' own regression values, at the
coordinates of the nodes it checks them at.

`seepage` is case C, the full Muskat problem (the STEM Muskat geometry of Deltares'
FEA-Tools `GeometryGenerator`): the right face is the tail water up to 0.48 m and a
seepage face above it, where the water leaves the soil between the tail water and the
exit point of the phreatic line. Its checks are the water balance and the discharge of
Dupuit and Charny, `CHARNY_DISCHARGE`.

It is also a script the GUI can open:

    run tests/models/muskat.py
"""

from __future__ import annotations

from core.model.schemas import (AnchorRows, Borehole, BoxRefinement, Domain, Excavation,
                                Material, MeshSettings, Phase, Piles, Project,
                                SeepageCondition, SoilLayer, Struts, Wall,
                                WaterPressureCondition, Wells)

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

KRATOS_A = {
    198: ((0.8304801232729199, 3.716939567583279), {"WATER_PRESSURE": 14346.4}),
    244: ((0.9434537187649228, 2.180925085276376), {"WATER_PRESSURE": -37.4452}),
    183: ((0.8117444171098307, 0.2649876821528811), {"WATER_PRESSURE": -20335.1}),
    273: ((1.522244011956799, 1.513952935239066),
          {"EFFECTIVE_SATURATION": 1.0, "FLUID_FLUX_VECTOR": (6.00133e-06, -1.34793e-11)}),
    890: ((1.522173923948319, 3.89326785097679),
          {"EFFECTIVE_SATURATION": 1.0, "FLUID_FLUX_VECTOR": (6.00131e-06, -8.38038e-12)}),
    1440: ((1.518261045603592, 2.068026372947416),
           {"EFFECTIVE_SATURATION": 1.0, "FLUID_FLUX_VECTOR": (6.00133e-06, -1.35382e-11)}),
}
"""Kratos' regression values of case A (`test_Muskat.py`), by its node number: the node's
(x, y) in its `common/column.mdpa`, and the values it asserts there. They are the exact
answer, to the digits Kratos keeps."""


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


# ── Case B ──────────────────────────────────────────────────────────────────

RIGHT_LEVEL_B = 1.62
"""The right face's level in case B: 1.62 m in its deck, where case A has 1.6 m."""

PHREATIC_START = WaterPressureCondition(
    id="initial_phreatic", name="Initial phreatic line", on="domain",
    fluid_pressure_type="Phreatic_Multi_Line", is_fixed=False,
    x_coordinates=[-0.25, 0.05, 1.6, 1.7], y_coordinates=[3.22, 3.22, 0.48, 0.48],
    z_coordinates=[0.0, 0.0, 0.0, 0.0])
"""The water pressure case B starts from: a phreatic line, start values only. The x of
its first point is the deck's -0.25 (its README says -0.05)."""

KRATOS_B = {
    198: ((0.8304801232729199, 3.716939567583279), {"WATER_PRESSURE": 7939.92}),
    244: ((0.9434537187649228, 2.180925085276376), {"WATER_PRESSURE": -2753.0}),
    183: ((0.8117444171098307, 0.2649876821528811), {"WATER_PRESSURE": -20549.3}),
    273: ((1.522244011956799, 1.513952935239066),
          {"EFFECTIVE_SATURATION": 1.0, "FLUID_FLUX_VECTOR": (8.1665e-06, -1.08412e-06)}),
    890: ((1.522173923948319, 3.89326785097679),
          {"EFFECTIVE_SATURATION": 0.485245, "FLUID_FLUX_VECTOR": (4.6101e-09, 4.7292e-11)}),
    1440: ((1.518261045603592, 2.068026372947416),
           {"EFFECTIVE_SATURATION": 0.991294,
            "FLUID_FLUX_VECTOR": (2.37856e-06, -1.57026e-06)}),
}
"""Kratos' regression values of case B (`test_Muskat.py`), by its node number: the node's
(x, y) in its `common/column.mdpa`, and the values it asserts there."""


def van_genuchten(order: int = 2, size: float = 0.1) -> Project:
    """Case B, meshed at `size`: the Van Genuchten soil, the phreatic start, the heads at
    3.0 m and 1.62 m, and the flow phase with the deck's Newton-Raphson settings (100
    iterations, a relative tolerance of 1e-3).

    0.1 m rather than case A's 0.4 m: with this soil, Newton-Raphson falls into a cycle
    and stops without converging on some meshes (0.2 m and 0.15 m), and 0.1 m is the
    coarsest uniform size tried on which it converges and lands within 15 Pa of Kratos'
    values."""
    return muskat(
        conditions=[head("left_head", "left", LEFT_LEVEL),
                    head("right_head", "right", RIGHT_LEVEL_B), PHREATIC_START],
        phases=[Phase(id="flow", name="Flow", calculation="Groundwater flow",
                      max_iterations=100, tolerated_error=1e-3)],
        soil={**SOIL, **VAN_GENUCHTEN}, order=order,
        mesh=MeshSettings(element_size=size, order=order),
        name="Semi-Muskat, Van Genuchten")


def at_point(mesh, values: dict, x: float, y: float) -> list[float]:
    """A nodal result of a run at (x, y): interpolated linearly between the corners of the
    triangle that holds the point. `mesh` is `catalog.stage_mesh`, `values` a field's
    values by node. Corners only: a quadratic deck solves the water pressure there, and
    its mid-side values are interpolated already."""
    for nodes in mesh.elements().values():
        a, b, c = (mesh.nodes[n] for n in nodes[:3])
        area = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / area
        second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / area
        weights = (first, second, 1.0 - first - second)
        if min(weights) >= -1e-9:
            corners = [values[n] for n in nodes[:3]]
            return [sum(w * value for w, value in zip(weights, column))
                    for column in zip(*corners)]
    raise ValueError(f"({x}, {y}) is in no element of the mesh")


# ── Case C ──────────────────────────────────────────────────────────────────

TAIL_LEVEL = 0.48
"""The tail water on the right face, m: below it a fixed head, above it the seepage face."""

FACE_SIZE = 0.04
"""m: the element size along the right face, as the STEM geometry meshes it."""

CHARNY_DISCHARGE = CONDUCTIVITY * (LEFT_LEVEL ** 2 - TAIL_LEVEL ** 2) / (2 * WIDTH)
"""m3/s per metre: the discharge of Dupuit and Charny, K (H1² - H2²) / 2L, exact for a
saturated flow with a free surface. About 1.88e-5. A Van Genuchten soil lets some
water through above the phreatic line too, so its discharge is a little larger."""

TAIL = WaterPressureCondition(
    id="tail_water", name="Tail water", on="line",
    points=[(WIDTH, 0.0), (WIDTH, TAIL_LEVEL)], reference_coordinate=TAIL_LEVEL,
    pressure_tension_cut_off=CUT_OFF)
SEEPAGE_FACE = SeepageCondition(id="seepage_face", name="Seepage face", on="line",
                                points=[(WIDTH, TAIL_LEVEL), (WIDTH, HEIGHT)])
START = WaterPressureCondition(
    id="start", name="Start", on="domain", is_fixed=False, reference_coordinate=LEFT_LEVEL,
    pressure_tension_cut_off=CUT_OFF)
"""The start values of `tests/seepage_tests`: hydrostatic about the upstream level."""


def seepage(order: int = 1, max_iterations: int = 100) -> Project:
    """Case C: the Van Genuchten soil, the left head at 3.0 m, the tail water and the
    seepage face on the right face, meshed at 0.4 m and at `FACE_SIZE` along the right
    face, started from `START`. The flow phase has the seepage decks' tolerance of 1e-4
    and `max_iterations`: the seepage strategy opens one node of the face per iteration,
    and the face has 89 nodes at this size, of which 35 open (35 iterations, linear)."""
    return muskat(
        conditions=[head("left_head", "left", LEFT_LEVEL), TAIL, SEEPAGE_FACE, START],
        phases=[Phase(id="flow", name="Flow", calculation="Groundwater flow",
                      max_iterations=max_iterations, tolerated_error=1e-4)],
        soil={**SOIL, **VAN_GENUCHTEN}, order=order,
        mesh=MeshSettings(element_size=0.4, order=order, refinements=[BoxRefinement(
            kind="box", size=FACE_SIZE, thickness=0.5, x_min=WIDTH - 0.12, x_max=WIDTH,
            y_min=0.0, y_max=HEIGHT, z_min=0.0, z_max=1.0)]),
        name="Muskat, seepage face")


def seepage_outcome(mesh, results) -> tuple[list, float, float]:
    """What a run of case C did at the faces: the seepage face's nodes, bottom to top, as
    (y, water pressure, nodal flow rate); the flow rate through the left face (negative:
    taken in); and through the right face (positive: let out). `mesh` is
    `catalog.stage_mesh`, `results` `catalog.stage_results`."""
    pressure = results.field("WATER_PRESSURE").values
    rate = results.field("NODAL_WATER_FLOW_RATE").values
    face = sorted((mesh.nodes[n][1], pressure[n][0], rate[n][0]) for n in rate
                  if abs(mesh.nodes[n][0] - WIDTH) < 1e-9
                  and mesh.nodes[n][1] >= TAIL_LEVEL - 1e-9)
    inflow = sum(rate[n][0] for n in rate if abs(mesh.nodes[n][0]) < 1e-9)
    outflow = sum(rate[n][0] for n in rate if abs(mesh.nodes[n][0] - WIDTH) < 1e-9)
    return face, inflow, outflow


def exit_point(face: list) -> float:
    """The highest node of the face the strategy opened: fixed at zero, letting water
    out."""
    return max(y for y, pressure, rate in face if pressure == 0.0 and rate > 0.0)


def at_kratos_nodes(mesh, results, kratos: dict) -> dict:
    """A run's values at the places of Kratos' nodes: by node, by each variable `kratos`
    (`KRATOS_A`, `KRATOS_B`) holds there, the value's components."""
    return {node: {variable: at_point(mesh, results.field(variable).values, x, y)
                   for variable in values}
            for node, ((x, y), values) in kratos.items()}


def project() -> Project:
    """`run tests/models/muskat.py` opens the column, quadratic."""
    return muskat(order=2)
