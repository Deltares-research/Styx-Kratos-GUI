"""Project -> OpenCASCADE B-rep solids -> physical groups.

This module is where the mockup stops pretending. js/viewport.js invents the model from
six constants with BoxGeometry and CylinderGeometry, so nothing has volume, nothing is
connected, and the five-box hand-split at js/viewport.js:83-88 stands in for a boolean.
Here OCC owns a real solid model that can be measured and meshed.

Two rules govern the code below:

*   **Never cache a bare tag across a boolean.** OCC booleans delete their inputs and
    mint new tags. Every boolean returns an `outDimTagsMap` indexed by the concatenated
    `objects + tools` argument list, and ownership is rebuilt from that map each time.
*   **`synchronize()` exactly once, at the end.** Nothing outside the `occ` namespace
    sees the model before it, and skipping it fails silently — `getEntities(3)` simply
    returns `[]`.

gmsh is a process-global singleton, so callers own the lifecycle: use `session()` in
tests, or the long-lived single worker process in production.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

import gmsh

from core.model.schemas import Anchor, Project, SpaceAnchor

# When a fragment output volume comes from several inputs, the structure wins over the
# soil it displaces, and the more specific structure wins over the more general. The
# walers, for instance, are buried inside the wall ring but are steel, not concrete.
PRIORITY = ["struts", "anchors", "piles", "wells", "wall"]

# Built after the booleans and never fragmented: a surface load is a kN/m2 boundary
# condition and the phreatic level is a reference plane. Their slabs are indicators, and
# letting them cut the soil would split volumes and change the mesh for nothing.
DISPLAY_ONLY = ["load", "water"]

TOLERANCE = 1e-6
"""Metres. How close an anchor head must be to a sheet pile to split it there."""


@dataclass
class BuildResult:
    volumes: dict[str, list[int]]
    """Part key -> OCC entity tags, of dimension `dim`. Keys are exactly
    `Project.part_keys()`. The name is historical: in a 2D project these are the
    surfaces of the section, not volumes. A key whose part does not reach the section
    plane maps to an empty list rather than disappearing, so the frontend's
    `userData.key` namespace is the same in both dimensions."""

    mass: dict[str, float]
    """Part key -> total volume in m3, or in 2D total area in m2 (per metre run)."""

    bbox: tuple[float, float, float, float, float, float]
    log: list[str] = field(default_factory=list)

    dim: int = 3
    """3 for the solid model, 2 for a plane-strain section."""

    tie_nodes: dict[str, int] = field(default_factory=dict)
    """Anchor key -> the 0D entity tag at its tail. `meshing` makes these visible so
    the mesh puts a node exactly there; the exporter then has both ends of the tie."""

    curves: dict[str, list[int]] = field(default_factory=dict)
    """Part key -> 1D entity tags for structural members meshed as line elements: the
    sheet piles, and the anchors that will follow. Unlike `overlays` these are real
    finite elements, and unlike `volumes` they are one dimension below the model -- a
    beam embedded in a 2D section is a curve inside a surface, sharing its nodes."""

    ties: dict[str, list[int]] = field(default_factory=dict)
    """Anchor key -> 1D entity tags. Separate from `curves` because an anchor is meshed
    and exported differently from a sheet pile: it is deliberately *not* embedded in the
    soil, and it becomes a two-node truss rather than a beam."""

    faces: dict[str, list[int]] = field(default_factory=dict)
    """Part key -> 2D entity tags for the 3D wall panels: shells fragmented into the
    solid so wall and soil share their nodes. What `curves` is to a 2D section, this is
    to the 3D model -- structural finite elements one dimension below the continuum they
    stand in. A 3D member is a curve and stays in `curves`."""

    overlays: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    """Part key -> (dim, tag) pairs for custom parts with no volume -- a drawn line or a
    bare surface. These never take part in a boolean or a fragment (there is nothing to
    cut), so they live outside `volumes` and are display-only, the same status load/water
    already have."""


@contextmanager
def session():
    """Own a gmsh instance for the duration of a block.

    Re-entrant: only the outermost caller initializes and finalizes. gmsh tracks one
    process-global `isInitialized` flag, so a nested block that finalized on exit would
    tear down the model its caller is still using.

    Production runs one long-lived `gmsh.initialize()` per worker process and calls
    `build_geometry` repeatedly; repeated initialize/finalize cycles are a documented
    source of trouble.
    """
    owned = not gmsh.isInitialized()
    if owned:
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
    try:
        yield
    finally:
        if owned:
            gmsh.finalize()


def bounding_box(tags: list[int], dim: int = 3,
                  fallback: tuple[float, float, float, float, float, float] | None = None
                  ) -> tuple[float, float, float, float, float, float]:
    """Union bounding box of some volumes, as (xmin, ymin, zmin, xmax, ymax, zmax).

    Conservative, not tight. OCC's `Bnd_Box` bounds a curved face by its control hull
    rather than the surface, so a solid with a bored hole or an oblique cylinder reports
    a box some centimetres larger than its true extent. Harmless at this scale -- it is
    used for camera framing -- but do not treat it as a measurement.

    `tags` is empty for a project with no soil layers and no custom parts (a blank
    project) -- there is nothing to union, so the camera frames on `fallback` instead.
    """
    if not tags:
        if fallback is None:
            raise ValueError("bounding_box: no volumes and no fallback given")
        return fallback
    boxes = [gmsh.model.getBoundingBox(dim, tag) for tag in tags]
    return (
        min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
        max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes),
    )


def build_geometry(project: Project) -> BuildResult:
    """Rebuild the current gmsh model from the project. Returns tags per part key."""
    if project.layered_soil:
        return _build_layered_soil(project)
    gmsh.logger.start()
    try:
        gmsh.clear()
        gmsh.model.add("model")

        notes: list[str] = []
        owners, overlays = _build_solids(project, notes)
        # One excavation level is an unstaged pit: a void, cut away before anything else
        # touches it. Several means it is dug in lifts, each removed in its own stage,
        # so the soil has to stay in the model to be staged (`_stage_bodies`).
        owners = (_stage_bodies(project, owners) if len(project.pit_levels()) > 1
                  else _cut_the_pit(project, owners))

        dim = 3
        if project.dimension == 2:
            # Section before fragmenting: the faces are what has to be made conformal,
            # and fragmenting the solids first would only be work thrown away.
            dim = 2
            owners = _section(owners, project.cut_at(), notes)
            overlays = _drop_overlays(overlays, notes)

        owners = _fragment(owners, dim)
        owners = _imprint_load_footprints(project, owners, dim)
        owners, curves, faces, points = _embed_beams(project, owners, dim, notes)
        ties, tie_nodes = _attach_anchors(project, dim, notes)

        volumes = _assign_by_priority(owners)
        volumes.update(_build_display_only(project, dim, notes))

        gmsh.model.occ.synchronize()

        # `excavation` is the soil block with the pit removed, shown in place of the
        # individual layers in staged-construction mode (js/viewport.js:404,426). The
        # backend already removed the pit, so it is the same material under one key --
        # an alias, not a second copy. A volume may belong to several physical groups.
        volumes["excavation"] = [t for key, tags in volumes.items()
                                 if key.startswith("soil_") for t in tags]

        # A part with nothing in the section keeps its key with an empty list, so the
        # frontend's userData.key namespace does not change between 2D and 3D. Only in
        # 2D: in 3D a key absent from `volumes` is a display-only overlay, and adding an
        # empty entry for it would claim it has geometry it does not have.
        if dim == 2:
            for key in project.part_keys():
                volumes.setdefault(key, [])

        _tag_physical_groups(volumes, dim)
        _tag_physical_groups(faces, 2, clear=False)
        _tag_physical_groups(curves, 1, clear=False)
        _tag_physical_groups(points, 0, clear=False)
        _tag_physical_groups(ties, 1, clear=False)
        _tag_physical_groups({key: [tag] for key, tag in tie_nodes.items()}, 0,
                             clear=False, suffix="_Support")
        _verify(project, volumes, overlays, {**curves, **ties})

        return BuildResult(
            volumes=volumes,
            mass={key: sum(gmsh.model.occ.getMass(dim, t) for t in tags)
                  for key, tags in volumes.items()},
            bbox=bounding_box([t for tags in volumes.values() for t in tags], dim,
                              fallback=(project.domain.x0, project.domain.y_bottom,
                                        project.domain.z0, project.domain.x1,
                                        project.domain.y_top, project.domain.z1)),
            log=notes + gmsh.logger.get(),
            dim=dim,
            curves=curves,
            faces=faces,
            ties=ties,
            tie_nodes=tie_nodes,
            overlays=overlays,
        )
    finally:
        gmsh.logger.stop()


def _build_layered_soil(project: Project) -> BuildResult:
    """Soil as the layer stack itself, plus whatever the user drew.

    One box per layer across the whole domain, the drawn beams/anchors/interfaces/custom
    parts embedded in it, and no excavation void unless the pit is staged. What this
    path does *not* do is raise the seeded demo structures -- the 3D wall ring, strut
    frame and pile group `_build_solids` makes -- which is the whole of the difference
    and the reason `Project.layered_soil` is named for the soil rather than for the
    example it was first written to serve.
    """
    gmsh.logger.start()
    try:
        gmsh.clear()
        gmsh.model.add("simple-cube")
        d = project.domain
        borehole = project.borehole_ids()[0]
        owners = {}
        for layer in project.layers:
            bottom, top = layer.bots[borehole], layer.tops[borehole]
            tag = gmsh.model.occ.addBox(d.x0, bottom, d.z0, d.dx, top - bottom, d.dz)
            owners[tag] = {f"soil_{layer.id}"}

        # Same gate as the full build: several excavation levels means the soil in the
        # pit is dug lift by lift and has to stay in the model to be staged. This path
        # never cuts a pit at all, so an unstaged project is untouched by it.
        if len(project.pit_levels()) > 1:
            owners = _stage_bodies(project, owners)

        notes: list[str] = []
        custom_volumes, overlays = _import_custom_parts(project.custom_parts, notes)
        for tag, key in custom_volumes.items():
            owners[tag] = {key}

        dim = 3
        if project.dimension == 2:
            dim = 2
            owners = _section(owners, project.cut_at(), notes)
            overlays = _drop_overlays(overlays, notes)

        owners, curves, faces, points = _embed_beams(
            project, _imprint_load_footprints(project, _fragment(owners, dim), dim),
            dim, notes,
        )
        ties, tie_nodes = _attach_anchors(project, dim, notes)
        volumes = _assign_by_priority(owners)
        if dim == 2:
            for key in project.part_keys():
                volumes.setdefault(key, [])
        gmsh.model.occ.synchronize()
        _tag_physical_groups(volumes, dim)
        _tag_physical_groups(faces, 2, clear=False)
        _tag_physical_groups(curves, 1, clear=False)
        _tag_physical_groups(points, 0, clear=False)
        _tag_physical_groups(ties, 1, clear=False)
        _tag_physical_groups({key: [tag] for key, tag in tie_nodes.items()}, 0,
                             clear=False, suffix="_Support")
        tags = [tag for values in volumes.values() for tag in values]
        return BuildResult(
            volumes=volumes,
            mass={key: sum(gmsh.model.occ.getMass(dim, tag) for tag in tags)
                  for key, tags in volumes.items()},
            bbox=bounding_box(tags, dim,
                              fallback=(project.domain.x0, project.domain.y_bottom,
                                        project.domain.z0, project.domain.x1,
                                        project.domain.y_top, project.domain.z1)),
            log=notes + gmsh.logger.get(),
            dim=dim,
            curves=curves,
            faces=faces,
            ties=ties,
            tie_nodes=tie_nodes,
            overlays=overlays,
        )
    finally:
        gmsh.logger.stop()


# ── Primitives ──────────────────────────────────────────────────────────────

def _build_solids(project: Project, log: list[str] | None = None
                  ) -> tuple[dict[int, set[str]], dict[str, list[tuple[int, int]]]]:
    """Every solid that takes part in the booleans, plus any display-only overlays.

    Returns (tag -> owning part keys, part key -> (dim, tag) pairs for custom parts with
    no volume).
    """
    p, d, e = project, project.domain, project.pit()
    # The validator refuses a full build without them; this tells the type checker.
    wall, struts, anchor_rows, piles, wells = p.wall, p.struts, p.anchor_rows, p.piles, p.wells
    if wall is None or struts is None or anchor_rows is None or piles is None or wells is None:
        raise ValueError("the full build needs the seeded demo's wall, struts, anchor rows, "
                         "piles and wells")
    owners: dict[int, set[str]] = {}

    def own(tag: int, key: str) -> int:
        owners.setdefault(tag, set()).add(key)
        return tag

    def box(x0, x1, y0, y1, z0, z1, key):
        """An axis-aligned box in world coordinates: x across, y up, z out of plane."""
        return own(gmsh.model.occ.addBox(x0, y0, z0, x1 - x0, y1 - y0, z1 - z0), key)

    # Soil layers span the domain in plan and are flat-bottomed. The frozen viewport
    # extrudes from the bh1 column only (js/viewport.js:75,100) and ignores the other
    # two boreholes; dipping layer surfaces are a later change, made here once.
    bh = p.borehole_ids()[0]
    for layer in p.layers:
        box(d.x0, d.x1, layer.bots[bh], layer.tops[bh], d.z0, d.z1, f"soil_{layer.id}")

    t, w = wall.thickness, wall
    outer = box(e.x0 - t, e.x1 + t, w.toe_y, w.top_y, e.z0 - t, e.z1 + t, "wall")
    inner = gmsh.model.occ.addBox(e.x0, w.toe_y, e.z0,
                                  e.x1 - e.x0, w.top_y - w.toe_y, e.z1 - e.z0)
    ring, _ = gmsh.model.occ.cut([(3, outer)], [(3, inner)])
    del owners[outer]
    for _, tag in ring:
        own(tag, "wall")

    s = struts
    span = (e.z1 + s.overhang) - (e.z0 - s.overhang)
    for x in s.xs:
        own(gmsh.model.occ.addCylinder(x, s.y, e.z0 - s.overhang, 0, 0, span, s.radius),
            "struts")
    for z in (e.z0 - s.waler_offset, e.z1 + s.waler_offset):
        box(e.x0, e.x1,
            s.y - s.waler_height / 2, s.y + s.waler_height / 2,
            z - s.waler_width / 2, z + s.waler_width / 2, "struts")

    a = anchor_rows
    reach = math.cos(math.radians(a.inclination_deg)) * a.length
    drop = math.sin(math.radians(a.inclination_deg)) * a.length
    for z_head, direction in ((e.z0 - t + a.head_offset, -1.0), (e.z1 + t - a.head_offset, 1.0)):
        for x in a.xs:
            own(gmsh.model.occ.addCylinder(
                x, a.head_y, z_head, 0, -drop, direction * reach, a.radius), "anchors")

    for x in piles.xs:
        for z in piles.zs:
            own(gmsh.model.occ.addCylinder(
                x, piles.top_y - piles.length, z,
                0, piles.length, 0, piles.radius), "piles")

    for x, z in wells.positions:
        own(gmsh.model.occ.addCylinder(
            x, wells.top_y - wells.length, z,
            0, wells.length, 0, wells.radius), "wells")

    # Import any custom parts
    custom_volumes, overlays = _import_custom_parts(p.custom_parts, log)
    for tag, key in custom_volumes.items():
        own(tag, key)

    return owners, overlays


def _import_custom_parts(
    custom_parts: list, log: list[str] | None = None,
) -> tuple[dict[int, str], dict[str, list[tuple[int, int]]]]:
    """Import each custom part's brep exactly once, split by whether it has a volume.

    A drawn box or an imported STEP file contributes a dim-3 tag that goes on to fragment
    and boolean with the rest of the model. A drawn line or bare surface has nothing to
    fragment -- it is display-only, so its dim-1/dim-2 tags are kept separate and never
    passed to `occ.fragment`, which only accepts dim-3 inputs.
    """
    volumes: dict[int, str] = {}
    overlays: dict[str, list[tuple[int, int]]] = {}
    for custom in custom_parts:
        if not (custom.source_file and os.path.exists(custom.source_file)):
            if log is not None:
                log.append(f"Info    : {custom.label} ({custom.key}) is not in the model: "
                           f"its solid {custom.source_file} is not there, and nothing says "
                           "how to build it again; import it again")
            continue
        for dim, tag in gmsh.model.occ.importShapes(custom.source_file):
            if dim == 3:
                volumes[tag] = custom.key
            elif dim in (1, 2):
                overlays.setdefault(custom.key, []).append((dim, tag))
    return volumes, overlays


def _build_display_only(project: Project, dim: int = 3,
                       log: list[str] | None = None) -> dict[str, list[int]]:
    p, d = project, project.domain
    loads = {}
    # `loads_for` rather than `p.loads`: a translated pair holds a surface record and a
    # line record for one load, and drawing both would show it twice.
    for load in p.loads_for(dim):
        # A 2D load has a symbol in either model. In the section it is drawn across the
        # full out-of-plane depth, because the section has none to speak of; in the
        # solid model it is drawn *at the cut*, one thickness wide, so it reads as the
        # plane-strain condition it is rather than as a load over the whole width.
        if load.kind == "point":
            loads[load.id] = [gmsh.model.occ.addSphere(
                load.x, load.y, project.cut_at(), load.thickness,
            )]
        elif load.kind == "line":
            z0, depth = ((d.z0, d.dz) if dim == 2
                         else (project.cut_at() - load.thickness / 2.0, load.thickness))
            loads[load.id] = [gmsh.model.occ.addBox(
                load.x0, load.y, z0,
                load.x1 - load.x0, load.thickness, depth,
            )]
        elif dim == 3 and load.kind == "surface":
            # `ground_y`, not `d.y_top`: the symbol belongs on top of the model, and a
            # drawn embankment puts that above the borehole block.
            loads[load.id] = [gmsh.model.occ.addBox(
                load.x0, project.elevation_of(load), load.z0,
                load.x1 - load.x0, load.thickness, load.z1 - load.z0,
            )]

    # A normal load draws no solid of its own: its symbol is the arrows the viewport
    # puts on the loaded line (frontend/js/viewport.js's `normalLoadGlyphSpec`). The strip
    # that used to be built here stood proud of the model -- a bar lying on top of the
    # loaded face rather than a load applied to it.

    built = dict(loads)
    wa = p.water
    # A dry model has no level to draw.
    if wa is not None:
        built["water"] = [gmsh.model.occ.addBox(
            d.x0 - wa.margin, wa.y - wa.thickness / 2, d.z0 - wa.margin,
            d.dx + 2 * wa.margin, wa.thickness, d.dz + 2 * wa.margin,
        )]
    if dim == 3:
        return built

    # Sectioned by the same helper as everything else, so "the load pad is not in
    # this section" needs no special case. Never fragmented, in either dimension:
    # these are indicators, and letting them cut the model would change the mesh.
    owners = {tag: {key} for key, tags in built.items() for tag in tags}
    sectioned = _assign_by_priority(_section(owners, project.cut_at(), log))
    return {key: sectioned.get(key, []) for key in built}


# ── Booleans ────────────────────────────────────────────────────────────────

def _cut_the_pit(project: Project, owners: dict[int, set[str]]) -> dict[int, set[str]]:
    """Remove the excavated void from the soil, before anything else touches it.

    Cutting here rather than fragmenting a pit solid and deleting the pieces afterwards
    keeps the intent local: only the soil is excavated. The struts hang in the void and
    the wells run through it, and neither needs a special case.
    """
    e, d = project.pit(), project.domain
    soil = [(3, tag) for tag, keys in owners.items() if any(k.startswith("soil_") for k in keys)]

    pit = gmsh.model.occ.addBox(e.x0, e.floor_y, e.z0,
                                e.x1 - e.x0, d.y_top - e.floor_y, e.z1 - e.z0)
    _, mapping = gmsh.model.occ.cut(soil, [(3, pit)])

    rebuilt = {tag: keys for tag, keys in owners.items() if (3, tag) not in soil}
    for (_, old), pieces in zip(soil, mapping):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])
    return rebuilt


def _stage_bodies(project: Project, owners: dict[int, set[str]]) -> dict[int, set[str]]:
    """Keep the excavated soil, split into the lifts it is dug in.

    The staged counterpart of `_cut_the_pit`, and its opposite: a staged excavation is
    dug lift by lift, each in its own stage, so the soil that will be removed has to
    exist in the mesh in order to be deactivated later. Cutting it away here would leave
    nothing to stage.

    The split is done by fragmenting the soil against one box per lift, which is what
    makes the seams conformal -- the two sides share their curves, and later their nodes,
    so `interfaces.py` still sees one set of shared nodes to duplicate rather than a
    mesh that is already torn. The pieces are then classified by centre of mass against
    `Project.soil_bodies`, the one authority on which bodies a project has: deriving the
    key from the geometry rather than from the boolean's output map is what keeps the
    two from disagreeing about how many bodies there are.
    """
    e, d = project.pit(), project.domain
    soil = [(3, tag) for tag, keys in owners.items()
            if any(k.startswith("soil_") for k in keys)]

    # One box per lift, plus one for the outline below the final floor: together they
    # cover the pit's full depth, so every seam the bodies need is cut exactly once.
    tools, ceiling = [], d.y_top
    for level in list(e.levels) + [d.y_bottom]:
        tools.append((3, gmsh.model.occ.addBox(e.x0, level, e.z0,
                                               e.x1 - e.x0, ceiling - level,
                                               e.z1 - e.z0)))
        ceiling = level

    _, mapping = gmsh.model.occ.fragment(soil, tools)

    # Only the pieces the soil became are soil. A tool covers ground the soil already
    # occupies, so its own pieces are the same entities; anything left over is the part
    # of a box outside every layer and is removed rather than left to be meshed.
    rebuilt = {tag: keys for tag, keys in owners.items() if (3, tag) not in soil}
    kept: set[int] = set()
    for (_, old), pieces in zip(soil, mapping[:len(soil)]):
        for _, tag in pieces:
            kept.add(tag)
            rebuilt.setdefault(tag, set()).update(owners[old])
    leftover = [(3, tag) for _, pieces in zip(tools, mapping[len(soil):])
                for _, tag in pieces if tag not in kept]
    if leftover:
        gmsh.model.occ.remove(leftover, recursive=True)

    return _key_staged_bodies(project, rebuilt, kept)


def _key_staged_bodies(project: Project, owners: dict[int, set[str]],
                       soil_tags: set[int]) -> dict[int, set[str]]:
    """Re-key each soil piece to the body it turned out to be.

    A piece inherited its layer's key from the fragment; which *body* of that layer it
    is -- a lift, the ground below the floor, or the untouched soil outside the outline
    -- is a question about where it ended up, so it is answered from its centre of mass
    against `Project.soil_bodies` rather than tracked through the boolean.
    """
    e = project.pit()
    bodies = project.soil_bodies()
    rebuilt: dict[int, set[str]] = {}
    for tag, keys in owners.items():
        if tag not in soil_tags:
            rebuilt[tag] = keys
            continue
        x, y, z = gmsh.model.occ.getCenterOfMass(3, tag)
        inside = (e.x0 < x < e.x1) and (e.z0 < z < e.z1)
        layer_keys = {k for k in keys if k.startswith("soil_")}
        match = next(
            (key for key, bottom, top, body_inside in bodies
             if body_inside == inside and bottom < y < top
             and key.split("__")[0] in layer_keys),
            None,
        )
        # No match means the piece is soil the body list does not describe, which would
        # otherwise be meshed under a layer key and silently double-count that layer.
        rebuilt[tag] = ({match} | (keys - layer_keys)) if match else keys
    return rebuilt


def _fragment(owners: dict[int, set[str]], dim: int = 3) -> dict[int, set[str]]:
    """Make every interface conformal, so the mesh matches across material boundaries."""
    inputs = [(dim, tag) for tag in owners]
    if len(inputs) < 2:
        # gmsh logs "too few arguments" and returns success with empty results, which
        # would surface later as a mystifying empty model.
        return owners

    _, mapping = gmsh.model.occ.fragment(inputs, [])

    rebuilt: dict[int, set[str]] = {}
    for (_, old), pieces in zip(inputs, mapping):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])
    return rebuilt


def _load_footprint_tools(project: Project, dim: int) -> list[tuple[int, int]]:
    """One boundary-coincident entity per active load, in this dimension's coordinates.

    A 2D load record is dimension-native `(x, y)`, so the tool is placed at the section
    offset along z -- the same world position `meshing.loaded_elements` reads a point
    load back at.
    """
    tools: list[tuple[int, int]] = []
    cut = project.cut_at() if dim == 3 else 0.0

    def point(x: float, y: float) -> int:
        return gmsh.model.occ.addPoint(x, y, cut)

    for load in project.loads_for(dim):
        if not load.active:
            continue
        # A point or line load is dimension-native, and imprints on the section plane
        # in either model: in 2D that plane *is* the model, and in 3D it is a line
        # across the solid's boundary at the cut. Same tool, same world position, so
        # `meshing.loaded_elements` reads it back the same way in both.
        if load.kind == "point":
            tools.append((0, point(load.x, load.y)))
        elif load.kind == "line":
            tools.append((1, gmsh.model.occ.addLine(point(load.x0, load.y),
                                                    point(load.x1, load.y))))
        elif dim == 3 and load.kind == "surface":
            # A pad lies flat on the ground, so its footprint is in the x-z plane at
            # the load's own elevation. `occ.addRectangle` only builds in x-y, so the
            # four corners are drawn directly instead.
            tools.append((2, _horizontal_rectangle(
                load.x0, load.x1, load.z0, load.z1, project.elevation_of(load),
            )))
    return tools


def _horizontal_rectangle(x0: float, x1: float, z0: float, z1: float,
                          y: float) -> int:
    """A flat plane surface in the x-z plane at elevation `y`.

    The counterpart of `occ.addRectangle`, which only builds in the x-y plane. A load
    pad and the ground surface it imprints are both horizontal, so with Y up the
    rectangle has to be drawn corner by corner.
    """
    corners = [gmsh.model.occ.addPoint(a, y, b)
               for a, b in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
    edges = [gmsh.model.occ.addLine(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(edges)])


def _clip_to_model(tools: list[tuple[int, int]],
                   inputs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep only the part of each tool that meets the model, tool by tool.

    A footprint may hang over the edge of the domain or over the excavated void. The
    overhang has no boundary to imprint, and left in place it becomes a free-floating
    surface at the load elevation -- which `meshing.loaded_elements` would then read
    back as loaded boundary. Intersecting first is what keeps the model clean.

    One boolean per tool, for the same reason `_section` runs one per volume: the
    result stays positional, with no `outDimTagsMap` to unpick across two lists.
    """
    clipped: list[tuple[int, int]] = []
    for dim, tag in tools:
        pieces, _ = gmsh.model.occ.intersect(
            [(dim, tag)], inputs, removeObject=True, removeTool=False,
        )
        clipped.extend(piece for piece in pieces if piece[0] == dim)
    return clipped


