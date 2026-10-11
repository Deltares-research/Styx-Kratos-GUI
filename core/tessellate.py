"""Solid model -> display buffers.

Deliberately *not* a mesh. `gmsh.model.mesh.importStl()` taps OpenCASCADE's own
`BRepMesh_IncrementalMesh` triangulation, which exists to draw B-reps, and skips the
meshing algorithms entirely: the whole model tessellates in about a tenth of a second.
Running `generate(2)` instead would take seconds and produce an order of magnitude more
triangles, because the 0.8 m wall and the ~0.2 m anchors force small elements that
propagate through the whole domain.

Three consequences of that choice shape the code:

*   `importStl()` calls `deleteMesh()` first, so a display tessellation and an FE mesh
    cannot coexist in one model. Meshing re-derives from the geometry.
*   STL nodes are non-conformal and carry no parametric coordinates, so
    `gmsh.model.getNormal` is unusable. Normals are not sent at all -- the frontend
    flat-shades, which suits the faceted look and avoids seam artefacts.
*   Node tags are positive but neither contiguous nor ordered, so everything goes
    through an explicit tag -> index map, built once from a single `getNodes()` call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import gmsh

from core import build
from core.schemas import Project

DECIMALS = 4
"""0.1 mm at metre scale. Python's float repr is 17 significant digits by default."""

STL_LINEAR_DEFLECTION = 0.01
"""Chord error, relative to curve length."""

STL_ANGULAR_DEFLECTION = 0.4
"""Radians between facet normals -- about 16 facets around a full circle."""

PROBE_HALVINGS = 20
"""Attempts to find a probe distance that separates the two sides of a facet."""

TRIANGLE, LINE = 2, 1

PART_COLORS = {
    "wall": "#4b6ea8",
    "struts": "#b5573a",
    "anchors": "#2f6f4f",
    "piles": "#7a6a55",
    "load": "#d4342d",
    "water": "#2f8fd8",
    "wells": "#2f8fd8",
    "beam": "#8c8f96",
}
"""js/viewport.js:330-337. Soil takes its colour from its assigned material instead.

`beam` is the sheet piles' steel grey; it has no counterpart in the frozen viewport
because the mockup had no individually drawn structural members to colour."""


@dataclass
class Section:
    """One drawable buffer: a part key and a single colour.

    Sections are not one-per-part. A part whose volumes carry different colours -- the
    `excavation` alias spans both soil layers -- yields one section per colour, which is
    exactly the THREE.Group-of-Meshes shape the frozen viewport already builds.
    """

    key: str
    color: str
    positions: list[float] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)
    edges: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "color": self.color, "positions": self.positions,
            "indices": self.indices, "edges": self.edges,
        }


@dataclass
class DisplayModel:
    bbox: tuple[float, float, float, float, float, float]
    sections: list[Section]

    def to_dict(self) -> dict:
        return {"bbox": list(self.bbox), "sections": [s.to_dict() for s in self.sections]}


