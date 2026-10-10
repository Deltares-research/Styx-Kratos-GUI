"""A stage's mesh, as buffers the viewport can draw and colour.

The payload is the shape `app.mdpa_import.to_sections` already produces for an imported
deck, and it is built with that module's own `_section_dict` rather than a copy of it:
positions, triangle indices, line-segment coordinates, a bbox, and -- the part that
matters here -- `node_ids`, the deck's own node number for every vertex, in the same
order as the positions. That last one is the whole contract the colouring rests on:
`/stages/{n}/field/{name}` answers with values keyed by node id, and the viewport turns
those into a vertex-colour buffer by looking each vertex's id up.

── Why this is not just `to_sections` ───────────────────────────────────────

**Quadratic subdivision.** The soil elements this project exports are six-node
triangles, and `to_sections` draws each as one flat triangle through its three corners
-- which is right for showing a mesh and wrong for contouring a field over it. The three
mid-side nodes carry their own solved values, and on a flat triangle those values have
nowhere to go: half of what the solver computed never reaches the screen. Splitting each
element into the four sub-triangles its own nodes define fixes that, at the cost of four
times the indices and no extra vertices at all.

**Drawing a beam through its middle.** For the same reason, a three-node beam is drawn
as two segments rather than one. Undeformed the two look identical; deformed, the single
end-to-end segment renders a bending sheet pile as a straight stick.

── What is deferred ─────────────────────────────────────────────────────────

3D gets its boundary faces from the corner nodes only, as `mdpa_import` already does.
Subdividing a quadratic tetrahedron's faces needs the mapping from each face to its own
mid-side nodes, and 3D is surface shading in this milestone (`plan/postprocessing-plan.md`,
task 23). A 2D section -- which is what this project mostly produces, and what the whole
staged-construction feature is built around -- is fully subdivided.
"""

from __future__ import annotations

from app.gid_results import GidMesh
from app.mdpa_import import MdpaModel, _section_dict, _tet_boundary_triangles, bbox_of

T6_SUBTRIANGLES = ((0, 3, 5), (3, 1, 4), (5, 4, 2), (3, 4, 5))
"""How a six-node triangle splits. Corners 0,1,2; mid-sides 3 = (0,1), 4 = (1,2),
5 = (2,0), which is Kratos' own ordering. Three corner triangles and the middle one."""

Q8_SUBTRIANGLES = ((0, 4, 7), (4, 1, 5), (5, 2, 6), (7, 6, 3), (4, 5, 6), (4, 6, 7))
"""How an eight-node quadrilateral splits, for the reason a six-node triangle does:
corners 0-3, mid-sides 4 = (0,1), 5 = (1,2), 6 = (2,3), 7 = (3,0), as Kratos orders
them. A triangle at each corner, and the inner quad of mid-sides as two more. Every
node the solver computed is a vertex, and the outline (`outline_of`) runs through the
mid-sides on vertices the shading has."""

Q9_SUBTRIANGLES = ((0, 4, 8), (4, 1, 8), (1, 5, 8), (5, 2, 8),
                   (2, 6, 8), (6, 3, 8), (3, 7, 8), (7, 0, 8))
"""A nine-node quadrilateral: the same eight boundary nodes, fanned around the centre."""

COLORS = {
    "continuum": "#b6ac97",
    "beam": "#4a6fa5",
    "truss": "#7d5ba6",
    "shell": "#4a8fa5",
    "interface": "#c0703a",
    "unknown": "#9aa0a6",
}
"""A colour per element kind, for the state where no field is being shown and for the
parts a contour does not cover.

By kind rather than from the project: a run outlives the project that produced it, and
the open model may be a different one entirely by the time its results are read. A
sheet pile that is always the same blue is more use than one tinted from whatever
happens to be loaded.
"""

UNCLAIMED = "Other elements"
"""Where an element no sub-model part names ends up. The mesh is what is on screen, so
an element with no home is drawn anyway rather than silently dropped."""


