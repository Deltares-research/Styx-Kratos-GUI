"""A staged sheet-pile excavation in plane strain: the model most tests build.

It carries every feature a staged excavation uses, each once, so a test about any of them
has it to hand: three soil layers, a pit dug in three lifts, a sheet-pile wall, a strut
from the wall to a pinned support, an interface on both faces of the wall, a surcharge
behind it, a water table, one hydrostatic water load per lift, a graded mesh carried by
the project, and the staged construction sequence `phases.staged_excavation_phases`
derives from all of that. `mohr_coulomb_project` is the same model with Mohr-Coulomb
soils and Coulomb contacts.

The numbers are round rather than taken from anywhere: a soft clay over a dense sand,
a steel wall, a steel strut. What the tests pin is the pipeline, not a validated answer.

It is also a script the GUI can open, through the same path a user's own model takes:

    run tests/models/excavation.py
"""

from __future__ import annotations

from core.model import phases
from core.model.schemas import (Anchor, AnchorRows, AnchorSection, Beam, BeamSection, Borehole,
                         BoxRefinement, Domain, Excavation, Interface, InterfaceSection,
                         LineLoad, Material, MeshSettings, NormalLoad, Piles, Project,
                         SoilLayer, Struts, Wall, WaterLevel, Wells)

NAME = "Staged excavation"

WALL_X = 6.0
DOMAIN_LEFT_X, DOMAIN_RIGHT_X = 0.0, 60.0
DOMAIN_BOTTOM_Y, DOMAIN_TOP_Y = -40.0, 0.0
LIFTS = (-2.0, -4.5, -7.0)
"""The three excavation levels. The deepest is also the bottom of the top layer, so the
last lift ends on a layer boundary."""
BOTTOM_LAYER_TOP_Y = -10.0
WALL_TOE_Y = -12.0
STRUT_Y, STRUT_END_X = -1.0, 5.0

ELEMENT_SIZE_GLOBAL = 5.0
ELEMENT_SIZE_WALL = 0.5
"""Divides every stretch of the wall between the levels that cut it (1, 1, 2.5, 2.5, 3 and
2 m), so the wall comes out uniform."""
ELEMENT_SIZE_EXCAVATION = 0.8
REFINED_REACH = WALL_X + 3.0
REFINED_DEPTH = WALL_TOE_Y - 3.0
REFINED_BAND = 30.0
"""How far past the refined box the size takes to grow back to `ELEMENT_SIZE_GLOBAL`."""
ELEMENT_ORDER = 2

WATER_Y = -1.0
SURCHARGE = -10_000.0
"""N/m, downward, on the ground behind the wall."""

# The out-of-plane extent. A plane-strain model is a slice, taken through the middle.
Z0, Z1 = 0.0, 10.0
SECTION_Z = 5.0


def _soil(id_, name, color, modulus, poisson, weight, cohesion, phi, permeability, k0):
    """A linear-elastic soil in Kratos' own variables, SI."""
    return Material(id=id_, name=name, color=color,
                    constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables={
                        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
                        "YOUNG_MODULUS": modulus,
                        "POISSON_RATIO": poisson,
                        "DENSITY_SOLID": weight / 9.81,
                        "DENSITY_WATER": 10_000.0 / 9.81,
                        "POROSITY": 0.0,
                        "BULK_MODULUS_SOLID": 1.0e10,
                        "BULK_MODULUS_FLUID": 2.2e9,
                        "DYNAMIC_VISCOSITY": 1.0e-3,
                        "PERMEABILITY_XX": permeability,
                        "PERMEABILITY_YY": permeability,
                        "PERMEABILITY_XY": 0.0,
                        "GEO_COHESION": cohesion,
                        "GEO_FRICTION_ANGLE": phi,
                        "K0_NC": k0,
                    })


