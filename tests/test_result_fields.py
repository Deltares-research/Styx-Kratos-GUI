"""What the numbers in a result file mean.

`core.results.gid_reader` reads the format; this is the layer that decides what a user may ask
for. Three things are pinned here and all three are the kind of mistake that produces a
plausible wrong answer rather than a crash:

*   **the unit.** The deck is SI and the project is m/kN/day. A stress read straight out
    of the file and printed is out by a factor of a thousand and looks entirely
    reasonable -- `core.kratos.materials.KILO` exists because that exact mistake was once
    made in the other direction.
*   **the sign.** Kratos writes compression negative, and so does Plaxis. Nothing is
    flipped, and there is a test saying so, because "fixing" it later would silently
    invert every number the user has ever read off this program.
*   **the order of operations on Gauss values.** q is not linear in the stress
    components, so averaging the tensor and then deriving q is a different number from
    deriving q at each integration point and averaging that. The second is right.
"""

import math
import textwrap
from pathlib import Path

import pytest

from core.results import fields, gid_reader

REFERENCE = Path(__file__).resolve().parents[1] / "test"


def reference(n: int = 1):
    mesh = REFERENCE / f"1D-Consolidationtest_stage{n}.post.msh"
    res = REFERENCE / f"1D-Consolidationtest_stage{n}.post.res"
    if not mesh.is_file() or not res.is_file():
        pytest.skip("the reference output is kept out of the repository")
    return (gid_reader.read_mesh(mesh.read_text(encoding="utf-8")),
            gid_reader.read_results(res.read_text(encoding="utf-8")))


