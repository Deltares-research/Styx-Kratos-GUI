"""The project schema — the single source of truth for the model.

Coordinates are X across, Y up and Z out of plane, metres, y = 0 at the ground
datum. A 2D model is the x-y plane at z = 0; a 3D model extrudes it along Z.

Units are the project's own (`Project.unit_system`, `core/model/units.py`): length in metres,
time in seconds, and force and mass in the system's units -- N and kg, or kN and t. Every
value a property set, load or pressure holds is in that system and goes into the deck as
it stands. Property sets hold what Kratos reads: a constitutive law name and a
`Variables` block under Kratos' own names (`KratosPropertySet`).

Part keys (`Project.part_keys`) are the contract with the frozen frontend: each one is a
`userData.key` on a picked mesh, an `obj:` on a model-tree node, and a key in
`App.OBJECT_PROPS`. gmsh physical group names must equal them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Literal

from pydantic import (BaseModel, Field, SerializerFunctionWrapHandler, computed_field,
                      field_validator, model_serializer, model_validator)

from core.model import migration, polylines, soil_models, solver, units

Hex = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Ident = Annotated[str, Field(min_length=1, max_length=64)]
PositiveSize = Annotated[float, Field(gt=0)]

ATTACHMENT_TOLERANCE = 1e-6
"""Metres. How close an anchor head must be to a sheet pile to count as on it."""

_LEVEL_TOLERANCE = 1e-9
"""Metres. Below this a layer and an excavation lift merely touch rather than overlap,
and no body lies between them -- the common case where a lift is dug exactly to a layer
boundary (`Project.soil_bodies`)."""


class Base(BaseModel):
    model_config = {"extra": "forbid"}

class CustomPart(Base):
    key: Ident
    label: str
    color: Hex = "#888888"
    source: Literal["import", "gui"]
    source_file: str | None = None
    recipe: dict | None = None
    imported_from: str | None = None
    """The CAD file an imported part was read from, absolute, when the importer knew it
    (`kratos-cli volume import`; a browser upload names only the file). A model script
    reads it again when the part's .brep is gone (`core.scripting.with_solids`)."""
    # A drawn or imported solid becomes *soil* once it is given a material: it then
    # carries the same strength/stiffness/permeability set as a stack layer and is
    # meshed as a soil body. Left unset, the part stays plain display geometry.
    mat: Ident | None = None
    bbox: tuple[float, float, float, float, float, float] | None = None
    """Where this part is, as (xmin, ymin, zmin, xmax, ymax, zmax) in metres.

    Measured by gmsh when the part is drawn or imported (`primitives.process_creation`,
    `cad_import`), and kept so `Project.extent` knows how far the model reaches without
    reopening every .brep. Optional: a project saved before this was recorded still
    loads, and simply contributes nothing to the extent."""


# ── Domain ──────────────────────────────────────────────────────────────────

class Domain(Base):
    x0: float
    x1: float
    z0: float
    z1: float
    y_top: float
    y_bottom: float

    @model_validator(mode="after")
    def _ordered(self) -> Domain:
        if self.x1 <= self.x0 or self.z1 <= self.z0 or self.y_top <= self.y_bottom:
            raise ValueError("domain extents must be strictly increasing (x0<x1, z0<z1, y_bottom<y_top)")
        return self

    @property
    def dx(self) -> float:
        return self.x1 - self.x0

    @property
    def dy(self) -> float:
        return self.y_top - self.y_bottom

    @property
    def dz(self) -> float:
        return self.z1 - self.z0

    @property
    def center(self) -> tuple[float, float, float]:
        return ((self.x0 + self.x1) / 2, (self.y_top + self.y_bottom) / 2,
                (self.z0 + self.z1) / 2)

    def contains_plan(self, x0: float, x1: float, z0: float, z1: float) -> bool:
        """Is this plan rectangle inside the box? Plan is x across, z out of plane."""
        return self.x0 <= x0 and x1 <= self.x1 and self.z0 <= z0 and z1 <= self.z1

    def contains(self, x: float, y: float, z: float) -> bool:
        """Is this point inside the model box? Closed, so a structure may sit on a face."""
        return (self.x0 <= x <= self.x1 and self.y_bottom <= y <= self.y_top
                and self.z0 <= z <= self.z1)


# ── Ground model ────────────────────────────────────────────────────────────

VariableName = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=96)]
VariableValue = float | int | bool | str | list[float] | list[list[float]]


def _finite(value: object) -> bool:
    if isinstance(value, (bool, str)):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_finite(v) for v in value)
    return True


SOIL_LAW_PAIRS = {law: (dim, model.laws[5 - dim])
                  for model in soil_models.MODELS.values()
                  for dim, law in model.laws.items()}
"""Soil laws that exist in one dimension only: law -> (its dimension, its counterpart),
one pair per soil model (`core/model/soil_models.py`). GeoMechanics registers no 3D
`GeoLinearElastic` law; its one 3D linear elastic soil law is the incremental one. A
project keeps such a law in step with its own dimension
(`Project._soil_laws_follow_the_dimension`), so what it shows is what it writes."""


class KratosPropertySet(Base):
    """What Kratos reads for one property set: a constitutive law and its `Variables`,
    exactly as `MaterialParameters.json` carries them, in the project's unit system.

    Written into the deck as they stand. The exporter adds only what is missing and can
    be derived (`core/kratos/materials.py`), and says so; it never rewrites a value the
    user gave. `tables` is Kratos' own `Tables` block, carried verbatim."""
    constitutive_law: str = Field(min_length=1)
    variables: dict[VariableName, VariableValue] = Field(default_factory=dict)
    tables: dict[str, Any] = Field(default_factory=dict)

    @field_validator("variables")
    @classmethod
    def _finite_values(cls, value: dict) -> dict:
        for name, entry in value.items():
            if not _finite(entry):
                raise ValueError(f"variable {name} must be finite")
        return value

    def number(self, name: str) -> float | None:
        """A numeric variable, or None when it is absent or not a number."""
        value = self.variables.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)


class Material(KratosPropertySet):
    """A soil property set. Its law and variables are Kratos'; `r_inter` and
    `interface_permeability` are this application's, the defaults an interface along
    this soil starts from (the Interfaces tab of the material editor)."""

    @model_validator(mode="before")
    @classmethod
    def _old_shape(cls, value: object) -> object:
        """Built from the fields this had before 2026-10-10 (a script written against
        them, say): converted the way a saved project in that shape is (`core/model/migration.py`)."""
        if isinstance(value, dict) and migration.is_old_record("materials", value):
            return migration.material(value, 2)
        return value

    id: Ident
    name: str
    color: Hex
    r_inter: float = Field(default=0.70, gt=0, le=1)
    interface_permeability: Literal["Neutral", "Drain", "Impermeable"] = "Neutral"


class SoilLayer(Base):
    id: Ident
    name: str
    mat: Ident
    top: float       # level (y) of the layer's top, m
    bottom: float    # level (y) of the layer's bottom, m

    @model_validator(mode="after")
    def _positive_thickness(self) -> SoilLayer:
        if self.bottom > self.top:
            raise ValueError(f"layer {self.id}: bottom {self.bottom} above top {self.top}")
        return self


def validate_layer_stack(layers: list[SoilLayer]) -> None:
    """The stack is gap-free: each layer's bottom is the next layer's top."""
    for upper, lower in zip(layers, layers[1:]):
        if abs(upper.bottom - lower.top) > 1e-9:
            raise ValueError(
                f"layer stack is not contiguous: "
                f"{upper.id} bottom {upper.bottom} != {lower.id} top {lower.top}"
            )


# ── Structures ──────────────────────────────────────────────────────────────

class Excavation(Base):
    x0: float
    x1: float
    z0: float
    z1: float
    floor_y: float
    """The final floor: the deepest level, and the one an unstaged project digs to in
    one go. Always `levels[-1]` -- see `_levels_are_the_truth`."""

    levels: list[float] = Field(default_factory=list)
    """The lifts the pit is dug in, shallowest first, each strictly below the last.

    A staged excavation is not one hole that appears at once: each lift is its own body
    in the mesh, deactivated in its own stage (`Excavated_Soil_1/2/3` in Kratos'
    staged-excavation reference deck). One level means an unstaged pit, which is what every project
    written before this field had, and is why it defaults to `[floor_y]` rather than to
    empty.
    """

    @model_validator(mode="before")
    @classmethod
    def _reconcile_floor_and_levels(cls, value: object) -> object:
        """Keep `floor_y` and `levels` from ever disagreeing, without guessing.

        Two fields describing one hole can drift, so the pair is reconciled on the way
        in. Three cases, and the third is the reason this is not a one-liner:

        *   **No `levels`** -- every project saved before this field. It becomes a
            single lift at `floor_y`, so old files keep opening.
        *   **They agree, or only `levels` is given** -- `floor_y` is (re)derived from
            the last level. This is the round-trip case, and the common one.
        *   **They disagree** -- refused, whatever the level count. Which field the
            caller meant to edit is not knowable from the payload, and silently
            rewriting the one they just changed is the outcome that must not happen.
            Editing the pit floor therefore means editing `levels`, and omitting
            `floor_y` is always allowed.
        """
        if not isinstance(value, dict):
            return value
        levels, floor = value.get("levels"), value.get("floor_y")
        if not levels:
            return value if floor is None else {**value, "levels": [floor]}
        if floor is None or floor == levels[-1]:
            return {**value, "floor_y": levels[-1]}
        raise ValueError(
            f"excavation floor_y ({floor}) disagrees with the last of its "
            f"{len(levels)} levels ({levels[-1]}); edit levels, which floor_y follows"
        )

    @model_validator(mode="after")
    def _ordered(self) -> Excavation:
        if self.x1 <= self.x0 or self.z1 <= self.z0:
            raise ValueError("excavation extents must be strictly increasing")
        if not all(math.isfinite(level) for level in self.levels):
            raise ValueError("excavation levels must all be finite")
        for upper, lower in zip(self.levels, self.levels[1:]):
            if lower >= upper:
                raise ValueError(
                    f"excavation levels must descend: {lower} does not lie below "
                    f"{upper}"
                )
        return self


class Wall(Base):
    """Retaining wall ring around the excavation, built outboard of the pit face."""
    thickness: float = Field(gt=0)
    top_y: float
    toe_y: float

    @model_validator(mode="after")
    def _ordered(self) -> Wall:
        if self.top_y <= self.toe_y:
            raise ValueError("wall top must be above its toe")
        return self


class Struts(Base):
    xs: list[float]
    y: float
    radius: float = Field(gt=0)
    overhang: float = Field(default=0.8, ge=0)   # extension past each pit face, m
    waler_width: float = Field(default=0.5, gt=0)
    waler_height: float = Field(default=0.6, gt=0)
    waler_offset: float = Field(default=0.5, gt=0)  # waler axis, outboard of the pit face


class AnchorRows(Base):
    """The seeded 3D anchor rows: aggregate display geometry, not individual members.

    Renamed from `Anchors` when `anchors` became the first-class collection below. It
    still draws the 3D cylinders under the part key `anchors`, exactly as before; only
    the project field moved, and `Project._migrate` accepts the old name.
    """
    xs: list[float]
    head_y: float
    length: float = Field(gt=0)
    inclination_deg: float = Field(gt=0, lt=90)
    radius: float = Field(gt=0)
    head_offset: float = Field(default=0.4, ge=0)
    """Anchor head position, measured inward from the wall's *outer* face.

    The head bears on the wall, so it sits within the wall thickness; the first
    `(thickness - head_offset) / cos(inclination)` of each shaft is embedded in wall
    material rather than soil.
    """


class Piles(Base):
    xs: list[float]
    zs: list[float]
    radius: float = Field(gt=0)
    length: float = Field(gt=0)
    top_y: float


class PointLoad(Base):
    id: Ident
    name: str
    kind: Literal["point"] = "point"
    x: float
    y: float
    thickness: float = Field(default=0.25, gt=0)
    components: tuple[float, float]  # in-plane x/y, a force
    distribution: Literal["Uniform"] = "Uniform"
    active: bool = True
    derived_from: Ident | None = None
    """The load in the other dimension this one is the translation of, if any.

    A surface load and a line load are one load seen from two dimensions, and both
    records are kept so a round trip does not widen the footprint (`core/model/load_translation.py`).
    Set on the *derived* record only; the one the user authored carries None."""

    @model_validator(mode="after")
    def _valid_condition(self) -> PointLoad:
        if not all(math.isfinite(value) for value in (self.x, self.y)):
            raise ValueError("point load coordinates must be finite")
        if not all(math.isfinite(value) for value in self.components):
            raise ValueError("load components must be finite")
        return self


class LineLoad(Base):
    id: Ident
    name: str
    kind: Literal["line"] = "line"
    x0: float
    x1: float
    y: float
    thickness: float = Field(default=0.15, gt=0)
    components: tuple[float, float]  # in-plane x/y, a force per length
    distribution: Literal["Uniform"] = "Uniform"
    active: bool = True
    derived_from: Ident | None = None
    """The load in the other dimension this one is the translation of, if any.

    A surface load and a line load are one load seen from two dimensions, and both
    records are kept so a round trip does not widen the footprint (`core/model/load_translation.py`).
    Set on the *derived* record only; the one the user authored carries None."""

    @model_validator(mode="after")
    def _valid_condition(self) -> LineLoad:
        if self.x1 <= self.x0:
            raise ValueError("line load extents must be strictly increasing")
        if not all(math.isfinite(value) for value in (self.x0, self.x1, self.y)):
            raise ValueError("line load coordinates must be finite")
        if not all(math.isfinite(value) for value in self.components):
            raise ValueError("load components must be finite")
        return self


class SurfaceLoad(Base):
    id: Ident
    name: str
    kind: Literal["surface"] = "surface"
    x0: float
    x1: float
    z0: float
    z1: float
    y: float | None = None
    """The elevation the pad lies at. None means the top of the model.

    Carried rather than rederived because rederiving it is not exact: `ground_y` is
    built from gmsh bounding boxes, which are padded by 1e-7, so a pad placed there
    floats just above the face it is meant to imprint. A translated load keeps the
    elevation of the line load it came from, which is on the face by construction.

    None is what every project saved before this field reads as, and it still means
    what it always did."""
    thickness: float = Field(gt=0)
    components: tuple[float, float, float]  # world x/y/z, a stress; y is vertical
    distribution: Literal["Uniform"] = "Uniform"
    active: bool = True
    derived_from: Ident | None = None
    """The load in the other dimension this one is the translation of, if any.

    A surface load and a line load are one load seen from two dimensions, and both
    records are kept so a round trip does not widen the footprint (`core/model/load_translation.py`).
    Set on the *derived* record only; the one the user authored carries None."""

    @model_validator(mode="after")
    def _valid_condition(self) -> SurfaceLoad:
        if self.x1 <= self.x0 or self.z1 <= self.z0:
            raise ValueError("load footprint extents must be strictly increasing")
        if not all(math.isfinite(value) for value in self.components):
            raise ValueError("load components must be finite")
        return self