def _imprint_load_footprints(project: Project, owners: dict[int, set[str]],
                             dim: int) -> dict[int, set[str]]:
    """Split the model boundary exactly at the edges of every load footprint.

    Without this the exporter can only quantise a load to whole boundary elements by a
    centroid test, which moves a loaded edge by as much as one element. Each tool is
    coincident with the boundary it lands on -- a point or segment on a 2D section edge,
    a rectangle on the 3D top face -- so the fragment imprints that boundary instead of
    cutting through material: the faces below it are split, no volume is, and every part
    keeps its ownership.

    Tool pieces are dropped from the result. They carry no part key, and OCC has already
    merged the ones that coincide with the boundary into the entities it split.
    """
    if not owners:
        return owners
    tools = _load_footprint_tools(project, dim)
    if not tools:
        return owners

    inputs = [(dim, tag) for tag in owners]
    tools = _clip_to_model(tools, inputs)
    if not tools:
        return owners
    _, mapping = gmsh.model.occ.fragment(inputs, tools, removeTool=True)

    rebuilt: dict[int, set[str]] = {}
    for (_, old), pieces in zip(inputs, mapping[:len(inputs)]):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])
    return rebuilt


def _split_at(points: Sequence[tuple[float, ...]],
              heads: Sequence[tuple[float, ...]]) -> list[tuple[float, ...]]:
    """The polyline with every anchor head that lies on it inserted as a vertex.

    The head has to be a vertex of the beam for the mesh to put one node there and for
    the anchor to hang off it -- the reference deck shows exactly that, a head node
    sitting in two beam elements. Inserting it before the beam meets the soil is what
    keeps a single fragment doing all the work: splitting the curve afterwards would
    detach the pieces from the face they are embedded in.

    Dimension-agnostic, so a 3D member splits at a space anchor's head the same way a
    2D sheet pile splits at a plane anchor's.
    """
    if not heads:
        return list(points)
    out = [points[0]]
    for start, end in zip(points, points[1:]):
        delta = [b - a for a, b in zip(start, end)]
        length_squared = sum(d * d for d in delta)
        on_segment = []
        for head in heads:
            if length_squared == 0:
                continue
            t = sum((h - a) * d for h, a, d in zip(head, start, delta)) / length_squared
            if not 0.0 < t < 1.0:
                continue        # an end of the segment is already a vertex
            closest = [a + t * d for a, d in zip(start, delta)]
            if math.dist(head, closest) <= TOLERANCE:
                on_segment.append((t, tuple(head)))
        out.extend(head for _, head in sorted(on_segment))
        out.append(end)
    return out


