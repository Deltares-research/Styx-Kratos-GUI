# Use the GUI

This page tells you how to make a model in the GUI, calculate it, and read the results. The
GUI is the part of Styx that you use in the browser. To install Styx, see
[INSTALLATION.md](INSTALLATION.md). To calculate, you also need Kratos: see
[KRATOS_SETUP.md](KRATOS_SETUP.md).

> [!WARNING]
> The Styx server keeps the open project in its memory. It does not save the project to a
> file itself. If you stop the server before you save, you lose your changes. Save often
> with **File** → **Save** (<kbd>Ctrl</kbd>+<kbd>S</kbd>).

## The window

| Part | Where | What it does |
|---|---|---|
| Menu bar | Top | All commands, in menus |
| Toolbar | Below the menu bar | New, open, save, the **2D** and **3D** buttons, undo, zoom, views, grid, rulers, snapping, **Calculate** |
| Mode tabs | Below the toolbar | One tab for each step of the work, from **Soil** to **Results** |
| Tool rail | Left | The tools of the mode that is open |
| Viewport | Centre | The model. Click an object to select it. |
| Model explorer | Right, top | A tree of all the objects in the model. Clear a check box to hide an object. |
| Selection explorer | Right, bottom | The properties of the selected object. You can edit most of them here. |
| Command panel | Bottom | The **Session** log with all messages, the **Model history** tab with the commands that you typed, and the command box |
| Status bar | Very bottom | The mode, the server status, the cursor coordinates, the unit system, snapping and zoom |

Staged construction mode adds a **Stages explorer**, and Results mode adds a **Results
explorer**, below the Model explorer.

Some menu items and tools come from the first design of the GUI and do nothing yet. They are
grey, in the menus and on the tool rail, and you cannot select them. The tip of a grey tool
says *not available yet*. These are, for example: **Import soil layers…**, **Create point**,
**Create plate**, **Create beam**, **Create embedded beam**, **Tunnel designer…**, **Refine
mesh**, **Coarsen mesh**, the wells, drains and flow functions, **Select multiple objects**,
**Activate selection**, **Deactivate selection**, **Preview stage**, **Pack project…**,
**Print…**, the **Expert** menu (except **Command line**), and **Help** → **Reference
manual** and **Tutorial manual**.

## The order of work

Do the modes from left to right:

| Mode | What you do there |
|---|---|
| Soil | Add boreholes, make the soil layers, and select the soil materials |
| Structures | Add sheet piles, anchors, interfaces, loads, and drawn or imported solids |
| Flow conditions | Set the water level and the water pressure conditions |
| Mesh | Set the mesh size and make the mesh. Make it after the water conditions: a condition is meshed into the model that Kratos reads. |
| Staged construction | Make the construction stages, and select the active parts in each stage |
| Results | Look at the results of a calculation |

Click **Calculate** between Staged construction and Results.

## Projects

- **New project:** **File** → **New project…** starts an empty site.
- **Open project:** **File** → **Open project…** opens a project file (`.json`).
- **Save:** **File** → **Save** or **Save as…** writes the project as a `.json` file. In
  Chrome and Edge, a window asks where to save the file. Other browsers put the file in your
  Downloads folder.
- **Undo and redo:** the toolbar buttons, or <kbd>Ctrl</kbd>+<kbd>Z</kbd> and
  <kbd>Ctrl</kbd>+<kbd>Y</kbd>. Styx keeps the last 40 steps.
- **2D or 3D:** the **2D** button shows a plane-strain section through the model. The **3D**
  button shows the full solid model. When you change between them, Styx converts the loads
  and the walls.
- **Units:** the project uses one unit system: SI (N, m, kg, s) or kN (kN, m, t, s). Click
  the units in the status bar, or type `units kN` or `units SI`, to convert all values.
- **A model from a Python script:** type `run <file.py>` in the command box. For an example,
  type `run tests/models/excavation.py`.

The project file has the same format as the project file of `kratos-cli`. So you can open a
file in the GUI that you made in the terminal, and the other way around.

## Move around in the viewport

