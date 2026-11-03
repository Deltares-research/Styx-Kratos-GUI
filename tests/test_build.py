"""The OCC geometry build.

These tests are the reason the backend exists: they assert the model is a real B-rep
solid with measurable volume, rather than the invented boxes of js/viewport.js.

The expected soil volume is recomputed analytically here, from the project fields, by a
formula written independently of solid_model.py. That redundancy is the point — if a boolean
silently drops a solid (the plan's headline risk, and gmsh's failure mode is to succeed
with empty results) the number moves and this test fails.
"""

import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.geometry import solid_model
from core.model.schemas import Project
from core.model.templates import seed_project


@pytest.fixture(scope="module")
def result():
    with solid_model.session():
        yield solid_model.build_geometry(seed_project(simple=False))


@pytest.fixture(scope="module")
def project() -> Project:
    return seed_project(simple=False)


def assert_bounds(got, exact, slack=0.2):
    """Assert a bounding box encloses `exact` without exceeding it by more than `slack`.

    Not equality: OCC's Bnd_Box bounds a curved face by its control hull rather than the
    surface (see solid_model.bounding_box), so a solid with a bored hole or an oblique
    cylinder overstates its extent by centimetres. Containment plus a ceiling is the
    strongest claim that is actually true.
    """
    names = ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax")
    for i, (name, g, e) in enumerate(zip(names, got, exact)):
        low, high = (e - slack, e + 1e-6) if i < 3 else (e - 1e-6, e + slack)
        assert low <= g <= high, f"{name}: {g} not within [{low}, {high}]"


# ── The identity contract ───────────────────────────────────────────────────

def test_every_part_key_becomes_a_physical_group(result, project):
    """gmsh physical group names ARE the frontend's userData.key strings.

    If these drift, selection silently degrades to "No object selected"
    (js/explorer.js:149) with no error anywhere.
    """
    assert sorted(result.volumes) == sorted(project.part_keys())


def test_no_part_is_lost_in_a_boolean(result, project):
    """OCC booleans on the 0.8 m wall ring can quietly return nothing."""
    empty = [key for key in project.part_keys() if not result.volumes[key]]
    assert empty == []


def test_physical_groups_are_registered_in_gmsh_under_the_same_names(result, project):
    import gmsh

    named = {gmsh.model.getPhysicalName(3, tag) for _, tag in gmsh.model.getPhysicalGroups(3)}
    assert named == set(project.part_keys())


# ── Real, measurable geometry ───────────────────────────────────────────────

def _expected_soil_volume(p: Project) -> float:
    """Domain box, less every void and every solid that displaces soil.

    Written from the project fields alone, deliberately not sharing code with solid_model.py.
    """
    d, e, w = p.domain, p.excavation, p.wall

    domain = d.dx * d.dy * d.dz
    pit = (e.x1 - e.x0) * (e.z1 - e.z0) * (d.y_top - e.floor_y)

    # Wall ring: outboard of the pit face, only the part below ground displaces soil.
    t = w.thickness
    ring_area = (e.x1 - e.x0 + 2 * t) * (e.z1 - e.z0 + 2 * t) - (e.x1 - e.x0) * (e.z1 - e.z0)
    wall = ring_area * (min(w.top_y, d.y_top) - w.toe_y)

    piles = len(p.piles.xs) * len(p.piles.zs) * math.pi * p.piles.radius**2 * p.piles.length

    # Both wells stand inside the pit footprint, so only the length below the pit floor
    # is still surrounded by soil; the rest passes through the excavated void.
    wells = len(p.wells.positions) * math.pi * p.wells.radius**2 * (e.floor_y - (p.wells.top_y - p.wells.length))

    # Anchor heads bear on the wall, so the first stretch of each shaft is inside wall
    # material, not soil. head_offset is measured inward from the wall's outer face.
    a = p.anchor_rows
    inside_wall = (t - a.head_offset) / math.cos(math.radians(a.inclination_deg))
    anchors = 2 * len(a.xs) * math.pi * a.radius**2 * (a.length - inside_wall)

    return domain - pit - wall - piles - wells - anchors


