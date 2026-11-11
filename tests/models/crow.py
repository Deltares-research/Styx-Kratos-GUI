"""The CROW sheet-pile excavation, as Kratos validates it: linear elastic and Mohr-Coulomb.

Kratos' `GeoMechanicsApplication/tests/crow_validation` (run by its `test_CROW_case.py`)
is a 2D pit behind a sheet pile with one strut, dug in three lifts: a clay over a sand,
contacts on both faces of the wall. It has two cases on one mesh, `linear_elastic`
(elastic soils and contacts) and `mohr_coulomb_clay-sand` (Mohr-Coulomb soils, Coulomb
contacts). This is that model built the way a user builds it here -- the same geometry,
soils, wall, strut, loads and stages, typed in Kratos' own variables and units -- and
meshed by this tool rather than read from Kratos' `model.mdpa`. `benchmarks/cases.py`
(BM-CROW-LE, BM-CROW-MC) runs both and holds the wall to the curves Kratos' test holds
its own runs to.

What is left to the export is what the reference derives too
(`crow_validation/CROW_documentation.md`): each contact's stiffness from the soil it
runs against (G / t and 10 G / t, t = 1 m), and, for a Coulomb contact, its strength from
that soil's by the soil's own Rinter, tan(delta) / tan(phi). The K0 stage is elastic in
both, as the reference's `initial_materials.json` is.

The Mohr-Coulomb case is also the model of the `kratos-cli` tutorial
(`docs/cli_tutorials/CROW_case.md`) and of the ready-made model it starts from: change one,
and change the other with it.

    run tests/models/crow.py      in the GUI's command box: open it there
"""

from __future__ import annotations

import math

from core.model.schemas import (Anchor, AnchorSection, Beam, BeamSection,
                                DisplacementCondition, Domain, Interface,
                                InterfaceSection, Line, LineLoad, Material, MeshSettings,
                                NormalLoad, Project, SoilBody, SoilLayer, Stage,
                                WaterPressureCondition)

NAME = "CROW excavation wall"

WALL_X = 5.0
WALL_TOE_Y = -13.0
WATER_Y = -1.5
LIFTS = (-2.0, -5.0, -8.0)
SAND_TOP_Y = -12.0
STRUT_Y, STRUT_END_X = -1.5, 4.0

LINEAR_ELASTIC = "Linear elastic"
MOHR_COULOMB = "Mohr-Coulomb"

LAWS = {
    # soil model -> (soil law, contact law)
    LINEAR_ELASTIC: ("GeoLinearElasticPlaneStrain2DLaw",
                     "GeoIncrementalLinearElasticInterfaceLaw"),
    MOHR_COULOMB: ("GeoMohrCoulombLawPlaneStrain", "GeoInterfaceCoulombLawPlaneStrain"),
}

# Saturated below the phreatic level. With the water pressure fixed (CONSTANT_PW_FIELD)
# Kratos reads no relative permeability, and it derives the Biot coefficient, 1 - K / K_s,
# from the solid's bulk modulus the export gives (1e10 Pa): 0.9994 for the sand, 0.99995
# for the clay. The reference writes 1.0; the Soil materials window offers neither for a
# drained soil, so the GUI builds the same soil as this one.
RETENTION = {"RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
             "SATURATED_SATURATION": 1.0, "RESIDUAL_SATURATION": 1.0e-10}


def r_inter(delta: float, phi: float) -> float:
    """The strength reduction that turns a soil's friction angle into the wall's."""
    return math.tan(math.radians(delta)) / math.tan(math.radians(phi))


def _soil(model, id_, name, color, density, modulus, poisson, cohesion, phi, delta, k0):
    """A soil with the reference's numbers, SI. An elastic one has no strength: the
    reference's has none either."""
    strength = {} if model == LINEAR_ELASTIC else {
        "GEO_COHESION": cohesion, "GEO_FRICTION_ANGLE": phi, "GEO_DILATANCY_ANGLE": 0.0,
        "GEO_ENABLE_TENSION_CUT_OFF": False}
    return Material(id=id_, name=name, color=color, r_inter=r_inter(delta, phi),
                    constitutive_law=LAWS[model][0],
                    variables={
                        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
                        "YOUNG_MODULUS": modulus,
                        "POISSON_RATIO": poisson,
                        "DENSITY_SOLID": density,
                        "POROSITY": 0.0,
                        **strength,
                        "K0_NC": k0,
                        **RETENTION,
                    })


