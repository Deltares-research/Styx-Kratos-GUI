"""Projects saved before the project had a unit system, converted once, on load.

Until 2026-10-10 a project was written in "engineering" units -- unit weights in kN/m3,
moduli and pressures in kN/m2, permeability in m/day, loads in kN -- and the exporter
converted all of it into the SI deck Kratos read. Now the project holds what Kratos
reads (a constitutive law and its `Variables`, under Kratos' own names) in a unit system
the project names, and the deck is written verbatim.

An old file is turned into the new shape here, in the SI system, carrying *exactly the
numbers the old exporter wrote*. So a project opened today exports the deck it exported
yesterday, and every derivation the old exporter made silently is now a value the user
can see and change. The constants and expressions below are therefore frozen history,
not configuration: they are what `core.kratos.materials` did on the day it stopped, and they
must not follow later changes there.

A file is old when its materials carry the old fields (`g_unsat`). Materials are
required in every project, so this is decided by the content, not by a version number
the file may or may not carry.
"""

from __future__ import annotations

import math
from typing import TypeGuard

KILO = 1000.0                   # kN -> N
GRAVITY = 9.81                  # m/s2: unit weight -> density
SECONDS_PER_DAY = 86_400.0      # m/day -> m/s
DEFAULT_POROSITY = 0.3
BULK_MODULUS_SOLID = 1.0e10     # Pa
BULK_MODULUS_FLUID = 2.2e9      # Pa
DYNAMIC_VISCOSITY = 1.0e-3      # Pa s
DEFAULT_WATER_SPECIFIC_WEIGHT = 10.0    # kN/m3

LINEAR_ELASTIC = {2: "GeoLinearElasticPlaneStrain2DLaw", 3: "GeoIncrementalLinearElastic3DLaw"}
BEAM_LAW = "TimoshenkoBeamElasticConstitutiveLaw"
PANEL_LAW = "LinearElasticPlaneStress2DLaw"
ANCHOR_LAW = "TrussConstitutiveLaw"
INTERFACE_LAW = "GeoIncrementalLinearElasticInterfaceLaw"

UNDRAINED_TYPES = ("Undrained (A)", "Undrained (B)")


def is_legacy(value: object) -> TypeGuard[dict]:
    """A whole old file: no unit system named, and every material in the old shape.

    A current document that merely carries one old-shaped record -- a script's -- is not
    one: its loads and pressures are already in its own units, and multiplying them by
    a thousand would be the very slip this module exists to prevent. Such records are
    converted one by one (`migrate_records`)."""
    if not isinstance(value, dict) or "unit_system" in value:
        return False
    materials = value.get("materials")
    return (isinstance(materials, list) and bool(materials)
            and all(isinstance(m, dict) and "g_unsat" in m for m in materials))


def migrate(value: dict) -> dict:
    """`value`, an old project document, in the current shape and the SI system."""
    out = dict(value)
    dim = out.get("dimension", 3)
    water = out.get("water")
    water_weight = (water.get("specific_weight", DEFAULT_WATER_SPECIFIC_WEIGHT)
                    if isinstance(water, dict) else DEFAULT_WATER_SPECIFIC_WEIGHT)

    out["unit_system"] = "SI"
    out["materials"] = [material(m, dim, water_weight) for m in out.get("materials", [])]
    out["beam_sections"] = [_beam_section(s) for s in out.get("beam_sections", [])]
    out["panel_sections"] = [_panel_section(s) for s in out.get("panel_sections", [])]
    out["anchor_sections"] = [_anchor_section(s) for s in out.get("anchor_sections", [])]
    out["interface_sections"] = [_interface_section(s)
                                 for s in out.get("interface_sections", [])]
    spacing = {sec.get("id"): sec.get("spacing", 2.5) for sec in value.get("anchor_sections", [])
               if isinstance(sec, dict)}
    out["anchors"] = [_anchor(a, spacing) for a in out.get("anchors", [])]
    out["loads"] = [_load(load) for load in out.get("loads", [])]
    if isinstance(out.get("load"), dict):           # the single load before `loads`
        out["load"] = _scaled(out["load"], "magnitude")
    out["normal_loads"] = [_scaled(n, "pressure") for n in out.get("normal_loads", [])]
    if isinstance(water, dict):
        out["water"] = {**water, "specific_weight": water_weight * KILO}
    return out


