"""Real finite-element meshing and browser boundary payload tests."""

import math

import pytest

from core.geometry import build, meshing
from core.model.seed import seed_project
from core.model.schemas import BoxRefinement, CylinderRefinement


@pytest.fixture(scope="module")
def quadratic_mesh():
    with build.session():
        yield meshing.mesh_project(seed_project(), element_size=4.0, order=2)


def test_real_volume_elements_are_generated(quadratic_mesh):
    assert quadratic_mesh.stats.elements > 0
    assert quadratic_mesh.stats.nodes > 0
    assert quadratic_mesh.stats.seconds >= 0


def test_order_two_produces_ten_node_tetrahedra(quadratic_mesh):
    import gmsh

    tetrahedron = gmsh.model.mesh.getElementType("Tetrahedron", 2)
    types, element_tags, node_tags = gmsh.model.mesh.getElements(3)
    by_type = {int(t): (elements, nodes) for t, elements, nodes in zip(types, element_tags, node_tags)}

    assert set(by_type) == {tetrahedron}
    elements, nodes = by_type[tetrahedron]
    assert len(nodes) == len(elements) * 10


def test_stats_are_internally_consistent(quadratic_mesh):
    stats = quadratic_mesh.stats
    assert sum(stats.by_type.values()) == stats.elements
    assert sum(stats.quality_histogram.values()) == stats.elements
    assert stats.quality_histogram["<0.0"] == 0, "inverted tetrahedra are not a usable FE mesh"


def test_every_mesh_node_is_inside_the_reported_bounds(quadratic_mesh):
    import gmsh

    _, coordinates, _ = gmsh.model.mesh.getNodes()
    xmin, ymin, zmin, xmax, ymax, zmax = quadratic_mesh.bbox
    for x, y, z in zip(coordinates[0::3], coordinates[1::3], coordinates[2::3]):
        assert xmin - 1e-6 <= x <= xmax + 1e-6
        assert ymin - 1e-6 <= y <= ymax + 1e-6
        assert zmin - 1e-6 <= z <= zmax + 1e-6


def test_boundary_payload_is_drawable_and_finite(quadratic_mesh):
    assert quadratic_mesh.sections
    for section in quadratic_mesh.sections:
        assert section.key == "mesh"
        assert section.indices and len(section.indices) % 3 == 0
        assert max(section.indices) < len(section.positions) // 3
        assert len(section.edges) % 6 == 0
        assert all(math.isfinite(value) for value in section.positions)


def test_result_serialises_to_the_frontend_contract(quadratic_mesh):
    payload = quadratic_mesh.to_dict()
    assert set(payload) == {"bbox", "stats", "sections", "log", "meshed_keys", "parts"}
    assert {"nodes", "elements", "by_type", "quality_histogram", "seconds"} <= payload["stats"].keys()
    assert set(payload["sections"][0]) == {"key", "color", "positions", "indices", "edges"}


def test_box_and_cylinder_refinements_create_a_background_size_field():
    import gmsh

    with build.session():
        gmsh.clear()
        gmsh.model.add("fields")
        background = meshing._apply_refinements(3.0, [
            BoxRefinement(kind="box", size=1.0, x_min=0, x_max=10,
                          z_min=0, z_max=10, y_min=-10, y_max=0),
            CylinderRefinement(kind="cylinder", size=0.5, x=5, y=5, z=-10,
                               axis_x=0, axis_y=0, axis_z=10, radius=2),
        ])
        assert background > 0
        assert gmsh.model.mesh.field.getType(background) == "Min"


def test_gmsh_controls_are_applied_before_generation():
    import gmsh

    with build.session():
        gmsh.clear()
        gmsh.model.add("options")
        meshing._configure(2.0, [], [], algorithm_3d="hxt", smoothing=7,
                           curvature_points=24, size_min_factor=0.2,
                           second_order_linear=False)
        assert gmsh.option.getNumber("Mesh.Algorithm3D") == 10
        assert gmsh.option.getNumber("Mesh.Smoothing") == 7
        assert gmsh.option.getNumber("Mesh.MeshSizeFromCurvature") == 24
        assert gmsh.option.getNumber("Mesh.MeshSizeMin") == pytest.approx(0.4)
        assert gmsh.option.getNumber("Mesh.SecondOrderLinear") == 0


def test_only_the_requested_body_gets_volume_elements():
    import gmsh

    with build.session():
        result = meshing.mesh_project(
            seed_project(), element_size=5.0, order=1,
            volume_keys=["soil_L1"], optimization="none",
        )
        groups = {
            gmsh.model.getPhysicalName(3, tag): gmsh.model.getEntitiesForPhysicalGroup(3, tag)
            for _, tag in gmsh.model.getPhysicalGroups(3)
        }
        l1_elements = sum(
            len(tags) for tags in gmsh.model.mesh.getElements(3, int(groups["soil_L1"][0]))[1]
        )
        l2_elements = sum(
            len(tags) for tags in gmsh.model.mesh.getElements(3, int(groups["soil_L2"][0]))[1]
        )

        assert result.meshed_keys == ["soil_L1"]
        assert l1_elements > 0
        assert l2_elements == 0


def test_different_layer_sizes_keep_the_shared_surface_conformal():
    import gmsh

    with build.session():
        result = meshing.mesh_project(
            seed_project(), element_size=5.0, order=1,
            volume_keys=["soil_L1", "soil_L2"],
            body_sizes={"soil_L1": 1.5, "soil_L2": 4.0}, optimization="none",
        )
        groups = {
            gmsh.model.getPhysicalName(3, tag): [int(v) for v in gmsh.model.getEntitiesForPhysicalGroup(3, tag)]
            for _, tag in gmsh.model.getPhysicalGroups(3)
        }
        upper, lower = groups["soil_L1"][0], groups["soil_L2"][0]
        upper_surfaces = {abs(tag) for _, tag in gmsh.model.getBoundary([(3, upper)], oriented=False)}
        lower_surfaces = {abs(tag) for _, tag in gmsh.model.getBoundary([(3, lower)], oriented=False)}
        shared = upper_surfaces & lower_surfaces
        assert len(shared) == 1

        shared_nodes = {int(n) for n in gmsh.model.mesh.getElements(2, shared.pop())[2][0]}
        upper_nodes = {int(n) for nodes in gmsh.model.mesh.getElements(3, upper)[2] for n in nodes}
        lower_nodes = {int(n) for nodes in gmsh.model.mesh.getElements(3, lower)[2] for n in nodes}
        assert shared_nodes <= upper_nodes
        assert shared_nodes <= lower_nodes

        upper_count = sum(len(tags) for tags in gmsh.model.mesh.getElements(3, upper)[1])
        lower_count = sum(len(tags) for tags in gmsh.model.mesh.getElements(3, lower)[1])
        assert upper_count > lower_count
        assert result.meshed_keys == ["soil_L1", "soil_L2"]
