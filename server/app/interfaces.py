"""Split a conformal mesh along an interface line and tie it back with contact elements.

`build._embed_beams` deliberately welds a sheet pile to the soil: it fragments the
section with the pile so both share every node, which is what the reference decks show
for a bonded wall. An interface is the opposite instruction. The wall has to be able to
slide and to open, so the one node where the two meet must become several -- one per
body -- and a zero-thickness element must be written across the gap to carry the
friction.

The arrangement is read off examples/crow_case.mdpa and reproduced here exactly:

*   The structure keeps the original node ids. Its beam elements are never rewritten.
*   Each soil body that touches the line gets its own copy of every node on it, and its
    elements are rewired onto those copies.
*   One interface element per mesh segment per detached side, written
    `(a, b, mid | a', b', mid')`: the structure's three nodes first, then the soil's,
    with the pair ordered so that a +90 degree turn from `a -> b` points at the soil the
    element holds. That is why the two faces of one wall carry opposite node orders in
    the reference deck.

Which node is duplicated is a topological question, not a geometric one, and it is
answered per node rather than per body. Around a node, two soil elements belong to the
same copy when a chain of shared edges joins them *without crossing the interface*. At a
node in the middle of the line that gives two copies, one per face. At the toe, where
the line stops and the ground closes underneath, it gives one -- the soil there really is
continuous, and crow_case.mdpa writes exactly one node for it. No geometric side test
could tell those two cases apart.

Nothing here imports gmsh: it takes connectivity and returns connectivity, so the split
can be checked against meshes small enough to draw on paper (tests/test_interfaces.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

Point = tuple[float, float]
Coordinates = dict[int, tuple[float, float, float]]

# Element edges as (corner, corner, midside...), by node count. Only the simplices the
# 2D exporter writes: a linear and a quadratic triangle.
EDGES: dict[int, tuple[tuple[int, ...], ...]] = {
    3: ((0, 1), (1, 2), (2, 0)),
    6: ((0, 1, 3), (1, 2, 4), (2, 0, 5)),
}

TOLERANCE = 1e-9


class InterfaceError(RuntimeError):
    """The interface cannot be built on this mesh. Surfaced to the command log."""


@dataclass(frozen=True)
class Spec:
    """One interface, as the mesh sees it.

    `path` is the polyline in the plane the deck is written in, in the order the user
    drew it -- left and right are relative to walking it that way. `segments` are the
    mesh's own line elements along it, `(end, end)` or `(end, end, midside)`, in any
    orientation; they are turned to face along the path here.

    `structural` says whether a structure owns the line. When it does, every soil side
    may be detached and the original nodes stay with the beam. When it does not, one
    side has to keep them, because nothing else would.
    """
    key: str
    path: list[Point]
    segments: list[list[int]]
    structural: bool
    sides: str          # "both" | "left" | "right"


@dataclass
class Split:
    duplicates: dict[int, int] = field(default_factory=dict)
    """New node id -> the node it copies. The caller gives the copy the same
    coordinates; that is what makes the element zero-thickness."""

    elements: dict[str, list[list[int]]] = field(default_factory=dict)
    """Interface key -> connectivity rows, in Kratos' `3Plus3N` order."""

    renamed: list[dict[int, int]] = field(default_factory=list)
    """Per continuum row, the substitution applied to it. Anything else built on the
    same nodes -- a boundary condition sitting on the soil, a node group -- follows the
    element it belongs to through this."""


def wanted_sides(sides: str) -> tuple[str, ...]:
    return ("left", "right") if sides == "both" else (sides,)


def split_mesh(specs: list[Spec], rows: list[list[int]],
               coordinates: Coordinates) -> Split:
    """Detach the soil along every spec and return the contact elements to write.

    `rows` is every continuum element in the model, rewritten in place onto the copies.
    """
    if not specs:
        return Split(renamed=[{} for _ in rows])

    barriers = _barriers(specs)
    segments = {spec.key: [_facing(spec, segment, coordinates) for segment in spec.segments]
                for spec in specs}

    # The split rewrites `rows` in place, so the connectivity the topology was read
    # from is kept: `_emit` still has to ask which element sits on which side, and by
    # then half of them name nodes that did not exist when the question was answered.
    original = [list(row) for row in rows]
    stars = _stars(original)
    components = _components(specs, segments, original, stars, barriers, coordinates)
    result = _duplicate(specs, components, rows, coordinates)
    _emit(specs, segments, components, original, coordinates, result)
    return result


# ── Reading the mesh ────────────────────────────────────────────────────────

