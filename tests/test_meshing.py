"""Real finite-element meshing and browser boundary payload tests."""

import math

import pytest

from core.geometry import solid_model, meshing
from core.model.templates import seed_project
from core.model.schemas import BoxRefinement, CylinderRefinement


@pytest.fixture(scope="module")
def quadratic_mesh():
    with solid_model.session():
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

    with solid_model.session():
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

    with solid_model.session():
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

    with solid_model.session():
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

    with solid_model.session():
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


def test_meshing_geometry_helpers_preserve_caller_visible_coordinates(monkeypatch):
    import gmsh

    monkeypatch.setattr(
        gmsh.model.mesh, "getElements",
        lambda *_: ([1], [], [[10, 11, 12, 13, 15, 14]]),
    )
    monkeypatch.setattr(
        gmsh.model.mesh, "getElementProperties",
        lambda *_: ("Line 3", 1, 2, 3, 1, 2),
    )
    coordinates = {
        10: (0.00001, 0.0, 0.0), 11: (1.00001, 0.0, 0.0), 12: (0.5, 0.1, 0.0),
        13: (1.00001, 1.0, 0.0), 14: (0.5, 0.6, 0.0), 15: (0.00001, 1.0, 0.0),
    }

    segments = meshing._line_segments([7], coordinates)

    assert segments == [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
                        ((1.0, 1.0, 0.0), (0.0, 1.0, 0.0))]


def test_mesh_project_rejects_invalid_size_and_order_before_building(monkeypatch):
    monkeypatch.setattr(
        solid_model, "build_geometry",
        lambda *_: pytest.fail("invalid mesh settings should be rejected before geometry"),
    )
    project = seed_project()

    with pytest.raises(ValueError, match="element_size must be greater than zero"):
        meshing.mesh_project(project, element_size=0)
    with pytest.raises(ValueError, match="order must be 1 or 2"):
        meshing.mesh_project(project, order=3)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"volume_keys": ["not-a-part"]}, "unknown mesh body key\\(s\\): not-a-part"),
        ({"body_sizes": {"not-a-part": 1.0}}, "unknown mesh body size key\\(s\\): not-a-part"),
    ],
)
def test_mesh_project_names_unknown_body_keys_before_starting_gmsh(monkeypatch, kwargs, message):
    monkeypatch.setattr(
        solid_model, "build_geometry",
        lambda *_: solid_model.BuildResult({}, {}, (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)),
    )

    with pytest.raises(ValueError, match=message):
        meshing.mesh_project(seed_project(), **kwargs)


def test_finite_element_volumes_omit_display_aliases_and_deduplicate_tags():
    project = seed_project()
    soil_keys = [f"soil_{layer.id}" for layer in project.layers]
    volumes = {key: [index] for index, key in enumerate(soil_keys, start=1)}
    first_structure_tag = len(soil_keys) + 1
    volumes.update({
        "wall": [first_structure_tag], "struts": [first_structure_tag + 1],
        "anchors": [first_structure_tag + 2], "piles": [first_structure_tag + 3],
        "wells": [first_structure_tag + 4], "excavation": [1, first_structure_tag + 5],
        "load": [first_structure_tag + 6], "water": [first_structure_tag + 7],
    })
    built = solid_model.BuildResult(
        volumes=volumes, mass={}, bbox=(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
    )

    assert meshing._finite_element_volumes(project, built) == list(
        range(1, first_structure_tag + 5),
    )


def test_refinement_fields_are_restricted_to_requested_entity_dimensions():
    import gmsh

    with solid_model.session():
        gmsh.clear()
        gmsh.model.add("scoped-fields")
        background = meshing._apply_refinements(
            4.0, [], volume_sizes={31: 1.25}, dim=2, curve_sizes={42: 0.5},
        )
        fields = gmsh.model.mesh.field
        assert background > 0
        assert fields.getType(background) == "Min"
        restrictions = fields.getNumbers(background, "FieldsList")
        assert len(restrictions) == 2
        restricted_dimensions = {
            tuple(fields.getNumbers(int(tag), option))
            for tag in restrictions for option in ("SurfacesList", "CurvesList")
            if len(fields.getNumbers(int(tag), option))
        }
        assert restricted_dimensions == {(31.0,), (42.0,)}


def test_a_surface_load_and_the_faces_of_a_solid_model_take_a_size():
    """In a solid model a surface load is sized on the soil's faces under it, and a
    face of the model on the soil's faces on that side -- the front and back too."""
    project = seed_project()
    load = project.loads[0].id

    def elements(sizes):
        with solid_model.session():
            return meshing.mesh_project(project, element_size=8.0, order=1,
                                        body_sizes=sizes).stats.elements

    plain = elements({})
    for key in (load, "face_bottom", "face_front", "face_back", "face_top"):
        assert elements({key: 2.0}) > plain, key
