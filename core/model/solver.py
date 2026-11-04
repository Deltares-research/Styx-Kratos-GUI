"""A stage's expert solver settings: what each one is, its default, and when it applies.

The stage panel shows the settings a stage is usually tuned by -- its calculation type,
time integration, convergence criterion, iterations and tolerances (`schemas.Stage`).
Everything else Kratos reads in a stage's `solver_settings` is an *expert* setting, and
is here: the solution strategy and its own parameters, the linear solver and its own,
the automatic time step control, the time scheme of a dynamic stage, and the assembly
switches.

A stage stores only the expert settings the user changed (`Stage.solver_settings`).
Everything else is its default, and the default depends on the stage: on its calculation
type and time integration, and on the choices made above it -- the linear solver's
parameters on which linear solver it is, the time scheme's on which scheme. So a stage
that changes from static to dynamic gets a dynamic stage's defaults for every setting it
did not change itself, and a value the user set stays set.

Only the settings that apply are shown and written, because a setting that does nothing
is a row that misleads: the line search lengths of a stage solved by quasi-Newton, the
Newmark coefficients of a static one. `resolve` decides which apply, and a stored value
of one that does not apply is kept -- switch back, and it is there -- but neither shown
nor written.

Two settings are fixed rather than chosen in some stages, shown with the reason rather
than hidden, since the user would otherwise go looking for them:

*   **the linear solver of the quasi-Newton strategy**, Kratos' Sparse LU. The strategy
    factorises the stiffness matrix once and reuses the factors for every iteration, so
    it builds that solver itself and uses no other
    (`GeoMechanicsQuasiNewtonStrategy`, `geo_mechanics_quasi_newton_strategy.hpp`).
*   **the strategy of a stage with a seepage face**, flow or mechanical, Newton-Raphson
    with seepage, which is what opens and closes the face node by node
    (`seepage_tests`); and with it one attempt per step, as the strategy refuses more.

Rayleigh damping is drawn among a dynamic stage's own settings rather than the expert
ones (`panel`), as it is what such a stage is tuned by.

The catalogue is data rather than code so that the browser can resolve it too: the
property grid has to show a stage's defaults, and which rows apply, as the user edits
it. `javascript` renders the catalogue as `frontend/js/solver-settings.js`, which
`frontend/js/stages.js` reads with the same few lines `resolve` is written in, and
`tests/test_solver_parity.py` holds the two to the same answers.

Every value below is read off Kratos GeoMechanicsApplication 10.4.4 -- its solvers'
`GetDefaultParameters` (`geomechanics_solver.py`), the reference decks
`core.kratos.parameters` copies, and the linear solvers' own defaults, which each one
prints when asked for a setting it does not have.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

QUASI_NEWTON = "quasi_newton"
NEWTON_RAPHSON = "newton_raphson"
LINE_SEARCH = "line_search"
LINEAR = "linear"
SEEPAGE = "newton_raphson_with_seepage"
SPARSE_LU = "LinearSolversApplication.sparse_lu"
SKYLINE_LU = "skyline_lu_factorization"

ITERATIVE = ["amgcl", "bicgstab", "cg"]
"""The iterative linear solvers, which have a tolerance and an iteration count."""
ITERATING = [QUASI_NEWTON, NEWTON_RAPHSON, LINE_SEARCH, SEEPAGE]
"""The strategies that iterate: all but the linear one, which solves once and so has no
convergence criterion, iterations or tolerances, and no failed step to cut."""
FACTORISING = [NEWTON_RAPHSON, LINE_SEARCH, LINEAR, SEEPAGE]
"""The strategies that use the linear solver chosen for them: all but quasi-Newton."""
GMRES = ["gmres", "lgmres", "fgmres"]
"""AMGCL's Krylov methods that restart, and so have a Krylov space dimension."""

MECHANICAL = {"calculation": ["mechanical"]}
FLOW = {"calculation": ["flow"]}
DYNAMIC = {"time_integration": ["dynamic"]}


