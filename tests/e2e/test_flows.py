"""The user flows every user takes, through the real page (plan sec 6.3).

Each starts from a reset project, drives the page through what a user touches -- the
command box, the toolbar, the windows, the keyboard -- and asserts on what the page
then shows, and on what the server then holds. Opt-in: `--run-e2e`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import test_soil_lines as soil_lines
from tests.e2e.conftest import command, log_text

LONG = 120_000
MODEL_NAME = "Staged excavation"


def wait_meshed(page):
    page.wait_for_function("App.Viewport.hasMesh && App.Viewport.hasMesh()", timeout=LONG)


def run_model(page):
    """Open the test model the way a user opens a model script."""
    command(page, "run tests/models/excavation.py")
    page.wait_for_function(f"App.PROJECT && App.PROJECT.name === '{MODEL_NAME}'",
                           timeout=LONG)
    wait_meshed(page)


def deck_case(directory: Path) -> Path:
    """A two-stage Kratos deck and the script that opens it (`tests/test_deck.py`'s
    stand-in for a real deck case), written into `directory`. Returns the script."""
    import json

    from tests.test_deck import MDPA, PARAMETERS

    deck = directory / "deck_case"
    deck.mkdir()
    (deck / "dike.mdpa").write_text(MDPA, encoding="utf-8")
    (deck / "dike.json").write_text(json.dumps(PARAMETERS, indent=2), encoding="utf-8")
    (deck / "materials_a.json").write_text('{"properties": []}', encoding="utf-8")
    (deck / "materials_b.json").write_text('{"properties": [1]}', encoding="utf-8")
    script = directory / "deck_case.py"
    script.write_text("from core.kratos.external_deck import deck_project\n\n\n"
                      "def dike_project():\n"
                      f"    return deck_project({deck.as_posix()!r}, 'dike.json', name='Dike')\n",
                      encoding="utf-8")
    return script


def calculate(page):
    page.locator('#maintoolbar .tbtn[data-action="calculate"]').click()
    page.wait_for_function("App.Results && App.Results.current() && App.state.mode === 'results'"
                           " && App.Results.stage()", timeout=LONG)


def test_the_page_boots_cleanly_with_the_live_layer_installed(app_page):
    assert app_page.errors == []
    command(app_page, "results")
    assert "Unknown command" not in log_text(app_page)
    assert "results runs" in log_text(app_page), "the live interpreter answered"


def test_a_model_runs_from_its_script_to_results_and_downloads(app_page):
    run_model(app_page)
    calculate(app_page)
    window = app_page.locator(".dlg-results")
    window.wait_for(state="visible")
    stage = window.locator('select[data-res="stage"]')
    stage.select_option("1")
    app_page.wait_for_function("App.Results.stage() === 1", timeout=LONG)
    with app_page.expect_download() as download:
        window.get_by_role("button", name="Download run").click()
    assert download.value.suggested_filename.endswith(".zip")
    assert app_page.errors == []


def test_rapid_stage_switching_with_deformation_ends_on_the_last_stage(app_page):
    """Finding F7 in the real page: replies arriving out of order must not leave a
    stage drawn under another's label."""
    run_model(app_page)
    calculate(app_page)
    command(app_page, "results deform 10")
    app_page.evaluate("() => { App.Command.run('results stage 2');"
                      " App.Command.run('results stage 5');"
                      " App.Command.run('results stage 3'); }")
    app_page.wait_for_function("App.Results.stage() === 3", timeout=LONG)
    app_page.wait_for_timeout(1500)
    assert app_page.evaluate("App.Results.stage()") == 3
    legend = app_page.locator("#vp-legend .vp-legend-foot")
    assert legend.inner_text().strip() == "stage 3"
    assert app_page.errors == []


