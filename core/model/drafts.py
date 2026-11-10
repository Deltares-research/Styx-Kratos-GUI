"""What a new record starts as, the way the GUI starts it.

The GUI's dialogs fill in a new layer, soil, soil volume or structure before the user
types anything: the soil dialog's Add puts a 5 m layer under the stack, a new soil is a loose drained sand, the material library
offers six presets, a 2D soil volume is an outline swept across the model, and a new
sheet pile, wall, member, anchor, interface or load is put where the Structure mode's
tools put one, with the section they give it. The
command line adds the same records without those dialogs, so the same starting points
live here, in Python. The numbers are copied from `frontend/js/property-sets.js` and
`frontend/js/material-library.js` and the Structure mode's modules, and
`tests/test_draft_parity.py` holds the two to one document so they cannot drift.

Nothing here edits a project; `core.session` does that with what these return.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from core.model import polylines, soil_models, units
from core.model.schemas import (Anchor, AnchorSection, BeamSection, Beam, Interface,
                                InterfaceSection, Line, LineLoad, Material, Member, NormalLoad,
                                Panel,
                                PanelSection, PointLoad, Project, SoilLayer, SpaceAnchor,
                                SeepageCondition, SurfaceLoad, WaterPressureCondition)
from core.model.schemas import (FACE_NORMALS, ConditionTarget, DisplacementCondition, Face,
                                PressureType, standard_conditions as standard_set)

SOIL_LAWS = dict(soil_models.MODELS[soil_models.LINEAR_ELASTIC].laws)
"""The law a new soil starts with, by the project's dimension (`App.PropertySets.lawFor`)."""

SOIL_DEFAULTS_SI = soil_models.defaults_si(soil_models.LINEAR_ELASTIC)
"""A complete soil: a loose drained sand, in SI (`App.PropertySets.KINDS.soil.defaults`),
the linear elastic model's defaults (`core/model/soil_models.py`). Porosity 0, as in
Kratos' reference, so the soil weighs DENSITY_SOLID g -- 17 kN/m3 -- above and below the
water alike. What the GUI gives a layer that has no soil to be of; a soil the user
creates starts blank (`soil`)."""

LAYER_THICKNESS = 5.0
"""How thick the soil dialog's Add makes a new layer, in metres."""

PER_M_PER_DAY = soil_models.PERMEABILITY_SI
"""The intrinsic permeability, m2, of a soil that conducts water at 1 m/day."""

