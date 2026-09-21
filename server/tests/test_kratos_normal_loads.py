"""Normal loads in the exported deck: the condition and the process that sizes it.

A `NormalLoad` (app/schemas.py) is a pressure normal to a free polyline -- an exposed
excavation face, a sloped boundary -- embedded into the section the same way a free
interface is (app/build.py:_embed_beams) and harvested the same way
(app/kratos.py:_normal_load_conditions), rather than by `_load_conditions`'s flat-
elevation scan. Its process, `ApplyNormalLoadTableProcess`, is read off a real working
example in Deltares/FEA-Tools (MiscellaneousTools/InterfaceInserter/
test_project_parameters.json), which this reproduces for the "Hydrostatic" case.
"""

from __future__ import annotations

import json

import pytest

from app import build, kratos
from app.schemas import MeshRequest, Project
from app.seed import seed_project
from tests import mdpa


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


def normal_load_project(fluid_pressure_type: str = "Hydrostatic", pressure: float = 0.0,
                        active: bool = True, dimension: int = 2,
                        points=None) -> Project:
    payload = seed_project().model_dump()
    payload.update(dimension=dimension, section_offset=20.0)
    payload["water"] = {"y": -3.5, "specific_weight": 10.0}
    payload["normal_loads"] = [{
        "id": "normal_1", "name": "River load", "kind": "normal",
        "points": points or [[8.0, 0.0], [8.0, -5.0], [16.0, -5.0]],
        "fluid_pressure_type": fluid_pressure_type, "pressure": pressure,
        "active": active,
    }]
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def hydrostatic(session):
    """A quadratic mesh, the sloped-then-flat exposed boundary of the docstring."""
    return kratos.export_project(normal_load_project(),
                                 MeshRequest(element_size=3.0, order=2))


def condition_block(deck: mdpa.Deck) -> mdpa.Block:
    return next(b for b in deck.conditions if "NormalLoad" in b.name)


def process_of(export: dict) -> dict:
    doc = json.loads(export["project_parameters"])
    processes = doc["stages"]["1_Stage"]["stage_settings"]["processes"]["loads_process_list"]
    return next(p for p in processes
               if p["process_name"] == "ApplyNormalLoadTableProcess")


# ── The condition ────────────────────────────────────────────────────────────

def test_a_quadratic_normal_load_writes_the_reference_deck_s_condition(hydrostatic):
    names = {block.name for block in mdpa.parse(hydrostatic["mdpa"]).conditions}
    assert "LineNormalLoadDiffOrderCondition2D3N" in names


def test_a_first_order_deck_writes_the_two_node_condition(session):
    export = kratos.export_project(normal_load_project(),
                                   MeshRequest(element_size=3.0, order=1))
    block = condition_block(mdpa.parse(export["mdpa"]))
    assert block.name == "LineNormalLoadCondition2D2N"
    assert all(len(nodes) == 2 for nodes in block.entries.values())


def test_the_condition_runs_the_whole_sloped_and_flat_polyline(hydrostatic):
    """Two segments in the fixture's polyline (down the face, across the floor), so a
    fine enough mesh must produce elements along both, not just the flat one."""
    deck = mdpa.parse(hydrostatic["mdpa"])
    ys = {deck.nodes[n][1] for nodes in condition_block(deck).entries.values()
          for n in nodes}
    assert any(y < -0.5 for y in ys), "elements along the vertical face"
    assert any(abs(y - (-5.0)) < 1e-6 for y in ys), "elements along the flat floor"


def test_the_normal_load_gets_its_own_sub_model_part(hydrostatic):
    deck = mdpa.parse(hydrostatic["mdpa"])
    part = deck.parts["River_load"]
    block = condition_block(deck)

    assert set(part.conditions) == set(block.entries)
    assert part.nodes == sorted({n for e in part.conditions for n in block.entries[e]})
    assert not part.elements


def test_an_inactive_normal_load_is_kept_in_the_project_but_not_exported(session):
    export = kratos.export_project(normal_load_project(active=False),
                                   MeshRequest(element_size=3.0, order=2))
    deck = mdpa.parse(export["mdpa"])

    assert not any("NormalLoad" in block.name for block in deck.conditions)
    assert "River_load" not in deck.parts


def test_a_3d_project_writes_no_normal_load_and_says_so(session):
    export = kratos.export_project(normal_load_project(dimension=3),
                                   MeshRequest(element_size=6.0, order=2))
    deck = mdpa.parse(export["mdpa"])

    assert not any("NormalLoad" in block.name for block in deck.conditions)
    assert any("normal load" in warning and "plane-strain" in warning
              for warning in export["warnings"])


# ── The process ──────────────────────────────────────────────────────────────

def test_a_hydrostatic_normal_load_writes_the_reference_process(hydrostatic):
    process = process_of(hydrostatic)
    assert process["python_module"] == "apply_normal_load_table_process"
    assert process["kratos_module"] == "KratosMultiphysics.GeoMechanicsApplication"
    parameters = process["Parameters"]
    assert parameters["model_part_name"] == "PorousDomain.River_load"
    assert parameters["variable_name"] == "NORMAL_CONTACT_STRESS"
    assert parameters["fluid_pressure_type"] == "Hydrostatic"
    assert parameters["gravity_direction"] == 1
    assert parameters["reference_coordinate"] == -3.5
    assert parameters["specific_weight"] == 10000.0


