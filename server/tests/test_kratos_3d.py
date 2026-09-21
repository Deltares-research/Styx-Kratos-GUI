"""Kratos export of the 3D structures: wall panels, members and space anchors.

The 2D contracts are read off real decks in examples/; every one of them is plane
strain, so nothing here has a fixture behind it. What *is* carried over unchanged is
the arrangement those decks pin down, one dimension up:

  * structural elements keep property 0, and bind their real properties by sub-model
    part name in MaterialParameters.json;
  * a structure's nodes are the soil's nodes, not a second set on top of them;
  * an anchor is one linear two-node truss whatever the mesh order, with its head node
    shared with the structure it hangs from and its tail node in no other element,
    alone in a one-node support group that a constraint process pins.

The element class names themselves are named in one place (app/kratos.py) and flagged
as unconfirmed; these tests hold the arrangement, not the spelling, wherever they can.
"""

import json

import pytest

from app import build, kratos
from app.kratos_materials import KILO
from app.schemas import MeshRequest, Project
from app.seed import seed_project
from tests import mdpa


def _stage_settings(export: dict) -> dict:
    """The lone stage's settings, found by position rather than by name -- the
    orchestrator can name its one stage however it likes."""
    doc = json.loads(export["project_parameters"])
    return next(iter(doc["stages"].values()))["stage_settings"]

SECTION_AZ26 = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
                "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}
WALL_AZ26 = {"id": "az26_wall", "name": "AZ 26-700 wall", "E": 2.1e8, "nu": 0.3,
             "thickness": 0.4, "density": 7850.0}
TENDON = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
          "density": 7850.0, "spacing": 2.5, "tension_limit": 900.0,
          "compression_limit": None}

PANEL = {"id": "panel_1", "name": "Wall 1", "kind": "panel", "section": "az26_wall",
         "footprint": [[12.0, 4.0], [12.0, 20.0]], "y_top": 0.0, "y_toe": -14.0,
         "active": True}
MEMBER = {"id": "member_1", "name": "King post 1", "kind": "member", "section": "az26",
          "points": [[18.0, 0.0, 10.0], [18.0, -12.0, 10.0]], "active": True}
ANCHOR = {"id": "anchor_1", "name": "Anchor 1", "kind": "anchor3d", "section": "strand",
          "head": [12.0, -2.0, 10.0], "tail": [17.0, -8.0, 10.0], "prestress": 250.0,
          "active": True}


def structured(beams: list[dict], anchors: list[dict] | None = None) -> Project:
    payload = seed_project(simple=True).model_dump()
    payload["beam_sections"] = [SECTION_AZ26]
    payload["panel_sections"] = [WALL_AZ26]
    payload["anchor_sections"] = [TENDON]
    payload["beams"] = beams
    payload["anchors"] = anchors or []
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def session():
    with build.session():
        yield


@pytest.fixture(scope="module")
def walled(session):
    """A wall, a member and an anchor in one quadratic 3D deck."""
    return kratos.export_project(structured([PANEL, MEMBER], [ANCHOR]),
                                 MeshRequest(element_size=6.0, order=2))


def deck_of(export: dict) -> mdpa.Deck:
    return mdpa.parse(export["mdpa"])


def shells_of(deck: mdpa.Deck):
    return next(b for b in deck.elements if "Shell" in b.name)


def beams_of(deck: mdpa.Deck):
    return next(b for b in deck.elements if "Beam" in b.name)


def truss_of(deck: mdpa.Deck):
    return next(b for b in deck.elements if "Truss" in b.name)


# ── Wall panels as shells ───────────────────────────────────────────────────

def test_the_wall_is_written_as_three_node_shell_elements(walled):
    """Kratos' shells are 3- and 4-node only: there is no quadratic shell to pair with
    a quadratic soil mesh, so a wall is always written from its corner nodes."""
    deck = deck_of(walled)
    block = shells_of(deck)

    assert block.name.endswith("3D3N")
    assert all(len(nodes) == 3 for nodes in block.entries.values())
    assert set(block.properties.values()) == {0}


def test_a_quadratic_mesh_says_the_wall_is_written_linear(walled):
    """Surfaced, not silent: the wall is a linear shell inside a quadratic soil mesh,
    which is a modelling compromise the user has to know about."""
    assert any("order 1" in w and "wall" in w.lower() for w in walled["warnings"]), \
        walled["warnings"]


