"""Run the JavaScript tests that need no browser, on a machine with no Node.

`frontend/tests/index.html` is the real suite and always will be: most of it drives a
THREE.js scene, a dock layout and real DOM events, and those need a browser. But a
good part of the live layer is pure logic -- the stage model, the water line, the
buffers -- and until now *none* of it had ever been executed, only bracket-checked
(plan sec 7.17). That is the largest untested surface in the project, and Milestone D
adds to it.

This runs the pure-logic part under `quickjs`, a JavaScript engine that installs as an
ordinary Python wheel. No Node, no browser, no build step.

    python frontend/tests/run_headless.py            # everything listed below
    python frontend/tests/run_headless.py stages     # one suite

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
TESTS = ROOT / "frontend" / "tests"
JS = ROOT / "frontend" / "js"

# Each suite: the sources it needs, then the test file. Order matters -- these are
# plain scripts sharing one global, exactly as the browser loads them.
SUITES = {
    "stages": (
        [TESTS / "fixtures" / "stage-cases.js", JS / "stages.js"],
        TESTS / "test-stages.js",
    ),
    # `results.js` loads no other module and touches no DOM, by design -- see its
    # header. Everything it reaches the world through, the suite replaces.
    # Arithmetic only, and the reason it is a module of its own: no DOM means the
    # headless runner can execute it, which is the only automated check JavaScript
    # gets on this machine.
    "results-render": (
        # The field fixture first: a whole section and its fields, so the arithmetic is
        # exercised on a mesh rather than only on four-vertex squares.
        [TESTS / "fixtures" / "results-field.js", JS / "results-render.js"],
        TESTS / "test-results-render.js",
    ),
    # The Model explorer's colour toggle and the `colour` command. The toggle and the
    # mesh drawing are DOM; which parts are on, in which colour, is not.
    "part-colors": (
        [JS / "part-colors.js"],
        TESTS / "test-part-colors.js",
    ),
    # `water <level>` / `water off`: what was asked and what to send. The request and
    # the redraw are patches.js's.
    "water": (
        [JS / "unit-table.js", JS / "units.js", JS / "water-command.js"],
        TESTS / "test-water-command.js",
    ),
    # `script <file.py>`: what was asked and what to send. The request and what is said
    # once it is written are patches.js's.
    "script": (
        [JS / "script-command.js"],
        TESTS / "test-script-command.js",
    ),
    # `node <id>`, the right-click "which parts is this node in" and the hover: the
    # node -> parts index and the text. The fetch, the marker and the menu are DOM.
    "node-parts": (
        [JS / "node-parts.js"],
        TESTS / "test-node-parts.js",
    ),
    # The Mesh properties dialog: its settings, validation and when the Mesh tab opens
    # it. The dialog itself is DOM, built only when `open()` runs.
    "mesh-settings": (
        [JS / "mesh-settings.js"],
        TESTS / "test-mesh-settings.js",
    ),
    # `run <case.py>` for a deck case: whether its mesh came along, the Model explorer
    # rows and the log line. Showing it and switching to the Mesh tab are DOM.
    "deck": (
        [JS / "stages.js", JS / "deck.js"],
        TESTS / "test-deck.js",
    ),
    # `results plot` and the figure it draws: the wall and interface curves per stage.
    # results.js comes along because it is what routes the command here.
    "results-plot": (
        [JS / "download.js", JS / "results-render.js", JS / "results.js", JS / "results-plot.js"],
        TESTS / "test-results-plot.js",
    ),
    # `results convergence` and its figure, drawn from real logs the server parsed
    # (the fixture, written by tests/test_convergence_parity.py).
    "convergence-plot": (
        [TESTS / "fixtures" / "convergence-cases.js", JS / "download.js",
         JS / "results-render.js", JS / "results.js", JS / "convergence-plot.js"],
        TESTS / "test-convergence-plot.js",
    ),
    # A saved picture: the scene as a list of shapes, then those shapes as a file. Reading
    # the scene, the canvas, the clipboard and the save windows are in the browser suite.
    "picture-draw": (
        [JS / "results-render.js", JS / "ruler.js", JS / "picture-draw.js"],
        TESTS / "test-picture-draw.js",
    ),
    "picture-dialog": (
        [JS / "picture-draw.js", JS / "picture-dialog.js"],
        TESTS / "test-picture-dialog.js",
    ),
    "picture-writers": (
        [JS / "zip.js", JS / "picture-draw.js", JS / "picture-writers.js"],
        TESTS / "test-picture-writers.js",
    ),
    # The rulers' arithmetic: steps, ticks, labels, the ranges a view shows. Painting
    # the canvases and the toolbar wiring are test-ruler-dom.js, in the browser.
    "ruler": (
        [JS / "ruler.js"],
        TESTS / "test-ruler.js",
    ),
    # Where node and element numbers go: grouping, fans, culling, the cap. The menu row
    # is test-mesh-labels-dom.js, in the browser.
    "mesh-labels": (
        [JS / "mesh-labels.js"],
        TESTS / "test-mesh-labels.js",
    ),
    # Drafting, validating and saving interfaces, with the API stood in.
    "interfaces": (
        [JS / "unit-table.js", JS / "units.js", JS / "soil-model-table.js",
         JS / "soil-models.js", JS / "property-sets.js",
         JS / "interfaces.js"],
        TESTS / "test-interfaces.js",
    ),
    "results": (
        # calculate.js comes along because the handoff between the two is the whole of
        # task P0.4: what Calculate just wrote has to become the run `results` opens.
        # It touches no DOM either, so it loads here as cleanly as results.js does.
        # stages.js gives `projectStage` the project's stage order to match a run to.
        [JS / "download.js", JS / "stages.js", JS / "results-render.js", JS / "results.js",
         JS / "calculate.js"],
        TESTS / "test-results.js",
    ),
    # The project's unit system: labels, conversions of library presets, and the
    # `units` command. The request and the redraw are patches.js's.
    "units": (
        [JS / "unit-table.js", JS / "units.js"],
        TESTS / "test-units.js",
    ),
    # Property sets: the law a new soil, profile, tendon or contact starts with, what
    # its law needs, what the server derives, and how a typed value becomes Kratos'.
    "property-sets": (
        [JS / "unit-table.js", JS / "units.js", JS / "soil-model-table.js",
         JS / "soil-models.js", JS / "property-sets.js"],
        TESTS / "test-property-sets.js",
    ),
    # The soil models: their laws, what the material window lists for each, and when.
    "soil-models": (
        [JS / "unit-table.js", JS / "units.js", JS / "soil-model-table.js",
         JS / "soil-models.js", JS / "property-sets.js"],
        TESTS / "test-soil-models.js",
    ),
    # What a new soil or structure starts as, held to the command line's
    # (core/model/drafts.py) through the fixture tests/test_draft_parity.py writes.
    "drafts": (
        [TESTS / "fixtures" / "drafts.js", JS / "unit-table.js", JS / "units.js",
         JS / "soil-model-table.js", JS / "soil-models.js", JS / "property-sets.js",
         JS / "material-library.js", JS / "beams.js",
         JS / "anchors.js", JS / "interfaces.js", JS / "loads.js", JS / "normal-loads.js",
         JS / "lines.js",
         JS / "boundary-conditions.js"],
        TESTS / "test-drafts.js",
    ),
    # What each Structure-mode Delete sends, held to the edit kratos-cli makes through
    # the fixture tests/cli/test_edit_parity.py writes. The request is stood in. The
    # Deletes made in a window, the stage list, the tree or the command box need the
    # DOM, so the browser suite drives those.
    "edits": (
        [TESTS / "fixtures" / "edits.js", JS / "unit-table.js", JS / "units.js",
         JS / "soil-model-table.js", JS / "soil-models.js", JS / "property-sets.js",
         JS / "material-library.js", JS / "beams.js",
         JS / "anchors.js", JS / "interfaces.js", JS / "loads.js", JS / "normal-loads.js",
         JS / "lines.js",
         JS / "boundary-conditions.js"],
        TESTS / "test-edits.js",
    ),
}


def _context():
    try:
        import quickjs
    except ImportError:
        print("quickjs is not installed, so no JavaScript can be executed here.\n"
              "    pip install quickjs\n"
              "The browser suite (frontend/tests/index.html) is unaffected.",
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
