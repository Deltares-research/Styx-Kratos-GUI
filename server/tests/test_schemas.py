"""Contract tests for the project schema.

The schema is the single source of truth the frontend currently lacks: today geometry
lives in js/viewport.js while descriptions of that geometry live in js/data.js, and the
two disagree (see test_parity.py).
"""

import pytest
from pydantic import ValidationError

from app import schemas
from app.seed import seed_project


# ── Domain ──────────────────────────────────────────────────────────────────

def test_domain_reports_its_extents():
    d = schemas.Domain(x0=0, x1=50, z0=0, z1=40, y_top=0, y_bottom=-25)
    assert (d.dx, d.dy, d.dz) == (50.0, 25.0, 40.0)
    assert d.center == (25.0, -12.5, 20.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(x0=50, x1=0, z0=0, z1=40, y_top=0, y_bottom=-25),   # x reversed
        dict(x0=0, x1=50, z0=40, z1=0, y_top=0, y_bottom=-25),   # y reversed
        dict(x0=0, x1=50, z0=0, z1=40, y_top=-25, y_bottom=0),   # z reversed
        dict(x0=0, x1=0, z0=0, z1=40, y_top=0, y_bottom=-25),    # zero width
    ],
)
def test_domain_rejects_degenerate_extents(kwargs):
    with pytest.raises(ValidationError):
        schemas.Domain(**kwargs)


# ── Materials ───────────────────────────────────────────────────────────────

def test_material_colour_must_be_a_css_hex():
    ok = schemas.Material(id="m2", name="Sand, loose", model="Hardening Soil",
                          type="Drained", color="#c4a86a", g_unsat=18.0, g_sat=20.5,
                          E=25000, nu=0.28, c=0.5, phi=32.0, k=1.5)
    assert ok.color == "#c4a86a"

    with pytest.raises(ValidationError):
        ok.model_copy(update={"color": "chartreuse"}).model_validate(
            {**ok.model_dump(), "color": "chartreuse"}
        )


def test_material_allows_null_cohesion_and_friction_for_non_porous_rock():
    """js/data.js:325 has c=null, phi=null for bedrock; js/dialogs.js:411 renders it as em-dash."""
    m = schemas.Material(id="m6", name="Bedrock", model="Linear Elastic",
                         type="Non-porous", color="#8e8e8e", g_unsat=24.0, g_sat=24.0,
                         E=2.0e6, nu=0.20, c=None, phi=None, k=0.0)
    assert m.c is None and m.phi is None


# ── Soil layers ─────────────────────────────────────────────────────────────

def test_layer_stack_must_be_contiguous_per_borehole():
    """The invariant js/dialogs.js:320-331 maintains by hand: bots[i] == tops[i+1]."""
    good = [
        schemas.SoilLayer(id="L1", name="Soil_1", mat="m2",
                          tops={"bh1": 0.0}, bots={"bh1": -8.0}),
        schemas.SoilLayer(id="L2", name="Soil_2", mat="m4",
                          tops={"bh1": -8.0}, bots={"bh1": -25.0}),
    ]
    schemas.validate_layer_stack(good, ["bh1"])  # does not raise

    gap = [
        good[0],
        schemas.SoilLayer(id="L2", name="Soil_2", mat="m4",
                          tops={"bh1": -9.0}, bots={"bh1": -25.0}),
    ]
    with pytest.raises(ValueError, match="contiguous"):
        schemas.validate_layer_stack(gap, ["bh1"])


def test_layer_must_cover_every_borehole():
    layers = [schemas.SoilLayer(id="L1", name="Soil_1", mat="m2",
                               tops={"bh1": 0.0}, bots={"bh1": -25.0})]
    with pytest.raises(ValueError, match="bh2"):
        schemas.validate_layer_stack(layers, ["bh1", "bh2"])


def test_layer_rejects_inverted_thickness():
    with pytest.raises(ValidationError):
        schemas.SoilLayer(id="L1", name="Soil_1", mat="m2",
                          tops={"bh1": -8.0}, bots={"bh1": 0.0})


# ── Project-level cross references ──────────────────────────────────────────

def test_project_rejects_layer_pointing_at_unknown_material():
    p = seed_project()
    bad = p.model_dump()
    bad["layers"][0]["mat"] = "does_not_exist"
    with pytest.raises(ValidationError, match="does_not_exist"):
        schemas.Project.model_validate(bad)


def test_project_rejects_duplicate_ids():
    p = seed_project()
    bad = p.model_dump()
    bad["boreholes"].append(bad["boreholes"][0])
    with pytest.raises(ValidationError, match="duplicate"):
        schemas.Project.model_validate(bad)


def test_excavation_must_sit_inside_the_domain():
    p = seed_project(simple=False)
    bad = p.model_dump()
    bad["excavation"]["x1"] = 500.0
    with pytest.raises(ValidationError, match="domain"):
        schemas.Project.model_validate(bad)


# ── Load conditions ────────────────────────────────────────────────────────

def test_surface_load_is_a_named_first_class_condition():
    load = schemas.SurfaceLoad(
        id="load_north", name="North surcharge",
        x0=1.0, x1=10.0, z0=14.0, z1=26.0, thickness=0.25,
        components=(0.0, -20.0, 0.0), distribution="Uniform", active=True,
    )

    assert load.id == "load_north"
    assert load.components == (0.0, -20.0, 0.0)
    assert load.distribution == "Uniform"


