"""The construction sequence: resolving a stage tree into what Kratos runs.

`core.model.stages` is pure model logic -- no gmsh, no Kratos -- so this file builds projects
and reads sets of part keys back, and never meshes anything. What it is checked against
is Kratos' own staged-construction reference deck: its seven stages, their
`stage_preprocess` operations, and their `problem_domain_sub_model_part_list`s. See
plan/outdated/staged-construction-plan.md sec 4.
"""

import pytest
from pydantic import ValidationError

from core.model import stages, schemas
from core.model.templates import blank_project, seed_project
from tests.models.excavation import excavation_project


def _project(*stage_records) -> schemas.Project:
    """A staged project -- layers crossed with three lifts -- and a stage list."""
    p = seed_project().model_dump()
    p["domain"] |= {"y_top": 0.0, "y_bottom": -60.0}
    p["layers"] = [
        {"id": "L1", "name": "Soil_1", "mat": p["materials"][0]["id"],
         "top": 0.0, "bottom": -8.0},
        {"id": "L2", "name": "Soil_2", "mat": p["materials"][1]["id"],
         "top": -8.0, "bottom": -60.0},
    ]
    p["excavation"] = {"x0": 0.0, "x1": 5.0, "z0": p["domain"]["z0"],
                         "z1": p["domain"]["z1"], "levels": [-2.0, -5.0, -8.0]}
    # Two parts for a stage to switch that are not soil.
    p["beam_sections"] = [schemas.BeamSection(id="s", name="S", variables={}).model_dump()]
    p["beams"] = [{"id": "pile", "name": "Pile", "section": "s",
                   "points": [(5.0, 0.0), (5.0, -13.0)]}]
    p["anchor_sections"] = [schemas.AnchorSection(id="t", name="T", variables={}).model_dump()]
    p["anchors"] = [{"id": "tie", "name": "Tie", "section": "t",
                     "head": (5.0, -1.0), "tail": (3.0, -1.0)}]
    p["stages"] = list(stage_records)
    return schemas.Project.model_validate(p)


def _stage(id_, parent=None, **kw) -> dict:
    return {"id": id_, "name": id_.replace("_", " ").title(), "parent": parent, **kw}


# -- linearise ---------------------------------------------------------------

def test_an_unstaged_project_runs_no_stages():
    """The compatibility contract: no stages means the single-stage export as it was."""
    assert stages.linearise(seed_project(simple=False)) == []


def test_a_chain_runs_root_first():
    p = _project(_stage("initial"),
                 _stage("dig_1", parent="initial"),
                 _stage("dig_2", parent="dig_1"))
    assert [ph.id for ph in stages.linearise(p)] == ["initial", "dig_1", "dig_2"]


def test_a_chain_runs_in_tree_order_not_list_order():
    """The list is storage; the parent links are the sequence. A stage inserted in the
    middle of the tree is appended to the list, and must still run in the middle."""
    p = _project(_stage("initial"),
                 _stage("dig_2", parent="install"),
                 _stage("install", parent="initial"))
    assert [ph.id for ph in stages.linearise(p)] == ["initial", "install", "dig_2"]


def test_a_branch_cannot_be_linearised():
    """Two stages can start from the same parent in the editor. Kratos has
    one `execution_list`, so export has to refuse it -- and say which stages branch,
    because "cannot linearise" on its own tells the user nothing."""
    p = _project(_stage("initial"),
                 _stage("dig_wet", parent="initial"),
                 _stage("dig_dry", parent="initial"))
    with pytest.raises(stages.StageError) as caught:
        stages.linearise(p)
    message = str(caught.value)
    assert "dig_wet" in message and "dig_dry" in message and "initial" in message


# -- active_parts ------------------------------------------------------------

def test_the_model_starts_with_everything_in_it():
    """The mesh carries every part; the first stage's job is to switch off what has not
    been built yet. That is exactly what the reference's stage 1 does -- it deactivates
    the wall, the anchor and all eight interfaces."""
    p = _project(_stage("initial", deactivate=["pile", "tie"]))
    assert stages.active_parts(p, "initial") == (
        set(p.stageable_keys()) - {"pile", "tie"})


