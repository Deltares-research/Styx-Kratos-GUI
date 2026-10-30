"""One edit, made on the command line and made in the GUI, gives one project.

The two front ends save the same project file through `core.session`, but they do not
make an edit the same way. `kratos-cli anchor FILE remove strut` calls
`session.remove_structure`; the GUI's Delete works out the new list in JavaScript and
sends it (`PATCH /api/project/structures` -> `session.replace_structures`). A rule kept
in one path and not the other is a project one front end makes and the other refuses,
as the mesh size of a deleted body was.

Each case is one Delete the GUI offers. This module holds the server half: the command
line, and the route given what the GUI sends, end on the same project, or both refuse.
`frontend/tests/test-edits.js` holds the browser half: the GUI's function sends exactly
that body. The body is the one document both are held to,
`frontend/tests/fixtures/edits.js`, written from here:

    python tests/cli/test_edit_parity.py --write
"""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import pytest   # noqa: E402
from fastapi.testclient import TestClient   # noqa: E402

from backend.main import app   # noqa: E402
from core import session   # noqa: E402
from core.model.schemas import Project   # noqa: E402
from tests.models.excavation import excavation_project   # noqa: E402

FIXTURE = (pathlib.Path(__file__).resolve().parents[2]
           / "frontend" / "tests" / "fixtures" / "edits.js")

HEADER = '''/* Generated fixture -- each Delete the GUI offers, with the body it sends.
   tests/cli/test_edit_parity.py checks that the command line, and the route given this
   body, end on the same project; frontend/tests/test-edits.js checks that the GUI's
   function sends exactly this body.
   Not hand-edited. `python tests/cli/test_edit_parity.py --write` rebuilds it. */
window.EDITS_FIXTURE =
'''

SIZES = {"sheetpile": 0.5, "strut": 0.5, "wall_contact": 0.5, "water_1": 0.5,
         "soil_L_mid": 1.0, "soil_L_mid__pit": 1.0}
"""An element size on each body a case takes away: the two front ends once disagreed on
what becomes of it."""

READ_BY_THE_GUI = ("loads", "beams", "beam_sections", "panel_sections", "anchors",
                   "anchor_sections", "interfaces", "interface_sections", "normal_loads",
                   "boundary_conditions", "layers")
"""What the GUI's Delete reads of the project: all the fixture carries of one."""

STRUCTURES = "/api/project/structures"


def model(*taken_out: str, staged: bool = False) -> Project:
    """The test pit with `SIZES`, less the structures `taken_out` first."""
    project = excavation_project(staged=staged)
    for id in taken_out:
        project = session.remove_structure(project, id)
    sizes = {key: size for key, size in SIZES.items() if key in project.part_keys()}
    return project.model_copy(update={"mesh": project.mesh.model_copy(
        update={"body_sizes": sizes})})


def _without(records: list[dict], id: str) -> list[dict]:
    return [record for record in records if record["id"] != id]


def _structures(field: str, sections: str | None) -> Callable[[dict, str], dict]:
    """A Structure-mode Delete (`beams.js`, `anchors.js`, `interfaces.js`,
    `normal-loads.js` `remove`): the loads as they are, the list without the record,
    and its section library as it is."""
    def body(project: dict, id: str) -> dict:
        sent = {"loads": project["loads"], field: _without(project[field], id)}
        if sections:
            sent[sections] = project[sections]
        return sent
    return body


def _loads(project: dict, id: str) -> dict:
    """`loads.js` `remove`."""
    return {"loads": _without(project["loads"], id)}


def _conditions(project: dict, id: str) -> dict:
    """`boundary-conditions.js` `remove`."""
    return {"boundary_conditions": _without(project["boundary_conditions"], id)}


def _layers(project: dict, id: str) -> dict:
    """The soil layers window's Delete (`SoilLayersDialog.remove`, then its commit): the
    layer above takes the bottom of the one removed; for the top layer, the layer below
    takes its top."""
    layers = json.loads(json.dumps(project["layers"]))
    index = [layer["id"] for layer in layers].index(id)
    gone = layers.pop(index)
    if index > 0:
        layers[index - 1]["bottom"] = gone["bottom"]
    else:
        layers[0]["top"] = gone["top"]
    return {"layers": layers, "materials": project["materials"]}


