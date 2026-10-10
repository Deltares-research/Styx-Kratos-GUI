"""Units: the deck carries the project's own numbers, in the project's own system.

Kratos has no units; it needs one consistent set, gravity in it. The project names the
set (`Project.unit_system`, `app/units.py`) and holds what Kratos reads -- property sets
under Kratos' names -- so the deck is the project's numbers, written as they stand.

Until 2026-10-10 the project was in kN, kN/m2 and m/day and the exporter converted
everything on the way out, which went wrong once in the most expensive way: `DENSITY_SOLID`
converted and nothing else, so one materials file carried two unit systems. There is now
nothing to convert, and an old project is converted once, on load (`app/legacy.py`).

The reference files are the authority, and they have been run:

    initial_materials_for_generated_mesh.json
    MaterialParameters_for_generated_mesh.json
    staged_construction_for_generated_mesh.json

`app/crow.py` is built to be the same model, in the reference's own SI numbers, so the
values below are the reference's -- and the test is that we reproduce them.
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

DENSITY = {"SI": 1000.0, "kN": 1.0}
"""Water's density, kg/m3 and t/m3: a density a thousand times off for its system is the
1000x slip deck rule 11 exists to catch, so each system gets its own."""


def _round_numbers(unit_system: str) -> dict:
    """A 2D project whose soils and load are round numbers, typed in `unit_system`."""
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=20.0, unit_system=unit_system)
    for material in payload["materials"]:
        material["variables"].update(YOUNG_MODULUS=1000.0, GEO_COHESION=2000.0,
                                     DENSITY_SOLID=DENSITY[unit_system])
    payload["loads"] = [{"id": "l", "name": "L", "kind": "line", "x0": 1.0, "x1": 4.0,
                         "y": 0.0, "components": [0.0, -3000.0], "active": True}]
    return payload


@pytest.mark.parametrize("unit_system", ["SI", "kN"])
def test_the_deck_carries_the_numbers_as_typed(unit_system):
    """In either system: Kratos reads the project's numbers, so there is nothing to
    convert -- a 1000 typed is a 1000 written."""
    project = Project.model_validate(_round_numbers(unit_system))
    with session():
        exported = kratos.export_project(project, MeshRequest(element_size=6.0, order=1))
    soil = next(iter(json.loads(exported["materials"])["properties"]))["Material"][
        "Variables"]
    assert soil["YOUNG_MODULUS"] == 1000.0
    assert soil["GEO_COHESION"] == 2000.0
    assert soil["DENSITY_SOLID"] == DENSITY[unit_system]
    assert _parameters(exported, "apply_vector_constraint_table_process", ".L")[
        "value"] == [0.0, -3000.0, 0.0]
    assert exported["unit_system"] == unit_system


def test_nothing_between_the_project_and_the_deck_converts_a_unit():
    """There used to be a `KILO` at a dozen sites. The only conversions left are of
    constants of nature the exporter supplies for a soil that says nothing (water's
    bulk modulus, its viscosity), expressed in the project's system."""
    import inspect
    from app import kratos_processes
    for module in (kratos_materials, kratos_processes, kratos):
        assert "KILO" not in inspect.getsource(module), module.__name__


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
    """`K0_NC` overrides `1 - sin(phi)`. The reference's 0.62 and 0.46 happen to be Jaky
    at its friction angles, but a user who types 0.62 gets 0.62, not 0.6205 -- in the
    K0 stage's file, and only there."""
    project = crow.crow_project(staged=True)
    with session():
        exported = kratos.export_project(project, MeshRequest(element_size=8.0, order=2))
    initial = {e["model_part_name"]: e["Material"]["Variables"]
               for e in json.loads(exported["initial_materials"])["properties"]}
    assert initial["PorousDomain.Soil_Top"]["K0_NC"] == 0.62
    assert initial["PorousDomain.Soil_Bottom"]["K0_NC"] == 0.46
    later = {e["model_part_name"]: e["Material"]["Variables"]
             for e in json.loads(exported["materials"])["properties"]}
    assert "K0_NC" not in later["PorousDomain.Soil_Top"]


def test_porosity_is_the_materials_own(exported):
    """It was a fixed 0.3 for every soil in every project. The reference uses 0.0 for
    both of its soils, which is a property of the ground, not of the exporter."""
    assert variables(exported, "Soil_Top")["POROSITY"] == 0.0
    assert variables(exported, "Soil_Bottom")["POROSITY"] == 0.0


def _bare(**variables) -> schemas.Material:
    return schemas.Material(id="m", name="M", color="#808080",
                            constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                            variables={"YOUNG_MODULUS": 1.0e7, "POISSON_RATIO": 0.3,
                                       "DENSITY_SOLID": 1800.0, **variables})


def test_a_material_that_says_nothing_about_porosity_still_gets_a_number():
    """Derived when empty, and said: the export lists every name it filled in."""
    project = seed_project()
    derived: list[str] = []
    written = kratos_materials._variables(_bare(), 2, False, project, derived)
    assert written["POROSITY"] == kratos_materials.DEFAULT_POROSITY
    assert "material 'M': POROSITY" in derived
    typed = kratos_materials._variables(_bare(POROSITY=0.0), 2, False, project, [])
    assert typed["POROSITY"] == 0.0


@pytest.mark.parametrize("unit_system, bulk", [("SI", 1.0e10), ("kN", 1.0e7)])
def test_the_constants_a_soil_leaves_out_are_in_the_projects_system(unit_system, bulk):
    project = seed_project().model_copy(update={"unit_system": unit_system})
    written = kratos_materials._variables(_bare(), 2, False, project, [])
    assert written["BULK_MODULUS_SOLID"] == pytest.approx(bulk)
    # Water's density from the project's own water: 10 kN/m3 over g, in its system.
    expected = 10_000.0 / 9.81 if unit_system == "SI" else 10.0 / 9.81
    assert written["DENSITY_WATER"] == pytest.approx(expected)


@pytest.mark.parametrize("typed, expected", [
    ({}, "CONSTANT_PW_FIELD"),
    ({"GEO_DRAINAGE_TYPE": "FULLY_COUPLED"}, "FULLY_COUPLED"),
    ({"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}, "CONSTANT_PW_FIELD"),
])
def test_the_drainage_type_is_the_materials_own(typed, expected):
    """As typed; a soil that says nothing is drained -- the pore pressure prescribed,
    not solved for -- which is what the reference's soils are."""
    written = kratos_materials._variables(_bare(**typed), 2, False, seed_project(), [])
    assert written["GEO_DRAINAGE_TYPE"] == expected


def test_the_crow_soils_are_written_as_a_constant_pressure_field(exported):
    assert variables(exported, "Soil_Top")["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"


def test_a_tendon_may_be_massless(exported):
    """`AnchorSection.density` was `gt=0`, so the reference's 0.0 could not be typed at
    all -- a prestressed tendon whose own weight is beside the point is an ordinary
    thing to model."""
    assert variables(exported, "Strut")["DENSITY"] == 0.0


# ── The derived-variables notice ─────────────────────────────────────────

def test_the_notice_names_what_was_derived_and_nothing_else():
    """A property set that gives everything gets no notice; one that leaves a value out
    is named with it, so the user can see what the deck decided."""
    project = crow.crow_project(staged=False)
    with session():
        exported = kratos.export_project(project, MeshRequest(element_size=8.0, order=2))
    notices = [w for w in exported["warnings"] if w.startswith("Derived where")]
    assert len(notices) == 1
    assert "material" not in notices[0], "CROW's soils give every variable"
    assert "interface section 'Wall contact': INTERFACE_SHEAR_STIFFNESS" in notices[0]