class BeamSection(KratosPropertySet):
    """A reusable structural profile, shared by every sheet pile and member that uses it.

    One `MaterialParameters.json` entry per part that uses it, with these variables
    (`YOUNG_MODULUS`, `POISSON_RATIO`, `DENSITY`, `CROSS_AREA`, `I33`, and in 3D `I22`,
    `TORSIONAL_INERTIA`; `AREA_EFFECTIVE_Y/Z` for shear). Values are per member: in 2D
    the exporter divides the extensive ones by `spacing` to give the metre run plane
    strain models -- geometry, not a unit conversion.
    """

    @model_validator(mode="before")
    @classmethod
    def _old_shape(cls, value: object) -> object:
        """Built from the fields this had before 2026-10-10 (a script written against
        them, say): converted the way a saved project in that shape is (`core/model/migration.py`)."""
        if migration.is_old_record("beam_sections", value):
            return migration.CONVERTERS['beam_sections'](value)
        return value

    id: Ident
    name: str
    constitutive_law: str = Field(default="TimoshenkoBeamElasticConstitutiveLaw", min_length=1)
    spacing: float = Field(default=1.0, gt=0)
    """Out-of-plane spacing in metres. 1.0 is a continuous wall -- the usual sheet
    pile -- and a larger value smears a discrete row of piles over the plane. A
    plane-strain device: a 3D member is discrete already, and ignores it."""


class Beam(Base):
    """One sheet pile: an open polyline meshed as 1D structural elements.

    Dimension-native, exactly like a 2D load (see `LineLoad`): the points are in-plane
    `(x, y)` only, with no hidden `z`. The section plane's own offset places the curve
    in the 3D build workspace; it is never stored on the record.
    """
    id: Ident
    name: str
    kind: Literal["beam"] = "beam"
    """Defaulted, so every project saved before the 3D kinds existed still loads as
    the 2D sheet pile it was written as."""
    section: Ident
    points: list[tuple[float, float]]      # in-plane (x, y), metres
    active: bool = True
    derived_from: Ident | None = None
    """The structure in the other dimension this one is the translation of, if any.

    A sheet pile and a wall panel are one wall seen from two dimensions, and both
    records are kept so a plan footprint survives a trip through the section, which has
    no z to remember it by (`core/model/wall_translation.py`). Set on the *derived* record only."""

    @model_validator(mode="after")
    def _usable_polyline(self) -> Beam:
        if len(self.points) < 2:
            raise ValueError(f"beam {self.id!r} needs at least two points")
        if not all(math.isfinite(v) for point in self.points for v in point):
            raise ValueError(f"beam {self.id!r} has a non-finite coordinate")
        for first, second in zip(self.points, self.points[1:]):
            if first == second:
                raise ValueError(
                    f"beam {self.id!r} repeats the point {first}; every segment needs length"
                )
        return self


class AnchorSection(KratosPropertySet):
    """A reusable tendon or bar, shared by every anchor installed with it
    (`YOUNG_MODULUS`, `CROSS_AREA`, `DENSITY`, per anchor).

    `spacing` matters more here than for a sheet pile: anchors are discrete members at
    centres along the wall, and plane strain smears them over a metre run.
    """

    @model_validator(mode="before")
    @classmethod
    def _old_shape(cls, value: object) -> object:
        """Built from the fields this had before 2026-10-10 (a script written against
        them, say): converted the way a saved project in that shape is (`core/model/migration.py`)."""
        if migration.is_old_record("anchor_sections", value):
            return migration.CONVERTERS['anchor_sections'](value)
        return value

    id: Ident
    name: str
    constitutive_law: str = Field(default="TrussConstitutiveLaw", min_length=1)
    spacing: float = Field(default=2.5, gt=0)
    tension_limit: float | None = Field(default=None, gt=0)
    """Force per anchor, in the project's units. A design value Kratos has no property
    for; kept in the project and named in the export's warnings."""
    compression_limit: float | None = Field(default=None, gt=0)
    """Left None for a tendon, which takes no compression at all."""


class Anchor(Base):
    """One anchor: a two-node tie from a sheet pile to a restrained point.

    The formulation is the one Kratos' reference decks write -- a single
    `LinearTrussElement2D2N` whose head node is shared with the beam and whose tail node
    belongs to no other element, held by its own node group. The tail is therefore *not*
    coupled to the soil continuum: the grouted body is idealised as a fixed point, which
    is the standard plane-strain treatment.

    Dimension-native `(x, y)` like every other 2D record.
    """
    id: Ident
    name: str
    kind: Literal["anchor"] = "anchor"
    section: Ident
    head: tuple[float, float]
    tail: tuple[float, float]
    prestress: float = 0.0
    """Kratos' `TRUSS_PRESTRESS_PK2` for this anchor, a stress in the project's units,
    positive in tension (smeared by the tendon's spacing in 2D, like its area). Per
    anchor rather than per section: two anchors of the same tendon are routinely
    stressed differently, and each anchor is its own property set in the deck."""
    active: bool = True

    @model_validator(mode="after")
    def _usable_line(self) -> Anchor:
        if not all(math.isfinite(v) for v in self.head + self.tail):
            raise ValueError(f"anchor {self.id!r} has a non-finite coordinate")
        if self.head == self.tail:
            raise ValueError(f"anchor {self.id!r} must have a non-zero length")
        if not math.isfinite(self.prestress):
            raise ValueError(f"anchor {self.id!r} has a non-finite prestress")
        return self



STRETCH_TOLERANCE = 1e-6
"""Metres. How close From and To must be to the pile, and how much two interfaces on
one face may overlap before they are refused. The window and `drafts.interface` snap a
typed point onto the pile first (`drafts.STRETCH_SNAP`), so a stored one is on it."""


FACE_ORDER = ("left", "right", "below", "above")
"""The faces in the order a refusal names the first of two (`App.Interfaces`, too)."""


def _xy(point: Sequence[float]) -> str:
    return "(" + ", ".join(f"{value:g}" for value in point) + ")"


def _runs_along(line: Sequence[Sequence[float]], pile: Sequence[Sequence[float]]) -> bool:
    """Whether some segment of `line` lies on a segment of `pile` over a length."""
    for a, b in zip(line, line[1:]):
        for c, d in zip(pile, pile[1:]):
            dx, dy = d[0] - c[0], d[1] - c[1]
            size = math.hypot(dx, dy)
            if size == 0.0:
                continue
            off = [abs(dx * (p[1] - c[1]) - dy * (p[0] - c[0])) / size for p in (a, b)]
            if max(off) > STRETCH_TOLERANCE:
                continue
            along = sorted(((p[0] - c[0]) * dx + (p[1] - c[1]) * dy) / size for p in (a, b))
            if min(along[1], size) - max(along[0], 0.0) > STRETCH_TOLERANCE:
                return True
    return False


# ── Interfaces ──────────────────────────────────────────────────────────────
#
# An interface is the sliding, opening contact between a structure and the ground it
# stands in. Kratos models it as a *zero-thickness* element: two coincident faces whose
# nodes are separate, so the wall and the soil can move relative to one another instead
# of being welded together the way `_embed_beams` leaves them.
#
# The formulation is read off Kratos' reference decks, which are exactly this: the sheet
# pile owns its own nodes, each side of the soil owns a duplicate set, and one
# `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N` per side per beam segment
# ties them together. See the element table in core/kratos/writer.py and the node split in
# core/kratos/interfaces.py.


class InterfaceSection(KratosPropertySet):
    """A reusable interface property set, shared by every interface using it.

    Its variables are Kratos' (`INTERFACE_NORMAL_STIFFNESS`, `INTERFACE_SHEAR_STIFFNESS`,
    `GEO_COHESION`, `GEO_FRICTION_ANGLE`, ...). Any left out are derived at export from
    the soil the contact runs against -- shear stiffness its shear modulus over
    `virtual_thickness`, normal ten times that, strength the soil's reduced by `r_inter`
    -- which is what `core/kratos/materials.py` does and where the reasoning lives.

    *Which* soil is the adjacent body's by default, one property set per body, as the
    reference deck does it. `material` overrides that for the whole contact.
    """

    @model_validator(mode="before")
    @classmethod
    def _old_shape(cls, value: object) -> object:
        """Built from the fields this had before 2026-10-10 (a script written against
        them, say): converted the way a saved project in that shape is (`core/model/migration.py`)."""
        if migration.is_old_record("interface_sections", value):
            return migration.CONVERTERS['interface_sections'](value)
        return value

    id: Ident
    name: str
    constitutive_law: str = Field(default="GeoIncrementalLinearElasticInterfaceLaw",
                                  min_length=1)
    material: Ident | None = None
    """One soil for the whole contact, overriding the per-body default."""
    r_inter: float | None = Field(default=None, gt=0, le=1)
    """The strength reduction for the whole contact. None -- each stretch of contact takes
    the Rinter of the soil it runs against (`Material.r_inter`). That is the rule here and
    the one Kratos' Mohr-Coulomb staged-excavation reference follows: a clay and a
    sand along the same wall are reduced by different factors."""
    virtual_thickness: float = Field(default=1.0, gt=0)       # m
    """The element size normal to the interface, which the derived stiffnesses are the
    soil's shear modulus over. 1.0 is the reference deck's own."""
    permeability: Literal["Neutral", "Drain", "Impermeable"] = "Neutral"


class Interface(Base):
    """One interface: a line along which the mesh is split and re-tied by contact.

    Two ways to place one, and exactly one of them per record:

    *   `structure` names a sheet pile. The interface runs the whole pile, or the part
        of it between the two points of `stretch`, and `side` says which of the two
        soils is unglued from it. This is the usual arrangement -- a wall slides
        against the ground on both faces.
    *   `points` is a free polyline in the section, which splits soil from soil: an
        excavation face, a slip surface, a lining. There is no structure in the middle,
        so one soil keeps the original nodes and the other is detached; `side` says
        which, and `both` is meaningless without a structure to sit between them.

    `side` names a face as the screen shows it, whichever way the line was drawn: for a
    line steeper than 45 degrees "left" is the face toward -x and "right" the face toward
    +x; for a flatter line the faces are "below" and "above" (`core.model.polylines`).
    The deck's `_Left_face` and `_Right_face` parts and the Kratos-side
    InterfaceInserter use the same words. `Project` turns a "left" on a flat line into
    "below", and back, so a record follows its line when the line is changed.

    Dimension-native `(x, y)`, like every other 2D record. Interfaces are plane strain
    only -- see core/kratos/writer.py's `INTERFACES` table for why.
    """
    id: Ident
    name: str
    kind: Literal["interface"] = "interface"
    section: Ident
    structure: Ident | None = None
    points: list[tuple[float, float]] | None = None
    side: Literal["both", "left", "right", "below", "above"] = "both"
    stretch: tuple[tuple[float, float], tuple[float, float]] | None = None
    """From and To: the two points on the pile between which the interface runs, or
    None for the whole pile. Only with `structure`. `Project` checks that both are on
    the pile and saves a stretch from one end of the pile to the other as None."""
    active: bool = True

    @model_validator(mode="after")
    def _usable_line(self) -> Interface:
        if (self.structure is None) == (self.points is None):
            raise ValueError(
                f"interface {self.id!r} needs either a structure to follow or its own "
                "points, and not both"
            )
        if self.stretch is not None:
            if self.structure is None:
                raise ValueError(
                    f"interface {self.id!r} has From and To but follows no sheet pile; "
                    "From and To are points on the pile it follows"
                )
            start, end = self.stretch
            if not all(math.isfinite(v) for v in start + end):
                raise ValueError(f"interface {self.id!r} has a non-finite From or To")
            if start == end:
                raise ValueError(
                    f"interface {self.id!r} has From and To at the same point; the part "
                    "of the pile it holds needs length"
                )
        if self.structure is None:
            if self.side == "both":
                raise ValueError(
                    f"interface {self.id!r} has no structure between its two sides, so "
                    "it must detach one of them: set side to 'left' or 'right'"
                )
            points = self.points or []
            if len(points) < 2:
                raise ValueError(f"interface {self.id!r} needs at least two points")
            if not all(math.isfinite(v) for point in points for v in point):
                raise ValueError(f"interface {self.id!r} has a non-finite coordinate")
            for first, second in zip(points, points[1:]):
                if first == second:
                    raise ValueError(
                        f"interface {self.id!r} repeats the point {first}; every "
                        "segment needs length"
                    )
        return self