def is_old_record(collection: str, record: object) -> bool:
    """Is `record`, an entry of `collection`, in the old shape?"""
    if not isinstance(record, dict) or "variables" in record:
        return False
    if collection == "materials":
        return "g_unsat" in record
    if collection == "interface_sections":
        return "normal_stiffness" in record or "shear_stiffness" in record
    return "E" in record


CONVERTERS = {
    "beam_sections": lambda s: _beam_section(s),
    "panel_sections": lambda s: _panel_section(s),
    "anchor_sections": lambda s: _anchor_section(s),
    "interface_sections": lambda s: _interface_section(s),
}


def migrate_records(value: dict) -> dict:
    """A current project document in which some property sets are still in the old
    shape -- a script written against the old fields, say. Each such record is
    converted as an old file's would be, then expressed in the project's own system.
    Loads and pressures carry no shape to tell old from new by, and are left alone."""
    from core.model import units

    out = dict(value)
    dim = out.get("dimension", 3)
    system = out.get("unit_system", units.DEFAULT)
    water = out.get("water")
    water_weight = DEFAULT_WATER_SPECIFIC_WEIGHT
    if isinstance(water, dict) and water.get("specific_weight") is not None:
        water_weight = units.convert(water["specific_weight"], units.SPECIFIC_WEIGHT,
                                     system, "kN")

    def converted(record: dict) -> dict:
        if system != "SI":
            record = {**record, "variables": units.convert_variables(
                record["variables"], "SI", system)[0]}
            for key in ("tension_limit", "compression_limit"):
                if record.get(key) is not None:
                    record[key] = units.convert(record[key], units.FORCE, "SI", system)
        return record

    for collection in ("materials", *CONVERTERS):
        entries = out.get(collection)
        if not isinstance(entries, list) or not any(
                is_old_record(collection, e) for e in entries):
            continue
        convert = (lambda m: without_water(material(m, dim, water_weight))) \
            if collection == "materials" else CONVERTERS[collection]
        out[collection] = [converted(convert(e)) if is_old_record(collection, e) else e
                           for e in entries]
    return out


def material(m: dict, dim: int,
             water_weight: float = DEFAULT_WATER_SPECIFIC_WEIGHT) -> dict:
    """One old material record (kN/m3, kN/m2, m/day) as a current one, in SI."""
    variables = {
        "GEO_DRAINAGE_TYPE": ("FULLY_COUPLED" if m.get("type") in UNDRAINED_TYPES
                              else "CONSTANT_PW_FIELD"),
        "YOUNG_MODULUS": m["E"] * KILO,
        "POISSON_RATIO": m["nu"],
        "DENSITY_SOLID": m["g_unsat"] * KILO / GRAVITY,
        "DENSITY_WATER": water_weight * KILO / GRAVITY,
        "POROSITY": DEFAULT_POROSITY if m.get("porosity") is None else m["porosity"],
        "BULK_MODULUS_SOLID": BULK_MODULUS_SOLID,
        "BULK_MODULUS_FLUID": BULK_MODULUS_FLUID,
        "DYNAMIC_VISCOSITY": DYNAMIC_VISCOSITY,
    }
    permeability = m["k"] / SECONDS_PER_DAY
    variables.update({"PERMEABILITY_XX": permeability, "PERMEABILITY_YY": permeability,
                      "PERMEABILITY_XY": 0.0})
    if dim == 3:
        variables.update({"PERMEABILITY_ZZ": permeability, "PERMEABILITY_YZ": 0.0,
                          "PERMEABILITY_ZX": 0.0})
    if m.get("c") is not None:
        variables["GEO_COHESION"] = m["c"] * KILO
    if m.get("phi") is not None:
        variables["GEO_FRICTION_ANGLE"] = m["phi"]
    if m.get("k0_nc") is not None:
        variables["K0_NC"] = m["k0_nc"]
    out = {"id": m["id"], "name": m["name"], "color": m["color"],
           # Every model was written as linear elastic: it was the only law mapped.
           "constitutive_law": LINEAR_ELASTIC.get(dim, LINEAR_ELASTIC[3]),
           "variables": variables}
    for key in ("r_inter", "interface_permeability"):
        if key in m:
            out[key] = m[key]
    return out