def _embed_beams(project: Project, owners: dict[int, set[str]], dim: int,
                 log: list[str] | None = None
                 ) -> tuple[dict[int, set[str]], dict[str, list[int]], dict[str, list[int]],
                            dict[str, list[int]]]:
    """Fragment the section with each sheet pile, and keep the curves it leaves behind.

    The same imprint `_imprint_load_footprints` performs, with the opposite half of the
    result kept: a load only needs the boundary split, while a beam *is* the tool
    pieces. Because the fragment makes the soil and the curve share their edges, the
    mesher puts one node where both meet -- which is what a Kratos sheet-pile deck
    shows: every sheet-pile node in the ground is also a soil node.

    A pile that stops inside the soil does not separate the surface into two regions,
    so nothing is cut away; the curve simply becomes an internal edge of the face. The
    tools are clipped to the model afterwards, so a free interface, a load or a condition
    line drawn past the soil contributes only the part that has soil around it. A pile
    also keeps what stands out of the soil inside the model's box, above the ground or
    over an excavated void, as long as some of it is in the soil.

    A boundary condition at a point is a tool too, a vertex: the fragment makes it a
    vertex of the face it lies in, so the mesh has a node exactly there.

    Returns the rebuilt owners, the beam key -> curve tags map (also holding every
    free interface's, normal load's and boundary condition line's own curves, embedded
    the same way), the panel key -> face tags map (3D only; a 2D section has no wall
    panels in it), and the condition key -> point tags map of the condition points.
    """
    if dim == 3:
        return (*_embed_3d_structures(project, owners, log), {})
    if not owners:
        return owners, {}, {}, {}
    active = [beam for beam in project.sheet_piles if beam.active]
    # A 3D wall or member has no place in a plane-strain cut -- it is not drawn in the
    # section's plane and has no in-plane polyline to embed. Saying so is honest;
    # silently dropping it would read as a bug.
    for structure in project.structures_3d():
        if structure.active and log is not None:
            noun = "a wall panel" if structure.kind == "panel" else "a member"
            log.append(f"Info    : {structure.id} is {noun}, which is built in the 3D "
                       "model only; it is not part of this section")
    free = [i for i in project.active_interfaces if i.structure is None]
    normal_loads = project.active_normal_loads
    drawn = project.drawn_conditions
    if not active and not free and not normal_loads and not drawn:
        return owners, {}, {}, {}

    def point(x: float, y: float) -> int:
        """A 2D record's own coordinates: the section has been moved to z = 0."""
        return gmsh.model.occ.addPoint(x, y, 0.0)

    heads = [anchor.head for anchor in project.plane_anchors if anchor.active]
    tools: list[tuple[int, int]] = []
    owner_of_tool: list[str] = []
    for beam in active:
        vertices = [point(x, y) for x, y in _split_at(beam.points, heads)]
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(beam.id)

    # A free interface -- one drawn through the soil rather than along a pile -- needs
    # the same imprint for the same reason: the mesh can only be split along a line it
    # actually has edges on. It carries no elements of its own, so unlike a beam it is
    # only ever an internal edge; `core.kratos.interfaces` does the rest, after meshing.
    for interface in free:
        vertices = [point(x, y) for x, y in interface.points or []]
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(interface.id)

    # A normal load's polyline is embedded the same way and for the same reason: it
    # needs its own mesh edges to harvest a condition off, which is what lets
    # `core.kratos.writer._normal_load_conditions` find it without scanning the boundary
    # at a fixed elevation the way `meshing.loaded_elements` does for a flat `LineLoad`.
    for load in normal_loads:
        vertices = [point(x, y) for x, y in load.points]
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(load.id)

    # A boundary condition on a drawn line, for the same reason again: its nodes are the
    # ones on its own mesh edges (`core.kratos.writer._condition_targets`). One at a
    # point is a vertex the fragment embeds, and its node is the one on that vertex.
    for condition in drawn:
        vertices = [point(x, y) for x, y in condition.points or []]
        if condition.on == "point":
            tools.append((0, vertices[0]))
            owner_of_tool.append(condition.id)
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(condition.id)

    inputs = [(dim, tag) for tag in owners]

    # One fragment, tools included, rather than clipping each tool against the soil
    # first and fragmenting what survived. The clip cannot be done separately once a
    # line can lie *on* a face boundary rather than inside a face: a retaining wall
    # drawn along the edge of the pit is exactly that -- `_stage_bodies` leaves a seam
    # there between the ground being dug and the ground being retained -- and an
    # `occ.intersect` of a line with the surfaces it borders returns only parts of it,
    # so most of the wall would quietly vanish. Fragmenting together instead unifies
    # the line with the seam it lies on, which is what makes both sides share it.
    _, mapping = gmsh.model.occ.fragment(inputs, tools, removeTool=False)
    gmsh.model.occ.synchronize()

    rebuilt: dict[int, set[str]] = {}
    for (_, old), pieces in zip(inputs, mapping[:len(inputs)]):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])

    # The clip, done on the result rather than on the tools. A curve belongs to the
    # model if it either bounds one of the faces the fragment produced or runs through
    # the middle of one, and it takes both tests to tell those from a curve that is
    # simply outside:
    #
    # *   a curve that cuts a face in two, or lies on a seam between two, *bounds* them;
    # *   a curve that stops inside a face -- a pile that ends in the ground, which this
    #     function's docstring calls out -- bounds nothing at all, and gmsh reports no
    #     adjacency for it. By that test alone it is indistinguishable from a curve
    #     drawn off the edge of the model, so its midpoint is asked instead.
    def in_the_model(tag: int) -> bool:
        if any(surface in rebuilt for surface in gmsh.model.getAdjacencies(1, tag)[0]):
            return True
        x0, y0, z0, x1, y1, z1 = gmsh.model.getBoundingBox(1, tag)
        middle = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]
        return any(gmsh.model.isInside(2, surface, middle) for surface in rebuilt)

    # The tool half of the map: a curve the fragment split becomes several curves, and
    # every one of them still belongs to the beam it was drawn for.
    pieces_of: dict[str, list[int]] = {}
    for key, pieces in zip(owner_of_tool, mapping[len(inputs):]):
        pieces_of.setdefault(key, []).extend(
            tag for piece_dim, tag in pieces if piece_dim == 1)
    # A pile keeps the pieces that stand out of the soil, above the ground or over an
    # excavated void: a load at its head is carried down it into the ground. The project
    # holds a pile to the model's box (`Project.extent`), and its pieces join end to end,
    # so one piece in the soil keeps them all. Their nodes are the pile's own.
    piles = {beam.id for beam in active}
    beam_curves: dict[str, list[int]] = {}
    for key, tags in pieces_of.items():
        inside = [tag for tag in tags if in_the_model(tag)]
        if key in piles and inside:
            inside = tags
        if inside:
            beam_curves[key] = sorted(set(inside))
    if not beam_curves and log is not None:
        for beam in active:
            log.append(f"Info    : {beam.id} lies outside the soil in this section "
                       "and is not part of the model")
    # A point is in the model when it lies in or on one of the faces; one outside them
    # survives the fragment as a free vertex, and has no soil node to fix.
    points: dict[str, list[int]] = {}
    for key, pieces in zip(owner_of_tool, mapping[len(inputs):]):
        for piece_dim, tag in pieces:
            if piece_dim == 0 and any(
                    gmsh.model.isInside(2, surface,
                                        list(gmsh.model.getBoundingBox(0, tag)[:3]))
                    for surface in rebuilt):
                points.setdefault(key, []).append(tag)
    return rebuilt, beam_curves, {}, points


