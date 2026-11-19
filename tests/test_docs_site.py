"""The documentation site (`mkdocs.yml`, `tools/docs_site.py`): every page of the nav is
there, and the site's copy of a page fixes what only works on GitHub, without building the
site."""

from __future__ import annotations

import re

import pytest

from tools import docs_site

REPOSITORY = docs_site.REPOSITORY + "/blob/main/"
PAGES = {"README.md", "docs/USAGE.md", "docs/KRATOS_SETUP.md", "docs/developer/README.md"}


def nav() -> list[str]:
    return docs_site.nav_pages(docs_site.CONFIG.read_text(encoding="utf-8"))


def test_every_page_of_the_nav_is_in_the_repository_once():
    pages = nav()
    assert "README.md" in pages and "docs/gui_tutorials/index.md" in pages
    assert len(pages) == len(set(pages)), "a page is twice in the nav"
    missing = [page for page in pages if not (docs_site.ROOT / page).is_file()]
    assert not missing, f"pages of the nav that are not there: {missing}"


def test_the_nav_reads_titles_with_a_colon():
    config = 'nav:\n  - Home: README.md\n  - Part:\n      - "Way 1: build": docs/a.md\n'
    assert docs_site.nav_pages(config) == ["README.md", "docs/a.md"]


@pytest.mark.parametrize("page, target, html, want", [
    ("docs/USAGE.md", "KRATOS_SETUP.md#environment-variables", False,
     "KRATOS_SETUP.md#environment-variables"),
    ("README.md", "docs/KRATOS_SETUP.md", True, "docs/KRATOS_SETUP.html"),
    ("README.md", "docs/developer/README.md", True, "docs/developer/index.html"),
    ("docs/USAGE.md", "../core/kratos/parameters.py", False,
     REPOSITORY + "core/kratos/parameters.py"),
    ("README.md", "LICENSE", True, REPOSITORY + "LICENSE"),
    ("README.md", "core", False, docs_site.REPOSITORY + "/tree/main/core"),
    ("README.md", "https://example.org/a.md", False, "https://example.org/a.md"),
    ("README.md", "#getting-started", True, "#getting-started"),
    ("README.md", "docs/no_such_page.md", False, "docs/no_such_page.md"),
])
def test_a_link_goes_to_the_page_of_the_site_or_to_github(page, target, html, want):
    assert docs_site.link(page, target, PAGES, html=html) == (want, None)


def test_a_picture_is_copied_next_to_the_page():
    assert docs_site.link("docs/developer/README.md", "pipeline.svg", PAGES) == \
        ("pipeline.svg", "docs/developer/pipeline.svg")
    logo = "frontend/assets/STYX-wordmark-transparent-dark.png"
    assert docs_site.link("README.md", logo + "#gh-light-mode-only", PAGES, html=True) == \
        (logo, logo)


def test_the_copy_of_a_page():
    text = "\n".join([
        '<img src="frontend/assets/STYX-wordmark-transparent-dark.png#gh-light-mode-only">',
        '<img src="frontend/assets/STYX-wordmark-transparent-light.png#gh-dark-mode-only">',
        f'<a href="{docs_site.REPOSITORY}/actions"><img src="{docs_site.REPOSITORY}'
        '/actions/workflows/tests.yml/badge.svg" alt="Tests"></a> <a href="docs/USAGE.md">Use</a>',
        "",
        "> [!WARNING]",
        "> Keep the default [host](docs/KRATOS_SETUP.md).",
        ">",
        "> Second line.",
        "",
        "```text",
        "[not a link](core)",
        "```",
        "![missing](images/none.png)",
    ])
    copy, pictures, missing = docs_site.site_copy("README.md", text, PAGES)
    lines = copy.splitlines()
    assert lines[0] == '<img src="frontend/assets/STYX-wordmark-transparent-dark.png">'
    assert lines[1] == ""
    assert lines[2] == ' <a href="docs/USAGE.html">Use</a>'
    assert lines[4:8] == ["!!! warning", "    Keep the default [host](docs/KRATOS_SETUP.md).",
                          "    ", "    Second line."]
    assert "[not a link](core)" in lines
    assert pictures == ["frontend/assets/STYX-wordmark-transparent-dark.png"]
    assert missing == ["images/none.png"]


def test_the_pages_copy_with_only_screenshots_missing(tmp_path):
    """The screenshots are made in CI, so they may be missing here; nothing else may."""
    problems = docs_site.prepare(tmp_path)
    assert all("shows images/" in problem for problem in problems), problems
    assert all((tmp_path / page).is_file() for page in nav())


def test_the_help_menu_opens_pages_of_the_published_site():
    """Help > Documentation and GUI tutorials (frontend/js/documentation.js) open the
    `site_url` of mkdocs.yml, on pages the nav lists: moving a page breaks the menu."""
    script = (docs_site.ROOT / "frontend" / "js" / "documentation.js").read_text(encoding="utf-8")
    config = docs_site.CONFIG.read_text(encoding="utf-8")
    site = re.search(r"var SITE = '([^']+)'", script).group(1)
    assert re.search(r"^site_url:\s*(\S+)\s*$", config, re.MULTILINE).group(1) == site
    pages = re.search(r"var PAGES = \{(.*?)\};", script, re.DOTALL).group(1)
    opened = re.findall(r":\s*'([^']+)'", pages)
    assert opened == ["index.html", "docs/gui_tutorials/index.html"]
    published = {docs_site.html_page(page) for page in nav()}
    assert set(opened) <= published, set(opened) - published
