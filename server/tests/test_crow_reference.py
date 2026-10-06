"""The CROW deck this pipeline builds, checked against the reference one.

`crow_excavation_wall.mdpa` in the repo root was written by STEM from
`demo_crow_excavation_wall.py`. `examples/crow/crow.py` builds the same model out of this
application's own `Project` and exports it through `app.build` -> `app.meshing` ->
`app.kratos`. These tests are what says the two are the same model.

**Structural equivalence, not equality.** Two things make a literal comparison the wrong
instrument, and both are by design:

*   *The mesh differs.* A different gmsh, driven differently, puts nodes in different
    places. Node counts and ids are not an invariant and are never compared; element
    counts are compared only as ratios, with a wide band.
*   *The names differ.* The reference names eight soil bodies by hand
    (`Excavated_Soil_1`, `Soil_Top_Right`). Here they are derived -- three layers
    crossed with three lifts -- because a user draws layers and digs lifts rather than
    naming a Cartesian product. `Soil_Top_lift1` is the same body under a name nobody
    typed.

So parts are compared by *role*, and role is read off the deck's own structure -- what a
part carries, and where its nodes are -- rather than off its name. That is also what
makes these tests worth having: a check that only compared names would pass on a deck
whose interfaces held the wrong faces.

See plan/staged-construction-plan.md sec A4.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from tests.crow_example import crow, reference as example_file
from tests import mdpa

REFERENCE = example_file("crow_validation_model.mdpa")
"""The deck the CROW case is *validated* against: `crow_validation/common/model.mdpa` in
the Kratos checkout, which `test_CROW_case.py` runs and compares wall forces from.

Not `crow_excavation_wall.mdpa`, also in this repo root, which is what STEM generates
(`crow_validation/generated_mesh/`) and which every comparison here used to be written
against. The two carry the same materials and the same seven stages -- both compared and
found identical -- and differ only in the mesh: the validated deck meshes its wall at a
uniform 0.5 m where the STEM one runs 0.5, 0.75 and 1.0 m, and starts its water loads at
the water table where the STEM one starts them at the ground surface. Three things
recorded here as deliberate divergences turned out to be this file being the wrong one
to compare against."""

REFERENCE_NAMES = {
    "SheetPileWall": "Sheet_Pile_Wall",
    "Master_side_1": "Master_side",
    "Slave_side_1": "Slave_side",
    "WaterLoad_Stage1": "Normal_Load_After_First_Excavation",
    "WaterLoad_Stage2": "Normal_Load_After_Second_Excavation",
    "WaterLoad_Stage3": "Normal_Load_After_Third_Excavation",
    "Interface_Soil_Top_Right": "Interface_Top_Right",
    "Interface_Soil_Middle_Right": "Interface_Middle_Right",
    "Interface_Soil_Bottom_Right": "Interface_Bottom_Right",
    "Interface_Soil_Below_Pit": "Interface_Middle_Left",
    "Interface_Soil_Bottom_Left": "Interface_Bottom_Left",
}
"""What the validated deck calls the eleven parts it does not name the way the STEM deck
does. Both have 32 parts and the other 21 share a name. Used only where a test reaches
into the reference by name; everything else is compared by role."""


def part_of(source, name: str):
    """A part by its STEM-deck name, whichever of the two decks is being read."""
    return source.parts[name if name in source.parts
                        else REFERENCE_NAMES.get(name, name)]

SOIL = "SmallStrainUPwDiffOrderElement2D6N"
BEAM = "LinearTimoshenkoCurvedBeamElement2D3N"
TRUSS = "LinearTrussElement2D2N"
CONTACT = "Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N"
LINE_LOAD = "LineLoadDiffOrderCondition2D3N"
NORMAL_LOAD = "LineNormalLoadDiffOrderCondition2D3N"

WALL_X = crow.WALL_X
TOLERANCE = 1e-6


@pytest.fixture(scope="module")
def reference() -> mdpa.Deck:
    if not REFERENCE.exists():                      # pragma: no cover - fixture guard
        pytest.skip(f"{REFERENCE.name} is not present; the reference decks are kept out of the repository")
    return mdpa.parse(REFERENCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def export() -> dict:
    return crow.export()


@pytest.fixture(scope="module")
def deck(export) -> mdpa.Deck:
    return mdpa.parse(export["mdpa"])


def classes(deck: mdpa.Deck) -> dict[str, int]:
    """Element/condition class -> how many of them, merging repeated blocks."""
    out: dict[str, int] = {}
    for block in deck.elements + deck.conditions:
        out[block.name] = out.get(block.name, 0) + len(block.entries)
    return out


def carrying(deck: mdpa.Deck, class_name: str) -> dict[str, mdpa.Part]:
    """The parts holding entities of one class: the deck's own statement of role.

    Elements and conditions are numbered in *separate* id spaces -- element 7 and
    condition 7 are different entities -- so a part's elements are only ever matched
    against element classes and its conditions against condition classes. Looking in
    both at once matches parts that merely share a number, which is how this first
    reported a water load running the full depth of the wall.
    """
    element_ids = {e for block in deck.elements if block.name == class_name
                   for e in block.entries}
    condition_ids = {e for block in deck.conditions if block.name == class_name
                     for e in block.entries}
    return {name: part for name, part in deck.parts.items()
            if (set(part.elements) & element_ids) or
               (set(part.conditions) & condition_ids)}


def node_only(deck: mdpa.Deck) -> dict[str, mdpa.Part]:
    return {name: part for name, part in deck.parts.items()
            if not part.elements and not part.conditions}


# ── The dialect ─────────────────────────────────────────────────────────────

def test_the_same_kratos_classes_are_used_and_no_others(deck, reference):
    """The deck speaks the reference's dialect exactly: same six classes, no extras."""
    assert set(classes(deck)) == set(classes(reference))


