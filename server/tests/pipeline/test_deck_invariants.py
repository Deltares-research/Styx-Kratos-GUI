"""`check_deck` itself: silent on a sound deck, and each rule fires on a deck broken in
exactly that way. A checker that has never been seen to fail proves nothing about the
decks it passes."""

from __future__ import annotations

import json
import re

import pytest

from app import build, kratos
from tests.models import excavation
from app.schemas import MeshRequest
from tests.pipeline.deck_invariants import check_deck


@pytest.fixture(scope="module")
def export():
    with build.session():
        return kratos.export_project(excavation.excavation_project(staged=True),
                                     MeshRequest(element_size=8.0, order=2))


def broken(export, **changes) -> dict:
    copy = dict(export)
    copy.update(changes)
    return copy


def params(export) -> dict:
    return json.loads(export["project_parameters"])


def rules(violations) -> set[str]:
    return {v.split(":")[0] for v in violations}


def test_a_sound_deck_has_no_violations(export):
    assert check_deck(export) == []


def test_rule_1_an_element_naming_a_missing_node(export):
    mdpa = re.sub(r"(Begin Elements \S+\s+\d+\s+\d+\s+)(\d+)",
                  lambda m: m.group(1) + "999999", export["mdpa"], count=1)
    assert "rule 1" in rules(check_deck(broken(export, mdpa=mdpa)))


def test_rule_2_an_undeclared_property(export):
    mdpa = export["mdpa"].replace("Begin Properties 0", "Begin Properties 7", 1)
    assert "rule 2" in rules(check_deck(broken(export, mdpa=mdpa)))


def test_rule_3_a_material_on_a_part_the_deck_lacks(export):
    materials = json.loads(export["materials"])
    materials["properties"][0]["model_part_name"] = "PorousDomain.Nowhere"
    assert "rule 3" in rules(check_deck(broken(export, materials=json.dumps(materials))))


def test_rule_4_two_materials_sharing_a_property_id(export):
    materials = json.loads(export["materials"])
    materials["properties"][1]["properties_id"] = materials["properties"][0]["properties_id"]
    assert "rule 4" in rules(check_deck(broken(export, materials=json.dumps(materials))))


def test_rule_5_a_process_on_a_part_the_deck_lacks(export):
    p = params(export)
    stage = next(iter(p["stages"].values()))
    stage["stage_settings"]["processes"]["constraints_process_list"][0]["Parameters"][
        "model_part_name"] = "PorousDomain.Ghost"
    assert "rule 5" in rules(check_deck(broken(export, project_parameters=json.dumps(p))))


def test_rule_5_an_activation_of_a_part_the_deck_lacks(export):
    p = params(export)
    stage = next(iter(p["stages"].values()))
    stage["stage_preprocess"]["operations"][0]["Parameters"]["model_part_name_list"].append(
        "PorousDomain.Ghost")
    assert "rule 5" in rules(check_deck(broken(export, project_parameters=json.dumps(p))))


def test_rule_6_a_stage_missing_from_the_run_order(export):
    p = params(export)
    p["orchestrator"]["settings"]["execution_list"].pop()
    assert "rule 6" in rules(check_deck(broken(export, project_parameters=json.dumps(p))))


def test_rule_8_an_orphan_node(export):
    mdpa = export["mdpa"].replace("End Nodes", "999999 1.0 2.0 0.0\nEnd Nodes", 1)
    assert "rule 8" in rules(check_deck(broken(export, mdpa=mdpa)))


def test_rule_9_a_3d_class_in_a_section(export):
    mdpa = export["mdpa"].replace("SmallStrainUPwDiffOrderElement2D6N",
                                  "SmallStrainUPwDiffOrderElement3D6N", 1)
    assert "rule 9" in rules(check_deck(broken(export, mdpa=mdpa)))


def test_rule_10_a_linear_condition_in_a_quadratic_section(export):
    mdpa = export["mdpa"].replace("LineLoadDiffOrderCondition2D3N",
                                  "UPwFaceLoadCondition2D2N", 1)
    assert "rule 10" in rules(check_deck(broken(export, mdpa=mdpa)))


def test_rule_11_a_stiffness_left_in_kilopascals(export):
    materials = json.loads(export["materials"])
    materials["properties"][0]["Material"]["Variables"]["YOUNG_MODULUS"] = 900.0
    assert "rule 11" in rules(check_deck(broken(export, materials=json.dumps(materials))))


def test_rule_11_a_density_given_as_a_unit_weight(export):
    materials = json.loads(export["materials"])
    materials["properties"][0]["Material"]["Variables"]["DENSITY_SOLID"] = 18.0
    assert "rule 11" in rules(check_deck(broken(export, materials=json.dumps(materials))))


def test_rule_12_a_k0_stage_with_a_soil_missing_k0_nc(export):
    initial = json.loads(export["initial_materials"])
    initial["properties"][0]["Material"]["Variables"].pop("K0_NC")
    assert "rule 12" in rules(check_deck(broken(export, initial_materials=json.dumps(initial))))


def test_rule_12_a_k0_stage_reading_a_file_that_was_not_written(export):
    assert "rule 12" in rules(check_deck(broken(export, initial_materials=None)))


def test_a_mesh_exported_for_its_numbering_only_carries_no_materials_to_check(export):
    """`include_materials=False` (labels, node parts): nobody runs that deck."""
    assert check_deck(broken(export, materials=None, initial_materials=None)) == []


def test_rule_13_a_line_condition_traversed_against_its_element(export):
    mdpa = re.sub(r"(Begin Conditions LineLoadDiffOrderCondition2D3N\s+\d+\s+\d+\s+)(\d+)(\s+)(\d+)",
                  lambda m: m.group(1) + m.group(4) + m.group(3) + m.group(2),
                  export["mdpa"], count=1)
    assert mdpa != export["mdpa"]
    assert "rule 13" in rules(check_deck(broken(export, mdpa=mdpa)))


def test_rule_14_a_stage_that_reads_the_mesh_twice(export):
    p = params(export)
    first = next(iter(p["stages"].values()))
    first["stage_settings"]["solver_settings"]["model_import_settings"] = {
        "input_type": "mdpa", "input_filename": "x"}
    assert "rule 14" in rules(check_deck(broken(export, project_parameters=json.dumps(p))))
