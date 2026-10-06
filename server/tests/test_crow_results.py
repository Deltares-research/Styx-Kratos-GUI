"""Reading a real CROW run back, end to end.

The postprocessing modules are each tested against the 1D consolidation deck in `test/`
and against hand-written literals: one soil block, no staging, no structures, nothing
deactivated. This file is the other kind of test -- one run of one real model, read
through `app.results` the way the GUI reads it, and checked against what the model is
known to be.

What only this fixture can say, and why each matters:

*   **Eight soil bodies and two structures**, so the join from GiD's anonymous mesh
    blocks (`Kratos_Triangle2D6_Mesh_2`) back to the deck's named parts is exercised on
    names nobody could have guessed from the mesh.
*   **A construction sequence**, so "this part is not in this stage" appears at all --
    and appears in both of its forms: the wall, which does not exist yet in stage 1, and
    the three excavation lifts, which have been dug away by stage 7.
*   **Interfaces**, which the GiD writer emits in no stage whatsoever. A postprocessor
    that reported them as demolished would be lying about the model, and this is the only
    fixture where the difference is visible.
*   **A second, independent writer of the same numbers.** The deck's `json_output`
    processes write the wall's displacements to their own files, so what the `.post.res`
    parser says can be checked against something that is not the `.post.res` parser.

The committed fixture carries stages 1 and 7 -- the k0 state, where the deck is whole,
and the last excavation, where three bodies are gone. Anything that is genuinely about
the *sequence* needs all seven, is marked as needing `crow_run.whole_run()`, and skips
where the run is not on the machine.

`test_crow_wall_forces.py` is the other half of this pair: it says the numbers are right.
This one says they are read correctly.
"""

from __future__ import annotations

import json

import pytest

from app import crow, kratos, phases, results
from tests import crow_run, mdpa

WATER_UNIT_WEIGHT = 10.0
"""kN/m3, as the deck writes it. Not 9.81: the project's own water is 10.0, and a test
that used 9.81 here would be testing a number nobody chose."""


@pytest.fixture(autouse=True)
def fixture_run(monkeypatch):
    """Every test in this module reads the committed run, through the runs root."""
    return crow_run.use_fixture_runs(monkeypatch)


@pytest.fixture(scope="module")
def project():
    """The same model the run was made from, as a `Project`."""
    return crow.crow_project(staged=True)


def deck_names(project) -> dict[str, str]:
    """Part key -> the name that key has in the deck.

    The user's keys and the deck's names are different vocabularies on purpose
    (`soil_L_top__lift1` against `Soil_Top_lift1`), and this is the translation the
    exporter itself uses -- so a rename in one place cannot quietly break the comparison
    in the other.
    """
    return kratos._part_names(project)


# ── The registry: what is in this directory ─────────────────────────────────

def test_the_run_reports_its_seven_stages_in_execution_order():
    """Named by the deck, not by the files.

    Filenames sort lexically, which puts stage 10 between 1 and 2 in a longer deck, and
    a stage that wrote nothing has no file to be named after at all -- as five of these
    seven do not, in the committed fixture. Both are why `ProjectParameters.json`'s
    `execution_list` is asked first.
    """
    described = results.describe(crow_run.RUN_ID)
    assert [stage["name"] for stage in described["stages"]] == crow_run.STAGES
    assert [stage["index"] for stage in described["stages"]] == list(range(1, 8))


def test_the_committed_fixture_is_honest_about_carrying_only_two_stages():
    """A run whose middle stages were never copied must not read as a run that died in
    stage 2. `complete` is False here and the reason is visible: the stages are all
    listed, two have results, and nothing in the log says a stage failed."""
    described = results.describe(crow_run.RUN_ID)
    with_results = [stage["name"] for stage in described["stages"] if stage["results"]]

    assert with_results == crow_run.GID_STAGES
    assert described["complete"] is False
    assert described["failed_at"] is None


