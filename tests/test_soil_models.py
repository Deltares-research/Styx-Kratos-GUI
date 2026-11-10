"""`core.model.soil_models`: the soil models a material can be, and what follows.

A soil model is a law per dimension and the parameters the material window lists for it,
with their defaults. The project keeps the law in step with its dimension and its current
name; a new soil, a model change and a choice changed fill in the defaults of what the
soil now lists; the export refuses a soil its law cannot run, naming why.
"""

from __future__ import annotations

import json
import math

import pytest

from core import session
from core.kratos import materials
from core.kratos.materials import MaterialError
from core.model import drafts, migration, soil_models, units
from core.model.schemas import DimensionUpdate, InterfaceSection, Material, Project
from core.model.templates import blank_project, seed_project

MC_2D, MC_3D = soil_models.law(soil_models.MOHR_COULOMB, 2), soil_models.law(
    soil_models.MOHR_COULOMB, 3)
ELASTIC_2D = soil_models.law(soil_models.LINEAR_ELASTIC, 2)


def names(parameters: list[soil_models.Parameter]) -> list[str]:
    return [p.name for p in parameters]


def mohr_coulomb_site(**variables) -> Project:
    """The seed section with its first soil made a default Mohr-Coulomb one."""
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    project = session.update_material(project, "m2", model=soil_models.MOHR_COULOMB)
    if variables:
        project = session.update_material(project, "m2", variables=variables)
    return project


def deck(project: Project, k0: bool = False) -> dict:
    text, _ = materials.material_parameters(project, [("Soil_1", "m2")], 2, k0=k0)
    return json.loads(text)["properties"][0]["Material"]


# ── The catalogue ───────────────────────────────────────────────────────────

def test_the_mohr_coulomb_laws_are_the_ones_kratos_registers_now():
    assert (MC_2D, MC_3D) == ("GeoMohrCoulombLawPlaneStrain", "GeoMohrCoulombLaw3D")
    assert soil_models.model_of("GeoMohrCoulombWithTensionCutOff2D") == soil_models.MOHR_COULOMB
    assert soil_models.model_of("SmallStrainUDSM2DPlaneStrainLaw") == soil_models.OTHER
    assert soil_models.law_dimension("GeoMohrCoulombWithTensionCutOff3D") == 3


def test_a_new_mohr_coulomb_soil_holds_what_its_law_reads():
    defaults = soil_models.defaults_si(soil_models.MOHR_COULOMB)

    assert defaults["GEO_COHESION"] == 1000.0
    assert defaults["GEO_FRICTION_ANGLE"] == 30.0
    assert defaults["GEO_DILATANCY_ANGLE"] == 0.0
    assert defaults["GEO_ENABLE_TENSION_CUT_OFF"] is False
    assert defaults["RETENTION_LAW"] == "SaturatedBelowPhreaticLevelLaw"
    assert (defaults["SATURATED_SATURATION"], defaults["RESIDUAL_SATURATION"]) ==         (1.0, 1.0e-10)
    assert "GEO_TENSILE_STRENGTH" not in defaults, "the cut-off is off"
    assert "MINIMUM_RELATIVE_PERMEABILITY" not in defaults, "a drained soil has no flow"
    assert soil_models.required(MC_2D, defaults) == [
        "YOUNG_MODULUS", "POISSON_RATIO", "DENSITY_SOLID", "POROSITY", "GEO_COHESION",
        "GEO_FRICTION_ANGLE", "GEO_DILATANCY_ANGLE"]
    assert soil_models.problem(MC_2D, defaults) is None


def test_a_new_linear_elastic_soil_is_the_sand_saturated_below_the_phreatic_level():
    assert soil_models.defaults_si(soil_models.LINEAR_ELASTIC) == {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 1.0e7,
        "POISSON_RATIO": 0.3, "DENSITY_SOLID": 17000 / 9.81, "POROSITY": 0.0,
        "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw", "SATURATED_SATURATION": 1.0,
        "RESIDUAL_SATURATION": 1.0e-10}


def test_a_linear_elastic_soil_lists_no_strength_and_a_mohr_coulomb_one_does():
    elastic = names(soil_models.shown(soil_models.LINEAR_ELASTIC, {}))
    plastic = names(soil_models.shown(soil_models.MOHR_COULOMB, {}))

    assert not {"GEO_COHESION", "GEO_FRICTION_ANGLE"} & set(elastic)
    assert {"GEO_COHESION", "GEO_FRICTION_ANGLE"} <= set(plastic)


def test_no_soil_lists_the_water_which_is_the_project_s():
    for model in soil_models.MODELS:
        assert not set(soil_models.WATER) & set(names(soil_models.parameters(model)))


@pytest.mark.parametrize("drainage, listed", [
    ("CONSTANT_PW_FIELD", False), ("FULLY_COUPLED", True)])
def test_the_flow_parameters_are_listed_for_a_coupled_soil_only(drainage, listed):
    soil = {"GEO_DRAINAGE_TYPE": drainage, "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw"}
    shown = names(soil_models.shown(soil_models.MOHR_COULOMB, soil))
    assert ("PERMEABILITY_XX" in shown) is listed
    assert ("MINIMUM_RELATIVE_PERMEABILITY" in shown) is listed
    in_a_flow_project = names(soil_models.shown(soil_models.MOHR_COULOMB, soil, flow=True))
    assert "PERMEABILITY_XX" in in_a_flow_project


def test_the_permeabilities_are_called_intrinsic():
    labels = {p.name: p.label for p in soil_models.parameters(soil_models.MOHR_COULOMB)}
    assert labels["PERMEABILITY_XX"] == "Intrinsic permeability xx"
    assert labels["PERMEABILITY_YY"] == "Intrinsic permeability yy"


