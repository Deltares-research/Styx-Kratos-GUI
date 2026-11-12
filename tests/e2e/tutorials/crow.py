"""The CROW GUI tutorial (`docs/gui_tutorials/CROW_case.md`): the excavation wall with
Mohr-Coulomb soils, built from an empty project through the GUI's windows.

It builds the model of `tests/models/crow.py`, and takes every number a reader types from
there, so the two cannot drift apart. `tests/e2e/test_gui_tutorials.py` holds the deck it
gives to that model's deck.

The soil bodies the two lines cut out of the top layers are numbered by the GUI (Part 1,
Part 2, ...). The step that renames them names each one by its number, as a reader sees it
in the Model explorer.
"""

from __future__ import annotations

from tests.e2e.tutorials.harness import (LONG, Step, Tour, choose_in_selection, field,
                                         fill, mode, project, rail, rename,
                                         select_in_tree, set_in_selection, tool,
                                         tree_row, type_command, window)
from tests.models import crow

MODEL = crow.project(crow.MOHR_COULOMB)


def _by_id(items, key):
    return next(item for item in items if item.id == key)


# ── 1. The project ─────────────────────────────────────────────────────────

def new_project(tour: Tour) -> None:
    page = tour.page
    tool(tour, "newProject")
    window(page).locator("input[name=name]").fill(MODEL.name)
    tour.picture()
    window(page).get_by_role("button", name="OK").click()
    tour.until(f"App.PROJECT.name === {MODEL.name!r}")
    tool(tour, "viewMode2D")
    tour.until("App.PROJECT.dimension === 2")


def project_is_new(tour: Tour) -> None:
    got = project(tour)
    assert got["name"] == MODEL.name and got["dimension"] == 2
    assert got["gravity_acceleration"] == MODEL.gravity_acceleration


# ── 2. The soils ───────────────────────────────────────────────────────────

def _put_variable(tour: Tour, props, variable: str, value) -> None:
    """One variable of the soil: in its own field, or in the Add row for one the window
    does not list."""
    control = props.locator(f'[data-variable="{variable}"]')
    if control.count():
        control = control.first
        kind = control.evaluate("e => e.tagName + ':' + (e.type || '')")
        if kind.startswith("SELECT"):
            control.select_option(str(value))
        elif kind.endswith("checkbox"):
            control.set_checked(bool(value))
        else:
            fill(control, repr(value))
    else:
        props.locator('[data-field="new-variable"]').fill(variable)
        props.locator('[data-field="new-value"]').fill(
            "false" if value is False else value if isinstance(value, str) else repr(value))
        props.locator('[data-action="add-variable"]').click()
    tour.settle()


def soils(tour: Tour) -> None:
    page = tour.page
    mode(tour, "soil")
    rail(tour, "materials")
    for soil in MODEL.materials:
        # Create soil opens the new soil's properties at once.
        window(page).locator('[data-action="create-soil"]').click()
        props = window(page)
        props.locator('[data-field="name"]').wait_for()
        fill(props.locator('[data-field="name"]'), soil.name)
        props.locator('[data-field="color"]').fill(soil.color)
        props.locator('[data-field="soil-model"]').select_option(label=crow.MOHR_COULOMB)
        tour.settle()
        for variable, value in soil.variables.items():
            _put_variable(tour, props, variable, value)
        fill(props.locator('[data-field="rInter"]'), repr(soil.r_inter))
        tour.settle()
        tour.picture(soil.id)
        props.get_by_role("button", name="Close").click()
    window(page).get_by_role("button", name="OK").click()
    tour.until(f"App.PROJECT.materials.length === {len(MODEL.materials)}")


def two_soils(tour: Tour) -> None:
    got = {m["name"]: m for m in project(tour)["materials"]}
    for soil in MODEL.materials:
        assert got[soil.name]["constitutive_law"] == soil.constitutive_law
        assert got[soil.name]["variables"] == soil.variables, soil.name
        assert abs(got[soil.name]["r_inter"] - soil.r_inter) < 1e-12


# ── 3. The layers and the width ────────────────────────────────────────────

