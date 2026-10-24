"""The processes a staged deck carries, and which stages carry them.

Two questions, and they are separate. *What* a process looks like is settled by copying
the reference deck field for field (`core/kratos/parameters.py`). *Which stages it belongs
in* is derived from the stage tree (`core/kratos/writer.py:_staged_stages`), and that is what
most of this file is about, because it is the part that can be wrong in a way no schema
catches.

Reference: `staged_construction_for_generated_mesh.json`. Plan sec C3, C4, C6, C7.
"""

import json

import pytest

from core.kratos import writer, materials
from core.model import stages
from tests.models import drawn_ground, excavation
from core.geometry.solid_model import session
from core.model.schemas import MeshRequest


@pytest.fixture(scope="module")
def result() -> dict:
    project = excavation.excavation_project(staged=True)
    with session():
        return writer.export_project(project,
                                     MeshRequest(**project.mesh.model_dump()))


@pytest.fixture(scope="module")
def doc(result) -> dict:
    return json.loads(result["project_parameters"])


STAGES = ["1_Initial_stage", "2_Null_step", "3_SheetPileWall_installation",
          "4_First_excavation", "5_Strut_installation", "6_Second_excavation",
          "7_Third_excavation"]


def processes(doc: dict, stage: str, listing: str) -> list[dict]:
    return doc["stages"][stage]["stage_settings"]["processes"].get(listing, [])


def modules(doc: dict, stage: str, listing: str) -> list[str]:
    return [p["python_module"] for p in processes(doc, stage, listing)]


def named(process: dict) -> list[str]:
    p = process["Parameters"]
    if "model_part_name_list" in p:
        return [n.partition(".")[2] for n in p["model_part_name_list"]]
    return [p["model_part_name"].partition(".")[2]]


def carrying(doc: dict, stage: str, listing: str, module: str) -> list[str]:
    """The parts named by the one process of `module` in that stage's `listing`."""
    found = [p for p in processes(doc, stage, listing) if p["python_module"] == module]
    assert len(found) == 1, f"{module} appears {len(found)} times in {stage}"
    return named(found[0])


def stages_with(doc: dict, listing: str, module: str) -> list[str]:
    return [stage for stage in STAGES if module in modules(doc, stage, listing)]


# -- C3: the active-parts filter ---------------------------------------------

def test_a_process_is_written_only_while_the_part_it_names_is_active(doc):
    """One rule delivers both halves of the reference's behaviour -- the left-edge
    rollers that vanish as the pit is dug, and the strut's support that arrives with the
    strut -- and it is applied in one place rather than per process type."""
    edges = {stage: [n for n in
                     [named(p)[0] for p in processes(doc, stage,
                                                     "constraints_process_list")
                      if p["python_module"] == "apply_vector_constraint_table_process"]
                     if n.endswith("_Left_Edge") and "lift" in n]
             for stage in STAGES}
    assert len(edges["1_Initial_stage"]) == 3
    assert len(edges["4_First_excavation"]) == 2
    assert len(edges["6_Second_excavation"]) == 1
    assert edges["7_Third_excavation"] == []


def test_a_support_arrives_with_the_structure_it_holds(doc):
    """`Strut_Support` is the pinned far end of the anchor. Before the anchor is
    installed there is nothing there to pin, and the reference does not name it."""
    def holds(stage):
        return any("Strut_Support" in named(p)
                   for p in processes(doc, stage, "constraints_process_list"))
    assert not holds("4_First_excavation")
    assert holds("5_Strut_installation") and holds("7_Third_excavation")


def test_each_water_load_arrives_with_its_own_excavation(doc):
    """The reference changes the exposed water surface per lift: `WaterLoad_Stage2`
    arrives as `WaterLoad_Stage1` leaves. Nothing special happens here -- the stages say
    so, and the filter does the rest."""
    def water(stage):
        return sorted(named(p)[0] for p in processes(doc, stage, "loads_process_list")
                      if p["python_module"] == "apply_normal_load_table_process")
    assert water("1_Initial_stage") == []
    assert water("3_SheetPileWall_installation") == []
    assert water("4_First_excavation") == ["WaterLoad_Stage1"]
    assert water("6_Second_excavation") == ["WaterLoad_Stage2"]
    assert water("7_Third_excavation") == ["WaterLoad_Stage3"]


