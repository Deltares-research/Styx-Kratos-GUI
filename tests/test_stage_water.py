"""The water of each stage: its phreatic line, each soil's water, the values of its
conditions, and the prescribed fluxes.

A stage may name its phreatic line (`Stage.phreatic_line`), so a line drawn as a head line
is the phreatic line from then on and the one before is a head line there. It may give a
soil another water (`Stage.soil_water`) -- a head line, interpolated, dry, or the phreatic
line again -- and a condition another value (`Stage.condition_values`). Each holds from
that stage on, as `activate` does. `core.model.stages.water_in` resolves them, and the
deck writes what differs between stages as processes of their own.
"""

from __future__ import annotations

import json

import pytest

from core.geometry import solid_model
from core.kratos import condition_checks, writer
from core.kratos.writer import ExportError
from core.model import stages
from core.model.schemas import (DRY, INTERPOLATE, PHREATIC as BACK, FluxCondition, Project,
                                SeepageCondition)
from tests import mdpa
from tests.models.muskat import HEADS, LEFT_LEVEL, head, muskat
from tests.models.muskat import FLOW
from tests.test_kratos_soil_water import HEAD, LEVEL, MESH, PHREATIC, layered, water


@pytest.fixture(scope="module")
def gmsh_session():
    with solid_model.session():
        yield


UNIFORM = {"id": "clay_pressure", "name": "Clay pressure", "kind": "water_pressure",
           "on": "part", "part": "soil_L2", "fluid_pressure_type": "Uniform",
           "value": -10_000.0}


def staged(conditions=(PHREATIC, HEAD), water=None, *later: dict, **first) -> Project:
    """`layered` in stages, with `conditions` and the soils' `water`: "First", then one
    stage after another for each of `later`, each the fields that stage has; `first` is
    the first stage's. Checked with its stages, as two phreatic lines are a project only
    where a stage names one."""
    p = layered(()).model_dump()
    p["boundary_conditions"] += [dict(c) for c in conditions]
    p["soil_water"] = water or {}
    p["stages"] = [{"id": "s1", "name": "First", **first}]
    for number, fields in enumerate(later, start=2):
        p["stages"].append({"id": f"s{number}", "name": f"Stage {number}",
                            "parent": f"s{number - 1}", **fields})
    return Project.model_validate(p)


# ── The water of a stage ─────────────────────────────────────────────────────

def test_the_model_as_built_has_the_line_typed_phreatic():
    water = stages.water_in(layered(), None)
    assert water.phreatic is not None and water.phreatic.id == "phreatic"
    assert [line.id for line in water.head_lines()] == ["head"]


def test_a_stage_makes_another_line_its_phreatic_line_from_then_on():
    project = staged((PHREATIC, HEAD), None, {"phreatic_line": "head"}, {})
    assert stages.water_in(project, "s1").phreatic.id == "phreatic"
    for stage in ("s2", "s3"):
        water = stages.water_in(project, stage)
        assert water.phreatic.id == "head"
        assert water.phreatic.fluid_pressure_type == "Phreatic_Multi_Line"
        assert water.conditions["phreatic"].fluid_pressure_type == "Head_Line"
        assert [line.id for line in water.head_lines()] == ["phreatic"]


def test_a_stage_that_names_its_line_has_no_two_phreatic_lines():
    """Two lines typed phreatic, both on: one too many, unless a stage names one."""
    second = dict(PHREATIC, id="second", name="Second", y_coordinates=[-3.0, -3.0])
    with pytest.raises(ValueError, match="both on in stage 'First'"):
        staged((PHREATIC, second))
    project = staged((PHREATIC, second), None, phreatic_line="second")
    assert stages.water_in(project, "s1").phreatic.id == "second"


def test_a_named_line_switched_off_leaves_the_stage_no_phreatic_line():
    project = staged((PHREATIC, HEAD), None, {"deactivate": ["head"]},
                     phreatic_line="head")
    assert stages.water_in(project, "s2").phreatic is None


