"""The pages of the GUI tutorials (`docs/gui_tutorials/`) fit the steps that make their
screenshots (`tests/e2e/tutorials/`), without playing the steps.

The e2e test (`tests/e2e/test_gui_tutorials.py`) holds each page to the exact list of
screenshots the steps take. This catches the common mistakes earlier, in the quick tier:
a page that names a step that is not there, a step with no screenshot on its page, and a
page that is not on the site.
"""

from __future__ import annotations

import pytest

from tests.e2e import tutorials

MKDOCS = tutorials.ROOT / "mkdocs.yml"


@pytest.mark.parametrize("name", tutorials.names())
def test_every_screenshot_on_the_page_belongs_to_a_step(name):
    ids = [step.id for step in tutorials.load(name).STEPS]
    assert len(ids) == len(set(ids)), f"two steps of {name} have one id"
    shown = tutorials.page_images(name)
    assert len(shown) == len(set(shown)), f"the page of {name} shows a screenshot twice"
    strangers = [image for image in shown
                 if not any(image == i or image.startswith(i + "_") for i in ids)]
    assert not strangers, f"screenshots of no step of {name}: {strangers}"


@pytest.mark.parametrize("name", tutorials.names())
def test_every_step_has_a_screenshot_on_the_page(name):
    shown = tutorials.page_images(name)
    bare = [step.id for step in tutorials.load(name).STEPS
            if not any(image == step.id or image.startswith(step.id + "_")
                       for image in shown)]
    assert not bare, f"steps of {name} with no screenshot on the page: {bare}"


@pytest.mark.parametrize("name", tutorials.names())
def test_the_page_is_on_the_site(name):
    page = tutorials.load(name).PAGE
    assert (tutorials.PAGES / page).is_file()
    assert f"({page})" in (tutorials.PAGES / "index.md").read_text(encoding="utf-8")
    assert f": docs/gui_tutorials/{page}" in MKDOCS.read_text(encoding="utf-8"), \
        f"{page} is not in the nav"
