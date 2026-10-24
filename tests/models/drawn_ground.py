"""A sheet pile through a borehole layer and through soil drawn on top of it.

The smallest model of a dike section built the way a user draws one: the ground below
y = -2 m comes from a borehole, the 2 m above it is two drawn polygons with a material of
their own, one each side of the pile, and the pile runs through both. The right-hand fill
is dug away in the last stage, and the water in the trench presses on the floor and on
the wall face.

It is the arrangement that once lost the contact along the drawn soil: the exporter
grouped contact elements by the `soil_` key prefix, which only borehole layers carry, so
everything above the layer was split from the wall and tied back to nothing.

The drawn parts carry a recipe and no .brep; `scripting.with_solids` builds them, the way
a model script does:

    run tests/models/drawn_ground.py
"""

from __future__ import annotations

from core import scripting
from core.model.schemas import (Beam, BeamSection, Borehole, CustomPart, Domain, Interface,
                                InterfaceSection, Material, MeshSettings, NormalLoad, Stage,
                                Project, SoilLayer, standard_conditions)

NAME = "Drawn ground"

DOMAIN_LEFT_X, DOMAIN_RIGHT_X = 0.0, 30.0
DOMAIN_BOTTOM_Y, DOMAIN_TOP_Y = -20.0, 0.0
Z0, Z1 = 0.0, 10.0
SECTION_Z = 5.0

LAYER_TOP_Y = -2.0
"""The top of the borehole layer, and the bottom of the drawn fill."""
WALL_X = 10.0
WALL_TOE_Y = -8.0

ELEMENT_SIZE = 2.0


def _soil(id_, name, color, modulus, weight, cohesion, phi):
    """A dry linear-elastic soil in Kratos' own variables, SI."""
    return Material(id=id_, name=name, color=color,
                    constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables={
                        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
                        "YOUNG_MODULUS": modulus,
                        "POISSON_RATIO": 0.3,
                        "DENSITY_SOLID": weight / 9.81,
                        "DENSITY_WATER": 10_000.0 / 9.81,
                        "POROSITY": 0.0,
                        "BULK_MODULUS_SOLID": 1.0e10,
                        "BULK_MODULUS_FLUID": 2.2e9,
                        "DYNAMIC_VISCOSITY": 1.0e-3,
                        "PERMEABILITY_XX": 1.0e-5,
                        "PERMEABILITY_YY": 1.0e-5,
                        "PERMEABILITY_XY": 0.0,
                        "GEO_COHESION": cohesion,
                        "GEO_FRICTION_ANGLE": phi,
                    })


def _drawn(key: str, label: str, material: str, corners: list[tuple[float, float]]
           ) -> CustomPart:
    """A polygon drawn in the section, extruded over the model's depth as the GUI does."""
    return CustomPart(
        key=key, label=label, source="gui", mat=material,
        recipe={"kind": "polygon_extrude", "material": material,
                "vertices": [[x, y, Z0] for x, y in corners],
                "extrusion": [0.0, 0.0, Z1 - Z0]})


