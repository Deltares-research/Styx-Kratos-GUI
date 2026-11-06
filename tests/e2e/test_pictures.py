"""Saving a picture on the real page, in a real browser.

Playwright cannot press a system window, so the windows answer with the browser's private
folder (`navigator.storage.getDirectory()`): a real handle, written to for real, and read
back here. `kratos-cli picture` runs for real too, with its own server and headless browser.

Opt-in: `--run-e2e`.
"""

from __future__ import annotations

import base64
import re
import struct
import xml.etree.ElementTree as ElementTree

import pytest

from cli.terminal import pictures
from cli.terminal.main import main
from core import session
from tests.e2e.conftest import command, log_text
from tests.e2e.test_flows import LONG, wait_meshed
from tests.models.excavation import excavation_project

CAMERA = '#maintoolbar .tbtn[data-action="savePicture"]'

PRIVATE_WINDOWS = """
async () => {
  const root = await navigator.storage.getDirectory();
  for await (const name of root.keys()) await root.removeEntry(name, { recursive: true });
  window.__picked = [];
  window.showSaveFilePicker = async (options) => {
    window.__picked.push({ kind: 'file', id: options.id, name: options.suggestedName });
    return root.getFileHandle(options.suggestedName, { create: true });
  };
  window.showDirectoryPicker = async (options) => {
    window.__picked.push({ kind: 'folder', id: options.id });
    return root;
  };
}"""

READ_FILES = """
async () => {
  const root = await navigator.storage.getDirectory();
  const out = {};
  for await (const [name, handle] of root.entries()) {
    const bytes = new Uint8Array(await (await handle.getFile()).arrayBuffer());
    let text = '';
    for (let i = 0; i < bytes.length; i += 32768) {
      text += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
    }
    out[name] = btoa(text);
  }
  return out;
}"""


def files_of(page) -> dict[str, bytes]:
    return {name: base64.b64decode(text) for name, text in page.evaluate(READ_FILES).items()}


def png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])


def png_dpi(data: bytes) -> float:
    at = data.index(b"pHYs")
    per_metre = struct.unpack(">I", data[at + 4:at + 8])[0]
    return per_metre * 0.0254


def wait_saved(page, pattern: str) -> None:
    page.wait_for_function("(p) => new RegExp(p).test(document.getElementById('cmd-log').innerText)",
                           arg=pattern, timeout=LONG)


@pytest.fixture
def excavation(app_page, live_server):
    """The staged test model on screen, with the save windows answering."""
    project = excavation_project()
    app_page.request.put(live_server["url"] + "/api/project",
                         data=project.model_dump_json(),
                         headers={"Content-Type": "application/json"})
    app_page.reload()
    app_page.wait_for_function("window.App && App.LivePatches && App.PROJECT && App.Viewport"
                               " && App.Viewport.getScene && App.Viewport.getScene()", timeout=60_000)
    app_page.wait_for_timeout(1500)
    app_page.evaluate(PRIVATE_WINDOWS)
    return app_page


def test_the_camera_opens_the_window_and_save_writes_a_300_dpi_png(excavation):
    page = excavation
    page.locator(CAMERA).click()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, r"Saved .*\.png")
    saved = files_of(page)
    assert len(saved) == 1
    data = next(iter(saved.values()))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert png_size(data)[0] == 1890, "16 cm at 300 dpi"
    assert round(png_dpi(data)) == 300
    assert page.evaluate("window.__picked")[0]["kind"] == "file"
    assert page.evaluate("window.__picked")[0]["id"] == "styx-pictures"
    assert page.errors == []


