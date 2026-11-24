"""The pieces a soil layer or a drawn soil surface falls into when lines cut it.

A layer is a rectangle in the section, a drawn soil surface a polygon (`polygon_pieces`),
and what cuts them is any number of polylines: the lines a user draws and the sheet piles.
This module takes the two and answers with the closed pieces, the one thing
`Project.soil_bodies`, the geometry and the deck all have to agree on. Pure Python: the project is validated outside the gmsh worker, and the browser
reads the answer off the project.

The cut is a small planar graph. Every segment is clipped to the rectangle and split where
it meets another, a dead end is pruned away, and each face of what is left is a piece. A
line that stops inside the soil therefore cuts nothing, a closed line inside the soil
leaves a hole in the piece around it, and a line along the rectangle's edge is that edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

Point = tuple[float, float]
Polyline = tuple[Point, ...]

TOLERANCE = 1e-6
"""Metres. Two points this close are one point, so a line typed to end on a layer's edge
reaches it."""


@dataclass(frozen=True)
class Piece:
    """One closed piece of a layer."""
    outline: Polyline
    """Its boundary, counter-clockwise, not repeating the first point."""
    holes: tuple[Polyline, ...]
    """What lies inside the outline and is not this piece."""
    point: Point
    """A point inside it, away from its boundary: inside also when the piece is L-shaped,
    where the centre of mass may not be."""

    @property
    def bottom(self) -> float:
        return min(y for _, y in self.outline)

    @property
    def top(self) -> float:
        return max(y for _, y in self.outline)

    @property
    def left(self) -> float:
        return min(x for x, _ in self.outline)

    def contains(self, point: Point) -> bool:
        return _inside(self.outline, point) and not any(_inside(hole, point)
                                                        for hole in self.holes)


@lru_cache(maxsize=256)
def pieces(x0: float, x1: float, bottom: float, top: float,
           cutters: tuple[Polyline, ...]) -> tuple[Piece, ...]:
    """The pieces of the rectangle `x0..x1`, `bottom..top` that `cutters` make, from the
    top down and then from the left. One piece, the rectangle, when nothing cuts it.

    Cached: a project asks several times per request, and the answer depends only on these
    numbers."""
    corners = ((x0, bottom), (x1, bottom), (x1, top), (x0, top))
    whole = (Piece(corners, (), ((x0 + x1) / 2, (bottom + top) / 2)),)
    segments = [segment for line in cutters for a, b in zip(line, line[1:])
                if (segment := _clipped(a, b, x0, x1, bottom, top)) is not None]
    if not segments:
        return whole
    rectangle = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return _cut(corners, rectangle, segments, whole)


@lru_cache(maxsize=256)
def polygon_pieces(outline: Polyline, cutters: tuple[Polyline, ...]) -> tuple[Piece, ...]:
    """The pieces of the simple polygon `outline` that `cutters` make, in the same order as
    `pieces`. One piece, the polygon, when nothing cuts it.

    The outline of a drawn soil surface: any number of corners, either way round, convex or
    not. Each cutter is clipped at the polygon's edges and keeps what lies inside, so a line
    that leaves the polygon and comes back cuts it twice."""
    corners = _counter_clockwise(outline)
    whole = (Piece(corners, (), _point_inside(corners, [])),)
    edges = [(corners[i], corners[(i + 1) % len(corners)]) for i in range(len(corners))]
    segments = [part for line in cutters for a, b in zip(line, line[1:])
                for part in _clipped_to_polygon(a, b, corners, edges)]
    if not segments:
        return whole
    return _cut(corners, edges, segments, whole)


def _cut(corners: Polyline, boundary: list[tuple[Point, Point]],
         segments: list[tuple[Point, Point]], whole: tuple[Piece, ...]) -> tuple[Piece, ...]:
    """The pieces the clipped `segments` cut the region with this `boundary` into."""
    nodes, edges = _graph(boundary + segments)
    faces, outers = _faces(nodes, edges)
    if len(faces) < 2 and not outers[1:]:
        return whole
    found = [Piece(tuple(nodes[n] for n in face), (), (0.0, 0.0)) for face in faces]
    holes: list[list[Polyline]] = [[] for _ in found]
    corner = next(n for n, node in enumerate(nodes) if _same(node, corners[0]))
    for outer in outers:
        if corner in outer:
            continue
        hole = tuple(nodes[n] for n in outer)
        around = [i for i, piece in enumerate(found)
                  if _inside(piece.outline, hole[0]) and hole[0] not in piece.outline]
        if around:
            holes[min(around, key=lambda i: _area(found[i].outline))].append(hole)
    out = [Piece(piece.outline, tuple(held), _point_inside(piece.outline, held))
           for piece, held in zip(found, holes)]
    return tuple(sorted(out, key=lambda piece: (-piece.top, piece.left, -piece.bottom)))


def _counter_clockwise(outline: Polyline) -> Polyline:
    """The outline as `Piece.outline` holds one: counter-clockwise, the first point not
    repeated at the end."""
    points = tuple((float(x), float(y)) for x, y in outline)
    if len(points) > 1 and _same(points[0], points[-1]):
        points = points[:-1]
    return points if _area(points) > 0.0 else points[::-1]


def _clipped_to_polygon(a: Point, b: Point, outline: Polyline,
                        edges: list[tuple[Point, Point]]) -> list[tuple[Point, Point]]:
    """The parts of a segment inside the polygon: split where it meets an edge, keeping
    each part whose middle is inside or on the edge. A point within the tolerance of an
    edge meets it, so a line typed to end on the edge reaches it."""
    stops = [a, b] + [point for edge in edges for point in _meeting(a, b, *edge)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    stops.sort(key=lambda p: (p[0] - a[0]) * dx + (p[1] - a[1]) * dy)
    out: list[tuple[Point, Point]] = []
    for start, end in zip(stops, stops[1:]):
        if _same(start, end):
            continue
        middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        if _inside(outline, middle) or any(_distance(middle, *edge) <= TOLERANCE
                                           for edge in edges):
            out.append((start, end))
    return out


def _same(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE


def _clipped(a: Point, b: Point, x0: float, x1: float, bottom: float, top: float
             ) -> tuple[Point, Point] | None:
    """The part of a segment inside the rectangle, or None (Liang-Barsky)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0.0, 1.0
    for delta, origin, minimum, maximum in ((dx, a[0], x0, x1), (dy, a[1], bottom, top)):
        if abs(delta) <= 1e-15:
            if origin < minimum - TOLERANCE or origin > maximum + TOLERANCE:
                return None
            continue
        first, second = sorted(((minimum - origin) / delta, (maximum - origin) / delta))
        low, high = max(low, first), min(high, second)
    if low >= high:
        return None
    # A point within the tolerance outside lands on the edge, as if it had been typed there.
    def on(t: float) -> Point:
        return (min(max(a[0] + t * dx, x0), x1), min(max(a[1] + t * dy, bottom), top))
    start, end = on(low), on(high)
    return None if _same(start, end) else (start, end)


