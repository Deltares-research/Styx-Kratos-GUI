"""The GUI tutorials, as steps a script plays on the real page.

Each module here, besides `harness`, is one tutorial: a list of `harness.Step`s (`STEPS`)
that build one model (`MODEL`) the way its page in `docs/gui_tutorials/` (`PAGE`) tells a
user to. `tests/e2e/test_gui_tutorials.py` plays them and checks the model they build.
The module's name names the tutorial: its screenshot folder, its recorded run and its test.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGES = ROOT / "docs" / "gui_tutorials"
"""The site's pages; the screenshots go in `images/<tutorial>/` under it."""
RUNS = ROOT / "tests" / "fixtures" / "tutorial_runs"
"""One recorded Kratos run for each tutorial, in `<tutorial>/`."""

IMAGE = re.compile(r"!\[[^\]]*\]\((images/[^)\s]+)\)")
"""A Markdown image, and its path."""


def names() -> list[str]:
    return sorted(path.stem for path in Path(__file__).parent.glob("*.py")
                  if path.stem not in ("__init__", "harness"))


def load(name: str):
    return importlib.import_module(f"{__name__}.{name}")


def page_images(name: str) -> list[str]:
    """The screenshot names the tutorial's page shows, in order, without `.png`."""
    text = (PAGES / load(name).PAGE).read_text(encoding="utf-8")
    prefix = f"images/{name}/"
    found = []
    for path in IMAGE.findall(text):
        assert path.startswith(prefix) and path.endswith(".png"), \
            f"{load(name).PAGE} shows {path}, which is not a screenshot of {prefix}"
        found.append(path[len(prefix):-len(".png")])
    return found
