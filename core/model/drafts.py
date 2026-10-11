"""What a new record starts as, the way the GUI starts it.

The GUI's dialogs fill in a new borehole, layer, soil or soil volume before the user
types anything: `App.addBorehole` copies its neighbour, the soil dialog's Add puts a
5 m layer under the stack, a new soil is a loose drained sand, the material library
offers six presets, and a 2D soil volume is an outline swept across the model. The
command line adds the same records without those dialogs, so the same starting points
live here, in Python. The numbers are copied from `frontend/js/property-sets.js` and
`frontend/js/material-library.js`, and `tests/test_draft_parity.py` holds the two to one
document so they cannot drift.

Nothing here edits a project; `core.session` does that with what these return.
"""

from __future__ import annotations

from core.model import units
from core.model.schemas import Borehole, Material, Project, SoilLayer

SOIL_LAWS = {2: "GeoLinearElasticPlaneStrain2DLaw", 3: "GeoIncrementalLinearElastic3DLaw"}
"""The law a new soil starts with, by the project's dimension (`App.PropertySets.lawFor`)."""

SOIL_DEFAULTS_SI = {
    "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 1.0e7,
    "POISSON_RATIO": 0.3, "DENSITY_SOLID": 17000 / 9.81, "POROSITY": 0.0,
    "PERMEABILITY_XX": 1 / 86400, "GEO_COHESION": 0.0, "GEO_FRICTION_ANGLE": 30.0,
}
"""A new soil: a loose drained sand, in SI (`App.PropertySets.KINDS.soil.defaults`).
Porosity 0, as in Kratos' reference, so the soil weighs DENSITY_SOLID g -- 17 kN/m3 --
above and below the water alike."""

SOIL_COLOR = "#9aa7b4"
"""The colour a new material gets (`App.newMaterialDefaults`)."""

LAYER_THICKNESS = 5.0
"""How thick the soil dialog's Add makes a new layer, in metres."""

BOREHOLE_SPACING = 10.0
"""How far past the last borehole `App.addBorehole` puts a new one, in metres."""

LIBRARY = [
    {"id": "m1", "name": "Fill", "color": "#d8c48a", "r_inter": 0.70,
     "interface_permeability": "Neutral",
     "variables": {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 1.5e7,
                   "POISSON_RATIO": 0.30, "DENSITY_SOLID": 17000 / 9.81,
                   "PERMEABILITY_XX": 1.0 / 86400, "POROSITY": 0.0, "GEO_COHESION": 1000,
                   "GEO_FRICTION_ANGLE": 30.0}},
    {"id": "m2", "name": "Sand, loose", "color": "#c4a86a", "r_inter": 0.70,
     "interface_permeability": "Neutral",
     "variables": {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 2.5e7,
                   "POISSON_RATIO": 0.28, "DENSITY_SOLID": 18000 / 9.81,
                   "PERMEABILITY_XX": 1.5 / 86400, "POROSITY": 0.0, "GEO_COHESION": 500,
                   "GEO_FRICTION_ANGLE": 32.0}},
    {"id": "m3", "name": "Clay, soft", "color": "#8fa86b", "r_inter": 0.50,
     "interface_permeability": "Impermeable",
     "variables": {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED", "YOUNG_MODULUS": 4.0e6,
                   "POISSON_RATIO": 0.35, "DENSITY_SOLID": 15000 / 9.81,
                   "PERMEABILITY_XX": 0.0001 / 86400, "POROSITY": 0.0,
                   "GEO_COHESION": 5000, "GEO_FRICTION_ANGLE": 22.0}},
    {"id": "m4", "name": "Clay, stiff", "color": "#6f8fa8", "r_inter": 0.55,
     "interface_permeability": "Impermeable",
     "variables": {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED", "YOUNG_MODULUS": 1.2e7,
                   "POISSON_RATIO": 0.33, "DENSITY_SOLID": 17500 / 9.81,
                   "PERMEABILITY_XX": 0.0005 / 86400, "POROSITY": 0.0,
                   "GEO_COHESION": 15000, "GEO_FRICTION_ANGLE": 25.0}},
    {"id": "m5", "name": "Sand, dense", "color": "#b08a6a", "r_inter": 0.75,
     "interface_permeability": "Neutral",
     "variables": {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 4.5e7,
                   "POISSON_RATIO": 0.25, "DENSITY_SOLID": 19000 / 9.81,
                   "PERMEABILITY_XX": 5.0 / 86400, "POROSITY": 0.0, "GEO_COHESION": 0,
                   "GEO_FRICTION_ANGLE": 36.0}},
    {"id": "m6", "name": "Bedrock", "color": "#8d8d99", "r_inter": 1.00,
     "interface_permeability": "Impermeable",
     "variables": {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 2.0e9,
                   "POISSON_RATIO": 0.20, "DENSITY_SOLID": 24000 / 9.81,
                   "PERMEABILITY_XX": 0.0, "POROSITY": 0.0}},
]
"""The material library's soils (`App.MaterialLibrary`), in SI. A preset is added in the
project's own unit system."""


