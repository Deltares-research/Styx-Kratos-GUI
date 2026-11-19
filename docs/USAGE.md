# Use the GUI

This page tells you how to make a model in the GUI, calculate it, and read the results. The
GUI is the part of Styx that you use in the browser. To install Styx, see
[INSTALLATION.md](INSTALLATION.md). To calculate, you also need Kratos: see
[KRATOS_SETUP.md](KRATOS_SETUP.md).

To learn the GUI by building one model step by step, start with the
[GUI tutorials](gui_tutorials/index.md).

> [!WARNING]
> The Styx server keeps the open project in its memory. It does not save the project to a
> file itself. If you stop the server before you save, you lose your changes. Save often
> with **File** → **Save** (<kbd>Ctrl</kbd>+<kbd>S</kbd>).

## The window

| Part | Where | What it does |
|---|---|---|
| Menu bar | Top | All commands, in menus |
| Toolbar | Below the menu bar | New, open, save, **Save picture** (the camera), the **2D** and **3D** buttons, undo, zoom, views, grid, rulers, snapping, **Calculate** |
| Mode tabs | Below the toolbar | One tab for each step of the work, from **Soil** to **Results** |
| Tool rail | Left | The tools of the mode that is open |
| Viewport | Centre | The model. Click an object to select it. |
| Model explorer | Right, top | A tree of all the objects in the model. A group, such as **Sheet piles**, shows when the model has one. Clear a check box to hide an object. |
| Selection explorer | Right, bottom | The properties of the selected object. You can edit most of them here. |
| Command panel | Bottom | The **Session** log with all messages, the **Model history** tab with the commands that you typed, and the command box |
| Status bar | Very bottom | The mode, the server status, the cursor coordinates, the unit system, snapping and zoom |

Staged construction mode adds a **Stages explorer**, and Results mode adds a **Results
explorer**, below the Model explorer.

The menus and the tool rail show only the items that work. Plates, beams, wells, drains and
other tools that Styx does not have yet are not shown.

## The order of work

Do the modes from left to right:

| Mode | What you do there |
|---|---|
| Soil | Make the soil layers and select the soil materials |
| Structures | Add sheet piles, anchors, interfaces, loads, and drawn or imported solids |
| Flow conditions | Set the water level and the water pressure conditions |
| Mesh | Set the mesh size and make the mesh. Make it after the water conditions: a condition is meshed into the model that Kratos reads. |
| Staged construction | Make the construction stages, and select the active parts in each stage |
| Results | Look at the results of a calculation |

Click **Calculate** between Staged construction and Results.

## Projects

- **New project:** **File** → **New project…** starts an empty site. Type the project name
  in the window. The name shows in the title bar, and **Save** names the file after it.
  The session starts clean: the command log, the Model history, the commands that the arrow
  keys bring back, the undo history, the mesh, the results, the node and element ID
  labels and the **Convergence** window of a finished calculation are cleared.
  **Open project…** clears them in the same way.
- **Project properties:** **File** → **Project properties…** changes the name of the open
  project, the size of the soil block, the gravitational acceleration g (9.81 m/s² in a
  new project) and the unit system. The size is **x min**, **x max**, **y min** (the
  bottom) and **y max** (the ground level), in m. A 3D model also has **z min** and
  **z max**. A new project is 20 m wide (x 0 to 20) and 15 m deep (y −15 to 0). A new
  **y min** or **y max** also moves the bottom of the last layer or the top of the first.
  In the terminal, `kratos-cli set FILE name NAME`, `kratos-cli domain FILE --x FROM TO
  --y BOTTOM TOP`, `kratos-cli gravity FILE G` and `kratos-cli units FILE kN` do the same.
  A new size writes its `domain --x ... --y ...` line in the command log. You can type
  that line in the command box too, and `domain` alone shows the size.
- **Open project:** **File** → **Open project…** opens a project file (`.json`).
- **Save:** **File** → **Save** or **Save as…** writes the project as a `.json` file. In
  Chrome and Edge, a window asks where to save the file. Other browsers put the file in your
  Downloads folder.
- **Undo and redo:** the toolbar buttons, or <kbd>Ctrl</kbd>+<kbd>Z</kbd> and
  <kbd>Ctrl</kbd>+<kbd>Y</kbd>. Styx keeps the last 40 steps.
- **2D or 3D:** the **2D** button shows a plane-strain section through the model. The **3D**
  button shows the full solid model. When you change between them, Styx converts the loads
  and the walls.
- **Units:** the project uses one unit system: SI (N, m, kg, s) or kN (kN, m, t, s). For
  example, a cohesion of 5000 Pa in SI is 5 kPa in kN. To convert all values, choose the
  **Unit system** in **File** → **Project properties…**, click the units in the status bar,
  or type `units kN` or `units SI`. Lengths stay in m and g stays in m/s².
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
properties. This works for every object, soil layers too. **Rename…** opens a small window:
type the new name and click **OK**, or press <kbd>Enter</kbd>.

Each soil layer and soil surface has a name of its own. If you give one a name that is
already in use, Styx adds a number: a second *Embankment* becomes *Embankment_2*. The
Session log says so. The Model explorer, `kratos-cli` and the Kratos input files then use
the same name.

## Soil mode

### Soil layers

A soil layer is a horizontal band across the whole domain, with one top and one bottom.
The top of the first layer is the ground level. To use NAP levels, type the ground level
as the top of the first layer, for example 1.7. The bottom of the last layer is the
bottom of the model.

1. Click **Modify soil layers…**. The window shows the layer table on the right and a column
   of the layers on the left. The column also shows the water level as a dashed blue line.
2. Use **Add**, **Insert** and **Delete** to change the layers. **Add** puts a 5 m layer under
   the last one. The first layer starts at the top of the domain. **Insert** splits the
   selected layer in two.
3. Type the name, the top, the bottom or the thickness, and select a material for each layer.
4. Click **OK** to save the layers and make the geometry again. Click **Cancel** to go back to
   the layers that you had before.

Styx keeps the layers without gaps. When you change the bottom or the thickness of a layer,
the top of the layer below it moves too. When you change the top of a layer, the bottom of
the layer above it moves too. A level that goes past the other level of the next layer is
refused, and the line under the table tells you why. You can also type the top (**y max**)
and the bottom (**y min**) of a layer in the Selection explorer. This is the same as
`kratos-cli layer set`.

For a layer that is not horizontal, draw a soil surface or a soil volume (see below).

### Soil materials

Click **Soil materials…**. Each soil material is a Kratos property set: a constitutive
law and its parameters.

- To add a soil, click **Create soil**. Styx adds a linear elastic soil that is mechanical
  only (`CONSTANT_PW_FIELD`) and saturated below the phreatic level (`SaturatedBelowPhreaticLevelLaw`), and
  opens its properties. `kratos-cli material add` makes the same soil. The other values are empty: type them. The line at the bottom of
  the window lists the values that the soil still needs for a calculation. Until you type
  K0, the window shows the K0 that the export calculates from the Poisson's ratio (linear
  elastic) or the friction angle (Mohr-Coulomb).
