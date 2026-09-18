"""The zero-thickness interface split, on meshes small enough to reason about by hand.

`app.interfaces` is deliberately free of gmsh: it takes connectivity and coordinates and
returns connectivity, so the topology it performs -- which node is duplicated, which
element follows which copy, and which way round the resulting element is written -- can
be asserted exactly rather than inferred from a mesh nobody chose.

The arrangement every test here builds is the one examples/crow_case.mdpa contains: the
structure keeps the original nodes, each side of the soil gets its own copies, and one
interface element per side per segment ties them back together.
"""

from __future__ import annotations

import pytest

from app import interfaces


# A unit square either side of the line x = 0, meshed as four linear triangles.
#
#   4 ────── 5 ────── 6      y = 1
#   │ ╲      │ ╲      │
#   │   ╲    │   ╲    │
#   1 ────── 2 ────── 3      y = 0
#          x = 0
SQUARE_NODES = {
    1: (-1.0, 0.0, 0.0), 2: (0.0, 0.0, 0.0), 3: (1.0, 0.0, 0.0),
    4: (-1.0, 1.0, 0.0), 5: (0.0, 1.0, 0.0), 6: (1.0, 1.0, 0.0),
}
LEFT = [[1, 2, 5], [1, 5, 4]]
RIGHT = [[2, 3, 6], [2, 6, 5]]

# The interface runs up the middle, drawn from the bottom. Walking that way, "left" is
# the -x half: a +90 degree turn from (0, 1) points at (-1, 0).
UP = [(0.0, 0.0), (0.0, 1.0)]


def spec(sides: str, structural: bool = True, path=None, segments=None) -> interfaces.Spec:
    return interfaces.Spec(key="iface_1", path=path or UP,
                           segments=segments or [[2, 5]],
                           structural=structural, sides=sides)


def rows_of(*groups) -> list[list[int]]:
    return [list(row) for group in groups for row in group]


def split(sides: str, structural: bool = True, rows=None, nodes=None, **kwargs):
    rows = rows_of(LEFT, RIGHT) if rows is None else [list(r) for r in rows]
    result = interfaces.split_mesh([spec(sides, structural, **kwargs)], rows,
                                   dict(nodes or SQUARE_NODES))
    return rows, result


# ── Which nodes are duplicated ──────────────────────────────────────────────

def test_a_structure_keeps_the_original_nodes_and_each_soil_side_gets_a_copy():
    rows, result = split("both")

    # Two nodes on the line, two soils: four copies, and none of them is an original.
    assert len(result.duplicates) == 4
    assert set(result.duplicates.values()) == {2, 5}
    assert not set(result.duplicates) & set(SQUARE_NODES)
    assert all(2 not in row and 5 not in row for row in rows), \
        "no soil element is still welded to the pile's own nodes"


def test_the_two_sides_are_given_different_copies():
    rows, _ = split("both")
    left = {node for row in rows[:2] for node in row}
    right = {node for row in rows[2:] for node in row}

    assert not left & right, "the soil is split, not merely renumbered"


def test_detaching_one_side_leaves_the_other_welded_to_the_structure():
    rows, result = split("left")

    assert set(result.duplicates.values()) == {2, 5}
    assert len(result.duplicates) == 2
    assert rows[2:] == RIGHT, "the right-hand soil still shares the pile's nodes"
    assert all(2 not in row and 5 not in row for row in rows[:2])


def test_without_a_structure_one_soil_keeps_the_originals():
    """A free interface splits soil from soil: there is nothing in the middle to own the
    original nodes, so the undetached side keeps them."""
    rows, result = split("left", structural=False)

    assert len(result.duplicates) == 2
    assert rows[2:] == RIGHT
    assert all(2 not in row and 5 not in row for row in rows[:2])


def test_a_node_off_the_line_is_never_touched():
    rows, result = split("both")
    assert {1, 3, 4, 6} <= {node for row in rows for node in row}


# ── The end of the line, where the soil wraps round ─────────────────────────

# The square above with a second row of soil under it, so the interface stops at node 2
# with continuous ground beneath -- a sheet pile's toe.
#
#   4 ── 5 ── 6
#   │ ╲  │ ╲  │
#   1 ── 2 ── 3
#   │ ╲  │ ╲  │
#   7 ── 8 ── 9
TOE_NODES = {**SQUARE_NODES, 7: (-1.0, -1.0, 0.0), 8: (0.0, -1.0, 0.0),
             9: (1.0, -1.0, 0.0)}
BELOW = [[7, 8, 2], [7, 2, 1], [8, 9, 3], [8, 3, 2]]


def test_the_toe_node_is_shared_because_the_soil_is_continuous_around_it():
    """crow_case.mdpa's own arrangement: 52 duplicates per side for 53 pile nodes. The
    node at the toe is one soil node, not two, because the ground closes under the pile
    -- and it is still detached from the pile, which is what the interface is for."""
    rows, result = split("both", rows=rows_of(LEFT, RIGHT, BELOW), nodes=TOE_NODES)

    copies_of = {source: [new for new, old in result.duplicates.items() if old == source]
                 for source in (2, 5)}
    assert len(copies_of[5]) == 2, "a node mid-line has soil on either side of it"
    assert len(copies_of[2]) == 1, "the toe has one soil around it, so one copy"
    assert all(2 not in row for row in rows), "the pile still keeps the toe to itself"


