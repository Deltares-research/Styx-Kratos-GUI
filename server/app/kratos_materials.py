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

KILO = 1000.0
"""kN -> N, and with it kN/m2 -> Pa and kN/m3 -> N/m3.

The project is in kN (`app/schemas.py`, first paragraph: "Units throughout are m / kN /
day"), because kN/m2 and kN/m3 are what a geotechnical engineer types. **The deck is
SI.** That is not a choice this module makes -- it follows from two numbers Kratos reads
directly: `DENSITY_SOLID` in kg/m3 and gravity in m/s2. Their product is N/m3, so every
stress the solver computes is in Pa, and every stiffness, strength, load and specific
weight written beside them has to be too.

So everything with a force in it is multiplied by this on the way out of the project, in
this module and in `app.kratos_processes`, and nothing else is: a length, an area, an
angle and a density cross unchanged.

This was wrong until the deck was measured against
`MaterialParameters_for_generated_mesh.json`. `DENSITY_SOLID` was converted and nothing
else was, so one materials file carried two unit systems at once -- soil 1000x too soft,
water pressures 1000x too small, a 20 kN/m surcharge written as 20 N/m -- and every deck
this application had ever produced was wrong in the same way. See
`tests/test_kratos_units.py`, which checks the numbers against the reference rather than
against the code.
"""

SECONDS_PER_DAY = 86_400.0
DEFAULT_POROSITY = 0.3
BULK_MODULUS_SOLID = 1.0e10     # Pa, already SI: the reference deck's own value
BULK_MODULUS_FLUID = 2.2e9      # Pa, already SI: water at 20 C, the reference's own
DYNAMIC_VISCOSITY = 1.0e-3      # Pa s, water at 20 C

NORMAL_TO_SHEAR_STIFFNESS = 10.0
"""How much stiffer a contact is across the joint than along it.

A fixed ratio, not a second formula. `MaterialParameters_for_generated_mesh.json` carries
two interface property sets whose normal stiffness is exactly ten times their own shear,
at two different Poisson ratios (0.2 and 0.3) -- so nothing about the soil's
compressibility is in it. What it expresses is what an interface is for: effectively
rigid across the joint, so the two sides do not interpenetrate, while free to slip along
it at the strength `r_inter` sets."""

ASSUMPTIONS = (
    "Material variables are derived: densities from unit weights at g=9.81 m/s2, "
    f"porosity {DEFAULT_POROSITY} where a material does not give one, "
    "permeability converted from m/day to m/s, "
    "and everything carrying a force converted from the project's kN to the deck's N. "
    "Check them against the Kratos version you run."
)
"""What the deck decided rather than read, said once per export.

Porosity is worded as a fallback rather than as a fixed value on purpose: it stopped
being fixed when `Material.porosity` arrived (plan sec 7.4, "the user owns the value"),
and the material editor now has a row for it -- so a notice claiming it is pinned at
0.3 would contradict a control the user is looking at."""


def material_parameters(
    project: Project,
    part_materials: list[tuple[str, str]],
    dim: int,
    beam_properties: list[tuple[str, BeamSection, int]] | None = None,
    anchor_properties: list[tuple[str, AnchorSection, float, int]] | None = None,
    panel_properties: list[tuple[str, PanelSection]] | None = None,
    interface_properties: list[tuple[str, InterfaceSection, Material | None]] | None = None,
    k0: bool = False,
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

    `k0` writes the initial stage's companion file instead: the same file with `K0_NC`
    and `K0_MAIN_DIRECTION` added to each *soil* property, which is the entire
    difference between the reference deck's two materials files. Only
    `apply_k0_procedure_process` reads them, and only the initial stage runs it.

    A keyword rather than a second generator, deliberately: two generators would be two
    places that describe a material, and the one written less often would be the one
    that drifts. **Unknown, and worth saying out loud:** the reference case is linear
    elastic in both files, so it cannot tell us whether a Mohr-Coulomb project should
    fall back to an elastic law for the K0 stage. The project's real law is written in
    both until a case says otherwise (plan sec C4).
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
                "Variables": _variables(material, dim, k0,
                                        project.water_specific_weight),
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
                "Variables": _anchor_variables(section, prestress, anchor_dim, warnings),
                "Tables": {},
            },
        })
    for offset, (part_name, section, adjacent) in enumerate(
            interface_properties or []):
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": (len(part_materials) + len(beam_properties or [])
                              + len(panel_properties or [])
                              + len(anchor_properties or []) + offset + 1),
            "Material": {
                "constitutive_law": {"name": INTERFACE_LAW},
                "Variables": _interface_variables(section, project, warnings,
                                                  adjacent),
                "Tables": {},
            },
        })
    if properties:
        warnings.append(ASSUMPTIONS)
    return json.dumps({"properties": properties}, indent=4), warnings