def test_active_parts_walks_the_whole_chain():
    p = _project(_stage("initial", deactivate=["pile", "tie"]),
                 _stage("build", parent="initial", activate=["pile"]),
                 _stage("dig_1", parent="build", deactivate=["soil_L1__lift1"]),
                 _stage("anchor", parent="dig_1", activate=["tie"]))
    at = stages.active_parts(p, "anchor")
    assert "pile" in at and "tie" in at
    assert "soil_L1__lift1" not in at
    assert "soil_L1__lift2" in at


def test_active_parts_takes_a_stage_or_its_id():
    p = _project(_stage("initial", deactivate=["pile"]))
    assert stages.active_parts(p, p.stages[0]) == stages.active_parts(p, "initial")


def test_active_parts_resolves_a_branch_export_would_refuse():
    """Resolution follows parents, so it works on any tree. It has to: the editor shows
    a half-built branch, and refusing to say what is in it would make the branch
    invisible until the user deleted it."""
    p = _project(_stage("initial", deactivate=["pile"]),
                 _stage("dig_wet", parent="initial", deactivate=["soil_L1__lift1"]),
                 _stage("dig_dry", parent="initial", deactivate=["soil_L1__lift2"]))
    assert "soil_L1__lift1" not in stages.active_parts(p, "dig_wet")
    assert "soil_L1__lift1" in stages.active_parts(p, "dig_dry")


def test_a_stage_that_names_nothing_inherits_its_parent_exactly():
    """The reference's null step: same model, solved again. Its domain list is its
    predecessor's, character for character."""
    p = _project(_stage("initial", deactivate=["pile"]),
                 _stage("null_step", parent="initial"))
    assert stages.active_parts(p, "null_step") == stages.active_parts(p, "initial")


# -- transitions -------------------------------------------------------------

def test_transitions_are_the_stage_preprocess():
    p = _project(_stage("initial", deactivate=["pile", "tie"]),
                 _stage("build", parent="initial", activate=["pile"]),
                 _stage("dig_1", parent="build", deactivate=["soil_L1__lift1"]))
    got = [(ph.id, on, off) for ph, on, off in stages.transitions(p)]
    assert got == [
        ("initial", set(), {"pile", "tie"}),
        ("build", {"pile"}, set()),
        ("dig_1", set(), {"soil_L1__lift1"}),
    ]


def test_a_transition_reports_only_what_actually_changes():
    """A stage may repeat an instruction its parent already gave -- deleting a lift and
    re-adding it leaves that behind. Writing the no-op into the deck would make Kratos
    deactivate an already inactive part, which it tolerates, and make the deck
    unreadable, which nobody does. The diff is filtered against the state it lands on."""
    p = _project(_stage("initial", deactivate=["pile"]),
                 _stage("again", parent="initial", deactivate=["pile"]),
                 _stage("on", parent="again", activate=["pile"]),
                 _stage("on_again", parent="on", activate=["pile"]))
    assert [(on, off) for _, on, off in stages.transitions(p)] == [
        (set(), {"pile"}), (set(), set()), ({"pile"}, set()), (set(), set()),
    ]


# -- The test model's sequence ----------------------------------------------------------
# The reference deck's seven stages:
#
#   1 Initial stage     K0     deactivate the wall, the anchor and every interface
#   2 Null step         --     nothing
#   3 Wall installation        activate the wall and its interfaces
#   4 First excavation         deactivate lift 1 (and its interface)
#   5 Anchor installation      activate the anchor
#   6 Second excavation        deactivate lift 2
#   7 Third excavation         deactivate lift 3
#
# The eight interface parts are one key below: one drawn `Interface` becomes eight deck
# parts at export (`core/kratos/writer.py:_interface_by_body`), which is export's business.

def _model():
    from tests.models import excavation
    return excavation.excavation_project()


def test_the_test_models_stages_follow_the_reference_sequence():
    got = [(ph.id, sorted(on), sorted(off))
           for ph, on, off in stages.transitions(_model())]
    assert got == [
        ("initial", [], ["sheetpile", "strut", "surcharge", "wall_contact",
                         "water_1", "water_2", "water_3"]),
        ("null_step", [], []),
        ("install_sheetpile", ["sheetpile", "surcharge", "wall_contact"], []),
        ("dig_1", ["water_1"], ["soil_L_top__lift1"]),
        ("install_strut", ["strut"], []),
        ("dig_2", ["water_2"], ["soil_L_top__lift2", "water_1"]),
        ("dig_3", ["water_3"], ["soil_L_top__lift3", "water_2"]),
    ]


