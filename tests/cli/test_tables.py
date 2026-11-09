"""`cli.terminal.tables`: the CSV files `kratos-cli results` writes, number for number the ones
the GUI saves.

The GUI writes a number with JavaScript's `String(value)`; the expected strings below
are what quickjs answered for each value.
"""

from __future__ import annotations

import pytest

from cli.terminal import tables


@pytest.mark.parametrize("value, written", [
    (0.0, "0"), (-0.0, "0"), (100.0, "100"), (-36000.0, "-36000"),
    (0.1, "0.1"), (0.28, "0.28"), (0.07, "0.07"), (0.1 + 0.2, "0.30000000000000004"),
    (-0.0015, "-0.0015"), (1e-5, "0.00001"), (1e-6, "0.000001"),
    (0.000001234, "0.000001234"), (1e-7, "1e-7"), (2.5e-7, "2.5e-7"), (5e-324, "5e-324"),
    (1e20, "100000000000000000000"), (1e21, "1e+21"), (1.2345e22, "1.2345e+22"),
    (1.7976931348623157e308, "1.7976931348623157e+308"),
    (12345678901234567.0, "12345678901234568"),
])
def test_a_number_is_written_as_javascript_writes_it(value, written):
    assert tables.js_number(value) == written


@pytest.mark.parametrize("value, shown", [
    (1.234e-4, "1.23e-4"), (123456.0, "1.23e+5"), (0.0005, "5.00e-4"), (99999.0, "99999"),
    (-2.5, "-2.50"), (15.25, "15.3"), (0.12345, "0.1235"), (0.0, "0"),
])
def test_a_number_is_shown_as_the_results_log_shows_it(value, shown):
    """`App.ResultsRender.format`: what the GUI's results log prints."""
    assert tables.shown(value) == shown


def test_a_cell_with_a_comma_or_a_quote_is_quoted():
    assert tables.cell('Dig, "deep"') == '"Dig, ""deep"""'
    assert tables.cell(None) == ""


@pytest.mark.parametrize("value, written", [
    (float("nan"), "NaN"),
    (float("inf"), "Infinity"),
    (float("-inf"), "-Infinity"),
])
def test_non_finite_field_values_keep_javascript_csv_spelling(value, written):
    assert tables.js_number(value) == written