def test_a_linear_mesh_writes_the_wall_with_no_such_warning(session):
    export = kratos.export_project(structured([PANEL]),
                                   MeshRequest(element_size=6.0, order=1))

    assert shells_of(deck_of(export)).entries
    assert not any("order 1" in w for w in export["warnings"])


def test_every_wall_node_is_a_soil_node_in_the_written_deck(walled):
    """The conformity contract, at the only place it finally matters: one deck, one
    node at the wall, with soil elements built on it."""
    deck = deck_of(walled)
    wall = {n for nodes in shells_of(deck).entries.values() for n in nodes}
    soil = {n for block in deck.elements if "UPw" in block.name or "DiffOrder" in block.name
            for nodes in block.entries.values() for n in nodes}

    assert wall, "no wall elements were written"
    assert wall <= soil, f"{len(wall - soil)} wall nodes are attached to no soil element"


def test_the_wall_gets_its_own_sub_model_part(walled):
    deck = deck_of(walled)
    part = deck.parts["Wall_1"]
    block = shells_of(deck)

    assert set(part.elements) == set(block.entries)
    assert part.nodes == sorted({n for nodes in block.entries.values() for n in nodes})


def test_the_panel_section_becomes_a_material_entry_mapped_to_its_part(walled):
    entries = json.loads(walled["materials"])["properties"]
    entry = next(e for e in entries if e["model_part_name"] == "PorousDomain.Wall_1")
    variables = entry["Material"]["Variables"]

    assert entry["Material"]["constitutive_law"]["name"]
    assert variables["YOUNG_MODULUS"] == pytest.approx(2.1e8 * KILO)
    assert variables["POISSON_RATIO"] == pytest.approx(0.3)
    assert variables["THICKNESS"] == pytest.approx(0.4)
    assert variables["DENSITY"] == pytest.approx(7850.0)
    # A thickness is the whole point of a shell: no per-metre-run reduction here.
    assert "CROSS_AREA" not in variables and "I33" not in variables


def test_an_inactive_wall_is_not_exported(session):
    export = kratos.export_project(structured([PANEL | {"active": False}]),
                                   MeshRequest(element_size=6.0, order=1))
    deck = deck_of(export)

    assert not any("Shell" in block.name for block in deck.elements)
    assert "Wall_1" not in deck.parts


def test_a_wall_saved_in_a_2d_project_is_not_exported(session):
    payload = structured([PANEL]).model_dump() | {"dimension": 2, "section_offset": 12.5}
    export = kratos.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=6.0, order=2))

    assert not any("Shell" in block.name for block in deck_of(export).elements)


# ── Members as 3D beams ─────────────────────────────────────────────────────

def test_the_member_is_written_as_a_three_dimensional_beam(walled):
    deck = deck_of(walled)
    block = beams_of(deck)

    assert "3D" in block.name
    assert set(block.properties.values()) == {0}


def test_every_member_node_is_a_soil_node_in_the_written_deck(walled):
    deck = deck_of(walled)
    member = {n for nodes in beams_of(deck).entries.values() for n in nodes}
    soil = {n for block in deck.elements if "UPw" in block.name or "DiffOrder" in block.name
            for nodes in block.entries.values() for n in nodes}

    assert member and member <= soil


def test_the_member_takes_the_sheet_piles_profile_library(walled):
    entries = json.loads(walled["materials"])["properties"]
    entry = next(e for e in entries if e["model_part_name"] == "PorousDomain.King_post_1")
    variables = entry["Material"]["Variables"]

    assert variables["YOUNG_MODULUS"] == pytest.approx(2.1e8 * KILO)
    assert variables["CROSS_AREA"] == pytest.approx(0.0198)
    assert variables["I33"] == pytest.approx(5.52e-4)
    # A beam in space bends about two axes and twists about the third.
    assert variables["I22"] == pytest.approx(5.52e-4)
    assert variables["TORSIONAL_INERTIA"] > 0


# ── Space anchors as two-node ties ──────────────────────────────────────────