def test_a_new_coupled_soil_conducts_water_at_a_metre_a_day():
    variables = {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED"}
    soil_models.fill(None, {}, ELASTIC_2D, variables, "SI")
    kappa = variables["PERMEABILITY_XX"]

    assert kappa == pytest.approx(1.157e-12, rel=1e-3)          # m2, intrinsic
    darcy = soil_models.computed(ELASTIC_2D, variables, soil_models.water("SI"), "SI")
    assert darcy["HYDRAULIC_CONDUCTIVITY_XX"] * 86400 == pytest.approx(1.0)   # m/day


def test_every_choice_lists_every_value_a_soil_can_take():
    choices = {p.name: p.choices for model in soil_models.MODELS
               for p in soil_models.parameters(model) if p.choices}
    assert choices["GEO_DRAINAGE_TYPE"] == ("CONSTANT_PW_FIELD", "FULLY_COUPLED")
    assert choices["RETENTION_LAW"] == ("SaturatedLaw", "SaturatedBelowPhreaticLevelLaw",
                                        "VanGenuchtenLaw")


# ── The project ─────────────────────────────────────────────────────────────

def test_an_old_mohr_coulomb_name_loads_as_the_current_one():
    payload = seed_project().model_dump(mode="json")
    payload["dimension"] = 2
    payload["materials"][0]["constitutive_law"] = "GeoMohrCoulombWithTensionCutOff2D"

    project = Project.model_validate(payload)

    assert project.materials[0].constitutive_law == MC_2D


def test_a_mohr_coulomb_soil_follows_the_dimension():
    project = mohr_coulomb_site()
    solid, _ = session.set_dimension(project, DimensionUpdate(dimension=3))

    assert solid.material("m2").constitutive_law == MC_3D
    back, _ = session.set_dimension(solid, DimensionUpdate(dimension=2))
    assert back.material("m2").constitutive_law == MC_2D


# ── A new soil and a changed one ───────────────────────────────────────────

def test_a_new_soil_of_a_model_is_the_blank_soil_made_that_model_in_the_window():
    """Create soil, then Mohr-Coulomb from the Soil model list: the law, and nothing it
    must have -- the strength stays the user's to type, as the stiffness does."""
    project = blank_project().model_copy(update={"unit_system": "kN"})

    material, notes = drafts.soil(project, "clay", model=soil_models.MOHR_COULOMB)

    assert material.constitutive_law == MC_2D
    assert material.variables == {**soil_models.blank_si(),
                                  "GEO_ENABLE_TENSION_CUT_OFF": False}
    assert "GEO_COHESION" in soil_models.missing(MC_2D, material.variables)
    assert notes == ["Filled in from the Mohr-Coulomb defaults: GEO_ENABLE_TENSION_CUT_OFF."]


def test_a_preset_with_a_strength_is_a_mohr_coulomb_soil_ready_to_run():
    material, notes = drafts.soil(blank_project(), "clay", preset="m3")

    assert material.constitutive_law == MC_2D
    assert material.variables["GEO_COHESION"] == drafts.preset("m3")["variables"]["GEO_COHESION"]
    assert material.variables["GEO_DILATANCY_ANGLE"] == 0.0
    assert notes == [], "a preset filled from its own model's defaults says nothing"


def test_a_preset_made_another_model_says_what_it_took():
    material, notes = drafts.soil(blank_project(), "rock", preset="m6",
                                  model=soil_models.MOHR_COULOMB)

    assert material.constitutive_law == MC_2D
    assert notes == ["Filled in from the Mohr-Coulomb defaults: RETENTION_LAW, "
                     "SATURATED_SATURATION, RESIDUAL_SATURATION, GEO_COHESION, "
                     "GEO_FRICTION_ANGLE, GEO_DILATANCY_ANGLE, GEO_ENABLE_TENSION_CUT_OFF."]


def test_a_soil_model_and_a_law_together_are_refused():
    with pytest.raises(drafts.DraftError, match="not both"):
        drafts.soil(blank_project(), "x", model=soil_models.MOHR_COULOMB, law="MyLaw")
    with pytest.raises(drafts.DraftError, match="no soil model 'hardening'"):
        drafts.soil(blank_project(), "x", model="hardening")


def test_a_model_change_keeps_what_was_typed_and_fills_the_rest():
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    before = project.material("m2").variables
    notes: list[str] = []

    changed = session.update_material(project, "m2", model=soil_models.MOHR_COULOMB,
                                      notes=notes)

    after = changed.material("m2").variables
    assert changed.material("m2").constitutive_law == MC_2D
    assert {name: after[name] for name in before} == before
    assert after["GEO_DILATANCY_ANGLE"] == 0.0
    assert notes and notes[0].startswith("Filled in from the Mohr-Coulomb defaults: ")


def test_a_soil_made_linear_elastic_leaves_out_the_strength_it_does_not_read():
    """As the window's Soil model list does (`App.MaterialSets`, `unread`): a linear
    elastic soil has no strength, and the export would write it into the deck. What no
    model lists -- the user's own, a 3D permeability -- stays."""
    project = mohr_coulomb_site(GEO_COULOMB_HARDENING_TYPE="Linear", MY_OWN=2.0)

    changed = session.update_material(project, "m2", model=soil_models.LINEAR_ELASTIC)

    after = changed.material("m2").variables
    assert changed.material("m2").constitutive_law == ELASTIC_2D
    assert not set(after) & {"GEO_COHESION", "GEO_FRICTION_ANGLE", "GEO_DILATANCY_ANGLE",
                             "GEO_ENABLE_TENSION_CUT_OFF", "GEO_COULOMB_HARDENING_TYPE"}
    assert after["MY_OWN"] == 2.0 and "PERMEABILITY_ZZ" in after
    assert deck(changed)["Variables"].keys().isdisjoint({"GEO_COHESION", "GEO_FRICTION_ANGLE"})
    typed = session.update_material(project, "m2", model=soil_models.LINEAR_ELASTIC,
                                    variables={"GEO_COHESION": 5.0})
    assert typed.material("m2").variables["GEO_COHESION"] == 5.0, "typed with it: kept"
    preset, _ = drafts.soil(project, "x", preset="m1", model=soil_models.LINEAR_ELASTIC)
    assert "GEO_COHESION" not in preset.variables
    assert soil_models.unread("SmallStrainUDSM2DPlaneStrainLaw", {"GEO_COHESION": 1.0}) == []


def test_a_choice_changed_fills_what_it_lists_and_a_left_out_value_stays_out():
    project = mohr_coulomb_site()
    project = session.update_material(project, "m2", unset=["RESIDUAL_SATURATION"])
    notes: list[str] = []

    project = session.update_material(project, "m2",
                                      variables={"RETENTION_LAW": "VanGenuchtenLaw"},
                                      notes=notes)

    soil = project.material("m2").variables
    assert soil["VAN_GENUCHTEN_GN"] == 1.377
    assert "RESIDUAL_SATURATION" not in soil
    assert notes == ["Filled in from the Mohr-Coulomb defaults: "
                     "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE, VAN_GENUCHTEN_GN."],         "a drained soil's flow exponent is not listed"


def test_a_value_unset_with_a_choice_is_not_filled_back():
    project = mohr_coulomb_site()
    project = session.update_material(project, "m2",
                                      variables={"GEO_ENABLE_TENSION_CUT_OFF": True})
    assert project.material("m2").variables["GEO_TENSILE_STRENGTH"] == 0.0

    project = session.update_material(project, "m2", unset=["GEO_TENSILE_STRENGTH"])
    assert "GEO_TENSILE_STRENGTH" not in project.material("m2").variables


def test_a_model_change_and_a_law_together_are_refused():
    with pytest.raises(session.EditRefused, match="not both"):
        session.update_material(seed_project(), "m1", model=soil_models.MOHR_COULOMB,
                                law="MyLaw")


# ── The export ──────────────────────────────────────────────────────────────

def test_a_default_mohr_coulomb_soil_is_written_with_its_law_and_variables():
    material = deck(mohr_coulomb_site())

    assert material["constitutive_law"]["name"] == MC_2D
    variables = material["Variables"]
    assert variables["GEO_DILATANCY_ANGLE"] == 0.0
    assert variables["GEO_ENABLE_TENSION_CUT_OFF"] is False
    assert variables["RETENTION_LAW"] == "SaturatedBelowPhreaticLevelLaw"


def test_the_k0_stage_runs_a_mohr_coulomb_soil_elastic():
    assert deck(mohr_coulomb_site(), k0=True)["constitutive_law"]["name"] == \
        materials.LINEAR_ELASTIC[0]


@pytest.mark.parametrize("unset, message", [
    ("GEO_DILATANCY_ANGLE", "has no GEO_DILATANCY_ANGLE"),
    ("GEO_COHESION", "has no GEO_COHESION"),
])
def test_a_mohr_coulomb_soil_without_its_strength_is_refused(unset, message):
    project = mohr_coulomb_site()
    payload = project.model_dump(mode="json")
    del payload["materials"][1]["variables"][unset]
    with pytest.raises(MaterialError, match=message):
        deck(Project.model_validate(payload))


@pytest.mark.parametrize("variables, message", [
    ({"GEO_DILATANCY_ANGLE": 35.0}, "GEO_DILATANCY_ANGLE cannot be larger"),
    ({"GEO_FRICTION_ANGLE": 90.0}, "below 90 degrees"),
    ({"GEO_ENABLE_TENSION_CUT_OFF": True, "GEO_TENSILE_STRENGTH": 1.0e4},
     r"GEO_TENSILE_STRENGTH cannot be larger than .* = 800.167"),   # c 0.5 kPa, phi 32
])
def test_a_mohr_coulomb_soil_kratos_would_refuse_is_refused(variables, message):
    with pytest.raises(MaterialError, match=message):
        deck(mohr_coulomb_site(**variables))


def test_the_cut_off_on_without_a_tensile_strength_is_refused():
    project = mohr_coulomb_site(GEO_ENABLE_TENSION_CUT_OFF=True)
    payload = project.model_dump(mode="json")
    del payload["materials"][1]["variables"]["GEO_TENSILE_STRENGTH"]
    with pytest.raises(MaterialError, match="has no GEO_TENSILE_STRENGTH"):
        deck(Project.model_validate(payload))


def test_a_law_of_no_model_is_written_as_typed():
    project = mohr_coulomb_site()
    payload = project.model_dump(mode="json")
    payload["materials"][1] = Material(
        id="m2", name="udsm", color="#000000",
        constitutive_law="SmallStrainUDSM2DPlaneStrainLaw",
        variables={"UDSM_NAME": "mc.dll"}).model_dump(mode="json")
    assert deck(Project.model_validate(payload))["constitutive_law"]["name"] == \
        "SmallStrainUDSM2DPlaneStrainLaw"


def test_interface_materials_preserve_user_values_and_refuse_unresolvable_stiffness():
    project = seed_project()
    section = InterfaceSection(
        id="contact", name="Contact", variables={
            "INTERFACE_NORMAL_STIFFNESS": 900.0,
            "INTERFACE_SHEAR_STIFFNESS": 90.0,
        },
    )
    warnings = []
    derived = []

    variables = materials._interface_variables(
        section, project, warnings, adjacent=None, derived=derived,
    )

    assert variables["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
    assert variables["INTERFACE_NORMAL_STIFFNESS"] == 900.0
    assert variables["INTERFACE_SHEAR_STIFFNESS"] == 90.0
    assert derived == ["interface section 'Contact': GEO_DRAINAGE_TYPE"]
    assert warnings == []

    with pytest.raises(materials.MaterialError, match="neither a soil material"):
        materials._interface_variables(
            InterfaceSection(id="missing", name="Missing"), project, [], None, [],
        )


@pytest.mark.parametrize("law, dimension", [
    ("GeoMohrCoulombWithTensionCutOff2D", 2),
    ("GeoMohrCoulombWithTensionCutOff3D", 3),
    ("UserSuppliedSoilLaw", None),
])
def test_soil_law_dimension_recognises_retired_names_without_guessing_custom_laws(
        law, dimension):
    assert soil_models.law_dimension(law) == dimension


def test_an_unknown_soil_model_lists_the_supported_choices():
    with pytest.raises(ValueError, match="there is no soil model 'unknown'; there are:"):
        soil_models.law("unknown", 2)


# ── What is derived, and what follows from a soil's numbers ────────────────

WATER_SI = soil_models.water("SI")


def test_a_permeability_left_out_in_y_is_the_one_in_x():
    found = soil_models.derived(ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
                                             "PERMEABILITY_XX": 2.0e-12}, WATER_SI, "SI")
    assert found["PERMEABILITY_YY"] == 2.0e-12


def test_k0_is_elastic_for_an_elastic_soil_and_jaky_s_for_a_plastic_one():
    elastic = soil_models.derived(ELASTIC_2D, {"POISSON_RATIO": 0.25}, WATER_SI, "SI")
    plastic = soil_models.derived(MC_2D, {"GEO_FRICTION_ANGLE": 30.0}, WATER_SI, "SI")

    assert elastic["K0_NC"] == pytest.approx(0.25 / 0.75)
    assert plastic["K0_NC"] == pytest.approx(0.5)


def test_a_coupled_soil_derives_its_permeability_and_a_constant_one_none():
    coupled = soil_models.derived(ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED"},
                                  WATER_SI, "SI")
    constant = soil_models.derived(ELASTIC_2D, {}, WATER_SI, "SI")

    assert coupled["PERMEABILITY_XX"] == soil_models.PERMEABILITY_SI
    assert "PERMEABILITY_XX" not in constant


@pytest.mark.parametrize("old", ["UNDRAINED", "undrained"])
def test_an_undrained_soil_read_in_is_coupled_with_its_own_permeability(old):
    """UNDRAINED is not offered: Kratos assembles it as FULLY_COUPLED. Read in, it is
    FULLY_COUPLED with the permeability it had, also the one a groundwater flow deck
    reads, and without the undrained Poisson ratio a coupled soil does not read."""
    project = mohr_coulomb_site(GEO_DRAINAGE_TYPE=old, PERMEABILITY_XX=3.0e-12,
                                PERMEABILITY_YY=2.0e-12, GEO_POISSON_UNDRAINED=0.49)

    soil = project.material("m2").variables
    variables = deck(project)["Variables"]

    assert soil["GEO_DRAINAGE_TYPE"] == "FULLY_COUPLED"
    assert (soil["PERMEABILITY_XX"], soil["PERMEABILITY_YY"]) == (3.0e-12, 2.0e-12)
    assert "GEO_POISSON_UNDRAINED" not in soil
    assert variables["GEO_DRAINAGE_TYPE"] == "FULLY_COUPLED"
    assert (variables["PERMEABILITY_XX"], variables["PERMEABILITY_YY"],
            variables["PERMEABILITY_XY"]) == (3.0e-12, 2.0e-12, 0.0)


@pytest.mark.parametrize("law, variables, given, flow, unused", [
    (ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}, {"PERMEABILITY_XX": 1e-12}, False,
     "PERMEABILITY_XX"),
    (ELASTIC_2D, {}, {"PERMEABILITY_XX": 1e-12, "PERMEABILITY_ZZ": 1e-12, "POROSITY": 0.3},
     False, "PERMEABILITY_XX, PERMEABILITY_ZZ"),
    (ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED"}, {"PERMEABILITY_XX": 1e-12}, False,
     None),
    (ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}, {"PERMEABILITY_XX": 1e-12}, True,
     None),
    (ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}, {"POROSITY": 0.3}, False, None),
    ("MyOwnLaw", {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}, {"PERMEABILITY_XX": 1e-12}, False,
     None),
])
def test_a_flow_parameter_given_to_a_soil_that_does_not_read_it_is_named(
        law, variables, given, flow, unused):
    """Not for a coupled soil or in a flow project, which read it, nor for a law of no
    model, which is written as typed."""
    note = soil_models.unused_flow_note(law, variables, given, flow)

    if unused is None:
        assert note is None
    else:
        assert note == (f"{unused} not used: Kratos reads no flow parameters of a soil "
                        "that is not FULLY_COUPLED. Remove it, or make the soil "
                        "FULLY_COUPLED.")


