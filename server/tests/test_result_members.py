"""The wall and interface plots: what the Results plot window draws.

Kratos' `json_output` process writes, per stage, one file per member --
`<stage>__output_wall.json` with the bending moment, shear force, normal force and
displacement at every wall node, and `<stage>__output_interface.json` with the effective
traction on one side of the wall. `app.result_members` turns one of those into a curve
along the member: (value, y) per node, sorted by y, in the units a retaining-wall plot is
read in.

Two halves:

*   **Synthetic** -- three-node outputs written here, which pin the reading rules: the
    last time step, the vector component, the unit, the sort, the extremes.
*   **CROW** -- the committed run, held to Kratos' own CROW run on the reference mesh,
    which is the orange line ("Kratos - mesh in repository") of the comparison figure in
    `test_CROW_case_testGUI_mesh.py`. That figure is what the plot window imitates, so
    every panel of it is a test here: six quantities, five stages.

The comparison follows `test_crow_wall_forces.py` -- our node against the reference
curve interpolated at our node's y, within Kratos' `calculate_delta` rule -- and differs
from it in one way that is the point: it goes through `results.member_profiles`, the
function the plot route serves, so the units, the sign and the sort are the ones on
screen rather than the deck's.
"""

from __future__ import annotations

import csv
import json

import pytest

from app import result_members, results
from tests import crow_run
from tests import test_crow_wall_forces as wall_forces


# ── Reading one output ──────────────────────────────────────────────────────

def output(nodes: dict[int, dict], times: int = 1) -> dict:
    """A json_output payload: `TIME`, then `NODE_<id>: {variable: [value per time]}`."""
    payload = {"TIME": [float(t + 1) for t in range(times)]}
    for node, variables in nodes.items():
        payload[f"NODE_{node}"] = {name: values for name, values in variables.items()}
    return payload


COORDINATES = {1: (5.0, 0.0, 0.0), 2: (5.0, -2.0, 0.0), 3: (5.0, -1.0, 0.0)}
"""Three wall nodes, deliberately out of order in y."""


def test_reading_takes_the_last_time_of_each_series_and_skips_time():
    read = result_members.read_output(json.dumps(output({
        1: {"BENDING_MOMENT": [1000.0, 2000.0]},
        2: {"BENDING_MOMENT": [3000.0, 4000.0]},
    }, times=2)))

    assert read == {1: {"BENDING_MOMENT": 2000.0}, 2: {"BENDING_MOMENT": 4000.0}}


def test_a_profile_is_sorted_by_level_from_toe_to_top():
    read = {1: {"BENDING_MOMENT": 10e3}, 2: {"BENDING_MOMENT": 30e3},
            3: {"BENDING_MOMENT": 20e3}}

    found = result_members.profile(read, COORDINATES, result_members.quantity("M"))

    assert [y for _, y in found["points"]] == [-2.0, -1.0, 0.0]
    assert found["nodes"] == [2, 3, 1]


def test_forces_are_the_runs_own_numbers_and_displacements_in_metres():
    """Nothing is scaled: a run's numbers are in its own unit system, and labelled."""
    read = {1: {"BENDING_MOMENT": 10e3, "TOTAL_DISPLACEMENT_X": -0.01}}
    coordinates = {1: COORDINATES[1]}

    moment = result_members.profile(read, coordinates, result_members.quantity("M"))
    ux = result_members.profile(read, coordinates, result_members.quantity("ux"))

    assert moment["points"] == [[pytest.approx(10e3), 0.0]]
    assert ux["points"] == [[pytest.approx(-0.01), 0.0]]


def test_the_sign_is_kratos_own():
    """Not flipped to match anyone else's convention. The reference figure plots
    Kratos' numbers as they are, and so does the window."""
    read = {1: {"SHEAR_FORCE": -5e3}}

    found = result_members.profile(read, {1: COORDINATES[1]},
                                   result_members.quantity("Q"))

    assert found["points"][0][0] == pytest.approx(-5e3)


def test_traction_is_split_into_its_normal_and_shear_components():
    read = {1: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-12e3, 3e3]}}
    coordinates = {1: COORDINATES[1]}

    normal = result_members.profile(read, coordinates, result_members.quantity("tn"))
    shear = result_members.profile(read, coordinates, result_members.quantity("ts"))

    assert normal["points"][0][0] == pytest.approx(-12e3)
    assert shear["points"][0][0] == pytest.approx(3e3)


def test_the_extremes_carry_the_level_they_occur_at():
    read = {1: {"BENDING_MOMENT": 10e3}, 2: {"BENDING_MOMENT": -30e3},
            3: {"BENDING_MOMENT": 20e3}}

    found = result_members.profile(read, COORDINATES, result_members.quantity("M"))

    assert found["min"] == {"value": pytest.approx(-30e3), "y": -2.0}
    assert found["max"] == {"value": pytest.approx(20e3), "y": -1.0}


def test_a_node_without_the_variable_is_left_out_rather_than_zero():
    read = {1: {"BENDING_MOMENT": 10e3}, 2: {}}

    found = result_members.profile(read, COORDINATES, result_members.quantity("M"))

    assert found["nodes"] == [1]


