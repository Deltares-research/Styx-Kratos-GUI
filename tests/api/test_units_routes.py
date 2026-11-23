"""Switching the project's unit system, and the 2D/3D switch carrying the soil laws with
it (PATCH /api/project/units, PATCH /api/project/dimension)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from core.model import units
from tests.models import excavation
from backend.main import app
from core.model.schemas import Project


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/project/reset")


def put(client, project: Project) -> None:
    assert client.put("/api/project", json=project.model_dump(mode="json")).status_code == 200


def current(client) -> Project:
    return Project.model_validate(client.get("/api/project").json())


def every_field() -> Project:
    """A 2D project with a value in every place a unit lives."""
    from tests.test_legacy import fixture
    return Project.model_validate(fixture("every_field_2d_v1"))


def test_a_project_starts_in_si(client):
    assert current(client).unit_system == "SI"


def test_switching_to_kn_converts_every_dimensioned_value(client):
    before = every_field()
    put(client, before)
    answer = client.patch("/api/project/units", json={"unit_system": "kN"})
    assert answer.status_code == 200, answer.text
    after = current(client)
    assert after.unit_system == "kN"

    soil, soil0 = after.materials[0], before.materials[0]
    assert soil.variables["YOUNG_MODULUS"] == pytest.approx(soil0.variables["YOUNG_MODULUS"] / 1000)
    assert soil.variables["DENSITY_SOLID"] == pytest.approx(soil0.variables["DENSITY_SOLID"] / 1000)
    assert soil.variables["POISSON_RATIO"] == soil0.variables["POISSON_RATIO"]
    assert soil.variables["GEO_FRICTION_ANGLE"] == soil0.variables["GEO_FRICTION_ANGLE"]
    assert soil.variables["PERMEABILITY_XX"] == soil0.variables["PERMEABILITY_XX"]
    assert soil.variables["GEO_DRAINAGE_TYPE"] == soil0.variables["GEO_DRAINAGE_TYPE"]

    beam, beam0 = after.beam_sections[0], before.beam_sections[0]
    assert beam.variables["YOUNG_MODULUS"] == pytest.approx(beam0.variables["YOUNG_MODULUS"] / 1000)
    assert beam.variables["DENSITY"] == pytest.approx(beam0.variables["DENSITY"] / 1000)
    assert beam.variables["I33"] == beam0.variables["I33"]

    contact, contact0 = after.interface_sections[0], before.interface_sections[0]
    assert contact.variables["INTERFACE_NORMAL_STIFFNESS"] == pytest.approx(
        contact0.variables["INTERFACE_NORMAL_STIFFNESS"] / 1000)

    assert after.anchor_sections[0].tension_limit == pytest.approx(
        before.anchor_sections[0].tension_limit / 1000)
    assert after.anchors[0].prestress == pytest.approx(before.anchors[0].prestress / 1000)
    assert after.loads[0].components[1] == pytest.approx(before.loads[0].components[1] / 1000)
    uniform = next(n for n in after.normal_loads if n.fluid_pressure_type == "Uniform")
    uniform0 = next(n for n in before.normal_loads if n.fluid_pressure_type == "Uniform")
    assert uniform.pressure == pytest.approx(uniform0.pressure / 1000)
    assert after.water.specific_weight == pytest.approx(before.water.specific_weight / 1000)
    # Geometry is metres in both systems, and is not touched.
    assert after.domain == before.domain and after.beams == before.beams


def test_a_round_trip_returns_the_same_numbers(client):
    before = every_field()
    put(client, before)
    client.patch("/api/project/units", json={"unit_system": "kN"})
    client.patch("/api/project/units", json={"unit_system": "SI"})
    after = current(client)
    for m, m0 in zip(after.materials, before.materials):
        for name, value in m0.variables.items():
            expected = value if isinstance(value, str) else pytest.approx(value, rel=1e-12)
            assert m.variables[name] == expected, name


def test_the_same_system_again_changes_nothing(client):
    put(client, every_field())
    before = current(client)
    answer = client.patch("/api/project/units", json={"unit_system": "SI"})
    assert answer.status_code == 200
    assert current(client) == before


def test_a_variable_whose_dimension_is_unknown_is_kept_and_named(client):
    project = every_field()
    data = project.model_dump(mode="json")
    data["materials"][0]["variables"]["UMAT_PARAMETERS"] = [1.0, 2.0]
    data["materials"][0]["variables"]["MY_STIFFNESS"] = 5.0
    put(client, Project.model_validate(data))
    answer = client.patch("/api/project/units", json={"unit_system": "kN"}).json()
    assert any("UMAT_PARAMETERS" in note and "MY_STIFFNESS" in note for note in answer["notes"])
    assert current(client).materials[0].variables["MY_STIFFNESS"] == 5.0


def test_an_unknown_system_is_refused(client):
    assert client.patch("/api/project/units", json={"unit_system": "imperial"}).status_code == 422


def test_the_kn_deck_is_the_si_deck_in_kilonewtons(client):
    """Kratos has no units: the same model in the kN system writes every force-bearing
    number a thousand times smaller and everything else the same."""
    from core.geometry import solid_model
    from core.kratos import writer
    from core.model.schemas import MeshRequest

    si = excavation.excavation_project(staged=True)
    kn_payload, _ = units.convert_project(si.model_dump(mode="json"), "kN")
    kn = Project.model_validate(kn_payload)
    with solid_model.session():
        a = writer.export_project(si, MeshRequest(element_size=8.0, order=2))
        b = writer.export_project(kn, MeshRequest(element_size=8.0, order=2))
    assert a["mdpa"] == b["mdpa"]
    ma, mb = json.loads(a["materials"]), json.loads(b["materials"])
    for pa, pb in zip(ma["properties"], mb["properties"]):
        for name, value in pa["Material"]["Variables"].items():
            quantity = units.VARIABLES.get(name, units.DIMENSIONLESS)
            if isinstance(value, float):
                assert pb["Material"]["Variables"][name] == pytest.approx(
                    units.convert(value, quantity, "SI", "kN"), rel=1e-12), name
    pa, pb = json.loads(a["project_parameters"]), json.loads(b["project_parameters"])
    gravity = [p for s in pa["stages"].values()
               for p in s["stage_settings"]["processes"]["loads_process_list"]
               if p["Parameters"]["variable_name"] == "VOLUME_ACCELERATION"]
    gravity_kn = [p for s in pb["stages"].values()
                  for p in s["stage_settings"]["processes"]["loads_process_list"]
                  if p["Parameters"]["variable_name"] == "VOLUME_ACCELERATION"]
    assert gravity == gravity_kn


def test_going_to_3d_carries_the_soil_law_with_it(client):
    put(client, excavation.excavation_project(staged=True))
    answer = client.patch("/api/project/dimension", json={"dimension": 3})
    assert answer.status_code == 200, answer.text
    assert {m.constitutive_law for m in current(client).materials} == {
        "GeoIncrementalLinearElastic3DLaw"}
    client.patch("/api/project/dimension", json={"dimension": 2})
    assert {m.constitutive_law for m in current(client).materials} == {
        "GeoLinearElasticPlaneStrain2DLaw"}


def test_a_law_this_application_cannot_pair_is_kept_and_named(client):
    data = excavation.excavation_project(staged=False).model_dump(mode="json")
    data["materials"][0]["constitutive_law"] = "SmallStrainUMAT2DPlaneStrainLaw"
    put(client, Project.model_validate(data))
    answer = client.patch("/api/project/dimension", json={"dimension": 3}).json()
    assert current(client).materials[0].constitutive_law == "SmallStrainUMAT2DPlaneStrainLaw"
    assert any("SmallStrainUMAT2DPlaneStrainLaw" in note for note in answer["notes"])
