"""The `.mdpa` columns stay apart for any number, not only the ones that fit GiD's widths.

The deck copies GiD's fixed column widths so the two decks diff against each other. A
coordinate of -100 or less, or 10000 or more, fills all 15 characters of its column, and
a node id of 100000 or more fills its 6. Before the fix nothing was left between such a
number and the one before it, so Kratos read two numbers as one and stopped with "A Nodes
statement was expected but the given statement was Conditions".
"""

from __future__ import annotations

from core.kratos import writer
from tests import mdpa

TRIANGLE = "UPwSmallStrainElement2D3N"
LINE = "UPwFaceLoadCondition2D2N"


def render(coordinates, node_id, elements=(), conditions=(), parts=()):
    return writer._render(coordinates, node_id, list(elements), list(conditions), list(parts))


def test_coordinates_of_minus_100_and_less_stay_apart():
    coordinates = {1: (-100.0, -250.5, 0.0), 2: (-1234.5, -100.0, -100.0),
                   3: (10000.0, 12345.678, -99999.0)}
    text = render(coordinates, {1: 1, 2: 2, 3: 3})

    assert mdpa.parse(text).nodes == {1: (-100.0, -250.5, 0.0),
                                      2: (-1234.5, -100.0, -100.0),
                                      3: (10000.0, 12345.678, -99999.0)}


def test_a_long_node_id_stays_apart_from_its_first_coordinate():
    text = render({7: (-100.0, 0.0, 0.0)}, {7: 123456})

    assert mdpa.parse(text).nodes == {123456: (-100.0, 0.0, 0.0)}


def test_node_ids_of_100000_and_more_stay_apart_in_elements_and_conditions():
    coordinates = {1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (0.0, 1.0, 0.0)}
    node_id = {1: 100000, 2: 123456, 3: 999999}
    triangle = (TRIANGLE, [(1, 12345678901, [100000, 123456, 999999])])
    edge = (LINE, [(2, 0, [123456, 999999])])

    deck = mdpa.parse(render(coordinates, node_id, [triangle], [edge]))

    assert deck.element(1) == [100000, 123456, 999999]
    assert deck.elements[0].properties[1] == 12345678901
    assert deck.conditions[0].entries[2] == [123456, 999999]


def test_numbers_that_fit_keep_the_gid_layout():
    """The extra space takes one character of the column, so a number that fits gives
    the same text as before and decks still diff against GiD's."""
    coordinates = {1: (-99.5, 12.25, 0.0), 2: (1.0, 0.0, 0.0), 3: (0.0, 1.0, 0.0)}
    node_id = {1: 1, 2: 2, 3: 3}
    text = render(coordinates, node_id, [(TRIANGLE, [(1, 0, [1, 2, 3])])])
    lines = text.split(writer.LINE_END)

    assert lines[4] == "    1 -99.5000000000  12.2500000000   0.0000000000"
    assert lines[10] =="        1          0     1     2     3 "
