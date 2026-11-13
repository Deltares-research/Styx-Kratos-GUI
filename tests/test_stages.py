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
    assert made[0].calculation == "K0 procedure"
    assert made[1].calculation == "Null step"
    assert all(ph.calculation == "Plastic" for ph in made[2:])


def test_the_test_models_stages_linearise():
    staged = _model()
    assert [ph.id for ph in stages.linearise(staged)] == \
        [ph.id for ph in staged.stages]


def test_an_anchor_is_installed_after_the_lift_that_exposes_it():
    """The reference installs the strut at -1.5 after the first lift reaches -2.0, not
    before: you cannot fix a strut to a wall face that is still buried."""
    order = [ph.id for ph in _model().stages]
    assert order.index("dig_1") < order.index("install_strut") < order.index("dig_2")


# -- default_stages ----------------------------------------------------------
# What "Create default stages" gives: Initial stage, then Null step, and nothing else.
# Every further stage is the user's to add.

def test_the_default_is_the_initial_stage_then_the_null_step():
    made = stages.default_stages(_model())
    assert [(ph.id, ph.name, ph.parent) for ph in made] == [
        ("initial", "Initial stage", None),
        ("null_step", "Null step", "initial"),
    ]
    assert made[0].calculation == "K0 procedure"
    assert made[1].calculation == "Null step"
    assert made[1].max_iterations == 150


def test_a_new_model_gets_no_excavation_stage():
    from core.model.templates import blank_project

    assert [ph.id for ph in stages.default_stages(blank_project())] ==         ["initial", "null_step"]


def test_the_default_switches_nothing_off():
    """With no stage after them to switch anything back on, every part has to be active
    from the start: a part that is off in every stage is missing from the deck."""
    for ph in stages.default_stages(_model()):
        assert not ph.activate and not ph.deactivate, ph.id


def test_the_default_makes_a_project_that_validates_and_linearises():
    staged = schemas.Project.model_validate(
        _model().model_dump()
        | {"stages": [ph.model_dump() for ph in stages.default_stages(_model())]})
    assert [ph.id for ph in stages.linearise(staged)] == ["initial", "null_step"]


def test_an_unexcavated_project_still_gets_a_sequence():
    """Opening staged mode on a project with nothing dug must not produce an empty or
    invalid list -- the stage editor has to have something to show."""
    p = seed_project(simple=False)
    made = stages.default_stages(p)
    assert [ph.id for ph in made] == ["initial", "null_step"]
    schemas.Project.model_validate(
        p.model_dump() | {"stages": [ph.model_dump() for ph in made]})


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
    assert phases.default_phases is stages.default_stages


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
    """Issue #135: after the two default stages, Add made `Stage 3` with the id
    `stage_1`. The name and the id now carry the same number."""
    project = blank_project().model_copy(update={"stages": stages.default_stages(
        blank_project())})

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
