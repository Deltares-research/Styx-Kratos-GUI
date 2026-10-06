"""One phase tree, resolved twice, held to the same answers.

Milestone D resolves the phase tree in the browser as well as on the server: the
viewport has to grey out what a phase switched off, and it cannot ask the server on
every click. That makes two implementations of one rule -- `app.phases.active_parts`
and `App.Phases.activeParts` -- and two implementations of one rule drift.

`live/tests/fixtures/phase-cases.js` is the document both are held to. This module owns
it: it builds the project, computes the answers with the real Python, and compares them
to what is on disk. `live/tests/test-phases.js` reads the same file in the browser and
compares the JavaScript to the same answers. Neither side can move without the fixture
moving, and the fixture cannot move without this test being run.

    python server/tests/test_phase_parity.py --write

rewrites it after a deliberate change.

It is a `.js` file assigning a global rather than a `.json` one because the browser
suite is opened from `file://`, where a fetch is blocked; Python strips the single
assignment off the front. One document, two readers.
"""

from __future__ import annotations

import json
import pathlib
import sys

# Run as a script (`--write`) there is no pytest to set up the path, and `server/` is
# the root everything here imports relative to. Harmless under pytest, which has put
# it there already.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import phases as phase_model, schemas   # noqa: E402
from app.seed import seed_project                # noqa: E402

FIXTURE = (pathlib.Path(__file__).resolve().parents[2]
           / "live" / "tests" / "fixtures" / "phase-cases.js")

HEADER = '''/* Generated fixture -- the one document both implementations of `active_parts` are
   held to. Milestone D asks for the phase tree to be resolved in the browser as well
   as on the server (plan sec D), and two implementations of one rule drift unless
   something says they agree. This is that something.

   A .js file assigning a global rather than a .json file, because the browser suite
   runs from `file://` and a fetch there is blocked; Python reads the same file and
   strips this one assignment off the front. One document, two readers -- see
   `server/tests/test_phase_parity.py`, which regenerates and compares it.

   Not hand-edited. `python server/tests/test_phase_parity.py --write` rebuilds it.
*/
window.PHASE_FIXTURE =
'''

# A hand-written sequence rather than `default_phases`, for two reasons. It has to
# exercise re-activation and a phase that changes nothing, neither of which the default
# sequence produces. And it must stay still: a fixture built from a function is a
# fixture that silently changes the day that function is improved, which is the
# opposite of what a parity fixture is for.
PHASES = [
    {"id": "initial", "name": "Initial stage", "parent": None,
     "calculation": "K0 procedure",
     "deactivate": ["wall", "anchors", "load", "soil_L1__lift1",
                    "soil_L1__lift2", "soil_L1__lift3"]},
    {"id": "null_step", "name": "Null step", "parent": "initial",
     "calculation": "Null step"},
    {"id": "build_wall", "name": "Wall installation", "parent": "null_step",
     "activate": ["wall", "load"], "reset_displacements": True},
    {"id": "dig_1", "name": "Dig to -2.0 m", "parent": "build_wall",
     "activate": ["soil_L1__lift1"], "deactivate": ["soil_L1"]},
    {"id": "prop", "name": "Strut installation", "parent": "dig_1",
     "activate": ["anchors"]},
    # Re-activates a part an earlier phase switched off -- the case a "last write wins"
    # reading of the chain gets wrong.
    {"id": "dig_2", "name": "Dig to -5.0 m", "parent": "prop",
     "activate": ["soil_L1__lift2", "soil_L1"], "deactivate": ["soil_L1__lift1"]},
    # Changes nothing: `soil_L1__lift1` is already off. Phases accumulate no-ops
    # through ordinary editing, and both sides have to shrug at them identically.
    {"id": "settle", "name": "Consolidate", "parent": "dig_2",
     "deactivate": ["soil_L1__lift1"]},
]