def test_the_space_anchor_is_written_as_a_single_two_node_truss(walled):
    deck = deck_of(walled)
    block = truss_of(deck)

    assert block.name.endswith("3D2N")
    assert len(block.entries) == 1
    assert all(len(nodes) == 2 for nodes in block.entries.values())
    assert set(block.properties.values()) == {0}


def test_the_tie_runs_from_the_head_to_the_tail_the_user_drew(walled):
    deck = deck_of(walled)
    head, tail = (deck.nodes[n] for n in next(iter(truss_of(deck).entries.values())))

    assert head == pytest.approx((12.0, -2.0, 10.0), abs=1e-6)
    assert tail == pytest.approx((17.0, -8.0, 10.0), abs=1e-6)


def test_the_anchor_head_node_is_a_node_of_the_wall_it_hangs_from(walled):
    """Shared, not merely coincident: the tie and the wall must be one structure."""
    deck = deck_of(walled)
    head = next(iter(truss_of(deck).entries.values()))[0]
    wall = {n for nodes in shells_of(deck).entries.values() for n in nodes}

    assert head in wall


def test_the_anchor_tail_node_is_attached_to_nothing_else(walled):
    deck = deck_of(walled)
    tail = next(iter(truss_of(deck).entries.values()))[1]
    others = {n for block in deck.elements if "Truss" not in block.name
              for nodes in block.entries.values() for n in nodes}

    assert tail not in others


def test_the_anchor_gets_its_own_part_and_a_support_group_for_its_tail(walled):
    deck = deck_of(walled)
    head, tail = next(iter(truss_of(deck).entries.values()))
    part = deck.parts["Anchor_1"]
    support = deck.parts["Anchor_1_Support"]

    assert part.nodes == sorted([head, tail])
    assert support.nodes == [tail]
    assert not support.elements and not support.conditions


def test_the_tail_support_is_fixed_in_all_three_directions(walled):
    constraints = {p["Parameters"]["model_part_name"]: p["Parameters"]
                   for p in _stage_settings(walled)["processes"]["constraints_process_list"]}
    fixity = constraints["PorousDomain.Anchor_1_Support"]

    assert fixity["is_fixed"] == [True, True, True], "a 3D tail is pinned in space"
    assert fixity["value"] == [0.0, 0.0, 0.0]


def test_the_tendon_becomes_a_material_entry_with_its_prestress(walled):
    entries = json.loads(walled["materials"])["properties"]
    entry = next(e for e in entries if e["model_part_name"] == "PorousDomain.Anchor_1")
    variables = entry["Material"]["Variables"]

    assert variables["YOUNG_MODULUS"] == pytest.approx(1.95e8 * KILO)
    # Discrete in 3D: the plane-strain smear over the out-of-plane spacing is exactly
    # what a 3D model does not do, because the anchor is where the user put it.
    assert variables["CROSS_AREA"] == pytest.approx(0.0006)
    assert variables["TRUSS_PRESTRESS_PK2"] == pytest.approx(250.0 * KILO)


def test_an_anchor_may_hang_from_a_member_instead_of_a_wall(session):
    on_member = ANCHOR | {"head": [18.0, -4.0, 10.0], "tail": [22.0, -9.0, 10.0]}
    export = kratos.export_project(structured([MEMBER], [on_member]),
                                   MeshRequest(element_size=6.0, order=1))
    deck = deck_of(export)
    head = next(iter(truss_of(deck).entries.values()))[0]
    member = {n for nodes in beams_of(deck).entries.values() for n in nodes}

    assert head in member


def test_an_inactive_space_anchor_is_not_exported(session):
    export = kratos.export_project(structured([PANEL], [ANCHOR | {"active": False}]),
                                   MeshRequest(element_size=6.0, order=1))
    deck = deck_of(export)

    assert not any("Truss" in block.name for block in deck.elements)
    assert "Anchor_1" not in deck.parts


def test_a_space_anchor_saved_in_a_2d_project_is_not_exported(session):
    payload = structured([PANEL], [ANCHOR]).model_dump() | {"dimension": 2,
                                                            "section_offset": 12.5}
    export = kratos.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=6.0, order=2))

    assert not any("Truss" in block.name for block in deck_of(export).elements)


# ── The deck as a whole ─────────────────────────────────────────────────────