class DraftError(ValueError):
    """A new record that cannot be started as asked -- a preset that is not there."""


def preset(preset_id: str) -> dict:
    """The library preset `preset_id`, as a copy."""
    return _library_preset(preset_id)


def _library_preset(preset_id: str) -> dict:
    for entry in LIBRARY:
        if entry["id"] == preset_id:
            return {**entry, "variables": dict(entry["variables"])}
    raise DraftError(f"there is no library preset {preset_id!r}; there are: "
                     + ", ".join(entry["id"] for entry in LIBRARY))


def soil(project: Project, id: str, *, name: str | None = None, preset: str | None = None,
         color: str | None = None, law: str | None = None) -> tuple[Material, list[str]]:
    """A new soil for `project`: the default sand, or the library preset `preset`, with
    the law of the project's dimension and its variables in the project's units.

    Returns the material and what the unit conversion had to say about it.
    """
    start = _library_preset(preset) if preset is not None else None
    variables_si = start["variables"] if start else dict(SOIL_DEFAULTS_SI)
    variables, notes = units.convert_variables(variables_si, "SI", project.unit_system)
    material = Material(
        id=id,
        name=name if name is not None else (start["name"] if start else id),
        color=color if color is not None else (start["color"] if start else SOIL_COLOR),
        constitutive_law=law or SOIL_LAWS[project.dimension],
        variables=variables,
        **({"r_inter": start["r_inter"],
            "interface_permeability": start["interface_permeability"]} if start else {}),
    )
    return material, notes


def borehole(project: Project, *, id: str | None = None, name: str | None = None,
             x: float | None = None, y: float | None = None, head: float | None = None,
             water: float | None = None) -> Borehole:
    """A new borehole, starting from its neighbour as `App.addBorehole` does: 10 m past
    the last one, at its plan y, with its ground and water levels."""
    last = project.boreholes[-1] if project.boreholes else None
    taken = [b.id for b in project.boreholes]
    return Borehole(
        id=id if id is not None else free_id(taken, "bh"),
        name=name if name is not None else f"BH-{len(project.boreholes) + 1}",
        x=x if x is not None else (last.x + BOREHOLE_SPACING if last else 0.0),
        y=y if y is not None else (last.y if last else 0.0),
        head=head if head is not None else (last.head if last else project.domain.y_top),
        water=water if water is not None else (last.water if last else project.domain.y_top),
    )


def layer(project: Project, id: str, material: str, *, name: str | None = None,
          bottom: float | None = None, thickness: float | None = None) -> SoilLayer:
    """A new layer under the stack: its top is the last layer's bottom -- the ground, at
    each borehole, for the first -- and its bottom is `bottom` everywhere, or `thickness`
    below its top (5 m, as the soil dialog's Add makes it)."""
    last = project.layers[-1] if project.layers else None
    tops = {b.id: (last.bots[b.id] if last else b.head) for b in project.boreholes}
    if bottom is not None:
        bots = {bh: bottom for bh in tops}
    else:
        depth = LAYER_THICKNESS if thickness is None else thickness
        bots = {bh: top - depth for bh, top in tops.items()}
    return SoilLayer(id=id, name=name if name is not None else id, mat=material,
                     tops=tops, bots=bots)


def section_prism(project: Project, points: list[tuple[float, float]]) -> dict:
    """The recipe for a 2D soil volume: the outline `points`, in the section's x-y plane,
    swept along z across the whole domain (`soil-volume-dialog.js` `prismFor`).

    A plane-strain body runs forever out of plane; sweeping it across the domain is the
    honest encoding of that -- every section plane cuts it, and in 3D it spans the model
    rather than being a slab of some arbitrary thickness.
    """
    z0, z1 = project.domain.z0, project.domain.z1
    return {"kind": "polygon_extrude",
            "vertices": [[x, y, z0] for x, y in points],
            "extrusion": [0, 0, z1 - z0]}


def free_id(taken: list[str], prefix: str) -> str:
    """`prefix` and the first number from 1 that no id in `taken` has."""
    number = 1
    while f"{prefix}{number}" in taken:
        number += 1
    return f"{prefix}{number}"