def test_the_deck_and_the_files_tell_the_same_story_about_the_stages():
    """Two readers of one truth, which is two things to drift.

    `_stages_from_deck` reads `execution_list`; `_stages_from_files` is the fallback for
    a directory whose deck cannot be read, and rebuilds the sequence from the output
    files. On a complete run they must agree exactly -- if they ever stop agreeing, the
    fallback is quietly wrong for every run written by an older exporter.
    """
    directory = crow_run.whole_run()
    from_deck = results._stages_from_deck(directory)
    from_files = results._stages_from_files(directory)

    assert [name for name, _ in from_deck] == crow_run.STAGES
    assert from_files == from_deck


# ── The mesh: what can be drawn ─────────────────────────────────────────────

def test_the_stage_mesh_carries_kratos_own_node_ids():
    """The join to everything else -- the deck, the member output, the phase model --
    is by node id, so a renumbering on the way in would break every one of them at
    once and each in a way that looks like a different bug."""
    mesh = results.stage_mesh(crow_run.RUN_ID, 7)
    deck = mdpa.parse(crow_run.deck_text())

    assert set(mesh.nodes) == set(deck.nodes)
    for node in list(mesh.nodes)[:50]:
        # Loosely, and that is the point: GiD writes coordinates to six significant
        # digits, so 4.2857142857 comes back as 4.28571. Positions in a post file are
        # for drawing; the id is what joins.
        assert mesh.nodes[node][:2] == pytest.approx(deck.nodes[node][:2], rel=1e-5)


def test_quadratic_soil_elements_are_subdivided_for_drawing():
    """Six-node triangles drawn through their corners would lose the mid-side nodes --
    and the mid-side nodes carry their own results, so a contour across them would be
    piecewise linear on a mesh the solver never used. Each element becomes four."""
    geometry = results.stage_geometry(crow_run.RUN_ID, 7)
    # `results:` keeps a results section from colliding with the live model's own part
    # keys in the viewport, which are the same names.
    sections = {section["key"]: section for section in geometry["sections"]}
    parts = {part["name"]: part
             for part in results.stage_parts(crow_run.RUN_ID, 7)["parts"]}

    soil = sections["results:Soil_Bottom"]
    assert len(soil["indices"]) // 3 == 4 * parts["Soil_Bottom"]["elements"]
    assert soil["node_ids"], "the drawn vertices have to say which node each one is"


def test_every_block_in_the_gid_mesh_belongs_to_a_named_part():
    """GiD names its blocks after nothing: `Kratos_Triangle2D6_Mesh_2` says neither which
    layer nor which lift. A block that resolved to no part would simply not be drawn, and
    nothing on screen would say so."""
    mesh = results.stage_mesh(crow_run.RUN_ID, 7)
    parts = results.stage_parts(crow_run.RUN_ID, 7)["parts"]

    in_blocks = {element for block in mesh.blocks for element in block.elements}
    in_parts = set()
    deck = mdpa.parse(crow_run.deck_text())
    for part in deck.parts.values():
        in_parts |= set(part.elements)

    assert in_blocks <= in_parts
    assert sum(part["elements"] for part in parts) >= len(in_blocks)


# ── The parts: what the phase did ───────────────────────────────────────────

def test_stage_one_has_the_ground_and_nothing_that_is_built_later():
    """The k0 stage: eight soil bodies, no wall, no strut. The wall is *in the deck* --
    it has elements, it is meshed -- and is switched off, which is a different state from
    not existing and has to read as one."""
    parts = {part["name"]: part
             for part in results.stage_parts(crow_run.RUN_ID, 1)["parts"]}

    alive = {name for name, part in parts.items() if part["alive"]}
    assert alive == {"Soil_Top", "Soil_Middle", "Soil_Bottom", "Soil_Top_lift1",
                     "Soil_Top_lift2", "Soil_Top_lift3", "Soil_Middle_pit",
                     "Soil_Bottom_pit"}
    for name in ("SheetPileWall", "Strut"):
        assert parts[name]["declared"] > 0 and parts[name]["elements"] == 0
        assert parts[name]["alive"] is False


