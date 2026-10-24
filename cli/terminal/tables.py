"""The CSV files `kratos-cli results` writes, and how it shows a number.

Both are the GUI's, so a file saved from the terminal is the file Results mode saves:
`field_csv` is `App.ResultsRender.csv` (`results csv`), `profile_csv` is
`App.ResultsPlot.csv` (the plot window's `results plot csv`), and every number in them is
written the way JavaScript's `String(value)` writes it (`js_number`). `shown` is
`App.ResultsRender.format`, what the results log prints.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal


def js_number(value: float) -> str:
    """`String(value)` in JavaScript: the shortest digits that read back as `value`, with
    an exponent only below 1e-6 or from 1e21 on, and no `.0` on a whole number.

    The digits are Python's `repr`, which is also the shortest that round-trip; only for
    a whole number of 18 or more digits can the two pick a different last digit.
    """
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    exact = Decimal(repr(abs(float(value)))).normalize()
    digits = "".join(map(str, exact.as_tuple().digits))
    k = len(digits)
    # The value is 0.<digits> x 10**n, as ECMA-262's Number::toString counts.
    n = k + int(exact.as_tuple().exponent)    # an int: the value is finite here
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * -n + digits
    mantissa = digits[0] + ("." + digits[1:] if k > 1 else "")
    return f"{sign}{mantissa}e{'+' if n - 1 >= 0 else '-'}{abs(n - 1)}"


def shown(value: float) -> str:
    """`App.ResultsRender.format`: three significant digits in an exponent outside
    1e-3 .. 1e5, fixed decimals inside it; ties rounded away from zero, as JavaScript's
    `toFixed` and `toExponential` do."""
    size = abs(value)
    if size == 0:
        return "0"
    if size >= 1e5 or size < 1e-3:
        exact = Decimal(size)
        exponent = exact.adjusted()
        mantissa = exact.scaleb(2 - exponent).quantize(Decimal(1), ROUND_HALF_UP)
        if mantissa >= 1000:
            mantissa, exponent = (mantissa / 10).quantize(Decimal(1), ROUND_HALF_UP), \
                exponent + 1
        text = str(int(mantissa))
        return (f"{'-' if value < 0 else ''}{text[0]}.{text[1:]}"
                f"e{'+' if exponent >= 0 else '-'}{abs(exponent)}")
    decimals = 0 if size >= 100 else 1 if size >= 10 else 2 if size >= 1 else 4
    fixed = Decimal(size).quantize(Decimal(1).scaleb(-decimals), ROUND_HALF_UP)
    return f"{'-' if value < 0 else ''}{fixed}"


def cell(text: object) -> str:
    """A CSV cell, quoted when it holds a comma, a quote or a line break."""
    value = "" if text is None else str(text)
    if any(mark in value for mark in ',"\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def field_csv(field: dict, run: str | None = None, stage: str | None = None) -> str:
    """One field, a row per node or element; an empty cell where there is no value, so
    a spreadsheet averaging the column is not handed zeroes."""
    column = "element" if field.get("location") == "elements" else "node"
    head = f"{column},{field.get('field') or 'value'}"
    if field.get("unit"):
        head += f" [{field['unit']}]"
    if run:
        head += f",# {run}" + (f" / {stage}" if stage else "")
    lines = [head]
    for id, value in zip(field["ids"], field["values"]):
        lines.append(f"{id}," + ("" if value is None else js_number(value)))
    return "\n".join(lines) + "\n"


def profile_csv(plot: dict) -> str:
    """One quantity along one member, a row per point, stage after stage."""
    lines = [f"stage,name,node,y [m],{plot['quantity']} [{plot['unit']}]"]
    for stage in plot["stages"]:
        nodes = stage.get("nodes") or []
        for at, (value, y) in enumerate(stage["points"]):
            lines.append(",".join([str(stage["index"]),
                                   cell(stage.get("stage") or stage.get("name")),
                                   str(nodes[at]) if at < len(nodes) else "",
                                   js_number(y), js_number(value)]))
    return "\n".join(lines) + "\n"
