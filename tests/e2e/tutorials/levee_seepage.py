"""The levee seepage GUI tutorial (`docs/gui_tutorials/levee_seepage_case.md`): a
steady-state groundwater flow under and through a clay levee, built from an empty project
through the GUI's windows.

It builds the model of `tests/models/levee_seepage.py`, and takes every number a reader
types from there, so the two cannot drift apart. `tests/e2e/test_gui_tutorials.py` holds
the deck it gives to that model's deck.

`MODEL` is built when it is first read: its drawn parts need their solids, which gmsh
makes, and the quick tests that read this module's steps need none of that.
"""

from __future__ import annotations

from tests.e2e.tutorials.harness import (LONG, TOOL, Step, Tour, field, fill, mode,
                                         project, rail, rail_tool, select_in_tree,
                                         selection_row, set_in_selection, tool, tree_row,
                                         window)
from tests.models import levee_seepage as levee

PLAN = levee.levee_project()
"""The model, without the solids of its drawn parts: what the steps type."""
PAGE = "levee_seepage_case.md"


def __getattr__(name: str):
    if name == "MODEL":
        return levee.project()
    raise AttributeError(name)


def _number(value) -> str:
    """A number as a reader types it: `1e+20` as `1e20`, `2650.0` as `2650`."""
    return f"{value:.17g}".replace("e+", "e")


# ── 1. The project ─────────────────────────────────────────────────────────

def new_project(tour: Tour) -> None:
    page = tour.page
    tool(tour, "newProject")
    window(page).locator("input[name=name]").fill(PLAN.name)
    tour.picture(mark=TOOL.format("newProject"))
    window(page).get_by_role("button", name="OK").click()
    tour.until(f"App.PROJECT.name === {PLAN.name!r}")
    tour.until("App.PROJECT.dimension === 2 && App.state.modelMode === '2d'")


def project_is_new(tour: Tour) -> None:
    got = project(tour)
    assert got["name"] == PLAN.name and got["dimension"] == 2


# ── 2. The soils and the water ─────────────────────────────────────────────

FLOW_ROWS = ("PERMEABILITY_XX", "PERMEABILITY_YY", "MINIMUM_RELATIVE_PERMEABILITY",
             "VAN_GENUCHTEN_GL", "BULK_MODULUS_SOLID", "BIOT_COEFFICIENT")
"""The rows the second screenshot of the first soil shows: what makes the water flow."""


def _put_variable(tour: Tour, props, variable: str, value) -> None:
    control = props.locator(f'[data-variable="{variable}"]').first
    if control.evaluate("e => e.tagName") == "SELECT":
        control.select_option(str(value))
    else:
        fill(control, _number(value))
    tour.settle()


def soils(tour: Tour) -> None:
    page = tour.page
    mode(tour, "soil")
    rail(tour, "materials")
    materials = window(page)
    materials.locator('[data-action="create-soil"]').wait_for()
    tour.picture(mark=[rail_tool("materials"), materials.locator('[data-action="create-soil"]')])
    for soil in PLAN.materials:
        materials.locator('[data-action="create-soil"]').click()
        props = window(page)
        props.locator('[data-field="name"]').wait_for()
        fill(props.locator('[data-field="name"]'), soil.name)
        props.locator('[data-field="color"]').fill(soil.color)
        props.locator('[data-field="soil-model"]').select_option(label="Linear elastic")
        tour.settle()
        for variable, value in soil.variables.items():
            _put_variable(tour, props, variable, value)
        tour.picture(soil.id, of=props, mark=[
            props.locator('[data-variable="GEO_DRAINAGE_TYPE"]'),
            props.locator('[data-variable="RETENTION_LAW"]')])
        if soil is PLAN.materials[0]:
            tour.picture(f"{soil.id}_flow", of=props, mark=[
                props.locator(f'[data-variable="{name}"]') for name in FLOW_ROWS])
        props.get_by_role("button", name="Close").click()
    for key, value in (("bulk_modulus", PLAN.fluid.bulk_modulus),
                       ("dynamic_viscosity", PLAN.fluid.dynamic_viscosity)):
        fill(materials.locator(f'input[data-water="{key}"]'), _number(value))
    tour.settle()
    tour.picture("water", of=materials, mark=[materials.locator('input[data-water]')])
    materials.get_by_role("button", name="OK").click()
    tour.until(f"App.PROJECT.materials.length === {len(PLAN.materials)}")