def _section_sweeps(project: Project, log: list[str] | None = None
                    ) -> list[tuple[str, list[int]]]:
    """Every 2D-native line structure, swept into a surface on the section plane.

    A sheet pile is an `(x, y)` polyline with no thickness and no out-of-plane extent,
    and the solid model has to give it both to have anything to mesh. It gets the one
    the profile already carries: `BeamSection.spacing`, the out-of-plane centres the
    plane-strain reduction smears the wall over. The sweep is centred on
    `section_offset`, so the wall sits *on* the cut it was drawn on rather than
    starting there and running off to one side.

    Free interfaces are swept the same way and for a narrower purpose: the imprint.
    Their zero-thickness elements are plane strain only (`core/kratos/writer.py`'s `INTERFACES`
    table), so the surface splits the mesh and nothing more -- which is still worth
    having, because it is what makes the interface visible in the solid model.

    Returns (part key, swept face tags), in the order the fragment should see them.
    """
    # A 2D record's two coordinates are the section's own axes, which are the world's
    # X and Y; the sweep is along Z, the axis the section has none of.
    spacings = {section.id: section.spacing for section in project.beam_sections}

    def sweep(key: str, points: Sequence[tuple[float, ...]], width: float
              ) -> tuple[str, list[int]] | None:
        start = project.cut_at() - width / 2.0
        vertices = [gmsh.model.occ.addPoint(x, y, start) for x, y in points]
        lines = [gmsh.model.occ.addLine(a, b) for a, b in zip(vertices, vertices[1:])]
        swept = gmsh.model.occ.extrude([(1, line) for line in lines], 0.0, 0.0, width)
        faces = [tag for entity_dim, tag in swept if entity_dim == 2]
        return (key, faces) if faces else None

    out: list[tuple[str, list[int]]] = []
    heads = [anchor.head for anchor in project.plane_anchors if anchor.active]
    # `structures_for` rather than `sheet_piles`: a pile the switch translated into a
    # wall panel is built as that panel, and sweeping it here as well would put two
    # walls in the same place. What is left is the piles with no panel form.
    swept = {b.id for b in project.structures_for(3)}
    for beam in project.sheet_piles:
        if not beam.active or beam.id not in swept:
            continue
        width = spacings.get(beam.section, 1.0)
        piece = sweep(beam.id, _split_at(beam.points, heads), width)
        if piece:
            out.append(piece)
        elif log is not None:
            log.append(f"Info    : {beam.id} could not be swept onto the section plane")

    for interface in project.active_interfaces:
        if interface.structure is not None or not interface.points:
            continue
        piece = sweep(interface.id, interface.points, INTERFACE_SWEEP)
        if piece:
            out.append(piece)
    if log is not None and any(i.structure is None for i in project.active_interfaces):
        log.append("Info    : interfaces are plane-strain elements; the ones drawn in "
                   "the section split this 3D mesh but export no interface elements")
    return out