def test_a_part_a_stage_uses_cannot_be_deleted_and_editing_goes_on(app_page):
    """Finding F3 in the real page."""
    run_model(app_page)
    key = app_page.evaluate("""async () => {
        const r = await fetch('/api/geometry/create', {method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({kind: 'box', origin: [30, -4, 15], size: [2, 2, 2],
                                label: 'Block'})});
        return (await r.json()).parts[0].key; }""")
    app_page.evaluate(f"""async () => {{
        const stages = App.PROJECT.stages.slice();
        stages[stages.length - 1] = Object.assign({{}}, stages[stages.length - 1],
          {{deactivate: (stages[stages.length - 1].deactivate || []).concat(['{key}'])}});
        await App.Api.patch('/api/project/stages', {{stages: stages}});
        await App.Model.load(); }}""")
    command(app_page, "cleargeometry")
    app_page.wait_for_function("document.querySelector('#cmd-log').innerText"
                               ".includes('still uses')", timeout=LONG)
    project = app_page.request.get(app_page.url + "api/project").json()
    assert key in [p["key"] for p in project["custom_parts"]]
    patched = app_page.request.patch(app_page.url + "api/project/layers",
                                     data={"layers": project["layers"]})
    assert patched.status == 200, "the project is still editable"


def test_switching_to_3d_and_undoing_restores_the_project(app_page):
    run_model(app_page)
    before = app_page.request.get(app_page.url + "api/project").json()
    app_page.locator('#maintoolbar .tbtn[data-action="viewMode3D"]').click()
    app_page.wait_for_function("App.PROJECT.dimension === 3", timeout=LONG)
    app_page.locator("#viewport canvas#scene").click(position={"x": 5, "y": 5})
    app_page.keyboard.press("Control+z")
    app_page.wait_for_function("App.PROJECT.dimension === 2", timeout=LONG)
    after = app_page.request.get(app_page.url + "api/project").json()
    for key in ("beams", "loads", "anchors", "interfaces", "layers", "stages"):
        assert after[key] == before[key], key


def test_a_reload_keeps_the_open_project(app_page):
    run_model(app_page)
    app_page.reload()
    app_page.wait_for_function("window.App && App.PROJECT", timeout=LONG)
    assert app_page.evaluate("App.PROJECT.name") == MODEL_NAME


@pytest.mark.xfail(strict=True, reason=(
    "known gap (session notes 2026-10-09): reloading the browser loses a deck's mesh "
    "preview until `run` is typed again"))
def test_a_reload_keeps_a_deck_preview(app_page, tmp_path):
    command(app_page, f"run {deck_case(tmp_path).as_posix()}")
    app_page.wait_for_function("App.Viewport.hasImportedMesh()", timeout=LONG)
    app_page.reload()
    app_page.wait_for_function("window.App && App.PROJECT", timeout=LONG)
    app_page.wait_for_function("App.Viewport.hasImportedMesh()", timeout=10_000)


def test_a_deck_case_opens_with_its_own_mesh_and_parts(app_page, tmp_path):
    from tests.test_deck import PARAMETERS

    command(app_page, f"run {deck_case(tmp_path).as_posix()}")
    app_page.wait_for_function("App.Viewport.hasImportedMesh()", timeout=LONG)
    assert app_page.evaluate("App.state.mode") == "mesh"
    assert app_page.locator("#tree-model").get_by_text("Imported mesh").count() >= 1
    stages = PARAMETERS["orchestrator"]["settings"]["execution_list"]
    assert app_page.evaluate("App.PROJECT.stages.length") == len(stages)


def test_a_model_built_by_hand_from_a_new_project_meshes(app_page):
    """New project from the toolbar, a soil layer added in the soil-layers dialog, then
    meshed from the command line -- no script anywhere."""
    app_page.locator('#maintoolbar .tbtn[data-action="newProject"]').click()
    confirm = app_page.locator("#modal-layer .dialog").filter(has_text="New project")
    confirm.get_by_role("button", name="OK").click()
    app_page.wait_for_function("App.PROJECT && App.PROJECT.layers.length === 0", timeout=LONG)

    command(app_page, "soillayers")
    dialog = app_page.locator("#modal-layer .dialog").filter(has_text="soil layers").first
    dialog.wait_for(state="visible")
    dialog.locator(".lay-toolbar button", has_text="Add").first.click()
    # The window edits a copy of the stack: the new layer is a row until OK.
    dialog.locator(".lay-table-wrap tbody tr").first.wait_for(state="visible")
    dialog.locator(".dlg-foot .btn-primary").click()
    app_page.wait_for_function("App.PROJECT.layers.length === 1", timeout=LONG)

    command(app_page, "mesh")
    wait_meshed(app_page)
    project = app_page.request.get(app_page.url + "api/project").json()
    assert len(project["layers"]) == 1 and len(project["materials"]) >= 1
    assert app_page.errors == []


