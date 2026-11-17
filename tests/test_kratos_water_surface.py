"""The water standing on the ground, added to the deck as a normal load that presses on it.

A Hydrostatic or Phreatic_Multi_Line water pressure condition whose level is above the
soil somewhere has water standing on the ground there, and that water weighs on it: on
the ground surface, on the floor of a pit and on the faces dug into it, and on a wall the
water stands against. The export adds that load itself
(core/kratos/writer.py:_water_surface_loads), stage by stage, as Kratos'
`ApplyNormalLoadTableProcess` -- the same process a drawn `NormalLoad` is written as.

What these hold it to: it is there where the water is above the ground and nowhere else;
it follows the surface each stage has; and it always presses on what it stands on, never
pulls, however the mesh or the wall happens to be ordered.
"""

from __future__ import annotations

import json

import pytest

from core.geometry import solid_model
from core.kratos import writer
from core.model.schemas import MeshRequest, Project
from core.model.templates import seed_project
from tests import mdpa
from tests.models import excavation

MESH = MeshRequest(element_size=3.0, order=2)
GAMMA = 10_000.0


@pytest.fixture(scope="module", autouse=True)
def gmsh_session():
    with solid_model.session():
        yield


def section(**water) -> Project:
    """The seed's ground, 25 m wide with its surface at 0, as a 2D section, with its
    supports and one water pressure condition on the whole soil."""
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=20.0)
    payload["boundary_conditions"] = [
        c for c in payload["boundary_conditions"] if c["kind"] == "displacement"
    ] + [{"id": "pp", "name": "Pore pressure", "kind": "water_pressure", "on": "domain",
          **water}]
    return Project.model_validate(payload)


def hydrostatic(level: float) -> Project:
    return section(fluid_pressure_type="Hydrostatic", reference_coordinate=level)


def surface_processes(export: dict, stage: str | None = None) -> list[dict]:
    doc = json.loads(export["project_parameters"])
    stage = stage or next(iter(doc["stages"]))
    processes = doc["stages"][stage]["stage_settings"]["processes"]["loads_process_list"]
    return [p["Parameters"] for p in processes
            if p["process_name"] == "ApplyNormalLoadTableProcess"
            and "_on_surface" in p["Parameters"]["model_part_name"]]


def surface_rows(deck: mdpa.Deck, part: str) -> list[list[tuple[float, float]]]:
    """The rows of a surface part's conditions, as the coordinates of their nodes."""
    block = next(b for b in deck.conditions
                 if set(deck.parts[part].conditions) <= set(b.entries))
    return [[deck.nodes[n][:2] for n in block.entries[c]]
            for c in deck.parts[part].conditions]


def inside(point, corners) -> bool:
    (ax, ay), (bx, by), (cx, cy) = corners
    px, py = point
    d1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    d2 = (cx - bx) * (py - by) - (cy - by) * (px - bx)
    d3 = (ax - cx) * (py - cy) - (ay - cy) * (px - cx)
    return (d1 >= 0 and d2 >= 0 and d3 >= 0) or (d1 <= 0 and d2 <= 0 and d3 <= 0)


def left_of(row) -> tuple[float, float]:
    """A point a hair to the left of a condition's first two nodes, which is where Kratos
    presses it."""
    (ax, ay), (bx, by) = row[0], row[1]
    reach = 1e-3
    length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    return ((ax + bx) / 2 - (by - ay) / length * reach,
            (ay + by) / 2 + (bx - ax) / length * reach)


def soil_triangles(deck: mdpa.Deck, parts: set[str]) -> list:
    elements = {e for name in parts for e in deck.parts[name].elements}
    return [[deck.nodes[n][:2] for n in nodes[:3]]
            for block in deck.elements if "UPw" in block.name and "Interface" not in block.name
            for e, nodes in block.entries.items() if e in elements]


# ── Where it is ──────────────────────────────────────────────────────────────