def test_the_magnitude_is_written_whichever_mode_the_load_is_in(session):
    """Hydrostatic derives its own pressure from the water level, but a magnitude the
    user gave still belongs in the deck rather than being dropped on the way out.
    Both branches share one parameter set, so `value` is a key the process declares."""
    for mode in ("Uniform", "Hydrostatic"):
        export = kratos.export_project(
            normal_load_project(fluid_pressure_type=mode, pressure=17.5),
            MeshRequest(element_size=3.0, order=2))
        parameters = process_of(export)["Parameters"]
        assert parameters["value"][0] == pytest.approx(17500.0), mode


def test_a_uniform_normal_load_writes_its_own_value_instead(session):
    export = kratos.export_project(
        normal_load_project(fluid_pressure_type="Uniform", pressure=25.0),
        MeshRequest(element_size=3.0, order=2))
    parameters = process_of(export)["Parameters"]

    assert parameters["fluid_pressure_type"] == "Uniform"
    assert parameters["value"][0] == pytest.approx(25000.0)
    assert "reference_coordinate" not in parameters
    # Only what the process declares: Kratos validates its parameters against its own
    # defaults and stops on a key it does not know, so nothing is invented here.
    assert set(parameters) == {"model_part_name", "variable_name", "active",
                               "fluid_pressure_type", "value", "table"}


def test_a_normal_load_applies_the_magnitude_it_was_given(session):
    """The default mode has to be the one that uses the number the user typed. A load
    that silently drops its magnitude -- which hydrostatic does, deriving the pressure
    from the water level instead -- is the bug this pins."""
    payload = normal_load_project().model_dump()
    payload["normal_loads"][0].pop("fluid_pressure_type")
    payload["normal_loads"][0]["pressure"] = 42.0
    export = kratos.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=3.0, order=2))

    parameters = process_of(export)["Parameters"]
    assert parameters["fluid_pressure_type"] == "Uniform"
    assert parameters["value"][0] == pytest.approx(42000.0)


def test_an_inactive_normal_load_writes_no_process(session):
    export = kratos.export_project(normal_load_project(active=False),
                                   MeshRequest(element_size=3.0, order=2))
    doc = json.loads(export["project_parameters"])
    processes = doc["stages"]["1_Stage"]["stage_settings"]["processes"]["loads_process_list"]
    assert not any(p["process_name"] == "ApplyNormalLoadTableProcess" for p in processes)


# ── The path a click through the GUI actually takes ──────────────────────────

def test_the_line_the_gui_drafts_by_default_exports_a_condition(session):
    """`App.NormalLoads.draft` (live/js/normal-loads.js) puts a line down the middle of
    the section, from the ground surface to half depth. That is what the first click on
    the new tool produces, so it is the one geometry that must not need editing first."""
    domain = seed_project().domain
    x = domain.x0 + (domain.x1 - domain.x0) * 0.5
    drafted = [[x, domain.y_top],
               [x, domain.y_top - (domain.y_top - domain.y_bottom) * 0.5]]
    export = kratos.export_project(
        normal_load_project(points=drafted, fluid_pressure_type="Uniform",
                            pressure=15.0),
        MeshRequest(element_size=3.0, order=2))

    block = condition_block(mdpa.parse(export["mdpa"]))
    assert block.name == "LineNormalLoadDiffOrderCondition2D3N"
    assert block.entries, "the drafted line has mesh on it"
    # The form's own defaults, so the first load anyone makes carries its magnitude.
    assert process_of(export)["Parameters"]["value"][0] == pytest.approx(15000.0)


def test_a_staged_project_applies_the_normal_load_in_every_stage(session):
    """A sheet pile splits the deck into an initial and a wall-installation stage. The
    water against an excavation face is there throughout -- nothing about a normal load
    waits for the wall -- so its process is repeated in both, the way an ordinary load's
    is (see kratos_processes' module docstring)."""
    payload = normal_load_project().model_dump()
    payload["beam_sections"] = [{"id": "az26", "name": "AZ 26-700", "E": 2.1e8,
                                 "nu": 0.3, "area": 0.0198, "inertia": 5.52e-4,
                                 "density": 7850.0, "spacing": 1.0}]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -10.0]], "active": True}]
    export = kratos.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=3.0, order=2))

    doc = json.loads(export["project_parameters"])
    assert doc["orchestrator"]["settings"]["execution_list"] == \
        ["1_Initial_stage", "2_Wall_installation"]
    for stage in ("1_Initial_stage", "2_Wall_installation"):
        processes = (doc["stages"][stage]["stage_settings"]["processes"]
                    ["loads_process_list"])
        applied = [p for p in processes
                  if p["process_name"] == "ApplyNormalLoadTableProcess"]
        assert len(applied) == 1, f"exactly one normal load in {stage}"
        assert applied[0]["Parameters"]["model_part_name"] == "PorousDomain.River_load"