def _meeting(a: Point, b: Point, c: Point, d: Point) -> list[Point]:
    """Where segments ab and cd meet: nothing, a point, or the ends of their overlap."""
    ux, uy = b[0] - a[0], b[1] - a[1]
    vx, vy = d[0] - c[0], d[1] - c[1]
    cross = ux * vy - uy * vx
    if abs(cross) > 1e-12 * math.hypot(ux, uy) * math.hypot(vx, vy):
        t = ((c[0] - a[0]) * vy - (c[1] - a[1]) * vx) / cross
        s = ((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) / cross
        length_u, length_v = math.hypot(ux, uy), math.hypot(vx, vy)
        if (-TOLERANCE <= t * length_u <= length_u + TOLERANCE
                and -TOLERANCE <= s * length_v <= length_v + TOLERANCE):
            return [(a[0] + t * ux, a[1] + t * uy)]
        return []
    return [p for p, seg in ((a, (c, d)), (b, (c, d)), (c, (a, b)), (d, (a, b)))
            if _distance(p, *seg) <= TOLERANCE]


def _distance(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _graph(segments: list[tuple[Point, Point]]) -> tuple[list[Point], set[frozenset[int]]]:
    """Every segment split where it meets another: the nodes, and the edges as node pairs."""
    nodes: list[Point] = []

    def node(p: Point) -> int:
        for index, known in enumerate(nodes):
            if _same(known, p):
                return index
        nodes.append(p)
        return len(nodes) - 1

    # Rectangle first, so a node on its corner reads the corner's exact numbers.
    stops: list[list[Point]] = [[a, b] for a, b in segments]
    for i, (a, b) in enumerate(segments):
        for j in range(i + 1, len(segments)):
            met = _meeting(a, b, *segments[j])
            stops[i].extend(met)
            stops[j].extend(met)
    edges: set[frozenset[int]] = set()
    for (a, b), points in zip(segments, stops):
        ordered = sorted(points, key=lambda p: (p[0] - a[0]) * (b[0] - a[0])
                         + (p[1] - a[1]) * (b[1] - a[1]))
        along = [node(p) for p in ordered]
        edges.update(frozenset(pair) for pair in zip(along, along[1:]) if pair[0] != pair[1])
    return nodes, edges


def _faces(nodes: list[Point], edges: set[frozenset[int]]
           ) -> tuple[list[list[int]], list[list[int]]]:
    """The bounded faces of the graph, counter-clockwise, and the outer boundary of each of
    its connected parts, with dead ends and bridges taken out. A bridge joins two loops and
    has the same face on both sides, so it cuts nothing."""
    edges = set(edges)
    while True:
        _prune(edges)
        walks, face_of = _walk(nodes, edges)
        bridges = {edge for edge in edges if _same_face_both_sides(edge, face_of)}
        if not bridges:
            break
        edges -= bridges
    bounded = [walk for walk in walks if _area([nodes[n] for n in walk]) > 0.0]
    outer = [walk for walk in walks if _area([nodes[n] for n in walk]) <= 0.0]
    return bounded, outer


def _same_face_both_sides(edge: frozenset[int], face_of: dict[tuple[int, int], int]) -> bool:
    a, b = edge
    return face_of[(a, b)] == face_of[(b, a)]


def _prune(edges: set[frozenset[int]]) -> None:
    """Take out what ends in the middle of nowhere, repeatedly: it cannot enclose anything."""
    while True:
        degree: dict[int, int] = {}
        for edge in edges:
            for n in edge:
                degree[n] = degree.get(n, 0) + 1
        ends = {edge for edge in edges if any(degree[n] == 1 for n in edge)}
        if not ends:
            return
        edges -= ends


def _walk(nodes: list[Point], edges: set[frozenset[int]]
          ) -> tuple[list[list[int]], dict[tuple[int, int], int]]:
    """Walk around every face, turning as far left as possible at each node: a bounded face
    comes out counter-clockwise, and each connected part's outside clockwise."""
    around: dict[int, list[int]] = {}
    for edge in edges:
        a, b = tuple(edge)
        around.setdefault(a, []).append(b)
        around.setdefault(b, []).append(a)
    for n, others in around.items():
        others.sort(key=lambda m: math.atan2(nodes[m][1] - nodes[n][1],
                                             nodes[m][0] - nodes[n][0]))
    walks: list[list[int]] = []
    face_of: dict[tuple[int, int], int] = {}
    for a in sorted(around):
        for b in around[a]:
            if (a, b) in face_of:
                continue
            walk, u, v = [], a, b
            while (u, v) not in face_of:
                face_of[(u, v)] = len(walks)
                walk.append(u)
                others = around[v]
                u, v = v, others[(others.index(u) - 1) % len(others)]
            walks.append(walk)
    return walks, face_of


def _area(outline) -> float:
    """Signed: positive counter-clockwise."""
    points = list(outline)
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1]
                     for a, b in zip(points, points[1:] + points[:1]))


def _inside(outline: Polyline, point: Point) -> bool:
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _point_inside(outline: Polyline, holes: list[Polyline]) -> Point:
    """The middle of the widest stretch inside the piece, along the middle of its tallest
    band between two vertex levels: no vertex lies on that level, so each edge crossing it
    crosses cleanly."""
    loops = [outline, *holes]
    levels = sorted({y for loop in loops for _, y in loop})
    low, high = max(zip(levels, levels[1:]), key=lambda band: band[1] - band[0])
    y = (low + high) / 2
    crossings = sorted(
        x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        for loop in loops
        for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1])
        if (y0 > y) != (y1 > y))
    start, end = max(zip(crossings[::2], crossings[1::2]), key=lambda span: span[1] - span[0])
    return ((start + end) / 2, y)