def _embed_3d_structures(project: Project, owners: dict[int, set[str]],
                         log: list[str] | None = None
                         ) -> tuple[dict[int, set[str]], dict[str, list[int]],
                                    dict[str, list[int]]]:
    """Fragment the solid model with each wall panel and member.

    The 3D half of `_embed_beams`, and the same idea one dimension up: the structure is
    the tool, the soil is the input, and the fragment is what makes the two share their
    boundary -- so the mesher puts one node where a wall face meets the soil around it,
    exactly as it does for a sheet pile inside a section.

    A panel is a plan footprint swept down to its toe, which leaves a surface; a member
    is a polyline, which leaves curves. Both are clipped to the soil first, so a wall
    drawn past the domain edge or across the pit contributes only the part with ground
    around it. A wall that stops inside the body does not separate it: the face simply
    becomes an internal one, as an internal edge does in 2D.
    """
    built = {b.id for b in project.structures_for(3)}
    panels = [p for p in project.panels if p.active and p.id in built]
    members = [m for m in project.members if m.active and m.id in built]
    # A 2D sheet pile is drawn in the section, not in plan, but it is still somewhere
    # in the solid model: on the plane it was drawn on. Swept there rather than
    # dropped, so switching to 3D shows the wall the section was built around instead
    # of an empty box. Interfaces ride along for the imprint alone -- see `_section_
    # sweeps`.
    section_lines = _section_sweeps(project, log)
    if not owners or not (panels or members or section_lines):
        return owners, {}, {}

    # An anchor drawn in the section hangs off a wall the section drew too, and after
    # the switch that wall is a panel. Its head is `(x, y)`, so it is placed on the cut
    # to be imprinted alongside the space anchors' -- the surface counterpart of the
    # vertex `_split_at` gives it in 2D.
    def at_cut(x: float, y: float) -> tuple[float, float, float]:
        return (x, y, project.cut_at())

    heads = [anchor.head for anchor in project.space_anchors if anchor.active]
    heads += [at_cut(*anchor.head) for anchor in project.plane_anchors if anchor.active]
    tools: list[tuple[int, int]] = []
    owner_of_tool: list[str] = []

    # Placed before the panels so a swept pile is fragmented by the same boolean, and
    # so a plane anchor's head lands on a vertex of it exactly as `_split_at` puts one
    # on a member.
    for key, faces_of in section_lines:
        for tag in faces_of:
            tools.append((2, tag))
            owner_of_tool.append(key)

    for panel in panels:
        # Swept from the top down: extruding the footprint's lines gives one face per
        # segment, which is what a wall in plan is.
        vertices = [gmsh.model.occ.addPoint(x, panel.y_top, z)
                    for x, z in panel.footprint]
        lines = [gmsh.model.occ.addLine(start, end)
                 for start, end in zip(vertices, vertices[1:])]
        swept = gmsh.model.occ.extrude([(1, line) for line in lines],
                                       0.0, panel.y_toe - panel.y_top, 0.0)
        for entity_dim, tag in swept:
            if entity_dim == 2:
                tools.append((2, tag))
                owner_of_tool.append(panel.id)

    for member in members:
        vertices = [gmsh.model.occ.addPoint(*point)
                    for point in _split_at(member.points, heads)]
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(member.id)

    inputs = [(3, tag) for tag in owners]
    kept: list[tuple[int, int]] = []
    kept_owners: list[str | None] = []
    for tool, key in zip(tools, owner_of_tool):
        pieces, _ = gmsh.model.occ.intersect(
            [tool], inputs, removeObject=True, removeTool=False,
        )
        for piece in pieces:
            if piece[0] == tool[0]:
                kept.append(piece)
                kept_owners.append(key)
    if not kept:
        if log is not None:
            for structure in panels + members:
                log.append(f"Info    : {structure.id} lies outside the soil and is not "
                           "part of the model")
        return owners, {}, {}

    # An anchor head on a wall has to be a node of the wall's own mesh, and a vertex
    # imprinted by this same fragment is what puts one there. It is the surface
    # counterpart of `_split_at`, which gives a member its head vertex directly, and it
    # has to ride along in the one boolean for the same reason: imprinting afterwards
    # would detach the face from the volume it was just made conformal with.
    for head in heads:
        kept.append((0, gmsh.model.occ.addPoint(*head)))
        kept_owners.append(None)

    _, mapping = gmsh.model.occ.fragment(inputs, kept, removeTool=False)

    rebuilt: dict[int, set[str]] = {}
    for (_, old), pieces in zip(inputs, mapping[:len(inputs)]):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])

    # The tool half of the map, split by what each structure is made of: a wall is
    # faces, a member is curves, and the fragment may have cut either into several.
    faces: dict[str, list[int]] = {}
    curves: dict[str, list[int]] = {}
    for owner, pieces in zip(kept_owners, mapping[len(inputs):]):
        if owner is None:      # an imprinted anchor head belongs to no structure
            continue
        for piece_dim, tag in pieces:
            if piece_dim == 2:
                faces.setdefault(owner, []).append(tag)
            elif piece_dim == 1:
                curves.setdefault(owner, []).append(tag)
    curves = {key: sorted(set(tags)) for key, tags in curves.items()}
    faces = {key: sorted(set(tags)) for key, tags in faces.items()}
    _embed_curves_in_volumes(curves, list(rebuilt), log)
    return rebuilt, curves, faces