def test_water_above_the_ground_presses_on_the_whole_surface():
    export = writer.export_project(hydrostatic(2.0), MESH)
    deck = mdpa.parse(export["mdpa"])

    rows = surface_rows(deck, "Pore_pressure_on_surface")
    assert rows and all(abs(y) < 1e-9 for row in rows for _, y in row)
    assert min(x for row in rows for x, _ in row) == pytest.approx(0.0)
    assert max(x for row in rows for x, _ in row) == pytest.approx(25.0)
    (process,) = surface_processes(export)
    assert process["fluid_pressure_type"] == "Hydrostatic"
    assert process["reference_coordinate"] == 2.0
    assert process["specific_weight"] == GAMMA
    assert any("stands above the ground" in note for note in export["notes"])


def test_the_surface_load_presses_down_into_the_ground():
    deck = mdpa.parse(writer.export_project(hydrostatic(2.0), MESH)["mdpa"])
    for row in surface_rows(deck, "Pore_pressure_on_surface"):
        assert left_of(row)[1] < 0.0, row


def test_water_below_the_ground_adds_nothing():
    export = writer.export_project(hydrostatic(-3.5), MESH)
    assert surface_processes(export) == []
    assert not any("_on_surface" in name for name in mdpa.parse(export["mdpa"]).parts)
    assert not any("stands above the ground" in note for note in export["notes"])


def test_a_uniform_water_pressure_has_no_level_and_adds_nothing():
    export = writer.export_project(section(fluid_pressure_type="Uniform", value=-5_000.0),
                                   MESH)
    assert surface_processes(export) == []


def test_a_phreatic_multi_line_loads_only_where_it_is_above_the_ground():
    """Above the ground left of x = 4, below it to the right. Kratos has no multi-line
    normal load, so the part carries the first stretch of the line and the nodes under
    the second are a node part with theirs."""
    project = section(fluid_pressure_type="Phreatic_Multi_Line",
                      x_coordinates=[-10.0, 2.0, 6.0, 100.0],
                      y_coordinates=[2.0, 1.0, -1.0, -1.0])
    export = writer.export_project(project, MESH)
    deck = mdpa.parse(export["mdpa"])

    rows = surface_rows(deck, "Pore_pressure_on_surface")
    assert rows
    # Every edge has a node under the water; none lies wholly past where it meets the
    # ground at x = 4.
    assert all(min(x for x, _ in row) < 4.0 for row in rows)
    first, second = surface_processes(export)
    assert first["model_part_name"] == "PorousDomain.Pore_pressure_on_surface"
    assert first["fluid_pressure_type"] == "Phreatic_Line"
    assert first["first_reference_coordinate"] == [-10.0, 2.0, 0.0]
    assert first["second_reference_coordinate"] == [2.0, 1.0, 0.0]
    assert second["model_part_name"] == "PorousDomain.Pore_pressure_on_surface_stretch_2"
    assert second["first_reference_coordinate"] == [2.0, 1.0, 0.0]
    assert second["second_reference_coordinate"] == [6.0, -1.0, 0.0]
    stretch = deck.parts["Pore_pressure_on_surface_stretch_2"]
    assert stretch.nodes and not stretch.conditions
    assert all(2.0 < deck.nodes[n][0] <= 6.0 for n in stretch.nodes)


