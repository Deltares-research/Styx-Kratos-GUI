"""The user flows every user takes, through the real page (plan sec 6.3).

Each starts from a reset project, drives the page through what a user touches -- the
command box, the toolbar, the windows, the keyboard -- and asserts on what the page
then shows, and on what the server then holds. Opt-in: `--run-e2e`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    app_page.wait_for_function("App.LAYERS.length === 1", timeout=LONG)
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
    assert modulus.input_value() == "2000000", "the test model's own 2e6 Pa, as typed"
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