def _barriers(specs: list[Spec]) -> dict[frozenset[int], str]:
    """Edge -> the interface that cuts it. Two interfaces on one edge is a modelling
    mistake, not something to average: the deck would carry two contacts holding the
    same pair of faces."""
    out: dict[frozenset[int], str] = {}
    for spec in specs:
        for segment in spec.segments:
            edge = frozenset(segment[:2])
            if edge in out:
                raise InterfaceError(
                    f"interfaces {out[edge]!r} and {spec.key!r} share a line; give each "
                    "one its own, or use a single interface with both sides."
                )
            out[edge] = spec.key
    return out


def _stars(rows: list[list[int]]) -> dict[int, list[int]]:
    """Node -> the indices of the continuum elements containing it."""
    star: dict[int, list[int]] = {}
    for index, row in enumerate(rows):
        for node in row:
            star.setdefault(node, []).append(index)
    return star


def _edges_of(row: list[int]) -> tuple[tuple[int, ...], ...]:
    try:
        pattern = EDGES[len(row)]
    except KeyError:
        raise InterfaceError(
            f"an interface cannot be split into a {len(row)}-node element; mesh the "
            "section with linear or quadratic triangles."
        ) from None
    return tuple(tuple(row[i] for i in edge) for edge in pattern)


# ── Which copy each element belongs to ──────────────────────────────────────

def _components(specs: list[Spec], segments: dict[str, list[list[int]]],
                rows: list[list[int]], stars: dict[int, list[int]],
                barriers: dict[frozenset[int], str],
                coordinates: Coordinates) -> dict[int, list[dict]]:
    """Node -> the groups of elements meeting at it, split by the interfaces through it.

    Two elements in a node's star belong to one group when they share an edge at that
    node which no interface cuts. Each group is `{"elements": [...], "specs": {key: side}}`,
    where `side` is which face of that interface the group sits on -- "both" for a group
    that wraps around the end of the line, which is the toe of a sheet pile.
    """
    on_line: dict[int, list[str]] = {}
    for spec in specs:
        for segment in segments[spec.key]:
            for node in segment:
                keys = on_line.setdefault(node, [])
                if spec.key not in keys:
                    keys.append(spec.key)

    out: dict[int, list[dict]] = {}
    by_key = {spec.key: spec for spec in specs}
    for node in sorted(on_line):
        star = stars.get(node, [])
        parent = {index: index for index in star}

        def root(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        shared: dict[frozenset[int], list[int]] = {}
        for index in star:
            for edge in _edges_of(rows[index]):
                if node in edge:
                    shared.setdefault(frozenset(edge[:2]), []).append(index)
        for edge, holders in shared.items():
            if edge in barriers:
                continue
            for other in holders[1:]:
                parent[root(other)] = root(holders[0])

        grouped: dict[int, list[int]] = {}
        for index in star:
            grouped.setdefault(root(index), []).append(index)
        groups = []
        for _, elements in sorted(grouped.items(), key=lambda item: min(item[1])):
            sides = {key: _side_of(by_key[key], elements, rows, coordinates)
                     for key in on_line[node]}
            groups.append({"elements": sorted(elements), "specs": sides})
        out[node] = groups
    return out


def _side_of(spec: Spec, elements: list[int], rows: list[int],
             coordinates: Coordinates) -> str:
    """Which face of `spec` a group of elements sits on, from their centroids.

    "both" is a real answer, not a failure: a group that reaches around the end of the
    line -- the ground under a pile's toe -- is on both faces at once, and is detached
    as a single body when either face is asked for.
    """
    signs = {_sign(_centroid(rows[index], coordinates), spec.path) for index in elements}
    signs.discard("on")
    if len(signs) == 1:
        return signs.pop()
    return "both"


def _centroid(row: list[int], coordinates: Coordinates) -> Point:
    corners = row[:3]
    return (sum(coordinates[n][0] for n in corners) / 3.0,
            sum(coordinates[n][1] for n in corners) / 3.0)


def _sign(point: Point, path: list[Point]) -> str:
    """Left or right of the nearest leg of `path`, walking it in its stored order."""
    ax, ay, bx, by = _nearest_leg(point, path)
    cross = (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)
    if abs(cross) <= TOLERANCE:
        return "on"
    return "left" if cross > 0 else "right"


def _nearest_leg(point: Point, path: list[Point]) -> tuple[float, float, float, float]:
    best = None
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else ((point[0] - ax) * dx + (point[1] - ay) * dy) / length
        t = min(1.0, max(0.0, t))
        near = (ax + t * dx, ay + t * dy)
        gap = (point[0] - near[0]) ** 2 + (point[1] - near[1]) ** 2
        if best is None or gap < best[0]:
            best = (gap, ax, ay, bx, by)
    if best is None:
        raise InterfaceError("an interface needs at least two points")
    return best[1:]


def _facing(spec: Spec, segment: list[int], coordinates: Coordinates) -> list[int]:
    """The mesh segment turned to run along the path, so left stays left.

    gmsh hands a curve's line elements back in its own parametric direction, which is
    not always the direction the user drew the line in, and the whole left/right
    convention hangs off that.
    """
    a, b = coordinates[segment[0]], coordinates[segment[1]]
    ax, ay, bx, by = _nearest_leg(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), spec.path)
    along = (bx - ax) * (b[0] - a[0]) + (by - ay) * (b[1] - a[1])
    if along >= 0:
        return list(segment)
    return [segment[1], segment[0], *segment[2:]]


