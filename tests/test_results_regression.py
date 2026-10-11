"""Reading a real Kratos run back, end to end -- when Kratos is installed.

The test model (`tests/models/excavation.py`) is calculated once per session
(`tests/results_run.py`) and read through `core.results.runs` the way the GUI reads it. Without
Kratos on the machine every case here skips and says why; nothing about a run is
committed.

What a real run says that a parser fed hand-written literals cannot:

*   **Eight soil bodies and two structures**, so the join from GiD's anonymous mesh
    blocks (`Kratos_Triangle2D6_Mesh_2`) back to the deck's named parts is exercised on
    names nobody could have guessed from the mesh.
*   **A construction sequence**, so "this part is not in this stage" appears in both of
    its forms: the wall, which does not exist yet in stage 1, and the three excavation
    lifts, which have been dug away by stage 7.
*   **Interfaces**, which the GiD writer emits in no stage whatsoever. A postprocessor
    that reported them as demolished would be lying about the model.
*   **A second, independent writer of the same numbers.** The deck's `json_output`
    processes write the wall's displacements to their own files, so what the `.post.res`
    parser says can be checked against something that is not the `.post.res` parser.

The checks are ones any correct run of this model passes: they pin how a run is read,
and that the physics is the right way up, not a particular set of numbers.
"""

from __future__ import annotations

import json

import pytest

from core.model import phases
from core.kratos import export as kratos
from core.results import runs as results
from tests import mdpa, results_run
from tests.models import excavation

WATER_UNIT_WEIGHT = 10_000.0
"""N/m3: the model's own water, 10 kN/m3, and the run is SI."""

STAGES = ["1_Initial_stage", "2_Null_step", "3_SheetPileWall_installation",
          "4_First_excavation", "5_Strut_installation", "6_Second_excavation",
          "7_Third_excavation"]
"""The seven stages, in execution order, as the deck names them."""

MEMBER_STAGES = STAGES[2:]
"""Every stage with a wall, and so with member output."""

WALL_PART = "SheetPileWall"


@pytest.fixture(scope="module")
def real():
    return results_run.real_run()


@pytest.fixture(autouse=True)
def run(real, monkeypatch):
    """Every test in this module reads the real run, through the runs root."""
    return results_run.use(monkeypatch, real)


@pytest.fixture(scope="module")
def project():
    """The model the run was made from."""
    return results_run.model()


@pytest.fixture(scope="module")
def deck(real):
    return mdpa.parse(results_run.deck_text(real))


def member_output(real, stage: str, member: str = "wall") -> dict:
    root, run_id = real
    path = root / run_id / f"{stage}__output_{member}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── The registry: what is in this directory ─────────────────────────────────

def test_the_run_reports_its_seven_stages_in_execution_order(run):
    described = results.describe(run)
    assert [stage["name"] for stage in described["stages"]] == STAGES
    assert [stage["index"] for stage in described["stages"]] == list(range(1, 8))
    assert described["complete"] is True
    assert described["failed_at"] is None


def test_the_deck_and_the_files_tell_the_same_story_about_the_stages(real):
    """`_stages_from_deck` reads `execution_list`; `_stages_from_files` is the fallback
    for a directory whose deck cannot be read. On a complete run they must agree."""
    root, run_id = real
    from_deck = results._stages_from_deck(root / run_id)
    from_files = results._stages_from_files(root / run_id)

    assert [name for name, _ in from_deck] == STAGES
    assert from_files == from_deck


# ── The mesh: what can be drawn ─────────────────────────────────────────────

def test_the_stage_mesh_carries_kratos_own_node_ids(run, deck):
    """The join to everything else is by node id, so a renumbering on the way in would
    break every one of them at once."""
    mesh = results.stage_mesh(run, 7)

    assert set(mesh.nodes) == set(deck.nodes)
    for node in list(mesh.nodes)[:50]:
        # GiD writes coordinates to six significant digits: positions are for drawing,
        # the id is what joins.
        assert mesh.nodes[node][:2] == pytest.approx(deck.nodes[node][:2], rel=1e-5)


def test_quadratic_soil_elements_are_subdivided_for_drawing(run):
    """Six-node triangles drawn through their corners would lose the mid-side nodes,
    which carry results of their own. Each element becomes four."""
    sections = {section["key"]: section
                for section in results.stage_geometry(run, 7)["sections"]}
    parts = {part["name"]: part for part in results.stage_parts(run, 7)["parts"]}

    soil = sections["results:Soil_Bottom"]
    assert len(soil["indices"]) // 3 == 4 * parts["Soil_Bottom"]["elements"]
    assert soil["node_ids"], "the drawn vertices have to say which node each one is"