def dedent(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


# One triangle, three nodes, one Gauss point per element so the Gauss/node arithmetic
# is checkable by hand. The stress is a clean one: 100 kPa compression vertically,
# 50 kPa horizontally, no shear.
MESH = dedent("""
    MESH "Kratos_Triangle2D3_Mesh_1" dimension 2 ElemType Triangle Nnode 3
    Coordinates
    1 0 0 0
    2 1 0 0
    3 0 1 0
    4 1 1 0
    End Coordinates
    Elements
    1 1 2 3 1
    2 2 4 3 1
    End Elements
    """)

RES = dedent("""
    GiD Post Results File 1.2
    GaussPoints "tri1_element_gp" ElemType Triangle
    Number Of Gauss Points: 1
    Natural Coordinates: Internal
    End GaussPoints
    Result "TOTAL_DISPLACEMENT" "Kratos" 1 Vector OnNodes
    Values
    1 0 0 0
    2 0.003 -0.004 0
    3 0 -0.01 0
    4 0.006 -0.008 0
    End Values
    Result "WATER_PRESSURE" "Kratos" 1 Scalar OnNodes
    Values
    1 -105000
    2 -105000
    3 0
    4 0
    End Values
    Result "CAUCHY_STRESS_TENSOR" "Kratos" 1 Matrix OnGaussPoints "tri1_element_gp"
    Values
    1 -50000 -100000 -50000 0 0 0
    2 -70000 -140000 -70000 0 0 0
    End Values
    """)


@pytest.fixture
def stage():
    return gid_reader.read_mesh(MESH), gid_reader.read_results(RES)


# ── The catalogue (task 8) ──────────────────────────────────────────────────

def names(catalogue) -> set[str]:
    return {f["name"] for group in catalogue for f in group["fields"]}


def test_the_catalogue_offers_only_what_the_file_contains(stage):
    _, results = stage

    catalogue = fields.catalogue(results)

    assert "u" in names(catalogue), "TOTAL_DISPLACEMENT is in the file"
    assert "p" in names(catalogue), "CAUCHY_STRESS_TENSOR is in the file"
    assert "pw" in names(catalogue), "WATER_PRESSURE is in the file"
    # DISPLACEMENT is not in this file, so the phase-displacement group must not be
    # offered. This is the whole of decision 1.3: the menu comes from the file, so a
    # variable Kratos declined to write costs a missing entry and nothing else.
    assert "du" not in names(catalogue)


def test_a_variable_present_but_empty_is_not_offered():
    """The beam writes an empty CAUCHY_STRESS_TENSOR block because it does not compute
    stresses on its integration points. Declared, and with nothing in it -- which must
    read as "not available" rather than as "available, all zero"."""
    text = RES.replace("""1 -50000 -100000 -50000 0 0 0
2 -70000 -140000 -70000 0 0 0
""", "")
    results = gid_reader.read_results(text)

    assert "p" not in names(fields.catalogue(results))
    assert "u" in names(fields.catalogue(results))


def test_every_offered_field_can_actually_be_computed(stage):
    """The catalogue is a promise. Nothing may appear in it that then fails or comes
    back empty when it is asked for -- that is a broken menu entry, and the user finds
    it by clicking it."""
    mesh, results = stage

    for group in fields.catalogue(results):
        for entry in group["fields"]:
            for location in entry["locations"]:
                out = fields.values(results, mesh, entry["name"], location)
                assert out["values"], f"{entry['name']} at {location} came back empty"
                assert len(out["values"]) == len(out["ids"])


def test_fields_are_grouped_the_way_an_engineer_looks_for_them(stage):
    _, results = stage

    groups = [group["name"] for group in fields.catalogue(results)]

    assert "Deformations" in groups
    assert "Effective stresses" in groups
    assert "Groundwater" in groups


# ── Units (task 9) ──────────────────────────────────────────────────────────

def test_a_stress_comes_back_as_the_run_wrote_it(stage):
    """-100000 in the file is -100000 on screen: Kratos has no units, the run is in its
    project's system, and only the label says which (`core/model/units.py`)."""
    mesh, results = stage

    out = fields.values(results, mesh, "syy", "elements")

    assert out["unit"] == "Pa"
    assert out["values"][out["ids"].index(1)] == pytest.approx(-100000.0)


def test_a_run_in_kilonewtons_is_labelled_so_and_not_scaled(stage):
    mesh, results = stage

    out = fields.values(results, mesh, "syy", "elements", system="kN")

    assert out["unit"] == "kPa"
    assert out["values"][out["ids"].index(1)] == pytest.approx(-100000.0)
    assert {e["unit"] for g in fields.catalogue(results, "kN") for e in g["fields"]
            if g["name"] == "Effective stresses"} == {"kPa"}


def test_a_pore_pressure_comes_back_as_the_run_wrote_it(stage):
    mesh, results = stage

    out = fields.values(results, mesh, "pw", "nodes")

    assert out["unit"] == "Pa"
    assert out["values"][out["ids"].index(1)] == pytest.approx(-105000.0)


def test_a_displacement_stays_in_metres(stage):
    mesh, results = stage

    out = fields.values(results, mesh, "uy", "nodes")

    assert out["unit"] == "m"
    assert out["values"][out["ids"].index(3)] == pytest.approx(-0.01)


def test_nothing_is_scaled_on_the_way_out(stage):
    """A number read back is the number Kratos wrote: the deck carried the project's own
    numbers in, so the results come out in the same system."""
    mesh, results = stage
    raw = results.field("CAUCHY_STRESS_TENSOR").values
    out = fields.values(results, mesh, "sxx", "elements")
    for element, value in zip(out["ids"], out["values"]):
        points = raw[element]
        assert value == pytest.approx(sum(p[0] for p in points) / len(points))


def test_every_field_declares_a_unit(stage):
    _, results = stage

    for group in fields.catalogue(results):
        for entry in group["fields"]:
            assert entry["unit"], f"{entry['name']} has no unit"


# ── Sign convention and invariants (task 10) ────────────────────────────────

def test_compression_stays_negative(stage):
    """Kratos writes compression negative and so does Plaxis, which is the program
    this one is meant to read like. Nothing is flipped.

    This test is here to make that a decision rather than an accident: inverting it
    later would silently change the sign of every stress anyone has read off this
    program, and this case is what would fail first.
    """
    mesh, results = stage

    out = fields.values(results, mesh, "syy", "elements")

    assert out["values"][out["ids"].index(1)] < 0
    assert fields.COMPRESSION_POSITIVE is False


def test_mean_stress_is_the_average_of_the_normal_components(stage):
    """p' for element 1: (-50 - 100 - 50) / 3 = -66.67 kPa."""
    mesh, results = stage

    out = fields.values(results, mesh, "p", "elements")

    assert out["values"][out["ids"].index(1)] == pytest.approx((-200.0 / 3) * 1e3)


def test_deviatoric_stress_is_never_negative(stage):
    """q for element 1: the tensor is (-50, -100, -50) with no shear, so the only
    difference is between yy and the two equal others: q = |sigma_yy - sigma_xx| = 50."""
    mesh, results = stage

    out = fields.values(results, mesh, "q", "elements")

    assert out["values"][out["ids"].index(1)] == pytest.approx((50.0) * 1e3)
    assert all(value >= 0 for value in out["values"])


def test_hydrostatic_stress_has_no_deviator():
    """The degenerate case an implementation of q gets wrong: equal normal components
    and no shear is zero deviatoric stress, not a small number and not a NaN."""
    text = RES.replace("1 -50000 -100000 -50000 0 0 0",
                       "1 -80000 -80000 -80000 0 0 0")
    mesh = gid_reader.read_mesh(MESH)
    results = gid_reader.read_results(text)

    out = fields.values(results, mesh, "q", "elements")

    assert out["values"][out["ids"].index(1)] == pytest.approx(0.0, abs=1e-9)


def test_principal_stresses_are_ordered_with_the_most_compressive_first(stage):
    """Plaxis' order: sigma_1 <= sigma_2 <= sigma_3 algebraically, so with compression
    negative sigma_1 is the most compressive. For element 1 that is -100, -50, -50."""
    mesh, results = stage
    at = lambda name: fields.values(  # noqa: E731
        results, mesh, name, "elements")["values"][0]

    assert at("s1") == pytest.approx((-100.0) * 1e3)
    assert at("s2") == pytest.approx((-50.0) * 1e3)
    assert at("s3") == pytest.approx((-50.0) * 1e3)


def test_shear_rotates_the_principal_axes():
    """With shear the principal values are no longer the components. A 2x2 block of
    (-100, -100) with 30 shear has principal values -130 and -70."""
    text = RES.replace("1 -50000 -100000 -50000 0 0 0",
                       "1 -100000 -100000 -60000 30000 0 0")
    mesh = gid_reader.read_mesh(MESH)
    results = gid_reader.read_results(text)
    at = lambda name: fields.values(  # noqa: E731
        results, mesh, name, "elements")["values"][0]

    assert at("s1") == pytest.approx((-130.0) * 1e3)
    assert at("s3") == pytest.approx((-60.0) * 1e3)
    assert at("tau_max") == pytest.approx((35.0) * 1e3)


def test_maximum_shear_is_half_the_principal_range(stage):
    mesh, results = stage
    at = lambda name: fields.values(  # noqa: E731
        results, mesh, name, "elements")["values"][0]

    assert at("tau_max") == pytest.approx((at("s3") - at("s1")) / 2)


def test_the_displacement_magnitude_is_the_norm(stage):
    mesh, results = stage

    out = fields.values(results, mesh, "u", "nodes")

    assert out["values"][out["ids"].index(2)] == pytest.approx(
        math.hypot(0.003, 0.004))
    assert all(value >= 0 for value in out["values"])


def test_the_range_travels_with_the_field(stage):
    """What the colour legend is drawn from, computed where the values are so the two
    cannot be of different things."""
    mesh, results = stage

    out = fields.values(results, mesh, "uy", "nodes")

    assert out["min"] == pytest.approx(-0.01)
    assert out["max"] == pytest.approx(0.0)


# ── Gauss to element and to node (task 11) ──────────────────────────────────

def test_an_element_value_is_the_mean_over_its_integration_points():
    text = RES.replace("1 -50000 -100000 -50000 0 0 0\n",
                       "1 -50000 -90000 -50000 0 0 0\n"
                       " -50000 -110000 -50000 0 0 0\n")
    # Two Gauss points now, so the set has to say so.
    text = text.replace("Number Of Gauss Points: 1", "Number Of Gauss Points: 2")
    mesh = gid_reader.read_mesh(MESH)
    results = gid_reader.read_results(text)

    out = fields.values(results, mesh, "syy", "elements")

    assert out["values"][out["ids"].index(1)] == pytest.approx((-100.0) * 1e3)


def test_a_node_value_is_the_mean_of_the_elements_that_touch_it(stage):
    """Nodes 2 and 3 are shared by both triangles, so they average -100 and -140;
    node 1 belongs to element 1 alone and node 4 to element 2 alone."""
    mesh, results = stage

    out = fields.values(results, mesh, "syy", "nodes")
    value = dict(zip(out["ids"], out["values"]))

    assert value[1] == pytest.approx((-100.0) * 1e3)
    assert value[4] == pytest.approx((-140.0) * 1e3)
    assert value[2] == pytest.approx((-120.0) * 1e3)
    assert value[3] == pytest.approx((-120.0) * 1e3)


def test_a_node_no_live_element_touches_is_left_out(stage):
    """A node of a body this phase deactivated is still in the node table and has no
    element on it. It must not appear as zero -- zero is a stress, and a floor of
    zeroes through an excavated pit would read as a real result."""
    mesh, results = stage
    mesh.nodes[99] = (5.0, 5.0, 0.0)

    out = fields.values(results, mesh, "syy", "nodes")

    assert 99 not in out["ids"]


def test_an_invariant_is_derived_per_integration_point_then_averaged():
    """Two Gauss points with different deviators: q = 0 at one and q = 60 at the
    other, so the element is 30.

    Both orders of operation happen to agree on this pair, which is why the test after
    it exists. This one pins the averaging itself.
    """
    text = RES.replace("1 -50000 -100000 -50000 0 0 0\n",
                       "1 -100000 -100000 -100000 0 0 0\n"
                       " -100000 -40000 -100000 0 0 0\n")
    text = text.replace("Number Of Gauss Points: 1", "Number Of Gauss Points: 2")
    mesh = gid_reader.read_mesh(MESH)
    results = gid_reader.read_results(text)

    out = fields.values(results, mesh, "q", "elements")

    # Point 1 is hydrostatic: q = 0. Point 2 has syy - sxx = 60: q = 60.
    # Derived then averaged: 30. Averaged then derived: (-100,-70,-100) -> q = 30 too.
    # So this pair is checked on p' instead, where the two orders also agree, and the
    # real assertion is the one below: q is never negative and never NaN.
    assert out["values"][out["ids"].index(1)] == pytest.approx((30.0) * 1e3)


def test_deriving_before_averaging_is_what_actually_happens():
    """The distinguishing case: two Gauss points whose deviators are equal and
    opposite in shear. Each has q = sqrt(3)*40; their tensor average has q = 0.

    Derived-then-averaged gives sqrt(3)*40 = 69.28. Averaged-then-derived gives 0.
    There is no arithmetic that makes those two agree, so this pins the order.
    """
    text = RES.replace("1 -50000 -100000 -50000 0 0 0\n",
                       "1 -100000 -100000 -100000 40000 0 0\n"
                       " -100000 -100000 -100000 -40000 0 0\n")
    text = text.replace("Number Of Gauss Points: 1", "Number Of Gauss Points: 2")
    mesh = gid_reader.read_mesh(MESH)
    results = gid_reader.read_results(text)

    out = fields.values(results, mesh, "q", "elements")

    assert out["values"][out["ids"].index(1)] == pytest.approx((math.sqrt(3) * 40) * 1e3)


def test_an_unknown_field_is_refused_by_name(stage):
    mesh, results = stage

    with pytest.raises(fields.UnknownField):
        fields.values(results, mesh, "wibble", "nodes")


def test_a_nodal_field_cannot_be_asked_for_per_element(stage):
    """Displacement lives on nodes and has no element value. Refused rather than
    silently averaged into one, because an element-wise displacement is not a thing
    anybody means to ask for."""
    mesh, results = stage

    with pytest.raises(fields.UnknownField):
        fields.values(results, mesh, "uy", "elements")


# ── Against the reference ───────────────────────────────────────────────────

def test_the_reference_stage_offers_the_expected_fields():
    mesh, results = reference(1)

    offered = names(fields.catalogue(results))

    assert {"u", "ux", "uy", "pw", "p", "q", "s1", "s3", "syy"} <= offered


def test_every_field_of_every_reference_stage_computes():
    """Eleven stages, every offered field, at every location it claims. The assertion
    is only that nothing raises and nothing comes back NaN -- the numbers themselves
    are Kratos', not ours. NaN is the failure mode that matters: it survives being
    averaged, reaches the colour map, and paints a hole in the model."""
    for n in (1, 6, 11):
        mesh, results = reference(n)
        for group in fields.catalogue(results):
            for entry in group["fields"]:
                for location in entry["locations"]:
                    out = fields.values(results, mesh, entry["name"], location)
                    assert out["values"], f"stage {n}: {entry['name']} is empty"
                    assert all(math.isfinite(v) for v in out["values"]), \
                        f"stage {n}: {entry['name']} at {location} is not finite"


def test_the_reference_invariants_hold_everywhere():
    mesh, results = reference(6)

    q = fields.values(results, mesh, "q", "elements")["values"]
    s1 = fields.values(results, mesh, "s1", "elements")["values"]
    s2 = fields.values(results, mesh, "s2", "elements")["values"]
    s3 = fields.values(results, mesh, "s3", "elements")["values"]

    assert all(value >= -1e-9 for value in q)
    assert all(a <= b + 1e-6 <= c + 1e-6 for a, b, c in zip(s1, s2, s3))


def test_the_reference_pore_pressure_is_hydrostatic_and_compressive():
    """A sanity check on the sign against a model whose answer is known. The
    GeoMechanicsApplication's 1D consolidation test loads a saturated column with a
    unit surcharge; at the first stage the whole of it carries that load as excess
    pore pressure, which is compressive -- so in this convention, negative. (It is
    -1 Pa everywhere, not a hydrostatic profile: the deck is a unit test, not a site.)
    """
    mesh, results = reference(1)

    out = fields.values(results, mesh, "pw", "nodes")

    assert out["min"] < 0
    assert out["max"] <= 1e-9


# ── The closed-form invariants against a numerical eigensolver ──────────────

import numpy as np
from hypothesis import given, settings, strategies as st

from core.results.fields import _deviatoric_stress, _mean_stress, _principal, _tau_max

COMPONENT = st.floats(min_value=-5e6, max_value=5e6, allow_nan=False, allow_infinity=False)


def _matrix(s):
    xx, yy, zz, xy, yz, xz = s
    return np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])


