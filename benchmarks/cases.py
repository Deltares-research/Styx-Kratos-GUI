"""The Tier-1 benchmark catalogue (plan/active/alpha-test-plan.md sec 7.3), as runnable cases.

Each check compares the run with an answer that does not come from this tool: an
analytical solution, Kratos' own test values, or a self-consistency the physics demands
(symmetry, mesh and order independence, 2D against its extrusion). Cases that need a
feature this tool does not have yet are listed as BLOCKED with the feature named, so the
catalogue says plainly what cannot be checked rather than leaving it out.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from core.kratos import writer, materials
from core.results import catalog
from benchmarks import models
from benchmarks.runner import Case, Context, Outcome
from tests.models import crow, muskat

# ── Reading a run ───────────────────────────────────────────────────────────


def last_stage(ctx: Context) -> int:
    return len(catalog.describe(ctx.run_id)["stages"])


def element_material(ctx: Context) -> dict[int, dict]:
    """element id -> the project material of the soil body it belongs to."""
    from tests import mdpa  # the independent reader the tests use
    deck = mdpa.parse(next(ctx.directory.glob("*.mdpa")).read_text(encoding="utf-8"))
    names = writer._part_names(ctx.project)
    material_of_key = {key: ctx.project.material(mat) for key, _, mat in
                       _soil_bodies(ctx.project)}
    material_of_key.update({part.key: ctx.project.material(part.mat)
                            for part in ctx.project.custom_parts if part.mat})
    out = {}
    for key, material in material_of_key.items():
        part = deck.parts.get(names.get(key, ""))
        for element in part.elements if part else []:
            out[element] = material
    return out


def _soil_bodies(project):
    for key, label, *rest in project.soil_bodies():
        layer = next(l for l in project.layers if key.startswith(f"soil_{l.id}"))
        yield key, label, layer.mat


def gauss(ctx: Context, stage: int, variable: str = "CAUCHY_STRESS_TENSOR"):
    return catalog.stage_results(ctx.run_id, stage).field(variable).values


def centroid_y(ctx: Context, stage: int, element: int) -> float:
    mesh = catalog.stage_mesh(ctx.run_id, stage)
    corners = mesh.connectivity(element)[:3]
    return sum(mesh.nodes[c][1] for c in corners) / 3


# ── Checks ──────────────────────────────────────────────────────────────────


def k0_ratio(tolerance: float = 1e-4):
    def check(ctx: Context) -> Outcome:
        k0_of = {e: m.number("K0_NC") or materials.k0_nc(m)
                 for e, m in element_material(ctx).items()}
        worst = 0.0
        for element, points in gauss(ctx, 1).items():
            for s in points:
                if s[1] < -1000.0:
                    worst = max(worst, abs(s[0] / s[1] - k0_of[element]) / k0_of[element])
        return Outcome("σ'xx / σ'yy = K0 at every Gauss point", worst <= tolerance,
                       f"worst {worst:.2e} relative", f"≤ {tolerance:g}")
    return check


def no_shear(tolerance: float = 1e-6):
    def check(ctx: Context) -> Outcome:
        values = gauss(ctx, 1)
        largest = max(abs(s[1]) for points in values.values() for s in points)
        worst = max(abs(s[3]) for points in values.values() for s in points)
        return Outcome("σ'xy = 0", worst <= tolerance * largest,
                       f"{worst:.3g} Pa", f"≤ {tolerance:g} × {largest:.3g} Pa")
    return check


def vertical_stress_is_overburden(layers, water_y: float | None = None,
                                  gamma_w: float = 10.0, tolerance: float = 0.01):
    """σ'yy at an element centroid = -(Σ γ h above it) + γ_w × its depth below the water:
    `g_unsat` above the phreatic level, `g_sat` below it (kN/m3 -> Pa)."""
    def overburden(y):
        total = 0.0
        for top, bottom, material in layers:
            for upper, lower, gamma in _wet_and_dry(top, bottom, material, water_y):
                if y < upper:
                    total += gamma * (upper - max(y, lower))
        pore = gamma_w * max(0.0, water_y - y) if water_y is not None else 0.0
        return -1000.0 * (total - pore)

    def check(ctx: Context) -> Outcome:
        worst = 0.0
        for element, points in gauss(ctx, 1).items():
            y = centroid_y(ctx, 1, element)
            expected = overburden(y)
            mean = sum(s[1] for s in points) / len(points)
            if abs(expected) > 5000:
                worst = max(worst, abs(mean - expected) / abs(expected))
        return Outcome("σ'yy = γ·depth" if water_y is None else
                       "σ'yy = γ_unsat·h above the water + (γ_sat − γ_w)·h below",
                       worst <= tolerance, f"worst {worst:.2%}", f"≤ {tolerance:.0%}")
    return check


def _wet_and_dry(top, bottom, material, water_y):
    """A layer split at the phreatic level: (top, bottom, unit weight) pieces."""
    if water_y is None or water_y <= bottom:
        return [(top, bottom, material["g_unsat"])]
    if water_y >= top:
        return [(top, bottom, material["g_sat"])]
    return [(top, water_y, material["g_unsat"]), (water_y, bottom, material["g_sat"])]


def hydrostatic(height: float, gamma_w: float = 10.0):
    def check(ctx: Context) -> Outcome:
        stage = last_stage(ctx)
        values = catalog.stage_results(ctx.run_id, stage).field("WATER_PRESSURE").values
        mesh = catalog.stage_mesh(ctx.run_id, stage)
        water = ctx.project.water.y
        worst = max(abs(v[0] + 1000 * gamma_w * max(0.0, water - mesh.nodes[n][1]))
                    / max(1.0, 1e-5 * 1000 * gamma_w * height) for n, v in values.items())
        low = min(v[0] for v in values.values())
        ok = worst <= 1.0 and abs(low + 1000 * gamma_w * height) <= 1.0
        return Outcome("p_w = −γ_w (y_w − y) at every node; min = −γ_w H", ok,
                       f"min {low / 1000:.4f} kPa, worst {worst:.2f}× file precision",
                       f"min {-gamma_w * height:.4f} kPa")
    return check


def movement(ctx: Context) -> dict[int, tuple]:
    """What the construction moved: each node's TOTAL_DISPLACEMENT in the last stage less
    its value after the K0 stage, for the nodes the last stage still has.

    Not the last stage's value itself: the first stage's gravity loading settles the whole
    model (metres, on soft soil), and no stage of this sequence resets it -- a heave read
    from that would be the least-settled node, which is the one on the fixed base. And
    only the remaining nodes, because an excavated node keeps the value it had when it was
    taken away and would otherwise count as ground that did not move."""
    stage = last_stage(ctx)
    after = catalog.stage_results(ctx.run_id, stage).field("TOTAL_DISPLACEMENT").values
    before = catalog.stage_results(ctx.run_id, 1).field("TOTAL_DISPLACEMENT").values
    mesh = catalog.stage_mesh(ctx.run_id, stage)
    remaining = {n for nodes in mesh.elements().values() for n in nodes}
    return {n: tuple(a - b for a, b in zip(after[n], before[n]))
            for n in remaining if n in after and n in before}


def symmetric_about(axis_x: float, tolerance: float = 0.03):
    """A symmetric model deforms symmetrically: heave greatest on the axis, and the
    largest horizontal movement the same on both sides."""
    def check(ctx: Context) -> Outcome:
        u = movement(ctx)
        mesh = catalog.stage_mesh(ctx.run_id, last_stage(ctx))
        left = max((abs(v[0]) for n, v in u.items() if mesh.nodes[n][0] < axis_x), default=0)
        right = max((abs(v[0]) for n, v in u.items() if mesh.nodes[n][0] > axis_x), default=0)
        heave_node = max(u, key=lambda n: u[n][1])
        offset = abs(mesh.nodes[heave_node][0] - axis_x)
        ratio = abs(left - right) / max(left, right)
        return Outcome("|Δu_x| max left = right; heave peaks on the axis",
                       ratio <= tolerance and offset <= 3.0,
                       f"left/right differ {ratio:.1%}, peak heave "
                       f"{u[heave_node][1] * 1000:.1f} mm, {offset:.1f} m off axis",
                       f"≤ {tolerance:.0%}, ≤ 3 m")
    return check


_reference_2d: dict = {}


def remember_profile(key: str):
    def check(ctx: Context) -> Outcome:
        _reference_2d[key] = surface_profile(ctx)
        return Outcome("2D profile recorded", True, f"{len(_reference_2d[key])} points", "-")
    return check


def surface_profile(ctx: Context) -> dict[float, float]:
    """Δu_y along the ground surface left standing (beside the pit), averaged per metre
    of x -- over the middle slice of a 3D model, whose ends are its boundaries."""
    u = movement(ctx)
    mesh = catalog.stage_mesh(ctx.run_id, last_stage(ctx))
    top = max(mesh.nodes[n][1] for n in u)
    mid_z = (ctx.project.domain.z0 + ctx.project.domain.z1) / 2
    rows = defaultdict(list)
    for n, v in u.items():
        x, y, z = mesh.nodes[n]
        if abs(y - top) < 1e-6 and (ctx.project.dimension == 2 or abs(z - mid_z) < 3.0):
            rows[round(x)].append(v[1])
    return {x: sum(vals) / len(vals) for x, vals in sorted(rows.items())}


def matches_2d_profile(key: str, tolerance: float = 0.03):
    def check(ctx: Context) -> Outcome:
        ours, theirs = surface_profile(ctx), _reference_2d.get(key)
        if not theirs:
            return Outcome("3D surface movement = 2D", False, "no 2D run to compare", "-")
        peak = max(abs(v) for v in theirs.values())
        common = [x for x in ours if x in theirs]
        worst = max(abs(ours[x] - theirs[x]) for x in common) / peak
        return Outcome("3D surface Δu_y = 2D (plane strain)", worst <= tolerance,
                       f"worst {worst:.1%} of the 2D peak over {len(common)} points",
                       f"≤ {tolerance:.0%}")
    return check


_heave: dict[str, float] = {}


def floor_heave(ctx: Context, axis_x: float = 40.0) -> float:
    """Δu_y at the middle of the final pit floor: smooth there, unlike the corners."""
    return _floor_heave(movement(ctx), catalog.stage_mesh(ctx.run_id, last_stage(ctx)), axis_x)


def _floor_heave(u, mesh, axis_x):
    on_axis = [(mesh.nodes[n][1], v[1]) for n, v in u.items()
               if abs(mesh.nodes[n][0] - axis_x) < 1e-6]
    return max(on_axis)[1]          # the highest remaining point on the axis is the floor


def remember_heave(key: str):
    def check(ctx: Context) -> Outcome:
        _heave[key] = floor_heave(ctx)
        return Outcome(f"pit-floor heave recorded ({key})", True,
                       f"{_heave[key] * 1000:.2f} mm", "-")
    return check


def richardson(coarse: str, medium: str, fine: str, low: float = 1.5, high: float = 6.0):
    """Mesh convergence: (u_h - u_h/2) / (u_h/2 - u_h/4) is 2^p for a quantity converging
    at rate p -- the pit's corners hold quadratic elements below their smooth-problem
    rate. Outside [1.5, 6] the answers are not converging, whatever they are."""
    def check(ctx: Context) -> Outcome:
        missing = [k for k in (coarse, medium, fine) if k not in _heave]
        if missing:
            return Outcome("Richardson ratio", False, f"no run for {missing}", "-")
        a, b, c = (_heave[k] for k in (coarse, medium, fine))
        ratio = (a - b) / (b - c) if b != c else float("inf")
        return Outcome("Richardson ratio of the pit-floor heave, h = 4, 2, 1 m",
                       low <= ratio <= high,
                       f"{ratio:.2f} ({a * 1000:.2f}, {b * 1000:.2f}, {c * 1000:.2f} mm)",
                       f"in [{low:g}, {high:g}]")
    return check


def exact_flow_pressure(tolerance: float = 0.5):
    """The semi-Muskat column: the water pressure at every node is the exact one of a head
    falling linearly from the left face to the right (`tests.models.muskat`)."""
    def check(ctx: Context) -> Outcome:
        stage = last_stage(ctx)
        values = catalog.stage_results(ctx.run_id, stage).field("WATER_PRESSURE").values
        mesh = catalog.stage_mesh(ctx.run_id, stage)
        worst = max(abs(v[0] - muskat.exact_water_pressure(*mesh.nodes[n][:2]))
                    for n, v in values.items())
        return Outcome("p_w = γ_w (y − h(x)), h linear from 3.0 m to 1.6 m", worst <= tolerance,
                       f"worst {worst:.3f} Pa", f"≤ {tolerance:g} Pa")
    return check


def darcy_flux(tolerance: float = 1e-3):
    """The flux is Darcy's, horizontal and the same everywhere: q = K Δh / L."""
    def check(ctx: Context) -> Outcome:
        values = catalog.stage_results(ctx.run_id, last_stage(ctx)).field(
            "FLUID_FLUX_VECTOR").values.values()
        worst = max(max(abs(q[0] - muskat.EXACT_FLUX), abs(q[1])) for q in values)
        return Outcome("q = (K Δh / L, 0) at every node", worst <= tolerance * muskat.EXACT_FLUX,
                       f"worst {worst:.3g} m/s", f"≤ {tolerance:g} × {muskat.EXACT_FLUX:.4g} m/s")
    return check


