"""Plane-strain meshing: triangles on the section face, not tetrahedra in a solid.

Everything gmsh needs told differently in 2D is asserted here, because each one fails
quietly rather than loudly: `generate(2)` instead of `generate(3)`, `Mesh.Algorithm`
instead of `Mesh.Algorithm3D`, and a `Restrict` field driven by `SurfacesList` rather
than `VolumesList` -- that last one simply has no effect if left as it was, so a
per-layer size would be silently ignored and every element would come out the same size.
"""

import pytest

from app import build, meshing
from app.schemas import BoxRefinement, Project
from app.seed import seed_project


def section_project(simple: bool = True, **extra) -> Project:
    return Project.model_validate(
        seed_project(simple=simple).model_dump() | {"dimension": 2} | extra
    )


@pytest.fixture(scope="module")
def quadratic():
    project = section_project()
    with build.session():
        yield project, meshing.mesh_project(project, element_size=2.0, order=2)


def test_real_surface_elements_are_generated(quadratic):
    _, mesh = quadratic
    assert mesh.stats.elements > 0
    assert mesh.stats.nodes > 0


def test_the_mesh_is_triangles_and_nothing_solid(quadratic):
    import gmsh

    triangle = gmsh.model.mesh.getElementType("Triangle", 2)
    types, elements, nodes = gmsh.model.mesh.getElements(2)
    by_type = {int(t): (e, n) for t, e, n in zip(types, elements, nodes)}
    assert set(by_type) == {triangle}

    # Order 2 in 2D is the six-node triangle, not the ten-node tetrahedron.
    element_tags, node_tags = by_type[triangle]
    assert len(node_tags) == len(element_tags) * 6

    solid_elements = sum(len(tags) for tags in gmsh.model.mesh.getElements(3)[1])
    assert solid_elements == 0, "a plane-strain model has no volume elements"


def test_stats_are_internally_consistent(quadratic):
    stats = quadratic[1].stats
    assert sum(stats.by_type.values()) == stats.elements
    assert sum(stats.quality_histogram.values()) == stats.elements
    assert stats.quality_histogram["<0.0"] == 0, "inverted triangles are not a usable mesh"


def test_every_node_lies_on_the_section_plane(quadratic):
    """Which is z = 0: the cut is taken at `section_offset` and moved onto the x-y
    plane, so the mesh has no third coordinate to speak of."""
    import gmsh

    _, mesh = quadratic
    _, coordinates, _ = gmsh.model.mesh.getNodes()
    for z in coordinates[2::3]:
        assert z == pytest.approx(0.0, abs=1e-6)


def test_the_payload_is_drawable_and_finite(quadratic):
    _, mesh = quadratic
    assert mesh.sections
    for section in mesh.sections:
        assert section.key == "mesh"
        assert section.indices and len(section.indices) % 3 == 0
        assert max(section.indices) < len(section.positions) // 3
        assert len(section.edges) % 6 == 0


def test_a_finer_body_size_actually_refines_that_body():
    """The Restrict field must be given SurfacesList in 2D. Left as VolumesList it
    matches nothing, gmsh reports no error, and the size is silently ignored."""
    project = section_project()
    coarse_key = f"soil_{project.layers[0].id}"
    with build.session():
        coarse = meshing.mesh_project(project, element_size=4.0, order=1)
        fine = meshing.mesh_project(project, element_size=4.0, order=1,
                                    body_sizes={coarse_key: 1.0})
    assert fine.stats.elements > coarse.stats.elements * 1.5


def test_a_local_refinement_box_still_applies():
    project = section_project()
    d = project.domain
    box = BoxRefinement(kind="box", size=0.8,
                        x_min=d.x0, x_max=d.x1 / 2,
                        z_min=d.z0 - 1, z_max=d.z1 + 1,
                        y_min=d.y_bottom, y_max=d.y_top)
    with build.session():
        plain = meshing.mesh_project(project, element_size=4.0, order=1)
        refined = meshing.mesh_project(project, element_size=4.0, order=1, refinements=[box])
    assert refined.stats.elements > plain.stats.elements


def test_meshing_reports_which_keys_it_meshed():
    project = section_project()
    with build.session():
        mesh = meshing.mesh_project(project, element_size=4.0, order=1)
    assert set(mesh.meshed_keys) <= set(project.part_keys())
    assert mesh.meshed_keys


# ── Mixed-dimensional meshing: 2D soil with 1D sheet piles ──────────────────

def piled_section(points=((12.0, 0.0), (12.0, -14.0))) -> Project:
    payload = section_project().model_dump()
    payload["beam_sections"] = [{"id": "az26", "name": "AZ 26-700", "E": 2.1e8,
                                 "nu": 0.3, "area": 0.0198, "inertia": 5.52e-4,
                                 "density": 7850.0, "spacing": 1.0}]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [list(p) for p in points], "active": True}]
    return Project.model_validate(payload)


