"""The plane-strain x-y section.

A 2D model is not a flattened 3D one: it is the *face* OCC cuts out of the solid at
`section_offset`. So the same rules the 3D build lives by still apply -- ownership is
rebuilt from the boolean's output map, never cached across it -- but every entity
that comes out is dim 2, and a part that does not reach the plane is simply not in
the section.

Areas are recomputed here from the project fields by a formula written independently
of solid_model.py, for the same reason test_build.py recomputes volumes: gmsh's failure mode
is to succeed with empty results.
"""

import gmsh
import pytest

from core.geometry import solid_model
from core.model.schemas import Project
from core.model.templates import seed_project


def section_project(simple: bool, z: float | None = None) -> Project:
    payload = seed_project(simple=simple).model_dump() | {"dimension": 2}
    if z is not None:
        payload["section_offset"] = z
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def simple():
    project = section_project(simple=True)
    with solid_model.session():
        yield project, solid_model.build_geometry(project)


@pytest.fixture(scope="module")
def full():
    project = section_project(simple=False)
    with solid_model.session():
        yield project, solid_model.build_geometry(project)


# ── The section is two-dimensional ──────────────────────────────────────────

def test_the_result_reports_its_dimension(simple):
    _, result = simple
    assert result.dim == 2


def test_every_entity_is_a_surface(simple):
    project, result = simple
    with solid_model.session():
        for key in project.part_keys():
            for tag in result.volumes[key]:
                # A dim-3 tag would still be a valid number here; asking gmsh which
                # entities exist at dim 2 is what actually proves the slice happened.
                assert (2, tag) in gmsh.model.getEntities(2), f"{key}:{tag} is not a surface"


def test_physical_groups_are_registered_at_dimension_two(simple):
    project, _ = simple
    named = {gmsh.model.getPhysicalName(2, tag) for _, tag in gmsh.model.getPhysicalGroups(2)}
    assert named == set(project.part_keys())
    assert gmsh.model.getPhysicalGroups(3) == []


def test_the_section_is_the_xy_plane_at_z_zero(simple):
    """The cut is taken at `section_offset` and then moved onto z = 0, so a 2D model
    *is* the x-y plane rather than a plane parked out along z."""
    _, result = simple
    assert result.bbox[2] == pytest.approx(0.0, abs=1e-6)
    assert result.bbox[5] == pytest.approx(0.0, abs=1e-6)
    # ...and it has real extent in both of its own axes.
    assert result.bbox[3] - result.bbox[0] > 1.0
    assert result.bbox[4] - result.bbox[1] > 1.0


def test_the_section_spans_the_domain_across_and_the_layers_down(simple):
    project, result = simple
    d = project.domain
    assert result.bbox[0] == pytest.approx(d.x0, abs=1e-6)
    assert result.bbox[3] == pytest.approx(d.x1, abs=1e-6)
    assert result.bbox[1] == pytest.approx(d.y_bottom, abs=1e-6)
    assert result.bbox[4] == pytest.approx(d.y_top, abs=1e-6)


# ── Real, measurable areas ──────────────────────────────────────────────────

def test_each_layer_sections_to_its_own_rectangle(simple):
    """The simple example is a stack of full-width boxes, so the section of each
    layer is exactly domain width x layer thickness."""
    project, result = simple
    for layer in project.layers:
        expected = project.domain.dx * (layer.top - layer.bottom)
        assert result.mass[f"soil_{layer.id}"] == pytest.approx(expected, rel=1e-6)


def test_mass_is_area_and_the_stack_tiles_the_domain(simple):
    project, result = simple
    total = sum(result.mass[f"soil_{l.id}"] for l in project.layers)
    assert total == pytest.approx(project.domain.dx * project.domain.dz, rel=1e-6)


def test_the_excavated_pit_is_missing_from_the_soil_section(full):
    """The pit is cut before the slice, so its rectangle must not be in the face."""
    project, result = full
    d, e = project.domain, project.excavation
    soil = sum(result.mass[f"soil_{l.id}"] for l in project.layers)
    pit = (e.x1 - e.x0) * (d.y_top - e.floor_y)
    # Structures inside the section displace a little more soil on top of the pit.
    assert soil < d.dx * d.dz - pit + 1e-6


# ── Staged excavation: the pit is kept, not cut away ────────────────────────
#
# With more than one excavation level the soil inside the pit outline stays in the
# model, split into the lifts it is dug in, because each lift is deactivated in its own
# stage (plan/outdated/staged-construction-plan.md sec A1). `Project.soil_bodies` names them;
# these tests are what says the geometry agrees with those names.


