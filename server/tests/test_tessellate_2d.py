"""Display buffers for the plane-strain section.

A section face encloses nothing, so the winding machinery that dominates the 3D path
(`_points_inward` and its probe-and-halve search) has no meaning here: there is no
"inside" for a flat face to point away from. The 2D payload is instead emitted with
both windings, so it draws from either side -- exactly what `_overlay_section` already
does for a drawn surface.

The headline assertion mirrors test_tessellate.py's `signed volume == OCC mass`: the
summed triangle area, halved for the doubled winding, must equal the area OCC measured.
It catches a dropped face (too small), a duplicated one (too large) and a broken
tag -> index remap (garbage) in a single number.
"""

import pytest

from app import build, tessellate
from app.schemas import Project
from app.seed import seed_project


def section_project(simple: bool) -> Project:
    return Project.model_validate(seed_project(simple=simple).model_dump() | {"dimension": 2})


@pytest.fixture(scope="module")
def simple():
    project = section_project(simple=True)
    with build.session():
        yield project, tessellate.tessellate(project)


@pytest.fixture(scope="module")
def full():
    project = section_project(simple=False)
    with build.session():
        yield project, tessellate.tessellate(project)


def sections_of(display, key):
    return [s for s in display.sections if s.key == key]


def triangle_area(section) -> float:
    p, total = section.positions, 0.0
    for i in range(0, len(section.indices), 3):
        a, b, c = (section.indices[i + k] * 3 for k in range(3))
        ux, uy, uz = p[b] - p[a], p[b + 1] - p[a + 1], p[b + 2] - p[a + 2]
        vx, vy, vz = p[c] - p[a], p[c + 1] - p[a + 1], p[c + 2] - p[a + 2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        total += (nx * nx + ny * ny + nz * nz) ** 0.5 / 2
    return total


# ── Structure ───────────────────────────────────────────────────────────────

def test_only_the_parts_present_in_the_section_are_drawable(full):
    project, display = full
    drawn = {s.key for s in display.sections}
    assert drawn <= set(project.part_keys())
    # The wells and anchors miss the plane at y = 20 (see test_build_2d.py); they must
    # not turn up as empty buffers the frontend would then have to defend against.
    assert "wells" not in drawn
    assert "anchors" not in drawn
    assert {"soil_L1", "soil_L2", "wall", "struts", "piles"} <= drawn


def test_the_payload_is_flat_in_z(simple):
    """The section is the x-y plane at z = 0, so every drawn vertex has z zero."""
    _, display = simple
    for section in display.sections:
        for z in section.positions[2::3]:
            assert z == pytest.approx(0.0, abs=1e-3)


def test_every_face_is_wound_both_ways(simple):
    """Without an enclosing solid there is no way to know which side a viewer
    approaches from, so a section must draw from either."""
    for section in sections_of(simple[1], "soil_L1"):
        assert section.indices
        assert len(section.indices) % 6 == 0
        half = len(section.indices) // 2
        front = section.indices[:half]
        back = section.indices[half:]
        assert len(front) == len(back)


# ── Real, measurable area ───────────────────────────────────────────────────

def test_drawn_area_equals_the_area_occ_measured(simple):
    project, display = simple
    with build.session():
        built = build.build_geometry(project)
    for layer in project.layers:
        key = f"soil_{layer.id}"
        drawn = sum(triangle_area(s) for s in sections_of(display, key))
        # Halved: every triangle is emitted twice, once per winding.
        assert drawn / 2 == pytest.approx(built.mass[key], rel=1e-4), key


def test_edges_are_emitted_as_line_segment_pairs(simple):
    for section in sections_of(simple[1], "soil_L1"):
        assert section.edges
        assert len(section.edges) % 6 == 0


def test_soil_takes_its_colour_from_its_material(simple):
    project, display = simple
    for layer in project.layers:
        colours = {s.color for s in sections_of(display, f"soil_{layer.id}")}
        assert colours == {project.material(layer.mat).color}


def test_the_bbox_is_the_flat_section(simple):
    _, display = simple
    assert display.bbox[2] == pytest.approx(0.0, abs=1e-6)
    assert display.bbox[5] == pytest.approx(0.0, abs=1e-6)


def test_a_sheet_pile_is_drawn_as_edges_with_no_surface():
    """1D geometry: the viewport gets a line to draw, not a sliver of a face."""
    payload = seed_project(simple=True).model_dump()
    payload.update(dimension=2)
    payload["beam_sections"] = [{"id": "az26", "name": "AZ 26-700", "E": 2.1e8,
                                 "nu": 0.3, "area": 0.0198, "inertia": 5.52e-4,
                                 "density": 7850.0, "spacing": 1.0}]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    project = Project.model_validate(payload)

    with build.session():
        model = tessellate.tessellate(project)

    section = next(s for s in model.sections if s.key == "sheetpile_1")
    assert section.edges, "the pile has to be drawable"
    assert not section.indices, "a curve has nothing to triangulate"
    assert min(section.edges[1::3]) == pytest.approx(-14.0, abs=1e-5)
    assert max(section.edges[1::3]) == pytest.approx(0.0, abs=1e-5)


def test_a_normal_load_draws_no_geometry_of_its_own():
    """Its symbol is the arrows the viewport puts on the loaded line, and nothing
    else. The strip the build used to make stood proud of the model -- on a 0.1 x 1 m
    column it was a bar lying across the top of the loaded face rather than a load
    applied to it -- and the curve the condition is written on must not be drawn as a
    sheet pile's hairline either."""
    payload = seed_project(simple=False).model_dump()
    payload.update(dimension=2, section_offset=20.0)
    payload["normal_loads"] = [{"id": "normal_1", "name": "River load", "kind": "normal",
                                "points": [[10.0, 0.0], [10.0, -5.0], [16.0, -5.0]],
                                "fluid_pressure_type": "Uniform", "pressure": 20.0,
                                "active": True}]
    project = Project.model_validate(payload)
    assert "normal_1" in project.part_keys(), "the key stays in the namespace"

    with build.session():
        model = tessellate.tessellate(project)

    assert not [s for s in model.sections if s.key == "normal_1"]


def test_a_normal_load_still_draws_nothing_in_the_project_the_server_opens_on():
    """The blank project takes a different build path (`_build_layered_soil`), which
    once drew the strip separately; it must not grow one back."""
    from app.seed import blank_project

    payload = blank_project().model_dump()
    payload.update(dimension=2, section_offset=0.5)
    payload["domain"] = {"x0": 0.0, "x1": 0.1, "z0": 0.0, "z1": 1.0,
                         "y_top": 1.0, "y_bottom": 0.0}
    payload["normal_loads"] = [{"id": "normalload_1", "name": "Normal load 1",
                                "kind": "normal",
                                "points": [[0.0, 1.0], [0.1, 1.0]],
                                "fluid_pressure_type": "Uniform", "pressure": 20.0,
                                "active": True}]
    project = Project.model_validate(payload)

    with build.session():
        model = tessellate.tessellate(project)

    assert not [s for s in model.sections if s.key == "normalload_1"]


def test_every_part_key_still_gets_a_section_when_a_pile_is_present():
    """The frontend's userData.key namespace has to stay complete."""
    payload = seed_project(simple=True).model_dump()
    payload.update(dimension=2)
    payload["beam_sections"] = [{"id": "az26", "name": "AZ 26-700", "E": 2.1e8,
                                 "nu": 0.3, "area": 0.0198, "inertia": 5.52e-4,
                                 "density": 7850.0, "spacing": 1.0}]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    project = Project.model_validate(payload)

    with build.session():
        model = tessellate.tessellate(project)

    assert set(project.part_keys()) <= {s.key for s in model.sections}


def test_an_anchor_is_drawn_as_edges_like_the_pile_it_hangs_from():
    payload = seed_project(simple=True).model_dump()
    payload.update(dimension=2)
    payload["beam_sections"] = [{"id": "az26", "name": "AZ 26-700", "E": 2.1e8,
                                 "nu": 0.3, "area": 0.0198, "inertia": 5.52e-4,
                                 "density": 7850.0, "spacing": 1}]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    payload["anchor_sections"] = [{"id": "strand", "name": "tendon", "E": 1.95e8,
                                   "area": 0.0006, "density": 7850.0, "spacing": 2.5,
                                   "tension_limit": 900.0, "compression_limit": None}]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": [12.0, -2.0],
                           "tail": [20.0, -8.0], "prestress": 250.0, "active": True}]
    project = Project.model_validate(payload)

    with build.session():
        model = tessellate.tessellate(project)

    drawn = {s.key for s in model.sections}
    assert set(project.part_keys()) <= drawn, "every part key stays selectable"
    anchor = next(s for s in model.sections if s.key == "anchor_1")
    assert anchor.edges and not anchor.indices
    assert min(anchor.edges[0::3]) == pytest.approx(12.0, abs=1e-5)
    assert max(anchor.edges[0::3]) == pytest.approx(20.0, abs=1e-5)