def _beam_section(s: dict) -> dict:
    variables = {"YOUNG_MODULUS": s["E"] * KILO, "POISSON_RATIO": s["nu"],
                 "DENSITY": s["density"], "CROSS_AREA": s["area"], "I33": s["inertia"]}
    if s.get("shear_area") is not None:
        variables["AREA_EFFECTIVE_Y"] = s["shear_area"]
    if s.get("inertia_minor") is not None:
        variables["I22"] = s["inertia_minor"]
    if s.get("torsional_inertia") is not None:
        variables["TORSIONAL_INERTIA"] = s["torsional_inertia"]
    out = {"id": s["id"], "name": s["name"], "constitutive_law": BEAM_LAW,
           "variables": variables}
    if "spacing" in s:
        out["spacing"] = s["spacing"]
    return out


def _panel_section(s: dict) -> dict:
    return {"id": s["id"], "name": s["name"], "constitutive_law": PANEL_LAW,
            "variables": {"YOUNG_MODULUS": s["E"] * KILO, "POISSON_RATIO": s["nu"],
                          "DENSITY": s["density"], "THICKNESS": s["thickness"]}}


def _anchor_section(s: dict) -> dict:
    out = {"id": s["id"], "name": s["name"], "constitutive_law": ANCHOR_LAW,
           "variables": {"YOUNG_MODULUS": s["E"] * KILO, "CROSS_AREA": s["area"],
                         "DENSITY": s["density"]}}
    if "spacing" in s:
        out["spacing"] = s["spacing"]
    for key in ("tension_limit", "compression_limit"):
        if s.get(key) is not None:
            out[key] = s[key] * KILO
    return out


def _interface_section(s: dict) -> dict:
    variables = {}
    if s.get("normal_stiffness") is not None:
        variables["INTERFACE_NORMAL_STIFFNESS"] = s["normal_stiffness"] * KILO
    if s.get("shear_stiffness") is not None:
        variables["INTERFACE_SHEAR_STIFFNESS"] = s["shear_stiffness"] * KILO
    out = {"id": s["id"], "name": s["name"], "constitutive_law": INTERFACE_LAW,
           "variables": variables}
    for key in ("material", "r_inter", "virtual_thickness", "permeability"):
        if key in s:
            out[key] = s[key]
    return out


def _anchor(anchor: object, spacing: dict) -> object:
    """The prestress as the stress the deck carried: kN x 1000, divided by the tendon's
    spacing for a 2D anchor, as the old exporter smeared it."""
    if not isinstance(anchor, dict) or not anchor.get("prestress"):
        return anchor
    per_metre = (1.0 / spacing.get(anchor.get("section"), 2.5)
                 if anchor.get("kind", "anchor") == "anchor" else 1.0)
    return {**anchor, "prestress": anchor["prestress"] * KILO * per_metre}


def _scaled(record: object, key: str) -> object:
    if not isinstance(record, dict) or record.get(key) is None:
        return record
    return {**record, key: record[key] * KILO}


def _load(load: object) -> object:
    if not isinstance(load, dict) or "components" not in load:
        return load
    return {**load, "components": [c * KILO for c in load["components"]]}


def rename_phases(value: dict) -> dict:
    """A document saved before 2026-10 calls its stages `phases`; Kratos, and Styx since,
    calls them `stages`. Only the key changes: stage ids such as `phase_1` are user data,
    referenced by `parent`, and stay as they are.

    Both keys at once is what old code makes of a new dump --
    `{**project.model_dump(), "phases": [...]}` -- and Styx itself never writes
    `phases`, so the `phases` there is the one deliberately set, and it wins."""
    if "phases" not in value:
        return value
    out = dict(value)
    out.pop("stages", None)
    out["stages"] = out.pop("phases")
    return out

