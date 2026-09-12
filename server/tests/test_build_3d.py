"""3D structures: wall panels, members and space anchors inside the solid model.

The 2D rules carry over unchanged -- ownership is rebuilt from the boolean's output
map, a structure is *fragmented into* the soil so the two share nodes, and an anchor is
deliberately left out of the topology -- but the shapes are one dimension up. A wall is
a swept surface inside a volume, where the 2D sheet pile was a curve inside a face; a
member is a curve inside a volume; and the anchor is still a bare line with a free tail.

Nothing here pins a Kratos element name; that lives in test_kratos.py. This file is
only about what OCC ends up holding.
"""

import gmsh
import pytest

from app import build
from app.schemas import Project
from app.seed import seed_project

SECTION_AZ26 = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
                "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}
WALL_AZ26 = {"id": "az26_wall", "name": "AZ 26-700 wall", "E": 2.1e8, "nu": 0.3,
             "thickness": 0.4, "density": 7850.0}
STRAND = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
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


def structured(beams: list[dict], anchors: list[dict] | None = None,
               simple: bool = True) -> Project:
    payload = seed_project(simple=simple).model_dump()
    payload["beam_sections"] = [SECTION_AZ26]
    payload["panel_sections"] = [WALL_AZ26]
    payload["anchor_sections"] = [STRAND]
    payload["beams"] = beams
    payload["anchors"] = anchors or []
    return Project.model_validate(payload)


def groups() -> dict[str, int]:
    return {gmsh.model.getPhysicalName(dim, tag): dim
            for dim, tag in gmsh.model.getPhysicalGroups()}


def conformity(result, entities: list[tuple[int, int]]) -> tuple[int, int, int]:
    """Mesh the model as it stands and measure whether a structure shares the soil's
    nodes.

    Conformity is a property of the mesh, not of the B-rep: an internal face bounds no
    volume, so `getAdjacencies` says nothing about it. What matters is that the soil
    elements use the very nodes the structure is meshed with, and that no second node
    sits at any of the same coordinates.

    Returns (structural nodes, of those used by soil elements, duplicated coordinates).
    """
    gmsh.option.setNumber("Mesh.MeshSizeMax", 6.0)
    gmsh.model.mesh.generate(3)
    structural: set[int] = set()
    for dim, tag in entities:
        tags, _, _ = gmsh.model.mesh.getNodes(dim, tag, includeBoundary=True)
        structural |= {int(t) for t in tags}
    soil = {tag for key, tags in result.volumes.items()
            if key.startswith("soil_") for tag in tags}
    used = {int(n) for tag in soil
            for connectivity in gmsh.model.mesh.getElements(3, tag)[2]
            for n in connectivity}
    all_tags, all_coords, _ = gmsh.model.mesh.getNodes()
    seen: set[tuple[float, ...]] = set()
    duplicates = 0
    for index in range(len(all_tags)):
        point = tuple(round(v, 6) for v in all_coords[3 * index:3 * index + 3])
        duplicates += point in seen
        seen.add(point)
    return len(structural), len(structural & used), duplicates


# ── Wall panels ─────────────────────────────────────────────────────────────

def test_a_panel_becomes_named_two_dimensional_faces():
    """Not a thin solid: a wall is a surface inside the volume, as the 2D pile is a
    curve inside the face."""
    with build.session():
        result = build.build_geometry(structured([PANEL]))
        named = groups()

    assert result.faces["panel_1"], "the wall must survive the build"
    assert named["panel_1"] == 2
    # It keeps its part key in the namespace, with no solid behind it.
    assert result.volumes.get("panel_1", []) == []


def test_the_panel_faces_span_exactly_the_footprint_and_levels_drawn():
    with build.session():
        result = build.build_geometry(structured([PANEL]))
        boxes = [gmsh.model.getBoundingBox(2, tag) for tag in result.faces["panel_1"]]

    assert min(b[0] for b in boxes) == pytest.approx(12.0, abs=1e-5)
    assert max(b[3] for b in boxes) == pytest.approx(12.0, abs=1e-5)
    assert min(b[2] for b in boxes) == pytest.approx(4.0, abs=1e-5)
    assert max(b[5] for b in boxes) == pytest.approx(20.0, abs=1e-5)
    assert min(b[1] for b in boxes) == pytest.approx(-14.0, abs=1e-5)
    assert max(b[4] for b in boxes) == pytest.approx(0.0, abs=1e-5)


