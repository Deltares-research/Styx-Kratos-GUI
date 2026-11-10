"""One edit, made on the command line and made in the GUI, gives one project.

The two front ends save the same project file through `core.session`, but they do not
make an edit the same way. `kratos-cli anchor FILE remove strut` calls
`session.remove_structure`; the GUI's Delete works out the new list in JavaScript and
sends it (`PATCH /api/project/structures` -> `session.replace_structures`). A rule kept
in one path and not the other is a project one front end makes and the other refuses,
as the mesh size of a deleted body was.

Each case is one Delete the GUI offers, found in its code by
`test_every_delete_the_gui_offers_is_a_case`. This module holds the server half: the
command line, and the route given what the GUI sends, end on the same project, or both
refuse. `frontend/tests/test-edits.js` holds the browser half: the GUI, driven the way
the user drives it, sends exactly that request. The request is the one document both
are held to, `frontend/tests/fixtures/edits.js`, written from here:

    python tests/cli/test_edit_parity.py --write

The GUI offers no Delete of a section (`kratos-cli section remove`): a section is
removed on the command line only.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Callable

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest   # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402

from backend.main import app   # noqa: E402
from core import session   # noqa: E402
from core.model.schemas import Project   # noqa: E402
from tests.models import edits   # noqa: E402
from tests.models.excavation import excavation_project   # noqa: E402

FIXTURE = ROOT / "frontend" / "tests" / "fixtures" / "edits.js"
GUI = ROOT / "frontend" / "js"

HEADER = '''/* Generated fixture -- each Delete the GUI offers, with the request it sends.
   tests/cli/test_edit_parity.py checks that the command line, and the route given this
   request, end on the same project; frontend/tests/test-edits.js checks that the GUI
   sends exactly this request.
   Not hand-edited. `python tests/cli/test_edit_parity.py --write` rebuilds it. */
window.EDITS_FIXTURE =
'''

STRUCTURES = "/api/project/structures"

BOX = {"kind": "box", "origin": [0, -5, 0], "size": [2, 2, 2]}
BRICK = {"brep_path": "drawn.brep", "bbox": [0, -5, 0, 2, -3, 2]}
"""A drawn box, and what the gmsh worker would answer for it: no gmsh runs here."""


def _pit(*taken_out: str, staged: bool = False) -> Project:
    """The test pit with `edits.SIZED`, less the structures `taken_out` first."""
    project = excavation_project(staged=staged)
    for id in taken_out:
        project = session.remove_structure(project, id)
    return edits.sized(project)


def _with_a_spare_material() -> Project:
    """A material no layer uses, which is the only kind the GUI lets go."""
    project = _pit()
    spare = project.materials[0].model_copy(update={"id": "m_spare", "name": "Spare"})
    return project.model_copy(update={"materials": [*project.materials, spare]})


def _with_a_drawn_box() -> Project:
    built, _ = session.with_created_part(excavation_project(staged=False), BOX, BRICK)
    return edits.sized(built)


PROJECTS: dict[str, Callable[[], Project]] = {
    "pit": _pit,
    "pit without strut or contact": lambda: _pit("strut", "wall_contact"),
    "staged pit": lambda: _pit(staged=True),
    "pit with a spare material": _with_a_spare_material,
    "pit with a drawn box": _with_a_drawn_box,
}


def _structures(field: str, sections: str | None) -> Callable[[dict, str], dict]:
    """A Structure-mode Delete (`beams.js`, `anchors.js`, `interfaces.js`,
    `normal-loads.js` `remove`): the loads as they are, the list without the record,
    and its section library as it is."""
    def body(project: dict, id: str) -> dict:
        lists = {field: edits.without(project[field], id)}
        if sections:
            lists[sections] = project[sections]
        return edits.structures_sent(project, **lists)
    return body


def _loads(project: dict, id: str) -> dict:
    """`loads.js` `remove`."""
    return {"loads": edits.without(project["loads"], id)}


def _conditions(project: dict, id: str) -> dict:
    """`boundary-conditions.js` `remove`."""
    return {"boundary_conditions": edits.without(project["boundary_conditions"], id)}


def _lines(project: dict, id: str) -> dict:
    """`lines.js` `remove`."""
    return {"lines": edits.without(project["lines"], id)}


def _layers_from_the_tree(project: dict, id: str) -> dict:
    """The Model explorer's Delete on a layer (`SoilLayersDialog.removeById`, then
    `App.commitSelectionEdit`): the stack, with the domain, the water and the custom
    parts that are edited from the same panel."""
    return {"layers": edits.stack_without(project["layers"], id),
            "domain": project["domain"], "water": project["water"],
            "custom_parts": project["custom_parts"]}


def _stages(project: dict, id: str) -> dict:
    """`stages.js` `removed`, sent by the stage list's Delete: its children start from
    its parent."""
    gone = next(stage for stage in project["stages"] if stage["id"] == id)
    stages = json.loads(json.dumps(edits.without(project["stages"], id)))
    for stage in stages:
        if stage["parent"] == id:
            stage["parent"] = gone["parent"]
    return {"stages": stages}


def _materials(project: dict, id: str) -> dict:
    """The Material sets window's Delete, then its OK: the library without it, and the
    water edited in the same window, as it was."""
    return {"materials": edits.without(project["materials"], id), "fluid": project["fluid"]}


@dataclass(frozen=True)
class Case:
    title: str
    cli: tuple[str, ...]
    """The command, less the file: `("anchor", "remove", "strut")`."""
    offered: str
    """Where the GUI offers it, as `offered_deletes` finds it in the GUI's code."""
    call: str
    """What `test-edits.js` drives: `App.<call>`."""
    route: str
    body: Callable[[dict, str], dict] | None
    """What the GUI sends, from the project as JSON and the id; None for a DELETE."""
    project: str = "pit"
    """The key of `PROJECTS` the case starts from."""
    method: str = "PATCH"
    refused: bool = False

    @property
    def target(self) -> str:
        return self.cli[-1]

    def sent(self, project: Project) -> dict | None:
        if self.body is None:
            return None
        return self.body(project.model_dump(mode="json"), self.target)