class NormalLoad(Base):
    """A pressure load normal to a free polyline -- an exposed excavation face, a
    sloped boundary -- rather than a fixed x/y vector on a flat horizontal run like
    `LineLoad`.

    Dimension-native `(x, y)`, like a free `Interface`'s points: 2D (plane strain)
    only, with no 3D translation -- `Project.active_normal_loads` is gated the same
    way `active_interfaces` is. The line is embedded into the section the same way a
    free interface's is (`core/geometry/solid_model.py:_embed_beams`), and its condition is harvested
    directly off that embedding (`core/kratos/writer.py:_normal_load_conditions`) rather than
    by scanning the boundary at a fixed elevation the way `LineLoad` is, which is what
    lets it run down a vertical face.

    Two ways to size it, picked by `fluid_pressure_type`, matching Kratos
    GeoMechanics' own `ApplyNormalLoadTableProcess`:

    *   `"Hydrostatic"` derives the pressure from a water level at export time -- zero at
        the level, increasing with depth below it. The level is the load's own
        `reference_coordinate`, which a new load is given (`drafts.normal_load`); one
        saved without it reads `Project.water`. This is a staged excavation's
        `WaterLoad_StageN` arrangement.
    *   `"Uniform"` applies `pressure` everywhere along the line instead, for a load
        that is not water: a surcharge normal to a sloped face, say.
    """
    id: Ident
    name: str
    kind: Literal["normal"] = "normal"
    points: list[tuple[float, float]]
    fluid_pressure_type: Literal["Uniform", "Hydrostatic"] = "Uniform"
    """`"Uniform"` by default, so a load given a magnitude applies it. Hydrostatic is
    the water case and derives the pressure from `Project.water` instead, ignoring
    `pressure` -- the wrong thing to fall into without asking for it."""
    pressure: float = 0.0
    """A stress in the project's units, compression positive. Read only when `fluid_pressure_type` is
    `"Uniform"`; a hydrostatic load is derived from its water level instead."""
    reference_coordinate: float | None = None
    """The water level of a hydrostatic load, m, under the name Kratos'
    `ApplyNormalLoadTableProcess` gives it. `None`, which only a load saved before the
    level was copied in has, is the project's own (`Project.water`). Read only when
    `fluid_pressure_type` is `"Hydrostatic"`."""
    active: bool = True

    @model_validator(mode="before")
    @classmethod
    def _drop_indicator_thickness(cls, value: object) -> object:
        """A normal load used to carry a `thickness`, for a strip drawn along its line
        the way a line load's pad is drawn. The strip stood proud of the model -- a bar
        laid on top of the loaded face rather than a load applied to it -- and the
        arrows say the same thing better, so it is gone. Saved projects still carry the
        field, and `extra: forbid` would refuse them over a number nothing reads."""
        if isinstance(value, dict) and "thickness" in value:
            value = {k: v for k, v in value.items() if k != "thickness"}
        return value

    @model_validator(mode="after")
    def _usable_polyline(self) -> NormalLoad:
        if len(self.points) < 2:
            raise ValueError(f"normal load {self.id!r} needs at least two points")
        if not all(math.isfinite(v) for point in self.points for v in point):
            raise ValueError(f"normal load {self.id!r} has a non-finite coordinate")
        for first, second in zip(self.points, self.points[1:]):
            if first == second:
                raise ValueError(
                    f"normal load {self.id!r} repeats the point {first}; every "
                    "segment needs length"
                )
        if not math.isfinite(self.pressure):
            raise ValueError(f"normal load {self.id!r} has a non-finite pressure")
        if self.reference_coordinate is not None and not math.isfinite(
                self.reference_coordinate):
            raise ValueError(f"normal load {self.id!r} has a non-finite water level")
        return self


# ── 3D structures ───────────────────────────────────────────────────────────
#
# A 3D wall is not a 2D sheet pile one dimension up. In plan it is a panel: a footprint
# swept between two levels, carrying a thickness rather than an area and inertia per
# metre run, and meshed as shells. A bored pile or king post, on the other hand, really
# is a 1D member in space and keeps the sheet pile's profile library.
#
# Both live in `beams[]` beside the 2D `Beam`, discriminated by `kind`, exactly as
# `loads[]` already holds three kinds. Records stay dimension-native: a 2D pile keeps
# its `(x, y)` polyline and is untouched by any of this.
#
# No 3D element class is pinned by a reference deck here -- every reference deck is
# plane strain. See plan/structure-mode-implementation-plan.md and the element tables
# in core/kratos/writer.py, which name every unconfirmed choice in one place.


class PanelSection(KratosPropertySet):
    """A reusable wall property set, shared by every panel built with it
    (`YOUNG_MODULUS`, `POISSON_RATIO`, `DENSITY`, `THICKNESS`). The 3D counterpart of
    `BeamSection`: a shell is defined by a thickness, not an area and inertia."""

    @model_validator(mode="before")
    @classmethod
    def _old_shape(cls, value: object) -> object:
        """Built from the fields this had before 2026-10-10 (a script written against
        them, say): converted the way a saved project in that shape is (`core/model/migration.py`)."""
        if migration.is_old_record("panel_sections", value):
            return migration.CONVERTERS['panel_sections'](value)
        return value

    id: Ident
    name: str
    constitutive_law: str = Field(default="LinearElasticPlaneStress2DLaw", min_length=1)

    @classmethod
    def from_beam_section(cls, section: BeamSection, id: str, name: str) -> PanelSection:
        """The shell a pile's profile becomes when its wall is swept into the solid
        model. `CROSS_AREA` per metre run is exactly a thickness in metres -- the
        plane-strain reduction of a plate, read backwards -- and the rest carry over."""
        mapping = {"YOUNG_MODULUS": "YOUNG_MODULUS", "POISSON_RATIO": "POISSON_RATIO",
                   "DENSITY": "DENSITY", "CROSS_AREA": "THICKNESS"}
        variables = {mapping[k]: v for k, v in section.variables.items() if k in mapping}
        return cls(id=id, name=name, variables=_ordered_like(variables, mapping.values()))


def _ordered_like(variables: dict, order) -> dict:
    return {k: variables[k] for k in order if k in variables}


class Panel(Base):
    """One 3D sheet-pile wall: a plan footprint swept from `y_top` down to `y_toe`.

    The footprint is `(x, z)` in plan and the sweep is vertical, which is what a sheet
    pile wall is: the surface it leaves behind is fragmented into the soil volume so
    both share their nodes, the same conformity the 2D pile gets from `_embed_beams`.
    """
    id: Ident
    name: str
    kind: Literal["panel"] = "panel"
    section: Ident
    footprint: list[tuple[float, float]]   # plan (x, z), metres
    y_top: float
    y_toe: float
    active: bool = True
    derived_from: Ident | None = None
    """The structure in the other dimension this one is the translation of, if any.

    A sheet pile and a wall panel are one wall seen from two dimensions, and both
    records are kept so a plan footprint survives a trip through the section, which has
    no z to remember it by (`core/model/wall_translation.py`). Set on the *derived* record only."""

    @model_validator(mode="after")
    def _usable_sweep(self) -> Panel:
        if len(self.footprint) < 2:
            raise ValueError(f"panel {self.id!r} needs at least two points")
        if not all(math.isfinite(v) for point in self.footprint for v in point):
            raise ValueError(f"panel {self.id!r} has a non-finite coordinate")
        if not (math.isfinite(self.y_top) and math.isfinite(self.y_toe)):
            raise ValueError(f"panel {self.id!r} has a non-finite level")
        for first, second in zip(self.footprint, self.footprint[1:]):
            if first == second:
                raise ValueError(
                    f"panel {self.id!r} repeats the point {first}; every segment needs "
                    "a zero-length-free run"
                )
        if self.y_top <= self.y_toe:
            raise ValueError(f"panel {self.id!r} must have its top above its toe")
        return self

    def height(self) -> float:
        return self.y_top - self.y_toe


class Member(Base):
    """One 3D structural member: a bored pile, king post or strut, meshed as 1D beams.

    The 3D sibling of `Beam`, and it shares `beam_sections`: a member is the same
    profile a 2D pile is drawn with, standing in space rather than in a section.
    """
    id: Ident
    name: str
    kind: Literal["member"] = "member"
    section: Ident
    points: list[tuple[float, float, float]]   # world (x, y, z), metres
    active: bool = True
    derived_from: Ident | None = None
    """Never set on a member: it has no 2D counterpart. Present so every structure in
    `beams[]` answers the same question -- see `Panel.derived_from`."""

    @model_validator(mode="after")
    def _usable_polyline(self) -> Member:
        if len(self.points) < 2:
            raise ValueError(f"member {self.id!r} needs at least two points")
        if not all(math.isfinite(v) for point in self.points for v in point):
            raise ValueError(f"member {self.id!r} has a non-finite coordinate")
        for first, second in zip(self.points, self.points[1:]):
            if first == second:
                raise ValueError(
                    f"member {self.id!r} repeats the point {first}; every segment needs "
                    "a zero-length-free run"
                )
        return self


class SpaceAnchor(Base):
    """One 3D anchor: a two-node tie in space, from a wall or member to a fixed point.

    The same formulation as the 2D `Anchor` -- head shared with the structure it hangs
    from, tail in no element at all and pinned by its own node group -- one dimension
    up. The tendon library is shared with the 2D anchors; `spacing` is a plane-strain
    smear and means nothing here, where every anchor is a discrete member.
    """
    id: Ident
    name: str
    kind: Literal["anchor3d"] = "anchor3d"
    section: Ident
    head: tuple[float, float, float]
    tail: tuple[float, float, float]
    prestress: float = 0.0
    active: bool = True

    @model_validator(mode="after")
    def _usable_line(self) -> SpaceAnchor:
        if not all(math.isfinite(v) for v in self.head + self.tail):
            raise ValueError(f"anchor {self.id!r} has a non-finite coordinate")
        if self.head == self.tail:
            raise ValueError(f"anchor {self.id!r} must have a non-zero length")
        if not math.isfinite(self.prestress):
            raise ValueError(f"anchor {self.id!r} has a non-finite prestress")
        return self


def point_on_polyline(point: tuple[float, ...],
                      points: Sequence[tuple[float, ...]], tol: float = 1e-6) -> bool:
    """Does `point` lie on any segment of `points`, within `tol` metres?

    Used to hold the anchor head onto a sheet pile. The head becomes a shared node in
    the mesh, so it has to be on the pile in the project first -- an anchor floating
    beside its wall would export a truss connected to nothing.

    Dimension-agnostic: the 2D anchors pass `(x, y)` pairs and the 3D ones pass either
    `(x, y, z)` triples, for a member, or the plan `(x, z)` of a panel footprint.
    """
    for start, end in zip(points, points[1:]):
        delta = [b - a for a, b in zip(start, end)]
        length_squared = sum(d * d for d in delta)
        if length_squared == 0:
            continue
        t = sum((p - a) * d for p, a, d in zip(point, start, delta)) / length_squared
        t = min(1.0, max(0.0, t))
        closest = [a + t * d for a, d in zip(start, delta)]
        if math.dist(point, closest) <= tol:
            return True
    return False


def point_on_panel(point: tuple[float, float, float], panel: Panel,
                   tol: float = 1e-6) -> bool:
    """Does `point` lie on the swept surface of `panel`, within `tol` metres?

    The sweep is vertical, so the test splits cleanly: the level has to be within the
    panel's own depth range, and the plan position has to be on its footprint.
    """
    x, y, z = point
    if not (panel.y_toe - tol <= y <= panel.y_top + tol):
        return False
    return point_on_polyline((x, z), panel.footprint, tol)


class Wells(Base):
    positions: list[tuple[float, float]]
    radius: float = Field(gt=0)
    top_y: float
    length: float = Field(gt=0)


WATER_SPECIFIC_WEIGHT_SI = 10_000.0
"""N/m3, the water a project that says nothing about it has."""


class WaterLevel(Base):
    y: float
    # The phreatic level is a reference plane, not a solid: it is drawn as a thin slab
    # overhanging the domain so the level reads against the model's outside faces
    # (js/viewport.js:201). It takes no part in the geometry booleans.
    margin: float = Field(default=3.0, ge=0)
    thickness: float = Field(default=0.06, gt=0)
    specific_weight: float | None = Field(default=None, gt=0)
    """In the project's units. None is water's 10 kN/m3 in whatever system the project
    uses (`Project.water_specific_weight`). Read by a `NormalLoad` in `"Hydrostatic"` mode
    (`core/kratos/parameters.py:_normal_load`) and by every `WaterPressureCondition`
    (`_water_pressure`). One value for the whole project, the same way `y` is one
    phreatic level -- not a per-load setting."""


# ── Boundary conditions ─────────────────────────────────────────────────────

FACES = ("bottom", "left", "right", "front", "back", "top")
"""The faces of the domain box a condition can name. Front and back exist in 3D only; a
2D section has no boundary along z."""

Face = Literal["bottom", "left", "right", "front", "back", "top"]

ConditionTarget = Literal["domain", "face", "part", "line", "point"]
"""What a condition acts on: the first of the two questions the GUI's condition dialog
asks. The second -- which face, which part, where -- is the field it names (`face`,
`part`, `points`). Two fields rather than one overloaded value, so the record holds the
dialog's two answers as they are and nothing has to guess what kind a value is."""

PressureType = Literal["Uniform", "Hydrostatic", "Phreatic_Multi_Line"]
"""How a water pressure condition gives each node its pressure: Kratos'
`fluid_pressure_type`, under its own names (`WaterPressureCondition`)."""

TARGET_ORDER = ("domain", "part", "face", "line", "point")
"""The order fixed conditions are written in, least specific first: where two act on
one node, Kratos keeps the value written last, so the more specific target wins."""