def two_soils(tour: Tour) -> None:
    got = project(tour)
    by_name = {m["name"]: m for m in got["materials"]}
    for soil in PLAN.materials:
        assert by_name[soil.name]["constitutive_law"] == soil.constitutive_law
        assert by_name[soil.name]["variables"] == soil.variables, soil.name
    assert got["fluid"]["bulk_modulus"] == PLAN.fluid.bulk_modulus
    assert got["fluid"]["dynamic_viscosity"] == PLAN.fluid.dynamic_viscosity


# ── 3. The layers and the width ────────────────────────────────────────────

def layers(tour: Tour) -> None:
    page = tour.page
    rail(tour, "soilLayers")
    dialog = window(page)
    for _ in PLAN.layers:
        dialog.locator(".lay-toolbar button", has_text="Add").first.click()
    rows = dialog.locator(".lay-table tbody tr")
    rows.nth(len(PLAN.layers) - 1).wait_for()
    soil_names = {m.id: m.name for m in PLAN.materials}
    for index, layer in enumerate(PLAN.layers):
        row = rows.nth(index)
        fill(row.locator("input").nth(0), layer.name)
        row.locator("select").select_option(label=soil_names[layer.mat])
        fill(row.locator("input").nth(2), f"{layer.bottom:g}")
    tour.picture(mark=rail_tool("soilLayers"))
    dialog.locator(".dlg-foot .btn-primary").click()
    tour.until(f"App.PROJECT.layers.length === {len(PLAN.layers)}")
    tour.settle()
    select_in_tree(tour, PLAN.layers[0].name)
    set_in_selection(tour, "x min", f"{PLAN.domain.x0:g}")
    set_in_selection(tour, "x max", f"{PLAN.domain.x1:g}")
    tour.until(f"App.PROJECT.domain.x0 === {PLAN.domain.x0} && "
               f"App.PROJECT.domain.x1 === {PLAN.domain.x1}")
    tour.picture("width", mark=[tree_row(page, PLAN.layers[0].name),
                                selection_row(page, "x min"), selection_row(page, "x max")])


def two_layers(tour: Tour) -> None:
    got = project(tour)
    assert [(lay["name"], lay["top"], lay["bottom"]) for lay in got["layers"]] == \
        [(lay.name, lay.top, lay.bottom) for lay in PLAN.layers]
    assert (got["domain"]["x0"], got["domain"]["x1"]) == (PLAN.domain.x0, PLAN.domain.x1)


# ── 4. The levee ───────────────────────────────────────────────────────────

def levee_parts(tour: Tour) -> None:
    page = tour.page
    soil_names = {m.id: m.name for m in PLAN.materials}
    for index, part in enumerate(PLAN.custom_parts, start=1):
        rail(tour, "createSoilVolume")
        dialog = page.locator("#soil-volume-dialog")
        dialog.wait_for()
        field(page, "Name").fill(part.label)
        field(page, "Material").select_option(label=soil_names[part.mat])
        corners = part.recipe["vertices"]
        rows = dialog.locator(".soil-volume-row")
        while rows.count() < len(corners):
            dialog.get_by_role("button", name="Add corner").click()
        while rows.count() > len(corners):
            rows.last.get_by_role("button").click()
        for row, (x, y, _) in enumerate(corners):
            fill(rows.nth(row).locator("input").nth(0), f"{x:g}")
            fill(rows.nth(row).locator("input").nth(1), f"{y:g}")
        if index == 1:
            tour.picture("core", mark=[rail_tool("createSoilVolume"),
                                       dialog.get_by_role("button", name="Add corner")])
        dialog.get_by_role("button", name="Create").click()
        dialog.wait_for(state="detached", timeout=LONG)
        tour.until(f"(App.PROJECT.custom_parts || []).length === {index}")
        tour.settle()
    tour.picture("after", mark=[tree_row(page, part.label) for part in PLAN.custom_parts])