@pytest.mark.parametrize("given", [{"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}, {}])
def test_a_mechanical_only_soil_is_written_as_kratos_constant_pw_field(given):
    """Kratos' own DRAINED couples the water as FULLY_COUPLED does; CONSTANT_PW_FIELD keeps
    the pressures the conditions set. So a soil that says nothing is written as
    CONSTANT_PW_FIELD, with no fixed permeability: Kratos reads none. One the soil
    carries is written as it is, unnamed."""
    project = mohr_coulomb_site(PERMEABILITY_XX=3.0e-12)
    project.material("m2").variables.pop("GEO_DRAINAGE_TYPE", None)
    project.material("m2").variables.update(given)

    variables = deck(project)["Variables"]
    _, warnings = materials.material_parameters(project, [("Soil_1", "m2")], 2)

    assert variables["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
    assert variables["PERMEABILITY_XX"] == 3.0e-12
    assert "PERMEABILITY_" not in " ".join(warnings)


def test_a_coupled_soil_is_written_under_its_own_name():
    assert deck(mohr_coulomb_site(GEO_DRAINAGE_TYPE="FULLY_COUPLED"))["Variables"][
        "GEO_DRAINAGE_TYPE"] == "FULLY_COUPLED"


def test_a_coupled_soil_s_biot_coefficient_is_shown_but_left_to_kratos():
    """Kratos derives it from the soil's current stiffness, which for a soil that yields
    is not the elastic one: the window shows the elastic value, and the deck leaves it
    out. A typed one is written; a groundwater flow deck's elements need it written."""
    project = mohr_coulomb_site(GEO_DRAINAGE_TYPE="FULLY_COUPLED")
    soil = project.material("m2").variables

    _, warnings = materials.material_parameters(project, [("Soil_1", "m2")], 2)

    assert "BIOT_COEFFICIENT" in soil_models.derived(MC_2D, soil, WATER_SI, "SI")
    assert "BIOT_COEFFICIENT" not in deck(project)["Variables"]
    assert "BIOT_COEFFICIENT" not in " ".join(warnings)
    typed = mohr_coulomb_site(GEO_DRAINAGE_TYPE="FULLY_COUPLED", BIOT_COEFFICIENT=0.8)
    assert deck(typed)["Variables"]["BIOT_COEFFICIENT"] == 0.8
    assert soil_models.left_to_kratos("BIOT_COEFFICIENT")
    assert not soil_models.left_to_kratos("BIOT_COEFFICIENT", flow=True)


@pytest.mark.parametrize("old", ["DRAINED", "drained"])
def test_drained_read_in_is_constant_pw_field(old):
    """A project or a script from before 2026-11-10 named a mechanical-only soil DRAINED,
    and the export wrote it as CONSTANT_PW_FIELD: it is CONSTANT_PW_FIELD now, and its
    deck does not change."""
    project = mohr_coulomb_site(GEO_DRAINAGE_TYPE=old)

    assert project.material("m2").variables["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
    assert deck(project)["Variables"]["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"


@pytest.mark.parametrize("drainage", soil_models.DRAINAGE_TYPES)
def test_a_soil_not_saturated_everywhere_is_written_with_a_minimum_relative_permeability(
        drainage):
    """Kratos' U-Pw elements check it for such a soil whatever its drainage type, also
    where the window does not list it: the new soil (`blank_si`) would not run."""
    for retention in soil_models.UNSATURATED:
        project = mohr_coulomb_site(GEO_DRAINAGE_TYPE=drainage, RETENTION_LAW=retention)
        project.material("m2").variables.pop("MINIMUM_RELATIVE_PERMEABILITY", None)

        variables = deck(project)["Variables"]
        _, warnings = materials.material_parameters(project, [("Soil_1", "m2")], 2)

        assert variables["MINIMUM_RELATIVE_PERMEABILITY"] == \
            soil_models.MINIMUM_RELATIVE_PERMEABILITY
        assert "MINIMUM_RELATIVE_PERMEABILITY" in " ".join(warnings)
    for saturated in ({}, {"RETENTION_LAW": "SaturatedLaw"}):
        assert "MINIMUM_RELATIVE_PERMEABILITY" not in soil_models.derived(
            ELASTIC_2D, {"GEO_DRAINAGE_TYPE": drainage, **saturated}, WATER_SI, "SI")
    assert "MINIMUM_RELATIVE_PERMEABILITY" not in soil_models.derived(
        ELASTIC_2D, {"RETENTION_LAW": "VanGenuchtenLaw",
                     "MINIMUM_RELATIVE_PERMEABILITY": 1e-3}, WATER_SI, "SI")


@pytest.mark.parametrize("drainage", soil_models.DRAINAGE_TYPES)
def test_a_van_genuchten_soil_is_written_with_its_relative_permeability_exponent(drainage):
    """`VanGenuchtenLaw::Check` asks for `VAN_GENUCHTEN_GL` whatever the drainage type,
    also where the window does not list it."""
    project = mohr_coulomb_site(GEO_DRAINAGE_TYPE=drainage, RETENTION_LAW="VanGenuchtenLaw")
    project.material("m2").variables.pop("VAN_GENUCHTEN_GL", None)

    variables = deck(project)["Variables"]
    _, warnings = materials.material_parameters(project, [("Soil_1", "m2")], 2)

    assert variables["VAN_GENUCHTEN_GL"] == soil_models.VAN_GENUCHTEN_GL
    assert "VAN_GENUCHTEN_GL" in " ".join(warnings)
    for other in ({}, {"RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw"}):
        assert "VAN_GENUCHTEN_GL" not in soil_models.derived(
            ELASTIC_2D, {"GEO_DRAINAGE_TYPE": drainage, **other}, WATER_SI, "SI")
    assert "VAN_GENUCHTEN_GL" not in soil_models.derived(
        ELASTIC_2D, {"RETENTION_LAW": "VanGenuchtenLaw", "VAN_GENUCHTEN_GL": 2.0},
        WATER_SI, "SI")


def test_a_drained_soil_in_a_flow_project_keeps_the_permeability_it_lists():
    assert soil_models.derived(ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"},
                               WATER_SI, "SI", flow=True)["PERMEABILITY_XX"] == soil_models.PERMEABILITY_SI


# ── Hardening ───────────────────────────────────────────────────────────────

def test_a_mohr_coulomb_soil_offers_linear_hardening_and_lists_its_slopes_once_on():
    off = [p.name for p in soil_models.shown(soil_models.MOHR_COULOMB, {})]
    on = soil_models.shown(soil_models.MOHR_COULOMB, {"GEO_COULOMB_HARDENING_TYPE": "Linear"})

    assert "GEO_COULOMB_HARDENING_TYPE" in off
    assert not set(soil_models.VECTORS) & set(off)
    assert [p.name for p in on if p.name in soil_models.VECTORS] == list(soil_models.VECTORS)
    assert all(p.default == 0.0 and not p.required for p in on
               if p.name in soil_models.VECTORS), "each starts at 0, a flat strength"
    assert "GEO_COULOMB_HARDENING_TYPE" not in soil_models.defaults_si(soil_models.MOHR_COULOMB)


def test_a_linear_hardening_is_written_with_its_slopes_as_kratos_vectors():
    project = mohr_coulomb_site(GEO_COULOMB_HARDENING_TYPE="Linear",
                                GEO_COHESION_FUNCTION_COEFFICIENTS=1.0e5,
                                GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS=0.1,
                                GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS=0.0)

    variables = deck(project)["Variables"]

    assert variables["GEO_COULOMB_HARDENING_TYPE"] == "Linear"
    assert variables["GEO_COHESION_FUNCTION_COEFFICIENTS"] == [1.0e5]
    assert variables["GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS"] == [0.1]
    assert variables["GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS"] == [0.0]
    assert units.label(units.VARIABLES["GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS"],
                       "SI") == "rad"


def test_linear_hardening_chosen_starts_every_slope_at_0():
    choosing = session.update_material(mohr_coulomb_site(), "m2",
                                       variables={"GEO_COULOMB_HARDENING_TYPE": "Linear"})
    blank = {**soil_models.blank_si(), "GEO_COULOMB_HARDENING_TYPE": "Linear"}
    filled = soil_models.fill_choice(MC_2D, soil_models.blank_si(), MC_2D, blank, "SI")

    for name in soil_models.VECTORS:
        assert choosing.material("m2").variables[name] == 0.0, name
        assert blank[name] == 0.0, f"{name}: a soil still being filled in gets it too"
    assert set(soil_models.VECTORS) <= set(filled)


def test_a_linear_hardening_slope_left_out_is_written_as_0_and_a_negative_one_refused():
    choosing = session.update_material(mohr_coulomb_site(), "m2",
                                       variables={"GEO_COULOMB_HARDENING_TYPE": "Linear"})
    lacking = session.update_material(choosing, "m2",
                                      unset=["GEO_COHESION_FUNCTION_COEFFICIENTS"])

    assert deck(lacking)["Variables"]["GEO_COHESION_FUNCTION_COEFFICIENTS"] == [0.0]
    assert soil_models.derived(MC_2D, lacking.material("m2").variables, WATER_SI, "SI")[
        "GEO_COHESION_FUNCTION_COEFFICIENTS"] == 0.0
    assert "GEO_COHESION_FUNCTION_COEFFICIENTS" not in soil_models.derived(
        MC_2D, mohr_coulomb_site().material("m2").variables, WATER_SI, "SI"), \
        "not with the hardening off"
    softening = session.update_material(choosing, "m2", variables={
        "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS": -0.1})
    with pytest.raises(MaterialError, match="cannot be negative"):
        deck(softening)


# ── A new soil, as the window and the command line make it ─────────────────

def test_a_new_soil_is_the_blank_one_the_window_creates():
    project = blank_project().model_copy(update={"unit_system": "kN"})

    material, notes = drafts.soil(project, "peat")

    assert material.constitutive_law == ELASTIC_2D
    assert material.variables == soil_models.blank_si()
    assert material.variables["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
    assert soil_models.missing(ELASTIC_2D, material.variables) == [
        "YOUNG_MODULUS", "POISSON_RATIO", "DENSITY_SOLID", "POROSITY"]
    assert notes == []


def test_a_value_typed_on_a_blank_soil_fills_nothing_else_in():
    project = session.add_material(blank_project(), drafts.soil(blank_project(), "peat")[0])

    project = session.update_material(project, "peat", variables={"YOUNG_MODULUS": 2.0e6})

    assert set(project.material("peat").variables) == {*soil_models.blank_si(), "YOUNG_MODULUS"}


def test_a_value_the_soil_gives_is_not_derived():
    found = soil_models.derived(ELASTIC_2D, {"POROSITY": 0.4, "K0_NC": 0.6}, WATER_SI, "SI")
    assert "POROSITY" not in found and "K0_NC" not in found


def test_the_unit_weights_follow_the_density_the_porosity_and_the_water():
    soil = {"DENSITY_SOLID": 2650.0, "POROSITY": 0.4}
    weights = soil_models.computed(ELASTIC_2D, soil, WATER_SI, "SI")

    assert weights["UNIT_WEIGHT_DRY"] == pytest.approx(0.6 * 2650.0 * 9.81)
    assert weights["UNIT_WEIGHT_SATURATED"] == pytest.approx(0.6 * 2650.0 * 9.81 + 0.4 * 1e4)
    in_kn = soil_models.computed(ELASTIC_2D, {"DENSITY_SOLID": 2.65, "POROSITY": 0.4},
                                 soil_models.water("kN"), "kN")
    assert in_kn["UNIT_WEIGHT_SATURATED"] == pytest.approx(
        weights["UNIT_WEIGHT_SATURATED"] / 1000)


def test_the_darcy_permeability_is_shown_only_where_the_intrinsic_one_is():
    drained = soil_models.computed(ELASTIC_2D, {"PERMEABILITY_XX": 1e-12}, WATER_SI, "SI")
    coupled = soil_models.computed(ELASTIC_2D, {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
                                                "PERMEABILITY_XX": 1e-12}, WATER_SI, "SI")

    assert "HYDRAULIC_CONDUCTIVITY_XX" not in drained
    assert coupled["HYDRAULIC_CONDUCTIVITY_XX"] == pytest.approx(1e-12 * 1e4 / 1e-3)
    assert coupled["HYDRAULIC_CONDUCTIVITY_YY"] == coupled["HYDRAULIC_CONDUCTIVITY_XX"]


# ── The water: the project's ────────────────────────────────────────────────

def test_a_soil_with_water_of_its_own_is_refused():
    with pytest.raises(ValueError,
                       match="belongs to the project's water"):
        session.update_material(seed_project(), "m2", variables={"DYNAMIC_VISCOSITY": 2e-3})


def test_an_older_document_s_soil_water_becomes_the_project_s():
    payload = seed_project().model_dump(mode="json")
    del payload["fluid"]
    for material in payload["materials"]:
        material["variables"].update({"DENSITY_WATER": 1000.0, "BULK_MODULUS_FLUID": 2.0e9,
                                      "DYNAMIC_VISCOSITY": 1.3e-3})

    project = Project.model_validate(payload)

    assert (project.fluid.bulk_modulus, project.fluid.dynamic_viscosity) == (2.0e9, 1.3e-3)
    assert not any(set(soil_models.WATER) & set(m.variables) for m in project.materials)


def older_document(**water_of: dict) -> dict:
    """The seed as saved before 2026-11-02: no `fluid`, its drained soils under the name
    they had then, and the soils named in `water_of` (by id) carrying the water variables
    given."""
    payload = seed_project().model_dump(mode="json")
    del payload["fluid"]
    for material in payload["materials"]:
        material["variables"].update(water_of.get(material["id"], {}))
    return payload


def test_a_soil_whose_water_the_project_s_overrides_is_named():
    payload = older_document(m1={"DYNAMIC_VISCOSITY": 1e-3},
                             m2={"DYNAMIC_VISCOSITY": 5e-3, "DENSITY_WATER": 1100.0})

    notes = migration.notes(payload)

    assert Project.model_validate(payload).fluid.dynamic_viscosity == 1e-3
    assert len(notes) == 1
    assert notes[0].startswith("Sand, loose:")
    assert "DYNAMIC_VISCOSITY 0.001 Pa·s instead of 0.005" in notes[0]
    assert "DENSITY_WATER 1019.37 kg/m³ instead of 1100" in notes[0]


def test_a_soil_that_gave_no_water_is_named_when_the_first_soil_s_is_not_water_s():
    notes = migration.notes(older_document(m1={"BULK_MODULUS_FLUID": 1e9}))

    assert [note.split(":")[0] for note in notes] == [
        "Sand, loose", "Clay, soft", "Clay, stiff", "Sand, dense", "Bedrock"]
    assert all("BULK_MODULUS_FLUID 1e+09 Pa instead of 2.2e+09" in note for note in notes)


def test_soils_that_agree_lose_nothing_and_say_nothing():
    water = {"DENSITY_WATER": 1019.37, "BULK_MODULUS_FLUID": 2.2e9, "DYNAMIC_VISCOSITY": 1e-3}
    payload = older_document(**{f"m{i}": water for i in range(1, 7)})

    assert migration.notes(payload) == []
    assert migration.notes(seed_project().model_dump(mode="json")) == []


def test_an_older_linear_elastic_soil_whose_k0_changes_is_named():
    """Until 2026-11-02 a linear elastic soil with a friction angle took Jaky's K0; now
    it takes nu / (1 - nu). The rule applies to the old project too, and says so."""
    payload = older_document()
    payload["stages"] = [{"id": "k0", "name": "Initial", "calculation": "K0 procedure"}]
    payload["materials"][2]["variables"]["K0_NC"] = 0.6

    notes = migration.notes(payload)

    assert [note.split(":")[0] for note in notes] == [
        "Fill", "Sand, loose", "Clay, stiff", "Sand, dense"],         "a typed K0_NC (Clay, soft) or no friction angle (Bedrock): none"
    assert "K0_NC 0.3889 instead of Jaky's 1 - sin(phi) = 0.4701" in notes[1]
    assert "Set K0_NC to 0.4701" in notes[1]
    assert "K0_NC" not in Project.model_validate(payload).material("m2").variables
    del payload["stages"]
    assert migration.notes(payload) == [], "no K0 procedure, no initial stresses"


def test_an_older_undrained_soil_that_is_coupled_now_is_named():
    payload = seed_project().model_dump(mode="json")
    payload["materials"][1]["variables"].update(GEO_DRAINAGE_TYPE="UNDRAINED",
                                                PERMEABILITY_XX=1e-12)

    notes = migration.notes(payload)

    assert notes == [
        "Sand, loose: UNDRAINED is no longer a drainage type: the soil is FULLY_COUPLED, "
        "as Kratos calculates it, and keeps its own permeability."]
    saved = Project.model_validate(payload).model_dump(mode="json")
    assert migration.notes(saved) == [], "said once: the first save writes the new shape"


def test_an_older_drained_soil_that_is_not_coupled_any_more_is_named():
    """Kratos calculates its own DRAINED as FULLY_COUPLED; the export now writes
    CONSTANT_PW_FIELD, so the results change. A soil that was CONSTANT_PW_FIELD or says
    nothing keeps its deck."""
    payload = older_document()
    payload["materials"][0]["variables"]["GEO_DRAINAGE_TYPE"] = "CONSTANT_PW_FIELD"
    payload["materials"][1]["variables"]["GEO_DRAINAGE_TYPE"] = "DRAINED"
    payload["materials"][2]["variables"].pop("GEO_DRAINAGE_TYPE", None)

    notes = migration.drained_notes(payload)

    assert notes == [
        "Sand, loose: a DRAINED soil is written as Kratos' CONSTANT_PW_FIELD now, so its "
        "water pressures are the ones the water conditions set, and Kratos does not solve "
        "them. It was written as Kratos' DRAINED, which Kratos calculates as FULLY_COUPLED "
        "with the soil's own permeability. Make it FULLY_COUPLED to keep that."]
    assert notes[0] in migration.notes(payload)
    assert migration.drained_notes({**payload, "fluid": {}}) == [], "a current document"


def test_an_older_flow_project_s_drained_soil_is_not_named():
    """Kratos' water pressure elements of a flow deck read no drainage type."""
    payload = older_document()
    payload["materials"][1]["variables"]["GEO_DRAINAGE_TYPE"] = "DRAINED"
    payload["stages"] = [{"id": "s", "name": "Flow", "calculation": "Groundwater flow"}]
    assert migration.drained_notes(payload) == []

    payload["stages"].append({"id": "t", "name": "Load", "calculation": "Plastic"})
    assert len(migration.drained_notes(payload)) == 1


def test_an_older_document_s_soil_without_a_porosity_gets_the_0_3_its_deck_had():
    """Until 2026-11-02 the export filled POROSITY = 0.3 into a soil without one; now a
    porosity is the soil's, and the export refuses a soil of a model without it."""
    payload = older_document()
    del payload["materials"][1]["variables"]["POROSITY"]
    payload["materials"][2]["variables"]["POROSITY"] = 0.45

    project = Project.model_validate(payload)

    assert project.material("m2").variables["POROSITY"] == migration.DEFAULT_POROSITY
    assert project.material("m3").variables["POROSITY"] == 0.45
    deck(project)                          # not refused for want of a porosity
    current = seed_project().model_dump(mode="json")
    del current["materials"][1]["variables"]["POROSITY"]
    assert "POROSITY" not in Project.model_validate(current).material("m2").variables


def older_contact(material: str | None, **variables) -> dict:
    """`older_document` with a Coulomb contact, naming `material` (an id, or None)."""
    payload = older_document()
    payload["interface_sections"] = [{
        "id": "c1", "name": "Wall contact", "constitutive_law":
        "GeoInterfaceCoulombLawPlaneStrain", "material": material, "r_inter": 0.5,
        "variables": dict(variables)}]
    payload["materials"][1]["variables"].update(GEO_COHESION=2000.0, GEO_FRICTION_ANGLE=30.0)
    return payload


def test_an_older_coulomb_contact_on_a_linear_elastic_soil_keeps_the_strength_it_had():
    """The export took the soil's c R and atan(R tan phi) whatever its law; now a linear
    elastic soil has none to give, so the contact carries them as its own."""
    contact = Project.model_validate(older_contact("m2")).interface_sections[0]

    assert contact.variables["GEO_COHESION"] == pytest.approx(1000.0)
    assert contact.variables["GEO_FRICTION_ANGLE"] == pytest.approx(
        math.degrees(math.atan(0.5 * math.tan(math.radians(30.0)))))
    own = Project.model_validate(older_contact("m2", GEO_COHESION=7.0)).interface_sections[0]
    assert own.variables["GEO_COHESION"] == 7.0, "its own is kept"
    assert migration.notes(older_contact("m2")) == []


def test_an_older_coulomb_contact_naming_no_soil_is_named_when_opened():
    payload = older_contact(None)

    notes = migration.notes(payload)

    assert "GEO_COHESION" not in Project.model_validate(payload).interface_sections[0].variables
    assert len(notes) == 1 and notes[0].startswith("interface section 'Wall contact'")
    assert "Sand, loose" in notes[0]
    current = older_contact(None)
    current["fluid"] = {}
    assert migration.notes(current) == []


def test_every_soil_is_written_with_the_project_s_water():
    project = mohr_coulomb_site()
    project = session.set_fluid(project, bulk_modulus=2.0e9, dynamic_viscosity=1.3e-3)

    variables = deck(project)["Variables"]

    assert variables["BULK_MODULUS_FLUID"] == 2.0e9
    assert variables["DYNAMIC_VISCOSITY"] == 1.3e-3
    assert variables["DENSITY_WATER"] == pytest.approx(
        project.water_specific_weight / 9.81)
    back = session.set_fluid(project, unset=["bulk_modulus"])
    assert deck(back)["Variables"]["BULK_MODULUS_FLUID"] == soil_models.WATER_BULK_MODULUS_SI


def test_the_water_converts_with_the_unit_system():
    project = session.set_fluid(seed_project(), bulk_modulus=2.0e9)
    payload, _ = units.convert_project(project.model_dump(mode="json"), "kN")
    assert payload["fluid"]["bulk_modulus"] == pytest.approx(2.0e6)