def test_the_ground_under_the_pit_stays_when_the_lifts_come_out():
    """`Soil_Below_Pit` is on the dug side of the wall but is never dug, and stays
    active in all seven reference stages. Only the lifts come out."""
    last = stages.active_parts(_model(), "dig_3")
    assert "soil_L_mid__pit" in last
    assert not {"soil_L_top__lift1", "soil_L_top__lift2", "soil_L_top__lift3"} & last


def test_the_displacements_are_reset_when_the_wall_goes_in():
    """The reference sets `reset_totals` true in exactly one stage, the wall's, so the
    wall's deflection is measured from the ground it was built into."""
    made = _model().stages
    assert [ph.id for ph in made if ph.reset_displacements] == ["install_sheetpile"]


def test_the_first_staged_stage_is_the_only_k0_one():
    made = _model().stages
    assert all(ph.calculation == "mechanical" for ph in made)
    assert [ph.stress_initialisation for ph in made] == ["K0"] + ["none"] * (len(made) - 1)


def test_the_test_models_stages_linearise():
    staged = _model()
    assert [ph.id for ph in stages.linearise(staged)] == \
        [ph.id for ph in staged.stages]


def test_an_anchor_is_installed_after_the_lift_that_exposes_it():
    """The reference installs the strut at -1.5 after the first lift reaches -2.0, not
    before: you cannot fix a strut to a wall face that is still buried."""
    order = [ph.id for ph in _model().stages]
    assert order.index("dig_1") < order.index("install_strut") < order.index("dig_2")


# -- the three choices of a stage ------------------------------------------------
# A calculation type, mechanical or flow; a stress initialisation, of a mechanical
# stage only; and a time integration. There are no default stages: every stage is the
# user's to add.

def test_a_stage_is_a_static_mechanical_stage_with_no_stress_initialisation():
    made = schemas.Stage(id="s", name="S")
    assert (made.calculation, made.stress_initialisation, made.time_integration) == \
        ("mechanical", "none", "static")


@pytest.mark.parametrize("calculation", ["mechanical", "flow"])
@pytest.mark.parametrize("time_integration", ["static", "dynamic"])
def test_either_calculation_type_solves_statically_or_in_time(calculation,
                                                              time_integration):
    made = schemas.Stage(id="s", name="S", calculation=calculation,
                         time_integration=time_integration)
    assert made.time_integration == time_integration


@pytest.mark.parametrize("stresses", ["K0", "gravity", "none"])
def test_a_mechanical_stage_initialises_its_stresses_three_ways(stresses):
    assert schemas.Stage(id="s", name="S",
                         stress_initialisation=stresses).stress_initialisation == stresses


@pytest.mark.parametrize("stresses", ["K0", "gravity"])
def test_a_flow_stage_has_no_stresses_to_initialise(stresses):
    with pytest.raises(ValueError, match="no stresses to initialise"):
        schemas.Stage(id="s", name="S", calculation="flow", stress_initialisation=stresses)


@pytest.mark.parametrize("field,value", [
    ("calculation", "Plastic2"), ("stress_initialisation", "k0"),
    ("time_integration", "quasi_static")])
def test_a_choice_that_is_not_one_is_refused(field, value):
    with pytest.raises(ValueError):
        schemas.Stage(id="s", name="S", **{field: value})


@pytest.mark.parametrize("old,new", [
    ("K0 procedure", ("mechanical", "K0")),
    ("Plastic", ("mechanical", "none")),
    ("Null step", ("mechanical", "none")),
    ("Groundwater flow", ("flow", "none")),
])
def test_a_stage_saved_with_an_old_calculation_opens_in_the_new_shape(old, new):
    made = schemas.Stage.model_validate({"id": "s", "name": "S", "parent": "before",
                                         "calculation": old})
    assert (made.calculation, made.stress_initialisation) == new
    assert made.time_integration == "static"


@pytest.mark.parametrize("old,new", [
    ("K0 procedure", ("mechanical", "K0")),
    ("Plastic", ("mechanical", "gravity")),
    ("Null step", ("mechanical", "gravity")),
    ("Groundwater flow", ("flow", "none")),
])
def test_an_old_initial_stage_keeps_the_self_weight_it_had(old, new):
    """An initial plastic stage, or null step, had the self weight, as gravity was on
    unless the project switched it off; now its stress initialisation decides it
    (`stages.gravity`), so it opens initialised by gravity loading."""
    made = schemas.Stage.model_validate({"id": "s", "name": "S", "calculation": old})
    assert (made.calculation, made.stress_initialisation) == new


