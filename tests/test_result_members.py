"""The wall and interface plots: what the Results plot window draws.

Kratos' `json_output` process writes, per stage, one file per member --
`<stage>__output_wall.json` with the bending moment, shear force, normal force and
displacement at every wall node, and `<stage>__output_interface_<face>.json` with the effective
traction on one face of the wall. `core.results.members` turns one of those into a curve
along the member: (value, y) per node, sorted by y, in the units a retaining-wall plot is
read in.

Three-node outputs written here pin the reading rules: the last time step, the vector
component, the unit, the sort, the extremes. The routes the plot window calls are read
against a fake run of the test model (`tests/results_run.py`), which has member output
in the files a real run writes. What a real Kratos run's curves look like is
`tests/test_results_regression.py`.
"""

from __future__ import annotations

import json
import shutil

import pytest

from core.results import members, catalog
from tests import results_run


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
    read = members.read_output(json.dumps(output({
        1: {"BENDING_MOMENT": [1000.0, 2000.0]},
        2: {"BENDING_MOMENT": [3000.0, 4000.0]},
    }, times=2)))

    assert read == {1: {"BENDING_MOMENT": 2000.0}, 2: {"BENDING_MOMENT": 4000.0}}


def test_a_profile_is_sorted_by_level_from_toe_to_top():
    read = {1: {"BENDING_MOMENT": 10e3}, 2: {"BENDING_MOMENT": 30e3},
            3: {"BENDING_MOMENT": 20e3}}

    found = members.profile(read, COORDINATES, members.quantity("M"))

    assert [y for _, y in found["points"]] == [-2.0, -1.0, 0.0]
    assert found["nodes"] == [2, 3, 1]


def test_forces_are_the_runs_own_numbers_and_displacements_in_metres():
    """Nothing is scaled: a run's numbers are in its own unit system, and labelled."""
    read = {1: {"BENDING_MOMENT": 10e3, "TOTAL_DISPLACEMENT_X": -0.01}}
    coordinates = {1: COORDINATES[1]}

    moment = members.profile(read, coordinates, members.quantity("M"))
    ux = members.profile(read, coordinates, members.quantity("ux"))

    assert moment["points"] == [[pytest.approx(10e3), 0.0]]
    assert ux["points"] == [[pytest.approx(-0.01), 0.0]]


def test_the_sign_is_kratos_own():
    """Not flipped to match anyone else's convention. The reference figure plots
    Kratos' numbers as they are, and so does the window."""
    read = {1: {"SHEAR_FORCE": -5e3}}

    found = members.profile(read, {1: COORDINATES[1]},
                                   members.quantity("Q"))

    assert found["points"][0][0] == pytest.approx(-5e3)


def test_traction_is_split_into_its_normal_and_shear_components():
    read = {1: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-12e3, 3e3]}}
    coordinates = {1: COORDINATES[1]}

    normal = members.profile(read, coordinates, members.quantity("tn"))
    shear = members.profile(read, coordinates, members.quantity("ts"))

    assert normal["points"][0][0] == pytest.approx(-12e3)
    assert shear["points"][0][0] == pytest.approx(3e3)


def test_the_extremes_carry_the_level_they_occur_at():
    read = {1: {"BENDING_MOMENT": 10e3}, 2: {"BENDING_MOMENT": -30e3},
            3: {"BENDING_MOMENT": 20e3}}

    found = members.profile(read, COORDINATES, members.quantity("M"))

    assert found["min"] == {"value": pytest.approx(-30e3), "y": -2.0}
    assert found["max"] == {"value": pytest.approx(20e3), "y": -1.0}


def test_a_node_without_the_variable_is_left_out_rather_than_zero():
    read = {1: {"BENDING_MOMENT": 10e3}, 2: {}}

    found = members.profile(read, COORDINATES, members.quantity("M"))

    assert found["nodes"] == [1]


def test_the_two_faces_of_an_interface_are_one_point_not_two():
    """A zero-thickness interface has a node on each face at every level, and Kratos
    writes the same traction on both (a real interface output: every node pair
    identical). Drawn as they come, every dot is drawn twice and the
    CSV has every row twice."""
    read = {1: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-12e3, 3e3]},
            9: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-12e3, 3e3]},
            3: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-20e3, 1e3]}}
    coordinates = {1: (18.0, 0.0, 0.0), 9: (18.0, 0.0, 0.0), 3: (18.0, -1.0, 0.0)}

    found = members.profile(read, coordinates, members.quantity("tn"))

    assert found["points"] == [[pytest.approx(-20e3), -1.0], [pytest.approx(-12e3), 0.0]]
    assert found["nodes"] == [3, 1]


