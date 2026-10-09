"""The project schema — the single source of truth for the model.

Coordinates are X across, Y up and Z out of plane, metres, y = 0 at the ground
datum. A 2D model is the x-y plane at z = 0; a 3D model extrudes it along Z. Units throughout are m / kN / day, matching the
status bar (index.html:117).

Part keys (`Project.part_keys`) are the contract with the frozen frontend: each one is a
`userData.key` on a picked mesh, an `obj:` on a model-tree node, and a key in
`App.OBJECT_PROPS`. gmsh physical group names must equal them.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, Field, computed_field, model_validator

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
    # A drawn or imported solid becomes *soil* once it is given a material: it then
    # carries the same strength/stiffness/permeability set as a stack layer and is
    # meshed as a soil body. Left unset, the part stays plain display geometry.
    mat: Ident | None = None
    bbox: tuple[float, float, float, float, float, float] | None = None
    """Where this part is, as (xmin, ymin, zmin, xmax, ymax, zmax) in metres.

    Measured by gmsh when the part is drawn or imported (`creator.process_creation`,
    `importer`), and kept so `Project.extent` knows how far the model reaches without
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

class Borehole(Base):
    id: Ident
    name: str
    x: float
    y: float
    head: float      # ground surface level, m
    water: float     # phreatic level, m


class Material(Base):
    id: Ident
    name: str
    model: Literal["Mohr-Coulomb", "Hardening Soil", "Soft Soil", "Linear Elastic"]
    type: Literal["Drained", "Undrained (A)", "Undrained (B)", "Non-porous"]
    color: Hex
    g_unsat: float = Field(gt=0)       # kN/m3
    g_sat: float = Field(gt=0)         # kN/m3
    E: float = Field(gt=0)             # kN/m2
    nu: float = Field(ge=0, lt=0.5)
    c: float | None = Field(default=None, ge=0)     # kN/m2; null for non-porous rock
    phi: float | None = Field(default=None, ge=0, lt=90)   # degrees
    k: float = Field(ge=0)             # m/day

    # Interface properties. A soil material set carries the strength reduction applied
    # where a structure meets this soil, so "Soil and interfaces" is one set type
    # rather than two (the Interfaces tab of the material editor).
    r_inter: float = Field(default=0.70, gt=0, le=1)
    interface_permeability: Literal["Neutral", "Drain", "Impermeable"] = "Neutral"

    porosity: float | None = Field(default=None, ge=0, lt=1)
    """Voids as a fraction of total volume. None falls back to
    `app/kratos_materials.py:DEFAULT_POROSITY`, which is what every project written
    before this field existed carries. A number here is the user's, and is written."""

    k0_nc: float | None = Field(default=None, gt=0, le=2)
    """Coefficient of earth pressure at rest, normally consolidated (Kratos' `K0_NC`).

    `None` means "use Jaky's formula" -- see `k0_normally_consolidated`. It is optional
    rather than defaulted because only a material with a friction angle has an answer,
    and non-porous rock has neither.
    """

    def k0_normally_consolidated(self) -> float | None:
        """K0 for the initial stage, or `None` if this material cannot say.

        Jaky's `1 - sin(phi)` when nothing overrides it: the standard correlation, and
        the one the CROW reference deck's own numbers follow (0.62 and 0.46 are Jaky at
        22.3 deg and 32.7 deg). Deriving it rather than defaulting to a constant keeps a
        stiff soil and a loose one from being handed the same initial stress ratio.

        `None` for a material with no friction angle -- non-porous rock -- because there
        is nothing to derive it from. The caller omits `K0_NC` in that case and leaves
        the k0 procedure on its own default rather than inventing one here.
        """
        if self.k0_nc is not None:
            return self.k0_nc
        if self.phi is None:
            return None
        return 1.0 - math.sin(math.radians(self.phi))


class SoilLayer(Base):
    id: Ident
    name: str
    mat: Ident
    tops: dict[str, float]    # borehole id -> level (y) of layer top
    bots: dict[str, float]    # borehole id -> level (y) of layer bottom

    @model_validator(mode="after")
    def _positive_thickness(self) -> SoilLayer:
        for bh, top in self.tops.items():
            bot = self.bots.get(bh)
            if bot is not None and bot > top:
                raise ValueError(f"layer {self.id}: bottom above top at borehole {bh}")
        return self


