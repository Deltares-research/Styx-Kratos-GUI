"""The benchmark catalogue (benchmarks/cases.py) as tests: one per case, through
real Kratos. Opt-in: `pytest --run-benchmarks`; `tools/test.py bench` runs the same cases
through `python -m benchmarks`, which also writes the report.

A BLOCKED case is skipped with the feature it waits for; a KNOWN one is an xfail naming
its defect -- strict, so the day the defect is fixed this file says so.
"""

from __future__ import annotations

import pytest

from core.analysis import calculation
from benchmarks.cases import BY_ID, CASES
from benchmarks.runner import run_case

pytestmark = pytest.mark.benchmark

_done: dict[str, object] = {}


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    try:
        calculation.interpreter()
    except calculation.CalculationError as failure:
        pytest.skip(f"no Kratos configured: {failure}")
    return tmp_path_factory.mktemp("benchmark-runs")


def outcome(case_id: str, root):
    if case_id not in _done:
        for name in BY_ID[case_id].needs:
            outcome(name, root)
        _done[case_id] = run_case(BY_ID[case_id], root)
    return _done[case_id]


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_benchmark(case, runs, request):
    if case.blocked:
        pytest.skip(f"BLOCKED: {case.blocked}")
    if case.known_defect:
        request.applymarker(pytest.mark.xfail(reason=case.known_defect, strict=True))
    result = outcome(case.id, runs)
    lines = [f"{'ok ' if o.passed else 'BAD'} {o.name}: {o.measured} (expected {o.expected})"
             for o in result.outcomes]
    # The checks, not the status: the runner turns a known defect's pass into FAIL, which
    # here would be one more expected failure and hide exactly the news strict is for.
    checks_pass = bool(result.outcomes) and all(o.passed for o in result.outcomes)
    assert result.status != "ERROR" and checks_pass, \
        f"{case.id} {result.status}: {result.detail}\n  " + "\n  ".join(lines)