@pytest.mark.parametrize("calculation,default,tolerance", [
    ("mechanical", "residual_criterion", 1e-9),
    ("flow", "water_pressure_criterion", 1e-8)])
def test_a_stage_converges_on_its_calculation_type_s_default_criterion(calculation,
                                                                      default, tolerance):
    """The residual criterion for a mechanical stage, the water pressure one for a flow
    stage, each with its own absolute tolerance."""
    made = schemas.Stage(id="s", name="S", calculation=calculation)
    assert (made.convergence_criterion, made.tolerated_error, made.absolute_tolerance) == \
        (default, 1e-4, tolerance)
    # A stage that names none opens with the default too.
    saved = schemas.Stage.model_validate({"id": "s", "name": "S",
                                          "calculation": calculation})
    assert saved.convergence_criterion == default


def test_an_old_flow_stage_keeps_the_residual_criterion_it_was_solved_on():
    saved = schemas.Stage.model_validate({"id": "s", "name": "S",
                                          "calculation": "Groundwater flow"})
    assert (saved.calculation, saved.convergence_criterion, saved.absolute_tolerance) == \
        ("flow", "residual_criterion", 1e-9)


@pytest.mark.parametrize("calculation,criterion", [
    ("mechanical", "residual_criterion"), ("mechanical", "displacement_criterion"),
    ("flow", "water_pressure_criterion"), ("flow", "residual_criterion")])
def test_each_calculation_type_has_its_own_convergence_criteria(calculation, criterion):
    made = schemas.Stage(id="s", name="S", calculation=calculation,
                         convergence_criterion=criterion)
    assert made.convergence_criterion == criterion


@pytest.mark.parametrize("calculation,criterion", [
    ("mechanical", "water_pressure_criterion"), ("flow", "displacement_criterion")])
def test_a_criterion_of_the_other_calculation_type_is_refused(calculation, criterion):
    with pytest.raises(ValueError, match="is not solved on the"):
        schemas.Stage(id="s", name="S", calculation=calculation,
                      convergence_criterion=criterion)


def test_the_combined_criterion_kratos_cannot_build_is_no_choice():
    with pytest.raises(ValueError):
        schemas.Stage(id="s", name="S",
                      convergence_criterion="displacement_and_water_pressure_criterion")


def test_there_is_no_default_sequence():
    assert not hasattr(stages, "default_stages")


def test_a_copy_keeps_the_calculation_and_the_time_integration_not_the_stresses():
    """A copy comes after the original, and only the initial stage initialises the
    stresses."""
    p = _project(schemas.Stage(id="initial", name="Initial", stress_initialisation="K0",
                               time_integration="dynamic"))
    made = stages.copied(p, "initial")[1]
    assert (made.calculation, made.stress_initialisation, made.time_integration) == \
        ("mechanical", "none", "dynamic")


def test_a_copy_keeps_the_convergence_criterion_and_its_tolerances():
    p = _project(schemas.Stage(id="initial", name="Initial",
                               convergence_criterion="residual_criterion",
                               tolerated_error=1e-3, absolute_tolerance=1e-6))
    made = stages.copied(p, "initial")[1]
    assert (made.convergence_criterion, made.tolerated_error, made.absolute_tolerance) == \
        ("residual_criterion", 1e-3, 1e-6)


# -- the initial stage ---------------------------------------------------------
# It chooses the calculation type and the stress initialisation of the whole sequence,
# and a new project starts with it.

def test_a_new_project_starts_with_the_initial_stage():
    from core.model.templates import blank_project
    made = blank_project().stages
    assert [(s.id, s.name, s.parent, s.calculation, s.stress_initialisation)
            for s in made] == [("initial", "Initial stage", None, "mechanical", "gravity")]


def test_a_project_with_no_stages_gets_the_initial_stage_first():
    p = _project()
    assert stages.added(p) == [stages.initial_stage()]


def test_the_initial_stage_is_neither_deleted_nor_preceded():
    p = _project(_stage("initial"), _stage("dig", parent="initial"))
    assert stages.removed(p, "initial") == p.stages
    assert stages.inserted(p, "initial") == p.stages


def test_a_later_stage_has_the_initial_stage_s_calculation_type():
    p = _project(_stage("initial", calculation="flow"))
    assert stages.added(p)[-1].calculation == "flow"
    p = _project(_stage("initial", calculation="flow"), _stage("b", parent="initial",
                                                                calculation="flow"))
    assert stages.inserted(p, "b")[1].calculation == "flow"


