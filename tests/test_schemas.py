"""Contract tests for the project schema.

The schema is the single source of truth the frontend currently lacks: today geometry
lives in js/viewport.js while descriptions of that geometry live in js/data.js, and the
two disagree (see test_parity.py).
"""

import pytest
from pydantic import ValidationError

from core.model import schemas
from core.model.templates import blank_project, seed_project
from tests.models.excavation import excavation_project


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

SAND = dict(id="m2", name="Sand, loose", color="#c4a86a",
            constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
            variables={"YOUNG_MODULUS": 2.5e7, "POISSON_RATIO": 0.28,
                       "DENSITY_SOLID": 1834.86, "GEO_COHESION": 500.0,
                       "GEO_FRICTION_ANGLE": 30.0, "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"})


def test_material_colour_must_be_a_css_hex():
    ok = schemas.Material(**SAND)
    assert ok.color == "#c4a86a"

    with pytest.raises(ValidationError):
        schemas.Material.model_validate({**ok.model_dump(), "color": "chartreuse"})


def test_a_material_is_a_kratos_law_and_its_variables():
    """What `MaterialParameters.json` carries, under Kratos' own names: numbers, strings,
    flags and parameter lists (a UDSM's) alike."""
    m = schemas.Material(**{**SAND, "variables": {
        **SAND["variables"], "UDSM_PARAMETERS": [1.0, 2.0], "IS_FORTRAN_UDSM": True}})
    assert m.constitutive_law == "GeoLinearElasticPlaneStrain2DLaw"
    assert m.variables["GEO_DRAINAGE_TYPE"] == "DRAINED", "Kratos' CONSTANT_PW_FIELD, renamed"
    assert m.number("YOUNG_MODULUS") == 2.5e7
    assert m.number("GEO_DRAINAGE_TYPE") is None and m.number("ABSENT") is None


@pytest.mark.parametrize("change, message", [
    ({"constitutive_law": ""}, "constitutive_law"),
    ({"variables": {"youngs_modulus": 1.0}}, "variables"),
    ({"variables": {"YOUNG_MODULUS": float("inf")}}, "finite"),
    ({"variables": {"UDSM_PARAMETERS": [1.0, float("nan")]}}, "finite"),
])
def test_a_material_refuses_what_kratos_could_not_read(change, message):
    with pytest.raises(ValidationError, match=message):
        schemas.Material(**{**SAND, **change})


def test_a_material_without_strength_simply_leaves_it_out():
    """Non-porous rock has no cohesion and no friction angle (js/data.js:325): the
    variables are absent, not zero."""
    rock = {k: v for k, v in SAND["variables"].items()
            if k not in ("GEO_COHESION", "GEO_FRICTION_ANGLE")}
    m = schemas.Material(**{**SAND, "variables": rock})
    assert m.number("GEO_COHESION") is None and m.number("GEO_FRICTION_ANGLE") is None


def test_a_material_built_from_the_old_fields_is_converted():
    """A script written against the old fields still works: the record is read as an
    old file's would be (`core/model/migration.py`), in SI."""
    m = schemas.Material(id="m2", name="Sand, loose", model="Hardening Soil",
                         type="Drained", color="#c4a86a", g_unsat=18.0, g_sat=20.5,
                         E=25000, nu=0.28, c=0.5, phi=32.0, k=1.5)
    assert m.variables["YOUNG_MODULUS"] == 25000 * 1000
    assert m.variables["DENSITY_SOLID"] == 18.0 * 1000 / 9.81


# ── K0, for the initial stage ───────────────────────────────────────────────
#
# `apply_k0_procedure_process` settles the initial stress field, and reads K0_NC off
# each soil property (plan/outdated/staged-construction-plan.md sec C4). A material gives one as
# a `K0_NC` variable; one that does not gets Jaky's at export.

def _sand(**variables) -> schemas.Material:
    return schemas.Material(**{**SAND, "variables": {**SAND["variables"], **variables}})


def test_k0_defaults_to_jaky_from_the_friction_angle_of_a_plastic_soil():
    """1 - sin(phi): the normally consolidated K0 a Mohr-Coulomb soil's own friction
    angle gives (0.62 at 22.3 deg, 0.46 at 32.7 deg)."""
    from core.kratos.materials import k0_nc
    plastic = {"constitutive_law": "GeoMohrCoulombLawPlaneStrain"}
    assert k0_nc(_sand(GEO_FRICTION_ANGLE=30.0).model_copy(update=plastic)) == \
        pytest.approx(0.5)
    assert k0_nc(_sand(GEO_FRICTION_ANGLE=22.3).model_copy(update=plastic)) == \
        pytest.approx(0.62, abs=5e-3)


def test_k0_of_an_elastic_soil_is_the_elastic_one_whatever_its_friction_angle():
    from core.kratos.materials import k0_nc
    assert k0_nc(_sand(GEO_FRICTION_ANGLE=30.0)) == pytest.approx(0.28 / 0.72)


def test_a_material_with_no_friction_angle_has_no_k0():
    """Non-porous rock with neither a friction angle nor a Poisson ratio: nothing should
    be invented for it."""
    from core.kratos.materials import k0_nc
    rock = schemas.Material(**{**SAND, "variables": {"YOUNG_MODULUS": 2e9}})
    assert k0_nc(rock) is None


# ── Soil layers ─────────────────────────────────────────────────────────────

def test_layer_stack_must_be_contiguous():
    """Each layer's bottom is the next layer's top: no gap, no overlap."""
    good = [
        schemas.SoilLayer(id="L1", name="Soil_1", mat="m2", top=0.0, bottom=-8.0),
        schemas.SoilLayer(id="L2", name="Soil_2", mat="m4", top=-8.0, bottom=-25.0),
    ]
    schemas.validate_layer_stack(good)  # does not raise

    gap = [good[0], schemas.SoilLayer(id="L2", name="Soil_2", mat="m4",
                                      top=-9.0, bottom=-25.0)]
    with pytest.raises(ValueError, match="contiguous"):
        schemas.validate_layer_stack(gap)

    overlap = [good[0], schemas.SoilLayer(id="L2", name="Soil_2", mat="m4",
                                          top=-7.0, bottom=-25.0)]
    with pytest.raises(ValueError, match="contiguous"):
        schemas.validate_layer_stack(overlap)