def validate_layer_stack(layers: list[SoilLayer], borehole_ids: list[str]) -> None:
    """Every layer covers every borehole, and the stack is gap-free.

    This is the invariant js/dialogs.js:320-331 maintains by hand when a depth is edited.
    """
    for layer in layers:
        missing = set(borehole_ids) - layer.tops.keys() | set(borehole_ids) - layer.bots.keys()
        if missing:
            raise ValueError(f"layer {layer.id} has no levels for borehole(s) {sorted(missing)}")

    for upper, lower in zip(layers, layers[1:]):
        for bh in borehole_ids:
            if abs(upper.bots[bh] - lower.tops[bh]) > 1e-9:
                raise ValueError(
                    f"layer stack is not contiguous at borehole {bh}: "
                    f"{upper.id} bottom {upper.bots[bh]} != {lower.id} top {lower.tops[bh]}"
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
    in the mesh, deactivated in its own phase (`Excavated_Soil_1/2/3` in the CROW
    reference deck). One level means an unstaged pit, which is what every project
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
    components: tuple[float, float]  # in-plane x/y, kN
    distribution: Literal["Uniform"] = "Uniform"
    active: bool = True
    derived_from: Ident | None = None
    """The load in the other dimension this one is the translation of, if any.

    A surface load and a line load are one load seen from two dimensions, and both
    records are kept so a round trip does not widen the footprint (`app/loads.py`).
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
    components: tuple[float, float]  # in-plane x/y, kN/m
    distribution: Literal["Uniform"] = "Uniform"
    active: bool = True
    derived_from: Ident | None = None
    """The load in the other dimension this one is the translation of, if any.

    A surface load and a line load are one load seen from two dimensions, and both
    records are kept so a round trip does not widen the footprint (`app/loads.py`).
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
    components: tuple[float, float, float]  # world x/y/z, kN/m2; y is vertical
    distribution: Literal["Uniform"] = "Uniform"
    active: bool = True
    derived_from: Ident | None = None
    """The load in the other dimension this one is the translation of, if any.

    A surface load and a line load are one load seen from two dimensions, and both
    records are kept so a round trip does not widen the footprint (`app/loads.py`).
    Set on the *derived* record only; the one the user authored carries None."""

    @model_validator(mode="after")
    def _valid_condition(self) -> SurfaceLoad:
        if self.x1 <= self.x0 or self.z1 <= self.z0:
            raise ValueError("load footprint extents must be strictly increasing")
        if not all(math.isfinite(value) for value in self.components):
            raise ValueError("load components must be finite")
        return self


class BeamSection(Base):
    """A reusable structural profile, shared by every sheet pile that uses it.

    Section values live here rather than on each beam because that is the shape Kratos
    wants: one `MaterialParameters.json` entry per distinct property set, referenced by
    name. Several sheet piles in one model normally share a profile, and duplicating
    the numbers per beam would let two copies of "AZ 26" drift apart. The pairing is
    the one `materials` / `layers[].mat` already uses, so the frontend's editor and
    tree patterns carry over unchanged.

    Units follow the project: kN, m. `E` is kN/m2, `area` m2/m and `inertia` m4/m --
    both per metre run, the plane-strain convention -- and `density` kg/m3, matching
    the `DENSITY_SOLID` the soil materials already export.
    """
    id: Ident
    name: str
    E: float = Field(gt=0)                 # kN/m2
    nu: float = Field(ge=0, lt=0.5)
    area: float = Field(gt=0)              # m2 per metre run
    inertia: float = Field(gt=0)           # m4 per metre run, about the out-of-plane axis
    shear_area: float | None = Field(default=None, gt=0)   # m2 per metre run
    """The area that carries shear, which is less than the whole section -- a rolled
    profile shears in its web. None takes the full section, which is what this exported
    before the field existed and is the shear-stiff end of the range.

    It is also how a model says shear deformation is not part of it: a value far larger
    than the section makes `GA_s` large enough that the beam bends as a Bernoulli one.
    The CROW reference does exactly that (`THICKNESS_EFFECTIVE_Y` twenty times its own
    thickness), which is why this is a field and not a derivation."""
    density: float = Field(gt=0)           # kg/m3
    spacing: float = Field(default=1.0, gt=0)
    """Out-of-plane spacing in metres. 1.0 is a continuous wall -- the usual sheet
    pile -- and a larger value smears a discrete row of piles over the plane. A
    plane-strain device: a 3D member is discrete already, and ignores it."""

    # A beam in space bends about two axes and twists about the third, none of which a
    # plane-strain section has room for. Optional so every saved profile still loads,
    # and so the 2D pile stays the two numbers an engineer reads off a profile table.
    inertia_minor: float | None = Field(default=None, gt=0)
    """m4, about the weak axis. Defaults to `inertia`, i.e. a section as stiff both
    ways, which is what a solid round pile is."""

    torsional_inertia: float | None = Field(default=None, gt=0)
    """m4. Defaults to `inertia + inertia_minor`, the usual estimate for a thin-walled
    open section. Only used by a 3D member."""


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
    no z to remember it by (`app/walls.py`). Set on the *derived* record only."""

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


class AnchorSection(Base):
    """A reusable tendon or bar, shared by every anchor installed with it.

    `spacing` matters more here than for a sheet pile: anchors are discrete members at
    centres along the wall, and plane strain smears them over a metre run.
    """
    id: Ident
    name: str
    E: float = Field(gt=0)                 # kN/m2
    area: float = Field(gt=0)              # m2 of steel per anchor
    density: float = Field(ge=0)           # kg/m3; 0 for a tendon modelled massless
    spacing: float = Field(default=2.5, gt=0)
    tension_limit: float | None = Field(default=None, gt=0)      # kN per anchor
    compression_limit: float | None = Field(default=None, gt=0)
    """Left None for a tendon, which takes no compression at all."""


class Anchor(Base):
    """One anchor: a two-node tie from a sheet pile to a restrained point.

    The formulation is the one examples/crow_case.mdpa writes -- a single
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
    """Lock-off force in kN per anchor, positive in tension. Per anchor rather than per
    section: two anchors of the same tendon are routinely stressed differently."""
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



# ── Interfaces ──────────────────────────────────────────────────────────────
#
# An interface is the sliding, opening contact between a structure and the ground it
# stands in. Kratos models it as a *zero-thickness* element: two coincident faces whose
# nodes are separate, so the wall and the soil can move relative to one another instead
# of being welded together the way `_embed_beams` leaves them.
#
# The formulation is read off examples/crow_case.mdpa, which is exactly this: the sheet
# pile owns its own nodes, each side of the soil owns a duplicate set, and one
# `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N` per side per beam segment
# ties them together. See the element table in app/kratos.py and the node split in
# app/interfaces.py.


class InterfaceSection(Base):
    """A reusable interface property set, shared by every interface using it.

    Zero thickness means there is no modulus here: the element's stiffness is a stiffness
    *per unit area*, kN/m3, and its strength is the adjacent soil's reduced by `r_inter`.
    Left unset, the two are derived from the soil the contact runs against -- shear is
    its shear modulus over `virtual_thickness`, normal is ten times that -- which is what
    `app/kratos_materials.py` does and where the reasoning for it lives.

    *Which* soil is the adjacent body's by default, one property set per body, as the
    reference deck does it. `material` overrides that for the whole contact.

    `r_inter` and `permeability` mirror the fields the soil `Material` already has, so
    the material library's interface presets (js/material-library.js) drop straight in.
    """
    id: Ident
    name: str
    material: Ident | None = None
    """One soil for the whole contact, overriding the per-body default. Its E, cohesion
    and friction angle are what `r_inter` reduces. None -- the usual case -- derives each
    stretch of contact from the body it actually runs against."""
    r_inter: float = Field(default=0.7, gt=0, le=1)
    virtual_thickness: float = Field(default=1.0, gt=0)       # m
    """The element size normal to the interface, which the derived stiffnesses are the
    soil's shear modulus over. 1.0 is the reference deck's own
    (`MaterialParameters_for_generated_mesh.json`); it was 0.01 until the stiffnesses
    were checked against it."""
    normal_stiffness: float | None = Field(default=None, gt=0)   # kN/m3
    shear_stiffness: float | None = Field(default=None, gt=0)    # kN/m3
    permeability: Literal["Neutral", "Drain", "Impermeable"] = "Neutral"

    # There used to be a validator here refusing a section with neither a material nor
    # explicit stiffnesses. That is the ordinary case now: such a section derives from
    # whatever soil each stretch of the contact runs against, which is a fact about the
    # mesh and cannot be known here. The one case that really has nothing to derive from
    # -- a contact with no soil on either side -- is still refused, at export, where the
    # adjacent bodies are known (`app/kratos_materials.py:_interface_variables`).


class Interface(Base):
    """One interface: a line along which the mesh is split and re-tied by contact.

    Two ways to place one, and exactly one of them per record:

    *   `structure` names a sheet pile. The interface runs the whole pile, and `side`
        says which of the two soils is unglued from it. This is the crow-case
        arrangement and the usual one -- a wall slides against the ground on both faces.
    *   `points` is a free polyline in the section, which splits soil from soil: an
        excavation face, a slip surface, a lining. There is no structure in the middle,
        so one soil keeps the original nodes and the other is detached; `side` says
        which, and `both` is meaningless without a structure to sit between them.

    Left and right are relative to walking the line in the order its points are stored:
    left is the side a +90 degree turn from the walking direction points at, the same
    convention the exported element's node order carries.

    Dimension-native `(x, y)`, like every other 2D record. Interfaces are plane strain
    only -- see app/kratos.py's `INTERFACES` table for why.
    """
    id: Ident
    name: str
    kind: Literal["interface"] = "interface"
    section: Ident
    structure: Ident | None = None
    points: list[tuple[float, float]] | None = None
    side: Literal["both", "left", "right"] = "both"
    active: bool = True

    @model_validator(mode="after")
    def _usable_line(self) -> Interface:
        if (self.structure is None) == (self.points is None):
            raise ValueError(
                f"interface {self.id!r} needs either a structure to follow or its own "
                "points, and not both"
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
    free interface's is (`app/build.py:_embed_beams`), and its condition is harvested
    directly off that embedding (`app/kratos.py:_normal_load_conditions`) rather than
    by scanning the boundary at a fixed elevation the way `LineLoad` is, which is what
    lets it run down a vertical face.

    Two ways to size it, picked by `fluid_pressure_type`, matching Kratos
    GeoMechanics' own `ApplyNormalLoadTableProcess`:

    *   `"Hydrostatic"` derives the pressure from `Project.water` at export time --
        zero at the phreatic level, increasing with depth below it -- so the load
        tracks the water table rather than a value copied onto each stage's record.
        This is the CROW reference case's `WaterLoad_StageN` arrangement.
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
    """kN/m2, compression positive. Read only when `fluid_pressure_type` is
    `"Uniform"`; a hydrostatic load is derived from `Project.water` instead."""
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
# No 3D element class is pinned by a reference deck here -- every deck in examples/ is
# plane strain. See plan/structure-mode-implementation-plan.md and the element tables
# in app/kratos.py, which name every unconfirmed choice in one place.


class PanelSection(Base):
    """A reusable wall property set, shared by every panel built with it.

    The 3D counterpart of `BeamSection`. A panel is a shell, so it is defined by a
    thickness: `area` and `inertia` per metre run are the plane-strain reduction of
    exactly this, and carrying both would let the two drift apart.

    Units follow the project: `E` in kN/m2, `thickness` in m, `density` in kg/m3.
    """
    id: Ident
    name: str
    E: float = Field(gt=0)                 # kN/m2
    nu: float = Field(ge=0, lt=0.5)
    thickness: PositiveSize                # m
    density: float = Field(gt=0)           # kg/m3


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
    no z to remember it by (`app/walls.py`). Set on the *derived* record only."""

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
                      points: list[tuple[float, ...]], tol: float = 1e-6) -> bool:
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


class WaterLevel(Base):
    y: float
    # The phreatic level is a reference plane, not a solid: it is drawn as a thin slab
    # overhanging the domain so the level reads against the model's outside faces
    # (js/viewport.js:201). It takes no part in the geometry booleans.
    margin: float = Field(default=3.0, ge=0)
    thickness: float = Field(default=0.06, gt=0)
    specific_weight: float = Field(default=10.0, gt=0)
    """kN/m3. Read by a `NormalLoad` in `"Hydrostatic"` mode
    (`app/kratos_processes.py:_normal_load`); otherwise unused. One value for the whole
    project, the same way `y` is one phreatic level -- not a per-load setting."""


class Phase(Base):
    """One construction phase: what changes about the model, and how it is solved.

    The field names follow the phase panel the GUI already draws (js/data.js:559),
    because that is the UI this feeds and a second vocabulary would have to be
    translated twice.

    **A phase stores a diff, not a state.** `activate` and `deactivate` say what this
    phase changes about the model it inherits from `parent`; they do not describe the
    whole model. Two reasons, and both matter: the reference deck's `stage_preprocess`
    *is* that diff, so nothing has to be reconstructed on export; and storing absolute
    state would mean rewriting every later phase whenever a part is added to the model.
    Resolving diff to state is one function, in `app.phases`, which is the only place
    that walks the parent chain.

    `parent` makes a tree, and a tree can branch. Kratos cannot run one: its orchestrator
    runs a flat `execution_list`. Linearising the tree, and refusing one that cannot be
    linearised, is the export's job (`app.phases`) rather than this class's -- a branch
    is a legitimate thing to have half-built in the editor, and refusing it here would
    make it impossible to type.

    Out of scope deliberately: a per-phase phreatic level ("Pore
    pressure calculation type" in the phase panel). The reference deck never varies
    it -- it changes which water *load* is active, not the water table -- so there is
    no worked example to follow and inventing one would be guessing. See
    plan/staged-construction-plan.md sec 7.
    """
    id: Ident
    name: str
    parent: Ident | None = None
    """The phase this one starts from. `None` only for the first, which starts from the
    model as built."""

    calculation: Literal["K0 procedure", "Plastic", "Null step"] = "Plastic"
    loading: Literal["Staged construction"] = "Staged construction"

    activate: list[Ident] = Field(default_factory=list)
    deactivate: list[Ident] = Field(default_factory=list)

    # The three the reference deck actually varies between its stages (see
    # plan sec 0.2). Their defaults are its initial stage's own values, so a phase that
    # says nothing solves the way that one does.
    reset_displacements: bool = False
    """Kratos' `reset_totals`: start this phase's displacements from zero. The reference
    turns it on when the wall is installed, so the wall's own deflection is measured
    from the ground it was built into rather than from the undisturbed state."""

    max_iterations: int = Field(default=15, gt=0)
    tolerated_error: float = Field(default=1e-4, gt=0)
    """Kratos' `residual_relative_tolerance`."""

    time_interval: float = Field(default=0.0, ge=0)
    """Days. Zero for the static phases this exporter writes; carried because the phase
    panel has it and a consolidation phase would need it."""

    @model_validator(mode="after")
    def _one_instruction_per_part(self) -> Phase:
        both = sorted(set(self.activate) & set(self.deactivate))
        if both:
            raise ValueError(
                f"phase {self.id!r} both activates and deactivates: {', '.join(both)}"
            )
        return self


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
    # Boreholes ride along because the two cannot move independently: adding a
    # borehole adds a tops/bots key to every layer and removing one takes it
    # away, so a stack that validates only does so against the matching
    # borehole list. Omitted means "leave the boreholes alone".
    boreholes: list[Borehole] | None = Field(default=None, min_length=1)
    # The plan extents, edited from the Selection explorer's Geometry rows.
    # Same reasoning: one request, one validation of the resulting model.
    domain: Domain | None = None
    # The phreatic level and the fluid's specific weight, edited from the same
    # explorer. One object for the whole project, exactly like `domain`, and carried
    # here rather than on an endpoint of its own for the same reason: the water level
    # is validated against the model it belongs to, not on its own.
    #
    # It is not merely cosmetic. `kratos_processes._pore_pressure` states the whole
    # ground's water pressure from these two numbers, `_normal_load` sizes every
    # hydrostatic load from them, and `kratos_materials` derives DENSITY_WATER from
    # the specific weight -- so this row is the deck's water table.
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


class PhasesUpdate(Base):
    """The construction sequence, replaced wholesale.

    Its own endpoint rather than a ride-along on `StructuresUpdate`, because a phase is
    the one collection that is *about* the others: `activate`/`deactivate` name part
    keys, so the list can only be validated against a model that has already settled.
    Sent together with a structure edit, which of the two the keys should be checked
    against would depend on the order they were applied in.

    Required rather than optional, and `[]` is meaningful: it is how a project goes
    back to being unphased, which must export exactly the deck it exported before
    staged construction existed (plan sec 7.18).
    """
    phases: list[Phase]


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

    Set by `app.deck.deck_project` for a case that is written as a deck rather than
    built from layers -- the Eemdijk case, with its twenty stages, three material sets
    and phreatic multi-lines, none of which this schema can say. The deck is shown as
    its own mesh and calculated as the files it is; nothing is exported. Every other
    field of a project carrying one is the empty site `seed.blank_project` is, there
    because the schema requires it.
    """
    directory: str
    """Absolute. The files the parameters name are read from here."""
    parameters: str = "ProjectParameters.json"
    """The orchestrator file, by name inside `directory`. It names everything else."""
    parts: list[str] = Field(default_factory=list)
    """The deck's parts that some stage computes on or loads, in the order the stages
    first name them -- what this project's phases switch on and off (`stageable_keys`).
    Read off the deck when it is opened, so that validating a project never has to."""


class Project(Base):
    name: str = "Deep excavation — Rotterdam Zuid"

    layered_soil: bool = True
    """Build the soil out of the layer stack and whatever the user drew, rather than
    also raising the seeded demo structures.

    `True` takes `build._build_layered_soil`: one box per layer across the whole domain,
    plus the drawn beams, anchors, interfaces and custom parts, and no pit cut unless
    the excavation is staged. `False` takes the full path, which additionally raises the
    seeded 3D wall ring, strut frame and pile group and cuts the excavation void.

    Named `simple_example` until the phase editor made it user-visible, which was the
    wrong name twice over: it is not about examples, and the models that set it are not
    simple -- `examples/crow/crow.py` sets it. The old spelling is still accepted on the
    way in (see `_reconcile_layered_soil`); nothing writes it any more.
    """

    dimension: Literal[2, 3] = 3
    """3 builds the solid model. 2 builds a planar section through it."""

    section_offset: float | None = None
    """Where the section is taken, as a world z. A 2D model is always the x-y plane,
    cut at a constant z. Resolved to the middle of the domain by the validator when the
    project is 2D and this is unset, so everything downstream -- geometry, mesh,
    viewport -- reads one authoritative number instead of each deriving its own."""

    domain: Domain
    boreholes: list[Borehole]
    materials: list[Material]
    layers: list[SoilLayer]
    excavation: Excavation
    wall: Wall
    struts: Struts
    anchor_rows: AnchorRows
    piles: Piles
    loads: list[PointLoad | LineLoad | SurfaceLoad] = Field(default_factory=list)
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
    # Its own collection, not folded into `loads[]`: a normal load is dimension-native
    # like a free interface (an arbitrary polyline, no 3D translation), not a
    # translated x/y vector like the three kinds `loads[]` already holds.
    normal_loads: list[NormalLoad] = Field(default_factory=list)
    wells: Wells
    water: WaterLevel | None = None
    """The phreatic level, or `None` for a model without one -- which is what a new
    project starts as. A model is not born with a water table at somebody else's depth;
    it has one when its author sets one. Without it the deck is dry: zero pore pressure,
    still fixed (`kratos_processes._pore_pressure`)."""
    mesh: MeshSettings = Field(default_factory=MeshSettings)
    custom_parts: list[CustomPart] = Field(default_factory=list)
    phases: list[Phase] = Field(default_factory=list)
    """The construction sequence, in creation order. Empty means an unphased project --
    every project written before staged construction -- which exports exactly what it
    always did. That is the compatibility contract; see `test_export_golden.py`."""
    deck: Deck | None = None
    """A deck this project *is*, rather than one it exports. See `Deck`."""

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
        derived = ("soil_body_keys", "soil_body_labels", "stageable_parts")
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
        """A hydrostatic normal load's pressure is derived from `water` at export time.
        With no water level there is nothing to derive it from, and quietly writing zero
        would be a wall with no water against it."""
        if self.water is None:
            for load in self.normal_loads:
                if load.fluid_pressure_type == "Hydrostatic":
                    raise ValueError(
                        f"normal load {load.name!r} is hydrostatic, which needs a water "
                        "level to measure its pressure from; set one, or make the load "
                        "uniform"
                    )
        return self

    @property
    def water_specific_weight(self) -> float:
        """kN/m3: the project's own, or `WaterLevel`'s default for a dry model -- the
        materials still need a unit weight of water for their permeability."""
        if self.water is not None:
            return self.water.specific_weight
        return WaterLevel.model_fields["specific_weight"].default

    @model_validator(mode="after")
    def _cross_references(self) -> Project:
        _reject_duplicates([b.id for b in self.boreholes], "borehole")
        _reject_duplicates([m.id for m in self.materials], "material")
        _reject_duplicates([l.id for l in self.layers], "layer")
        _reject_duplicates([p.key for p in self.custom_parts], "custom_part")
        _reject_duplicates([load.id for load in self.loads], "load")
        _reject_duplicates([s.id for s in self.interface_sections], "interface_section")
        _reject_duplicates([i.id for i in self.interfaces], "interface")
        _reject_duplicates([n.id for n in self.normal_loads], "normal_load")

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

        self._check_phases()

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
        # domain is only the block the boreholes describe. See `Project.extent`.
        extent = self.extent()
        for load in self.loads:
            if load.kind == "point" and not (
                extent.x0 <= load.x <= extent.x1
                and extent.y_bottom <= load.y <= extent.y_top
            ):
                raise ValueError(f"point load {load.id!r} lies outside the domain")
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
            for x, y in (anchor.head, anchor.tail):
                if not (extent.x0 <= x <= extent.x1
                        and extent.y_bottom <= y <= extent.y_top):
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
            for x, y in beam.points:
                if not (extent.x0 <= x <= extent.x1
                        and extent.y_bottom <= y <= extent.y_top):
                    raise ValueError(
                        f"beam {beam.id!r} lies outside the domain at ({x}, {y})"
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
        validate_layer_stack(self.layers, [b.id for b in self.boreholes])

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
            e = self.excavation
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

        `Domain` is the soil block the boreholes describe, and a drawn or imported part
        is not held to it -- an embankment stands above `y_top`. Anything asking "may a
        structure be here?" wants this, not the domain: a load on a custom layer above
        ground stands on model geometry, and refusing it as "outside the domain" is the
        bug this exists to fix. `build.SECTION_PAD` measures the section the same way,
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
        boreholes describe, so once a drawn embankment stands above it, `domain.y_top`
        is buried inside the fill rather than on top of it. `extent` knows where the
        model actually ends; everything that places or reads a surface load asks here,
        so the build, the exporter and `app/loads.py` agree on one answer.
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
        and are carried at the section plane instead (`build._load_footprint_tools`).
        """
        if dimension == 2:
            return [load for load in self.loads if load.kind != "surface"]
        # Both ends of every pair, so a 2D half is recognised whether it was the record
        # the user authored or the one translated from a surface load.
        paired = {id for load in self.loads if load.derived_from is not None
                  for id in (load.id, load.derived_from)}
        return [load for load in self.loads
                if load.kind == "surface" or load.id not in paired]

    def material(self, mat_id: str) -> Material:
        return next(m for m in self.materials if m.id == mat_id)

    def borehole_ids(self) -> list[str]:
        return [b.id for b in self.boreholes]

    def beam_section(self, section_id: str) -> BeamSection:
        return next(s for s in self.beam_sections if s.id == section_id)

    def panel_section(self, section_id: str) -> PanelSection:
        return next(s for s in self.panel_sections if s.id == section_id)

    def anchor_section(self, section_id: str) -> AnchorSection:
        return next(s for s in self.anchor_sections if s.id == section_id)

    def interface_section(self, section_id: str) -> InterfaceSection:
        return next(s for s in self.interface_sections if s.id == section_id)

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
        onto the section plane instead (`build._section_sweeps`).
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

    def _check_phases(self) -> None:
        """The construction sequence is a tree of real phases over real parts.

        Structure only. Whether the tree can be flattened into the one sequence Kratos
        runs is the export's question, not this one -- a branch is a legitimate thing to
        have half-built in the editor, and refusing it here would make it impossible to
        type (see `Phase`).
        """
        if not self.phases:
            return
        _reject_duplicates([phase.id for phase in self.phases], "phase")

        ids = {phase.id for phase in self.phases}
        roots = [phase.id for phase in self.phases if phase.parent is None]
        if len(roots) != 1:
            raise ValueError(
                "a construction sequence needs exactly one root phase -- the one that "
                f"starts from the model as built -- but {len(roots)} have no parent"
            )
        for phase in self.phases:
            if phase.parent is not None and phase.parent not in ids:
                raise ValueError(
                    f"phase {phase.id!r} starts from nowhere: there is no phase "
                    f"{phase.parent!r}"
                )
            if phase.parent == phase.id:
                raise ValueError(f"phase {phase.id!r} starts from itself")

        # Every phase has to reach the root by following parents. Anything that does not
        # is in a cycle, which would make `app.phases` walk for ever.
        parents = {phase.id: phase.parent for phase in self.phases}
        for start in ids:
            seen, at = set(), start
            while at is not None:
                if at in seen:
                    raise ValueError(
                        f"phases form a cycle through {at!r}; every phase must lead "
                        "back to the one that starts from the model as built"
                    )
                seen.add(at)
                at = parents[at]

        # A phase may only name parts the model actually has. Caught here rather than at
        # export because a phase naming a deleted structure is a modelling mistake the
        # user can fix, and finding it only when Calculate is pressed would be late.
        parts = set(self.stageable_keys())
        for phase in self.phases:
            unknown = sorted({key for key in phase.activate + phase.deactivate
                              if key not in parts})
            if unknown:
                raise ValueError(
                    f"phase {phase.id!r} names no such part: {', '.join(unknown)}"
                )

    @computed_field
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

    @computed_field
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
        soil (`build._cut_the_pit`) and each layer is one body under its own key, which
        is what every project did before staged construction existed.

        With several, the soil inside the pit's plan outline is *kept* -- it has to be,
        because each lift is deactivated in its own phase -- and split into the lifts it
        is dug in. A body is the intersection of one layer with one lift, so a lift
        deeper than the layer it starts in cannot produce a single body spanning two
        materials. What lies below the final floor but still inside the outline is its
        own body too: it is never dug, but it sits on the excavated side of the wall and
        has to be nameable apart from the same layer on the retained side.

        Soil outside the outline keeps the layer's own key, so a body that was never
        staged never changes name. Ordered outside-first, then by lift, so the key list
        is stable for the viewport and the exporter.
        """
        boreholes = self.borehole_ids()
        if not boreholes or not self.layers:
            # Called from `part_keys`, which runs during validation and on a project
            # that has no ground in it yet -- the site the server opens on. No layers
            # means no bodies, and it must not be an error to ask.
            return []
        bh = boreholes[0]
        layers = [(f"soil_{layer.id}", layer.bots[bh], layer.tops[bh])
                  for layer in self.layers]
        outside = [(key, bottom, top, False) for key, bottom, top in layers]
        if len(self.excavation.levels) < 2:
            return outside

        # The lifts, top down, then the ground below the final floor. `None` marks that
        # last one: it is the part of the outline that is never dug.
        bands: list[tuple[str | None, float, float]] = []
        ceiling = self.domain.y_top
        for index, level in enumerate(self.excavation.levels, start=1):
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

    def expand_body_keys(self, keys: list[str]) -> list[str]:
        """Turn a list that may name soil *layers* into one naming soil *bodies*.

        A staged layer is several bodies -- the lifts it is dug in, plus what is left
        below the floor -- and the parts of the app that let a user pick soil pick
        layers, because that is what a user drew: the Mesh properties dialog lists
        `project.layers` (`live/js/mesh-settings.js`). Naming a layer therefore has to
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

    @computed_field
    @property
    def stageable_parts(self) -> list[str]:
        """`stageable_keys`, published with the project.

        The browser resolves the phase tree too (`live/js/phases.js`), and resolving it
        starts from "everything is active" -- so it needs the same namespace the server
        starts from. It cannot derive it: the staging namespace is `part_keys` plus
        every load id, and a `layered_soil` project draws no load pads, so a load that
        a phase may legitimately name appears nowhere the viewport can see.

        Named `stageable_parts` rather than `stageable_keys` because a computed field
        may not share a name with a method on the same model.
        """
        return self.stageable_keys()

    def stageable_keys(self) -> list[str]:
        """What a phase may switch on and off, which is wider than what is drawn.

        `part_keys` is the *render* namespace, in draw order, and the simple example
        deliberately draws no load pads -- so a project built that way has line loads
        that appear nowhere in it. They are still real parts of the deck: the reference
        stages one, `Load`, which arrives with the wall and stays. A phase has to be
        able to name them, so the staging namespace is `part_keys` plus every load id.

        Everything drawn is stageable; not everything stageable is drawn. The two are
        kept as separate lists rather than by widening `part_keys`, which would change
        draw order: `part_keys` feeds tessellation, and a key appearing there makes the
        viewport look for geometry that a load pad in the simple example does not have.
        """
        if self.deck is not None:
            # A deck's phases are its stages, and they switch the deck's own parts.
            return list(self.deck.parts)
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
