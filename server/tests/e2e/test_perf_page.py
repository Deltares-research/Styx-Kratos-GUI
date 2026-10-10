"""What a user waits for in the page (plan alpha 6.2): from `results phase <n>` to that
phase drawn, and from Calculate to the first results on screen. Needs both `--run-e2e`
and `--run-perf`; compared with tests/perf/baseline.json like the server timings."""

from __future__ import annotations

import time

import pytest

from tests.e2e.test_flows import LONG, calculate, run_crow
from tests.perf.test_perf import check

pytestmark = pytest.mark.perf


def test_first_results_on_screen_and_a_phase_switch(app_page, request):
    run_crow(app_page)
    started = time.perf_counter()
    calculate(app_page)
    app_page.wait_for_function("document.querySelector('#vp-legend')"
                               " && !document.querySelector('#vp-legend').hidden", timeout=LONG)
    check("page_calculate_to_first_results_s", time.perf_counter() - started, request)

    switches = []
    for phase in (3, 5, 2, 7):
        started = time.perf_counter()
        app_page.evaluate(f"App.Command.run('results phase {phase}')")
        app_page.wait_for_function(
            f"App.Results.stage() === {phase} && document.querySelector('#vp-legend')"
            f".textContent.includes('phase {phase}')", timeout=LONG)
        switches.append(time.perf_counter() - started)
    switches.sort()
    check("page_phase_switch_s", switches[len(switches) // 2], request)