def drop_boreholes(value: dict) -> dict:
    """A document saved before 2026-10-24 hangs each layer's levels on boreholes:
    `tops` and `bots` map a borehole id to a level. Now a layer has one `top` and one
    `bottom`. Each layer takes the levels of the first borehole, the only levels the
    geometry ever read, so the mesh and the deck stay the same. The other boreholes'
    levels, and every borehole's ground and water level, had no effect and are dropped.

    A layer already in the new shape is left alone."""
    if "boreholes" not in value:
        return value
    out = dict(value)
    boreholes = out.pop("boreholes")
    first = (boreholes[0].get("id") if isinstance(boreholes, list) and boreholes
             and isinstance(boreholes[0], dict) else None)
    layers = out.get("layers")
    if isinstance(layers, list):
        out["layers"] = [_layer_at(layer, first) for layer in layers]
    return out


def _layer_at(layer: object, borehole: str | None) -> object:
    if not isinstance(layer, dict) or "tops" not in layer or "bots" not in layer:
        return layer
    out = {key: v for key, v in layer.items() if key not in ("tops", "bots")}
    for old, new in (("tops", "top"), ("bots", "bottom")):
        levels = layer[old]
        if isinstance(levels, dict) and borehole in levels:
            out[new] = levels[borehole]
    return out


def screen_sides(value: dict) -> dict:
    """A document saved before 2026-10-25 reads an interface's left and right walking its
    line in the order the points are stored. Now they are the faces on the screen
    (`Interface.side`). A one-side interface whose walking left is the screen's right --
    a pile drawn from the top down, say -- gets the other word, so it holds the same soil
    as before. A flat line's faces are named below and above.

    The document says which way it reads them by `interface_sides`, which every document
    saved since carries. One without it is converted; a record built in Python (a
    script's `Interface(...)`) is already in the new reading and is left alone."""
    if "interface_sides" in value:
        return value
    out = dict(value)
    out["interface_sides"] = "screen"
    interfaces = out.get("interfaces")
    if not isinstance(interfaces, list):
        return out
    piles = {b.get("id"): b.get("points") for b in out.get("beams") or []
             if isinstance(b, dict)}
    out["interfaces"] = [_on_screen(i, piles) for i in interfaces]
    return out


WATER = ("DENSITY_WATER", "BULK_MODULUS_FLUID", "DYNAMIC_VISCOSITY")
"""A soil's water variables until 2026-11-02 (`soil_models.WATER`)."""


def without_water(material: dict) -> dict:
    """A soil record without the water's variables, which are the project's now."""
    variables = material.get("variables")
    if not isinstance(variables, dict) or not any(name in variables for name in WATER):
        return material
    return {**material, "variables": {name: value for name, value in variables.items()
                                      if name not in WATER}}


def lift_water(value: dict) -> dict:
    """A document saved before 2026-11-02 has no `fluid`: each soil carried the water in
    its pores as its own `DENSITY_WATER`, `BULK_MODULUS_FLUID` and `DYNAMIC_VISCOSITY`.
    Now the water is the project's, one for every soil (`Fluid`). Its bulk modulus and
    viscosity are the first soil's that gives them -- every soil the application made
    gives the same -- and the soils' `DENSITY_WATER` goes: the export writes the water
    level's specific weight over g, the value the application filled it with. A soil
    whose deck that changes -- water of its own the others do not share -- is named
    when the file is opened (`water_notes`).

    The document says it is in the new shape by carrying `fluid`, which every document
    saved since does; one that does is left alone, so a soil given water of its own is
    refused, not quietly emptied."""
    if "fluid" in value:
        return value
    out = dict(value)
    materials = out.get("materials")
    out["fluid"] = _fluid(materials)
    if isinstance(materials, list):
        out["materials"] = [without_water(m) if isinstance(m, dict) else m
                            for m in materials]
    return out


FLUID_FIELDS = {"BULK_MODULUS_FLUID": "bulk_modulus", "DYNAMIC_VISCOSITY": "dynamic_viscosity"}