def test_the_surcharge_arrives_with_the_wall_and_stays(doc):
    def loaded(stage):
        return any(named(p)[0] == "Load"
                   for p in processes(doc, stage, "loads_process_list"))
    assert not loaded("1_Initial_stage") and not loaded("2_Null_step")
    assert all(loaded(stage) for stage in STAGES[2:])


# -- C3: the K0 procedure ----------------------------------------------------

def test_the_k0_procedure_runs_in_the_k0_stage_only(doc):
    assert stages_with(doc, "auxiliary_process_list",
                       "apply_k0_procedure_process") == ["1_Initial_stage"]


def test_the_k0_procedure_names_the_soil_and_only_the_soil(doc):
    parts = carrying(doc, "1_Initial_stage", "auxiliary_process_list",
                     "apply_k0_procedure_process")
    assert len(parts) == 8
    assert not [name for name in parts if "Interface" in name]
    assert "SheetPileWall" not in parts


def test_the_k0_procedure_also_sets_up_drawn_soil():
    """A drawn part with a material is ground like a borehole layer is. Named by the
    `soil_` key prefix, the K0 stage set up the layer and left the fill on top of it with
    whatever the elastic gravity step gave it."""
    project = drawn_ground.project()
    with session():
        export = writer.export_project(project)
    parts = carrying(json.loads(export["project_parameters"]), "1_Initial",
                     "auxiliary_process_list", "apply_k0_procedure_process")
    assert parts == ["Ground", "Fill_left", "Fill_right"]


# -- C3: interfaces ----------------------------------------------------------

def test_neighbours_are_found_in_the_stage_the_interfaces_arrive(doc):
    """Before that they are not in the model; afterwards what it found is still
    recorded, so the reference runs it exactly once."""
    assert stages_with(doc, "auxiliary_process_list",
                       "find_neighbours_of_interfaces_process") == \
        ["3_SheetPileWall_installation"]
    assert len(carrying(doc, "3_SheetPileWall_installation", "auxiliary_process_list",
                        "find_neighbours_of_interfaces_process")) == 8


def test_stresses_carry_over_from_the_stage_after_the_wall_goes_in(doc):
    """Not in stages 1-3: there is nothing structural in the model before the wall, and
    in the stage it arrives it has no previous stress to carry."""
    assert stages_with(doc, "auxiliary_process_list",
                       "apply_final_stresses_of_previous_stage_to_initial_state") == \
        STAGES[3:]


def test_a_part_installed_this_stage_has_no_previous_stress_to_carry(doc):
    """The reference leaves the anchor out of stage 5, where it arrives, and puts it
    back in stage 6. Nothing else distinguishes those two stages."""
    module = "apply_final_stresses_of_previous_stage_to_initial_state"
    assert "Strut" not in carrying(doc, "5_Strut_installation",
                                   "auxiliary_process_list", module)
    assert "Strut" in carrying(doc, "6_Second_excavation",
                               "auxiliary_process_list", module)


def test_a_dug_out_lifts_interface_stops_carrying_stress(doc):
    module = "apply_final_stresses_of_previous_stage_to_initial_state"
    fourth = carrying(doc, "4_First_excavation", "auxiliary_process_list", module)
    assert not [name for name in fourth if name.endswith("lift1")]
    assert [name for name in fourth if name.endswith("lift2")]


# -- C3: extrapolation and JSON output ---------------------------------------

def test_results_are_extrapolated_from_the_wall_and_the_retained_interfaces(doc):
    """Two processes, because the reference writes one per group that shares a variable
    list: the wall's forces and the retained side's tractions."""
    module = "geo_extrapolate_integration_point_values_to_nodes_process"
    written = [p for p in processes(doc, "4_First_excavation", "auxiliary_process_list")
               if p["python_module"] == module]
    assert len(written) == 2
    wall, interface = written
    assert named(wall) == ["SheetPileWall"]
    assert wall["Parameters"]["list_of_variables"] == \
        ["AXIAL_FORCE", "BENDING_MOMENT", "SHEAR_FORCE"]
    assert interface["Parameters"]["list_of_variables"] == \
        ["GEO_EFFECTIVE_TRACTION_VECTOR"]