def test_a_project_refuses_a_gap_in_the_layer_stack():
    bad = seed_project().model_dump()
    bad["layers"][1]["top"] = -9.0
    with pytest.raises(ValidationError, match="contiguous"):
        schemas.Project.model_validate(bad)


def test_layer_rejects_inverted_thickness():
    with pytest.raises(ValidationError):
        schemas.SoilLayer(id="L1", name="Soil_1", mat="m2", top=-8.0, bottom=0.0)


def test_a_layer_has_no_borehole_levels():
    with pytest.raises(ValidationError):
        schemas.SoilLayer(id="L1", name="Soil_1", mat="m2", tops={"bh1": 0.0},
                          bots={"bh1": -8.0})


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
    bad["layers"].append(bad["layers"][-1])
    with pytest.raises(ValidationError, match="duplicate"):
        schemas.Project.model_validate(bad)


def test_excavation_must_sit_inside_the_domain():
    p = seed_project(simple=False)
    bad = p.model_dump()
    bad["excavation"]["x1"] = 500.0
    with pytest.raises(ValidationError, match="domain"):
        schemas.Project.model_validate(bad)


# ── Staged excavation levels ────────────────────────────────────────────────
#
# A staged excavation is dug in lifts, and each lift is a separately deactivatable body
# in the deck (plan/outdated/staged-construction-plan.md sec 0.1: Excavated_Soil_1/2/3). `levels`
# is that sequence; `floor_y` is the last of them, kept as the name everything already
# reads.

def test_excavation_without_levels_is_a_single_lift_at_its_floor():
    """Every saved project predates `levels` and must keep opening."""
    e = schemas.Excavation(x0=0, x1=10, z0=0, z1=10, floor_y=-7.0)
    assert e.levels == [-7.0]


def test_excavation_levels_set_the_floor():
    """Giving `levels` alone is enough: `floor_y` follows from the last of them."""
    e = schemas.Excavation(x0=0, x1=10, z0=0, z1=10, levels=[-2.0, -5.0, -8.0])
    assert e.floor_y == -8.0
    assert e.levels == [-2.0, -5.0, -8.0]


def test_excavation_levels_must_descend():
    for levels in ([-5.0, -2.0], [-2.0, -2.0], [-2.0, -8.0, -5.0]):
        with pytest.raises(ValidationError, match="descend"):
            schemas.Excavation(x0=0, x1=10, z0=0, z1=10, levels=levels)


def test_an_empty_level_list_means_unspecified_not_invalid():
    """`[]` is what an old record round-tripped through a client that knows the field
    but has nothing to put in it looks like; it is the `floor_y` case, not an error."""
    e = schemas.Excavation(x0=0, x1=10, z0=0, z1=10, floor_y=-7.0, levels=[])
    assert e.levels == [-7.0]


def test_every_excavation_level_must_lie_inside_the_domain():
    """Not just the floor: an intermediate lift above the ground is just as wrong."""
    p = seed_project(simple=False)
    bad = p.model_dump()
    bad["excavation"]["levels"] = [5.0, bad["excavation"]["floor_y"]]
    with pytest.raises(ValidationError, match="domain"):
        schemas.Project.model_validate(bad)


@pytest.mark.parametrize("levels", [[-7.0], [-2.0, -5.0, -8.0]])
def test_a_floor_disagreeing_with_its_levels_is_refused_not_guessed(levels):
    """Whichever field the caller edited, the other must not silently overwrite it --
    and the payload cannot say which that was, so neither is allowed to win."""
    with pytest.raises(ValidationError, match="disagrees"):
        schemas.Excavation(x0=0, x1=10, z0=0, z1=10, floor_y=-9.0, levels=levels)


def _layered_pit() -> schemas.Project:
    """A staged excavation's soil arrangement: three layers, three excavation lifts.

    Layer 1 spans 0..-8 and is dug away in three lifts; layer 2 (-8..-12) and layer 3
    (-12..-60) are never dug. That produces eight bodies -- see
    plan/outdated/staged-construction-plan.md sec 0.1.
    """
    p = seed_project(simple=False).model_dump()
    p["domain"] |= {"y_top": 0.0, "y_bottom": -60.0}
    p["layers"] = [
        {"id": "L1", "name": "Soil_1", "mat": p["materials"][0]["id"],
         "top": 0.0, "bottom": -8.0},
        {"id": "L2", "name": "Soil_2", "mat": p["materials"][0]["id"],
         "top": -8.0, "bottom": -12.0},
        {"id": "L3", "name": "Soil_3", "mat": p["materials"][1]["id"],
         "top": -12.0, "bottom": -60.0},
    ]
    # `levels` supersedes the seed's `floor_y`, and the two may not disagree.
    p["excavation"] = {k: v for k, v in p["excavation"].items() if k != "floor_y"}
    p["excavation"] |= {"x0": 0.0, "x1": 5.0, "levels": [-2.0, -5.0, -8.0]}
    p["wall"] |= {"top_y": 0.0, "toe_y": -13.0}
    return schemas.Project.model_validate(p)


def test_an_unstaged_project_has_one_soil_body_per_layer():
    """The pit is a void cut out of the soil, so nothing is renamed and nothing splits."""
    p = seed_project(simple=False)
    assert [key for key, *_ in p.soil_bodies()] == [f"soil_{l.id}" for l in p.layers]


def test_a_staged_excavation_splits_the_soil_inside_the_pit_into_lifts():
    bodies = {key: (y0, y1) for key, y0, y1, _ in _layered_pit().soil_bodies()}
    assert bodies == {
        # Outside the pit outline the layers are untouched and keep their own keys.
        "soil_L1": (-8.0, 0.0),
        "soil_L2": (-12.0, -8.0),
        "soil_L3": (-60.0, -12.0),
        # Inside it, layer 1 is dug away one lift per stage ...
        "soil_L1__lift1": (-2.0, 0.0),
        "soil_L1__lift2": (-5.0, -2.0),
        "soil_L1__lift3": (-8.0, -5.0),
        # ... and what is never dug is still its own body, because it sits on the
        # excavated side of the wall.
        "soil_L2__pit": (-12.0, -8.0),
        "soil_L3__pit": (-60.0, -12.0),
    }


