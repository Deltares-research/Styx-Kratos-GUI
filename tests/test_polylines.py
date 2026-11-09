"""Distances, nearest points and clipping along drawn polylines."""

import pytest

from core.model import polylines
from core.model.schemas import point_on_polyline


def test_polyline_distances_and_clipping_ignore_zero_length_legs():
    points = [(0, 0), (0, 0), (3, 0), (3, 0), (3, 4)]

    assert polylines.length(points) == 7
    on, distance, along = polylines.nearest(points, (4, 2))
    assert on == pytest.approx((3, 2))
    assert distance == pytest.approx(1)
    assert along == pytest.approx(5)
    assert polylines.between(points, 6, 1) == [(1, 0), (3, 0), (3, 3)]
    assert point_on_polyline((3, 2), points)
    assert not point_on_polyline((4, 2), points)


@pytest.mark.parametrize("points", [[], [(1, 2)], [(1, 2), (1, 2)]])
def test_a_degenerate_polyline_cannot_supply_a_nearest_point(points):
    with pytest.raises(ValueError, match="two distinct points"):
        polylines.nearest(points, (0, 0))