LIBRARY: list[dict[str, Any]] = [
    {"id": "m1", "model": "mohr_coulomb", "name": "Fill", "color": "#d8c48a", "r_inter": 0.70,
     "interface_permeability": "Neutral",
     "variables": {"GEO_DRAINAGE_TYPE": "DRAINED", "YOUNG_MODULUS": 1.5e7,
                   "POISSON_RATIO": 0.30, "DENSITY_SOLID": 17000 / 9.81,
                   "PERMEABILITY_XX": 1.0 * PER_M_PER_DAY, "POROSITY": 0.0, "GEO_COHESION": 1000,
                   "GEO_FRICTION_ANGLE": 30.0}},
    {"id": "m2", "model": "mohr_coulomb", "name": "Sand, loose", "color": "#c4a86a", "r_inter": 0.70,
     "interface_permeability": "Neutral",
     "variables": {"GEO_DRAINAGE_TYPE": "DRAINED", "YOUNG_MODULUS": 2.5e7,
                   "POISSON_RATIO": 0.28, "DENSITY_SOLID": 18000 / 9.81,
                   "PERMEABILITY_XX": 1.5 * PER_M_PER_DAY, "POROSITY": 0.0, "GEO_COHESION": 500,
                   "GEO_FRICTION_ANGLE": 32.0}},
    {"id": "m3", "model": "mohr_coulomb", "name": "Clay, soft", "color": "#8fa86b", "r_inter": 0.50,
     "interface_permeability": "Impermeable",
     "variables": {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED", "YOUNG_MODULUS": 4.0e6,
                   "POISSON_RATIO": 0.35, "DENSITY_SOLID": 15000 / 9.81,
                   "PERMEABILITY_XX": 0.0001 * PER_M_PER_DAY, "POROSITY": 0.0,
                   "GEO_COHESION": 5000, "GEO_FRICTION_ANGLE": 22.0}},
    {"id": "m4", "model": "mohr_coulomb", "name": "Clay, stiff", "color": "#6f8fa8", "r_inter": 0.55,
     "interface_permeability": "Impermeable",
     "variables": {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED", "YOUNG_MODULUS": 1.2e7,
                   "POISSON_RATIO": 0.33, "DENSITY_SOLID": 17500 / 9.81,
                   "PERMEABILITY_XX": 0.0005 * PER_M_PER_DAY, "POROSITY": 0.0,
                   "GEO_COHESION": 15000, "GEO_FRICTION_ANGLE": 25.0}},
    {"id": "m5", "model": "mohr_coulomb", "name": "Sand, dense", "color": "#b08a6a", "r_inter": 0.75,
     "interface_permeability": "Neutral",
     "variables": {"GEO_DRAINAGE_TYPE": "DRAINED", "YOUNG_MODULUS": 4.5e7,
                   "POISSON_RATIO": 0.25, "DENSITY_SOLID": 19000 / 9.81,
                   "PERMEABILITY_XX": 5.0 * PER_M_PER_DAY, "POROSITY": 0.0, "GEO_COHESION": 0,
                   "GEO_FRICTION_ANGLE": 36.0}},
    {"id": "m6", "model": "linear_elastic", "name": "Bedrock", "color": "#8d8d99", "r_inter": 1.00,
     "interface_permeability": "Impermeable",
     "variables": {"GEO_DRAINAGE_TYPE": "DRAINED", "YOUNG_MODULUS": 2.0e9,
                   "POISSON_RATIO": 0.20, "DENSITY_SOLID": 24000 / 9.81,
                   "PERMEABILITY_XX": 0.0, "POROSITY": 0.0}},
]
"""The material library's soils (`App.MaterialLibrary`), in SI. A preset is added in the
project's own unit system, as its soil model with that model's defaults for what it does
not give. A soil with a strength is a Mohr-Coulomb one: a linear elastic soil has none.
The permeabilities are intrinsic, the frozen demo's m/day conductivities times
`PER_M_PER_DAY`."""


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
         color: str | None = None, law: str | None = None,
         model: str | None = None) -> tuple[Material, list[str]]:
    """A new soil for `project`: the blank soil the material window's **Create soil**
    makes (`soil_models.blank_si`), or the library preset `preset`, with the law of the
    project's dimension and its variables in the project's units, and a colour no soil
    of `project` has (`soil_models.fresh_color`): the preset's own while it is free.

    `model` (`core/model/soil_models.py`) makes it that soil model instead of linear
    elastic: its law, and what choosing it in the window fills in (`fill_choice`) -- for
    a blank soil, nothing the law must have, which stays the user's to type; for a
    preset, its defaults for what the preset lacks. `law` names any other law, written
    as typed.

    Returns the material and what the unit conversion and the model had to say about it.
    """
    if model is not None and law is not None:
        raise DraftError("give a soil model or a law, not both")
    if model is not None and model not in soil_models.MODELS:
        raise DraftError(f"there is no soil model {model!r}; there are: "
                         + ", ".join(soil_models.MODELS))
    start = _library_preset(preset) if preset is not None else None
    if start is not None and model is None and law is None:
        model = start["model"]
    chosen = soil_models.law(model, project.dimension) if model is not None else (
        law or SOIL_LAWS[project.dimension])
    filled: list[str] = []
    if start is not None:
        variables_si = {name: value for name, value in start["variables"].items()
                        if name not in soil_models.unread(chosen, start["variables"])}
        if model is not None:
            # What the model lists that the preset does not give, it fills -- quietly
            # for the preset's own model, which is how a preset is made.
            filled = soil_models.fill(None, {}, chosen, variables_si, "SI",
                                      flow=reads_flow(project))
            if model == start["model"]:
                filled = []
    else:
        # Created as the window creates it, then made `model` as the window's list does.
        blank_law = soil_models.law(soil_models.LINEAR_ELASTIC, project.dimension)
        variables_si = soil_models.blank_si()
        if model is not None and model != soil_models.LINEAR_ELASTIC:
            filled = soil_models.fill_choice(blank_law, soil_models.blank_si(), chosen,
                                             variables_si, "SI", flow=reads_flow(project))
    variables, notes = units.convert_variables(variables_si, "SI", project.unit_system)
    note = soil_models.filled_note(model, filled) if model is not None else None
    if note:
        notes.append(note)
    material = Material(
        id=id,
        name=name if name is not None else (start["name"] if start else id),
        color=color if color is not None else soil_models.fresh_color(
            [m.color for m in project.materials], start["color"] if start else None),
        constitutive_law=chosen,
        variables=variables,
        **({"r_inter": start["r_inter"],
            "interface_permeability": start["interface_permeability"]} if start else {}),
    )
    return material, notes


def reads_flow(project: Project) -> bool:
    """Whether every soil's flow parameters are read: the project is a groundwater flow
    calculation. A mix of flow and deformation stages, which the export refuses, is not
    one."""
    from core.model import stages
    try:
        return stages.groundwater_flow(project)
    except stages.StageError:
        return False


def layer(project: Project, id: str, material: str, *, name: str | None = None,
          bottom: float | None = None, thickness: float | None = None) -> SoilLayer:
    """A new layer under the stack: its top is the last layer's bottom -- the top of the
    domain for the first -- and its bottom is `bottom`, or `thickness` below its top
    (5 m, as the soil dialog's Add makes it)."""
    top = project.layers[-1].bottom if project.layers else project.domain.y_top
    if bottom is None:
        bottom = top - (LAYER_THICKNESS if thickness is None else thickness)
    return SoilLayer(id=id, name=name if name is not None else id, mat=material,
                     top=top, bottom=bottom)


def section_prism(project: Project, points: Sequence[tuple[float, ...]]) -> dict:
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


# ── Structures ──────────────────────────────────────────────────────────────
#
# What the Structure mode's tools start a new one as: `beams.js` (sheet piles, walls,
# members), `anchors.js`, `interfaces.js`, `loads.js` and `normal-loads.js`, each its
# `draft` and the default section its `sectionsFor` adds. The arithmetic is written as
# the JavaScript writes it, operation for operation, so the two give the same numbers
# and not merely close ones; `tests/test_draft_parity.py` runs both on the same projects.