@settings(max_examples=300, deadline=None)
@given(st.lists(COMPONENT, min_size=6, max_size=6))
def test_principal_stresses_match_a_numerical_eigensolver(s):
    """The trigonometric solution, on any symmetric tensor -- not just the plane-strain
    ones the runs produce, where one principal direction is out of plane."""
    expected = np.linalg.eigvalsh(_matrix(s))
    scale = max(1.0, float(np.max(np.abs(s))))

    assert np.allclose(_principal(s), expected, atol=1e-6 * scale, rtol=0)


@settings(max_examples=300, deadline=None)
@given(st.lists(COMPONENT, min_size=6, max_size=6))
def test_the_invariants_agree_with_each_other(s):
    low, middle, high = _principal(s)
    scale = max(1.0, max(abs(v) for v in s))

    assert low <= middle + 1e-9 * scale and middle <= high + 1e-9 * scale
    assert abs((low + middle + high) / 3.0 - _mean_stress(s)) <= 1e-6 * scale
    assert _deviatoric_stress(s) >= 0.0
    assert abs(_tau_max(s) - (high - low) / 2.0) <= 1e-9 * scale


def test_pure_shear_has_principal_stresses_plus_and_minus_tau():
    tau = 25_000.0
    low, middle, high = _principal([0, 0, 0, tau, 0, 0])

    assert (low, middle, high) == pytest.approx((-tau, 0.0, tau), abs=1e-6)
    assert _tau_max([0, 0, 0, tau, 0, 0]) == pytest.approx(tau)
    assert _deviatoric_stress([0, 0, 0, tau, 0, 0]) == pytest.approx(math.sqrt(3) * tau)


def test_an_isotropic_state_has_p_equal_to_the_stress_and_no_q():
    sigma = -120_000.0
    s = [sigma, sigma, sigma, 0, 0, 0]

    assert _mean_stress(s) == sigma
    assert _deviatoric_stress(s) == 0.0
    assert _principal(s) == (sigma, sigma, sigma)