def test_every_element_carries_property_zero(deck, reference):
    """Materials are assigned by sub-model part, not by the mdpa's property column --
    the reference writes 0 throughout and so must this."""
    for source in (deck, reference):
        for block in source.elements:
            assert set(block.properties.values()) == {0}, block.name


# ── The bodies ──────────────────────────────────────────────────────────────

def test_the_soil_is_split_into_the_same_eight_bodies(deck, reference):
    assert len(carrying(deck, SOIL)) == len(carrying(reference, SOIL)) == 8


def test_the_bodies_occupy_the_same_ground(deck, reference):
    """Same extents, body for body, whatever each deck calls them.

    This is the check the names cannot do: a body matched by its (x-side, y-band) is
    the same piece of ground in both decks or the geometry is wrong.
    """
    def extents(source: mdpa.Deck) -> set[tuple[float, float, float]]:
        out = set()
        for part in carrying(source, SOIL).values():
            ys = [source.nodes[n][1] for n in part.nodes]
            xs = [source.nodes[n][0] for n in part.nodes]
            # Which side of the wall, then the band -- rounded, because the two meshes
            # put different nodes on the same boundary.
            side = 0 if max(xs) <= WALL_X + TOLERANCE else 1
            out.add((side, round(min(ys), 3), round(max(ys), 3)))
        return out

    assert extents(deck) == extents(reference)


def test_the_wall_and_the_tie_are_each_one_body(deck, reference):
    for source in (deck, reference):
        assert len(carrying(source, BEAM)) == 1
        assert len(carrying(source, TRUSS)) == 1


def test_the_wall_spans_the_same_depth(deck, reference):
    def span(source: mdpa.Deck) -> tuple[float, float]:
        part = next(iter(carrying(source, BEAM).values()))
        ys = [source.nodes[n][1] for n in part.nodes]
        return round(min(ys), 3), round(max(ys), 3)

    assert span(deck) == span(reference) == (crow.WALL_TOE_Y, crow.DOMAIN_TOP_Y)


# ── The contact ─────────────────────────────────────────────────────────────

def test_the_contact_is_split_per_body_the_same_way(deck, reference):
    """Eight contact parts, one per soil body the wall touches, so each is deactivated
    with the ground it holds."""
    assert len(carrying(deck, CONTACT)) == len(carrying(reference, CONTACT)) == 8


def test_every_contact_element_is_zero_thickness(deck):
    """The two faces are copies at the same point, which is what makes the element a
    contact rather than a sliver of material. Checked on our deck: it is the property
    the split has to produce, and the reference is where it was read from."""
    block = next(b for b in deck.elements if b.name == CONTACT)
    for nodes in block.entries.values():
        half = len(nodes) // 2
        for one, other in zip(nodes[:half], nodes[half:]):
            assert deck.nodes[one] == pytest.approx(deck.nodes[other], abs=TOLERANCE)


def test_the_contact_runs_down_the_wall_and_no_further(deck, reference):
    def span(source: mdpa.Deck) -> tuple[float, float]:
        nodes = {n for part in carrying(source, CONTACT).values() for n in part.nodes}
        ys = [source.nodes[n][1] for n in nodes]
        return round(min(ys), 3), round(max(ys), 3)

    assert span(deck) == span(reference)


# ── Loads and supports ──────────────────────────────────────────────────────

def test_there_is_one_surcharge_and_three_water_loads(deck, reference):
    for source in (deck, reference):
        assert len(carrying(source, LINE_LOAD)) == 1
        assert len(carrying(source, NORMAL_LOAD)) == 3


def test_each_water_load_covers_its_own_lift(deck, reference):
    """Down the exposed wall face to that level, then along that level's floor. The
    three together are what makes the water follow the excavation.

    Both ends agree with the validated reference: each load runs from the water table
    down to its own lift level. Above the water table hydrostatic pressure is negative
    and Kratos clips it to zero, so neither deck puts conditions there -- the STEM deck
    this file used to compare against does, which is what made those look deliberate.
    """
    def spans(source: mdpa.Deck) -> list[tuple[float, float]]:
        out = []
        for part in carrying(source, NORMAL_LOAD).values():
            ys = [source.nodes[n][1] for n in part.nodes]
            out.append((round(min(ys), 3), round(max(ys), 3)))
        return sorted(out)

    assert spans(deck) == spans(reference) == [
        (crow.THIRD, crow.WATER_Y),
        (crow.SECOND, crow.WATER_Y),
        (crow.FIRST, crow.WATER_Y),
    ]