SECTION_DEFAULTS_SI: dict[str, dict[str, Any]] = {
    "beam": {"name": "Sheet pile section", "spacing": 1.0,
             "constitutive_law": "TimoshenkoBeamElasticConstitutiveLaw",
             # An AZ 26-700 sheet pile, per metre run.
             "variables": {"YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.3,
                           "DENSITY": 7850.0, "CROSS_AREA": 0.0198, "I33": 5.52e-4}},
    "panel": {"name": "Wall section", "constitutive_law": "LinearElasticPlaneStress2DLaw",
              "variables": {"YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.3,
                            "DENSITY": 7850.0, "THICKNESS": 0.4}},
    "anchor": {"name": "Anchor tendon", "spacing": 2.5, "tension_limit": 900000.0,
               "compression_limit": None, "constitutive_law": "TrussConstitutiveLaw",
               # A four-strand tendon, per anchor.
               "variables": {"YOUNG_MODULUS": 1.95e11, "CROSS_AREA": 0.0006,
                             "DENSITY": 7850.0}},
    "interface": {"name": "Interface", "r_inter": 0.7, "virtual_thickness": 0.01,
                  "permeability": "Neutral",
                  "constitutive_law": "GeoIncrementalLinearElasticInterfaceLaw",
                  "variables": {}},
}
"""A new section of each kind, in SI (`App.Beams.defaultSection`, `defaultPanelSection`,
`App.Anchors.defaultSection`, `App.Interfaces.defaultSection`). The tendon's working
limit is a force and is stated in the project's force unit; a new interface section
reduces the project's first soil."""

SECTION_KINDS = {"beam": BeamSection, "panel": PanelSection, "anchor": AnchorSection,
                 "interface": InterfaceSection}
SECTION_FIELDS = {"beam": "beam_sections", "panel": "panel_sections",
                  "anchor": "anchor_sections", "interface": "interface_sections"}
"""The project list each kind of section is kept in."""

FIRST_SECTION = {"beam": "beamsection_1", "panel": "panelsection_1", "anchor": "tendon_1"}
"""The id a structure's section takes when the project has none of its kind yet; an
interface's is the first free `interfacesection_<n>`."""

SNAP_DISTANCE = 1.0
"""How far, in metres, an anchor head may be off the structure it is snapped onto."""

ANCHOR_LENGTH = 10.0
ANCHOR_RAKE = 35.0
"""A new anchor: 10 m, raking back and down at 35 degrees -- the usual ground anchor."""

LOAD_SI = 20000.0
"""A new load: 20 kN down -- per point, per metre or per square metre -- in SI."""


def section(project: Project, kind: str, id: str, *, name: str | None = None):
    """A new section of `kind` (beam, panel, anchor or interface) for `project`, with its
    variables in the project's units."""
    if kind not in SECTION_DEFAULTS_SI:
        raise DraftError(f"there is no section kind {kind!r}; there are: "
                         + ", ".join(SECTION_DEFAULTS_SI))
    start = SECTION_DEFAULTS_SI[kind]
    variables, _ = units.convert_variables(start["variables"], "SI", project.unit_system)
    fields = {key: value for key, value in start.items() if key != "variables"}
    if kind == "anchor":
        fields["tension_limit"] = units.from_si(start["tension_limit"], units.FORCE,
                                                project.unit_system)
    if kind == "interface":
        fields["material"] = project.materials[0].id if project.materials else None
    if name is not None:
        fields["name"] = name
    return SECTION_KINDS[kind](id=id, **fields, variables=variables, tables={})


def section_kind(record) -> str | None:
    """The kind of section `record` is built with, or None for one that has none."""
    if isinstance(record, Panel):
        return "panel"
    if isinstance(record, (Beam, Member)):
        return "beam"
    if isinstance(record, (Anchor, SpaceAnchor)):
        return "anchor"
    if isinstance(record, Interface):
        return "interface"
    return None


def section_for(project: Project, record):
    """The default section `record` needs saved with it, when its project has no section
    by that id -- what each tool's `sectionsFor` adds -- or None when it has one."""
    kind = section_kind(record)
    if kind is None:
        return None
    if any(s.id == record.section for s in getattr(project, SECTION_FIELDS[kind])):
        return None
    return section(project, kind, record.section)


def _first_section(project: Project, kind: str) -> str:
    library = getattr(project, SECTION_FIELDS[kind])
    if library:
        return library[0].id
    if kind == "interface":
        return free_id([s.id for s in library], "interfacesection_")
    return FIRST_SECTION[kind]


def _named(id: str | None, taken: list[str], prefix: str, noun: str) -> tuple[str, str]:
    """An id and the name that goes with it: `Sheet pile 3` for the free `beam_3`, and
    the id itself for one that was given."""
    if id is not None:
        return id, id
    new = free_id(taken, prefix)
    return new, f"{noun} {new[len(prefix):]}"


def _middle(project: Project) -> list[tuple[float, float]]:
    """Down the middle of the section to half its depth: where each tool puts a new line
    for the user to move."""
    d = project.domain
    x = d.x0 + (d.x1 - d.x0) * 0.5
    return [(x, d.y_top), (x, d.y_top - (d.y_top - d.y_bottom) * 0.5)]


def _centre(project: Project) -> tuple[float, float]:
    """The middle of the section: where a new point goes for the user to move."""
    d = project.domain
    return (d.x0 + (d.x1 - d.x0) * 0.5, d.y_bottom + (d.y_top - d.y_bottom) * 0.5)


def _finite(points, message: str) -> None:
    if not all(math.isfinite(value) for point in points for value in point):
        raise DraftError(message)


def _no_repeats(points, noun: str) -> None:
    for first, second in zip(points, points[1:]):
        if tuple(first) == tuple(second):
            raise DraftError(f"A {noun} cannot repeat the same point twice.")