def test_each_stage_gives_its_soils_their_water_over_the_stage_before():
    project = staged((PHREATIC, HEAD), {"soil_L3": "head"},
                     {"soil_water": {"soil_L3": BACK, "soil_L1": DRY}},
                     {"soil_water": {"soil_L2": INTERPOLATE}})
    assert stages.water_in(project, "s1").soil_water == {"soil_L3": "head"}
    assert stages.water_in(project, "s2").soil_water == {"soil_L1": DRY}
    assert stages.water_in(project, "s3").soil_water == {"soil_L1": DRY,
                                                         "soil_L2": INTERPOLATE}


def test_a_soil_that_takes_the_stage_s_phreatic_line_takes_it_as_every_soil_does():
    project = staged((PHREATIC, HEAD), {"soil_L3": "head"}, phreatic_line="head")
    assert stages.water_in(project, "s1").soil_water == {}


def test_a_stage_s_values_hold_from_then_on():
    project = staged((PHREATIC, LEVEL), None,
                     {"condition_values": {"level": {"reference_coordinate": -6.0}}}, {})
    level = [stages.water_in(project, stage).conditions["level"].reference_coordinate
             for stage in ("s1", "s2", "s3")]
    assert level == [-3.0, -6.0, -6.0]


def test_a_stage_may_move_its_phreatic_line():
    lowered = {"phreatic": {"y_coordinates": [-4.0, -4.0]}}
    project = staged((PHREATIC,), None, {"condition_values": lowered})
    assert stages.water_in(project, "s2").phreatic.y_coordinates == [-4.0, -4.0]
    assert stages.water_in(project, "s1").phreatic.y_coordinates == [-1.0, -1.0]


# ── What a stage may say ─────────────────────────────────────────────────────

def test_a_stage_changes_values_not_what_a_condition_is():
    with pytest.raises(ValueError, match="cannot change; it can change value"):
        staged((PHREATIC, LEVEL), None,
               condition_values={"level": {"fluid_pressure_type": "Uniform"}})


def test_a_support_has_no_value_a_stage_can_change():
    with pytest.raises(ValueError, match="switch it on or off instead"):
        staged((PHREATIC,), None, condition_values={"fixed_bottom": {"fixed": [1, 1, 1]}})


def test_a_value_that_breaks_its_condition_is_refused_in_its_stage():
    with pytest.raises(ValueError, match="in stage 's1'.*must increase"):
        staged((PHREATIC,), None,
               condition_values={"phreatic": {"x_coordinates": [25.0, 0.0]}})


def test_what_a_deleted_line_soil_or_condition_took_goes_with_it():
    project = staged((PHREATIC, HEAD), None, phreatic_line="gone",
                     soil_water={"soil_L9": DRY, "soil_L1": "gone", "soil_L2": DRY},
                     condition_values={"gone": {"value": 1.0}})
    first = project.stages[0]
    assert first.phreatic_line is None
    assert first.soil_water == {"soil_L2": DRY}
    assert first.condition_values == {}


def test_a_water_line_cannot_be_called_dry():
    with pytest.raises(ValueError, match="water line cannot be called 'dry'"):
        layered((PHREATIC, dict(HEAD, id=DRY)))


def test_a_soil_may_be_dry_in_the_model_as_built():
    assert layered(soil_water={"soil_L1": DRY}).soil_water == {"soil_L1": DRY}


def test_a_flux_is_on_a_face_or_a_line():
    FluxCondition(id="rain", name="Rain", on="face", face="top", value=1e-6)
    with pytest.raises(ValueError):
        FluxCondition(id="rain", name="Rain", on="point", points=[(1.0, 1.0)])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="needs points"):
        FluxCondition(id="rain", name="Rain", on="line")
    with pytest.raises(ValueError, match="non-finite"):
        FluxCondition(id="rain", name="Rain", on="face", face="top", value=float("nan"))


def test_a_head_line_a_stage_makes_phreatic_acts_somewhere():
    said = condition_checks.warnings(staged((PHREATIC, HEAD), None, {"phreatic_line": "head"}))
    assert not any("no soil does" in line for line in said)


def test_a_flux_in_3d_is_left_out_and_said():
    project = layered((PHREATIC, {"id": "rain", "name": "Rain", "kind": "flux",
                                  "on": "face", "face": "top", "value": 1e-6}),
                      dimension=3)
    assert any("'Rain'" in line and "2D section only" in line
               for line in condition_checks.warnings(project))