def test_a_phreatic_line_drawn_as_a_line_puts_its_water_in_a_pit():
    """The GUI draws a phreatic line as a condition on a line. Its level is the free
    water's all the same: in a pit dug to -5 left of x = 4, with the line at -2, the
    water stands on the pit's floor and on the dug face up to -2, and presses on both."""
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=0.0,
                   domain={"x0": 0, "x1": 20, "z0": -10, "z1": 10,
                           "y_top": 0, "y_bottom": -10})
    material = payload["layers"][0]["mat"]
    payload["layers"] = [{"id": "L1", "name": "Top", "mat": material, "top": 0, "bottom": -5},
                         {"id": "L2", "name": "Bottom", "mat": material, "top": -5,
                          "bottom": -10}]
    payload["lines"] = [{"id": "cut", "name": "Cut", "points": [[4, 0], [4, -5]]}]
    payload["bodies"] = [{"id": "pit", "name": "Pit", "layer": "L1", "point": [2, -2.5]},
                         {"id": "rest", "name": "Rest", "layer": "L1", "point": [12, -2.5]}]
    payload["boundary_conditions"] = [
        c for c in payload["boundary_conditions"] if c["kind"] == "displacement"
    ] + [{"id": "phreatic", "name": "Phreatic line", "kind": "water_pressure", "on": "line",
          "points": [[0, -2], [20, -2]], "fluid_pressure_type": "Phreatic_Multi_Line",
          "x_coordinates": [0, 20], "y_coordinates": [-2, -2]}]
    payload["stages"] = [{"id": "initial", "name": "Initial", "deactivate": ["soil_L1__pit"]}]
    export = writer.export_project(Project.model_validate(payload), MESH)
    deck = mdpa.parse(export["mdpa"])

    rows = surface_rows(deck, "Phreatic_line_on_surface")
    floor = [row for row in rows if all(abs(y + 5.0) < 1e-9 for _, y in row)]
    face = [row for row in rows if all(abs(x - 4.0) < 1e-9 for x, _ in row)]
    assert floor and face and len(floor) + len(face) == len(rows)
    assert min(x for row in floor for x, _ in row) == pytest.approx(0.0)
    assert max(y for row in face for _, y in row) == pytest.approx(-2.0)
    assert all(left_of(row)[1] < -5.0 for row in floor)
    assert all(left_of(row)[0] > 4.0 for row in face)
    (process,) = surface_processes(export)
    assert process["fluid_pressure_type"] == "Phreatic_Line"


# ── Stage by stage ───────────────────────────────────────────────────────────

def dug(flip_wall: bool = False) -> Project:
    """The staged excavation with its drawn water loads taken out, so the water on the
    floor of the pit is the export's own. Its water stands at -1 everywhere; the pit is
    dug to -2, -4.5 and -7, left of the wall at x = 6."""
    data = excavation.excavation_project().model_dump()
    data["normal_loads"] = []
    for stage in data["stages"]:
        stage["activate"] = [k for k in stage["activate"] if not k.startswith("water_")]
        stage["deactivate"] = [k for k in stage["deactivate"] if not k.startswith("water_")]
    if flip_wall:
        data["beams"][0]["points"] = data["beams"][0]["points"][::-1]
    return Project.model_validate(data)


@pytest.fixture(scope="module")
def dug_export():
    return writer.export_project(dug())


def stage_names(export: dict) -> list[str]:
    return json.loads(export["project_parameters"])["orchestrator"]["settings"][
        "execution_list"]


def test_the_ground_above_the_water_carries_none_until_the_pit_is_dug(dug_export):
    for stage in stage_names(dug_export)[:3]:
        assert surface_processes(dug_export, stage) == [], stage


def test_each_lift_has_the_surface_of_its_own_stage(dug_export):
    """One part per surface: the first lift's floor, then the second's, then the third's,
    each in the stages that have that surface and no other."""
    applied = {stage: [p["model_part_name"] for p in surface_processes(dug_export, stage)]
               for stage in stage_names(dug_export)[3:]}
    assert applied == {
        "4_First_excavation": ["PorousDomain.Pore_pressure_on_surface"],
        "5_Strut_installation": ["PorousDomain.Pore_pressure_on_surface"],
        "6_Second_excavation": ["PorousDomain.Pore_pressure_on_surface_2"],
        "7_Third_excavation": ["PorousDomain.Pore_pressure_on_surface_3"],
    }
    deck = mdpa.parse(dug_export["mdpa"])
    for part, floor in (("Pore_pressure_on_surface", -2.0),
                        ("Pore_pressure_on_surface_2", -4.5),
                        ("Pore_pressure_on_surface_3", -7.0)):
        points = [p for row in surface_rows(deck, part) for p in row]
        assert min(y for _, y in points) == pytest.approx(floor), part
        # The pit's floor and the face of the wall, up to the water; not the ground
        # behind the wall, which is above it.
        assert all(x <= 6.0 + 1e-9 and y <= -1.0 + 1e-9 for x, y in points), part
        assert any(abs(x - 6.0) < 1e-9 and y > floor + 0.1 for x, y in points), part


