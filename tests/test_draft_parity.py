"""What a new soil starts as, said twice and held to one document.

The GUI starts a new soil from `App.PropertySets.KINDS.soil` and offers the six presets
of `App.MaterialLibrary`; the command line starts one from `core.model.drafts`. Two
copies of one table drift, so `frontend/tests/fixtures/drafts.js` is the document both
are held to: this module writes it from the Python, and `frontend/tests/test-drafts.js`
compares the JavaScript to it (`frontend/tests/run_headless.py drafts`).

    python tests/test_draft_parity.py --write

rewrites it after a deliberate change. The pattern is `tests/test_phase_parity.py`'s: a
`.js` file assigning one global, which Python reads by stripping the assignment.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.model import drafts   # noqa: E402

FIXTURE = (pathlib.Path(__file__).resolve().parents[1]
           / "frontend" / "tests" / "fixtures" / "drafts.js")

HEADER = '''/* Generated fixture -- what a new soil starts as, in the one document the GUI
   (property-sets.js, material-library.js) and the command line (core/model/drafts.py)
   are both held to. See tests/test_draft_parity.py, which writes and compares it, and
   frontend/tests/test-drafts.js, which reads it.

   Not hand-edited. `python tests/test_draft_parity.py --write` rebuilds it.
*/
window.DRAFTS_FIXTURE =
'''


def document() -> dict:
    return {
        "soil_laws": {str(dimension): law for dimension, law in drafts.SOIL_LAWS.items()},
        "soil_defaults": drafts.SOIL_DEFAULTS_SI,
        "library": drafts.LIBRARY,
    }


def rendered() -> str:
    return HEADER + json.dumps(document(), indent=2) + ";\n"


def on_disk() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    return json.loads(text[len(HEADER):].rstrip().rstrip(";"))


def test_the_fixture_is_what_the_python_says():
    assert FIXTURE.is_file(), "run `python tests/test_draft_parity.py --write`"
    assert on_disk() == document(), "run `python tests/test_draft_parity.py --write`"


def test_the_fixture_is_written_as_this_module_writes_it():
    assert FIXTURE.read_text(encoding="utf-8") == rendered()


if __name__ == "__main__" and "--write" in sys.argv:
    FIXTURE.write_text(rendered(), encoding="utf-8", newline="\n")
    print(f"wrote {FIXTURE}")
