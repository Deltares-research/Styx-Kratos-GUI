"""One command per test tier (plan/active/alpha-test-plan.md sec 2.3).

    python tools/test.py quick      JS syntax + headless JS + pytest without the browser
    python tools/test.py browser    quick, with the browser unit suite (Playwright)
    python tools/test.py e2e        browser, with the GUI end-to-end tests
    python tools/test.py kratos     tests that run Kratos
    python tools/test.py bench      the benchmark runner
    python tools/test.py perf       performance tests
    python tools/test.py all        everything this machine can run; prints what was skipped

Arguments after the tier go to pytest (or to the benchmark runner), e.g.
`python tools/test.py quick -k phases -x`. pytest always runs in the server's own venv,
whichever Python started this script. A step whose prerequisite is missing is reported as
skipped with the reason, never as a failure; the exit code is non-zero only when a step
that ran failed.
"""

from __future__ import annotations

import functools
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.launcher import platform_venv_name, venv_python  # noqa: E402

QUICKJS_ENV = "KRATOS_GUI_QUICKJS_PYTHON"
HEADLESS_NO_QUICKJS = 3
"""`frontend/tests/run_headless.py`'s exit code when quickjs cannot be imported."""

PYTEST_FLAGS = {
    "quick": ["-m", "not browser"],
    "browser": [],
    "e2e": ["--run-e2e"],
    "kratos": ["-m", "kratos", "--run-kratos"],
    "perf": ["-m", "perf", "--run-perf"],
    "all": ["--run-e2e", "--run-kratos", "--run-benchmarks", "--run-perf", "--run-slow", "-rs"],
}
WITH_JS_CHECKS = ("quick", "browser", "e2e", "all")
TIERS = (*PYTEST_FLAGS, "bench")


@dataclass
class Step:
    name: str
    command: list[str] | None
    cwd: pathlib.Path
    unavailable: str = ""
    skip_codes: tuple[int, ...] = field(default_factory=tuple)


def server_python(root: pathlib.Path = ROOT) -> pathlib.Path:
    candidate = venv_python(root / platform_venv_name())
    return candidate if candidate.exists() else pathlib.Path(sys.executable)


@functools.lru_cache(maxsize=None)
def _imports_quickjs(python: str) -> bool:
    try:
        return subprocess.call([python, "-c", "import quickjs"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except OSError:
        return False


def headless_python(has_quickjs=_imports_quickjs) -> str | None:
    """The interpreter for the quickjs suites: the one named in the environment, else the
    first of the server venv and this interpreter that can import quickjs."""
    named = os.environ.get(QUICKJS_ENV)
    if named:
        return named
    for python in dict.fromkeys([str(server_python()), sys.executable]):
        if has_quickjs(python):
            return python
    return None


def plan(tier: str, extra: list[str] | tuple[str, ...] = (), root: pathlib.Path = ROOT,
         has_quickjs=_imports_quickjs) -> list[Step]:
    tests = root / "frontend" / "tests"
    python = str(server_python())
    steps: list[Step] = []

    if tier in WITH_JS_CHECKS:
        steps.append(Step("syntax", [python, str(tests / "syntax_check.py")], root))
        headless = headless_python(has_quickjs)
        if headless:
            steps.append(Step("headless", [headless, str(tests / "run_headless.py")], root,
                              skip_codes=(HEADLESS_NO_QUICKJS,)))
        else:
            steps.append(Step("headless", None, root, unavailable=(
                f"no Python with quickjs found: pip install quickjs into one, or set "
                f"{QUICKJS_ENV} to it")))

    if tier == "bench":
        if (root / "benchmarks" / "__init__.py").exists():
            steps.append(Step("bench", [python, "-m", "benchmarks", "run", "--all", *extra],
                              root))
        else:
            steps.append(Step("bench", None, root, unavailable=(
                "benchmarks/ does not exist yet (plan Task 4.1)")))
        return steps

    steps.append(Step("pytest", [python, "-m", "pytest", "-q", *PYTEST_FLAGS[tier], *extra],
                      root))
    return steps


def _call(command: list[str], cwd: pathlib.Path) -> int:
    return subprocess.call(command, cwd=cwd)


def main(argv: list[str], execute=_call, has_quickjs=_imports_quickjs) -> int:
    tier = argv[1] if len(argv) > 1 else "quick"
    if tier not in TIERS:
        print(f"unknown tier {tier!r}; one of: {', '.join(TIERS)}", file=sys.stderr)
        return 2

    outcomes: list[tuple[str, str]] = []
    for step in plan(tier, argv[2:], has_quickjs=has_quickjs):
        if step.command is None:
            outcomes.append((step.name, f"skipped: {step.unavailable}"))
            continue
        print(f"\n== {step.name} ==", flush=True)
        code = execute(step.command, step.cwd)
        if code == 0:
            outcomes.append((step.name, "passed"))
        elif code in step.skip_codes:
            outcomes.append((step.name, f"skipped (exit {code})"))
        else:
            outcomes.append((step.name, f"FAILED (exit {code})"))

    print(f"\n== {tier} ==")
    for name, outcome in outcomes:
        print(f"  {name:<9} {outcome}")
    return 1 if any(outcome.startswith("FAILED") for _, outcome in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