def two_parts(tour: Tour) -> None:
    got = project(tour)["custom_parts"]
    assert [(p["label"], p["recipe"]["vertices"]) for p in got] == \
        [(p.label, p.recipe["vertices"]) for p in PLAN.custom_parts]


# ── 5. The water ───────────────────────────────────────────────────────────

RIVER, POLDER, SEEPAGE, START = levee.CONDITIONS


def _points(points) -> str:
    return ", ".join(f"{x:g} {y:g}" for x, y in points)


def _condition(tour: Tour, record, picture: str = "") -> None:
    page = tour.page
    rail(tour, "createBoundaryCondition", "Create boundary condition…")
    field(page, "Name").fill(record.name)
    field(page, "Condition").select_option(record.kind)
    field(page, "Where").select_option(record.on)
    if record.on == "line":
        field(page, "Points").fill(_points(record.points))
    if record.kind == "water_pressure":
        field(page, "Type").select_option(record.fluid_pressure_type)
        if record.fluid_pressure_type == "Hydrostatic":
            field(page, "Reference level").fill(f"{record.reference_coordinate:g}")
        else:
            field(page, "Phreatic line").fill(
                _points(zip(record.x_coordinates, record.y_coordinates)))
        field(page, "Tension cut-off").fill(f"{record.pressure_tension_cut_off:g}")
        field(page, "Initial only").set_checked(not record.is_fixed)
    if picture:
        tour.picture(picture, mark=rail_tool("createBoundaryCondition"))
    count = len(project(tour)["boundary_conditions"])
    window(page).get_by_role("button", name="Save").click()
    tour.until(f"App.PROJECT.boundary_conditions.length === {count + 1}")
    tour.settle()


def water(tour: Tour) -> None:
    mode(tour, "structures")
    _condition(tour, RIVER, "river")
    _condition(tour, POLDER)
    _condition(tour, SEEPAGE, "seepage")
    _condition(tour, START, "start")


def water_conditions(tour: Tour) -> None:
    got = {b["name"]: b for b in project(tour)["boundary_conditions"]}
    for record in levee.CONDITIONS:
        made = got[record.name]
        assert (made["kind"], made["on"]) == (record.kind, record.on), record.name
        if record.on == "line":
            assert [tuple(p) for p in made["points"]] == [tuple(p) for p in record.points]
    assert got[START.name]["is_fixed"] is False
    assert got[START.name]["x_coordinates"] == START.x_coordinates


# ── 6. The mesh ────────────────────────────────────────────────────────────

def mesh(tour: Tour) -> None:
    page = tour.page
    mode(tour, "mesh")
    dialog = page.locator("#mesh-settings-dialog")
    if not dialog.count():
        rail(tour, "meshSettings")
    dialog.wait_for()
    dialog.locator("[name=element_size]").fill(f"{PLAN.mesh.element_size:g}")
    dialog.locator("select[name=order]").select_option(str(PLAN.mesh.order))
    tour.picture("window", mark=[dialog.locator("[name=element_size]"),
                                 dialog.locator("select[name=order]")])
    dialog.get_by_role("button", name="Apply and generate").click()
    tour.until("App.Viewport.hasMesh && App.Viewport.hasMesh()", timeout=LONG)
    tour.picture("mesh")


def meshed(tour: Tour) -> None:
    got = project(tour)["mesh"]
    assert (got["element_size"], got["order"]) == (PLAN.mesh.element_size, PLAN.mesh.order)


# ── 7. The stage ───────────────────────────────────────────────────────────

STAGE = PLAN.stages[0]


def _stage_row(dialog, label: str):
    return dialog.locator(".pgrid-row").filter(
        has=dialog.page.locator(".pgrid-key", has_text=label))