def test_the_calculation_type_is_set_in_the_initial_stage_for_every_stage():
    p = _project(_stage("initial", stress_initialisation="K0"),
                 _stage("dig", parent="initial"))
    flow = stages.edited(p, "initial", "calculation", "flow")
    assert [(s.calculation, s.stress_initialisation) for s in flow] == \
        [("flow", "none"), ("flow", "none")]
    assert stages.edited(p, "dig", "calculation", "flow") == p.stages
    assert stages.edited(p, "dig", "stress_initialisation", "K0") == p.stages
    assert stages.edited(p, "dig", "time_integration", "dynamic")[1].time_integration == \
        "dynamic"


def test_trying_flow_and_going_back_to_mechanical_keeps_the_self_weight():
    """The initial stage of a new project is initialised by gravity loading; a flow
    sequence has none, so going back to mechanical gives it gravity loading again
    rather than leaving the self weight out of every stage."""
    p = blank_project()
    assert stages.gravity(p)
    flow = p.model_copy(update={"stages": stages.edited(p, "initial", "calculation",
                                                        "flow")})
    back = flow.model_copy(update={"stages": stages.edited(flow, "initial", "calculation",
                                                           "mechanical")})
    assert back.stages[0].stress_initialisation == "gravity"
    assert stages.gravity(back)
    # Its own choice, made before trying flow, is gone with flow; none stays none when
    # the type does not change.
    off = _project(_stage("initial", stress_initialisation="none"),
                   _stage("dig", parent="initial"))
    assert [s.stress_initialisation
            for s in stages.edited(off, "initial", "calculation", "mechanical")] == \
        ["none", "none"]
    two = _project(_stage("initial", calculation="flow"),
                   _stage("dig", parent="initial", calculation="flow"))
    assert [s.stress_initialisation
            for s in stages.edited(two, "initial", "calculation", "mechanical")] == \
        ["gravity", "none"]


def test_a_later_stage_with_a_stress_initialisation_can_go_back_to_none():
    """An old project's later K0 procedure opens as a later stage initialised by K0,
    which `check_settings` refuses every edit with: setting it to none has to work."""
    p = _project(_stage("initial", stress_initialisation="K0"),
                 _stage("dig", parent="initial", stress_initialisation="K0"))
    with pytest.raises(stages.StageError, match="only the initial stage"):
        stages.check_settings(p)
    fixed = p.model_copy(update={"stages": stages.edited(p, "dig", "stress_initialisation",
                                                         "none")})
    assert fixed.stages[1].stress_initialisation == "none"
    stages.check_settings(fixed)
    assert stages.edited(fixed, "dig", "stress_initialisation", "gravity") == fixed.stages


def test_a_new_calculation_type_gives_every_stage_a_criterion_it_has():
    """Every stage gets the new type's default -- the water pressure one for flow, the
    residual one for mechanical: a flow stage made from a mechanical one converges as a
    new flow stage does. The same type again changes nothing."""
    p = _project(_stage("initial", convergence_criterion="displacement_criterion"),
                 _stage("dig", parent="initial"))
    flow = stages.edited(p, "initial", "calculation", "flow")
    assert [s.convergence_criterion for s in flow] == ["water_pressure_criterion"] * 2
    back = stages.edited(_project(*flow), "initial", "calculation", "mechanical")
    assert [s.convergence_criterion for s in back] == ["residual_criterion"] * 2
    same = stages.edited(p, "initial", "calculation", "mechanical")
    assert [s.convergence_criterion for s in same] == \
        ["displacement_criterion", "residual_criterion"]


def test_a_stage_on_the_displacement_criterion_defaults_to_an_absolute_tolerance_of_1e_12():
    def made(**kw):
        return schemas.Stage.model_validate(_stage("a", **kw)).absolute_tolerance
    assert made(convergence_criterion="displacement_criterion") == 1e-12
    assert made() == 1e-9
    assert made(convergence_criterion="displacement_criterion",
                absolute_tolerance=1e-6) == 1e-6


