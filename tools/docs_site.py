"""Build the documentation site from the pages that `mkdocs.yml` lists.

    python tools/docs_site.py     the site, with the GUI tutorial screenshots there now

The pages stay where they are in the repository: the README, `docs/` and the folders
next to their models. Zensical reads one folder only, so this script copies each page in
the `nav` of `mkdocs.yml`, and each picture a page shows, into `build/docs_site/pages/` at
the same path. Then Zensical builds the site from there into `build/docs_site/site/` (open
its `index.html`). On the way, the copy of a page changes what only works on GitHub:

- a link to a file that is not on the site (code, a project file, a folder) goes to that
  file on GitHub;
- a link in HTML to a page of the site goes to the HTML page;
- of a picture in two versions, for GitHub's light and dark mode, the site shows the
  light one, as it has a light theme only;
- a picture from the repository's own GitHub pages, such as the status badge of a
  workflow, is left out: the site cannot show it while the repository is private;
- a GitHub alert (`> [!NOTE]`) becomes a box of the same kind.

`tools/gui_tutorial.py` makes the screenshots first, then builds the site with this. The
site needs the packages of `requirements-docs.txt`.
"""

from __future__ import annotations

import pathlib
import posixpath
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mkdocs.yml"
PAGES = ROOT / "build" / "docs_site" / "pages"
"""Where the pages are copied to (`docs_dir` of `mkdocs.yml`)."""
SITE = ROOT / "build" / "docs_site" / "site"
"""Where Zensical builds the site (`site_dir` of `mkdocs.yml`)."""
REPOSITORY = "https://github.com/Deltares-research/Styx-Kratos-GUI"
BRANCH = "main"

PICTURES = {".png", ".svg", ".jpg", ".jpeg", ".gif"}
NAV_PAGE = re.compile(r"^\s*-\s.*:\s+(\S+\.md)\s*$", re.MULTILINE)
"""A page of the `nav`: `- Title: path/to/page.md`."""
MARKDOWN_LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^)\s]+)(\))")
HTML_LINK = re.compile(r"""(\b(?:src|href)=")([^"]+)(")""")
OWN_PICTURE = re.compile(
    r"(<a\b[^>]*>\s*)?<img\b[^>]*\bsrc=\"" + re.escape(REPOSITORY) + r"/[^\"]*\"[^>]*>"
    r"(\s*</a>)?")
"""A picture from the repository's GitHub pages, with the link around it."""
DARK_PICTURE = re.compile(r"<img\b[^>]*#gh-dark-mode-only\"[^>]*>\s*"
                          r"|!\[[^\]\n]*\]\([^)\s]*#gh-dark-mode-only\)")