# ── Kratos property sets and the project's unit system ──────────────────────
# A soil is what Kratos reads, in the project's units (plan/outdated/kratos-native-inputs-plan.md):
# the Material sets window edits exactly that and saves it, and `units` converts the
# whole project, with the status bar saying which system it is in.

def test_a_soil_is_edited_as_kratos_reads_it_and_saved(app_page, live_server):
    run_model(app_page)
    app_page.evaluate("App.Dialogs.materials()")
    window = app_page.locator("#modal-layer .dialog").last
    window.locator('[data-action="material-properties"]').first.click()
    modulus = app_page.locator('.material-variables [data-variable="YOUNG_MODULUS"]')
    assert modulus.input_value() == "2e6", "the test model's own 2e6 Pa, as typed"
    modulus.fill("2500000")
    modulus.press("Enter")
    app_page.locator("#modal-layer .dialog").last.get_by_role("button", name="Close").click()
    app_page.locator("#modal-layer .dialog").last.get_by_role("button", name="OK").click()
    app_page.wait_for_function(
        "App.PROJECT.materials[0].variables.YOUNG_MODULUS === 2500000", timeout=LONG)
    stored = app_page.request.get(live_server["url"] + "/api/project").json()
    assert stored["materials"][0]["variables"]["YOUNG_MODULUS"] == 2500000
    assert app_page.errors == []


def test_the_units_command_converts_the_project_and_the_status_bar_follows(app_page, live_server):
    run_model(app_page)
    assert "SI" in app_page.locator("#sb-units").inner_text()
    command(app_page, "units kN")
    app_page.wait_for_function("App.PROJECT.unit_system === 'kN'", timeout=LONG)
    assert "kN" in app_page.locator("#sb-units").inner_text()
    stored = app_page.request.get(live_server["url"] + "/api/project").json()
    assert stored["unit_system"] == "kN"
    assert stored["materials"][0]["variables"]["YOUNG_MODULUS"] == pytest.approx(2000.0)
    assert stored["loads"][0]["components"][1] == pytest.approx(-10.0)
    command(app_page, "units")
    assert "kN, m, t, s" in log_text(app_page)
    assert app_page.errors == []


def test_the_boundary_conditions_are_set_in_their_window_and_by_command(app_page, live_server):
    """The standard supports a new project has, the dialog's whole-soil row given a dry
    pore pressure, and gravity switched off from the command box: each one write the
    server stores."""
    url = live_server["url"] + "/api/project"
    command(app_page, "boundary list")
    app_page.wait_for_function("document.querySelector('#cmd-log').innerText"
                               ".indexOf('fixed_bottom') >= 0", timeout=LONG)

    app_page.evaluate("App.runAction({action: 'boundaryConditions'})")
    rows = app_page.locator(".boundary-conditions table.bc-grid tr")
    soil = rows.last
    soil.locator("select.bc-water").select_option("Uniform")
    soil.locator("input.bc-number").fill("0")
    app_page.get_by_role("button", name="Save").click()
    app_page.wait_for_function("(App.PROJECT.boundary_conditions || []).some(function (c) {"
                               " return c.kind === 'water_pressure' && c.on === 'domain'; })",
                               timeout=LONG)
    stored = app_page.request.get(url).json()
    water = [c for c in stored["boundary_conditions"] if c["kind"] == "water_pressure"]
    assert [(c["on"], c["fluid_pressure_type"], c["value"]) for c in water] == [
        ("domain", "Uniform", 0.0)]
    assert sum(c["kind"] == "displacement" for c in stored["boundary_conditions"]) == 5

    command(app_page, "gravity off")
    app_page.wait_for_function("App.PROJECT.gravity === false", timeout=LONG)
    assert app_page.request.get(url).json()["gravity"] is False
    assert app_page.errors == []


