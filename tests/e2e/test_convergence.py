"""The Convergence window, live during Calculate, in the real page. Opt-in: `--run-e2e`.

Kratos is the fake of `tests/fakes/fake_kratos.py`, in its slow form: it writes the
test model's log one iteration at a time, a quarter of a second apart, while
`calculation.current_run` names the run -- what a real run does, only faster. Three
iterations per stage, seven stages.
"""

from __future__ import annotations

import re

import pytest

from tests.e2e.conftest import command, log_text
from tests.e2e.test_flows import LONG, run_model
from tests.e2e.test_pictures import PRIVATE_WINDOWS, files_of, png_dpi, wait_saved

SECONDS_PER_ITERATION = 0.25
ITERATIONS = 7 * 3


@pytest.fixture
def slow_kratos(monkeypatch):
    from core.analysis import calculation
    from tests.fakes import fake_kratos

    monkeypatch.setattr(calculation, "run", fake_kratos.slow_run(SECONDS_PER_ITERATION))


def dots(page) -> int:
    return page.locator(".dlg-convergence .cp-relative .cp-dot").count()


def test_the_window_follows_a_run_and_the_results_menu_opens_it_again(app_page, slow_kratos):
    page = app_page
    run_model(page)

    page.locator('#maintoolbar .tbtn[data-action="calculate"]').click()
    window = page.locator(".dlg-convergence")
    window.wait_for(state="visible", timeout=LONG)

    # The points come in while the run goes on: seen at a few counts on the way.
    seen = set()
    for _ in range(200):
        count = dots(page)
        seen.add(count)
        if "Finished" in window.locator(".cv-line1").inner_text():
            break
        page.wait_for_timeout(100)
    in_between = {count for count in seen if 0 < count < ITERATIONS}
    assert len(in_between) >= 2, f"the plot grew in steps, not at once: {sorted(seen)}"

    window.locator(".cv-line1").filter(has_text="Finished").wait_for(timeout=LONG)
    assert dots(page) == ITERATIONS
    assert "Criterion met" in window.locator(".cv-line2").inner_text()
    box = window.bounding_box()
    dock = page.locator("#dock").bounding_box()
    viewport = page.viewport_size
    assert box["x"] + box["width"] <= dock["x"], "left of the dock: the model tree stays in view"
    assert box["x"] + box["width"] > dock["x"] - 40, "at the right of the viewport"
    assert box["y"] + box["height"] > viewport["height"] - 120, "at the bottom"

    # Results mode came on with the run, and left Choose results closed: it would lie
    # over the window and hide how the run ended.
    page.wait_for_function("App.state.mode === 'results'", timeout=LONG)
    assert page.locator(".dlg-results").count() == 0
    window.get_by_role("button", name="Close").click()
    window.wait_for(state="detached")

    page.locator("#menubar").get_by_text("Results", exact=True).click()
    page.locator("#menu-layer").get_by_text("Convergence…").click()
    window.wait_for(state="visible", timeout=LONG)
    page.wait_for_function(f"document.querySelectorAll('.dlg-convergence .cp-relative "
                           f".cp-dot').length === {ITERATIONS}", timeout=LONG)
    assert "finished" in window.locator(".cv-line1").inner_text()
    assert page.errors == []


def test_the_command_box_opens_it_and_says_how_to_save(app_page):
    page = app_page
    run_model(page)
    page.locator('#maintoolbar .tbtn[data-action="calculate"]').click()
    window = page.locator(".dlg-convergence")
    window.locator(".cv-line1").filter(has_text="Finished").wait_for(timeout=LONG)
    window.get_by_role("button", name="Close").click()

    command(page, "results convergence")

    window.wait_for(state="visible", timeout=LONG)
    assert "results convergence csv" in log_text(page)
    assert page.errors == []


def test_the_save_button_saves_the_run_the_window_shows(app_page):
    page = app_page
    run_model(page)
    page.evaluate(PRIVATE_WINDOWS)
    page.locator('#maintoolbar .tbtn[data-action="calculate"]').click()
    window = page.locator(".dlg-convergence")
    window.locator(".cv-line1").filter(has_text="Finished").wait_for(timeout=LONG)
    run = page.evaluate("App.ConvergenceWindow.state().run")

    for label, ending in (("PNG", ".png"), ("CSV", ".csv")):
        window.get_by_role("button", name="Save ▾").click()
        page.locator("#modal-layer .menu").get_by_text(label, exact=True).click()
        wait_saved(page, re.escape(f"Saved {run}_convergence{ending}"))

    saved = files_of(page)
    assert set(saved) == {f"{run}_convergence.png", f"{run}_convergence.csv"}
    assert round(png_dpi(saved[f"{run}_convergence.png"])) == 300
    rows = saved[f"{run}_convergence.csv"].decode("utf-8").splitlines()
    assert len(rows) == 1 + ITERATIONS, "a header and a row per iteration"
    assert page.errors == []