def staged_project() -> Project:
    """A staged excavation in plane strain: three layers, three lifts, pit on the left.

    Areas below are recomputed from these numbers rather than read off the build, for
    the reason this module's docstring gives: gmsh's failure mode is to succeed with
    empty results.
    """
    p = seed_project(simple=False).model_dump() | {"dimension": 2}
    p["domain"] |= {"y_top": 0.0, "y_bottom": -60.0}
    p["layers"] = [
        {"id": "L1", "name": "Soil_1", "mat": p["materials"][0]["id"],
         "top": 0.0, "bottom": -8.0},
        {"id": "L2", "name": "Soil_2", "mat": p["materials"][0]["id"],
         "top": -8.0, "bottom": -12.0},
        {"id": "L3", "name": "Soil_3", "mat": p["materials"][1]["id"],
         "top": -12.0, "bottom": -60.0},
    ]
    p["excavation"] = {k: v for k, v in p["excavation"].items() if k != "floor_y"}
    p["excavation"] |= {"x0": 0.0, "x1": 5.0, "levels": [-2.0, -5.0, -8.0]}
    p["wall"] |= {"top_y": 0.0, "toe_y": -13.0}
    return Project.model_validate(p)


@pytest.fixture(scope="module")
def staged():
    project = staged_project()
    with solid_model.session():
        yield project, solid_model.build_geometry(project)


def test_the_staged_pit_is_still_there(staged):
    """The opposite of test_the_excavated_pit_is_missing_from_the_soil_section: with
    lifts to dig, the soil has to survive in order to be dug."""
    project, result = staged
    for key, *_ in project.soil_bodies():
        assert result.volumes[key], f"{key} has no geometry"


def test_every_staged_body_occupies_the_band_and_side_it_is_named_for(staged):
    """Each body is where `soil_bodies` says it is.

    Checked on extents rather than area: the section's structures displace soil out of
    whichever bodies they pass through, so an area comparison would measure the wall
    rather than the split. Where a body *is* answers the question this step exists for
    -- is lift 2 the ground between the first and second dig? -- and is untouched by
    what stands in it.
    """
    project, result = staged
    e = project.excavation
    for key, bottom, top, inside in project.soil_bodies():
        x0, y0, _, x1, y1, _ = solid_model.bounding_box(result.volumes[key], dim=2)
        assert (y0, y1) == pytest.approx((bottom, top), abs=1e-3), f"{key} y-extent"
        if inside:
            assert x0 == pytest.approx(e.x0, abs=1e-3), f"{key} should start at the pit"
            assert x1 == pytest.approx(e.x1, abs=1e-3), f"{key} should end at the wall"
        else:
            assert x1 > e.x1, f"{key} should reach beyond the pit"


def test_the_excavated_ground_is_still_in_the_model(staged):
    """The whole point of staging it: soil covers more than the domain minus the pit.

    Stated as an inequality rather than an area identity. Soil plus structures does not
    add up to the domain here -- the wall ring is built outboard of the pit face
    (`_build_solids`), and this fixture puts that face on the domain edge, a symmetry
    plane, so part of the wall stands outside the soil
    entirely.
    """
    project, result = staged
    d, e = project.domain, project.excavation
    soil = sum(result.mass[key] for key, *_ in project.soil_bodies())
    assert soil > d.dx * d.dy - (e.x1 - e.x0) * d.dy, "the pit was cut away, not staged"
    assert soil <= d.dx * d.dy + 1e-6, "soil cannot exceed the domain it fills"


def test_no_entity_belongs_to_two_staged_bodies(staged):
    """The re-keying risk, tested where it lives.

    Each piece is assigned to a body by where its centre of mass fell, so a piece
    matching two bands -- or a band matching two pieces of the same layer -- would be
    meshed twice and counted twice in every area above. Tags are what says it did not
    happen; areas only say the total came out plausible.
    """
    project, result = staged
    seen: dict[int, str] = {}
    for key, *_ in project.soil_bodies():
        for tag in result.volumes[key]:
            assert tag not in seen, f"entity {tag} is both {seen.get(tag)} and {key}"
            seen[tag] = key


def test_each_staged_body_is_its_own_physical_group(staged):
    """One body, one group, one sub-model part -- which is what lets a stage deactivate
    one lift without taking its neighbour with it."""
    project, result = staged
    groups = {gmsh.model.getPhysicalName(dim, tag): (dim, tag)
              for dim, tag in gmsh.model.getPhysicalGroups(2)}
    for key, *_ in project.soil_bodies():
        assert key in groups, f"{key} is not a physical group"
    assert len({groups[key] for key, *_ in project.soil_bodies()}) == \
        len(project.soil_bodies()), "two bodies share one group"