def layers(tour: Tour) -> None:
    page = tour.page
    rail(tour, "soilLayers")
    dialog = window(page)
    for _ in MODEL.layers:
        dialog.locator(".lay-toolbar button", has_text="Add").first.click()
    rows = dialog.locator(".lay-table tbody tr")
    rows.nth(len(MODEL.layers) - 1).wait_for()
    soil_names = {m.id: m.name for m in MODEL.materials}
    for index, layer in enumerate(MODEL.layers):
        row = rows.nth(index)
        fill(row.locator("input").nth(0), layer.name)
        row.locator("select").select_option(label=soil_names[layer.mat])
        fill(row.locator("input").nth(2), f"{layer.bottom:g}")
    tour.picture()
    dialog.locator(".dlg-foot .btn-primary").click()
    tour.until(f"App.PROJECT.layers.length === {len(MODEL.layers)}")
    tour.settle()
    # No window sets the width: the Selection explorer of a layer does.
    select_in_tree(tour, MODEL.layers[0].name)
    set_in_selection(tour, "x max", f"{MODEL.domain.x1:g}")
    tour.until(f"App.PROJECT.domain.x1 === {MODEL.domain.x1}")


def three_layers(tour: Tour) -> None:
    got = project(tour)
    assert [(lay["name"], lay["top"], lay["bottom"]) for lay in got["layers"]] == \
        [(lay.name, lay.top, lay.bottom) for lay in MODEL.layers]
    assert (got["domain"]["x0"], got["domain"]["x1"]) == (MODEL.domain.x0, MODEL.domain.x1)


# ── 4. The water ───────────────────────────────────────────────────────────

WATER = _by_id(MODEL.boundary_conditions, "pore_pressure")


def water(tour: Tour) -> None:
    page = tour.page
    mode(tour, "structures")
    rail(tour, "createBoundaryCondition", "Create boundary condition…")
    field(page, "Name").fill(WATER.name)
    field(page, "Condition").select_option("Water pressure")
    field(page, "Where").select_option(label="Whole soil")
    field(page, "Type").select_option(WATER.fluid_pressure_type)
    field(page, "Reference level").fill(f"{WATER.reference_coordinate:g}")
    tour.picture()
    window(page).get_by_role("button", name="Save").click()
    tour.until(f"App.PROJECT.boundary_conditions.some(b => b.name === {WATER.name!r})")


def water_condition(tour: Tour) -> None:
    (got,) = [b for b in project(tour)["boundary_conditions"] if b["name"] == WATER.name]
    assert got["on"] == "domain"
    assert got["reference_coordinate"] == WATER.reference_coordinate


# ── 5. The wall ────────────────────────────────────────────────────────────

WALL = MODEL.beams[0]
WALL_SECTION = _by_id(MODEL.beam_sections, WALL.section)


def wall(tour: Tour) -> None:
    page = tour.page
    rail(tour, "createSheetPile")
    (x1, y1), (x2, y2) = WALL.points
    for label, value in [("Name", WALL.name), ("x1", x1), ("y1", y1), ("x2", x2),
                         ("y2", y2), *WALL_SECTION.variables.items(),
                         ("Spacing", WALL_SECTION.spacing)]:
        field(page, label).fill(repr(value) if isinstance(value, float) else str(value))
    tour.picture()
    window(page).get_by_role("button", name="Save").click()
    tour.until("(App.PROJECT.beams || []).length === 1")


def one_wall(tour: Tour) -> None:
    got = project(tour)
    (beam,) = got["beams"]
    assert [tuple(p) for p in beam["points"]] == [tuple(p) for p in WALL.points]
    (section,) = got["beam_sections"]
    assert section["variables"] == WALL_SECTION.variables


# ── 6. The lines, and the soil bodies they make ────────────────────────────

FLOOR_1, FLOOR_2 = MODEL.lines


