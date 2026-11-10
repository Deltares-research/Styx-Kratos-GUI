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
        convert = (lambda m: material(m, dim, water_weight)) if collection == "materials"             else CONVERTERS[collection]
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


OLD_CALCULATIONS = {
    "K0 procedure": ("mechanical", "K0"),
    "Plastic": ("mechanical", "none"),
    "Null step": ("mechanical", "none"),
    "Groundwater flow": ("flow", "none"),
}


def stage_calculation(value: dict) -> dict:
    """A stage saved before 2026-11 names one of four calculations. Now a stage has a
    calculation type and, if it is mechanical, a stress initialisation. A null step was
    a plastic stage that changes nothing, and it still is one. A stage in the new shape,
    or with a value that is neither, is left alone for the schema to judge.

    An initial plastic stage, or null step, becomes one initialised by gravity loading:
    that is what it was, as gravity was on unless the project switched it off
    (`drop_gravity`), and the initial stage's stress initialisation is now what decides
    the self weight (`core.model.stages.gravity`). Initialised by none, it would lose
    it."""
    old = OLD_CALCULATIONS.get(str(value.get("calculation")))
    if old is None:
        return value
    calculation, stresses = old
    if calculation == "mechanical" and stresses == "none" and value.get("parent") is None:
        stresses = "gravity"
    return {**value, "calculation": calculation, "stress_initialisation": stresses}


def stage_time(value: dict) -> dict:
    """A stage saved before 2026-11 has a `time_interval` in days, which the deck never
    read: every stage ran for one second in one step. Now a stage has a `duration` and a
    `time_step` in the project's unit of time, which is seconds in every system. A zero
    interval -- every stage the GUI made -- becomes the default; any other one its
    seconds, in one step, so the deck still solves the stage once."""
    if "time_interval" not in value:
        return value
    out = {key: v for key, v in value.items() if key != "time_interval"}
    days = value["time_interval"]
    if isinstance(days, (int, float)) and not isinstance(days, bool) and days > 0:
        out.setdefault("duration", days * SECONDS_PER_DAY)
        out.setdefault("time_step", out["duration"])
    return out


def drop_gravity(value: dict) -> dict:
    """A document saved before 2026-11-03 switches gravity on and off for itself
    (`gravity`). Now the initial stage's stress initialisation decides it
    (`core.model.stages.gravity`): none leaves the self weight out. Gravity off becomes
    an initial mechanical stage that initialises no stresses -- the stresses it had with
    gravity off were zero -- and the key is dropped. A flow sequence, or a project with
    no stages, always has the self weight now."""
    if "gravity" not in value:
        return value
    out = {key: v for key, v in value.items() if key != "gravity"}
    stages = out.get("stages")
    if value["gravity"] is not False or not isinstance(stages, list):
        return out
    out["stages"] = [_without_stresses(stage) for stage in stages]
    return out


def _without_stresses(stage: object) -> object:
    if not isinstance(stage, dict) or stage.get("parent") is not None:
        return stage
    stage = stage_calculation(stage)
    if stage.get("calculation", "mechanical") != "mechanical":
        return stage
    return {**stage, "stress_initialisation": "none"}


def notes(value: object) -> list[str]:
    """What opening the document `value` changes about its calculation, one sentence
    each, for whoever opens it: the conversions above that have no equivalent. Empty for
    a document in the current shape.

    Only gravity has one: switched off in a project with no stages, or in a flow
    sequence, it is on now (`drop_gravity`)."""
    if not isinstance(value, dict) or value.get("gravity") is not False:
        return []
    stages = value.get("stages", value.get("phases"))
    first = next((stage for stage in stages if isinstance(stage, dict)
                  and stage.get("parent") is None), None) if isinstance(stages, list) else None
    if first is None:
        return ["This project switched gravity off, which is no longer a switch of its "
                "own: the initial stage's stress initialisation decides it, and with no "
                "stages the self weight acts. To leave it out, add an initial stage and "
                "set its stress initialisation to none."]
    if stage_calculation(first).get("calculation") == "flow":
        return ["This project switched gravity off, which a flow calculation no longer "
                "can: the water has its weight again, so it flows from the differences "
                "in head rather than in pressure, and the hydraulic head is written. A "
                "horizontal section cannot be modelled now."]
    return []