def _project() -> schemas.Project:
    """The CROW soil arrangement -- three layers, three lifts -- with PHASES on it.

    The same shape `test_schemas._crow_like` builds, restated rather than imported so
    that the fixture does not move when that helper is edited for a different reason.
    """
    payload = seed_project(simple=False).model_dump()
    payload["domain"] |= {"y_top": 0.0, "y_bottom": -60.0}
    payload["boreholes"] = [payload["boreholes"][0]]
    borehole = payload["boreholes"][0]["id"]
    payload["layers"] = [
        {"id": "L1", "name": "Soil_1", "mat": payload["materials"][0]["id"],
         "tops": {borehole: 0.0}, "bots": {borehole: -8.0}},
        {"id": "L2", "name": "Soil_2", "mat": payload["materials"][0]["id"],
         "tops": {borehole: -8.0}, "bots": {borehole: -12.0}},
        {"id": "L3", "name": "Soil_3", "mat": payload["materials"][1]["id"],
         "tops": {borehole: -12.0}, "bots": {borehole: -60.0}},
    ]
    payload["excavation"] = {k: v for k, v in payload["excavation"].items()
                             if k != "floor_y"}
    payload["excavation"] |= {"x0": 0.0, "x1": 5.0, "levels": [-2.0, -5.0, -8.0]}
    payload["wall"] |= {"top_y": 0.0, "toe_y": -13.0}
    payload["phases"] = PHASES
    return schemas.Project.model_validate(payload)


def build() -> dict:
    project = _project()
    return {
        "project": json.loads(project.model_dump_json()),
        "stageable_keys": project.stageable_keys(),
        "active_parts": {phase.id: sorted(phase_model.active_parts(project, phase.id))
                         for phase in project.phases},
        "order": [phase.id for phase in phase_model.linearise(project)],
    }


def render(document: dict) -> str:
    return HEADER + json.dumps(document, indent=2) + ";\n"


def stored() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    marker = "window.PHASE_FIXTURE ="
    body = text[text.index(marker) + len(marker):].strip()
    return json.loads(body.rstrip(";"))


# ── The tests ───────────────────────────────────────────────────────────────

def test_the_fixture_on_disk_is_what_the_server_computes():
    """The fixture is generated, so it can go stale the moment `active_parts` changes
    -- and a stale fixture would make the JavaScript agree with an answer the server
    no longer gives, which is worse than having no fixture at all."""
    assert stored() == build(), (
        "live/tests/fixtures/phase-cases.js is out of date. Rerun\n"
        "    python server/tests/test_phase_parity.py --write\n"
        "and check what changed before committing it."
    )


def test_the_fixture_is_a_parseable_javascript_assignment():
    """The browser reads it as a script tag; Python reads it by stripping one prefix.
    Both readings have to keep working, and only this one is automated."""
    text = FIXTURE.read_text(encoding="utf-8")
    assert text.count("window.PHASE_FIXTURE =") == 1
    assert text.rstrip().endswith(";")


def test_the_fixture_exercises_the_cases_a_chain_walk_gets_wrong():
    """A fixture both sides pass trivially proves nothing. These are the three shapes
    worth having: a part switched off and later switched back on, an instruction that
    changes nothing, and a phase that says nothing at all."""
    document = stored()
    assert document["active_parts"]["dig_1"] != document["active_parts"]["dig_2"]
    # soil_L1 is off from dig_1 and back on at dig_2.
    assert "soil_L1" not in document["active_parts"]["dig_1"]
    assert "soil_L1" in document["active_parts"]["dig_2"]
    # `settle` repeats an instruction that has already taken effect.
    assert document["active_parts"]["settle"] == document["active_parts"]["dig_2"]
    # `null_step` carries neither list.
    assert document["active_parts"]["null_step"] == document["active_parts"]["initial"]


def test_every_phase_has_an_answer_and_the_order_is_the_chain():
    document = stored()
    assert set(document["active_parts"]) == {p["id"] for p in document["project"]["phases"]}
    assert document["order"] == [p["id"] for p in document["project"]["phases"]]


def test_the_active_set_is_always_a_subset_of_what_can_be_staged():
    """`active_parts` starts from `stageable_keys` and only ever removes and re-adds
    from it, so a part appearing that the model does not have would mean one of the
    two implementations invented it."""
    document = stored()
    keys = set(document["stageable_keys"])
    for phase, active in document["active_parts"].items():
        assert set(active) <= keys, phase


if __name__ == "__main__":
    if "--write" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(render(build()), encoding="utf-8")
        print(f"wrote {FIXTURE}")
    else:
        print(__doc__)