def test_a_line_drawn_in_the_section_splits_the_soil(app_page, live_server):
    """The Create line tool: two clicks, Enter, the exact points typed in its window, Save.
    The layer it crosses is two soil parts then, each with its own row, and the Delete
    joins them again."""
    url = live_server["url"] + "/api/project"
    answer = app_page.request.put(url, data=soil_lines.model().model_dump_json(),
                                  headers={"Content-Type": "application/json"})
    assert answer.status == 200
    app_page.evaluate("App.Viewport.refresh()")
    app_page.wait_for_function("(App.PROJECT.soil_body_keys || []).length === 2", timeout=LONG)

    app_page.evaluate("App.setMode('structures'); App.runAction({action: 'drawLine'})")
    box = app_page.locator("canvas").first.bounding_box()
    for across in (0.4, 0.6):
        app_page.mouse.click(box["x"] + box["width"] * across, box["y"] + box["height"] / 2)
    app_page.keyboard.press("Enter")

    rows = app_page.locator(".dialog .line-point")
    rows.first.wait_for(state="visible")
    for row, (x, y) in zip((rows.nth(0), rows.nth(1)), ((5, 0), (5, -4))):
        row.locator("input").nth(0).fill(str(x))
        row.locator("input").nth(1).fill(str(y))
    app_page.locator(".dialog button", has_text="Save").click()

    app_page.wait_for_function("(App.PROJECT.soil_body_keys || []).length === 3", timeout=LONG)
    stored = app_page.request.get(url).json()
    assert stored["soil_body_keys"] == ["soil_top__part1", "soil_top__part2", "soil_low"]
    assert stored["lines"][0]["points"] == [[5.0, 0.0], [5.0, -4.0]]
    tree = app_page.locator("#tree-model")
    tree.get_by_text("Top · Part 2").wait_for(state="visible")
    tree.get_by_text("Line 1").wait_for(state="visible")

    app_page.evaluate("App.Lines.remove('line_1')")
    app_page.wait_for_function("(App.PROJECT.soil_body_keys || []).length === 2", timeout=LONG)
    assert app_page.errors == []


def open_project(page, url: str, project) -> None:
    """`project` on the server and in the page, with no step to undo yet."""
    answer = page.request.put(url + "/api/project", data=project.model_dump_json(),
                              headers={"Content-Type": "application/json"})
    assert answer.status == 200
    page.evaluate("App.Viewport.refresh()")
    page.wait_for_function("keys => JSON.stringify(App.PROJECT.soil_body_keys || [])"
                           " === JSON.stringify(keys)", arg=project.soil_body_keys, timeout=LONG)
    page.evaluate("App.History.reset()")


def tree_row(page, label: str):
    """The Model explorer's row whose text starts with `label`."""
    return page.locator("#tree-model .tree-row").filter(
        has=page.locator(".tree-label", has_text=label)).first


def tree_label(page, label: str) -> str:
    return tree_row(page, label).locator(".tree-label").inner_text()


def wait_tree_label(page, text: str) -> None:
    """The Model explorer is built again once the viewport has redrawn the change."""
    page.locator("#tree-model .tree-label", has_text=text).first.wait_for(state="visible")


def panel_button(page, text: str):
    return page.locator("#grid-selection button", has_text=text)


def rename_body(page, row: str, name: str) -> None:
    """Select the body's row and rename it with the button in its panel: the first one, as
    the second renames its layer."""
    tree_row(page, row).click()
    panel_button(page, "Rename…").first.click()
    window = page.locator("#modal-layer .name-dialog-window")
    window.locator("input[name=name]").fill(name)
    window.get_by_role("button", name="OK").click()
    window.wait_for(state="detached")


def press(page, keys: str) -> None:
    """A shortcut, with the focus on the model rather than in a box."""
    page.locator("#viewport canvas#scene").click(position={"x": 5, "y": 5})
    page.keyboard.press(keys)


def test_a_soil_part_is_renamed_in_its_panel(app_page, live_server):
    """The row, the label the project publishes and the deck's part all take the new name;
    the key stays, so the stages that name it still do."""
    url = live_server["url"]
    open_project(app_page, url, soil_lines.model(lines=[soil_lines.PIT_SIDE]))
    keys = app_page.evaluate("App.PROJECT.soil_body_keys")

    rename_body(app_page, "Top · Part 1", "Pit")

    app_page.wait_for_function(
        "App.PROJECT.soil_body_labels.soil_top__part1 === 'Pit'", timeout=LONG)
    tree_row(app_page, "Pit").wait_for(state="visible")
    app_page.wait_for_function(
        "document.querySelector('#grid-selection .pgrid-header').innerText.trim() === 'Pit'",
        timeout=LONG)
    stored = app_page.request.get(url + "/api/project").json()
    assert stored["soil_body_keys"] == keys
    assert stored["soil_body_labels"]["soil_top__part1"] == "Pit"
    mdpa = app_page.request.post(url + "/api/export/mdpa", data={}).json()["mdpa"]
    assert "Begin SubModelPart Top_Pit" in mdpa.splitlines()
    assert "Top_Part_1" not in mdpa
    assert app_page.errors == []


