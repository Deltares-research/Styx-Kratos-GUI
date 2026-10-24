"""Projects saved before the unit system (core/model/migration.py): converted once, on load, into
the Kratos property sets and the SI values the old exporter wrote -- so an old project
writes the deck it always wrote."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.model import migration
from core.model.schemas import Project

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "projects"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def old():
    return fixture("every_field_2d_v1")


@pytest.fixture(scope="module")
def new(old):
    return Project.model_validate(old)


def test_an_old_file_is_recognised_by_its_materials(old):
    assert migration.is_legacy(old)
    assert not migration.is_legacy(Project.model_validate(old).model_dump(mode="json"))
    assert not migration.is_legacy({"materials": []})
    assert not migration.is_legacy("not a project")


def test_the_converted_project_is_si(new):
    assert new.unit_system == "SI"


def test_a_soil_becomes_the_property_set_the_old_deck_carried(old, new):
    o, m = old["materials"][0], new.materials[0]
    assert m.constitutive_law == "GeoLinearElasticPlaneStrain2DLaw"
    v = m.variables
    assert v["YOUNG_MODULUS"] == o["E"] * 1000
    assert v["POISSON_RATIO"] == o["nu"]
    assert v["DENSITY_SOLID"] == o["g_unsat"] * 1000 / 9.81
    assert v["DENSITY_WATER"] == old["water"]["specific_weight"] * 1000 / 9.81
    assert v["POROSITY"] == o["porosity"] == 0.25
    assert v["PERMEABILITY_XX"] == v["PERMEABILITY_YY"] == o["k"] / 86_400
    assert v["GEO_COHESION"] == o["c"] * 1000
    assert v["GEO_FRICTION_ANGLE"] == o["phi"]
    assert v["K0_NC"] == o["k0_nc"]
    assert v["GEO_DRAINAGE_TYPE"] == "CONSTANT_PW_FIELD"
    assert (m.r_inter, m.interface_permeability) == (o["r_inter"], o["interface_permeability"])


def test_what_the_old_soil_left_empty(old, new):
    """No cohesion stays no cohesion; no porosity is the 0.3 the old deck wrote; no K0 is
    left to Jaky, as before."""
    o, v = old["materials"][1], new.materials[1].variables
    assert o["c"] is None and "GEO_COHESION" not in v
    assert migration.material({**o, "porosity": None, "k0_nc": None}, 2)["variables"]["POROSITY"] == 0.3
    assert "K0_NC" not in migration.material({**o, "k0_nc": None}, 2)["variables"]


def test_an_undrained_soil_is_fully_coupled():
    o = fixture("seed_3d_v1")["materials"][2]
    assert o["type"] == "Undrained (A)"
    m = migration.material(o, 3)
    assert m["variables"]["GEO_DRAINAGE_TYPE"] == "FULLY_COUPLED"
    assert m["constitutive_law"] == "GeoIncrementalLinearElastic3DLaw"
    assert {"PERMEABILITY_ZZ", "PERMEABILITY_YZ", "PERMEABILITY_ZX"} <= set(m["variables"])


def test_sections_become_property_sets(old, new):
    beam, beam0 = new.beam_sections[0], old["beam_sections"][0]
    assert beam.constitutive_law == "TimoshenkoBeamElasticConstitutiveLaw"
    assert beam.variables == {"YOUNG_MODULUS": beam0["E"] * 1000, "POISSON_RATIO": beam0["nu"],
                              "DENSITY": beam0["density"], "CROSS_AREA": beam0["area"],
                              "I33": beam0["inertia"], "AREA_EFFECTIVE_Y": beam0["shear_area"]}
    assert beam.spacing == beam0["spacing"]

    tendon, tendon0 = new.anchor_sections[0], old["anchor_sections"][0]
    assert tendon.variables == {"YOUNG_MODULUS": tendon0["E"] * 1000,
                                "CROSS_AREA": tendon0["area"], "DENSITY": tendon0["density"]}
    assert tendon.tension_limit == tendon0["tension_limit"] * 1000

    contact, contact0 = new.interface_sections[0], old["interface_sections"][0]
    assert contact.variables == {
        "INTERFACE_NORMAL_STIFFNESS": contact0["normal_stiffness"] * 1000,
        "INTERFACE_SHEAR_STIFFNESS": contact0["shear_stiffness"] * 1000}
    assert contact.r_inter == contact0["r_inter"]


def test_an_interface_section_that_derived_its_stiffness_still_does():
    contact = Project.model_validate(fixture("staged_v1")).interface_sections[0]
    assert contact.variables == {}


def test_loads_pressures_and_water_in_newtons(old, new):
    assert list(new.loads[0].components) == [c * 1000 for c in old["loads"][0]["components"]]
    uniform0 = next(n for n in old["normal_loads"] if n["fluid_pressure_type"] == "Uniform")
    uniform = next(n for n in new.normal_loads if n.id == uniform0["id"])
    assert uniform.pressure == uniform0["pressure"] * 1000
    assert new.water.specific_weight == old["water"]["specific_weight"] * 1000


def test_the_prestress_is_the_stress_the_old_deck_carried(old, new):
    """kN x 1000, smeared by the tendon's spacing as the old exporter did -- now the
    anchor's `TRUSS_PRESTRESS_PK2` as such."""
    spacing = old["anchor_sections"][0]["spacing"]
    assert new.anchors[0].prestress == old["anchors"][0]["prestress"] * 1000 / spacing


