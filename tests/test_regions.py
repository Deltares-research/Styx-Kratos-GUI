"""The pieces a soil layer falls into when lines cut it (`core.model.regions`)."""

from __future__ import annotations

import pytest

from core.model import regions

BOX = (0.0, 10.0, -8.0, 0.0)


def pieces(*lines):
    return regions.pieces(*BOX, tuple(tuple(line) for line in lines))


def area(piece) -> float:
    return regions._area(piece.outline) + sum(regions._area(hole) for hole in piece.holes)


def test_nothing_cuts_a_layer_without_lines():
    only, = pieces()
    assert only.outline == ((0.0, -8.0), (10.0, -8.0), (10.0, 0.0), (0.0, 0.0))
    assert only.point == (5.0, -4.0)


def test_a_line_from_edge_to_edge_makes_two_pieces():
    left, right = pieces([(4.0, 0.0), (4.0, -8.0)])
    assert area(left) == pytest.approx(32.0)
    assert area(right) == pytest.approx(48.0)
    assert left.left == 0.0 and right.left == 4.0
    assert left.contains(left.point) and not right.contains(left.point)


def test_a_line_past_the_edges_is_clipped_to_the_layer():
    assert len(pieces([(4.0, 5.0), (4.0, -20.0)])) == 2


def test_a_line_that_stops_inside_cuts_nothing():
    assert len(pieces([(4.0, 0.0), (4.0, -3.0)])) == 1
    assert len(pieces([(2.0, -2.0), (4.0, -3.0)])) == 1


def test_a_dead_end_on_a_cut_cuts_no_more():
    assert len(pieces([(4.0, 0.0), (4.0, -8.0)], [(4.0, -3.0), (6.0, -3.0)])) == 2


def test_a_line_on_the_edge_of_the_layer_cuts_nothing():
    assert len(pieces([(0.0, 0.0), (10.0, 0.0)])) == 1
    assert len(pieces([(0.0, -2.0), (0.0, -6.0)])) == 1
    assert len(pieces([(-5.0, 0.0), (15.0, 0.0)])) == 1


def test_a_line_outside_the_layer_cuts_nothing():
    assert len(pieces([(0.0, 3.0), (10.0, 3.0)])) == 1


def test_lines_that_cross_make_four_pieces():
    assert len(pieces([(5.0, 0.0), (5.0, -8.0)], [(0.0, -4.0), (10.0, -4.0)])) == 4


def test_a_line_ending_on_another_cuts_only_its_own_side():
    found = pieces([(5.0, 0.0), (5.0, -8.0)], [(0.0, -2.0), (5.0, -2.0)],
                   [(0.0, -5.0), (5.0, -5.0)])
    assert sorted(round(area(p)) for p in found) == [10, 15, 15, 40]


def test_a_polyline_cuts_as_one_line():
    found = pieces([(0.0, -2.0), (5.0, -2.0), (5.0, 0.0)])
    assert sorted(round(area(p)) for p in found) == [10, 70]


def test_an_l_shaped_piece_has_a_point_inside_it():
    corner, rest = sorted(pieces([(0.0, -2.0), (5.0, -2.0), (5.0, 0.0)]), key=area)
    assert rest.contains(rest.point)
    assert not corner.contains(rest.point)
    assert corner.contains(corner.point)


def test_a_closed_line_inside_leaves_a_hole():
    found = pieces([(2.0, -2.0), (4.0, -2.0), (4.0, -4.0), (2.0, -4.0), (2.0, -2.0)])
    lens, rest = sorted(found, key=area)
    assert area(lens) == pytest.approx(4.0)
    assert area(rest) == pytest.approx(76.0)
    assert len(rest.holes) == 1
    assert rest.contains(rest.point) and not rest.contains(lens.point)
    assert lens.contains(lens.point)


def test_a_line_joining_a_closed_line_to_the_edge_cuts_nothing_more():
    found = pieces([(2.0, -2.0), (4.0, -2.0), (4.0, -4.0), (2.0, -4.0), (2.0, -2.0)],
                   [(2.0, -2.0), (2.0, 0.0)])
    lens, rest = sorted(found, key=area)
    assert area(lens) == pytest.approx(4.0)
    assert len(rest.holes) == 1


def test_a_sloped_line_cuts():
    assert sorted(round(area(p)) for p in pieces([(0.0, -8.0), (10.0, 0.0)])) == [40, 40]


def test_pieces_come_from_the_top_down_then_from_the_left():
    found = pieces([(5.0, 0.0), (5.0, -8.0)], [(0.0, -4.0), (5.0, -4.0)])
    assert [(p.left, p.top, p.bottom) for p in found] == [
        (0.0, 0.0, -4.0), (5.0, 0.0, -8.0), (0.0, -4.0, -8.0)]


def test_an_end_within_the_tolerance_reaches_the_edge():
    assert len(pieces([(4.0, 1e-9), (4.0, -8.0 - 1e-9)])) == 2
    assert len(pieces([(4.0, -1e-9), (4.0, -8.0 + 1e-9)])) == 2
    assert len(pieces([(4.0, -0.01), (4.0, -8.0)])) == 1


# ── A drawn soil surface: any polygon ───────────────────────────────────────

SQUARE = ((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0))


def polygon(outline, *lines):
    return regions.polygon_pieces(tuple(outline), tuple(tuple(line) for line in lines))


