"""Parse a Kratos `.mdpa` deck back into mesh data: nodes, typed elements and
conditions, and named sub-model-part groupings.

The mirror image of `app.kratos`: that module picks a Kratos class for each
(dimension, gmsh element type) pair via its ELEMENTS/BEAMS/SHELLS/TRUSSES/CONDITIONS
tables; this inverts those same tables so a class name found in a file resolves back to
what kind of entity it is (soil continuum, beam, shell, truss, or load condition) and
its dimension and node count. Those tables are imported rather than re-derived, so the
two directions cannot silently drift apart.

Node order is not un-permuted -- `kratos.FLIP` only ever encodes orientation (which way
an element's normal or a beam's local axis points), and that does not matter for
re-displaying a mesh that already exists.

Only the mesh is recoverable this way. The parametric model that produced it -- soil
layers with borehole interpolation, section properties, load definitions, mesh settings
-- is baked into node coordinates and discarded on export; nothing here attempts to
invert that. What *is* recoverable, from a sub-model part's shape alone: whether it is a
structural body (has elements), a load (has conditions), a support (its
SubModelPartData carries a fixity-shaped variable), or a plain boundary/group (nodes
only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.kratos import BEAMS, BOUNDARIES, CONDITIONS, ELEMENTS, SHELLS, TRUSSES

TOLERANCE = 1e-6
"""Metres. A node's z counts as zero, i.e. the deck is a 2D plane-strain model,
within this."""

BOUNDARY_NAMES = {name for name, _, _ in BOUNDARIES}
"""Domain-face node groups (`kratos.BOUNDARIES`). Their fixities live in
project_parameters.json, not in any SubModelPartData the .mdpa itself carries, so a
group is only recognisable as a boundary by this reserved name."""


class ImportError_(ValueError):
    """The file is not a well-formed `.mdpa` deck."""


def _reverse(table: dict, kind: str) -> dict[str, tuple[str, int, int]]:
    """`{(dim, gmsh_type): (class_name, node_order)}` -> `{class_name: (kind, dim, n)}`."""
    return {name: (kind, dim, len(order)) for (dim, _gmsh_type), (name, order) in table.items()}


def _reverse_trusses() -> dict[str, tuple[str, int, int]]:
    return {name: ("truss", dim, 2) for dim, name in TRUSSES.items()}


CLASS_KIND: dict[str, tuple[str, int, int]] = {
    **_reverse(ELEMENTS, "continuum"),
    **_reverse(BEAMS, "beam"),
    **_reverse(SHELLS, "shell"),
    **_reverse_trusses(),
}
"""Kratos element class name -> (kind, dimension, node count)."""

CONDITION_KIND: dict[str, tuple[str, int, int]] = _reverse(CONDITIONS, "condition")
"""Kratos condition class name -> ("condition", dimension, node count)."""


@dataclass
class Entity:
    kratos_class: str
    kind: str
    """"continuum" | "beam" | "shell" | "truss" | "condition" | "unknown"."""
    dim: int | None
    """None when `kratos_class` is not one this codebase's exporter ever writes."""
    entries: dict[int, list[int]] = field(default_factory=dict)
    """Entity id -> connectivity, in Kratos node numbering, in file order."""
    properties: dict[int, int] = field(default_factory=dict)
    """Entity id -> its Properties id."""

    def to_dict(self) -> dict:
        return {
            "kratos_class": self.kratos_class, "kind": self.kind, "dim": self.dim,
            "count": len(self.entries),
        }


@dataclass
class Part:
    name: str
    nodes: list[int] = field(default_factory=list)
    elements: list[int] = field(default_factory=list)
    conditions: list[int] = field(default_factory=list)
    data: dict[str, list[float]] = field(default_factory=dict)
    kind: str = "group"
    """"body" (owns elements), "load" (owns conditions), "boundary" (a reserved domain-
    face name), "support" (nodes only, named `*_Support` by `kratos.export_project`'s
    anchor-tail convention), or "group" (any other nodes-only part)."""

    def to_dict(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "data": self.data,
            "nodes": len(self.nodes), "elements": len(self.elements),
            "conditions": len(self.conditions),
        }


