"""Focused geometry edge cases that are cheaper to pin than full-model snapshots."""

from types import SimpleNamespace

import pytest

from core.geometry import cad_import, meshing, primitives, solid_model, tessellation
from core.model.templates import seed_project


@pytest.mark.parametrize(
    "recipe, message",
    [
        ({"kind": "box", "origin": [0, 0, 0], "size": [1, 0, 1]}, "non-zero 'size'"),
        ({"kind": "cylinder", "center": [0, 0, 0], "axis": [0, 0, 0],
          "radius": 1}, "non-zero 'axis'"),
        ({"kind": "polygon", "vertices": [[0, 0, 0], [1, 0, 0], [2, 0, 0]],
          }, "has no area"),
        ({"kind": "polygon_extrude", "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
          "extrusion": [0, 0, 0]}, "non-zero 'extrusion'"),
    ],
)
def test_creation_recipe_rejects_geometries_that_cannot_be_built(recipe, message):
    with pytest.raises(ValueError, match=message):
        primitives._check(recipe, recipe["kind"])


def test_creation_recipe_requires_a_kind_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path / "data")
    with solid_model.session(), pytest.raises(ValueError, match="missing 'kind'"):
        primitives.process_creation({})


def test_line_creation_requires_two_vertices(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path / "data")
    with solid_model.session(), pytest.raises(ValueError, match="at least 2 vertices"):
        primitives.process_creation({"kind": "line", "vertices": [[0, 0, 0]]})


def test_obj_negative_indices_are_relative_to_vertices_already_read(tmp_path):
    obj = tmp_path / "fan.obj"
    obj.write_text(
        "v 0 0 0\nv 2 0 0\nv 2 1 0\nv 0 1 0\nf -4 -3 -2 -1\n",
        encoding="ascii",
    )

    points, triangles = cad_import._read_obj(obj)

    assert points == [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0),
                      (2.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    assert triangles == [(0, 1, 2), (0, 2, 3)]


def test_obj_face_with_an_unavailable_vertex_is_refused(tmp_path):
    obj = tmp_path / "bad.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nf 1 2 3\n", encoding="ascii")

    with pytest.raises(cad_import.ImportRefused, match="does not have"):
        cad_import._read_obj(obj)


def test_cad_healing_options_are_restored_even_when_gmsh_cannot_read_the_file(
    tmp_path, monkeypatch,
):
    import gmsh

    source = tmp_path / "broken.step"
    source.write_text("not a CAD model", encoding="ascii")
    monkeypatch.setattr(gmsh, "merge", lambda *_: (_ for _ in ()).throw(RuntimeError("bad CAD")))

    with solid_model.session():
        previous = {name: gmsh.option.getNumber(name) for name in cad_import.HEALING}
        with pytest.raises(cad_import.ImportRefused, match="bad CAD"):
            cad_import._merge_cad(source)

        assert {name: gmsh.option.getNumber(name) for name in cad_import.HEALING} == previous


def test_first_facet_skips_a_degenerate_triangle_and_uses_a_valid_one(monkeypatch):
    import gmsh

    monkeypatch.setattr(
        gmsh.model.mesh, "getElements",
        lambda *_: ([tessellation.TRIANGLE], [], [[1, 2, 3, 1, 2, 4]]),
    )
    coordinates = {
        1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (2.0, 0.0, 0.0),
        4: (0.0, 1.0, 0.0),
    }

    facet = tessellation._first_facet(9, coordinates)

    assert facet[0] == pytest.approx([1 / 3, 1 / 3, 0.0])
    assert facet[1] == pytest.approx([0.0, 0.0, 1.0])
    assert facet[2] == pytest.approx(0.5)


def test_first_facet_returns_none_when_the_surface_has_no_triangles(monkeypatch):
    import gmsh

    monkeypatch.setattr(gmsh.model.mesh, "getElements", lambda *_: ([], [], []))
    assert tessellation._first_facet(9, {}) is None


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


def test_solid_model_helpers_assign_owners_and_report_omitted_overlays():
    assert solid_model._assign_by_priority({
        1: {"soil_L1", "wall"}, 2: {"soil_L1", "custom_z", "custom_a"},
    }) == {"wall": [1], "custom_a": [2]}

    log = []
    assert solid_model._drop_overlays({"z_line": [(1, 4)], "a_surface": [(2, 3)]}, log) == {}
    assert [entry.split(" : ")[1].split()[0] for entry in log] == ["a_surface", "z_line"]


def test_three_dimensional_build_verification_names_parts_without_geometry():
    with pytest.raises(solid_model.GeometryError, match="soil_L1"):
        solid_model._verify(seed_project(), {})


def test_plane_strain_verification_allows_parts_that_miss_the_section():
    project = seed_project().model_copy(update={"dimension": 2})
    solid_model._verify(project, {})


def test_empty_bounding_box_requires_or_returns_a_camera_fallback():
    fallback = (-1.0, -2.0, -3.0, 1.0, 2.0, 3.0)

    assert solid_model.bounding_box([], fallback=fallback) == fallback
    with pytest.raises(ValueError, match="no volumes and no fallback"):
        solid_model.bounding_box([])


def test_load_footprint_containment_distinguishes_line_and_surface_loads():
    coordinates = {
        1: (1.0, 0.0, -2.0), 2: (2.0, 0.0, -2.0), 3: (1.5, 0.0, -1.0),
        4: (1.0, 0.0, 1.0),
    }
    line = SimpleNamespace(kind="line", x0=1.0, x1=2.0)
    surface = SimpleNamespace(kind="surface", x0=1.0, x1=2.0, z0=-2.0, z1=0.0)

    assert meshing._under_load([1, 2], coordinates, line)
    assert meshing._under_load([1, 2], coordinates, surface)
    assert not meshing._under_load([1, 4], coordinates, surface)
