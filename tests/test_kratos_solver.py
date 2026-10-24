"""The half of ProjectParameters.json that makes the deck runnable.

`core.kratos.parameters` used to leave `problem_data` and `solver_settings` empty, which
made the export a deck Kratos could read and not one it could run. It now fills both
from a documented default analysis (see `parameters.DEFAULTS`), so that pressing
Calculate has something to hand the orchestrator.

The two reference decks these are checked against both ship with Kratos itself:
`GeoMechanicsApplication/tests/test_interface_prestress/ProjectParameters_stage1.json`
(a static U_Pw analysis with an interface) and this repo's own
`test/ProjectParameters_stage1.json`.
"""

import json

import pytest

from core.geometry import solid_model
from core.kratos import writer, parameters
from core.model.schemas import LineLoad, MeshRequest, Project
from core.model.templates import seed_project

PILE_SECTION = {"id": "az26", "name": "AZ 26-700", "E": 2.1e8, "nu": 0.3,
                "area": 0.0198, "inertia": 5.52e-4, "density": 7850.0, "spacing": 1.0}
PILE = {"id": "pile_1", "name": "Sheet pile 1", "section": "az26",
        "points": [[12.0, 0.0], [12.0, -14.0]], "active": True}


@pytest.fixture(scope="module")
def session():
    with solid_model.session():
        yield


@pytest.fixture(scope="module")
def section(session):
    project = seed_project()
    project.dimension = 2
    project.section_offset = 20.0
    project.loads = [LineLoad(
        id="load_line", name="LineLoad_1", x0=1.0, x1=10.0,
        y=project.domain.y_top, thickness=0.25, components=(0.0, -20.0),
    )]
    return writer.export_project(project, MeshRequest(element_size=6.0, order=2))


@pytest.fixture(scope="module")
def solid(session):
    return writer.export_project(seed_project(), MeshRequest(element_size=6.0, order=2))


@pytest.fixture(scope="module")
def piled(session):
    payload = seed_project().model_dump()
    payload.update(dimension=2, section_offset=20.0,
                   beam_sections=[PILE_SECTION], beams=[PILE])
    project = Project.model_validate(payload)
    return writer.export_project(project, MeshRequest(element_size=6.0, order=1))


def stages(export: dict) -> list[dict]:
    doc = json.loads(export["project_parameters"])
    return [stage["stage_settings"] for stage in doc["stages"].values()]


# ── The analysis each stage carries ─────────────────────────────────────────

def test_every_stage_carries_a_runnable_solver_block(section):
    solver = stages(section)[0]["solver_settings"]

    assert solver["solver_type"] == "U_Pw"
    assert solver["model_part_name"] == "PorousDomain"
    assert solver["model_import_settings"]["input_type"] == "mdpa"
    assert solver["material_import_settings"]["materials_filename"] \
        == "MaterialParameters.json"
    assert solver["time_stepping"]["time_step"] > 0
    assert solver["linear_solver_settings"]["solver_type"]


def test_the_problem_data_names_the_deck_and_spans_one_step(section):
    problem_data = stages(section)[0]["problem_data"]

    assert problem_data["problem_name"]
    assert problem_data["end_time"] > problem_data["start_time"]
    assert problem_data["parallel_type"] == "OpenMP"


def test_the_stages_run_one_after_another_in_time(piled):
    """Two stages, and the second picks up where the first left off -- an installation
    that started at the same time as the stage before it would overwrite it."""
    initial, installation = [stage["problem_data"] for stage in stages(piled)]

    assert initial["end_time"] == installation["start_time"]
    assert installation["end_time"] > installation["start_time"]


def test_the_domain_size_follows_the_model_mode(section, solid):
    assert stages(section)[0]["solver_settings"]["domain_size"] == 2
    assert stages(solid)[0]["solver_settings"]["domain_size"] == 3


def test_the_mdpa_is_named_without_its_extension(section):
    """Kratos appends `.mdpa` itself; naming the file here would look for
    `<name>.mdpa.mdpa`."""
    solver = stages(section)[0]["solver_settings"]

    assert not solver["model_import_settings"]["input_filename"].endswith(".mdpa")
    assert solver["model_import_settings"]["input_filename"] == section["deck_name"]


def test_a_staged_deck_reads_the_mesh_before_its_first_operation(piled):
    """A stage's solver imports the mesh *after* `stage_preprocess`, so deactivating the
    pile there would name a sub-model part that does not exist yet -- Kratos stops on
    it. The modeler is what puts the mesh in the model in time, and every stage then
    works on that one model instead of re-reading the file over its own results."""
    doc = json.loads(piled["project_parameters"])
    initial, installation = doc["stages"].values()

    modeler = initial["stage_preprocess"]["modelers"][0]
    assert modeler["name"] == "Modelers.KratosMultiphysics.ImportMDPAModeler"
    assert modeler["Parameters"]["input_filename"] == piled["deck_name"]
    assert modeler["Parameters"]["model_part_name"] == "PorousDomain"
    assert "modelers" not in installation["stage_preprocess"]

    for stage in (initial, installation):
        assert stage["stage_settings"]["solver_settings"]["model_import_settings"] \
            == {"input_type": "use_input_model_part"}


