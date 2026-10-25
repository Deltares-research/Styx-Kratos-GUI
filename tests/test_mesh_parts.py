"""The mesh, split by the part each piece belongs to.

`MeshModel.sections` is the whole FE mesh as one grey buffer, which is all the viewport
needed while the mesh was only ever looked at as a whole. `MeshModel.parts` is the same
mesh again, cut along the Model explorer's own keys -- a soil body, a sheet pile, an
anchor, an interface, a normal load -- so a single part can be drawn in a colour of its
own and the user can see which elements are the sheet pile's.

The staged test model is the case: it has every kind of part a staged excavation has, and
three of them (the interface and the normal loads) own no geometry of their own.
"""

import pytest

from core.geometry import solid_model, meshing
from tests.models.excavation import excavation_project
@pytest.fixture(scope="module")
def model():
    project = excavation_project()
    with solid_model.session():
        built = solid_model.build_geometry(project)
        areas = dict(built.mass)
        mesh = meshing.mesh_project(project)
    return project, mesh, areas


def by_key(mesh):
    return {section.key: section for section in mesh.parts}


def points(flat):
    return [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]


def triangle_area(section):
    p = points(section.positions)
    total = 0.0
    for i in range(0, len(section.indices), 3):
        (ax, ay, _), (bx, by, _), (cx, cy, _) = (p[j] for j in section.indices[i:i + 3])
        total += abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2
    return total


def test_every_part_with_elements_has_a_section_and_no_alias_does(model):
    project, mesh, _ = model
    soils = [key for key, *_ in project.soil_bodies()]
    expected = set(soils) | {"sheetpile", "strut", "wall_contact:L", "wall_contact:R",
                             "water_1", "water_2", "water_3", "surcharge", "water"}
    assert set(by_key(mesh)) == expected
    assert len(mesh.parts) == len(expected), "one section per part, not one per colour"


def test_a_soil_body_is_triangles_covering_exactly_its_own_area(model):
    _, mesh, areas = model
    for key, section in by_key(mesh).items():
        if not key.startswith("soil_"):
            continue
        assert section.indices and len(section.indices) % 3 == 0, key
        assert max(section.indices) < len(section.positions) // 3, key
        assert triangle_area(section) == pytest.approx(areas[key], rel=1e-6), key


def test_the_soil_bodies_partition_the_whole_mesh(model):
    """Every triangle of the grey mesh is in exactly one body: nothing is drawn twice
    and nothing is left without an owner."""
    _, mesh, _ = model
    whole = sum(len(section.indices) for section in mesh.sections) // 3
    split = sum(len(section.indices) for key, section in by_key(mesh).items()
                if key.startswith("soil_")) // 3
    assert split == whole


def test_a_structure_is_line_segments_with_no_faces(model):
    _, mesh, _ = model
    parts = by_key(mesh)
    for key in ("sheetpile", "strut", "water_1"):
        section = parts[key]
        assert not section.indices, key
        assert section.edges and len(section.edges) % 6 == 0, key


def test_the_sheet_pile_segments_lie_on_the_wall(model):
    project, mesh, _ = model
    (beam,) = project.beams
    xs = {round(x, 6) for x, _, _ in points(by_key(mesh)["sheetpile"].edges)}
    assert xs == {round(beam.points[0][0], 6)}, "a vertical wall has one x"


def segments(section):
    p = points(section.edges)
    return [(p[i], p[i + 1]) for i in range(0, len(p), 2)]


def test_an_interface_on_a_structure_has_one_section_per_side(model):
    """`wall_contact` has no curve of its own: `core.kratos.interfaces` builds its elements from
    the pile's edges after meshing, and with `side="both"` it does so on each face. The
    two faces are what a user has to tell apart, so each is a section of its own,
    `<key>:L` and `<key>:R`, with one segment per pile segment."""
    _, mesh, _ = model
    parts = by_key(mesh)
    assert "wall_contact" not in parts
    pile = len(segments(parts["sheetpile"]))
    assert len(segments(parts["wall_contact:L"])) == pile
    assert len(segments(parts["wall_contact:R"])) == pile


def test_each_side_is_drawn_just_off_the_line_on_its_own_side(model):
    """Both faces sit exactly on the pile, so drawn there they would hide each other.
    Each is moved a little toward its own side of the screen -- L toward -x, R toward
    +x, `schemas.Interface`'s convention, whichever way the pile was drawn -- by much
    less than a segment, so it still reads as the pile."""
    project, mesh, _ = model
    (beam,) = project.beams
    (x0, _), (x1, _) = beam.points
    assert x0 == x1, "the model's pile is vertical"
    parts = by_key(mesh)
    shortest = min(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
                   for a, b in segments(parts["sheetpile"]))
    for key, sign in (("wall_contact:L", -1), ("wall_contact:R", 1)):
        for x, y, _ in points(parts[key].edges):
            off = x - x0
            assert sign * off > 0, (key, x, y)
            assert abs(off) < shortest / 4, (key, off)


def test_a_one_sided_interface_has_only_that_side():
    project = excavation_project()
    project = project.model_copy(update={"interfaces": [
        interface.model_copy(update={"side": "right"}) for interface in project.interfaces]})
    with solid_model.session():
        mesh = meshing.mesh_project(project)
    keys = set(by_key(mesh))
    assert "wall_contact:R" in keys
    assert "wall_contact:L" not in keys


def test_a_surface_load_is_the_ground_edges_under_its_footprint(model):
    """The same edges the deck writes the load's conditions on
    (`meshing.loaded_elements`): the ground surface between x0 and x1, all of it and
    nothing else."""
    project, mesh, _ = model
    (load,) = project.loads
    section = by_key(mesh)["surcharge"]
    assert not section.indices
    for x, y, _ in points(section.edges):
        assert y == pytest.approx(load.y, abs=1e-6)
        assert load.x0 - 1e-6 <= x <= load.x1 + 1e-6
    loaded = sum(abs(b[0] - a[0]) for a, b in segments(section))
    assert loaded == pytest.approx(load.x1 - load.x0, abs=1e-6)


def test_the_anchor_is_one_truss_from_head_to_tail(model):
    """`core.kratos.writer._anchor_ties` exports it as one two-node element, so that is what is
    drawn, whatever gmsh did along its curve."""
    project, mesh, _ = model
    (anchor,) = project.anchors
    ends = points(by_key(mesh)["strut"].edges)
    assert len(ends) == 2
    xs = [x for x, _, _ in ends]
    assert min(xs) == pytest.approx(min(anchor.head[0], anchor.tail[0]), abs=1e-6)
    assert max(xs) == pytest.approx(max(anchor.head[0], anchor.tail[0]), abs=1e-6)


def test_parts_travel_in_the_payload(model):
    _, mesh, _ = model
    payload = mesh.to_dict()
    assert [part["key"] for part in payload["parts"]] == [s.key for s in mesh.parts]
    assert set(payload["parts"][0]) == {"key", "color", "positions", "indices", "edges"}


def test_a_solid_model_draws_each_body_by_its_own_skin():
    """In 3D the grey mesh is the outer skin of everything meshed together. A body's
    section is the skin of that body alone, so a body inside the model still has one."""
    from core.model.templates import seed_project

    project = seed_project(simple=True)
    with solid_model.session():
        mesh = meshing.mesh_project(project, element_size=6.0, order=1)
    parts = by_key(mesh)
    soils = [key for key, *_ in project.soil_bodies()]
    assert set(soils) <= set(parts)
    for key in soils:
        assert parts[key].indices and len(parts[key].indices) % 3 == 0, key