def test_stage_seven_has_dug_away_three_bodies_and_built_two():
    """The end of the sequence, as a set rather than as a list of the parts that happen
    to be shared: a comparison that only looked at the bodies both stages carry could not
    see a body that went missing."""
    parts = {part["name"]: part
             for part in results.stage_parts(crow_run.RUN_ID, 7)["parts"]}

    alive = {name for name, part in parts.items() if part["alive"]}
    assert alive == {"Soil_Top", "Soil_Middle", "Soil_Bottom", "Soil_Middle_pit",
                     "Soil_Bottom_pit", "SheetPileWall", "Strut"}
    for lift in ("Soil_Top_lift1", "Soil_Top_lift2", "Soil_Top_lift3"):
        assert parts[lift]["declared"] > 0 and parts[lift]["elements"] == 0


def test_interfaces_are_reported_as_unwritten_rather_than_as_demolished():
    """The distinction this whole module exists for.

    The eight interfaces are in the deck, they are solved, and GiD writes them in *no*
    stage -- so `elements == 0` says nothing about whether a phase removed them.
    `written=False` is what stops the explorer greying them out for seven stages running.
    """
    for index in (1, 7):
        # By elements, not by name: `Interface_Master` and `Interface_Slave` are the
        # node groups the tie is built from and own no elements at all.
        parts = [part for part in results.stage_parts(crow_run.RUN_ID, index)["parts"]
                 if part["name"].startswith("Interface_") and part["declared"]]
        assert len(parts) == 8
        assert all(part["written"] is False for part in parts)


def test_supports_and_boundaries_are_not_answered_with_a_yes_or_no():
    """A support owns no elements, so "is it in the model during this stage" is not a
    question about it. Answered False, every boundary condition in the deck would appear
    to have been removed."""
    parts = {part["name"]: part
             for part in results.stage_parts(crow_run.RUN_ID, 7)["parts"]}
    for name in ("Bottom_Fixed", "Left_Edge", "Right_Edge", "Strut_Support"):
        assert parts[name]["declared"] == 0
        assert parts[name]["alive"] is None
        assert parts[name]["written"] is None


@pytest.mark.parametrize("index", [1, 7])
def test_the_output_agrees_with_the_phase_model_about_what_exists(project, index):
    """The deck, the phase model and the results, all saying the same thing.

    `phases.active_parts` resolves the phase tree on the *input* side -- it is what greys
    out a part in the viewport before anything has been calculated. This asserts that the
    run agrees with it, which is the one comparison that can catch a deck exporting a
    sequence subtly different from the one the user built.

    Interfaces are outside the comparison: GiD writes none of them, so the run has no
    opinion about them to compare (see the test above). Loads and supports carry no
    elements and are outside it for the same reason.
    """
    names = deck_names(project)
    parts = {part["name"]: part
             for part in results.stage_parts(crow_run.RUN_ID, index)["parts"]}
    with_elements = {name for name, part in parts.items() if part["declared"]}
    interfaces = {name for name in with_elements if name.startswith("Interface_")}

    expected = {names[key] for key in phases.active_parts(project,
                                                          project.phases[index - 1])}
    expected = (expected & with_elements) - interfaces
    alive = {name for name, part in parts.items() if part["alive"]} - interfaces

    assert alive == expected


def test_the_whole_sequence_agrees_with_the_phase_model(project):
    """The same comparison, for all seven stages, where the run is on this machine.

    One stage agreeing is a coincidence away from meaningless; the sequence agreeing is
    the statement worth making. Skips on a machine with no complete run, which is why the
    two stages above are asserted separately rather than only here.
    """
    directory = crow_run.whole_run()
    names = deck_names(project)
    from app import calculate

    root = str(directory.parent)
    previous = calculate.runs_root()
    import os
    os.environ[calculate.RUNS_ENV] = root
    results.forget_cache()
    try:
        for index, phase in enumerate(project.phases, start=1):
            parts = {part["name"]: part
                     for part in results.stage_parts(directory.name, index)["parts"]}
            with_elements = {name for name, part in parts.items() if part["declared"]}
            interfaces = {name for name in with_elements
                          if name.startswith("Interface_")}
            expected = ({names[key] for key in phases.active_parts(project, phase)}
                        & with_elements) - interfaces
            alive = {name for name, part in parts.items() if part["alive"]} - interfaces
            assert alive == expected, f"stage {index} ({phase.name})"
    finally:
        os.environ[calculate.RUNS_ENV] = str(previous)
        results.forget_cache()