def test_a_lift_crossing_a_layer_boundary_yields_one_body_per_layer():
    """Bodies are the intersection of a layer with a lift, so a lift deeper than the
    layer it starts in cannot produce one body spanning two materials."""
    p = _layered_pit().model_dump()
    # The first lift is dug straight through L1 and on into L2. `floor_y` follows
    # `levels` rather than the other way round, so it goes out with the levels it
    # belonged to.
    p["excavation"] = {k: v for k, v in p["excavation"].items() if k != "floor_y"}
    p["excavation"]["levels"] = [-10.0, -11.0]
    bodies = {key: (y0, y1)
              for key, y0, y1, _ in schemas.Project.model_validate(p).soil_bodies()}
    assert bodies["soil_L1__lift1"] == (-8.0, 0.0)     # the part of lift 1 in L1 ...
    assert bodies["soil_L2__lift1"] == (-10.0, -8.0)   # ... and the part in L2
    assert bodies["soil_L2__pit"] == (-12.0, -11.0)    # below the floor, still in L2


def test_staged_soil_bodies_are_part_keys():
    """Anything with geometry needs a key, or the viewport and the exporter cannot
    name it (`Project.part_keys` is that namespace)."""
    p = _layered_pit()
    keys = p.part_keys()
    assert len(keys) == len(set(keys)), "part keys must stay unique"
    for key, *_ in p.soil_bodies():
        assert key in keys


def test_excavation_levels_survive_a_round_trip():
    p = seed_project(simple=False)
    raw = p.model_dump()
    raw["excavation"]["levels"] = [-2.0, -5.0, -7.0]
    reloaded = schemas.Project.model_validate(
        schemas.Project.model_validate(raw).model_dump())
    assert reloaded.excavation.levels == [-2.0, -5.0, -7.0]
    assert reloaded.excavation.floor_y == -7.0


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
    assert project.loads[0].components == (0.0, -20_000.0, 0.0)     # Pa: SI


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


def test_layered_soil_exposes_only_soil_geometry():
    assert seed_project().layered_soil is True
    assert seed_project().part_keys() == ["soil_L1", "soil_L2"]
    domain = seed_project().domain
    assert domain.dx == domain.dy == domain.dz


def test_part_keys_track_the_layers():
    p = seed_project()
    extra = p.model_dump()
    extra["layers"][1]["bottom"] = -18.0
    extra["layers"].append(dict(id="L3", name="Soil_3", mat="m6", top=-18.0, bottom=-25.0))
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

    Resolved here rather than in solid_model.py so that everything downstream -- the
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

STEEL_PILE = {"YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.3, "CROSS_AREA": 0.0198,
              "I33": 5.52e-4, "DENSITY": 7850.0}


def _section(**overrides) -> dict:
    return {"id": "az26", "name": "AZ 26-700", "spacing": 1.0,
            "variables": dict(STEEL_PILE)} | overrides


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
    assert section.constitutive_law == "TimoshenkoBeamElasticConstitutiveLaw"
    assert section.variables == STEEL_PILE
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
    {"spacing": 0.0}, {"variables": STEEL_PILE | {"I33": float("nan")}},
    {"constitutive_law": ""},
])
def test_a_beam_section_rejects_unusable_property_values(change):
    """What Kratos would refuse to read. A missing variable the law needs is refused at
    export, naming it (`test_export_golden.py`)."""
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
# The formulation is Kratos' own staged-excavation one: one LinearTrussElement2D2N whose
# head node is shared with the sheet-pile beam and whose tail node belongs to no other
# element at all, held instead by its own single-node group. The tail is therefore not
# coupled to the soil -- the grouted body is idealised as a fixed point.

TENDON = {"YOUNG_MODULUS": 1.95e11, "CROSS_AREA": 0.0006, "DENSITY": 7850.0}


def _anchor_section(**overrides) -> dict:
    return {"id": "strand", "name": "4-strand tendon", "spacing": 2.5,
            "tension_limit": 900_000.0, "compression_limit": None,
            "variables": dict(TENDON)} | overrides


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

    assert section.constitutive_law == "TrussConstitutiveLaw"
    assert section.variables == TENDON
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
    {"spacing": 0.0}, {"tension_limit": 0.0}, {"compression_limit": -5.0},
    {"variables": TENDON | {"CROSS_AREA": float("inf")}},
])
def test_an_anchor_section_rejects_unusable_property_values(change):
    with pytest.raises(ValidationError):
        schemas.AnchorSection(**_anchor_section(**change))


def test_a_tendon_may_be_massless():
    """Zero density used to be refused along with the negative one. A prestressed strut
    whose own weight is beside the point next to the force it carries is an ordinary
    thing to model, and the reference deck's tendon is exactly that."""
    tendon = schemas.AnchorSection(**_anchor_section(variables=TENDON | {"DENSITY": 0.0}))
    assert tendon.variables["DENSITY"] == 0.0


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
    return {"id": "az26_wall", "name": "AZ 26-700 wall", "variables": {
        "YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.3, "THICKNESS": 0.4,
        "DENSITY": 7850.0}} | overrides


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

    assert section.variables["THICKNESS"] == 0.4
    assert section.constitutive_law == "LinearElasticPlaneStress2DLaw"
    assert not {"CROSS_AREA", "I33"}.intersection(section.variables)
    assert "spacing" not in section.model_dump()


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
    assert project.beam_section(project.members[0].section).variables["CROSS_AREA"] == \
        _section()["variables"]["CROSS_AREA"]


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
# it, the arrangement Kratos' staged-excavation decks use. Its properties live in a
# reusable `interface_sections` set for the same reason a beam's do: several contacts
# normally share one, and Kratos wants one property entry per distinct set.

def _contact(**overrides) -> dict:
    return {"id": "contact_1", "name": "Steel against sand", "material": "mat_sand",
            "r_inter": 0.67, "virtual_thickness": 0.01, "permeability": "Neutral"} | overrides


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
    assert section.constitutive_law == "GeoIncrementalLinearElasticInterfaceLaw"
    assert section.variables == {}, "derived from the soil unless given"


