"""The browser's copy of the soil models, held to the server's (core/model/soil_models.py).

The material window offers a soil model and lists, per model, the parameters its law
reads, with their defaults, choices and when each is shown. The export checks a soil
against the same table, and `kratos-cli material ... models` prints it. Two copies of
that drift, so there is one -- generated from `core.model.soil_models` into
`frontend/js/soil-model-table.js` -- and this test fails the moment it is stale.
`frontend/js/soil-models.js` repeats the few functions that read it, and
`tests/test_draft_parity.py` holds those to the Python's answers.

    python tests/test_soil_model_table.py --write

rewrites it after a deliberate change.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.model import soil_models, units   # noqa: E402

TABLE = (pathlib.Path(__file__).resolve().parents[1] / "frontend" / "js"
         / "soil-model-table.js")

HEADER = '''/* Generated from core/model/soil_models.py -- the soil models a material can be: each
   one's law per dimension, its older law names, and the parameters the material window
   lists for it, in groups, with their SI defaults, choices and when each is shown. Read
   by frontend/js/soil-models.js.

   Not hand-edited: `python tests/test_soil_model_table.py --write` rebuilds it, and
   tests/test_soil_model_table.py fails when it is stale.
*/
window.App = window.App || {};
App.SOIL_MODEL_TABLE =
'''


def render(document: dict) -> str:
    return HEADER + json.dumps(document, indent=2, ensure_ascii=False) + ";\n"


def stored() -> dict:
    text = TABLE.read_text(encoding="utf-8")
    marker = "App.SOIL_MODEL_TABLE ="
    return json.loads(text[text.index(marker) + len(marker):].strip().rstrip(";"))


def test_the_browser_table_is_what_the_server_knows():
    assert stored() == soil_models.table(), (
        "frontend/js/soil-model-table.js is out of date. Rerun\n"
        "    python tests/test_soil_model_table.py --write")


def test_the_file_is_written_as_this_module_writes_it():
    assert TABLE.read_text(encoding="utf-8") == render(soil_models.table())


def test_every_numeric_parameter_has_a_unit():
    """A default the unit table cannot convert would arrive in a kN project in SI."""
    for model in soil_models.MODELS:
        for p in soil_models.parameters(model):
            if p.choices or p.flag:
                continue
            assert p.name in units.VARIABLES, p.name


if __name__ == "__main__":
    if "--write" in sys.argv:
        TABLE.write_text(render(soil_models.table()), encoding="utf-8", newline="\n")
        print(f"wrote {TABLE}")