# ── The fields: what a user may ask for ─────────────────────────────────────

def test_the_field_menu_is_exactly_what_this_deck_writes():
    """A set, deliberately.

    Widening the deck's output (postprocessing P4) is supposed to change this list, and
    changing it should mean editing this line and looking at what turned up. A test that
    only checked the fields it already knew about could not see a field appear, and an
    omission is the failure mode this project has been bitten by before.
    """
    catalogue = results.stage_fields(crow_run.RUN_ID, 7)["groups"]
    offered = {group["name"]: [field["name"] for field in group["fields"]]
               for group in catalogue}

    assert offered == {
        "Deformations": ["u", "ux", "uy", "uz"],
        "Phase deformations": ["du", "dux", "duy", "duz"],
        "Effective stresses": ["sxx", "syy", "szz", "sxy", "syz", "sxz",
                               "p", "q", "s1", "s2", "s3", "tau_max"],
        "Groundwater": ["pw"],
    }


def test_the_units_offered_are_the_projects_own():
    """The deck is SI and the project is m/kN/day. A stress read straight out of the file
    is out by a thousand and looks perfectly reasonable on screen."""
    catalogue = results.stage_fields(crow_run.RUN_ID, 7)["groups"]
    units = {field["name"]: field["unit"]
             for group in catalogue for field in group["fields"]}

    assert units["u"] == "m"
    assert units["p"] == units["q"] == units["pw"] == "kPa"


def test_pore_pressure_is_hydrostatic_below_the_water_table_and_zero_above_it():
    """A physical check on a whole field, which no fixture of hand-written literals can
    make: in the k0 stage the pore pressure is the water table's depth times the unit
    weight of water, compression negative, everywhere in the far field."""
    mesh = results.stage_mesh(crow_run.RUN_ID, 1)
    field = results.stage_field(crow_run.RUN_ID, 1, "pw", "nodes")
    values = dict(zip(field["ids"], field["values"]))

    checked = 0
    for node, value in values.items():
        y = mesh.nodes[node][1]
        depth = max(0.0, crow.WATER_Y - y)
        assert value == pytest.approx(-WATER_UNIT_WEIGHT * depth, abs=0.05), (
            f"pore pressure {value} kPa at y = {y} m")
        checked += 1

    assert checked > 3000, f"only {checked} nodes carried a pore pressure"
    assert field["min"] == pytest.approx(
        -WATER_UNIT_WEIGHT * (crow.WATER_Y - crow.DOMAIN_BOTTOM_Y))


def test_effective_stress_is_compression_negative_and_q_is_not():
    """Kratos writes compression negative, and nothing here flips a sign --
    p' is negative in compression, and "fixing" that later would silently invert every
    number this program has ever shown. q is an invariant magnitude and is positive
    whichever way the convention goes."""
    p = results.stage_field(crow_run.RUN_ID, 7, "p", "nodes")
    q = results.stage_field(crow_run.RUN_ID, 7, "q", "nodes")

    assert p["max"] < 0.0, "somewhere in this model the ground is in tension"
    assert q["min"] > 0.0
    assert -400.0 < p["min"] < -100.0, f"p' bottoms out at {p['min']} kPa"


def test_stresses_are_in_kilopascals_and_not_pascals():
    """The 3990.4 trap: a number three orders of magnitude out is still a plausible
    number, and nothing on screen says which it is."""
    p = results.stage_field(crow_run.RUN_ID, 7, "p", "nodes")
    assert abs(p["min"]) < 5.0e3, "p' looks like pascals"


# ── One quantity, two writers ───────────────────────────────────────────────