"""A picture for GitHub's dark mode: the site has a light theme only."""
LIGHT_MODE = "#gh-light-mode-only"
FENCE = re.compile(r"^\s*(```|~~~)")
ALERT = re.compile(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$")
ALERT_BOXES = {"NOTE": "note", "TIP": "tip", "IMPORTANT": 'info "Important"',
               "WARNING": "warning", "CAUTION": 'danger "Caution"'}
"""The box of the site's theme for each kind of GitHub alert."""


def nav_pages(config: str) -> list[str]:
    """The pages the `nav` of `mkdocs.yml` lists, as paths from the repository root."""
    return NAV_PAGE.findall(config.split("\nnav:", 1)[-1])


def html_page(path: str) -> str:
    """The HTML page a Markdown page becomes (`use_directory_urls: false`)."""
    folder, name = posixpath.split(path)
    stem = "index" if name == "README.md" else name[:-len(".md")]
    return posixpath.join(folder, stem + ".html")


def link(page: str, target: str, pages: set[str], *,
         html: bool = False) -> tuple[str, str | None]:
    """The link `target` of `page` as the site's copy writes it, and the repository file
    to copy next to the page (a picture it shows), if any. A target that is not in the
    repository is left as it is, for the strict build or the picture check to report."""
    if re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith(("#", "/")):
        return target, None
    path, mark, fragment = target.partition("#")
    fragment = mark + fragment
    file = posixpath.normpath(posixpath.join(posixpath.dirname(page), path))
    if file.startswith("../") or not (ROOT / file).exists():
        return target, None
    if file in pages:
        return (html_page(path) if html else path) + fragment, None
    if (ROOT / file).is_file() and posixpath.splitext(file)[1].lower() in PICTURES:
        return path + ("" if fragment == LIGHT_MODE else fragment), file
    kind = "tree" if (ROOT / file).is_dir() else "blob"
    return f"{REPOSITORY}/{kind}/{BRANCH}/{file}{fragment}", None


def site_copy(page: str, text: str, pages: set[str]) -> tuple[str, list[str], list[str]]:
    """The page's text for the site, the pictures to copy next to it, and the pictures it
    shows that are not there (a screenshot not made yet, a wrong path)."""
    pictures: list[str] = []
    missing: list[str] = []

    def rewrite(match: re.Match, html: bool) -> str:
        before, target, after = match.groups()
        new, picture = link(page, target, pages, html=html)
        if picture:
            pictures.append(picture)
        elif new == target and (before.startswith("!") or before.startswith("src")) \
                and "://" not in target \
                and posixpath.splitext(target.partition("#")[0])[1].lower() in PICTURES:
            missing.append(target)
        return before + new + after

    lines: list[str] = []
    in_fence = False
    alert_open = False
    for line in text.splitlines():
        if FENCE.match(line) and not alert_open:
            in_fence = not in_fence
        if in_fence:
            lines.append(line)
            continue
        alert = ALERT.match(line)
        if alert:
            lines.append("!!! " + ALERT_BOXES[alert.group(1)])
            alert_open = True
            continue
        if alert_open:
            if line.startswith(">"):
                line = "    " + line[1:].removeprefix(" ")
            else:
                alert_open = False
        line = DARK_PICTURE.sub("", OWN_PICTURE.sub("", line))
        line = MARKDOWN_LINK.sub(lambda m: rewrite(m, html=False), line)
        line = HTML_LINK.sub(lambda m: rewrite(m, html=True), line)
        lines.append(line)
    return "\n".join(lines) + "\n", pictures, missing


def prepare(out: pathlib.Path = PAGES) -> list[str]:
    """Copy the pages and their pictures into `out`. Returns what is wrong: a page of the
    `nav` that is not there, and each picture a page shows that is not there."""
    shutil.rmtree(out, ignore_errors=True)
    pages = nav_pages(CONFIG.read_text(encoding="utf-8"))
    problems = [f"{page}: in the nav of mkdocs.yml, but not in the repository"
                for page in pages if not (ROOT / page).is_file()]
    for page in pages:
        if not (ROOT / page).is_file():
            continue
        text, pictures, missing = site_copy(
            page, (ROOT / page).read_text(encoding="utf-8"), set(pages))
        problems += [f"{page}: shows {target}, which is not there" for target in missing]
        (out / page).parent.mkdir(parents=True, exist_ok=True)
        (out / page).write_text(text, encoding="utf-8")
        for picture in pictures:
            (out / picture).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / picture, out / picture)
    return problems


def build(python: pathlib.Path) -> int:
    """Copy the pages, then build the site with Zensical in the venv of `python`."""
    problems = prepare()
    if problems:
        print("The site was not built:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    found = subprocess.run([str(python), "-c", "import zensical"], cwd=ROOT,
                           capture_output=True).returncode == 0
    if not found:
        print(f"The site was not built, because zensical is not installed in {python}.\n"
              "To build the site, install zensical with\n"
              f"  {python} -m pip install -r requirements-docs.txt", file=sys.stderr)
        return 2
    code = subprocess.run([str(python), "-m", "zensical", "build", "--strict", "--clean",
                           "-f", str(CONFIG)], cwd=ROOT).returncode
    if code == 0:
        print(f"site in {SITE}: open {SITE / 'index.html'}")
    return code


if __name__ == "__main__":
    sys.exit(build(pathlib.Path(sys.executable)))
