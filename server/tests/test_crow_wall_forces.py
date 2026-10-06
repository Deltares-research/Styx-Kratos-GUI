"""The wall this model computes, against the CROW case Kratos is validated on.

This is the only test in the repository that says the numbers are *right* rather than
merely unchanged. Everything else about CROW compares structure -- that the deck has the
parts, the materials and the stages the reference deck has (`test_crow_reference.py`).
A deck can be structurally perfect and still bend the wall the wrong way.

**Where the expected values come from.** Kratos' GeoMechanicsApplication carries the CROW
validation case, and beside it, per stage, a CSV of the bending moment, shear force,
normal force and horizontal displacement along the sheet pile. `make_crow_fixture.py`
re-keyed those from the reference mesh's node ids to **y along the wall** and committed
them as `fixtures/crow_run/expected_wall/<stage>.csv`.

**How they are compared.** Our mesh is not the reference mesh -- different node
numbering, different node positions, 39 nodes against 53 -- so each of our nodes is
compared with the reference curve *interpolated at that node's y*, and the tolerance is
Kratos' own rule from `test_helper.calculate_delta`:

    delta = max(0.02 * max|expected over the whole curve|, 0.02 * |expected|)

The absolute floor is what keeps a value that passes through zero from demanding
impossible relative accuracy. This is exactly what `test_CROW_case_generated_mesh.py`
does for the STEM-generated mesh; the difference is that this runs without Kratos, in a
second, against a frozen run.

**Units are SI on both sides** -- N*m/m, N/m, m -- and nothing is converted. This is the
one place in the project where the raw deck units are the right units: `KILO` belongs to
the field catalogue a user reads, not to a comparison between two solver outputs.

**Shear force is compared in two parts, and the split is measured rather than chosen.**
The shear diagram jumps where a distributed load starts or stops -- the ground surface
and each excavation level -- and interpolating the reference curve *across* a jump, at a
node our mesh happens to place inside it, does not produce a meaningful expected value.
Away from those levels shear is held to the same 2 % rule as everything else. Within one
or two elements of one, it is held to a looser bound that records what the difference
actually is today.

What was measured first (plan/crow-regression-test-plan.md, appendix): moment and
displacement agree at *every* node of all four stages, and every shear disagreement sits
within 0.75 m of a load discontinuity -- 0.75 m being two elements at this mesh density.
Moment is the integral of shear, so a moment curve that agrees everywhere bounds the
error in its derivative: what is left is a coarser mesh differentiating an almost
identical moment curve, not a different model. The strut at -1.5 m jumps the shear harder
than anything else in the last stage, and needs no exclusion at all, because both meshes
put a node exactly on it.
"""

from __future__ import annotations

import csv

import pytest

from tests import crow_run, mdpa

RELATIVE_TOLERANCE = 0.02
"""Kratos' own, from `test_CROW_case_generated_mesh.py`."""

DISCONTINUITY_BAND = 0.8
"""How far from a jump in the shear diagram a node has to be before it is held to the
2 % rule. Two elements at this mesh density (0.375 m near the top, so 0.75 m), which is
exactly how far the disagreement reaches -- see the module docstring. Widening this
further would start excluding the wall rather than the jumps, which is what
`compare`'s coverage assertion is there to catch."""

NEAR_JUMP_TOLERANCE = 0.12
"""What a node *inside* the band is held to instead, as a fraction of the largest
expected shear in that stage. The measured worst today is 9.3 %, at the ground surface in
stage 3; this is a regression bound with a little headroom, not a claim that 12 % is
acceptable engineering agreement."""

SHEAR_DISCONTINUITIES = [0.0, -2.0, -5.0, -8.0]
"""The ground surface, where the surcharge stops, and the three excavation levels. The
strut at -1.5 m is not here: it is the sharpest jump of all in the last stage, and both
meshes have a node exactly on it, so nothing needs excluding around it."""

FIELDS = {
    # ours <- the variable in the deck's json_output
    "bending_moment": "BENDING_MOMENT",
    "shear_force": "SHEAR_FORCE",
    "normal_force": "AXIAL_FORCE",
    "horizontal_total_displacement": "TOTAL_DISPLACEMENT_X",
}


def expected_curve(stage: str, field: str) -> list[tuple[float, float]]:
    """The reference curve for one field in one stage: [(y, value), ...], sorted by y."""
    path = crow_run.EXPECTED_WALL / f"{stage}.csv"
    with open(path, newline="") as handle:
        return sorted((float(row["y"]), float(row[field]))
                      for row in csv.DictReader(handle))