def test_the_panel_is_fragmented_into_the_soil_so_the_two_share_nodes():
    """The conformity target, and the whole reason the wall is a fragment tool: the
    soil elements have to be built on the wall's own nodes."""
    with build.session():
        result = build.build_geometry(structured([PANEL]))
        total, shared, duplicates = conformity(
            result, [(2, tag) for tag in result.faces["panel_1"]]
        )

    assert total, "the wall meshed to nothing"
    assert shared == total, f"{total - shared} of {total} wall nodes are not soil nodes"
    assert duplicates == 0, "a second node sits on top of a wall node"


def test_a_wall_that_stops_inside_the_soil_does_not_cut_the_body_in_two():
    """A panel shorter than the block leaves the soil one volume, imprinted."""
    shallow = PANEL | {"y_toe": -6.0, "footprint": [[12.0, 8.0], [12.0, 16.0]]}
    with build.session():
        result = build.build_geometry(structured([shallow]))
        soil = [tag for key, tags in result.volumes.items()
                if key.startswith("soil_") for tag in tags]

    # Two layers in the seed, and neither is split by a wall that ends mid-body.
    assert len(soil) == len(seed_project(simple=True).layers)
    assert result.faces["panel_1"]


def test_an_inactive_panel_is_not_built():
    with build.session():
        result = build.build_geometry(structured([PANEL | {"active": False}]))

    assert result.faces.get("panel_1", []) == []


def test_a_panel_is_not_built_into_a_2d_section_and_says_so():
    """The mirror of the 2D pile in 3D: a wall in plan has no place in an x-y cut."""
    payload = structured([PANEL]).model_dump() | {"dimension": 2}
    project = Project.model_validate(payload)
    with build.session():
        result = build.build_geometry(project)

    assert result.faces.get("panel_1", []) == []
    assert any("panel_1" in line for line in result.log)


# ── Members ─────────────────────────────────────────────────────────────────

def test_a_member_becomes_named_one_dimensional_curves():
    with build.session():
        result = build.build_geometry(structured([MEMBER]))
        named = groups()

    assert result.curves["member_1"]
    assert named["member_1"] == 1
    assert result.volumes.get("member_1", []) == []


def test_the_member_curves_span_exactly_the_polyline_drawn():
    with build.session():
        result = build.build_geometry(structured([MEMBER]))
        boxes = [gmsh.model.getBoundingBox(1, tag) for tag in result.curves["member_1"]]

    assert min(b[1] for b in boxes) == pytest.approx(-12.0, abs=1e-5)
    assert max(b[4] for b in boxes) == pytest.approx(0.0, abs=1e-5)
    assert all(b[0] == pytest.approx(18.0, abs=1e-5) for b in boxes)
    assert all(b[2] == pytest.approx(10.0, abs=1e-5) for b in boxes)


def test_the_member_is_fragmented_into_the_soil_it_stands_in():
    """Same contract as the wall, one dimension lower: a pile the soil does not share
    nodes with is a pile the soil slides past."""
    with build.session():
        result = build.build_geometry(structured([MEMBER]))
        total, shared, duplicates = conformity(
            result, [(1, tag) for tag in result.curves["member_1"]]
        )

    assert total, "the member meshed to nothing"
    assert shared == total, f"{total - shared} of {total} member nodes are not soil nodes"
    assert duplicates == 0


def test_a_wall_and_a_member_can_stand_in_one_model():
    with build.session():
        result = build.build_geometry(structured([PANEL, MEMBER]))
        named = groups()

    assert result.faces["panel_1"] and result.curves["member_1"]
    assert named["panel_1"] == 2 and named["member_1"] == 1


# ── Space anchors ───────────────────────────────────────────────────────────

def test_a_space_anchor_is_drawn_as_a_bare_line_with_a_free_tail():
    with build.session():
        result = build.build_geometry(structured([PANEL], [ANCHOR]))
        named = groups()

    assert result.ties["anchor_1"], "the tie must be drawn"
    assert named["anchor_1"] == 1
    assert named["anchor_1_Support"] == 0
    assert result.tie_nodes["anchor_1"], "the tail needs a 0D entity to mesh a node on"