def _setting(key: str, label: str, group: str, kind: str, default: Any, *,
             when: dict | None = None, options: list | None = None,
             locked: list | None = None, deck: str | None = None, help: str = "",
             panel: str | None = None, **bounds: Any) -> dict:
    """One expert setting.

    `default` is a value, or a list of `{"when": ..., "value": ...}` rules of which the
    first that holds is the default; a rule may name a context value (`"from"`) instead
    of a value. `when` says when the setting applies, as allowed values per context
    name: the stage's `calculation` and `time_integration`, the strategy its model calls
    for (`model_strategy`), and the value of any setting listed before it. `locked` is
    rules like the default's, each with the `reason` a fixed value is shown with. `deck`
    is where it goes in Kratos' `solver_settings`, if not under its own key. `panel`
    `"stage"` draws it among the stage's own settings rather than the expert ones, for a
    setting a stage of its kind is usually tuned by. `bounds` are `integer`, `minimum`
    (inclusive), `above` (exclusive) and `maximum`."""
    out: dict[str, Any] = {"key": key, "label": label, "group": group, "kind": kind,
                           "default": default if isinstance(default, list)
                           else [{"value": default}]}
    if when:
        out["when"] = when
    if options:
        out["options"] = options
    if locked:
        out["locked"] = locked
    out["deck"] = deck or key
    if help:
        out["help"] = help
    if panel:
        out["panel"] = panel
    out.update(bounds)
    return out