# ── Duplicating ─────────────────────────────────────────────────────────────

def _duplicate(specs: list[Spec], components: dict[int, list[dict]],
               rows: list[list[int]], coordinates: Coordinates) -> Split:
    """Give every detached group its own copy of the node, and rewire it onto that.

    A group that is not detached keeps the original, which is how one face of a wall
    stays welded to it while the other slides.
    """
    wanted = {spec.key: wanted_sides(spec.sides) for spec in specs}
    structural = {spec.key: spec.structural for spec in specs}
    result = Split(renamed=[{} for _ in rows])
    next_tag = max(coordinates) + 1

    for node in sorted(components):
        groups = components[node]
        detached = [group for group in groups
                    if _is_detached(group, wanted, structural)]
        if len(detached) == len(groups) and not any(
                structural[key] for group in groups for key in group["specs"]):
            raise InterfaceError(
                "a free interface has to leave one side of the soil holding the "
                "original nodes; give it a structure to sit in, or detach one side."
            )
        for group in detached:
            tag = next_tag
            next_tag += 1
            result.duplicates[tag] = node
            for index in group["elements"]:
                rows[index] = [tag if n == node else n for n in rows[index]]
                result.renamed[index][node] = tag
    return result


def _is_detached(group: dict, wanted: dict[str, tuple[str, ...]],
                 structural: dict[str, bool]) -> bool:
    """Whether a group of elements is pulled off the original node.

    A group labelled "both" wraps around the end of the line -- the ground under a
    pile's toe. It is detached when a structure owns the line, because there is a pile
    there to pull it away from, and that is what crow_case.mdpa writes: one copy at the
    toe, held by both faces. Along a free interface there is nothing in the middle, so
    the same wrap is simply continuous soil and stays where it is.
    """
    for key, side in group["specs"].items():
        if side == "both":
            if structural[key]:
                return True
            continue
        if side in wanted[key]:
            return True
    return False


# ── Writing the contact elements ────────────────────────────────────────────

def _emit(specs: list[Spec], segments: dict[str, list[list[int]]],
          components: dict[int, list[dict]], rows: list[list[int]],
          coordinates: Coordinates, result: Split) -> None:
    """One element per segment per detached side, structure side first."""
    for spec in specs:
        written: list[list[int]] = []
        for segment in segments[spec.key]:
            for side in wanted_sides(spec.sides):
                index = _adjacent(spec, segment, components, rows, coordinates, side)
                ordered = segment if side == "left" else \
                    [segment[1], segment[0], *segment[2:]]
                copies = [result.renamed[index].get(node, node) for node in ordered]
                written.append(ordered + copies)
        result.elements[spec.key] = written


def _adjacent(spec: Spec, segment: list[int], components: dict[int, list[dict]],
              rows: list[list[int]], coordinates: Coordinates, side: str) -> int:
    """The continuum element holding this segment on the given side.

    Found through the node's own groups rather than by scanning the mesh, so an element
    that merely touches the line at a point cannot be mistaken for the one attached to
    it.
    """
    edge = frozenset(segment[:2])
    for group in components.get(segment[0], []):
        for index in group["elements"]:
            if not any(frozenset(e[:2]) == edge for e in _edges_of(rows[index])):
                continue
            if _sign(_centroid(rows[index], coordinates), spec.path) == side:
                return index
    raise InterfaceError(
        f"interface {spec.key!r} has no soil on its {side} along the whole line; it "
        "cannot hold a face that is not there. Detach the other side only, or move the "
        "line into the model."
    )