def interpolate(curve: list[tuple[float, float]], y: float,
                tolerance: float = 1e-6) -> float:
    """The curve's value at y, linearly between the two points that bracket it."""
    for (y1, value1), (y2, value2) in zip(curve, curve[1:]):
        if y1 - tolerance <= y <= y2 + tolerance:
            if y2 == y1:
                return value1
            return value1 + (value2 - value1) * (y - y1) / (y2 - y1)
    raise AssertionError(
        f"y = {y} m is outside the reference curve's range "
        f"[{curve[0][0]}, {curve[-1][0]}] m, so it cannot be compared. The wall extent "
        f"test should have caught this first.")


def delta(expected: float, largest: float) -> float:
    """Kratos' `test_helper.calculate_delta`, with its absolute floor."""
    return max(RELATIVE_TOLERANCE * largest, RELATIVE_TOLERANCE * abs(expected))


def wall_nodes() -> dict[int, float]:
    """{node id: y} for our wall, from the run's own deck."""
    deck = mdpa.parse(crow_run.deck_text())
    return {node: deck.nodes[node][1] for node in deck.parts[crow_run.WALL_PART].nodes}


def computed(stage: str, variable: str) -> dict[int, float]:
    """{node id: value} for one variable of one stage, from the deck's member output."""
    output = crow_run.member_output(stage, "wall")
    return {node: output[f"NODE_{node}"][variable][0]
            for node in wall_nodes()
            if f"NODE_{node}" in output and variable in output[f"NODE_{node}"]}


def near_discontinuity(y: float) -> bool:
    return any(abs(y - level) <= DISCONTINUITY_BAND for level in SHEAR_DISCONTINUITIES)


def compare(stage: str, field: str, region: str = "all", minimum: int = 20) -> None:
    """Every wall node of one stage against the reference curve.

    `region` selects which nodes: "all", "away" from the shear discontinuities, or
    "near" them -- the last with `NEAR_JUMP_TOLERANCE` in place of Kratos' rule.

    Failures are collected and reported together rather than raising at the first node:
    "17 of 39 nodes disagree, worst at y = -2.0 m" is a different diagnosis from "one
    node at the toe disagrees", and a test that stops at the first cannot tell them
    apart.
    """
    curve = expected_curve(stage, field)
    largest = max(abs(value) for _, value in curve)
    y_by_node = wall_nodes()
    values = computed(stage, FIELDS[field])
    assert values, f"{stage} has no {FIELDS[field]} for any wall node"

    failures = []
    compared = 0
    for node, value in sorted(values.items()):
        y = y_by_node[node]
        if region == "away" and near_discontinuity(y):
            continue
        if region == "near" and not near_discontinuity(y):
            continue
        compared += 1
        want = interpolate(curve, y)
        allowed = (NEAR_JUMP_TOLERANCE * largest if region == "near"
                   else delta(want, largest))
        if abs(value - want) > allowed:
            failures.append(f"    y = {y:8.4f} m: {value:12.6g} vs {want:12.6g} "
                            f"expected (out by {abs(value - want) / allowed:.2f}x the "
                            f"{allowed:.6g} allowed)")

    assert compared >= minimum, (
        f"only {compared} of {len(values)} wall nodes were compared in {stage}; "
        f"the exclusion band has eaten the test")
    assert not failures, (
        f"{len(failures)} of {compared} wall nodes disagree with the CROW reference "
        f"for {field} in {stage}:\n" + "\n".join(failures))


# ── The wall has to be comparable at all ────────────────────────────────────

def test_our_wall_spans_the_same_depth_as_the_reference_wall():
    """Interpolation is not extrapolation.

    A wall that reached deeper than the reference's would be compared against a curve
    that says nothing there, and `interpolate` would raise rather than quietly returning
    the end value -- but the failure would read as a missing expected value instead of as
    a model that is the wrong size. Kratos' own test asserts this first, for the same
    reason.
    """
    ours = wall_nodes().values()
    curve = expected_curve("7_Third_excavation", "bending_moment")
    reference_top, reference_toe = curve[-1][0], curve[0][0]

    assert min(ours) >= reference_toe - 1e-6, "our wall reaches deeper than the reference"
    assert max(ours) <= reference_top + 1e-6, "our wall reaches higher than the reference"
    assert (reference_toe, reference_top) == (-13.0, 0.0)


def test_every_checked_stage_has_member_output_for_the_whole_wall():
    """The comparison is only worth as much as its coverage: a stage whose output
    carried three nodes would pass every assertion below and mean nothing."""
    for stage in crow_run.WALL_OUTPUT_STAGES:
        values = computed(stage, "BENDING_MOMENT")
        assert len(values) == len(wall_nodes()) >= 39, (
            f"{stage} reports {len(values)} of {len(wall_nodes())} wall nodes")


