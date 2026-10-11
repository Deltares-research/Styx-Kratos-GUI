"""The construction sequence: resolving a phase tree into what Kratos runs.

`core.phases` is pure model logic -- no gmsh, no Kratos -- so this file builds projects
and reads sets of part keys back, and never meshes anything. What it is checked against
is Kratos' own staged-construction reference deck: its seven stages, their
`stage_preprocess` operations, and their `problem_domain_sub_model_part_list`s. See
plan/outdated/staged-construction-plan.md sec 4.
"""

import pytest
from pydantic import ValidationError

from core import phases, schemas
from core.seed import seed_project


def _project(*phase_records) -> schemas.Project:
    """A staged project -- layers crossed with three lifts -- and a phase list."""
    p = seed_project(simple=False).model_dump()
    p["domain"] |= {"y_top": 0.0, "y_bottom": -60.0}
    p["boreholes"] = [p["boreholes"][0]]
    bh = p["boreholes"][0]["id"]
    p["layers"] = [
        {"id": "L1", "name": "Soil_1", "mat": p["materials"][0]["id"],
         "tops": {bh: 0.0}, "bots": {bh: -8.0}},
        {"id": "L2", "name": "Soil_2", "mat": p["materials"][1]["id"],
         "tops": {bh: -8.0}, "bots": {bh: -60.0}},
    ]
    p["excavation"] = {k: v for k, v in p["excavation"].items() if k != "floor_y"}
    p["excavation"] |= {"x0": 0.0, "x1": 5.0, "levels": [-2.0, -5.0, -8.0]}
    p["wall"] |= {"top_y": 0.0, "toe_y": -13.0}
    p["phases"] = list(phase_records)
    return schemas.Project.model_validate(p)


def _phase(id_, parent=None, **kw) -> dict:
    return {"id": id_, "name": id_.replace("_", " ").title(), "parent": parent, **kw}


# -- linearise ---------------------------------------------------------------

def test_an_unphased_project_runs_no_stages():
    """The compatibility contract: no phases means the single-stage export as it was."""
    assert phases.linearise(seed_project(simple=False)) == []


def test_a_chain_runs_root_first():
    p = _project(_phase("initial"),
                 _phase("dig_1", parent="initial"),
                 _phase("dig_2", parent="dig_1"))
    assert [ph.id for ph in phases.linearise(p)] == ["initial", "dig_1", "dig_2"]


def test_a_chain_runs_in_tree_order_not_list_order():
    """The list is storage; the parent links are the sequence. A phase inserted in the
    middle of the tree is appended to the list, and must still run in the middle."""
    p = _project(_phase("initial"),
                 _phase("dig_2", parent="install"),
                 _phase("install", parent="initial"))
    assert [ph.id for ph in phases.linearise(p)] == ["initial", "install", "dig_2"]


def test_a_branch_cannot_be_linearised():
    """Plaxis lets two phases start from the same parent and compares them. Kratos has
    one `execution_list`, so export has to refuse it -- and say which phases branch,
    because "cannot linearise" on its own tells the user nothing."""
    p = _project(_phase("initial"),
                 _phase("dig_wet", parent="initial"),
                 _phase("dig_dry", parent="initial"))
    with pytest.raises(phases.PhaseError) as caught:
        phases.linearise(p)
    message = str(caught.value)
    assert "dig_wet" in message and "dig_dry" in message and "initial" in message


# -- active_parts ------------------------------------------------------------

def test_the_model_starts_with_everything_in_it():
    """The mesh carries every part; the first phase's job is to switch off what has not
    been built yet. That is exactly what the reference's stage 1 does -- it deactivates
    the wall, the anchor and all eight interfaces."""
    p = _project(_phase("initial", deactivate=["wall", "anchors"]))
    assert phases.active_parts(p, "initial") == (
        set(p.stageable_keys()) - {"wall", "anchors"})


def test_active_parts_walks_the_whole_chain():
    p = _project(_phase("initial", deactivate=["wall", "anchors"]),
                 _phase("build", parent="initial", activate=["wall"]),
                 _phase("dig_1", parent="build", deactivate=["soil_L1__lift1"]),
                 _phase("anchor", parent="dig_1", activate=["anchors"]))
    at = phases.active_parts(p, "anchor")
    assert "wall" in at and "anchors" in at
    assert "soil_L1__lift1" not in at
    assert "soil_L1__lift2" in at


def test_active_parts_takes_a_phase_or_its_id():
    p = _project(_phase("initial", deactivate=["wall"]))
    assert phases.active_parts(p, p.phases[0]) == phases.active_parts(p, "initial")