def _embed_curves_in_volumes(curves: dict[str, list[int]], volumes: list[int],
                             log: list[str] | None) -> None:
    """Force each member curve into the volume mesh around it.

    A wall face survives the fragment as an internal boundary the mesher recovers on its
    own. A curve does not, once a face is in the same model: OCC keeps it as geometry
    but the volume mesher stops treating it as a constraint, and the pile ends up meshed
    beside the soil rather than through it -- one line of nodes the tetrahedra never
    touch. `mesh.embed` is gmsh's own answer to exactly this, and it needs the volume
    each curve lies in, which is the one whose box holds the curve's midpoint.

    Left as a note rather than an exception when a curve cannot be placed: the deck is
    still valid, the wall or member simply meshes unbonded, and test_kratos_3d.py checks
    the shared nodes where it matters.
    """
    if not curves:
        return
    gmsh.model.occ.synchronize()
    boxes = {tag: gmsh.model.getBoundingBox(3, tag) for tag in volumes}
    for key, tags in curves.items():
        for tag in tags:
            # A curve that already bounds a face is part of the model's topology and
            # is meshed with it -- embedding it again is both unnecessary and an
            # error. Asking first is what keeps this off gmsh's exception path.
            if gmsh.model.getAdjacencies(1, tag)[0].size:
                continue
            point = gmsh.model.occ.getCenterOfMass(1, tag)
            host = next((volume for volume, box in boxes.items()
                         if all(box[i] - TOLERANCE <= point[i] <= box[i + 3] + TOLERANCE
                                for i in range(3))), None)
            if host is None:
                note = f"{key} lies in no soil volume"
            else:
                try:
                    gmsh.model.mesh.embed(1, [tag], 3, host)
                    continue
                except Exception as error:   # gmsh raises a bare Exception
                    note = f"{key} could not be embedded in volume {host} ({error})"
            if log is not None:
                log.append(f"Info    : {note}; it is meshed unbonded from the soil")


