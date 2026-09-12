"""A load, translated between the section and the solid model.

A surface load and a line load are the same load seen from two dimensions: plane strain
reduces a pressure over a footprint to a pressure per metre run in the cut. Switching
mode translates one into the other so the load does not disappear on the way.

Both records are kept. A line load carries no `y` at all -- deliberately, it is
dimension-native -- so replacing the surface record outright would widen its footprint
to the whole model on the way back. The counterpart is stored instead and refreshed
from whichever dimension the user was last working in, which is the one they edited.
"""

import gmsh
import pytest

from app import loads as translate
from app.schemas import Project
from app.seed import seed_project


SURFACE = {"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
           "x0": 4.0, "x1": 16.0, "y0": 5.0, "y1": 10.0, "thickness": 0.3,
           "components": [0.0, 0.0, -25.0]}
LINE = {"id": "lineload_1", "name": "LineLoad_1", "kind": "line",
        "x0": 4.0, "x1": 16.0, "z": 0.0, "components": [0.0, -25.0]}
POINT = {"id": "pointload_1", "name": "PointLoad_1", "kind": "point",
         "x": 10.0, "z": 0.0, "components": [0.0, -30.0]}
BURIED = {"id": "lineload_2", "name": "LineLoad_2", "kind": "line",
          "x0": 4.0, "x1": 16.0, "z": -5.0, "components": [0.0, -25.0]}


def project_with(loads: list[dict], dimension: int = 3) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
    payload["section_plane"] = "xz"
    payload["loads"] = loads
    return Project.model_validate(payload)


def by_id(project: Project, key: str):
    return next(load for load in project.loads if load.id == key)


def kinds(loads) -> list[str]:
    return sorted(load.kind for load in loads)


# ── Down into the section ───────────────────────────────────────────────────

def test_a_surface_load_gains_a_line_counterpart_in_2d():
    project = project_with([SURFACE])

    translated = translate.translate(project, dimension=2)

    assert kinds(translated) == ["line", "surface"]


def test_the_line_counterpart_keeps_the_footprints_x_extent_and_pressure():
    """kN/m2 over a footprint is kN/m per metre run: the number carries unchanged."""
    project = project_with([SURFACE])

    line = next(l for l in translate.translate(project, dimension=2) if l.kind == "line")

    assert (line.x0, line.x1) == (SURFACE["x0"], SURFACE["x1"])
    assert line.components == (0.0, -25.0)
    assert line.z == project.domain.z_top


def test_the_line_counterpart_points_back_at_the_surface_load():
    project = project_with([SURFACE])

    line = next(l for l in translate.translate(project, dimension=2) if l.kind == "line")

    assert line.derived_from == "surfaceload_1"


def test_the_surface_record_survives_the_switch():
    project = project_with([SURFACE])

    translated = translate.translate(project, dimension=2)

    assert any(l.id == "surfaceload_1" for l in translated)


# ── Up into the solid model ─────────────────────────────────────────────────

def test_a_line_load_gains_a_surface_counterpart_in_3d():
    project = project_with([LINE], dimension=2)

    translated = translate.translate(project, dimension=3)

    assert kinds(translated) == ["line", "surface"]


def test_a_new_surface_counterpart_spans_the_full_out_of_plane_width():
    """Plane strain is uniform out of plane, so a first translation runs the whole
    model. Nothing better is knowable: the line record carries no y."""
    project = project_with([LINE], dimension=2)

    surface = next(l for l in translate.translate(project, dimension=3)
                   if l.kind == "surface")

    assert (surface.y0, surface.y1) == (project.domain.y0, project.domain.y1)
    assert (surface.x0, surface.x1) == (LINE["x0"], LINE["x1"])
    assert surface.components == (0.0, 0.0, -25.0)


# ── The round trip ──────────────────────────────────────────────────────────

def test_a_round_trip_keeps_the_original_footprint():
    """The reason both records are kept: y = 5..10 must not become the whole model."""
    project = project_with([SURFACE])

    down = project_with([l.model_dump() for l in translate.translate(project, 2)],
                        dimension=2)
    up = translate.translate(down, dimension=3)

    surface = next(l for l in up if l.id == "surfaceload_1")
    assert (surface.y0, surface.y1) == (SURFACE["y0"], SURFACE["y1"])