def test_property_ids_stay_unique_across_soil_wall_member_and_tendon(walled):
    entries = json.loads(walled["materials"])["properties"]
    ids = [entry["properties_id"] for entry in entries]

    assert len(set(ids)) == len(ids)
    assert all(i > 0 for i in ids)


def test_every_node_written_is_used_and_ids_are_contiguous(walled):
    deck = deck_of(walled)
    used = {n for block in deck.elements for nodes in block.entries.values() for n in nodes}
    used |= {n for block in deck.conditions for nodes in block.entries.values() for n in nodes}

    assert sorted(deck.nodes) == list(range(1, len(deck.nodes) + 1))
    assert used <= set(deck.nodes)


# ── 2D structures carried into the 3D deck ──────────────────────────────────
#
# A sheet pile and a plane anchor are drawn in the section and built on it in the solid
# model too (build._section_sweeps). Having built them, the deck has to carry them: a
# structure the viewport shows but Calculate silently drops is worse than one that was
# never there.

PILE = {"id": "sheetpile_1", "name": "Sheet pile 1", "kind": "beam",
        "section": "az26", "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}
PLANE_ANCHOR = {"id": "anchor_2d", "name": "Anchor 2D", "kind": "anchor",
                "section": "strand", "head": [12.0, -2.0], "tail": [18.0, -8.0],
                "prestress": 250.0, "active": True}


@pytest.fixture(scope="module")
def sectioned(session):
    """A 2D sheet pile and a 2D anchor, exported from a *3D* project."""
    return kratos.export_project(structured([PILE], [PLANE_ANCHOR]),
                                 MeshRequest(element_size=6.0, order=1))


def test_a_sheet_pile_reaches_the_3d_deck_as_a_shell(sectioned):
    """Swept into a surface, so it is a shell here -- not the beam a section writes."""
    block = shells_of(deck_of(sectioned))

    assert block.entries
    assert set(block.properties.values()) == {0}


def test_the_sheet_pile_gets_its_own_sub_model_part(sectioned):
    deck = deck_of(sectioned)

    assert "Sheet_pile_1" in deck.parts, list(deck.parts)


def test_the_pile_shell_thickness_is_the_profiles_area_per_metre_run(sectioned):
    """`area` is m2 per metre run, which is exactly a thickness in metres. The sweep
    width never enters it: widening the strip adds no steel."""
    materials = json.loads(sectioned["materials"])
    thicknesses = [
        m["Material"]["Variables"]["THICKNESS"]
        for m in materials["properties"]
        if "THICKNESS" in m["Material"]["Variables"]
    ]

    assert pytest.approx(SECTION_AZ26["area"]) in thicknesses


def test_a_plane_anchor_reaches_the_3d_deck_as_a_truss(sectioned):
    block = truss_of(deck_of(sectioned))

    assert block.entries
    assert all(len(nodes) == 2 for nodes in block.entries.values())


def test_the_plane_anchors_tail_is_pinned_in_all_three_directions(sectioned):
    """A 3D deck restrains z as well; the 2D origin of the record changes nothing."""
    processes = _stage_settings(sectioned)["processes"]
    constraints = [
        p for p in processes["constraints_process_list"]
        if "anchor_2d" in p["Parameters"]["model_part_name"].lower()
    ]

    assert constraints, processes["constraints_process_list"]
    assert constraints[0]["Parameters"]["is_fixed"] == [True, True, True]


# ── 2D loads that reach a 3D deck ───────────────────────────────────────────
#
# A point load and a line load below the ground surface have no surface form (a
# SurfaceLoad has no z of its own), so `app/loads.py` translates neither and the solid
# model carries them at the section plane instead. What the deck can do with them
# differs, and the difference is said out loud rather than left to be discovered.

POINT_LOAD = {"id": "pointload_1", "name": "PointLoad_1", "kind": "point",
              "x": 10.0, "y": 0.0, "components": [0.0, -30.0], "active": True}
BURIED_LINE = {"id": "lineload_2", "name": "LineLoad_2", "kind": "line",
               "x0": 4.0, "x1": 16.0, "y": -5.0, "components": [0.0, -25.0],
               "active": True}


def loaded(loads: list[dict]) -> Project:
    payload = seed_project(simple=True).model_dump()
    payload["loads"] = loads
    return Project.model_validate(payload)


def test_a_2d_point_load_is_written_as_a_3d_point_condition(session):
    """It has a node to sit on wherever it is, so the dimension costs it nothing."""
    export = kratos.export_project(loaded([POINT_LOAD]),
                                   MeshRequest(element_size=6.0, order=1))
    deck = deck_of(export)

    block = next((b for b in deck.conditions if "PointLoad" in b.name), None)
    assert block is not None, [b.name for b in deck.conditions]
    assert "3D" in block.name


def test_a_buried_line_load_in_3d_warns_rather_than_vanishing(session):
    """Kratos has no 3D line-load condition in this deck's table, so it cannot be
    written -- and a load that is drawn but not applied has to be said out loud."""
    export = kratos.export_project(loaded([BURIED_LINE]),
                                   MeshRequest(element_size=6.0, order=1))

    assert any("LineLoad_2" in w for w in export["warnings"]), export["warnings"]


# ── Staged construction in 3D ───────────────────────────────────────────────
# `kratos.py`'s two `if dim == 2 else []` guards keep a 3D deck from staging its
# structures: no automatic wall-installation stage, and no master/slave tie. That is
# the restriction plan sec 7.13 says to keep -- but it used to be silent, and the
# phases panel is visible in 3D projects, so a user could build a sequence here and
# never be told which part of it the deck dropped.
#
# What the guards do *not* stop is the phase list itself, and these tests say so in
# both directions: the warning is about the structures, not about staging as a whole.

def _phased(project: Project, activate: list[str]) -> Project:
    payload = project.model_dump()
    payload["phases"] = [
        {"id": "initial", "name": "Initial", "calculation": "K0 procedure",
         "deactivate": activate},
        {"id": "build", "name": "Build", "parent": "initial", "activate": activate},
    ]
    return Project.model_validate(payload)


def test_a_3d_phase_list_still_activates_and_deactivates_its_parts(session):
    """The restriction is narrower than "staging is 2D only", and a warning that
    claimed otherwise would send a user to redraw a model that works.

    A panel and an anchor switched off in the first phase and on in the second come
    out as a Deactivate and an Activate operation, exactly as they would in plane
    strain. Only the *implicit* sheet-pile staging and the interface ties are dropped.
    """
    export = kratos.export_project(
        _phased(structured([PANEL, MEMBER], [ANCHOR]), ["panel_1", "anchor_1"]),
        MeshRequest(element_size=6.0, order=1))
    doc = json.loads(export["project_parameters"])

    assert doc["orchestrator"]["settings"]["execution_list"] == ["1_Initial", "2_Build"]
    operations = {
        name: [op["Parameters"]["model_part_name_list"]
               for op in stage.get("stage_preprocess", {}).get("operations", [])]
        for name, stage in doc["stages"].items()
    }
    assert operations["1_Initial"] == [["PorousDomain.Wall_1", "PorousDomain.Anchor_1"]]
    assert operations["2_Build"] == [["PorousDomain.Wall_1", "PorousDomain.Anchor_1"]]


def test_a_3d_project_with_structures_says_they_are_not_staged(session):
    """The silent skip, made audible. A 2D deck installs its wall in a stage of its
    own even with no phases at all; the same model in 3D gets one stage and said
    nothing about the difference."""
    export = kratos.export_project(structured([PANEL, MEMBER], [ANCHOR]),
                                   MeshRequest(element_size=6.0, order=1))

    note = [w for w in export["warnings"] if "not staged" in w]
    assert note, export["warnings"]
    assert "3D" in note[0] or "plane strain" in note[0]


def test_the_note_is_absent_from_a_3d_project_with_nothing_to_stage(session):
    """No structures, nothing withheld, nothing to say. A warning that fires on every
    3D export is one people learn to skip past."""
    export = kratos.export_project(seed_project(simple=True),
                                   MeshRequest(element_size=6.0, order=1))

    assert not any("not staged" in w for w in export["warnings"]), export["warnings"]


def test_the_note_is_absent_in_plane_strain(session):
    """2D is the case where the structures *are* staged."""
    payload = structured([PANEL, MEMBER], [ANCHOR]).model_dump()
    payload["dimension"] = 2
    export = kratos.export_project(Project.model_validate(payload),
                                   MeshRequest(element_size=6.0, order=1))

    assert not any("not staged" in w for w in export["warnings"]), export["warnings"]
