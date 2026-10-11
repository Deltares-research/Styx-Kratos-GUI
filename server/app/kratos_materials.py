"""Write the Kratos GeoMechanics MaterialParameters.json beside an exported .mdpa.

Continuum elements keep property id 0, exactly as GiD writes them. Kratos' material
import process assigns their material properties by sub-model part name, and the names
here must be the ones the mdpa writes.

Load conditions never appear here. A line/point/surface load is not a constitutive
material, and no real Kratos GeoMechanics deck defines LINE_LOAD, POINT_LOAD or
SURFACE_LOAD in a MaterialParameters.json -- its magnitude is applied by a
ProjectParameters.json process against the load's sub-model part instead.

**The project already holds what Kratos reads.** Every property set is a constitutive law
and a `Variables` block under Kratos' names, in the project's unit system
(`app/schemas.py:KratosPropertySet`, `app/units.py`), and this module writes it as it
stands. It does three things on top, and no others:

*   **Fills what is missing and can be derived** -- the fluid constants, the water's
    density, the symmetric permeabilities, a beam's shear areas, an interface's
    stiffness and strength from its soil, K0 from Jaky. A value the user gave is never
    replaced, and every filled-in name is listed in the export's warnings.
*   **Smears** a 2D pile or anchor over its out-of-plane `spacing` -- plane strain models
    a metre run of wall. Geometry, not units.
*   **Orders** each block canonically (`_ordered`), so the same project always writes the
    same text.

Until 2026-10-10 the project was in kN, kN/m2 and m/day and this module converted it.
`app/legacy.py` turns such a project into the current shape with the numbers this module
used to write, so an old project's deck does not change.
"""

from __future__ import annotations

import json
import math

from app import units
from app.schemas import (SOIL_LAW_PAIRS, AnchorSection, BeamSection, InterfaceSection,
                         KratosPropertySet, Material, PanelSection, Project)


class MaterialError(RuntimeError):
    """A property set cannot be written. Surfaced to the command log, never guessed at."""


LINEAR_ELASTIC = ("GeoLinearElasticPlaneStrain2DLaw", "GeoIncrementalLinearElastic3DLaw")
"""The linear-elastic soil law per dimension. GeoMechanics registers no
`GeoLinearElastic3DLaw` -- the name this wrote until tests/kratos/test_kratos_registry.py
looked -- and its one 3D linear elastic soil law is the incremental one."""

LAW_IN_OTHER_DIMENSION = {law: other for law, (_, other) in SOIL_LAW_PAIRS.items()}
LAW_DIMENSION = {law: dim for law, (dim, _) in SOIL_LAW_PAIRS.items()}
"""Soil laws that exist in one dimension only (`schemas.SOIL_LAW_PAIRS`)."""

ANCHOR_LAW = "TrussConstitutiveLaw"
"""The law paired with `LinearTrussElement2D2N`."""

PANEL_LAW = "LinearElasticPlaneStress2DLaw"
"""The law paired with `ShellThinElement3D3N`, and the wall's counterpart to `BEAM_LAW`."""

INTERFACE_LAW = "GeoIncrementalLinearElasticInterfaceLaw"
"""The law paired with the `Geo_UPwLineInterface*` elements."""

BEAM_LAW = "TimoshenkoBeamElasticConstitutiveLaw"
"""The law paired with `LinearTimoshenkoCurvedBeamElement2D*N`."""

REQUIRED = {
    LINEAR_ELASTIC[0]: ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY_SOLID"),
    LINEAR_ELASTIC[1]: ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY_SOLID"),
    BEAM_LAW: ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY", "CROSS_AREA", "I33"),
    PANEL_LAW: ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY", "THICKNESS"),
    ANCHOR_LAW: ("YOUNG_MODULUS", "CROSS_AREA", "DENSITY"),
}
"""What each known law cannot run without and nothing here can derive. A property set
missing one is refused at export, naming it, rather than left for Kratos to stop on. A law
not listed here is the user's own business: it is written as given."""

# The constants a soil gets when it says nothing about them, in SI and expressed in the
# project's system when used -- the one place a unit conversion remains, and it converts
# a constant of nature, not anything the user typed.
DEFAULT_POROSITY = 0.3
BULK_MODULUS_SOLID_SI = 1.0e10     # Pa, the reference deck's own value
BULK_MODULUS_FLUID_SI = 2.2e9      # Pa, water at 20 C
DYNAMIC_VISCOSITY_SI = 1.0e-3      # Pa s, water at 20 C

