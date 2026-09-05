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
from contextlib import contextmanager
from dataclasses import dataclass, field

import gmsh

from app.schemas import Project

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
    if project.simple_example:
        return _build_simple_example(project)
    gmsh.logger.start()
    try:
        gmsh.clear()
        gmsh.model.add("model")

        owners, overlays = _build_solids(project)
        owners = _cut_the_pit(project, owners)

        dim, notes = 3, []
        if project.dimension == 2:
            # Section before fragmenting: the faces are what has to be made conformal,
            # and fragmenting the solids first would only be work thrown away.
            dim = 2
            owners = _section(owners, project.section_offset, project.section_plane, notes)
            overlays = _drop_overlays(overlays, notes)

        owners = _fragment(owners, dim)
        owners = _imprint_load_footprints(project, owners, dim)
        owners, curves, faces = _embed_beams(project, owners, dim, notes)
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
        _tag_physical_groups(ties, 1, clear=False)
        _tag_physical_groups({key: [tag] for key, tag in tie_nodes.items()}, 0,
                             clear=False, suffix="_Support")
        _verify(project, volumes, overlays, {**curves, **ties})

        return BuildResult(
            volumes=volumes,
            mass={key: sum(gmsh.model.occ.getMass(dim, t) for t in tags)
                  for key, tags in volumes.items()},
            bbox=bounding_box([t for tags in volumes.values() for t in tags], dim,
                              fallback=(project.domain.x0, project.domain.y0, project.domain.z_bottom,
                                        project.domain.x1, project.domain.y1, project.domain.z_top)),
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


def _build_simple_example(project: Project) -> BuildResult:
    """A stable, structure-free layered block for the current UI example."""
    gmsh.logger.start()
    try:
        gmsh.clear()
        gmsh.model.add("simple-cube")
        d = project.domain
        borehole = project.borehole_ids()[0]
        owners = {}
        for layer in project.layers:
            bottom, top = layer.bots[borehole], layer.tops[borehole]
            tag = gmsh.model.occ.addBox(d.x0, d.y0, bottom, d.dx, d.dy, top - bottom)
            owners[tag] = {f"soil_{layer.id}"}
            
        custom_volumes, overlays = _import_custom_parts(project.custom_parts)
        for tag, key in custom_volumes.items():
            owners[tag] = {key}

        dim, notes = 3, []
        if project.dimension == 2:
            dim = 2
            owners = _section(owners, project.section_offset, project.section_plane, notes)
            overlays = _drop_overlays(overlays, notes)

        owners, curves, faces = _embed_beams(
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
        _tag_physical_groups(ties, 1, clear=False)
        _tag_physical_groups({key: [tag] for key, tag in tie_nodes.items()}, 0,
                             clear=False, suffix="_Support")
        tags = [tag for values in volumes.values() for tag in values]
        return BuildResult(
            volumes=volumes,
            mass={key: sum(gmsh.model.occ.getMass(dim, tag) for tag in tags)
                  for key, tags in volumes.items()},
            bbox=bounding_box(tags, dim,
                              fallback=(project.domain.x0, project.domain.y0, project.domain.z_bottom,
                                        project.domain.x1, project.domain.y1, project.domain.z_top)),
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

def _build_solids(project: Project) -> tuple[dict[int, set[str]], dict[str, list[tuple[int, int]]]]:
    """Every solid that takes part in the booleans, plus any display-only overlays.

    Returns (tag -> owning part keys, part key -> (dim, tag) pairs for custom parts with
    no volume).
    """
    p, d, e = project, project.domain, project.excavation
    owners: dict[int, set[str]] = {}

    def own(tag: int, key: str) -> int:
        owners.setdefault(tag, set()).add(key)
        return tag

    def box(x0, x1, y0, y1, z0, z1, key):
        return own(gmsh.model.occ.addBox(x0, y0, z0, x1 - x0, y1 - y0, z1 - z0), key)

    # Soil layers span the domain in plan and are flat-bottomed. The frozen viewport
    # extrudes from the bh1 column only (js/viewport.js:75,100) and ignores the other
    # two boreholes; dipping layer surfaces are a later change, made here once.
    bh = p.borehole_ids()[0]
    for layer in p.layers:
        box(d.x0, d.x1, d.y0, d.y1, layer.bots[bh], layer.tops[bh], f"soil_{layer.id}")

    t, w = p.wall.thickness, p.wall
    outer = box(e.x0 - t, e.x1 + t, e.y0 - t, e.y1 + t, w.toe_z, w.top_z, "wall")
    inner = gmsh.model.occ.addBox(e.x0, e.y0, w.toe_z, e.x1 - e.x0, e.y1 - e.y0, w.top_z - w.toe_z)
    ring, _ = gmsh.model.occ.cut([(3, outer)], [(3, inner)])
    del owners[outer]
    for _, tag in ring:
        own(tag, "wall")

    s = p.struts
    span = (e.y1 + s.overhang) - (e.y0 - s.overhang)
    for x in s.xs:
        own(gmsh.model.occ.addCylinder(x, e.y0 - s.overhang, s.z, 0, span, 0, s.radius), "struts")
    for y in (e.y0 - s.waler_offset, e.y1 + s.waler_offset):
        box(e.x0, e.x1,
            y - s.waler_width / 2, y + s.waler_width / 2,
            s.z - s.waler_height / 2, s.z + s.waler_height / 2, "struts")

    a = p.anchor_rows
    reach = math.cos(math.radians(a.inclination_deg)) * a.length
    drop = math.sin(math.radians(a.inclination_deg)) * a.length
    for y_head, direction in ((e.y0 - t + a.head_offset, -1.0), (e.y1 + t - a.head_offset, 1.0)):
        for x in a.xs:
            own(gmsh.model.occ.addCylinder(
                x, y_head, a.head_z, 0, direction * reach, -drop, a.radius), "anchors")

    for x in p.piles.xs:
        for y in p.piles.ys:
            own(gmsh.model.occ.addCylinder(
                x, y, p.piles.top_z - p.piles.length, 0, 0, p.piles.length, p.piles.radius), "piles")

    for x, y in p.wells.positions:
        own(gmsh.model.occ.addCylinder(
            x, y, p.wells.top_z - p.wells.length, 0, 0, p.wells.length, p.wells.radius), "wells")

    # Import any custom parts
    custom_volumes, overlays = _import_custom_parts(p.custom_parts)
    for tag, key in custom_volumes.items():
        own(tag, key)

    return owners, overlays


def _import_custom_parts(
    custom_parts: list,
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
    for load in p.loads:
        if dim == 2 and load.kind == "point":
            loads[load.id] = [gmsh.model.occ.addSphere(
                load.x, project.section_offset, load.z, load.thickness,
            )]
        elif dim == 2 and load.kind == "line":
            loads[load.id] = [gmsh.model.occ.addBox(
                load.x0, d.y0, load.z,
                load.x1 - load.x0, d.dy, load.thickness,
            )]
        elif dim == 3 and load.kind == "surface":
            loads[load.id] = [gmsh.model.occ.addBox(
                load.x0, load.y0, d.z_top,
                load.x1 - load.x0, load.y1 - load.y0, load.thickness,
            )]
    wa = p.water
    water = gmsh.model.occ.addBox(
        d.x0 - wa.margin, d.y0 - wa.margin, wa.z - wa.thickness / 2,
        d.dx + 2 * wa.margin, d.dy + 2 * wa.margin, wa.thickness,
    )
    built = {**loads, "water": [water]}
    if dim == 3:
        return built

    # Sectioned by the same helper as everything else, so "the load pad is not in
    # this section" needs no special case. Never fragmented, in either dimension:
    # these are indicators, and letting them cut the model would change the mesh.
    owners = {tag: {key} for key, tags in built.items() for tag in tags}
    sectioned = _assign_by_priority(
        _section(owners, project.section_offset, project.section_plane, log))
    return {key: sectioned.get(key, []) for key in built}


# ── Booleans ────────────────────────────────────────────────────────────────

def _cut_the_pit(project: Project, owners: dict[int, set[str]]) -> dict[int, set[str]]:
    """Remove the excavated void from the soil, before anything else touches it.

    Cutting here rather than fragmenting a pit solid and deleting the pieces afterwards
    keeps the intent local: only the soil is excavated. The struts hang in the void and
    the wells run through it, and neither needs a special case.
    """
    e, d = project.excavation, project.domain
    soil = [(3, tag) for tag, keys in owners.items() if any(k.startswith("soil_") for k in keys)]

    pit = gmsh.model.occ.addBox(e.x0, e.y0, e.floor_z,
                                e.x1 - e.x0, e.y1 - e.y0, d.z_top - e.floor_z)
    _, mapping = gmsh.model.occ.cut(soil, [(3, pit)])

    rebuilt = {tag: keys for tag, keys in owners.items() if (3, tag) not in soil}
    for (_, old), pieces in zip(soil, mapping):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])
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

    A 2D load record is dimension-native `(x, z)`, so the tool is placed at the section
    offset along the plane's normal -- the same world position `kratos._load_conditions`
    reads a point load back at.
    """
    tools: list[tuple[int, int]] = []
    normal = PLANE_AXES[project.section_plane][0]

    def point(x: float, z: float) -> int:
        xyz = [x, 0.0, z]
        xyz[normal] = project.section_offset
        return gmsh.model.occ.addPoint(*xyz)

    for load in project.loads:
        if not load.active:
            continue
        if dim == 2 and load.kind == "point":
            tools.append((0, point(load.x, load.z)))
        elif dim == 2 and load.kind == "line":
            tools.append((1, gmsh.model.occ.addLine(point(load.x0, load.z),
                                                    point(load.x1, load.z))))
        elif dim == 3 and load.kind == "surface":
            tools.append((2, gmsh.model.occ.addRectangle(
                load.x0, load.y0, project.domain.z_top,
                load.x1 - load.x0, load.y1 - load.y0,
            )))
    return tools


def _clip_to_model(tools: list[tuple[int, int]],
                   inputs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep only the part of each tool that meets the model, tool by tool.

    A footprint may hang over the edge of the domain or over the excavated void. The
    overhang has no boundary to imprint, and left in place it becomes a free-floating
    surface at the load elevation -- which `kratos._load_conditions` would then read
    back as loaded boundary. Intersecting first is what keeps the model clean.

    One boolean per tool, for the same reason `_section` runs one per volume: the
    result stays positional, with no `outDimTagsMap` to unpick across two lists.
    """
    clipped = []
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


def _split_at(points: list[tuple[float, ...]],
              heads: list[tuple[float, ...]]) -> list[tuple[float, ...]]:
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
                 ) -> tuple[dict[int, set[str]], dict[str, list[int]], dict[str, list[int]]]:
    """Fragment the section with each sheet pile, and keep the curves it leaves behind.

    The same imprint `_imprint_load_footprints` performs, with the opposite half of the
    result kept: a load only needs the boundary split, while a beam *is* the tool
    pieces. Because the fragment makes the soil and the curve share their edges, the
    mesher puts one node where both meet -- which is what the reference deck shows
    (examples/dike_with_sheet_pile.mdpa: every sheet-pile node is also a soil node).

    A pile that stops inside the soil does not separate the surface into two regions,
    so nothing is cut away; the curve simply becomes an internal edge of the face. The
    tools are clipped to the model first, so a pile drawn past the domain edge or over
    the excavated void contributes only the part that has soil around it.

    Returns the rebuilt owners, the beam key -> curve tags map, and the panel key ->
    face tags map (3D only; a 2D section has no wall panels in it).
    """
    if dim == 3:
        return _embed_3d_structures(project, owners, log)
    if not owners:
        return owners, {}, {}
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
    if not active and not free:
        return owners, {}, {}

    normal = PLANE_AXES[project.section_plane][0]

    def point(x: float, z: float) -> int:
        xyz = [x, 0.0, z]
        xyz[normal] = project.section_offset
        return gmsh.model.occ.addPoint(*xyz)

    heads = [anchor.head for anchor in project.plane_anchors if anchor.active]
    tools: list[tuple[int, int]] = []
    owner_of_tool: list[str] = []
    for beam in active:
        vertices = [point(x, z) for x, z in _split_at(beam.points, heads)]
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(beam.id)

    # A free interface -- one drawn through the soil rather than along a pile -- needs
    # the same imprint for the same reason: the mesh can only be split along a line it
    # actually has edges on. It carries no elements of its own, so unlike a beam it is
    # only ever an internal edge; `app.interfaces` does the rest, after meshing.
    for interface in free:
        vertices = [point(x, z) for x, z in interface.points]
        for start, end in zip(vertices, vertices[1:]):
            tools.append((1, gmsh.model.occ.addLine(start, end)))
            owner_of_tool.append(interface.id)

    inputs = [(dim, tag) for tag in owners]
    kept, kept_owners = [], []
    for tool, key in zip(tools, owner_of_tool):
        pieces, _ = gmsh.model.occ.intersect(
            [tool], inputs, removeObject=True, removeTool=False,
        )
        for piece in pieces:
            if piece[0] == 1:
                kept.append(piece)
                kept_owners.append(key)
    if not kept:
        if log is not None:
            for beam in active:
                log.append(f"Info    : {beam.id} lies outside the soil in this section "
                           "and is not part of the model")
        return owners, {}, {}

    _, mapping = gmsh.model.occ.fragment(inputs, kept, removeTool=False)

    rebuilt: dict[int, set[str]] = {}
    for (_, old), pieces in zip(inputs, mapping[:len(inputs)]):
        for _, tag in pieces:
            rebuilt.setdefault(tag, set()).update(owners[old])

    # The tool half of the map: a curve the fragment split becomes several curves, and
    # every one of them still belongs to the beam it was drawn for.
    beam_curves: dict[str, list[int]] = {}
    for key, pieces in zip(kept_owners, mapping[len(inputs):]):
        beam_curves.setdefault(key, []).extend(
            tag for piece_dim, tag in pieces if piece_dim == 1
        )
    return rebuilt, {key: sorted(set(tags)) for key, tags in beam_curves.items()}, {}


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
    panels = [panel for panel in project.panels if panel.active]
    members = [member for member in project.members if member.active]
    # A 2D sheet pile has no place in the solid model, for the mirror of the reason a
    # panel has none in a section: it is drawn in a plane the 3D model does not have.
    for beam in project.sheet_piles:
        if beam.active and log is not None:
            log.append(f"Info    : {beam.id} is a sheet pile, which is built in a 2D "
                       "section only; it is not part of this 3D model")
    if not owners or not (panels or members):
        return owners, {}, {}

    heads = [anchor.head for anchor in project.space_anchors if anchor.active]
    tools: list[tuple[int, int]] = []
    owner_of_tool: list[str] = []

    for panel in panels:
        # Swept from the top down: extruding the footprint's lines gives one face per
        # segment, which is what a wall in plan is.
        vertices = [gmsh.model.occ.addPoint(x, y, panel.z_top) for x, y in panel.footprint]
        lines = [gmsh.model.occ.addLine(start, end)
                 for start, end in zip(vertices, vertices[1:])]
        swept = gmsh.model.occ.extrude([(1, line) for line in lines],
                                       0.0, 0.0, panel.z_toe - panel.z_top)
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
    kept, kept_owners = [], []
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
    for key, pieces in zip(kept_owners, mapping[len(inputs):]):
        if key is None:      # an imprinted anchor head belongs to no structure
            continue
        for piece_dim, tag in pieces:
            if piece_dim == 2:
                faces.setdefault(key, []).append(tag)
            elif piece_dim == 1:
                curves.setdefault(key, []).append(tag)
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

    Deliberately *not* fragmented into anything. The reference deck
    (examples/crow_case.mdpa) has a tail node that belongs to no element at all, held by
    its own node group: the grouted body is idealised as a fixed point, so embedding the
    tie in the soil would model a fully bonded bar instead. The head needs no fragment
    either -- `_split_at` has already made it a vertex of the beam, which is where the
    shared node comes from.

    Returns the anchor key -> display curve tags, and the anchor key -> tail point tag
    that `meshing` makes visible so a node lands exactly on it.
    """
    # Each dimension draws its own kind and says so about the other's: an anchor drawn
    # in a section has no place in the solid model, and one drawn in space has none in
    # the section, for the same reason their structures do not cross over either.
    if dim == 3:
        active = [anchor for anchor in project.space_anchors if anchor.active]
        skipped = [anchor for anchor in project.plane_anchors if anchor.active]
        noun, other = "in the 2D section", "3D model"
    else:
        active = [anchor for anchor in project.plane_anchors if anchor.active]
        skipped = [anchor for anchor in project.space_anchors if anchor.active]
        noun, other = "in space", "section"
    for anchor in skipped:
        if log is not None:
            log.append(f"Info    : {anchor.id} is an anchor drawn {noun}; it is not "
                       f"part of this {other}")
    if not active:
        return {}, {}

    if dim == 3:
        def point(x: float, y: float, z: float) -> int:
            return gmsh.model.occ.addPoint(x, y, z)
    else:
        normal = PLANE_AXES[project.section_plane][0]

        def point(x: float, z: float) -> int:
            xyz = [x, 0.0, z]
            xyz[normal] = project.section_offset
            return gmsh.model.occ.addPoint(*xyz)

    curves: dict[str, list[int]] = {}
    tails: dict[str, int] = {}
    for anchor in active:
        head, tail = point(*anchor.head), point(*anchor.tail)
        curves[anchor.id] = [gmsh.model.occ.addLine(head, tail)]
        tails[anchor.id] = tail
    return curves, tails


# ── The plane-strain section ────────────────────────────────────────────────

SECTION_PAD = 1.0
"""Metres the cutting plane extends past the model, so nothing is clipped by it.

Sized from the built solids rather than the domain: the wall top (0.6 m above z_top)
and any drawn or imported part can legitimately stick out of the declared domain.
"""


# Which coordinate index each section plane holds constant, and which two it spans.
PLANE_AXES = {"xy": (2, 0, 1), "xz": (1, 0, 2), "yz": (0, 1, 2)}


def _section_extents(tags: list[int], plane: str) -> tuple[float, float, float, float]:
    """The span every cutting plane must cover, as (u0, u1, v0, v1) in its own axes.

    Measured once, before any boolean runs. `_section` removes each volume as it cuts
    it, so measuring inside that loop reads a tag OCC has already deleted.
    """
    _, u, v = PLANE_AXES[plane]
    boxes = [gmsh.model.occ.getBoundingBox(3, tag) for tag in tags]
    return (min(b[u] for b in boxes) - SECTION_PAD, max(b[u + 3] for b in boxes) + SECTION_PAD,
            min(b[v] for b in boxes) - SECTION_PAD, max(b[v + 3] for b in boxes) + SECTION_PAD)


def _section_plane(extents: tuple[float, float, float, float],
                   offset: float, plane: str) -> int:
    """A plane surface at `offset` along its normal, spanning the whole model."""
    normal, u, v = PLANE_AXES[plane]
    u0, u1, v0, v1 = extents

    def point(a: float, b: float) -> int:
        xyz = [0.0, 0.0, 0.0]
        xyz[normal], xyz[u], xyz[v] = offset, a, b
        return gmsh.model.occ.addPoint(*xyz)

    corners = [point(a, b) for a, b in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    edges = [gmsh.model.occ.addLine(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(edges)])


def _section(owners: dict[int, set[str]], offset: float, plane: str = "xz",
             log: list[str] | None = None) -> dict[int, set[str]]:
    """Cut the solids with the section plane and keep the faces, with their owners.

    One boolean per volume rather than one batched over all of them. `occ.intersect`
    consumes its arguments and returns an `outDimTagsMap` indexed by the concatenated
    object + tool list, so a batched call would have to be unpicked across both lists
    to answer "which part did this face come from". Per-volume, ownership is positional
    and there is nothing to unpick -- and a plane is a cheap solid to boolean against.

    A volume that misses the plane contributes nothing. That is the correct plane-strain
    answer -- a pile row at another y is genuinely not in this section -- but it is
    logged, because a part silently vanishing otherwise reads as a boolean failure.
    """
    if not owners:
        return {}
    extents = _section_extents(list(owners), plane)
    normal = {"xy": "z", "xz": "y", "yz": "x"}[plane]

    rebuilt: dict[int, set[str]] = {}
    for tag, keys in owners.items():
        # A fresh plane each time: intersect deletes the object it was given.
        cutter = _section_plane(extents, offset, plane)
        pieces, _ = gmsh.model.occ.intersect(
            [(2, cutter)], [(3, tag)], removeObject=True, removeTool=True
        )
        faces = [t for dim, t in pieces if dim == 2]
        if not faces and log is not None:
            log.append(f"Info    : {', '.join(sorted(keys))} does not reach the section "
                       f"plane at {normal} = {offset} and is not part of this 2D model")
        for face in faces:
            rebuilt.setdefault(face, set()).update(keys)
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
    # Sheet piles are 2D-only for now and `_embed_beams` has logged each one it skipped,
    # so a 3D project is not missing anything by having no geometry for them.
    beams = ({beam.id for beam in project.beams} | {a.id for a in project.anchors}
             | {i.id for i in project.interfaces})
    missing = [key for key in project.part_keys()
               if key not in beams
               and not volumes.get(key) and not overlays.get(key) and not curves.get(key)]
    if missing:
        raise GeometryError(
            "the geometry build produced no volume for: " + ", ".join(missing)
            + ". An OCC boolean most likely failed on a thin solid."
        )


class GeometryError(RuntimeError):
    """A boolean silently produced nothing. Surfaced to the command log, never swallowed."""