def test_an_edit_made_in_the_section_reaches_the_solid_model():
    """The counterpart is refreshed, not merely kept: what the user last edited wins."""
    project = project_with([SURFACE])
    down = [l.model_dump() for l in translate.translate(project, 2)]
    for load in down:
        if load["kind"] == "line":
            load["x1"] = 12.0
            load["components"] = [0.0, -40.0]

    up = translate.translate(project_with(down, dimension=2), dimension=3)

    surface = next(l for l in up if l.id == "surfaceload_1")
    assert surface.x1 == 12.0
    assert surface.components == (0.0, 0.0, -40.0)
    assert (surface.y0, surface.y1) == (SURFACE["y0"], SURFACE["y1"]), "footprint kept"


# ── The loads with no counterpart ───────────────────────────────────────────

def test_a_point_load_gets_no_counterpart():
    """kN is not kN/m2 and there is no 3D point-load kind; it stays as it is and is
    built at the section plane instead."""
    project = project_with([POINT], dimension=2)

    translated = translate.translate(project, dimension=3)

    assert kinds(translated) == ["point"]


def test_a_line_load_below_the_ground_surface_gets_no_counterpart():
    """A surface load has no z of its own -- it sits on `domain.z_top`. Lifting a
    buried load up to it would relocate the model, so it is carried instead."""
    project = project_with([BURIED], dimension=2)

    translated = translate.translate(project, dimension=3)

    assert kinds(translated) == ["line"]


# ── What each dimension actually builds ─────────────────────────────────────

def test_a_translated_pair_is_built_once_in_each_dimension():
    """Both records exist; only one of them is the model's, or the load is doubled."""
    project = project_with([l.model_dump() for l in
                            translate.translate(project_with([SURFACE]), 2)])

    assert [l.id for l in project.loads_for(3)] == ["surfaceload_1"]
    assert [l.kind for l in project.loads_for(2)] == ["line"]


def test_a_load_with_no_counterpart_is_built_in_both_dimensions():
    project = project_with([POINT, BURIED], dimension=3)

    assert kinds(project.loads_for(3)) == ["line", "point"]
    assert kinds(project.loads_for(2)) == ["line", "point"]


# ── Through the API, which is where the mode switch actually happens ────────

def test_the_dimension_switch_translates_the_loads_end_to_end():
    """The whole point: a surface load drawn in 3D is a line load after the switch."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        client.patch("/api/project/structures", json={"loads": [SURFACE]})

        down = client.patch("/api/project/dimension",
                            json={"dimension": 2, "section_plane": "xz"})
        assert down.status_code == 200, down.text
        after = down.json()["project"]["loads"]
        line = next(l for l in after if l["kind"] == "line")
        assert (line["x0"], line["x1"]) == (SURFACE["x0"], SURFACE["x1"])
        assert line["components"] == [0.0, -25.0]
        assert any(l["id"] == "surfaceload_1" for l in after), "the 3D record is kept"

        up = client.patch("/api/project/dimension", json={"dimension": 3})
        assert up.status_code == 200, up.text
        surface = next(l for l in up.json()["project"]["loads"]
                       if l["id"] == "surfaceload_1")
        assert (surface["y0"], surface["y1"]) == (SURFACE["y0"], SURFACE["y1"])


def test_the_switch_says_what_became_of_each_load():
    """A record the user did not author appearing in the tree needs an explanation."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        client.patch("/api/project/structures", json={"loads": [SURFACE, POINT]})
        notes = client.patch("/api/project/dimension",
                             json={"dimension": 2, "section_plane": "xz"}).json()["notes"]

    assert any("SurfaceLoad_1" in note and "line load" in note for note in notes), notes


def test_a_translated_pair_is_drawn_once_in_the_solid_model():
    """The failure this guards against is a load applied twice: both halves of a pair
    imprinting the same boundary, and both symbols drawn on top of each other."""
    from app import build, tessellate

    paired = [l.model_dump() for l in
              translate.translate(project_with([SURFACE], dimension=3), 2)]
    payload = seed_project(simple=False).model_dump() | {"dimension": 3}
    payload["loads"] = paired
    project = Project.model_validate(payload)

    with build.session():
        display = tessellate.tessellate(project)

    drawn = {s.key for s in display.sections} & {"surfaceload_1", "surfaceload_1_2d"}
    assert drawn == {"surfaceload_1"}, drawn


