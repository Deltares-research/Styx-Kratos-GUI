"""The CROW example model, and the reference decks it is checked against.

The model itself is `app.crow` and is in the repository: it builds one specific project
out of the ordinary schema and exports it through the ordinary pipeline, and
`examples/crow/crow.py` is only a launcher that calls it (`run examples/crow/crow.py` in
the command box). Tests import it from the package, so they run on a fresh clone.

The *reference decks* are a different matter. They are copies of files from the
GeoMechanicsApplication's test suite, they are large, and they are not ours to vendor, so
they are gitignored and live beside the launcher in `examples/crow/`. `reference(name)`
is where a test asks for one, and a test that needs one skips -- itself, not the whole
module -- when it is not on disk::

    from tests.crow_example import crow, reference

    DECK = reference("crow_validation_model.mdpa")

    @pytest.mark.skipif(not DECK.exists(), reason="reference deck not in this clone")
    def test_something(): ...

This module used to load the model by path from `examples/crow/crow.py` as well, and
skipped every module that imported it when the example was absent -- 21 cases that a
clone without `examples/` never ran, although the model they exercise was tracked all
along. Only the comparisons against the gitignored decks need to skip.
"""

from __future__ import annotations

import pathlib

from app import crow                              # noqa: F401  (re-exported)

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "crow"
PATH = EXAMPLES / "crow.py"
"""The launcher. Nothing here imports it; it is named so a test can say where the
user-facing entry point is meant to be."""


def reference(name: str) -> pathlib.Path:
    """A reference deck beside the launcher, by file name.

    Returns the path whether or not it exists -- the caller decides whether a missing
    deck is a skip or a failure.
    """
    return EXAMPLES / name