def test_an_unstaged_project_still_cuts_the_pit_away(full):
    """The gate: one excavation level means the old behaviour, unchanged."""
    project, _ = full
    assert len(project.excavation.levels) == 1
    assert [key for key, *_ in project.soil_bodies()] == \
        [f"soil_{layer.id}" for layer in project.layers]


# ── A part that does not reach the plane ────────────────────────────────────

@pytest.mark.parametrize("key", ["wells", "anchors"])
def test_a_part_that_misses_the_plane_drops_out_instead_of_failing(full, key):
    """Two parts of the seed model genuinely have nothing at y = 20.

    The wells sit at y = 15 and y = 25, so a section at y = 20 passes between them.
    The anchors run outward in +/-y from the pit walls at y = 10 and y = 30 and slope
    away, so they never come back to mid-pit either.

    In 3D either would be a build failure (_verify). In plane strain it is the correct
    answer -- there is no well and no anchor in this section -- so it must be reported,
    not raised.
    """
    project, result = full
    assert project.section_offset == pytest.approx(20.0)
    assert result.volumes[key] == []
    assert any(key in line for line in result.log), "the drop must be logged"


def test_the_parts_that_do_reach_the_plane_are_present(full):
    _, result = full
    for key in ("wall", "struts", "piles"):
        assert result.volumes[key], f"{key} crosses y = 20 and must be in the section"


def test_part_keys_still_map_one_to_one(full):
    """Missing parts keep their key with an empty list, so the frontend's
    userData.key namespace is unchanged between 2D and 3D."""
    project, result = full
    assert sorted(result.volumes) == sorted(project.part_keys())


# ── The offset still selects ────────────────────────────────────────────────

def test_the_offset_chooses_which_parts_the_section_catches():
    """A part at another z is genuinely not in this section.

    The cut is moved onto z = 0 afterwards, so the section itself cannot say where it
    was taken -- what it *contains* has to. The piles stand on a z grid of
    14/20/26, so a cut between two rows misses them and a cut through one catches them.
    """
    with solid_model.session():
        between = solid_model.build_geometry(section_project(simple=False, z=17.0))
    with solid_model.session():
        through = solid_model.build_geometry(section_project(simple=False, z=20.0))

    assert between.volumes["piles"] == []
    assert through.volumes["piles"]
    # Both are the same plane, moved to the same place, whatever they caught.
    for result in (between, through):
        assert result.bbox[2] == pytest.approx(0.0, abs=1e-6)
        assert result.bbox[5] == pytest.approx(0.0, abs=1e-6)


# ── Load footprint imprint ──────────────────────────────────────────────────

def _vertices_at(y: float, slack: float = 1e-5) -> list[float]:
    """x of every model vertex sitting on the elevation `y`."""
    out = []
    for _, tag in gmsh.model.getEntities(0):
        box = gmsh.model.getBoundingBox(0, tag)
        if abs(box[1] - y) < slack:
            out.append(box[0])
    return sorted(out)


def _loaded_section(load: dict | None = None) -> Project:
    payload = section_project(simple=True).model_dump()
    payload["loads"] = [load or LINE_LOAD]
    return Project.model_validate(payload)


LINE_LOAD = {"id": "load_line", "name": "LineLoad_1", "kind": "line",
             "x0": 3.2, "x1": 11.7, "y": 0.0, "components": (0.0, -20.0)}
POINT_LOAD = {"id": "load_jack", "name": "PointLoad_1", "kind": "point",
              "x": 7.3, "y": -2.0, "components": (0.0, -50.0)}


def test_a_line_load_puts_a_vertex_at_each_of_its_ends():
    """Both ends become model vertices, so the mesh cannot straddle them."""
    project = _loaded_section()
    load = project.loads[0]
    with solid_model.session():
        solid_model.build_geometry(project)
        xs = _vertices_at(load.y)

    assert any(x == pytest.approx(load.x0) for x in xs)
    assert any(x == pytest.approx(load.x1) for x in xs)


def test_a_point_load_puts_a_vertex_at_its_own_coordinate():
    project = _loaded_section(POINT_LOAD)
    load = project.loads[0]
    with solid_model.session():
        solid_model.build_geometry(project)
        xs = _vertices_at(load.y)

    assert any(x == pytest.approx(load.x) for x in xs)