# ── The validation itself ───────────────────────────────────────────────────

@pytest.mark.parametrize("stage", crow_run.WALL_OUTPUT_STAGES)
def test_bending_moment_matches_the_crow_reference(stage):
    """The headline number of a sheet-pile calculation, at every node of every checked
    stage. This is the one that says the model is right."""
    compare(stage, "bending_moment")


@pytest.mark.parametrize("stage", crow_run.WALL_OUTPUT_STAGES)
def test_horizontal_displacement_matches_the_crow_reference(stage):
    """What the user looks at second, and what the excavation is designed around."""
    compare(stage, "horizontal_total_displacement")


@pytest.mark.parametrize("stage", crow_run.WALL_OUTPUT_STAGES)
def test_shear_force_matches_the_crow_reference_away_from_its_jumps(stage):
    """Shear, at Kratos' tolerance, everywhere the quantity is continuous. See the module
    docstring for why the band exists and how wide it had to be."""
    compare(stage, "shear_force", region="away")


@pytest.mark.parametrize("stage", crow_run.WALL_OUTPUT_STAGES)
def test_shear_force_next_to_its_jumps_stays_within_the_measured_difference(stage):
    """The nodes the test above steps over, held to what they are instead of to nothing.

    A band that excluded nodes from every check would hide a real divergence in exactly
    the place a load is applied. This does not claim 12 % is good agreement -- it says
    the difference is 9.3 % at worst today and is not allowed to grow quietly.
    """
    compare(stage, "shear_force", region="near", minimum=10)


def test_the_strut_is_where_the_shear_jumps_hardest():
    """A load has to arrive where the model says it does.

    The strut sits at y = -1.5 m, and in the final stage the two largest changes in shear
    between adjacent wall nodes are the two intervals either side of it. That is the
    signature of a point load landing on the right node -- and a check the wall-force
    comparison itself cannot make, since it compares values rather than what produced
    them.
    """
    y_by_node = wall_nodes()
    values = computed("7_Third_excavation", "SHEAR_FORCE")
    along = sorted((y_by_node[node], value) for node, value in values.items())
    jumps = sorted(((abs(b - a), (y1 + y2) / 2)
                    for (y1, a), (y2, b) in zip(along, along[1:])), reverse=True)

    for size, y in jumps[:2]:
        assert abs(y + 1.5) <= 0.25, (
            f"the largest jumps in shear are not at the strut: {size:.0f} N/m across "
            f"y = {y:.3f} m")


# ── The summary numbers a person actually reads ─────────────────────────────

def test_the_peak_moment_and_deflection_of_the_final_stage():
    """The two numbers that end up in a report, checked as numbers rather than as curves.

    These survive a re-mesh, where the node-by-node comparison above would have to be
    regenerated, so they are the part of this file that keeps working when the mesh
    changes.
    """
    y_by_node = wall_nodes()
    moments = computed("7_Third_excavation", "BENDING_MOMENT")
    displacements = computed("7_Third_excavation", "TOTAL_DISPLACEMENT_X")

    peak_node = max(moments, key=lambda node: abs(moments[node]))
    peak_moment = abs(moments[peak_node]) / 1000.0            # N*m/m -> kN*m/m
    curve = expected_curve("7_Third_excavation", "bending_moment")
    expected_y, expected_value = max(curve, key=lambda point: abs(point[1]))
    expected_peak = abs(expected_value) / 1000.0

    assert peak_moment == pytest.approx(expected_peak, rel=RELATIVE_TOLERANCE), (
        f"peak moment {peak_moment:.1f} kN*m/m against {expected_peak:.1f} expected")
    assert abs(y_by_node[peak_node] - expected_y) <= 0.5, (
        f"the peak moment is at y = {y_by_node[peak_node]} m, where the reference puts "
        f"it at y = {expected_y} m. Depth is read off the diagram as much as magnitude "
        f"is, so the two have to agree.")

    top = max(displacements, key=lambda node: y_by_node[node])
    top_displacement = displacements[top] * 1000.0            # m -> mm
    expected_top = interpolate(
        expected_curve("7_Third_excavation", "horizontal_total_displacement"),
        y_by_node[top]) * 1000.0
    assert top_displacement == pytest.approx(expected_top, abs=1.0), (
        f"wall-top deflection {top_displacement:.2f} mm against {expected_top:.2f} mm")
    assert top_displacement < 0.0, "the wall deflects towards the excavation"
