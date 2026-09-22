"""What a user may ask to see, and what the number means when they do.

`app.gid_results` reads the file; this decides what is in it worth looking at. The two
are separate because the first is a question about a text format and the second is a
question about geotechnics, and only the second has opinions.

── The catalogue comes from the file, never from a list here ────────────────

`catalogue` asks the parsed results what variables they carry and offers only the
quantities those support. That is decision 1.3 of `plan/postprocessing-plan.md`, and it
is what makes widening the deck's output (P4) safe: a variable Kratos declines to write,
or writes an empty block for because the element does not implement it, costs one
missing menu entry and breaks nothing. The beam's empty `CAUCHY_STRESS_TENSOR` block is
exactly that case, and it is in every run on this machine.

── Units: the deck is SI, the project is kN ─────────────────────────────────

`server/app/schemas.py` opens by saying the project is m / kN / day, and
`kratos_materials.KILO` exists because the deck once went out in two unit systems at
once. The same hazard runs in reverse here: `BENDING_MOMENT` comes back from a real run
as `3990.4`, which is 3.99 kN*m, and a postprocessor printing 3990 kN*m is wrong by a
factor of a thousand in a way that looks completely reasonable. So there is one scale
per quantity, `KILO` is imported rather than restated, and a test asserts the two agree.

── Signs: compression is negative, and stays negative ───────────────────────

Kratos writes compression negative, which is the continuum-mechanics convention -- and
it is the one this program shows its results in. So nothing is
flipped. `p'` is negative in compression, `q` and `tau_max` are non-negative, and the
principal stresses are ordered algebraically, `s1 <= s2 <= s3`, so `s1` is the most
compressive. `COMPRESSION_POSITIVE` names the decision so that reversing it is an edit
to one constant and a failing test rather than a silent inversion of every number
anyone has ever read off this program.

── One thing that is not obvious and is easy to get backwards ───────────────

A Gauss-point quantity reaches an element by averaging, and an element quantity reaches
a node by averaging again over the elements that touch it. For a *component* the order
does not matter. For an invariant it does: `q` is not linear in the components, so
averaging the tensor and then deriving `q` is a different number from deriving `q` at
each integration point and averaging that. Two integration points with equal and
opposite shear have `q = sqrt(3)*tau` each and a tensor average with `q = 0`.

Everything here derives first and averages second.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from app import kratos_materials
from app.gid_results import GidMesh, Results

KILO = kratos_materials.KILO
"""kN -> N, imported rather than written again. Every scale below is expressed through
it, so a stress read back cannot drift from a stress written out."""

STRESS_SCALE = 1.0 / KILO
"""Pa -> kPa. Also N/m2 -> kN/m2, which is what a geotechnical engineer types."""

LENGTH_SCALE = 1.0
"""m -> m. Named rather than left implicit so that a field with no conversion says so."""

COMPRESSION_POSITIVE = False
"""Whether stresses are flipped on the way out. They are not -- see the module
docstring. This is a constant so that the decision is visible and testable."""

XX, YY, ZZ, XY, YZ, XZ = range(6)
"""GiD's component order for a symmetric tensor."""


class UnknownField(LookupError):
    """No such field, or not at that location. Surfaced as a 404/422, never guessed at."""


# ── Deriving one number from one entry ──────────────────────────────────────

def _component(index: int) -> Callable[[list[float]], float]:
    return lambda values: values[index]


def _magnitude(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values[:3]))


def _mean_stress(s: list[float]) -> float:
    """p'. Negative in compression, as the module docstring sets out."""
    return (s[XX] + s[YY] + s[ZZ]) / 3.0


def _deviatoric_stress(s: list[float]) -> float:
    """q = sqrt(3/2 * s:s), the von Mises equivalent. Never negative.

    Written as the explicit component form rather than by building a deviator, because
    the component form has no cancellation to get wrong and is exact for a hydrostatic
    tensor -- which is the case that produces a small non-zero q, or a NaN out of a
    square root of a negative rounding error, in the implementations that do not.
    """
    normal = ((s[XX] - s[YY]) ** 2 + (s[YY] - s[ZZ]) ** 2 + (s[ZZ] - s[XX]) ** 2) / 2.0
    shear = 3.0 * (s[XY] ** 2 + s[YZ] ** 2 + s[XZ] ** 2)
    return math.sqrt(max(normal + shear, 0.0))


