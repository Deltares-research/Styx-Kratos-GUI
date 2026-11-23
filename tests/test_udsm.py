"""UDSM soils: the libraries that come with Styx (`core/model/udsm_libraries`), a soil of one
(`core/model/soil_models.py`), its units, and the deck it writes
(`core/kratos/materials.py`).

The library's models come from `tests/fakes/udsm.py`, so these run on every system; the
tests marked `windows` read the library itself.
"""

from __future__ import annotations

import json
import math
import sys

import pytest

from core import session
from core.analysis import calculation
from core.kratos import materials
from core.model import soil_models, units
from core.model.schemas import DimensionUpdate, UnitsUpdate
from core.model.templates import seed_project
from core.model import udsm, udsm_parser
from tests.fakes import udsm as fakes

windows = pytest.mark.skipif(sys.platform != "win32", reason="the .dll loads on Windows only")

UDSM_2D = soil_models.law(soil_models.UDSM, 2)


@pytest.fixture(autouse=True)
def the_mohr_coulomb_library():
    with udsm.using([fakes.mohr_coulomb()]) as models:
        yield models


def udsm_project(**variables):
    """The demo model in 2D, its first soil the Mohr-Coulomb UDSM given `variables`."""
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    soil = project.materials[0].id
    return session.update_material(project, soil, udsm="MohrCoulomb64:1",
                                   variables=variables), soil


# ── Reading a library ───────────────────────────────────────────────────────

def test_a_counted_string_is_read_to_its_length():
    assert udsm_parser.text(b"\x0cMohr-Coulomb" + b" " * 40 + b"\0junk") == "Mohr-Coulomb"
    assert udsm_parser.text(b"0     7. yield function (MC=1; DP=2; MNC=3; MN=4)    ") == \
        "7. yield function (MC=1; DP=2; MNC=3; MN=4)"


def test_a_string_that_is_not_counted_is_read_as_it_stands():
    assert udsm_parser.text(b"  plain text   \0") == "plain text"


def test_the_library_s_names_are_made_readable_and_typeable():
    assert [(p.label, p.key) for p in fakes.mohr_coulomb().parameters] == [
        ("E", "E"), ("ν_ur", "nu_ur"), ("c'", "c"), ("φ_peak", "phi_peak"),
        ("ψ_peak", "psi_peak"), ("σ_t, cut-off", "sigma_t_cut_off"),
        ("yield function (MC=1; DP=2; MNC=3; MN=4)", "yield_function"),
        ("ν_un (UMAT)", "nu_un")]


def test_the_library_s_units_are_quantities_in_the_project_s_system():
    model = fakes.mohr_coulomb()
    assert [p.quantity.name for p in model.parameters] == [
        "stress", "dimensionless", "stress", "angle", "angle", "stress", "dimensionless",
        "dimensionless"]
    assert udsm.unit_label(model.parameters[0], "kN") == "kPa"
    assert udsm.unit_label(fakes.unknown().parameters[2], "SI") == "s"
    assert udsm.quantity("1/T") is None


def test_a_known_model_has_start_values_and_roles():
    model = fakes.mohr_coulomb()
    assert model.id == "MohrCoulomb64:1" and model.known
    assert model.defaults == (1.0e7, 0.3, 1000.0, 30.0, 0.0, 1000.0, 1.0, 0.0)
    assert model.roles["GEO_FRICTION_ANGLE"] == 4


def test_a_model_styx_does_not_know_starts_at_zeros():
    model = fakes.unknown()
    assert not model.known and model.roles == {}
    assert model.defaults == (0.0, 0.0, 0.0)
    assert [p.key for p in model.parameters] == ["lambda", "p_ref", "t_ref"]


def test_a_known_model_whose_library_reads_otherwise_is_not_known():
    read = {**fakes.MOHR_COULOMB_READ, "parameters": fakes.MOHR_COULOMB_READ["parameters"][:3]}
    assert not udsm.model("MohrCoulomb64.dll", read).known


def test_two_parameters_of_one_name_get_two_keys():
    model = udsm.model("Two.dll", {"number": 1, "name": "Two", "parameters": [
        {"name": "1. c", "unit": "-"}, {"name": "2. c'", "unit": "-"}]})
    assert [p.key for p in model.parameters] == ["c", "c_2"]


def test_a_model_is_found_by_its_deck_path_and_its_id():
    assert udsm.find("udsm/MohrCoulomb64.dll", 1).id == "MohrCoulomb64:1"
    assert udsm.find("mohrcoulomb64.DLL", 1) is not None
    assert udsm.find("MohrCoulomb64.dll", 2) is None
    assert udsm.find("MohrCoulomb64.dll", True) is None
    assert udsm.by_id("mohrcoulomb64").number == 1
    with pytest.raises(LookupError, match="there are: MohrCoulomb64:1"):
        udsm.by_id("Creep:1")