def test_a_new_criterion_takes_its_default_absolute_tolerance_unless_the_stage_has_its_own():
    p = _project(_stage("initial"), _stage("dig", parent="initial", absolute_tolerance=1e-6))
    on = stages.edited(p, "initial", "convergence_criterion", "displacement_criterion")
    assert (on[0].convergence_criterion, on[0].absolute_tolerance) == \
        ("displacement_criterion", 1e-12)
    off = stages.edited(_project(*on), "initial", "convergence_criterion",
                        "residual_criterion")
    assert off[0].absolute_tolerance == 1e-9
    own = stages.edited(p, "dig", "convergence_criterion", "displacement_criterion")
    assert own[1].absolute_tolerance == 1e-6
    flow = stages.edited(_project(*on), "initial", "calculation", "flow")
    assert flow[0].absolute_tolerance == 1e-8
    residual = stages.edited(_project(*flow), "initial", "convergence_criterion",
                             "residual_criterion")
    assert residual[0].absolute_tolerance == 1e-9


def test_a_sequence_that_chooses_them_elsewhere_is_refused():
    with pytest.raises(stages.StageError, match="not mechanical, as the initial stage"):
        stages.check_settings(_project(_stage("initial"),
                                       _stage("b", parent="initial", calculation="flow")))
    with pytest.raises(stages.StageError, match="only the initial stage"):
        stages.check_settings(_project(_stage("initial"),
                                       _stage("b", parent="initial",
                                              stress_initialisation="gravity")))
    stages.check_settings(_project(_stage("initial", stress_initialisation="K0"),
                                   _stage("b", parent="initial")))


@pytest.mark.parametrize("stresses,on", [("K0", True), ("gravity", True), ("none", False)])
def test_the_initial_stage_s_stress_initialisation_decides_gravity(stresses, on):
    p = _project(_stage("initial", stress_initialisation=stresses),
                 _stage("dig", parent="initial"))
    assert stages.gravity(p) is on


def test_a_flow_sequence_and_an_unstaged_project_keep_their_gravity():
    assert stages.gravity(_project(_stage("initial", calculation="flow"))) is True
    assert stages.gravity(_project()) is True


# -- structure refusals and long chains (alpha 1.7) -------------------------

@pytest.mark.parametrize("records,message", [
    ([_stage("initial"), _stage("dig", parent="nowhere")], "starts from nowhere"),
    ([_stage("initial"), _stage("dig", parent="dig")], "starts from itself"),
    ([_stage("initial"), _stage("other")], "exactly one root"),
    ([_stage("initial"), _stage("a", parent="b"), _stage("b", parent="a")], "cycle"),
])
def test_a_stage_tree_that_is_not_a_tree_is_refused_by_name(records, message):
    with pytest.raises(ValidationError, match=message):
        _project(*records)


def test_a_part_switched_both_ways_in_one_stage_is_refused():
    with pytest.raises(ValidationError, match="soil_L1__lift1"):
        _project(_stage("initial"),
                 _stage("dig", parent="initial", activate=["soil_L1__lift1"],
                        deactivate=["soil_L1__lift1"]))


def test_a_fifty_stage_chain_runs_in_tree_order_however_it_is_listed():
    records = [_stage("initial")] + [_stage(f"p{n}", parent="initial" if n == 1 else f"p{n-1}")
                                     for n in range(1, 50)]
    project = _project(*reversed(records))

    order = [stage.id for stage in stages.linearise(project)]

    assert order == ["initial"] + [f"p{n}" for n in range(1, 50)]


def test_deactivating_a_part_already_gone_is_dropped_as_a_no_op():
    project = _project(
        _stage("initial"),
        _stage("dig1", parent="initial", deactivate=["soil_L1__lift1"]),
        _stage("dig2", parent="dig1", deactivate=["soil_L1__lift1", "soil_L1__lift2"]))

    by_id = {stage.id: (on, off) for stage, on, off in stages.transitions(project)}

    assert by_id["dig2"] == (set(), {"soil_L1__lift2"})


def test_reactivating_a_part_brings_it_back_from_that_stage_on():
    project = _project(
        _stage("initial"),
        _stage("dig", parent="initial", deactivate=["soil_L1__lift1"]),
        _stage("fill", parent="dig", activate=["soil_L1__lift1"]))

    assert "soil_L1__lift1" not in stages.active_parts(project, "dig")
    assert "soil_L1__lift1" in stages.active_parts(project, "fill")


# ── Editing: the Stages toolbar's list transforms (`App.Stages`) ─────────────

def _test_model() -> schemas.Project:
    """tests/models/excavation.py, staged: seven stages to edit."""
    return excavation_project()