def _fluid(materials: object) -> dict:
    """The project's `Fluid` from its soils' water: each value the first soil's that
    gives it."""
    fluid: dict = {}
    for variables in _soil_variables(materials).values():
        for name, key in FLUID_FIELDS.items():
            given = _given(variables.get(name))
            if given is not None:
                fluid.setdefault(key, given)
    return fluid


def _soil_variables(materials: object) -> dict[str, dict]:
    """Each soil's `variables`, by its name."""
    if not isinstance(materials, list):
        return {}
    return {str(m.get("name") or m.get("id")): m["variables"] for m in materials
            if isinstance(m, dict) and isinstance(m.get("variables"), dict)}


def _given(value: object) -> float | None:
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            and value > 0 else None)


def water_notes(value: object) -> list[str]:
    """What `lift_water` changes in the deck, one line per soil: every water value a
    soil was written with that the project's water now overrides. A soil that gave none
    was written with water's own, so it is named when the project's water is not that.
    Values within a rounding (0.1 %) of each other are the same water."""
    from core.model import soil_models, units

    if not isinstance(value, dict) or "fluid" in value:
        return []
    soils = _soil_variables(value.get("materials"))
    system = value.get("unit_system", units.DEFAULT)
    if not soils or system not in units.SYSTEMS:
        return []
    level = value.get("water")
    weight = _given(level.get("specific_weight")) if isinstance(level, dict) else None
    fluid = _fluid(value.get("materials"))
    before = soil_models.water(system, weight)
    after = soil_models.water(system, weight, fluid.get("bulk_modulus"),
                              fluid.get("dynamic_viscosity"))
    notes = []
    for soil, variables in soils.items():
        changed = []
        for name in WATER:
            was = _given(variables.get(name))
            was = before[name] if was is None else was
            if not math.isclose(was, after[name], rel_tol=1e-3):
                unit = units.label(units.VARIABLES[name], system)
                changed.append(f"{name} {after[name]:g} {unit} instead of {was:g}")
        if changed:
            notes.append(f"{soil}: the pore water is the project's now, one for every "
                         f"soil, so this soil is written with {', '.join(changed)}. "
                         "Set the water with `fluid` and the water level's specific "
                         "weight, or under Water in the material window.")
    return notes


COULOMB_INTERFACE_LAWS = ("GeoInterfaceCoulombLawPlaneStrain",
                          "GeoInterfaceCoulombWithTensionCutOff")
"""The interface laws that read a strength (`core.kratos.materials`)."""
INTERFACE_STRENGTH = ("GEO_COHESION", "GEO_FRICTION_ANGLE")
DEFAULT_R_INTER = 0.70          # `Material.r_inter` when a soil gives none


def keep_old_deck(value: dict) -> dict:
    """What the export filled in for a document saved before 2026-11-02 -- one without
    `fluid` -- and fills no longer, put into the project, so its deck does not change:

    *   a soil's `POROSITY`, 0.3 when it had none. A porosity is the soil's now, and the
        export refuses a soil of a model without one.
    *   the strength of a Coulomb contact against a linear elastic soil it names: its
        cohesion c R and friction angle atan(R tan phi), with R the section's Rinter or
        else the soil's. The export took them from the soil whatever its law; now a
        linear elastic soil has no strength to give, and the contact carries its own.

    A Coulomb contact that names no soil takes each adjacent one's, which only the
    export knows; `contact_notes` names it when opening the file. A document with
    `fluid` is left alone."""
    if "fluid" in value:
        return value
    out = dict(value)
    materials = out.get("materials")
    if not isinstance(materials, list):
        return out
    out["materials"] = [_with_porosity(m) for m in materials]
    soils = {m.get("id"): m for m in materials if isinstance(m, dict)}
    sections = out.get("interface_sections")
    if isinstance(sections, list):
        out["interface_sections"] = [_with_own_strength(s, soils) for s in sections]
    return out