def test_a_deck_takes_the_library_and_its_linux_twin_when_there_is_one():
    files = udsm.deck_files(fakes.mohr_coulomb())
    assert list(files) == ["udsm/MohrCoulomb64.dll"]
    assert files["udsm/MohrCoulomb64.dll"] == str(udsm.FOLDER / "MohrCoulomb64.dll")


def test_a_library_without_a_linux_twin_is_left_out_on_linux(monkeypatch):
    monkeypatch.setattr(udsm.sys, "platform", "linux")
    found, problems = udsm.scan()
    assert found == []
    assert problems == ["MohrCoulomb64.dll has no MohrCoulomb64.so beside it, so it cannot "
                        "run on this system"]


def test_a_library_that_cannot_be_read_is_said(monkeypatch, tmp_path):
    broken = tmp_path / "Broken.dll"
    broken.write_bytes(b"not a library")
    monkeypatch.setattr(udsm, "FOLDER", tmp_path)
    monkeypatch.setattr(udsm.sys, "platform", "win32")
    found, problems = udsm.scan()
    assert found == [] and len(problems) == 1
    assert problems[0].startswith("Broken.dll cannot be read: ")


@windows
def test_the_library_says_what_the_fake_says():
    """`tests/fakes/udsm.py` is what the library itself answers."""
    answer = udsm.read(udsm.FOLDER / "MohrCoulomb64.dll")
    assert answer == {"models": [fakes.MOHR_COULOMB_READ]}


@windows
def test_the_libraries_that_come_with_styx_list_the_mohr_coulomb_model():
    found, problems = udsm.scan()
    assert problems == []
    assert [m.id for m in found] == ["MohrCoulomb64:1"]


# ── A UDSM soil ─────────────────────────────────────────────────────────────

def test_a_new_udsm_soil_takes_its_model_in_the_project_s_units():
    after: dict = {}
    filled = soil_models.fill(None, {}, UDSM_2D, after, "kN")
    assert filled[:6] == list(soil_models.UDSM_VARIABLES)
    assert after["UDSM_NAME"] == "MohrCoulomb64.dll" and after["UDSM_NUMBER"] == 1
    assert after["IS_FORTRAN_UDSM"] is True
    assert after["UMAT_PARAMETERS"] == [1.0e4, 0.3, 1.0, 30.0, 0.0, 1.0, 1.0, 0.0]
    assert (after["INDEX_OF_UMAT_C_PARAMETER"], after["INDEX_OF_UMAT_PHI_PARAMETER"]) == (3, 4)
    assert "YOUNG_MODULUS" not in after and "DENSITY_SOLID" in after


def test_a_model_of_no_known_roles_takes_no_indices():
    variables = {"INDEX_OF_UMAT_C_PARAMETER": 3}
    soil_models.udsm_choose(variables, fakes.unknown(), "SI")
    assert "INDEX_OF_UMAT_C_PARAMETER" not in variables
    assert variables["UMAT_PARAMETERS"] == [0.0, 0.0, 0.0]


def test_no_library_leaves_a_udsm_soil_to_be_typed():
    with udsm.using([]):
        after: dict = {}
        soil_models.fill(None, {}, UDSM_2D, after, "SI")
    assert "UDSM_NAME" not in after
    assert soil_models.missing(UDSM_2D, after) == ["UDSM_NAME", "UDSM_NUMBER",
                                                   "UMAT_PARAMETERS"]


def test_a_udsm_soil_needs_a_library_a_model_and_numbers():
    soil = soil_models.defaults_si(soil_models.UDSM)
    assert soil_models.missing(UDSM_2D, soil) == []
    assert soil_models.missing(UDSM_2D, {**soil, "UDSM_NAME": " "}) == ["UDSM_NAME"]
    assert soil_models.missing(UDSM_2D, {**soil, "UDSM_NUMBER": 0}) == ["UDSM_NUMBER"]
    assert soil_models.missing(UDSM_2D, {**soil, "UMAT_PARAMETERS": [1.0, "x"]}) == \
        ["UMAT_PARAMETERS"]


def test_a_udsm_soil_with_the_wrong_count_of_parameters_is_refused():
    soil = {**soil_models.defaults_si(soil_models.UDSM), "UMAT_PARAMETERS": [1.0]}
    assert soil_models.problem(UDSM_2D, soil) == (
        "UMAT_PARAMETERS has 1 values, and Mohr-Coulomb in MohrCoulomb64.dll reads 8: E, "
        "ν_ur, c', φ_peak, ψ_peak, σ_t, cut-off, yield function (MC=1; DP=2; MNC=3; "
        "MN=4), ν_un (UMAT).")