def lines(tour: Tour) -> None:
    page = tour.page
    # One drawn: each point typed in the command box, then Enter in the empty box.
    rail(tour, "drawLine", "Draw line")
    for x, y in FLOOR_1.points:
        type_command(tour, f"{x:g} {y:g}")
    type_command(tour, "")
    field(page, "Name").wait_for()
    field(page, "Name").fill(FLOOR_1.name)
    tour.picture("drawn")
    window(page).get_by_role("button", name="Save").click()
    tour.until("(App.PROJECT.lines || []).length === 1")
    # One typed in a window.
    rail(tour, "drawLine", "Line by coordinates…")
    field(page, "Name").fill(FLOOR_2.name)
    points = window(page).locator(".line-point")
    for index, (x, y) in enumerate(FLOOR_2.points):
        points.nth(index).locator("input").nth(0).fill(f"{x:g}")
        points.nth(index).locator("input").nth(1).fill(f"{y:g}")
    tour.picture("typed")
    window(page).get_by_role("button", name="Save").click()
    tour.until("(App.PROJECT.lines || []).length === 2")


BODY_NAMES = [
    # (the label the GUI gives the body, the name the model gives it)
    ("Soil_Top · Part 3", "lift 1"),
    ("Soil_Top · Part 1", "lift 2"),
    ("Soil_Top · Part 4", "lift 3"),
    ("Soil_Top · Part 2", "retained"),
    ("Soil_Middle · Part 1", "below the pit"),
    ("Soil_Middle · Part 2", "retained"),
]


def name_the_bodies(tour: Tour) -> None:
    tree_row(tour.page, BODY_NAMES[0][0]).wait_for()
    tour.picture("before")
    for label, name in BODY_NAMES:
        rename(tour, label, name)


def bodies_named(tour: Tour) -> None:
    """The names only: the deck at the end shows each name is on the right piece."""
    got = project(tour)
    layer = {lay["id"]: lay["name"] for lay in got["layers"]}
    want_layer = {lay.id: lay.name for lay in MODEL.layers}
    assert sorted((layer[b["layer"]], b["name"]) for b in got["bodies"]) == \
        sorted((want_layer[b.layer], b.name) for b in MODEL.bodies)


# ── 7. The strut ───────────────────────────────────────────────────────────

STRUT = MODEL.anchors[0]
STRUT_SECTION = _by_id(MODEL.anchor_sections, STRUT.section)


def strut(tour: Tour) -> None:
    page = tour.page
    rail(tour, "createAnchor")
    tour.until("(App.PROJECT.anchors || []).length === 1")
    tour.settle()
    for label, value in [*STRUT_SECTION.variables.items(),
                         ("Spacing", STRUT_SECTION.spacing),
                         ("Head x", STRUT.head[0]), ("Head y", STRUT.head[1]),
                         ("Tail x", STRUT.tail[0]), ("Tail y", STRUT.tail[1])]:
        set_in_selection(tour, label, f"{value:g}")
    page.locator("#grid-selection button", has_text="No tension limit").click()
    tour.settle()
    tour.picture()
    rename(tour, page.evaluate("App.PROJECT.anchors[0].name"), STRUT.name)


def one_strut(tour: Tour) -> None:
    got = project(tour)
    (anchor,) = got["anchors"]
    assert anchor["name"] == STRUT.name
    assert tuple(anchor["head"]) == STRUT.head and tuple(anchor["tail"]) == STRUT.tail
    (section,) = got["anchor_sections"]
    assert section["variables"] == STRUT_SECTION.variables


# ── 8. The interface ───────────────────────────────────────────────────────

CONTACT = MODEL.interfaces[0]
CONTACT_SECTION = _by_id(MODEL.interface_sections, CONTACT.section)


def interface(tour: Tour) -> None:
    page = tour.page
    rail(tour, "interface")
    field(page, "Name").fill(CONTACT.name)
    field(page, "Side").select_option("both")
    tour.picture("window")
    window(page).get_by_role("button", name="Save").click()
    tour.until("(App.PROJECT.interfaces || []).length === 1")
    tour.settle()
    set_in_selection(tour, "Virtual thickness", f"{CONTACT_SECTION.virtual_thickness:g}")
    choose_in_selection(tour, "Law", "Coulomb")
    page.locator("#grid-selection button", has_text="Each soil’s own R_inter").click()
    tour.settle()
    tour.picture("contact")


