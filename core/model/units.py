"""The project's unit system.

Kratos has no units. It needs one consistent set, with gravity expressed in it, and then
every number it reads and writes is in that set. So the project chooses the set, the
user types every value in it, the deck carries those values verbatim, and the results
come back in it -- there is no conversion anywhere between the editor and Kratos.

Both systems on offer measure length in metres and time in seconds, which is why gravity
is 9.81 in each and why a deck in either one needs no constant changed:

| System | mass | length | time | force | stress | density |
|---|---|---|---|---|---|---|
| `SI` | kg | m | s | N | Pa | kg/m3 |
| `kN` | t | m | s | kN | kPa | t/m3 |

The one place values *are* converted is a deliberate switch of system
(`convert`, `convert_variables`), which rewrites the stored project once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DEFAULT: Final = "SI"


@dataclass(frozen=True)
class System:
    name: str
    mass: float            # this system's unit of mass, in kg
    length: float          # in m
    time: float            # in s
    title: str


SYSTEMS: dict[str, System] = {
    "SI": System("SI", 1.0, 1.0, 1.0, "SI (N, m, kg, s)"),
    "kN": System("kN", 1000.0, 1.0, 1.0, "kN, m, t, s"),
}

GRAVITY_SI = 9.81
"""m/s2. The magnitude the deck's gravity is written with."""


@dataclass(frozen=True)
class Quantity:
    """A physical quantity: its dimension as exponents of (mass, length, time), and its
    label in each system. Two quantities can share a dimension and differ in label --
    a force and a moment per metre run are both M L T^-2."""
    name: str
    dimension: tuple[int, int, int]
    labels: dict[str, str]


def _q(name: str, dimension: tuple[int, int, int], si: str, kn: str) -> Quantity:
    return Quantity(name, dimension, {"SI": si, "kN": kn})


STRESS = _q("stress", (1, -1, -2), "Pa", "kPa")
FORCE = _q("force", (1, 1, -2), "N", "kN")
LINE_FORCE = _q("line force", (1, 0, -2), "N/m", "kN/m")
MOMENT_PER_LENGTH = _q("moment per length", (1, 1, -2), "N·m/m", "kN·m/m")
DENSITY = _q("density", (1, -3, 0), "kg/m³", "t/m³")
SPECIFIC_WEIGHT = _q("specific weight", (1, -2, -2), "N/m³", "kN/m³")
STIFFNESS_PER_AREA = _q("stiffness per area", (1, -2, -2), "N/m³", "kN/m³")
VISCOSITY = _q("viscosity", (1, -1, -1), "Pa·s", "kPa·s")
PERMEABILITY = _q("permeability", (0, 2, 0), "m²", "m²")
AREA = _q("area", (0, 2, 0), "m²", "m²")
INERTIA = _q("second moment of area", (0, 4, 0), "m⁴", "m⁴")
LENGTH = _q("length", (0, 1, 0), "m", "m")
ACCELERATION = _q("acceleration", (0, 1, -2), "m/s²", "m/s²")
DIMENSIONLESS = _q("dimensionless", (0, 0, 0), "", "")
ANGLE = _q("angle", (0, 0, 0), "°", "°")

QUANTITIES = {q.name: q for q in (STRESS, FORCE, LINE_FORCE, MOMENT_PER_LENGTH, DENSITY,
                                  SPECIFIC_WEIGHT, STIFFNESS_PER_AREA, VISCOSITY,
                                  PERMEABILITY, AREA, INERTIA, LENGTH, ACCELERATION,
                                  DIMENSIONLESS, ANGLE)}

VARIABLES: dict[str, Quantity] = {
    # Soil
    "YOUNG_MODULUS": STRESS, "POISSON_RATIO": DIMENSIONLESS,
    "DENSITY_SOLID": DENSITY, "DENSITY_WATER": DENSITY, "POROSITY": DIMENSIONLESS,
    "BULK_MODULUS_SOLID": STRESS, "BULK_MODULUS_FLUID": STRESS,
    "DYNAMIC_VISCOSITY": VISCOSITY, "BIOT_COEFFICIENT": DIMENSIONLESS,
    "PERMEABILITY_XX": PERMEABILITY, "PERMEABILITY_YY": PERMEABILITY,
    "PERMEABILITY_ZZ": PERMEABILITY, "PERMEABILITY_XY": PERMEABILITY,
    "PERMEABILITY_YZ": PERMEABILITY, "PERMEABILITY_ZX": PERMEABILITY,
    "GEO_COHESION": STRESS, "GEO_FRICTION_ANGLE": ANGLE, "GEO_DILATANCY_ANGLE": ANGLE,
    "GEO_TENSILE_STRENGTH": STRESS,
    "K0_NC": DIMENSIONLESS, "K0_MAIN_DIRECTION": DIMENSIONLESS,
    "K0_VALUE_XX": DIMENSIONLESS, "K0_VALUE_YY": DIMENSIONLESS,
    "K0_VALUE_ZZ": DIMENSIONLESS, "OCR": DIMENSIONLESS,
    "POISSON_UNLOADING_RELOADING": DIMENSIONLESS,
    "SATURATED_SATURATION": DIMENSIONLESS, "RESIDUAL_SATURATION": DIMENSIONLESS,
    "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": STRESS, "VAN_GENUCHTEN_GN": DIMENSIONLESS,
    "VAN_GENUCHTEN_GL": DIMENSIONLESS, "MINIMUM_RELATIVE_PERMEABILITY": DIMENSIONLESS,
    "PERMEABILITY_CHANGE_INVERSE_FACTOR": DIMENSIONLESS,
    # Interfaces
    "INTERFACE_NORMAL_STIFFNESS": STIFFNESS_PER_AREA,
    "INTERFACE_SHEAR_STIFFNESS": STIFFNESS_PER_AREA,
    # Structures
    "DENSITY": DENSITY, "CROSS_AREA": AREA, "AREA_EFFECTIVE_Y": AREA,
    "AREA_EFFECTIVE_Z": AREA, "I33": INERTIA, "I22": INERTIA,
    "TORSIONAL_INERTIA": INERTIA, "THICKNESS": LENGTH,
    "THICKNESS_EFFECTIVE_Y": LENGTH, "THICKNESS_EFFECTIVE_Z": LENGTH,
    "TRUSS_PRESTRESS_PK2": STRESS,
}
"""The dimension of each Kratos variable this application knows. A variable missing here
is still written as typed; only a change of unit system cannot convert it."""