| To do this | Do this |
|---|---|
| Rotate the model (3D only) | Drag with the left mouse button, when the **Rotate** button is on |
| Pan | Drag with the middle mouse button, or hold <kbd>Shift</kbd> and drag. When the **Pan** button is on, the left mouse button also pans. |
| Zoom | Turn the mouse wheel |
| Show the full model | <kbd>F5</kbd>, or the **Zoom to fit** button |
| Use a standard view | The **Front**, **Top**, **Side** and **Iso** buttons in the viewport |
| Show coordinates along the edges (2D) | The **Show rulers** button |

Right-click in the viewport for more commands: hide the selected object, hide all other
objects, show all, show node or element labels, and visibility settings.

Right-click an object in the Model explorer to zoom to it, rename it, delete it, or open its
properties.

## Soil mode

### Boreholes and soil layers

1. Add boreholes with the **Create borehole** tool, or type `borehole <x> <y>`. `x` and `y`
   are map coordinates. A borehole gets the levels of the last borehole. Without `x` and `y`,
   it goes 10 m past the last borehole. This is the same as `kratos-cli borehole add`.
2. Click **Modify soil layers…**. The window shows the boreholes on the left and the layers of
   one borehole on the right. You can also add a borehole there with **Add borehole**.
3. Use **Add**, **Insert** and **Delete** to change the layers. Type the top, the bottom or
   the thickness, and select a material for each layer.
4. Click **OK** to save the layers and make the geometry again. Click **Cancel** to go back to
   the layers that you had before.

Styx keeps the layers without gaps. When you change the bottom or the thickness of a layer,
the top of the layer below it moves too.