def _choose_in_stage(tour: Tour, dialog, label: str, value: str) -> None:
    _stage_row(dialog, label).locator("select").first.select_option(value)
    tour.settle()


def _type_in_stage(tour: Tour, dialog, label: str, text: str) -> None:
    box = _stage_row(dialog, label).locator("input").first
    box.fill(text)
    box.press("Enter")
    tour.settle()


def stage(tour: Tour) -> None:
    page = tour.page
    mode(tour, "staged")
    page.locator(".phase-list .phase-row").first.click()
    tour.settle()
    page.locator(".stage-toolbar button", has_text="Stages…").click()
    dialog = window(page)
    _stage_row(dialog, "Name").locator("input").first.wait_for()
    _choose_in_stage(tour, dialog, "Calculation type", STAGE.calculation)
    _type_in_stage(tour, dialog, "Name", STAGE.name)
    _choose_in_stage(tour, dialog, "Convergence criterion", STAGE.convergence_criterion)
    _type_in_stage(tour, dialog, "Max iterations", str(STAGE.max_iterations))
    _type_in_stage(tour, dialog, "Tolerated error", f"{STAGE.tolerated_error:g}")
    tour.picture(of=dialog, mark=[_stage_row(dialog, label) for label in (
        "Name", "Calculation type", "Convergence criterion", "Max iterations",
        "Tolerated error")])
    dialog.get_by_role("button", name="Close").click()


def one_flow_stage(tour: Tour) -> None:
    (got,) = project(tour)["stages"]
    assert (got["name"], got["calculation"], got["convergence_criterion"],
            got["max_iterations"], got["tolerated_error"], got["absolute_tolerance"]) == \
        (STAGE.name, STAGE.calculation, STAGE.convergence_criterion, STAGE.max_iterations,
         STAGE.tolerated_error, STAGE.absolute_tolerance)


# ── 8. Calculate ───────────────────────────────────────────────────────────

def calculate(tour: Tour) -> None:
    tool(tour, "calculate")
    tour.until("App.Results && App.Results.current() && App.state.mode === 'results'",
               timeout=600_000)
    tour.settle()
    window(tour.page).wait_for()
    tour.picture(mark=TOOL.format("calculate"))
    window(tour.page).locator(".dlg-foot").get_by_role("button", name="Close").click()
    tour.settle()
    tour.page.locator("#modal-layer .dialog").first.wait_for(state="detached")


# ── 9. Contour plots ───────────────────────────────────────────────────────

CONTOURS = (("pw", "pressure"), ("head", "head"), ("effective_saturation", "saturation"),
            ("flux", "flux"))
"""The fields the page shows on the mesh, and the name of each screenshot."""


def contours(tour: Tour) -> None:
    panel = tour.page.locator("#panel-results")
    panel.locator('select[data-res="stage"]').select_option("1")
    tour.until("App.Results.stage() === 1", timeout=LONG)
    for name, part in CONTOURS:
        panel.locator('select[data-res="field"]').select_option(name)
        tour.until(f"App.Results.field() && App.Results.field().field === {name!r}",
                   timeout=LONG)
        tour.settle()
        tour.picture(part, mark=[panel.locator('select[data-res="stage"]'),
                                 panel.locator('select[data-res="field"]')])


STEPS = [
    Step("01_project", "Start a new project", new_project, project_is_new),
    Step("02_soils", "Make the two soils and the water", soils, two_soils),
    Step("03_layers", "Add the soil layers and set the width", layers, two_layers),
    Step("04_levee", "Draw the levee", levee_parts, two_parts),
    Step("05_water", "Add the water conditions", water, water_conditions),
    Step("06_mesh", "Make the mesh", mesh, meshed),
    Step("07_stage", "Make the stage a groundwater flow stage", stage, one_flow_stage),
    Step("08_results", "Calculate", calculate),
    Step("09_contours", "Look at the water pressure and the flow", contours),
]