def tessellate(project: Project) -> DisplayModel:
    """Build the solid model and return display buffers for it."""
    result = build.build_geometry(project)

    gmsh.option.setNumber("Mesh.StlLinearDeflection", STL_LINEAR_DEFLECTION)
    gmsh.option.setNumber("Mesh.StlAngularDeflection", STL_ANGULAR_DEFLECTION)
    gmsh.model.mesh.importStl()

    coords = _node_coordinates()
    colors = _colors_by_volume(project, result)
    custom_colors = {p.key: p.color for p in project.custom_parts}

    sections = []
    # A normal load owns a curve -- the line its condition is written on (core/kratos.py)
    # -- but nothing to draw from it. Its symbol is the arrows the viewport puts on that
    # line, and drawing the curve as well would lay a stray line over the loaded face,
    # which is what a sheet pile's hairline would look like there.
    drawn_as_glyphs = {load.id for load in project.normal_loads}
    for key in project.part_keys():
        if key in result.overlays:
            sections.append(_overlay_section(key, custom_colors[key], result.overlays[key], coords))
            continue
        if result.ties.get(key):
            # An anchor is drawn from its ends like any other line. It is never meshed
            # as a curve -- the deck's truss is built from located nodes -- so this is
            # display geometry, and drawing it is the only thing it is for.
            sections.append(_overlay_section(
                key, PART_COLORS["anchors"],
                [(1, tag) for tag in result.ties[key]], coords,
            ))
            continue
        if result.curves.get(key) and key not in drawn_as_glyphs:
            # A sheet pile is 1D geometry, which `_overlay_section` already draws from
            # its endpoints alone -- the same treatment a drawn line gets, and for the
            # same reason: there is no surface to triangulate. A 3D member is the same
            # shape in the solid model and takes the same branch.
            sections.append(_overlay_section(
                key, PART_COLORS["beam"],
                [(1, tag) for tag in result.curves[key]], coords,
            ))
            continue
        if result.faces.get(key):
            # A wall panel is the one structural part with a surface to draw. Both
            # windings, like a section face: it is a sheet with soil on either side, so
            # the viewport has to see it from wherever the camera happens to be.
            sections.append(_overlay_section(
                key, PART_COLORS["beam"],
                [(2, tag) for tag in result.faces[key]], coords,
            ))
            continue
        if result.dim == 2:
            # A section face encloses nothing, so there is no "inward" to work out and
            # none of `_outer_surfaces` / `_points_inward` applies -- that machinery
            # exists only to decide which side of a facet is solid. A flat face is
            # exactly the shape `_overlay_section` already handles: both windings, so
            # it draws from either side, plus its true B-rep boundary edges.
            for color, tags in _group_by_color(result.volumes.get(key, []), colors).items():
                sections.append(
                    _overlay_section(key, color, [(2, tag) for tag in tags], coords)
                )
            continue
        # A part can end up owning no volume -- fragmenting two solids that occupy
        # the same space assigns the shared tags to one of them (core/build.py:320-326).
        # It then contributes no sections; it must not fail the whole model.
        for color, tags in _group_by_color(result.volumes.get(key, []), colors).items():
            sections.append(_section(key, color, tags, coords))
    return DisplayModel(bbox=result.bbox, sections=sections)


# ── Nodes ───────────────────────────────────────────────────────────────────

def _node_coordinates() -> dict[int, tuple[float, float, float]]:
    """Every node in the model, keyed by tag.

    Fetched once, in bulk. A per-surface `getNodes(2, tag)` omits the nodes owned by the
    surface's bounding curves, so element connectivity would reference tags that are
    missing from the map.
    """
    tags, flat, _ = gmsh.model.mesh.getNodes()
    return {int(tag): (flat[3 * i], flat[3 * i + 1], flat[3 * i + 2])
            for i, tag in enumerate(tags)}


# ── Colour ──────────────────────────────────────────────────────────────────

def _colors_by_volume(project: Project, result: build.BuildResult) -> dict[int, str]:
    colors: dict[int, str] = {}
    # Keyed by body rather than by layer: a staged excavation splits a layer into the
    # lifts it is dug in, and a lift is still the layer it came out of, so it is drawn
    # in that layer's material colour. Colouring only `soil_<layer id>` left every lift
    # without one, which `_group_by_color` reports as a KeyError that takes the whole
    # model view down rather than drawing one body grey.
    layer_color = {f"soil_{layer.id}": project.material(layer.mat).color
                   for layer in project.layers}
    for key, *_ in project.soil_bodies():
        # .get, not [...]: in a 2D section a layer that does not cross the plane keeps
        # its key but owns nothing.
        for tag in result.volumes.get(key, []):
            colors[tag] = layer_color[key.partition("__")[0]]
    for key, color in PART_COLORS.items():
        for tag in result.volumes.get(key, []):
            colors[tag] = color
    for load in project.loads:
        for tag in result.volumes.get(load.id, []):
            colors[tag] = PART_COLORS["load"]
    for custom in project.custom_parts:
        # A part with a material is soil, so it takes the material's colour the same
        # way a stack layer does; `color` is only the fallback for plain geometry.
        color = project.material(custom.mat).color if custom.mat else custom.color
        for tag in result.volumes.get(custom.key, []):
            colors[tag] = color
    return colors