SETTINGS: list[dict] = [
    # -- Strategy ---------------------------------------------------------------
    _setting(
        "strategy_type", "Strategy", "Strategy", "select",
        # A mechanical stage is solved by quasi-Newton. A flow stage by what its model
        # calls for -- see `core.model.stages.model_strategy` -- which is also the one
        # strategy a seepage face can have, in a stage of either kind.
        [{"when": FLOW, "from": "model_strategy"}, {"value": QUASI_NEWTON}],
        options=[[QUASI_NEWTON, "Quasi-Newton"], [NEWTON_RAPHSON, "Newton-Raphson"],
                 [LINE_SEARCH, "Newton-Raphson with line search"],
                 [LINEAR, "Linear (one solve)"]],
        locked=[{"when": {"model_strategy": [SEEPAGE]}, "value": SEEPAGE,
                 "label": "Newton-Raphson with seepage",
                 "reason": "A seepage face needs it: it opens and closes the face node "
                           "by node as it iterates."}],
        help="How each step's equations are solved. Quasi-Newton factorises the "
             "stiffness matrix once and updates its inverse from the residuals; "
             "Newton-Raphson rebuilds and factorises it every iteration."),
    _setting("quasi_newton_type", "Update", "Strategy", "select", "lbfgs",
             when={"strategy_type": [QUASI_NEWTON]},
             options=[["lbfgs", "L-BFGS"], ["broyden", "Broyden"]],
             help="How the inverse of the stiffness matrix is updated between "
                  "iterations."),
    _setting("quasi_newton_max_rank", "Stored updates", "Strategy", "number", 10,
             when={"strategy_type": [QUASI_NEWTON]}, integer=True, minimum=1,
             help="How many updates are kept; the oldest is dropped beyond it."),
    _setting("quasi_newton_restart_interval", "Restart interval", "Strategy", "number",
             100, when={"strategy_type": [QUASI_NEWTON]}, integer=True, minimum=1,
             help="Rebuild and refactorise the stiffness matrix every this many "
                  "iterations."),
    _setting("max_line_search_iterations", "Line search iterations", "Strategy",
             "number", 5, when={"strategy_type": [LINE_SEARCH]}, integer=True,
             minimum=1),
    _setting("first_alpha_value", "First step length", "Strategy", "number", 0.5,
             when={"strategy_type": [LINE_SEARCH]}, above=0),
    _setting("second_alpha_value", "Second step length", "Strategy", "number", 1.0,
             when={"strategy_type": [LINE_SEARCH]}, above=0),
    _setting("min_alpha", "Smallest step length", "Strategy", "number", 0.1,
             when={"strategy_type": [LINE_SEARCH]}, above=0),
    _setting("max_alpha", "Largest step length", "Strategy", "number", 2.0,
             when={"strategy_type": [LINE_SEARCH]}, above=0),
    _setting("line_search_tolerance", "Line search tolerance", "Strategy", "number", 0.5,
             when={"strategy_type": [LINE_SEARCH]}, above=0),

    # -- Linear solver ----------------------------------------------------------
    _setting(
        "linear_solver_type", "Linear solver", "Linear solver", "select",
        # The reference decks' own: Skyline LU for the mechanical one, Sparse LU for
        # the flow one (`core.kratos.parameters.SOLVER`, `FLOW_SOLVER`).
        [{"when": FLOW, "value": SPARSE_LU}, {"value": SKYLINE_LU}],
        options=[[SPARSE_LU, "Sparse LU (direct)"], [SKYLINE_LU, "Skyline LU (direct)"],
                 ["amgcl", "AMGCL (iterative)"], ["bicgstab", "BiCGStab (iterative)"],
                 ["cg", "CG (iterative)"]],
        locked=[{"when": {"strategy_type": [QUASI_NEWTON]}, "value": SPARSE_LU,
                 "reason": "The quasi-Newton strategy factorises the stiffness matrix "
                           "once with Sparse LU and reuses it; it uses no other linear "
                           "solver."}],
        deck="linear_solver_settings.solver_type"),
    _setting("linear_solver_scaling", "Scaling", "Linear solver", "check",
             # Both reference decks scale their direct solver; the iterative ones are
             # Kratos' own defaults, unscaled.
             [{"when": {"linear_solver_type": ITERATIVE}, "value": False},
              {"value": True}],
             when={"strategy_type": FACTORISING}, deck="linear_solver_settings.scaling",
             help="Scale the system to a unit diagonal before solving it."),
    _setting("linear_solver_tolerance", "Tolerance", "Linear solver", "number", 1e-6,
             when={"strategy_type": FACTORISING, "linear_solver_type": ITERATIVE},
             above=0, deck="linear_solver_settings.tolerance"),
    _setting("linear_solver_max_iteration", "Max linear iterations", "Linear solver",
             "number",
             [{"when": {"linear_solver_type": ["amgcl"]}, "value": 100}, {"value": 200}],
             when={"strategy_type": FACTORISING, "linear_solver_type": ITERATIVE},
             integer=True, minimum=1, deck="linear_solver_settings.max_iteration"),
    _setting("linear_solver_preconditioner_type", "Preconditioner", "Linear solver",
             "select",
             # CG keeps a symmetric system symmetric only with a symmetric preconditioner.
             [{"when": {"linear_solver_type": ["cg"]}, "value": "diagonal"},
              {"value": "ilu0"}],
             when={"strategy_type": FACTORISING, "linear_solver_type": ["bicgstab", "cg"]},
             options=[["ilu0", "ILU(0)"], ["ilu", "ILU"], ["diagonal", "Diagonal"],
                      ["none", "None"]],
             deck="linear_solver_settings.preconditioner_type",
             # Kratos' own default is none, and an unpreconditioned BiCGStab rarely
             # converges on a stiffness matrix at all.
             help="Kratos' default is none. ILU(0) is what makes BiCGStab converge on "
                  "a stiffness matrix; CG takes the diagonal one, which keeps a symmetric "
                  "system symmetric."),
    _setting("linear_solver_krylov_type", "Krylov method", "Linear solver", "select",
             "gmres", when={"strategy_type": FACTORISING, "linear_solver_type": ["amgcl"]},
             options=[["gmres", "GMRES"], ["lgmres", "LGMRES"], ["fgmres", "FGMRES"],
                      ["bicgstab", "BiCGStab"], ["bicgstabl", "BiCGStab(L)"],
                      ["cg", "CG"], ["idrs", "IDR(s)"]],
             deck="linear_solver_settings.krylov_type"),
    _setting("linear_solver_gmres_krylov_space_dimension", "Krylov space dimension",
             "Linear solver", "number", 100,
             when={"strategy_type": FACTORISING, "linear_solver_type": ["amgcl"],
                   "linear_solver_krylov_type": GMRES},
             integer=True, minimum=1,
             deck="linear_solver_settings.gmres_krylov_space_dimension",
             help="Iterations between restarts of the GMRES method."),
    _setting("linear_solver_smoother_type", "Smoother", "Linear solver", "select",
             "ilu0", when={"strategy_type": FACTORISING, "linear_solver_type": ["amgcl"]},
             options=[["ilu0", "ILU(0)"], ["ilut", "ILUT"], ["iluk", "ILU(k)"],
                      ["spai0", "SPAI-0"], ["spai1", "SPAI-1"],
                      ["damped_jacobi", "Damped Jacobi"],
                      ["gauss_seidel", "Gauss-Seidel"], ["chebyshev", "Chebyshev"]],
             deck="linear_solver_settings.smoother_type"),
    _setting("linear_solver_coarsening_type", "Coarsening", "Linear solver", "select",
             "aggregation",
             when={"strategy_type": FACTORISING, "linear_solver_type": ["amgcl"]},
             options=[["aggregation", "Aggregation"],
                      ["smoothed_aggregation", "Smoothed aggregation"],
                      ["smoothed_aggr_emin", "Smoothed aggregation (energy minimising)"],
                      ["ruge_stuben", "Ruge-Stuben"]],
             deck="linear_solver_settings.coarsening_type"),

    # -- Time step control ------------------------------------------------------
    # Kratos' `GeoMechanicsAnalysis` grows a step that converged in few iterations and
    # cuts one that did not converge, then tries it again. The mechanical defaults are
    # the reference deck's, the flow ones those of the Muskat and seepage decks.
    _setting("min_iterations", "Min iterations", "Time step control", "number", 6,
             when={"strategy_type": ITERATING}, integer=True, minimum=1,
             help="A step that converges in fewer iterations than this is followed by "
                  "a larger one."),
    _setting("number_cycles", "Attempts per step", "Time step control", "number", 5,
             when={"strategy_type": ITERATING}, integer=True, minimum=1,
             locked=[{"when": {"strategy_type": [SEEPAGE]}, "value": 1,
                      "reason": "Kratos' seepage strategy refuses more than one: it "
                                "cannot undo the faces it opened before trying a step "
                                "again."}],
             help="How often a step that does not converge is tried again with a "
                  "smaller step before the stage stops."),
    _setting("reduction_factor", "Step reduction factor", "Time step control", "number",
             [{"when": FLOW, "value": 1.0}, {"value": 0.5}],
             when={"strategy_type": ITERATING}, above=0, maximum=1),
    _setting("minimum_step_fraction", "Smallest step (x duration)", "Time step control",
             "number", 1e-4, when={"strategy_type": ITERATING}, above=0, maximum=1,
             deck="time_stepping.minimum_allowable_value",
             help="A step cut below this fraction of the stage's duration stops the stage "
                  "(Kratos: 'The time step is too small'). Never more than the stage's "
                  "own time step. Kratos' own default."),
    _setting("increase_factor", "Step increase factor", "Time step control", "number",
             # A linear flow stage was always written without one, so it has Kratos'
             # own default, and keeps it.
             [{"when": {**FLOW, "strategy_type": ITERATING}, "value": 1.0},
              {"value": 2.0}],
             minimum=1),
    _setting("max_delta_time_factor", "Largest step (x time step)", "Time step control",
             "number",
             1000.0, minimum=1, deck="time_stepping.max_delta_time_factor",
             help="The largest a step grows to after steps that converged in few "
                  "iterations, as a multiple of the stage's time step."),

    # -- Time integration -------------------------------------------------------
    # A static stage has no time scheme: a static mechanical one is solved by Kratos'
    # `GeoStaticScheme`, and a steady state flow by water pressure elements that have
    # no storage term for a scheme to integrate.
    _setting("scheme_type", "Time scheme", "Time integration", "select", "newmark",
             when=DYNAMIC,
             options=[["newmark", "Newmark"], ["backward_euler", "Backward Euler"]],
             help="In a mechanical stage, Backward Euler integrates the water pressure "
                  "in time without inertia: Kratos' quasi-static U-Pw, the only one it "
                  "builds Backward Euler for (geomechanics_U_Pw_solver.py)."),
    _setting("newmark_beta", "Newmark beta", "Time integration", "number", 0.25,
             when={**MECHANICAL, **DYNAMIC, "scheme_type": ["newmark"]}, above=0),
    _setting("newmark_gamma", "Newmark gamma", "Time integration", "number", 0.5,
             when={**MECHANICAL, **DYNAMIC, "scheme_type": ["newmark"]}, above=0),
    _setting("newmark_theta", "Newmark theta", "Time integration", "number", 0.5,
             when={**DYNAMIC, "scheme_type": ["newmark"]}, above=0, maximum=1,
             help="For the water pressure."),
    # Rayleigh damping is what a dynamic stage is tuned by, so it is drawn among the
    # stage's own settings. Kratos reads it in the Newmark scheme only.
    _setting("rayleigh_m", "Rayleigh mass damping", "Damping", "number", 0.0,
             when={**MECHANICAL, **DYNAMIC, "scheme_type": ["newmark"]}, minimum=0,
             panel="stage",
             help="Rayleigh's alpha: the damping proportional to the mass."),
    _setting("rayleigh_k", "Rayleigh stiffness damping", "Damping", "number", 0.0,
             when={**MECHANICAL, **DYNAMIC, "scheme_type": ["newmark"]}, minimum=0,
             panel="stage",
             help="Rayleigh's beta: the damping proportional to the stiffness."),

    # -- Assembly ---------------------------------------------------------------
    _setting("block_builder", "Block builder", "Assembly", "check", True,
             help="Assemble the whole system and fix its constraints in place, rather "
                  "than eliminating them."),
    _setting("reform_dofs_at_each_step", "Reform DOFs each step", "Assembly", "check",
             [{"when": FLOW, "value": True}, {"value": False}]),
    _setting("compute_reactions", "Compute reactions", "Assembly", "check", True),
    _setting("move_mesh_flag", "Updated mesh", "Assembly", "check", False,
             when=MECHANICAL,
             help="Move the mesh with the displacements, so each step is solved on the "
                  "deformed geometry."),
]