def _interface_variables(section: InterfaceSection, project: Project,
                         warnings: list[str],
                         adjacent: Material | None = None) -> dict:
    """The contact's property set: two stiffnesses per unit area and a reduced strength.

    A zero-thickness element has no modulus, so the stiffnesses are kN/m3 in the project
    and N/m3 in the deck (`KILO`). Given explicitly they are used as they stand; left out
    they are derived from the soil the contact slides against:

        shear  = G / t,  where G = E / 2(1 + nu) and t is `virtual_thickness`,
                         the element size normal to the interface
        normal = NORMAL_TO_SHEAR_STIFFNESS * shear

    read off `MaterialParameters_for_generated_mesh.json`, whose two property sets are
    exactly `G` and `10 G` for its two soils at `t = 1`.

    **Which soil.** `adjacent` is the material of the body this stretch of contact
    actually runs against, which the deck already knows because it writes one part per
    body (`app/kratos.py:_interface_by_body`). It is the default, because a contact's
    stiffness and strength are properties of the ground it slides on: the reference
    groups its eight interfaces into two property sets on exactly that basis. A section
    that *names* a material overrides it for the whole contact, because a user who typed
    one meant it.

    Strength is that same soil's, reduced by `r_inter` -- the definition of the factor.
    A contact with no soil on either count and no explicit stiffnesses cannot be written,
    and is refused rather than defaulted to a number nobody chose.
    """
    soil = adjacent
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
    if shear is None:
        shear = soil.E / (2.0 * (1.0 + soil.nu) * section.virtual_thickness)
    if normal is None:
        normal = NORMAL_TO_SHEAR_STIFFNESS * shear
    variables = {
        # Fixed, and not inherited from the soil the way the stiffness and the strength
        # are. Kratos defaults a material that says nothing to `FULLY_COUPLED`, with a
        # deprecation warning and no other sign; a fully coupled element evaluates the
        # poro-elastic coupling terms, and a zero-thickness interface carries none of
        # what they need -- no `BULK_MODULUS_FLUID`, `BULK_MODULUS_SOLID`, `POROSITY`,
        # `BIOT_COEFFICIENT`, `DYNAMIC_VISCOSITY` or permeability. Those default to
        # zero, the water-pressure block divides zero by zero, and the stage that
        # installs the wall fails on NaN. The reference writes `CONSTANT_PW_FIELD` on
        # its interfaces for the same reason.
        #
        # So this follows what an interface section *carries*, not what the ground it
        # slides on does. If interfaces ever gain the fluid-storage properties, this can
        # follow the soil like everything else; until then, following it would only
        # reproduce that failure for an undrained model.
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
        # Both are kN/m3 in the project, whether typed on the section or derived
        # from the soil's E above, so both cross in one place.
        "INTERFACE_NORMAL_STIFFNESS": normal * KILO,
        "INTERFACE_SHEAR_STIFFNESS": shear * KILO,
    }
    if soil is not None:
        if soil.c is not None:
            variables["GEO_COHESION"] = soil.c * section.r_inter * KILO
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
        "YOUNG_MODULUS": section.E * KILO,
        "POISSON_RATIO": section.nu,
        # Not scaled: `BeamSection.density` is documented kg/m3, which is already SI.
        "DENSITY": section.density * per_metre,
        "CROSS_AREA": section.area * per_metre,
        "I33": section.inertia * per_metre,
        # A Timoshenko beam shears as well as bends, and Kratos checks for the shear
        # area before it solves anything: without it the element's own Check() stops the
        # run ("AREA_EFFECTIVE_Y is not defined in the properties"). A section that says
        # nothing takes the full one, exactly as Kratos' own GeoMechanics beam benchmarks
        # do (`tests/Interface/base_beam/MaterialParameters.json`) -- the shear-stiff end
        # of the range, since a real sheet pile shears in its web alone.
        "AREA_EFFECTIVE_Y": (section.area if section.shear_area is None
                             else section.shear_area) * per_metre,
    }
    if dim == 3:
        minor = section.inertia if section.inertia_minor is None else section.inertia_minor
        variables["I22"] = minor
        variables["TORSIONAL_INERTIA"] = (
            section.inertia + minor if section.torsional_inertia is None
            else section.torsional_inertia
        )
        # The second shear direction, which a plane-strain beam does not have.
        variables["AREA_EFFECTIVE_Z"] = section.area
    return variables


def _panel_variables(section: PanelSection) -> dict:
    """The wall shell's property set. A thickness, where a 2D pile has area and inertia.

    Nothing is smeared: a panel is the wall itself, not a metre run of one.
    """
    return {
        "YOUNG_MODULUS": section.E * KILO,
        "POISSON_RATIO": section.nu,
        "DENSITY": section.density,
        "THICKNESS": section.thickness,
    }