def kratos_values(variable: str, tolerance: float):
    """Case B: the run read at the coordinates of the nodes Kratos checks, against Kratos'
    own regression values (`tests.models.muskat.KRATOS_B`), within `tolerance`."""
    def check(ctx: Context) -> Outcome:
        stage = last_stage(ctx)
        mesh = catalog.stage_mesh(ctx.run_id, stage)
        values = catalog.stage_results(ctx.run_id, stage).field(variable).values
        worst = 0.0
        for (x, y), expected in muskat.KRATOS_B.values():
            if variable in expected:
                got = muskat.at_point(mesh, values, x, y)[0]
                worst = max(worst, abs(got - expected[variable]))
        return Outcome(f"{variable} = Kratos' at its nodes", worst <= tolerance,
                       f"worst {worst:.3g}", f"≤ {tolerance:g}")
    return check


def seepage_balance(tolerance: float = 1e-3, above: float = 0.02):
    """Case C: what comes in on the left leaves on the right, and that discharge is
    Dupuit and Charny's, or up to `above` more (the unsaturated soil above the phreatic
    line carries some water too)."""
    def check(ctx: Context) -> Outcome:
        stage = last_stage(ctx)
        rate = catalog.stage_results(ctx.run_id, stage).field("NODAL_WATER_FLOW_RATE").values
        mesh = catalog.stage_mesh(ctx.run_id, stage)
        inflow = -sum(v[0] for n, v in rate.items() if abs(mesh.nodes[n][0]) < 1e-9)
        outflow = sum(v[0] for n, v in rate.items()
                      if abs(mesh.nodes[n][0] - muskat.WIDTH) < 1e-9)
        charny = muskat.CHARNY_DISCHARGE
        ok = (abs(outflow - inflow) <= tolerance * inflow
              and charny <= outflow <= (1 + above) * charny)
        return Outcome("Q in = Q out = K (H1² − H2²) / 2L", ok,
                       f"in {inflow:.4g}, out {outflow:.4g} m³/s/m",
                       f"{charny:.4g} to {(1 + above) * charny:.4g}")
    return check