def test_active_parts_resolves_a_branch_export_would_refuse():
    """Resolution follows parents, so it works on any tree. It has to: the editor shows
    a half-built branch, and refusing to say what is in it would make the branch
    invisible until the user deleted it."""
    p = _project(_phase("initial", deactivate=["wall"]),
                 _phase("dig_wet", parent="initial", deactivate=["soil_L1__lift1"]),
                 _phase("dig_dry", parent="initial", deactivate=["soil_L1__lift2"]))
    assert "soil_L1__lift1" not in phases.active_parts(p, "dig_wet")
    assert "soil_L1__lift1" in phases.active_parts(p, "dig_dry")


def test_a_phase_that_names_nothing_inherits_its_parent_exactly():
    """The reference's null step: same model, solved again. Its domain list is its
    predecessor's, character for character."""
    p = _project(_phase("initial", deactivate=["wall"]),
                 _phase("null_step", parent="initial"))
    assert phases.active_parts(p, "null_step") == phases.active_parts(p, "initial")


# -- transitions -------------------------------------------------------------

def test_transitions_are_the_stage_preprocess():
    p = _project(_phase("initial", deactivate=["wall", "anchors"]),
                 _phase("build", parent="initial", activate=["wall"]),
                 _phase("dig_1", parent="build", deactivate=["soil_L1__lift1"]))
    got = [(ph.id, on, off) for ph, on, off in phases.transitions(p)]
    assert got == [
        ("initial", set(), {"wall", "anchors"}),
        ("build", {"wall"}, set()),
        ("dig_1", set(), {"soil_L1__lift1"}),
    ]


def test_a_transition_reports_only_what_actually_changes():
    """A phase may repeat an instruction its parent already gave -- deleting a lift and
    re-adding it leaves that behind. Writing the no-op into the deck would make Kratos
    deactivate an already inactive part, which it tolerates, and make the deck
    unreadable, which nobody does. The diff is filtered against the state it lands on."""
    p = _project(_phase("initial", deactivate=["wall"]),
                 _phase("again", parent="initial", deactivate=["wall"]),
                 _phase("on", parent="again", activate=["wall"]),
                 _phase("on_again", parent="on", activate=["wall"]))
    assert [(on, off) for _, on, off in phases.transitions(p)] == [
        (set(), {"wall"}), (set(), set()), ({"wall"}, set()), (set(), set()),
    ]


# -- staged_excavation_phases ----------------------------------------------------------
# The staged excavation sequence (`tests/models/excavation.py` builds its phases
# with it). Not what
# "Create default phases" gives any more -- that is `default_phases`, below.
#
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
# parts at export (`core/kratos.py:_interface_by_body`), which is export's business.

def _model():
    from tests.models import excavation
    return excavation.excavation_project()


def _staged(project) -> schemas.Project:
    return schemas.Project.model_validate(
        project.model_dump()
        | {"phases": [ph.model_dump() for ph in phases.staged_excavation_phases(project)]})


def test_staged_excavation_phases_reproduce_the_reference_sequence():
    got = [(ph.id, sorted(on), sorted(off))
           for ph, on, off in phases.transitions(_staged(_model()))]
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


def test_staged_excavation_phases_leave_the_ground_under_the_pit_alone():
    """`Soil_Below_Pit` is on the dug side of the wall but is never dug, and stays
    active in all seven reference stages. Only the lifts come out."""
    last = phases.active_parts(_staged(_model()), "dig_3")
    assert {"soil_L_mid__pit", "soil_L_bot__pit"} <= last
    assert not {"soil_L_top__lift1", "soil_L_top__lift2", "soil_L_top__lift3"} & last


def test_staged_excavation_phases_reset_displacements_when_the_wall_goes_in():
    """The reference sets `reset_totals` true in exactly one stage, the wall's, so the
    wall's deflection is measured from the ground it was built into."""
    made = phases.staged_excavation_phases(_model())
    assert [ph.id for ph in made if ph.reset_displacements] == ["install_sheetpile"]


def test_the_first_staged_phase_is_the_only_k0_one():
    made = phases.staged_excavation_phases(_model())
    assert made[0].calculation == "K0 procedure"
    assert made[1].calculation == "Null step"
    assert all(ph.calculation == "Plastic" for ph in made[2:])


def test_staged_excavation_phases_make_a_project_that_validates():
    """They are written straight into `Project.phases`, so every id, parent and part key
    has to satisfy the schema's own cross-checks, and the chain has to linearise."""
    staged = _staged(_model())
    assert [ph.id for ph in phases.linearise(staged)] == \
        [ph.id for ph in staged.phases]