def test_line_load_is_dimension_native_and_contains_no_hidden_z_values():
    load = schemas.LineLoad(
        id="load_strip", name="Strip surcharge", kind="line",
        x0=2.0, x1=9.0, y=0.0, thickness=0.15,
        components=(5.0, -20.0), active=True,
    )

    assert (load.x0, load.x1, load.y) == (2.0, 9.0, 0.0)
    assert load.components == (5.0, -20.0)
    assert not {"z", "z0", "z1"}.intersection(load.model_dump())


def test_point_load_accepts_an_explicit_2d_coordinate():
    load = schemas.PointLoad(
        id="load_crane", name="Crane reaction", kind="point",
        x=8.5, y=0.0, thickness=0.25,
        components=(15.0, -120.0), active=True,
    )

    assert (load.x, load.y) == (8.5, 0.0)
    assert load.components == (15.0, -120.0)
    assert "z" not in load.model_dump()


def test_point_load_rejects_a_non_finite_coordinate():
    with pytest.raises(ValidationError, match="coordinates"):
        schemas.PointLoad(
            id="bad", name="Bad", kind="point", x=float("nan"), y=0,
            thickness=0.25, components=(0, -1),
        )


def test_project_rejects_a_point_load_coordinate_outside_the_domain():
    payload = seed_project().model_dump()
    payload["loads"] = [{
        "id": "outside", "name": "Outside", "kind": "point",
        "x": payload["domain"]["x1"] + 1, "y": 0,
        "thickness": 0.25, "components": [0, -1],
    }]

    with pytest.raises(ValidationError, match="outside the domain"):
        schemas.Project.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"x1": 1.0},
        {"z1": 14.0},
        {"components": (0.0, float("inf"), -20.0)},
    ],
)
def test_surface_load_rejects_degenerate_geometry_and_non_finite_components(change):
    values = dict(
        id="load_north", name="North surcharge",
        x0=1.0, x1=10.0, z0=14.0, z1=26.0, thickness=0.25,
        components=(0.0, -20.0, 0.0), distribution="Uniform", active=True,
    )
    values.update(change)
    with pytest.raises(ValidationError):
        schemas.SurfaceLoad(**values)


def test_project_rejects_duplicate_load_ids():
    payload = seed_project(simple=False).model_dump()
    payload["loads"].append(payload["loads"][0])

    with pytest.raises(ValidationError, match="duplicate load"):
        schemas.Project.model_validate(payload)


def test_load_id_cannot_collide_with_an_existing_model_part_key():
    payload = seed_project(simple=False).model_dump()
    payload["loads"][0]["id"] = "wall"

    with pytest.raises(ValidationError, match="model part key"):
        schemas.Project.model_validate(payload)


def test_seed_surface_load_has_migrated_to_the_load_collection():
    project = seed_project(simple=False)

    assert not hasattr(project, "load")
    assert [(load.id, load.name) for load in project.loads] == [
        ("load", "SurfaceLoad_1")
    ]
    assert project.loads[0].components == (0.0, -20.0, 0.0)


def test_legacy_single_load_is_migrated_when_a_saved_project_is_opened():
    payload = seed_project(simple=False).model_dump()
    payload.pop("loads")
    payload["load"] = {
        "x0": 1.0, "x1": 10.0, "z0": 14.0, "z1": 26.0,
        "thickness": 0.25, "magnitude": 20.0,
    }

    migrated = schemas.Project.model_validate(payload)

    assert migrated.loads[0].id == "load"
    assert migrated.loads[0].components == (0.0, -20.0, 0.0)
    assert "load" not in migrated.model_dump()


def test_legacy_2d_line_footprint_is_migrated_without_hidden_z_data():
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=20.0)
    payload["loads"] = [{
        "id": "load_1", "name": "LineLoad_1", "kind": "surface",
        "x0": 2.0, "x1": 9.0, "z0": 0.0, "z1": 40.0,
        "thickness": 0.15, "components": [3.0, 8.0, -20.0],
        "distribution": "Uniform", "active": True,
    }]

    migrated = schemas.Project.model_validate(payload)
    dumped = migrated.loads[0].model_dump()

    assert isinstance(migrated.loads[0], schemas.LineLoad)
    assert dumped["components"] == (3.0, 8.0)
    assert not {"z", "z0", "z1"}.intersection(dumped)


# ── The key namespace: the contract with the frozen frontend ────────────────

def test_project_part_keys_match_the_frontend_userdata_key_namespace():
    """These strings are userData.key in js/viewport.js and obj: in js/data.js TREES.

    gmsh physical group names must equal them or selection silently degrades to
    "No object selected" (js/explorer.js:149).
    """
    keys = seed_project(simple=False).part_keys()
    assert keys == [
        "soil_L1", "soil_L2", "excavation", "wall", "struts",
        "anchors", "piles", "load", "water", "wells",
    ]


def test_simple_example_exposes_only_soil_geometry():
    assert seed_project().simple_example is True
    assert seed_project().part_keys() == ["soil_L1", "soil_L2"]
    domain = seed_project().domain
    assert domain.dx == domain.dy == domain.dz