def excavation_project(staged: bool = True) -> Project:
    """The model. `staged=False` is the same geometry with no construction sequence, for
    a test about the mesh or the deck that should not depend on the phases."""
    borehole = "bh1"
    upper = _soil("m_upper", "Soft clay", "#c4a86a", 2.0e6, 0.3, 17_000.0, 2_000.0,
                  25.0, 1.0e-8, 0.58)
    lower = _soil("m_lower", "Dense sand", "#b08a6a", 3.0e7, 0.3, 19_000.0, 0.0,
                  32.0, 1.0e-5, 0.47)
    layers = [
        SoilLayer(id="L_top", name="Soil_Top", mat=upper.id,
                  tops={borehole: DOMAIN_TOP_Y}, bots={borehole: LIFTS[-1]}),
        SoilLayer(id="L_mid", name="Soil_Middle", mat=upper.id,
                  tops={borehole: LIFTS[-1]}, bots={borehole: BOTTOM_LAYER_TOP_Y}),
        SoilLayer(id="L_bot", name="Soil_Bottom", mat=lower.id,
                  tops={borehole: BOTTOM_LAYER_TOP_Y}, bots={borehole: DOMAIN_BOTTOM_Y}),
    ]
    # A steel sheet pile, per metre of wall.
    sheet_pile = BeamSection(id="sheetpile", name="Sheet pile", variables={
        "YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.0, "DENSITY": 7_850.0,
        "CROSS_AREA": 0.015, "I33": 3.0e-4, "AREA_EFFECTIVE_Y": 0.0075})
    strand = AnchorSection(id="strand", name="Strut", spacing=2.0, variables={
        "YOUNG_MODULUS": 2.1e11, "CROSS_AREA": 2.0e-3, "DENSITY": 0.0})
    # No material: each stretch of the contact takes the soil it runs against.
    contact = InterfaceSection(id="contact", name="Wall contact",
                               r_inter=0.67, virtual_thickness=0.5)

    project = Project(
        name=NAME,
        mesh=MeshSettings(
            element_size=ELEMENT_SIZE_GLOBAL, order=ELEMENT_ORDER,
            body_sizes={"sheetpile": ELEMENT_SIZE_WALL},
            refinements=[BoxRefinement(
                kind="box", size=ELEMENT_SIZE_EXCAVATION, thickness=REFINED_BAND,
                x_min=DOMAIN_LEFT_X - 1.0, x_max=REFINED_REACH,
                y_min=REFINED_DEPTH, y_max=DOMAIN_TOP_Y + 1.0,
                z_min=Z0 - 1.0, z_max=Z1 + 1.0)]),
        layered_soil=True,
        dimension=2,
        section_offset=SECTION_Z,
        domain=Domain(x0=DOMAIN_LEFT_X, x1=DOMAIN_RIGHT_X, z0=Z0, z1=Z1,
                      y_top=DOMAIN_TOP_Y, y_bottom=DOMAIN_BOTTOM_Y),
        boreholes=[Borehole(id=borehole, name="BH1", x=DOMAIN_LEFT_X, y=Z0,
                            head=DOMAIN_TOP_Y, water=WATER_Y)],
        materials=[upper, lower],
        layers=layers,
        # Against the left edge, the model's symmetry plane, dug in three lifts.
        excavation=Excavation(x0=DOMAIN_LEFT_X, x1=WALL_X, z0=Z0, z1=Z1,
                              levels=list(LIFTS)),
        # Unused by the layered build path; emptied so none of the seeded 3D pit
        # furniture can reach the deck.
        wall=Wall(thickness=0.5, top_y=DOMAIN_TOP_Y, toe_y=WALL_TOE_Y),
        struts=Struts(xs=[], y=STRUT_Y, radius=0.1),
        anchor_rows=AnchorRows(xs=[], head_y=STRUT_Y, length=1.0,
                               inclination_deg=45.0, radius=0.1),
        piles=Piles(xs=[], zs=[], radius=0.1, length=1.0, top_y=DOMAIN_TOP_Y),
        wells=Wells(positions=[], radius=0.1, length=1.0, top_y=DOMAIN_TOP_Y),
        water=WaterLevel(y=WATER_Y),
        beam_sections=[sheet_pile],
        beams=[Beam(id="sheetpile", name="SheetPileWall", section=sheet_pile.id,
                    points=[(WALL_X, DOMAIN_TOP_Y), (WALL_X, WALL_TOE_Y)])],
        anchor_sections=[strand],
        # Node to node: one end on the wall, the other in no element, which becomes a
        # pinned support part of its own.
        anchors=[Anchor(id="strut", name="Strut", section=strand.id,
                        head=(WALL_X, STRUT_Y), tail=(STRUT_END_X, STRUT_Y))],
        interface_sections=[contact],
        interfaces=[Interface(id="wall_contact", name="Interface", section=contact.id,
                              structure="sheetpile", side="both")],
        loads=[LineLoad(id="surcharge", name="Load", x0=WALL_X, x1=DOMAIN_RIGHT_X,
                        y=DOMAIN_TOP_Y, components=(0.0, SURCHARGE))],
        # One water load per lift: the exposed wall face from the water table down to
        # that level, then that level's floor back to the symmetry plane.
        normal_loads=[
            NormalLoad(id=f"water_{index}", name=f"WaterLoad_Stage{index}",
                       fluid_pressure_type="Hydrostatic",
                       points=[(WALL_X, WATER_Y), (WALL_X, level), (DOMAIN_LEFT_X, level)])
            for index, level in enumerate(LIFTS, start=1)
        ],
    )
    if not staged:
        return project
    return Project.model_validate(
        project.model_dump()
        | {"phases": [phase.model_dump() for phase in phases.staged_excavation_phases(project)]})