def test_more_than_one_format_goes_in_a_folder(excavation):
    page = excavation
    page.locator(CAMERA).click()
    page.locator('input[name="picture-format-pdf"]').check()
    page.locator('input[name="picture-format-svg"]').check()
    page.locator('input[name="picture-width"]').fill("10")
    assert "1181 px wide" in page.locator(".picture-form").inner_text()
    assert "3 files" in page.locator(".picture-note").inner_text()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, r"Saved 3 files")
    saved = files_of(page)
    assert sorted(name.rsplit(".", 1)[1] for name in saved) == ["pdf", "png", "svg"]
    assert page.evaluate("window.__picked")[0]["kind"] == "folder"

    by_kind = {name.rsplit(".", 1)[1]: data for name, data in saved.items()}
    assert png_size(by_kind["png"])[0] == 1181
    root = ElementTree.fromstring(by_kind["svg"].decode("utf-8"))
    assert root.get("width") == "100mm"
    assert by_kind["pdf"].startswith(b"%PDF-")
    assert b"/MediaBox [0 0 283.465" in by_kind["pdf"]
    start = int(re.search(rb"startxref\n(\d+)", by_kind["pdf"]).group(1))
    assert by_kind["pdf"][start:start + 4] == b"xref"


def test_the_box_says_the_same_as_the_window(excavation):
    page = excavation
    command(page, "picture save svg --width 12")
    wait_saved(page, r"Saved .*\.svg")
    data = next(iter(files_of(page).values()))
    assert ElementTree.fromstring(data.decode("utf-8")).get("width") == "120mm"


def test_a_bad_box_line_says_why(excavation):
    command(excavation, "picture save tiff")
    assert "tiff" in log_text(excavation)
    assert files_of(excavation) == {}


def test_right_click_copies_the_picture(excavation, context):
    page = excavation
    context.grant_permissions(["clipboard-read", "clipboard-write"])
    box = page.locator("#scene").bounding_box()
    page.mouse.click(box["x"] + 20, box["y"] + box["height"] - 20, button="right")
    page.locator("#menu-layer").get_by_text("Copy picture").click()
    wait_saved(page, r"Picture copied")
    answer = page.evaluate("""async () => {
      const items = await navigator.clipboard.read();
      const blob = await items[0].getType('image/png');
      const bitmap = await createImageBitmap(blob);
      return { types: items[0].types, width: bitmap.width };
    }""")
    assert answer == {"types": ["image/png"], "width": 1890}


def test_the_context_menu_opens_the_window_too(excavation):
    page = excavation
    box = page.locator("#scene").bounding_box()
    page.mouse.click(box["x"] + 20, box["y"] + box["height"] - 20, button="right")
    page.locator("#menu-layer").get_by_text("Save picture…").click()
    assert page.locator(".picture-form").is_visible()


def test_the_file_menu_has_it_too(excavation):
    page = excavation
    page.locator("#menubar").get_by_text("File", exact=True).click()
    page.locator("#menu-layer").get_by_text("Save picture…").click()
    assert page.locator(".picture-form").is_visible()


def test_every_stage_is_saved_with_its_own_parts_and_the_screen_comes_back(excavation):
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(1000)
    stages = page.evaluate("App.PROJECT.stages.map(s => s.id)")
    assert len(stages) > 1
    page.evaluate("(id) => { App.state.phase = id; App.Viewport.applyStageVisibility(); }", stages[1])
    keep = page.evaluate("App.state.phase")
    page.locator(CAMERA).click()
    page.locator('input[name="picture-scope"][value="stages"]').check()
    page.locator('input[name="picture-format-png"]').uncheck()
    page.locator('input[name="picture-format-svg"]').check()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, rf"Saved {len(stages)} files")

    saved = files_of(page)
    assert len(saved) == len(stages)
    assert page.evaluate("App.state.phase") == keep, "the stage on screen is the one left there"
    assert all(re.search(r"_stage\d+_", name) for name in saved)
    # A stage that switches a part on or off draws differently.
    assert len({data for data in saved.values()}) > 1
    names = page.evaluate("App.PROJECT.stages.map(s => s.name)")
    texts = [data.decode("utf-8") for data in saved.values()]
    assert any(f"Stage 1: {names[0]}" in text for text in texts), "each says which stage it is"


