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

from core import loads as translate
from core.schemas import Project
from core.seed import seed_project


# Narrower than the model (z 0..25) and across its section plane (z 12.5).
SURFACE = {"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
           "x0": 4.0, "x1": 16.0, "z0": 10.0, "z1": 15.0, "thickness": 0.3,
           "components": [0.0, -25.0, 0.0]}
OFF_CUT = SURFACE | {"id": "surfaceload_2", "name": "SurfaceLoad_2",
                     "z0": 2.0, "z1": 6.0}
LINE = {"id": "lineload_1", "name": "LineLoad_1", "kind": "line",
        "x0": 4.0, "x1": 16.0, "y": 0.0, "components": [0.0, -25.0]}
POINT = {"id": "pointload_1", "name": "PointLoad_1", "kind": "point",
         "x": 10.0, "y": 0.0, "components": [0.0, -30.0]}
BURIED = {"id": "lineload_2", "name": "LineLoad_2", "kind": "line",
          "x0": 4.0, "x1": 16.0, "y": -5.0, "components": [0.0, -25.0]}


def project_with(loads: list[dict], dimension: int = 3) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
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
    assert line.y == project.domain.y_top


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

    assert (surface.z0, surface.z1) == (project.domain.z0, project.domain.z1)
    assert (surface.x0, surface.x1) == (LINE["x0"], LINE["x1"])
    assert surface.components == (0.0, -25.0, 0.0)


# ── The round trip ──────────────────────────────────────────────────────────

def test_a_round_trip_keeps_the_original_footprint():
    """The reason both records are kept: z = 10..15 must not become the whole model."""
    project = project_with([SURFACE])

    down = project_with([l.model_dump() for l in translate.translate(project, 2)],
                        dimension=2)
    up = translate.translate(down, dimension=3)

    surface = next(l for l in up if l.id == "surfaceload_1")
    assert (surface.z0, surface.z1) == (SURFACE["z0"], SURFACE["z1"])


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
    assert surface.components == (0.0, -40.0, 0.0)
    assert (surface.z0, surface.z1) == (SURFACE["z0"], SURFACE["z1"]), "footprint kept"


# ── The loads with no counterpart ───────────────────────────────────────────

def test_a_point_load_gets_no_counterpart():
    """kN is not kN/m2 and there is no 3D point-load kind; it stays as it is and is
    built at the section plane instead."""
    project = project_with([POINT], dimension=2)

    translated = translate.translate(project, dimension=3)

    assert kinds(translated) == ["point"]


def test_a_line_load_below_the_ground_surface_gets_no_counterpart():
    """A surface load has no z of its own -- it sits on `domain.y_top`. Lifting a
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


# ── Repeated switches (plan Task 1.6) ───────────────────────────────────────

def switched(project: Project, dimension: int, **extra) -> Project:
    """`project` after a mode switch, the way the route does it."""
    loads = [l.model_dump() for l in translate.translate(project, dimension)]
    payload = project.model_dump() | {"dimension": dimension, "loads": loads}
    payload.setdefault("section_offset", None)
    payload.update(extra)
    return Project.model_validate(payload)


def test_a_point_load_survives_a_round_trip_unchanged():
    project = project_with([POINT, BURIED], dimension=2)

    back = switched(switched(project, 3), 2)

    assert [l.model_dump() for l in back.loads] == [l.model_dump() for l in project.loads]


def test_a_pair_stays_one_pair_over_many_switches():
    """Each switch refreshes the partner it already has; none of them makes another."""
    project = project_with([LINE], dimension=2)
    first = switched(project, 3)
    pair = [(l.id, l.kind, l.derived_from) for l in first.loads]

    later = first
    for dimension in (2, 3, 2, 3):
        later = switched(later, dimension)

    assert [(l.id, l.kind, l.derived_from) for l in later.loads] == pair
    assert pair == [("lineload_1", "line", None),
                    ("lineload_1_3d", "surface", "lineload_1")]


def test_a_pair_made_in_3d_stays_one_pair_too():
    later = project_with([SURFACE])
    for dimension in (2, 3, 2):
        later = switched(later, dimension)

    assert [(l.id, l.derived_from) for l in later.loads] == [
        ("surfaceload_1", None), ("surfaceload_1_2d", "surfaceload_1")]


# ── A footprint that misses the section plane ───────────────────────────────
# Plane strain is the model *at the cut*. A pad at z = 2..6 with the cut at z = 12.5
# does not load the section at all, and translating it into one put a load in the 2D
# model -- and the 2D deck -- that is nowhere near it.

def test_a_surface_load_clear_of_the_cut_is_not_in_the_section():
    project = switched(project_with([SURFACE, OFF_CUT]), 2)

    built = {l.derived_from for l in project.loads_for(2)}
    assert built == {"surfaceload_1"}


def test_the_switch_says_the_load_is_clear_of_the_cut():
    notes: list[str] = []
    translate.translate(project_with([OFF_CUT]), 2, notes)

    assert any("SurfaceLoad_2" in note and "section plane" in note
               and "12.5" in note for note in notes), notes


def test_the_record_is_kept_so_moving_the_cut_onto_it_brings_it_back():
    project = switched(project_with([OFF_CUT]), 2, section_offset=4.0)

    assert [l.derived_from for l in project.loads_for(2)] == ["surfaceload_2"]


def test_a_footprint_narrowed_off_the_cut_in_3d_leaves_the_section():
    """The line half was authored in 2D; the user then moved its pad in 3D."""
    in_3d = switched(project_with([LINE], dimension=2), 3)
    payload = in_3d.model_dump()
    for load in payload["loads"]:
        if load["kind"] == "surface":
            load["z0"], load["z1"] = 20.0, 25.0
    back = switched(Project.model_validate(payload), 2)

    assert back.loads_for(2) == []


def test_a_footprint_touching_the_cut_is_in_the_section():
    edge = SURFACE | {"z0": 12.5, "z1": 20.0}
    project = switched(project_with([edge]), 2)

    assert [l.kind for l in project.loads_for(2)] == ["line"]


def test_the_section_deck_leaves_out_a_load_clear_of_the_cut():
    """End to end through the route and the exporter's own load selection."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        client.patch("/api/project/structures", json={"loads": [SURFACE, OFF_CUT]})
        down = client.patch("/api/project/dimension", json={"dimension": 2})
        assert down.status_code == 200, down.text
        assert any("SurfaceLoad_2" in n for n in down.json()["notes"])
        project = Project.model_validate(down.json()["project"])
        client.post("/api/project/reset")

    assert [l.id for l in project.loads_for(2)] == ["surfaceload_1_2d"]