def _attach_anchors(project: Project, dim: int, log: list[str] | None = None
                    ) -> tuple[dict[str, list[int]], dict[str, int]]:
    """Draw each anchor and give its tail a node, without touching the model topology.

    Deliberately *not* fragmented into anything. The tail is a node that belongs to no
    element at all, held by its own node group: the grouted body is idealised as a fixed point, so embedding the
    tie in the soil would model a fully bonded bar instead. The head needs no fragment
    either -- `_split_at` has already made it a vertex of the beam, which is where the
    shared node comes from.

    Returns the anchor key -> display curve tags, and the anchor key -> tail point tag
    that `meshing` makes visible so a node lands exactly on it.
    """
    # Each dimension draws its own kind and says so about the other's: an anchor drawn
    # in a section has no place in the solid model, and one drawn in space has none in
    # the section, for the same reason their structures do not cross over either.
    # A 2D section has been moved to z = 0; in the solid model the same record sits on
    # the cut it was drawn on.
    cut = project.cut_at() if dim == 3 else 0.0

    def in_plane(x: float, y: float) -> int:
        """A dimension-native `(x, y)` end, placed on the cut it was drawn on."""
        return gmsh.model.occ.addPoint(x, y, cut)

    def in_space(x: float, y: float, z: float) -> int:
        return gmsh.model.occ.addPoint(x, y, z)

    # An anchor drawn in the section belongs to the solid model too -- it hangs off a
    # sheet pile, and `_section_sweeps` has just put that pile on the section plane.
    # One anchor, on the plane: a plane-strain record says where the tie is in the
    # section, not how many of them run out of plane.
    plane: list[tuple[Anchor | SpaceAnchor, Callable[..., int]]] = [
        (a, in_plane) for a in project.plane_anchors if a.active]
    space: list[tuple[Anchor | SpaceAnchor, Callable[..., int]]] = [
        (a, in_space) for a in project.space_anchors if a.active]
    if dim == 3:
        active, skipped = plane + space, []
    else:
        active, skipped = plane, [a for a, _ in space]
    for anchor in skipped:
        if log is not None:
            log.append(f"Info    : {anchor.id} is an anchor drawn in space; it is not "
                       "part of this section")
    if not active:
        return {}, {}

    curves: dict[str, list[int]] = {}
    tails: dict[str, int] = {}
    for anchor, point in active:
        head, tail = point(*anchor.head), point(*anchor.tail)
        curves[anchor.id] = [gmsh.model.occ.addLine(head, tail)]
        tails[anchor.id] = tail
    return curves, tails