def project(model: str = MOHR_COULOMB) -> Project:
    """The model with `model`'s soils and contacts: `LINEAR_ELASTIC` or `MOHR_COULOMB`."""
    clay = _soil(model, "clay", "Clay", "#c4a86a", 1.83486e3, 9.0e5, 0.2, 3.0e3, 22.5,
                 11.25, 0.62)
    sand = _soil(model, "sand", "Sand", "#b08a6a", 2.03874e3, 7.4286e6, 0.3, 0.0, 32.5,
                 20.0, 0.46)
    sheet_pile = BeamSection(id="sheetpile", name="Sheet pile", variables={
        "YOUNG_MODULUS": 8.4449e9, "POISSON_RATIO": 0.0, "DENSITY": 298.36,
        "CROSS_AREA": 0.4924, "I33": 0.4924 ** 3 / 12, "AREA_EFFECTIVE_Y": 1.0e4})
    strut = AnchorSection(id="strut", name="Strut", spacing=1.0, variables={
        "YOUNG_MODULUS": 2.1e11, "CROSS_AREA": 4.7619e-5, "DENSITY": 0.0})
    # No material, no Rinter and no variables: each stretch of contact takes the soil it
    # runs against, its retention and (Coulomb) its tension cut-off included.
    contact = InterfaceSection(
        id="contact", name="Wall contact", constitutive_law=LAWS[model][1],
        virtual_thickness=1.0)
    water_loads = [NormalLoad(id=f"water_{index}", name=f"WaterLoad_Stage{index}",
                              fluid_pressure_type="Hydrostatic", reference_coordinate=WATER_Y,
                              points=[(0.0, level), (WALL_X, level), (WALL_X, WATER_Y)])
                   for index, level in enumerate(LIFTS, start=1)]
    solved = {"max_iterations": 150, "tolerated_error": 1e-3}
    return Project(
        name=NAME if model == MOHR_COULOMB else f"{NAME}, {model.lower()}",
        dimension=2,
        section_offset=5.0,
        domain=Domain(x0=0.0, x1=80.0, z0=0.0, z1=10.0, y_top=0.0, y_bottom=-60.0),
        materials=[clay, sand],
        layers=[SoilLayer(id="L_top", name="Soil_Top", mat="clay", top=0.0, bottom=LIFTS[-1]),
                SoilLayer(id="L_mid", name="Soil_Middle", mat="clay", top=LIFTS[-1],
                          bottom=SAND_TOP_Y),
                SoilLayer(id="L_bot", name="Soil_Bottom", mat="sand", top=SAND_TOP_Y,
                          bottom=-60.0)],
        # The pit is against the left edge, the model's symmetry plane. The wall cuts it off
        # from the ground it retains, and each line is the floor of a lift; the last floor
        # is a layer boundary.
        lines=[Line(id=f"floor_{index}", name=f"Floor of lift {index}",
                    points=[(0.0, level), (WALL_X, level)])
               for index, level in enumerate(LIFTS[:-1], start=1)],
        bodies=[
            *[SoilBody(id=f"lift{index}", name=f"lift {index}", layer="L_top",
                       point=(WALL_X / 2, (level + ceiling) / 2))
              for index, (level, ceiling) in enumerate(zip(LIFTS, (0.0, *LIFTS)), start=1)],
            SoilBody(id="retained", name="retained", layer="L_top", point=(40.0, LIFTS[-1] / 2)),
            SoilBody(id="pit", name="below the pit", layer="L_mid",
                     point=(WALL_X / 2, (LIFTS[-1] + SAND_TOP_Y) / 2)),
            SoilBody(id="retained", name="retained", layer="L_mid",
                     point=(40.0, (LIFTS[-1] + SAND_TOP_Y) / 2))],
        boundary_conditions=[
            DisplacementCondition(id="fixed_bottom", name="Fixed bottom", on="face",
                                  face="bottom", fixed=(True, True, True)),
            DisplacementCondition(id="roller_left", name="Roller left", on="face",
                                  face="left", fixed=(True, False, False)),
            DisplacementCondition(id="roller_right", name="Roller right", on="face",
                                  face="right", fixed=(True, False, False)),
            WaterPressureCondition(id="pore_pressure", name="Pore pressure", on="domain",
                                   fluid_pressure_type="Hydrostatic",
                                   reference_coordinate=WATER_Y)],
        beam_sections=[sheet_pile],
        beams=[Beam(id="sheetpile", name="SheetPileWall", section="sheetpile",
                    points=[(WALL_X, 0.0), (WALL_X, WALL_TOE_Y)])],
        anchor_sections=[strut],
        anchors=[Anchor(id="strut", name="Strut", section="strut",
                        head=(WALL_X, STRUT_Y), tail=(STRUT_END_X, STRUT_Y))],
        interface_sections=[contact],
        interfaces=[Interface(id="wall_contact", name="Interface", section="contact",
                              structure="sheetpile")],
        loads=[LineLoad(id="surcharge", name="Load", x0=WALL_X, x1=80.0, y=0.0,
                        components=(0.0, -20_000.0))],
        normal_loads=water_loads,
        # The reference's mesh: 0.5 m quadratic elements along the wall, 0.25 m between
        # its nodes, growing to 5 m over 30 m from the wall. The Mohr-Coulomb strut stage
        # is sensitive to the mesh: over 45 m or 55 m it does not converge in its 500
        # iterations, over 30 m it takes about 270.
        mesh=MeshSettings(element_size=5.0, order=2, body_sizes={"sheetpile": 0.5},
                          size_bands={"sheetpile": 30.0}),
        stages=[
            Stage(id="initial", name="Initial stage", calculation="K0 procedure",
                  deactivate=["sheetpile", "strut", "wall_contact", "surcharge",
                              *(load.id for load in water_loads)]),
            Stage(id="null_step", name="Null step", parent="initial",
                  calculation="Null step", max_iterations=150),
            Stage(id="install_wall", name="Wall installation", parent="null_step",
                  activate=["sheetpile", "wall_contact", "surcharge"], **solved),
            Stage(id="dig_1", name="First excavation", parent="install_wall",
                  activate=["water_1"], deactivate=["soil_L_top__lift1"],
                  max_iterations=500, tolerated_error=1e-3),
            Stage(id="install_strut", name="Strut installation", parent="dig_1",
                  activate=["strut"], **solved),
            Stage(id="dig_2", name="Second excavation", parent="install_strut",
                  activate=["water_2"], deactivate=["soil_L_top__lift2", "water_1"],
                  max_iterations=300, tolerated_error=1e-3),
            Stage(id="dig_3", name="Third excavation", parent="dig_2",
                  activate=["water_3"], deactivate=["soil_L_top__lift3", "water_2"],
                  max_iterations=300, tolerated_error=1e-3),
        ],
    )