def test_an_interface_section_needs_no_soil_of_its_own():
    """It used to be refused without either a material or both stiffnesses. That is the
    ordinary case now: such a section derives each stretch of the contact from the soil
    body it actually runs against, which is a fact about the mesh and unknowable here.
    The contact that really has nothing to derive from -- no adjacent soil either -- is
    refused at export instead (`tests/test_kratos_interfaces.py`)."""
    section = schemas.InterfaceSection(**_contact(material=None))
    assert section.material is None
    assert "INTERFACE_NORMAL_STIFFNESS" not in section.variables

    typed = schemas.InterfaceSection(**_contact(material=None, variables={
        "INTERFACE_NORMAL_STIFFNESS": 1.0e9, "INTERFACE_SHEAR_STIFFNESS": 4.0e8}))
    assert typed.variables["INTERFACE_NORMAL_STIFFNESS"] == 1.0e9


def test_the_element_size_normal_to_an_interface_defaults_to_one_metre():
    """The reference deck's own, and what its stiffnesses are the soil's shear modulus
    over. It was 0.01, which made every derived contact 100x too stiff."""
    assert schemas.InterfaceSection.model_fields["virtual_thickness"].default == 1.0


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


# ── An interface on a part of a pile, and its faces on the screen ───────────

def test_a_stretch_needs_a_pile_and_two_distinct_points():
    with pytest.raises(ValidationError, match="follows no sheet pile"):
        schemas.Interface(**_interface(structure=None, points=[[8.0, 0.0], [8.0, -10.0]],
                                       side="left", stretch=[[8.0, 0.0], [8.0, -4.0]]))
    with pytest.raises(ValidationError, match="same point"):
        schemas.Interface(**_interface(stretch=[[12.0, -2.0], [12.0, -2.0]]))
    with pytest.raises(ValidationError, match="non-finite"):
        schemas.Interface(**_interface(stretch=[[12.0, -2.0], [12.0, float("nan")]]))


def test_a_stretch_must_lie_on_its_pile():
    with pytest.raises(ValidationError, match=r"To \(12.2, -6\) is 0.2 m from Sheet pile"):
        schemas.Project.model_validate(_with_interfaces(
            [_interface(stretch=[[12.0, -2.0], [12.2, -6.0]])]))


def test_an_interface_runs_along_the_part_of_its_pile_between_from_and_to():
    project = schemas.Project.model_validate(_with_interfaces(
        [_interface(stretch=[[12.0, -6.0], [12.0, -2.0]])]))
    interface = project.interfaces[0]

    assert interface.stretch == ((12.0, -6.0), (12.0, -2.0))
    assert project.interface_path(interface) == [(12.0, -2.0), (12.0, -6.0)], \
        "in the pile's own order, whichever way From and To are given"


def test_a_stretch_over_the_whole_pile_is_saved_as_the_whole_pile():
    """So a whole pile has one form, and the records of today load as they are."""
    project = schemas.Project.model_validate(_with_interfaces(
        [_interface(stretch=[[12.0, -14.0], [12.0, 0.0]])]))
    assert project.interfaces[0].stretch is None
    assert project.interface_path(project.interfaces[0]) == [(12.0, 0.0), (12.0, -14.0)]


def test_a_whole_pile_record_of_today_loads_unchanged():
    payload = _with_interfaces([_interface(side="left")])
    project = schemas.Project.model_validate(payload)
    assert project.model_dump()["interfaces"][0] == {**_interface(side="left"),
                                                     "kind": "interface", "stretch": None}


def test_the_faces_of_a_flat_line_are_below_and_above():
    """A record follows its line: left on a line flatter than 45 degrees is below."""
    beams = [_beam(points=[[2.0, -3.0], [20.0, -5.0]])]
    project = schemas.Project.model_validate(_with_interfaces(
        [_interface(side="left")], beams=beams))
    assert project.interfaces[0].side == "below"

    steep = [_beam(points=[[12.0, 0.0], [12.0, -14.0]])]
    project = schemas.Project.model_validate(_with_interfaces(
        [_interface(side="above")], beams=steep))
    assert project.interfaces[0].side == "right"


def test_an_old_one_side_record_drawn_downward_loads_with_its_side_swapped():
    """Before 2026-10-25 left was left walking the line. Walking down a pile, that is
    the soil toward +x: the screen's right. The pile's soil stays the soil it was."""
    payload = _with_interfaces([_interface(side="left"),
                                _interface(id="interface_2", name="Slip", structure=None,
                                           points=[[4.0, -1.0], [4.0, -9.0]],
                                           side="right")])
    del payload["interface_sides"]
    project = schemas.Project.model_validate(payload)

    assert [i.side for i in project.interfaces] == ["right", "left"]
    assert project.interface_sides == "screen"
    again = schemas.Project.model_validate(project.model_dump())
    assert [i.side for i in again.interfaces] == ["right", "left"], "converted once only"


def test_an_old_record_drawn_upward_keeps_its_side():
    beams = [_beam(points=[[12.0, -14.0], [12.0, 0.0]])]
    payload = _with_interfaces([_interface(side="left")], beams=beams)
    del payload["interface_sides"]
    assert schemas.Project.model_validate(payload).interfaces[0].side == "left"


def test_two_interfaces_may_not_hold_the_same_face_over_the_same_length():
    with pytest.raises(ValidationError, match=(
            "Bottom and Wall contact both hold the left face of Sheet pile 1 between "
            "y -4 and y -6")):
        schemas.Project.model_validate(_with_interfaces([
            _interface(side="left", stretch=[[12.0, 0.0], [12.0, -6.0]]),
            _interface(id="interface_2", name="Bottom", side="both",
                       stretch=[[12.0, -4.0], [12.0, -14.0]])]))


def test_two_interfaces_may_hold_the_two_faces_or_two_parts_of_one_face():
    project = schemas.Project.model_validate(_with_interfaces([
        _interface(side="left", stretch=[[12.0, 0.0], [12.0, -6.0]]),
        _interface(id="interface_2", name="Right", side="right"),
        _interface(id="interface_3", name="Bottom", side="left",
                   stretch=[[12.0, -6.0], [12.0, -14.0]])]))
    assert len(project.active_interfaces) == 3