@dataclass(frozen=True)
class Case:
    title: str
    cli: tuple[str, ...]
    """The command, less the file: `("anchor", "remove", "strut")`."""
    call: str
    """The GUI's function, `App.<call>`."""
    route: str
    body: Callable[[dict, str], dict]
    project: Callable[[], Project] = model
    refused: bool = False

    @property
    def target(self) -> str:
        return self.cli[-1]

    def sent(self, project: Project) -> dict:
        return self.body(project.model_dump(mode="json"), self.target)


CASES = [
    Case("an anchor", ("anchor", "remove", "strut"), "Anchors.remove", STRUCTURES,
         _structures("anchors", "anchor_sections")),
    Case("an interface", ("interface", "remove", "wall_contact"), "Interfaces.remove",
         STRUCTURES, _structures("interfaces", "interface_sections")),
    Case("a sheet pile nothing hangs from", ("beam", "remove", "sheetpile"),
         "Beams.remove", STRUCTURES, _structures("beams", "beam_sections"),
         project=lambda: model("strut", "wall_contact")),
    Case("a line load", ("load", "remove", "surcharge"), "Loads.remove", STRUCTURES, _loads),
    Case("a normal load", ("normal-load", "remove", "water_1"), "NormalLoads.remove",
         STRUCTURES, _structures("normal_loads", None)),
    Case("a boundary condition", ("boundary", "remove", "roller_front"),
         "BoundaryConditions.remove", "/api/project/conditions", _conditions),
    Case("a soil layer", ("layer", "remove", "L_mid"), "SoilLayersDialog.remove",
         "/api/project/layers", _layers),
    Case("a sheet pile an anchor hangs from", ("beam", "remove", "sheetpile"),
         "Beams.remove", STRUCTURES, _structures("beams", "beam_sections"), refused=True),
    Case("an anchor a stage switches on", ("anchor", "remove", "strut"), "Anchors.remove",
         STRUCTURES, _structures("anchors", "anchor_sections"),
         project=lambda: model(staged=True), refused=True),
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/project/reset")


def _in_the_gui(client, case: Case, project: Project):
    assert client.put("/api/project", json=project.model_dump(mode="json")).status_code == 200
    return client.patch(case.route, json=case.sent(project))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.title)
def test_the_command_line_and_the_gui_make_one_edit_alike(case, cli, client, tmp_path):
    project = case.project()
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
    edited = _in_the_gui(client, case, case.project()).json()["project"]
    path = tmp_path / "saved.json"
    path.write_text(json.dumps(edited, indent=2), encoding="utf-8")   # as the GUI saves

    ran = cli("check", path)

    assert ran.code == 0, ran.err


def test_every_delete_the_gui_offers_is_a_case():
    """A Delete with no case is one the two front ends can disagree on unseen."""
    assert {case.call for case in CASES} >= {
        "Beams.remove", "Anchors.remove", "Interfaces.remove", "Loads.remove",
        "NormalLoads.remove", "BoundaryConditions.remove", "SoilLayersDialog.remove"}


def document() -> dict:
    cases = []
    for case in CASES:
        project = case.project().model_dump(mode="json")
        cases.append({"title": case.title, "call": case.call, "target": case.target,
                      "route": case.route,
                      "project": {key: project[key] for key in READ_BY_THE_GUI},
                      "body": case.body(project, case.target)})
    return {"cases": cases}


def rendered() -> str:
    return HEADER + json.dumps(document(), indent=2, ensure_ascii=False) + ";\n"


def test_the_fixture_is_what_the_cases_say():
    assert FIXTURE.is_file(), "run `python tests/cli/test_edit_parity.py --write`"
    assert FIXTURE.read_text(encoding="utf-8") == rendered(), (
        "run `python tests/cli/test_edit_parity.py --write`")


if __name__ == "__main__" and "--write" in sys.argv:
    FIXTURE.write_text(rendered(), encoding="utf-8", newline="\n")
    print(f"wrote {FIXTURE}")