def _with_porosity(material: object) -> object:
    if not isinstance(material, dict) or not isinstance(material.get("variables"), dict) \
            or "POROSITY" in material["variables"]:
        return material
    return {**material, "variables": {**material["variables"], "POROSITY": DEFAULT_POROSITY}}


def _elastic(soil: object) -> TypeGuard[dict]:
    from core.model import soil_models

    return isinstance(soil, dict) and \
        soil_models.model_of(str(soil.get("constitutive_law"))) == soil_models.LINEAR_ELASTIC


def _number(value: object) -> float | None:
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def _takes_no_strength(section: object) -> TypeGuard[dict]:
    """A Coulomb contact without a strength of its own."""
    return (isinstance(section, dict)
            and section.get("constitutive_law") in COULOMB_INTERFACE_LAWS
            and not all(name in (section.get("variables") or {})
                        for name in INTERFACE_STRENGTH))


def _with_own_strength(section: object, soils: dict) -> object:
    if not _takes_no_strength(section):
        return section
    soil = soils.get(section.get("material"))
    if not _elastic(soil):
        return section
    given = soil.get("variables") or {}
    r_inter = _number(section.get("r_inter"))
    r_inter = r_inter if r_inter is not None else (_number(soil.get("r_inter"))
                                                   or DEFAULT_R_INTER)
    variables = dict(section.get("variables") or {})
    cohesion, phi = _number(given.get("GEO_COHESION")), _number(given.get("GEO_FRICTION_ANGLE"))
    if cohesion is not None:
        variables.setdefault("GEO_COHESION", cohesion * r_inter)
    if phi is not None:
        variables.setdefault("GEO_FRICTION_ANGLE", math.degrees(
            math.atan(math.tan(math.radians(phi)) * r_inter)))
    return {**section, "variables": variables}


def contact_notes(value: object) -> list[str]:
    """The Coulomb contacts of a document saved before 2026-11-02 whose deck may change,
    one line each: one that names no soil, in a project with a linear elastic soil that
    has a strength. Along such a soil the export took that strength, reduced by Rinter;
    now it refuses the contact until it has one of its own."""
    if not isinstance(value, dict) or "fluid" in value:
        return []
    materials = value.get("materials")
    elastic = [str(m.get("name") or m.get("id"))
               for m in (materials if isinstance(materials, list) else [])
               if _elastic(m) and any(name in (m.get("variables") or {})
                                      for name in INTERFACE_STRENGTH)]
    sections = value.get("interface_sections")
    if not elastic or not isinstance(sections, list):
        return []
    return [f"interface section {s.get('name') or s.get('id')!r}: a Coulomb contact takes "
            f"no strength from a linear elastic soil any more ({', '.join(elastic)}). "
            "Where it runs against one, it took that soil's cohesion and friction angle, "
            "reduced by Rinter, and the export now refuses it: give the section its own "
            "GEO_COHESION and GEO_FRICTION_ANGLE."
            for s in sections if _takes_no_strength(s) and s.get("material") is None]


def k0_notes(value: object) -> list[str]:
    """The linear elastic soils of a document saved before 2026-11-02 whose K0 changes,
    one line each: a soil without `K0_NC` that has a friction angle, in a project with a
    K0 procedure. The export took Jaky's 1 - sin(phi) for it; now it takes the elastic
    nu / (1 - nu) (`soil_models.k0`)."""
    from core.model import soil_models

    if not isinstance(value, dict) or "fluid" in value:
        return []
    stages = value.get("stages")
    if not any(isinstance(s, dict) and s.get("calculation") == "K0 procedure"
               for s in (stages if isinstance(stages, list) else [])):
        return []
    notes = []
    materials = value.get("materials")
    for soil in materials if isinstance(materials, list) else []:
        if not _elastic(soil) or not isinstance(soil.get("variables"), dict) \
                or "K0_NC" in soil["variables"]:
            continue
        phi = _number(soil["variables"].get("GEO_FRICTION_ANGLE"))
        now = soil_models.k0(str(soil.get("constitutive_law")), soil["variables"])
        if phi is None or now is None:
            continue
        was = 1.0 - math.sin(math.radians(phi))
        if not math.isclose(was, now, rel_tol=1e-3):
            notes.append(f"{soil.get('name') or soil.get('id')}: a linear elastic soil's K0 "
                         f"is nu / (1 - nu) now, so this soil starts from K0_NC {now:.4g} "
                         f"instead of Jaky's 1 - sin(phi) = {was:.4g}. Set K0_NC to "
                         f"{was:.4g} to keep the old initial stresses.")
    return notes