# ── The plane-strain section ────────────────────────────────────────────────

SECTION_PAD = 1.0
"""Metres the cutting plane extends past the model, so nothing is clipped by it.

Sized from the built solids rather than the domain: the wall top (0.6 m above y_top)
and any drawn or imported part can legitimately stick out of the declared domain.
"""


INTERFACE_SWEEP = 1.0
"""Metres a free interface is swept out of plane, so it has a surface to imprint with.

Arbitrary in a way `BeamSection.spacing` is not: an interface carries no out-of-plane
dimension of its own, and this one only has to be wide enough to cut the mesh.
"""


def _section_extents(tags: list[int]) -> tuple[float, float, float, float]:
    """The span the cutting plane must cover, as (x0, x1, y0, y1).

    Measured once, before any boolean runs. `_section` removes each volume as it cuts
    it, so measuring inside that loop reads a tag OCC has already deleted.
    """
    boxes = [gmsh.model.occ.getBoundingBox(3, tag) for tag in tags]
    return (min(b[0] for b in boxes) - SECTION_PAD, max(b[3] for b in boxes) + SECTION_PAD,
            min(b[1] for b in boxes) - SECTION_PAD, max(b[4] for b in boxes) + SECTION_PAD)


def _section_plane(extents: tuple[float, float, float, float], offset: float) -> int:
    """An x-y plane surface at z = `offset`, spanning the whole model."""
    x0, x1, y0, y1 = extents
    corners = [gmsh.model.occ.addPoint(a, b, offset)
               for a, b in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    edges = [gmsh.model.occ.addLine(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(edges)])


def _section(owners: dict[int, set[str]], offset: float,
             log: list[str] | None = None) -> dict[int, set[str]]:
    """Cut the solids with the section plane and keep the faces, with their owners.

    One boolean per volume rather than one batched over all of them. `occ.intersect`
    consumes its arguments and returns an `outDimTagsMap` indexed by the concatenated
    object + tool list, so a batched call would have to be unpicked across both lists
    to answer "which part did this face come from". Per-volume, ownership is positional
    and there is nothing to unpick -- and a plane is a cheap solid to boolean against.

    A volume that misses the plane contributes nothing. That is the correct plane-strain
    answer -- a pile row at another z is genuinely not in this section -- but it is
    logged, because a part silently vanishing otherwise reads as a boolean failure.

    The faces are moved to z = 0 afterwards, which is what makes the 2D model *be* the
    x-y plane rather than a plane parked somewhere out along z. No rotation is needed:
    the section's own axes are already X and Y.
    """
    if not owners:
        return {}
    extents = _section_extents(list(owners))

    rebuilt: dict[int, set[str]] = {}
    for tag, keys in owners.items():
        # A fresh plane each time: intersect deletes the object it was given.
        cutter = _section_plane(extents, offset)
        pieces, _ = gmsh.model.occ.intersect(
            [(2, cutter)], [(3, tag)], removeObject=True, removeTool=True
        )
        faces = [t for dim, t in pieces if dim == 2]
        if not faces and log is not None:
            log.append(f"Info    : {', '.join(sorted(keys))} does not reach the section "
                       f"plane at z = {offset} and is not part of this 2D model")
        for face in faces:
            rebuilt.setdefault(face, set()).update(keys)
    if rebuilt and offset:
        gmsh.model.occ.translate([(2, tag) for tag in rebuilt], 0.0, 0.0, -offset)
    return rebuilt


def _assign_by_priority(owners: dict[int, set[str]]) -> dict[str, list[int]]:
    """One part key per volume, so nothing is drawn or meshed twice."""
    out: dict[str, list[int]] = {}
    for tag, keys in owners.items():
        chosen = next((k for k in PRIORITY if k in keys), None)
        if chosen is None:
            # Custom parts win over soil
            customs = [k for k in keys if not k.startswith("soil_")]
            if customs:
                chosen = sorted(customs)[0]
            else:
                chosen = sorted(keys)[0]      # soil only; layers never overlap
        out.setdefault(chosen, []).append(tag)
    return {key: sorted(tags) for key, tags in out.items()}


# ── Output ──────────────────────────────────────────────────────────────────

def _tag_physical_groups(volumes: dict[str, list[int]], dim: int = 3,
                         clear: bool = True, suffix: str = "") -> None:
    """Physical groups do not survive booleans, so they are created last, after sync.

    The names are the contract with the frozen frontend: each one is a `userData.key` on
    a picked mesh and an `obj:` on a model-tree node.

    `clear=False` adds a second dimension's groups to the ones already tagged, for a
    model that is mixed-dimensional: 2D soil with 1D sheet piles inside it.
    """
    if clear:
        gmsh.model.removePhysicalGroups([])
    for key, tags in volumes.items():
        if tags:      # a part absent from a 2D section has no entities to group
            gmsh.model.addPhysicalGroup(dim, tags, name=key + suffix)


def _drop_overlays(overlays: dict[str, list[tuple[int, int]]],
                   log: list[str]) -> dict[str, list[tuple[int, int]]]:
    """Display-only custom parts do not survive a section.

    A drawn line or bare surface has no volume for the plane to cut, and a curve that
    happens to lie in the plane would need a wholly different treatment. Dropping them
    with a note is honest; projecting them onto the plane would invent geometry.
    """
    for key in sorted(overlays):
        log.append(f"Info    : {key} is a display-only line or surface and is not "
                   "carried into the 2D section")
    return {}


def _verify(
    project: Project, volumes: dict[str, list[int]],
    overlays: dict[str, list[tuple[int, int]]] | None = None,
    curves: dict[str, list[int]] | None = None,
) -> None:
    overlays = overlays or {}
    curves = curves or {}
    if project.dimension == 2:
        # In plane strain an absent part is an answer, not a failure: it means nothing
        # of that part crosses the section plane. `_section` has already logged which.
        return
    # A structure may legitimately contribute nothing: one drawn outside the soil, or
    # of the other dimension's kind, which `_embed_beams` has already logged.
    exempt = ({beam.id for beam in project.beams} | {a.id for a in project.anchors}
              | {i.id for i in project.interfaces}
              | {n.id for n in project.normal_loads})
    # So may the half of a translated load pair that this dimension does not build: the
    # pair is one load with two records, and `loads_for` picks which one is the model's.
    # Its key stays in `part_keys` so the frontend's namespace does not change.
    built = {load.id for load in project.loads_for(3)}
    exempt |= {load.id for load in project.loads if load.id not in built}
    missing = [key for key in project.part_keys()
               if key not in exempt
               and not volumes.get(key) and not overlays.get(key) and not curves.get(key)]
    if missing:
        raise GeometryError(
            "the geometry build produced no volume for: " + ", ".join(missing)
            + ". An OCC boolean most likely failed on a thin solid."
        )


class GeometryError(RuntimeError):
    """A boolean silently produced nothing. Surfaced to the command log, never swallowed."""