def flow_tolerance(value: dict) -> dict:
    """A flow stage saved before 2026-11 has no absolute tolerance, and was written with
    the one of the Kratos deck its strategy was copied from: Muskat's
    `van_genuchten_hydrostatic`'s 1e-15 for Newton-Raphson, which a soil whose
    permeability depends on the water pressure is solved by -- without a seepage face,
    whose strategy has the default's 1e-9. A linear stage writes none. So a project
    with such a soil and no seepage face gives its old flow stages 1e-15, and the deck
    stays as it was."""
    stages = value.get("stages")
    if not isinstance(stages, list):
        return value
    conditions = value.get("boundary_conditions")
    if isinstance(conditions, list) and any(
            isinstance(c, dict) and c.get("kind") == "seepage" for c in conditions):
        return value
    materials = value.get("materials")
    if not isinstance(materials, list) or not any(
            isinstance(m, dict) and isinstance(m.get("variables"), dict)
            and m["variables"].get("RETENTION_LAW", "SaturatedLaw") != "SaturatedLaw"
            for m in materials):
        return value
    return {**value, "stages": [
        {**stage, "absolute_tolerance": VAN_GENUCHTEN_ABSOLUTE_TOLERANCE}
        if isinstance(stage, dict) and stage.get("calculation") == "Groundwater flow"
        and "absolute_tolerance" not in stage else stage
        for stage in stages]}


VAN_GENUCHTEN_ABSOLUTE_TOLERANCE = 1e-15
"""Kratos' `tests/Muskat/van_genuchten_hydrostatic`'s `residual_absolute_tolerance`."""


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


def pit_as_lines(pit: dict, domain: dict, layers: list[tuple[str, float, float]]
                 ) -> tuple[list[dict], list[dict], dict[str, list[str]]]:
    """A layered project's old pit, dug in two or more levels, as what says the same today:
    lines that cut the same pieces, and records that give them the keys and names they had.

    `layers` is (id, bottom, top). A vertical line down each side of the pit that is not the
    domain's edge, from the ground to the bottom, and one line across it per level that is
    not a layer boundary already. The pieces keep `soil_<layer>__lift<n>` and
    `soil_<layer>__pit`, so a saved stage still names the same soil. What lay outside the
    pit had the layer's plain key, which a cut layer no longer has: it is
    `soil_<layer>__outside` now, or `__outside_left` and `__outside_right` when the pit is
    in the middle.

    Returns the lines, the records, and what became of each plain key a stage may name.
    """
    x0, x1 = max(pit["x0"], domain["x0"]), min(pit["x1"], domain["x1"])
    top, bottom = domain["y_top"], domain["y_bottom"]
    levels = list(pit["levels"])

    lines = []
    if x1 < domain["x1"]:
        lines.append({"id": "pit_side", "name": "Pit side", "points": [(x1, top), (x1, bottom)]})
    if x0 > domain["x0"]:
        lines.append({"id": "pit_side_left", "name": "Pit side, left",
                      "points": [(x0, top), (x0, bottom)]})
    boundaries = {level for _, *span in layers for level in span}
    lines += [{"id": f"pit_level_{index}", "name": f"Pit level {index}",
               "points": [(x0, level), (x1, level)]}
              for index, level in enumerate(levels, start=1) if level not in boundaries]

    bands = [(f"lift{index}", f"lift {index}", level, ceiling) for index, (level, ceiling)
             in enumerate(zip(levels, [top, *levels]), start=1)]
    bands.append(("pit", "below the pit", bottom, levels[-1]))
    sides = []
    if x1 < domain["x1"]:
        sides.append(("right", (x1 + domain["x1"]) / 2))
    if x0 > domain["x0"]:
        sides.append(("left", (domain["x0"] + x0) / 2))

    bodies, outside = [], {}
    for layer, low, high in layers:
        for id, name, band_low, band_high in bands:
            floor, ceiling = max(low, band_low), min(high, band_high)
            if ceiling - floor > 1e-9:
                bodies.append({"id": id, "name": name, "layer": layer,
                               "point": ((x0 + x1) / 2, (floor + ceiling) / 2)})
        kept = []
        for side, x in sides:
            id = "outside" if len(sides) == 1 else f"outside_{side}"
            bodies.append({"id": id, "name": id.replace("_", " ") + " the pit", "layer": layer,
                           "point": (x, (low + high) / 2)})
            kept.append(f"soil_{layer}__{id}")
        outside[f"soil_{layer}"] = kept
    return lines, bodies, outside