class WaterPressureCondition(Base):
    """A water pressure the user prescribes: on the whole soil, on one soil part, on a
    face of the domain, along a drawn line, or at a point.

    Nothing else puts a water pressure in the deck: a project with no such record has no
    water pressure process at all, whatever its water level. Each record is complete in
    itself -- a hydrostatic one carries its own level -- so two of them can hold two
    water levels. The fields carry the names of Kratos' `ApplyScalarConstraintTableProcess`
    (GeoMechanicsApplication), so the record reads like the process it is written as
    (`core/kratos/parameters.py:_water_pressure`):

    *   `"Uniform"`: `value` at every node.
    *   `"Hydrostatic"`: zero at the horizontal level `reference_coordinate`, growing with
        depth below it.
    *   `"Phreatic_Multi_Line"`: hydrostatic below the phreatic line through
        (`x_coordinates[i]`, `y_coordinates[i]`, `z_coordinates[i]`).

    Above the level Kratos' formula gives suction, which is positive in its sign
    convention; `pressure_tension_cut_off` is the most it may reach, and the Kratos
    default 0 holds the pressure at zero there. `is_fixed=False` makes the record start
    values only -- an initial field the calculation then changes.

    The target is `on` and the one field it names:

    *   `"domain"`: every soil node.
    *   `"face"`: the face `face` of the domain. A face the model does not have (front
        and back in 2D) is left out with a warning, so switching dimension keeps the
        record.
    *   `"part"`: the soil part `part`, a key `Project.part_keys` lists -- a layer
        (`soil_<id>`, with every lift dug out of it), one of its bodies, or a custom part
        that has a material.
    *   `"line"`: the polyline `points` (two or more), and `"point"`: the one point in
        `points`. Both are drawn in the 2D section and embedded in its mesh the way a
        normal load's line is; a 3D export leaves them out with a warning.
    """
    id: Ident
    name: str
    kind: Literal["water_pressure"] = "water_pressure"
    on: ConditionTarget
    face: Face | None = None
    part: str | None = None
    points: list[tuple[float, float]] | None = None
    fluid_pressure_type: PressureType = "Hydrostatic"
    is_fixed: bool = True
    value: float = 0.0
    """A stress in the project's units, Kratos' sign (compression negative). Read only
    when `fluid_pressure_type` is `"Uniform"`."""
    reference_coordinate: float | None = None
    """The water level, m: the height where the pressure is zero. Required when
    `fluid_pressure_type` is `"Hydrostatic"`, and read only then."""
    x_coordinates: list[float] | None = None
    y_coordinates: list[float] | None = None
    z_coordinates: list[float] | None = None
    """The phreatic line, m, x increasing; `z_coordinates` may be left out, which is all
    zeros. Read only when `fluid_pressure_type` is `"Phreatic_Multi_Line"`; the line may
    start and end outside the domain."""
    pressure_tension_cut_off: float = Field(default=0.0, ge=0)
    """A stress in the project's units. Read by `"Hydrostatic"` and
    `"Phreatic_Multi_Line"`."""
    active: bool = True

    @model_validator(mode="after")
    def _usable(self) -> WaterPressureCondition:
        noun = f"water pressure condition {self.id!r}"
        _check_target(self, noun)
        numbers = [self.value, self.pressure_tension_cut_off]
        if self.reference_coordinate is not None:
            numbers.append(self.reference_coordinate)
        if not all(math.isfinite(v) for v in numbers):
            raise ValueError(f"{noun} has a non-finite value")
        if self.fluid_pressure_type == "Hydrostatic" and self.reference_coordinate is None:
            raise ValueError(f"{noun} is Hydrostatic, which needs its water level "
                             "(reference_coordinate)")
        if (self.x_coordinates is None) != (self.y_coordinates is None):
            raise ValueError(f"{noun} needs both x_coordinates and y_coordinates, or "
                             "neither")
        if self.z_coordinates is not None and self.x_coordinates is None:
            raise ValueError(f"{noun} has z_coordinates but no x_coordinates and "
                             "y_coordinates")
        if self.x_coordinates is not None and self.y_coordinates is not None:
            xs, ys = self.x_coordinates, self.y_coordinates
            zs = self.z_coordinates if self.z_coordinates is not None else [0.0] * len(xs)
            if len(xs) != len(ys) or len(xs) != len(zs) or len(xs) < 2:
                raise ValueError(f"{noun}: the phreatic line needs two or more points, "
                                 "with as many x as y (and z) coordinates")
            if not all(math.isfinite(v) for v in xs + ys + zs):
                raise ValueError(f"{noun}: the phreatic line has a non-finite coordinate")
            if any(second <= first for first, second in zip(xs, xs[1:])):
                raise ValueError(f"{noun}: the x coordinates of the phreatic line must "
                                 "increase")
        elif self.fluid_pressure_type == "Phreatic_Multi_Line":
            raise ValueError(f"{noun} is a Phreatic_Multi_Line, which needs the points of "
                             "the line (x_coordinates and y_coordinates)")
        return self

def _check_target(record: WaterPressureCondition | DisplacementCondition | SeepageCondition,
                  noun: str) -> None:
    """`on` and the one field it names, and none of the others: the target check both
    kinds of condition share."""
    named = {"face": record.face, "part": record.part, "points": record.points}
    wanted = {"face": "face", "part": "part", "line": "points",
              "point": "points"}.get(record.on)
    stray = sorted(field for field, value in named.items()
                   if value is not None and field != wanted)
    if stray:
        raise ValueError(f"{noun} is on {record.on!r}, which takes no "
                         + " or ".join(stray))
    if wanted is not None and not named[wanted]:
        raise ValueError(f"{noun} is on {record.on!r}, which needs {wanted}")
    if record.points is None:
        return
    if not all(math.isfinite(v) for point in record.points for v in point):
        raise ValueError(f"{noun} has a non-finite coordinate")
    if record.on == "point" and len(record.points) != 1:
        raise ValueError(f"{noun} is on a point, which is one point, not "
                         f"{len(record.points)}")
    if record.on == "line":
        if len(record.points) < 2:
            raise ValueError(f"{noun} is on a line, which needs at least two points")
        for first, second in zip(record.points, record.points[1:]):
            if first == second:
                raise ValueError(f"{noun} repeats the point {first}; every segment "
                                 "needs length")


FACE_NORMALS = {"bottom": 1, "top": 1, "left": 0, "right": 0, "front": 2, "back": 2}
"""The axis normal to each face (x 0, y 1, z 2): what a roller on it holds."""


class DisplacementCondition(Base):
    """Displacements the user holds at zero: on a face of the domain, on a soil part,
    along a drawn line, or at a point.

    `fixed` is the components held, x, y and z: all three for a fixed support, the one
    normal to a face for a roller (`FACE_NORMALS`). A 2D section has no z displacement,
    so its deck holds only x and y whatever the third says, and a face the section does
    not have (front and back) is left out without a word: the plane-strain section holds
    z everywhere already. Written as Kratos' `ApplyVectorConstraintTableProcess` on the
    target's node part (`core/kratos/parameters.py:_constraint`).

    The target is `on` and the field it names, as for a `WaterPressureCondition`, except
    that the whole soil (`"domain"`) is no target for a displacement: it would hold the
    model still.
    """
    id: Ident
    name: str
    kind: Literal["displacement"] = "displacement"
    on: ConditionTarget
    face: Face | None = None
    part: str | None = None
    points: list[tuple[float, float]] | None = None
    fixed: tuple[bool, bool, bool] = (True, True, True)
    active: bool = True

    @model_validator(mode="after")
    def _usable(self) -> DisplacementCondition:
        noun = f"displacement condition {self.id!r}"
        if self.on == "domain":
            raise ValueError(f"{noun} is on the whole soil, which would hold the whole "
                             "model still; put it on a face, a part, a line or a point")
        _check_target(self, noun)
        if not any(self.fixed):
            raise ValueError(f"{noun} holds no component; fix x, y or z, or remove it")
        return self


SeepageTarget = Literal["face", "line"]
"""Where a seepage face can be: a face of the domain, or a line drawn along the soil's
outer boundary."""


class SeepageCondition(Base):
    """A seepage face: a stretch of the soil's outer boundary where the water may leave
    the soil but not enter it, such as the downstream slope of a dike above the tail
    water.

    In a groundwater flow calculation only. The deck writes a `GeoSeepageCondition2D2N`
    (`2D3N` in a quadratic mesh) on each mesh edge of the target, one
    `ApplySeepageBoundaryProcess` on them, and solves the stage with Kratos'
    `newton_raphson_with_seepage` strategy (`core/kratos/parameters.py`). The strategy
    decides node by node, while it iterates: a free node where the water pressure would
    be above the atmosphere (negative, in Kratos' sign) is fixed at zero, and the water
    flows out there; a fixed node through which water would flow in is freed again.
    Where the water pressure stays below the atmosphere the face is closed, as a
    boundary with no condition is.

    The target is `on` and the field it names, as for a `WaterPressureCondition`: the
    face `face`, or the polyline `points`, drawn in the 2D section. Every mesh edge of
    the target has to be on the soil's outer boundary, as Kratos requires; a line
    through the soil is refused at export. A seepage face is not switched by stages: it
    acts in every stage, as Kratos collects the seepage nodes once, from every seepage
    condition in the model. A deformation calculation leaves it out, with a warning.
    """
    id: Ident
    name: str
    kind: Literal["seepage"] = "seepage"
    on: SeepageTarget
    face: Face | None = None
    part: str | None = None
    points: list[tuple[float, float]] | None = None
    active: bool = True

    @model_validator(mode="after")
    def _usable(self) -> SeepageCondition:
        _check_target(self, f"seepage condition {self.id!r}")
        return self


AnyCondition = DisplacementCondition | WaterPressureCondition | SeepageCondition
"""Any one boundary condition, for a type annotation (`BoundaryCondition` is the same
union, told apart by `kind` when a project is read)."""


def standard_conditions() -> list[AnyCondition]:
    """The supports a model starts with: the bottom fixed, every side on rollers.

    What a new project has, what a project saved before the conditions existed opens
    with, and what `core.session.standard_conditions` puts back. Displacements only: no
    project gets a water pressure it did not ask for."""
    out: list[AnyCondition] = [DisplacementCondition(
        id="fixed_bottom", name="Fixed bottom", on="face", face="bottom")]
    for face in ("left", "right", "front", "back"):
        fixed = [False, False, False]
        fixed[FACE_NORMALS[face]] = True
        out.append(DisplacementCondition(
            id=f"roller_{face}", name=f"Roller {face}", on="face", face=face,
            fixed=(fixed[0], fixed[1], fixed[2])))
    return out


BoundaryCondition = Annotated[DisplacementCondition | WaterPressureCondition
                              | SeepageCondition, Field(discriminator="kind")]
"""One record of `Project.boundary_conditions`, told apart by its `kind`."""


CalculationType = Literal["mechanical", "flow"]
StressInitialisation = Literal["K0", "gravity", "none"]
TimeIntegration = Literal["static", "dynamic"]
ConvergenceCriterion = Literal["residual_criterion", "displacement_criterion",
                               "water_pressure_criterion"]

CONVERGENCE_CRITERIA: dict[str, tuple[str, ...]] = {
    calculation: tuple(name for name, _ in criteria)
    for calculation, criteria in solver.CRITERIA.items()}
"""The convergence criteria a stage of each calculation type can be solved on, its
default first: Kratos' names, which its `U_Pw` and `Pw` solvers read
(`core.kratos.parameters.CONVERGENCE_TOLERANCES`). Listed, with their labels, in
`core.model.solver.CRITERIA`, which the browser reads too.

The residual one is the default of both types: every reference deck converges on it.
Kratos' displacement criterion measures the update of every degree of freedom, the
water pressure too: in a coupled soil whose water pressure builds up, it does not
converge where the residual one does. The water pressure criterion of a flow stage
can fail to settle in the same way with a seepage face, whose opening and closing keeps
the water pressure moving (a quadratic Muskat case C). Kratos'
`displacement_and_water_pressure_criterion` is not offered: Kratos 10.4.4 cannot build
it (`geomechanics_U_Pw_solver.py` hands `MixedGenericCriteria` two criteria where it
takes variables)."""

ABSOLUTE_TOLERANCES: dict[str, float] = solver.ABSOLUTE_TOLERANCES
"""The default absolute tolerance of each convergence criterion (`Stage.absolute_tolerance`)."""


def followed_tolerance(tolerance: float, old: str, new: str) -> float:
    """The absolute tolerance of a stage whose criterion goes from `old` to `new`: the new
    criterion's default if it was the old one's, otherwise the stage's own."""
    if old in ABSOLUTE_TOLERANCES and new in ABSOLUTE_TOLERANCES \
            and tolerance == ABSOLUTE_TOLERANCES[old]:
        return ABSOLUTE_TOLERANCES[new]
    return tolerance