def test_a_udsm_soil_s_k0_follows_its_friction_angle():
    soil = soil_models.defaults_si(soil_models.UDSM)
    assert soil_models.k0(UDSM_2D, soil) == pytest.approx(1 - math.sin(math.radians(30)))
    del soil["INDEX_OF_UMAT_PHI_PARAMETER"]
    assert soil_models.k0(UDSM_2D, soil) is None


def test_a_udsm_soil_s_stiffness_and_strength_under_the_built_in_names():
    soil = soil_models.defaults_si(soil_models.UDSM)
    assert soil_models.udsm_equivalents(soil) == {
        "YOUNG_MODULUS": 1.0e7, "POISSON_RATIO": 0.3, "GEO_COHESION": 1000.0,
        "GEO_FRICTION_ANGLE": 30.0, "GEO_DILATANCY_ANGLE": 0.0}


def test_a_udsm_soil_takes_its_parameters_by_their_keys():
    soil = soil_models.defaults_si(soil_models.UDSM)
    rest = soil_models.udsm_assign(soil, {"E": 2.0e7, "phi_peak": 33, "POROSITY": 0.3})
    assert rest == {"POROSITY": 0.3}
    assert soil["UMAT_PARAMETERS"][:4] == [2.0e7, 0.3, 1000.0, 33.0]
    with pytest.raises(ValueError, match="c must be a number"):
        soil_models.udsm_assign(soil, {"c": "soft"})


def test_choosing_another_model_puts_a_udsm_soil_s_own_variables_aside():
    soil = soil_models.defaults_si(soil_models.UDSM)
    mohr_coulomb = soil_models.law(soil_models.MOHR_COULOMB, 2)
    assert soil_models.unread(mohr_coulomb, soil) == list(soil_models.UDSM_VARIABLES)
    assert soil_models.unread(UDSM_2D, {"GEO_COHESION": 1.0, "UDSM_NAME": "x"}) == \
        ["GEO_COHESION"]


def test_a_udsm_soil_changes_units_by_each_parameter_s_unit():
    soil = soil_models.defaults_si(soil_models.UDSM)
    converted, unknown = units.convert_variables(soil, "SI", "kN")
    assert unknown == []
    assert converted["UMAT_PARAMETERS"] == [1.0e4, 0.3, 1.0, 30.0, 0.0, 1.0, 1.0, 0.0]
    assert converted["UDSM_NUMBER"] == 1 and isinstance(converted["UDSM_NUMBER"], int)


def test_the_parameters_of_a_library_styx_does_not_have_are_kept_and_said():
    soil = {"UDSM_NAME": "Own.dll", "UDSM_NUMBER": 1, "UMAT_PARAMETERS": [1.0e3]}
    converted, unknown = units.convert_variables(soil, "SI", "kN")
    assert converted["UMAT_PARAMETERS"] == [1.0e3] and unknown == ["UMAT_PARAMETERS"]


# ── The project: CLI and GUI edits ──────────────────────────────────────────

def test_a_soil_made_a_udsm_model_takes_its_start_values_and_the_keys_given():
    notes: list[str] = []
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    soil = project.materials[0].id
    project = session.update_material(project, soil, udsm="MohrCoulomb64:1",
                                      variables={"c": 5000.0}, notes=notes)
    material = project.material(soil)
    assert material.constitutive_law == UDSM_2D
    assert material.variables["UMAT_PARAMETERS"][2] == 5000.0
    assert "YOUNG_MODULUS" not in material.variables
    assert notes[0].startswith("Filled in from the User-defined (UDSM) defaults: UDSM_NAME")


def test_a_udsm_model_with_another_law_is_refused():
    project, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    soil = project.materials[0].id
    with pytest.raises(session.EditRefused, match="a UDSM model is the UDSM soil model"):
        session.update_material(project, soil, udsm="MohrCoulomb64:1",
                                model=soil_models.MOHR_COULOMB)
    with pytest.raises(session.EditRefused, match="there is no UDSM model 'Creep:1'"):
        session.update_material(project, soil, udsm="Creep:1")


def test_a_unit_change_converts_a_udsm_soil_s_parameters():
    project, soil = udsm_project()
    project, notes = session.set_units(project, UnitsUpdate(unit_system="kN"))
    assert project.material(soil).variables["UMAT_PARAMETERS"][:3] == [1.0e4, 0.3, 1.0]
    assert not any("UMAT_PARAMETERS" in note for note in notes)


