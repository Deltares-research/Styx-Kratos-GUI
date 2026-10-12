"""A structural member's results, as curves along it.

The deck asks Kratos' `json_output` process for one file per member per stage --
`<stage>__output_wall.json` (bending moment, shear force, normal force, displacement at
every wall node) and `<stage>__output_interface.json` (effective traction on one side of
the wall). These are the numbers a retaining-wall designer opens the program for, and
they are not in the GiD output at all for the interface (`plan/active/postprocessing-plan.md`
sec 0.3), so this reads them where they are.

What comes out is the plot Plaxis and Kratos' own staged-excavation validation both
draw: per stage, the quantity against the level y, node by node, toe to top. Kratos'
comparison figure is the model -- same quantities and the same sign, which
is Kratos' own and is not flipped to anybody else's convention. The numbers are the run's
own, in its unit system (`core/model/units.py`), and labelled for it rather than scaled.

Nothing here opens a file. `core.results.catalog` finds them and caches them; this turns text into
numbers and numbers into curves, so the tests can feed it three nodes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from core.model import units


class UnknownQuantity(ValueError):
    """A quantity this catalogue has no entry for, or one this member did not write."""


@dataclass(frozen=True)
class Quantity:
    name: str
    """What the command takes: `results plot wall M`."""
    label: str
    quantity: units.Quantity
    variable: str
    """The Kratos variable in the json_output file."""
    component: int | None
    """For a vector variable, which component; None for a scalar."""

    def unit(self, system: str = units.DEFAULT) -> str:
        return units.label(self.quantity, system)

    def summary(self, system: str = units.DEFAULT) -> dict:
        return {"name": self.name, "label": self.label, "unit": self.unit(system)}


QUANTITIES = (
    Quantity("M", "Bending moment", units.MOMENT_PER_LENGTH, "BENDING_MOMENT", None),
    Quantity("Q", "Shear force", units.LINE_FORCE, "SHEAR_FORCE", None),
    Quantity("N", "Normal force", units.LINE_FORCE, "AXIAL_FORCE", None),
    Quantity("ux", "Horizontal total displacement", units.LENGTH, "TOTAL_DISPLACEMENT_X", None),
    Quantity("uy", "Vertical total displacement", units.LENGTH, "TOTAL_DISPLACEMENT_Y", None),
    # The traction is in the interface's own axes: normal first, then shear. Kratos'
    # validation plots take exactly these two components.
    Quantity("tn", "Normal traction", units.STRESS, "GEO_EFFECTIVE_TRACTION_VECTOR", 0),
    Quantity("ts", "Shear traction", units.STRESS, "GEO_EFFECTIVE_TRACTION_VECTOR", 1),
)
"""Every quantity a member can be plotted for, in the order a menu offers them."""


def quantity(name: str) -> Quantity:
    for entry in QUANTITIES:
        if entry.name == name:
            return entry
    raise UnknownQuantity(f"No quantity called {name!r}. There is "
                          + ", ".join(entry.name for entry in QUANTITIES) + ".")


def member_name(filename: str, stage: str) -> str | None:
    """`7_Third_excavation__output_wall.json` -> `wall`, for the stage it belongs to.

    The deck names these `<stage>__output_<member>.json`. `output_` is dropped because
    every one has it; anything else after the stage is kept as it is, so a file written
    by a deck from elsewhere is still offered, under whatever it is called.
    """
    prefix, suffix = f"{stage}__", ".json"
    if not (filename.startswith(prefix) and filename.endswith(suffix)):
        return None
    name = filename[len(prefix):-len(suffix)]
    if name.startswith("output_"):
        name = name[len("output_"):]
    return name or None


def read_output(text: str) -> dict[int, dict[str, object]]:
    """{node id: {variable: value}} from one json_output file.

    Each variable is a series, one value per time the process wrote; the last is the end
    of the stage, which is what a stage's plot shows. The deck asks for one write per
    stage, so it is usually also the only one.
    """
    payload = json.loads(text)
    out: dict[int, dict[str, object]] = {}
    for key, variables in payload.items():
        if not key.startswith("NODE_") or not isinstance(variables, dict):
            continue
        out[int(key[len("NODE_"):])] = {
            name: series[-1] for name, series in variables.items()
            if isinstance(series, list) and series}
    return out


def available(outputs: Iterable[dict[int, dict[str, object]]]) -> list[Quantity]:
    """The quantities these outputs carry, in catalogue order."""
    carried = {variable for output in outputs
               for variables in output.values() for variable in variables}
    return [entry for entry in QUANTITIES if entry.variable in carried]


def _value(raw: object, entry: Quantity) -> float | None:
    if entry.component is not None:
        if not isinstance(raw, list) or len(raw) <= entry.component:
            return None
        raw = raw[entry.component]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw)


def profile(output: dict[int, dict[str, object]],
            coordinates: dict[int, tuple[float, float, float]],
            entry: Quantity) -> dict:
    """One stage of one member: (value, y) per node, sorted by y, and its extremes.

    `coordinates` are the deck's -- undeformed -- which is what the level of a point on
    the wall means. A node without the variable, or without a position, is left out
    rather than drawn at zero: a gap in a curve is honest, a zero is a result.
    """
    rows = []
    for node, variables in output.items():
        if entry.variable not in variables or node not in coordinates:
            continue
        value = _value(variables[entry.variable], entry)
        if value is not None:
            rows.append((coordinates[node][1], value, node))
    rows.sort()
    # The two faces of a zero-thickness interface: a node on each at every level, with
    # the same traction written on both. One point, kept under the lower node id.
    rows = [row for at, row in enumerate(rows)
            if not (at and row[:2] == rows[at - 1][:2])]

    found = {"points": [[value, y] for y, value, _ in rows],
             "nodes": [node for _, _, node in rows],
             "min": None, "max": None}
    if rows:
        low = min(rows, key=lambda row: row[1])
        high = max(rows, key=lambda row: row[1])
        found["min"] = {"value": low[1], "y": low[0]}
        found["max"] = {"value": high[1], "y": high[0]}
    return found