@dataclass
class MdpaModel:
    nodes: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    elements: list[Entity] = field(default_factory=list)
    conditions: list[Entity] = field(default_factory=list)
    parts: dict[str, Part] = field(default_factory=dict)
    properties: list[int] = field(default_factory=list)
    dimension: int = 3
    """Inferred from the node table: 2 when every z is zero (a plane-strain section),
    3 otherwise."""

    def world_nodes(self) -> dict[int, tuple[float, float, float]]:
        """The node table in the viewer's world frame (X across, Y up, Z out of plane).

        The identity, in both dimensions. A plane-strain deck is written in Kratos X
        and Y with Z zero, and since the re-basis that is exactly where a 2D model
        lives -- the x-y plane at z = 0 -- so there is nothing to stand up. It was a
        remapping only while the section was authored in the world x-z elevation.
        """
        return self.nodes

    @property
    def bbox(self) -> tuple[float, float, float, float, float, float]:
        return bbox_of(self.nodes)

    def to_dict(self) -> dict:
        """The bbox travels with the geometry -- it is what frames the camera, so the
        two have to be in one frame."""
        placed = self.world_nodes()
        return {
            "dimension": self.dimension,
            "bbox": list(bbox_of(placed)),
            "nodes": len(self.nodes),
            "elements": [entity.to_dict() for entity in self.elements],
            "conditions": [entity.to_dict() for entity in self.conditions],
            "parts": [part.to_dict() for part in self.parts.values()],
            "sections": to_sections(self),
        }


def bbox_of(nodes: dict[int, tuple[float, float, float]]
            ) -> tuple[float, float, float, float, float, float]:
    if not nodes:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [xyz[0] for xyz in nodes.values()]
    ys = [xyz[1] for xyz in nodes.values()]
    zs = [xyz[2] for xyz in nodes.values()]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def import_mdpa(text: str) -> MdpaModel:
    """Parse a `.mdpa` deck's text into nodes, typed entities, and named parts."""
    model = MdpaModel()
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    index = 0
    try:
        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.startswith("Begin "):
                continue
            head = line.split()
            if head[1] == "Properties":
                model.properties.append(int(head[2]))
            elif head[1] == "Nodes":
                index = _nodes(lines, index, model)
            elif head[1] == "Elements":
                index = _entities(lines, index, model.elements, head[2], CLASS_KIND)
            elif head[1] == "Conditions":
                index = _entities(lines, index, model.conditions, head[2], CONDITION_KIND)
            elif head[1] == "SubModelPart":
                index = _part(lines, index, model, head[2])
    except (IndexError, ValueError) as error:
        raise ImportError_(f"malformed .mdpa deck: {error}") from error

    model.dimension = 2 if all(abs(xyz[2]) <= TOLERANCE for xyz in model.nodes.values()) else 3
    return model


def _nodes(lines: list[str], index: int, model: MdpaModel) -> int:
    while lines[index] != "End Nodes":
        parts = lines[index].split()
        model.nodes[int(parts[0])] = tuple(float(v) for v in parts[1:4])
        index += 1
    return index + 1


def _entities(lines: list[str], index: int, into: list[Entity], name: str,
             kinds: dict[str, tuple[str, int, int]]) -> int:
    kind, dim, _n = kinds.get(name, ("unknown", None, None))
    entity = Entity(kratos_class=name, kind=kind, dim=dim)
    while not lines[index].startswith("End "):
        values = [int(v) for v in lines[index].split()]
        entity.entries[values[0]] = values[2:]
        entity.properties[values[0]] = values[1]
        index += 1
    into.append(entity)
    return index + 1


def _part(lines: list[str], index: int, model: MdpaModel, name: str) -> int:
    part = Part(name=name)
    field_of = {"SubModelPartNodes": part.nodes, "SubModelPartElements": part.elements,
                "SubModelPartConditions": part.conditions}
    while lines[index] != "End SubModelPart":
        line = lines[index]
        index += 1
        match = re.fullmatch(r"Begin (SubModelPart\w+)", line)
        if not match:
            continue
        if match.group(1) == "SubModelPartData":
            index = _part_data(lines, index, part)
            continue
        target = field_of[match.group(1)]
        while not lines[index].startswith("End "):
            target.append(int(lines[index]))
            index += 1
        index += 1
    part.kind = ("body" if part.elements else
                 "load" if part.conditions else
                 "boundary" if name in BOUNDARY_NAMES else
                 "support" if name.endswith("_Support") else
                 "group")
    model.parts[name] = part
    return index + 1