def test_part_keys_track_the_layers():
    p = seed_project()
    extra = p.model_dump()
    extra["layers"][1]["bots"] = {bh: -18.0 for bh in extra["layers"][1]["bots"]}
    extra["layers"].append(
        dict(id="L3", name="Soil_3", mat="m6",
             tops={bh: -18.0 for bh in extra["layers"][1]["bots"]},
             bots={bh: -25.0 for bh in extra["layers"][1]["bots"]})
    )
    assert schemas.Project.model_validate(extra).part_keys()[:3] == [
        "soil_L1", "soil_L2", "soil_L3",
    ]


# ── Round trip ──────────────────────────────────────────────────────────────

def test_seed_project_round_trips_through_json():
    p = seed_project()
    assert schemas.Project.model_validate_json(p.model_dump_json()) == p


# ── Local mesh refinements ────────────────────────────────────────────────

def test_mesh_request_accepts_box_and_cylinder_refinements():
    request = schemas.MeshRequest.model_validate({
        "element_size": 3.0, "order": 2,
        "refinements": [
            {"kind": "box", "size": 1.0, "x_min": 1, "x_max": 2,
             "z_min": 3, "z_max": 4, "y_min": -5, "y_max": 0},
            {"kind": "cylinder", "size": 0.5, "x": 1, "y": 2, "z": -5,
             "axis_x": 0, "axis_y": 0, "axis_z": 10, "radius": 2},
        ],
    })
    assert len(request.refinements) == 2


def test_mesh_request_rejects_degenerate_refinements():
    with pytest.raises(ValidationError):
        schemas.MeshRequest.model_validate({
            "element_size": 3.0, "order": 1,
            "refinements": [{"kind": "box", "size": 1, "x_min": 2, "x_max": 1,
                             "z_min": 0, "z_max": 1, "y_min": -1, "y_max": 0}],
        })


def test_mesh_settings_expose_safe_gmsh_controls():
    settings = schemas.MeshSettings()
    assert settings.algorithm_3d == "delaunay"
    assert settings.optimization == "gmsh"
    assert settings.smoothing == 10
    assert settings.curvature_points == 16
    assert settings.size_min_factor == 0.05
    assert settings.second_order_linear is True

    with pytest.raises(ValidationError):
        schemas.MeshSettings(element_size=2, smoothing=-1)
    with pytest.raises(ValidationError):
        schemas.MeshSettings(element_size=2, algorithm_3d="unknown")


def test_mesh_request_accepts_an_explicit_body_selection():
    request = schemas.MeshRequest(
        element_size=2, order=1, volume_keys=["soil_L1", "soil_L2"],
        body_sizes={"soil_L1": 1.0, "soil_L2": 3.0},
    )
    assert request.volume_keys == ["soil_L1", "soil_L2"]
    assert request.body_sizes == {"soil_L1": 1.0, "soil_L2": 3.0}


def test_mesh_request_rejects_non_positive_body_size():
    with pytest.raises(ValidationError):
        schemas.MeshRequest(element_size=2, body_sizes={"soil_L1": 0})
    with pytest.raises(ValidationError):
        schemas.MeshRequest.model_validate({
            "element_size": 3.0, "order": 1,
            "refinements": [{"kind": "cylinder", "size": 1, "x": 0, "y": 0, "z": 0,
                             "axis_x": 0, "axis_y": 0, "axis_z": 0, "radius": 1}],
        })


# ── Model dimension ─────────────────────────────────────────────────────────

def test_a_project_is_three_dimensional_by_default():
    p = seed_project()
    assert p.dimension == 3
    assert p.section_offset is None


def test_switching_to_2d_fills_in_the_section_offset():
    """Left unset, the section goes through the middle of the domain.

    Resolved here rather than in build.py so that everything downstream -- the
    geometry, the mesh and the viewport -- reads one authoritative number instead
    of each deriving its own.
    """
    p = seed_project().model_copy(update={"dimension": 2})
    p = schemas.Project.model_validate(p.model_dump())
    assert p.section_offset == pytest.approx((p.domain.z0 + p.domain.z1) / 2)


def test_an_explicit_section_offset_is_kept():
    payload = seed_project().model_dump() | {"dimension": 2, "section_offset": 7.5}
    assert schemas.Project.model_validate(payload).section_offset == 7.5


@pytest.mark.parametrize("z", [-1.0, 40.0, 0.0, 100.0])
def test_a_section_outside_the_domain_is_rejected(z):
    """Including flush with a face: a section on the boundary grazes the outside
    of the solid and cuts a zero-area or knife-edge face out of it."""
    payload = seed_project(simple=False).model_dump() | {"dimension": 2, "section_offset": z}
    with pytest.raises(ValidationError):
        schemas.Project.model_validate(payload)


def test_section_offset_is_inert_in_3d():
    """A domain edit while in 3D must not fail on a stale out-of-range section."""
    payload = seed_project(simple=False).model_dump() | {"dimension": 3, "section_offset": 999.0}
    assert schemas.Project.model_validate(payload).section_offset == 999.0