def _group_by_color(tags: list[int], colors: dict[int, str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for tag in tags:
        out.setdefault(colors[tag], []).append(tag)
    return out


# ── Surfaces ────────────────────────────────────────────────────────────────

def _outer_surfaces(volume_tags: list[int],
                    coords: dict[int, tuple[float, float, float]]) -> dict[int, bool]:
    """The surfaces enclosing a group of volumes, mapped to whether to flip winding.

    A surface shared by two volumes in the same group is an interior face: invisible,
    but it would double the triangle count and show as a seam through anything
    transparent. Those are dropped -- which is also what makes the remaining set a
    closed manifold, so its enclosed volume is measurable.
    """
    owners: dict[int, list[int]] = {}
    for tag in volume_tags:
        for _, signed in gmsh.model.getBoundary([(3, tag)], oriented=True):
            owners.setdefault(abs(signed), []).append(tag)

    return {surface: _points_inward(volumes[0], surface, coords)
            for surface, volumes in owners.items() if len(volumes) == 1}


def _points_inward(volume_tag: int, surface: int,
                   coords: dict[int, tuple[float, float, float]]) -> bool:
    """Does the stored triangle winding face into this volume?

    Decided geometrically, by probing both sides of a facet and asking OCC which side is
    solid. `getBoundary(oriented=True)` looks like the answer and is not: its sign
    describes the face's parametric orientation within the solid, whereas importStl's
    winding comes from OCC's face triangulation, which is stored once per face and knows
    nothing about which solid is asking. Taking the sign at face value turns the 27 m3
    load pad into 50 m3 and inverts soil_L1 outright.

    Probing only one side does not work either. A facet on a convex curved face is a
    chord, inset from the true surface by r(1 - cos(pi/n)) -- about 6 mm on a 0.3 m pile
    at this deflection -- so a short step "outward" is still inside the solid and every
    cylinder ends up inverted. Stepping far enough to clear that sagitta would instead
    tunnel out of thin parts like the 0.06 m water slab.

    So: probe symmetrically and halve until the two sides disagree. The first distance
    that separates them is by construction larger than the local sagitta and smaller
    than the local thickness.
    """
    facet = _first_facet(surface, coords)
    if facet is None:
        return False
    centroid, normal, area = facet

    x0, y0, z0, x1, y1, z1 = gmsh.model.getBoundingBox(3, volume_tag)
    thinnest = min(x1 - x0, y1 - y0, z1 - z0)
    step = min(0.5 * math.sqrt(area), 0.25 * thinnest)

    for _ in range(PROBE_HALVINGS):
        ahead = gmsh.model.isInside(3, volume_tag, [centroid[k] + normal[k] * step for k in range(3)])
        behind = gmsh.model.isInside(3, volume_tag, [centroid[k] - normal[k] * step for k in range(3)])
        if bool(ahead) != bool(behind):
            return bool(ahead)
        step *= 0.5
    return False


def _first_facet(surface: int, coords: dict[int, tuple[float, float, float]]):
    """A representative triangle as (centroid, unit normal, area), or None."""
    types, _, nodes = gmsh.model.mesh.getElements(2, surface)
    for element_type, connectivity in zip(types, nodes):
        if element_type != TRIANGLE:
            continue
        for i in range(0, len(connectivity), 3):
            a, b, c = (coords[int(t)] for t in connectivity[i:i + 3])
            u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
            n = (u[1] * v[2] - u[2] * v[1],
                 u[2] * v[0] - u[0] * v[2],
                 u[0] * v[1] - u[1] * v[0])
            norm = math.sqrt(sum(k * k for k in n))
            if norm < 1e-12:
                continue                      # degenerate sliver; try the next facet
            return (
                [(a[k] + b[k] + c[k]) / 3 for k in range(3)],
                [n[k] / norm for k in range(3)],
                norm / 2,
            )
    return None


def _section(key: str, color: str, volume_tags: list[int],
             coords: dict[int, tuple[float, float, float]]) -> Section:
    section = Section(key=key, color=color)
    local: dict[int, int] = {}

    def index_of(node_tag: int) -> int:
        if node_tag not in local:
            local[node_tag] = len(local)
            x, y, z = coords[node_tag]
            section.positions.extend((round(x, DECIMALS), round(y, DECIMALS), round(z, DECIMALS)))
        return local[node_tag]

    surfaces = _outer_surfaces(volume_tags, coords)
    for surface, flip in surfaces.items():
        types, _, nodes = gmsh.model.mesh.getElements(2, surface)
        for element_type, connectivity in zip(types, nodes):
            if element_type != TRIANGLE:
                continue
            for i in range(0, len(connectivity), 3):
                a, b, c = (index_of(int(t)) for t in connectivity[i:i + 3])
                section.indices.extend((a, c, b) if flip else (a, b, c))

    _add_edges(section, surfaces, coords)
    return section


def _overlay_section(key: str, color: str, entities: list[tuple[int, int]],
                     coords: dict[int, tuple[float, float, float]]) -> Section:
    """A drawn line or bare surface: no volume, so no `_outer_surfaces` winding to work
    out -- there is no "inward" for a shape that does not enclose anything.

    A line has nothing to triangulate; it draws from its edges alone, the same as the
    curves in `_add_edges`. A surface is emitted with both triangle windings, since
    without an enclosing volume there is no way to know which side a viewer approaches
    from -- unlike `_section`, which orients strictly outward.
    """
    section = Section(key=key, color=color)
    local: dict[int, int] = {}

    def index_of(node_tag: int) -> int:
        if node_tag not in local:
            local[node_tag] = len(local)
            x, y, z = coords[node_tag]
            section.positions.extend((round(x, DECIMALS), round(y, DECIMALS), round(z, DECIMALS)))
        return local[node_tag]

    surface_tags = [tag for dim, tag in entities if dim == 2]
    for tag in surface_tags:
        types, _, nodes = gmsh.model.mesh.getElements(2, tag)
        for element_type, connectivity in zip(types, nodes):
            if element_type != TRIANGLE:
                continue
            for i in range(0, len(connectivity), 3):
                a, b, c = (index_of(int(t)) for t in connectivity[i:i + 3])
                section.indices.extend((a, b, c))
                section.indices.extend((a, c, b))
    if surface_tags:
        _add_edges(section, {tag: False for tag in surface_tags}, coords)

    for tag in (t for dim, t in entities if dim == 1):
        # Straight curves only (creator.py builds lines from occ.addLine segments), so
        # the two endpoints are the whole edge -- no need to mesh a free-standing curve,
        # which importStl() does not do (it tessellates faces; edges come along only as
        # a face's boundary, and a bare line borders no face).
        for _, point in gmsh.model.getBoundary([(1, tag)], oriented=False, combined=False):
            x, y, z = gmsh.model.getValue(0, point, [])
            section.edges.extend((round(x, DECIMALS), round(y, DECIMALS), round(z, DECIMALS)))

    return section


def _add_edges(section: Section, surfaces: dict[int, bool],
               coords: dict[int, tuple[float, float, float]]) -> None:
    """The CAD edges bounding the drawn surfaces, as flat LineSegments pairs.

    These come free with the STL import as Line elements on the model's curves, and are
    the true B-rep edges -- unlike three.js EdgesGeometry, which infers them from a
    crease angle and so both misses smooth joins and speckles curved surfaces.
    """
    curves = {abs(tag) for surface in surfaces
              for _, tag in gmsh.model.getBoundary([(2, surface)], oriented=False)}

    for curve in curves:
        types, _, nodes = gmsh.model.mesh.getElements(1, curve)
        for element_type, connectivity in zip(types, nodes):
            if element_type != LINE:
                continue
            for tag in connectivity:
                x, y, z = coords[int(tag)]
                section.edges.extend(
                    (round(x, DECIMALS), round(y, DECIMALS), round(z, DECIMALS))
                )