def unavailable(project: Project, kind: str) -> str:
    """Why a structure of `kind` cannot be made in `project` (`App.Beams.unavailableMessage`)."""
    if kind == "beam":
        return ("Sheet piles are created in the 2D x-y section." if project.dimension == 2
                else "A sheet pile is a 2D section object; switch to 2D, or create a wall "
                     "instead.")
    if kind == "panel":
        return "Wall panels are created in the 3D model; switch to 3D, or create a sheet pile."
    return "Members are created in the 3D model; switch to 3D, or create a sheet pile."


def sheet_pile(project: Project, points=None, *, id: str | None = None,
               name: str | None = None, section: str | None = None) -> Beam:
    """A new 2D sheet pile along `points`, or down the middle of the section to half its
    depth (`App.Beams.draft`, `draftFromPoints`)."""
    if project.dimension != 2:
        raise DraftError(unavailable(project, "beam"))
    points = _middle(project) if points is None else points
    if len(points) < 2:
        raise DraftError("A sheet pile needs at least two points.")
    span = project.extent()
    flat = [(p[0], p[1]) for p in points]
    # Only the top is free: a pile may stand out above the ground (`Project`'s check).
    for x, y in flat:
        _finite([(x, y)], "Every pile coordinate must be a number.")
        if x < span.x0 or x > span.x1 or y < span.y_bottom:
            raise DraftError("The sheet pile must stay inside the model domain.")
    _no_repeats(flat, "sheet pile")
    if min(y for _, y in flat) >= span.y_top:
        raise DraftError("A sheet pile may stand out above the ground, but part of it "
                         "has to be in the soil.")
    id, default_name = _named(id, [b.id for b in project.beams], "beam_", "Sheet pile")
    return Beam(id=id, name=name or default_name, kind="beam",
                section=section or _first_section(project, "beam"), points=flat,
                active=True)


def wall(project: Project, footprint=None, *, id: str | None = None,
         name: str | None = None, section: str | None = None, top: float | None = None,
         toe: float | None = None) -> Panel:
    """A new 3D wall: a plan footprint swept from the ground to half the depth, by
    default across the middle of the site a quarter in from either edge
    (`App.Beams.draftPanel`)."""
    if project.dimension == 2:
        raise DraftError(unavailable(project, "panel"))
    d = project.domain
    if footprint is None:
        x = d.x0 + (d.x1 - d.x0) * 0.5
        footprint = [(x, d.z0 + (d.z1 - d.z0) * 0.25), (x, d.z1 - (d.z1 - d.z0) * 0.25)]
    plan = [(p[0], p[1]) for p in footprint]
    if len(plan) < 2:
        raise DraftError("A wall needs at least two points.")
    for x, z in plan:
        _finite([(x, z)], "Every wall coordinate must be a number.")
        if x < d.x0 or x > d.x1 or z < d.z0 or z > d.z1:
            raise DraftError("The wall must stay inside the model domain.")
    id, default_name = _named(id, [b.id for b in project.beams], "panel_", "Wall")
    return Panel(id=id, name=name or default_name, kind="panel",
                 section=section or _first_section(project, "panel"), footprint=plan,
                 y_top=d.y_top if top is None else top,
                 y_toe=d.y_top - (d.y_top - d.y_bottom) * 0.5 if toe is None else toe,
                 active=True)


def member(project: Project, points=None, *, id: str | None = None,
           name: str | None = None, section: str | None = None) -> Member:
    """A new 3D member along `points`, or standing vertical in the middle of the site
    from the ground to half the depth (`App.Beams.draftMember`)."""
    if project.dimension == 2:
        raise DraftError(unavailable(project, "member"))
    d = project.domain
    if points is None:
        x = d.x0 + (d.x1 - d.x0) * 0.5
        z = d.z0 + (d.z1 - d.z0) * 0.5
        points = [(x, d.y_top, z), (x, d.y_top - (d.y_top - d.y_bottom) * 0.5, z)]
    space = [(p[0], p[1], p[2]) for p in points]
    if len(space) < 2:
        raise DraftError("A member needs at least two points.")
    span = project.extent()
    for x, y, z in space:
        _finite([(x, y, z)], "Every member coordinate must be a number.")
        if (x < span.x0 or x > span.x1 or y < span.y_bottom or y > span.y_top
                or z < span.z0 or z > span.z1):
            raise DraftError("The member must stay inside the model domain.")
    id, default_name = _named(id, [b.id for b in project.beams], "member_", "Member")
    return Member(id=id, name=name or default_name, kind="member",
                  section=section or _first_section(project, "beam"), points=space,
                  active=True)


# Anchors

def live_piles(project: Project) -> list:
    """What an anchor may hang from in `project`: a live sheet pile in a section, a live
    wall or member in the solid model (`App.Anchors.livePiles`)."""
    kinds = ("beam",) if project.dimension == 2 else ("panel", "member")
    return [b for b in project.beams if b.active and b.kind in kinds]


def _nearest_on_polyline(points, point) -> tuple[list[float], float] | None:
    best = None
    for a, b in zip(points, points[1:]):
        delta = [b[axis] - a[axis] for axis in range(len(a))]
        length_squared = 0.0
        for d in delta:
            length_squared = length_squared + d * d
        if not length_squared:
            continue
        t = 0.0
        for axis in range(len(a)):
            t = t + (point[axis] - a[axis]) * delta[axis]
        t = max(0.0, min(1.0, t / length_squared))
        on = [a[axis] + t * delta[axis] for axis in range(len(a))]
        away = 0.0
        for axis in range(len(a)):
            away = away + (point[axis] - on[axis]) * (point[axis] - on[axis])
        away = math.sqrt(away)
        if best is None or away < best[1]:
            best = (on, away)
    return best