def test_the_single_load_of_the_oldest_files_is_in_newtons_too():
    project = Project.model_validate(fixture("single_load_2d"))
    raw = fixture("single_load_2d")
    if "load" in raw:
        assert project.loads[0].components[1] == -raw["load"]["magnitude"] * 1000
    else:
        assert project.loads[0].components[1] == raw["loads"][0]["components"][1] * 1000


@pytest.mark.parametrize("name", ["staged_v1", "every_field_2d_v1", "seed_3d_v1",
                                  "single_load_2d", "simple_example_3d"])
def test_every_old_fixture_opens(name):
    assert Project.model_validate(fixture(name)).unit_system == "SI"


def test_a_legacy_phases_file_still_opens():
    """Before the rename the sequence was saved as "phases"; it opens as stages, ids kept."""
    doc = fixture("staged_v1")
    assert "phases" in doc and "stages" not in doc
    project = Project.model_validate(doc)
    assert [s.id for s in project.stages] == [p["id"] for p in doc["phases"]]
    assert "phases" not in project.model_dump(mode="json")


def test_a_converted_project_is_stable(new):
    """Converted once: saving and opening it again changes nothing."""
    assert Project.model_validate(new.model_dump(mode="json")) == new


# ── Old-shaped records inside a current project ─────────────────────────────

def test_an_old_shaped_section_in_a_kn_project_arrives_in_kilonewtons():
    """A script written against the old fields, run against a project in the kN system:
    the record is read as the old exporter would have (kN -> SI) and then expressed in
    the project's own system."""
    data = Project.model_validate(fixture("staged_v1")).model_dump(mode="json")
    data, _ = __import__("core.model.units", fromlist=["units"]).convert_project(data, "kN")
    data["beam_sections"] = [{"id": "az26", "name": "AZ 26", "E": 2.1e8, "nu": 0.3,
                              "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0,
                              "spacing": 1.0, "shear_area": 0.01, "inertia_minor": 1e-4,
                              "torsional_inertia": 2e-4}]
    data["beams"][0]["section"] = "az26"
    data["anchor_sections"][0] = {"id": data["anchor_sections"][0]["id"], "name": "t",
                                  "E": 2.1e8, "area": 1e-3, "density": 0.0,
                                  "tension_limit": 500.0}
    project = Project.model_validate(data)
    beam = project.beam_section("az26").variables
    assert beam["YOUNG_MODULUS"] == pytest.approx(2.1e8)        # kPa, as typed in kN/m2
    assert beam["DENSITY"] == pytest.approx(7.85)                # t/m3
    assert (beam["AREA_EFFECTIVE_Y"], beam["I22"], beam["TORSIONAL_INERTIA"]) == (0.01, 1e-4, 2e-4)
    assert project.anchor_sections[0].tension_limit == pytest.approx(500.0)   # kN


def test_an_old_shaped_material_takes_the_projects_water():
    data = Project.model_validate(fixture("staged_v1")).model_dump(mode="json")
    data["water"]["specific_weight"] = 9_810.0                   # N/m3, the SI project's
    old = fixture("staged_v1")["materials"][0]
    data["materials"][0] = old
    project = Project.model_validate(data)
    assert project.materials[0].variables["DENSITY_WATER"] == pytest.approx(1000.0)
    # Only the record: the project's loads are its own already, not kN to be multiplied
    # (it used to read the whole document as an old file and crash on the new soil).
    assert project.loads[0].components == tuple(data["loads"][0]["components"])
    assert project.materials[1].variables == data["materials"][1]["variables"]


def test_things_that_are_not_records_pass_through_untouched():
    assert migration._scaled("x", "pressure") == "x"
    assert migration._load({"id": "l"}) == {"id": "l"}
    assert migration.migrate_records({"materials": [{"id": "m", "variables": {}}]}) == \
        {"materials": [{"id": "m", "variables": {}}]}
