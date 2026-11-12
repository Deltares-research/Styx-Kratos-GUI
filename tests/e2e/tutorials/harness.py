"""What every GUI tutorial uses: the `Step` record, the `Tour` that plays the steps on a
page, and helpers that click the GUI the way a user does.

A step does only what the tutorial tells the reader to do: menus, the mode tabs, rail
tools, windows, the Model and Selection explorers, and the command box where the page says
to type. It never calls `App.runAction`, `App.setMode` or the API, because a reader can do
none of that. Reading `App.PROJECT` is fine in a wait or a check: it changes nothing.

A step waits for what it waits on (a condition, or the end of the page's requests to the
server), never for a fixed time, so a slower computer only makes the tutorial slower.

`Tour.picture` takes a screenshot where the page shows one. Without a folder to write to
(the test's `--doc-screenshots DIR`), it only records the name. The screenshots are the
same on every run of one computer: a fixed window size, no animations, no text cursor, the
mouse away from the model, and the cursor coordinates in the status bar hidden. A window
that scrolls is shown from its top, or scrolled just far enough to show what is marked.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tests.e2e.conftest import command

LONG = 120_000
"""How long to wait for the server: meshing and a run take a while."""

TOOL = '#maintoolbar .tbtn[data-action="{}"]'
QUIET = 0.15
"""Seconds with no request to the server before the page counts as settled."""

MARK = "tutorial-mark"
SHOT = "tutorial-shot"
HIDDEN = ("#sb-coords",)
"""What changes with the mouse, and so is hidden in every screenshot."""
STYLE = (f".{MARK} {{ outline: 3px solid #e8590c !important;"
         " outline-offset: -1px !important; }"
         + "".join(f" .{SHOT} {selector} {{ visibility: hidden !important; }}"
                   for selector in HIDDEN))
"""How a screenshot shows the reader what to click (an orange outline), and what it
hides. The classes are only on the page while the screenshot is taken."""

TO_THE_TOP = """() => document.querySelectorAll('#modal-layer .dialog *').forEach(e => {
    const overflow = getComputedStyle(e).overflowY;
    if ((overflow === 'auto' || overflow === 'scroll') && e.scrollHeight > e.clientHeight)
        e.scrollTop = 0;
})"""


@dataclass(frozen=True)
class Step:
    """One step of a tutorial.

    `id` names the step's screenshots (`<id>.png`, or `<id>_<part>.png` for a step with
    more than one) and its place on the page, so it never changes once the page links it.
    `do` plays the step through the GUI. `check` says what must be true after it.
    """

    id: str
    title: str
    do: Callable[["Tour"], None]
    check: Callable[["Tour"], None] | None = None


class StepFailed(AssertionError):
    pass


@dataclass
class Tour:
    """A tutorial played on one page."""

    page: object
    out: Path | None = None
    """Where the screenshots go, or None to make none."""
    pictures: list[str] = field(default_factory=list)
    """The screenshot names, in order, that the played steps asked for."""
    step: Step | None = None
    _open: set = field(default_factory=set)

    def __post_init__(self):
        page = self.page
        page.on("request", self._sent)
        page.on("requestfinished", self._done)
        page.on("requestfailed", self._done)
        if self.out is not None:
            self.out.mkdir(parents=True, exist_ok=True)

    # ── requests to the server ─────────────────────────────────────────────

    def _sent(self, request):
        if "/api/" in request.url:
            self._open.add(request)

    def _done(self, request):
        self._open.discard(request)

    def settle(self, timeout: float = LONG / 1000) -> None:
        """Wait until the page has sent nothing to the server for `QUIET` seconds: the
        edit just made is saved and the page has redrawn from the answer."""
        deadline = time.monotonic() + timeout
        quiet_since = None
        while True:
            self.page.wait_for_timeout(30)
            now = time.monotonic()
            if self._open:
                quiet_since = None
            elif quiet_since is None:
                quiet_since = now
            elif now - quiet_since >= QUIET:
                return
            if now > deadline:
                raise TimeoutError(f"requests still open: {[r.url for r in self._open]}")

    def until(self, expression: str, timeout: int = LONG) -> None:
        """Wait until `expression`, JavaScript on the page, is true."""
        self.page.wait_for_function(expression, timeout=timeout)

    # ── screenshots ────────────────────────────────────────────────────────

    def picture(self, part: str = "", of=None, mark=()) -> None:
        """The screenshot of this moment of the step, `<step id>[_<part>].png`: the whole
        page, or only the window or panel `of` (a locator). `mark` is what to outline:
        one selector or locator, or a list of them.

        Without a folder to write to, it only records the name, so a test can hold the
        page to the list of screenshots without making them."""
        name = self.step.id + (f"_{part}" if part else "")
        assert name not in self.pictures, f"two screenshots named {name}"
        self.pictures.append(name)
        if self.out is None:
            return
        page = self.page
        self.settle()
        if not page.evaluate("!!document.getElementById('tutorial-style')"):
            page.add_style_tag(content=STYLE)
            page.evaluate("document.head.lastElementChild.id = 'tutorial-style'")
        # Away from the model and the rail, so nothing shows a hover.
        size = page.viewport_size
        page.mouse.move(size["width"] - 2, size["height"] - 2)
        marked = [page.locator(m) if isinstance(m, str) else m
                  for m in ([mark] if isinstance(mark, str) or hasattr(mark, "evaluate_all")
                            else mark)]
        page.evaluate(TO_THE_TOP)
        for locator in marked:
            assert locator.count(), f"{name}: nothing to mark at {locator}"
            locator.first.scroll_into_view_if_needed()
            locator.evaluate_all(f"(es) => es.forEach(e => e.classList.add('{MARK}'))")
        page.evaluate(f"document.body.classList.add('{SHOT}')")
        # Two frames, so the outline and the last redraw are on screen.
        page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        (of or page).screenshot(path=str(self.out / f"{name}.png"), animations="disabled",
                                caret="hide")
        page.evaluate(f"document.body.classList.remove('{SHOT}');"
                      f"document.querySelectorAll('.{MARK}')"
                      f".forEach(e => e.classList.remove('{MARK}'))")

    # ── playing ────────────────────────────────────────────────────────────

    def play(self, steps: list[Step]) -> None:
        for step in steps:
            self.step = step
            try:
                step.do(self)
                self.settle()
                if step.check:
                    step.check(self)
            except Exception as error:
                raise StepFailed(f"step {step.id} ({step.title}): {error}") from error


# ── clicking the GUI ───────────────────────────────────────────────────────

def open_as_started(page, url: str) -> None:
    """The app as a reader sees it when Styx starts: the empty 2D project the server
    opens on. Test setup resets to the demo model, which no reader has seen."""
    answer = page.request.post(url + "/api/project/new")
    assert answer.ok, answer.text()
    page.reload()
    page.wait_for_function("window.App && App.PROJECT && App.PROJECT.layers"
                           " && App.PROJECT.layers.length === 0 && App.Viewport"
                           " && App.Viewport.getScene && App.Viewport.getScene()",
                           timeout=LONG)


def window(page):
    """The window on top."""
    return page.locator("#modal-layer .dialog").last


def field(page, label: str):
    """The control after the label `label` in the window on top."""
    return window(page).locator(
        f"xpath=.//label[normalize-space()='{label}']/following-sibling::*[1]")


def fill(control, value) -> None:
    """Type `value` and leave the field, so the window takes it."""
    control.fill(str(value))
    control.press("Tab")


def tool(tour: Tour, action: str) -> None:
    """A button of the main toolbar."""
    tour.page.locator(TOOL.format(action)).click()


def mode(tour: Tour, name: str) -> None:
    """A mode tab: soil, structures, mesh, flow, staged, results."""
    tour.page.locator(f'button[data-mode="{name}"]').click()
    tour.until(f"App.state.mode === '{name}'")
    tour.settle()


def rail_tool(key: str) -> str:
    """The selector of a rail tool, to click or to mark."""
    return f'#toolrail .rail-btn[data-tool="{key}"]'


def rail(tour: Tour, key: str, flyout: str | None = None) -> None:
    """A tool on the rail, or one item of its flyout (the small corner of the button)."""
    page = tour.page
    button = page.locator(rail_tool(key))
    assert button.count() == 1, f"no rail tool {key}"
    if not flyout:
        button.click()
        return
    item = page.get_by_text(flyout, exact=True).locator("visible=true")
    box = button.bounding_box()
    corner = (box["x"] + box["width"] - 3, box["y"] + box["height"] - 3)
    # A click on the corner while the flyout of the tool just used is closing can close
    # the new one as well: click again until it shows.
    for _ in range(3):
        page.mouse.move(*corner)
        page.mouse.click(*corner)
        try:
            item.last.wait_for(state="visible", timeout=2000)
            break
        except Exception:
            continue
    item.last.click()


def tree_row(page, label: str):
    """A row of the Model explorer, by its label (`Soil_Top · Part 1` for a soil body)."""
    pattern = "^" + re.escape(label).replace(r"\ ·\ ", r"\s+·\s+") + r"(\s|$)"
    return page.locator("#tree-model .tree-row").filter(
        has=page.locator(".tree-label", has_text=re.compile(pattern))).first


def select_in_tree(tour: Tour, label: str) -> None:
    tree_row(tour.page, label).locator(".tree-label").click()
    tour.settle()


def selection_row(page, label: str):
    """A row of the Selection explorer, by the start of its label."""
    return page.locator("#grid-selection .pgrid-row").filter(
        has=page.locator(f"xpath=./*[1][starts-with(normalize-space(), '{label}')]")).first


def set_in_selection(tour: Tour, label: str, value) -> None:
    """Type a value in a row of the Selection explorer and press Enter."""
    control = selection_row(tour.page, label).locator("input").first
    control.fill(str(value))
    control.press("Enter")
    tour.settle()


def choose_in_selection(tour: Tour, label: str, option: str) -> None:
    selection_row(tour.page, label).locator("select").first.select_option(label=option)
    tour.settle()


def rename(tour: Tour, label: str, new: str, picture: str = "") -> None:
    """Right-click a row of the Model explorer, Rename…, type the new name, OK. With
    `picture`, the screenshot of that part is taken with the name typed."""
    page = tour.page
    row = tree_row(page, label)
    row.locator(".tree-label").click(button="right")
    page.get_by_text("Rename…", exact=True).locator("visible=true").last.click()
    dialog = page.locator("#modal-layer .name-dialog-window")
    dialog.locator("input[name=name]").fill(new)
    if picture:
        tour.picture(picture, mark=[row, dialog.get_by_role("button", name="OK")])
    dialog.get_by_role("button", name="OK").click()
    dialog.wait_for(state="detached")
    tour.settle()


def type_command(tour: Tour, text: str) -> None:
    command(tour.page, text)
    tour.settle()


def project(tour: Tour) -> dict:
    """The project the page holds. For checks only."""
    return tour.page.evaluate("App.PROJECT")
