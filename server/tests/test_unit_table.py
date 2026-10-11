"""The browser's copy of the unit systems, held to the server's (app/units.py).

The material editor labels each Kratos variable with its unit in the project's system,
and the library converts its presets into that system, so the browser needs what
`app.units` knows: the systems, each quantity's dimension and labels, and which quantity
each Kratos variable is. Two copies of that drift, so there is one -- generated from
`app.units` into `live/js/unit-table.js` -- and this test fails the moment it is stale.

    python server/tests/test_unit_table.py --write

rewrites it after a deliberate change.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import units   # noqa: E402

TABLE = pathlib.Path(__file__).resolve().parents[2] / "live" / "js" / "unit-table.js"

HEADER = '''/* Generated from server/app/units.py -- the unit systems a project can be in, each
   quantity's dimension (mass, length, time) and label, and the quantity of every Kratos
   variable the application knows. Read by live/js/units.js.

   Not hand-edited: `python server/tests/test_unit_table.py --write` rebuilds it, and
   server/tests/test_unit_table.py fails when it is stale.
*/
window.App = window.App || {};
App.UNIT_TABLE =
'''


def build() -> dict:
    return {
        "default": units.DEFAULT,
        "gravity": units.GRAVITY_SI,
        "systems": {name: {"title": s.title, "mass": s.mass, "length": s.length,
                           "time": s.time}
                    for name, s in units.SYSTEMS.items()},
        "quantities": {q.name: {"dimension": list(q.dimension), "labels": q.labels}
                       for q in units.QUANTITIES.values()},
        "variables": {name: q.name for name, q in units.VARIABLES.items()},
    }


def render(document: dict) -> str:
    return HEADER + json.dumps(document, indent=2, ensure_ascii=False) + ";\n"


def stored() -> dict:
    text = TABLE.read_text(encoding="utf-8")
    marker = "App.UNIT_TABLE ="
    return json.loads(text[text.index(marker) + len(marker):].strip().rstrip(";"))


def test_the_browser_table_is_what_the_server_knows():
    assert stored() == build(), (
        "live/js/unit-table.js is out of date. Rerun\n"
        "    python server/tests/test_unit_table.py --write")


def test_every_variable_names_a_quantity_the_table_has():
    table = build()
    assert set(table["variables"].values()) <= set(table["quantities"])


if __name__ == "__main__":
    if "--write" in sys.argv:
        TABLE.write_text(render(build()), encoding="utf-8")
        print(f"wrote {TABLE}")