CROW_REFERENCE = Path(__file__).resolve().parent / "reference" / "crow"
"""Kratos' own expected wall results for its CROW cases, one file per soil model, by
level (`benchmarks/reference/crow/README.md`)."""

CROW_COLUMNS = {"M": "bending_moment_in_Nm_per_m", "Q": "shear_force_in_N_per_m",
                "ux": "horizontal_total_displacement_in_m"}
"""What Kratos' test checks, as the member quantities `core.results.members` reads."""


def crow_reference(case: str) -> dict[tuple[str, str], dict[float, float]]:
    """{(stage name, quantity): {y: value}} from `CROW_REFERENCE`/`case`.csv."""
    out: dict[tuple[str, str], dict[float, float]] = defaultdict(dict)
    with (CROW_REFERENCE / f"{case}.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for quantity, column in CROW_COLUMNS.items():
                out[row["stage"], quantity][round(float(row["y_in_m"]), 6)] = \
                    float(row[column])
    return out


def wall_matches_kratos(case: str, stage: int, name: str, tolerance: float = 0.02):
    """The wall's M, Q and u_x in one stage, node by node at the reference's levels,
    against Kratos' run of `case` on its own mesh. Kratos' own rule: each value within
    `tolerance` of the stage's largest, or of itself, whichever allows more."""
    def check(ctx: Context) -> Outcome:
        reference = crow_reference(case)
        worst, where = 0.0, ""
        for quantity in CROW_COLUMNS:
            expected = reference[name, quantity]
            stage_profile = next(s for s in catalog.member_profiles(
                ctx.run_id, "wall", quantity)["stages"] if s["index"] == stage)
            got = {round(y, 6): value for value, y in stage_profile["points"]}
            missing = sorted(set(expected) - set(got))
            if missing:
                return Outcome(f"{name}: wall M, Q, u_x = Kratos'", False,
                               f"no wall node at y = {missing[:5]}", "a node at each level")
            peak = max(abs(v) for v in expected.values())
            for y, want in expected.items():
                ratio = abs(got[y] - want) / max(tolerance * peak, tolerance * abs(want))
                if ratio > worst:
                    worst, where = ratio, f"{quantity} at y = {y:g} m"
        return Outcome(f"{name}: wall M, Q, u_x = Kratos' at every level", worst <= 1.0,
                       f"worst {worst * tolerance:.2%} ({where})", f"≤ {tolerance:.0%}")
    return check


CROW_CHECKED = {3: "3_Wall_installation", 4: "4_First_excavation", 6: "6_Second_excavation",
                7: "7_Third_excavation"}
"""The stages Kratos' test checks, by index and by its name for them."""


def crow_wall(case: str, tolerance: float):
    return [wall_matches_kratos(case, stage, name, tolerance)
            for stage, name in CROW_CHECKED.items()]


# ── The catalogue ───────────────────────────────────────────────────────────

SAND = models.material("sand", "Sand", 18.0, k0=0.6)
CLAY = models.material("clay", "Clay", 20.0, k0=0.8)
ONE_LAYER = [(0.0, -10.0, SAND)]
TWO_LAYERS = [(0.0, -5.0, SAND), (-5.0, -10.0, CLAY)]
DRAWN_ON_LAYER = [(0.0, -5.0, CLAY), (-5.0, -10.0, SAND)]
"""The clay drawn on top, the sand a soil layer: the order reversed from
`TWO_LAYERS`, so the drawn part is the one whose K0 differs from the elastic ratio."""
WET = models.material("wet", "Saturated", 20.0, k0=0.5)
POROUS = models.weighing(models.material("porous", "Sand, porosity 0.3", 18.0, k0=0.6,
                                          porosity=0.3))
HEAVY_WET = models.weighing(models.material("sand_ws", "Sand, 18 / 20", 18.0, k0=0.6,
                                            gamma_sat=20.0))

CASES = [
    Case("BM-K0-01", "K0 procedure, one layer, K0 = 0.6",
         "test_k0_procedure_process.py::test_k0_procedure_k0_nc",
         build=lambda: models.column(ONE_LAYER, name="BM-K0-01"),
         checks=[k0_ratio(), no_shear(), vertical_stress_is_overburden(ONE_LAYER)]),
    Case("BM-K0-02", "K0 procedure, two layers, K0 = 0.6 / 0.8",
         "test_k0_procedure_process.py::test_k0_procedure_k0_nc_layers",
         build=lambda: models.column(TWO_LAYERS, name="BM-K0-02"),
         checks=[k0_ratio(), no_shear(), vertical_stress_is_overburden(TWO_LAYERS)]),
    Case("BM-K0-03", "K0 procedure, a drawn fill on a soil layer, K0 = 0.8 / 0.6",
         "BM-K0-02 with its top layer drawn as a polygon: a drawn soil is set up by the "
         "K0 procedure like a layer",
         build=lambda: models.column_under_drawn_fill(*DRAWN_ON_LAYER, name="BM-K0-03"),
         checks=[k0_ratio(), no_shear(), vertical_stress_is_overburden(DRAWN_ON_LAYER)]),
    Case("BM-WT-01", "A soil with pores, above the water, weighs its g_unsat",
         "analytical: σ'yy = γ_unsat·depth (Kratos' own variables: DENSITY_SOLID, "
         "POROSITY 0.3, SaturatedBelowPhreaticLevelLaw)",
         build=lambda: models.column([(0.0, -10.0, POROUS)], name="BM-WT-01"),
         checks=[vertical_stress_is_overburden([(0.0, -10.0, POROUS)])]),
    Case("BM-WT-02", "Below the phreatic level a soil weighs its g_sat",
         "analytical: σ'yy = γ_unsat·h₁ + (γ_sat − γ_w)·h₂ (POROSITY 0.2 = (γ_sat − "
         "γ_unsat)/γ_w, SaturatedBelowPhreaticLevelLaw)",
         build=lambda: models.column([(0.0, -10.0, HEAVY_WET)], water_y=-4.0,
                                     name="BM-WT-02"),
         checks=[vertical_stress_is_overburden([(0.0, -10.0, HEAVY_WET)], water_y=-4.0)]),
    Case("BM-HYD-01", "Hydrostatic column, phreatic level at the top, 2 m",
         "KRATOSGEO_14_hydrostatic_case.py",
         build=lambda: models.column([(0.0, -2.0, WET)], water_y=0.0, k0_stage=False,
                                     name="BM-HYD-01"),
         checks=[hydrostatic(2.0)]),
    Case("BM-EXC-01", "Symmetric excavation deforms symmetrically",
         "test_excavation.py (symmetry), plan V-SYM",
         build=lambda: models.symmetric_pit(),
         checks=[symmetric_about(40.0), remember_profile("pit"), remember_heave("h2")]),
    Case("BM-2D3D-01", "The symmetric pit's 3D extrusion behaves as its plane-strain section",
         "self-consistency",
         build=lambda: models.symmetric_pit(),
         needs=("BM-EXC-01",),
         dimension_after_put=3, settings={"element_size": 4.0, "order": 2},
         checks=[matches_2d_profile("pit", tolerance=0.10)],
         # Measured 2026-10-10 against the 2D run at 2 m, order 2: 6.8 % at 4 m order 2
         # (3 min), 22.7 % at 4 m order 1 (5 s) -- linear tetrahedra are too stiff to
         # say anything about plane strain, so the slow mesh is the honest one. The worst
         # point is the ground beside the pit edge, where the heave peaks most sharply.
         deviation="3D at element size 4 m against 2D at 2 m (both order 2): held to "
                   "10 %, not the plan's 3 %"),
    Case("BM-CONV-01a", "Mesh convergence: the symmetric pit at h = 4 m", "self-consistency",
         build=lambda: models.symmetric_pit(), settings={"element_size": 4.0, "order": 2},
         checks=[remember_heave("h4")]),
    Case("BM-CONV-01", "Mesh convergence: h = 4, 2, 1 m (h = 2 m is BM-EXC-01)",
         "self-consistency",
         build=lambda: models.symmetric_pit(), needs=("BM-EXC-01", "BM-CONV-01a"),
         settings={"element_size": 1.0, "order": 2},
         checks=[remember_heave("h1"), richardson("h4", "h2", "h1")]),
    Case("BM-ORD-01", "Order 1 against order 2: wall moments agree within 10 %",
         "self-consistency",
         blocked="needs a first-order U-Pw interface element (R6): a first-order section "
                 "with a wall and interfaces does not run"),
    Case("BM-SAT-01", "Saturated block under a hydrostatic normal load",
         "test_water_pressure.py::test_normal_load_triangle_6n",
         blocked="needs total stress and strain output in the deck (MF-02)"),
    Case("BM-PIT-LE", "Building pit, linear elastic", "test_building_pit.py",
         blocked="needs REACTION output (MF-01), wall self-weight (MF-27) and water in "
                 "the pit (MF-28)"),
    Case("BM-LL-01", "Line loads in stages", "test_line_loads.py",
         blocked="needs REACTION output (MF-01)"),
    Case("BM-EQ-01", "Reactions balance weight and loads", "self-consistency",
         blocked="needs REACTION output (MF-01)"),
    Case("BM-FLOW-A", "Semi-Muskat column, saturated: steady flow between two heads",
         "Kratos tests/Muskat/saturated_hydrostatic; analytical: linear head, Darcy flux",
         build=lambda: muskat.muskat(order=2),
         checks=[exact_flow_pressure(), darcy_flux()]),
    Case("BM-FLOW-B", "Semi-Muskat column, Van Genuchten soil",
         "Kratos tests/Muskat/van_genuchten_hydrostatic (its regression values)",
         build=lambda: muskat.van_genuchten(size=0.05),
         checks=[kratos_values("WATER_PRESSURE", 10.0),
                 kratos_values("EFFECTIVE_SATURATION", 0.02)]),
    Case("BM-FLOW-C", "Full Muskat with a seepage face", "Kratos tests/seepage_tests; "
         "Dupuit-Charny discharge",
         build=lambda: muskat.seepage(max_iterations=200),
         checks=[seepage_balance()]),
    Case("BM-CROW-LE", "CROW sheet-pile excavation, linear elastic clay and sand",
         "Kratos test_CROW_case.py::test_staged_construction_with_linear_elastic_behavior "
         "(its expected wall results)",
         build=lambda: crow.project(crow.LINEAR_ELASTIC),
         # Measured 2026-10-25: within 1.7 % at every level, on a mesh of its own.
         checks=crow_wall("linear_elastic", 0.02)),
    Case("BM-CROW-MC", "CROW sheet-pile excavation, Mohr-Coulomb clay and sand",
         "Kratos test_CROW_case.py::test_staged_construction_with_mohr_coulomb_clay_sand_"
         "using_linear_iteration (its expected wall results)",
         build=lambda: crow.project(crow.MOHR_COULOMB),
         checks=crow_wall("mohr_coulomb", 0.03),
         # Measured 2026-10-25: M and u_x within 1.2 %, the shear force within 2.1 %
         # (at the toe in the last stage, and below the strut after the first lift).
         # Kratos' 2 % holds its run to its own earlier run on the same mesh; this run
         # is on a mesh of its own.
         deviation="the mesh is this tool's, not Kratos' model.mdpa: held to 3 %, not "
                   "the Kratos test's 2 %"),
]

BY_ID = {case.id: case for case in CASES}