def test_only_the_retained_side_interfaces_are_extrapolated(doc):
    """The three against soil outside the pit -- the reference's `*_Right` ones. The
    contacts on the dug side are excavated away and have nothing to report."""
    module = "geo_extrapolate_integration_point_values_to_nodes_process"
    written = [p for p in processes(doc, "3_SheetPileWall_installation",
                                    "auxiliary_process_list")
               if p["python_module"] == module]
    retained = named(written[1])
    assert len(retained) == 3
    assert not [name for name in retained if "lift" in name or "pit" in name]


def test_nothing_is_extrapolated_before_the_wall_exists(doc):
    module = "geo_extrapolate_integration_point_values_to_nodes_process"
    assert stages_with(doc, "auxiliary_process_list", module) == STAGES[2:]


def test_each_stage_writes_its_own_json_output_files(doc):
    """One per stage, named after it, so a seven-stage run leaves seven pairs rather
    than seven writes into the same two files."""
    for stage in STAGES[2:]:
        written = processes(doc, stage, "json_output")
        assert [p["Parameters"]["output_file_name"] for p in written] == [
            f"{stage}__output_wall.json", f"{stage}__output_interface.json"]
    assert processes(doc, "1_Initial_stage", "json_output") == []


def test_the_interface_output_reads_the_node_part_built_for_it(doc):
    written = processes(doc, "7_Third_excavation", "json_output")
    assert named(written[1]) == [writer.RIGHT_SIDE_PART]


# -- C7: Right_Side_Of_Right_Interfaces --------------------------------------

def test_the_retained_side_node_part_is_in_the_mdpa(result):
    assert f"Begin SubModelPart {writer.RIGHT_SIDE_PART}" in result["mdpa"]


def test_the_retained_side_node_part_holds_nodes_and_no_elements(result):
    block = result["mdpa"].partition(
        f"Begin SubModelPart {writer.RIGHT_SIDE_PART}")[2].partition("End SubModelPart")[0]
    assert "Begin SubModelPartNodes" in block
    assert "Begin SubModelPartElements\n" not in block


def test_an_unstaged_project_grows_no_part_it_never_reads():
    """It exists only because the `JsonOutputProcess` of a staged deck reads it."""
    project = excavation.excavation_project(staged=False)
    with session():
        plain = writer.export_project(project,
                                      MeshRequest(**project.mesh.model_dump()))
    assert writer.RIGHT_SIDE_PART not in plain["mdpa"]


# -- C6: master/slave across the pre-installation stages ---------------------

def test_the_split_soil_is_tied_back_together_until_the_wall_arrives(doc):
    """Deactivating an interface removes its contact stiffness but does nothing to
    reconnect the two soil copies the split made, so without the tie the initial stage
    -- meant to be undisturbed ground -- models two disconnected halves. The reference
    ties in stages 1 and 2 and stops."""
    assert stages_with(doc, "constraints_process_list",
                       "assign_master_slave_constraints_to_neighbours_process") == \
        ["1_Initial_stage", "2_Null_step"]


# -- C4: the two materials files ---------------------------------------------

def test_the_initial_stage_reads_a_materials_file_of_its_own(doc):
    def materials(stage):
        return doc["stages"][stage]["stage_settings"]["solver_settings"][
            "material_import_settings"]["materials_filename"]
    assert materials("1_Initial_stage") == "initial_materials.json"
    assert {materials(stage) for stage in STAGES[1:]} == {"MaterialParameters.json"}


def test_a_staged_export_returns_both_materials_files(result):
    assert result["materials"] and result["initial_materials"]