NORMAL_TO_SHEAR_STIFFNESS = 10.0
"""How much stiffer a contact is across the joint than along it, when neither stiffness
is given. `MaterialParameters_for_generated_mesh.json` carries two interface property sets
whose normal stiffness is exactly ten times their own shear: effectively rigid across the
joint, free to slip along it at the strength `r_inter` sets."""

SOIL_ORDER = (
    "GEO_DRAINAGE_TYPE", "YOUNG_MODULUS", "POISSON_RATIO", "DENSITY_SOLID",
    "DENSITY_WATER", "POROSITY", "BULK_MODULUS_SOLID", "BULK_MODULUS_FLUID",
    "DYNAMIC_VISCOSITY", "PERMEABILITY_XX", "PERMEABILITY_YY", "PERMEABILITY_XY",
    "PERMEABILITY_ZZ", "PERMEABILITY_YZ", "PERMEABILITY_ZX", "GEO_COHESION",
    "GEO_FRICTION_ANGLE",
)
K0_ORDER = ("K0_MAIN_DIRECTION", "K0_NC")
BEAM_ORDER = ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY", "CROSS_AREA", "I33",
              "AREA_EFFECTIVE_Y", "I22", "TORSIONAL_INERTIA", "AREA_EFFECTIVE_Z")
PANEL_ORDER = ("YOUNG_MODULUS", "POISSON_RATIO", "DENSITY", "THICKNESS")
ANCHOR_ORDER = ("YOUNG_MODULUS", "CROSS_AREA", "DENSITY", "TRUSS_PRESTRESS_PK2")
INTERFACE_ORDER = ("GEO_DRAINAGE_TYPE", "INTERFACE_NORMAL_STIFFNESS",
                   "INTERFACE_SHEAR_STIFFNESS", "GEO_COHESION", "GEO_FRICTION_ANGLE",
                   "GEO_DILATANCY_ANGLE")

SMEARED_BEAM = ("CROSS_AREA", "I33", "AREA_EFFECTIVE_Y", "I22", "TORSIONAL_INERTIA",
                "AREA_EFFECTIVE_Z")