BY_KEY = {setting["key"]: setting for setting in SETTINGS}
GROUPS = list(dict.fromkeys(setting["group"] for setting in SETTINGS))


def _holds(when: Mapping[str, list] | None, context: Mapping[str, Any]) -> bool:
    return all(context.get(name) in allowed for name, allowed in (when or {}).items())


def _rule(rules: list[dict], context: Mapping[str, Any]) -> dict | None:
    for rule in rules:
        if _holds(rule.get("when"), context) and (
                "from" not in rule or context.get(rule["from"]) is not None):
            return rule
    return None


def _value(rule: dict, context: Mapping[str, Any]) -> Any:
    return context[rule["from"]] if "from" in rule else rule["value"]


def resolve(calculation: str, time_integration: str,
            overrides: Mapping[str, Any] | None = None,
            model_strategy: str | None = None) -> list[dict]:
    """The expert settings that apply to a stage, in order, each as `key`, its `value`,
    its `default`, whether the stage `overridden` it, and the reason it is `locked` to
    its value, or `None`.

    `overrides` is the stage's own `solver_settings`; `model_strategy` is the strategy a
    flow stage's model calls for (`core.model.stages.model_strategy`). A setting is
    decided before the ones after it, which is what lets the linear solver's parameters
    depend on which linear solver it is."""
    overrides = overrides or {}
    context: dict[str, Any] = {"calculation": calculation,
                               "time_integration": time_integration,
                               "model_strategy": model_strategy}
    out = []
    for setting in SETTINGS:
        if not _holds(setting.get("when"), context):
            continue
        key = setting["key"]
        lock = _rule(setting.get("locked", []), context)
        default = _value(lock or _rule(setting["default"], context) or {"value": None},
                         context)
        overridden = lock is None and key in overrides
        value = overrides[key] if overridden else default
        context[key] = value
        out.append({"key": key, "value": value, "default": default,
                    "overridden": overridden,
                    "locked": lock["reason"] if lock else None})
    return out