# ── Drawable preview ──────────────────────────────────────────────────────
#
# A payload shaped exactly like the `Section`s `app.tessellate` renders for a
# generated mesh (server/app/tessellate.py:62), so the viewer can draw an imported
# deck through the buffer path it already has (js/buffers.js's `geometry`/`edges`)
# rather than needing a second renderer.
#
# One section per body sub-model part, so the deck's own grouping (a soil layer, a
# sheet pile, an anchor -- whatever the file's own SubModelPart names call out) becomes
# something the viewer can toggle and frame individually, the same as a real project's
# own bodies. An element no body part claims -- most often because the deck declares no
# SubModelParts at all -- falls back to one section per *kind* instead, exactly as
# before this was per-part; a synthetic deck with no parts still draws.

SECTION_COLORS = {"continuum": "#d9dee6", "shell": "#4b6ea8", "beam": "#b5573a",
                  "truss": "#2f6f4f"}
"""Colours for the *kind*-grouped fallback sections (unclaimed elements) -- all from
the app's own palette: continuum is meshing.MESH_COLOR, and the rest are
tessellate.PART_COLORS' wall, struts and anchors. Structural line work takes the two
saturated entries rather than PART_COLORS' beam grey, because a beam shares the soil's
nodes -- it is drawn as a line lying inside the mesh's own wireframe, and grey on grey
is a sheet pile nobody can see."""

PART_PALETTE = (
    "#c9a35c", "#5b8dbd", "#7fae6f", "#b5573a", "#8f7ab5",
    "#4fada0", "#c98750", "#5c76b0", "#a3b04f", "#b0507e",
)
"""Cycled by a body part's position in the deck. There is no per-body material to key a
colour off here, the way `kratos._part_materials` has for an export -- only an
arbitrary, but stable (same file, same order, same colours), position in the file."""


def _tet_boundary_triangles(conns: list[list[int]]) -> list[list[int]]:
    """The outer skin of a set of tetrahedra: the face of a tet that no other tet *in
    this set* shares. Called per body part, so two neighbouring bodies each get their
    own outer surface at the interface between them -- the same thing a real project's
    own per-body sections do (`tessellate._section`). Only the four corners of each tet
    matter -- a 10-node quadratic tet's midside nodes sit on faces the corners alone
    already describe."""
    faces: dict[frozenset, list[int]] = {}
    counts: dict[frozenset, int] = {}
    for conn in conns:
        c = conn[:4]
        for face in ((c[0], c[2], c[1]), (c[0], c[1], c[3]),
                    (c[1], c[2], c[3]), (c[2], c[0], c[3])):
            key = frozenset(face)
            counts[key] = counts.get(key, 0) + 1
            faces.setdefault(key, list(face))
    return [face for key, face in faces.items() if counts[key] == 1]


def _triangles_and_edges(conns_by_kind: dict[str, list[list[int]]],
                         dim: int) -> tuple[list[list[int]], list[tuple[int, int]]]:
    """A set of elements, split out by kind already, as drawable triangles and line
    segments. `dim` picks how a continuum element becomes a triangle: a 2D one already
    is one, a 3D one is a tetrahedron whose outer skin has to be found."""
    triangles = (_tet_boundary_triangles(conns_by_kind.get("continuum", [])) if dim == 3
                else [conn[:3] for conn in conns_by_kind.get("continuum", [])])
    triangles += [conn[:3] for conn in conns_by_kind.get("shell", [])]
    # The far end is the *second* node, never the last: a quadratic beam is written
    # (end, end, midside) -- see `kratos.BEAMS` -- so drawing to the last node covers
    # half of each element and renders a sheet pile as a dashed line.
    edges = [(conn[0], conn[1]) for conn in conns_by_kind.get("beam", [])]
    edges += [(conn[0], conn[1]) for conn in conns_by_kind.get("truss", [])]
    return triangles, edges