> [!NOTE]
> Each borehole has a **Water level** field. Styx keeps this value, but does not send it to
> Kratos. The water pressures come from the water pressure conditions of
> [Flow conditions mode](#flow-conditions-mode).

### Material sets

Click **Show material sets…**. Each soil material is a Kratos property set: a constitutive
law and its parameters.

- To add a soil, select a preset in **Default library** (Fill, Sand loose, Sand dense, Clay
  soft, Clay stiff or Bedrock) and click **Add to project**. Styx adds a copy that you can
  change.
- To change a material, click **Properties…** in its row.
- To give a material the strength and permeability of an interface, select the material, then
  select an interface preset and click **Apply to selected**.
- Click **OK** to save the materials, or **Cancel** to forget your changes.

The preset values are only a start. Check them for your soil.

### Soil surfaces and volumes

**Create soil surface…** (in 2D) or **Create soil volume…** (in 3D) adds a body of soil that
is not a layer, for example an embankment or a lens. Type the corners of its outline and
select its material.

### Excavations

The GUI cannot make an excavation pit yet. To add a pit and the levels to which it is dug,
use `kratos-cli excavation` (see [CLI.md](CLI.md)) or a Python script. The GUI then shows each
lift of the pit as its own soil body, for example *Soil_Top · lift 1*.

## Structures mode

| Object | How to add it |
|---|---|
| Sheet pile (2D) | Click **Create sheet pile…**. Type the two end points and the section properties, then click **Save**. |
| Wall panel (3D) | Click **Create wall panel…**. Type the corners of the footprint, the **Top level** and the **Toe level**. |
| Member (3D): a bored pile, a king post or a strut | Click **Create member…**. |
| Anchor | Click **Create anchor…** (in 3D: **Create anchor in space…**). Styx puts the head of the anchor on a sheet pile, a wall panel or a member. Then change the head, the tail and the prestress in the Selection explorer. |
| Interface (2D only) | Click **Create interface**. See [Interfaces](#interfaces). |
| Point or line load (2D), surface load (3D) | Click **Create load**. Type the position and the load components, or click **Pick on model…** and click in the viewport. |
| Normal load (2D only) | Click **Create normal load**. Type the two end points. Select **Uniform** and type the pressure, or select **Hydrostatic** and type the **Reference level**, where the pressure is zero. An empty level takes the water level. |
| Support (2D only, along a line or at a point) | Click **Create boundary condition** and select **Line prescribed displacement** or **Point prescribed displacement**. Click the points in the viewport, then select the components to fix. See [Boundary conditions](#boundary-conditions). |
| Point, line, surface, or box (3D only) | Click the tool, then click the points in the viewport. You can also type `x y` or `x y z` in the command box for each point. Press <kbd>Enter</kbd> to finish a line or a surface, or <kbd>Esc</kbd> to stop. |
| Solid from a CAD file | Click **Import model…** and select a STEP, IGES, BREP, STL or OBJ file. |

To change an object, select it in the viewport or in the Model explorer, then change its
properties in the Selection explorer. An object that is not **Active** stays in the project,
but Styx does not send it to Kratos.

The sheet pile section starts with values near an AZ 26-700 steel sheet pile. In 2D, the
values are for each metre of wall, divided by the **Spacing**.

### Interfaces

An interface is a contact with zero thickness between a sheet pile and the soil. It lets the
wall slide along the soil.

- **Create interface** adds an interface to the first sheet pile. If the model has no sheet
  pile, the tool draws a free interface line through the soil.
- The **Side** row selects the faces that get the interface: both, left or right. For a
  retaining wall, you usually select both.
- The **Contact** rows set the soil whose strength `R_inter` reduces, the virtual thickness,
  and the permeability.

Interfaces work only in plane strain, so the tool is not available in 3D.

## Flow conditions mode

The water pressures in the soil come from the water pressure conditions only. A model with
no water pressure condition has no fixed water pressure, also when it has a water level.
See [Boundary conditions](#boundary-conditions).

The model has one horizontal water level. A new hydrostatic water pressure condition or
normal load takes this level as its own. To change the water level, select **Global water
level** in the Model explorer. Then change **Level** or **Specific weight** in the Selection
explorer. You can also type `water -1.5` to set the level to -1.5 m, or `water off` to
remove the water. A condition keeps its own level when the water level changes.

**Create water pressure line** draws a water pressure along a line or at a point (2D).
**Boundary conditions…** opens the window of all conditions. The well, drain and flow
function tools are not available yet.

## Boundary conditions

Kratos gets the boundary conditions of the model and no others. Open the **Boundary
conditions** window from the Structures or Flow conditions tool rail, or from **Flow
conditions** → **Boundary conditions…**. The Model explorer lists the conditions under
**Model conditions** → **Boundary conditions**. Select one to change it in the Selection
explorer.

To add one condition, click **Create boundary condition** in the Structures or Mesh tool
rail, or select **Create boundary condition…** in the **Structures** or **Mesh** menu. The
window asks for the condition and where it acts. For a line, type the points or click **Pick
on model…** and click them in the viewport; right-click to end the line.

Styx finds a face of the model on the soil: the left face is the soil at the lowest x, and
the bottom face is the soil at the lowest y. On a slope or a step, the soil can touch such a
face at one corner only, so a roller on that face holds one node. To hold a sloping or
stepped edge, put a support on a line along it. A roller on a sloping line is not possible,
because a support holds x or y and a sloping line has no x or y normal; select the
components to hold.

| Condition | What it does |
|---|---|
| Support | Holds the displacement at zero in x, y or z. **Fixed** holds all components. **Roller** holds the component normal to the face, or to a vertical or horizontal line. A 2D model does not hold z. |
| Water pressure, Uniform | One pressure at each node of the target, compression negative |
| Water pressure, Hydrostatic | Zero at its **Reference level**, growing with depth below it. **Tension cut-off** is the most suction above the level; 0 holds the pressure at zero there. |
| Water pressure, Phreatic line | Hydrostatic below a line through points that you type, x increasing |

A condition acts on the whole soil (water pressure only), a face of the model, a soil part,
a line or a point. Lines and points are drawn in the 2D section. A water pressure is fixed in
each stage that has it on, or, with **Initial**, only gives the start values. To change the
water from one stage to the next, see
[Switch water conditions on and off](#switch-water-conditions-on-and-off).

The viewport does not show the conditions when a model opens. To show a condition, turn on
its eye in the Model explorer, or select it there; the eye of **Boundary conditions** shows
all of them. A condition that you only selected goes away when you select something else.
In 2D, a support that holds x and y has the clamp symbol (a stem on hatched ground), and a
support that holds one of them has a triangle on rollers. A 2D model does not list its
front and back supports: the section holds z without them. They stay in the project for the
solid model, and the calculation files of a 2D model do not contain them.

The window has a row for each face of the model and one for the whole soil. For each row,
select the support and the water pressure, and type the level or the value. **More…** opens
the full form of the water pressure, and **Add condition…** makes a condition on a part, a
line or a point. In the water pressure column of a face, **Seepage face** makes that face a
seepage face (see below). **Standard conditions** sets the bottom to fixed and the sides to rollers.
**Clear** removes the conditions on the faces and on the whole soil. Click **Save** to keep
the changes.

A new project has the standard supports and no water pressure condition. For a dry model
whose soil couples the water pressure to the deformation (`GEO_DRAINAGE_TYPE` other than
`CONSTANT_PW_FIELD`), add a **Uniform** water pressure of 0 on the whole soil. The export
warns about it, and about a model that nothing holds.

**Gravity** is on in a new project. Clear it in the window, or select **Model conditions**
→ **Gravity**, to remove the self weight from every stage. A K0 stage then has zero
stresses.

A **seepage face** is a part of the soil's outer boundary where the water may leave the
soil in a groundwater flow calculation, for example the downstream face of a dam above the
tail water. Kratos decides, while it calculates, where the face is open: there the water
pressure is zero and the water flows out. Make one in one of these ways:

- In the **Boundary conditions** window, select **Seepage face** in the water pressure
  column of a face.
- In **Create boundary condition**, select the condition **Seepage face**, on a face or a
  line.
- In Flow conditions mode, open the water pressure tool of the tool rail, select
  **Seepage line** and draw the line along the boundary.

A seepage line through the soil is refused when you calculate. The viewport shows a seepage
face as a line with arrows that point out of the soil. Kratos opens or closes one node of
the face for each iteration, so give the stage enough iterations: the calculation warns
when the stage allows fewer iterations than the face has nodes. A deformation calculation
leaves a seepage face out, and warns.

## Mesh mode

When you open Mesh mode, the **Mesh properties** window opens:

| Setting | What it does |
|---|---|
| Layer mesh sizes | Select the layers to mesh, and give each one its own target size. Styx meshes the selected layers together, so their shared faces have common nodes. |
| Global element size | The maximum length of an element edge, in metres |
| Element order | Linear elements, or quadratic elements with a midside node on each edge |
| 2D algorithm, 3D algorithm | The Gmsh algorithm that makes the elements |
| Optimization | A step that makes the shape of the elements better |
| Smoothing steps | The number of smoothing steps on the surface mesh |
| Curvature points | The minimum number of points along a curved edge. 0 switches this off. |
| Minimum-size factor | The smallest element size, as a fraction of the global size |
| Straight quadratic edges | Keeps the midside nodes on straight lines, so that elements do not turn inside out |

Click **Apply and generate** to make the mesh, or **Apply** to only keep the settings.
<kbd>F9</kbd> in Mesh mode makes the mesh again with the saved settings.

To see the numbers of the nodes or the elements, right-click in the viewport and select
**Show labels**. To show a part of the mesh in its own colour, type `colour <part>`. To see
the parts that contain a node, type `node <id>`.

## Staged construction mode

A construction stage is one step of the calculation. In each stage, parts of the model are
on (active) or off. A stage starts from the result of the stage before it.

> Stages were called *phases* before Styx took Kratos' word for them. A project saved with
> a `phases` list opens unchanged, and the command box still answers `phases`. Styx saves
> the project with `stages`, which older versions of Styx cannot read.

### Make the stages

If the project has no stages, the Stages explorer shows **Create default stages**. Click it.
Styx then makes two stages: the initial stage (K0 procedure) and a null step. Add the other
stages yourself, for example one to install the wall and one for each excavation lift.

To make the full sequence from the model in one step, use
`kratos-cli stages P staged-excavation` (see
[Stage commands](CLI.md#stage-commands)). It installs each wall, digs lift by lift, and puts
in each anchor after the lift that uncovers it.

Use the buttons at the top of the Stages explorer to change the sequence:

| Button | What it does |
|---|---|
| Add stage | Adds a stage at the end |
| Insert stage | Adds a stage above the selected stage |
| Duplicate | Makes a copy of the selected stage |
| Delete | Deletes the selected stage |
| Stages… | Opens the **Stages** window with the settings of each stage |

### Switch parts on and off

1. Select a stage in the Stages explorer.
2. In the Model explorer, select or clear the check box of a part. You can also click the
   part in the viewport.

The stages after the selected stage keep this change until a later stage changes it again.

### Switch water conditions on and off

A water pressure condition is on in every stage until a stage switches it off. In
Staged construction mode, each water pressure condition under **Model conditions** →
**Boundary conditions** has a check box for the selected stage, as a part has. For
example, to lower the water from a level at -1 m to a level at -6 m in stage 3:

1. Add a second hydrostatic condition with its **Reference level** at -6 m.
2. Select the first stage, and clear the check box of the -6 m condition.
3. Select stage 3. Select the check box of the -6 m condition, and clear the check box of
   the -1 m condition.

The viewport shows the water conditions that the selected stage has on. A stage with no
water condition on keeps the water pressures that the stage before it ended with, for a
**Hydrostatic** or **Phreatic line** condition. A **Uniform** condition does not keep its
values: after its stage, the water pressure of a soil that couples it to the deformation is
free, and the export warns about it. You cannot delete a condition that a stage switches;
clear its check boxes first. The supports are on in every stage.

### Stage settings

In the **Stages** window, select a stage and set:

- **Name** and **Start from stage**
- **Calculation type**: **K0 procedure** (calculates the initial stresses), **Plastic**,
  **Null step**, or **Groundwater flow**
- **Reset displacements to zero**
- **Max iterations** and **Tolerated error**

A **Groundwater flow** stage calculates a steady-state flow of the water through the soil.
It calculates the water pressure only, so the soil does not move:

- Give every stage the type Groundwater flow. Calculate refuses a project that has both
  flow stages and deformation stages.
- Use a 2D model, and give every soil material a `PERMEABILITY_XX`.
- In each stage, switch on at least one fixed water pressure condition on a face or a
  line, where the head is known. A boundary with no water pressure condition lets no water
  through.
- The calculation uses the soil only. It leaves out sheet piles, anchors, interfaces and
  loads, and says so. It also leaves out the supports: the Model explorer marks them
  "(unused in flow)", and **Reset displacements to zero** is greyed out.
- The results are the water pressure, the hydraulic head, the effective saturation and the
  flux `q` (the specific discharge, in m/s).

The window also lists the parts that each stage switches on and off, and the result of the
last calculation for each stage.

The **Activate selection**, **Deactivate selection** and **Preview stage** tools in the tool
rail are not available yet.

## Calculate

> [!IMPORTANT]
> Calculate needs Kratos. Set it up first with [KRATOS_SETUP.md](KRATOS_SETUP.md).

Click **Calculate** in the toolbar, or press <kbd>F9</kbd> outside Mesh mode. Styx then:

1. makes the mesh,
2. writes the Kratos input files into a new run folder in `~/KratosGUI/runs`,
3. runs Kratos, and
4. opens Results mode when Kratos is done.

While Kratos runs, the log shows *Meshing, writing the deck and running Kratos…*. You can run
one calculation at a time. If a stage fails, the log shows which stage failed and why, and
the Stages explorer shows which stages finished.

Styx never overwrites or deletes a run folder. See
[What a calculation writes](KRATOS_SETUP.md#what-a-calculation-writes).

## Export and import Kratos files

- **File** → **Export model…** writes the Kratos input files into one ZIP file: the mesh
  (`.mdpa`), `MaterialParameters.json`, `ProjectParameters.json`, and the other files that
  the stages need. The log lists each assumption and warning of the export. Use this to run
  the model in Kratos without Styx.
- **File** → **Import mesh (.mdpa)…** shows the mesh of an existing Kratos file, with a list
  of its parts. You can look at this mesh, but you cannot change it.
- `script <file.py>` writes the model as a Python script that builds it again.

## Results mode

### Open a run

After a calculation, Results mode opens with the new run. To open a different run, also from
an earlier session:

1. Type `results runs`, or click **Results** → **Open run…**. The log shows all the runs,
   newest first, with a number for each run.
2. Type `results open <number>`.

### Show a result

Use the Results explorer, or click **Choose results** in the tool rail:

| Setting | What it does |
|---|---|
| Stage | The construction stage to show |
| Field | The quantity: displacements, effective stresses, pore pressure, and more |
| Shading | Smooth colours, or 8 to 48 colour bands |
| Colours | The colour map, for example Rainbow, Viridis or Greyscale |
| Limits | The minimum and maximum of the legend. **Auto** uses the range of the field. |
| Reverse | Turns the colour map around |
| Mesh | Shows the element edges over the colours |
| Deformed | Shows the deformed mesh: off, automatic scale, true scale, ×10 or ×100 |

Compression is negative, as Kratos writes it. Each value is in the unit system of the run:
stresses in Pa for SI, or in kPa for kN.

### Other results

- **Plot along the wall:** click **Plot wall…**, or type `results plot`. The plot shows the
  bending moment (M), the shear force (Q), the normal force (N), the horizontal displacement
  (ux) and the interface tractions (tn, ts) against depth, with one line for each stage.
  **Save SVG** saves the figure, and **Save CSV** saves the numbers.
- **Values at a node:** click **Results** → **Value at a node…**, or type
  `results at <node>`.
- **Save the field as CSV:** click **Save CSV**, or type `results csv`.
- **Save the full run:** click **Download run**, or type `results zip`.

## The command box

Type a command in the command box below the log, and press <kbd>Enter</kbd>. Use
<kbd>↑</kbd> and <kbd>↓</kbd> to get earlier commands again. Type `help` to see the list.

| Command | What it does |
|---|---|
| `run <file.py>` | Builds the model from a Python script |
| `script <file.py>` | Writes the model as a Python script |
| `export` | Writes the Kratos input files, as **File** → **Export model…** |
| `mesh` | Makes the mesh |
| `calculate` | Calculates the model, as the **Calculate** button |
| `stages` | Opens the **Stages** window |
| `water <level>`, `water off` | Sets or removes the water level |
| `boundary`, `boundary standard` | Lists the boundary conditions, or puts the standard supports back |
| `gravity`, `gravity on`, `gravity off` | Shows gravity, or switches it on or off |
| `units`, `units SI`, `units kN` | Shows or changes the unit system |
| `borehole`, `borehole <x> <y>` | Adds a borehole, 10 m past the last one or at map `x`, `y` |
| `soillayers`, `materials` | Opens the **Modify soil layers** or **Material sets** window |
| `cleargeometry` | Removes all drawn and imported solids |
| `colour <part>`, `colour all`, `colour off` | Shows parts of the mesh in their own colour |
| `node <id>` | Shows the parts that contain a node of the mesh |
| `gotosoil`, `gotostructures`, `gotomesh`, `gotoflow`, `gotostaged` | Opens a mode |
| `view iso`, `view top`, `view front`, `view side`, `zoomfit` | Changes the view |
| `clear` | Clears the log |
| `results …` | Works with results. Type `results` alone to see all its forms. |

**Help** → **Command reference** shows the same list in a window.

[CLI.md](CLI.md#the-guis-command-box-in-the-terminal) gives the `kratos-cli` command that does
the same as each command of the command box.

## Keyboard shortcuts

| Key | What it does |
|---|---|
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Save the project |
| <kbd>Ctrl</kbd>+<kbd>O</kbd> | Open a project |
| <kbd>Ctrl</kbd>+<kbd>N</kbd> | Start a new project |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | Undo |
| <kbd>Ctrl</kbd>+<kbd>Y</kbd> or <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> | Redo |
| <kbd>F5</kbd> | Zoom to fit |
| <kbd>F9</kbd> | In Mesh mode: make the mesh. In all other modes: calculate. |
| <kbd>Esc</kbd> | Clear the selection, or stop a drawing tool |
| <kbd>Enter</kbd> | Finish a line or a surface that you draw |

Some browsers keep <kbd>Ctrl</kbd>+<kbd>N</kbd> and <kbd>Ctrl</kbd>+<kbd>O</kbd> for
themselves. If these keys do not work, use the **File** menu or the toolbar.