# ── Through the API, which is where the mode switch actually happens ────────

def test_the_dimension_switch_translates_the_loads_end_to_end():
    """The whole point: a surface load drawn in 3D is a line load after the switch."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        client.patch("/api/project/structures", json={"loads": [SURFACE]})

        down = client.patch("/api/project/dimension",
                            json={"dimension": 2})
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
        assert (surface["z0"], surface["z1"]) == (SURFACE["z0"], SURFACE["z1"])


def test_the_switch_says_what_became_of_each_load():
    """A record the user did not author appearing in the tree needs an explanation."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        client.post("/api/project/reset")
        client.patch("/api/project/structures", json={"loads": [SURFACE, POINT]})
        notes = client.patch("/api/project/dimension",
                             json={"dimension": 2}).json()["notes"]

    assert any("SurfaceLoad_1" in note and "line load" in note for note in notes), notes


def test_a_translated_pair_is_drawn_once_in_the_solid_model():
    """The failure this guards against is a load applied twice: both halves of a pair
    imprinting the same boundary, and both symbols drawn on top of each other."""
    from core import build, tessellate

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
# reported. The default names carry their kind (frontend/js/loads.js), so the translation
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
# `domain.y_top`, which is only the top of the *borehole* block -- so once a drawn
# embankment could stand above it (see `Project.extent`), a load on that embankment sat
# above the only elevation a surface load was allowed to have, and stopped translating.
# The ground is the top of the model now, and the two ends agree on where that is.

EMBANKMENT = {"key": "drawn_1", "label": "Embankment", "source": "gui",
              "source_file": "x.brep", "color": "#cccccc",
              "bbox": [0.0, 0.0, 0.0, 25.0, 4.0, 25.0]}


def raised(loads: list[dict], dimension: int = 2) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
    payload["custom_parts"] = [EMBANKMENT]
    payload["loads"] = loads
    return Project.model_validate(payload)


def test_the_ground_is_the_top_of_the_model_not_of_the_borehole_block():
    assert raised([]).ground_y() == 4.0
    assert Project.model_validate(
        seed_project(simple=True).model_dump()).ground_y() == 0.0


def test_a_line_load_on_a_drawn_embankment_translates():
    """The regression: this is exactly the load `Project.extent` newly allows."""
    project = raised([LINE | {"y": 4.0}])

    assert kinds(translate.translate(project, 3)) == ["line", "surface"]


def test_a_line_load_at_the_borehole_top_still_translates_when_nothing_is_drawn():
    project = project_with([LINE], dimension=2)

    assert kinds(translate.translate(project, 3)) == ["line", "surface"]


def test_a_line_load_buried_in_the_embankment_still_gets_no_counterpart():
    """The earlier rule is intact: a load part-way up is not on a ground surface."""
    project = raised([LINE | {"y": 2.0}])

    assert kinds(translate.translate(project, 3)) == ["line"]