def test_a_soil_layer_is_renamed_from_the_model_explorer_menu(app_page, live_server):
    """Right-click, Rename…: the app's Rename window, not the browser's prompt."""
    url = live_server["url"]
    layer = app_page.evaluate("App.LAYERS[0]")
    key = "soil_" + layer["id"]
    row = app_page.locator(f'#tree-model .tree-row[data-obj="{key}"]')
    row.click(button="right")
    app_page.locator(".menu .menu-item", has_text="Rename…").click()
    window = app_page.locator("#modal-layer .name-dialog-window")
    assert window.locator("input[name=name]").input_value() == layer["name"]
    window.locator("input[name=name]").fill("Clay top")
    window.get_by_role("button", name="OK").click()
    window.wait_for(state="detached")

    app_page.wait_for_function("App.LAYERS[0].name === 'Clay top'", timeout=LONG)
    stored = app_page.request.get(url + "/api/project").json()
    assert stored["layers"][0]["name"] == "Clay top"
    assert app_page.errors == []


def test_a_soil_part_takes_its_own_material_and_gives_it_back(app_page, live_server):
    url = live_server["url"]
    open_project(app_page, url, soil_lines.model(lines=[soil_lines.PIT_SIDE]))
    tree_row(app_page, "Top · Part 1").click()
    material = app_page.locator("#grid-selection .pgrid-row", has_text="Material")
    assert material.locator("option").all_inner_texts() == [
        m["name"] for m in app_page.evaluate("App.MATERIALS")]
    assert material.locator("select").input_value() == "sand"

    material.locator("select").select_option("grout")

    app_page.wait_for_function(
        "App.PROJECT.soil_body_materials.soil_top__part1 === 'grout'", timeout=LONG)
    wait_tree_label(app_page, "Soil grout")
    assert tree_label(app_page, "Top · Part 1").endswith("Soil grout")
    assert tree_label(app_page, "Top · Part 2").endswith("Soil sand")
    stored = app_page.request.get(url + "/api/project").json()
    assert stored["soil_body_materials"]["soil_top__part1"] == "grout"

    material.locator("select").select_option("sand")

    app_page.wait_for_function(
        "App.PROJECT.soil_body_materials.soil_top__part1 === 'sand'", timeout=LONG)
    app_page.locator("#tree-model .tree-label", has_text="Soil grout").wait_for(
        state="detached")
    assert tree_label(app_page, "Top · Part 1").endswith("Soil sand")
    stored = app_page.request.get(url + "/api/project").json()
    assert [body["mat"] for body in stored["bodies"]] == ["sand", "sand"]
    assert app_page.errors == []


def soil_span(page, key: str) -> list[float]:
    """Where the viewport draws a soil part, from left to right."""
    return page.evaluate("""key => {
        const box = App.Viewport.boundsOf(App.Viewport.getScene().getObjectByName(key));
        return [Math.round(box.min.x * 100) / 100, Math.round(box.max.x * 100) / 100]; }""",
                         key)


def test_a_line_opened_from_its_row_is_moved_and_the_parts_follow(app_page, live_server):
    url = live_server["url"]
    open_project(app_page, url, soil_lines.model(lines=[soil_lines.PIT_SIDE]))
    keys = app_page.evaluate("App.PROJECT.soil_body_keys")
    assert soil_span(app_page, "soil_top__part1") == [0, 5]
    assert soil_span(app_page, "soil_top__part2") == [5, 20]

    tree_row(app_page, "Pit side").click()
    panel_button(app_page, "Edit line…").click()
    top = app_page.locator(".dialog .line-point").first
    top.locator("input").nth(0).fill("8")
    app_page.locator(".dialog button", has_text="Save").click()

    app_page.wait_for_function("App.PROJECT.lines[0].points[0][0] === 8", timeout=LONG)
    app_page.wait_for_function("!document.querySelector('.dialog .line-point')", timeout=LONG)
    stored = app_page.request.get(url + "/api/project").json()
    assert stored["lines"][0]["points"] == [[8.0, 0.0], [5.0, -4.0]]
    assert stored["soil_body_keys"] == keys
    assert soil_span(app_page, "soil_top__part1") == [0, 8]
    assert soil_span(app_page, "soil_top__part2") == [5, 20]
    assert app_page.errors == []