MOHR_COULOMB = "GeoMohrCoulombLawPlaneStrain"
COULOMB_CONTACT = "GeoInterfaceCoulombLawPlaneStrain"

RETENTION = {"BIOT_COEFFICIENT": 1.0, "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
             "SATURATED_SATURATION": 1.0, "RESIDUAL_SATURATION": 1.0e-10,
             "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-4}

STRENGTHS = {
    # material -> (GEO_COHESION in Pa, GEO_FRICTION_ANGLE, Rinter)
    "m_upper": (2_000.0, 25.0, 0.67),
    "m_lower": (0.0, 32.0, 0.67),
}

MOHR_COULOMB_SOLVER = {"dig_3": (1e-3, 300)}
"""phase id -> (residual relative tolerance, max iterations), typed per phase."""


def mohr_coulomb_project(staged: bool = True) -> Project:
    """The same model with Mohr-Coulomb soils and Coulomb contacts, every law and variable
    typed as a user would type it in the material editor."""
    data = excavation_project(staged).model_dump(mode="json")
    data["name"] = f"{NAME}, Mohr-Coulomb"
    for material in data["materials"]:
        cohesion, phi, r_inter = STRENGTHS[material["id"]]
        material["constitutive_law"] = MOHR_COULOMB
        material["variables"].update(GEO_COHESION=cohesion, GEO_FRICTION_ANGLE=phi,
                                     GEO_ENABLE_TENSION_CUT_OFF=False,
                                     GEO_DILATANCY_ANGLE=0.0, **RETENTION)
        material["r_inter"] = r_inter
    # Stiffness and strength from each soil the contact runs against, the strength by
    # that soil's own Rinter.
    contact = data["interface_sections"][0]
    contact.update(constitutive_law=COULOMB_CONTACT, r_inter=None,
                   variables={"GEO_ENABLE_TENSION_CUT_OFF": False, **RETENTION})
    for phase in data["phases"]:
        if phase["id"] in MOHR_COULOMB_SOLVER:
            phase["tolerated_error"], phase["max_iterations"] = MOHR_COULOMB_SOLVER[phase["id"]]
    return Project.model_validate(data)