# ── The deck ─────────────────────────────────────────────────────────────────

def parts_and_types(export: dict, stage: str) -> list[tuple[str, str]]:
    return [(p["model_part_name"], p.get("fluid_pressure_type", "Uniform"))
            for p in water(export, stage)]


def test_the_phreatic_line_a_stage_names_is_the_whole_soil_s_there(gmsh_session):
    """Before: the drawn phreatic line on the whole soil and the head on the aquifer.
    After: the head line on the whole soil, and the old phreatic line nowhere, as no soil
    takes it."""
    project = staged((PHREATIC, HEAD), {"soil_L3": "head"}, {"phreatic_line": "head"})
    export = writer.export_project(project, MESH)
    first, second = water(export, "1_First"), water(export, "2_Stage_2")
    assert [(p["model_part_name"], p["y_coordinates"]) for p in first] == [
        ("PorousDomain", [-1.0, -1.0]), ("PorousDomain.Aquifer", [1.0, 3.0])]
    assert [(p["model_part_name"], p["y_coordinates"]) for p in second] == [
        ("PorousDomain", [1.0, 3.0])]


def test_a_dry_soil_is_held_at_zero_in_the_stages_it_is_dry(gmsh_session):
    project = staged((PHREATIC, HEAD), {"soil_L1": DRY},
                     {"soil_water": {"soil_L1": BACK}})
    export = writer.export_project(project, MESH)
    dry = {"model_part_name": "PorousDomain.Sand", "variable_name": "WATER_PRESSURE",
           "is_fixed": True, "value": 0.0, "table": 0}
    assert water(export, "1_First")[-1] == dry
    assert dry not in water(export, "2_Stage_2")


def test_a_value_a_stage_gives_is_written_in_that_stage(gmsh_session):
    project = staged((PHREATIC, UNIFORM), None,
                     {"condition_values": {"clay_pressure": {"value": -25_000.0}}})
    export = writer.export_project(project, MESH)
    values = {stage: [p["value"] for p in water(export, stage)
                      if p["model_part_name"] == "PorousDomain.Clay"]
              for stage in ("1_First", "2_Stage_2")}
    assert values == {"1_First": [-10_000.0], "2_Stage_2": [-25_000.0]}


def test_a_soil_s_own_uniform_pressure_beats_the_head_line_it_takes(gmsh_session):
    on_aquifer = dict(UNIFORM, id="aquifer_pressure", part="soil_L3")
    export = writer.export_project(
        layered((PHREATIC, HEAD, on_aquifer), soil_water={"soil_L3": "head"}), MESH)
    only = next(iter(json.loads(export["project_parameters"])["stages"]))
    assert parts_and_types(export, only) == [("PorousDomain", "Phreatic_Multi_Line"),
                                             ("PorousDomain.Aquifer", "Phreatic_Multi_Line"),
                                             ("PorousDomain.Aquifer", "Uniform")]


def test_an_interpolated_soil_is_interpolated_in_its_stages_only(gmsh_session):
    project = staged((PHREATIC, HEAD), {"soil_L3": "head", "soil_L2": INTERPOLATE},
                     {"soil_water": {"soil_L2": BACK}})
    export = writer.export_project(project, MESH)
    assert ("PorousDomain.Clay", "Interpolate_Line") in parts_and_types(export, "1_First")
    assert ("PorousDomain.Clay", "Interpolate_Line") not in parts_and_types(export,
                                                                            "2_Stage_2")


# ── A prescribed flux ────────────────────────────────────────────────────────

RAIN = FluxCondition(id="rain", name="Rain", on="face", face="left", value=2.0e-6)


def fluxes(export: dict, stage: str) -> list[dict]:
    loads = json.loads(export["project_parameters"])["stages"][stage]["stage_settings"][
        "processes"]["loads_process_list"]
    return [p["Parameters"] for p in loads
            if p["Parameters"].get("variable_name") == "NORMAL_FLUID_FLUX"]