def test_soil_volume_matches_an_independent_analytic_model(result, project):
    soil = sum(result.mass[key] for key in result.volumes if key.startswith("soil_"))
    assert soil == pytest.approx(_expected_soil_volume(project), rel=1e-6)


def test_soil_layers_keep_their_relative_thickness(result, project):
    """L1 is 8 m thick, L2 is 17 m; the pit and the structures bite into both."""
    l1, l2 = result.mass["soil_L1"], result.mass["soil_L2"]
    assert l1 < l2
    assert l1 + l2 == pytest.approx(_expected_soil_volume(project), rel=1e-6)


def test_excavation_aliases_the_remaining_soil(result, project):
    """js/viewport.js:404 builds `excavation` as buildSoil(true, ...) — the soil block
    with the pit removed, shown instead of the layers in staged-construction mode
    (js/viewport.js:426). It is the same material, grouped under one key."""
    soil = sum(result.mass[key] for key in result.volumes if key.startswith("soil_"))
    assert result.mass["excavation"] == pytest.approx(soil, rel=1e-9)


def test_the_pit_is_actually_empty(result, project):
    """No soil survives above the pit floor inside the excavation footprint."""
    import gmsh

    e, d = project.excavation, project.domain
    probes = [
        ((e.x0 + e.x1) / 2, (e.floor_y + d.y_top) / 2, (e.z0 + e.z1) / 2),
        (e.x0 + 0.5, e.floor_y + 0.5, e.z0 + 0.5),
        (e.x1 - 0.5, d.y_top - 0.5, e.z1 - 0.5),
    ]
    soil_tags = [t for key in result.volumes if key.startswith("soil_") for t in result.volumes[key]]
    for x, y, z in probes:
        inside = [t for t in soil_tags if gmsh.model.isInside(3, t, [x, y, z])]
        assert inside == [], f"soil {inside} still occupies the pit at ({x}, {y}, {z})"


def test_soil_survives_below_the_pit_floor(result, project):
    """The complement of the test above: the pit is a void, not a hole through the model."""
    import gmsh

    e = project.excavation
    x, y, z = (e.x0 + e.x1) / 2, e.floor_y - 3.0, (e.z0 + e.z1) / 2
    soil_tags = [t for key in result.volumes if key.startswith("soil_") for t in result.volumes[key]]
    assert any(gmsh.model.isInside(3, t, [x, y, z]) for t in soil_tags)


# ── Structures ──────────────────────────────────────────────────────────────

def test_wall_is_a_ring_not_a_slab(result, project):
    """A closed ring outboard of the pit face, hollow in the middle.

    No exact volume here: the struts and the anchor shafts both pass through the wall
    and are claimed from it by priority, so the closed form would be an inclusion-
    exclusion exercise that tests arithmetic rather than the build. Bounds plus a
    hollowness probe catch the failure that matters -- a solid plug instead of a ring.
    """
    import gmsh

    e, w, t = project.excavation, project.wall, project.wall.thickness
    assert_bounds(
        solid_model.bounding_box(result.volumes["wall"]),
        (e.x0 - t, w.toe_y, e.z0 - t, e.x1 + t, w.top_y, e.z1 + t),
    )

    # Mid-pit, at wall depth: inside the ring's bounding box but outside the ring.
    x, y, z = (e.x0 + e.x1) / 2, (w.toe_y + e.floor_y) / 2, (e.z0 + e.z1) / 2
    assert not any(gmsh.model.isInside(3, tag, [x, y, z]) for tag in result.volumes["wall"])

    # An upper bound: the ring can only ever be thinner than its full extrusion.
    ring_area = (e.x1 - e.x0 + 2 * t) * (e.z1 - e.z0 + 2 * t) - (e.x1 - e.x0) * (e.z1 - e.z0)
    assert 0 < result.mass["wall"] < ring_area * (w.top_y - w.toe_y)