def test_the_section_imprint_splits_no_area():
    """A load is a boundary condition: it must not cut the sectioned soil."""
    loaded, plain = _loaded_section(), section_project(simple=True)
    with solid_model.session():
        with_load = solid_model.build_geometry(loaded)
        without_load = solid_model.build_geometry(plain)

    for key, mass in without_load.mass.items():
        if key not in solid_model.DISPLAY_ONLY:
            assert with_load.mass[key] == pytest.approx(mass), key


# ── Sheet piles embedded in the section ─────────────────────────────────────

SECTION_AZ26 = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
                "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}


def _piled_section(points, simple: bool = True) -> Project:
    payload = section_project(simple=simple).model_dump()
    payload["beam_sections"] = [SECTION_AZ26]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": points, "active": True}]
    return Project.model_validate(payload)


def test_a_sheet_pile_becomes_named_one_dimensional_curves():
    """Not a thin solid: a sheet pile is 1D structural geometry inside a 2D model."""
    project = _piled_section([[12.0, 0.0], [12.0, -14.0]])
    with solid_model.session():
        result = solid_model.build_geometry(project)
        groups = {gmsh.model.getPhysicalName(dim, tag): dim
                  for dim, tag in gmsh.model.getPhysicalGroups()}

    assert result.curves["sheetpile_1"], "the pile must survive the build"
    assert groups["sheetpile_1"] == 1
    # It keeps its part key in the 2D namespace, but with no surface behind it: the
    # pile is a curve, not a thin sliver of material.
    assert result.volumes["sheetpile_1"] == []


def test_the_pile_curves_span_exactly_the_polyline_the_user_drew():
    project = _piled_section([[12.0, 0.0], [12.0, -14.0]])
    with solid_model.session():
        result = solid_model.build_geometry(project)
        boxes = [gmsh.model.getBoundingBox(1, tag)
                 for tag in result.curves["sheetpile_1"]]

    # abs=1e-5 throughout: OCC pads a bounding box by about 1.5e-7, and approx(0.0)
    # would otherwise compare against an absolute tolerance of 1e-12.
    assert min(b[1] for b in boxes) == pytest.approx(-14.0, abs=1e-5)
    assert max(b[4] for b in boxes) == pytest.approx(0.0, abs=1e-5)
    assert all(b[0] == pytest.approx(12.0, abs=1e-5)
               and b[3] == pytest.approx(12.0, abs=1e-5) for b in boxes)


def test_the_pile_is_embedded_in_the_soil_rather_than_cutting_it_away():
    """It displaces no soil: the same area is there with and without the pile."""
    plain = section_project(simple=True)
    piled = _piled_section([[12.0, 0.0], [12.0, -14.0]])
    with solid_model.session():
        without = solid_model.build_geometry(plain)
        with_pile = solid_model.build_geometry(piled)

    for key, area in without.mass.items():
        if key not in solid_model.DISPLAY_ONLY:
            # A layer the pile crosses is in two pieces now, with the same area between them.
            pieces = piled.expand_body_keys([key])
            assert sum(with_pile.mass[piece] for piece in pieces) == pytest.approx(area), key


def test_a_polyline_pile_keeps_every_segment():
    project = _piled_section([[12.0, 0.0], [12.0, -7.0], [14.0, -12.0]])
    with solid_model.session():
        result = solid_model.build_geometry(project)
        boxes = [gmsh.model.getBoundingBox(1, tag)
                 for tag in result.curves["sheetpile_1"]]

    assert max(b[3] for b in boxes) == pytest.approx(14.0)
    assert min(b[1] for b in boxes) == pytest.approx(-12.0)


def test_an_inactive_pile_is_kept_in_the_project_but_not_built():
    payload = section_project(simple=True).model_dump()
    payload["beam_sections"] = [SECTION_AZ26]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": False}]
    project = Project.model_validate(payload)
    with solid_model.session():
        result = solid_model.build_geometry(project)

    assert result.curves.get("sheetpile_1", []) == []


def test_a_sheet_pile_is_swept_onto_the_section_plane_of_a_3d_model():
    """A 2D pile is not dropped by the solid model: it is built where it was drawn.

    It becomes a surface rather than the curve a section leaves, because a wall needs
    an out-of-plane width to be meshed as a shell -- see `solid_model._section_sweeps`, and
    tests/test_section_structures_3d.py for where the sweep is placed.
    """
    payload = seed_project(simple=True).model_dump()
    payload["beam_sections"] = [SECTION_AZ26]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    project = Project.model_validate(payload)
    with solid_model.session():
        result = solid_model.build_geometry(project)

    assert result.faces.get("sheetpile_1"), "the pile vanished from the solid model"
    assert not any("not part of this 3D model" in line for line in result.log)