def beam_mesh(project: Project, order: int = 2) -> tuple[list[int], set[int], set[int]]:
    """(line element types, beam node ids, soil node ids) after a real mesh run."""
    import gmsh
    meshing.mesh_project(project, element_size=3.0, order=order)
    types, beam_nodes, soil_nodes = [], set(), set()
    for dim, group in gmsh.model.getPhysicalGroups():
        name = gmsh.model.getPhysicalName(dim, group)
        for entity in gmsh.model.getEntitiesForPhysicalGroup(dim, group):
            kinds, _, connectivity = gmsh.model.mesh.getElements(dim, entity)
            for kind, nodes in zip(kinds, connectivity):
                if name.startswith("soil_"):
                    soil_nodes.update(int(n) for n in nodes)
                elif name == "sheetpile_1":
                    types.append(int(kind))
                    beam_nodes.update(int(n) for n in nodes)
    return types, beam_nodes, soil_nodes


def test_a_sheet_pile_is_meshed_as_line_elements_beside_the_soil_triangles():
    with build.session():
        types, beam_nodes, _ = beam_mesh(piled_section())

    assert beam_nodes, "the pile has to reach the mesh, not just the geometry"
    assert set(types) == {8}, "gmsh type 8 is the 3-node line, the quadratic beam"


def test_a_first_order_run_meshes_the_pile_as_two_node_lines():
    with build.session():
        types, _, _ = beam_mesh(piled_section(), order=1)

    assert set(types) == {1}, "gmsh type 1 is the 2-node line"


def test_every_sheet_pile_node_is_also_a_soil_node():
    """Conformity is the whole point of embedding the curve, and it is what the
    reference deck shows: in examples/dike_with_sheet_pile.mdpa every one of the
    sheet pile's nodes belongs to the soil mesh too."""
    with build.session():
        _, beam_nodes, soil_nodes = beam_mesh(piled_section())

    assert beam_nodes - soil_nodes == set()


def test_a_pile_crossing_a_layer_boundary_still_shares_its_nodes():
    with build.session():
        _, beam_nodes, soil_nodes = beam_mesh(
            piled_section(points=((12.0, 0.0), (12.0, -7.0), (15.0, -12.0)))
        )

    assert len(beam_nodes) > 2
    assert beam_nodes - soil_nodes == set()


# ── Anchors: a tie hanging off a pile, detached from the soil ───────────────

TENDON = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
          "density": 7850.0, "spacing": 2.5, "tension_limit": 900.0,
          "compression_limit": None}


def anchored_section(head=(12.0, -2.0), tail=(20.0, -8.0)) -> Project:
    payload = piled_section().model_dump()
    payload["anchor_sections"] = [TENDON]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": list(head), "tail": list(tail),
                           "prestress": 250.0, "active": True}]
    return Project.model_validate(payload)


def mesh_nodes_at(x: float, y: float, tol: float = 1e-6) -> list[int]:
    import gmsh
    tags, coords, _ = gmsh.model.mesh.getNodes()
    return [int(t) for i, t in enumerate(tags)
            if abs(coords[3 * i] - x) < tol and abs(coords[3 * i + 1] - y) < tol]


def test_the_anchor_head_is_a_node_the_sheet_pile_owns():
    """Splitting the pile at the head is what makes the tie land on a real beam node."""
    with build.session():
        _, beam_nodes, soil_nodes = beam_mesh(anchored_section())
        at_head = mesh_nodes_at(12.0, -2.0)

    assert [n for n in at_head if n in beam_nodes], "no beam node sits at the head"
    assert beam_nodes - soil_nodes == set(), "the pile stays bonded to the soil"


def test_an_anchor_does_not_cost_the_pile_its_conformity():
    """The pile must keep every node it had before an anchor was hung off it."""
    with build.session():
        _, plain_nodes, _ = beam_mesh(piled_section())
        _, anchored_nodes, _ = beam_mesh(anchored_section())

    assert len(anchored_nodes) >= len(plain_nodes)


def test_the_anchor_tail_gets_exactly_one_node_belonging_to_nothing_else():
    """The reference deck's tail node is in no element at all: the grouted body is
    idealised as a fixed point, not bonded to the soil."""
    import gmsh
    with build.session():
        meshing.mesh_project(anchored_section(), element_size=3.0, order=2)
        at_tail = mesh_nodes_at(20.0, -8.0)
        used = set()
        for dim, group in gmsh.model.getPhysicalGroups():
            if gmsh.model.getPhysicalName(dim, group).endswith("_Support"):
                continue
            for entity in gmsh.model.getEntitiesForPhysicalGroup(dim, group):
                for connectivity in gmsh.model.mesh.getElements(dim, entity)[2]:
                    used.update(int(n) for n in connectivity)

    assert len(at_tail) == 1
    assert at_tail[0] not in used, "the tail must not be bonded to soil, pile or anything"