def _anchor_variables(section: AnchorSection, prestress: float, dim: int,
                      warnings: list[str]) -> dict:
    """The tendon's property set, smeared over its out-of-plane spacing in 2D.

    Plane strain models a metre run of wall, so an anchor every 2.5 m contributes
    two-fifths of its steel and two-fifths of its lock-off force to that metre. The
    section keeps the per-anchor numbers an engineer reads off a supplier sheet.

    In 3D there is nothing to smear: the anchor is a discrete member at the position it
    was drawn, so it carries its own full area and its own full lock-off force.

    The section's tension and compression limits are *not* written. This used to put
    them in as MAX_TENSION_STRESS and MAX_COMPRESSION_STRESS, two names that exist
    nowhere in Kratos -- `ReadMaterialsUtility` stops on the first variable it cannot
    resolve ("Value type for MAX_TENSION_STRESS not defined"), so every deck with a
    tendon limit died at material import, before a single node was solved. There is no
    Kratos property for a truss's capacity to put them in instead, so they stay in the
    project as the design values they are, and the export says so: a limit silently
    dropped reads as a capacity check the analysis is making and is not.
    """
    per_metre = 1.0 / section.spacing if dim == 2 else 1.0
    if section.tension_limit is not None or section.compression_limit is not None:
        warning = (f"tendon {section.name!r} carries a tension or compression limit; "
                   "Kratos has no truss property for one, so it is not exported and "
                   "the analysis will not check the anchor against it")
        if warning not in warnings:
            warnings.append(warning)
    return {
        "YOUNG_MODULUS": section.E * KILO,
        "CROSS_AREA": section.area * per_metre,
        "DENSITY": section.density * per_metre,
        "TRUSS_PRESTRESS_PK2": prestress * KILO * per_metre,
    }


def _law(material: Material, dim: int, warnings: list[str]) -> str:
    mapped = CONSTITUTIVE_LAWS.get(material.model)
    if mapped is None:
        mapped = LINEAR_ELASTIC
        warning = (f"{material.model!r} has no mapped Kratos constitutive law; "
                   f"material {material.name!r} is written as linear elastic")
        if warning not in warnings:
            warnings.append(warning)
    return mapped[0] if dim == 2 else mapped[1]


UNDRAINED_TYPES = ("Undrained (A)", "Undrained (B)")
"""The drainage types that generate excess pore pressure, and so need the fluid solved
for alongside the skeleton. Everything else prescribes the pressure field instead."""


def _drainage(material: Material) -> str:
    """Kratos' `GEO_DRAINAGE_TYPE`, from the material's own drainage type.

    `Material.type` is already the drainage vocabulary the GUI shows -- Drained, Undrained
    (A), Undrained (B), Non-porous -- so this is a mapping, not a new setting. A drained
    analysis prescribes the pore pressure field rather than solving for it, which is
    `CONSTANT_PW_FIELD`; only a material that generates excess pore pressure is
    `FULLY_COUPLED`.

    Everything but `Non-porous` went to `FULLY_COUPLED` until the deck was compared
    against `MaterialParameters_for_generated_mesh.json`, whose two drained soils are
    both `CONSTANT_PW_FIELD`.
    """
    return "FULLY_COUPLED" if material.type in UNDRAINED_TYPES else "CONSTANT_PW_FIELD"


def _variables(material: Material, dim: int, k0: bool = False,
               water_specific_weight: float = 10.0) -> dict:
    permeability = material.k / SECONDS_PER_DAY          # m/day -> m/s
    variables = {
        # Not `IGNORE_UNDRAINED`, which this wrote until the first real run: Kratos
        # deprecated that flag and converts it, once, into exactly this variable --
        # true to CONSTANT_PW_FIELD, false to FULLY_COUPLED
        # (`ConstitutiveLawUtilities::ReplaceIgnoreUndrainedByDrainageType`). Converting
        # it *once* is the problem: a staged deck reads its materials again in the
        # second stage, onto properties the first stage already converted, and Kratos
        # refuses a property set carrying both ("Both IGNORE_UNDRAINED and
        # GEO_DRAINAGE_TYPE are used"). Writing the modern name says the same thing and
        # survives being read twice.
        "GEO_DRAINAGE_TYPE": _drainage(material),
        "YOUNG_MODULUS": material.E * KILO,
        "POISSON_RATIO": material.nu,
        "DENSITY_SOLID": material.g_unsat * KILO / GRAVITY,
        # The same water the two hydrostatic processes stand in, rather than a flat
        # 1000: a project whose water is not exactly 9.81 kN/m3 used to describe it one
        # way in this file and another in `app.kratos_processes`.
        "DENSITY_WATER": water_specific_weight * KILO / GRAVITY,
        "POROSITY": (DEFAULT_POROSITY if material.porosity is None
                     else material.porosity),
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
        variables["GEO_COHESION"] = material.c * KILO
    if material.phi is not None:
        variables["GEO_FRICTION_ANGLE"] = material.phi
    if k0:
        # `K0_MAIN_DIRECTION` is the index of the vertical axis, which is the same 1 the
        # constraint and normal-load processes already write as `gravity_direction` --
        # derived rather than stored, because a project with two answers to "which way
        # is down" would be broken in more places than this one.
        variables["K0_MAIN_DIRECTION"] = 1
        variables["K0_NC"] = (material.k0_nc if material.k0_nc is not None
                              else material.k0_normally_consolidated())
    return variables