# ── What the translated half is called ──────────────────────────────────────
#
# The explorer lists a load by name and nothing else, so a surface load called
# "LineLoad_1" reads as a load that never converted -- which is exactly how the bug was
# reported. The default names carry their kind (live/js/loads.js), so the translation
# has to carry it too.

def test_the_surface_counterpart_is_named_for_its_own_kind():
    project = project_with([LINE], dimension=2)

    surface = next(l for l in translate.translate(project, 3) if l.kind == "surface")

    assert surface.name == "SurfaceLoad_1"


def test_the_line_counterpart_is_named_for_its_own_kind():
    project = project_with([SURFACE])

    line = next(l for l in translate.translate(project, 2) if l.kind == "line")

    assert line.name == "LineLoad_1"


def test_a_name_the_user_chose_is_carried_across_untouched():
    """Only the default names encode a kind. "Crane pad" is the user's word for the
    load itself, and renaming it on a mode switch would lose what they wrote."""
    project = project_with([LINE | {"name": "Crane pad"}], dimension=2)

    surface = next(l for l in translate.translate(project, 3) if l.kind == "surface")

    assert surface.name == "Crane pad"


def test_a_renamed_counterpart_keeps_its_own_name_on_a_later_switch():
    project = project_with([LINE], dimension=2)
    both = [l.model_dump() for l in translate.translate(project, 3)]
    for load in both:
        if load["kind"] == "surface":
            load["name"] = "Pad by the crane"

    again = translate.translate(project_with(both, dimension=2), 3)

    surface = next(l for l in again if l.kind == "surface")
    assert surface.name == "Pad by the crane"


def test_the_default_name_is_renumbered_to_match_its_source():
    project = project_with([LINE | {"id": "lineload_7", "name": "LineLoad_7"}],
                           dimension=2)

    surface = next(l for l in translate.translate(project, 3) if l.kind == "surface")

    assert surface.name == "SurfaceLoad_7"


# ── The ground a surface load sits on ───────────────────────────────────────
#
# A `SurfaceLoad` carries no z: it lies on the top of the model. That used to be
# `domain.z_top`, which is only the top of the *borehole* block -- so once a drawn
# embankment could stand above it (see `Project.extent`), a load on that embankment sat
# above the only elevation a surface load was allowed to have, and stopped translating.
# The ground is the top of the model now, and the two ends agree on where that is.

EMBANKMENT = {"key": "drawn_1", "label": "Embankment", "source": "gui",
              "source_file": "x.brep", "color": "#cccccc",
              "bbox": [0.0, 0.0, 0.0, 25.0, 25.0, 4.0]}


def raised(loads: list[dict], dimension: int = 2) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
    payload["section_plane"] = "xz"
    payload["custom_parts"] = [EMBANKMENT]
    payload["loads"] = loads
    return Project.model_validate(payload)


def test_the_ground_is_the_top_of_the_model_not_of_the_borehole_block():
    assert raised([]).ground_z() == 4.0
    assert Project.model_validate(
        seed_project(simple=True).model_dump()).ground_z() == 0.0


def test_a_line_load_on_a_drawn_embankment_translates():
    """The regression: this is exactly the load `Project.extent` newly allows."""
    project = raised([LINE | {"z": 4.0}])

    assert kinds(translate.translate(project, 3)) == ["line", "surface"]


def test_a_line_load_at_the_borehole_top_still_translates_when_nothing_is_drawn():
    project = project_with([LINE], dimension=2)

    assert kinds(translate.translate(project, 3)) == ["line", "surface"]


def test_a_line_load_buried_in_the_embankment_still_gets_no_counterpart():
    """The earlier rule is intact: a load part-way up is not on a ground surface."""
    project = raised([LINE | {"z": 2.0}])

    assert kinds(translate.translate(project, 3)) == ["line"]


def test_the_line_counterpart_comes_back_at_the_top_of_the_model():
    project = raised([{"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
                       "x0": 4.0, "x1": 16.0, "y0": 5.0, "y1": 10.0, "thickness": 0.3,
                       "components": [0.0, 0.0, -25.0]}], dimension=3)

    line = next(l for l in translate.translate(project, 2) if l.kind == "line")

    assert line.z == 4.0