# ── Anchors: a tie from a sheet pile to a restrained point ──────────────────

TENDON = {"id": "strand", "name": "4-strand tendon", "E": 1.95e8, "area": 0.0006,
          "density": 7850.0, "spacing": 2.5, "tension_limit": 900.0,
          "compression_limit": None}


def _anchored_section(head=(12.0, -2.0), tail=(20.0, -8.0), active=True) -> Project:
    payload = _piled_section([[12.0, 0.0], [12.0, -14.0]]).model_dump()
    payload["anchor_sections"] = [TENDON]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": list(head), "tail": list(tail),
                           "prestress": 250.0, "active": active}]
    return Project.model_validate(payload)


def test_an_anchor_becomes_its_own_named_curve():
    with solid_model.session():
        result = solid_model.build_geometry(_anchored_section())
        groups = {gmsh.model.getPhysicalName(dim, tag): dim
                  for dim, tag in gmsh.model.getPhysicalGroups()}

    assert result.ties["anchor_1"], "the anchor must survive the build"
    assert groups["anchor_1"] == 1
    assert result.volumes["anchor_1"] == [], "an anchor is a line, not a sliver of soil"


def test_the_anchor_splits_the_pile_at_its_head():
    """The head has to become a vertex the beam shares, which is what makes it one
    node in the mesh, where the head sits in two beam elements."""
    with solid_model.session():
        plain = solid_model.build_geometry(_piled_section([[12.0, 0.0], [12.0, -14.0]]))
        plain_pieces = len(plain.curves["sheetpile_1"])
        anchored = solid_model.build_geometry(_anchored_section())

    assert len(anchored.curves["sheetpile_1"]) == plain_pieces + 1


def test_the_anchor_spans_exactly_the_head_and_tail_drawn():
    with solid_model.session():
        result = solid_model.build_geometry(_anchored_section())
        boxes = [gmsh.model.getBoundingBox(1, tag) for tag in result.ties["anchor_1"]]

    assert min(b[0] for b in boxes) == pytest.approx(12.0, abs=1e-5)
    assert max(b[3] for b in boxes) == pytest.approx(20.0, abs=1e-5)
    assert min(b[1] for b in boxes) == pytest.approx(-8.0, abs=1e-5)
    assert max(b[4] for b in boxes) == pytest.approx(-2.0, abs=1e-5)


def test_the_anchor_does_not_cut_or_displace_the_soil():
    with solid_model.session():
        without = solid_model.build_geometry(_piled_section([[12.0, 0.0], [12.0, -14.0]]))
        with_anchor = solid_model.build_geometry(_anchored_section())

    for key, area in without.mass.items():
        if key not in solid_model.DISPLAY_ONLY:
            assert with_anchor.mass[key] == pytest.approx(area), key


def test_an_inactive_anchor_is_kept_in_the_project_but_not_built():
    with solid_model.session():
        result = solid_model.build_geometry(_anchored_section(active=False))

    assert result.ties.get("anchor_1", []) == []


def test_a_plane_anchor_is_built_on_the_section_plane_of_a_3d_model():
    """The mirror of the sheet pile above: the tie hangs off the wall in 3D too."""
    payload = seed_project(simple=True).model_dump()
    payload["beam_sections"] = [SECTION_AZ26]
    payload["beams"] = [{"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
                         "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}]
    payload["anchor_sections"] = [TENDON]
    payload["anchors"] = [{"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
                           "section": "strand", "head": [12.0, -2.0],
                           "tail": [20.0, -8.0], "prestress": 250.0, "active": True}]
    with solid_model.session():
        result = solid_model.build_geometry(Project.model_validate(payload))

    assert result.ties.get("anchor_1"), "the 2D anchor vanished from the solid model"
    assert "anchor_1" in result.tie_nodes


def test_plane_strain_verification_allows_parts_that_miss_the_section():
    project = seed_project().model_copy(update={"dimension": 2})
    solid_model._verify(project, {})


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


def test_anchor_head_insertion_skips_a_zero_length_polyline_leg():
    assert solid_model._split_at(
        [(0, 0), (0, 0), (2, 0)], [(1, 0)]) == [
            (0, 0), (0, 0), (1, 0), (2, 0)]