def test_struts_span_the_pit_horizontally(result, project):
    """A strut spans the pit out of plane, which is the Z axis: the frozen mockup's
    PY1-PY0+1.6 length is that span. Its vertical extent is the beam depth only."""

    s, e = project.struts, project.excavation
    tags = result.volumes["struts"]
    xmin, ymin, zmin, xmax, ymax, zmax = solid_model.bounding_box(tags)

    assert zmin == pytest.approx(e.z0 - s.overhang, abs=1e-6)
    assert zmax == pytest.approx(e.z1 + s.overhang, abs=1e-6)
    # Vertical extent is the beam depth only, nowhere near the 21.6 m span.
    assert ymax - ymin == pytest.approx(s.waler_height, abs=1e-6)


def test_piles_hang_below_the_pit_floor(result, project):
    p = project
    xmin, ymin, zmin, xmax, ymax, zmax = solid_model.bounding_box(result.volumes["piles"])
    assert ymax == pytest.approx(p.piles.top_y, abs=1e-6)
    assert ymin == pytest.approx(p.piles.top_y - p.piles.length, abs=1e-6)
    assert result.mass["piles"] == pytest.approx(
        len(p.piles.xs) * len(p.piles.zs) * math.pi * p.piles.radius**2 * p.piles.length, rel=1e-6
    )


def test_anchors_rake_outward_and_downward_from_both_walls(result, project):
    """Two rows, heads bearing on the wall, each shaft reaching out into the retained
    soil and down at the design inclination."""
    a, e, t = project.anchor_rows, project.excavation, project.wall.thickness
    inc = math.radians(a.inclination_deg)
    reach, drop = a.length * math.cos(inc), a.length * math.sin(inc)
    head_z0, head_z1 = e.z0 - t + a.head_offset, e.z1 + t - a.head_offset

    assert_bounds(
        solid_model.bounding_box(result.volumes["anchors"]),
        (
            min(a.xs) - a.radius, a.head_y - drop, head_z0 - reach,
            max(a.xs) + a.radius, a.head_y + a.radius * math.cos(inc), head_z1 + reach,
        ),
    )

    # Only the stretch beyond the wall's outer face is grouted into soil; the rest is
    # claimed by `anchors` out of wall material.
    embedded = a.length - (t - a.head_offset) / math.cos(inc)
    assert result.mass["anchors"] == pytest.approx(
        2 * len(a.xs) * math.pi * a.radius**2 * a.length, rel=1e-6
    )
    assert embedded < a.length


def test_wells_are_vertical_pipes_through_the_full_drawdown_depth(result, project):
    w = project.wells
    xmin, ymin, zmin, xmax, ymax, zmax = solid_model.bounding_box(result.volumes["wells"])
    assert ymin == pytest.approx(w.top_y - w.length, abs=1e-6)
    assert (xmax - xmin) == pytest.approx(
        max(x for x, _ in w.positions) - min(x for x, _ in w.positions) + 2 * w.radius, abs=1e-6
    )


# ── Display-only parts stay out of the FE partition ─────────────────────────

def test_load_and_water_do_not_carve_the_soil(result, project):
    """The surface load is a kN/m2 boundary condition and the phreatic level is a
    reference plane. Their 3D pads are indicators, so they must not participate in the
    fragment — otherwise they would split soil volumes and change the mesh."""
    assert result.volumes["load"] and result.volumes["water"]
    soil = sum(result.mass[key] for key in result.volumes if key.startswith("soil_"))
    assert soil == pytest.approx(_expected_soil_volume(project), rel=1e-6)


def test_water_plane_sits_at_the_phreatic_level(result, project):
    xmin, ymin, zmin, xmax, ymax, zmax = solid_model.bounding_box(result.volumes["water"])
    assert (ymin + ymax) / 2 == pytest.approx(project.water.y, abs=1e-6)


# ── Model-wide ──────────────────────────────────────────────────────────────

def test_bounding_box_covers_the_domain(result, project):
    d = project.domain
    xmin, ymin, zmin, xmax, ymax, zmax = result.bbox
    assert xmin <= d.x0 and zmin <= d.z0
    assert xmax >= d.x1 and zmax >= d.z1
    assert ymin == pytest.approx(d.y_bottom, abs=1e-6)
    assert ymax >= project.wall.top_y