def triangles_of(connectivity: list[int], nnode: int, element_type: str,
                 dimension: int) -> list[list[int]]:
    """One element's drawable triangles, in its own node numbers."""
    kind = element_type.lower()
    if kind.startswith("tri"):
        if nnode >= 6:
            return [[connectivity[i] for i in triple] for triple in T6_SUBTRIANGLES]
        return [connectivity[:3]]
    if kind.startswith("quad"):
        if nnode >= 9 and len(connectivity) >= 9:
            return [[connectivity[i] for i in triple] for triple in Q9_SUBTRIANGLES]
        if nnode >= 8 and len(connectivity) >= 8:
            return [[connectivity[i] for i in triple] for triple in Q8_SUBTRIANGLES]
        # Two triangles across the quad's own diagonal.
        corners = connectivity[:4]
        return [[corners[0], corners[1], corners[2]], [corners[0], corners[2], corners[3]]]
    return []


def outline_of(connectivity: list[int], nnode: int,
               element_type: str) -> list[tuple[int, int]]:
    """One surface element's own sides, as node pairs -- what `results mesh on` draws.

    Not the triangles it is shaded with: a six-node triangle is shaded as four and an
    eight-node quadrilateral as two, and neither the inner edges nor the diagonal is a
    side. A quadratic side goes corner, mid-side, corner (Kratos puts the corners first,
    then the mid-sides in the same order), so the outline bends with the deformed mesh
    exactly as the shading does. Anything that is not a 2D surface element has none.
    """
    kind = element_type.lower()
    corners = 3 if kind.startswith("tri") else 4 if kind.startswith("quad") else 0
    if not corners or len(connectivity) < corners:
        return []
    out: list[tuple[int, int]] = []
    for side in range(corners):
        a, b = connectivity[side], connectivity[(side + 1) % corners]
        if nnode >= 2 * corners and len(connectivity) >= 2 * corners:
            middle = connectivity[corners + side]
            out += [(a, middle), (middle, b)]
        else:
            out.append((a, b))
    return out


def edges_of(connectivity: list[int], nnode: int, element_type: str) -> list[tuple[int, int]]:
    """One line element's drawable segments.

    A three-node element is (end, end, middle) in Kratos' ordering -- see
    `kratos.BEAMS` -- so it is drawn end-to-middle and middle-to-end. Drawing
    `(conn[0], conn[1])` alone is what `mdpa_import` does, and is right for a straight
    undeformed member and wrong for a deformed one.
    """
    if not element_type.lower().startswith(("lin", "point")):
        return []
    if nnode >= 3:
        return [(connectivity[0], connectivity[2]), (connectivity[2], connectivity[1])]
    if nnode == 2:
        return [(connectivity[0], connectivity[1])]
    return []


def stage_sections(model: MdpaModel, mesh: GidMesh) -> dict:
    """Every part with something to draw in this stage, as render-ready buffers.

    A part this phase deactivated has no elements in the stage mesh and so produces no
    section at all. It is not missing information: `/stages/{n}/parts` still lists it,
    which is where the explorer learns that it exists and is switched off.
    """
    owner = _owners(model)
    kinds = _element_kinds(model)

    grouped: dict[str, dict] = {}
    for block in mesh.blocks:
        for element, connectivity in block.elements.items():
            name = owner.get(element, UNCLAIMED)
            bucket = grouped.setdefault(
                name, {"triangles": [], "edges": [], "kind": None, "outline": [],
                       "triangle_elements": [], "edge_elements": []})
            made = triangles_of(connectivity, block.nnode, block.element_type,
                                mesh.dimension)
            bucket["triangles"] += made
            # Which element each triangle came from. Not derivable on the other side:
            # a six-node triangle makes *four* of them, so the n-th triangle is not
            # the n-th element, and a viewer colouring a per-element field by position
            # would smear each value across four neighbours.
            bucket["triangle_elements"] += [element] * len(made)
            if mesh.dimension == 2:
                bucket["outline"] += outline_of(connectivity, block.nnode,
                                                block.element_type)
            segments = edges_of(connectivity, block.nnode, block.element_type)
            bucket["edges"] += segments
            bucket["edge_elements"] += [element] * len(segments)
            if bucket["kind"] is None:
                bucket["kind"] = kinds.get(element, "unknown")

    if mesh.dimension == 3:
        # The outer skin, per part, so two neighbouring bodies each keep their own
        # surface where they meet -- the same rule `mdpa_import` uses.
        grouped = _skins(grouped, mesh, owner, kinds)

    sections = []
    for name in _order(model, grouped):
        bucket = grouped[name]
        kind = bucket["kind"] or "unknown"
        section = _section_dict(
            nodes=mesh.nodes, key=f"results:{name}", color=COLORS.get(kind, COLORS["unknown"]),
            part=None if name == UNCLAIMED else name, kind=kind,
            triangles=bucket["triangles"], edges=bucket["edges"])
        if section is not None:
            _index_edges(section, bucket["edges"])
            # 3D draws only a part's skin, so its outline is the skin's own edges.
            outline = (bucket["outline"] if mesh.dimension == 2 else
                       [(t[i], t[(i + 1) % 3]) for t in bucket["triangles"]
                        for i in range(3)])
            _index_outline(section, outline)
            section["triangle_elements"] = bucket["triangle_elements"]
            section["edge_elements"] = bucket["edge_elements"]
            sections.append(section)

    drawn = {node for section in sections for node in section["node_ids"]}
    return {
        "dimension": mesh.dimension,
        "bbox": list(bbox_of({tag: mesh.nodes[tag] for tag in drawn if tag in mesh.nodes})),
        "sections": sections,
    }