"""A 2D pile's per-member values divided by its spacing. Section quantities only: a
density is a property of the steel and does not thin out when the piles are further
apart -- the area already does that. (Dividing the density too, as this did until
2026-10-10, weighed a row of piles at 1/spacing^2 of its real weight.)"""
SMEARED_ANCHOR = ("CROSS_AREA",)
"""An anchor's steel per metre run of wall. Not its density (as above), and not its
prestress: `TRUSS_PRESTRESS_PK2` is a stress, and the force it puts into a metre of wall
is that stress times the smeared area already. (It was divided by the spacing as well
until 2026-10-10; `app/legacy.py` folds that into an old project's value, so its deck
does not change.)"""


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

    `part_materials` is (sub-model part name, material id) and the other lists the
    structural parts with their sections, all in the order the parts appear in the deck.
    Returns the JSON text and any warnings for the caller's log.

    One entry per sub-model part, not per material or section: Kratos binds a
    `Properties` object to a model part by name, so two sheet piles sharing a profile
    get two entries carrying the same numbers under different ids.

    `k0` writes the initial stage's companion file instead: the same file with the soil's
    `K0_*` variables in it, which only `apply_k0_procedure_process` reads, and only the
    initial stage runs. That stage is elastic whatever the model: a soil or contact with
    another law gets the elastic one in this file, exactly as Kratos' own Mohr-Coulomb
    staged-excavation reference runs its stage 1 on an elastic materials file.
    """
    warnings: list[str] = []
    derived: list[str] = []
    properties = []

    def add(part_name: str, law: str, variables: dict, tables: dict) -> None:
        properties.append({
            "model_part_name": f"PorousDomain.{part_name}",
            "properties_id": len(properties) + 1,
            "Material": {
                "constitutive_law": {"name": law},
                "Variables": variables,
                "Tables": tables,
            },
        })

    elastic: list[str] = []
    for part_name, material_id in part_materials:
        material = project.material(material_id)
        _check(material, f"material {material.name!r}")
        law = dimension_law(material.constitutive_law, dim)
        if k0 and law not in LINEAR_ELASTIC:
            elastic.append(f"material {material.name!r}")
            law = LINEAR_ELASTIC[0] if dim == 2 else LINEAR_ELASTIC[1]
        add(part_name, law, _variables(material, dim, k0, project, derived),
            material.tables)
    for part_name, section, beam_dim in beam_properties or []:
        _check(section, f"section {section.name!r}")
        add(part_name, section.constitutive_law,
            _beam_variables(section, beam_dim, derived), section.tables)
    for part_name, section in panel_properties or []:
        _check(section, f"wall section {section.name!r}")
        add(part_name, section.constitutive_law, _panel_variables(section), section.tables)
    for part_name, section, prestress, anchor_dim in anchor_properties or []:
        _check(section, f"tendon {section.name!r}")
        add(part_name, section.constitutive_law,
            _anchor_variables(section, prestress, anchor_dim, warnings), section.tables)
    for part_name, section, adjacent in interface_properties or []:
        law = section.constitutive_law
        if k0 and law != INTERFACE_LAW:
            elastic.append(f"interface section {section.name!r}")
            law = INTERFACE_LAW
        add(part_name, law,
            _interface_variables(section, project, warnings, adjacent, derived),
            section.tables)
    if elastic:
        warnings.append(
            "The K0 stage runs elastic: "
            + ", ".join(dict.fromkeys(elastic)) + " use the elastic law in "
            "initial_materials.json and their own from the next stage on.")
    if derived:
        warnings.append(
            "Derived where a property set left them out (type a value to replace it): "
            + "; ".join(dict.fromkeys(derived)))
    return json.dumps({"properties": properties}, indent=4), warnings


def dimension_law(law: str, dim: int) -> str:
    """`law` in a model of dimension `dim`: its counterpart when it is a one-dimension
    soil law of the other dimension, itself otherwise. A validated project is already in
    step (`Project._soil_laws_follow_the_dimension`); this covers one whose dimension
    was set by assignment, which validates nothing."""
    if LAW_DIMENSION.get(law, dim) == dim:
        return law
    return LAW_IN_OTHER_DIMENSION[law]


def translate_laws(materials: list[dict], dim: int, notes: list[str]) -> list[dict]:
    """Soil property sets (as dicts) with each one-dimension law swapped for its
    counterpart in `dim`. A law this application does not pair is kept, and named."""
    out = []
    for material in materials:
        law = material.get("constitutive_law", "")
        if law not in LAW_DIMENSION:
            notes.append(f"material {material.get('name')!r} keeps {law}: whether it is "
                         f"a {dim}D law is not known here -- check it")
            out.append(material)
            continue
        out.append({**material, "constitutive_law": dimension_law(law, dim)})
    return out


def _check(prop: KratosPropertySet, label: str) -> None:
    law = prop.constitutive_law
    missing = [name for name in REQUIRED.get(law, ()) if prop.number(name) is None]
    if missing:
        raise MaterialError(
            f"{label} ({law}) has no {', '.join(missing)}; Kratos cannot run it without "
            f"{'it' if len(missing) == 1 else 'them'}")


def _ordered(variables: dict, order: tuple[str, ...]) -> dict:
    """`variables` with the names in `order` first, in that order, then the rest as
    given: one text per project, whichever order the editor stored them in."""
    out = {name: variables[name] for name in order if name in variables}
    out.update((name, value) for name, value in variables.items() if name not in out)
    return out


def _fill(variables: dict, name: str, value, derived: list[str], label: str) -> None:
    if name not in variables and value is not None:
        variables[name] = value
        derived.append(f"{label}: {name}")


def _variables(material: Material, dim: int, k0: bool, project: Project,
               derived: list[str] | None = None) -> dict:
    """A soil's `Variables`: as given, plus what is missing and derivable."""
    derived = [] if derived is None else derived
    system = project.unit_system
    label = f"material {material.name!r}"
    given = dict(material.variables)
    k0_given = {name: given.pop(name) for name in list(given) if name.startswith("K0_")}
    v = dict(given)

    _fill(v, "GEO_DRAINAGE_TYPE", "CONSTANT_PW_FIELD", derived, label)
    _fill(v, "DENSITY_WATER", project.water_specific_weight / units.gravity(system),
          derived, label)
    _fill(v, "POROSITY", DEFAULT_POROSITY, derived, label)
    _fill(v, "BULK_MODULUS_SOLID",
          units.from_si(BULK_MODULUS_SOLID_SI, units.STRESS, system), derived, label)
    _fill(v, "BULK_MODULUS_FLUID",
          units.from_si(BULK_MODULUS_FLUID_SI, units.STRESS, system), derived, label)
    _fill(v, "DYNAMIC_VISCOSITY",
          units.from_si(DYNAMIC_VISCOSITY_SI, units.VISCOSITY, system), derived, label)
    permeability = material.number("PERMEABILITY_XX")
    if permeability is not None:
        _fill(v, "PERMEABILITY_YY", permeability, derived, label)
        _fill(v, "PERMEABILITY_XY", 0.0, derived, label)
        if dim == 3:
            _fill(v, "PERMEABILITY_ZZ", permeability, derived, label)
            _fill(v, "PERMEABILITY_YZ", 0.0, derived, label)
            _fill(v, "PERMEABILITY_ZX", 0.0, derived, label)
    v = _ordered(v, SOIL_ORDER)

    if k0:
        # `K0_MAIN_DIRECTION` is the index of the vertical axis, the same 1 the
        # constraint and normal-load processes write as `gravity_direction`.
        k0_v = dict(k0_given)
        _fill(k0_v, "K0_MAIN_DIRECTION", 1, derived, label)
        _fill(k0_v, "K0_NC", jaky(material), derived, label)
        v.update(_ordered(k0_v, K0_ORDER))
    return v


