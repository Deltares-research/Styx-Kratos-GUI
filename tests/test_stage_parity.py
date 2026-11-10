"""One stage tree, resolved twice, held to the same answers.

Milestone D resolves the stage tree in the browser as well as on the server: the
viewport has to grey out what a stage switched off, and it cannot ask the server on
every click. That makes two implementations of one rule -- `core.model.stages.active_parts`
and `App.Stages.activeParts` -- and two implementations of one rule drift.

`frontend/tests/fixtures/stage-cases.js` is the document both are held to. This module owns
it: it builds the project, computes the answers with the real Python, and compares them
to what is on disk. `frontend/tests/test-stages.js` reads the same file in the browser and
compares the JavaScript to the same answers. Neither side can move without the fixture
moving, and the fixture cannot move without this test being run.

    python tests/test_stage_parity.py --write

rewrites it after a deliberate change.

It is a `.js` file assigning a global rather than a `.json` one because the browser
suite is opened from `file://`, where a fetch is blocked; Python strips the single
assignment off the front. One document, two readers.
"""

from __future__ import annotations

import json
import pathlib
import sys

# Run as a script (`--write`) there is no pytest to set up the path, and the repository
# root is what everything here imports relative to. Harmless under pytest, which has put
# it there already.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.model import stages, schemas   # noqa: E402
from core.model.templates import seed_project                # noqa: E402

FIXTURE = (pathlib.Path(__file__).resolve().parents[1]
           / "frontend" / "tests" / "fixtures" / "stage-cases.js")

HEADER = '''/* Generated fixture -- the one document both implementations of `active_parts` are
   held to. Milestone D asks for the stage tree to be resolved in the browser as well
   as on the server (plan sec D), and two implementations of one rule drift unless
   something says they agree. This is that something.

   A .js file assigning a global rather than a .json file, because the browser suite
   runs from `file://` and a fetch there is blocked; Python reads the same file and
   strips this one assignment off the front. One document, two readers -- see
   `tests/test_stage_parity.py`, which regenerates and compares it.

   Not hand-edited. `python tests/test_stage_parity.py --write` rebuilds it.
*/
window.STAGE_FIXTURE =
'''

# A hand-written sequence rather than `default_stages`, for two reasons. It has to
# exercise re-activation and a stage that changes nothing, neither of which the default
# sequence produces. And it must stay still: a fixture built from a function is a
# fixture that silently changes the day that function is improved, which is the
# opposite of what a parity fixture is for.
STAGES = [
    {"id": "initial", "name": "Initial stage", "parent": None,
     "calculation": "K0 procedure",
     "deactivate": ["pile", "tie", "load", "soil_L1__lift1",
                    "soil_L1__lift2", "soil_L1__lift3"]},
    {"id": "null_step", "name": "Null step", "parent": "initial",
     "calculation": "Null step"},
    {"id": "build_wall", "name": "Wall installation", "parent": "null_step",
     "activate": ["pile", "load"], "reset_displacements": True},
    {"id": "dig_1", "name": "Dig to -2.0 m", "parent": "build_wall",
     "activate": ["soil_L1__lift1"], "deactivate": ["soil_L1"]},
    {"id": "prop", "name": "Strut installation", "parent": "dig_1",
     "activate": ["tie"]},
    # Re-activates a part an earlier stage switched off -- the case a "last write wins"
    # reading of the chain gets wrong.
    {"id": "dig_2", "name": "Dig to -5.0 m", "parent": "prop",
     "activate": ["soil_L1__lift2", "soil_L1"], "deactivate": ["soil_L1__lift1"]},
    # Changes nothing: `soil_L1__lift1` is already off. Stages accumulate no-ops
    # through ordinary editing, and both sides have to shrug at them identically.
    {"id": "settle", "name": "Consolidate", "parent": "dig_2",
     "deactivate": ["soil_L1__lift1"]},
]


def _project() -> schemas.Project:
    """A staged soil arrangement -- three layers, three lifts -- with STAGES on it.

    The same shape `test_schemas._layered_pit` builds, restated rather than imported so
    that the fixture does not move when that helper is edited for a different reason.
    """
    payload = seed_project().model_dump()
    payload["domain"] |= {"y_top": 0.0, "y_bottom": -60.0}
    payload["layers"] = [
        {"id": "L1", "name": "Soil_1", "mat": payload["materials"][0]["id"],
         "top": 0.0, "bottom": -8.0},
        {"id": "L2", "name": "Soil_2", "mat": payload["materials"][0]["id"],
         "top": -8.0, "bottom": -12.0},
        {"id": "L3", "name": "Soil_3", "mat": payload["materials"][1]["id"],
         "top": -12.0, "bottom": -60.0},
    ]
    payload["excavation"] = {"x0": 0.0, "x1": 5.0, "z0": payload["domain"]["z0"],
                         "z1": payload["domain"]["z1"], "levels": [-2.0, -5.0, -8.0]}
    # Two parts for a stage to switch that are not soil.
    payload["beam_sections"] = [schemas.BeamSection(id="s", name="S", variables={}).model_dump()]
    payload["beams"] = [{"id": "pile", "name": "Pile", "section": "s",
                         "points": [(5.0, 0.0), (5.0, -13.0)]}]
    payload["anchor_sections"] = [schemas.AnchorSection(id="t", name="T",
                                                        variables={}).model_dump()]
    payload["anchors"] = [{"id": "tie", "name": "Tie", "section": "t",
                           "head": (5.0, -1.0), "tail": (3.0, -1.0)}]
    payload["stages"] = STAGES
    return schemas.Project.model_validate(payload)


