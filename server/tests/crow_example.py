"""The CROW example model, loaded from outside the package.

`examples/crow/crow.py` is an *example*, not part of the application: it builds one
specific model, the way a user's own script would, and the GUI opens it the same way a
user would -- `run examples/crow/crow.py` in the command box. So it lives with the
reference decks it is checked against rather than in `server/app/`, and like them it is
not in the repository (see `.gitignore`).

That leaves the tests that compare against it needing to load a module by path and to
say something useful when it is absent. Both happen here, once, so no test file has to
know where the example lives or repeat the skip.

Every test module that needs it does:

    from tests.crow_example import crow

and is skipped whole if the example is not on disk -- the same way
`test_crow_reference.py` already skips when a reference deck is missing. A clone without
`examples/` still runs green rather than erroring during collection.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "crow"
PATH = EXAMPLES / "crow.py"


def reference(name: str) -> pathlib.Path:
    """A reference deck beside the example, by file name."""
    return EXAMPLES / name


def _load():
    if not PATH.exists():                      # pragma: no cover - depends on the clone
        pytest.skip(f"{PATH} is not present; the CROW example and the reference decks "
                    "it is checked against are kept out of the repository",
                    allow_module_level=True)
    # A module name of its own, not `app.crow`: the example is not part of the package,
    # and importing it under a package name would put it into `app`'s namespace for
    # every later import in the session.
    specification = importlib.util.spec_from_file_location("crow_example_model", PATH)
    module = importlib.util.module_from_spec(specification)
    # Registered before it runs, so that its own `__main__` guard and anything that
    # inspects `sys.modules` behave as they would on a normal import.
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


crow = _load()