def iterates(rows: list[dict]) -> bool:
    """Whether the strategy of the stage `rows` resolve iterates, and so has a
    convergence criterion, iterations and tolerances."""
    return next(row["value"] for row in rows if row["key"] == "strategy_type") in ITERATING


def label(key: str, value: Any) -> str:
    """What to call a setting's value in front of a user: its option's label, or a
    fixed value's own."""
    setting = BY_KEY[key]
    for option, text in setting.get("options", []):
        if option == value:
            return text
    for lock in setting.get("locked", []):
        if lock["value"] == value and "label" in lock:
            return lock["label"]
    if setting["kind"] == "check":
        return "Yes" if value else "No"
    return f"{value:g}" if isinstance(value, float) else str(value)


def deck_settings(rows: list[dict]) -> dict:
    """The settings `rows` resolve, where Kratos reads them in a stage's
    `solver_settings`: nested where the deck nests them (`time_stepping`,
    `linear_solver_settings`).

    AMGCL is also told to be quiet: its default prints a line per linear solve, and the
    run log is where a user reads what went wrong."""
    out: dict[str, Any] = {}
    for row in rows:
        *path, name = BY_KEY[row["key"]]["deck"].split(".")
        at = out
        for part in path:
            at = at.setdefault(part, {})
        at[name] = _number(row["key"], row["value"])
    if out.get("linear_solver_settings", {}).get("solver_type") == "amgcl":
        out["linear_solver_settings"]["verbosity"] = 0
    return out