CASES = [
    Case("an anchor", ("anchor", "remove", "strut"), "App.Anchors.remove",
         "Anchors.remove", STRUCTURES, _structures("anchors", "anchor_sections")),
    Case("an interface", ("interface", "remove", "wall_contact"), "App.Interfaces.remove",
         "Interfaces.remove", STRUCTURES, _structures("interfaces", "interface_sections")),
    Case("a sheet pile nothing hangs from", ("beam", "remove", "sheetpile"),
         "App.Beams.remove", "Beams.remove", STRUCTURES,
         _structures("beams", "beam_sections"), project="pit without strut or contact"),
    Case("a line load", ("load", "remove", "surcharge"), "App.Loads.remove",
         "Loads.remove", STRUCTURES, _loads),
    Case("a line", ("line", "remove", "floor_2"), "App.Lines.remove", "Lines.remove",
         "/api/project/lines", _lines),
    Case("a normal load", ("normal-load", "remove", "water_1"), "App.NormalLoads.remove",
         "NormalLoads.remove", STRUCTURES, _structures("normal_loads", None)),
    Case("a boundary condition", ("boundary", "remove", "roller_front"),
         "App.BoundaryConditions.remove", "BoundaryConditions.remove",
         "/api/project/conditions", _conditions),
    Case("a soil layer, in the soil layers window", ("layer", "remove", "L_mid"),
         "Delete button: deleteLayer", "Dialogs.soilLayers", "/api/project/layers",
         edits.layers_window_sent),
    Case("a soil layer, in the model tree", ("layer", "remove", "L_mid"),
         "App.SoilLayersDialog.removeById", "deleteLayerById", "/api/project/layers",
         _layers_from_the_tree),
    Case("a stage", ("stages", "remove", "dig_2"), "App.Stages.removed",
         "Explorer.mountPhases", "/api/project/stages", _stages, project="staged pit"),
    Case("a material set", ("material", "remove", "m_spare"), "App.MATERIALS.splice",
         "Dialogs.materials", "/api/project/materials", _materials,
         project="pit with a spare material"),
    Case("a custom volume", ("volume", "remove", "drawn_0"),
         "DELETE /api/geometry/parts/", "LivePatches.deleteCustomPart",
         "/api/geometry/parts/drawn_0", None, project="pit with a drawn box",
         method="DELETE"),
    Case("every custom volume", ("volume", "clear"),
         "DELETE /api/project/custom_parts", "Command.run",
         "/api/project/custom_parts", None, project="pit with a drawn box", method="DELETE"),
    Case("a sheet pile an anchor hangs from", ("beam", "remove", "sheetpile"),
         "App.Beams.remove", "Beams.remove", STRUCTURES,
         _structures("beams", "beam_sections"), refused=True),
    Case("an anchor a stage switches on", ("anchor", "remove", "strut"),
         "App.Anchors.remove", "Anchors.remove", STRUCTURES,
         _structures("anchors", "anchor_sections"), project="staged pit", refused=True),
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/project/reset")


def _in_the_gui(client, case: Case, project: Project):
    assert client.put("/api/project", json=project.model_dump(mode="json")).status_code == 200
    return client.request(case.method, case.route, json=case.sent(project))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.title)