def test_the_two_faces_of_an_interface_are_one_point_not_two():
    """A zero-thickness interface has a node on each face at every level, and Kratos
    writes the same traction on both (Eemdijk's interface output: 1494 nodes, 747
    levels, every pair identical). Drawn as they come, every dot is drawn twice and the
    CSV has every row twice."""
    read = {1: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-12e3, 3e3]},
            9: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-12e3, 3e3]},
            3: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-20e3, 1e3]}}
    coordinates = {1: (18.0, 0.0, 0.0), 9: (18.0, 0.0, 0.0), 3: (18.0, -1.0, 0.0)}

    found = result_members.profile(read, coordinates, result_members.quantity("tn"))

    assert found["points"] == [[pytest.approx(-20e3), -1.0], [pytest.approx(-12e3), 0.0]]
    assert found["nodes"] == [3, 1]


def test_only_what_an_output_carries_is_offered_in_catalogue_order():
    wall = {1: {"TOTAL_DISPLACEMENT_X": 0.0, "BENDING_MOMENT": 0.0,
                "SHEAR_FORCE": 0.0}}
    interface = {7: {"GEO_EFFECTIVE_TRACTION_VECTOR": [0.0, 0.0]}}

    assert [q.name for q in result_members.available([wall])] == ["M", "Q", "ux"]
    assert [q.name for q in result_members.available([interface])] == ["tn", "ts"]


def test_an_unknown_quantity_is_refused_by_name():
    with pytest.raises(result_members.UnknownQuantity, match="sigma"):
        result_members.quantity("sigma")


@pytest.mark.parametrize("filename, stage, member", [
    ("7_Third_excavation__output_wall.json", "7_Third_excavation", "wall"),
    ("12_Damwand_installatie__output_interface.json", "12_Damwand_installatie",
     "interface"),
    ("7_Third_excavation__something_else.json", "7_Third_excavation", "something_else"),
    ("6_Second_excavation__output_wall.json", "7_Third_excavation", None),
])
def test_the_member_is_named_by_what_follows_the_stage(filename, stage, member):
    assert result_members.member_name(filename, stage) == member


# ── The committed CROW run ──────────────────────────────────────────────────

@pytest.fixture
def run(monkeypatch):
    crow_run.use_fixture_runs(monkeypatch)
    return crow_run.RUN_ID


def test_the_run_offers_the_wall_and_the_interface(run):
    members = {m["name"]: m for m in results.stage_members(run)["members"]}

    assert sorted(members) == ["interface", "wall"]
    assert members["wall"]["stages"] == [3, 4, 5, 6, 7]
    assert [q["name"] for q in members["wall"]["quantities"]] == \
        ["M", "Q", "N", "ux", "uy"]
    assert [q["name"] for q in members["interface"]["quantities"]] == ["tn", "ts"]
    assert members["wall"]["quantities"][0] == \
        {"name": "M", "label": "Bending moment", "unit": "N·m/m"}


def test_a_plot_has_one_panel_per_stage_with_the_wall_in_it(run):
    plot = results.member_profiles(run, "wall", "M")

    assert (plot["member"], plot["quantity"], plot["unit"]) == ("wall", "M", "N·m/m")
    assert [s["index"] for s in plot["stages"]] == [3, 4, 5, 6, 7]
    assert [s["name"] for s in plot["stages"]] == crow_run.MEMBER_STAGES
    assert plot["stages"][0]["phase"] == "SheetPileWall installation"


def test_the_wall_runs_from_its_toe_to_its_top(run):
    """y is the vertical axis, so the points are ordered toe to top -- the reference
    wall is 13 m long with its top at ground level."""
    for stage in results.member_profiles(run, "wall", "ux")["stages"]:
        levels = [y for _, y in stage["points"]]
        assert levels == sorted(levels)
        assert levels[0] == pytest.approx(-13.0)
        assert levels[-1] == pytest.approx(0.0)


def test_an_unknown_member_or_quantity_is_refused(run):
    with pytest.raises(results.UnknownRun, match="strut"):
        results.member_profiles(run, "strut", "M")
    with pytest.raises(result_members.UnknownQuantity):
        results.member_profiles(run, "wall", "tn")


# ── Against the benchmark ───────────────────────────────────────────────────

RELATIVE_TOLERANCE = 0.02
"""Kratos' own, from `test_CROW_case_generated_mesh.py`."""

COLUMNS = {
    # quantity -> (member, column in expected_members/, scale to the plot's unit). The
    # run is SI and so is Kratos' reference: nothing to scale.
    "M": ("wall", "BENDING_MOMENT", 1.0),
    "Q": ("wall", "SHEAR_FORCE", 1.0),
    "N": ("wall", "AXIAL_FORCE", 1.0),
    "ux": ("wall", "TOTAL_DISPLACEMENT_X", 1.0),
    "tn": ("interface", "GEO_EFFECTIVE_TRACTION_VECTOR_0", 1.0),
    "ts": ("interface", "GEO_EFFECTIVE_TRACTION_VECTOR_1", 1.0),
}


