"""Run the JavaScript tests that need no browser, on a machine with no Node.

`live/tests/index.html` is the real suite and always will be: most of it drives a
THREE.js scene, a dock layout and real DOM events, and those need a browser. But a
good part of the live layer is pure logic -- the phase model, the water line, the
buffers -- and until now *none* of it had ever been executed, only bracket-checked
(plan sec 7.17). That is the largest untested surface in the project, and Milestone D
adds to it.

This runs the pure-logic part under `quickjs`, a JavaScript engine that installs as an
ordinary Python wheel. No Node, no browser, no build step.

    python live/tests/run_headless.py            # everything listed below
    python live/tests/run_headless.py phases     # one suite

What it does *not* do is pretend to be a browser. There is no DOM here and no attempt
at one: a suite gets into the list below only because it touches neither, and a suite
that starts touching the DOM belongs in `index.html` instead. A half-faked `document`
would let a test pass against a stub that the real page does not behave like, which is
worse than not running it.

`pip install quickjs` if it is missing; the script says so rather than failing
obscurely, and the browser suite is unaffected either way.
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = ROOT / "live" / "tests"
JS = ROOT / "live" / "js"

# Each suite: the sources it needs, then the test file. Order matters -- these are
# plain scripts sharing one global, exactly as the browser loads them.
SUITES = {
    "phases": (
        [TESTS / "fixtures" / "phase-cases.js", JS / "phases.js"],
        TESTS / "test-phases.js",
    ),
    # `results.js` loads no other module and touches no DOM, by design -- see its
    # header. Everything it reaches the world through, the suite replaces.
    # Arithmetic only, and the reason it is a module of its own: no DOM means the
    # headless runner can execute it, which is the only automated check JavaScript
    # gets on this machine.
    "results-render": (
        # The CROW fixture first: a real section and its fields, so the arithmetic is
        # exercised on a mesh rather than only on four-vertex squares.
        [TESTS / "fixtures" / "crow-field.js", JS / "results-render.js"],
        TESTS / "test-results-render.js",
    ),
    "results": (
        # calculate.js comes along because the handoff between the two is the whole of
        # task P0.4: what Calculate just wrote has to become the run `results` opens.
        # It touches no DOM either, so it loads here as cleanly as results.js does.
        [JS / "results-render.js", JS / "results.js", JS / "calculate.js"],
        TESTS / "test-results.js",
    ),
}


def _context():
    try:
        import quickjs
    except ImportError:
        print("quickjs is not installed, so no JavaScript can be executed here.\n"
              "    pip install quickjs\n"
              "The browser suite (live/tests/index.html) is unaffected.",
              file=sys.stderr)
        raise SystemExit(3)

    context = quickjs.Context()
    # The live layer is written for a browser and hangs everything off `window`;
    # harness.js takes it as an argument. Nothing below needs it to be anything more
    # than the global object.
    context.eval("var window = globalThis; window.App = window.App || {};")
    context.eval((TESTS / "harness.js").read_text(encoding="utf-8"))
    return context


def run(name: str) -> tuple[int, int, list[str]]:
    sources, test_file = SUITES[name]
    context = _context()
    for source in list(sources) + [test_file]:
        try:
            context.eval(source.read_text(encoding="utf-8"))
        except Exception as failure:
            print(f"{name}: {source.name} did not load: {failure}", file=sys.stderr)
            return 0, 1, [f"{source.name} did not load: {failure}"]

    # `T.run` returns a promise and the harness chains every case onto it, so the
    # engine's job queue has to be drained before the result exists.
    context.eval("var __result = null; T.run().then(function (r) { __result = r; });")
    while context.execute_pending_job():
        pass

    passed = context.eval("__result ? __result.passed : -1")
    failed = context.eval("__result ? __result.failed : -1")
    if passed < 0:
        return 0, 1, ["the suite never settled -- a test returned a promise "
                      "that nothing resolves"]
    count = int(context.eval("__result.failures.length"))
    failures = [str(context.eval(f"__result.failures[{n}]")) for n in range(count)]
    return int(passed), int(failed), failures


def main(argv: list[str]) -> int:
    wanted = argv[1:] or sorted(SUITES)
    unknown = [name for name in wanted if name not in SUITES]
    if unknown:
        print(f"no such suite: {', '.join(unknown)}. "
              f"Known: {', '.join(sorted(SUITES))}", file=sys.stderr)
        return 2

    total_passed = total_failed = 0
    for name in wanted:
        passed, failed, failures = run(name)
        total_passed += passed
        total_failed += failed
        status = "ok" if not failed else f"{failed} FAILED"
        print(f"{name}: {passed} passed, {status}")
        for failure in failures:
            print(f"  {failure}")

    print(f"\n{total_passed} passed, {total_failed} failed")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
