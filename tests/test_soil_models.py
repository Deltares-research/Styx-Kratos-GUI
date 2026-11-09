"""`core.model.soil_models`: the soil models a material can be, and what follows.

A soil model is a law per dimension and the parameters the material window lists for it,
with their defaults. The project keeps the law in step with its dimension and its current
name; a new soil, a model change and a choice changed fill in the defaults of what the
soil now lists; the export refuses a soil its law cannot run, naming why.
"""

from __future__ import annotations

import json

import pytest

from core import session
from core.kratos import materials
from core.kratos.materials import MaterialError
from core.model import drafts, soil_models
from core.model.schemas import DimensionUpdate, InterfaceSection, Material, Project
from core.model.templates import blank_project, seed_project

MC_2D, MC_3D = soil_models.law(soil_models.MOHR_COULOMB, 2), soil_models.law(
    soil_models.MOHR_COULOMB, 3)


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
    assert (defaults["SATURATED_SATURATION"], defaults["RESIDUAL_SATURATION"],
            defaults["MINIMUM_RELATIVE_PERMEABILITY"]) == (1.0, 1.0e-10, 1.0e-4)
    assert "GEO_TENSILE_STRENGTH" not in defaults, "the cut-off is off"
    assert soil_models.required(MC_2D, defaults) == [
        "YOUNG_MODULUS", "POISSON_RATIO", "DENSITY_SOLID", "GEO_COHESION",
        "GEO_FRICTION_ANGLE", "GEO_DILATANCY_ANGLE"]
    assert soil_models.problem(MC_2D, defaults) is None


def test_the_linear_elastic_defaults_are_the_sand_a_new_soil_always_was():
    assert soil_models.defaults_si(soil_models.LINEAR_ELASTIC) == {
        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "YOUNG_MODULUS": 1.0e7,
        "POISSON_RATIO": 0.3, "DENSITY_SOLID": 17000 / 9.81, "POROSITY": 0.0,
        "PERMEABILITY_XX": 1 / 86400, "GEO_COHESION": 0.0, "GEO_FRICTION_ANGLE": 30.0}


def test_every_choice_lists_every_value_kratos_accepts():
    choices = {p.name: p.choices for model in soil_models.MODELS
               for p in soil_models.parameters(model) if p.choices}
    assert choices["GEO_DRAINAGE_TYPE"] == ("CONSTANT_PW_FIELD", "FULLY_COUPLED", "DRAINED",
                                            "UNDRAINED")
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

def test_a_new_soil_of_a_model_takes_its_law_and_defaults_in_the_project_s_units():
    project = blank_project().model_copy(update={"unit_system": "kN"})

    material, notes = drafts.soil(project, "clay", model=soil_models.MOHR_COULOMB)

    assert material.constitutive_law == MC_2D
    assert material.variables["GEO_COHESION"] == pytest.approx(1.0)        # kPa
    assert material.variables["YOUNG_MODULUS"] == pytest.approx(1.0e4)
    assert notes == []


def test_a_preset_made_mohr_coulomb_keeps_its_values_and_says_what_it_took():
    material, notes = drafts.soil(blank_project(), "clay", preset="m3",
                                  model=soil_models.MOHR_COULOMB)

    assert material.variables["GEO_COHESION"] == drafts.preset("m3")["variables"]["GEO_COHESION"]
    assert material.variables["GEO_DILATANCY_ANGLE"] == 0.0
    assert notes == ["Filled in from the Mohr-Coulomb defaults: RETENTION_LAW, "
                     "SATURATED_SATURATION, RESIDUAL_SATURATION, MINIMUM_RELATIVE_PERMEABILITY, "
                     "GEO_DILATANCY_ANGLE, GEO_ENABLE_TENSION_CUT_OFF."]


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


def test_a_choice_changed_fills_what_it_lists_and_a_left_out_value_stays_out():
    project = mohr_coulomb_site()
    project = session.update_material(project, "m2", unset=["POROSITY"])
    notes: list[str] = []

    project = session.update_material(project, "m2",
                                      variables={"RETENTION_LAW": "VanGenuchtenLaw"},
                                      notes=notes)

    soil = project.material("m2").variables
    assert soil["VAN_GENUCHTEN_GN"] == 1.377
    assert "POROSITY" not in soil
    assert notes == ["Filled in from the Mohr-Coulomb defaults: "
                     "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE, VAN_GENUCHTEN_GN, VAN_GENUCHTEN_GL."]


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


RETENTION = {"BIOT_COEFFICIENT": 1.0, "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
             "SATURATED_SATURATION": 1.0, "RESIDUAL_SATURATION": 1e-10,
             "MINIMUM_RELATIVE_PERMEABILITY": 1e-4}


def _clay(**variables):
    return Material(id="clay", name="Clay", color="#c4a86a",
                    constitutive_law="GeoMohrCoulombLawPlaneStrain",
                    r_inter=0.5, variables={"YOUNG_MODULUS": 9e5, "POISSON_RATIO": 0.2,
                                            "GEO_COHESION": 3000.0,
                                            "GEO_FRICTION_ANGLE": 22.5, **variables})


def test_a_contact_takes_the_saturation_of_the_soil_it_runs_against():
    """The soil's retention law and saturations, as the contact's strength is the soil's:
    the reference deck gives each interface the retention of its soil."""
    derived = []

    got = materials._interface_variables(InterfaceSection(id="c", name="C"), seed_project(),
                                         [], _clay(**RETENTION), derived)

    assert {name: got[name] for name in RETENTION} == RETENTION
    assert "interface section 'C': RETENTION_LAW" in derived


def test_a_coulomb_contact_takes_the_soil_s_tension_cut_off_and_an_elastic_one_does_not():
    soil = _clay(GEO_ENABLE_TENSION_CUT_OFF=True, GEO_TENSILE_STRENGTH=1000.0)
    coulomb = InterfaceSection(id="c", name="C",
                               constitutive_law="GeoInterfaceCoulombLawPlaneStrain")

    got = materials._interface_variables(coulomb, seed_project(), [], soil, [])

    assert got["GEO_ENABLE_TENSION_CUT_OFF"] is True
    assert got["GEO_TENSILE_STRENGTH"] == pytest.approx(500.0), "reduced by r_inter"
    elastic = materials._interface_variables(InterfaceSection(id="e", name="E"),
                                             seed_project(), [], soil, [])
    assert "GEO_ENABLE_TENSION_CUT_OFF" not in elastic
    assert "GEO_TENSILE_STRENGTH" not in elastic


def test_what_a_contact_gives_itself_is_kept_over_its_soil_s():
    contact = InterfaceSection(id="c", name="C",
                               constitutive_law="GeoInterfaceCoulombLawPlaneStrain",
                               variables={"RETENTION_LAW": "SaturatedLaw",
                                          "GEO_ENABLE_TENSION_CUT_OFF": False})

    got = materials._interface_variables(
        contact, seed_project(), [], _clay(GEO_ENABLE_TENSION_CUT_OFF=True, **RETENTION), [])

    assert (got["RETENTION_LAW"], got["GEO_ENABLE_TENSION_CUT_OFF"]) == ("SaturatedLaw", False)


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
