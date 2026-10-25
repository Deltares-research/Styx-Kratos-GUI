"""Points along a 2D polyline: the nearest point on it, how far along it a point is, and
the part of it between two points.

What an interface on a part of a sheet pile needs (`Interface.stretch`): the project
check, the drafts, the mesh and the writer all ask the same questions of the pile's
polyline, so they ask them here. The window asks them in JavaScript
(`App.Interfaces.snap` and `pathOf`, frontend/js/interfaces.js), with the same rules.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

Point = tuple[float, float]
Face = Literal["left", "right", "below", "above"]

STEEP = 1.0
"""A line is steep when it rises at least as much as it runs (45 degrees or more):
its faces are then left and right, else below and above."""


def nearest(points: Sequence[Sequence[float]], point: Sequence[float]
            ) -> tuple[Point, float, float]:
    """The point on the polyline nearest `point`, its distance from `point`, and how far
    along the polyline it is (metres from the first point)."""
    best: tuple[Point, float, float] | None = None
    walked = 0.0
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0.0:
            continue
        t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (length * length)
        t = max(0.0, min(1.0, t))
        on = (a[0] + t * dx, a[1] + t * dy)
        away = math.hypot(point[0] - on[0], point[1] - on[1])
        if best is None or away < best[1]:
            best = (on, away, walked + t * length)
        walked += length
    if best is None:
        raise ValueError("a polyline needs two distinct points")
    return best


def length(points: Sequence[Sequence[float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))


def between(points: Sequence[Sequence[float]], start: float, end: float) -> list[Point]:
    """The part of the polyline from `start` to `end` metres along it, in the polyline's
    own order whichever of the two is larger. Its vertices are the polyline's own in
    between, so it follows every bend."""
    start, end = sorted((start, end))
    out: list[Point] = []
    walked = 0.0
    for a, b in zip(points, points[1:]):
        size = math.hypot(b[0] - a[0], b[1] - a[1])
        if size == 0.0:
            continue
        low, high = max(start, walked), min(end, walked + size)
        if low <= high:
            for at in (low, high):
                t = (at - walked) / size
                point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                if not out or math.dist(out[-1], point) > 0.0:
                    out.append(point)
        walked += size
    return out


def is_steep(points: Sequence[Sequence[float]]) -> bool:
    """Steeper than 45 degrees from its first point to its last (`STEEP`)."""
    dx, dy = points[-1][0] - points[0][0], points[-1][1] - points[0][1]
    return abs(dy) >= STEEP * abs(dx)


def faces(points: Sequence[Sequence[float]]) -> tuple[Face, Face]:
    """The two faces of a line as the screen shows them: ("left", "right") for a steep
    line, ("below", "above") for a flatter one. The first is the face toward -x, or
    toward -y -- the face whose soil is the master of a tie."""
    return ("left", "right") if is_steep(points) else ("below", "above")


def walking_side(points: Sequence[Sequence[float]], face: str) -> str:
    """The screen face `face` as the side it is on walking the line in its stored order:
    "left" is where a +90 degree turn from the walking direction points, which is how
    `core.kratos.interfaces` and the element's node order count.

    Walking up a steep line, its left is the screen's left; walking down, the screen's
    right. Walking a flat line toward +x, its right is below."""
    first = face in ("left", "below")
    dx, dy = points[-1][0] - points[0][0], points[-1][1] - points[0][1]
    toward_first = ("left" if dy > 0 else "right") if is_steep(points) else \
        ("right" if dx > 0 else "left")
    if first:
        return toward_first
    return "right" if toward_first == "left" else "left"


def screen_face(points: Sequence[Sequence[float]], walking: str) -> str:
    """The inverse of `walking_side`: the screen face of the side `walking` is on."""
    first, second = faces(points)
    return first if walking_side(points, first) == walking else second