def test_the_pit_water_presses_on_the_floor_and_the_wall_it_stands_on(dug_export):
    """Down into the floor, and towards the ground behind the wall: never up out of the
    floor or into the pit, which is the way an edge taken in the dug lift's order would
    press."""
    deck = mdpa.parse(dug_export["mdpa"])
    for part in ("Pore_pressure_on_surface", "Pore_pressure_on_surface_2",
                 "Pore_pressure_on_surface_3"):
        for row in surface_rows(deck, part):
            on_wall = abs(row[0][0] - 6.0) < 1e-9 and abs(row[1][0] - 6.0) < 1e-9
            px, py = left_of(row)
            if on_wall:
                assert px > 6.0, row
            else:
                assert py < row[0][1], row


def test_the_soil_edges_are_pressed_into_the_soil_that_is_there(dug_export):
    """Probed against the mesh rather than the drawing: left of every floor edge is an
    element of the soil left after the lift is dug."""
    deck = mdpa.parse(dug_export["mdpa"])
    soil = {name for name in deck.parts if name.startswith("Soil_")}
    remaining = soil - {"Soil_Top_lift1"}
    triangles = soil_triangles(deck, remaining)
    for row in surface_rows(deck, "Pore_pressure_on_surface"):
        if abs(row[0][0] - 6.0) < 1e-9 and abs(row[1][0] - 6.0) < 1e-9:
            continue
        assert any(inside(left_of(row), t) for t in triangles), row


def test_a_wall_drawn_the_other_way_still_has_the_water_pushing_it():
    """The wall's condition can only take the wall's own order, which now has the pit on
    its left: so the pressure is written negative, node by node, at the water's depth."""
    export = writer.export_project(dug(flip_wall=True))
    deck = mdpa.parse(export["mdpa"])

    processes = surface_processes(export, "4_First_excavation")
    assert processes[0]["fluid_pressure_type"] == "Hydrostatic"
    turned = processes[1:]
    assert turned and all(p["fluid_pressure_type"] == "Uniform" for p in turned)
    for p in turned:
        (node,) = deck.parts[p["model_part_name"].split(".")[1]].nodes
        x, y = deck.nodes[node][:2]
        assert x == pytest.approx(6.0)
        assert p["value"][0] == pytest.approx(-GAMMA * (-1.0 - y))
    assert any("node by node" in note for note in export["notes"])


def test_the_water_loads_drawn_by_hand_are_the_ones_used():
    """The staged excavation draws its own water load per lift; where one is, the export
    adds none of its own on top."""
    export = writer.export_project(excavation.excavation_project())
    for stage in stage_names(export):
        assert surface_processes(export, stage) == [], stage
    assert not any("stands above the ground" in note for note in export["notes"])


def test_a_stage_with_the_water_switched_off_has_no_water_on_the_ground():
    data = dug().model_dump()
    data["stages"][-1]["deactivate"] = [*data["stages"][-1]["deactivate"], "pore_pressure"]
    export = writer.export_project(Project.model_validate(data))
    assert surface_processes(export, "7_Third_excavation") == []
    assert surface_processes(export, "6_Second_excavation")


def test_a_3d_project_adds_none():
    payload = hydrostatic(2.0).model_dump()
    payload["dimension"] = 3
    export = writer.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=8.0, order=1))
    assert surface_processes(export) == []