def test_the_section_is_always_the_xy_plane_cut_at_a_constant_z():
    """There is one section plane now: x across, y up, normal to z. The offset is a
    world z and travels the domain's out-of-plane depth."""
    p = seed_project(simple=False)
    assert p.section_normal() == "z"
    assert p.section_bounds() == (p.domain.z0, p.domain.z1) == (0.0, 40.0)


def test_the_default_offset_is_the_middle_of_the_travel():
    payload = seed_project(simple=False).model_dump() | {"dimension": 2}
    assert schemas.Project.model_validate(payload).section_offset == pytest.approx(20.0)


def test_a_project_carries_no_section_plane():
    """`section_plane` is gone: sending one is a schema error, not a silent no-op."""
    assert not hasattr(seed_project(), "section_plane")
    payload = seed_project().model_dump() | {"section_plane": "xz"}
    with pytest.raises(ValidationError):
        schemas.Project.model_validate(payload)


# ── Sheet piles: reusable sections and beam records ─────────────────────────
#
# Section values live in a reusable `beam_sections` set rather than on each beam, the
# plan's stated preference: several sheet piles usually share one profile, and Kratos
# wants one MaterialParameters.json entry per distinct property set, not per beam.
# The pairing mirrors `materials` / `layers[].mat`, which the frontend already knows.

def _section(**overrides) -> dict:
    return {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
            "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0,
            "spacing": 1.0} | overrides


def _beam(**overrides) -> dict:
    return {"id": "sheetpile_1", "name": "Sheet pile 1", "section": "az26",
            "points": [[12.0, 0.0], [12.0, -14.0]], "active": True} | overrides


def _with_beams(beams: list[dict], sections: list[dict] | None = None) -> dict:
    payload = seed_project(simple=False).model_dump()
    payload["beam_sections"] = sections if sections is not None else [_section()]
    payload["beams"] = beams
    return payload


def test_a_beam_section_is_a_reusable_named_property_set():
    section = schemas.BeamSection(**_section())

    assert section.id == "az26"
    assert (section.E, section.area, section.inertia) == (2.1e8, 0.0198, 5.52e-4)
    assert section.spacing == 1.0, "out-of-plane spacing, per metre run in plane strain"


def test_a_beam_is_a_dimension_native_polyline_with_no_hidden_y():
    """A 2D record carries only in-plane coordinates, the Step 1 dimension contract."""
    beam = schemas.Beam(**_beam(points=[[12.0, 0.0], [12.0, -7.0], [13.0, -14.0]]))

    assert beam.points == [(12.0, 0.0), (12.0, -7.0), (13.0, -14.0)]
    assert beam.section == "az26"
    assert not {"y", "z0", "z1", "section_offset"}.intersection(beam.model_dump())
    assert all(len(point) == 2 for point in beam.points)


@pytest.mark.parametrize("points, message", [
    ([[12.0, 0.0]], "at least two"),
    ([[12.0, 0.0], [12.0, 0.0]], "repeats"),
    ([[12.0, 0.0], [12.0, -7.0], [12.0, -7.0]], "repeats"),
    ([[12.0, 0.0], [float("inf"), -7.0]], "finite"),
])
def test_a_beam_rejects_a_degenerate_polyline(points, message):
    with pytest.raises(ValidationError, match=message):
        schemas.Beam(**_beam(points=points))


@pytest.mark.parametrize("change", [
    {"E": 0.0}, {"area": 0.0}, {"inertia": -1.0}, {"density": 0.0},
    {"nu": 0.5}, {"spacing": 0.0},
])
def test_a_beam_section_rejects_unusable_property_values(change):
    with pytest.raises(ValidationError):
        schemas.BeamSection(**_section(**change))


def test_project_rejects_duplicate_beam_and_section_ids():
    with pytest.raises(ValidationError, match="duplicate beam"):
        schemas.Project.model_validate(_with_beams([_beam(), _beam()]))
    with pytest.raises(ValidationError, match="duplicate beam section"):
        schemas.Project.model_validate(
            _with_beams([_beam()], sections=[_section(), _section()])
        )


def test_project_rejects_a_beam_pointing_at_an_unknown_section():
    with pytest.raises(ValidationError, match="unknown beam section"):
        schemas.Project.model_validate(_with_beams([_beam(section="larssen")]))


def test_beam_id_cannot_collide_with_another_model_part_key():
    with pytest.raises(ValidationError, match="model part key"):
        schemas.Project.model_validate(_with_beams([_beam(id="wall")]))
    with pytest.raises(ValidationError, match="model part key"):
        schemas.Project.model_validate(_with_beams([_beam(id="load")]))


def test_project_rejects_a_beam_outside_the_domain():
    payload = seed_project(simple=False).model_dump()
    outside = payload["domain"]["x1"] + 5.0
    with pytest.raises(ValidationError, match="outside the domain"):
        schemas.Project.model_validate(
            _with_beams([_beam(points=[[outside, 0.0], [outside, -14.0]])])
        )


def test_a_beam_becomes_a_part_key_so_the_frontend_can_pick_it():
    project = schemas.Project.model_validate(_with_beams([_beam()]))

    assert "sheetpile_1" in project.part_keys()


def test_a_project_without_sheet_piles_stays_valid_and_empty():
    """Every saved project predates beams; none of them may fail to load."""
    project = seed_project(simple=False)

    assert project.beams == [] and project.beam_sections == []


