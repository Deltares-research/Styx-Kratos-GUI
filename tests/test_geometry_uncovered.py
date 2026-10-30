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


def test_import_refuses_unsupported_formats(tmp_path, monkeypatch):
    import gmsh

    monkeypatch.setattr(cad_import, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(gmsh, "clear", lambda: None)
    monkeypatch.setattr(gmsh.model, "add", lambda *_args: None)

    with pytest.raises(cad_import.ImportRefused, match="\\.xyz is not a format"):
        cad_import.process_import(str(tmp_path / "model.xyz"), ".xyz")


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


def test_ascii_stl_reader_preserves_facet_vertices(tmp_path):
    stl = tmp_path / "triangle.stl"
    stl.write_text(
        "solid triangle\nfacet normal 0 0 1\nouter loop\n"
        "vertex 0 0 0\nvertex 2 0 0\nvertex 0 1 0\n"
        "endloop\nendfacet\nendsolid triangle\n",
        encoding="ascii",
    )

    assert cad_import._read_stl(stl) == (
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2)],
    )


def test_obj_reader_accepts_texture_index_face_syntax(tmp_path):
    obj = tmp_path / "textured.obj"
    obj.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1/1 2/2 3/3\n",
        encoding="ascii",
    )

    assert cad_import._read_obj(obj) == (
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [(0, 1, 2)],
    )


def test_split_at_inserts_on_segment_heads_in_order_and_ignores_other_points():
    points = [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0)]
    heads = [
        (3.0, 0.0), (1.0, 0.0), (4.0, 1.0), (1.0, 0.0000005),
        (0.0, 0.0), (4.0, 0.0), (2.0, 1.0),
    ]

    assert solid_model._split_at(points, heads) == [
        (0.0, 0.0), (1.0, 0.0), (3.0, 0.0),
        (4.0, 0.0), (4.0, 1.0), (4.0, 2.0),
    ]


def test_overlay_surface_is_visible_from_both_sides(monkeypatch):
    import gmsh

    edge_nodes = {10: [1, 2], 11: [2, 3], 12: [3, 1]}

    def elements(dim, tag):
        if dim == 2:
            return [tessellation.TRIANGLE], [], [[1, 2, 3]]
        return [tessellation.LINE], [], [edge_nodes[tag]]

    monkeypatch.setattr(gmsh.model.mesh, "getElements", elements)
    monkeypatch.setattr(
        gmsh.model, "getBoundary",
        lambda *_args, **_kwargs: [(1, tag) for tag in edge_nodes],
    )
    coordinates = {
        1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0), 3: (0.0, 1.0, 0.0),
    }

    section = tessellation._overlay_section(
        "panel", "#fff", [(2, 9)], coordinates,
    )

    assert section.positions == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    assert section.indices == [0, 1, 2, 0, 2, 1]
    assert len(section.edges) == 18