def _principal(s: list[float]) -> tuple[float, float, float]:
    """The three principal stresses, ascending, so `s1` is the most compressive.

    Solved as a symmetric 3x3 eigenproblem in closed form (the standard trigonometric
    solution for the three real roots of the characteristic polynomial), because that
    is exact for the plane-strain case this project mostly produces -- where `yz` and
    `xz` are zero and one principal direction is out of plane -- and does not need an
    iterative solver in the request path.

    The hydrostatic case is handled before anything is divided: there `q` is zero and
    the general formula divides by it.
    """
    q = _deviatoric_stress(s)
    mean = _mean_stress(s)
    if q < 1e-12 * max(1.0, abs(mean)):
        return (mean, mean, mean)

    # The deviator, and its second and third invariants.
    d = [s[XX] - mean, s[YY] - mean, s[ZZ] - mean, s[XY], s[YZ], s[XZ]]
    j2 = (d[XX] ** 2 + d[YY] ** 2 + d[ZZ] ** 2) / 2.0 + d[XY] ** 2 + d[YZ] ** 2 + d[XZ] ** 2
    j3 = (d[XX] * d[YY] * d[ZZ] + 2.0 * d[XY] * d[YZ] * d[XZ]
          - d[XX] * d[YZ] ** 2 - d[YY] * d[XZ] ** 2 - d[ZZ] * d[XY] ** 2)

    radius = 2.0 * math.sqrt(max(j2 / 3.0, 0.0))
    # Clamped: the argument is within [-1, 1] mathematically and can leave it by a
    # rounding error at the degenerate corners, where acos would raise.
    cosine = 0.0 if radius == 0 else max(-1.0, min(1.0, 4.0 * j3 / radius ** 3))
    angle = math.acos(cosine) / 3.0

    roots = sorted(mean + radius * math.cos(angle - 2.0 * math.pi * k / 3.0)
                   for k in (0, 1, 2))
    return (roots[0], roots[1], roots[2])


def _tau_max(s: list[float]) -> float:
    low, _, high = _principal(s)
    return (high - low) / 2.0


# ── What is on offer ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Definition:
    """One thing a user can ask to see.

    `name` is what `results field <name>` takes and what the API path carries; `source`
    is the Kratos variable it needs, and a definition whose source is absent from the
    file is simply never offered.
    """
    name: str
    label: str
    group: str
    source: str
    derive: Callable[[list[float]], float]
    unit: str
    scale: float


def _displacements(source: str, prefix: str, group: str, label: str) -> tuple:
    return (
        Definition(prefix, f"|{label}|", group, source, _magnitude, "m", LENGTH_SCALE),
        Definition(f"{prefix}x", f"{label}_x", group, source, _component(0), "m", LENGTH_SCALE),
        Definition(f"{prefix}y", f"{label}_y", group, source, _component(1), "m", LENGTH_SCALE),
        Definition(f"{prefix}z", f"{label}_z", group, source, _component(2), "m", LENGTH_SCALE),
    )


def _stresses(source: str, group: str, mark: str) -> tuple:
    kPa = "kPa"
    return (
        Definition(f"s{mark}xx", f"σ{mark}xx", group, source, _component(XX), kPa, STRESS_SCALE),
        Definition(f"s{mark}yy", f"σ{mark}yy", group, source, _component(YY), kPa, STRESS_SCALE),
        Definition(f"s{mark}zz", f"σ{mark}zz", group, source, _component(ZZ), kPa, STRESS_SCALE),
        Definition(f"s{mark}xy", f"σ{mark}xy", group, source, _component(XY), kPa, STRESS_SCALE),
        Definition(f"s{mark}yz", f"σ{mark}yz", group, source, _component(YZ), kPa, STRESS_SCALE),
        Definition(f"s{mark}xz", f"σ{mark}xz", group, source, _component(XZ), kPa, STRESS_SCALE),
        Definition(f"p{mark}", f"p{mark} (mean)", group, source, _mean_stress, kPa, STRESS_SCALE),
        Definition(f"q{mark}", "q (deviatoric)", group, source, _deviatoric_stress, kPa, STRESS_SCALE),
        Definition(f"s{mark}1", f"σ{mark}1 (most compressive)", group, source,
                   lambda s: _principal(s)[0], kPa, STRESS_SCALE),
        Definition(f"s{mark}2", f"σ{mark}2", group, source,
                   lambda s: _principal(s)[1], kPa, STRESS_SCALE),
        Definition(f"s{mark}3", f"σ{mark}3 (least compressive)", group, source,
                   lambda s: _principal(s)[2], kPa, STRESS_SCALE),
        Definition(f"tau{mark}_max" if mark else "tau_max", "τ max", group, source,
                   _tau_max, kPa, STRESS_SCALE),
    )