def _nearest_on_panel(panel: Panel, point) -> tuple[list[float], float] | None:
    plan = _nearest_on_polyline(panel.footprint, (point[0], point[2]))
    if plan is None:
        return None
    y = max(panel.y_toe, min(panel.y_top, point[1]))
    return [plan[0][0], y, plan[0][1]], math.hypot(plan[1], point[1] - y)


def nearest_on_pile(project: Project, point) -> tuple[list[float], float] | None:
    """The closest point on any structure an anchor may hang from, and how far away it
    is (`App.Anchors.nearestOnPile`)."""
    best = None
    for beam in live_piles(project):
        found = (_nearest_on_panel(beam, point) if isinstance(beam, Panel)
                 else _nearest_on_polyline(beam.points, point))
        if found is not None and (best is None or found[1] < best[1]):
            best = found
    return best


def _round(value: float) -> float:
    """To the micrometre, as JavaScript's `Math.round(value * 1e6) / 1e6`: halves
    upwards, not to even."""
    return math.floor(value * 1e6 + 0.5) / 1e6


def anchor_head(project: Project, point) -> tuple[float, ...]:
    """`point` snapped onto the nearest structure an anchor may hang from, refused when
    that is more than `SNAP_DISTANCE` away: the head becomes a node of that structure."""
    snapped = nearest_on_pile(project, point)
    if snapped is None or snapped[1] > SNAP_DISTANCE:
        raise DraftError("The anchor head must be placed on a wall or a member."
                         if project.dimension != 2
                         else "The anchor head must be placed on a sheet pile.")
    return tuple(_round(value) for value in snapped[0])


def _no_pile(project: Project) -> str:
    if project.dimension != 2:
        return "An anchor hangs from a wall or a member; create one first."
    return "An anchor hangs from a sheet pile; create one first."


def _raked(project: Project, head) -> list[float]:
    """The tail of a new anchor from `head`: back and down into the longer side of the
    domain, kept inside it."""
    d = project.domain
    radians = ANCHOR_RAKE * math.pi / 180
    into = 1 if (d.x1 - head[0]) >= (head[0] - d.x0) else -1
    tail = [head[0] + into * ANCHOR_LENGTH * math.cos(radians),
            head[1] - ANCHOR_LENGTH * math.sin(radians), *head[2:]]
    tail[0] = max(d.x0, min(d.x1, tail[0]))
    tail[1] = max(d.y_bottom, min(d.y_top, tail[1]))
    return tail


def _default_head(project: Project) -> list[float]:
    """A quarter of the way down the first structure an anchor may hang from -- halfway
    along a wall's footprint."""
    pile = live_piles(project)[0]
    if isinstance(pile, Panel):
        first, last = pile.footprint[0], pile.footprint[-1]
        return [(first[0] + last[0]) / 2, pile.y_top + (pile.y_toe - pile.y_top) * 0.25,
                (first[1] + last[1]) / 2]
    top, toe = pile.points[0], pile.points[-1]
    return [top[0], top[1] + (toe[1] - top[1]) * 0.25, *top[2:]]


def anchor(project: Project, head=None, tail=None, *, id: str | None = None,
           name: str | None = None, section: str | None = None,
           prestress: float = 0.0):
    """A new anchor from `head`, snapped onto the nearest structure, to `tail`
    (`App.Anchors.draft`, `draftFromPoints`). Without a head it hangs a quarter of the way
    down the first structure; without a tail it rakes back and down from its head."""
    if not live_piles(project):
        raise DraftError(_no_pile(project))
    width = 2 if project.dimension == 2 else 3
    head = _default_head(project) if head is None else list(head)
    tail = _raked(project, head) if tail is None else list(tail)
    if len(head) != width or len(tail) != width:
        raise DraftError(f"An anchor's head and tail are {width} coordinates each here.")
    _finite([head, tail], "Every anchor coordinate must be a number.")
    snapped = anchor_head(project, head)
    span = project.extent()
    # In a section the top is free (`Project`'s check): a strut from the part of a pile
    # above the ground ends at a fixed point in the air.
    inside = (span.x0 <= tail[0] <= span.x1 and span.y_bottom <= tail[1]
              and (width == 2 or (tail[1] <= span.y_top and span.z0 <= tail[2] <= span.z1)))
    if not inside:
        raise DraftError("The anchor must stay inside the model domain.")
    if all(value == tail[axis] for axis, value in enumerate(snapped)):
        raise DraftError("An anchor must have a non-zero length.")
    id, default_name = _named(id, [a.id for a in project.anchors], "anchor_", "Anchor")
    # Any: the one call below builds either, so its kind and coordinates are the
    # width's own -- which mypy cannot follow through the conditional.
    record: Any = SpaceAnchor if width == 3 else Anchor
    return record(id=id, name=name or default_name,
                  kind="anchor3d" if width == 3 else "anchor",
                  section=section or _first_section(project, "anchor"),
                  head=snapped, tail=tuple(_round(value) for value in tail),
                  prestress=prestress, active=True)


# Interfaces and normal loads -- plane strain only

STRETCH_SNAP = 0.5
"""How far, in metres, a typed From or To may be off the pile: it is moved onto the
pile, and refused further away (`App.Interfaces.snap`)."""


def stretch_point(pile: Beam, point, label: str) -> tuple[float, float]:
    """`point` moved onto `pile`, to the micrometre, refused when it is more than
    `STRETCH_SNAP` away. `label` is From or To, which the refusal names."""
    _finite([point], f"{label} must be two numbers.")
    on, away, _ = polylines.nearest(pile.points, point)
    if away > STRETCH_SNAP:
        raise DraftError(f"{label} is {away:.1f} m from {pile.name}; From and To are "
                         "points on the pile.")
    return (_round(on[0]), _round(on[1]))


