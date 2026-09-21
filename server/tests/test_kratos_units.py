"""Units: the project is kN-based, the deck is SI, and the conversion happens once.

`app/schemas.py` says it in its first paragraph -- "Units throughout are m / kN / day" --
because kN/m2 and kN/m3 are what a geotechnical engineer types. Kratos reads the deck in
SI: densities in kg/m3, gravity in m/s2, and therefore stresses in Pa and forces in N. So
everything with a force in it is multiplied by 1000 on the way out.

This was wrong until it was measured against the reference deck. `DENSITY_SOLID` was
converted (unit weight / g) and nothing else was, so one materials file carried two unit
systems: soil 1000x too soft, water pressures 1000x too small, and a surcharge of 20 N/m
where 20 kN/m was meant.

The reference files are the authority, and they have been run:

    initial_materials_for_generated_mesh.json
    MaterialParameters_for_generated_mesh.json
    staged_construction_for_generated_mesh.json

`examples/crow/crow.py` is built to be the same model, so the numbers below are not "what the code
happens to produce" -- they are the reference's own values, and the test is that we
reproduce them.
"""

import json

import pytest

from app import kratos, kratos_materials, schemas
from tests.crow_example import crow, reference as example_file
from app.build import session
from app.schemas import MeshRequest, Project
from app.seed import seed_project



@pytest.fixture(scope="module")
def exported() -> dict:
    project = crow.crow_project()
    with session():
        return kratos.export_project(project,
                                     MeshRequest(**project.mesh.model_dump()))


def variables(exported: dict, part: str) -> dict:
    entry = next(e for e in json.loads(exported["materials"])["properties"]
                 if e["model_part_name"] == f"PorousDomain.{part}")
    return entry["Material"]["Variables"]


# -- The soil ----------------------------------------------------------------
# Reference property sets 1 and 2. `examples/crow/crow.py` types the same two materials in kN/m2,
# so these are the reference's numbers reached from the project's own input.

def test_the_soil_stiffness_is_written_in_pascals(exported):
    assert variables(exported, "Soil_Top")["YOUNG_MODULUS"] == pytest.approx(9.0e5)
    assert variables(exported, "Soil_Bottom")["YOUNG_MODULUS"] == pytest.approx(7.4286e6)


def test_a_lift_keeps_the_stiffness_of_the_layer_it_was_dug_from(exported):
    assert variables(exported, "Soil_Top_lift1")["YOUNG_MODULUS"] == \
        variables(exported, "Soil_Top")["YOUNG_MODULUS"]


def test_the_solid_density_is_the_unit_weight_at_g(exported):
    """This one was always right, and it is what pins the deck as SI: it only agrees
    with the reference because both are kg/m3."""
    assert variables(exported, "Soil_Top")["DENSITY_SOLID"] == pytest.approx(1834.86,
                                                                            rel=1e-5)
    assert variables(exported, "Soil_Bottom")["DENSITY_SOLID"] == pytest.approx(2038.74,
                                                                               rel=1e-5)


def test_the_water_density_follows_the_projects_own_specific_weight(exported):
    """1019.37 kg/m3 is 10 kN/m3 at g, which is the reference's number and the same
    `Project.water.specific_weight` the two water processes read. It was a flat 1000.0
    before, so a project whose water was not exactly 9.81 kN/m3 described it one way in
    the materials file and another in the processes."""
    assert variables(exported, "Soil_Top")["DENSITY_WATER"] == pytest.approx(1019.37,
                                                                            rel=1e-5)


def test_the_bulk_moduli_are_the_references_own(exported):
    soil = variables(exported, "Soil_Top")
    assert soil["BULK_MODULUS_SOLID"] == pytest.approx(1.0e10)
    assert soil["BULK_MODULUS_FLUID"] == pytest.approx(2.2e9)


def test_cohesion_is_written_in_pascals(exported):
    """`Material.c` is kN/m2 like `E`, and was written raw for the same reason."""
    assert variables(exported, "Soil_Top")["GEO_COHESION"] == pytest.approx(1.0e3)


# -- The structures ----------------------------------------------------------

def test_the_sheet_pile_stiffness_is_written_in_pascals(exported):
    assert variables(exported, "SheetPileWall")["YOUNG_MODULUS"] == \
        pytest.approx(8.4449e9)


def test_the_tendon_stiffness_is_written_in_pascals(exported):
    assert variables(exported, "Strut")["YOUNG_MODULUS"] == pytest.approx(2.1e11)