def test_the_initial_file_is_the_main_one_plus_the_two_k0_variables(result):
    """That is the whole difference between the reference's two files -- there is no
    'linear elastic for K0, the real law afterwards' story in it. `K0_NC` and
    `K0_MAIN_DIRECTION` are what `apply_k0_procedure_process` reads, and only the
    initial stage runs it."""
    main = {p["model_part_name"]: p for p in json.loads(result["materials"])["properties"]}
    initial = {p["model_part_name"]: p
               for p in json.loads(result["initial_materials"])["properties"]}
    assert set(main) == set(initial)
    for name, entry in main.items():
        was, now = entry["Material"], initial[name]["Material"]
        assert was["constitutive_law"] == now["constitutive_law"]
        extra = {k: v for k, v in now["Variables"].items()
                 if k not in was["Variables"]}
        assert not [k for k in was["Variables"] if k not in now["Variables"]]
        assert extra in ({}, {"K0_MAIN_DIRECTION": 1,
                              "K0_NC": extra.get("K0_NC")})


def test_only_the_soil_carries_the_k0_variables(result):
    """A beam, a tendon and an interface have no K0 -- the reference adds the two
    variables to its two soil property sets and to nothing else."""
    initial = json.loads(result["initial_materials"])["properties"]
    with_k0 = [p["model_part_name"] for p in initial
               if "K0_NC" in p["Material"]["Variables"]]
    assert with_k0 and not [n for n in with_k0
                            if "SheetPileWall" in n or "Strut" in n or "Interface" in n]


def test_k0_nc_is_jaky_unless_the_material_says_otherwise():
    """The test model types 0.58 and 0.47, which are Jaky at its two friction angles --
    so its typed K0_NC and the fallback agree."""
    from core.kratos.materials import jaky
    project = excavation.excavation_project(staged=False)
    for key, k0 in (("m_upper", 0.58), ("m_lower", 0.47)):
        material = project.material(key)
        assert material.variables["K0_NC"] == k0
        assert round(jaky(material), 2) == k0


def test_an_unstaged_project_gets_no_second_materials_file():
    project = excavation.excavation_project(staged=False)
    with session():
        plain = writer.export_project(project,
                                      MeshRequest(**project.mesh.model_dump()))
    assert plain["materials"] and plain["initial_materials"] is None


def test_material_parameters_writes_the_k0_variables_on_request():
    """The same generator with a keyword, not a second one: two generators would be two
    places for a material to be described, and they would drift."""
    project = excavation.excavation_project(staged=False)
    parts = [("Soil_Top", "m_upper")]
    plain, _ = materials.material_parameters(project, parts, 2)
    with_k0, _ = materials.material_parameters(project, parts, 2, k0=True)
    variables = json.loads(with_k0)["properties"][0]["Material"]["Variables"]
    assert "K0_NC" not in json.loads(plain)["properties"][0]["Material"]["Variables"]
    assert variables["K0_MAIN_DIRECTION"] == 1
    assert round(variables["K0_NC"], 2) == 0.58


# -- What is built from the start ----------------------------------------------
#
# "Create default stages" switches nothing off (`stages.default_stages`), so a wall and
# its interfaces drawn before that are in the model from the first stage. There is no
# stage before the first for them to carry a stress from, and the first stage is where
# they arrive.

@pytest.fixture(scope="module")
def from_the_start() -> dict:
    project = excavation.excavation_project(staged=False)
    project = project.model_copy(update={"stages": stages.default_stages(project)})
    with session():
        exported = writer.export_project(project, MeshRequest(**project.mesh.model_dump()))
    return json.loads(exported["project_parameters"])


def test_nothing_carries_a_stress_into_the_first_stage(from_the_start):
    module = "apply_final_stresses_of_previous_stage_to_initial_state"
    assert module not in modules(from_the_start, "1_Initial_stage", "auxiliary_process_list")
    carried = carrying(from_the_start, "2_Null_step", "auxiliary_process_list", module)
    assert "SheetPileWall" in carried and [name for name in carried if "Interface" in name]


def test_interfaces_built_from_the_start_find_their_neighbours_in_the_first_stage(
        from_the_start):
    module = "find_neighbours_of_interfaces_process"
    assert len(carrying(from_the_start, "1_Initial_stage", "auxiliary_process_list",
                        module)) == 8
    assert module not in modules(from_the_start, "2_Null_step", "auxiliary_process_list")