def test_every_block_in_the_gid_mesh_belongs_to_a_named_part(run, deck):
    """A block that resolved to no part would simply not be drawn."""
    mesh = results.stage_mesh(run, 7)
    parts = results.stage_parts(run, 7)["parts"]

    in_blocks = {element for block in mesh.blocks for element in block.elements}
    in_parts = set()
    for part in deck.parts.values():
        in_parts |= set(part.elements)

    assert in_blocks <= in_parts
    assert sum(part["elements"] for part in parts) >= len(in_blocks)


# ── The parts: what the phase did ───────────────────────────────────────────

SOIL = {"Soil_Top", "Soil_Middle", "Soil_Bottom", "Soil_Middle_pit", "Soil_Bottom_pit"}
LIFTS = {"Soil_Top_lift1", "Soil_Top_lift2", "Soil_Top_lift3"}


def test_stage_one_has_the_ground_and_nothing_that_is_built_later(run):
    """The wall is in the deck and switched off, which is a different state from not
    existing and has to read as one."""
    parts = {part["name"]: part for part in results.stage_parts(run, 1)["parts"]}

    assert {name for name, part in parts.items() if part["alive"]} == SOIL | LIFTS
    for name in (WALL_PART, "Strut"):
        assert parts[name]["declared"] > 0 and parts[name]["elements"] == 0
        assert parts[name]["alive"] is False


def test_stage_seven_has_dug_away_three_bodies_and_built_two(run):
    parts = {part["name"]: part for part in results.stage_parts(run, 7)["parts"]}

    assert {name for name, part in parts.items() if part["alive"]} == \
        SOIL | {WALL_PART, "Strut"}
    for lift in LIFTS:
        assert parts[lift]["declared"] > 0 and parts[lift]["elements"] == 0


def test_interfaces_are_reported_as_unwritten_rather_than_as_demolished(run):
    """The interfaces are solved, and GiD writes them in no stage, so `elements == 0`
    says nothing about whether a phase removed them."""
    for index in (1, 7):
        # By elements, not by name: `Interface_Master` and `Interface_Slave` are node
        # groups and own no elements.
        parts = [part for part in results.stage_parts(run, index)["parts"]
                 if part["name"].startswith("Interface_") and part["declared"]]
        # One per soil body the wall runs against.
        assert len(parts) == len(SOIL | LIFTS)
        assert all(part["written"] is False for part in parts)


def test_supports_and_boundaries_are_not_answered_with_a_yes_or_no(run):
    """A support owns no elements, so "is it in the model during this stage" is not a
    question about it."""
    parts = {part["name"]: part for part in results.stage_parts(run, 7)["parts"]}
    for name in ("Bottom_Fixed", "Left_Edge", "Right_Edge", "Strut_Support"):
        assert parts[name]["declared"] == 0
        assert parts[name]["alive"] is None
        assert parts[name]["written"] is None


def test_every_stage_agrees_with_the_phase_model_about_what_exists(run, project):
    """`phases.active_parts` resolves the phase tree on the input side -- it is what greys
    out a part before anything is calculated -- and the run has to agree with it in every
    stage. Interfaces, loads and supports carry no written elements and are outside the
    comparison."""
    names = kratos._part_names(project)
    for index, phase in enumerate(project.phases, start=1):
        parts = {part["name"]: part for part in results.stage_parts(run, index)["parts"]}
        with_elements = {name for name, part in parts.items() if part["declared"]}
        interfaces = {name for name in with_elements if name.startswith("Interface_")}
        expected = ({names[key] for key in phases.active_parts(project, phase)}
                    & with_elements) - interfaces
        alive = {name for name, part in parts.items() if part["alive"]} - interfaces
        assert alive == expected, f"stage {index} ({phase.name})"


# ── The fields: what a user may ask for ─────────────────────────────────────

def test_the_field_menu_is_exactly_what_this_deck_writes(run):
    """A set, deliberately: widening the deck's output should mean editing this line and
    looking at what turned up."""
    offered = {group["name"]: [field["name"] for field in group["fields"]]
               for group in results.stage_fields(run, 7)["groups"]}

    assert offered == {
        "Deformations": ["u", "ux", "uy", "uz"],
        "Phase deformations": ["du", "dux", "duy", "duz"],
        "Effective stresses": ["sxx", "syy", "szz", "sxy", "syz", "sxz",
                               "p", "q", "s1", "s2", "s3", "tau_max"],
        "Groundwater": ["pw"],
    }


def test_the_units_offered_are_the_runs_own(run):
    """The run is SI, so a stress is in pascals and labelled so."""
    units = {field["name"]: field["unit"]
             for group in results.stage_fields(run, 7)["groups"]
             for field in group["fields"]}

    assert units["u"] == "m"
    assert units["p"] == units["q"] == units["pw"] == "Pa"