DEFINITIONS: tuple[Definition, ...] = (
    # Total, then per-phase: the order a user looks for them in, and the reason
    # the two are separate groups rather than one. `TOTAL_DISPLACEMENT` accumulates
    # across stages, `DISPLACEMENT` is what this stage alone did -- confirmed against a
    # real seven-stage run, where the two differ in both magnitude and sign.
    *_displacements("TOTAL_DISPLACEMENT", "u", "Deformations", "u"),
    *_displacements("DISPLACEMENT", "du", "Phase deformations", "Δu"),

    *_stresses("CAUCHY_STRESS_TENSOR", "Effective stresses", ""),
    # Written only once the deck asks for it (P4). Offered automatically when it is
    # there, which is the whole point of deriving the catalogue from the file.
    *_stresses("TOTAL_STRESS_TENSOR", "Total stresses", "_t"),

    Definition("pw", "Pore pressure", "Groundwater", "WATER_PRESSURE",
               _component(0), "kPa", STRESS_SCALE),
    Definition("head", "Hydraulic head", "Groundwater", "HYDRAULIC_HEAD",
               _component(0), "m", LENGTH_SCALE),
    Definition("saturation", "Degree of saturation", "Groundwater",
               "DEGREE_OF_SATURATION", _component(0), "-", 1.0),
)

BY_NAME = {definition.name: definition for definition in DEFINITIONS}

GROUP_ORDER = ("Deformations", "Phase deformations", "Effective stresses",
               "Total stresses", "Strains", "Groundwater")


def catalogue(results: Results) -> list[dict]:
    """The field menu for one stage, derived from what that stage's file contains.

    A definition is offered when its source variable is present *and has values*. The
    distinction matters: Kratos writes a declared but empty block for a variable an
    element does not implement, and offering that would put a menu entry in front of
    the user that paints nothing.
    """
    available = {field.variable for field in results.all_fields() if field.values}

    groups: dict[str, list[dict]] = {}
    for definition in DEFINITIONS:
        if definition.source not in available:
            continue
        source = results.field(definition.source)
        groups.setdefault(definition.group, []).append({
            "name": definition.name,
            "label": definition.label,
            "unit": definition.unit,
            "source": definition.source,
            "locations": _locations(source.location),
        })
    return [{"name": name, "fields": groups[name]}
            for name in GROUP_ORDER if name in groups]


def _locations(location: str) -> list[str]:
    """Where a field can be drawn.

    A nodal variable is only ever nodal -- an element-wise displacement is not a thing
    anyone means to ask for. A Gauss variable can be either: per element, which is what
    the solver actually computed, or averaged onto nodes, which is what a smooth
    contour needs.
    """
    return ["nodes"] if location == "nodes" else ["elements", "nodes"]


# ── Getting one ─────────────────────────────────────────────────────────────