def test_a_free_line_along_a_live_pile_is_refused():
    with pytest.raises(ValidationError, match=(
            "Slip runs along Sheet pile 1. Put it on Sheet pile 1 instead")):
        schemas.Project.model_validate(_with_interfaces([
            _interface(id="interface_2", name="Slip", structure=None,
                       points=[[12.0, -2.0], [12.0, -20.0]], side="left")]))
    # Crossing the pile, or along a switched-off one, is a free line like any other.
    schemas.Project.model_validate(_with_interfaces([
        _interface(id="interface_2", name="Slip", structure=None,
                   points=[[4.0, -2.0], [20.0, -6.0]], side="left")]))


def test_interfaces_are_plane_strain_only():
    payload = _with_interfaces([_interface()])
    payload["dimension"] = 3
    project = schemas.Project.model_validate(payload)

    assert project.interfaces, "the record is kept, like every other 2D record"
    assert project.active_interfaces == [], "but nothing is built from it in 3D"


# ── Normal loads ─────────────────────────────────────────────────────────────

def _normal_load(**overrides) -> dict:
    return {"id": "normal_1", "name": "River load", "kind": "normal",
            "points": [[8.0, 0.0], [8.0, -3.5], [20.0, -3.5]],
            "fluid_pressure_type": "Hydrostatic", "pressure": 0.0,
            "active": True} | overrides


def _with_normal_loads(records: list[dict]) -> dict:
    payload = seed_project(simple=False).model_dump()
    payload["dimension"] = 2
    payload["normal_loads"] = records
    return payload


def test_a_normal_load_defaults_to_the_magnitude_it_was_given():
    """Uniform, not hydrostatic: a load carrying a pressure has to apply it. The
    hydrostatic mode derives its pressure from the water level and ignores the field,
    which is right for water and wrong to fall into by default."""
    load = schemas.NormalLoad(**{k: v for k, v in _normal_load().items()
                                 if k != "fluid_pressure_type"})
    assert load.fluid_pressure_type == "Uniform"
    assert load.points == [(8.0, 0.0), (8.0, -3.5), (20.0, -3.5)]


def test_a_normal_load_can_be_a_fixed_uniform_pressure():
    load = schemas.NormalLoad(
        **_normal_load(fluid_pressure_type="Uniform", pressure=25.0))
    assert load.fluid_pressure_type == "Uniform"
    assert load.pressure == 25.0


def test_a_normal_load_needs_a_usable_polyline():
    for points in ([[8.0, 0.0]], [[8.0, 0.0], [8.0, 0.0]],
                  [[8.0, 0.0], [8.0, float("nan")]]):
        with pytest.raises(ValidationError):
            schemas.NormalLoad(**_normal_load(points=points))


def test_a_normal_load_rejects_a_non_finite_pressure():
    with pytest.raises(ValidationError):
        schemas.NormalLoad(**_normal_load(pressure=float("nan")))


def test_duplicate_normal_load_ids_are_rejected():
    with pytest.raises(ValidationError):
        schemas.Project.model_validate(
            _with_normal_loads([_normal_load(), _normal_load(name="Twin")]))


def test_a_normal_load_becomes_a_part_key_so_the_frontend_can_pick_it():
    project = schemas.Project.model_validate(_with_normal_loads([_normal_load()]))
    assert "normal_1" in project.part_keys()


def test_only_active_normal_loads_are_built():
    payload = _with_normal_loads([_normal_load(),
                                  _normal_load(id="normal_2", name="Off", active=False)])
    project = schemas.Project.model_validate(payload)
    assert [n.id for n in project.active_normal_loads] == ["normal_1"]


def test_normal_loads_are_plane_strain_only():
    payload = _with_normal_loads([_normal_load()])
    payload["dimension"] = 3
    project = schemas.Project.model_validate(payload)

    assert project.normal_loads, "the record is kept, like every other 2D record"
    assert project.active_normal_loads == [], "but nothing is built from it in 3D"


def test_asking_for_a_layer_asks_for_the_lifts_dug_out_of_it():
    """The Mesh dialog lists layers, not bodies (frontend/js/mesh-settings.js:73).

    A staged layer is several bodies, and naming the layer has to mean all of them --
    otherwise checking `Soil_Top` in that dialog meshes the retained side and silently
    leaves the whole excavation out of the model.
    """
    p = _layered_pit()
    assert set(p.expand_body_keys(["soil_L1"])) == {
        "soil_L1", "soil_L1__lift1", "soil_L1__lift2", "soil_L1__lift3"}
    assert p.expand_body_keys(["soil_L3"]) == ["soil_L3", "soil_L3__pit"]
    # Anything that is not a soil layer is passed through untouched.
    assert p.expand_body_keys(["wall", "soil_L2__pit"]) == ["wall", "soil_L2__pit"]


def test_expanding_body_keys_is_a_no_op_when_nothing_is_staged():
    p = seed_project(simple=False)
    keys = [f"soil_{layer.id}" for layer in p.layers]
    assert p.expand_body_keys(keys) == keys


def test_the_project_publishes_its_soil_body_keys():
    """The viewport cannot derive these for itself.

    It used to build its visible-soil list from `project.layers`, which named three
    bodies where a staged project has eight -- the five inside the pit were drawn and
    then left out of every mode, so the whole excavated side was invisible. Deriving it
    in the browser instead would be a second implementation of `soil_bodies` to keep in
    step, so the project says it.
    """
    p = _layered_pit()
    assert p.soil_body_keys == [key for key, *_ in p.soil_bodies()]
    assert len(p.soil_body_keys) == 8


def test_soil_body_keys_survive_a_round_trip():
    """It is published, not accepted: a client that sends the project back must not be
    rejected for echoing a field it was given."""
    p = _layered_pit()
    dumped = p.model_dump()
    assert "soil_body_keys" in dumped
    assert schemas.Project.model_validate(dumped).soil_body_keys == p.soil_body_keys