@pytest.mark.parametrize("previous", [None, "python-handler"])
def test_posix_initialization_restores_pythons_sigpipe_handler(monkeypatch, previous):
    from unittest.mock import Mock

    events = []
    signal = SimpleNamespace(
        SIGPIPE=13,
        getsignal=Mock(side_effect=lambda sig: events.append(("get", sig)) or previous),
        signal=Mock(side_effect=lambda sig, handler: events.append(("restore", sig, handler))),
    )
    monkeypatch.setattr(solid_model, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(solid_model, "signal", signal)
    monkeypatch.setattr(solid_model, "gmsh", SimpleNamespace(
        initialize=lambda: events.append(("initialize",))))

    solid_model.initialize()

    expected = [("get", 13), ("initialize",)]
    if previous is not None:
        expected.append(("restore", 13, previous))
    assert events == expected


@pytest.mark.parametrize("swept_faces", [[], [(2, 20)]])
def test_section_sweeps_report_failed_piles_and_imprint_free_interfaces(
        monkeypatch, swept_faces):
    from unittest.mock import Mock
    from tests.test_kratos_interfaces import interfaced_project

    project = interfaced_project(
        side="left", structure=None, points=[(5, 0), (5, -2)])
    occ = SimpleNamespace(
        addPoint=Mock(side_effect=range(1, 20)),
        addLine=Mock(side_effect=range(30, 50)),
        extrude=Mock(side_effect=[[], swept_faces]),
    )
    monkeypatch.setattr(solid_model, "gmsh", SimpleNamespace(
        model=SimpleNamespace(occ=occ)))
    log = []

    result = solid_model._section_sweeps(project, log)

    assert result == ([("interface_1", [20])] if swept_faces else [])
    assert any("sheetpile_1 could not be swept" in note for note in log)
    assert any("export no interface elements" in note for note in log)
    assert occ.extrude.call_count == 2
    assert occ.extrude.call_args.args[1:] == (0.0, 0.0, solid_model.INTERFACE_SWEEP)


@pytest.mark.parametrize("scenario", ["embedded", "boundary", "outside", "failure"])
def test_volume_curve_embedding_preserves_topology_and_reports_unbonded_members(
        monkeypatch, scenario):
    from unittest.mock import Mock

    occ = SimpleNamespace(synchronize=Mock(), getCenterOfMass=Mock(
        return_value=(2, 2, 2) if scenario == "outside" else (0.5, 0.5, 0.5)))
    embed = Mock(side_effect=RuntimeError("mesher refused") if scenario == "failure" else None)
    model = SimpleNamespace(
        occ=occ, mesh=SimpleNamespace(embed=embed),
        getBoundingBox=Mock(return_value=(0, 0, 0, 1, 1, 1)),
        getAdjacencies=Mock(return_value=(SimpleNamespace(
            size=1 if scenario == "boundary" else 0), [])),
    )
    monkeypatch.setattr(solid_model, "gmsh", SimpleNamespace(model=model))
    log = []

    solid_model._embed_curves_in_volumes({"member": [7]}, [10], log)

    occ.synchronize.assert_called_once_with()
    if scenario in ("boundary", "outside"):
        embed.assert_not_called()
    else:
        embed.assert_called_once_with(1, [7], 3, 10)
    if scenario in ("outside", "failure"):
        assert len(log) == 1
        assert "member" in log[0]
        assert "meshed unbonded from the soil" in log[0]
        assert ("lies in no soil volume" if scenario == "outside"
                else "could not be embedded in volume 10 (mesher refused)") in log[0]
    else:
        assert log == []


def test_a_spatial_structure_outside_the_soil_is_not_returned_as_embedded(monkeypatch):
    from unittest.mock import Mock
    from core.model.schemas import Member
    from core.model.templates import blank_project

    member = Member(id="member", name="Member", section="steel",
                    points=[(1, 0, 0), (1, -2, 0)])
    project = blank_project().model_copy(update={"dimension": 3, "beams": [member]})
    occ = SimpleNamespace(
        addPoint=Mock(side_effect=[1, 2]), addLine=Mock(return_value=7),
        intersect=Mock(return_value=([], [])), fragment=Mock())
    monkeypatch.setattr(solid_model, "gmsh", SimpleNamespace(model=SimpleNamespace(occ=occ)))
    owners = {10: {"soil"}}
    log = []

    assert solid_model._embed_3d_structures(project, owners, log) == (owners, {}, {})
    assert log == ["Info    : member lies outside the soil and is not part of the model"]
    occ.intersect.assert_called_once_with(
        [(1, 7)], [(3, 10)], removeObject=True, removeTool=False)
    occ.fragment.assert_not_called()


def test_anchor_head_insertion_skips_a_zero_length_polyline_leg():
    assert solid_model._split_at(
        [(0, 0), (0, 0), (2, 0)], [(1, 0)]) == [
            (0, 0), (0, 0), (1, 0), (2, 0)]
