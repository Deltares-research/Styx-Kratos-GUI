"""What every GUI tutorial uses: the `Step` record, the `Tour` that plays the steps on a
page, and helpers that click the GUI the way a user does.

A step does only what the tutorial tells the reader to do: menus, the mode tabs, rail
tools, windows, the Model and Selection explorers, and the command box where the page says
to type. It never calls `App.runAction`, `App.setMode` or the API, because a reader can do
none of that. Reading `App.PROJECT` is fine in a wait or a check: it changes nothing.

A step waits for what it waits on (a condition, or the end of the page's requests to the
server), never for a fixed time, so a slower computer only makes the tutorial slower.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable

from tests.e2e.conftest import command

LONG = 120_000
"""How long to wait for the server: meshing and a run take a while."""

TOOL = '#maintoolbar .tbtn[data-action="{}"]'
QUIET = 0.15
"""Seconds with no request to the server before the page counts as settled."""


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
    pictures: list[str] = field(default_factory=list)
    """The screenshot names, in order, that the played steps asked for."""
    step: Step | None = None
    _open: set = field(default_factory=set)

    def __post_init__(self):
        page = self.page
        page.on("request", self._sent)
        page.on("requestfinished", self._done)
        page.on("requestfailed", self._done)

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

    def picture(self, part: str = "", of=None, mark: str | None = None) -> None:
        """The screenshot of this moment of the step: the whole page, or the window or
        panel `of` (a locator), with the tool `mark` (a selector) outlined.

        Without a folder to write to, it only records the name, so a test can hold the
        page to the list of screenshots without making them."""
        name = self.step.id + (f"_{part}" if part else "")
        self.pictures.append(name)

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


def rail(tour: Tour, key: str, flyout: str | None = None) -> None:
    """A tool on the rail, or one item of its flyout (the small corner of the button)."""
    page = tour.page
    button = page.locator(f'#toolrail .rail-btn[data-tool="{key}"]')
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


def rename(tour: Tour, label: str, new: str) -> None:
    """Right-click a row of the Model explorer, Rename…, type the new name, OK."""
    page = tour.page
    tree_row(page, label).locator(".tree-label").click(button="right")
    page.get_by_text("Rename…", exact=True).locator("visible=true").last.click()
    dialog = page.locator("#modal-layer .name-dialog-window")
    dialog.locator("input[name=name]").fill(new)
    dialog.get_by_role("button", name="OK").click()
    dialog.wait_for(state="detached")
    tour.settle()


def type_command(tour: Tour, text: str) -> None:
    command(tour.page, text)
    tour.settle()


def project(tour: Tour) -> dict:
    """The project the page holds. For checks only."""
    return tour.page.evaluate("App.PROJECT")