def test_the_tie_runs_from_the_head_on_the_wall_to_the_tail():
    with build.session():
        result = build.build_geometry(structured([PANEL], [ANCHOR]))
        boxes = [gmsh.model.getBoundingBox(1, tag) for tag in result.ties["anchor_1"]]

    assert min(b[0] for b in boxes) == pytest.approx(12.0, abs=1e-5)
    assert max(b[3] for b in boxes) == pytest.approx(17.0, abs=1e-5)
    assert min(b[1] for b in boxes) == pytest.approx(-8.0, abs=1e-5)
    assert max(b[4] for b in boxes) == pytest.approx(-2.0, abs=1e-5)


def test_the_tie_is_not_fragmented_into_the_soil():
    """The grouted body is idealised as a fixed point, exactly as in 2D: bonding the
    tie into the mesh would model a fully grouted bar instead."""
    with build.session():
        result = build.build_geometry(structured([PANEL], [ANCHOR]))
        soil = {tag for key, tags in result.volumes.items()
                if key.startswith("soil_") for tag in tags}
        touching = {v for tag in result.ties["anchor_1"]
                    for face in gmsh.model.getAdjacencies(1, tag)[0]
                    for v in gmsh.model.getAdjacencies(2, face)[0]}

    assert not (touching & soil), "the tie was absorbed into the soil topology"


def test_an_anchor_head_splits_the_member_it_hangs_from():
    """The same trick the 2D pile uses: split at the head and the shared node is free."""
    on_member = ANCHOR | {"head": [18.0, -4.0, 10.0], "tail": [22.0, -9.0, 10.0]}
    with build.session():
        result = build.build_geometry(structured([MEMBER], [on_member]))
        ends = set()
        for tag in result.curves["member_1"]:
            for point in gmsh.model.getAdjacencies(1, tag)[1]:
                ends.add(tuple(round(v, 6) for v in gmsh.model.getValue(0, point, [])))

    assert (18.0, -4.0, 10.0) in ends, "the head is not a vertex of the member"


def test_an_inactive_space_anchor_is_not_built():
    with build.session():
        result = build.build_geometry(
            structured([PANEL], [ANCHOR | {"active": False}])
        )

    assert result.ties.get("anchor_1", []) == []


def test_a_space_anchor_is_not_built_into_a_2d_section_and_says_so():
    payload = structured([PANEL], [ANCHOR]).model_dump() | {"dimension": 2}
    project = Project.model_validate(payload)
    with build.session():
        result = build.build_geometry(project)

    assert result.ties.get("anchor_1", []) == []
    assert any("anchor_1" in line for line in result.log)


# ── The full (non-simple) model takes them too ──────────────────────────────

def test_the_full_example_builds_the_3d_structures_as_well():
    with build.session():
        result = build.build_geometry(structured([PANEL, MEMBER], [ANCHOR], simple=False))

    assert result.faces["panel_1"] and result.curves["member_1"]
    assert result.ties["anchor_1"]


# ── Display buffers ─────────────────────────────────────────────────────────
#
# What the viewport is handed. A wall has a surface to triangulate, unlike every other
# structural part built so far, so it is the one that needed a new branch.

def test_a_wall_is_drawn_as_a_surface_and_a_member_as_edges():
    from app import tessellate

    with build.session():
        model = tessellate.tessellate(structured([PANEL, MEMBER], [ANCHOR]))

    wall = next(s for s in model.sections if s.key == "panel_1")
    assert wall.indices, "a wall is a surface: there is something to triangulate"
    assert wall.edges, "and it keeps its outline"
    assert min(wall.positions[1::3]) == pytest.approx(-14.0, abs=1e-4)
    assert max(wall.positions[1::3]) == pytest.approx(0.0, abs=1e-4)

    member = next(s for s in model.sections if s.key == "member_1")
    assert member.edges and not member.indices, "a member is a curve"

    tie = next(s for s in model.sections if s.key == "anchor_1")
    assert tie.edges and not tie.indices


def test_every_part_key_still_gets_a_section_with_3d_structures_present():
    from app import tessellate

    project = structured([PANEL, MEMBER], [ANCHOR])
    with build.session():
        model = tessellate.tessellate(project)

    assert set(project.part_keys()) <= {s.key for s in model.sections}