def _section_dict(nodes: dict[int, tuple[float, float, float]], key: str, color: str,
                  part: str | None, kind: str | None, triangles: list[list[int]],
                  edges: list[tuple[int, int]]) -> dict | None:
    """A render-ready section local to just the nodes it actually uses -- not the
    whole deck's node table -- so a payload with one section per body part does not
    multiply its size by the number of bodies, and so its own bbox is tight enough to
    frame a camera on just this part."""
    used = sorted({node for triangle in triangles for node in triangle}
                 | {node for pair in edges for node in pair})
    if not used:
        return None
    index_of = {tag: i for i, tag in enumerate(used)}
    edge_coords = [c for a, b in edges for c in (*nodes[a], *nodes[b])]
    return {
        "key": key, "color": color, "part": part, "kind": kind,
        "positions": [c for tag in used for c in nodes[tag]],
        "indices": [index_of[node] for triangle in triangles for node in triangle],
        "edges": edge_coords,
        "bbox": list(bbox_of({tag: nodes[tag] for tag in used})),
    }


def to_sections(model: MdpaModel) -> list[dict]:
    """Render-ready sections for the mesh a deck contains: one per body sub-model part
    (soil layer, sheet pile, anchor, wall panel -- whatever the file itself calls a
    body), each with its own colour, local geometry and bbox; anything no body part
    claims falls back to one section per element kind, coloured by `SECTION_COLORS`.

    A class this exporter does not recognise (`Entity.kind == "unknown"`, e.g. an
    interface element) contributes no geometry -- its topology is not known here, so
    guessing at a triangulation would risk drawing something that is not actually in
    the deck. It still counts in `MdpaModel.to_dict()`'s per-class stats, and a body
    part made entirely of such elements (an "Interface_..." part, say) simply has no
    section of its own.
    """
    if not model.nodes:
        return []
    nodes = model.world_nodes()
    by_id: dict[int, tuple[str, list[int]]] = {
        element_id: (entity.kind, conn)
        for entity in model.elements for element_id, conn in entity.entries.items()
    }

    sections: list[dict] = []
    claimed: set[int] = set()
    for part in model.parts.values():
        if part.kind != "body":
            continue
        conns_by_kind: dict[str, list[list[int]]] = {}
        for element_id in part.elements:
            claimed.add(element_id)
            kind, conn = by_id.get(element_id, (None, None))
            if kind in ("continuum", "shell", "beam", "truss"):
                conns_by_kind.setdefault(kind, []).append(conn)
        triangles, edges = _triangles_and_edges(conns_by_kind, model.dimension)
        # Indexed by sections actually drawn so far, not by position among body parts:
        # an "Interface_..." part (elements this exporter cannot draw) must not burn a
        # palette slot nobody sees, or two real bodies apart by exactly the palette's
        # length end up sharing a colour for no visible reason.
        color = PART_PALETTE[len(sections) % len(PART_PALETTE)]
        dominant = next(iter(conns_by_kind), None)
        section = _section_dict(nodes, f"imported:{part.name}", color, part.name,
                                dominant, triangles, edges)
        if section:
            sections.append(section)

    leftover_by_kind: dict[str, list[list[int]]] = {}
    for element_id, (kind, conn) in by_id.items():
        if element_id in claimed or kind not in ("continuum", "shell", "beam", "truss"):
            continue
        leftover_by_kind.setdefault(kind, []).append(conn)
    for kind in ("continuum", "shell", "beam", "truss"):
        conns = leftover_by_kind.get(kind, [])
        if not conns:
            continue
        triangles, edges = _triangles_and_edges({kind: conns}, model.dimension)
        section = _section_dict(nodes, f"imported_{kind}", SECTION_COLORS[kind],
                                None, kind, triangles, edges)
        if section:
            sections.append(section)
    return sections


VECTOR_DATA = re.compile(r"(\w+)\s*\[\d+\]\s*\(([^)]*)\)")


def _part_data(lines: list[str], index: int, part: Part) -> int:
    while not lines[index].startswith("End "):
        line = lines[index]
        index += 1
        vector = VECTOR_DATA.fullmatch(line)
        if vector:
            name, values = vector.groups()
            part.data[name] = [float(v) for v in values.split(",")]
        else:
            name, value = line.split(maxsplit=1)
            part.data[name] = [float(value)]
    return index + 1
