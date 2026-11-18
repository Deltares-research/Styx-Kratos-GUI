"""What a user does in the GUI leaves a file the command line takes, and the other way.

Opt-in: `--run-e2e`. `tests/cli/test_edit_parity.py` and `tests/cli/test_handover.py`
hold the same without a browser; this drives the real page.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout

from cli.terminal.main import main
from tests.e2e.conftest import command, log_text
from tests.e2e.test_flows import LONG, wait_meshed
from tests.models.excavation import excavation_project

TOOL = '#maintoolbar .tbtn[data-action="{}"]'


def kratos_cli(*argv) -> int:
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return main([str(arg) for arg in argv])


def test_a_sized_strut_and_interface_deleted_in_the_gui_leave_a_project_both_mesh(
        app_page, live_server, tmp_path):
    project = excavation_project(staged=False)
    sizes = {**project.mesh.body_sizes, "strut": 0.5, "wall_contact": 0.5}
    project = project.model_copy(update={"mesh": project.mesh.model_copy(
        update={"body_sizes": sizes})})
    assert app_page.request.put(live_server["url"] + "/api/project",
                                data=project.model_dump(mode="json")).ok
    app_page.reload()
    app_page.wait_for_function(
        f"App.PROJECT && App.PROJECT.name === '{project.name}' && App.ANCHORS"
        " && App.ANCHORS.length === 1", timeout=LONG)

    app_page.evaluate("App.Anchors.remove('strut')"
                      ".then(function () { return App.Interfaces.remove('wall_contact'); })")
    command(app_page, "mesh")
    # The page refuses a size for a body it does not have with "unknown mesh body
    # key(s): ..." in the command log, and then never has a mesh: wait for either.
    app_page.wait_for_function(
        "App.Viewport.hasMesh() || document.querySelector('#cmd-log').innerText"
        ".includes('unknown mesh body')", timeout=LONG)
    assert "unknown mesh body" not in log_text(app_page)
    wait_meshed(app_page)

    project = app_page.request.get(live_server["url"] + "/api/project").json()
    assert project["anchors"] == [] and project["interfaces"] == []
    saved = tmp_path / "saved.json"
    saved.write_text(json.dumps(project, indent=2), encoding="utf-8")
    assert kratos_cli("check", saved) == 0
    assert kratos_cli("mesh", saved) == 0
    assert app_page.errors == []


def test_a_project_stays_meshable_after_mesh_properties_and_a_deleted_layer(
        app_page, live_server, tmp_path):
    """Its Apply leaves alone the sizes it shows no row for, and the mesh and the export
    name no layers, so a layer deleted later is not asked for and one added later is meshed."""
    project = excavation_project(staged=False)
    sizes = {"sheetpile": 0.5, "strut": 0.5, "soil_L_mid": 1.0}
    project = project.model_copy(update={"mesh": project.mesh.model_copy(
        update={"body_sizes": sizes})})
    assert app_page.request.put(live_server["url"] + "/api/project",
                                data=project.model_dump(mode="json")).ok
    app_page.reload()
    app_page.wait_for_function(
        f"App.PROJECT && App.PROJECT.name === '{project.name}' && App.LAYERS"
        " && App.LAYERS.length === 3", timeout=LONG)

    app_page.evaluate("App.MeshSettings.open()")
    app_page.locator("#mesh-settings-dialog").get_by_role(
        "button", name="Apply", exact=True).click()
    app_page.wait_for_selector("#mesh-settings-dialog", state="detached", timeout=LONG)
    saved = app_page.request.get(live_server["url"] + "/api/project").json()
    assert saved["mesh"]["body_sizes"] == sizes

    app_page.evaluate("""() => {
        var refused = App.deleteLayerById('L_mid');
        if (refused) throw new Error(refused);
        return App.commitSelectionEdit(null);
    }""")
    command(app_page, "mesh")
    app_page.wait_for_function(
        "App.Viewport.hasMesh() || document.querySelector('#cmd-log').innerText"
        ".includes('unknown mesh body')", timeout=LONG)
    assert "unknown mesh body" not in log_text(app_page)
    wait_meshed(app_page)

    project = app_page.request.get(live_server["url"] + "/api/project").json()
    assert project["mesh"]["body_sizes"] == {"sheetpile": 0.5, "strut": 0.5}
    saved = tmp_path / "saved.json"
    saved.write_text(json.dumps(project, indent=2), encoding="utf-8")
    assert kratos_cli("check", saved) == 0

    stack = [*project["layers"], {**project["layers"][-1], "id": "L_new", "name": "New",
                                  "top": project["layers"][-1]["bottom"],
                                  "bottom": project["layers"][-1]["bottom"] - 5}]
    app_page.evaluate("""stack => App.Api.patch('/api/project/layers', {layers: stack})
        .then(function (answer) { App.Model.apply(answer.project); })""", stack)
    assert app_page.evaluate("App.Export.meshRequest().volume_keys") is None
    assert app_page.evaluate("App.Viewport.meshSettings().volume_keys") is None
    assert app_page.errors == []


def test_mesh_properties_saves_what_it_shows(app_page, live_server):
    """A row with no size of its own follows the global size as it is typed; a size typed
    on a row is kept, also when it is the old global size. Every layer is meshed: the
    window has no check box to leave one out."""
    project = excavation_project(staged=False)
    assert project.mesh.element_size == 5.0
    assert app_page.request.put(live_server["url"] + "/api/project",
                                data=project.model_dump(mode="json")).ok
    app_page.reload()
    app_page.wait_for_function(
        f"App.PROJECT && App.PROJECT.name === '{project.name}' && App.LAYERS"
        " && App.LAYERS.length === 3", timeout=LONG)

    app_page.evaluate("App.MeshSettings.open()")
    window = app_page.locator("#mesh-settings-dialog")
    window.locator("[name=element_size]").fill("2.5")
    assert window.locator("[data-body-size-key=soil_L_mid]").input_value() == "2.5"
    window.locator("[data-body-size-key=soil_L_top]").fill("5")
    window.locator("[data-body-size-key=soil_L_bot]").fill("7")
    assert window.locator(".mesh-body-table input[type=checkbox]").count() == 0
    window.get_by_role("button", name="Apply", exact=True).click()
    app_page.wait_for_selector("#mesh-settings-dialog", state="detached", timeout=LONG)

    mesh = app_page.request.get(live_server["url"] + "/api/project").json()["mesh"]
    assert mesh["element_size"] == 2.5
    assert mesh["body_sizes"] == {**project.mesh.body_sizes, "soil_L_top": 5.0, "soil_L_bot": 7.0}
    assert app_page.evaluate("App.Export.meshRequest().volume_keys") is None
    assert app_page.errors == []


def test_a_project_made_on_the_command_line_opens_in_the_gui_and_saves_back(
        app_page, tmp_path):
    made = tmp_path / "pit.json"
    assert kratos_cli("new", made, "--demo", "--dim", "2", "--name", "Pit A") == 0

    with app_page.expect_file_chooser() as chooser:
        app_page.locator(TOOL.format("openProject")).click()
    chooser.value.set_files(str(made))
    # Open names the project after its file (`projectNameFromFile`).
    app_page.wait_for_function("App.PROJECT && App.PROJECT.name === 'pit'", timeout=LONG)

    # No save picker, so Save writes through App.Download.anchor; record what it writes.
    app_page.evaluate("""() => {
        window.showSaveFilePicker = undefined;
        window.savedText = null;
        App.Download.anchor = function (name, text) { window.savedText = text; };
    }""")
    app_page.locator(TOOL.format("saveProject")).click()
    app_page.wait_for_function("window.savedText !== null", timeout=LONG)
    text = app_page.evaluate("window.savedText")

    assert json.loads(text) == {**json.loads(made.read_text(encoding="utf-8")), "name": "pit"}
    saved = tmp_path / "saved.json"
    saved.write_text(text, encoding="utf-8")
    assert kratos_cli("check", saved) == 0
    assert kratos_cli("export", saved, "--out", tmp_path / "deck") == 0
    assert app_page.errors == []