def test_custom_parts_are_integrated_and_prioritized(project, tmp_path):
    from core.model.schemas import CustomPart
    from core.geometry import solid_model

    # We create a dummy .brep file representing a box cutting through the soil
    p = project.model_copy(deep=True)

    import gmsh
    with solid_model.session():
        # A box spanning from x=5, y=5, z=-2 to x=10, y=10, z=-5
        gmsh.clear()
        gmsh.model.occ.addBox(5, 5, -2, 5, 5, -3)
        gmsh.model.occ.synchronize()
        # `tmp_path`, not "/tmp": there is no /tmp on Windows, and gmsh wrote the brep
        # somewhere the import then could not find -- which surfaced as "the geometry
        # build produced no volume for custom_1", a failure that reads like a boolean
        # problem and is not one.
        brep_path = str(tmp_path / "test_custom.brep")
        gmsh.write(brep_path)
        gmsh.clear()

    p.custom_parts.append(CustomPart(
        key="custom_1",
        label="My Custom Box",
        source="import",
        source_file=brep_path
    ))
    
    with solid_model.session():
        res = solid_model.build_geometry(p)
        
    assert "custom_1" in res.volumes
    # Volume is 5 * 5 * 3 = 75
    assert res.mass["custom_1"] == pytest.approx(75.0, rel=1e-6)


def test_custom_line_and_surface_parts_are_display_only_overlays(project, tmp_path):
    """A drawn line or flat surface has no volume to fragment or boolean -- it is a
    display-only overlay, the same status load/water already have. Before this, any
    custom part without a volume made `_verify` raise GeometryError, because it only
    ever checked `volumes`."""
    from core.model.schemas import CustomPart

    p = project.model_copy(deep=True)

    import gmsh
    with solid_model.session():
        gmsh.clear()
        p1 = gmsh.model.occ.addPoint(0, 0, 0)
        p2 = gmsh.model.occ.addPoint(10, 0, 0)
        gmsh.model.occ.addLine(p1, p2)
        gmsh.model.occ.synchronize()
        line_path = str(tmp_path / "line.brep")
        gmsh.write(line_path)

        gmsh.clear()
        q1 = gmsh.model.occ.addPoint(0, 0, 0)
        q2 = gmsh.model.occ.addPoint(10, 0, 0)
        q3 = gmsh.model.occ.addPoint(10, 10, 0)
        q4 = gmsh.model.occ.addPoint(0, 10, 0)
        l1 = gmsh.model.occ.addLine(q1, q2)
        l2 = gmsh.model.occ.addLine(q2, q3)
        l3 = gmsh.model.occ.addLine(q3, q4)
        l4 = gmsh.model.occ.addLine(q4, q1)
        loop = gmsh.model.occ.addCurveLoop([l1, l2, l3, l4])
        gmsh.model.occ.addPlaneSurface([loop])
        gmsh.model.occ.synchronize()
        surface_path = str(tmp_path / "surface.brep")
        gmsh.write(surface_path)
        gmsh.clear()

    p.custom_parts.append(CustomPart(
        key="drawn_line", label="A line", source="gui", source_file=line_path,
    ))
    p.custom_parts.append(CustomPart(
        key="drawn_surface", label="A surface", source="gui", source_file=surface_path,
    ))

    with solid_model.session():
        res = solid_model.build_geometry(p)  # must not raise GeometryError

    assert "drawn_line" not in res.volumes
    assert "drawn_surface" not in res.volumes
    assert [dim for dim, _ in res.overlays["drawn_line"]] == [1]
    assert [dim for dim, _ in res.overlays["drawn_surface"]] == [2]


def test_build_is_repeatable(project):
    """Every request rebuilds in the same long-lived worker process, so a stale model
    leaking between builds would show up as drifting volumes."""
    with solid_model.session():
        first = solid_model.build_geometry(project)
        first_mass = dict(first.mass)
        second = solid_model.build_geometry(project)

        assert sorted(second.volumes) == sorted(first_mass)
        for key, mass in first_mass.items():
            assert second.mass[key] == pytest.approx(mass, rel=1e-9)