# ── The sub-model part lists, which must name parts the .mdpa really has ────

def test_the_domain_lists_name_every_body_in_the_deck(section):
    from tests import mdpa

    deck = mdpa.parse(section["mdpa"])
    solver = stages(section)[0]["solver_settings"]

    assert solver["problem_domain_sub_model_part_list"]
    assert solver["problem_domain_sub_model_part_list"] \
        == solver["body_domain_sub_model_part_list"]
    for name in solver["problem_domain_sub_model_part_list"]:
        assert name in deck.parts, name
        assert deck.parts[name].elements, name


def test_the_process_list_names_every_part_a_process_acts_on(section):
    """`check_and_prepare_model_process_geo` looks each of these up by name, so a part
    named in a process and missing from this list is a load that never reaches the
    computational model part."""
    settings = stages(section)[0]
    processes = settings["processes"]
    named = {p["Parameters"]["model_part_name"].partition(".")[2]
             for p in processes["constraints_process_list"] + processes["loads_process_list"]
             if "model_part_name" in p["Parameters"]}
    # Two names a process may carry that are not sub-model parts of the .mdpa, so
    # listing them here would ask Kratos to look them up among its own children: the
    # computational model part, which it assembles out of the lists beside this one
    # (gravity and the ties address it), and the root `PorousDomain` itself, which the
    # pore-pressure field is stated over.
    named -= {parameters.COMPUTATIONAL_MODEL_PART, ""}

    listed = set(settings["solver_settings"]["processes_sub_model_part_list"])
    assert named <= listed


def test_a_deck_with_a_beam_switches_rotation_dofs_on(piled, section):
    """A Timoshenko beam has rotations; soil alone does not, and asking for dofs no
    element carries costs memory for nothing."""
    assert stages(piled)[0]["solver_settings"]["rotation_dofs"] is True
    assert stages(section)[0]["solver_settings"]["rotation_dofs"] is False


# ── Output ──────────────────────────────────────────────────────────────────

def test_each_stage_writes_its_own_gid_output(piled):
    names = [stage["output_processes"]["gid_output"][0]["Parameters"]["output_name"]
             for stage in stages(piled)]

    assert len(names) == len(set(names)), "stages would overwrite each other's results"
    assert all(name.startswith(piled["deck_name"]) for name in names)


def test_the_output_asks_for_displacement_and_water_pressure(section):
    output = stages(section)[0]["output_processes"]["gid_output"][0]["Parameters"]
    results = output["postprocess_parameters"]["result_file_configuration"]["nodal_results"]

    assert "TOTAL_DISPLACEMENT" in results
    assert "WATER_PRESSURE" in results


# ── What docs/FEATURES.md A1 promises about the solver, pinned─────────────────

def test_the_linear_solver_is_the_direct_skyline_one_on_one_thread(section):
    """A direct solver, a block builder and one OpenMP thread in every stage: the
    reference decks' settings, and the ones every validated run used."""
    for settings in stages(section):
        solver = settings["solver_settings"]
        assert solver["linear_solver_settings"]["solver_type"] == "skyline_lu_factorization"
        assert solver["block_builder"] is True
        assert settings["problem_data"]["number_of_threads"] == 1


def test_the_default_tolerances_and_step_controls(section):
    """Relative 1e-4, absolute 1e-9, 6 to 15 iterations, halving and doubling -- the
    defaults a stage can override (`Stage.max_iterations`, `tolerated_error`)."""
    solver = stages(section)[0]["solver_settings"]
    assert (solver["residual_relative_tolerance"], solver["residual_absolute_tolerance"]) == (1e-4, 1e-9)
    assert (solver["min_iterations"], solver["max_iterations"]) == (6, 15)
    assert (solver["reduction_factor"], solver["increase_factor"]) == (0.5, 2.0)


def test_each_stage_is_one_step_and_the_settling_stages_sit_before_zero():
    """dt = 1 per stage; the K0 stage and the null step run at negative time, as in the
    reference deck, so the construction starts at t = 0."""
    import json as _json
    from tests.models import excavation
    params = _json.loads(writer.export_project(excavation.excavation_project(staged=True))["project_parameters"])
    order = params["orchestrator"]["settings"]["execution_list"]
    times = [(params["stages"][n]["stage_settings"]["problem_data"]["start_time"],
              params["stages"][n]["stage_settings"]["problem_data"]["end_time"]) for n in order]
    assert times[:3] == [(-2.0, -1.0), (-1.0, 0.0), (0.0, 1.0)]
    assert all(end - start == 1.0 for start, end in times)
    assert all(params["stages"][n]["stage_settings"]["solver_settings"]["time_stepping"]
               ["time_step"] == 1.0 for n in order)