- To start from a preset instead, go to **Default soil material library** under the soils, select a preset
  in **Soil** and a soil model in **Model**, and click **Add to project**. Styx adds a
  copy that you can change. The presets are the default soils of D-Stability and
  D-Settlement, from Embankment to Sand, less permeable, and Bedrock. **Model**
  starts at the preset's own model: Mohr-Coulomb, or linear elastic for Bedrock. A preset
  added as linear elastic has no strength. Bedrock added as Mohr-Coulomb gets the default
  strength, and the line at the bottom of the window names those values.
- To look at a preset before you add it, click **Properties…** next to **Model**. The
  soil's window opens with all its values, but the soil is not in the project. Click
  **Close** to leave it out, or change values and click **Add to project** to add it as
  it stands. `kratos-cli material presets ID` shows the same values.
- To change a material, click **Properties…** in its row.
- To make a material Mohr-Coulomb, open **Properties…** and select **Mohr-Coulomb** in
  **Soil model**. Styx sets the Kratos law for the dimension of the model, keeps the values
  the material has, and fills in defaults for the others. The line at the bottom of the
  window lists the values it filled in. The material is then ready for a calculation. For a
  soil that still has empty values, such as a new soil, Styx fills in no values that you
  must type, for example the friction angle: the soil stays yours to fill in.
- In the **Properties…** window, the parameters are in groups (Drainage, Stiffness,
  Weight, Saturation, Flow, Grain-water interaction, Strength, Hardening, Initial
  stresses). Each has
  a name, with its Kratos variable when you hover it, and its unit beside the field. A text value, such
  as the drainage type or the retention law, is a list of the values Kratos accepts. The
  drainage type shows them as **Mechanical only** (`CONSTANT_PW_FIELD`) and **Fully
  coupled** (`FULLY_COUPLED`), with a line under the list that says what each solves. A
  true/false value, such as the tension cut-off, is a check box.