# ── Anchors: two-node ties from a sheet pile to a restrained point ──────────
#
# The formulation is read off examples/crow_case.mdpa: one LinearTrussElement2D2N whose
# head node is shared with the sheet-pile beam and whose tail node belongs to no other
# element at all, held instead by its own single-node group. The tail is therefore not
# coupled to the soil -- the grouted body is idealised as a fixed point.

def _anchor_section(**overrides) -> dict:
    return {"id": "strand", "name": "4-strand tendon", "E": 1.95e8,
            "area": 0.0006, "density": 7850.0, "spacing": 2.5,
            "tension_limit": 900.0, "compression_limit": None} | overrides


def _anchor(**overrides) -> dict:
    return {"id": "anchor_1", "name": "Anchor 1", "kind": "anchor",
            "section": "strand", "head": [12.0, -2.0], "tail": [20.0, -8.0],
            "prestress": 250.0, "active": True} | overrides


def _with_anchors(anchors: list[dict], beams: list[dict] | None = None) -> dict:
    payload = seed_project(simple=False).model_dump()
    payload["beam_sections"] = [_section()]
    payload["beams"] = beams if beams is not None else [
        _beam(points=[[12.0, 0.0], [12.0, -14.0]])
    ]
    payload["anchor_sections"] = [_anchor_section()]
    payload["anchors"] = anchors
    return payload


def test_an_anchor_section_is_a_reusable_named_property_set():
    section = schemas.AnchorSection(**_anchor_section())

    assert (section.E, section.area) == (1.95e8, 0.0006)
    assert section.spacing == 2.5, "anchors are spaced along the wall, not continuous"
    assert section.compression_limit is None, "a tendon takes no compression"


def test_an_anchor_is_a_dimension_native_head_and_tail():
    anchor = schemas.Anchor(**_anchor())

    assert anchor.head == (12.0, -2.0) and anchor.tail == (20.0, -8.0)
    assert anchor.prestress == 250.0
    assert not {"y", "head_y", "section_offset"}.intersection(anchor.model_dump())


@pytest.mark.parametrize("change, message", [
    ({"tail": [12.0, -2.0]}, "length"),
    ({"tail": [float("nan"), -8.0]}, "finite"),
])
def test_an_anchor_rejects_a_degenerate_line(change, message):
    with pytest.raises(ValidationError, match=message):
        schemas.Anchor(**_anchor(**change))


@pytest.mark.parametrize("change", [
    {"E": 0.0}, {"area": -1.0}, {"density": 0.0}, {"spacing": 0.0},
    {"tension_limit": 0.0}, {"compression_limit": -5.0},
])
def test_an_anchor_section_rejects_unusable_property_values(change):
    with pytest.raises(ValidationError):
        schemas.AnchorSection(**_anchor_section(**change))


def test_project_rejects_duplicate_anchor_and_section_ids():
    with pytest.raises(ValidationError, match="duplicate anchor"):
        schemas.Project.model_validate(_with_anchors([_anchor(), _anchor()]))


def test_project_rejects_an_anchor_pointing_at_an_unknown_section():
    with pytest.raises(ValidationError, match="unknown anchor section"):
        schemas.Project.model_validate(_with_anchors([_anchor(section="bar")]))


def test_an_anchor_head_must_sit_on_a_sheet_pile():
    """The head node is shared with the beam, so it has to be on one to begin with."""
    with pytest.raises(ValidationError, match="sheet pile"):
        schemas.Project.model_validate(_with_anchors([_anchor(head=[5.0, -2.0])]))


def test_an_anchor_head_on_a_pile_segment_is_accepted():
    project = schemas.Project.model_validate(_with_anchors([_anchor()]))

    assert project.anchors[0].head == (12.0, -2.0)
    assert "anchor_1" in project.part_keys()


def test_an_anchor_head_must_sit_on_an_active_pile():
    beams = [_beam(points=[[12.0, 0.0], [12.0, -14.0]], active=False)]
    with pytest.raises(ValidationError, match="sheet pile"):
        schemas.Project.model_validate(_with_anchors([_anchor()], beams=beams))


def test_an_inactive_anchor_is_not_required_to_be_attached():
    """A pile deleted under a disabled anchor must not make the project unloadable."""
    project = schemas.Project.model_validate(
        _with_anchors([_anchor(head=[5.0, -2.0], active=False)])
    )

    assert project.anchors[0].active is False


def test_project_rejects_an_anchor_outside_the_domain():
    outside = seed_project(simple=False).domain.x1 + 5.0
    with pytest.raises(ValidationError, match="outside the domain"):
        schemas.Project.model_validate(_with_anchors([_anchor(tail=[outside, -8.0])]))


def test_the_legacy_anchor_row_block_still_loads_under_its_new_name():
    """Every saved project carries the aggregate `anchors` block that used to draw the
    3D cylinders; none of them may fail to open now that the name means a collection."""
    payload = seed_project(simple=False).model_dump()
    rows = payload.pop("anchor_rows")
    payload["anchors"] = rows

    project = schemas.Project.model_validate(payload)

    assert project.anchor_rows.xs == rows["xs"]
    assert project.anchors == []