def test_an_anchor_is_installed_after_the_lift_that_exposes_it():
    """The reference installs the strut at -1.5 after the first lift reaches -2.0, not
    before: you cannot fix a strut to a wall face that is still buried."""
    order = [ph.id for ph in phases.staged_excavation_phases(_model())]
    assert order.index("dig_1") < order.index("install_strut") < order.index("dig_2")


# -- default_phases ----------------------------------------------------------
# What "Create default phases" gives: Initial stage, then Null step, and nothing else.
# Every further phase is the user's to add. The staged sequence above used to be
# the default, and on a new model it produced a "First excavation" that dug nothing --
# the blank project's placeholder excavation has a level but no soil to remove.

def test_the_default_is_the_initial_stage_then_the_null_step():
    made = phases.default_phases(_model())
    assert [(ph.id, ph.name, ph.parent) for ph in made] == [
        ("initial", "Initial stage", None),
        ("null_step", "Null step", "initial"),
    ]
    assert made[0].calculation == "K0 procedure"
    assert made[1].calculation == "Null step"
    assert made[1].max_iterations == 150


def test_a_new_model_gets_no_excavation_phase():
    from core.seed import blank_project

    assert [ph.id for ph in phases.default_phases(blank_project())] ==         ["initial", "null_step"]


def test_the_default_switches_nothing_off():
    """With no phase after them to switch anything back on, every part has to be active
    from the start: a part that is off in every phase is missing from the deck."""
    for ph in phases.default_phases(_model()):
        assert not ph.activate and not ph.deactivate, ph.id


def test_the_default_makes_a_project_that_validates_and_linearises():
    staged = schemas.Project.model_validate(
        _model().model_dump()
        | {"phases": [ph.model_dump() for ph in phases.default_phases(_model())]})
    assert [ph.id for ph in phases.linearise(staged)] == ["initial", "null_step"]


def test_an_unexcavated_project_still_gets_a_sequence():
    """Opening staged mode on a project with nothing dug must not produce an empty or
    invalid list -- the phase editor has to have something to show."""
    p = seed_project(simple=False)
    made = phases.default_phases(p)
    assert [ph.id for ph in made] == ["initial", "null_step"]
    schemas.Project.model_validate(
        p.model_dump() | {"phases": [ph.model_dump() for ph in made]})


# -- structure refusals and long chains (alpha 1.7) -------------------------

@pytest.mark.parametrize("records,message", [
    ([_phase("initial"), _phase("dig", parent="nowhere")], "starts from nowhere"),
    ([_phase("initial"), _phase("dig", parent="dig")], "starts from itself"),
    ([_phase("initial"), _phase("other")], "exactly one root"),
    ([_phase("initial"), _phase("a", parent="b"), _phase("b", parent="a")], "cycle"),
])
def test_a_phase_tree_that_is_not_a_tree_is_refused_by_name(records, message):
    with pytest.raises(ValidationError, match=message):
        _project(*records)


def test_a_part_switched_both_ways_in_one_phase_is_refused():
    with pytest.raises(ValidationError, match="soil_L1__lift1"):
        _project(_phase("initial"),
                 _phase("dig", parent="initial", activate=["soil_L1__lift1"],
                        deactivate=["soil_L1__lift1"]))


def test_a_fifty_phase_chain_runs_in_tree_order_however_it_is_listed():
    records = [_phase("initial")] + [_phase(f"p{n}", parent="initial" if n == 1 else f"p{n-1}")
                                     for n in range(1, 50)]
    project = _project(*reversed(records))

    order = [phase.id for phase in phases.linearise(project)]

    assert order == ["initial"] + [f"p{n}" for n in range(1, 50)]


def test_deactivating_a_part_already_gone_is_dropped_as_a_no_op():
    project = _project(
        _phase("initial"),
        _phase("dig1", parent="initial", deactivate=["soil_L1__lift1"]),
        _phase("dig2", parent="dig1", deactivate=["soil_L1__lift1", "soil_L1__lift2"]))

    by_id = {phase.id: (on, off) for phase, on, off in phases.transitions(project)}

    assert by_id["dig2"] == (set(), {"soil_L1__lift2"})


def test_reactivating_a_part_brings_it_back_from_that_phase_on():
    project = _project(
        _phase("initial"),
        _phase("dig", parent="initial", deactivate=["soil_L1__lift1"]),
        _phase("fill", parent="dig", activate=["soil_L1__lift1"]))

    assert "soil_L1__lift1" not in phases.active_parts(project, "dig")
    assert "soil_L1__lift1" in phases.active_parts(project, "fill")


def test_more_than_ten_lifts_are_still_named():
    assert phases._ordinal(10) == "Tenth"
    assert phases._ordinal(11) == "#11"
