"""2D structures carried into the solid model at the section plane.

A sheet pile, an anchor, a 2D load and an interface are all drawn in the plane-strain
section, and every one of them used to vanish the moment the model switched to 3D --
`_embed_3d_structures` logged them as "built in a 2D section only" and built nothing.
They are built now, at `section_offset`, so the solid model shows what the section was
drawn with instead of an empty box.

Placed *at the cut* rather than smeared across the domain width: a plane-strain record
says where a structure is in the section, not how far it runs out of plane, so the
build puts one of it on the plane it was drawn on. A sheet pile is the exception that
needs a width at all -- a shell has to have somewhere to be -- and takes it from the
profile's own out-of-plane `spacing`.
"""

import gmsh
import pytest

from core.geometry import solid_model
from core.model.schemas import Project
from core.model.templates import seed_project


PILE_X = 10.0
PILE_TOP, PILE_TOE = 0.0, -8.0
OFFSET = 12.5          # the seed domain's mid-plane, where the section defaults to
SPACING = 2.0


def project_with_2d_structures(dimension: int, simple: bool = True) -> Project:
    """The seed model plus one of every 2D-native structure, in `dimension`.

    `simple=False` for anything that looks at a load: `Project.part_keys` lists the
    loads only in the full model, so a simple-example project draws none of them in
    either dimension and would prove nothing here.
    """
    payload = seed_project(simple=simple).model_dump() | {"dimension": dimension}
    payload["section_offset"] = OFFSET
    payload["beam_sections"] = [{
        "id": "bs1", "name": "AZ18", "E": 2.1e8, "nu": 0.3,
        "area": 0.015, "inertia": 1e-4, "density": 7850, "spacing": SPACING,
    }]
    payload["beams"] = [{
        "id": "pile1", "name": "Sheet pile 1", "kind": "beam", "section": "bs1",
        "points": [[PILE_X, PILE_TOP], [PILE_X, PILE_TOE]],
    }]
    payload["anchor_sections"] = [{
        "id": "as1", "name": "Strand", "E": 2.0e8, "area": 0.0015, "density": 7850,
    }]
    payload["anchors"] = [{
        "id": "anchor1", "name": "Anchor 1", "kind": "anchor", "section": "as1",
        "head": [PILE_X, -2.0], "tail": [PILE_X - 6.0, -6.0],
    }]
    payload["loads"] = [{
        "id": "load1", "name": "LineLoad_1", "kind": "line",
        "x0": 2.0, "x1": 8.0, "y": 0.0, "components": [0.0, -10.0],
    }]
    return Project.model_validate(payload)


@pytest.fixture(scope="module")
def solid():
    project = project_with_2d_structures(dimension=3)
    with solid_model.session():
        yield project, solid_model.build_geometry(project)


@pytest.fixture(scope="module")
def section():
    project = project_with_2d_structures(dimension=2)
    with solid_model.session():
        yield project, solid_model.build_geometry(project)


# ── The sheet pile ──────────────────────────────────────────────────────────

def test_a_sheet_pile_is_built_in_the_solid_model(solid):
    """The regression this file exists for: no faces at all before the change."""
    _, result = solid
    assert result.faces.get("pile1"), "the sheet pile contributed no geometry in 3D"


def test_the_sheet_pile_is_no_longer_logged_as_excluded(solid):
    _, result = solid
    excluded = [line for line in result.log
                if "pile1" in line and "not part of this 3D model" in line]
    assert not excluded, excluded


def test_the_sheet_pile_is_swept_across_the_section_plane(solid):
    """Centred on the cut, one profile spacing wide, and nowhere near the z extremes."""
    _, result = solid
    with solid_model.session():
        boxes = [gmsh.model.occ.getBoundingBox(2, tag) for tag in result.faces["pile1"]]
    z0, z1 = min(b[2] for b in boxes), max(b[5] for b in boxes)
    assert z0 == pytest.approx(OFFSET - SPACING / 2, abs=1e-6)
    assert z1 == pytest.approx(OFFSET + SPACING / 2, abs=1e-6)