def undrained_notes(value: object) -> list[str]:
    """The `UNDRAINED` soils of a document saved before 2026-11-04, one line each: they
    are `FULLY_COUPLED` now, with their own permeability
    (`soil_models.project_drainage`)."""
    from core.model import soil_models

    if not isinstance(value, dict):
        return []
    notes = []
    for soil, variables in _soil_variables(value.get("materials")).items():
        note = soil_models.undrained_note(variables.get("GEO_DRAINAGE_TYPE"))
        if note:
            notes.append(f"{soil}: {note}")
    return notes


def drained_notes(value: object) -> list[str]:
    """The `DRAINED` soils of a document saved before 2026-11-02, one line each. The
    export wrote them as Kratos' `DRAINED`, which its U-Pw elements assemble as a coupled
    soil with the soil's own permeability; now it writes `CONSTANT_PW_FIELD`
    (`soil_models.KRATOS_DRAINAGE`). None in a groundwater flow calculation, whose water
    pressure elements read no drainage type."""
    from core.model import stages

    if not isinstance(value, dict) or "fluid" in value:
        return []
    every = value.get("stages")
    if isinstance(every, list) and every and all(
            isinstance(s, dict) and s.get("calculation") == stages.GROUNDWATER_FLOW
            for s in every):
        return []
    return [f"{soil}: a DRAINED soil is written as Kratos' CONSTANT_PW_FIELD now, so its "
            "water pressures are the ones the water conditions set, and Kratos does not "
            "solve them. It was written as Kratos' DRAINED, which Kratos calculates as "
            "FULLY_COUPLED with the soil's own permeability. Make it FULLY_COUPLED to "
            "keep that."
            for soil, variables in _soil_variables(value.get("materials")).items()
            if variables.get("GEO_DRAINAGE_TYPE") == "DRAINED"]


def upgraded(value: object) -> object:
    """`value`, a project document of any age, in the current shape: every conversion
    above, in the order the shapes came (`Project`'s validator)."""
    value = _before_water(value)
    return lift_water(keep_old_deck(value)) if isinstance(value, dict) else value


def notes(value: object) -> list[str]:
    """What opening `value` changes in its deck that the user has to know, one line
    each: the soils' own water it replaces (`water_notes`), the linear elastic soils
    whose K0 changes (`k0_notes`), the undrained soils that are coupled now
    (`undrained_notes`), the drained soils that are not any more (`drained_notes`) and
    the contacts that lose their soil's strength (`contact_notes`). Empty for a current
    document. Said when a file is opened (`core.session.migration_notes`, the GUI's
    Open), as the first save of it writes the new shape and the old values are gone."""
    value = _before_water(value)
    return (water_notes(value) + k0_notes(value) + undrained_notes(value)
            + drained_notes(value) + contact_notes(value))


def _before_water(value: object) -> object:
    if isinstance(value, dict):
        value = rename_phases(value)
    if is_legacy(value):
        value = migrate(value)
    elif isinstance(value, dict):
        value = migrate_records(value)
    if not isinstance(value, dict):
        return value
    return screen_sides(drop_boreholes(value))


def _on_screen(interface: object, piles: dict) -> object:
    from core.model import polylines

    if not isinstance(interface, dict) or interface.get("side") not in ("left", "right"):
        return interface
    line = (piles.get(interface.get("structure")) if interface.get("structure")
            else interface.get("points"))
    if not line:
        return interface        # no line to read it on: the schema says why
    try:
        face = polylines.screen_face(line, interface["side"])
    except (TypeError, IndexError, KeyError, ValueError):
        return interface        # not a usable line: the schema says why
    return {**interface, "side": face}