def test_a_flux_in_a_flow_deck_is_the_flow_elements_own_condition(gmsh_session):
    export = writer.export_project(muskat(conditions=[HEADS[1], RAIN]))
    deck = mdpa.parse(export["mdpa"])
    assert {block.name for block in deck.conditions} == {"PwNormalFluxCondition2D2N"}
    rain = deck.parts["Rain"]
    assert rain.nodes and len(rain.conditions) == len(rain.nodes) - 1
    assert fluxes(export, "1_Flow") == [{
        "model_part_name": "PorousDomain.Rain", "variable_name": "NORMAL_FLUID_FLUX",
        "is_fixed": False, "value": -2.0e-6, "table": 0}]


def test_a_flux_in_a_flow_deck_is_no_seepage_face(gmsh_session):
    """A flux is no face the seepage strategy may open: written as one too, its nodes
    were held at zero pressure where the water stood above them, a drain."""
    face = SeepageCondition(id="exit", name="Exit", on="face", face="right")
    for conditions in ([HEADS[1], RAIN], [HEADS[1], RAIN, face]):
        export = writer.export_project(muskat(conditions=conditions))
        stage = json.loads(export["project_parameters"])["stages"]["1_Flow"][
            "stage_settings"]
        seepage = [p["Parameters"]["model_part_name"]
                   for p in stage["processes"]["loads_process_list"]
                   if p["process_name"] == "ApplySeepageBoundaryProcess"]
        assert seepage == (["PorousDomain.Exit"] if face in conditions else [])
        assert (stage["solver_settings"]["strategy_type"]
                == "newton_raphson_with_seepage") == (face in conditions)
        assert not any("Rain" in w for w in export["warnings"]
                       if "seepage faces have" in w)


def test_a_flux_in_a_coupled_deck_is_the_coupled_elements_condition(gmsh_session):
    top = {"id": "rain", "name": "Rain", "kind": "flux", "on": "face", "face": "top",
           "value": 1.0e-7}
    export = writer.export_project(layered((PHREATIC, top)), MESH)
    assert "UPwNormalFluxCondition2D2N" in {block.name
                                            for block in mdpa.parse(export["mdpa"]).conditions}


def test_a_flux_drawn_along_the_ground_is_one_part_of_its_conditions(gmsh_session):
    """A drawn line is embedded in the mesh, as a seepage line is; the flux is its edge
    conditions alone, not a node part of the same name beside them."""
    along = {"id": "rain", "name": "Rain", "kind": "flux", "on": "line",
             "points": [[5.0, 0.0], [20.0, 0.0]], "value": 1.0e-7}
    export = writer.export_project(layered((PHREATIC, along)), MESH)
    deck = mdpa.parse(export["mdpa"])
    rain = deck.parts["Rain"]
    assert rain.conditions and len(rain.conditions) == len(rain.nodes) - 1
    assert not any(name.startswith("Rain_") for name in deck.parts)
    assert [p["model_part_name"] for p in fluxes(export, next(iter(json.loads(
        export["project_parameters"])["stages"])))] == ["PorousDomain.Rain"]


def test_a_flux_takes_the_value_its_stage_gives_it(gmsh_session):
    later = FLOW.model_copy(update={"id": "later", "name": "Later", "parent": "flow",
                                    "condition_values": {"rain": {"value": 5.0e-6}}})
    export = writer.export_project(muskat(conditions=[HEADS[1], RAIN],
                                          stages=[FLOW, later]))
    assert [p["value"] for p in fluxes(export, "1_Flow")] == [-2.0e-6]
    assert [p["value"] for p in fluxes(export, "2_Later")] == [-5.0e-6]


def test_a_flux_a_stage_switches_off_is_not_in_it(gmsh_session):
    later = FLOW.model_copy(update={"id": "later", "name": "Later", "parent": "flow",
                                    "deactivate": ["rain"]})
    export = writer.export_project(muskat(conditions=[head("left_head", "left", LEFT_LEVEL),
                                                      HEADS[1], RAIN],
                                          stages=[FLOW, later]))
    assert fluxes(export, "1_Flow") and not fluxes(export, "2_Later")