def _index_edges(section: dict, pairs: list[tuple[int, int]]) -> None:
    """Add `edge_indices`: the line work as vertex indices, beside the raw coordinates.

    `mdpa_import._section_dict` writes edges as flat coordinates, which is all its own
    viewer needs -- an imported mesh is drawn once and never moves. A *result* moves:
    the same line has to take a vertex colour and shift with the deformation factor,
    and neither is possible from coordinates that have lost which node they came from.

    The coordinates stay, so nothing that already reads a section breaks.
    """
    index_of = {tag: i for i, tag in enumerate(section["node_ids"])}
    section["edge_indices"] = [index_of[node] for pair in pairs for node in pair
                               if node in index_of]


def _index_outline(section: dict, pairs: list[tuple[int, int]]) -> None:
    """Add `wire_indices`: the element outlines as vertex-index pairs, each edge once.

    Two neighbouring elements share a side, and drawing it twice would make every
    interior line darker than the boundary. Indices into the section's own vertices,
    like `edge_indices`, so the outline takes the deformation the shading takes.
    """
    index_of = {tag: i for i, tag in enumerate(section["node_ids"])}
    seen: set[frozenset] = set()
    flat: list[int] = []
    for a, b in pairs:
        key = frozenset((a, b))
        if a == b or key in seen or a not in index_of or b not in index_of:
            continue
        seen.add(key)
        flat += [index_of[a], index_of[b]]
    section["wire_indices"] = flat


def _skins(grouped: dict[str, dict], mesh: GidMesh, owner: dict[int, str],
           kinds: dict[int, str]) -> dict[str, dict]:
    """3D only: replace each part's tetrahedra with the faces nothing else in that part
    shares. Corner nodes only -- see the module docstring."""
    tets: dict[str, list[list[int]]] = {}
    for block in mesh.blocks:
        if not block.element_type.lower().startswith("tet"):
            continue
        for element, connectivity in block.elements.items():
            tets.setdefault(owner.get(element, UNCLAIMED), []).append(connectivity)
    for name, conns in tets.items():
        faces = _tet_boundary_triangles(conns)
        grouped[name]["triangles"] = faces
        # The skin is built from the whole part at once and a face no longer belongs
        # to an identifiable element, so per-element colouring is not offered in 3D.
        # Empty rather than wrong: the viewer falls back to nodal values.
        grouped[name]["triangle_elements"] = []
    return grouped


def _owners(model: MdpaModel) -> dict[int, str]:
    owner: dict[int, str] = {}
    for part in model.parts.values():
        for element in part.elements:
            owner.setdefault(element, part.name)
    return owner


def _element_kinds(model: MdpaModel) -> dict[int, str]:
    """Element id -> "continuum" | "beam" | "truss" | "interface" | ...

    Read off the deck's element *classes*, which `mdpa_import` has already classified.
    It is what decides whether a part is drawn as a surface or as line work, and it is
    not recoverable from the GiD mesh alone: a beam and an interface are both `Linear`
    there.
    """
    return {element: entity.kind
            for entity in model.elements for element in entity.entries}


def _order(model: MdpaModel, grouped: dict[str, dict]) -> list[str]:
    """The deck's own declaration order, with the catch-all last."""
    named = [name for name in model.parts if name in grouped]
    return named + [name for name in grouped if name not in set(named)]