def system(name: str) -> System:
    try:
        return SYSTEMS[name]
    except KeyError:
        raise ValueError(f"unknown unit system {name!r}; one of {sorted(SYSTEMS)}") \
            from None


def gravity(name: str) -> float:
    """Gravity's magnitude in the system `name`."""
    s = system(name)
    return GRAVITY_SI * s.time ** 2 / s.length


def _unit(quantity: Quantity, s: System) -> float:
    m, l, t = quantity.dimension
    return s.mass ** m * s.length ** l * s.time ** t


def convert(value: float, quantity: Quantity, source: str, target: str) -> float:
    """`value`, a `quantity` in system `source`, expressed in system `target`."""
    return value * _unit(quantity, system(source)) / _unit(quantity, system(target))


def from_si(value: float, quantity: Quantity, target: str) -> float:
    return convert(value, quantity, "SI", target)


def label(quantity: Quantity, name: str) -> str:
    system(name)
    return quantity.labels[name]


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def convert_variables(variables: dict, source: str, target: str) -> tuple[dict, list[str]]:
    """A Kratos `Variables` block in `target`, and the names of the numeric entries it
    could not convert because their dimension is not known here. Order is kept."""
    out, unknown = {}, []
    for name, value in variables.items():
        quantity = VARIABLES.get(name)
        if quantity is not None and _is_number(value):
            out[name] = convert(float(value), quantity, source, target)
            continue
        if quantity is None and (_is_number(value) or isinstance(value, list)):
            unknown.append(name)
        out[name] = value
    return out, unknown


# ── Changing the system of a whole project ──────────────────────────────────

_PROPERTY_SETS = ("materials", "beam_sections", "panel_sections", "anchor_sections",
                  "interface_sections")
_LOAD_QUANTITY = {"point": FORCE, "line": LINE_FORCE, "surface": STRESS}


def convert_project(payload: dict, target: str) -> tuple[dict, list[str]]:
    """A project document (`Project.model_dump`) re-expressed in system `target`, and
    notes on anything that could not be converted.

    Every value that carries a mass converts -- property-set variables by their Kratos
    name, loads, pressures, the water's weight, prestress, tendon limits. Geometry does
    not: both systems are in metres and seconds.
    """
    source = payload.get("unit_system", DEFAULT)
    system(source), system(target)
    out = dict(payload)
    out["unit_system"] = target
    if source == target:
        return out, []
    notes: list[str] = []

    def value(v, quantity):
        return None if v is None else convert(v, quantity, source, target)

    for collection in _PROPERTY_SETS:
        converted = []
        for entry in payload.get(collection, []):
            variables, unknown = convert_variables(entry.get("variables", {}), source, target)
            entry = {**entry, "variables": variables}
            if unknown:
                notes.append(f"{entry.get('name', entry.get('id'))}: "
                             f"{', '.join(unknown)} kept as typed -- their units are not "
                             f"known here; convert them to {system(target).title} by hand")
            if entry.get("tables"):
                notes.append(f"{entry.get('name', entry.get('id'))}: its Tables were kept "
                             "as typed; check their units")
            if collection == "anchor_sections":
                for key in ("tension_limit", "compression_limit"):
                    entry[key] = value(entry.get(key), FORCE)
            converted.append(entry)
        out[collection] = converted

    out["anchors"] = [{**a, "prestress": value(a.get("prestress", 0.0), STRESS)}
                      for a in payload.get("anchors", [])]
    out["loads"] = [{**load, "components": [value(c, _LOAD_QUANTITY[load.get("kind", "surface")])
                                            for c in load["components"]]}
                    for load in payload.get("loads", [])]
    out["normal_loads"] = [{**n, "pressure": value(n.get("pressure", 0.0), STRESS)}
                           for n in payload.get("normal_loads", [])]
    out["boundary_conditions"] = [
        {**c, "value": value(c.get("value", 0.0), STRESS),
         "pressure_tension_cut_off": value(c.get("pressure_tension_cut_off", 0.0), STRESS)}
        if c.get("kind") == "water_pressure" else c
        for c in payload.get("boundary_conditions", [])]
    water = payload.get("water")
    if isinstance(water, dict):
        out["water"] = {**water,
                        "specific_weight": value(water.get("specific_weight"),
                                                 SPECIFIC_WEIGHT)}
    return out, notes