def test_the_surface_load_is_drawn_on_top_of_the_drawn_layer():
    """Not buried at z = 0 inside the embankment, where nothing would be visible."""
    from app import build

    project = raised([{"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
                       "x0": 4.0, "x1": 16.0, "y0": 5.0, "y1": 10.0, "thickness": 0.3,
                       "components": [0.0, 0.0, -25.0]}], dimension=3)

    with build.session():
        build.build_geometry(project)
        tools = build._load_footprint_tools(project, 3)
        boxes = [gmsh.model.occ.getBoundingBox(dim, tag) for dim, tag in tools]

    assert boxes and all(box[2] == pytest.approx(4.0) for box in boxes), boxes


# ── The ground is not exact, and a load is not placed by guessing ───────────
#
# gmsh pads every bounding box it reports by 1e-7, so a box drawn 0..4 comes back as
# reaching 4.0000001. `ground_z` is built from those boxes, while a load the user
# places on the visible top of that embankment is at 4.0 -- and `4.0 == 4.0000001` is
# false, so the load silently stopped translating. Two fixes, because a tolerance alone
# would still leave the surface load imprinted 1e-7 above the face it belongs on:
# compare with a tolerance, and carry the elevation on the record instead of rederiving
# it. `SurfaceLoad.z` left None means "the top of the model", so older projects are
# unchanged.

PADDED = {"key": "drawn_1", "label": "Embankment", "source": "gui",
          "source_file": "x.brep", "color": "#cccccc",
          "bbox": [-1e-07, -1e-07, -1e-07, 20.0000001, 20.0000001, 4.0000001]}


def padded(loads: list[dict], dimension: int = 2) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
    payload["section_plane"] = "xz"
    payload["custom_parts"] = [PADDED]
    payload["loads"] = loads
    return Project.model_validate(payload)


def test_a_load_on_the_visible_top_of_a_drawn_layer_translates():
    """The bug as reported: the user clicks the surface and gets 4.0, not 4.0000001."""
    project = padded([LINE | {"z": 4.0}])

    assert kinds(translate.translate(project, 3)) == ["line", "surface"]


def test_the_surface_load_carries_the_elevation_it_was_translated_from():
    """Not the padded ground: the imprint has to land on the face, not above it."""
    project = padded([LINE | {"z": 4.0}])

    surface = next(l for l in translate.translate(project, 3) if l.kind == "surface")

    assert surface.z == 4.0


def test_the_pad_is_placed_on_the_face_not_on_the_padded_ground():
    """What `build` and `kratos` feed to gmsh when they place the pad.

    Asserted on the elevation itself rather than on the built entity: gmsh reports
    every bounding box padded by 1e-7, so the geometry cannot tell 4.0 from 4.0000001
    -- which is the whole difference between imprinting the face and floating above it.
    """
    project = padded([LINE | {"z": 4.0}], dimension=2)
    both = [l.model_dump() for l in translate.translate(project, 3)]
    solid = padded(both, dimension=3)

    surface = next(l for l in solid.loads if l.kind == "surface")
    assert solid.elevation_of(surface) == 4.0
    assert solid.ground_z() != 4.0, "the padded ground is what this must not use"


def test_the_elevation_survives_the_round_trip():
    project = padded([LINE | {"z": 4.0}])
    both = [l.model_dump() for l in translate.translate(project, 3)]

    back = translate.translate(padded(both, dimension=3), 2)

    line = next(l for l in back if l.kind == "line")
    assert line.z == 4.0


def test_a_surface_load_with_no_elevation_still_means_the_top_of_the_model():
    """Every project saved before `SurfaceLoad.z` existed reads exactly as it used to."""
    project = padded([{"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
                       "x0": 4.0, "x1": 16.0, "y0": 5.0, "y1": 10.0, "thickness": 0.3,
                       "components": [0.0, 0.0, -25.0]}], dimension=3)

    assert project.loads[0].z is None
    assert project.elevation_of(project.loads[0]) == project.ground_z()


def test_a_load_buried_in_the_embankment_still_gets_no_counterpart():
    project = padded([LINE | {"z": 2.0}])

    assert kinds(translate.translate(project, 3)) == ["line"]