# ── Staged excavation ───────────────────────────────────────────────────────

def test_a_staged_excavation_is_drawable():
    """The whole CROW model, through the path the viewport uses.

    Every soil body has to be drawable, and colour is what this catches: a lift takes
    the colour of the layer it was dug out of, and one that is not given one used to
    take the whole geometry endpoint down with a KeyError rather than simply arriving
    grey.
    """
    from tests.crow_example import crow
    crow_project = crow.crow_project
    project = crow_project()
    with build.session():
        display = tessellate.tessellate(project)

    drawn = {section.key for section in display.sections}
    for key, *_ in project.soil_bodies():
        assert key in drawn, f"{key} is not drawable"
    assert "sheetpile" in drawn, "the wall must be drawn"
    assert "strut" in drawn, "the anchor must be drawn"


def test_a_lift_is_drawn_in_the_colour_of_the_layer_it_came_from():
    from tests.crow_example import crow
    crow_project = crow.crow_project
    project = crow_project()
    with build.session():
        display = tessellate.tessellate(project)

    colours = {}
    for section in display.sections:
        colours.setdefault(section.key, set()).add(section.color)
    for key, *_ in project.soil_bodies():
        layer = next(l for l in project.layers if f"soil_{l.id}" == key.partition("__")[0])
        assert colours[key] == {project.material(layer.mat).color}, key
