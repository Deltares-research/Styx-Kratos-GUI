"""Display tessellation: the OCC solid model turned into buffers the browser can draw.

The payload is deliberately buffer-shaped -- flat arrays, never [{x,y,z}, ...] -- so the
frontend can hand it straight to THREE.BufferAttribute and so switching to a binary
encoder later is a serializer change rather than a schema change.

The headline test here is `signed volume == OCC mass`. It is one assertion that catches
four separate failures at once: inward-facing winding (negative), a surface left out
(too small), an interior face emitted (double-counted), and a broken tag->index remap
(garbage). Triangle soup that merely *looks* plausible cannot pass it.
"""

import json
import math

import pytest

from core.geometry import solid_model, tessellation
from core.model.schemas import PointLoad, Project
from core.model.templates import seed_project


@pytest.fixture(scope="module")
def project() -> Project:
    return seed_project(simple=False)


@pytest.fixture(scope="module")
def display(project):
    with solid_model.session():
        yield tessellation.tessellate(project)


def sections_of(display, key):
    return [s for s in display.sections if s.key == key]


def signed_volume(section) -> float:
    """Divergence theorem over a closed triangulated surface.

    Positive only when the winding is counter-clockwise seen from outside, which is what
    THREE.FrontSide culling expects.
    """
    p, total = section.positions, 0.0
    for i in range(0, len(section.indices), 3):
        a, b, c = (section.indices[i + k] * 3 for k in range(3))
        ax, ay, az = p[a], p[a + 1], p[a + 2]
        bx, by, bz = p[b], p[b + 1], p[b + 2]
        cx, cy, cz = p[c], p[c + 1], p[c + 2]
        total += (ax * (by * cz - bz * cy)
                  - ay * (bx * cz - bz * cx)
                  + az * (bx * cy - by * cx))
    return total / 6.0


# ── Structure ───────────────────────────────────────────────────────────────

def test_every_part_key_is_drawable(display, project):
    assert {s.key for s in display.sections} == set(project.part_keys())


def test_sections_are_non_empty_and_well_formed(display):
    for s in display.sections:
        assert s.indices and len(s.indices) % 3 == 0, s.key
        assert len(s.positions) % 3 == 0 and s.positions, s.key
        assert max(s.indices) < len(s.positions) // 3, f"{s.key}: index out of range"
        assert min(s.indices) >= 0, s.key


def test_no_coordinate_is_nan_or_infinite(display):
    for s in display.sections:
        assert all(math.isfinite(v) for v in s.positions), s.key
        assert all(math.isfinite(v) for v in s.edges), s.key


def test_edges_are_line_segment_pairs(display):
    """OCC's curve tessellation comes back as Line elements, which is a free and much
    cleaner wireframe than three.js EdgesGeometry guessing from a crease angle."""
    for s in display.sections:
        assert len(s.edges) % 6 == 0, s.key
    assert sum(len(s.edges) for s in display.sections) > 0


# ── The geometry is real ────────────────────────────────────────────────────

def test_closed_surfaces_wind_outward_and_enclose_their_true_volume(display, project):
    """The tolerance is faceting error and nothing else.

    Inscribed facets make a tessellated cylinder about half a percent light, while a
    faceted *hole* shrinks and leaves the surrounding solid a hair heavy -- so the band
    is two-sided. Every real failure here is far larger: an inverted part reads negative,
    a dropped face loses whole cubic metres, a doubled face roughly doubles the total.
    """
    with solid_model.session():
        result = solid_model.build_geometry(project)

        for key in project.part_keys():
            enclosed = sum(signed_volume(s) for s in sections_of(display, key))
            mass = result.mass[key]
            assert enclosed > 0, f"{key}: winding points inward"
            assert 0.98 * mass <= enclosed <= 1.01 * mass, (
                f"{key}: tessellation encloses {enclosed:.4f} m3, solid measures {mass:.4f} m3"
            )


def test_box_shaped_parts_tessellate_exactly(display, project):
    """The load pad and the water plane are plain boxes -- no curvature, so no
    faceting loss. They pin the volume test's arithmetic independently of tolerance."""
    lo, wa, d = project.loads[0], project.water, project.domain
    assert sum(signed_volume(s) for s in sections_of(display, "load")) == pytest.approx(
        (lo.x1 - lo.x0) * (lo.z1 - lo.z0) * lo.thickness, rel=1e-6
    )
    assert sum(signed_volume(s) for s in sections_of(display, "water")) == pytest.approx(
        (d.dx + 2 * wa.margin) * (d.dz + 2 * wa.margin) * wa.thickness, rel=1e-6
    )