def inner_edges(deck: mdpa.Deck, part: str) -> tuple[int, int]:
    """How many of `part`'s conditions have an element on each side, and how many it
    has: an edge two soil elements share is inside the soil."""
    shared: dict[frozenset[int], int] = {}
    for block in deck.elements:
        for row in block.entries.values():
            for a, b in zip(row[:3], row[1:3] + row[:1]):
                key = frozenset((a, b))
                shared[key] = shared.get(key, 0) + 1
    rows = [row for block in deck.conditions for cid, row in block.entries.items()
            if cid in deck.parts[part].conditions]
    return sum(shared.get(frozenset(row[:2]), 0) == 2 for row in rows), len(rows)


def test_a_flux_line_across_a_soil_is_a_line_source_in_it(gmsh_session):
    """Kratos' normal flux condition reads its edge alone, so inside the soil it is a
    line source: every mesh edge of the line is a condition, with soil on both sides."""
    across = {"id": "pipe", "name": "Pipe", "kind": "flux", "on": "line",
              "points": [[5.0, -2.0], [20.0, -2.0]], "value": 1.0e-7}
    export = writer.export_project(layered((PHREATIC, across)), MESH)
    deck = mdpa.parse(export["mdpa"])
    pipe = deck.parts["Pipe"]
    assert pipe.conditions and len(pipe.conditions) == len(pipe.nodes) - 1
    assert all(deck.nodes[n][1] == pytest.approx(-2.0) for n in pipe.nodes)
    assert sorted(deck.nodes[n][0] for n in pipe.nodes)[::len(pipe.nodes) - 1] \
        == pytest.approx([5.0, 20.0])
    inside, every = inner_edges(deck, "Pipe")
    assert inside == every
    assert [p["value"] for p in fluxes(export, next(iter(json.loads(
        export["project_parameters"])["stages"])))] == [-1.0e-7]


def test_a_flux_line_between_two_soils_is_on_their_shared_edges(gmsh_session):
    between = {"id": "seam", "name": "Seam", "kind": "flux", "on": "line",
               "points": [[0.0, -5.0], [25.0, -5.0]], "value": 1.0e-7}
    deck = mdpa.parse(writer.export_project(layered((PHREATIC, between)), MESH)["mdpa"])
    inside, every = inner_edges(deck, "Seam")
    assert every and inside == every
    assert all(deck.nodes[n][1] == pytest.approx(-5.0) for n in deck.parts["Seam"].nodes)


def test_a_flux_line_partly_on_the_boundary_takes_both_stretches(gmsh_session):
    """Down the ground and on into the soil: the edges on the boundary and the ones
    inside it are one flux."""
    bent = {"id": "bent", "name": "Bent", "kind": "flux", "on": "line",
            "points": [[5.0, 0.0], [10.0, 0.0], [10.0, -4.0]], "value": 1.0e-7}
    deck = mdpa.parse(writer.export_project(layered((PHREATIC, bent)), MESH)["mdpa"])
    inside, every = inner_edges(deck, "Bent")
    assert 0 < inside < every


def test_a_quadratic_flux_line_through_the_soil_has_three_node_conditions(gmsh_session):
    across = {"id": "pipe", "name": "Pipe", "kind": "flux", "on": "line",
              "points": [[5.0, -2.0], [20.0, -2.0]], "value": 1.0e-7}
    deck = mdpa.parse(writer.export_project(
        layered((PHREATIC, across)), MESH.model_copy(update={"order": 2}))["mdpa"])
    rows = [row for block in deck.conditions for cid, row in block.entries.items()
            if cid in deck.parts["Pipe"].conditions]
    assert rows and all(len(row) == 3 for row in rows)
    assert {block.name for block in deck.conditions
            if set(block.entries) & set(deck.parts["Pipe"].conditions)} \
        == {"UPwNormalFluxCondition2D3N"}


def test_a_seepage_line_through_the_soil_is_still_refused(gmsh_session):
    """The seepage strategy lets water out only where there is no soil beyond the face,
    so only a flux may run through the soil."""
    through = {"id": "seep", "name": "Seep", "kind": "seepage", "on": "line",
               "points": [[5.0, -2.0], [20.0, -2.0]]}
    flow = layered((PHREATIC, through), stages=[FLOW.model_dump()])
    with pytest.raises(ExportError, match="A seepage face is on the soil's outer"):
        writer.export_project(flow, MESH)