def test_the_gid_parser_agrees_with_the_decks_own_json_output():
    """The strongest check in this file, because the two sides share no code.

    `TOTAL_DISPLACEMENT_X` along the wall is written twice by the same run: once into the
    GiD `.post.res` that `app.gid_results` parses, and once into
    `7_Third_excavation__output_wall.json` by Kratos' own json_output process. If the
    parser dropped a column, mis-associated a node or averaged something it should not,
    these would not agree -- and no fixture written by hand could catch it, since a hand
    written fixture agrees with whatever the parser does to it.
    """
    deck = mdpa.parse(crow_run.deck_text())
    wall = deck.parts[crow_run.WALL_PART].nodes
    written = crow_run.member_output("7_Third_excavation", "wall")
    field = results.stage_field(crow_run.RUN_ID, 7, "ux", "nodes")
    parsed = dict(zip(field["ids"], field["values"]))

    compared = 0
    for node in wall:
        key = f"NODE_{node}"
        if node not in parsed or key not in written:
            continue
        assert parsed[node] == pytest.approx(
            written[key]["TOTAL_DISPLACEMENT_X"][0], abs=1e-6)
        compared += 1

    assert compared == len(wall) >= 39, (
        f"only {compared} of {len(wall)} wall nodes could be compared")


# ── Every field, at seven places, to the last digit ─────────────────────────

EXPECTED = json.loads((crow_run.FIXTURE / "expected.json").read_text(encoding="utf-8"))
"""Written by `make_crow_fixture.py --write`: `results.stage_at_node` at seven points of
the model, in both committed stages. Regenerating it is a deliberate act whose diff is
meant to be read -- every line of it is a number this program shows a user."""

PROBES = [(probe["label"], probe) for probe in EXPECTED["probes"]]


@pytest.mark.parametrize("stage", ["1", "7"])
@pytest.mark.parametrize("label,probe", PROBES, ids=[label for label, _ in PROBES])
def test_every_field_at_a_known_place_is_what_it_was(label, probe, stage):
    """The pin, as opposed to the physics.

    The cases above say the numbers are *plausible*: hydrostatic where they should be,
    compression negative, in kPa rather than Pa. A plausible number can still be a
    changed one, and the changes that matter most here are the quiet ones -- the
    Gauss-to-node averaging done in the wrong order (q is not linear, so averaging the
    tensor and then deriving q gives a different, entirely plausible answer), an
    invariant picking up a sign, a unit applied twice.

    So: every field this reader offers, at seven places chosen for what they are in the
    model rather than for their node ids, in both stages. Tight, because nothing here
    should move without somebody deciding it should.
    """
    recorded = probe["stages"][stage]
    at_node = results.stage_at_node(crow_run.RUN_ID, int(stage), probe["node"])

    assert at_node["at"] == pytest.approx(probe["at"], abs=1e-9)

    expected = {value["field"]: value["value"] for value in recorded["values"]}
    got = {value["field"]: value["value"] for value in at_node["values"]}
    assert set(got) == set(expected), "the fields available at this node have changed"

    for field, value in expected.items():
        assert got[field] == pytest.approx(value, rel=1e-9, abs=1e-12), (
            f"{field} at {label} in stage {stage}")


def test_the_probes_cover_the_parts_of_the_model_that_behave_differently():
    """A pin is only as good as where it is pinned.

    Seven points, and the ones that matter are the last four: ground that is about to be
    excavated, ground under the pit floor that heaves rather than settles, and both ends
    of the wall. A file of far-field probes would reproduce faithfully and notice
    nothing about the excavation.
    """
    assert len(PROBES) == 7
    heaving = next(probe for label, probe in PROBES if "pit floor" in label)
    settling = next(probe for label, probe in PROBES if "middle ground" in label)

    def uy(probe, stage):
        return next(value["value"] for value in probe["stages"][stage]["values"]
                    if value["field"] == "uy")

    assert uy(heaving, "7") > 0.0, "the ground under an excavation heaves"
    assert uy(settling, "7") < 0.0, "the far field settles under its own weight"
