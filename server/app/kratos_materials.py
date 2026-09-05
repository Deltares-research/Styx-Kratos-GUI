"""Write the Kratos GeoMechanics MaterialParameters.json beside an exported .mdpa.

Continuum elements keep property id 0, exactly as GiD writes them. Kratos' material
import process assigns their material properties by sub-model part name, and the names
here must be the ones the mdpa writes.

Load conditions never appear here. A line/point/surface load is not a constitutive
material, and no real Kratos GeoMechanics deck defines LINE_LOAD, POINT_LOAD or
SURFACE_LOAD in a MaterialParameters.json -- its magnitude is applied by a
ProjectParameters.json process against the load's sub-model part instead. `app.kratos`
records it as `SubModelPartData` in the .mdpa in the meantime.

Two things in this module are conventions rather than facts about our model, and both
are deliberately kept in one place so they can be corrected in a single edit:

*   `CONSTITUTIVE_LAWS` maps our four material models onto Kratos law names. Only the
    linear elastic law is mapped; the three non-linear models have no drop-in
    equivalent in a stock GeoMechanicsApplication build (Hardening Soil and Soft Soil
    need a UDSM, Mohr-Coulomb's law name has moved between Kratos versions). They fall
    back to linear elastic and the substitution is *named in the export's warnings*
    rather than made silently.
*   `_variables` derives Kratos' variable set from our material sheet, which is written
    in engineering units (kN/m3, kN/m2, m/day). The conversions and the defaults for
    quantities we do not model are listed in `ASSUMPTIONS`.
"""

from __future__ import annotations

import json
import math

from app.schemas import (AnchorSection, BeamSection, InterfaceSection, Material,
                         PanelSection, Project)

class MaterialError(RuntimeError):
    """A property set cannot be written. Surfaced to the command log, never guessed at."""


LINEAR_ELASTIC = ("GeoLinearElasticPlaneStrain2DLaw", "GeoLinearElastic3DLaw")

ANCHOR_LAW = "TrussConstitutiveLaw"
"""The law paired with `LinearTrussElement2D2N`. Carries the same confidence note as
`BEAM_LAW` below: the element class is read off the reference decks, the law and the
prestress variable name are not."""

PANEL_LAW = "LinearElasticPlaneStress2DLaw"
"""The law paired with `ShellThinElement3D3N`, and the wall's counterpart to `BEAM_LAW`.

Same confidence note, one degree weaker: the 2D beam *elements* at least come off a
reference deck, while every 3D structural name in this app -- element and law alike --
follows Kratos' documented convention, because not one deck in examples/ is 3D."""

INTERFACE_LAW = "GeoIncrementalLinearElasticInterfaceLaw"
"""The law paired with the `Geo_UPwLineInterface*` elements.

Same confidence note as `BEAM_LAW`: examples/crow_case.mdpa pins the *element* class and
its node layout, but ships no MaterialParameters.json, so the law name and the two
stiffness variables in `_interface_variables` follow GeoMechanicsApplication's
documented convention. Check them against the first real run with an interface."""

BEAM_LAW = "TimoshenkoBeamElasticConstitutiveLaw"
"""The law paired with `LinearTimoshenkoCurvedBeamElement2D*N`.

Confidence note: the element classes themselves are read off the reference decks in
examples/, but neither ships a MaterialParameters.json, so this name and the variable
set in `_beam_variables` follow Kratos StructuralMechanicsApplication's documented
convention rather than a fixture in this repo. Check them against the first real
sheet-pile run, the same way the load conventions were checked against the decks.
"""

CONSTITUTIVE_LAWS: dict[str, tuple[str, str]] = {
    "Linear Elastic": LINEAR_ELASTIC,
}

GRAVITY = 9.81                  # m/s2, for unit weight -> density
SECONDS_PER_DAY = 86_400.0
WATER_DENSITY = 1000.0          # kg/m3
DEFAULT_POROSITY = 0.3
BULK_MODULUS_SOLID = 1.0e12     # kN/m2; grains treated as incompressible
BULK_MODULUS_FLUID = 2.0e6      # kN/m2
DYNAMIC_VISCOSITY = 1.0e-3      # Pa s, water at 20 C

ASSUMPTIONS = (
    "Material variables are derived: densities from unit weights at g=9.81 m/s2, "
    f"porosity fixed at {DEFAULT_POROSITY}, permeability converted from m/day to m/s. "
    "Check them against the Kratos version you run."
)