def _ids(listed):
    return [(stage.id, stage.parent) for stage in listed]


def test_add_puts_a_blank_stage_at_the_end_of_the_sequence():
    project = _test_model()

    listed = stages.added(project)

    new = listed[-1]
    assert (new.id, new.name, new.parent) == ("stage_8", "Stage 8", "dig_3")
    assert new == schemas.Stage(id="stage_8", name="Stage 8", parent="dig_3")


def test_insert_puts_a_stage_between_a_stage_and_its_parent():
    listed = stages.inserted(_test_model(), "dig_1")

    assert _ids(listed)[3:5] == [("stage_8", "install_sheetpile"), ("dig_1", "stage_8")]
    assert listed[3].name == "New stage"


def test_remove_heals_the_chain():
    listed = stages.removed(_test_model(), "install_strut")

    assert ("dig_2", "dig_1") in _ids(listed)
    assert "install_strut" not in [stage.id for stage in listed]


def test_copy_repeats_the_solver_settings_but_not_the_parts():
    listed = stages.copied(_test_model(), "install_sheetpile")

    made = listed[3]
    assert (made.id, made.name, made.parent) == ("stage_8",
                                                 "SheetPileWall installation (copy)",
                                                 "install_sheetpile")
    assert (made.reset_displacements, made.max_iterations, made.tolerated_error) == (
        True, 150, 1e-3)
    assert made.activate == [] and made.deactivate == []
    assert ("dig_1", "stage_8") in _ids(listed)


def test_set_active_gives_the_smallest_instruction():
    """Switching a part to what its parent already gives drops the instruction rather
    than stacking a second one."""
    project = _test_model()

    off = stages.set_active(project, "dig_1", ["strut"], True)
    assert next(p for p in off if p.id == "dig_1").activate == ["water_1", "strut"]

    back = stages.set_active(project, "install_sheetpile", ["sheetpile"], False)
    assert next(p for p in back if p.id == "install_sheetpile").activate == [
        "wall_contact", "surcharge"]


def test_an_edit_of_a_stage_that_is_not_there_changes_nothing():
    project = _test_model()

    for edit in (stages.inserted, stages.removed, stages.copied):
        assert edit(project, "nope") == project.stages


def test_the_phases_module_still_imports():
    from core.model import phases, stages
    assert phases.PhaseError is stages.StageError
    assert phases.linearise is stages.linearise


def test_adding_a_stage_to_an_unresolved_branch_uses_the_last_stored_stage():
    project = blank_project().model_copy(update={"stages": [
        schemas.Stage(id="initial", name="Initial"),
        schemas.Stage(id="wet", name="Wet", parent="initial"),
        schemas.Stage(id="dry", name="Dry", parent="initial"),
    ]})

    added = stages.added(project)

    assert added[-1].parent == "dry"
    assert [stage.id for stage in project.stages] == ["initial", "wet", "dry"]
    assert all(new is not old for new, old in zip(added, project.stages))


def test_adding_a_stage_skips_a_taken_number_without_duplicating_an_id():
    project = blank_project().model_copy(update={"stages": [
        schemas.Stage(id="stage_1", name="Initial"),
        schemas.Stage(id="stage_3", name="Dig", parent="stage_1"),
    ]})

    added = stages.added(project)

    assert (added[-1].id, added[-1].name) == ("stage_4", "Stage 4")
    assert added[-1].parent == "stage_3"
    assert len({stage.id for stage in added}) == len(added)


def test_a_new_stage_has_the_same_number_in_its_name_and_its_id():
    """Issue #135: after two stages, Add made `Stage 3` with the id `stage_1`. The name
    and the id now carry the same number."""
    project = blank_project().model_copy(update={"stages": [
        schemas.Stage(id="initial", name="Initial stage"),
        schemas.Stage(id="null_step", name="Null step", parent="initial"),
    ]})

    added = stages.added(project)

    assert (added[-1].id, added[-1].name) == ("stage_3", "Stage 3")


def test_a_new_stage_skips_a_number_whose_name_is_taken():
    project = blank_project().model_copy(update={"stages": [
        schemas.Stage(id="initial", name="Initial"),
        schemas.Stage(id="dig", name="Stage 4", parent="initial"),
        schemas.Stage(id="more", name="More", parent="dig"),
    ]})

    added = stages.added(project)

    assert (added[-1].id, added[-1].name) == ("stage_5", "Stage 5")