def jaky(material: Material) -> float | None:
    """Jaky's 1 - sin(phi), the standard correlation for K0 of a normally consolidated
    soil, and the one Kratos' staged-excavation reference deck's own numbers follow. None for a material with no friction angle: there is
    nothing to derive it from, and the K0 procedure is left to its own default."""
    phi = material.number("GEO_FRICTION_ANGLE")
    return None if phi is None else 1.0 - math.sin(math.radians(phi))


def _interface_variables(section: InterfaceSection, project: Project,
                         warnings: list[str], adjacent: Material | None = None,
                         derived: list[str] | None = None) -> dict:
    """The contact's property set: as given, plus what its soil lets us derive.

    A zero-thickness element has no modulus, so its stiffnesses are per unit area. Left
    out, they are derived from the soil the contact slides against:

        shear  = G / t,  where G = E / 2(1 + nu) and t is `virtual_thickness`,
        normal = NORMAL_TO_SHEAR_STIFFNESS * shear

    read off `MaterialParameters_for_generated_mesh.json`, whose two property sets are
    exactly `G` and `10 G` for its two soils at `t = 1`. Strength is that soil's,
    reduced by `r_inter` -- the definition of the factor.

    **Which soil.** `adjacent` is the material of the body this stretch of contact runs
    against (`app/kratos.py:_interface_by_body`): the reference groups its interfaces
    into property sets on exactly that basis. A section that *names* a material
    overrides it for the whole contact.

    A contact with neither a soil nor both stiffnesses cannot be written, and is refused
    rather than defaulted to a number nobody chose.
    """
    derived = [] if derived is None else derived
    label = f"interface section {section.name!r}"
    soil = adjacent
    if section.material is not None:
        soil = next((m for m in project.materials if m.id == section.material), None)
        if soil is None:
            warnings.append(
                f"interface section {section.name!r} references material "
                f"{section.material!r}, which is not in the project; its stiffnesses "
                "have to be given explicitly."
            )
    v = dict(section.variables)
    # Fixed, and not inherited from the soil: Kratos defaults a material that says
    # nothing to `FULLY_COUPLED`, and a zero-thickness interface carries none of what
    # the coupling terms need, so the stage that installs the wall fails on NaN. The
    # reference writes `CONSTANT_PW_FIELD` on its interfaces for the same reason.
    _fill(v, "GEO_DRAINAGE_TYPE", "CONSTANT_PW_FIELD", derived, label)
    shear = section.number("INTERFACE_SHEAR_STIFFNESS")
    if shear is None or "INTERFACE_NORMAL_STIFFNESS" not in v:
        modulus = soil.number("YOUNG_MODULUS") if soil is not None else None
        poisson = (soil.number("POISSON_RATIO") or 0.0) if soil is not None else 0.0
        if shear is None and modulus is None:
            raise MaterialError(
                f"interface section {section.name!r} has neither a soil material to "
                "reduce nor explicit INTERFACE_NORMAL_STIFFNESS and "
                "INTERFACE_SHEAR_STIFFNESS; one of the two is needed before the deck can "
                "be written.")
        if shear is None:
            shear = modulus / (2.0 * (1.0 + poisson) * section.virtual_thickness)
        _fill(v, "INTERFACE_NORMAL_STIFFNESS", NORMAL_TO_SHEAR_STIFFNESS * shear,
              derived, label)
        _fill(v, "INTERFACE_SHEAR_STIFFNESS", shear, derived, label)
    if soil is not None:
        # The section's own Rinter, or -- left unset -- the soil's.
        r_inter = section.r_inter if section.r_inter is not None else soil.r_inter
        cohesion = soil.number("GEO_COHESION")
        if cohesion is not None:
            _fill(v, "GEO_COHESION", cohesion * r_inter, derived, label)
        phi = soil.number("GEO_FRICTION_ANGLE")
        if phi is not None:
            _fill(v, "GEO_FRICTION_ANGLE", math.degrees(
                math.atan(math.tan(math.radians(phi)) * r_inter)), derived, label)
        _fill(v, "GEO_DILATANCY_ANGLE", 0.0, derived, label)
    return _ordered(v, INTERFACE_ORDER)