class Stage(Base):
    """One construction stage: what changes about the model, and how it is solved.

    The field names follow the stage panel the GUI already draws (js/data.js:559),
    because that is the UI this feeds and a second vocabulary would have to be
    translated twice.

    **A stage stores a diff, not a state.** `activate` and `deactivate` say what this
    stage changes about the model it inherits from `parent`; they do not describe the
    whole model. Two reasons, and both matter: the reference deck's `stage_preprocess`
    *is* that diff, so nothing has to be reconstructed on export; and storing absolute
    state would mean rewriting every later stage whenever a part is added to the model.
    Resolving diff to state is one function, in `core.model.stages`, which is the only place
    that walks the parent chain.

    `parent` makes a tree, and a tree can branch. Kratos cannot run one: its orchestrator
    runs a flat `execution_list`. Linearising the tree, and refusing one that cannot be
    linearised, is the export's job (`core.model.stages`) rather than this class's -- a branch
    is a legitimate thing to have half-built in the editor, and refusing it here would
    make it impossible to type.

    The water in a stage is its water pressure conditions: their ids are stageable
    keys (`Project.stageable_keys`), so a stage switches one on or off as it does a
    load -- a high level, then a low one.
    """
    id: Ident
    name: str
    parent: Ident | None = None
    """The stage this one starts from. `None` only for the first, which starts from the
    model as built."""

    calculation: CalculationType = "mechanical"
    """What the stage solves for. "mechanical" is the deformation of the soil and the
    water pressure in it (Kratos' `U_Pw` solver); "flow" is the flow of the water alone
    (the `Pw` solver). A flow stage needs water pressure elements, and the mesh is one
    for all the stages, so a project mixes it with no other type: the export refuses the
    mix (`core.model.stages.groundwater_flow`). A new type is a new value here, and its
    Kratos solver in `core.kratos.parameters.SOLVERS`."""
    stress_initialisation: StressInitialisation = "none"
    """How a mechanical stage sets up its initial stresses. "K0" derives them from the
    self weight and each soil's K0 (Kratos' `ApplyK0ProcedureProcess`); "gravity" solves
    for them under the self weight; "none" continues from the stage before. A flow stage
    has no stresses, so it has none."""
    time_integration: TimeIntegration = "static"
    """"static" solves for equilibrium; "dynamic" integrates in time -- inertia in a
    mechanical stage, a transient flow in a flow stage."""
    loading: Literal["Staged construction"] = "Staged construction"

    activate: list[Ident] = Field(default_factory=list)
    deactivate: list[Ident] = Field(default_factory=list)

    # The three the reference deck actually varies between its stages (see
    # plan sec 0.2). Their defaults are its initial stage's own values, so a stage that
    # says nothing solves the way that one does.
    reset_displacements: bool = False
    """Kratos' `reset_totals`: start this stage's displacements from zero. The reference
    turns it on when the wall is installed, so the wall's own deflection is measured
    from the ground it was built into rather than from the undisturbed state."""

    convergence_criterion: ConvergenceCriterion = "residual_criterion"
    """What Kratos measures to decide the stage has converged: one of
    `CONVERGENCE_CRITERIA` for its calculation type. A stage that names none -- one
    saved before it could be chosen, or made without it -- has its type's default, the
    residual criterion."""
    max_iterations: int = Field(default=int(solver.STAGE_DEFAULTS["max_iterations"]), gt=0)
    tolerated_error: float = Field(default=solver.STAGE_DEFAULTS["tolerated_error"], gt=0)
    """The convergence criterion's relative tolerance: Kratos'
    `<quantity>_relative_tolerance` for each quantity it measures."""
    absolute_tolerance: float = Field(
        default=solver.ABSOLUTE_TOLERANCES["residual_criterion"], gt=0)
    """Its absolute tolerance, `<quantity>_absolute_tolerance`. A stage that names none
    has its criterion's default (`ABSOLUTE_TOLERANCES`): the reference decks' 1e-9 for
    the residual criterion, 1e-12 for the displacement one, 1e-8 for the water pressure.
    A stage solved in several steps can need more than 1e-9: it reaches equilibrium in
    the first, after which every step starts from a round-off residual of 1e-9 to 1e-8
    that 1e-9 cannot be met below, and Kratos runs out of cycles with the model already
    at rest (an interface model, a 3D excavation, 2026-11-04)."""

    duration: float = Field(default=solver.STAGE_DEFAULTS["duration"], gt=0)
    """How long the stage lasts, in the project's unit of time (`core.model.units`): its
    deck's `end_time` minus its `start_time`. A static stage has no real clock, so the
    default is the one second every stage was before it could be set."""
    time_step: float = Field(default=solver.STAGE_DEFAULTS["time_step"], gt=0)
    """The solver's `time_step`, in the same unit: the stage is solved in
    `duration / time_step` steps. The default solves it in one."""

    solver_settings: dict[str, bool | int | float | str] = Field(default_factory=dict)
    """The expert solver settings this stage changed from their defaults, by name
    (`core.model.solver.SETTINGS`): the strategy, the linear solver, the time step
    control, the time scheme of a dynamic stage, the assembly. Every one it does not
    name has the default for its calculation type and time integration, so a stage
    that names none -- every stage saved before they could be set -- is solved as the
    reference decks are: by Newton-Raphson if it is mechanical. A setting that does not apply to the stage as it
    is now is kept, and neither shown nor written (`solver.resolve`)."""

    @field_validator("solver_settings")
    @classmethod
    def _known_solver_settings(cls, value: dict) -> dict:
        found = solver.problems(value)
        if found:
            raise ValueError("; ".join(found))
        return solver.normalised(value)

    @model_validator(mode="before")
    @classmethod
    def _old_calculation(cls, value: object) -> object:
        """A stage saved before 2026-11 names one of four calculations
        (`migration.stage_calculation`), and has a time interval in days
        (`migration.stage_time`) and no convergence criterion, which is then its
        calculation type's default. A stage that names no absolute tolerance has its
        criterion's (`ABSOLUTE_TOLERANCES`)."""
        if not isinstance(value, dict):
            return value
        value = migration.stage_time(migration.stage_calculation(value))
        if value.get("convergence_criterion") is None:
            calculation = value.get("calculation", "mechanical")
            if calculation in CONVERGENCE_CRITERIA:
                value = {**value,
                         "convergence_criterion": CONVERGENCE_CRITERIA[calculation][0]}
        if "absolute_tolerance" not in value \
                and value.get("convergence_criterion") in ABSOLUTE_TOLERANCES:
            value = {**value, "absolute_tolerance":
                     ABSOLUTE_TOLERANCES[value["convergence_criterion"]]}
        return value

    @model_validator(mode="after")
    def _step_fits(self) -> Stage:
        if self.time_step > self.duration:
            raise ValueError(
                f"stage {self.id!r} has a time step of {self.time_step:g}, longer than "
                f"its duration of {self.duration:g}: make the step at most the duration")
        return self

    @model_validator(mode="after")
    def _criterion_fits(self) -> Stage:
        allowed = CONVERGENCE_CRITERIA[self.calculation]
        if self.convergence_criterion not in allowed:
            raise ValueError(
                f"stage {self.id!r} is a {self.calculation} stage, which is not solved on "
                f"the {self.convergence_criterion}: use "
                f"{' or '.join(allowed)}")
        return self

    @model_validator(mode="after")
    def _stresses_are_mechanical(self) -> Stage:
        if self.calculation != "mechanical" and self.stress_initialisation != "none":
            raise ValueError(
                f"stage {self.id!r} is a {self.calculation} stage, which has no stresses "
                f"to initialise: set its stress initialisation to none, or make it a "
                "mechanical stage")
        return self

    @model_validator(mode="after")
    def _one_instruction_per_part(self) -> Stage:
        both = sorted(set(self.activate) & set(self.deactivate))
        if both:
            raise ValueError(
                f"stage {self.id!r} both activates and deactivates: {', '.join(both)}"
            )
        return self


Phase = Stage
"""Deprecated: the name Styx used before it took Kratos' word. Kept so old model
scripts and imports keep working."""


class MeshSettings(Base):
    element_size: float = Field(default=2.5, gt=0)
    order: Literal[1, 2] = 2
    algorithm_3d: Literal["delaunay", "frontal", "hxt"] = "delaunay"
    # Used when the project is 2D. Both are kept on the same settings object so
    # switching dimension does not discard the other dimension's choice.
    algorithm_2d: Literal["meshadapt", "auto", "delaunay", "frontal"] = "frontal"
    optimization: Literal["none", "gmsh", "netgen"] = "gmsh"
    smoothing: int = Field(default=10, ge=0, le=100)
    curvature_points: int = Field(default=16, ge=0, le=100)
    size_min_factor: float = Field(default=0.05, gt=0, le=1)
    second_order_linear: bool = True
    body_sizes: dict[Ident, PositiveSize] = Field(default_factory=dict)
    refinements: list[BoxRefinement | CylinderRefinement] = Field(default_factory=list)
    """Local size fields, finer than `element_size`, in the region each one covers.

    On the settings rather than on the mesh *request*, where this used to live, because
    a refinement is part of what a model is: a deep excavation wants a fine mesh around
    its wall whoever opens it and whichever button they press. Left on the request, it
    had to be re-typed for every mesh and could not travel in a saved project at all."""


class WaterUpdate(Base):
    """`PUT /api/project/water`: the project's water level, or `None` to remove it.
    Required rather than defaulted, so an empty body is an error instead of a quiet
    removal."""
    water: WaterLevel | None


class LayersUpdate(Base):
    layers: list[SoilLayer]
    materials: list[Material] | None = None
    # The plan extents, edited from the Selection explorer's Geometry rows. They ride
    # along so one request gets one validation of the resulting model.
    domain: Domain | None = None
    # The phreatic level and the fluid's specific weight, edited from the same
    # explorer. One object for the whole project, exactly like `domain`, and carried
    # here rather than on an endpoint of its own for the same reason: the water level
    # is validated against the model it belongs to, not on its own.
    #
    # It is not merely cosmetic. Every hydrostatic water pressure condition and normal
    # load with no level of its own is measured from `y` (`core.kratos.parameters.
    # _water_pressure`, `_normal_load`), the specific weight scales all of them, and
    # `core.kratos.materials` derives DENSITY_WATER from it.
    water: WaterLevel | None = None
    # Custom soil bodies, so reassigning one's material is validated against the
    # same library in the same request.
    custom_parts: list[CustomPart] | None = None


class MaterialsUpdate(Base):
    materials: list[Material] = Field(min_length=1)


class StructuresUpdate(Base):
    """The atomic Structure-mode write contract; anchors still follow.

    `loads` is required -- it is the original contract, and every client that writes
    structures already sends it. The collections added since are optional, and omitting
    one means "leave it alone" rather than "empty it": a client editing a load must not
    silently delete the sheet piles it never mentioned. Sending `[]` explicitly is how
    a collection is cleared.
    """
    loads: list[PointLoad | LineLoad | SurfaceLoad]
    beam_sections: list[BeamSection] | None = None
    panel_sections: list[PanelSection] | None = None
    # The same unions the project holds: one endpoint writes a 2D sheet pile, a 3D wall
    # panel and a 3D member, because they are one collection and one tree node, and a
    # client editing in either dimension sends the whole list back.
    beams: list[Beam | Panel | Member] | None = None
    anchor_sections: list[AnchorSection] | None = None
    anchors: list[Anchor | SpaceAnchor] | None = None
    interface_sections: list[InterfaceSection] | None = None
    interfaces: list[Interface] | None = None
    normal_loads: list[NormalLoad] | None = None


class ConditionsUpdate(Base):
    """The boundary conditions, replaced as one list
    (`core.session.replace_conditions`). Left out, they stay as they are."""
    boundary_conditions: list[BoundaryCondition] | None = None


class StagesUpdate(Base):
    """The construction sequence, replaced wholesale.

    Its own endpoint rather than a ride-along on `StructuresUpdate`, because a stage is
    the one collection that is *about* the others: `activate`/`deactivate` name part
    keys, so the list can only be validated against a model that has already settled.
    Sent together with a structure edit, which of the two the keys should be checked
    against would depend on the order they were applied in.

    Required rather than optional, and `[]` is meaningful: it is how a project goes
    back to being unstaged, which must export exactly the deck it exported before
    staged construction existed (plan sec 7.18).
    """
    stages: list[Stage]

    @model_validator(mode="before")
    @classmethod
    def _stages_were_phases(cls, value: object) -> object:
        """A client written before the rename sends `phases`."""
        return migration.rename_phases(value) if isinstance(value, dict) else value


PhasesUpdate = StagesUpdate
"""Deprecated alias of `StagesUpdate`."""


class UnitsUpdate(Base):
    unit_system: Literal["SI", "kN"]


class DimensionUpdate(Base):
    dimension: Literal[2, 3]
    # Omitted going to 2D, the Project validator resolves it to the middle of the
    # domain. Omitted going to 3D it is simply inert.
    section_offset: float | None = None


class BoxRefinement(Base):
    kind: Literal["box"]
    size: float = Field(gt=0)
    thickness: float = Field(default=0.0, ge=0)
    """The width of the band outside the box over which the element size grows from
    `size` back to the model's own. Zero -- the default, and what every refinement
    written before this field carried -- steps straight from one to the other, which is
    what a refinement drawn as a box means. A band is what turns a box around a
    structure into a graded mesh: fine where the answer is read, coarse where it is
    not, and no sudden change in element size in between."""
    x_min: float
    x_max: float
    z_min: float
    z_max: float
    y_min: float
    y_max: float

    @model_validator(mode="after")
    def _ordered(self) -> BoxRefinement:
        if self.x_max <= self.x_min or self.z_max <= self.z_min or self.y_max <= self.y_min:
            raise ValueError("box refinement extents must be strictly increasing")
        return self


class CylinderRefinement(Base):
    kind: Literal["cylinder"]
    size: float = Field(gt=0)
    x: float
    y: float
    z: float
    axis_x: float
    axis_y: float
    axis_z: float
    radius: float = Field(gt=0)

    @model_validator(mode="after")
    def _axis_has_length(self) -> CylinderRefinement:
        if self.axis_x == self.axis_y == self.axis_z == 0:
            raise ValueError("cylinder refinement axis must have non-zero length")
        return self


class MeshRequest(MeshSettings):
    volume_keys: list[Ident] | None = Field(default=None, min_length=1)


class ExportRequest(MeshRequest):
    """A mesh request that also produces a Kratos deck.

    Export meshes the project itself rather than reusing whatever `POST /api/mesh` last
    produced: the gmsh worker keeps one model and clears it per request, so the only
    mesh an export can trust is the one it made.
    """
    include_materials: bool = True


# ── Project ─────────────────────────────────────────────────────────────────

class Deck(Base):
    """A Kratos deck that already exists on disk, standing in for the parametric model.

    Set by `core.kratos.external_deck.deck_project` for a case that is written as a deck rather than
    built from layers -- a dike analysis, say, with twenty stages, three material sets
    and phreatic multi-lines, none of which this schema can say. The deck is shown as
    its own mesh and calculated as the files it is; nothing is exported. Every other
    field of a project carrying one is the empty site `templates.blank_project` is, there
    because the schema requires it.
    """
    directory: str
    """Absolute. The files the parameters name are read from here."""
    parameters: str = "ProjectParameters.json"
    """The orchestrator file, by name inside `directory`. It names everything else."""
    parts: list[str] = Field(default_factory=list)
    """The deck's parts that some stage computes on or loads, in the order the stages
    first name them -- what this project's stages switch on and off (`stageable_keys`).
    Read off the deck when it is opened, so that validating a project never has to."""


FULL_BUILD_BLOCKS = ("excavation", "wall", "struts", "anchor_rows", "piles", "wells")
"""The `Project` fields the full build (`layered_soil` false) reads, and needs given."""