# ── 3D structures: panels, members and space anchors ────────────────────────
#
# The 2D records stay exactly as they are. A 3D wall is not a beam one dimension up --
# in plan it is a panel, so it carries a thickness and meshes as shells -- while a
# bored pile or king post really is a 1D member in space. Both live in `beams[]`
# alongside the 2D sheet pile, discriminated by `kind`, the way `loads[]` already holds
# three kinds. No 3D element class here is pinned by a reference deck; see
# plan/structure-mode-implementation-plan.md.

def _panel_section(**overrides) -> dict:
    return {"id": "az26_wall", "name": "AZ 26-700 wall", "E": 2.1e8, "nu": 0.3,
            "thickness": 0.4, "density": 7850.0} | overrides


def _panel(**overrides) -> dict:
    return {"id": "panel_1", "name": "Wall 1", "kind": "panel", "section": "az26_wall",
            "footprint": [[12.0, 4.0], [12.0, 26.0]], "y_top": 0.0, "y_toe": -14.0,
            "active": True} | overrides


def _member(**overrides) -> dict:
    return {"id": "member_1", "name": "King post 1", "kind": "member",
            "section": "az26", "points": [[20.0, 0.0, 10.0], [20.0, -12.0, 10.0]],
            "active": True} | overrides


def _space_anchor(**overrides) -> dict:
    return {"id": "anchor_1", "name": "Anchor 1", "kind": "anchor3d",
            "section": "strand", "head": [12.0, -2.0, 10.0], "tail": [18.0, -8.0, 10.0],
            "prestress": 250.0, "active": True} | overrides


def _with_3d(beams: list[dict], anchors: list[dict] | None = None) -> dict:
    payload = seed_project(simple=False).model_dump()
    payload["beam_sections"] = [_section()]
    payload["panel_sections"] = [_panel_section()]
    payload["anchor_sections"] = [_anchor_section()]
    payload["beams"] = beams
    payload["anchors"] = anchors or []
    return payload


def test_a_panel_is_a_plan_footprint_swept_between_two_levels():
    panel = schemas.Panel(**_panel())

    assert panel.footprint == [(12.0, 4.0), (12.0, 26.0)]
    assert (panel.y_top, panel.y_toe) == (0.0, -14.0)
    assert panel.kind == "panel"
    # A wall in plan has no in-section (x, y) polyline and no per-metre-run area.
    assert not {"points", "area", "inertia"}.intersection(panel.model_dump())


def test_a_panel_section_carries_a_thickness_rather_than_area_and_inertia():
    section = schemas.PanelSection(**_panel_section())

    assert section.thickness == 0.4
    assert not {"area", "inertia", "spacing"}.intersection(section.model_dump())


@pytest.mark.parametrize("overrides, message", [
    ({"footprint": [[12.0, 4.0]]}, "at least two points"),
    ({"footprint": [[12.0, 4.0], [12.0, 4.0]]}, "zero-length"),
    ({"y_top": -14.0, "y_toe": 0.0}, "above its toe"),
    ({"y_top": -14.0, "y_toe": -14.0}, "above its toe"),
    ({"footprint": [[12.0, float("inf")], [12.0, 26.0]]}, "non-finite"),
])
def test_panel_rejects_a_footprint_it_could_not_sweep(overrides, message):
    with pytest.raises(ValidationError, match=message):
        schemas.Panel(**_panel(**overrides))


def test_a_member_is_a_polyline_in_space():
    member = schemas.Member(**_member())

    assert member.points == [(20.0, 0.0, 10.0), (20.0, -12.0, 10.0)]
    assert member.kind == "member"
    assert all(len(point) == 3 for point in member.points)


@pytest.mark.parametrize("overrides, message", [
    ({"points": [[20.0, 0.0, 10.0]]}, "at least two points"),
    ({"points": [[20.0, 0.0, 10.0], [20.0, 0.0, 10.0]]}, "zero-length"),
    ({"points": [[20.0, float("nan"), 10.0], [20.0, -12.0, 10.0]]}, "non-finite"),
])
def test_member_rejects_a_polyline_it_could_not_mesh(overrides, message):
    with pytest.raises(ValidationError, match=message):
        schemas.Member(**_member(**overrides))


def test_a_space_anchor_is_a_tie_between_two_points_in_space():
    anchor = schemas.SpaceAnchor(**_space_anchor())

    assert anchor.head == (12.0, -2.0, 10.0)
    assert anchor.tail == (18.0, -8.0, 10.0)
    assert anchor.kind == "anchor3d"


def test_space_anchor_rejects_a_tie_of_zero_length():
    with pytest.raises(ValidationError, match="non-zero length"):
        schemas.SpaceAnchor(**_space_anchor(tail=[12.0, -2.0, 10.0]))


def test_the_three_pile_kinds_live_in_one_collection_and_keep_their_types():
    project = schemas.Project.model_validate(
        _with_3d([_beam(), _panel(), _member()])
    )

    assert [type(b) for b in project.beams] == [schemas.Beam, schemas.Panel, schemas.Member]
    assert [b.id for b in project.sheet_piles] == ["sheetpile_1"]
    assert [b.id for b in project.panels] == ["panel_1"]
    assert [b.id for b in project.members] == ["member_1"]