- The window shows only what the soil model and its choices use. A linear elastic soil has
  no cohesion or friction angle. The flow parameters (the intrinsic permeabilities, the
  minimum relative permeability) show for a `FULLY_COUPLED` soil only, or in a groundwater
  flow project. The tensile strength shows when the tension cut-off is on, the saturations
  for a retention law other than `SaturatedLaw`, and the Van Genuchten parameters for
  `VanGenuchtenLaw`, and the three hardening slopes when **Hardening** is Linear (the
  angles' in radians per unit of plastic strain; each starts at 0). When a choice brings in new
  parameters, Styx fills in their defaults. A mechanical-only soil shows no
  permeability: its water pressures are the ones the water conditions set, and the
  deformation does not change them. Styx has no
  undrained drainage type. A low permeability does not make a soil undrained: a stage
  is static, so a load does not raise the water pressure of a `FULLY_COUPLED` soil. For
  an undrained soil, use a mechanical-only soil with undrained values (total stresses): the
  undrained Young's modulus, a Poisson's ratio close to 0.5 (such as 0.49), and, for
  Mohr-Coulomb, the undrained shear strength as cohesion with a friction angle of 0.
  A new soil is saturated below the phreatic level (`SaturatedBelowPhreaticLevelLaw`).
- A value you leave empty shows, in grey, the value the export writes for it: the
  permeability in y is the one in x, K0 is ν / (1 − ν) for a linear elastic soil and
  1 − sin φ for a Mohr-Coulomb one, and so on. Type a value to replace it.
- The window also shows what follows from the soil's values: its unit weight dry and
  saturated, and for a coupled soil the Darcy permeability (in m/s and m/day) that its
  intrinsic permeability gives with the project's water.
- The water is the same in every soil. Its bulk modulus and viscosity are under **Water**
  in the Soil materials window; its unit weight is that of the water level. Empty, each is
  the value of water at 20 °C.
- For any other Kratos law, for example a UDSM, select **Other** in **Soil model** and type
  the law name. Styx writes it as you type it, with the variables you give it: only here
  can you add variables of your own.
- Click **OK** to save the materials, or **Cancel** to forget your changes.

The preset values are only a start. Check them for your soil.

### Soil surfaces and volumes

**Create soil surface…** (in 2D) or **Create soil volume…** (in 3D) adds a body of soil that
is not a layer, for example an embankment or a lens. Type the corners of its outline and
select its material. In a terminal, `kratos-cli surface add` makes the same soil surface.

A line splits a soil surface in the same way as a layer (see below). Each part then has its
own row in the Model explorer, for example *Embankment · Part 1*. Select a part and click
**Edit coordinates…** to change the corners of the whole surface. A new material for the
surface goes to all of its parts. In 3D, a line splits a soil volume only if the volume is
a polygon extruded along z, or a box.

### Lines that split the soil

**Structures > Create line** splits soil into parts. Click the points of the line in the
section, then press Enter or right-click. The Line window opens with the points. Correct
them there if needed, and select **Save**. The arrow in the corner of the button also has
**Line by coordinates…**, which opens the same window with no drawing first. While you
draw, you can also type `x y` in the command box to place a point.

Where a line crosses a soil layer or a soil surface from one edge to another, it becomes
separate soil parts. A sheet pile splits a layer in the same way. In the Model explorer each part has its
own row, for example *Soil_Top · Part 1*. In **Staged construction** you can switch each
part off in its own stage. Select a part to rename it or to give it another material. A
part starts with its layer's material. Change the layer's material, in the **Soil layers**
window or in the Selection explorer, and every part of that layer takes the new material,
also a part you gave a material of its own.

A part you rename shows the new name alone, for example *Clay*. A part with the name it
was given, such as *Part 1*, also shows its layer or soil surface.

Right-click a part to rename it or delete it, or to delete its whole layer or soil surface.
The Selection explorer of a part has the same buttons. The Rename window starts with the
name the Model explorer shows, for example *Soil_Top · Part 1*. To rename a layer, use the
**Soil layers** window. **Delete part** deletes that
part alone: no soil is left there, and the other parts stay. The last part of a layer or a
soil surface cannot be deleted alone; delete the whole layer or surface. A deleted part
comes back when you delete the line that cut it off, or with undo. To take soil away in one
stage only, switch the part off in that stage instead.

Lines have their own group in the Model explorer. Delete a line there, and the parts join
again, unless a stage still uses one of them. Then the deletion is refused.

A part of a line that ends inside the soil splits nothing. The Session log says so when no
part of a line splits anything.

An excavation is made in this way: a wall and a line at each level make the lifts, and a
stage switches each lift off.

A project saved with an excavation pit opens with lines and soil parts in its place, for
example *lift 1*, a part of the layer *Soil_Top*. A pit with one level was never dug, so it just goes. A 3D pit
narrower than the model in z cannot be made of lines, and the project does not open.

## Structures mode

| Object | How to add it |
|---|---|
| Sheet pile (2D) | Click **Create sheet pile…**. Type the two end points and the section properties, then click **Save**. |
| Wall panel (3D) | Click **Create wall panel…**. Type the corners of the footprint, the **Top level** and the **Toe level**. |
| Member (3D): a bored pile, a king post or a strut | Click **Create member…**. |
| Anchor | Click **Create anchor…** (in 3D: **Create anchor in space…**). A window opens, as for a sheet pile. Type the name, the head, the tail, the prestress and the tendon properties, then click **Save**. An anchor does not need a structure. When the head is less than 1 m from a sheet pile, wall panel or member, Styx moves it onto that structure, and the anchor shares its node. A head further away is a node of the soil mesh, so it must be in the soil. With no structure in the model, a new anchor starts 2 m below the top of the soil, in the middle of the model. **Head end** and **Tail end** set what each end is joined to. **Free (attached to the mesh)** is the default for a new anchor: a free head is a node of the structure it is on, or of the soil mesh; a free tail is a node of the soil mesh, so the anchor pulls on the soil. **Fixed (held in place)** holds the end in place and joins it to nothing, as for a strut to a fixed point. Styx does not move a fixed head onto a structure. A free end on no structure must be in the soil: in the air, or in soil that a stage removes, use **Fixed**. A new anchor goes 8 m across and 6 m down from its head, with the tail on whole metres. To change an anchor later, click **Edit anchor…** in the Selection explorer, or **Properties…** in the Model explorer, or change the values in the Selection explorer. The **Tension limit** and **Compression limit** of the tendon are design values: Kratos does not use them, and the export warns while one is set. A new tendon has a tension limit of 900 kN. Type another value, or click **No tension limit** or **No compression limit** to take a limit away. |
| Interface (2D only) | Click **Create interface…**. Select the sheet pile in **Along**, or **Own coordinates**, then click **Save**. See [Interfaces](#interfaces). |
| Point or line load (2D), surface load (3D) | Click **Create load**. Type the position and the load components, or click **Pick on model…** and click in the viewport. |
| Normal load (2D only) | Click **Create normal load**. Type the points of the line: **Add point** adds one after the last, and **Remove** takes one away. Or click **Pick on model…**, click the points in the viewport and press <kbd>Enter</kbd>. Select **Uniform** and type the pressure, or select **Hydrostatic** and type the **Reference level**, where the pressure is zero. A hydrostatic load does not use a pressure. An empty level takes the water level. The arrows of a hydrostatic load grow with depth below its level. |
| Support (2D only, along a line or at a point) | Click **Create boundary condition** and select **Line prescribed displacement** or **Point prescribed displacement**. Click the points in the viewport, then select the components to fix. See [Boundary conditions](#boundary-conditions). |

To change an object, select it in the viewport or in the Model explorer, then change its
properties in the Selection explorer. An object that is not **Active** stays in the project,
but Styx does not send it to Kratos.

In the viewport, a sheet pile is a thick dark line, an anchor is a green line with a dot at
each end, and an interface is a dashed purple line. An interface on a sheet pile is drawn
next to the pile, on each face that has the interface. These lines keep the same width when
you zoom, and they are drawn over the soil and the mesh. On the **Soil** and **Flow
conditions** tabs they are drawn half transparent. A sheet pile, anchor or interface that is
not **Active**, or that the selected stage deactivates, is drawn half transparent too. On the
**Soil** and **Flow conditions** tabs it is fainter still.

The sheet pile section starts with values near an AZ 26-700 steel sheet pile. In 2D, the
values are for each metre of wall, divided by the **Spacing**.

### Interfaces

An interface is a contact with zero thickness between a sheet pile and the soil. It lets the
wall slide along the soil.

**Create interface…** opens the interface window. Nothing is saved until you click
**Save**, so **Cancel** leaves the model as it was. **Edit interface…** in the Selection
explorer, and **Properties…** on the Model explorer row, open the same window.

1. In **Along**, select a sheet pile by its name, or **Own coordinates** for a line through
   the soil.
2. On a sheet pile, **From** and **To** start at the two ends of the pile, so **Save**
   puts the interface on the whole pile. To put it on a part of the pile only, for example
   the part below an anchor, type other points. Styx moves a point onto the pile. A point
   more than 0.5 m from the pile is refused.
3. With **Own coordinates**, type the points of the line, or click **Pick on model…** and
   click two points in the viewport. **Add point** gives the line a bend.
4. In **Side**, select the faces that get the interface: **Both sides**, **Left (toward
   -x)** or **Right (toward +x)**, as you see them on the screen. For a line flatter than
   45 degrees, the faces are **Below** and **Above**. **Both sides** is only for a sheet
   pile. For a retaining wall, you usually select both.
5. In **Contact**, select the contact properties, or **New contact**. You change their
   numbers in the Selection explorer: the law, the stiffnesses, the soil, the virtual
   thickness, and the permeability. A new contact takes the soil each part of the
   interface runs against (**From the soil it runs against**), the R_inter of each soil,
   and a virtual thickness of 1 m. Under **Stiffness**, select **From the soil** (the
   export takes shear G / t and normal 10 G / t from the soil, with t the virtual
   thickness) or **Set on the interface** (type `INTERFACE_NORMAL_STIFFNESS` and
   `INTERFACE_SHEAR_STIFFNESS`; they start from the values the soil gives). The
   **Elastic** law reads the stiffnesses only. The **Coulomb** law reads a strength too,
   and slips when the shear stress reaches it: under **Strength**, select **From the
   soil** (the soil's, reduced by **R_inter**) or **Set on the interface** (type
   `GEO_COHESION` and `GEO_FRICTION_ANGLE`). R_inter reduces the strength only, not the
   stiffness. Under **R_inter**, select **Each soil's own** (the R_inter of each
   soil) or **Set on the interface** (type one number for the whole contact in **R_inter
   value**). A linear elastic soil has no strength, so against one the contact gets its
   own, and you set it. The contact takes the saturation of its soil, and a Coulomb
   contact also takes its tension cut-off.

You can make as many interfaces as you need, for example one on each face of a pile, or
two on parts of one face. Two interfaces on the same face of a pile over the same length
are refused. A line of its own coordinates that runs along a sheet pile is refused too:
select the pile in **Along** and set **From** and **To**.

At an end where the pile goes on, the soil beyond the end stays fixed to the pile. An
interface along the grout body of a ground anchor is not possible, because the grout body
is a point in the model.

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

**Create flow boundary condition…** opens the window of one new water pressure or seepage
face. **Create water pressure line** draws a water pressure along a line or at a point
(2D). **Flow boundary conditions…** opens the window of all water pressures and seepage
faces.

## Boundary conditions

Kratos gets the boundary conditions of the model and no others. The conditions are in two
groups:

| Group | Conditions | Where to set them |
|---|---|---|
| Mechanical | Supports | Structures mode |
| Flow | Water pressures and seepage faces | Flow conditions mode |

Each mode has a window for all conditions of its group: **Mechanical boundary
conditions…** on the Structures tool rail and in the **Structures** menu, and **Flow
boundary conditions…** on the Flow conditions tool rail and in the **Flow conditions**
menu. Each window is a table with one row for each condition of the group in the model:

- **Mechanical boundary conditions**: name, where it acts, the support (Fixed, Roller or
  Custom), and the components it holds. A 2D section does not hold z, so the table shows x
  and y only, and leaves out the front and back supports, which are kept for the solid
  model. **Standard conditions** puts back the bottom fixed and the sides on rollers.
- **Flow boundary conditions**: name, condition, where it acts, type, level or value,
  tension cut-off, and if it gives start values only.

Clear **Active** to leave a condition out of the calculation. Click **Edit…** to change a
condition, or **Delete** to remove it. **Add condition…** adds a condition of the group.

The Model explorer lists all conditions under **Model conditions** → **Boundary
conditions**. Select one to change it in the Selection explorer.

To add one support, click **Create boundary condition** in the Structures tool rail, or
select **Create boundary condition…** in the **Structures** menu. To add one water pressure
or seepage face, click **Create flow boundary condition…** in the Flow conditions tool
rail or menu. The window asks for the condition and where it acts. For a line, type the points or click **Pick
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
| Water pressure, Phreatic line | Hydrostatic below a line through points, x increasing. On a drawn line, the points of the line are filled in for you, in order of x. Type other points to use a different line. A phreatic line on the whole soil or on a line is the water of every soil, wherever it is drawn. A stage can have one on, so a later stage can switch to a lower one. A new phreatic line is **Initial only**: it gives the soil its starting pressures, and a flow or coupled calculation can change them. |
| Water pressure, Head line | As a phreatic line, for the soils that take it under **Soil water** (see [The water of each soil](#the-water-of-each-soil)). |

Water above the ground also presses on it. When the phreatic line is above the soil, the
calculation adds the weight of that water on the ground below it, on the floor and the sides
of a pit, and on the face of a wall (2D). A head line or a hydrostatic level is the water in
a soil, not water that stands on the ground, so it adds no load. This is so whatever the
phreatic line is on; a phreatic line on a soil part puts its water on that part only. This
is done for each stage, with the soil that the stage has, and the water always pushes on the
soil or the wall. You do not draw this load. Where you drew a normal load yourself, your load is used
there instead. The export notes say where the water was added. In **Staged construction**,
the water standing on the ground in the selected stage is filled in light blue up to the
phreatic line. Small light blue arrows press into the soil (longer where the water is
deeper), and the pressure where the water is deepest is shown, for example "p = 10000 Pa"
under 1 m of water. **Flow conditions** shows the same for the model
as built. The other tabs do not show it. In the Model explorer, a phreatic line with water on the ground has a
**Water on the ground** row under it, which says in which stages. A 3D model does not add
this load, and the export warns when the phreatic line is above the ground.

Under open water, the water pressure on the soil surface is the water's. So where an
**Initial only** phreatic line stands above the ground, the calculation also fixes the
water pressure on the wet soil surface under it, stage by stage (2D). This is the boundary
that a flow or a coupled calculation needs. Inside the soil the line gives only the
starting pressures. The phreatic line is written in the stage that switches it on, and the
stages after it continue from the pressures that the stage before left. When a stage leaves
part of the surface dry (it lowers the water, or switches it off), that part is no longer
fixed.

A condition acts on the whole soil (water pressure only), a face of the model, a soil part,
a line or a point. Lines and points are drawn in the 2D section. A water pressure is fixed in
each stage that has it on, or, with **Initial**, only gives the start values. To change the
water from one stage to the next, see
[Switch water conditions on and off](#switch-water-conditions-on-and-off).

In the Model explorer, the check box of a condition shows if the condition is active. Clear
it to keep the condition in the project but leave it out of the calculation. The check box
of **Boundary conditions** switches all of them. In Staged construction mode, the check box
of a water pressure condition is for the selected stage.

Each tab shows the conditions that belong to it. **Soil**, **Structures** and **Mesh** show
the supports. **Flow conditions** shows the water pressure conditions and the seepage faces,
and not the supports. **Staged construction** shows both. Click a condition or the water level
to select it. A click a few pixels away from the line also selects it. To hide a condition,
right-click its row in the Model explorer and select **Hide**. When you select a condition in
the Model explorer, the viewport shows it in every tab until you select something else.
In 2D, a support on a face or a line is drawn from its start to its end. A support that holds
x and y is hatched ground along the edge. A support that holds one of them (a roller) is a
row of triangles on two wheels, from one end to the other. A support on a point is a triangle on hatched ground, or a triangle on two wheels for
a roller. A 2D model does not list its
front and back supports: the section holds z without them. They stay in the project for the
solid model, and the calculation files of a 2D model do not contain them.

The window has a row for each face of the model and one for the whole soil. For each row,
select the support and the water pressure, and type the level or the value. **More…** opens
the full form of the water pressure, and **Add condition…** makes a condition on a part, a
line or a point. In the water pressure column of a face, **Seepage face** makes that face a
seepage face (see below). **Standard conditions** sets the bottom to fixed and the sides to rollers.
**Clear** removes the conditions on the faces and on the whole soil. Under **Soil water**,
select the water of each soil (see [The water of each soil](#the-water-of-each-soil)). Click
**Save** to keep the changes.

A new project has the standard supports and no water pressure condition. For a dry model
whose soil couples the water pressure to the deformation (`GEO_DRAINAGE_TYPE`
`FULLY_COUPLED`), add a **Uniform** water pressure of 0 on the whole soil. The export
warns about it, and about a model that nothing holds.

**Gravity** is not a condition. Whether the self weight acts is decided by the stress
initialisation of the initial stage (see [Stage settings](#stage-settings)): **K0
procedure** and **Gravity loading** put it on every body, the soil and the structures, in
every stage; **None** leaves it out of every stage. The initial stage's **Gravity** row in
the **Stages** window says which. A flow calculation always has it. The acceleration g is
9.81 m/s² unless you change it in **File** → **Project properties…**. The water keeps its
specific weight when g changes: Styx writes the water's density as the specific weight
divided by g.

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

### The water of each soil

The phreatic line is the water of every soil. To model an aquifer under an aquitard, draw
a head line for the aquifer and give a soil other water under **Soil water** in the
Boundary conditions window. Each soil (a layer, a piece of a layer, or a soil part) takes
one of these:

| Soil water | What it does |
|---|---|
| Phreatic line (the default) | Hydrostatic below the phreatic line |
| Head line | Hydrostatic below the head line, for example the head of an aquifer. A head line acts only on the soils that take it. |
| Interpolated between the soils above and below | The pressure of the soil above and of the soil below, interpolated over the depth of this soil, for an aquitard. Kratos' `Interpolate_Line` reads the pressures that the other soils set on the edges of this soil. 2D only; a 3D model gives the soil the phreatic line, and the export says so. |

The phreatic line and the head lines are water pressures of the type **Phreatic line** and
**Head line**: polylines through points, x increasing, which can slope. Draw one on a line
(**Pick on model…**), and its points are filled in from the line, or put it on the whole
soil and type its points. Where it is drawn is only where it is: the phreatic line acts on
every soil, and a head line on the soils that take it. A stage has one phreatic line on, and
any number of head lines. To change the phreatic line in a later stage (a pit pumped dry),
select that stage in **Staged construction** and then create the new phreatic line: it is
switched off in the initial stage and on from the selected stage, and the phreatic line
that was on there is switched off from that stage on. The status line names the stage.
With the initial stage selected, a second phreatic line is refused. For a pressure on a line only, use a **Hydrostatic** condition on
that line. In 2D the viewport draws it in indigo on that line: the line is thick where it
is below the level, a filled diagram grows with the depth, and the deepest pressure is
shown. The same applies to a
Hydrostatic condition on a face.

A project saved before 2026-11-18 read a phreatic line drawn on a line as a pressure on
that line only. When you open it, a level one becomes a Hydrostatic condition on the same
line, which sets the same pressure there. A sloping one becomes the water of the whole soil
(or a head line, if the project has another phreatic line), and a note says so. A head line that no soil takes acts nowhere, and the export warns
about it.

You can also right-click a soil in Flow conditions mode, in the viewport or in the Model
explorer, and choose its water under **Water**. The tick shows the water it takes now.

In Flow conditions mode each soil is filled with the colour of the water it takes, and a
legend in the viewport says which colour is which:

| Water | Colour | How the line is drawn |
|---|---|---|
| Phreatic line | Always blue | A solid line, with the water table mark (▽) near its start |
| Head line | A colour for each head line: red, purple, teal, pink, brown or olive, in list order | A dashed line, labelled with its name |
| Interpolated | Always amber | No line of its own |
| No water line | Grey: a soil on the phreatic line in a project that has none | — |

A project with no phreatic line, no head line and no soil water keeps the soils in their
own colours. The other modes show the soils in their material colours.

Kratos gets a head line as a `Phreatic_Multi_Line`, written on the soils that take it after
the phreatic line, so it replaces the phreatic line there. A Hydrostatic level, a face, a
part or a point condition acts on its own target, as before. When a stage switches a head
line off, its soils have the phreatic line in that stage.

## Mesh mode

When you open Mesh mode and there is no mesh yet, the **Mesh properties** window opens.
When there is a mesh, Mesh mode shows it, and the window stays closed. Use the
**Mesh properties** tool to change the settings and mesh again. A calculation uses this
mesh and does not mesh again. A calculation on a model with no mesh makes one: after it,
Mesh mode shows that mesh. A change to the stages, the materials or the
project name keeps the mesh. Any other change to the model removes it.

The **Mesh properties** window has these settings:

| Setting | What it does |
|---|---|
| Layer mesh sizes | Every layer is meshed, and each layer can have its own target size. A layer or a soil surface that a line splits has one row for each part, named as in the Model explorer. A layer with no size of its own shows the global size and follows it. Type a value to give the layer its own size. **Band** is the distance outside the layer over which its size grows back to the global size. Styx meshes the layers together, so their shared faces have common nodes. To leave a part out of the mesh, remove it from the model. |
| Object mesh sizes | The element size at each structure, anchor, interface, normal load, soil line, load, condition on a line or at a point, and face of the model, and its **Band**: the distance over which the size grows back to the global size. Empty: the object takes the size of the mesh around it. With the layers, these rows cover every node group that the Kratos input file has. |
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
**Mesh** → **Clear mesh**, the tool under **Generate mesh** on the tool rail, or the command
`clearmesh` removes the mesh from the view. The mesh settings and the local mesh sizes stay,
so <kbd>F9</kbd> makes the same mesh again.

### A finer mesh at one object

You can give a finer mesh to a layer, a soil body, a sheet pile, an anchor, an interface,
a normal load, a soil line, a load (point, line or surface), a boundary condition, or a face
of the model. Select the object. The **Mesh** group of the Selection explorer then shows two
rows:

- **Mesh size**: the element size at the object. *global* means that the object has no
  size of its own.
- **Band**: the distance over which the size grows back to the global size. With a band of
  0, the size applies on the object only, and the mesh next to it changes size as Gmsh
  chooses. A point with a band of 0 gets its size within one element of it.

Click **Use the global size** to remove the object's own size. **Mesh** → **Refine mesh**
halves the size of the selected object, **Coarsen mesh** doubles it, and **Reset local
refinement** removes it. The same tools are on the tool rail in Mesh mode. A tool keeps the
band. If a mesh is shown in Mesh mode, the tool makes the mesh again, so you see the change
at once, and the object stays selected, so you can click the tool again.

Some objects use the size of another object:

- An anchor is one element. Its size applies at its head, where it connects to the
  structure. A free tail is a node of the soil mesh; a fixed end is a point outside
  the mesh.
- A condition on a face uses the size of that face. All conditions on the same face share
  one size, because the Kratos input file has one node group for each face. The Mesh group
  of the condition shows **Size of** with the name of the face. The faces are also in the
  **Mesh properties** window, also the top face, which often has no condition.
- A condition on a soil part uses the size of that part.
- A condition on the whole soil has no size of its own. The whole soil uses the global
  element size.

For example, select the sheet pile, type 0.5 in **Mesh size** and 45 in **Band**: the
elements are 0.5 m along the wall and round its toe, and grow to the global size 45 m away.
A band only makes the mesh finer: on a size that is larger than the global size, it does
nothing.

A model from an older version can have a refinement box (`mesh.refinements`). Styx still
meshes it. To add one, use `kratos-cli add` or a model script.

A mesh size belongs to its body. An edit that takes a body away also removes the body's
size: for example, deleting a layer or a structure, or moving a layer boundary so that
a soil part is no longer in any layer. The Session log names each size that was
removed, and its value. If the body comes back later, for example when you move the
boundary back, set its size again, or use undo to get the body and its size back.

To see the numbers of the nodes or the elements, right-click in the viewport and select
**Show labels**. The numbers show on the mesh in the Mesh tab, and on the result mesh in
Results. The other tabs do not show the mesh, so they do not show the numbers. To show a part of the mesh in its own colour, type `colour <part>`. To see
the parts that contain a node, type `node <id>`.

## Staged construction mode

A construction stage is one step of the calculation. In each stage, parts of the model are
on (active) or off. A stage starts from the result of the stage before it.

> Stages were called *phases* before Styx took Kratos' word for them. A project saved with
> a `phases` list opens unchanged, and the command box still answers `phases`. Styx saves
> the project with `stages`, which older versions of Styx cannot read.

### Make the stages

A new project has one stage, the **Initial stage**. It chooses the calculation type and
the stress initialisation of the whole sequence, and it cannot be deleted, nor can a stage
be inserted before it. Click **Add stage** at the top of the Stages explorer to add the
other stages, for example one to install the wall and one for each excavation lift. A
project saved without stages gets its initial stage from the first **Add stage**.

Use the buttons at the top of the Stages explorer to change the sequence:

| Button | What it does |
|---|---|
| Add stage | Adds a stage at the end |
| Insert stage | Adds a stage above the selected stage |
| Duplicate | Makes a copy of the selected stage |
| Delete | Deletes the selected stage |
| Stages… | Opens the **Stages** window with the settings of each stage |

The **Stages** window has the same four buttons (Add stage, Insert stage, Duplicate and
Delete) above its list of stages, so you can change the sequence without closing it. A new
stage is selected, so you can set it up next.

### Switch parts on and off

1. Select a stage in the Stages explorer.
2. In the Model explorer, select or clear the check box of a part. Or right-click the part
   in the viewport and click **Activate in** *stage* or **Deactivate in** *stage*.

A click on a part in the viewport only selects it. A part that is switched off in the
selected stage is shown faint, so you can right-click it to switch it on again.

The change is made in the selected stage only. The other stages keep what they had. A
stage that you add later starts with the parts of the stage before it.

### Switch water conditions on and off

A water pressure condition is on in every stage until a stage switches it off. In
Staged construction mode, each water pressure condition under **Model conditions** →
**Boundary conditions** has a check box for the selected stage, as a part has. For
example, to lower the water from a level at -1 m to a level at -6 m in stage 3:

1. Add a second hydrostatic condition with its **Reference level** at -6 m. It is on in
   every stage.
2. Select each stage before stage 3, and clear the check box of the -6 m condition.
3. Select stage 3 and each stage after it, and clear the check box of the -1 m condition.

As for a part, a check box changes the selected stage only. A stage that you add later
starts with the check boxes of the stage before it.

The viewport shows the water conditions that the selected stage has on. A stage with no
water condition on keeps the water pressures that the stage before it ended with, for a
**Hydrostatic** or **Phreatic line** condition. A **Uniform** condition does not keep its
values: after its stage, the water pressure of a soil that couples it to the deformation is
free, and the export warns about it. You cannot delete a condition that a stage switches;
clear its check boxes first. The supports are on in every stage.

### Stage settings

In the **Stages** window, select a stage and set:

- **Name** and **Start from stage**
- **Calculation type**: **Mechanical (U-Pw)** (the deformation of the soil, with the
  water pressure in it) or **Flow (Pw)** (the flow of the water alone). You choose it in
  the initial stage, and every stage has it: a later stage shows it, but cannot change it.
- **Stress initialisation**, in the initial stage of a mechanical sequence only: **K0
  procedure** (the initial stresses from the self weight and each soil's K0), **Gravity
  loading** (the initial stresses calculated under the self weight, the default), or
  **None** (no initial stresses, and no self weight in any stage). K0 and gravity loading
  put the self weight on every body, the structures too, in every stage.
- **Time integration**: **Static** or **Dynamic**. A dynamic mechanical stage includes
  inertia; a dynamic flow stage is a transient flow.
- **Damping**, for a dynamic mechanical stage on the Newmark scheme: the **Rayleigh
  mass damping** (alpha) and **Rayleigh stiffness damping** (beta), both 0 until you set
  them.
- **Start time**, in the initial stage only: when the calculation starts, 0 unless you
  set it. A later stage shows its start time, where the stage before it ends, but cannot
  change it (`kratos-cli stages PROJECT set STAGE --start-time`, on the initial stage).
- **Stage duration** and **Time step**: how long the stage lasts and the step Kratos
  solves it in, both in the project's unit of time.
- **Reset displacements to zero**
- **Convergence criterion**: what Kratos checks to decide that a stage has converged. A
  mechanical stage converges on the **Residual** (the default) or the **Displacement**; a
  flow stage on the **Water pressure** (the default) or the **Residual**. A flow stage
  of a project saved before the criterion could be chosen keeps the Residual it was
  solved on. Changing the
  calculation type gives a stage on the other type's criterion the new type's default. The displacement criterion measures the water pressure too, so in a
  coupled soil whose water pressure builds up it may not converge where the residual one
  does; a flow stage with a seepage face that does not converge on the water pressure
  may converge on the residual.
- **Max iterations**, **Tolerated error** (the relative tolerance of the convergence
  criterion) and **Absolute tolerance** (1e-9 for the residual criterion, 1e-12 for the
  displacement one, 1e-8 for the water pressure; changing the criterion changes it to
  the new one's default unless you set your own)

**Expert settings**, below these and closed until you open them, are the rest of the
solver settings Kratos reads. Only the settings that apply to the stage are shown. Each
has the default for the stage's calculation type and time integration until you change
it. A changed setting is shown in bold, and ↺ beside it puts the default back.

- **Strategy**: **Newton-Raphson** (the default for a mechanical stage),
  **Quasi-Newton**, **Newton-Raphson with line search** or **Linear (one solve)**, each
  with its own settings. A flow stage's default is the one its soil calls for: one
  linear solve for a saturated soil, Newton-Raphson for a soil with another retention
  law. A flow stage with a seepage face always uses Newton-Raphson with seepage, tried
  once per step: you see it, but cannot change it. A linear stage has
  nothing to converge, so it has no convergence criterion, iterations or tolerances.
- **Linear solver**: **Sparse LU** (the default, scaled) or **Skyline LU** (direct),
  **AMGCL**, **BiCGStab** or **CG** (iterative), each with its own settings. CG needs a
  symmetric system, as a flow stage's is. The quasi-Newton strategy
  factorises the stiffness matrix once with Sparse LU and reuses it, so with that
  strategy you see Sparse LU, but cannot change it. Kratos does not scale it: a fully
  coupled soil with a very low permeability then settles a few percent too little, so
  use Newton-Raphson for such a soil.
- **Time step control**: how much Kratos enlarges a step that converges in few
  iterations, up to the **Largest step** (a multiple of the time step), and how it cuts
  a step that does not converge and tries it again, if **Attempts per step** is more
  than one (the default),
  until a step is smaller than the **Smallest step** (a fraction of the stage's
  duration), where the stage stops.
- **Time integration**, for a dynamic stage only: **Newmark** (the default) or
  **Backward Euler**, and the Newmark coefficients. A mechanical stage on Backward Euler
  is integrated in time without inertia, Kratos' quasi-static U-Pw, which is the only
  one Kratos has Backward Euler for; it has no Rayleigh damping.
- **Assembly**: the block builder, reforming the degrees of freedom at each step,
  computing the reactions, and the updated mesh of a mechanical stage.

Changing the calculation type puts every stage's expert settings back to the new
type's defaults. A copied stage has the expert settings of its original.

A stage that repeats the stage before it without changes, a *null step*, is a stage that
switches nothing on or off.

A **Flow** stage calculates a flow of the water through the soil, a steady state when it
is static. It calculates the water pressure only, so the soil does not move and it has no
stress initialisation:

- Choose Flow in the initial stage: every stage then has it.
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

## Calculate

> [!IMPORTANT]
> Calculate needs Kratos. Set it up first with [KRATOS_SETUP.md](KRATOS_SETUP.md).

Click **Calculate** in the toolbar, or press <kbd>F9</kbd> outside Mesh mode. Styx then:

1. uses the mesh of the model, or makes one if there is no mesh yet,
2. writes the Kratos input files into a new run folder in `~/KratosGUI/runs`,
3. runs Kratos, and
4. opens Results mode when Kratos is done.

If you made the mesh in Mesh mode, or an earlier calculation made it, and the model did not
change since, Calculate uses that mesh and does not mesh again. The log shows *Writing the
deck from the existing mesh and running Kratos…*. If there is no mesh yet, the log shows a
warning: Calculate makes the mesh with the global settings of **Mesh properties**. To check
the mesh before you calculate, make it in Mesh mode first.

While Kratos runs, the **Convergence** window shows each iteration of the solver (see
[Follow the solver](#follow-the-solver)). You can run one calculation at a time. If a stage
fails, the log shows which stage failed and why, and the Stages explorer shows which stages
finished.

### Stop a calculation

While Kratos runs, the **Calculate** button in the toolbar is a red **Stop** button. Click it
and then **Stop calculation** to stop Kratos at once. The **Convergence** window has the same
button, and the **Stages** menu has **Stop calculation**. To stop without the question, type
`calculate stop` in the command box.

When you stop a calculation:

- your model does not change, and Styx stays in the mode you were in;
- the run folder keeps the input files, the log and the results of the stages that finished,
  so you can still open them in Results mode;
- the log says *Calculation stopped after 41 s, in stage 3 of 7*, and the Stages window marks
  that stage *Stopped by the user*.

<kbd>F9</kbd> does not stop a calculation, so a key pressed twice cannot end a long run.

Styx never overwrites or deletes a run folder. See
[What a calculation writes](KRATOS_SETUP.md#what-a-calculation-writes).

### Follow the solver

When you click **Calculate**, the **Convergence** window opens at the bottom right. It shows
how the solver converges while Kratos runs, so you can see early if a stage has problems.
You can move the window, and make it bigger with its bottom-right corner: the plot grows
with it. If you close the window, the run continues. To stop the run, click
**Stop calculation** (see [Stop a calculation](#stop-a-calculation)).

After each iteration, Kratos compares two values with their targets: a relative value and
an absolute value. The criterion is met when one of the two is below its target. What the
values measure depends on the stage's convergence criterion:

| Criterion | What Kratos compares |
|---|---|
| Residual | The force that is still out of balance |
| Displacement | The change of the displacements in the iteration |
| Water pressure | The change of the water pressures in the iteration |

Each stage has its own criterion, so one run can use more than one. The plot draws each
criterion in its own colour, and the legend names them. When all stages use the same
criterion, the axes name it too, for example *Relative residual*.

The top of the window gives the stage that runs and the last values in words, for example
*Iteration 57 (stage 3, step 2, iteration 5 of the step). Relative residual 3.2e-03 (target
1.0e-04).* The first number counts the iterations of the whole run, as the horizontal axis
of the plot does. Below it, the plot has two panels:

| Item | What it shows |
|---|---|
| Upper panel | The relative value of each iteration, on a log scale |
| Lower panel | The absolute value of each iteration, on a log scale |
| Horizontal axis | The iteration number, counted over all stages (from 0 in the stage, when one stage is shown alone) |
| Dashed line | The target |
| Green X | An iteration where the criterion was met |
| Red mark after an iteration | A step that reached the maximum number of iterations, or that Kratos cut back to a smaller step |
| Red dot on the top edge | A residual that is not a number (`nan`) or infinite: the solution diverged |
| Grey bands | The stages, with the stage name where it fits |
| Red line and right axis | The fraction of unbalance, from 0 to 1. Kratos prints it only when the stage uses load stepping, so most runs do not show it. |

Point at a dot to see its stage, step, iteration and values. Point at a stage name to see
its criterion.

With many stages, the early stages are narrow. If the run has two stages or more, use the
**Show** slider under the status line to show one stage alone: move it to the right to go
through the stages one by one, and back to the left end for all stages. A stage shown
alone has its own horizontal axis: it starts at 0 and counts the iterations of that stage.
Point at a dot to see its number in the whole run too. You can also type
`results convergence stage 3`, or
words of the stage name such as `results convergence stage first excavation`, and
`results convergence stage all`.

When the run ends, the window stays open. It says *Finished in 12.3 s*, or the stage where
the run stopped. Styx opens Results mode and shows the last stage. To choose a different
result, use the Results explorer in the dock, or click **Choose results** in the tool rail.

If the window says *Kratos printed no residuals*, the deck has `echo_level` 0 in
`solver_settings`. Styx writes 1. In an existing Kratos deck, set it to 1 in
`ProjectParameters.json`, and calculate again.

To see the plot of a run later, also of a run that failed, do one of these:

- Click **Results** → **Convergence…**.
- In Results mode, click **Convergence** in the tool rail.
- Type `results convergence`.

Styx shows the run that Kratos works on, else the open run, else the newest run.

To save the plot, click **Save ▾** in the window and choose a format. **PNG**, **PDF** or
**SVG** saves the figure, and **CSV** saves one row for each iteration, with the criterion
of that iteration in the `criterion` column. The file is of the run and the stages that the
window shows. When one stage is shown alone, its number is in the file name, for example
`Pit_A_2026-10-12_09-14_convergence_stage_3.csv`.

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

When you open Results mode, Styx shows the result at once: the last stage of the run.
Styx does not open the **Choose results** window by itself. To change what is shown, use
the Results explorer, or click **Choose results** in the tool rail:

| Setting | What it does |
|---|---|
| Stage | The construction stage to show |
| Field | The quantity, in groups: deformations, stresses, water pressure and head, groundwater flow, saturation, nodal forces |
| Location | Only for a field computed at the integration points (a stress, the hydraulic head): **per element**, as Kratos computed it, or **averaged to the nodes** for a smooth contour. The choice holds for all of them. |
| Arrows | Only when the stage has a vector (displacement, flux, reaction): off, or one of the stage's vectors as arrows over any field, for example the flux over the hydraulic head |
| Shading | Smooth colours, or 8 to 48 colour bands |
| Colours | The colour map, for example Rainbow, Viridis or Greyscale |
| Limits | The minimum and maximum of the legend. **Auto** uses the range of the field. |
| Reverse | Turns the colour map around |
| Mesh | Shows the element edges over the colours |
| Loads, water | Shows the loads and the water level over the colours (on by default) |
| Zero pressure | Shows the line where the pore pressure is zero (off by default). Only for a coupled stage: after a groundwater flow stage the line is always shown. |
| Deformed | Shows the deformed mesh: off, automatic scale, true scale, ×10 or ×100 |

Compression is negative, as Kratos writes it. Each value is in the unit system of the run:
stresses in Pa for SI, or in kPa for kN.

The loads and the water level are those of the open project, as they are in the stage on
screen: a load that the stage switched off is not shown. They are shown only when the run
was calculated from the open project, with the same stages. They stay where they are in the
model, also when the mesh is shown deformed. Type `results loads off` to hide them.

When you go to a different tab and then back to Results, Styx shows the same result again.
The wall plot opens again if it was open when you left. The **Choose results** window does
not: click **Choose results** in the tool rail to open it.

After a groundwater flow stage a dark line shows where the calculated pore pressure is
zero: the phreatic surface the flow calculation found. After a coupled (mechanical) stage
the line is hidden until you tick **Zero pressure**, or type `results zeroline on`. The
line is drawn only when the stage wrote a pore pressure.

The arrows are black. The longest is 4 % of the model, and the others are to the same
scale. On a fine mesh one node in each square of that size gets an arrow. The legend
says which vector they show and its largest value. Type `results arrows flux` to draw the
flux over any field, `results arrows on` for the vector of the field on screen (or the
stage's first vector when that field is not part of one), and `results arrows off` to
hide them.

The nodal water flow rate (**Groundwater flow**) is the water that leaves the model at a
node, per metre of the section: positive out, negative in. It is not zero only where the
water pressure is fixed. When you show it, the Session log gives the water that goes out,
the water that comes in, and the difference: zero in a steady state, and in a transient
stage the water that the pores stored. The reactions (**Nodal forces**) are added up the
same way: the sum of R_y is the vertical force the supports carry.

### Other results

- **Plot along the wall:** click **Plot wall…**, or type `results plot`. The plot shows the
  bending moment (M), the shear force (Q), the normal force (N), the horizontal displacement
  (ux) and the interface tractions (tn, ts) against depth, with one line for each stage.
  Each face of the wall has its own tractions. They show only where the contact is on in
  that stage, so the face a pit is dug against starts at the pit floor.
  Click **Save ▾** and choose a format: **PNG**, **PDF** or **SVG** saves the figure, and
  **CSV** saves the numbers. The plot of an interface is saved in the same way.
- **Convergence of the solver:** click **Convergence** in the tool rail, or type
  `results convergence`. See [Follow the solver](#follow-the-solver).
- **Values at a node:** click **Results** → **Value at a node…**, type the node number in
  the small window and click **OK**. Or type `results at <node>`. The values appear in the
  Session log.
- **Save the field as CSV:** click **Save CSV**, or type `results csv`.
- **Save the full run:** click **Download run**, or type `results zip`.

## Save pictures

A picture shows the parts that the viewport shows, on a white background, with white space on each
side of the model. It shows the whole model, also if you zoom in or pan. To save what the screen
shows, zoomed in on a detail or zoomed out, select **Use the zoom of the screen**. The view
buttons, the mode label, the
selection box and the highlight of a selected object are not in the picture. The symbols that you
show by selecting a condition are in the picture.

The other parts are outside the view, so they never cover the model:

| Part | Where | When |
|---|---|---|
| Stage number and name | Above the view | Staged construction and Results |
| Rulers | Left and bottom of the view | 2D |
| Axes | Below the view, at the left | When **Axes** is selected |
| Field name, and its maximum and minimum value with the node or element | Below the view, in the middle | Results |
| Legend, with the unit | Right of the view, low | Results, when **Legend** is selected |

### Copy a picture

1. Right-click in the viewport.
2. Click **Copy picture**.
3. Paste the picture into your document.

The picture on the clipboard is 16 cm wide at 300 dpi (1890 pixels). The clipboard does not
keep the dpi value, so your document can show the picture at a different size. To get the
correct size, save a PNG file.

Copying works when the address of Styx is `localhost`, `127.0.0.1` or `https`. On other
addresses **Copy picture** is grey.

### Save pictures to files

1. Show what you want to save: for example, open the **Mesh** tab, or select a stage in the
   **Staged construction** tab.
2. Click the camera in the toolbar, or click **File** → **Save picture…**, or right-click in
   the viewport and click **Save picture…**.
3. Set the options, then click **Save…**.
4. In the system window, choose the location.

| Option | What it does |
|---|---|
| Format | PNG, PDF and SVG. You can select more than one. |
| Width | The width of the picture in cm, 16 by default, with the legend. The height follows the shape of the model in all its stages. The resolution is 300 dpi. |
| Pictures | **This view**, or more than one picture: see [Save every stage or field](#save-every-stage-or-field) |
| PDF files | Only when you select **PDF** and more than one picture: **One PDF file for each picture**, or **All pictures in one PDF file, one per page** |
| Show | The legend, the rulers (2D), the axes and the grid. **Grid** can be selected only when the grid is on in the viewport. |
| Zoom | **Use the zoom of the screen**: the picture shows what is on the screen, and leaves out what is off it. This option is off each time that you open the window. |
| Also save | In Results mode: the values of each field as a CSV file |

One file opens the browser's save window, also for one PDF file with many pages. More than one
file opens the system folder window, and all the files go in that folder. You can select any folder that you can write to, such as
Downloads or Desktop. If a file exists in the folder, Styx asks one time if it can overwrite the
files.

If you do not see the folder window, look behind the browser or in the taskbar. Only one folder
window opens at a time. If you do not choose a folder in 10 minutes, the window closes and
nothing is saved.

If Styx runs on another computer, the browser's own folder window opens. Chrome and Edge can refuse
some folders in that window, such as Downloads or Desktop themselves. If this occurs, select a
subfolder. A browser without that window, such as Firefox, puts one zip file in the Downloads
folder.

### Save every stage or field

In the **Staged construction** tab, select **Every stage**. Each picture shows the stage with
its own active parts.

To get one document, select **PDF** and **All pictures in one PDF file, one per page**. If you stop
the save, the file has the pages that were ready.

All the pictures of the stages of a model have the same size, with the model in the same place,
also if you save them one by one. The frame is large enough for what each stage draws, so a stage
with no load has the same frame as a stage with a load. Pictures of the other tabs, such as
**Soil** and **Mesh**, have this frame too, with space above the view where a stage picture has its
title. In 3D, the frame follows the direction that you look from. In Results, to find this frame,
Styx goes through the stages before it saves or copies a picture, so the viewport changes for a
moment.

A picture in Results shows the same part of the model, but it has a different size and a smaller
model. The legend takes 24 mm of the width, and the field name and its values go below the view. A
deformed shape that goes past the frame makes the frame larger in Results.

In Results mode, select **Every stage**, **This stage, every field** or **Every stage, every
field**. The colour map, the bands and the other display settings stay as they are on screen.
A stage that has no results is not saved. To stop, click **Stop** in the viewport. After the
save, the viewport shows the same stage and field as before.

### What is in each format

| Format | Lines and text | Colours |
|---|---|---|
| PNG | Pixels at 300 dpi | Pixels at 300 dpi |
| SVG, PDF in 2D | Vector: you can scale and edit them | Flat faces are vector. Contour colours are an image at 300 dpi. |
| SVG, PDF in 3D | Vector | All faces are an image at 300 dpi |

PDF text uses Helvetica and Symbol. A character that is not in these fonts shows as `?`, and
the Session log says so. PNG and SVG keep all characters.

### Type the command

The window runs these commands, and you can type them in the command box:

```text
picture                                     opens the window
picture copy
picture save --format png,pdf,svg --width 12
picture save --format svg --stage all --field all --csv
picture save --format png --no-legend --no-rulers --no-axes --grid
picture save --format png --screen-zoom
picture save --format pdf --stage all --one-pdf
```

`picture save pdf` is short for `picture save --format pdf`. `kratos-cli picture` takes the
same words and makes the same pictures in a terminal: see [CLI.md](CLI.md#pictures).

## The command box

Type a command in the command box below the log, and press <kbd>Enter</kbd>. Use
<kbd>↑</kbd> and <kbd>↓</kbd> to get earlier commands again. Type `help` to see the list.

| Command | What it does |
|---|---|
| `run <file.py>` | Builds the model from a Python script |
| `script <file.py>` | Writes the model as a Python script |
| `export` | Writes the Kratos input files, as **File** → **Export model…** |
| `mesh` | Makes the mesh |
| `clearmesh` | Removes the mesh from the view; its settings stay |
| `calculate` | Calculates the model, as the **Calculate** button |
| `calculate stop` | Stops the calculation that runs, without asking first |
| `stages` | Opens the **Stages** window |
| `water <level>`, `water off` | Sets or removes the water level |
| `boundary`, `boundary standard` | Lists the boundary conditions, or puts the standard supports back |
| `gravity`, `gravity 9.80665` | Shows whether the self weight acts, or sets g in m/s² |
| `units`, `units SI`, `units kN` | Shows or changes the unit system |
| `soillayers`, `materials` | Opens the **Modify soil layers** or **Soil materials** window |
| `cleargeometry` | Removes all drawn and imported solids |
| `colour <part>`, `colour all`, `colour off` | Shows parts of the mesh in their own colour |
| `node <id>` | Shows the parts that contain a node of the mesh |
| `gotosoil`, `gotostructures`, `gotomesh`, `gotoflow`, `gotostaged` | Opens a mode |
| `view iso`, `view top`, `view front`, `view side`, `zoomfit` | Changes the view |
| `clear` | Clears the log |
| `results …` | Works with results. Type `results` alone to see all its forms. |

**Help** → **Command reference** shows the same list in a window. **Help** → **Kratos
documentation** opens the Kratos GeoMechanics user documentation in a new browser tab.

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