def benchmark(stage: str, quantity: str) -> list[tuple[float, float]]:
    """Kratos' reference curve for one panel, as [(y, value in the plot's unit)]."""
    member, column, scale = COLUMNS[quantity]
    path = crow_run.EXPECTED_MEMBERS / f"{stage}__{member}.csv"
    with open(path, newline="") as handle:
        return sorted((float(row["y"]), float(row[column]) * scale)
                      for row in csv.DictReader(handle))


def interpolate(curve: list[tuple[float, float]], y: float) -> float:
    for (y1, v1), (y2, v2) in zip(curve, curve[1:]):
        if y1 - 1e-6 <= y <= y2 + 1e-6:
            return v1 if y2 == y1 else v1 + (v2 - v1) * (y - y1) / (y2 - y1)
    raise AssertionError(f"y = {y} is outside the benchmark [{curve[0][0]}, {curve[-1][0]}]")


def disagreements(run: str, quantity: str, excluded=lambda stage, y: False,
                  tolerance: float = RELATIVE_TOLERANCE) -> list[str]:
    """Every plotted point, of every stage, that misses the benchmark."""
    member = COLUMNS[quantity][0]
    found = []
    for stage in results.member_profiles(run, member, quantity)["stages"]:
        curve = benchmark(stage["name"], quantity)
        largest = max(abs(value) for _, value in curve)
        for value, y in stage["points"]:
            if excluded(stage["name"], y):
                continue
            expected = interpolate(curve, y)
            allowed = max(tolerance * largest, RELATIVE_TOLERANCE * abs(expected))
            if abs(value - expected) > allowed:
                found.append(f"{stage['name']} y={y:+.2f}: {value:.4g} against "
                             f"{expected:.4g} (allowed {allowed:.3g})")
    return found


@pytest.mark.parametrize("quantity", ["M", "N", "ux"])
def test_the_wall_plot_lies_on_the_benchmark(run, quantity):
    assert disagreements(run, quantity) == []


# Shear force and the two tractions miss Kratos' 2 % in narrow, named places, and only
# there. Every band below was measured on this run before it was written down; the
# tolerance inside it is a regression bound with a little headroom over that measurement,
# not a claim that the difference is acceptable engineering agreement. Outside the bands
# all three are held to 2 % like everything else.

def near_shear_jump(stage: str, y: float) -> bool:
    return wall_forces.near_discontinuity(y)


def test_the_shear_force_plot_lies_on_the_benchmark_away_from_load_jumps(run):
    """The same split as `test_crow_wall_forces.py`, for the same reason: a jump in the
    shear diagram, interpolated across at a node our coarser mesh puts inside it."""
    assert disagreements(run, "Q", excluded=near_shear_jump) == []


def test_the_shear_force_plot_stays_near_the_benchmark_at_load_jumps(run):
    """Measured worst 9.3 % of the stage's peak, at the ground surface in stage 3."""
    assert disagreements(run, "Q", tolerance=wall_forces.NEAR_JUMP_TOLERANCE) == []


GROUND_BAND = 0.8
"""The top of the wall, where our mesh is 0.375 m against the reference's 0.25 m and the
nodal traction is extrapolated from fewer points. Two of our elements."""

TOE_BAND = 0.8
"""The bottom of the wall, where the traction concentrates round the tip."""


def test_the_normal_traction_plot_lies_on_the_benchmark_below_the_ground_surface(run):
    assert disagreements(run, "tn", excluded=lambda stage, y: y > -GROUND_BAND) == []


def test_the_normal_traction_plot_stays_near_the_benchmark_at_the_ground_surface(run):
    """Measured worst 6.6 % of the stage's peak, at y = 0 in stages 4 and 5."""
    assert disagreements(run, "tn", tolerance=0.10) == []


def test_the_shear_traction_plot_lies_on_the_benchmark_above_the_toe(run):
    assert disagreements(run, "ts", excluded=lambda stage, y: y < -13.0 + TOE_BAND) == []


def test_the_shear_traction_plot_stays_near_the_benchmark_at_the_toe(run):
    """Measured worst 2.9 % of the stage's peak, at y = -12.5 in stage 7."""
    assert disagreements(run, "ts", tolerance=0.05) == []


# ── The routes the plot window calls ────────────────────────────────────────

@pytest.fixture
def client(run):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_the_members_route_lists_what_can_be_plotted(client, run):
    answer = client.get(f"/api/results/runs/{run}/members")

    assert answer.status_code == 200
    assert answer.json() == results.stage_members(run)


def test_the_plot_route_serves_one_quantity_along_one_member(client, run):
    answer = client.get(f"/api/results/runs/{run}/members/wall/M")

    assert answer.status_code == 200
    plot = answer.json()
    assert plot["label"] == "Bending moment"
    assert len(plot["stages"]) == 5


def test_the_plot_route_refuses_a_member_with_404_and_a_quantity_with_422(client, run):
    assert client.get(f"/api/results/runs/{run}/members/strut/M").status_code == 404
    assert client.get(f"/api/results/runs/{run}/members/wall/tn").status_code == 422