def _number(key: str, value: Any) -> Any:
    """A whole number where Kratos reads one (`GetInt` refuses 6.0), a real one where it
    reads that."""
    setting = BY_KEY[key]
    if setting["kind"] != "number":
        return value
    return int(value) if setting.get("integer") else float(value)


def problems(overrides: Mapping[str, Any]) -> list[str]:
    """What is wrong with a stage's `solver_settings`, one sentence each: a setting
    there is no such thing as, or a value it cannot have."""
    out = []
    for key, value in overrides.items():
        setting = BY_KEY.get(key)
        if setting is None:
            out.append(f"there is no solver setting {key!r}: use one of "
                       f"{', '.join(BY_KEY)}")
            continue
        name = f"{setting['label'].lower()} ({key})"
        kind = setting["kind"]
        if kind == "check":
            if not isinstance(value, bool):
                out.append(f"the {name} must be true or false, not {value!r}")
        elif kind == "select":
            allowed = [option for option, _ in setting["options"]]
            if value not in allowed:
                out.append(f"the {name} must be one of {', '.join(allowed)}, not {value!r}")
        elif (isinstance(value, bool) or not isinstance(value, (int, float))
              or not math.isfinite(value)):
            out.append(f"the {name} must be a number, not {value!r}")
        else:
            out.extend(f"the {name} {problem}" for problem in _bounds(setting, value))
    return out


def _bounds(setting: dict, value: float) -> list[str]:
    out = []
    if setting.get("integer") and value != int(value):
        out.append(f"must be a whole number, not {value:g}")
    if "minimum" in setting and value < setting["minimum"]:
        out.append(f"must be at least {setting['minimum']:g}, not {value:g}")
    if "above" in setting and value <= setting["above"]:
        out.append(f"must be more than {setting['above']:g}, not {value:g}")
    if "maximum" in setting and value > setting["maximum"]:
        out.append(f"must be at most {setting['maximum']:g}, not {value:g}")
    return out


def normalised(overrides: Mapping[str, Any]) -> dict[str, Any]:
    """`overrides` with every number the kind Kratos reads -- a whole number for a count,
    a real one otherwise -- so that a stage saved by the browser, which writes 1 for
    1.0, reads back the way it was meant. Assumes `problems` found nothing."""
    return {key: _number(key, value) for key, value in overrides.items()}


def from_deck(solver: Mapping[str, Any]) -> dict[str, Any]:
    """The expert settings a deck's own `solver_settings` block states, as overrides:
    every one it gives that a stage can have. A value no stage can have -- a strategy or
    a linear solver this catalogue does not offer -- is left out rather than refused, as
    the deck still runs as it is (`core.kratos.external_deck`)."""
    out: dict[str, Any] = {}
    for setting in SETTINGS:
        at: Any = solver
        for part in setting["deck"].split("."):
            at = at.get(part) if isinstance(at, Mapping) else None
        if at is None:
            continue
        if setting["kind"] == "select" and isinstance(at, str):
            at = at.lower() if at.lower() in {o for o, _ in setting["options"]} else at
        if not problems({setting["key"]: at}):
            out[setting["key"]] = _number(setting["key"], at)
    return out


JAVASCRIPT_HEADER = '''/* Generated from core/model/solver.py -- the expert solver settings of a stage: what
   each one is, its default, and when it applies. The browser resolves them with
   App.Stages.solverRows, written the way `core.model.solver.resolve` is, and
   tests/test_solver_parity.py holds the two to the same answers.

   Not hand-edited. `python tests/test_solver_parity.py --write` rebuilds it.
*/
var App = window.App || {};
App.SOLVER_SETTINGS = '''


def javascript() -> str:
    """`frontend/js/solver-settings.js`: the catalogue, for the browser."""
    return JAVASCRIPT_HEADER + json.dumps(SETTINGS, indent=2) + ";\n"