def stretch(pile: Beam, start, end) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """From and To on `pile`, snapped (`stretch_point`); None when they are the pile's
    two ends, which is the whole pile."""
    points = (stretch_point(pile, start, "From"), stretch_point(pile, end, "To"))
    if points[0] == points[1]:
        raise DraftError(f"From and To are the same point on {pile.name}; the part of "
                         "the pile needs length.")
    ends = {tuple(pile.points[0]), tuple(pile.points[-1])}
    return None if set(points) == ends else points


def interface(project: Project, structure: str | None = None, points=None, *,
              side: str | None = None, id: str | None = None, name: str | None = None,
              section: str | None = None, stretch_from=None,
              stretch_to=None) -> Interface:
    """A new interface: along the sheet pile `structure`, or the first live one, on both
    sides -- the whole pile, or the part from `stretch_from` to `stretch_to`, snapped
    onto it; or, with `points` or no pile to follow, a free line -- down the middle of
    the section by default -- that detaches the soil on the left of the screen
    (`App.Interfaces.draft`)."""
    if project.dimension != 2:
        raise DraftError("An interface is a plane-strain object; switch to 2D to create one.")
    piles = [b for b in project.beams if b.active and b.kind == "beam"]
    pile = None
    if points is None:
        pile = next((b for b in piles if b.id == structure), None) if structure else (
            piles[0] if piles else None)
        if structure and pile is None:
            raise DraftError("An interface can only follow a live sheet pile.")
    part = None
    if stretch_from is not None or stretch_to is not None:
        if not isinstance(pile, Beam):
            raise DraftError("From and To are points on a sheet pile; an interface on its "
                             "own points runs its whole line.")
        part = stretch(pile, stretch_from if stretch_from is not None else pile.points[0],
                       stretch_to if stretch_to is not None else pile.points[-1])
    id, default_name = _named(id, [i.id for i in project.interfaces], "interface_",
                              "Interface")
    # `side` rides in the fields as a plain string: the record checks it is one of
    # its five.
    fields: dict[str, Any] = dict(id=id, name=name or default_name, kind="interface",
                                  section=section or _first_section(project, "interface"),
                                  active=True)
    if pile is not None:
        fields["side"] = side or "both"
        return Interface(**fields, structure=pile.id, points=None, stretch=part)
    fields["side"] = side or "left"
    line = _middle(project) if points is None else [(p[0], p[1]) for p in points]
    return Interface(**fields, structure=None, points=line, stretch=None)


def normal_load(project: Project, points=None, *, id: str | None = None,
                name: str | None = None, hydrostatic: bool = False,
                pressure: float = 0.0,
                reference_coordinate: float | None = None) -> NormalLoad:
    """A new normal load along `points`, or down the middle of the section: a uniform
    pressure, zero until it is given (`App.NormalLoads.draft`). Hydrostatic only when
    asked -- it derives the pressure from a water level and ignores the number: its own
    `reference_coordinate` when given, else the project's, copied into the record as a
    water pressure condition's is (`water_pressure_condition`)."""
    if project.dimension != 2:
        raise DraftError("A normal load is a plane-strain object; switch to 2D to create "
                         "one.")
    id, default_name = _named(id, [n.id for n in project.normal_loads], "normalload_",
                              "Normal load")
    line = _middle(project) if points is None else [(p[0], p[1]) for p in points]
    if hydrostatic and reference_coordinate is None and project.water is not None:
        reference_coordinate = project.water.y
    # Passed only when given, so a record that names no level reads as the GUI's draft
    # does, field for field (`tests/test_draft_parity.py` compares the fields set).
    level = {} if reference_coordinate is None else {
        "reference_coordinate": reference_coordinate}
    return NormalLoad(id=id, name=name or default_name, kind="normal", points=line,
                      fluid_pressure_type="Hydrostatic" if hydrostatic else "Uniform",
                      pressure=pressure, active=True, **level)


def line(project: Project, points=None, *, id: str | None = None,
         name: str | None = None) -> Line:
    """A new line along `points`, or across the middle of the section
    (`App.Lines.draft`). It is drawn in the 2D section; a solid model has it swept."""
    if project.dimension != 2:
        raise DraftError("A line is drawn in the 2D section; switch to 2D to create one.")
    id, default_name = _named(id, [each.id for each in project.lines], "line_", "Line")
    d = project.domain
    middle = (d.y_top + d.y_bottom) / 2
    drawn = ([(d.x0, middle), (d.x1, middle)] if points is None
             else [(p[0], p[1]) for p in points])
    return Line(id=id, name=name or default_name, points=drawn)


# Boundary conditions