def test_the_line_counterpart_comes_back_at_the_top_of_the_model():
    project = raised([{"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
                       "x0": 4.0, "x1": 16.0, "z0": 5.0, "z1": 10.0, "thickness": 0.3,
                       "components": [0.0, -25.0, 0.0]}], dimension=3)

    line = next(l for l in translate.translate(project, 2) if l.kind == "line")

    assert line.y == 4.0


def test_the_surface_load_is_drawn_on_top_of_the_drawn_layer():
    """Not buried at z = 0 inside the embankment, where nothing would be visible."""
    from core import build

    project = raised([{"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
                       "x0": 4.0, "x1": 16.0, "z0": 5.0, "z1": 10.0, "thickness": 0.3,
                       "components": [0.0, -25.0, 0.0]}], dimension=3)

    with build.session():
        build.build_geometry(project)
        tools = build._load_footprint_tools(project, 3)
        boxes = [gmsh.model.occ.getBoundingBox(dim, tag) for dim, tag in tools]

    assert boxes and all(box[1] == pytest.approx(4.0) for box in boxes), boxes


# ── The ground is not exact, and a load is not placed by guessing ───────────
#
# gmsh pads every bounding box it reports by 1e-7, so a box drawn 0..4 comes back as
# reaching 4.0000001. `ground_y` is built from those boxes, while a load the user
# places on the visible top of that embankment is at 4.0 -- and `4.0 == 4.0000001` is
# false, so the load silently stopped translating. Two fixes, because a tolerance alone
# would still leave the surface load imprinted 1e-7 above the face it belongs on:
# compare with a tolerance, and carry the elevation on the record instead of rederiving
# it. `SurfaceLoad.y` left None means "the top of the model", so older projects are
# unchanged.

PADDED = {"key": "drawn_1", "label": "Embankment", "source": "gui",
          "source_file": "x.brep", "color": "#cccccc",
          "bbox": [-1e-07, -1e-07, -1e-07, 20.0000001, 4.0000001, 20.0000001]}


def padded(loads: list[dict], dimension: int = 2) -> Project:
    payload = seed_project(simple=True).model_dump() | {"dimension": dimension}
    payload["custom_parts"] = [PADDED]
    payload["loads"] = loads
    return Project.model_validate(payload)


def test_a_load_on_the_visible_top_of_a_drawn_layer_translates():
    """The bug as reported: the user clicks the surface and gets 4.0, not 4.0000001."""
    project = padded([LINE | {"y": 4.0}])

    assert kinds(translate.translate(project, 3)) == ["line", "surface"]


def test_the_surface_load_carries_the_elevation_it_was_translated_from():
    """Not the padded ground: the imprint has to land on the face, not above it."""
    project = padded([LINE | {"y": 4.0}])

    surface = next(l for l in translate.translate(project, 3) if l.kind == "surface")

    assert surface.y == 4.0


def test_the_pad_is_placed_on_the_face_not_on_the_padded_ground():
    """What `build` and `kratos` feed to gmsh when they place the pad.

    Asserted on the elevation itself rather than on the built entity: gmsh reports
    every bounding box padded by 1e-7, so the geometry cannot tell 4.0 from 4.0000001
    -- which is the whole difference between imprinting the face and floating above it.
    """
    project = padded([LINE | {"y": 4.0}], dimension=2)
    both = [l.model_dump() for l in translate.translate(project, 3)]
    solid = padded(both, dimension=3)

    surface = next(l for l in solid.loads if l.kind == "surface")
    assert solid.elevation_of(surface) == 4.0
    assert solid.ground_y() != 4.0, "the padded ground is what this must not use"


def test_the_elevation_survives_the_round_trip():
    project = padded([LINE | {"y": 4.0}])
    both = [l.model_dump() for l in translate.translate(project, 3)]

    back = translate.translate(padded(both, dimension=3), 2)

    line = next(l for l in back if l.kind == "line")
    assert line.y == 4.0


def test_a_surface_load_with_no_elevation_still_means_the_top_of_the_model():
    """Every project saved before `SurfaceLoad.y` existed reads exactly as it used to."""
    project = padded([{"id": "surfaceload_1", "name": "SurfaceLoad_1", "kind": "surface",
                       "x0": 4.0, "x1": 16.0, "z0": 5.0, "z1": 10.0, "thickness": 0.3,
                       "components": [0.0, -25.0, 0.0]}], dimension=3)

    assert project.loads[0].y is None
    assert project.elevation_of(project.loads[0]) == project.ground_y()


def test_a_load_buried_in_the_embankment_still_gets_no_counterpart():
    project = padded([LINE | {"y": 2.0}])

    assert kinds(translate.translate(project, 3)) == ["line"]
