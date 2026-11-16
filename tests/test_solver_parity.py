"""The expert solver settings, resolved twice, held to the same answers.

`core.model.solver` is the catalogue of a stage's expert settings and the rule that
decides which apply, and at what default. The browser resolves them too -- the stage
panel shows them as the user edits a stage -- so the catalogue goes to it as data,
`frontend/js/solver-settings.js`, and `App.Stages.resolveSolver` reads it with the same
few lines `solver.resolve` is written in. Two implementations of one rule drift unless
something says they agree; this module is that something, as `test_stage_parity` is
for the stage tree.

It owns two generated files: the catalogue the browser runs on, and
`frontend/tests/fixtures/solver-cases.js`, the answers `solver.resolve` gives for a
set of stages, which `frontend/tests/test-stages.js` compares the JavaScript to.

    python tests/test_solver_parity.py --write

rewrites both after a deliberate change.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.model import solver  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "frontend" / "js" / "solver-settings.js"
FIXTURE = ROOT / "frontend" / "tests" / "fixtures" / "solver-cases.js"

HEADER = '''/* Generated fixture -- what `core.model.solver.resolve` gives for a set of stages,
   which App.Stages.resolveSolver is held to (frontend/tests/test-stages.js).

   Not hand-edited. `python tests/test_solver_parity.py --write` rebuilds it.
*/
window.SOLVER_FIXTURE =
'''

# Every branch the catalogue has: each calculation type and time integration, each
# strategy, each linear solver and the Krylov methods that do and do not restart, both
# time schemes, the two fixed values and the flow strategies a model can call for --
# and overrides of settings that do not apply, which are kept but not shown.
CONTEXTS = [("mechanical", "static", None), ("mechanical", "dynamic", None),
            ("flow", "static", "linear"), ("flow", "dynamic", "newton_raphson"),
            ("flow", "static", "newton_raphson_with_seepage"),
            ("mechanical", "dynamic", "newton_raphson_with_seepage")]
OVERRIDES = [
    {},
    {"strategy_type": "newton_raphson"},
    {"strategy_type": "line_search", "min_alpha": 0.2},
    {"strategy_type": "linear", "min_iterations": 3},
    {"strategy_type": "quasi_newton", "quasi_newton_type": "broyden",
     "linear_solver_type": "amgcl"},
    {"strategy_type": "newton_raphson", "linear_solver_type": "amgcl",
     "linear_solver_krylov_type": "bicgstab"},
    {"strategy_type": "newton_raphson", "linear_solver_type": "amgcl",
     "linear_solver_krylov_type": "lgmres", "linear_solver_tolerance": 1e-8},
    {"strategy_type": "newton_raphson", "linear_solver_type": "bicgstab",
     "linear_solver_scaling": True},
    {"strategy_type": "newton_raphson", "linear_solver_type": "cg",
     "minimum_step_fraction": 0.01},
    {"scheme_type": "backward_euler", "newmark_theta": 1.0, "number_cycles": 3},
    {"move_mesh_flag": True, "rayleigh_k": 0.01},
]


def build() -> dict:
    return {"cases": [
        {"calculation": calculation, "time_integration": time_integration,
         "model_strategy": model_strategy, "overrides": overrides,
         "rows": solver.resolve(calculation, time_integration, overrides, model_strategy)}
        for calculation, time_integration, model_strategy in CONTEXTS
        for overrides in OVERRIDES
    ]}


def render(document: dict) -> str:
    return HEADER + json.dumps(document, indent=2) + ";\n"


def stored() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    marker = "window.SOLVER_FIXTURE ="
    return json.loads(text[text.index(marker) + len(marker):].strip().rstrip(";"))


def test_the_catalogue_the_browser_runs_on_is_the_servers():
    assert CATALOGUE.read_text(encoding="utf-8") == solver.javascript(), (
        "frontend/js/solver-settings.js is out of date. Rerun\n"
        "    python tests/test_solver_parity.py --write")


def test_the_fixture_on_disk_is_what_the_server_resolves():
    assert stored() == build(), (
        "frontend/tests/fixtures/solver-cases.js is out of date. Rerun\n"
        "    python tests/test_solver_parity.py --write")


def test_every_setting_is_reached_by_some_case():
    """A fixture that never shows a setting cannot say the two sides agree on it."""
    shown = {row["key"] for case in stored()["cases"] for row in case["rows"]}
    assert shown == set(solver.BY_KEY)


def test_every_override_in_the_fixture_is_one_a_stage_can_store():
    for overrides in OVERRIDES:
        assert solver.problems(overrides) == [], overrides


if __name__ == "__main__":
    if "--write" in sys.argv:
        CATALOGUE.write_text(solver.javascript(), encoding="utf-8")
        FIXTURE.write_text(render(build()), encoding="utf-8")
        print(f"wrote {CATALOGUE}\nwrote {FIXTURE}")
    else:
        print(__doc__)