def material_parameters(
    project: Project,
    part_materials: list[tuple[str, str]],
    dim: int,
    beam_properties: list[tuple[str, BeamSection, int]] | None = None,
    anchor_properties: list[tuple[str, AnchorSection, float, int]] | None = None,
    panel_properties: list[tuple[str, PanelSection]] | None = None,
    interface_properties: list[tuple[str, InterfaceSection]] | None = None,
) -> tuple[str, list[str]]:
    """Render MaterialParameters.json for the exported parts.

    `part_materials` is (sub-model part name, material id) and `beam_properties` is
    (sub-model part name, section), both in the order the parts appear in the deck.
    Returns the JSON text and any warnings for the caller's log.

    One entry per sub-model part, not per material or section: Kratos binds a
    `Properties` object to a model part by name, so two sheet piles sharing a profile
    get two entries carrying the same numbers under different ids. Sharing happens in
    the project -- one `BeamSection` edited once -- which is where it stops the values
    drifting apart.
    """
    warnings: list[str] = []
    properties = []
    for index, (part_name, material_id) in enumerate(part_materials, start=1):
        material = project.material(material_id)
        law = _law(material, dim, warnings)
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": index,
            "Material": {
                "constitutive_law": {"name": law},
                "Variables": _variables(material, dim),
                "Tables": {},
            },
        })
    for offset, (part_name, section, beam_dim) in enumerate(beam_properties or []):
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": len(part_materials) + offset + 1,
            "Material": {
                "constitutive_law": {"name": BEAM_LAW},
                "Variables": _beam_variables(section, beam_dim),
                "Tables": {},
            },
        })
    for offset, (part_name, section) in enumerate(panel_properties or []):
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": (len(part_materials) + len(beam_properties or [])
                              + offset + 1),
            "Material": {
                "constitutive_law": {"name": PANEL_LAW},
                "Variables": _panel_variables(section),
                "Tables": {},
            },
        })
    for offset, (part_name, section, prestress, anchor_dim) in enumerate(
            anchor_properties or []):
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": (len(part_materials) + len(beam_properties or [])
                              + len(panel_properties or []) + offset + 1),
            "Material": {
                "constitutive_law": {"name": ANCHOR_LAW},
                "Variables": _anchor_variables(section, prestress, anchor_dim),
                "Tables": {},
            },
        })
    for offset, (part_name, section) in enumerate(interface_properties or []):
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": (len(part_materials) + len(beam_properties or [])
                              + len(panel_properties or [])
                              + len(anchor_properties or []) + offset + 1),
            "Material": {
                "constitutive_law": {"name": INTERFACE_LAW},
                "Variables": _interface_variables(section, project, warnings),
                "Tables": {},
            },
        })
    if properties:
        warnings.append(ASSUMPTIONS)
    return json.dumps({"properties": properties}, indent=4), warnings


def _interface_variables(section: InterfaceSection, project: Project,
                         warnings: list[str]) -> dict:
    """The contact's property set: two stiffnesses per unit area and a reduced strength.

    A zero-thickness element has no modulus, so the stiffnesses are kN/m3. Given
    explicitly they are used as they stand; left out they are derived from the soil the
    interface slides against, E over a virtual thickness, which is the device every
    geotechnical preprocessor uses to turn a continuum stiffness into a contact one.
    Shear follows from the same E through the soil's Poisson ratio.

    Strength is the adjacent soil's, reduced by `r_inter` -- the definition of the
    factor, and the reason an interface section is worth pairing with a material at all.
    An interface with neither a material nor explicit stiffnesses cannot be written, and
    is refused rather than defaulted to a number nobody chose.
    """
    soil = None
    if section.material is not None:
        soil = next((m for m in project.materials if m.id == section.material), None)
        if soil is None:
            warnings.append(
                f"interface section {section.name!r} references material "
                f"{section.material!r}, which is not in the project; its stiffnesses "
                "have to be given explicitly."
            )
    normal, shear = section.normal_stiffness, section.shear_stiffness
    if (normal is None or shear is None) and soil is None:
        raise MaterialError(
            f"interface section {section.name!r} has neither a soil material to reduce "
            "nor explicit normal and shear stiffnesses; one of the two is needed before "
            "the deck can be written."
        )
    if normal is None:
        normal = soil.E / section.virtual_thickness
    if shear is None:
        shear = soil.E / (2.0 * (1.0 + soil.nu) * section.virtual_thickness)
    variables = {
        "INTERFACE_NORMAL_STIFFNESS": normal,
        "INTERFACE_SHEAR_STIFFNESS": shear,
    }
    if soil is not None:
        if soil.c is not None:
            variables["GEO_COHESION"] = soil.c * section.r_inter
        if soil.phi is not None:
            variables["GEO_FRICTION_ANGLE"] = math.degrees(
                math.atan(math.tan(math.radians(soil.phi)) * section.r_inter))
        variables["GEO_DILATANCY_ANGLE"] = 0.0
    return variables