def test_the_server_writes_a_batch_in_the_folder_chosen_in_the_system_window(
        excavation, monkeypatch, tmp_path):
    """The way round a browser that refuses Downloads: no browser window at all."""
    from backend.routes import files as routes

    monkeypatch.setattr(routes, "choose_folder", lambda _start: str(tmp_path))
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(1000)
    stages = page.evaluate("App.PROJECT.stages.length")

    def save_every_stage():
        page.locator(CAMERA).click()
        page.locator('input[name="picture-scope"][value="stages"]').check()
        page.get_by_role("button", name="Save…").click()

    save_every_stage()
    wait_saved(page, rf"Saved {stages} files in ")

    assert page.evaluate("window.__picked") == [], "the browser's own window did not open"
    written = sorted(tmp_path.glob("*.png"))
    assert len(written) == stages
    assert len({png_size(path.read_bytes()) for path in written}) == 1, "one size for every stage"

    # A second time the files are there, and the user is asked.
    save_every_stage()
    page.get_by_role("button", name="Overwrite").click()
    wait_saved(page, rf"Saved {stages} files in [\s\S]*Saved {stages} files in ")
    assert page.errors == []


def test_a_picture_saved_alone_has_the_size_of_the_same_stage_in_a_batch(excavation):
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(1000)
    page.locator(CAMERA).click()
    page.locator('input[name="picture-scope"][value="stages"]').check()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, r"Saved \d+ files")
    sizes = {png_size(data) for data in files_of(page).values()}
    assert len(sizes) == 1

    page.evaluate(PRIVATE_WINDOWS)
    page.locator(CAMERA).click()
    page.locator('input[name="picture-scope"][value="view"]').check()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, r"Saved [^ ]*\.png")
    assert {png_size(data) for data in files_of(page).values()} == sizes


def test_every_stage_of_the_results_has_one_size(excavation):
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(500)
    page.evaluate("App.runAction({ action: 'calculate' })")
    page.wait_for_function("App.state.mode === 'results' && App.Results.field()", timeout=LONG)
    page.wait_for_timeout(1000)
    keep = page.evaluate("[App.Results.stage(), App.Results.field().field]")

    page.locator(CAMERA).click()
    page.locator('input[name="picture-scope"][value="stages"]').check()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, r"Saved \d+ files")
    sizes = {png_size(data) for data in files_of(page).values()}
    assert len(sizes) == 1

    # A picture on its own goes through the stages for its frame, and puts the screen back.
    page.evaluate(PRIVATE_WINDOWS)
    page.locator(CAMERA).click()
    page.locator('input[name="picture-scope"][value="view"]').check()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, r"Saved [^ ]*\.png")
    assert {png_size(data) for data in files_of(page).values()} == sizes
    assert page.evaluate("[App.Results.stage(), App.Results.field().field]") == keep
    assert page.errors == []


def test_a_results_batch_saves_each_field_and_stage_with_csv(excavation, live_server):
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(500)
    page.evaluate("App.runAction({ action: 'calculate' })")
    page.wait_for_function("App.state.mode === 'results' && App.Results.field()", timeout=LONG)
    page.wait_for_timeout(1000)
    keep = page.evaluate("[App.Results.stage(), App.Results.field().field]")
    stages = page.evaluate("App.Picture.resultStages().length")

    page.locator(CAMERA).click()
    page.locator('input[name="picture-scope"][value="stages"]').check()
    page.locator('input[name="picture-format-png"]').uncheck()
    page.locator('input[name="picture-format-svg"]').check()
    page.locator('input[name="picture-csv"]').check()
    page.get_by_role("button", name="Save…").click()
    wait_saved(page, rf"Saved {stages * 2} files")

    saved = files_of(page)
    svgs = [name for name in saved if name.endswith(".svg")]
    csvs = [name for name in saved if name.endswith(".csv")]
    assert len(svgs) == stages and len(csvs) == stages
    assert page.evaluate("[App.Results.stage(), App.Results.field().field]") == keep
    assert all(name.endswith(f"_{keep[1]}.svg") for name in svgs)
    one = saved[svgs[0]].decode("utf-8")
    assert "data:image/png;base64," in one, "the contour is an image"
    assert ">Stage " in one, "the stage's number and name are in the title"
    assert ">Maximum value = " in one and ">Minimum value = " in one, "and the field's range below"
    assert page.errors == []