def test_nothing_cuts_a_surface_without_lines():
    only, = polygon(SQUARE)
    assert only.outline == SQUARE
    assert only.contains(only.point)


def test_a_line_across_a_surface_makes_two_pieces():
    """The steps of issue #125: a 3 m square and a line from (1, 3) down to (1, 0)."""
    left, right = polygon(SQUARE, [(1.0, 3.0), (1.0, 0.0)])
    assert area(left) == pytest.approx(3.0)
    assert area(right) == pytest.approx(6.0)
    assert left.left == 0.0 and right.left == 1.0


def test_a_surface_drawn_clockwise_gives_the_same_pieces():
    assert polygon(SQUARE[::-1], [(1.0, 3.0), (1.0, 0.0)]) \
        == polygon(SQUARE, [(1.0, 3.0), (1.0, 0.0)])


def test_a_line_past_the_edges_of_a_surface_is_clipped_to_it():
    assert len(polygon(SQUARE, [(1.0, 10.0), (1.0, -10.0)])) == 2


def test_a_line_that_stops_inside_a_surface_cuts_nothing():
    assert len(polygon(SQUARE, [(1.0, 3.0), (1.0, 1.0)])) == 1


def test_a_line_on_the_edge_of_a_surface_or_outside_it_cuts_nothing():
    assert len(polygon(SQUARE, [(0.0, 0.0), (3.0, 0.0)])) == 1
    assert len(polygon(SQUARE, [(5.0, 0.0), (5.0, 3.0)])) == 1


def test_a_line_typed_just_short_of_the_edge_still_reaches_it():
    assert len(polygon(SQUARE, [(1.0, 3.0 - 1e-7), (1.0, 1e-7)])) == 2


def test_a_line_that_leaves_a_concave_surface_and_comes_back_cuts_it_twice():
    # A U: two arms standing on a base, open at the top between x = 1 and x = 2.
    u = ((0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (2.0, 3.0), (2.0, 1.0), (1.0, 1.0),
         (1.0, 3.0), (0.0, 3.0))
    found = polygon(u, [(-1.0, 2.0), (4.0, 2.0)])
    assert len(found) == 3
    assert sum(area(piece) for piece in found) == pytest.approx(7.0)
    assert all(piece.contains(piece.point) for piece in found)


def test_a_triangle_cut_through_a_corner():
    triangle = ((0.0, 0.0), (4.0, 0.0), (0.0, 4.0))
    first, second = polygon(triangle, [(0.0, 0.0), (3.0, 3.0)])
    assert area(first) == pytest.approx(4.0) and area(second) == pytest.approx(4.0)


# ── Two soil surfaces intersected (`regions.overlay`) ──────────────────────────

def square(x0, y0, size):
    return ((x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size))


def total(found) -> float:
    return sum(area(piece) for piece in found)


def test_two_overlapping_squares_fall_into_their_own_parts_and_the_overlap():
    a_only, both, b_only = regions.overlay(square(0.0, 0.0, 4.0), square(2.0, 2.0, 4.0))
    assert [total(found) for found in (a_only, both, b_only)] == pytest.approx(
        [12.0, 4.0, 12.0])
    overlap, = both
    assert sorted(overlap.outline) == [(2.0, 2.0), (2.0, 4.0), (4.0, 2.0), (4.0, 4.0)]


def test_no_piece_of_an_overlay_has_a_hole():
    # The lens lies wholly inside the layer: what is left of the layer is a ring, which a
    # soil surface's outline cannot hold, so it comes in pieces either side of the lens.
    a_only, both, b_only = regions.overlay(square(0.0, 0.0, 10.0), square(4.0, 4.0, 2.0))
    assert not b_only
    assert total(both) == pytest.approx(4.0)
    assert total(a_only) == pytest.approx(96.0)
    assert len(a_only) >= 2
    assert all(not piece.holes for found in (a_only, both) for piece in found)


def test_an_overlay_either_way_round_gives_the_same_overlap():
    a, b = square(0.0, 0.0, 4.0), square(3.0, -1.0, 2.0)
    a_only, both, b_only = regions.overlay(a, b)
    b_only_too, both_too, a_only_too = regions.overlay(b, a)
    assert total(both) == pytest.approx(total(both_too)) == pytest.approx(1.0)
    assert total(a_only) == pytest.approx(total(a_only_too)) == pytest.approx(15.0)
    assert total(b_only) == pytest.approx(total(b_only_too)) == pytest.approx(3.0)


def test_surfaces_that_only_touch_have_no_overlap():
    _, both, _ = regions.overlay(square(0.0, 0.0, 4.0), square(4.0, 0.0, 4.0))
    assert both == ()


def test_a_concave_surface_can_overlap_another_in_two_places():
    u_shape = ((0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (4.0, 4.0), (4.0, 1.0), (2.0, 1.0),
               (2.0, 4.0), (0.0, 4.0))
    a_only, both, b_only = regions.overlay(u_shape, ((-1.0, 2.0), (7.0, 2.0), (7.0, 3.0),
                                                     (-1.0, 3.0)))
    assert len(both) == 2
    assert total(both) == pytest.approx(4.0)
    assert total(a_only) == pytest.approx(18.0 - 4.0)
    assert total(b_only) == pytest.approx(8.0 - 4.0)