def test_a_saved_2d_pile_written_before_the_3d_kinds_still_loads_as_a_beam():
    """Every project saved so far has beams with no `kind` at all."""
    payload = _with_3d([{k: v for k, v in _beam().items() if k != "kind"}])

    project = schemas.Project.model_validate(payload)

    assert isinstance(project.beams[0], schemas.Beam)
    assert project.beams[0].kind == "beam"
    assert project.beams[0].points == [(12.0, 0.0), (12.0, -14.0)]


def test_the_two_anchor_kinds_live_in_one_collection():
    project = schemas.Project.model_validate(
        _with_3d([_beam(points=[[12.0, 0.0], [12.0, -14.0]]), _panel()],
                 anchors=[_anchor(id="anchor_2"), _space_anchor()])
    )

    assert [type(a) for a in project.anchors] == [schemas.Anchor, schemas.SpaceAnchor]
    assert [a.id for a in project.plane_anchors] == ["anchor_2"]
    assert [a.id for a in project.space_anchors] == ["anchor_1"]


def test_a_panel_must_reference_a_panel_section_and_a_member_a_beam_section():
    with pytest.raises(ValidationError, match="unknown panel section"):
        schemas.Project.model_validate(_with_3d([_panel(section="larssen")]))
    with pytest.raises(ValidationError, match="unknown beam section"):
        schemas.Project.model_validate(_with_3d([_member(section="larssen")]))
    # A member shares the sheet pile's profile library: same E, area and inertia.
    project = schemas.Project.model_validate(_with_3d([_member()]))
    assert project.beam_section(project.members[0].section).area == _section()["area"]


def test_panel_sections_have_their_own_id_namespace_and_reject_duplicates():
    with pytest.raises(ValidationError, match="duplicate panel section"):
        payload = _with_3d([_panel()])
        payload["panel_sections"] = [_panel_section(), _panel_section()]
        schemas.Project.model_validate(payload)


def test_ids_stay_unique_across_every_pile_kind():
    with pytest.raises(ValidationError, match="duplicate beam"):
        schemas.Project.model_validate(_with_3d([_beam(id="x"), _panel(id="x")]))
    with pytest.raises(ValidationError, match="model part key"):
        schemas.Project.model_validate(_with_3d([_panel(id="wall")]))


@pytest.mark.parametrize("beams, anchors", [
    ([_panel(footprint=[[999.0, 4.0], [999.0, 26.0]])], []),
    ([_panel(y_toe=-999.0)], []),
    ([_member(points=[[999.0, 0.0, 10.0], [999.0, -12.0, 10.0]])], []),
    ([_panel()], [_space_anchor(tail=[999.0, -8.0, 10.0])]),
])
def test_a_3d_structure_outside_the_domain_is_rejected(beams, anchors):
    with pytest.raises(ValidationError, match="outside the domain"):
        schemas.Project.model_validate(_with_3d(beams, anchors))


def test_a_space_anchor_head_must_be_on_a_panel_or_a_member():
    # On the panel's footprint, between its levels: the head becomes a shared node.
    ok = schemas.Project.model_validate(_with_3d([_panel()], [_space_anchor()]))
    assert ok.space_anchors[0].head == (12.0, -2.0, 10.0)

    # On a member's polyline instead.
    ok = schemas.Project.model_validate(
        _with_3d([_member()], [_space_anchor(head=[20.0, -4.0, 10.0])])
    )
    assert ok.space_anchors[0].head == (20.0, -4.0, 10.0)

    # Beside the wall, in mid-air.
    with pytest.raises(ValidationError, match="not on a wall or member"):
        schemas.Project.model_validate(
            _with_3d([_panel()], [_space_anchor(head=[13.0, -2.0, 10.0])])
        )
    # On the footprint in plan, but below the toe.
    with pytest.raises(ValidationError, match="not on a wall or member"):
        schemas.Project.model_validate(
            _with_3d([_panel()], [_space_anchor(head=[12.0, -20.0, 10.0],
                                                tail=[18.0, -22.0, 10.0])])
        )


def test_an_inactive_space_anchor_is_not_required_to_be_attached():
    project = schemas.Project.model_validate(
        _with_3d([_panel()], [_space_anchor(head=[13.0, -2.0, 10.0], active=False)])
    )

    assert project.space_anchors[0].active is False


def test_a_2d_anchor_may_hang_from_a_2d_pile_while_a_3d_one_hangs_from_a_panel():
    """Both kinds coexist: each is checked against the structures of its own dimension."""
    project = schemas.Project.model_validate(
        _with_3d([_beam(points=[[12.0, 0.0], [12.0, -14.0]]), _panel()],
                 anchors=[_anchor(id="anchor_2"), _space_anchor()])
    )

    assert len(project.anchors) == 2


def test_3d_structures_become_part_keys_so_the_frontend_can_pick_them():
    project = schemas.Project.model_validate(
        _with_3d([_panel(), _member()], [_space_anchor()])
    )
    keys = project.part_keys()

    assert {"panel_1", "member_1", "anchor_1"} <= set(keys)


def test_a_project_without_3d_structures_stays_valid_and_empty():
    project = seed_project(simple=False)

    assert project.panels == [] and project.members == []
    assert project.space_anchors == [] and project.panel_sections == []


