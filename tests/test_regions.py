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