def test_the_sheet_pile_keeps_its_in_plane_position_and_depth(solid):
    _, result = solid
    with solid_model.session():
        boxes = [gmsh.model.occ.getBoundingBox(2, tag) for tag in result.faces["pile1"]]
    assert min(b[0] for b in boxes) == pytest.approx(PILE_X, abs=1e-6)
    assert max(b[3] for b in boxes) == pytest.approx(PILE_X, abs=1e-6)
    assert min(b[1] for b in boxes) == pytest.approx(PILE_TOE, abs=1e-6)


# ── The anchor ──────────────────────────────────────────────────────────────

def test_a_plane_anchor_is_built_in_the_solid_model(solid):
    _, result = solid
    assert result.ties.get("anchor1"), "the 2D anchor contributed no tie in 3D"


def test_the_plane_anchor_lies_on_the_section_plane(solid):
    """One anchor at the cut -- not a row smeared over the out-of-plane spacing."""
    _, result = solid
    with solid_model.session():
        boxes = [gmsh.model.occ.getBoundingBox(1, tag) for tag in result.ties["anchor1"]]
    for box in boxes:
        assert box[2] == pytest.approx(OFFSET, abs=1e-6)
        assert box[5] == pytest.approx(OFFSET, abs=1e-6)


def test_the_plane_anchor_gets_a_tail_node(solid):
    _, result = solid
    assert "anchor1" in result.tie_nodes


# ── The 2D load ─────────────────────────────────────────────────────────────

def test_a_two_dimensional_load_is_imprinted_in_the_solid_model(solid):
    """The load's edges have to be mesh edges, or the exporter can only quantise it."""
    project, _ = solid
    with solid_model.session():
        solid_model.build_geometry(project)
        edges = [gmsh.model.occ.getBoundingBox(1, tag)
                 for _, tag in gmsh.model.getEntities(1)]
    on_plane_at_top = [b for b in edges
                       if abs(b[2] - OFFSET) < 1e-6 and abs(b[5] - OFFSET) < 1e-6
                       and abs(b[1] - project.domain.y_top) < 1e-6]
    assert on_plane_at_top, "no imprinted edge on the section plane at the surface"


# ── Nothing about the section changed ───────────────────────────────────────

def test_the_section_still_builds_its_structures(section):
    """The 2D path is untouched: the same records still build the same way."""
    _, result = section
    assert result.curves.get("pile1")
    assert result.ties.get("anchor1")


# ── What the viewport is handed ─────────────────────────────────────────────
#
# Building the geometry is only half of it: the bug reported was that the structures
# "do not show" in 3D, and what shows is whatever `tessellation` puts in a section. These
# close the loop from the build to the viewport.

@pytest.fixture(scope="module")
def drawn():
    from core.geometry import tessellation
    project = project_with_2d_structures(dimension=3, simple=False)
    with solid_model.session():
        yield tessellation.tessellate(project)


def sections_of(display, key):
    return [s for s in display.sections if s.key == key]


def drawable(display, key) -> bool:
    """Something the viewport can actually put on screen under `key`.

    A swept wall is triangles (`positions`); an anchor is a line, which
    `_overlay_section` emits as `edges` alone. Either counts as drawn.
    """
    return any(s.positions or s.edges for s in sections_of(display, key))


def test_the_swept_sheet_pile_is_drawn_in_the_solid_model(drawn):
    assert drawable(drawn, "pile1"), "the viewport is handed nothing for the sheet pile"


def test_the_plane_anchor_is_drawn_in_the_solid_model(drawn):
    assert drawable(drawn, "anchor1")


def test_the_two_dimensional_load_symbol_is_drawn_in_the_solid_model(drawn):
    """The red arrows in the section have to survive the switch to 3D too."""
    assert drawable(drawn, "load1")