# ── The deck ────────────────────────────────────────────────────────────────

def soil_entry(text: str) -> dict:
    return json.loads(text)["properties"][0]["Material"]


def test_the_deck_opens_the_library_from_beside_it():
    project, soil = udsm_project()
    text, warnings = materials.material_parameters(project, [("Soil", soil)], 2)
    entry = soil_entry(text)
    assert entry["constitutive_law"]["name"] == UDSM_2D
    assert entry["Variables"]["UDSM_NAME"] == "udsm/MohrCoulomb64.dll"
    assert entry["Variables"]["UMAT_PARAMETERS"] == [1.0e7, 0.3, 1000.0, 30.0, 0.0, 1000.0,
                                                     1.0, 0.0]
    assert not any("UDSM_NAME" in line for line in warnings)
    assert materials.library_files(project, [soil, soil]) == udsm.deck_files(
        fakes.mohr_coulomb())


def test_the_k0_stage_runs_a_udsm_soil_elastic_with_its_stiffness():
    project, soil = udsm_project(E=3.0e7, nu_ur=0.25)
    text, warnings = materials.material_parameters(project, [("Soil", soil)], 2, k0=True)
    entry = soil_entry(text)
    assert entry["constitutive_law"]["name"] == "GeoLinearElasticPlaneStrain2DLaw"
    assert entry["Variables"]["YOUNG_MODULUS"] == 3.0e7
    assert entry["Variables"]["POISSON_RATIO"] == 0.25
    assert entry["Variables"]["K0_NC"] == pytest.approx(0.5)
    assert any("The K0 stage runs elastic" in line for line in warnings)


def test_the_k0_stage_of_a_model_of_unknown_roles_needs_a_stiffness():
    project, soil = udsm_project()
    with udsm.using([fakes.mohr_coulomb(), fakes.unknown()]):
        variables = dict(project.material(soil).variables)
        soil_models.udsm_choose(variables, fakes.unknown(), "SI")
        project = session.update_material(project, soil, variables=variables)
        with pytest.raises(materials.MaterialError, match="give the soil YOUNG_MODULUS"):
            materials.material_parameters(project, [("Soil", soil)], 2, k0=True)
        project = session.update_material(project, soil, variables={
            "YOUNG_MODULUS": 1.0e7, "POISSON_RATIO": 0.3, "K0_NC": 0.5})
        text, _ = materials.material_parameters(project, [("Soil", soil)], 2, k0=True)
    assert soil_entry(text)["Variables"]["YOUNG_MODULUS"] == 1.0e7


def test_a_library_styx_does_not_have_is_written_as_given_and_said():
    project, soil = udsm_project()
    project = session.update_material(project, soil, variables={"UDSM_NAME": "C:/own/x.dll"})
    text, warnings = materials.material_parameters(project, [("Soil", soil)], 2)
    assert soil_entry(text)["Variables"]["UDSM_NAME"] == "C:/own/x.dll"
    assert any("is not a library that comes with Styx" in line for line in warnings)
    assert materials.library_files(project, [soil]) == {}


def test_a_udsm_soil_with_the_wrong_count_of_parameters_is_not_written():
    project, soil = udsm_project()
    project = session.update_material(project, soil, variables={"UMAT_PARAMETERS": [1.0]})
    with pytest.raises(materials.MaterialError, match="UMAT_PARAMETERS has 1 values"):
        materials.material_parameters(project, [("Soil", soil)], 2)


def test_a_contact_takes_its_stiffness_and_strength_from_a_udsm_soil():
    project, soil = udsm_project(E=2.6e7, nu_ur=0.3, c=4000.0, phi_peak=30.0)
    material = project.material(soil)
    assert materials.soil_number(material, "YOUNG_MODULUS") == 2.6e7
    assert materials.soil_number(material, "GEO_COHESION") == 4000.0
    assert materials.soil_number(project.materials[1], "GEO_COHESION") == \
        project.materials[1].number("GEO_COHESION")


def test_the_deck_folder_gets_a_copy_of_the_library(tmp_path):
    export = {"deck_name": "deck", "mdpa": "", "project_parameters": "{}",
              "library_files": udsm.deck_files(fakes.mohr_coulomb())}
    written = calculation.write_deck(export, tmp_path)
    assert "udsm/MohrCoulomb64.dll" in written
    assert (tmp_path / "udsm" / "MohrCoulomb64.dll").read_bytes() == \
        (udsm.FOLDER / "MohrCoulomb64.dll").read_bytes()