def test_a_project_with_no_ground_in_it_has_no_soil_bodies():
    """`part_keys` reads these, and runs during validation on the empty site the server
    opens on. Asking a project with no layers what bodies it has is not an error."""
    from core.model.templates import blank_project
    blank = blank_project()
    assert blank.soil_bodies() == []
    assert blank.soil_body_keys == []
    stripped = blank.model_dump() | {"layers": []}
    assert schemas.Project.model_validate(stripped).soil_bodies() == []


def test_a_load_cannot_take_a_staged_body_s_name():
    """One part-key namespace: a load named after a lift would collide in the deck."""
    p = _layered_pit().model_dump()
    p["loads"] = [{"id": "soil_L1__lift1", "name": "Surcharge", "kind": "line",
                   "x0": 0.0, "x1": 5.0, "y": 0.0, "components": [0.0, -10.0]}]
    with pytest.raises(ValidationError, match="collides"):
        schemas.Project.model_validate(p)


def test_each_soil_body_has_a_label_saying_which_part_of_its_layer_it_is():
    """The Model explorer lists bodies, and three keys that differ only by a `__lift2`
    suffix are not something to put in front of a user."""
    p = _layered_pit()
    labels = p.soil_body_labels
    assert set(labels) == set(p.soil_body_keys)
    assert labels["soil_L1"] == "Soil_1"
    assert labels["soil_L1__lift1"] == "Soil_1 · lift 1"
    assert labels["soil_L1__lift3"] == "Soil_1 · lift 3"
    assert labels["soil_L2__pit"] == "Soil_2 · below the pit"


def test_an_unstaged_layer_is_labelled_with_nothing_but_its_name():
    p = seed_project(simple=False)
    assert p.soil_body_labels == {f"soil_{l.id}": l.name for l in p.layers}


# ── Stages ──────────────────────────────────────────────────────────────────
#
# A construction stage, in the sense the GUI already draws (js/data.js:559) and
# the sense the reference deck's seven stages have. See
# plan/outdated/staged-construction-plan.md sec B1 for why a stage stores a *diff* against its
# parent rather than an absolute state.

def _staged(*stages) -> schemas.Project:
    return schemas.Project.model_validate(_layered_pit().model_dump() | {"stages": list(stages)})


def _stage(id_, parent=None, **kw) -> dict:
    return {"id": id_, "name": id_.replace("_", " ").title(), "parent": parent, **kw}


def test_a_project_has_no_stages_until_one_is_made():
    """The compatibility contract: an unstaged project is every project written before
    staged construction, and must behave exactly as it did."""
    assert seed_project(simple=False).stages == []


def test_a_stage_stores_what_it_changes_not_the_whole_model_state():
    p = _staged(
        _stage("initial", calculation="K0 procedure"),
        _stage("dig_1", parent="initial", deactivate=["soil_L1__lift1"]),
    )
    assert p.stages[1].deactivate == ["soil_L1__lift1"]
    assert p.stages[1].activate == []
    assert p.stages[0].calculation == "K0 procedure"
    # The defaults are the reference deck's own initial-stage numbers.
    assert p.stages[1].max_iterations == 15
    assert p.stages[1].reset_displacements is False


def test_the_first_stage_starts_from_nothing_and_the_rest_from_a_parent():
    with pytest.raises(ValidationError, match="root"):
        _staged(_stage("a", parent=None), _stage("b", parent=None))
    with pytest.raises(ValidationError, match="root"):
        _staged(_stage("a", parent="a"))


def test_a_stage_must_start_from_a_stage_that_exists():
    with pytest.raises(ValidationError, match="nowhere"):
        _staged(_stage("initial"), _stage("dig", parent="ghost"))


def test_stages_may_not_form_a_cycle():
    with pytest.raises(ValidationError, match="cycle|nowhere"):
        _staged(_stage("initial"), _stage("a", parent="b"), _stage("b", parent="a"))


def test_stage_ids_are_unique():
    with pytest.raises(ValidationError, match="duplicate"):
        _staged(_stage("initial"), _stage("initial", parent="initial"))


def test_a_stage_may_only_name_parts_the_model_has():
    with pytest.raises(ValidationError, match="no such part"):
        _staged(_stage("initial"), _stage("dig", parent="initial",
                                          deactivate=["soil_does_not_exist"]))


def test_a_stage_cannot_both_activate_and_deactivate_the_same_part():
    """Two contradictory instructions in one diff have no defined order."""
    with pytest.raises(ValidationError, match="both"):
        _staged(_stage("initial"),
                _stage("dig", parent="initial",
                       activate=["sheetpile"], deactivate=["sheetpile"]))


def test_a_stage_carries_the_solver_settings_the_reference_varies():
    """The three the reference deck actually changes between stages, and nothing else
    (plan sec 0.2): iterations, tolerance, and resetting displacements."""
    p = _staged(_stage("initial"),
                _stage("install", parent="initial", reset_displacements=True,
                       max_iterations=150, tolerated_error=1e-3))
    install = p.stages[1]
    assert (install.reset_displacements, install.max_iterations,
            install.tolerated_error) == (True, 150, 1e-3)


def test_stages_survive_a_round_trip():
    p = _staged(_stage("initial", calculation="K0 procedure"),
                _stage("dig", parent="initial", deactivate=["soil_L1__lift1"]))
    reloaded = schemas.Project.model_validate(p.model_dump())
    assert [ph.id for ph in reloaded.stages] == ["initial", "dig"]
    assert reloaded.stages[1].deactivate == ["soil_L1__lift1"]


# ── What a stage may name ───────────────────────────────────────────────────
# `part_keys` is the *render* namespace, in draw order, and a `layered_soil` project
# deliberately draws no load pads -- so its line loads are missing from it. They are
# still real parts of the deck, and the reference stages one (`Load` arrives with the
# wall and stays), so they have to be nameable in a stage. Hence a second, wider list.

