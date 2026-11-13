"""The Convergence window, live during Calculate, in the real page. Opt-in: `--run-e2e`.

Kratos is the fake of `tests/fakes/fake_kratos.py`, in its slow form: it writes the
test model's log one iteration at a time, a quarter of a second apart, while
`calculation.current_run` names the run -- what a real run does, only faster. Three
iterations per stage, seven stages.
"""

from __future__ import annotations

import pytest

from tests.e2e.conftest import command, log_text
from tests.e2e.test_flows import LONG, run_model

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
    viewport = page.viewport_size
    assert box["x"] + box["width"] > viewport["width"] - 40, "at the right"
    assert box["y"] + box["height"] > viewport["height"] - 120, "at the bottom"

    window.get_by_role("button", name="Close").click()
    window.wait_for(state="detached")
    # The Choose results window opened with Results mode; it lies over the menu.
    page.locator(".dlg-results").get_by_role("button", name="Close").click()

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