def _beam_variables(section: BeamSection, dim: int = 2,
                    derived: list[str] | None = None) -> dict:
    """The beam's property set: as given, its shear areas and 3D inertias filled in, and
    in 2D smeared over the section's spacing.

    A Timoshenko beam shears as well as bends, and Kratos checks for the shear area
    before it solves anything ("AREA_EFFECTIVE_Y is not defined in the properties"). A
    section that says nothing takes the full one, exactly as Kratos' own GeoMechanics
    beam benchmarks do. In 3D the weak-axis inertia defaults to the strong one and the
    torsion constant to their sum, the thin-walled open-section estimate.
    """
    derived = [] if derived is None else derived
    label = f"section {section.name!r}"
    v = dict(section.variables)
    area = section.number("CROSS_AREA")
    _fill(v, "AREA_EFFECTIVE_Y", area, derived, label)
    if dim == 3:
        inertia = section.number("I33")
        _fill(v, "I22", inertia, derived, label)
        minor = v.get("I22")
        if inertia is not None and isinstance(minor, (int, float)):
            _fill(v, "TORSIONAL_INERTIA", inertia + minor, derived, label)
        _fill(v, "AREA_EFFECTIVE_Z", area, derived, label)
    else:
        per_metre = 1.0 / section.spacing
        for name in SMEARED_BEAM:
            if isinstance(v.get(name), (int, float)) and not isinstance(v[name], bool):
                v[name] = v[name] * per_metre
    return _ordered(v, BEAM_ORDER)


def _panel_variables(section: PanelSection) -> dict:
    """The wall shell's property set, as given. Nothing is smeared: a panel is the wall
    itself, not a metre run of one."""
    return _ordered(dict(section.variables), PANEL_ORDER)


def _anchor_variables(section: AnchorSection, prestress: float, dim: int,
                      warnings: list[str]) -> dict:
    """The tendon's property set, the anchor's own prestress in it, smeared over the
    out-of-plane spacing in 2D.

    Plane strain models a metre run of wall, so an anchor every 2.5 m contributes
    two-fifths of its steel to that metre. In 3D there is nothing to smear: the anchor
    is the discrete member drawn.

    The anchor's `prestress` is its `TRUSS_PRESTRESS_PK2`; a non-zero one replaces any
    the tendon's own variables carry, which are the default for every anchor using it.

    The tension and compression limits are *not* written: Kratos has no truss property
    for a capacity (writing `MAX_TENSION_STRESS` once stopped every such deck at material
    import), so they stay in the project as design values, and the export says so.
    """
    if section.tension_limit is not None or section.compression_limit is not None:
        warning = (f"tendon {section.name!r} carries a tension or compression limit; "
                   "Kratos has no truss property for one, so it is not exported and "
                   "the analysis will not check the anchor against it")
        if warning not in warnings:
            warnings.append(warning)
    v = dict(section.variables)
    if prestress or "TRUSS_PRESTRESS_PK2" not in v:
        v["TRUSS_PRESTRESS_PK2"] = prestress
    if dim == 2:
        per_metre = 1.0 / section.spacing
        for name in SMEARED_ANCHOR:
            if isinstance(v.get(name), (int, float)) and not isinstance(v[name], bool):
                v[name] = v[name] * per_metre
    return _ordered(v, ANCHOR_ORDER)