def _beam_variables(section: BeamSection, dim: int = 2) -> dict:
    """The Timoshenko beam's property set, in Kratos' names.

    Spacing is applied here rather than stored pre-divided, so the section keeps the
    number an engineer reads off a profile table. A row of piles at 2 m centres carries
    half the stiffness and half the weight of a continuous wall per metre run.

    That smear is a plane-strain device and stops at 3D: a member in space is the
    discrete pile the user drew, standing where they put it. It does gain the second
    bending axis and the torsion constant a 3D beam needs, which the 2D section has no
    room for -- `inertia_minor` defaults to the strong-axis value and the torsion
    constant to their sum, the thin-walled open-section estimate, both overridable on
    the section.
    """
    per_metre = 1.0 / section.spacing if dim == 2 else 1.0
    variables = {
        "YOUNG_MODULUS": section.E,
        "POISSON_RATIO": section.nu,
        "DENSITY": section.density * per_metre,
        "CROSS_AREA": section.area * per_metre,
        "I33": section.inertia * per_metre,
    }
    if dim == 3:
        minor = section.inertia if section.inertia_minor is None else section.inertia_minor
        variables["I22"] = minor
        variables["TORSIONAL_INERTIA"] = (
            section.inertia + minor if section.torsional_inertia is None
            else section.torsional_inertia
        )
    return variables


def _panel_variables(section: PanelSection) -> dict:
    """The wall shell's property set. A thickness, where a 2D pile has area and inertia.

    Nothing is smeared: a panel is the wall itself, not a metre run of one.
    """
    return {
        "YOUNG_MODULUS": section.E,
        "POISSON_RATIO": section.nu,
        "DENSITY": section.density,
        "THICKNESS": section.thickness,
    }


def _anchor_variables(section: AnchorSection, prestress: float, dim: int = 2) -> dict:
    """The tendon's property set, smeared over its out-of-plane spacing in 2D.

    Plane strain models a metre run of wall, so an anchor every 2.5 m contributes
    two-fifths of its steel and two-fifths of its lock-off force to that metre. The
    section keeps the per-anchor numbers an engineer reads off a supplier sheet.

    In 3D there is nothing to smear: the anchor is a discrete member at the position it
    was drawn, so it carries its own full area and its own full lock-off force.
    """
    per_metre = 1.0 / section.spacing if dim == 2 else 1.0
    variables = {
        "YOUNG_MODULUS": section.E,
        "CROSS_AREA": section.area * per_metre,
        "DENSITY": section.density * per_metre,
        "TRUSS_PRESTRESS_PK2": prestress * per_metre,
    }
    if section.tension_limit is not None:
        variables["MAX_TENSION_STRESS"] = section.tension_limit / section.area
    if section.compression_limit is not None:
        variables["MAX_COMPRESSION_STRESS"] = section.compression_limit / section.area
    return variables


def _law(material: Material, dim: int, warnings: list[str]) -> str:
    mapped = CONSTITUTIVE_LAWS.get(material.model)
    if mapped is None:
        mapped = LINEAR_ELASTIC
        warning = (f"{material.model!r} has no mapped Kratos constitutive law; "
                   f"material {material.name!r} is written as linear elastic")
        if warning not in warnings:
            warnings.append(warning)
    return mapped[0] if dim == 2 else mapped[1]


def _variables(material: Material, dim: int) -> dict:
    permeability = material.k / SECONDS_PER_DAY          # m/day -> m/s
    variables = {
        "IGNORE_UNDRAINED": material.type == "Non-porous",
        "YOUNG_MODULUS": material.E,
        "POISSON_RATIO": material.nu,
        "DENSITY_SOLID": material.g_unsat * 1000.0 / GRAVITY,
        "DENSITY_WATER": WATER_DENSITY,
        "POROSITY": DEFAULT_POROSITY,
        "BULK_MODULUS_SOLID": BULK_MODULUS_SOLID,
        "BULK_MODULUS_FLUID": BULK_MODULUS_FLUID,
        "DYNAMIC_VISCOSITY": DYNAMIC_VISCOSITY,
        "PERMEABILITY_XX": permeability,
        "PERMEABILITY_YY": permeability,
        "PERMEABILITY_XY": 0.0,
    }
    if dim == 3:
        variables.update({"PERMEABILITY_ZZ": permeability,
                          "PERMEABILITY_YZ": 0.0, "PERMEABILITY_ZX": 0.0})
    if material.c is not None:
        variables["GEO_COHESION"] = material.c
    if material.phi is not None:
        variables["GEO_FRICTION_ANGLE"] = material.phi
    return variables