def test_coordinate_defined_point_load_has_a_display_indicator(project):
    candidate = project.model_copy(deep=True)
    candidate.dimension = 2
    candidate.section_offset = 5.0
    candidate.loads = [PointLoad(
        id="load_crane", name="Crane", x=5.0, y=-3.0,
        thickness=0.25, components=(0.0, -100.0),
    )]
    with solid_model.session():
        rendered = tessellation.tessellate(candidate)

    sections = sections_of(rendered, "load_crane")
    assert sections and sections[0].positions
    xs = sections[0].positions[0::3]
    ys = sections[0].positions[1::3]
    zs = sections[0].positions[2::3]
    assert sum(xs) / len(xs) == pytest.approx(5.0, abs=0.05)
    assert sum(ys) / len(ys) == pytest.approx(-3.0, abs=0.05)
    # The section was cut at z = 5.0 and moved onto the x-y plane with everything else.
    assert sum(zs) / len(zs) == pytest.approx(0.0, abs=0.05)


def test_interior_faces_between_volumes_of_one_part_are_dropped(display, project):
    """Every pile is split in two where it crosses the L1/L2 interface at z = -8, so the
    12 piles are 24 volumes meeting on 12 shared discs. Drawing those would waste
    triangles and show through as seams wherever the part is transparent.

    Note the two soil_L1 volumes are *not* a valid subject here: the wall ring separates
    the soil outside it from the sliver trapped inside it between the pit floor and the
    layer base, so they share no face at all.
    """
    import gmsh

    with solid_model.session():
        result = solid_model.build_geometry(project)
        gmsh.model.mesh.importStl()

        naive = 0
        for tag in result.volumes["piles"]:
            for _, surf in gmsh.model.getBoundary([(3, tag)], oriented=False):
                types, elems, _ = gmsh.model.mesh.getElements(2, abs(surf))
                naive += sum(len(e) for t, e in zip(types, elems) if t == 2)

    emitted = sum(len(s.indices) // 3 for s in sections_of(display, "piles"))
    assert len(result.volumes["piles"]) == 2 * len(project.piles.xs) * len(project.piles.zs)
    assert emitted < naive, f"emitted {emitted} triangles of {naive}; interior faces kept"


def test_geometry_stays_inside_the_model_bounds(display):
    xmin, ymin, zmin, xmax, ymax, zmax = display.bbox
    for s in display.sections:
        xs, ys, zs = s.positions[0::3], s.positions[1::3], s.positions[2::3]
        assert xmin <= min(xs) and max(xs) <= xmax, s.key
        assert ymin <= min(ys) and max(ys) <= ymax, s.key
        assert zmin <= min(zs) and max(zs) <= zmax, s.key


# ── Colours: the frozen palette, and materials for soil ─────────────────────

def test_soil_takes_its_colour_from_its_assigned_material(display, project):
    for layer in project.layers:
        section = sections_of(display, f"soil_{layer.id}")
        assert {s.color for s in section} == {project.material(layer.mat).color}


def test_excavation_carries_one_section_per_soil_material(display, project):
    """`excavation` is the same soil under one key (js/viewport.js:404), so it is drawn
    with the same per-layer colours rather than flattened to a single tint."""
    expected = {project.material(l.mat).color for l in project.layers}
    assert {s.color for s in sections_of(display, "excavation")} == expected


def test_structures_use_the_frozen_viewport_palette(display):
    """js/viewport.js:330-337. Changing these changes how the app looks, so they are
    pinned rather than left to drift."""
    for key, color in {
        "wall": "#4b6ea8", "struts": "#b5573a", "anchors": "#2f6f4f",
        "piles": "#7a6a55", "load": "#d4342d", "water": "#2f8fd8", "wells": "#2f8fd8",
    }.items():
        assert {s.color for s in sections_of(display, key)} == {color}, key


# ── Wire format ─────────────────────────────────────────────────────────────

def test_coordinates_are_rounded_for_the_wire(display):
    """Python's repr emits 17 significant digits by default, which triples the payload to
    describe sub-nanometre positions of a 50 m excavation."""
    for s in display.sections:
        for v in s.positions[:600]:
            assert round(v, tessellation.DECIMALS) == v, f"{s.key}: {v!r} is not rounded"


def test_payload_serialises_to_plain_json(display):
    encoded = json.dumps(display.to_dict())
    restored = json.loads(encoded)
    assert restored["bbox"] == list(display.bbox)
    assert len(restored["sections"]) == len(display.sections)
    assert set(restored["sections"][0]) == {"key", "color", "positions", "indices", "edges"}


def test_payload_stays_small_enough_to_send_as_json(display):
    """The plan's premise: at this size JSON plus GZipMiddleware is the right call, and
    a binary format would be premature. If this trips, revisit that."""
    raw = len(json.dumps(display.to_dict()))
    assert raw < 6_000_000, f"{raw} bytes uncompressed"
    assert sum(len(s.indices) // 3 for s in display.sections) < 60_000


# ── Display-only overlays: drawn lines and bare surfaces ────────────────────

@pytest.fixture
def project_with_line_and_surface(tmp_path):
    import gmsh

    from core.model.schemas import CustomPart

    p = seed_project(simple=False)

    with solid_model.session():
        gmsh.clear()
        a = gmsh.model.occ.addPoint(2, 2, 0)
        b = gmsh.model.occ.addPoint(8, 2, 0)
        gmsh.model.occ.addLine(a, b)
        gmsh.model.occ.synchronize()
        line_path = str(tmp_path / "line.brep")
        gmsh.write(line_path)

        gmsh.clear()
        q1 = gmsh.model.occ.addPoint(2, 6, 0)
        q2 = gmsh.model.occ.addPoint(8, 6, 0)
        q3 = gmsh.model.occ.addPoint(8, 12, 0)
        q4 = gmsh.model.occ.addPoint(2, 12, 0)
        loop = gmsh.model.occ.addCurveLoop([
            gmsh.model.occ.addLine(q1, q2), gmsh.model.occ.addLine(q2, q3),
            gmsh.model.occ.addLine(q3, q4), gmsh.model.occ.addLine(q4, q1),
        ])
        gmsh.model.occ.addPlaneSurface([loop])
        gmsh.model.occ.synchronize()
        surface_path = str(tmp_path / "surface.brep")
        gmsh.write(surface_path)
        gmsh.clear()

    p.custom_parts.append(CustomPart(
        key="drawn_line", label="A line", source="gui", source_file=line_path,
        color="#ff8800",
    ))
    p.custom_parts.append(CustomPart(
        key="drawn_surface", label="A surface", source="gui", source_file=surface_path,
        color="#00aaff",
    ))
    return p


def test_a_drawn_line_renders_as_an_edges_only_section(project_with_line_and_surface):
    with solid_model.session():
        result = tessellation.tessellate(project_with_line_and_surface)

    sections = sections_of(result, "drawn_line")
    assert len(sections) == 1
    section = sections[0]
    assert section.color == "#ff8800"
    assert section.indices == []
    assert section.edges, "a line has nothing to triangulate, but it must still draw"
    assert len(section.edges) % 6 == 0


def test_a_drawn_surface_renders_as_a_visible_flat_section(project_with_line_and_surface):
    with solid_model.session():
        result = tessellation.tessellate(project_with_line_and_surface)

    sections = sections_of(result, "drawn_surface")
    assert len(sections) == 1
    section = sections[0]
    assert section.color == "#00aaff"
    assert section.indices and len(section.indices) % 3 == 0
    assert max(section.indices) < len(section.positions) // 3

    # 6 x 6 square, visible from both sides -- every OCC triangle is emitted with both
    # windings, since a bare surface (unlike a solid) has no "outward" to pick.
    xs, zs = section.positions[0::3], section.positions[1::3]
    assert max(xs) - min(xs) == pytest.approx(6.0, rel=1e-6)
    assert max(zs) - min(zs) == pytest.approx(6.0, rel=1e-6)


def test_every_part_key_is_drawable_including_overlays(project_with_line_and_surface):
    with solid_model.session():
        result = tessellation.tessellate(project_with_line_and_surface)

    assert {s.key for s in result.sections} == set(project_with_line_and_surface.part_keys())
