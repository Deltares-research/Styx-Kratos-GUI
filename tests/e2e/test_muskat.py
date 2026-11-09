"""The Muskat column built in the GUI, through its windows, and calculated from the
toolbar. Opt-in: `--run-e2e`; with `--run-kratos` too, Kratos itself calculates.

Each test opens the column with its soil, mesh and stage (a model script, as a user runs
one) and gives it its water in the GUI: the heads and the tail water in the Boundary
conditions windows, the seepage face in Create boundary condition, and the calculation
type in the Stages window. The deck the GUI then exports is the deck of
`tests/models/muskat.py`, less the names (`tests/muskat_reference.deck_view`), which is
held to Kratos' own `tests/Muskat` elsewhere. With Kratos, the run gives the answer:
case A Kratos' own values at its nodes, case C the water balance and the exit point of
the seepage face.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.geometry import solid_model
from core.kratos import writer
from core.results import catalog
from tests import muskat_reference as reference
from tests.e2e.conftest import command
from tests.models import muskat

LONG = 120_000

COLUMN = '''from core.model.schemas import Stage
from tests.models import muskat


def project():
    """{doc}"""
    model = {model}
    return model.model_copy(update={{
        "boundary_conditions": [c for c in model.boundary_conditions if c.id in {keep!r}],
        "stages": [stage.model_copy(update={{"calculation": "mechanical"}})
                   for stage in model.stages]}})
'''
"""A model script: `model` with only the conditions in `keep`, and its stage not yet a
groundwater flow stage."""


def open_column(page, directory: Path, name: str, model: str, keep: tuple, doc: str):
    script = directory / f"{name}.py"
    script.write_text(COLUMN.format(model=model, keep=keep, doc=doc), encoding="utf-8")
    command(page, f"run {script.as_posix()}")
    page.wait_for_function("App.PROJECT && App.PROJECT.stages.length === 1"
                           " && App.PROJECT.stages[0].calculation === 'mechanical'",
                           timeout=LONG)


def window(page):
    return page.locator("#modal-layer .dialog").last


def field(page, label: str):
    """The control of a row of the condition window."""
    return window(page).locator(
        f"xpath=.//label[normalize-space()='{label}']/following-sibling::*[1]")


def conditions(page) -> int:
    return page.evaluate("(App.PROJECT.boundary_conditions || []).length")


def save_condition(page, count: int):
    window(page).get_by_role("button", name="Save").click()
    page.wait_for_function(f"(App.PROJECT.boundary_conditions || []).length === {count}",
                           timeout=LONG)


def head_on_face(page, face: str, name: str, level: float):
    """A fixed hydrostatic head on `face`: More… on its row of the Boundary conditions
    window, then the condition's own window."""
    count = conditions(page)
    page.evaluate("App.runAction({action: 'boundaryConditions'})")
    row = page.locator(".boundary-conditions table.bc-grid tr").filter(
        has=page.locator("td:first-child", has_text=face))
    row.get_by_role("button", name="More…").click()
    field(page, "Name").fill(name)
    field(page, "Type").select_option("Hydrostatic")
    field(page, "Reference level").fill(str(level))
    field(page, "Tension cut-off").fill("100000")
    save_condition(page, count + 1)


def on_a_line(page, kind: str, name: str, points: str, **water):
    """A condition on a line: Add condition… in the Boundary conditions window."""
    count = conditions(page)
    page.evaluate("App.runAction({action: 'boundaryConditions'})")
    window(page).get_by_role("button", name="Add condition…").click()
    field(page, "Condition").select_option(kind)
    field(page, "Where").select_option("line")
    field(page, "Name").fill(name)
    field(page, "Points").fill(points)
    if water:
        field(page, "Type").select_option("Hydrostatic")
        field(page, "Reference level").fill(str(water["level"]))
        field(page, "Tension cut-off").fill("100000")
    save_condition(page, count + 1)


def groundwater_flow(page):
    """The stage's calculation type, in the Stages window."""
    command(page, "stages")
    row = window(page).locator(".stages-overview .pgrid-row", has_text="Calculation type")
    row.locator("select").select_option("flow")
    page.wait_for_function("App.PROJECT.stages[0].calculation === 'flow'", timeout=LONG)
    window(page).get_by_role("button", name="Close").click()


def gui_deck(page, server) -> dict:
    """The deck the GUI exports for the project the server holds."""
    project = page.request.get(server["url"] + "/api/project").json()
    answer = page.request.post(server["url"] + "/api/export/mdpa", data=project["mesh"])
    assert answer.ok, answer.text()
    return answer.json()


def script_deck(model) -> dict:
    with solid_model.session():
        return writer.export_project(model)


def calculate(page) -> str:
    """Calculate from the toolbar, and the run the results then show."""
    page.locator('#maintoolbar .tbtn[data-action="calculate"]').click()
    page.wait_for_function("App.Results && App.Results.current() && App.state.mode === 'results'"
                           " && App.Results.stage()", timeout=LONG)
    return page.evaluate("App.Results.current()")


@pytest.fixture
def kratos(request) -> bool:
    """Whether Kratos calculates here, or `tests/fakes/fake_kratos.py` in its place."""
    return bool(request.config.getoption("--run-kratos"))


def test_case_a_built_in_the_gui_is_kratos_model_and_answer(app_page, live_server,
                                                            tmp_path, kratos):
    open_column(app_page, tmp_path, "column", "muskat.muskat(order=2)", (),
                "The saturated column, with no water and a deformation stage.")
    head_on_face(app_page, "Left", "Left head", 3.0)
    head_on_face(app_page, "Right", "Right head", 1.6)
    groundwater_flow(app_page)

    assert reference.deck_view(gui_deck(app_page, live_server)) == \
        reference.deck_view(script_deck(muskat.muskat(order=2)))

    run = calculate(app_page)
    assert app_page.errors == []
    if not kratos:
        return
    got = muskat.at_kratos_nodes(catalog.stage_mesh(run, 1), catalog.stage_results(run, 1),
                                 muskat.KRATOS_A)
    for node, (_, expected) in muskat.KRATOS_A.items():
        for variable, value in expected.items():
            if variable == "FLUID_FLUX_VECTOR":
                assert got[node][variable][0] == pytest.approx(value[0], rel=1e-4)
            else:
                assert got[node][variable][0] == pytest.approx(value, abs=1.0), (node, variable)


def test_case_c_seepage_face_drawn_in_the_gui_lets_the_water_out(app_page, live_server,
                                                                 tmp_path, kratos):
    open_column(app_page, tmp_path, "seepage", "muskat.seepage()", ("left_head", "start"),
                "Case C without its right face: no tail water, no seepage face.")
    on_a_line(app_page, "water_pressure", "Tail water", "1.62 0, 1.62 0.48", level=0.48)
    on_a_line(app_page, "seepage", "Seepage face", "1.62 0.48, 1.62 4")
    groundwater_flow(app_page)

    assert reference.deck_view(gui_deck(app_page, live_server)) == \
        reference.deck_view(script_deck(muskat.seepage()))

    run = calculate(app_page)
    assert app_page.errors == []
    if not kratos:
        return
    face, inflow, outflow = muskat.seepage_outcome(catalog.stage_mesh(run, 1),
                                                   catalog.stage_results(run, 1))
    assert outflow == pytest.approx(-inflow, rel=1e-3)
    assert muskat.CHARNY_DISCHARGE <= outflow <= 1.02 * muskat.CHARNY_DISCHARGE
    assert 1.7 <= muskat.exit_point(face) <= 2.0