EDITS = [
    ("added", []),
    ("inserted", ["dig_1"]),
    ("inserted", ["initial"]),
    ("removed", ["prop"]),
    ("removed", ["initial"]),
    ("copied", ["build_wall"]),
    ("copied", ["settle"]),
    ("setActive", ["dig_1", ["wall"], False]),
    ("setActive", ["prop", ["soil_L1", "anchors"], False]),
    ("setActive", ["settle", ["soil_L1__lift1"], True]),
    ("setActive", ["build_wall", ["wall"], False]),
    # The stage after is kept as it was: build_wall gains a "deactivate" for the lift
    # null_step now switches on, and dig_2's "activate soil_L1" is dropped once prop
    # already has it on.
    ("setActive", ["null_step", ["soil_L1__lift1"], True]),
    ("setActive", ["prop", ["soil_L1"], True]),
]
"""The Stages toolbar's edits and the Model explorer's checkbox, each called on the
project by its JavaScript name with these arguments after it. The roots and the last
stage are in it because that is where healing a chain goes wrong."""

PYTHON_EDITS = {"added": stages.added, "inserted": stages.inserted,
                "removed": stages.removed, "copied": stages.copied,
                "setActive": stages.set_active}


def build() -> dict:
    project = _project()
    return {
        "edits": [{"call": call, "args": args,
                   "result": [stage.model_dump(mode="json")
                              for stage in PYTHON_EDITS[call](project, *args)]}
                  for call, args in EDITS],
        "project": json.loads(project.model_dump_json()),
        "stageable_keys": project.stageable_keys(),
        "active_parts": {stage.id: sorted(stages.active_parts(project, stage.id))
                         for stage in project.stages},
        "order": [stage.id for stage in stages.linearise(project)],
    }


def render(document: dict) -> str:
    return HEADER + json.dumps(document, indent=2) + ";\n"


def stored() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    marker = "window.STAGE_FIXTURE ="
    body = text[text.index(marker) + len(marker):].strip()
    return json.loads(body.rstrip(";"))


# ── The tests ───────────────────────────────────────────────────────────────

def test_every_edit_the_gui_makes_is_in_the_fixture():
    assert {call for call, _ in EDITS} == set(PYTHON_EDITS)


def test_the_fixture_on_disk_is_what_the_server_computes():
    """The fixture is generated, so it can go stale the moment `active_parts` changes
    -- and a stale fixture would make the JavaScript agree with an answer the server
    no longer gives, which is worse than having no fixture at all."""
    assert stored() == build(), (
        "frontend/tests/fixtures/stage-cases.js is out of date. Rerun\n"
        "    python tests/test_stage_parity.py --write\n"
        "and check what changed before committing it."
    )


def test_the_fixture_is_a_parseable_javascript_assignment():
    """The browser reads it as a script tag; Python reads it by stripping one prefix.
    Both readings have to keep working, and only this one is automated."""
    text = FIXTURE.read_text(encoding="utf-8")
    assert text.count("window.STAGE_FIXTURE =") == 1
    assert text.rstrip().endswith(";")


def test_the_fixture_exercises_the_cases_a_chain_walk_gets_wrong():
    """A fixture both sides pass trivially proves nothing. These are the three shapes
    worth having: a part switched off and later switched back on, an instruction that
    changes nothing, and a stage that says nothing at all."""
    document = stored()
    assert document["active_parts"]["dig_1"] != document["active_parts"]["dig_2"]
    # soil_L1 is off from dig_1 and back on at dig_2.
    assert "soil_L1" not in document["active_parts"]["dig_1"]
    assert "soil_L1__outside" in document["active_parts"]["dig_2"]
    # `settle` repeats an instruction that has already taken effect.
    assert document["active_parts"]["settle"] == document["active_parts"]["dig_2"]
    # `null_step` carries neither list.
    assert document["active_parts"]["null_step"] == document["active_parts"]["initial"]


def test_every_stage_has_an_answer_and_the_order_is_the_chain():
    document = stored()
    assert set(document["active_parts"]) == {p["id"] for p in document["project"]["stages"]}
    assert document["order"] == [p["id"] for p in document["project"]["stages"]]


def test_the_active_set_is_always_a_subset_of_what_can_be_staged():
    """`active_parts` starts from `stageable_keys` and only ever removes and re-adds
    from it, so a part appearing that the model does not have would mean one of the
    two implementations invented it."""
    document = stored()
    keys = set(document["stageable_keys"])
    for stage, active in document["active_parts"].items():
        assert set(active) <= keys, stage


if __name__ == "__main__":
    if "--write" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(render(build()), encoding="utf-8")
        print(f"wrote {FIXTURE}")
    else:
        print(__doc__)