def _simple_with_a_load() -> schemas.Project:
    p = _layered_pit().model_dump()
    p["layered_soil"] = True
    p["loads"] = [{"id": "surcharge", "name": "Load", "kind": "line",
                   "x0": 5.0, "x1": p["domain"]["x1"], "y": 0.0,
                   "components": [0.0, -20.0]}]
    p["normal_loads"] = [
        {"id": f"water_{n}", "name": f"WaterLoad_Stage{n}", "kind": "normal",
         "fluid_pressure_type": "Hydrostatic",
         "points": [[5.0, 0.0], [5.0, level], [0.0, level]]}
        for n, level in enumerate((-2.0, -5.0, -8.0), start=1)
    ]
    return schemas.Project.model_validate(p)


def test_a_load_the_viewport_never_draws_is_still_stageable():
    p = _simple_with_a_load()
    assert "surcharge" not in p.part_keys()
    assert "surcharge" in p.stageable_keys()


def test_everything_drawn_is_stageable():
    """The wider list is a superset, not a different list: a part that can be seen and
    not switched off would be a hole in the stage editor."""
    for project in (seed_project(simple=False), seed_project(simple=True),
                    _simple_with_a_load()):
        assert set(project.part_keys()) <= set(project.stageable_keys())
    assert len(set(p := _simple_with_a_load().stageable_keys())) == len(p)


def test_a_stage_may_switch_a_load_off_and_on_again():
    """This is how the reference stages water: `WaterLoad_Stage2` arrives as
    `WaterLoad_Stage1` leaves. No separate per-load stage field -- the diff already
    says it, and two mechanisms for one question is one authority too many."""
    p = schemas.Project.model_validate(
        _simple_with_a_load().model_dump() | {"stages": [
            _stage("initial", deactivate=["surcharge", "water_2"]),
            _stage("build", parent="initial", activate=["surcharge"]),
            _stage("dig", parent="build",
                   activate=["water_2"], deactivate=["water_1"]),
        ]})
    assert p.stages[2].activate == ["water_2"]


# ── layered_soil (was simple_example) ───────────────────────────────────────
# The rename is `plan/outdated/staged-construction-plan.md` sec 7.14: the flag never meant "this
# model is simple", it meant "build the soil out of the layer stack and whatever the
# user drew, rather than raising the seeded demo wall ring, strut frame and pile group".
# A real staged excavation sets it on a model nobody would call simple, which is what
# made the old name worth the churn.

def test_layered_soil_accepts_the_old_simple_example_name():
    """Every project file written before the rename carries `simple_example`.

    Backwards compatibility is the hard requirement in sec 7.18, and a saved project is
    the one artefact this application cannot re-derive, so the old spelling stays
    readable for good rather than for a deprecation window.
    """
    # The full-build seed, because `layered_soil=False` is the path that reads the
    # excavation block, and the simple seed's placeholder pit is outside its domain.
    payload = seed_project(simple=False).model_dump()
    payload.pop("layered_soil", None)
    payload["simple_example"] = False
    assert schemas.Project.model_validate(payload).layered_soil is False

    payload = seed_project().model_dump()
    payload.pop("layered_soil", None)
    payload["simple_example"] = True
    assert schemas.Project.model_validate(payload).layered_soil is True


def test_layered_soil_round_trips_under_its_new_name():
    payload = seed_project().model_dump()
    assert payload["layered_soil"] is True
    assert "simple_example" not in payload
    assert schemas.Project.model_validate(payload).layered_soil is True


def test_the_two_names_may_not_disagree():
    """Sent both, and differing, the payload does not say which the caller meant.

    Same reasoning as `Excavation._reconcile_floor_and_levels`: two fields describing
    one thing are reconciled on the way in, and an irreconcilable pair is refused
    rather than silently resolved to whichever pydantic happens to read last.
    """
    payload = seed_project().model_dump()
    payload["simple_example"] = False
    with pytest.raises(ValidationError, match="simple_example"):
        schemas.Project.model_validate(payload)


def test_the_two_names_agreeing_is_accepted():
    payload = seed_project().model_dump()
    payload["simple_example"] = payload["layered_soil"]
    assert schemas.Project.model_validate(payload).layered_soil is True


# ── The seeded demo's blocks are optional ───────────────────────────────────
# The excavation, wall, struts, anchor rows, piles and wells: a model that has none of
# them leaves them out, and only the full build, which raises them, needs them given.

def _without_demo_blocks(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in schemas.FULL_BUILD_BLOCKS}


def test_a_layered_model_needs_none_of_the_demo_blocks():
    project = schemas.Project.model_validate(_without_demo_blocks(seed_project().model_dump()))
    assert all(getattr(project, name) is None for name in schemas.FULL_BUILD_BLOCKS)
    assert project.pit_levels() == []
    # No pit, so no lifts: one body per layer, as with a pit of one level.
    assert project.soil_bodies() == seed_project().soil_bodies()
    with pytest.raises(ValueError, match="no excavation"):
        project.pit()


def test_the_full_build_needs_every_demo_block():
    payload = seed_project(simple=False).model_dump()
    del payload["struts"], payload["wells"]
    with pytest.raises(ValidationError, match="needs struts, wells"):
        schemas.Project.model_validate(payload)


def test_a_model_saved_with_placeholder_blocks_still_opens():
    """What every project and model script written before the blocks were optional
    carries: empty demo structures with made-up sizes."""
    payload = _without_demo_blocks(seed_project().model_dump()) | {
        "excavation": {"x0": 0.0, "x1": 1.0, "z0": 0.0, "z1": 1.0, "levels": [-1.0]},
        "wall": {"thickness": 0.5, "top_y": 0.0, "toe_y": -1.0},
        "struts": {"xs": [], "y": 0.0, "radius": 0.1},
        "anchor_rows": {"xs": [], "head_y": 0.0, "length": 1.0, "inclination_deg": 45.0,
                        "radius": 0.1},
        "piles": {"xs": [], "zs": [], "radius": 0.1, "length": 1.0, "top_y": 0.0},
        "wells": {"positions": [], "radius": 0.1, "top_y": 0.0, "length": 1.0},
    }
    project = schemas.Project.model_validate(payload)
    assert project.struts is not None and project.struts.xs == []
    assert project.pit_levels() == [-1.0]