def test_the_tie_s_far_end_is_a_pinned_node_in_no_element_but_the_truss(deck, reference):
    """The reference's `Strut_Support`: one node, held by nothing else."""
    for source in (deck, reference):
        truss = next(b for b in source.elements if b.name == TRUSS)
        ends = set(next(iter(truss.entries.values())))
        singles = [part for part in node_only(source).values() if len(part.nodes) == 1]
        assert len(singles) == 1
        assert singles[0].nodes[0] in ends

        soil = {n for b in source.elements if b.name == SOIL
                for nodes in b.entries.values() for n in nodes}
        assert singles[0].nodes[0] not in soil, "the far end hangs in no soil"


# ── The domain edges ────────────────────────────────────────────────────────

def test_the_dug_edge_is_segmented_and_the_others_are_not(deck, reference):
    """One edge part per lift on the side the pit is dug against, so a lift's own
    restraint leaves the deck with it -- and no segmentation anywhere else."""
    def left_edge_parts(source: mdpa.Deck) -> int:
        out = 0
        for part in node_only(source).values():
            xs = [source.nodes[n][0] for n in part.nodes]
            ys = [source.nodes[n][1] for n in part.nodes]
            if max(xs) > TOLERANCE or min(ys) < crow.THIRD - TOLERANCE:
                continue           # not on the dug stretch of the symmetry plane
            out += 1
        return out

    assert left_edge_parts(deck) == left_edge_parts(reference) == 3


def test_the_bottom_is_held_across_the_whole_model(deck, reference):
    def bottom(source: mdpa.Deck) -> tuple[float, float]:
        part = max(
            (p for p in node_only(source).values()
             if all(abs(source.nodes[n][1] - crow.DOMAIN_BOTTOM_Y) < TOLERANCE
                    for n in p.nodes)),
            key=lambda p: len(p.nodes))
        xs = [source.nodes[n][0] for n in part.nodes]
        return round(min(xs), 3), round(max(xs), 3)

    assert bottom(deck) == bottom(reference) == (crow.DOMAIN_LEFT_X,
                                                 crow.DOMAIN_RIGHT_X)


# ── The tie across the not-yet-installed wall ───────────────────────────────

def test_the_split_nodes_are_tied_in_matched_pairs(deck, reference):
    """A master and a slave at the same point, one pair per node the wall split. Before
    the wall is installed nothing else holds the two halves of the soil together."""
    for source in (deck, reference):
        pairs = [p for name, p in node_only(source).items()
                 if "aster" in name or "lave" in name]
        assert len(pairs) == 2, "one master part and one slave part"
        master, slave = pairs
        assert len(master.nodes) == len(slave.nodes)
        assert ({source.nodes[n] for n in master.nodes} ==
                {source.nodes[n] for n in slave.nodes})


# ── Size, as a ratio only ───────────────────────────────────────────────────

def test_the_two_meshes_cover_the_same_ground(deck, reference):
    """The same ground, and the same split of it either side of the wall.

    This compared the share of *elements* on the dug side, on the reasoning that element
    counts vary with the mesher but the dug/retained split is a property of the geometry.
    Only the second half of that is true: the split of elements matches the split of
    ground only while both meshes are equally dense everywhere, and ours is deliberately
    not -- it refines the excavation and grades out (`examples/crow/crow.py`), where the reference
    spends its elements evenly. So the area is compared, which is the geometric invariant
    the sentence was reaching for, and it is exact rather than approximate.
    """
    def dug_area(source: mdpa.Deck) -> tuple[float, float]:
        dug = whole = 0.0
        for block in source.elements:
            if block.name != SOIL:
                continue
            for connectivity in block.entries.values():
                (x1, y1, _), (x2, y2, _), (x3, y3, _) = (source.nodes[n]
                                                         for n in connectivity[:3])
                size = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2
                whole += size
                if max(x1, x2, x3) <= WALL_X + TOLERANCE:
                    dug += size
        return dug, whole

    ours, theirs = dug_area(deck), dug_area(reference)
    assert ours[1] == pytest.approx(theirs[1], rel=1e-6), "the same total ground"
    assert ours[0] / ours[1] == pytest.approx(theirs[0] / theirs[1], rel=1e-6)


# ── The seven-stage ProjectParameters ───────────────────────────────────────
# Task 19 of plan/staged-construction-plan.md, and the one that says the whole exercise
# worked: the same `Project` that produced the .mdpa above, run through the GUI's own
# phase model, has to produce the reference's seven-stage deck.
#
# Compared by *role*, for the same reason the mdpa is (see this module's docstring): the
# reference's `Excavated_Soil_1` is our `Soil_Top_lift1`, and a comparison of names would
# fail on the one difference that is deliberate. So each stage is reduced to a profile --
# what it switches, what it solves, and how many parts of each role each of its processes
# names -- and the profiles are compared stage for stage.
#
# The role of a part is read off the deck itself wherever it can be: the soil is whatever
# the first stage solves, and the interfaces and structures are what later stages add to
# that. Only the parts no stage lists as a body -- edges, supports, loads -- are
# classified by name, using the reference's own naming convention, which we follow.