def drawn_ground_project(staged: bool = True) -> Project:
    """The model, its drawn parts not built yet: `with_solids` builds them."""
    borehole = "bh1"
    ground = _soil("m_ground", "Ground", "#b08a6a", 2.0e7, 18_000.0, 1_000.0, 30.0)
    fill = _soil("m_fill", "Fill", "#c4a86a", 3.0e7, 19_000.0, 1_500.0, 40.0)
    pile = BeamSection(id="sheetpile", name="Sheet pile", variables={
        "YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.2, "DENSITY": 7_850.0,
        "CROSS_AREA": 0.015, "I33": 3.0e-4, "AREA_EFFECTIVE_Y": 0.0075})
    # No material: each stretch of the contact takes the soil it runs against.
    contact = InterfaceSection(id="contact", name="Wall contact", r_inter=0.7,
                               virtual_thickness=0.1)
    project = Project(
        name=NAME,
        mesh=MeshSettings(element_size=ELEMENT_SIZE, order=2),
        layered_soil=True,
        dimension=2,
        section_offset=SECTION_Z,
        domain=Domain(x0=DOMAIN_LEFT_X, x1=DOMAIN_RIGHT_X, z0=Z0, z1=Z1,
                      y_top=DOMAIN_TOP_Y, y_bottom=DOMAIN_BOTTOM_Y),
        boreholes=[Borehole(id=borehole, name="BH1", x=DOMAIN_LEFT_X, y=Z0,
                            head=LAYER_TOP_Y, water=DOMAIN_BOTTOM_Y)],
        materials=[ground, fill],
        layers=[SoilLayer(id="ground", name="Ground", mat=ground.id,
                          tops={borehole: LAYER_TOP_Y}, bots={borehole: DOMAIN_BOTTOM_Y})],
        custom_parts=[
            _drawn("drawn_0", "Fill left", fill.id,
                   [(DOMAIN_LEFT_X, DOMAIN_TOP_Y), (DOMAIN_LEFT_X, LAYER_TOP_Y),
                    (WALL_X, LAYER_TOP_Y), (WALL_X, DOMAIN_TOP_Y)]),
            _drawn("drawn_1", "Fill right", fill.id,
                   [(WALL_X, DOMAIN_TOP_Y), (WALL_X, LAYER_TOP_Y),
                    (DOMAIN_RIGHT_X, LAYER_TOP_Y), (DOMAIN_RIGHT_X, DOMAIN_TOP_Y)]),
        ],
        boundary_conditions=standard_conditions(),
        beam_sections=[pile],
        # Drawn from the toe up, so its left face is the -x one.
        beams=[Beam(id="sheetpile", name="Sheet pile", section=pile.id,
                    points=[(WALL_X, WALL_TOE_Y), (WALL_X, DOMAIN_TOP_Y)])],
        interface_sections=[contact],
        interfaces=[Interface(id="wall_contact", name="Wall contact", section=contact.id,
                              structure="sheetpile", side="both")],
        # The trench water, walked with the soil that stays on its right, where a
        # normal load presses: down the wall face, then along the floor.
        normal_loads=[NormalLoad(
            id="trench_water", name="Trench water", fluid_pressure_type="Hydrostatic",
            reference_coordinate=DOMAIN_TOP_Y,
            points=[(WALL_X, DOMAIN_TOP_Y), (WALL_X, LAYER_TOP_Y),
                    (DOMAIN_RIGHT_X, LAYER_TOP_Y)])],
    )
    if not staged:
        return project
    stages = [
        Stage(id="initial", name="Initial", calculation="K0 procedure",
              deactivate=["sheetpile", "wall_contact", "trench_water"]),
        Stage(id="install", name="Install wall", parent="initial",
              activate=["sheetpile", "wall_contact"]),
        Stage(id="dig", name="Dig trench", parent="install",
              activate=["trench_water"], deactivate=["drawn_1"]),
    ]
    return Project.model_validate(
        project.model_dump() | {"stages": [stage.model_dump() for stage in stages]})


HEAD_LOAD = 10_000.0
"""N/m, the horizontal push at the pile head in `pushed_pile_project`."""


def pushed_pile_project(interface: bool = True, variables: dict | None = None,
                        law: str | None = None, load: tuple[float, float] = (HEAD_LOAD, 0.0),
                        max_iterations: int = 15) -> Project:
    """The pile pushed at its head, the ground left as it is: Kratos' own
    `tests/Interface/interface_on_beam` asked of this model.

    The ground settles in a K0 stage without the pile; the second stage installs the pile
    -- and its interface, unless `interface` is False -- with the load on its head, and
    starts its displacements from nought, so they are the load's alone. `variables`
    are typed on the interface section (its stiffnesses, say), `law` replaces its law.
    """
    data = drawn_ground_project(staged=False).model_dump()
    data["normal_loads"] = []
    data["loads"] = [{"id": "head_load", "name": "Head load", "kind": "point",
                      "x": WALL_X, "y": DOMAIN_TOP_Y, "components": list(load)}]
    contact = data["interface_sections"][0]
    contact["variables"] = dict(variables or {})
    if law is not None:
        contact["constitutive_law"] = law
    if not interface:
        data["interfaces"] = []
    built = ["sheetpile", "head_load"] + (["wall_contact"] if interface else [])
    data["stages"] = [
        Stage(id="initial", name="Initial", calculation="K0 procedure",
              deactivate=built).model_dump(),
        Stage(id="push", name="Push", parent="initial", activate=built,
              reset_displacements=True, max_iterations=max_iterations).model_dump(),
    ]
    return scripting.with_solids(Project.model_validate(data))


def project() -> Project:
    """The model with its drawn parts built, for `run tests/models/drawn_ground.py`."""
    return scripting.with_solids(drawn_ground_project())


PILE_HEAD_Y = 1.0
"""The top of the pile in `standing_pile_project`, 1 m above the fill."""


def standing_pile_project() -> Project:
    """The model with the pile standing 1 m out of the ground, as a dike's sheet pile
    stands above its crest. The domain reaches the pile head, the soil does not."""
    data = drawn_ground_project().model_dump()
    data["domain"]["y_top"] = PILE_HEAD_Y
    data["beams"][0]["points"] = [(WALL_X, WALL_TOE_Y), (WALL_X, PILE_HEAD_Y)]
    return scripting.with_solids(Project.model_validate(data))