def test_a_saved_line_and_a_renamed_part_are_undone_and_redone(app_page, live_server):
    url = live_server["url"]
    open_project(app_page, url, soil_lines.model())
    app_page.evaluate("App.setMode('structures');"
                      " App.runAction({action: 'createLineByCoordinates'})")
    rows = app_page.locator(".dialog .line-point")
    rows.first.wait_for(state="visible")
    for row, (x, y) in zip((rows.nth(0), rows.nth(1)), ((5, 0), (5, -4))):
        row.locator("input").nth(0).fill(str(x))
        row.locator("input").nth(1).fill(str(y))
    app_page.locator(".dialog button", has_text="Save").click()
    app_page.wait_for_function("App.PROJECT.soil_body_keys.length === 3", timeout=LONG)
    keys = app_page.evaluate("App.PROJECT.soil_body_keys")

    press(app_page, "Control+z")
    app_page.wait_for_function("App.PROJECT.soil_body_keys.length === 2", timeout=LONG)
    stored = app_page.request.get(url + "/api/project").json()
    assert stored.get("lines", []) == [] and stored["soil_body_keys"] == ["soil_top", "soil_low"]
    tree_row(app_page, "Line 1").wait_for(state="detached")

    press(app_page, "Control+y")
    app_page.wait_for_function("App.PROJECT.soil_body_keys.length === 3", timeout=LONG)
    assert app_page.request.get(url + "/api/project").json()["soil_body_keys"] == keys
    tree_row(app_page, "Line 1").wait_for(state="visible")

    rename_body(app_page, "Top · Part 1", "Pit")
    app_page.wait_for_function(
        "App.PROJECT.soil_body_labels.soil_top__part1 === 'Pit'", timeout=LONG)

    press(app_page, "Control+z")
    app_page.wait_for_function(
        "App.PROJECT.soil_body_labels.soil_top__part1 === 'Top · Part 1'", timeout=LONG)
    tree_row(app_page, "Top · Part 1").wait_for(state="visible")

    press(app_page, "Control+y")
    app_page.wait_for_function(
        "App.PROJECT.soil_body_labels.soil_top__part1 === 'Pit'", timeout=LONG)
    stored = app_page.request.get(url + "/api/project").json()
    assert stored["soil_body_keys"] == keys
    assert stored["soil_body_labels"]["soil_top__part1"] == "Pit"
    assert app_page.errors == []


def test_a_line_a_stage_needs_is_not_deleted_and_the_log_says_why(app_page, live_server,
                                                                   tmp_path, capsys):
    """The Session log gives the reason `kratos-cli line remove` gives for the same edit."""
    from cli.terminal.main import main
    from core import session
    from core.model.schemas import Stage

    url = live_server["url"]
    project = soil_lines.model(lines=[soil_lines.PIT_SIDE], stages=[
        Stage(id="dig", name="Dig", deactivate=["soil_top__part1"])])
    open_project(app_page, url, project)
    before = app_page.request.get(url + "/api/project").json()

    tree_row(app_page, "Pit side").click()
    panel_button(app_page, "Delete line").click()

    app_page.wait_for_function("document.querySelector('#cmd-log').innerText"
                               ".includes('Could not save the line')", timeout=LONG)
    assert app_page.request.get(url + "/api/project").json() == before
    tree_row(app_page, "Pit side").wait_for(state="visible")
    assert app_page.evaluate("App.PROJECT.lines.length") == 1

    capsys.readouterr()
    assert main(["line", str(session.save(project, tmp_path / "pit.json")), "remove",
                 "pit_side"]) == 1
    reason = capsys.readouterr().err.split("the project: ", 1)[1].strip()
    assert reason == "Value error, stage 'dig' names no such part: soil_top__part1"
    assert f"Could not save the line: {reason}" in log_text(app_page)
    # The browser itself notes the refused request; the page adds nothing to it. What
    # follows the 422 is the server's wording, which differs per Python version.
    assert len(app_page.errors) == 1
    assert app_page.errors[0].startswith(
        "Failed to load resource: the server responded with a status of 422")