# ── Interfaces ──────────────────────────────────────────────────────────────
#
# An interface is the zero-thickness contact between a structure and the soil around
# it, the arrangement examples/crow_case.mdpa contains. Its properties live in a
# reusable `interface_sections` set for the same reason a beam's do: several contacts
# normally share one, and Kratos wants one property entry per distinct set.

def _contact(**overrides) -> dict:
    return {"id": "contact_1", "name": "Steel against sand", "material": "mat_sand",
            "r_inter": 0.67, "virtual_thickness": 0.01, "normal_stiffness": None,
            "shear_stiffness": None, "permeability": "Neutral"} | overrides


def _interface(**overrides) -> dict:
    return {"id": "interface_1", "name": "Wall contact", "section": "contact_1",
            "structure": "sheetpile_1", "points": None, "side": "both",
            "active": True} | overrides


def _with_interfaces(records: list[dict], contacts: list[dict] | None = None,
                     beams: list[dict] | None = None) -> dict:
    payload = seed_project(simple=False).model_dump()
    # Plane strain: an interface is a line in a section, so the project it lives in is
    # one. `test_interfaces_are_plane_strain_only` puts it back in 3D on purpose.
    payload["dimension"] = 2
    payload["beam_sections"] = [_section()]
    payload["beams"] = beams if beams is not None else [
        _beam(points=[[12.0, 0.0], [12.0, -14.0]])
    ]
    material = payload["materials"][0]["id"]
    payload["interface_sections"] = [dict(c, material=material)
                                     for c in (contacts if contacts is not None
                                               else [_contact()])]
    payload["interfaces"] = records
    return payload


def test_an_interface_section_is_a_reusable_named_property_set():
    section = schemas.InterfaceSection(**_contact())

    assert section.r_inter == 0.67
    assert section.virtual_thickness == 0.01
    assert section.normal_stiffness is None, "derived from the soil unless given"


def test_an_interface_section_needs_a_soil_or_both_stiffnesses():
    """There is nothing else to derive a zero-thickness element's stiffness from."""
    with pytest.raises(ValidationError):
        schemas.InterfaceSection(**_contact(material=None))

    section = schemas.InterfaceSection(
        **_contact(material=None, normal_stiffness=1.0e6, shear_stiffness=4.0e5))
    assert section.material is None


def test_an_interface_follows_a_structure_or_its_own_points_but_never_both():
    assert schemas.Interface(**_interface()).structure == "sheetpile_1"
    assert schemas.Interface(
        **_interface(structure=None, points=[[8.0, 0.0], [8.0, -10.0]], side="left")
    ).points == [(8.0, 0.0), (8.0, -10.0)]

    with pytest.raises(ValidationError):
        schemas.Interface(**_interface(points=[[8.0, 0.0], [8.0, -10.0]]))
    with pytest.raises(ValidationError):
        schemas.Interface(**_interface(structure=None))


def test_a_free_interface_must_detach_one_side():
    """With no structure between the two soils, "both" leaves nothing holding the
    original nodes -- there is no third body for them to belong to."""
    with pytest.raises(ValidationError):
        schemas.Interface(**_interface(structure=None,
                                       points=[[8.0, 0.0], [8.0, -10.0]], side="both"))


def test_a_free_interface_needs_a_usable_polyline():
    for points in ([[8.0, 0.0]], [[8.0, 0.0], [8.0, 0.0]], [[8.0, 0.0], [8.0, float("nan")]]):
        with pytest.raises(ValidationError):
            schemas.Interface(**_interface(structure=None, points=points, side="left"))


def test_an_interface_must_name_a_section_the_project_has():
    with pytest.raises(ValidationError):
        schemas.Project.model_validate(
            _with_interfaces([_interface(section="missing")]))


def test_an_interface_must_follow_a_sheet_pile_the_project_has():
    with pytest.raises(ValidationError):
        schemas.Project.model_validate(
            _with_interfaces([_interface(structure="sheetpile_9")]))


def test_duplicate_interface_ids_are_rejected():
    with pytest.raises(ValidationError):
        schemas.Project.model_validate(
            _with_interfaces([_interface(), _interface(name="Twin")]))


def test_an_interface_becomes_a_part_key_so_the_frontend_can_pick_it():
    project = schemas.Project.model_validate(_with_interfaces([_interface()]))

    assert "interface_1" in project.part_keys()


def test_only_live_interfaces_on_live_piles_are_built():
    """A contact against a switched-off wall is not a contact, and exporting one would
    quietly weld the soil back together."""
    payload = _with_interfaces([_interface(), _interface(id="interface_2",
                                                        name="Off", active=False)])
    project = schemas.Project.model_validate(payload)
    assert [i.id for i in project.active_interfaces] == ["interface_1"]

    payload["beams"][0]["active"] = False
    assert schemas.Project.model_validate(payload).active_interfaces == []


def test_interfaces_are_plane_strain_only():
    payload = _with_interfaces([_interface()])
    payload["dimension"] = 3
    project = schemas.Project.model_validate(payload)

    assert project.interfaces, "the record is kept, like every other 2D record"
    assert project.active_interfaces == [], "but nothing is built from it in 3D"