# ── Load footprint imprint ──────────────────────────────────────────────────

def _top_faces(slack: float = 1e-5) -> list[tuple[float, ...]]:
    """Bounding boxes of every face lying flat on y = 0, the domain's top plane.

    `slack` rather than an exact comparison: OCC pads a bounding box by about 1.5e-7,
    so a face on the plane reports a hair above it.
    """
    import gmsh
    return [box for box in (gmsh.model.getBoundingBox(2, tag)
                            for _, tag in gmsh.model.getEntities(2))
            if abs(box[1] - box[4]) < slack and abs(box[4]) < slack]


def test_a_load_footprint_splits_the_top_face_at_its_own_edges():
    """The whole point of the imprint: the pad's edges become model edges.

    On the simple example, whose ground surface is the flat plane the 3D surface-load
    export requires. The full project has no face at `y_top` for a surface load to sit
    on in the first place.
    """
    project = seed_project()
    load = project.loads[0]
    with solid_model.session():
        solid_model.build_geometry(project)
        footprints = [box for box in _top_faces()
                      if box[0] == pytest.approx(load.x0) and box[3] == pytest.approx(load.x1)]

    assert len(footprints) == 1
    assert footprints[0][2] == pytest.approx(load.z0)
    # Clipped where the pad overhangs the domain; see the overhang test below.
    assert footprints[0][5] == pytest.approx(min(load.z1, project.domain.z1))


def test_the_imprint_splits_no_material_and_leaves_nothing_behind():
    """A load is a boundary condition: imprinting it must not change the solid model."""
    with_load = seed_project(simple=False)
    without_load = seed_project(simple=False)
    without_load.loads = []

    with solid_model.session():
        loaded = solid_model.build_geometry(with_load)
        plain = solid_model.build_geometry(without_load)

    material = lambda volumes: {key: len(tags) for key, tags in volumes.items()
                                if key not in solid_model.DISPLAY_ONLY}

    assert material(loaded.volumes) == material(plain.volumes)
    for key, mass in plain.mass.items():
        if key not in solid_model.DISPLAY_ONLY:
            assert loaded.mass[key] == pytest.approx(mass), key


def test_a_footprint_overhanging_the_domain_leaves_no_free_floating_surface():
    """The seeded pad hangs 1 m past the simple example's 25 m domain."""
    project = seed_project()
    with solid_model.session():
        solid_model.build_geometry(project)
        overhang = [box for box in _top_faces() if box[5] > project.domain.z1 + 1e-5]

    assert overhang == []


def test_solid_model_reentrant_session_does_not_finalize_a_caller_owned_gmsh():
    import gmsh

    with solid_model.session():
        with solid_model.session():
            assert gmsh.isInitialized()
        assert gmsh.isInitialized()


def test_solid_model_helpers_assign_owners_and_report_omitted_overlays():
    assert solid_model._assign_by_priority({
        1: {"soil_L1", "wall"}, 2: {"soil_L1", "custom_z", "custom_a"},
    }) == {"wall": [1], "custom_a": [2]}

    log = []
    assert solid_model._drop_overlays({"z_line": [(1, 4)], "a_surface": [(2, 3)]}, log) == {}
    assert [entry.split(" : ")[1].split()[0] for entry in log] == ["a_surface", "z_line"]


def test_empty_bounding_box_requires_or_returns_a_camera_fallback():
    fallback = (-1.0, -2.0, -3.0, 1.0, 2.0, 3.0)

    assert solid_model.bounding_box([], fallback=fallback) == fallback
    with pytest.raises(ValueError, match="no volumes and no fallback"):
        solid_model.bounding_box([])


@pytest.mark.parametrize("previous, expected", [
    (None, [("get", 13), ("initialize",)]),
    ("python-handler", [("get", 13), ("initialize",), ("restore", 13, "python-handler")]),
])
def test_posix_initialization_restores_pythons_sigpipe_handler(
        monkeypatch, previous, expected):
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

    assert events == expected
