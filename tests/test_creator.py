import pytest
import os
from core.geometry import primitives, solid_model

def test_creator_creates_box(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)
    
    recipe = {
        "kind": "box",
        "origin": [1, 2, 3],
        "size": [4, 5, 6]
    }
    
    import gmsh
    solid_model.initialize()
    try:
        res = primitives.process_creation(recipe)
        assert res["volumes"] == 1
        assert os.path.exists(res["brep_path"])
        
        # Bbox checks
        xmin, ymin, zmin, xmax, ymax, zmax = res["bbox"]
        assert xmin == pytest.approx(1, abs=1e-5)
        assert ymin == pytest.approx(2, abs=1e-5)
        assert zmin == pytest.approx(3, abs=1e-5)
        assert xmax == pytest.approx(5, abs=1e-5)
        assert ymax == pytest.approx(7, abs=1e-5)
        assert zmax == pytest.approx(9, abs=1e-5)
    finally:
        gmsh.finalize()


def test_creator_creates_cylinder(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)
    
    recipe = {
        "kind": "cylinder",
        "center": [0, 0, 0],
        "axis": [0, 0, 10],
        "radius": 5
    }
    
    import gmsh
    solid_model.initialize()
    try:
        res = primitives.process_creation(recipe)
        assert res["volumes"] == 1
        assert os.path.exists(res["brep_path"])
    finally:
        gmsh.finalize()


def test_creator_creates_polygon_extrude(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    recipe = {
        "kind": "polygon_extrude",
        "vertices": [[0,0,0], [10,0,0], [10,10,0], [0,10,0]],
        "extrusion": [0, 0, 5]
    }

    import gmsh
    solid_model.initialize()
    try:
        res = primitives.process_creation(recipe)
        assert res["volumes"] == 1
        assert os.path.exists(res["brep_path"])

        xmin, ymin, zmin, xmax, ymax, zmax = res["bbox"]
        assert xmin == pytest.approx(0, abs=1e-5)
        assert ymin == pytest.approx(0, abs=1e-5)
        assert zmin == pytest.approx(0, abs=1e-5)
        assert xmax == pytest.approx(10, abs=1e-5)
        assert ymax == pytest.approx(10, abs=1e-5)
        assert zmax == pytest.approx(5, abs=1e-5)
    finally:
        gmsh.finalize()


def test_creator_creates_line(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    recipe = {
        "kind": "line",
        "vertices": [[0, 0, 0], [10, 0, 0]],
    }

    import gmsh
    solid_model.initialize()
    try:
        res = primitives.process_creation(recipe)
        assert res["dim"] == 1
        assert res["volumes"] == 0
        assert os.path.exists(res["brep_path"])

        xmin, ymin, zmin, xmax, ymax, zmax = res["bbox"]
        assert xmin == pytest.approx(0, abs=1e-5)
        assert xmax == pytest.approx(10, abs=1e-5)
        assert ymin == pytest.approx(0, abs=1e-5)
        assert ymax == pytest.approx(0, abs=1e-5)
    finally:
        gmsh.finalize()


def test_creator_creates_polyline_with_more_than_two_vertices(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    recipe = {
        "kind": "line",
        "vertices": [[0, 0, 0], [10, 0, 0], [10, 10, 0]],
    }

    import gmsh
    solid_model.initialize()
    try:
        res = primitives.process_creation(recipe)
        assert res["dim"] == 1
        xmin, ymin, zmin, xmax, ymax, zmax = res["bbox"]
        assert xmax == pytest.approx(10, abs=1e-5)
        assert ymax == pytest.approx(10, abs=1e-5)
    finally:
        gmsh.finalize()


def test_creator_line_requires_at_least_two_vertices(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    import gmsh
    solid_model.initialize()
    try:
        with pytest.raises(ValueError):
            primitives.process_creation({"kind": "line", "vertices": [[0, 0, 0]]})
    finally:
        gmsh.finalize()


def test_creator_creates_polygon_surface(tmp_path, monkeypatch):
    """A plain 'polygon' recipe is a flat surface -- no extrusion, no volume. This is
    what the GUI's 'Create surface' tool sends; 'polygon_extrude' is a distinct recipe."""
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    recipe = {
        "kind": "polygon",
        "vertices": [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]],
    }

    import gmsh
    solid_model.initialize()
    try:
        res = primitives.process_creation(recipe)
        assert res["dim"] == 2
        assert res["volumes"] == 0
        assert os.path.exists(res["brep_path"])

        xmin, ymin, zmin, xmax, ymax, zmax = res["bbox"]
        assert xmin == pytest.approx(0, abs=1e-5)
        assert ymin == pytest.approx(0, abs=1e-5)
        assert zmin == pytest.approx(0, abs=1e-5)
        assert xmax == pytest.approx(10, abs=1e-5)
        assert ymax == pytest.approx(10, abs=1e-5)
        assert zmax == pytest.approx(0, abs=1e-5)
    finally:
        gmsh.finalize()


def test_creator_polygon_requires_at_least_three_vertices(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    import gmsh
    solid_model.initialize()
    try:
        with pytest.raises(ValueError):
            primitives.process_creation({"kind": "polygon", "vertices": [[0, 0, 0], [1, 0, 0]]})
    finally:
        gmsh.finalize()


def test_creator_rejects_unknown_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(primitives, "DATA_DIR", tmp_path)

    import gmsh
    solid_model.initialize()
    try:
        with pytest.raises(ValueError):
            primitives.process_creation({"kind": "sphere"})
    finally:
        gmsh.finalize()


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