def test_saves_of_a_run_ask_where_they_go(excavation):
    """`results zip` and `results csv` used to land in Downloads with no choice."""
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(500)
    page.evaluate("App.runAction({ action: 'calculate' })")
    page.wait_for_function("App.state.mode === 'results' && App.Results.field()", timeout=LONG)
    command(page, "results zip")
    wait_saved(page, r"Downloading .*\.zip")
    command(page, "results csv")
    wait_saved(page, r"Saved .*\.csv")
    saved = files_of(page)
    assert next(data for name, data in saved.items() if name.endswith(".zip"))[:2] == b"PK"
    assert b"," in next(data for name, data in saved.items() if name.endswith(".csv"))
    assert [entry["kind"] for entry in page.evaluate("window.__picked")] == ["file", "file"]


def test_a_stop_ends_the_batch_and_says_so(excavation):
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(500)
    # Stops as soon as the loop shows its button.
    page.evaluate("""() => {
      const box = document.querySelector('.vp-loading-box');
      new MutationObserver((_, watcher) => {
        const stop = box.querySelector('.picture-stop');
        if (stop) { watcher.disconnect(); stop.click(); }
      }).observe(box, { childList: true });
    }""")
    command(page, "picture save png --stage all")
    wait_saved(page, r"Stopped after \d+ file")
    assert len(files_of(page)) < page.evaluate("App.PROJECT.stages.length")
    assert page.locator("#vp-loading").is_hidden()


def test_the_rulers_and_the_mesh_are_in_the_file(excavation):
    page = excavation
    page.evaluate("App.runAction({ action: 'generateMesh' })")
    wait_meshed(page)
    command(page, "picture save svg")
    wait_saved(page, r"Saved .*\.svg")
    text = next(iter(files_of(page).values())).decode("utf-8")
    assert "<text" in text
    assert text.count("<path") > 5


def test_the_plot_window_saves_a_png_and_a_pdf(excavation):
    page = excavation
    command(page, "gotostaged")
    page.wait_for_timeout(500)
    page.evaluate("App.runAction({ action: 'calculate' })")
    page.wait_for_function("App.state.mode === 'results' && App.Results.field()", timeout=LONG)
    command(page, "results plot")
    page.get_by_role("button", name="Save PNG").click()
    wait_saved(page, r"Saved .*\.png")
    page.get_by_role("button", name="Save PDF").click()
    wait_saved(page, r"Saved .*\.pdf")
    saved = files_of(page)
    png = next(data for name, data in saved.items() if name.endswith(".png"))
    assert round(png_dpi(png)) == 300
    assert next(data for name, data in saved.items() if name.endswith(".pdf")).startswith(b"%PDF-")


@pytest.mark.skipif(pictures.find_browser() is None, reason="no Chrome or Edge on this machine")
def test_the_command_line_draws_the_same_picture_as_the_page(excavation, live_server, tmp_path):
    """The real thing: its own server, a headless browser, the receiver."""
    model = tmp_path / "pit.json"
    session.save(excavation_project(), model)
    out = tmp_path / "out"
    assert main(["picture", "stage", str(model), "--format", "png,svg,pdf", "--stage", "1",
                 "--out", str(out) + "/"]) == 0
    names = sorted(path.name for path in out.iterdir())
    assert len(names) == 3
    assert {name.rsplit(".", 1)[1] for name in names} == {"png", "svg", "pdf"}
    png = next(out.glob("*.png")).read_bytes()
    assert png_size(png)[0] == 1890
    assert round(png_dpi(png)) == 300