def test_pore_pressure_is_hydrostatic_below_the_water_table_and_zero_above_it(run):
    """In the K0 stage the pore pressure is the depth below the water table times the
    unit weight of water, compression negative, everywhere."""
    mesh = results.stage_mesh(run, 1)
    field = results.stage_field(run, 1, "pw", "nodes")

    for node, value in zip(field["ids"], field["values"]):
        y = mesh.nodes[node][1]
        depth = max(0.0, excavation.WATER_Y - y)
        assert value == pytest.approx(-WATER_UNIT_WEIGHT * depth, abs=50.0), (
            f"pore pressure {value} Pa at y = {y} m")

    assert len(field["ids"]) == len(mesh.nodes)
    assert field["min"] == pytest.approx(
        -WATER_UNIT_WEIGHT * (excavation.WATER_Y - excavation.DOMAIN_BOTTOM_Y))


def test_effective_stress_is_compression_negative_and_q_is_not(run):
    """Kratos writes compression negative, and nothing here flips a sign. q
    is an invariant magnitude and positive whichever way the convention goes."""
    p = results.stage_field(run, 7, "p", "nodes")
    q = results.stage_field(run, 7, "q", "nodes")

    assert p["max"] < 0.0, "somewhere in this model the ground is in tension"
    assert q["min"] > 0.0


def test_stresses_are_in_the_runs_pascals_not_scaled(run):
    """Nothing scales a run's numbers: forty metres of ground puts p' at the bottom in
    the hundreds of thousands of pascals -- not hundreds."""
    p = results.stage_field(run, 7, "p", "nodes")
    assert -1.0e6 < p["min"] < -5.0e4, f"p' bottoms out at {p['min']} Pa"
    assert p["unit"] == "Pa"


def test_the_ground_under_the_pit_heaves_and_the_far_field_settles(run):
    """The direction of the answer, which is what a sign error anywhere between the deck
    and the screen would turn over."""
    mesh = results.stage_mesh(run, 7)
    field = results.stage_field(run, 7, "uy", "nodes")
    uy = dict(zip(field["ids"], field["values"]))

    def nearest(x, y):
        return min(mesh.nodes, key=lambda node: (mesh.nodes[node][0] - x) ** 2
                   + (mesh.nodes[node][1] - y) ** 2)

    pit_floor = excavation.LIFTS[-1]
    assert uy[nearest(excavation.WALL_X / 2, pit_floor - 1.5)] > 0.0
    assert uy[nearest(excavation.DOMAIN_RIGHT_X - 15.0, -10.0)] < 0.0


# ── One quantity, two writers ───────────────────────────────────────────────

def test_the_gid_parser_agrees_with_the_decks_own_json_output(run, real, deck):
    """`TOTAL_DISPLACEMENT_X` along the wall is written twice by the same run: into the
    GiD `.post.res` that `core.results.gid` parses, and by Kratos' own json_output
    process. The two sides share no code."""
    wall = deck.parts[WALL_PART].nodes
    written = member_output(real, "7_Third_excavation", "wall")
    field = results.stage_field(run, 7, "ux", "nodes")
    parsed = dict(zip(field["ids"], field["values"]))

    compared = 0
    for node in wall:
        key = f"NODE_{node}"
        if node not in parsed or key not in written:
            continue
        assert parsed[node] == pytest.approx(written[key]["TOTAL_DISPLACEMENT_X"][0],
                                             abs=1e-6)
        compared += 1

    assert compared == len(wall) > 20, f"only {compared} of {len(wall)} wall nodes compared"


# ── The members: the wall and its interface along their length ──────────────

def test_the_run_offers_the_wall_and_the_interface(run):
    members = {m["name"]: m for m in results.stage_members(run)["members"]}

    assert sorted(members) == ["interface", "wall"]
    assert members["wall"]["stages"] == [3, 4, 5, 6, 7]
    assert [q["name"] for q in members["wall"]["quantities"]] == ["M", "Q", "N", "ux", "uy"]
    assert [q["name"] for q in members["interface"]["quantities"]] == ["tn", "ts"]
    assert members["wall"]["quantities"][0] == \
        {"name": "M", "label": "Bending moment", "unit": "N·m/m"}


def test_a_plot_has_one_panel_per_stage_with_the_wall_in_it(run):
    plot = results.member_profiles(run, "wall", "M")

    assert (plot["member"], plot["quantity"], plot["unit"]) == ("wall", "M", "N·m/m")
    assert [s["index"] for s in plot["stages"]] == [3, 4, 5, 6, 7]
    assert [s["name"] for s in plot["stages"]] == MEMBER_STAGES
    assert plot["stages"][0]["phase"] == "SheetPileWall installation"


def test_the_wall_runs_from_its_toe_to_its_top(run):
    """y is the vertical axis, so the points are ordered toe to top."""
    for stage in results.member_profiles(run, "wall", "ux")["stages"]:
        levels = [y for _, y in stage["points"]]
        assert levels == sorted(levels)
        assert levels[0] == pytest.approx(excavation.WALL_TOE_Y)
        assert levels[-1] == pytest.approx(excavation.DOMAIN_TOP_Y)