def test_areas_and_thicknesses_are_metres_and_are_not_scaled(exported):
    """Only the force carries a kilo. A length, an area and an angle do not, and
    multiplying them too would be the easiest way to get this half right."""
    assert variables(exported, "Strut")["CROSS_AREA"] == pytest.approx(4.7619e-5)
    # The section area of the wall. The reference calls it `THICKNESS`, because its beam
    # law is `TimoshenkoBeamPlaneStrainElasticConstitutiveLaw` where ours is
    # `TimoshenkoBeamElasticConstitutiveLaw`; the number is the same 0.4924 m2/m either
    # way, and which law to write is a separate question from what units it is in.
    assert variables(exported, "SheetPileWall")["CROSS_AREA"] == pytest.approx(0.4924)
    assert variables(exported, "Soil_Top")["GEO_FRICTION_ANGLE"] == pytest.approx(22.3)


def test_the_beam_density_is_already_si_and_is_left_alone(exported):
    """`BeamSection.density` is documented kg/m3, not kN/m3, so it crosses unchanged."""
    assert variables(exported, "SheetPileWall")["DENSITY"] == pytest.approx(298.36)


# -- The processes -----------------------------------------------------------

def _parameters(exported: dict, module: str, ends_with: str) -> dict:
    doc = json.loads(exported["project_parameters"])
    stage = next(iter(doc["stages"].values()))["stage_settings"]["processes"]
    for listing in stage.values():
        for process in listing:
            if (process["python_module"] == module
                    and process["Parameters"]["model_part_name"].endswith(ends_with)):
                return process["Parameters"]
    raise AssertionError(f"no {module} on {ends_with}")


def test_a_line_load_is_written_in_newtons_per_metre(exported):
    """The reference's `Load` is `[0.0, -20000.0, 0.0]` for the 20 kN/m surcharge
    `examples/crow/crow.py` types."""
    doc = json.loads(exported["project_parameters"])
    stage = doc["stages"]["3_SheetPileWall_installation"]["stage_settings"]["processes"]
    (load,) = [p for p in stage["loads_process_list"]
               if p["Parameters"]["model_part_name"].endswith(".Load")]
    assert load["Parameters"]["value"] == [0.0, -20000.0, 0.0]


def test_both_water_processes_use_newtons_per_cubic_metre(exported):
    """10000.0, the reference's own, from `Project.water.specific_weight` of 10 kN/m3."""
    doc = json.loads(exported["project_parameters"])
    for stage in doc["stages"].values():
        processes = stage["stage_settings"]["processes"]
        hydrostatic = [p["Parameters"] for listing in processes.values()
                       for p in listing
                       if p["Parameters"].get("fluid_pressure_type") == "Hydrostatic"]
        assert hydrostatic
        for parameters in hydrostatic:
            assert parameters["specific_weight"] == pytest.approx(1.0e4)
            assert parameters["reference_coordinate"] == pytest.approx(-1.5)


def test_gravity_is_not_scaled(exported):
    """It is an acceleration in m/s2, not a force in kN, and it was already SI. Scaling
    everything in the loads list would have taken it with the rest."""
    doc = json.loads(exported["project_parameters"])
    for stage in doc["stages"].values():
        (body,) = [p for p in stage["stage_settings"]["processes"]["loads_process_list"]
                   if p["Parameters"]["variable_name"] == "VOLUME_ACCELERATION"]
        assert body["Parameters"]["value"] == [0.0, -9.81, 0.0]


# -- The rule, stated on its own ---------------------------------------------

def test_one_kilonewton_of_anything_leaves_as_a_thousand_newtons():
    """Stated against a project of round numbers, so the rule is readable without
    holding the CROW model in your head."""
    # 2D: a line load has no Kratos condition in a 3D deck, so it would be dropped
    # before it could carry a unit anywhere.
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=20.0)
    for material in payload["materials"]:
        material |= {"E": 1.0, "c": 2.0, "g_unsat": 9.81, "g_sat": 9.81}
    payload["loads"] = [{"id": "l", "name": "L", "kind": "line", "x0": 1.0, "x1": 4.0,
                         "y": 0.0, "components": [0.0, -3.0], "active": True}]
    project = Project.model_validate(payload)
    with session():
        exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    soil = next(iter(json.loads(exported["materials"])["properties"]))["Material"][
        "Variables"]
    assert soil["YOUNG_MODULUS"] == pytest.approx(1000.0)
    assert soil["GEO_COHESION"] == pytest.approx(2000.0)
    # 9.81 kN/m3 at g = 1000 kg/m3: the conversion that was always there.
    assert soil["DENSITY_SOLID"] == pytest.approx(1000.0)
    assert _parameters(exported, "apply_vector_constraint_table_process", ".L")[
        "value"] == [0.0, -3000.0, 0.0]


def test_the_conversion_is_one_named_constant():
    """Not a 1000 written out at each site. There are a dozen of them and the next one
    added is the one that gets forgotten."""
    assert kratos_materials.KILO == 1000.0