def test_a_free_interface_does_not_split_the_soil_at_its_own_tip():
    """The end of a free line is a crack tip, not a toe: with no structure between the
    faces the ground there really is continuous, so the node stays single and the two
    faces meet at it. Splitting it would tear the soil open along a line the user drew
    the end of."""
    rows, result = split("left", structural=False,
                         rows=rows_of(LEFT, RIGHT, BELOW), nodes=TOE_NODES)

    assert set(result.duplicates.values()) == {5}, "only the node with two sides splits"
    element = result.elements["iface_1"][0]
    assert element[0] == element[2], "both faces share the tip"


def test_an_interface_element_at_the_toe_uses_the_shared_copy_on_both_sides():
    _, result = split("both", rows=rows_of(LEFT, RIGHT, BELOW), nodes=TOE_NODES)
    toe_copy = next(new for new, old in result.duplicates.items() if old == 2)

    both = result.elements["iface_1"]
    assert len(both) == 2
    assert all(toe_copy in element for element in both)


# ── How the element is written ──────────────────────────────────────────────

def test_one_interface_element_per_segment_per_detached_side():
    _, result = split("both")
    assert len(result.elements["iface_1"]) == 2

    _, one_sided = split("right")
    assert len(one_sided.elements["iface_1"]) == 1


def test_the_element_is_the_structure_side_then_the_soil_side():
    """The reference deck's shape: (a, b, ...) from the pile, then their copies."""
    _, result = split("both")

    for element in result.elements["iface_1"]:
        assert len(element) == 4
        first, second = element[:2], element[2:]
        assert set(first) == {2, 5}
        assert [result.duplicates[node] for node in second] == first


def test_the_element_normal_points_at_the_soil_it_holds():
    """A +90 degree turn from the first pair's direction has to point at the second
    pair's side -- the convention crow_case.mdpa writes, where the two faces of one wall
    carry opposite node orders."""
    rows, result = split("both")
    left_nodes = {node for row in rows[:2] for node in row}

    for element in result.elements["iface_1"]:
        (x0, z0, _), (x1, z1, _) = (SQUARE_NODES[n] for n in element[:2])
        normal = (-(z1 - z0), x1 - x0)
        towards_left = normal[0] < 0
        assert towards_left == (element[2] in left_nodes)


def test_a_quadratic_segment_keeps_its_midside_node_in_place():
    """Six nodes, written (end, end, mid | end, end, mid) -- the 3Plus3N layout."""
    nodes = {1: (-1.0, 0.0, 0.0), 2: (0.0, 0.0, 0.0), 3: (1.0, 0.0, 0.0),
             4: (-1.0, 1.0, 0.0), 5: (0.0, 1.0, 0.0), 6: (1.0, 1.0, 0.0),
             7: (-0.5, 0.5, 0.0), 8: (0.0, 0.5, 0.0), 9: (0.5, 0.5, 0.0),
             10: (-0.5, 0.0, 0.0), 11: (-1.0, 0.5, 0.0), 12: (-0.5, 1.0, 0.0),
             13: (0.5, 0.0, 0.0), 14: (1.0, 0.5, 0.0), 15: (0.5, 1.0, 0.0)}
    left = [[1, 2, 5, 10, 8, 7], [1, 5, 4, 7, 12, 11]]
    right = [[2, 3, 6, 13, 14, 9], [2, 6, 5, 9, 15, 8]]
    rows = rows_of(left, right)
    result = interfaces.split_mesh(
        [spec("both", segments=[[2, 5, 8]])], rows, nodes)

    assert set(result.duplicates.values()) == {2, 5, 8}
    for element in result.elements["iface_1"]:
        assert len(element) == 6
        assert [result.duplicates[n] for n in element[3:]] == element[:3]
        mid = nodes[result.duplicates[element[5]]]
        ends = [nodes[result.duplicates[n]] for n in element[3:5]]
        assert mid == pytest.approx([(a + b) / 2 for a, b in zip(*ends)])


def test_the_rows_a_caller_holds_are_remapped_the_same_way_the_elements_were():
    """Conditions and any other block sharing the split nodes have to follow the soil
    they sit on, which `renamed` is what lets a caller do."""
    rows, result = split("both")

    assert len(result.renamed) == len(rows)
    assert result.renamed[0] and set(result.renamed[0]) <= {2, 5}
    assert not result.renamed[2].keys() & result.renamed[0].keys() or \
        result.renamed[2] != result.renamed[0]


# ── Refusals ────────────────────────────────────────────────────────────────

def test_an_interface_with_no_soil_on_the_asked_side_is_reported():
    """A pile down the very edge of the model has ground on one face only. Saying so
    beats writing a deck whose contact holds nothing."""
    rows = rows_of(RIGHT)
    with pytest.raises(interfaces.InterfaceError, match="left"):
        interfaces.split_mesh([spec("both")], rows, dict(SQUARE_NODES))


def test_two_interfaces_on_one_line_are_refused_rather_than_silently_merged():
    rows = rows_of(LEFT, RIGHT)
    twin = interfaces.Spec(key="iface_2", path=UP, segments=[[2, 5]],
                           structural=True, sides="both")
    with pytest.raises(interfaces.InterfaceError):
        interfaces.split_mesh([spec("both"), twin], rows, dict(SQUARE_NODES))