class Project(Base):
    name: str = "Deep excavation — Rotterdam Zuid"

    layered_soil: bool = True
    """Build the soil out of the layer stack and whatever the user drew, rather than
    also raising the seeded demo structures.

    `True` takes `solid_model._build_layered_soil`: one box per layer across the whole domain,
    plus the drawn beams, anchors, interfaces and custom parts, and no pit cut unless
    the excavation is staged. `False` takes the full path, which additionally raises the
    seeded 3D wall ring, strut frame and pile group and cuts the excavation void.

    Named `simple_example` until the stage editor made it user-visible, which was the
    wrong name twice over: it is not about examples, and the models that set it are not
    simple -- a staged model script sets it. The old spelling is still accepted on the
    way in (see `_reconcile_layered_soil`); nothing writes it any more.
    """

    dimension: Literal[2, 3] = 3
    """3 builds the solid model. 2 builds a planar section through it."""

    unit_system: Literal["SI", "kN"] = units.DEFAULT
    """The consistent set every value is in, and the deck and its results with it:
    "SI" (N, m, kg, s) or "kN" (kN, m, t, s). See `core/model/units.py`. Changed only through
    `PATCH /api/project/units`, which converts the values with it."""

    section_offset: float | None = None
    """Where the section is taken, as a world z. A 2D model is always the x-y plane,
    cut at a constant z. Resolved to the middle of the domain by the validator when the
    project is 2D and this is unset, so everything downstream -- geometry, mesh,
    viewport -- reads one authoritative number instead of each deriving its own."""

    domain: Domain
    materials: list[Material]
    layers: list[SoilLayer]
    excavation: Excavation | None = None
    """The pit, or `None` for a model that digs none. A layered model reads it only when
    it has two or more levels (`pit_levels`); the full build needs it always."""
    # The seeded demo's own structures, which only the full build raises
    # (`solid_model._build_solids`). `None` in a model that has none of them; the full
    # build needs all of them, and the validator says so.
    wall: Wall | None = None
    struts: Struts | None = None
    anchor_rows: AnchorRows | None = None
    piles: Piles | None = None
    loads:list[PointLoad | LineLoad | SurfaceLoad] = Field(default_factory=list)
    beam_sections: list[BeamSection] = Field(default_factory=list)
    panel_sections: list[PanelSection] = Field(default_factory=list)
    # One collection per family, holding every kind of it: a 2D sheet pile, a 3D wall
    # panel and a 3D member are all "the piles" to the tree, the part-key namespace and
    # the structures patch, and keeping them in one list is what lets those stay as they
    # are. `loads[]` has held three kinds this way since it was written.
    beams: list[Beam | Panel | Member] = Field(default_factory=list)
    anchor_sections: list[AnchorSection] = Field(default_factory=list)
    anchors: list[Anchor | SpaceAnchor] = Field(default_factory=list)
    # Interfaces are their own collection rather than a flag on the beam: one sheet pile
    # can carry a different contact on each face, and a free interface has no beam at
    # all. `part_keys()` gives each one a key beside the structures, so the tree, the
    # viewport and the exporter name it the same way they name a pile.
    interface_sections: list[InterfaceSection] = Field(default_factory=list)
    interfaces: list[Interface] = Field(default_factory=list)
    interface_sides: Literal["screen"] = "screen"
    """How the document reads an interface's `side`: as the face on the screen. A
    document without it was saved before 2026-10-25 and read it walking the line; its
    one-side interfaces are converted when it loads (`migration.screen_sides`)."""
    # Its own collection, not folded into `loads[]`: a normal load is dimension-native
    # like a free interface (an arbitrary polyline, no 3D translation), not a
    # translated x/y vector like the three kinds `loads[]` already holds.
    normal_loads: list[NormalLoad] = Field(default_factory=list)
    wells: Wells | None = None
    water: WaterLevel | None = None
    """The phreatic level, or `None` for a model without one -- which is what a new
    project starts as. A model is not born with a water table at somebody else's depth;
    it has one when its author sets one. The level fixes no pressure by itself: it is
    the level a new hydrostatic `WaterPressureCondition` or `NormalLoad` is given
    (`core.model.drafts`), which the record then keeps as its own. Only a hydrostatic
    normal load saved without a level still reads it at export."""
    boundary_conditions: list[BoundaryCondition] = Field(
        default_factory=standard_conditions)
    """The conditions the user prescribes on the model's boundaries and soil. The deck
    holds these and no others: a project with no water pressure condition fixes no water
    pressure, and one with no displacement condition holds nothing still. Left out --
    every project saved before the conditions existed, and a new one -- it is the
    standard supports (`standard_conditions`), which are what the export always wrote;
    given, even empty, it is exactly what it lists."""
    mesh: MeshSettings = Field(default_factory=MeshSettings)
    custom_parts: list[CustomPart] = Field(default_factory=list)
    stages: list[Stage] = Field(default_factory=list)
    """The construction sequence, in creation order. Empty means an unstaged project --
    every project written before staged construction -- which exports exactly what it
    always did. That is the compatibility contract; see `test_export_golden.py`."""
    deck: Deck | None = None
    """A deck this project *is*, rather than one it exports. See `Deck`."""

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_units(cls, value: object) -> object:
        """A project saved before the unit system existed, converted once into the
        current shape in SI, with the numbers the old exporter wrote (`core/model/migration.py`).
        A project saved before 2026-10 also calls its stages `phases`, and one saved
        before 2026-10-24 has boreholes (`migration.drop_boreholes`), and one saved
        before 2026-10-25 reads an interface's side walking its line
        (`migration.screen_sides`), and one saved before 2026-11-03 switches gravity
        itself (`migration.drop_gravity`), and one saved before 2026-11 has flow stages
        with no absolute tolerance (`migration.flow_tolerance`)."""
        if isinstance(value, dict):
            value = migration.drop_gravity(migration.rename_phases(value))
        if migration.is_legacy(value):
            value = migration.migrate(value)
        elif isinstance(value, dict):
            value = migration.migrate_records(value)
        if not isinstance(value, dict):
            return value
        return migration.flow_tolerance(
            migration.screen_sides(migration.drop_boreholes(value)))

    @model_serializer(mode="wrap")
    def _leave_out_absent_blocks(self, handler: SerializerFunctionWrapHandler) -> dict:
        """A model without a pit or the demo's structures says nothing about them: the
        saved file, the API's project and `model_dump` leave the `None` blocks out,
        so the GUI's Save and `kratos-cli save` write the same file."""
        data = handler(self)
        return {key: value for key, value in data.items()
                if value is not None or key not in FULL_BUILD_BLOCKS}

    @model_validator(mode="before")
    @classmethod
    def _drop_derived(cls, value: object) -> object:
        """Ignore fields the project publishes but does not accept.

        `soil_body_keys` and `soil_body_labels` are computed from the layers and the
        excavation, and go out with every project so the viewport knows which bodies
        exist and the Model explorer knows what to call them. A client that edits a
        project and PUTs it back sends the whole document, these fields included, and
        `extra: forbid` would refuse it over values the server itself produced.
        """
        derived = ("soil_body_keys", "soil_body_labels", "stageable_parts",
                   "model_strategies", "flow_strategies")
        if not isinstance(value, dict) or not any(k in value for k in derived):
            return value
        return {k: v for k, v in value.items() if k not in derived}

    @model_validator(mode="before")
    @classmethod
    def _reconcile_layered_soil(cls, value: object) -> object:
        """Accept `simple_example`, the name `layered_soil` carried until sec 7.14.

        Every project file written before the rename spells it the old way, and a saved
        project is the one thing this application cannot re-derive -- so the old key is
        read for good rather than for a deprecation window. `extra: forbid` is what
        makes this a validator rather than a plain `alias`: the key has to be taken out
        of the payload, not merely mapped, or an old file is refused over the very field
        being migrated.

        Both present and disagreeing is refused. Which one the caller meant to edit is
        not knowable from the payload -- the same reasoning, and the same answer, as
        `Excavation._reconcile_floor_and_levels`.
        """
        if not isinstance(value, dict) or "simple_example" not in value:
            return value
        migrated = dict(value)
        legacy = migrated.pop("simple_example")
        current = migrated.get("layered_soil")
        if current is not None and bool(current) != bool(legacy):
            raise ValueError(
                f"layered_soil ({current}) and its old name simple_example ({legacy}) "
                f"disagree; send one of them"
            )
        migrated["layered_soil"] = legacy
        return migrated

    @model_validator(mode="before")
    @classmethod
    def _migrate_single_load(cls, value: object) -> object:
        """Accept old load records and remove the hidden out-of-plane 2D data."""
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        # `anchors` used to be the aggregate row block and is now the collection of
        # individual anchors. A saved project carries the block; move it across rather
        # than refusing to open.
        rows = migrated.get("anchors")
        if isinstance(rows, dict):
            migrated.setdefault("anchor_rows", rows)
            migrated["anchors"] = []
        if "load" in migrated and "loads" not in migrated:
            legacy = dict(migrated.pop("load"))
            magnitude = legacy.pop("magnitude")
            legacy.update({
                "id": "load",
                "name": "SurfaceLoad_1",
                "components": (0.0, -magnitude, 0.0),
                "distribution": "Uniform",
                "active": True,
            })
            migrated["loads"] = [legacy]

        normalised = []
        for raw in migrated.get("loads", []):
            if not isinstance(raw, dict):
                normalised.append(raw)
                continue
            load = dict(raw)
            components = load.get("components", ())
            if load.get("kind") == "point":
                load.pop("z", None)
                if len(components) == 3:
                    load["components"] = (components[0], components[1])
            elif (migrated.get("dimension") == 2
                  and load.get("name", "").startswith("LineLoad_")
                  and load.get("kind", "surface") == "surface"):
                load = {
                    "id": load["id"], "name": load["name"], "kind": "line",
                    "x0": load["x0"], "x1": load["x1"],
                    "y": migrated["domain"]["y_top"],
                    "thickness": load.get("thickness", 0.15),
                    "components": (components[0], components[1]),
                    "distribution": load.get("distribution", "Uniform"),
                    "active": load.get("active", True),
                }
            normalised.append(load)
        migrated["loads"] = normalised
        return migrated

    @model_validator(mode="after")
    def _water_for_hydrostatic_loads(self) -> Project:
        """A hydrostatic normal load with no level of its own takes `water`'s at export
        time. With no water level either there is nothing to derive it from, and quietly
        writing zero would be a wall with no water against it."""
        if self.water is None:
            for load in self.normal_loads:
                if (load.fluid_pressure_type == "Hydrostatic"
                        and load.reference_coordinate is None):
                    raise ValueError(
                        f"normal load {load.name!r} is hydrostatic, which needs a water "
                        "level to measure its pressure from; give it one, set the "
                        "project's, or make the load uniform"
                    )
        return self

    @model_validator(mode="after")
    def _soil_laws_follow_the_dimension(self) -> Project:
        """A soil model's law in the project's dimension: its counterpart when the
        project is the other dimension -- however the dimension came to change -- and
        its current name when it carries an old one (`GeoMohrCoulombWithTensionCutOff2D`,
        which Kratos still registers but will remove). Any other law is the user's, and
        is left exactly as typed."""
        for material in self.materials:
            material.constitutive_law = soil_models.law_in(material.constitutive_law,
                                                           self.dimension)
        return self

    @property
    def water_specific_weight(self) -> float:
        """The water's specific weight in the project's units: the project's own, or
        10 kN/m3 in its system -- a dry model's materials still describe water."""
        if self.water is not None and self.water.specific_weight is not None:
            return self.water.specific_weight
        return units.from_si(WATER_SPECIFIC_WEIGHT_SI, units.SPECIFIC_WEIGHT,
                             self.unit_system)

    @model_validator(mode="after")
    def _cross_references(self) -> Project:
        _reject_duplicates([m.id for m in self.materials], "material")
        _reject_duplicates([l.id for l in self.layers], "layer")
        _reject_duplicates([p.key for p in self.custom_parts], "custom_part")
        _reject_duplicates([load.id for load in self.loads], "load")
        _reject_duplicates([s.id for s in self.interface_sections], "interface_section")
        _reject_duplicates([i.id for i in self.interfaces], "interface")
        _reject_duplicates([n.id for n in self.normal_loads], "normal_load")
        _reject_duplicates([c.id for c in self.boundary_conditions], "boundary condition")
        # A condition on a line is a gmsh physical group of its own, named by its id, in
        # the namespace the parts' groups are in -- and a water pressure condition is a
        # key a stage names, in the namespace of the parts and loads.
        parts = set(self._staged_parts_and_loads()) | {"excavation", "water"}
        collisions = sorted(c.id for c in self.boundary_conditions if c.id in parts)
        if collisions:
            raise ValueError("boundary condition id collides with an existing model part "
                             "key: " + ", ".join(collisions))
        soil = self.soil_part_keys()
        for condition in self.boundary_conditions:
            if condition.on == "part" and condition.part not in soil:
                raise ValueError(
                    f"boundary condition {condition.id!r} is on part {condition.part!r}, "
                    "which is not a soil part of this project; the soil parts are "
                    + (", ".join(soil) or "none"))

        # Interfaces are the one collection whose references are checked here rather
        # than left to blow up in the exporter: an interface names a section *and* a
        # structure, and a pile deleted out from under one would otherwise mesh into
        # a contact against nothing.
        sections = {s.id for s in self.interface_sections}
        piles = {beam.id for beam in self.sheet_piles}
        for interface in self.interfaces:
            if interface.section not in sections:
                raise ValueError(
                    f"interface {interface.id!r} references unknown interface section "
                    f"{interface.section!r}"
                )
            if interface.structure is not None and interface.structure not in piles:
                raise ValueError(
                    f"interface {interface.id!r} follows {interface.structure!r}, which "
                    "is not a sheet pile in this project"
                )
        self._check_interface_lines()
        _reject_duplicates([s.id for s in self.beam_sections], "beam section")
        _reject_duplicates([s.id for s in self.panel_sections], "panel section")
        # One id namespace across all three pile kinds: they share a collection, a
        # part-key namespace and a tree node, so a panel named after a sheet pile is
        # the same collision two sheet piles would be.
        _reject_duplicates([beam.id for beam in self.beams], "beam")
        _reject_duplicates([s.id for s in self.anchor_sections], "anchor section")
        _reject_duplicates([a.id for a in self.anchors], "anchor")

        occupied = {
            "excavation", "wall", "struts", "anchors", "piles", "water", "wells",
        } | set(self.soil_body_keys) | {part.key for part in self.custom_parts}
        collisions = sorted(load.id for load in self.loads if load.id in occupied)
        if collisions:
            raise ValueError(
                "load id collides with an existing model part key: " + ", ".join(collisions)
            )
        # Beams share the one part-key namespace with the loads created before them, so
        # the check has to see both -- a sheet pile named after a load is as broken as
        # one named after the wall.
        occupied |= {load.id for load in self.loads}
        collisions = sorted(beam.id for beam in self.beams if beam.id in occupied)
        if collisions:
            raise ValueError(
                "beam id collides with an existing model part key: " + ", ".join(collisions)
            )
        occupied |= {beam.id for beam in self.beams}
        collisions = sorted(a.id for a in self.anchors if a.id in occupied)
        if collisions:
            raise ValueError(
                "anchor id collides with an existing model part key: " + ", ".join(collisions)
            )

        self._check_stages()

        known = {m.id for m in self.materials}
        for layer in self.layers:
            if layer.mat not in known:
                raise ValueError(f"layer {layer.id} references unknown material {layer.mat!r}")
        for part in self.custom_parts:
            if part.mat is not None and part.mat not in known:
                raise ValueError(
                    f"custom part {part.key} references unknown material {part.mat!r}"
                )
        # Structures are placed against the *extent*, not the domain: a load or a pile
        # standing on a drawn embankment above `y_top` is on model geometry, and the
        # domain is only the layer block. See `Project.extent`.
        extent = self.extent()
        for load in self.loads:
            # A point load may also sit on the part of a pile above the ground, which
            # carries it down into the soil (`meshing.loaded_elements` puts it on the
            # pile's node there). Only a live pile: an inactive one is not meshed.
            if load.kind == "point" and not (
                extent.x0 <= load.x <= extent.x1
                and extent.y_bottom <= load.y <= extent.y_top
            ) and not any(
                point_on_polyline((load.x, load.y), beam.points, ATTACHMENT_TOLERANCE)
                for beam in self.sheet_piles if beam.active
            ):
                raise ValueError(
                    f"point load {load.id!r} lies outside the domain; above the ground "
                    "it has to be on a sheet pile"
                )
            if load.kind == "line" and not (
                extent.x0 <= load.x0 < load.x1 <= extent.x1
                and extent.y_bottom <= load.y <= extent.y_top
            ):
                raise ValueError(f"line load {load.id!r} lies outside the domain")

        tendons = {s.id for s in self.anchor_sections}
        for anchor in self.anchors:
            if anchor.section not in tendons:
                raise ValueError(
                    f"anchor {anchor.id} references unknown anchor section "
                    f"{anchor.section!r}"
                )
        for anchor in self.plane_anchors:
            # Its top is free, as a pile's is: a strut may hang from the part of a pile
            # above the ground, and its tail is a fixed point that no soil has to hold.
            for x, y in (anchor.head, anchor.tail):
                if not (extent.x0 <= x <= extent.x1 and extent.y_bottom <= y):
                    raise ValueError(
                        f"anchor {anchor.id!r} lies outside the domain at ({x}, {y})"
                    )
            # The head becomes a node the beam shares, so it has to be on a live pile.
            # Only checked while the anchor is active: deleting a pile under a disabled
            # anchor must not make the saved project unopenable.
            if anchor.active and not any(
                point_on_polyline(anchor.head, beam.points, ATTACHMENT_TOLERANCE)
                for beam in self.sheet_piles if beam.active
            ):
                raise ValueError(
                    f"anchor {anchor.id!r} head at {anchor.head} is not on a sheet pile"
                )
        for anchor in self.space_anchors:
            for point in (anchor.head, anchor.tail):
                if not extent.contains(*point):
                    raise ValueError(
                        f"anchor {anchor.id!r} lies outside the domain at {point}"
                    )
            # The 3D head hangs from whatever structure is there: the swept surface of a
            # panel, or the polyline of a member. Same rule as 2D, two shapes to test.
            if anchor.active and not (
                any(point_on_panel(anchor.head, panel, ATTACHMENT_TOLERANCE)
                    for panel in self.panels if panel.active)
                or any(point_on_polyline(anchor.head, member.points, ATTACHMENT_TOLERANCE)
                       for member in self.members if member.active)
            ):
                raise ValueError(
                    f"anchor {anchor.id!r} head at {anchor.head} is not on a wall or member"
                )

        sections = {s.id for s in self.beam_sections}
        for beam in self.sheet_piles:
            if beam.section not in sections:
                raise ValueError(
                    f"beam {beam.id} references unknown beam section {beam.section!r}"
                )
            # A pile may stand out above the ground -- a load at its head is carried
            # down it into the soil, and `solid_model._embed_beams` keeps that part --
            # so its top is not held to the model. Its sides and toe are, and some of
            # it has to be in the ground, or nothing holds it.
            for x, y in beam.points:
                if not (extent.x0 <= x <= extent.x1 and extent.y_bottom <= y):
                    raise ValueError(
                        f"beam {beam.id!r} lies outside the domain at ({x}, {y})"
                    )
            if min(y for _, y in beam.points) >= extent.y_top:
                raise ValueError(
                    f"beam {beam.id!r} lies wholly above the ground; part of it has to "
                    "be in the soil"
                )
        # A member stands in the same profile library the sheet piles use; a panel has
        # its own, because a thickness is not an area and an inertia.
        for member in self.members:
            if member.section not in sections:
                raise ValueError(
                    f"beam {member.id} references unknown beam section {member.section!r}"
                )
            for point in member.points:
                if not extent.contains(*point):
                    raise ValueError(
                        f"member {member.id!r} lies outside the domain at {point}"
                    )
        wall_sections = {s.id for s in self.panel_sections}
        for panel in self.panels:
            if panel.section not in wall_sections:
                raise ValueError(
                    f"panel {panel.id} references unknown panel section {panel.section!r}"
                )
            for x, z in panel.footprint:
                for y in (panel.y_top, panel.y_toe):
                    if not extent.contains(x, y, z):
                        raise ValueError(
                            f"panel {panel.id!r} lies outside the domain at ({x}, {y}, {z})"
                        )
        validate_layer_stack(self.layers)

        if self.dimension == 2:
            low, high = self.section_bounds()
            if self.section_offset is None:
                # A section through a symmetric excavation belongs on its axis.
                object.__setattr__(self, "section_offset", (low + high) / 2)
            elif not (low < self.section_offset < high):
                # Strictly inside: a plane flush with a domain face grazes the outside
                # of the solid and cuts a zero-area or knife-edge face out of it.
                raise ValueError(
                    f"section_offset {self.section_offset} must lie strictly inside the "
                    f"domain along {self.section_normal()} ({low}, {high})"
                )
        # In 3D these are inert and deliberately unchecked: editing the domain while in
        # 3D must not fail on a stale section plane the user cannot even see.

        if not self.layered_soil:
            missing = [name for name in FULL_BUILD_BLOCKS if getattr(self, name) is None]
            if missing:
                raise ValueError(
                    "a project with layered_soil false builds the seeded demo pit, and "
                    f"needs {', '.join(missing)}")
            e = self.pit()
            if not self.domain.contains_plan(e.x0, e.x1, e.z0, e.z1):
                raise ValueError("excavation extends outside the domain in plan")
            # Every lift, not only the last: an intermediate level above the ground or
            # below the model is as unbuildable as a floor there, and saying so here
            # means the geometry step never has to check.
            if not all(self.domain.y_bottom < level < self.domain.y_top
                       for level in e.levels):
                raise ValueError(
                    "every excavation level must lie inside the domain depth range")
        return self

    def section_normal(self) -> str:
        """The axis the section plane is normal to. Always z: 2D is the x-y plane."""
        return "z"

    def extent(self) -> Domain:
        """How far the model reaches: the domain grown to cover every custom part.

        `Domain` is the block the soil layers fill, and a drawn or imported part
        is not held to it -- an embankment stands above `y_top`. Anything asking "may a
        structure be here?" wants this, not the domain: a load on a custom layer above
        ground stands on model geometry, and refusing it as "outside the domain" is the
        bug this exists to fix. `solid_model.SECTION_PAD` measures the section the same way,
        from the built solids rather than the declared box.

        Parts with no recorded box contribute nothing, so an older project is unchanged.
        """
        boxes = [p.bbox for p in self.custom_parts if p.bbox is not None]
        if not boxes:
            return self.domain
        d = self.domain
        return Domain(
            x0=min([d.x0] + [b[0] for b in boxes]),
            y_bottom=min([d.y_bottom] + [b[1] for b in boxes]),
            z0=min([d.z0] + [b[2] for b in boxes]),
            x1=max([d.x1] + [b[3] for b in boxes]),
            y_top=max([d.y_top] + [b[4] for b in boxes]),
            z1=max([d.z1] + [b[5] for b in boxes]),
        )

    def ground_y(self) -> float:
        """The elevation a surface load lies on: the top of the model.

        A `SurfaceLoad` carries no level of its own -- it sits on the ground surface --
        and
        that used to be read as `domain.y_top`. But the domain is only the block the
        layers fill, so once a drawn embankment stands above it, `domain.y_top`
        is buried inside the fill rather than on top of it. `extent` knows where the
        model actually ends; everything that places or reads a surface load asks here,
        so the build, the exporter and `core/model/load_translation.py` agree on one answer.
        """
        return self.extent().y_top

    def elevation_of(self, load: PointLoad | LineLoad | SurfaceLoad) -> float:
        """Where a load lies, whichever kind it is.

        A point or line load carries its own y. A surface load may leave it unset,
        which means the top of the model -- the reading every such load had before the
        field existed.
        """
        if load.kind == "surface":
            return self.ground_y() if load.y is None else load.y
        return load.y

    def section_bounds(self) -> tuple[float, float]:
        """How far the section may travel: the domain's out-of-plane depth."""
        return (self.domain.z0, self.domain.z1)

    def cut_at(self) -> float:
        """Where the section plane sits, resolved even when nothing has resolved it.

        A 3D project never runs the validator that fills `section_offset` in (only
        dimension 2 does), yet the solid model still needs the plane: it is where a
        sheet pile, an anchor and a 2D load are built. Falling back to the mid-plane
        picks exactly what switching to 2D would pick, so a structure does not move
        when the mode changes.
        """
        low, high = self.section_bounds()
        return self.section_offset if self.section_offset is not None else (low + high) / 2

    def loads_for(self, dimension: int) -> list[PointLoad | LineLoad | SurfaceLoad]:
        """The loads this dimension builds, in `loads[]` order.

        A translated pair holds two records for one load, so exactly one of them is the
        model's or the load is applied twice. The section builds its own kinds; the
        solid model builds the surface loads, plus the 2D loads nothing was derived
        from -- a point load, or a line load below `y_top`, which have no surface form
        and are carried at the section plane instead (`solid_model._load_footprint_tools`).
        """
        if dimension == 2:
            # A pad whose footprint misses the section plane does not load the section;
            # its 2D half is kept, so moving the plane onto it brings it back.
            cut = self.cut_at()
            clear = {load.id: load.derived_from for load in self.loads
                     if load.kind == "surface"
                     and not load.z0 - 1e-9 <= cut <= load.z1 + 1e-9}
            off = set(clear.values()) | {load.id for load in self.loads
                                         if load.derived_from in clear}
            return [load for load in self.loads
                    if load.kind != "surface" and load.id not in off]
        # Both ends of every pair, so a 2D half is recognised whether it was the record
        # the user authored or the one translated from a surface load.
        paired = {id for load in self.loads if load.derived_from is not None
                  for id in (load.id, load.derived_from)}
        return [load for load in self.loads
                if load.kind == "surface" or load.id not in paired]

    def material(self, mat_id: str) -> Material:
        return next(m for m in self.materials if m.id == mat_id)

    def pit_levels(self) -> list[float]:
        """The levels the pit is dug to, shallowest first; none without an excavation."""
        return list(self.excavation.levels) if self.excavation is not None else []

    def pit(self) -> Excavation:
        """The excavation, for code that runs only when there is one: the full build,
        and a pit dug in lifts."""
        if self.excavation is None:
            raise ValueError("the project has no excavation")
        return self.excavation

    def beam_section(self, section_id: str) -> BeamSection:
        return next(s for s in self.beam_sections if s.id == section_id)

    def panel_section(self, section_id: str) -> PanelSection:
        return next(s for s in self.panel_sections if s.id == section_id)

    def anchor_section(self, section_id: str) -> AnchorSection:
        return next(s for s in self.anchor_sections if s.id == section_id)

    def interface_section(self, section_id: str) -> InterfaceSection:
        return next(s for s in self.interface_sections if s.id == section_id)

    def interface_path(self, interface: Interface) -> list[tuple[float, float]]:
        """The polyline `interface` runs along: its own points, the whole of its pile,
        or the part of the pile between From and To. In the pile's own order, so the
        walking sides of the part are the pile's."""
        if interface.structure is None:
            return [(x, y) for x, y in interface.points or []]
        pile = next(b for b in self.sheet_piles if b.id == interface.structure)
        line = [(x, y) for x, y in pile.points]
        if interface.stretch is None:
            return line
        start, end = (polylines.nearest(line, point)[2] for point in interface.stretch)
        return polylines.between(line, start, end)

    def _check_interface_lines(self) -> None:
        """Each interface fits the line it runs along, and no two hold the same face.

        Called from `_cross_references`, once each interface's pile is known to exist.
        Also brings `side` to the words of its line (left and right on a steep line,
        below and above on a flat one) and saves a stretch that reaches from one end of
        the pile to the other as None, the whole pile, so the record keeps one form.
        """
        piles = {beam.id: beam for beam in self.sheet_piles}
        for interface in self.interfaces:
            if interface.stretch is not None:
                pile = piles[interface.structure or ""]
                line = [(x, y) for x, y in pile.points]
                for label, point in zip(("From", "To"), interface.stretch):
                    away = polylines.nearest(line, point)[1]
                    if away > STRETCH_TOLERANCE:
                        raise ValueError(
                            f"{interface.name}: {label} {_xy(point)} is {away:.3g} m from "
                            f"{pile.name}; From and To are points on the pile"
                        )
                if all(min(math.dist(point, end) for end in (line[0], line[-1]))
                       <= STRETCH_TOLERANCE for point in interface.stretch):
                    interface.stretch = None
            if interface.side != "both":
                first, second = polylines.faces(self.interface_path(interface))
                interface.side = (first if interface.side in ("left", "below")
                                  else second)
        self._no_double_contact(piles)
        self._no_free_line_along_a_pile()

    def _no_double_contact(self, piles: dict[str, Beam]) -> None:
        """Two interfaces may not hold the same face of one pile over the same length:
        the soil there would be split twice, with two contacts between one pair of
        faces. A switched-off interface holds nothing, so it may stand in for another
        until it is switched on."""
        held: list[tuple[Interface, set[str], float, float]] = []
        for interface in self.interfaces:
            if interface.structure is None or not interface.active:
                continue
            line = [(x, y) for x, y in piles[interface.structure].points]
            path = self.interface_path(interface)
            start, end = sorted(polylines.nearest(line, point)[2]
                                for point in (path[0], path[-1]))
            faces: set[str] = (set(polylines.faces(path)) if interface.side == "both"
                               else {interface.side})
            for other, other_faces, low, high in held:
                if other.structure != interface.structure:
                    continue
                common = sorted(faces & other_faces, key=FACE_ORDER.index)
                over = (max(start, low), min(end, high))
                if not common or over[1] - over[0] <= STRETCH_TOLERANCE:
                    continue
                part = polylines.between(line, *over)
                axis, index = ("y", 1) if polylines.is_steep(line) else ("x", 0)
                raise ValueError(
                    f"{interface.name} and {other.name} both hold the {common[0]} face of "
                    f"{piles[interface.structure].name} between {axis} {part[0][index]:g} "
                    f"and {axis} {part[-1][index]:g}"
                )
            held.append((interface, faces, start, end))

    def _no_free_line_along_a_pile(self) -> None:
        """A free line that runs along a live pile would split the soil from the soil
        there, with the pile still welded to one of them and no ties while it is not
        installed: an interface on the pile is what is meant."""
        for interface in self.interfaces:
            if interface.structure is not None:
                continue
            for pile in self.sheet_piles:
                if pile.active and _runs_along(interface.points or [], pile.points):
                    raise ValueError(
                        f"{interface.name} runs along {pile.name}. Put it on {pile.name} "
                        "instead (Along in the window, --structure on the command line) "
                        "and set From and To"
                    )

    @property
    def active_interfaces(self) -> list[Interface]:
        """The interfaces this model actually builds: 2D only, and only those whose
        structure is itself active. A contact against a switched-off pile is not a
        contact, and silently exporting one would weld the soil back together."""
        if self.dimension != 2:
            return []
        live = {beam.id for beam in self.sheet_piles if beam.active}
        return [i for i in self.interfaces
                if i.active and (i.structure is None or i.structure in live)]

    @property
    def active_normal_loads(self) -> list[NormalLoad]:
        """The normal loads this model actually builds: 2D only, like `active_interfaces`."""
        if self.dimension != 2:
            return []
        return [n for n in self.normal_loads if n.active]

    @property
    def drawn_conditions(self) -> list[AnyCondition]:
        """The active boundary conditions on a drawn line or point, which the section
        embeds: 2D only, like `active_normal_loads`."""
        if self.dimension != 2:
            return []
        return [c for c in self.boundary_conditions
                if c.active and c.on in ("line", "point")]

    # The kind-wise views of the two mixed collections. Every consumer wants one
    # dimension's worth at a time -- the 2D build, the 3D build, the exporter's element
    # tables -- and `isinstance` scattered through all of them would say much less about
    # why the split is there.
    @property
    def sheet_piles(self) -> list[Beam]:
        """The 2D sheet piles: in-plane polylines, built in a section only."""
        return [b for b in self.beams if isinstance(b, Beam)]

    @property
    def panels(self) -> list[Panel]:
        """The 3D walls: plan footprints swept between two levels, meshed as shells."""
        return [b for b in self.beams if isinstance(b, Panel)]

    @property
    def members(self) -> list[Member]:
        """The 3D 1D members: bored piles, king posts and struts."""
        return [b for b in self.beams if isinstance(b, Member)]

    @property
    def plane_anchors(self) -> list[Anchor]:
        return [a for a in self.anchors if isinstance(a, Anchor)]

    @property
    def space_anchors(self) -> list[SpaceAnchor]:
        return [a for a in self.anchors if isinstance(a, SpaceAnchor)]

    def structures_for(self, dimension: int) -> list[Beam | Panel | Member]:
        """The structures this dimension builds, in `beams[]` order.

        A translated pair holds a sheet pile and a wall panel for one wall, so exactly
        one of them is the model's or the wall is built twice. The section builds its
        own kind; the solid model builds the panels and members, plus the piles nothing
        was translated from -- a raking or stepped pile has no panel form and is swept
        onto the section plane instead (`solid_model._section_sweeps`).
        """
        if dimension == 2:
            return [b for b in self.beams if isinstance(b, Beam)]
        paired = {i for b in self.beams if b.derived_from is not None
                  for i in (b.id, b.derived_from)}
        return [b for b in self.beams
                if isinstance(b, (Panel, Member)) or b.id not in paired]

    def structures_3d(self) -> list[Panel | Member]:
        """Everything a 3D model builds structure from, in `beams[]` order."""
        return [b for b in self.beams if isinstance(b, (Panel, Member))]

    def _check_stages(self) -> None:
        """The construction sequence is a tree of real stages over real parts.

        Structure only. Whether the tree can be flattened into the one sequence Kratos
        runs is the export's question, not this one -- a branch is a legitimate thing to
        have half-built in the editor, and refusing it here would make it impossible to
        type (see `Stage`).
        """
        if not self.stages:
            return
        _reject_duplicates([stage.id for stage in self.stages], "stage")

        ids = {stage.id for stage in self.stages}
        roots = [stage.id for stage in self.stages if stage.parent is None]
        if len(roots) != 1:
            raise ValueError(
                "a construction sequence needs exactly one root stage -- the one that "
                f"starts from the model as built -- but {len(roots)} have no parent"
            )
        for stage in self.stages:
            if stage.parent is not None and stage.parent not in ids:
                raise ValueError(
                    f"stage {stage.id!r} starts from nowhere: there is no stage "
                    f"{stage.parent!r}"
                )
            if stage.parent == stage.id:
                raise ValueError(f"stage {stage.id!r} starts from itself")

        # Every stage has to reach the root by following parents. Anything that does not
        # is in a cycle, which would make `core.model.stages` walk for ever.
        parents = {stage.id: stage.parent for stage in self.stages}
        for start in ids:
            seen: set[str] = set()
            at: str | None = start
            while at is not None:
                if at in seen:
                    raise ValueError(
                        f"stages form a cycle through {at!r}; every stage must lead "
                        "back to the one that starts from the model as built"
                    )
                seen.add(at)
                at = parents[at]

        # A stage may only name parts the model actually has. Caught here rather than at
        # export because a stage naming a deleted structure is a modelling mistake the
        # user can fix, and finding it only when Calculate is pressed would be late.
        parts = set(self.stageable_keys())
        for stage in self.stages:
            unknown = sorted({key for key in stage.activate + stage.deactivate
                              if key not in parts})
            if unknown:
                raise ValueError(
                    f"stage {stage.id!r} names no such part: {', '.join(unknown)}"
                )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def soil_body_keys(self) -> list[str]:
        """The part keys of `soil_bodies`, published with the project.

        Read by the viewport, which needs to know which soil bodies exist in order to
        show them and cannot work it out for itself: deriving the lift split in the
        browser would be a second implementation of `soil_bodies` to keep in step with
        this one. It is published, not accepted -- `_drop_derived` removes it on the way
        back in -- so a client that echoes the project it was given is not rejected for
        a field it did not invent.
        """
        return [key for key, *_ in self.soil_bodies()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def soil_body_labels(self) -> dict[str, str]:
        """What to call each soil body in front of a user, keyed by part key.

        The Model explorer lists bodies, and three keys differing only by a `__lift2`
        suffix are not something to show anyone. A body that is the whole of its layer
        is just the layer's name; one that is part of a staged layer says which part.

        Published beside `soil_body_keys` rather than derived in the browser from the
        key's suffix, for the same reason: the split is this class's to describe.
        """
        names = {f"soil_{layer.id}": layer.name for layer in self.layers}
        labels: dict[str, str] = {}
        for key, *_ in self.soil_bodies():
            stem, _, suffix = key.partition("__")
            name = names.get(stem, stem)
            if not suffix:
                labels[key] = name
            elif suffix.startswith("lift"):
                labels[key] = f"{name} · lift {suffix[len('lift'):]}"
            else:
                labels[key] = f"{name} · below the pit"
        return labels

    def soil_bodies(self) -> list[tuple[str, float, float, bool]]:
        """Every soil body the excavation splits the layers into, as
        `(part key, y_bottom, y_top, inside the pit outline)`.

        With one excavation level nothing is split: the pit is a void cut out of the
        soil (`solid_model._cut_the_pit`) and each layer is one body under its own key, which
        is what every project did before staged construction existed.

        With several, the soil inside the pit's plan outline is *kept* -- it has to be,
        because each lift is deactivated in its own stage -- and split into the lifts it
        is dug in. A body is the intersection of one layer with one lift, so a lift
        deeper than the layer it starts in cannot produce a single body spanning two
        materials. What lies below the final floor but still inside the outline is its
        own body too: it is never dug, but it sits on the excavated side of the wall and
        has to be nameable apart from the same layer on the retained side.

        Soil outside the outline keeps the layer's own key, so a body that was never
        staged never changes name. Ordered outside-first, then by lift, so the key list
        is stable for the viewport and the exporter.
        """
        if not self.layers:
            # Called from `part_keys`, which runs during validation and on a project
            # that has no ground in it yet -- the site the server opens on. No layers
            # means no bodies, and it must not be an error to ask.
            return []
        layers = [(f"soil_{layer.id}", layer.bottom, layer.top) for layer in self.layers]
        outside = [(key, bottom, top, False) for key, bottom, top in layers]
        levels = self.pit_levels()
        if len(levels) < 2:
            return outside

        # The lifts, top down, then the ground below the final floor. `None` marks that
        # last one: it is the part of the outline that is never dug.
        bands: list[tuple[str | None, float, float]] = []
        ceiling = self.domain.y_top
        for index, level in enumerate(levels, start=1):
            bands.append((f"lift{index}", level, ceiling))
            ceiling = level
        bands.append((None, self.domain.y_bottom, ceiling))

        inside = []
        for key, bottom, top in layers:
            for suffix, band_bottom, band_top in bands:
                low, high = max(bottom, band_bottom), min(top, band_top)
                if high - low <= _LEVEL_TOLERANCE:
                    continue     # this layer does not reach this band
                inside.append((f"{key}__{suffix or 'pit'}", low, high, True))
        return outside + inside

    def soil_part_keys(self) -> list[str]:
        """What a condition on a soil part may name: each layer, each body dug out of a
        staged one, and each custom part that has a material -- the soil a user can
        pick in the explorer, the viewport or the Mesh properties dialog."""
        keys = [f"soil_{layer.id}" for layer in self.layers]
        keys += [key for key, *_ in self.soil_bodies() if key not in keys]
        return keys + [part.key for part in self.custom_parts if part.mat is not None]

    def expand_body_keys(self, keys: list[str]) -> list[str]:
        """Turn a list that may name soil *layers* into one naming soil *bodies*.

        A staged layer is several bodies -- the lifts it is dug in, plus what is left
        below the floor -- and the parts of the app that let a user pick soil pick
        layers, because that is what a user drew: the Mesh properties dialog lists
        `project.layers` (`frontend/js/mesh-settings.js`). Naming a layer therefore has to
        mean every body dug out of it, or checking one there would mesh the retained
        side and leave the entire excavation out of the model.

        Anything that is not a soil layer passes through untouched, and a key that
        already names a body is kept as it stands, so this is safe to apply to any list
        and is a no-op on a project with nothing staged.
        """
        bodies: dict[str, list[str]] = {}
        for key, *_ in self.soil_bodies():
            bodies.setdefault(key.partition("__")[0], []).append(key)
        out: list[str] = []
        for key in keys:
            for expanded in bodies.get(key, [key]):
                if expanded not in out:
                    out.append(expanded)
        return out

    def part_keys(self) -> list[str]:
        """The frontend's userData.key namespace, in render order."""
        # `soil_bodies` is the authority on what soil there is: one key per layer while
        # the pit is a void, and one per (layer, lift) once it is staged. Deriving both
        # from it keeps the namespace and the geometry from disagreeing about how many
        # soil bodies a project has.
        soils = [key for key, *_ in self.soil_bodies()]
        customs = [p.key for p in self.custom_parts]
        beams = ([beam.id for beam in self.beams] + [a.id for a in self.anchors]
                 + [i.id for i in self.interfaces])
        if self.layered_soil:
            # Normal loads travel with the structures rather than with `loads[]`: the
            # simple example draws no load pads, but it does draw what the user has
            # drawn in it, and a symbol missing from this list is never tessellated.
            return soils + beams + [n.id for n in self.normal_loads] + customs
        return soils + [
            "excavation", "wall", "struts", "anchors", "piles",
        ] + [load.id for load in self.loads] + [n.id for n in self.normal_loads] \
          + beams + (["water"] if self.water is not None else []) + ["wells"] + customs

    @property
    def phases(self) -> list[Stage]:
        """Deprecated alias of `stages`, the name before Styx took Kratos' word."""
        return self.stages

    def model_copy(self, *, update: Mapping[str, Any] | None = None,
                   deep: bool = False) -> Project:
        """`model_copy` skips validation, so an old `update={"phases": ...}` would be
        silently dropped; it is renamed here as on load."""
        if update and "phases" in update:
            update = migration.rename_phases(dict(update))
        return super().model_copy(update=update, deep=deep)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stageable_parts(self) -> list[str]:
        """`stageable_keys`, published with the project.

        The browser resolves the stage tree too (`frontend/js/stages.js`), and resolving it
        starts from "everything is active" -- so it needs the same namespace the server
        starts from. It cannot derive it: the staging namespace is `part_keys` plus
        every load id, and a `layered_soil` project draws no load pads, so a load that
        a stage may legitimately name appears nowhere the viewport can see.

        Named `stageable_parts` rather than `stageable_keys` because a computed field
        may not share a name with a method on the same model.
        """
        return self.stageable_keys()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def model_strategies(self) -> dict[str, str]:
        """The strategy each stage's model calls for, by stage id
        (`core.model.stages.model_strategy`): a flow stage's default, and the only one
        it can have with a seepage face.

        Published because the stage panel shows a stage's expert settings with their
        defaults (`frontend/js/stages.js`'s `solverRows`), and this default depends on
        the soil in the stage and the project's conditions, which is the server's to
        work out. Empty for a mechanical project."""
        from core.model import stages  # stages imports this module
        found = {stage.id: stages.model_strategy(self, stage) for stage in self.stages}
        return {id: strategy for id, strategy in found.items() if strategy is not None}

    def stageable_keys(self) -> list[str]:
        """What a stage may switch on and off, which is wider than what is drawn.

        `part_keys` is the *render* namespace, in draw order, and the simple example
        deliberately draws no load pads -- so a project built that way has line loads
        that appear nowhere in it. They are still real parts of the deck: the reference
        stages one, `Load`, which arrives with the wall and stays. A stage has to be
        able to name them, so the staging namespace is `part_keys` plus every load id.

        Everything drawn is stageable; not everything stageable is drawn. The two are
        kept as separate lists rather than by widening `part_keys`, which would change
        draw order: `part_keys` feeds tessellation, and a key appearing there makes the
        viewport look for geometry that a load pad in the simple example does not have.

        The water pressure conditions are stageable too, last: a stage switches the
        water on and off as it does a load -- the pit pumped dry, a level that drops.
        The supports are not; they hold the model in every stage.
        """
        if self.deck is not None:
            # A deck's Styx stages are its Kratos stages, and they switch the deck's own parts.
            return list(self.deck.parts)
        keys = self._staged_parts_and_loads()
        seen = set(keys)
        for condition in self.boundary_conditions:
            if condition.kind == "water_pressure" and condition.id not in seen:
                seen.add(condition.id)
                keys.append(condition.id)
        return keys

    def _staged_parts_and_loads(self) -> list[str]:
        """`stageable_keys` without the conditions: the parts, then every load id."""
        keys = list(self.part_keys())
        seen = set(keys)
        for load in [l.id for l in self.loads] + [n.id for n in self.normal_loads]:
            if load not in seen:
                seen.add(load)
                keys.append(load)
        return keys


def _reject_duplicates(ids: list[str], what: str) -> None:
    seen = set()
    for i in ids:
        if i in seen:
            raise ValueError(f"duplicate {what} id {i!r}")
        seen.add(i)