def values(results: Results, mesh: GidMesh, name: str, location: str = "nodes") -> dict:
    """One field, as the ids it is defined on and the numbers on them.

    Returns the range alongside, computed here rather than by the caller so that the
    colour legend and the colours can never be of two different things.
    """
    definition = BY_NAME.get(name)
    if definition is None:
        raise UnknownField(f"There is no field called {name!r}.")
    source = results.field(definition.source)
    if source is None or not source.values:
        raise UnknownField(
            f"{name!r} needs {definition.source}, which this stage did not write.")
    if location not in _locations(source.location):
        raise UnknownField(f"{name!r} cannot be shown per {location}.")

    if source.location == "nodes":
        table = {id: definition.derive(components) * definition.scale
                 for id, components in source.values.items()}
    else:
        # Derive at each integration point, then average. See the module docstring --
        # for q the other order is a different and wrong number.
        per_element = {
            element: _mean([definition.derive(point) for point in points]) * definition.scale
            for element, points in source.values.items() if points
        }
        table = per_element if location == "elements" else _to_nodes(per_element, mesh)

    ids = sorted(table)
    numbers = [table[id] for id in ids]
    return {
        "field": name,
        "label": definition.label,
        "unit": definition.unit,
        "location": location,
        "ids": ids,
        "values": numbers,
        "min": min(numbers) if numbers else 0.0,
        "max": max(numbers) if numbers else 0.0,
    }


DEFORM_SOURCES = ("TOTAL_DISPLACEMENT", "DISPLACEMENT")
"""What a deformed mesh is drawn with, in order of preference. Total first: the shape
of the model at this stage is the sum of everything that has happened to it, and the
per-phase increment is a different picture."""


def displacement(results: Results) -> dict:
    """The displacement vectors, for deforming a drawn mesh.

    A vector, not a scalar, so it does not come through `values` -- every entry in the
    catalogue derives one number, and this needs all three components. The scale is
    metres to metres, but it goes through `LENGTH_SCALE` anyway so that a project whose
    length unit ever stops being the deck's cannot leave this behind.
    """
    for name in DEFORM_SOURCES:
        field = results.field(name)
        if field is None or not field.values:
            continue
        ids = sorted(field.values)
        return {
            "source": name,
            "ids": ids,
            "values": [[c * LENGTH_SCALE for c in field.values[id][:3]] for id in ids],
        }
    return {"source": None, "ids": [], "values": []}


def at_node(results: Results, mesh: GidMesh, node: int) -> dict:
    """Every field this stage offers, at one node.

    One request rather than one per field, which is what makes `results at <node>`
    usable: the alternative is twenty-odd round trips to answer a question somebody
    asked because they want to check a number against a hand calculation.

    A field the node has no value for is reported as `None` rather than left out, so
    the answer is the same shape whatever node is asked about -- and so "this node is
    in a body that was excavated" is visible instead of looking like a short list.
    """
    if node not in mesh.nodes:
        raise UnknownField(f"This stage has no node {node}.")

    rows = []
    for group in catalogue(results):
        for entry in group["fields"]:
            location = "nodes"
            try:
                field = values(results, mesh, entry["name"], location)
            except UnknownField:
                continue
            found = dict(zip(field["ids"], field["values"])).get(node)
            rows.append({"group": group["name"], "field": entry["name"],
                         "label": entry["label"], "unit": entry["unit"],
                         "value": found})
    x, y, z = mesh.nodes[node]
    return {"node": node, "at": [x, y, z], "values": rows}


def _mean(numbers: list[float]) -> float:
    return sum(numbers) / len(numbers)


def _to_nodes(per_element: dict[int, float], mesh: GidMesh) -> dict[int, float]:
    """An element quantity spread onto the nodes, by averaging over the elements that
    touch each one.

    Nodal averaging, not a shape-function extrapolation, and named as such: it is what
    a contour plot needs and what most viewers do, and it is exact where the field is
    constant. A true extrapolation is available a different way -- the deck can ask
    Kratos for it with `GeoExtrapolateIntegrationPointValuesToNodesProcess`, which it
    already does for the wall -- and when it does, the result arrives as a *nodal*
    variable and never comes through here at all.

    A node no live element touches is left out rather than given a zero. Zero is a
    stress: a floor of them through an excavated pit would read as a real result.
    """
    total: dict[int, float] = {}
    count: dict[int, int] = {}
    for block in mesh.blocks:
        for element, conn in block.elements.items():
            value = per_element.get(element)
            if value is None:
                continue
            for node in conn:
                total[node] = total.get(node, 0.0) + value
                count[node] = count.get(node, 0) + 1
    return {node: total[node] / count[node] for node in total}