def displacement_condition(
        project: Project, on: ConditionTarget, *, face: Face | None = None,
        part: str | None = None, points=None, fixed: Sequence[bool] | None = None,
        roller: bool = False, id: str | None = None,
        name: str | None = None) -> DisplacementCondition:
    """A new displacement condition on `on`: `"face"` with `face`, `"part"` with
    `part`, or `"line"` / `"point"` with `points` (down the middle of the section, or at
    its centre, when none are given). Fixed in x, y and z unless `fixed` says which.

    `roller=True` holds only the component normal to the target: a face's own normal
    (`schemas.FACE_NORMALS`), x for a vertical line and y for a horizontal one. Any other
    target has no one normal, and says so."""
    if on == "domain":
        raise DraftError("A displacement condition on the whole soil would hold the whole "
                         "model still; put it on a face, a part, a line or a point.")
    if on in ("line", "point") and project.dimension != 2:
        raise DraftError(f"A displacement {on} is drawn in the 2D section; switch to 2D "
                         "to create one, or put the condition on a face or a part.")
    drawn = None
    if on == "line":
        drawn = _middle(project) if points is None else [(p[0], p[1]) for p in points]
    elif on == "point":
        drawn = [_centre(project)] if points is None else [(p[0], p[1]) for p in points]
    if roller:
        held = [False, False, False]
        held[_normal(on, face, drawn)] = True
        fixed = held
    elif fixed is None:
        fixed = (True, True, True)
    if len(fixed) != 3:
        raise DraftError("A displacement condition holds x, y and z: give three values.")
    taken = [c.id for c in project.boundary_conditions]
    id, default_name = _named(id, taken, "displacement_", "Displacement")
    # Every field given, `kind` too, so the record reads as the GUI's draft does, field
    # for field (`tests/test_draft_parity.py` compares the fields set).
    return DisplacementCondition(
        id=id, name=name or default_name, kind="displacement", on=on, face=face,
        part=part, points=drawn, fixed=(bool(fixed[0]), bool(fixed[1]), bool(fixed[2])),
        active=True)


def _normal(on: str, face: str | None, points) -> int:
    """The axis a roller on this target holds."""
    if on == "face" and face in FACE_NORMALS:
        return FACE_NORMALS[face]
    if on == "line" and points:
        if all(abs(x - points[0][0]) < 1e-9 for x, _ in points):
            return 0
        if all(abs(y - points[0][1]) < 1e-9 for _, y in points):
            return 1
        raise DraftError("A roller holds the component normal to its line, and a sloping "
                         "line has no x or y normal; give the components it fixes.")
    raise DraftError(f"A roller on a {on} has no normal to hold; give the components it "
                     "fixes.")


def standard_conditions(
        project: Project) -> list[DisplacementCondition | WaterPressureCondition]:
    """The standard supports -- the bottom fixed, every side on rollers -- with ids no
    other condition of `project` has (`schemas.standard_conditions`)."""
    taken = [c.id for c in project.boundary_conditions]
    out: list[DisplacementCondition | WaterPressureCondition] = []
    for record in standard_set():
        id = record.id
        if id in taken:
            id, _ = _named(None, taken, f"{record.id}_", "")
        taken.append(id)
        out.append(DisplacementCondition(**{**record.model_dump(), "id": id}))
    return out


def water_pressure_condition(
        project: Project, on: ConditionTarget, *, face: Face | None = None,
        part: str | None = None, points=None, id: str | None = None,
        name: str | None = None, fluid_pressure_type: PressureType = "Hydrostatic",
        is_fixed: bool = True,
        value: float = 0.0, reference_coordinate: float | None = None,
        x_coordinates: Sequence[float] | None = None,
        y_coordinates: Sequence[float] | None = None,
        z_coordinates: Sequence[float] | None = None,
        pressure_tension_cut_off: float = 0.0) -> WaterPressureCondition:
    """A new water pressure condition on `on`: `"domain"` for the whole soil, `"face"`
    with `face`, `"part"` with `part`, or `"line"` / `"point"` with `points` (down the
    middle of the section, or at its centre, when none are given).

    A hydrostatic condition with no `reference_coordinate` takes the project's water
    level, copied into the record, so the record says what it is measured from; with no
    water level either, there is no level to give it. A line or a point is drawn in the
    2D section and nowhere else, as a normal load is."""
    if on in ("line", "point") and project.dimension != 2:
        raise DraftError(f"A water pressure {on} is drawn in the 2D section; switch to 2D "
                         "to create one, or put the condition on the whole soil, a face "
                         "or a part.")
    if fluid_pressure_type == "Hydrostatic" and reference_coordinate is None:
        if project.water is None:
            raise DraftError("A hydrostatic water pressure needs the level where its "
                             "pressure is zero: give its reference_coordinate. For a dry "
                             "model, add no water pressure condition, or a Uniform one "
                             "with value 0.")
        reference_coordinate = project.water.y
    taken = [c.id for c in project.boundary_conditions]
    id, default_name = _named(id, taken, "waterpressure_", "Water pressure")
    drawn = None
    if on == "line":
        drawn = _middle(project) if points is None else [(p[0], p[1]) for p in points]
    elif on == "point":
        drawn = [_centre(project)] if points is None else [(p[0], p[1]) for p in points]
    return WaterPressureCondition(
        id=id, name=name or default_name, kind="water_pressure", on=on, face=face,
        part=part, points=drawn,
        fluid_pressure_type=fluid_pressure_type, is_fixed=is_fixed, value=value,
        reference_coordinate=reference_coordinate,
        x_coordinates=None if x_coordinates is None else list(x_coordinates),
        y_coordinates=None if y_coordinates is None else list(y_coordinates),
        z_coordinates=None if z_coordinates is None else list(z_coordinates),
        pressure_tension_cut_off=pressure_tension_cut_off, active=True)