def one_interface(tour: Tour) -> None:
    got = project(tour)
    (section,) = got["interface_sections"]
    assert section["constitutive_law"] == CONTACT_SECTION.constitutive_law
    assert section["virtual_thickness"] == CONTACT_SECTION.virtual_thickness
    assert section.get("r_inter") is None and section.get("material") is None


# ── 9. The loads ───────────────────────────────────────────────────────────

SURCHARGE = MODEL.loads[0]


def loads(tour: Tour) -> None:
    page = tour.page
    rail(tour, "createLoad", "Line load")
    for label, value in [("Name", SURCHARGE.name), ("x min", SURCHARGE.x0),
                         ("x max", SURCHARGE.x1), ("y", SURCHARGE.y),
                         ("qx", SURCHARGE.components[0]), ("qy", SURCHARGE.components[1])]:
        field(page, label).fill(value if isinstance(value, str) else f"{value:g}")
    tour.picture("surcharge")
    window(page).get_by_role("button", name="Save").click()
    tour.until("(App.PROJECT.loads || []).length === 1")
    for index, load in enumerate(MODEL.normal_loads, start=1):
        rail(tour, "createLoad", "Normal load")
        field(page, "Name").fill(load.name)
        rows = window(page).locator(".line-point")
        while rows.count() < len(load.points):
            window(page).get_by_role("button", name="Add point").click()
        for row, (x, y) in enumerate(load.points):
            rows.nth(row).locator("input").nth(0).fill(f"{x:g}")
            rows.nth(row).locator("input").nth(1).fill(f"{y:g}")
        field(page, "Type").select_option(load.fluid_pressure_type)
        field(page, "Reference level").fill(f"{load.reference_coordinate:g}")
        if index == 1:
            tour.picture("water")
        window(page).get_by_role("button", name="Save").click()
        tour.until(f"(App.PROJECT.normal_loads || []).length === {index}")


def all_loads(tour: Tour) -> None:
    got = project(tour)
    (load,) = got["loads"]
    assert (load["x0"], load["x1"], tuple(load["components"])) == \
        (SURCHARGE.x0, SURCHARGE.x1, SURCHARGE.components)
    assert [[tuple(p) for p in n["points"]] for n in got["normal_loads"]] == \
        [[tuple(p) for p in n.points] for n in MODEL.normal_loads]


# ── 10. The mesh ───────────────────────────────────────────────────────────

def mesh(tour: Tour) -> None:
    page = tour.page
    mode(tour, "mesh")
    dialog = page.locator("#mesh-settings-dialog")
    if not dialog.count():
        rail(tour, "meshSettings")
    dialog.wait_for()
    dialog.locator("[name=element_size]").fill(f"{MODEL.mesh.element_size:g}")
    wall_row = dialog.locator("label.mesh-body-row").filter(has_text=WALL.name)
    wall_row.locator(".mesh-structure-size").fill(f"{MODEL.mesh.body_sizes['sheetpile']:g}")
    wall_row.locator(".mesh-structure-band").fill(f"{MODEL.mesh.size_bands['sheetpile']:g}")
    tour.picture("window")
    dialog.get_by_role("button", name="Apply and generate").click()
    tour.until("App.Viewport.hasMesh && App.Viewport.hasMesh()", timeout=LONG)
    tour.picture("mesh")


def meshed(tour: Tour) -> None:
    got = project(tour)["mesh"]
    assert got["element_size"] == MODEL.mesh.element_size
    assert got["order"] == MODEL.mesh.order
    assert list(got["body_sizes"].values()) == [MODEL.mesh.body_sizes["sheetpile"]]
    assert list(got["size_bands"].values()) == [MODEL.mesh.size_bands["sheetpile"]]


# ── 11. The stages ─────────────────────────────────────────────────────────

INITIAL_OFF = [WALL.name, STRUT.name, CONTACT.name, SURCHARGE.name,
               *(load.name for load in MODEL.normal_loads)]