REFERENCE_PARAMETERS = example_file("crow_validation_staged_construction.json")

# Nothing. Every process the reference deck carries, this exporter now writes, and the
# comparison below is unfiltered: each stage's profile is compared whole.
#
# Two entries lived here while task 19's findings were open, and both are fixed:
# `VOLUME_ACCELERATION` (gravity, plan sec 7.1) and `apply_scalar_constraint_table_process`
# (the pore-pressure field, sec 7.2). They are kept as empty sets rather than deleted
# because `test_the_deck_is_missing_only_what_is_recorded_here` asserts against them --
# so if a process ever goes missing again it fails there, naming itself, instead of
# being quietly absorbed by `_profile`.

MISSING_MODULES = set()

MISSING_ROLES = set()


@pytest.fixture(scope="module")
def reference_parameters() -> dict:
    if not REFERENCE_PARAMETERS.exists():         # pragma: no cover - fixture guard
        pytest.skip(f"{REFERENCE_PARAMETERS.name} is not present; the reference decks are kept out of the repository")
    return json.loads(REFERENCE_PARAMETERS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parameters(export) -> dict:
    return json.loads(export["project_parameters"])


def _role_of(doc: dict):
    """A function from a sub-model part name to the role it plays in that deck."""
    stages = [doc["stages"][name]
              for name in doc["orchestrator"]["settings"]["execution_list"]]

    def bodies(stage):
        return stage["stage_settings"]["solver_settings"][
            "problem_domain_sub_model_part_list"]

    soils = set(bodies(stages[0]))
    everything = set().union(*(set(bodies(stage)) for stage in stages))
    interfaces = {name for name in everything if "Interface" in name}
    structures = everything - soils - interfaces

    def role(name: str) -> str:
        name = name.partition(".")[2] or name
        if name in ("", "PorousDomain"):
            return "domain"
        if name == "porous_computational_model_part":
            return "computational"
        if name in soils:
            return "soil"
        if name in interfaces:
            return "interface"
        if name in structures:
            return "structure"
        if name.endswith("_Support"):
            return "support"
        if name == "Bottom_Fixed":
            return "fixed"
        if name.endswith("_Edge"):
            return "edge"
        if "Right_Side" in name:
            return "interface_nodes"
        # The two sides of a tie. The reference calls them `Master_side_1` and
        # `Slave_side_1`; we name ours after the interface whose split made them.
        if re.search(r"_Master$|_Slave$|^Master_side|^Slave_side", name):
            return "tie"
        return "load"
    return role


def _named(process: dict) -> list[str]:
    parameters = process["Parameters"]
    out = list(parameters.get("model_part_name_list", []))
    for key in ("model_part_name", "master_model_part_name", "slave_model_part_name"):
        if key in parameters:
            out.append(parameters[key])
    return out


def _listing(listing: str, processes: list[dict], role) -> dict[str, dict[str, int]]:
    """One process list, as module -> role -> how many parts of that role it names.

    Processes of the same module are merged before counting, because the reference
    groups parts that share settings into a single process with a `model_part_name_list`
    where this exporter writes one process per part. Both are valid Kratos and which one
    a deck uses says nothing about the model, so the difference is invisible here.
    """
    merged: dict[str, Counter] = {}
    for process in processes:
        module = process["python_module"]
        if (listing, module) in MISSING_MODULES:
            continue
        counts = Counter(role(name) for name in _named(process))
        for ignored in [r for r in counts
                        if (listing, module, r) in MISSING_ROLES]:
            del counts[ignored]
        if counts:
            merged.setdefault(module, Counter()).update(counts)
    return {module: dict(counts) for module, counts in merged.items()}


def _profile(doc: dict) -> list[dict]:
    """Each stage reduced to what it does, with every part replaced by its role."""
    role = _role_of(doc)
    out = []
    for name in doc["orchestrator"]["settings"]["execution_list"]:
        stage = doc["stages"][name]
        settings = stage["stage_settings"]
        preprocess = stage.get("stage_preprocess", {})

        switching = {}
        for operation in preprocess.get("operations", []):
            kind = "activate" if "Activate" in operation["name"] else "deactivate"
            switching[kind] = dict(Counter(role(n) for n in _named(operation)))

        solver = settings["solver_settings"]
        out.append({
            "modeler": bool(preprocess.get("modelers")),
            "switching": switching,
            "processes": {listing: _listing(listing, processes, role)
                          for listing, processes in settings["processes"].items()},
            "time": (settings["problem_data"]["start_time"],
                     settings["problem_data"]["end_time"]),
            "reset_totals": solver["reset_totals"],
            "materials": ("initial" if "initial" in
                          solver["material_import_settings"]["materials_filename"]
                          else "main"),
            "bodies": dict(Counter(
                role(n) for n in solver["problem_domain_sub_model_part_list"])),
        })
    return out


def test_the_deck_runs_the_same_seven_stages(parameters, reference_parameters):
    ours = parameters["orchestrator"]["settings"]
    theirs = reference_parameters["orchestrator"]["settings"]
    assert len(ours["execution_list"]) == len(theirs["execution_list"]) == 7
    assert list(parameters["stages"]) == ours["execution_list"]
    assert parameters["orchestrator"]["name"] == reference_parameters["orchestrator"]["name"]


@pytest.mark.parametrize("index", range(7))
def test_each_stage_matches_the_reference_stage_for_stage(
        index, parameters, reference_parameters):
    """One case per stage, so a failure names the stage rather than the whole deck."""
    assert _profile(parameters)[index] == _profile(reference_parameters)[index]


def test_the_two_decks_solve_with_the_same_analysis(parameters, reference_parameters):
    """Solver type, solution type, scheme and criterion -- the choices that say what
    kind of analysis this is, as opposed to how tightly any one stage is converged."""
    def analysis(doc):
        first = next(iter(doc["stages"].values()))["stage_settings"]["solver_settings"]
        return {key: first[key] for key in
                ("solver_type", "solution_type", "strategy_type",
                 "convergence_criterion", "domain_size", "rotation_dofs")}
    assert analysis(parameters) == analysis(reference_parameters)


def test_the_deck_is_missing_only_what_is_recorded_here(parameters, reference_parameters):
    """The divergence list above is a claim, and this is what holds it to its size."""
    def modules(doc):
        return {(listing, process["python_module"])
                for entry in doc["stages"].values()
                for listing, processes in entry["stage_settings"]["processes"].items()
                for process in processes}

    assert modules(reference_parameters) - modules(parameters) == MISSING_MODULES
    assert modules(parameters) - modules(reference_parameters) == set()


# -- The materials file ------------------------------------------------------
# The reference's six property sets, compared variable for variable. Paired by hand
# because the names differ by design (see this module's docstring): the reference groups
# six soil bodies under one property set where we write one entry per part, so a
# representative part of each group stands for it.

REFERENCE_INITIAL_MATERIALS = example_file(
    "crow_validation_initial_materials.json")

MATERIAL_PAIRS = [
    ("Soil_Top", 1, "the upper ground"),
    ("Soil_Bottom", 2, "the deeper sand"),
    ("Interface_Soil_Top", 3, "the contacts against the upper ground"),
    ("Interface_Soil_Bottom", 4, "the contacts against the sand"),
    ("SheetPileWall", 5, "the wall"),
    ("Strut", 6, "the tendon"),
]


@pytest.fixture(scope="module")
def reference_initial_materials() -> dict:
    if not REFERENCE_INITIAL_MATERIALS.exists():   # pragma: no cover - fixture guard
        pytest.skip(f"{REFERENCE_INITIAL_MATERIALS.name} is not present; the reference decks are kept out of the repository")
    return json.loads(REFERENCE_INITIAL_MATERIALS.read_text(encoding="utf-8"))


@pytest.mark.parametrize("part, index, label", MATERIAL_PAIRS)
def test_each_property_set_agrees_with_the_reference(
        part, index, label, export, reference_initial_materials):
    """Every variable the two files share carries the same number, for `label`.

    Shared, not identical: we also write permeability and the Mohr-Coulomb strength
    parameters the reference's linear-elastic soils have no use for, and it writes a
    retention block we deliberately do not (plan sec C4b). What both describe, they
    describe the same way.
    """
    ours = next(e["Material"]["Variables"]
                for e in json.loads(export["initial_materials"])["properties"]
                if e["model_part_name"] == f"PorousDomain.{part}")
    theirs = reference_initial_materials["properties"][index - 1]["Material"]["Variables"]

    shared = sorted(set(ours) & set(theirs))
    assert shared, f"nothing in common for {label}"
    differing = {key: (ours[key], theirs[key]) for key in shared
                 if ours[key] != theirs[key]
                 and not (isinstance(ours[key], float)
                          and abs(ours[key] - theirs[key]) <= 1e-4 * abs(theirs[key]))}
    assert differing == {}


def test_both_decks_use_the_same_constitutive_laws_for_the_soil(
        export, reference_initial_materials):
    ours = {e["Material"]["constitutive_law"]["name"]
            for e in json.loads(export["initial_materials"])["properties"]
            if e["model_part_name"].startswith("PorousDomain.Soil")}
    assert ours == {reference_initial_materials["properties"][0]["Material"][
        "constitutive_law"]["name"]}


# ── Orientation ─────────────────────────────────────────────────────────────
# What a line entity's node order means, and where it has to match the reference.
#
# For a beam the order is the local axis, so reversing it flips the sign of the axial
# force, bending moment and shear the `JsonOutputProcess` writes -- two runs of the same
# model would show mirrored diagrams. For a normal load it is the normal: the pressure
# is applied along the 90-degree rotation of the tangent, so a reversed segment pushes
# the wrong way. Neither shows up in a count of parts or elements, which is why they are
# checked here on the geometry itself.

def _tangent(deck: mdpa.Deck, connectivity: list[int]) -> tuple[float, float]:
    (x0, y0, _), (x1, y1, _) = (deck.nodes[n] for n in connectivity[:2])
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    return round((x1 - x0) / length, 6), round((y1 - y0) / length, 6)


def _normal(deck: mdpa.Deck, connectivity: list[int]) -> tuple[float, float]:
    """The 90-degree clockwise rotation of the tangent, which is the side the pressure
    of a `LineNormalLoadCondition` acts towards."""
    tx, ty = _tangent(deck, connectivity)
    return round(ty, 6), round(-tx, 6)


def _conditions(deck: mdpa.Deck) -> dict[int, list[int]]:
    return {cid: conn for block in deck.conditions for cid, conn in block.entries.items()}


def _beam_elements(deck: mdpa.Deck) -> list[list[int]]:
    return [conn for block in deck.elements
            if block.name == BEAM for conn in block.entries.values()]


def test_the_wall_runs_the_way_the_reference_does(deck, reference):
    """Every element of the sheet pile points down, as the reference's do, because that
    is the order its points are drawn in. Consistency alone is not enough: the sign of
    the wall's reported forces follows this."""
    for source, label in ((deck, "ours"), (reference, "the reference")):
        directions = {_tangent(source, conn)[1] < 0 for conn in _beam_elements(source)}
        assert directions == {True}, f"{label} does not run the wall downwards"


def test_the_wall_is_written_start_end_mid_like_the_reference(deck, reference):
    """Kratos' own 3-node ordering. The midside node is third, not second."""
    for source in (deck, reference):
        for conn in _beam_elements(source):
            (_, y0, _), (_, y1, _), (_, ym, _) = (source.nodes[n] for n in conn)
            assert abs(ym - (y0 + y1) / 2) < TOLERANCE


def test_each_water_load_pushes_into_the_excavation(deck, reference):
    """The whole loaded surface -- the wall face and the pit floor -- carries one
    outward normal, pointing from the ground that stays into the void that opens.

    The floor used to carry the opposite one. Its edge is shared between the lift being
    dug out and the body underneath, and the condition was aligned to the lift: the
    water then pressed down into ground that was about to be removed instead of up
    against the base of the excavation, which is the load that matters most there.
    """
    for source, label in ((deck, "ours"), (reference, "the reference")):
        conditions = _conditions(source)
        for stage in ("WaterLoad_Stage1", "WaterLoad_Stage2", "WaterLoad_Stage3"):
            normals = {_normal(source, conditions[cid])
                       for cid in part_of(source, stage).conditions}
            assert normals == {(-1.0, 0.0), (0.0, 1.0)}, f"{label}, {stage}: {normals}"


def test_the_interfaces_keep_the_orientation_the_reference_has(deck, reference):
    """Unchanged by the two fixes above, and worth pinning while they were made: the
    contact's first three nodes are the wall's copy and its last three the soil's, and
    the pit-side interfaces run up the wall where the retained-side ones run down."""
    for source in (deck, reference):
        wall = set(part_of(source, "SheetPileWall").nodes)
        entries = {}
        for block in source.elements:
            if block.name == CONTACT:
                entries.update(block.entries)
        owning = {e: n for n, p in source.parts.items() for e in p.elements}
        pit = {"lift", "_pit", "Excavated", "Below_Pit", "Middle_Left", "Bottom_Left"}
        for eid, conn in entries.items():
            assert set(conn[:3]) <= wall, "the first half is the wall's copy"
            assert not set(conn[3:]) & wall, "the second half is the soil's"
            name = owning[eid]
            upwards = _tangent(source, conn)[1] > 0
            assert upwards == any(tag in name for tag in pit), name


# What the reference's property sets carry and ours do not. Compared as a *set*, because
# comparing only the variables both files share cannot see one we leave out altogether --
# which is how a missing `GEO_DRAINAGE_TYPE` on the interfaces reached a real run, where
# Kratos defaulted them to `FULLY_COUPLED` and the wall-installation stage died on NaN.
# Anything that goes missing in future fails here, naming itself.

RETENTION_BLOCK = {"BIOT_COEFFICIENT", "RETENTION_LAW", "SATURATED_SATURATION",
                   "RESIDUAL_SATURATION", "MINIMUM_RELATIVE_PERMEABILITY"}
"""Deliberate: four of the five reference decks in this repo agree with what we emit --
permeability and a dynamic viscosity, no retention law -- and the CROW pair is the
outlier because STEM wrote it. Recorded rather than matched (plan sec C4b)."""

BEAM_SECTION_NAMES = {"THICKNESS", "THICKNESS_EFFECTIVE_Y"}
"""The same two numbers under the other beam law's names: the reference pairs its beam
with `TimoshenkoBeamPlaneStrainElasticConstitutiveLaw`, where we write
`TimoshenkoBeamElasticConstitutiveLaw` and call them `CROSS_AREA` and `AREA_EFFECTIVE_Y`
(plan sec 7.4)."""

ABSENT_FROM_OURS = {
    1: RETENTION_BLOCK, 2: RETENTION_BLOCK,
    3: RETENTION_BLOCK, 4: RETENTION_BLOCK,
    5: BEAM_SECTION_NAMES, 6: set(),
}


@pytest.mark.parametrize("part, index, label", MATERIAL_PAIRS)
def test_nothing_else_is_missing_from_a_property_set(
        part, index, label, export, reference_initial_materials):
    ours = next(e["Material"]["Variables"]
                for e in json.loads(export["initial_materials"])["properties"]
                if e["model_part_name"] == f"PorousDomain.{part}")
    theirs = reference_initial_materials["properties"][index - 1]["Material"]["Variables"]
    assert set(theirs) - set(ours) == ABSENT_FROM_OURS[index], label


# ── The wall's stiffness ────────────────────────────────────────────────────
# The two decks pair the beam with different constitutive laws, and that is deliberate
# (plan sec 7.4): the reference's `TimoshenkoBeamPlaneStrainElasticConstitutiveLaw`
# idealises the wall as a solid plate and derives both the area and the second moment
# from one `THICKNESS`, where ours takes them separately, because a real sheet pile's
# area and inertia are not related by t^3/12 and `BeamSection` is made for real profiles.
#
# What must not differ is the wall the two decks actually model. `THICKNESS = 0.4924` is
# not a plate anyone rolled: it is the thickness whose t^3/12 gives the second moment
# this case wants, and 0.4924 = (12 * 9.9489e-3)^(1/3) exactly. So the reference states
# its stiffness through a thickness and we state it directly, and these compare the
# stiffness rather than the numbers it is spelled with.

def _beam_material(source: dict, part: str) -> dict:
    wanted = {f"PorousDomain.{part}",
              f"PorousDomain.{REFERENCE_NAMES.get(part, part)}"}
    return next(e["Material"]["Variables"] for e in source["properties"]
                if e.get("model_part_name") in wanted)


def test_the_wall_bends_as_stiffly_as_the_reference_wall(
        export, reference_initial_materials):
    """EI per metre run. Ours was 3.38e7 against the reference's 8.40e7 -- two and a
    half times too soft -- because `examples/crow/crow.py` carried an inertia of its own where the
    reference derives one, and nothing in the deck compared the two."""
    ours = _beam_material(json.loads(export["initial_materials"]), "SheetPileWall")
    theirs = _beam_material(reference_initial_materials, "SheetPileWall")

    their_inertia = theirs["THICKNESS"] ** 3 / 12.0
    assert ours["YOUNG_MODULUS"] == pytest.approx(theirs["YOUNG_MODULUS"], rel=1e-6)
    assert ours["I33"] == pytest.approx(their_inertia, rel=1e-4)
    assert ours["YOUNG_MODULUS"] * ours["I33"] == pytest.approx(8.40e7, rel=1e-3)


def test_the_wall_stretches_as_stiffly_as_the_reference_wall(
        export, reference_initial_materials):
    """EA per metre run. The plane-strain law takes the area as the thickness itself."""
    ours = _beam_material(json.loads(export["initial_materials"]), "SheetPileWall")
    theirs = _beam_material(reference_initial_materials, "SheetPileWall")
    assert ours["CROSS_AREA"] == pytest.approx(theirs["THICKNESS"], rel=1e-6)


def test_the_wall_shears_as_stiffly_as_the_reference_wall(
        export, reference_initial_materials):
    """GA_s per metre run. `THICKNESS_EFFECTIVE_Y = 10.0` is twenty times the section's
    own area -- not a shear area anybody measured, but a way of saying that shear
    deformation is not part of this model. Ours took the full section and was twenty
    times softer, which is a real difference in a wall this short."""
    ours = _beam_material(json.loads(export["initial_materials"]), "SheetPileWall")
    theirs = _beam_material(reference_initial_materials, "SheetPileWall")
    assert ours["AREA_EFFECTIVE_Y"] == pytest.approx(theirs["THICKNESS_EFFECTIVE_Y"],
                                                     rel=1e-6)


# ── The wall's own mesh ─────────────────────────────────────────────────────

def test_the_wall_is_meshed_at_a_uniform_half_metre():
    """26 elements of 0.5 m, from the toe to the head, with no size change anywhere.

    Not a preference. The wall was meshed at whatever the box refinement around the
    excavation asked for, and gmsh then fitted a whole number of elements into each
    stretch between the lift levels -- so the wall came out in three sizes, 0.5 m at the
    toe and 0.667 m and 0.75 m above it. Comparing a run against the validation deck,
    every node that fell outside tolerance lay inside a 0.667 m or 0.75 m element and
    none lay in the 0.5 m band.

    The head is where it shows worst: the 20 kPa surcharge starts exactly at the wall, so
    the shear gradient there is steep, and a single 0.75 m element cannot represent it --
    the extrapolated value at the free head came out at 3360 against the reference's
    1986, where both should tend to zero.
    """
    project = crow.crow_project()
    with crow.build.session():
        exported = crow.kratos.export_project(
            project, crow.MeshRequest(**project.mesh.model_dump()))
    deck = mdpa.parse(exported["mdpa"])
    spans = sorted(
        (min(deck.nodes[c[0]][1], deck.nodes[c[1]][1]),
         max(deck.nodes[c[0]][1], deck.nodes[c[1]][1]))
        for block in deck.elements if block.name == BEAM
        for c in block.entries.values())

    assert len(spans) == 26
    lengths = {round(high - low, 6) for low, high in spans}
    assert lengths == {0.5}, sorted(lengths)
    # End to end with no gap: 26 x 0.5 m covers y = -13 to 0 exactly.
    assert spans[0][0] == pytest.approx(-13.0) and spans[-1][1] == pytest.approx(0.0)
    assert all(a[1] == pytest.approx(b[0]) for a, b in zip(spans, spans[1:]))


def test_the_top_of_the_wall_carries_three_elements_not_two():
    """The 1.5 m between the head and the strut, where the surcharge gradient is."""
    project = crow.crow_project()
    with crow.build.session():
        exported = crow.kratos.export_project(
            project, crow.MeshRequest(**project.mesh.model_dump()))
    deck = mdpa.parse(exported["mdpa"])
    top = [c for block in deck.elements if block.name == BEAM
           for c in block.entries.values()
           if min(deck.nodes[c[0]][1], deck.nodes[c[1]][1]) >= -1.5 - TOLERANCE]
    assert len(top) == 3


# ── Which nodes the water pushes on ─────────────────────────────────────────

def _owners(deck: mdpa.Deck) -> dict[int, set[str]]:
    out: dict[int, set[str]] = {}
    for name, part in deck.parts.items():
        for node in part.nodes:
            out.setdefault(node, set()).add(name)
    return out


def _water(deck: mdpa.Deck, stage: str):
    """(wall-face conditions, pit-floor conditions) of one water load."""
    conditions = {cid: c for block in deck.conditions
                  for cid, c in block.entries.items()}
    face, floor = [], []
    for cid in deck.parts[stage].conditions:
        connectivity = conditions[cid]
        vertical = abs(deck.nodes[connectivity[0]][0]
                       - deck.nodes[connectivity[1]][0]) < TOLERANCE
        (face if vertical else floor).append(connectivity)
    return face, floor


@pytest.mark.parametrize("stage", ["WaterLoad_Stage1", "WaterLoad_Stage2",
                                   "WaterLoad_Stage3"])
def test_the_water_pushes_on_the_wall_not_on_the_soil_behind_it(deck, stage):
    """Three nodes sit at every point of the wall line: the wall's own, and one copy per
    side of the soil the interface split. The exposed face of an excavation is the
    *wall*, so its water load belongs on the wall's copy.

    It was landing on the retained soil's, which is on the far side of the interface --
    so instead of pressing on the wall, the water pressed the retained ground away from
    it. The retained interface's traction drifted to zero and then into tension as the
    pit was dug, where it should have grown with depth.
    """
    face, _ = _water(deck, stage)
    assert face, stage
    owners = _owners(deck)
    for connectivity in face:
        for node in connectivity:
            assert "SheetPileWall" in owners.get(node, set()), (
                stage, node, sorted(owners.get(node, set())))


def test_the_water_on_the_pit_floor_still_stands_on_the_soil(deck):
    """Only the wall face moved. The floor of the excavation is ground, and its load
    belongs to the body that remains under it."""
    _, floor = _water(deck, "WaterLoad_Stage1")
    assert floor
    owners = _owners(deck)
    for connectivity in floor:
        assert not any("SheetPileWall" in owners.get(n, set()) for n in connectivity)


@pytest.mark.parametrize("stage", ["WaterLoad_Stage1", "WaterLoad_Stage2",
                                   "WaterLoad_Stage3"])
def test_the_loaded_nodes_are_listed_on_the_part_as_well(deck, stage):
    """`ApplyNormalLoadTableProcess` sets `NORMAL_CONTACT_STRESS` on the *sub-model
    part's* nodes, so moving the connectivity alone would leave the node list behind and
    silently drop the load. Both have to move together."""
    face, _ = _water(deck, stage)
    listed = set(deck.parts[stage].nodes)
    for connectivity in face:
        assert set(connectivity) <= listed, stage


@pytest.mark.parametrize("stage", ["WaterLoad_Stage1", "WaterLoad_Stage2",
                                   "WaterLoad_Stage3"])
def test_no_water_is_applied_above_the_water_table(deck, stage):
    """Hydrostatic pressure above the phreatic level is negative and clipped to zero, so
    conditions up there do nothing -- but they are still conditions, and the reference
    has none. The load starts where the water does."""
    face, _ = _water(deck, stage)
    highest = max(deck.nodes[n][1] for c in face for n in c)
    assert highest == pytest.approx(crow.WATER_Y)