def seepage_condition(project: Project, on: ConditionTarget, *, face: Face | None = None,
                      points=None, id: str | None = None,
                      name: str | None = None) -> SeepageCondition:
    """A new seepage face on `on`: `"face"` with `face`, or `"line"` with `points` (down
    the right side of the section to half its depth when none are given: a seepage face
    is on the soil's outer boundary, so the middle of the section is no place for one)."""
    if on not in ("face", "line"):
        raise DraftError("A seepage face is on a face of the model, or on a line along the "
                         "soil's outer boundary.")
    if on == "line" and project.dimension != 2:
        raise DraftError("A seepage line is drawn in the 2D section; switch to 2D to "
                         "create one, or put the seepage face on a face.")
    drawn = None
    if on == "line":
        drawn = _right_side(project) if points is None else [(p[0], p[1]) for p in points]
    taken = [c.id for c in project.boundary_conditions]
    id, default_name = _named(id, taken, "seepage_", "Seepage face")
    return SeepageCondition(id=id, name=name or default_name, kind="seepage",
                            on="face" if on == "face" else "line", face=face, part=None,
                            points=drawn, active=True)


def _right_side(project: Project) -> list[tuple[float, float]]:
    """Down the right side of the section to half its depth: where a new seepage line
    goes for the user to move."""
    d = project.domain
    return [(d.x1, d.y_top), (d.x1, d.y_top - (d.y_top - d.y_bottom) * 0.5)]


# Loads

def _load_id(project: Project, id: str | None, prefix: str) -> tuple[str, str]:
    """`load_<n>` and `<Kind>Load_<n>` with the same number, as `loads.js` numbers them."""
    if id is not None:
        return id, id
    number = 1
    while f"load_{number}" in {load.id for load in project.loads}:
        number += 1
    return f"load_{number}", f"{prefix}_{number}"


def point_load(project: Project, at=None, *, id: str | None = None,
               name: str | None = None, components=None) -> PointLoad:
    """A new 2D point load at `at`, or on the ground in the middle of the section
    (`App.Loads.draftPoint`)."""
    d = project.domain
    at = ((d.x0 + d.x1) / 2, d.y_top) if at is None else at
    if project.dimension != 2 or len(at) != 2 or not all(map(math.isfinite, at)):
        raise DraftError("A 2D point load needs one finite x-y coordinate.")
    span = project.extent()
    if at[0] < span.x0 or at[0] > span.x1 or at[1] < span.y_bottom or at[1] > span.y_top:
        # Outside the model it may still be on a pile standing out above the ground,
        # snapped onto it the way an anchor head is.
        snapped = nearest_on_pile(project, at)
        if snapped is None or snapped[1] > SNAP_DISTANCE:
            raise DraftError("The point-load coordinate must stay inside the model "
                             "domain, or be on a sheet pile.")
        at = tuple(_round(value) for value in snapped[0])
    id, default_name = _load_id(project, id, "PointLoad")
    return PointLoad(id=id, name=name or default_name, kind="point", x=at[0], y=at[1],
                     thickness=0.25,
                     components=components or (0, -units.from_si(LOAD_SI, units.FORCE,
                                                                  project.unit_system)),
                     distribution="Uniform", active=True)


def line_load(project: Project, x=None, *, y: float | None = None, id: str | None = None,
              name: str | None = None, components=None) -> LineLoad:
    """A new 2D line load over `x` (from, to) -- the middle fifth of the section by
    default -- on the top of the model (`App.Loads.draftFromPoints`)."""
    if project.dimension != 2:
        raise DraftError("Point and line loads are available only in 2D mode.")
    d = project.domain
    if x is None:
        x = (d.x0 + (d.x1 - d.x0) * 0.4, d.x0 + (d.x1 - d.x0) * 0.6)
    x0, x1 = min(x[0], x[1]), max(x[0], x[1])
    if not x1 > x0:
        raise DraftError("The load must have a non-zero width.")
    span = project.extent()
    if x0 < span.x0 or x1 > span.x1:
        raise DraftError("The load interval must stay inside the model domain.")
    id, default_name = _load_id(project, id, "LineLoad")
    return LineLoad(id=id, name=name or default_name, kind="line", x0=x0, x1=x1,
                    y=span.y_top if y is None else y, thickness=0.15,
                    components=components or (0, -units.from_si(
                        LOAD_SI, units.LINE_FORCE, project.unit_system)),
                    distribution="Uniform", active=True)


def surface_load(project: Project, x=None, z=None, *, id: str | None = None,
                 name: str | None = None, components=None) -> SurfaceLoad:
    """A new 3D surface load over the footprint `x` by `z` (each from, to) -- the middle
    fifth of the site each way by default -- on the top of the model
    (`App.Loads.draftSurface`)."""
    if project.dimension != 3:
        raise DraftError("A surface load needs a 3D model domain.")
    d = project.domain
    dx, dz = d.x1 - d.x0, d.z1 - d.z0
    if x is None:
        x = (d.x0 + dx * 0.4, d.x0 + dx * 0.6)
    if z is None:
        z = (d.z0 + dz * 0.4, d.z0 + dz * 0.6)
    x0, x1 = min(x[0], x[1]), max(x[0], x[1])
    z0, z1 = min(z[0], z[1]), max(z[0], z[1])
    if not (x1 > x0 and z1 > z0):
        raise DraftError("The load must have a non-zero width.")
    if x0 < d.x0 or x1 > d.x1 or z0 < d.z0 or z1 > d.z1:
        raise DraftError("The load footprint must stay inside the model domain.")
    id, default_name = _load_id(project, id, "SurfaceLoad")
    return SurfaceLoad(id=id, name=name or default_name, kind="surface", x0=x0, x1=x1,
                       z0=z0, z1=z1, y=project.extent().y_top, thickness=0.15,
                       components=components or (0, -units.from_si(
                           LOAD_SI, units.STRESS, project.unit_system), 0),
                       distribution="Uniform", active=True)