SWITCHES = [
    # (what the stage switches on, what it switches off), by Model explorer label
    ([WALL.name, CONTACT.name, SURCHARGE.name], []),
    (["WaterLoad_Stage1"], ["Soil_Top · lift 1"]),
    ([STRUT.name], []),
    (["WaterLoad_Stage2"], ["Soil_Top · lift 2", "WaterLoad_Stage1"]),
    (["WaterLoad_Stage3"], ["Soil_Top · lift 3", "WaterLoad_Stage2"]),
]


def _switch(tour: Tour, label: str, on: bool) -> None:
    """The check box of a Model explorer row: is the object there in this stage."""
    eye = tree_row(tour.page, label).locator(".tree-eye")
    if ("off" not in (eye.get_attribute("class") or "")) != on:
        eye.click()
        tour.settle()


def _pick_stage(tour: Tour, name: str) -> None:
    tour.page.locator(".phase-list .phase-row").filter(has_text=name).first.click()
    tour.settle()


def stages(tour: Tour) -> None:
    page = tour.page
    mode(tour, "staged")
    page.get_by_role("button", name="Create default stages").click()
    tour.until("(App.PROJECT.stages || []).length === 2")
    tour.settle()
    _pick_stage(tour, MODEL.stages[0].name)
    for label in INITIAL_OFF:
        _switch(tour, label, False)
    tour.picture("initial")
    for number, (stage, (on, off)) in enumerate(zip(MODEL.stages[2:], SWITCHES), start=3):
        page.locator('.stage-toolbar .tbtn[data-action="addStage"]').click()
        tour.until(f"App.PROJECT.stages.length === {number}")
        tour.settle()
        page.locator(".stage-toolbar button", has_text="Stages…").click()
        dialog = window(page)
        texts = dialog.locator(".stages-overview .pgrid input:not([type=checkbox])")
        texts.nth(0).wait_for()
        for index, value in [(0, stage.name)]:
            texts.nth(index).fill(value)
            texts.nth(index).press("Enter")
            tour.settle()
        dialog.locator(".stages-overview .pgrid select").first.select_option(stage.calculation)
        tour.settle()
        for index, value in [(2, stage.max_iterations), (3, stage.tolerated_error)]:
            texts.nth(index).fill(f"{value:g}")
            texts.nth(index).press("Enter")
            tour.settle()
        if number == 3:
            tour.picture("window")
        dialog.get_by_role("button", name="Close").click()
        _pick_stage(tour, stage.name)
        for label in on:
            _switch(tour, label, True)
        for label in off:
            _switch(tour, label, False)
    tour.picture("last")


def seven_stages(tour: Tour) -> None:
    got = project(tour)["stages"]
    assert [(s["name"], s["calculation"], s["max_iterations"], s["tolerated_error"])
            for s in got] == \
        [(s.name, s.calculation, s.max_iterations, s.tolerated_error) for s in MODEL.stages]


# ── 12. Calculate, and the moment in the wall ──────────────────────────────

def calculate(tour: Tour) -> None:
    tool(tour, "calculate")
    tour.until("App.Results && App.Results.current() && App.state.mode === 'results'",
               timeout=600_000)
    tour.settle()
    rail(tour, "plotResults")
    tour.page.locator("#modal-layer .dialog").last.wait_for()
    tour.settle()
    tour.picture("plot")


STEPS = [
    Step("01_project", "Start a new project", new_project, project_is_new),
    Step("02_soils", "Make the two soils", soils, two_soils),
    Step("03_layers", "Add the soil layers and set the width", layers, three_layers),
    Step("04_water", "Give the soil its water pressure", water, water_condition),
    Step("05_wall", "Add the sheet pile wall", wall, one_wall),
    Step("06_lines", "Draw the floors of the first two lifts", lines),
    Step("07_bodies", "Name the soil bodies", name_the_bodies, bodies_named),
    Step("08_strut", "Add the strut", strut, one_strut),
    Step("09_interface", "Add the interface along the wall", interface, one_interface),
    Step("10_loads", "Add the surcharge and the water loads", loads, all_loads),
    Step("11_mesh", "Make the mesh", mesh, meshed),
    Step("12_stages", "Set up the seven stages", stages, seven_stages),
    Step("13_results", "Calculate and look at the wall", calculate),
]