def test_only_what_an_output_carries_is_offered_in_catalogue_order():
    wall = {1: {"TOTAL_DISPLACEMENT_X": 0.0, "BENDING_MOMENT": 0.0,
                "SHEAR_FORCE": 0.0}}
    interface = {7: {"GEO_EFFECTIVE_TRACTION_VECTOR": [0.0, 0.0]}}

    assert [q.name for q in members.available([wall])] == ["M", "Q", "ux"]
    assert [q.name for q in members.available([interface])] == ["tn", "ts"]


def test_an_unknown_quantity_is_refused_by_name():
    with pytest.raises(members.UnknownQuantity, match="sigma"):
        members.quantity("sigma")


@pytest.mark.parametrize("filename, stage, member", [
    ("7_Third_excavation__output_wall.json", "7_Third_excavation", "wall"),
    ("12_Damwand_installatie__output_interface.json", "12_Damwand_installatie",
     "interface"),
    ("7_Third_excavation__something_else.json", "7_Third_excavation", "something_else"),
    ("6_Second_excavation__output_wall.json", "7_Third_excavation", None),
])
def test_the_member_is_named_by_what_follows_the_stage(filename, stage, member):
    assert members.member_name(filename, stage) == member


# ── The routes the plot window calls ────────────────────────────────────────

@pytest.fixture
def run(monkeypatch):
    return results_run.use(monkeypatch, results_run.fake_run())


@pytest.fixture
def client(run):
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as c:
        yield c


def test_the_members_route_lists_what_can_be_plotted(client, run):
    answer = client.get(f"/api/results/runs/{run}/members")

    assert answer.status_code == 200
    assert answer.json() == catalog.stage_members(run)


def test_the_plot_route_serves_one_quantity_along_one_member(client, run):
    answer = client.get(f"/api/results/runs/{run}/members/wall/M")

    assert answer.status_code == 200
    plot = answer.json()
    assert plot["label"] == "Bending moment"
    assert len(plot["stages"]) == 5


def test_the_plot_route_refuses_a_member_with_404_and_a_quantity_with_422(client, run):
    assert client.get(f"/api/results/runs/{run}/members/strut/M").status_code == 404
    assert client.get(f"/api/results/runs/{run}/members/wall/tn").status_code == 422


def test_a_run_saved_before_the_two_faces_still_plots_its_one_interface(tmp_path, monkeypatch):
    """A run from before each face had its own output wrote `__output_interface.json`."""
    root, run_id = results_run.fake_run()
    old = tmp_path / run_id
    shutil.copytree(root / run_id, old)
    for path in old.glob("*__output_interface_left.json"):
        path.unlink()
    for path in old.glob("*__output_interface_right.json"):
        path.rename(path.with_name(path.name.replace("_interface_right", "_interface")))
    run = results_run.use(monkeypatch, (tmp_path, run_id))

    listed = {m["name"]: m for m in catalog.stage_members(run)["members"]}
    plot = catalog.member_profiles(run, "interface", "tn")

    assert sorted(listed) == ["interface", "wall"]
    assert [q["name"] for q in listed["interface"]["quantities"]] == ["tn", "ts"]
    assert [stage["index"] for stage in plot["stages"]] == listed["interface"]["stages"]
    assert all(stage["points"] for stage in plot["stages"])


@pytest.mark.parametrize("raw", [None, "bad", True, [], [1], [1, False], [1, "bad"]])
def test_invalid_member_values_leave_a_gap_in_the_profile_instead_of_zero(raw):
    output = {1: {"GEO_EFFECTIVE_TRACTION_VECTOR": raw},
              2: {"GEO_EFFECTIVE_TRACTION_VECTOR": [-10, 5]}}
    coordinates = {1: (0, 0, 0), 2: (0, -1, 0)}

    profile = members.profile(output, coordinates, members.quantity("ts"))

    assert profile["nodes"] == [2]
    assert profile["points"] == [[5.0, -1]]