# -- The interfaces ----------------------------------------------------------
# Reference property sets 3 and 4. Their stiffnesses are what pinned the derivation:
# `G / t` at `t = 1`, and a normal ten times the shear at two different Poisson ratios.

def test_each_interface_takes_the_stiffness_of_the_soil_behind_it(exported):
    """The reference splits its contacts in two -- those against the upper ground and
    those against the deeper sand -- and gives each the shear modulus of that soil."""
    upper = variables(exported, "Interface_Soil_Top")
    lower = variables(exported, "Interface_Soil_Bottom")
    assert upper["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(3.75e5, rel=1e-4)
    assert upper["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(3.75e6, rel=1e-4)
    assert lower["INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(2.8571e6, rel=1e-4)
    assert lower["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(2.8571e7, rel=1e-4)


def test_a_lifts_contact_takes_the_layer_it_was_dug_from(exported):
    """`Interface_Soil_Top_lift1` is the reference's `Interface_Excavated_Soil_1`, and
    sits in its upper-ground group."""
    for part in ("Interface_Soil_Top_lift1", "Interface_Soil_Top_lift2",
                 "Interface_Soil_Top_lift3", "Interface_Soil_Middle_pit"):
        assert variables(exported, part)["INTERFACE_SHEAR_STIFFNESS"] == \
            pytest.approx(3.75e5, rel=1e-4)
    assert variables(exported, "Interface_Soil_Bottom_pit")[
        "INTERFACE_SHEAR_STIFFNESS"] == pytest.approx(2.8571e6, rel=1e-4)


# -- What the user typed, not what the exporter assumed ----------------------
# Four values the reference deck carries that this exporter used to decide for itself.
# The rule Marjan gave: the user is responsible for the values, so where a material
# carries one it is written, and the derived default is only for when it does not.


def test_a_typed_k0_is_written_instead_of_jaky():
    """`Material.k0_nc` overrides `1 - sin(phi)`. The reference's 0.62 and 0.46 happen to
    be Jaky at its friction angles, but a user who types 0.62 gets 0.62, not 0.6205."""
    project = crow.crow_project(staged=False)
    assert project.material("m_upper").k0_normally_consolidated() == 0.62
    assert project.material("m_lower").k0_normally_consolidated() == 0.46


def test_porosity_is_the_materials_own(exported):
    """It was a fixed 0.3 for every soil in every project. The reference uses 0.0 for
    both of its soils, which is a property of the ground, not of the exporter."""
    assert variables(exported, "Soil_Top")["POROSITY"] == 0.0
    assert variables(exported, "Soil_Bottom")["POROSITY"] == 0.0


def test_a_material_that_says_nothing_about_porosity_still_gets_a_number():
    """Every project written before the field existed, which must keep exporting."""
    material = schemas.Material(id="m", name="M", model="Linear Elastic",
                                type="Drained", color="#808080", g_unsat=18.0,
                                g_sat=20.0, E=1.0e4, nu=0.3, k=1.0)
    assert material.porosity is None
    assert kratos_materials._variables(material, 2)["POROSITY"] ==         kratos_materials.DEFAULT_POROSITY


@pytest.mark.parametrize("drainage, expected", [
    ("Drained", "CONSTANT_PW_FIELD"),
    ("Non-porous", "CONSTANT_PW_FIELD"),
    ("Undrained (A)", "FULLY_COUPLED"),
    ("Undrained (B)", "FULLY_COUPLED"),
])
def test_the_drainage_type_follows_the_materials_own(drainage, expected):
    """`Material.type` is already the drainage vocabulary the GUI shows. A
    drained analysis prescribes the pore pressure field rather than solving for it, so
    it is `CONSTANT_PW_FIELD`; only a material that generates excess pore pressure is
    fully coupled. This used to send everything but `Non-porous` to `FULLY_COUPLED`."""
    material = schemas.Material(id="m", name="M", model="Linear Elastic",
                                type=drainage, color="#808080", g_unsat=18.0,
                                g_sat=20.0, E=1.0e4, nu=0.3, k=1.0)
    assert kratos_materials._variables(material, 2)["GEO_DRAINAGE_TYPE"] == expected


def test_the_crow_soils_are_written_as_a_constant_pressure_field(exported):
    assert variables(exported, "Soil_Top")["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"


def test_a_tendon_may_be_massless(exported):
    """`AnchorSection.density` was `gt=0`, so the reference's 0.0 could not be typed at
    all -- a prestressed tendon whose own weight is beside the point is an ordinary
    thing to model."""
    assert variables(exported, "Strut")["DENSITY"] == 0.0