@pytest.mark.parametrize("record, changes, message", [
    ("PointLoad", {"components": [float("nan"), 0]}, "components must be finite"),
    ("LineLoad", {"x0": 2, "x1": 1}, "extents must be strictly increasing"),
    ("LineLoad", {"y": float("inf")}, "coordinates must be finite"),
    ("LineLoad", {"components": [0, float("inf")]}, "components must be finite"),
    ("Anchor", {"prestress": float("nan")}, "non-finite prestress"),
    ("SpaceAnchor", {"head": [0, 0, float("inf")]}, "non-finite coordinate"),
    ("SpaceAnchor", {"tail": [0, 0, 0]}, "non-zero length"),
    ("SpaceAnchor", {"prestress": float("inf")}, "non-finite prestress"),
    ("Panel", {"footprint": [[0, 0]]}, "at least two points"),
    ("Panel", {"y_toe": float("-inf")}, "non-finite level"),
    ("NormalLoad", {"points": [[0, 0]]}, "at least two points"),
    ("NormalLoad", {"reference_coordinate": float("inf")}, "non-finite water level"),
    ("WaterPressureCondition", {"value": float("nan")}, "non-finite value"),
    ("WaterPressureCondition", {"z_coordinates": [0, 0]}, "z_coordinates but no"),
    ("WaterPressureCondition", {"x_coordinates": [0, 1], "y_coordinates": [0, 0],
                                "z_coordinates": [0]}, "as many x as y"),
    ("WaterPressureCondition", {"on": "point", "points": [[float("inf"), 0]]},
     "non-finite coordinate"),
])
def test_schema_refuses_invalid_structural_and_hydraulic_inputs(record, changes, message):
    fields = {
        "PointLoad": {"x": 0, "y": 0, "components": [0, -1]},
        "LineLoad": {"x0": 0, "x1": 1, "y": 0, "components": [0, -1]},
        "Anchor": {"section": "section", "head": [0, 0], "tail": [1, -1]},
        "SpaceAnchor": {"section": "section", "head": [0, 0, 0], "tail": [1, -1, 0]},
        "Panel": {"section": "section", "footprint": [[0, 0], [1, 0]],
                  "y_top": 0, "y_toe": -5},
        "NormalLoad": {"points": [[0, 0], [0, -1]]},
        "WaterPressureCondition": {"on": "domain", "fluid_pressure_type": "Uniform"},
    }

    schema = getattr(schemas, record)
    valid = {"id": "test", "name": "Test"} | fields[record]
    schema.model_validate(valid)
    with pytest.raises(ValidationError, match=message):
        schema.model_validate(valid | changes)


def test_an_excavation_requires_increasing_plan_extents():
    with pytest.raises(ValidationError, match="extents must be strictly increasing"):
        schemas.Excavation(x0=1, x1=1, z0=0, z1=2, levels=[-1])


def test_a_demo_wall_requires_its_top_above_its_toe():
    with pytest.raises(ValidationError, match="wall top must be above its toe"):
        schemas.Wall(thickness=0.5, top_y=-2, toe_y=-1)


def test_drawn_conditions_are_retained_but_not_embedded_in_a_3d_project():
    payload = blank_project().model_dump()
    payload["boundary_conditions"] = [{
        "id": "point_pressure", "name": "Point pressure", "kind": "water_pressure",
        "on": "point", "points": [[0, 0]], "fluid_pressure_type": "Uniform",
    }]
    section = schemas.Project.model_validate(payload)
    spatial = schemas.Project.model_validate(payload | {"dimension": 3})

    assert [condition.id for condition in section.drawn_conditions] == ["point_pressure"]
    assert [condition.id for condition in spatial.boundary_conditions] == ["point_pressure"]
    assert spatial.drawn_conditions == []


def test_interfaces_on_different_piles_may_hold_the_same_depth_range():
    payload = excavation_project(staged=False).model_dump()
    payload["beams"].append({
        **payload["beams"][0], "id": "second_pile", "name": "Second pile",
        "points": [(12, 0), (12, -12)],
    })
    payload["interfaces"].append({
        **payload["interfaces"][0], "id": "second_contact", "name": "Second contact",
        "structure": "second_pile",
    })

    project = schemas.Project.model_validate(payload)

    assert len(project.active_interfaces) == 2
    assert project.interface_path(project.interfaces[0]) == [(6, 0), (6, -12)]
    assert project.interface_path(project.interfaces[1]) == [(12, 0), (12, -12)]


def test_an_anchor_id_cannot_overwrite_a_load_in_the_part_namespace():
    payload = excavation_project(staged=False).model_dump()
    payload["anchors"][0]["id"] = "surcharge"

    with pytest.raises(ValidationError, match="anchor id collides.*surcharge"):
        schemas.Project.model_validate(payload)


@pytest.mark.parametrize("section_type, old, variable, expected, fields", [
    (schemas.BeamSection, {"E": 200000000, "nu": 0.3, "density": 7850,
                           "area": 0.02, "inertia": 0.001, "spacing": 2},
     "YOUNG_MODULUS", 2e11, {"spacing": 2}),
    (schemas.AnchorSection, {"E": 200000000, "density": 7850, "area": 0.002,
                             "spacing": 2, "tension_limit": 900},
     "YOUNG_MODULUS", 2e11, {"spacing": 2, "tension_limit": 900000}),
    (schemas.PanelSection, {"E": 30000000, "nu": 0.2, "density": 2400, "thickness": 0.4},
     "THICKNESS", 0.4, {}),
])
def test_old_script_section_constructors_migrate_and_round_trip(
        section_type, old, variable, expected, fields):
    section = section_type.model_validate({"id": "profile", "name": "Profile", **old})

    assert section.variables[variable] == expected
    assert {name: getattr(section, name) for name in fields} == fields
    assert section_type.model_validate(section.model_dump()) == section


@pytest.mark.parametrize("levels, message", [
    ([-2, -2], "levels must descend"),
    ([-4, -2], "levels must descend"),
    ([-2, float("-inf")], "levels must all be finite"),
])
def test_excavation_lifts_must_represent_successively_deeper_finite_floors(levels, message):
    with pytest.raises(ValidationError, match=message):
        schemas.Excavation(x0=0, x1=5, z0=0, z1=5, levels=levels)
