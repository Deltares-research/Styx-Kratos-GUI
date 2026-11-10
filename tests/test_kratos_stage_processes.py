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
from core.model.schemas import MeshRequest, Project


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
    assert len(parts) == 7
    assert not [name for name in parts if "Interface" in name]
    assert "SheetPileWall" not in parts


def test_the_k0_procedure_also_sets_up_drawn_soil():
    """A drawn part with a material is ground like a soil layer is. Named by the
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
                        "find_neighbours_of_interfaces_process")) == 7


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
    assert not [name for name in fourth if name.endswith("lift_1")]
    assert [name for name in fourth if name.endswith("lift_2")]


# -- C3: extrapolation and JSON output ---------------------------------------

def test_results_are_extrapolated_from_the_wall_and_the_interfaces(doc):
    """Two processes, because the reference writes one per group that shares a variable
    list: the wall's forces and the contacts' tractions."""
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


def test_only_the_interfaces_still_in_the_stage_are_extrapolated(doc):
    """A contact goes with the soil it runs against, and then has nothing to report."""
    module = "geo_extrapolate_integration_point_values_to_nodes_process"

    def contacts(stage):
        written = [p for p in processes(doc, stage, "auxiliary_process_list")
                   if p["python_module"] == module]
        return named(written[1])

    assert len(contacts("3_SheetPileWall_installation")) == 7
    assert [name for name in contacts("3_SheetPileWall_installation") if "lift_1" in name]
    assert len(contacts("4_First_excavation")) == 6
    assert not [name for name in contacts("4_First_excavation") if "lift_1" in name]


def test_nothing_is_extrapolated_before_the_wall_exists(doc):
    module = "geo_extrapolate_integration_point_values_to_nodes_process"
    assert stages_with(doc, "auxiliary_process_list", module) == STAGES[2:]


def test_each_stage_writes_its_own_json_output_files(doc):
    """One per member per stage, named after it, so a seven-stage run does not write
    seven times into the same files."""
    for stage in STAGES[2:]:
        written = processes(doc, stage, "json_output")
        assert [p["Parameters"]["output_file_name"] for p in written] == [
            f"{stage}__output_wall.json", f"{stage}__output_interface_left.json",
            f"{stage}__output_interface_right.json"]
    assert processes(doc, "1_Initial_stage", "json_output") == []


def test_the_interface_output_reads_the_node_part_built_for_each_face(doc):
    written = processes(doc, "3_SheetPileWall_installation", "json_output")
    assert named(written[1]) == ["Interface_Left_face"]
    assert named(written[2]) == ["Interface_Right_face"]


def face_heights(result: dict, doc: dict, stage: str, face: str) -> list[float]:
    """The heights of the nodes a stage's curve of `face` reads, highest first."""
    written = [p for p in processes(doc, stage, "json_output")
               if p["Parameters"]["output_file_name"].endswith(f"interface_{face}.json")]
    lines = result["mdpa"].splitlines()
    start = lines.index(f"Begin SubModelPart {named(written[0])[0]}")
    block = "\n".join(lines[start:]).partition("Begin SubModelPartNodes")[2]
    nodes = block.partition("End SubModelPartNodes")[0].split()
    assert nodes, "the curve reads no nodes"
    height = {index: y for index, _, y, _ in result["nodes"]}
    return sorted((height[int(node)] for node in nodes), reverse=True)


@pytest.mark.parametrize("stage, floor", [("4_First_excavation", excavation.LIFTS[0]),
                                          ("5_Strut_installation", excavation.LIFTS[0]),
                                          ("6_Second_excavation", excavation.LIFTS[1]),
                                          ("7_Third_excavation", excavation.LIFTS[2])])
def test_the_curve_of_a_dug_face_starts_at_the_pit_floor(result, doc, stage, floor):
    """A contact that is switched off no longer updates its nodes: they would plot the
    tractions of the stage before, against soil that is gone."""
    assert face_heights(result, doc, stage, "left")[0] == pytest.approx(floor)


@pytest.mark.parametrize("stage", STAGES[3:])
def test_the_curve_of_a_retained_face_stays_whole(result, doc, stage):
    assert face_heights(result, doc, stage, "right") == face_heights(
        result, doc, "3_SheetPileWall_installation", "right")


def test_a_contact_on_one_face_writes_a_curve_of_that_face_only():
    project = excavation.excavation_project(staged=True)
    payload = project.model_dump()
    payload["interfaces"][0]["side"] = "right"
    with session():
        one_sided = writer.export_project(Project.model_validate(payload),
                                          MeshRequest(**project.mesh.model_dump()))
    written = processes(json.loads(one_sided["project_parameters"]), "7_Third_excavation",
                        "json_output")
    assert [p["Parameters"]["output_file_name"] for p in written] == [
        "7_Third_excavation__output_wall.json",
        "7_Third_excavation__output_interface_right.json"]


# -- The node part of each face of the wall ------------------------------------

@pytest.mark.parametrize("part", ["Interface_Left_face", "Interface_Right_face"])
def test_a_face_s_node_part_is_in_the_mdpa(result, part):
    assert f"Begin SubModelPart {part}" in result["mdpa"]


@pytest.mark.parametrize("part", ["Interface_Left_face", "Interface_Right_face"])
def test_a_face_s_node_part_holds_nodes_and_no_elements(result, part):
    block = result["mdpa"].partition(
        f"Begin SubModelPart {part}")[2].partition("End SubModelPart")[0]
    assert "Begin SubModelPartNodes" in block
    assert "Begin SubModelPartElements\n" not in block


def test_an_unstaged_project_grows_no_part_it_never_reads():
    """It exists only because the `JsonOutputProcess` of a staged deck reads it."""
    project = excavation.excavation_project(staged=False)
    with session():
        plain = writer.export_project(project,
                                      MeshRequest(**project.mesh.model_dump()))
    assert "_face" not in plain["mdpa"]


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
                        module)) == 7
    assert module not in modules(from_the_start, "2_Null_step", "auxiliary_process_list")