def test_the_command_line_and_the_gui_make_one_edit_alike(case, cli, client, tmp_path):
    project = PROJECTS[case.project]()
    path = session.save(project, tmp_path / "model.json")

    ran = cli(case.cli[0], path, *case.cli[1:])
    answer = _in_the_gui(client, case, project)

    if case.refused:
        assert (ran.code, answer.status_code) == (1, 422), (ran.err, answer.text)
        return
    assert (ran.code, answer.status_code) == (0, 200), (ran.err, answer.text)
    in_the_gui = Project.model_validate(answer.json()["project"])
    assert session.load(path).model_dump(mode="json") == in_the_gui.model_dump(mode="json")


@pytest.mark.parametrize("case", [c for c in CASES if not c.refused],
                         ids=lambda case: case.title)
def test_a_project_the_gui_edited_passes_the_command_lines_check(case, cli, client, tmp_path):
    edited = _in_the_gui(client, case, PROJECTS[case.project]()).json()["project"]
    path = tmp_path / "saved.json"
    path.write_text(json.dumps(edited, indent=2), encoding="utf-8")   # as the GUI saves

    ran = cli("check", path)

    assert ran.code == 0


# ── Every Delete the GUI offers ─────────────────────────────────────────────

OFFERS = (
    (r"App\.(\w+)\.(remove|removed|removeById)\b", r"App.\1.\2"),
    (r"deleteRequest\(\s*'([^']*)'", r"DELETE \1"),
    (r"App\.([A-Z_]+)\.splice\([^()]*,\s*1\)", r"App.\1.splice"),
    (r"\['Delete',\s*(\w+)\]", r"Delete button: \1"),
)
"""How the GUI takes a record out of the project: a module's `remove` (the Delete
buttons and the tree menu call these), a DELETE request, one record spliced out of a
project list, and a Delete button bound to a function of its window."""

FROZEN_DELETES_REPLACED = ("App.Dialogs.soilLayers = ", "App.Dialogs.materials = function",
                           "App.deleteLayerById = ")
"""`frontend/base` is the frozen mockup. Its layer, borehole and material windows and
its tree's layer Delete are replaced by these in `patches.js`, so only `frontend/js`
is read for a Delete."""


def offered_deletes() -> dict[str, list[str]]:
    """Each Delete found in the GUI's code, and the files it is in."""
    found: dict[str, list[str]] = {}
    for path in sorted(GUI.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for pattern, name in OFFERS:
            for match in re.finditer(pattern, text):
                found.setdefault(match.expand(name), []).append(path.name)
    return found


def test_every_delete_the_gui_offers_is_a_case():
    """A Delete with no case is one the two front ends can disagree on unseen."""
    found = offered_deletes()
    covered = {case.offered for case in CASES}

    assert len(found) >= 12, f"the scan found too little to be reading the GUI: {found}"
    assert sorted(set(found) - covered) == [], "a Delete the GUI offers has no case here"
    assert sorted(covered - set(found)) == [], "a case names a Delete the GUI no longer has"
    patches = (GUI / "patches.js").read_text(encoding="utf-8")
    assert [text for text in FROZEN_DELETES_REPLACED if text not in patches] == []


# ── The fixture ─────────────────────────────────────────────────────────────

def document() -> dict:
    projects = {name: PROJECTS[name]().model_dump(mode="json")
                for name in sorted({case.project for case in CASES})}
    cases = []
    for case in CASES:
        project = projects[case.project]
        cases.append({"title": case.title, "call": case.call, "target": case.target,
                      "method": case.method, "route": case.route, "project": case.project,
                      "body": case.body(project, case.target) if case.body else None})
    return {"projects": projects, "cases": cases}


def rendered() -> str:
    return HEADER + json.dumps(document(), indent=2, ensure_ascii=False) + ";\n"


def test_the_fixture_is_what_the_cases_say():
    assert FIXTURE.is_file(), "run `python tests/cli/test_edit_parity.py --write`"
    assert FIXTURE.read_text(encoding="utf-8") == rendered(), (
        "run `python tests/cli/test_edit_parity.py --write`")


if __name__ == "__main__" and "--write" in sys.argv:
    FIXTURE.write_text(rendered(), encoding="utf-8", newline="\n")
    print(f"wrote {FIXTURE}")
