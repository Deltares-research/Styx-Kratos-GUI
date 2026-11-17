# Build the CROW excavation wall in the GUI

In this tutorial you build a staged sheet-pile excavation in the Styx GUI, from an empty
project to the bending moment in the wall and the stresses in the soil. You use only the
windows, the tool rail and the explorers of the GUI. The tutorial is for a geotechnical
engineer who has not used Styx before.

The model is the CROW excavation wall with Mohr-Coulomb soils. It is the same model as the
[`kratos-cli` tutorial of the CROW case](https://github.com/Deltares-research/Styx-Kratos-GUI/blob/main/docs/cli_tutorials/CROW_case.md), and Kratos uses the
same case to validate its GeoMechanicsApplication.

Each step has a screenshot. An orange outline on the screenshot shows the button, field or
row to use.

## What you build

A 2D plane-strain section, 80 m wide and 60 m deep. All values are in SI units: m, N, Pa
and kg/m³. The y axis points up, so a depth of 8 m is y = −8 m.

```text
             x = 0       x = 5                                         x = 80
                           ↓ ↓ ↓ ↓ ↓ ↓  surcharge 20 kN/m  ↓ ↓ ↓ ↓ ↓ ↓
  y = 0        +-----------+--------------------------------------------+
               |  lift 1  =|  strut at -1.5      water table at -1.5    |
  y = -2       | - - - - - |                                            |
               |  lift 2   |                                            |
  y = -5       | - - - - - |  Clay                                      |
               |  lift 3   |                                            |
  y = -8       +-----------+--------------------------------------------+
               |           |  Clay                                      |
  y = -12      +-----------+--------------------------------------------+
               |           '  wall toe at -13                           |
               |              Sand                                      |
  y = -60      +--------------------------------------------------------+
         symmetry plane
```

- A sheet pile wall at x = 5 m, from the ground surface down to y = −13 m.
- A strut at y = −1.5 m, which holds the wall from the pit side.
- The pit, between the wall and the symmetry plane at x = 0, is dug in three lifts: to −2 m,
  −5 m and −8 m.
- The water table is at −1.5 m. A surcharge of 20 kN/m is on the retained side.
- Seven calculation stages: the initial stresses (K0), a null step, the wall, the first
  lift, the strut, the second lift and the third lift.

## Before you start

- Install Styx and start it with `run.bat` (Windows) or `run.sh` (Linux and macOS). See
  [INSTALLATION.md](https://github.com/Deltares-research/Styx-Kratos-GUI/blob/main/docs/INSTALLATION.md). Styx opens in your browser with an empty 2D project.
- Step 13 calculates the model, and for that Styx needs Kratos. If Kratos is not set up
  yet, follow [KRATOS_SETUP.md](https://github.com/Deltares-research/Styx-Kratos-GUI/blob/main/docs/KRATOS_SETUP.md). You can do steps 1 to 12 without
  Kratos.

How the GUI takes the values that you type:

- In a window with a **Save** or **OK** button, the window keeps your values until you
  click that button. **Cancel** leaves the model as it was.
- In the Soil material window and in the Selection explorer, a value is used when you
  leave the field (press Tab) or press Enter.
- The decimal sign is a point (`.`).
- The Styx server keeps the project in its memory. Save it at the end (step 15), or at any
  time with **File** > **Save**.

## 1. Start a new project

1. On the toolbar, click **New project** (the first button).
2. In **Project name**, type `CROW excavation wall`.
3. Click **OK**.

![The New project window with the project name typed in. The New project button on the toolbar is outlined.](images/crow/01_project.png)

The title bar shows the project name. A new project is a 2D section, so the **2D** button
on the toolbar is already selected. **File** > **Project properties…** shows the
gravitational acceleration g = 9.81 m/s². Keep that value.

## 2. Make the two soils

A soil in Styx is a Kratos material: a constitutive law (the soil model) and its variables.
The model has two Mohr-Coulomb soils:

| Field | Clay | Sand |
|---|---|---|
| **Identification** | `Clay` | `Sand` |
| **Colour** | any, for example `#c4a86a` | any, for example `#b08a6a` |
| **Soil model** | Mohr-Coulomb | Mohr-Coulomb |
| **Drainage type** | Mechanical only | Mechanical only |
| **Young's modulus** (Pa) | `900000` | `7428600` |
| **Poisson's ratio** | `0.2` | `0.3` |
| **Density of the solid** (kg/m³) | `1834.86` | `2038.74` |
| **Porosity** | `0` | `0` |
| **Retention law** | SaturatedBelowPhreaticLevelLaw | SaturatedBelowPhreaticLevelLaw |
| **Saturated saturation** | `1` | `1` |
| **Residual saturation** | `1e-10` | `1e-10` |
| **Cohesion** (Pa) | `3000` | `0` |
| **Friction angle** (°) | `22.5` | `32.5` |
| **Dilatancy angle** (°) | `0` | `0` |
| **Tension cut-off** | cleared | cleared |
| **K0, normally consolidated** | `0.62` | `0.46` |
| **Rinter** | `0.48021693505171` | `0.571318827227732` |

- Kratos calculates the unit weight of the soil from the density of the solid
  ρ<sub>s</sub>, the density of the water ρ<sub>w</sub> and the porosity n:

  - Dry unit weight: γ<sub>dry</sub> = (1 − n) · ρ<sub>s</sub> · g
  - Saturated unit weight: γ<sub>sat</sub> = ((1 − n) · ρ<sub>s</sub> + n · ρ<sub>w</sub>) · g

  With n = 0, the two are the same: γ = ρ<sub>s</sub> · g. The densities in the table give
  γ = 18 kN/m³ for the clay and 20 kN/m³ for the sand, the unit weights of the CROW case.
- The **Mechanical only** drainage type solves the displacements with an imposed pore
  pressure, which you give in step 4. It does not calculate groundwater flow.
- **Rinter** reduces the strength of the soil along interfaces (step 9). It is
  tan δ / tan φ, where δ is the wall friction angle (11.25° for the clay, 20° for the sand)
  and φ is the friction angle of the soil.

To make the soils:

1. Click the **Soil** tab.
2. On the tool rail, click **Soil materials…**.
3. Click **Create soil**. The Soil material window of the new soil opens.
4. Type the values of the clay from the table. Scroll down to see all fields.
5. Click **Close**.
6. Do steps 3 to 5 again for the sand.
7. In the Soil materials window, click **OK**.

![The Soil materials window, with the Soil materials tool and the Create soil button outlined.](images/crow/02_soils.png)

The top of the Soil material window of the clay:

![The Soil material window of the clay, from its top: identification, soil model, drainage type, stiffness and weight.](images/crow/02_soils_clay.png)

The strength, K0 and Rinter of the clay, further down in the same window:

![The Soil material window of the clay, scrolled down. The cohesion, friction angle, dilatancy angle, K0 and Rinter fields are outlined.](images/crow/02_soils_clay_strength.png)

The sand, from the top of its window:

![The Soil material window of the sand, from its top.](images/crow/02_soils_sand.png)

## 3. Add the soil layers and set the width

The layers are stacked from the ground surface down. The clay is split at −8 m, so that the
floor of the third lift is on a layer boundary.

| Layer | Material | Bottom (m) |
|---|---|---|
| `Soil_Top` | Clay | `-8` |
| `Soil_Middle` | Clay | `-12` |
| `Soil_Bottom` | Sand | `-60` |

1. On the tool rail, click **Modify soil layers…**.
2. Click **Add** three times. The window adds three layers.
3. For each layer, type the name in **Layer**, select the material, and type the bottom
   level in **Bottom [m]**. The top of each layer follows from the layer above it.
4. Click **OK**.

![The Modify soil layers window with the three layers. The Modify soil layers tool is outlined.](images/crow/03_layers.png)

No window sets the width of the model. Set it in the Selection explorer of a layer:

1. In the Model explorer, click **Soil_Top**.
2. In the Selection explorer, type `80` in **x max** and press Enter.

![The model after x max is set to 80 m. The Soil_Top row in the Model explorer and the x max row in the Selection explorer are outlined.](images/crow/03_layers_width.png)

All layers are now 80 m wide.

## 4. Give the soil its water pressure

The water table is at y = −1.5 m in all stages. Below the water table the pore pressure is
hydrostatic: it is zero at the water table and grows by 10 kPa per metre of depth. Above
the water table the pore pressure is zero.

1. Click the **Structures** tab.
2. On the tool rail, click the small arrow in the corner of **Create boundary condition**,
   then click **Create boundary condition…**.
3. In **Name**, type `Pore pressure`.
4. In **Condition**, select **Water pressure**.
5. In **Where**, select **Whole soil**.
6. In **Type**, select **Hydrostatic**, and in **Reference level**, type `-1.5`.
7. Click **Save**.

![The Create boundary condition window for the water pressure. The Create boundary condition tool is outlined.](images/crow/04_water.png)

A new project already has the displacement conditions: the bottom is fixed, and the left
and right sides are fixed in the horizontal direction only. The Model explorer now shows
four boundary conditions.

## 5. Add the sheet pile wall

The wall is a plate 0.4924 m thick, per metre of wall. Its section values are Kratos
variables in SI units:

| Field | Value | What it is |
|---|---|---|
| **Name** | `SheetPileWall` | |
| **x1**, **y1** | `5`, `0` | the top of the wall (m) |
| **x2**, **y2** | `5`, `-13` | the toe of the wall (m) |
| **YOUNG_MODULUS** | `8444900000` | E (Pa) |
| **POISSON_RATIO** | `0` | ν |
| **DENSITY** | `298.36` | density (kg/m³) |
| **CROSS_AREA** | `0.4924` | A (m²) |
| **I33** | `0.009948850085333335` | I = t³ / 12 (m⁴) |
| **AREA_EFFECTIVE_Y** | `10000` | a large shear area, so the wall has no shear deformation (m²) |
| **Spacing** | `1` | 1 m of wall per metre out of plane, for plane strain (m) |

The thickness 0.4924 m is not the real thickness of the steel. It is the thickness of a
solid plate that has the same bending stiffness EI and axial stiffness EA as the sheet
pile. For that reason, the density is low: ρ · A = 298.36 × 0.4924 ≈ 147 kg per m² of
wall, close to the mass of a steel sheet pile. The values are those of Kratos' own CROW
test.

1. On the tool rail, click **Create sheet pile…**.
2. Type the values from the table. Scroll down to see all fields.
3. Click **Save**.

![The Create sheet pile window. The Create sheet pile tool is outlined.](images/crow/05_wall.png)

The wall cuts `Soil_Top` and `Soil_Middle` in two parts each. `Soil_Bottom` stays whole,
because the wall ends inside it.

## 6. Draw the floors of the first two lifts

A line that crosses a soil layer from one edge to another splits the layer into separate
soil parts. A stage can then switch each part off. Two lines make the floors of the first
and the second lift. The floor of the third lift is the boundary between `Soil_Top` and
`Soil_Middle`.

You can make a line in two ways. This step shows both.

Draw the first line with points that you type:

1. On the tool rail, click the small arrow in the corner of **Create line**, then click
   **Draw line**.
2. In the command box at the bottom of the window, type `0 -2` and press Enter.
3. Type `5 -2` and press Enter.

   ![The two points of the first line, typed in the command box. The Create line tool and the command box are outlined.](images/crow/06_lines_drawn.png)

4. Press Enter in the empty command box. The Create line window opens with the two points.
5. In **Name**, type `Floor of lift 1`.

   ![The Create line window of the first line.](images/crow/06_lines_drawn_window.png)

6. Click **Save**.

You can also click the points in the viewport. The status bar shows the coordinates of the
cursor, and typed points are exact.

Make the second line in a window:

1. On the tool rail, click the small arrow in the corner of **Create line**, then click
   **Line by coordinates…**.
2. In **Name**, type `Floor of lift 2`.
3. In **Points**, type `0` and `-5` for point 1, and `5` and `-5` for point 2.
4. Click **Save**.

![The Create line window of the second line, with its points typed in. The Create line tool is outlined.](images/crow/06_lines_typed.png)

## 7. Name the soil bodies

The wall and the two lines cut the top two layers into six soil parts. The Model explorer
names them after their layer and a number, for example `Soil_Top · Part 3`:

![The Model explorer with the six soil parts outlined.](images/crow/07_bodies_before.png)

Give each part a name that says what it is. A name makes the stages of step 12 easier to
set up. To see which part a row is, click the row: the viewport shows that part as
selected.

| Row in the Model explorer | Where the part is | New name |
|---|---|---|
| `Soil_Top · Part 3` | in the pit, from 0 to −2 m | `lift 1` |
| `Soil_Top · Part 1` | in the pit, from −2 to −5 m | `lift 2` |
| `Soil_Top · Part 4` | in the pit, from −5 to −8 m | `lift 3` |
| `Soil_Top · Part 2` | behind the wall, from 0 to −8 m | `retained` |
| `Soil_Middle · Part 1` | below the pit, from −8 to −12 m | `below the pit` |
| `Soil_Middle · Part 2` | behind the wall, from −8 to −12 m | `retained` |

For each row:

1. In the Model explorer, right-click the row and click **Rename…**.
2. Type the new name.
3. Click **OK**.

![The Rename window for the first part, with the name lift 1 typed in.](images/crow/07_bodies_rename.png)

After you rename all six parts, the Model explorer shows the new names:

![The Model explorer with the six renamed soil parts outlined.](images/crow/07_bodies_after.png)

## 8. Add the strut

The strut holds the wall from the pit side, at y = −1.5 m. It goes from the wall to a fixed
point 1 m into the pit. There is one strut per metre of wall, with E = 210 GPa and
A = 4.76 × 10⁻⁵ m².

In the finite element model, the strut is a truss element: a straight bar between two
points that carries only an axial force, in tension and in compression. In engineering, a
strut takes compression and an anchor takes tension, but both are the same truss element.
Styx makes this element with the **Create anchor** tool, so you make the strut as an anchor
and then rename it.

1. On the tool rail, click **Create anchor…**. Styx adds an anchor on the wall, named
   `Anchor 1`, and selects it.
2. In the Selection explorer, type these values. Press Enter after each value.

   | Row | Value |
   |---|---|
   | **YOUNG_MODULUS** (Pa) | `210000000000` |
   | **CROSS_AREA** (m²) | `4.7619e-05` |
   | **DENSITY** (kg/m³) | `0` |
   | **Spacing** (m) | `1` |
   | **Head x**, **Head y** (m) | `5`, `-1.5` |
   | **Tail x**, **Tail y** (m) | `4`, `-1.5` |

3. In the **Tension limit** row, click **No tension limit**. Leave **Compression limit**
   empty. The strut then has no force limits.
4. In the Model explorer, right-click **Anchor 1**, click **Rename…**, type `Strut` and
   click **OK**.

![The Selection explorer of the strut. The Create anchor tool and the rows with typed values are outlined.](images/crow/08_strut.png)

The head of the strut is on the wall, so it becomes a node of the wall. The tail is a fixed
support.

## 9. Add the interface along the wall

An interface lets the soil slip along the wall. Here it is on both faces of the wall. Each
part of the interface takes the soil it is against, and reduces the strength of that soil
by the soil's own **Rinter** from step 2.

1. On the tool rail, click **Create interface…**.
2. In **Name**, type `Interface`. **Along** shows **SheetPileWall**.
3. In **Side**, select **Both sides**.
4. Click **Save**.

   ![The Create interface window. The Create interface tool is outlined.](images/crow/09_interface_window.png)

5. In the Selection explorer of the interface, set **Virtual thickness** to `1` and press
   Enter. With a virtual thickness of 1 m, the stiffness of the interface comes directly
   from the shear modulus of the soil, as the next paragraph shows.
6. In **Law**, select **Coulomb**.
7. In the **R_inter** row, click **Each soil's own R_inter**.

![The Selection explorer of the interface. The Law and Virtual thickness rows and the Each soil's own R_inter button are outlined.](images/crow/09_interface_contact.png)

A Coulomb interface slips when the shear stress reaches the reduced strength of the soil.
Styx derives the stiffness of the interface from the soil: the shear stiffness is G / t
and the normal stiffness is 10 G / t, where G is the shear modulus of the soil and t is
the virtual thickness. For the clay, G = 375 kPa, so the shear stiffness is 375 kPa/m and
the normal stiffness is 3 750 kPa/m. The factor 10 makes the interface much stiffer across
the wall than along it: the soil can slip along the wall, but it does not go into the wall
or come away from it. Kratos' reference interface materials use the same factor.

## 10. Add the surcharge and the water loads

The surcharge is 20 kN/m on the retained ground surface, from the wall to the right edge.

1. On the tool rail, click the small arrow in the corner of **Create load**, then click
   **Line load**.
2. Type these values:

   | Field | Value |
   |---|---|
   | **Name** | `Load` |
   | **x min**, **x max** (m) | `5`, `80` |
   | **y** (m) | `0` |
   | **qx**, **qy** (N/m) | `0`, `-20000` |

3. Click **Save**.

![The Create line load window. The Create load tool is outlined.](images/crow/10_loads_surcharge.png)

In each lift, the water in the pit pushes on the soil. Each water load runs along the
floor of its lift, from the symmetry plane to the wall, and then up the face of the wall to
the water table. The pressure is hydrostatic and zero at −1.5 m.

| Name | Point 1 | Point 2 | Point 3 |
|---|---|---|---|
| `WaterLoad_Stage1` | `0`, `-2` | `5`, `-2` | `5`, `-1.5` |
| `WaterLoad_Stage2` | `0`, `-5` | `5`, `-5` | `5`, `-1.5` |
| `WaterLoad_Stage3` | `0`, `-8` | `5`, `-8` | `5`, `-1.5` |

For each water load:

1. On the tool rail, click the small arrow in the corner of **Create load**, then click
   **Normal load**.
2. In **Name**, type the name.
3. Click **Add point** until the window has three points, and type the points in order.
4. In **Type**, select **Hydrostatic (from a water level)**.
5. In **Reference level**, type `-1.5`.
6. Click **Save**.

![The Create normal load window of the first water load. The Create load tool and the Add point button are outlined.](images/crow/10_loads_water.png)

A normal load pushes on the soil on the right side of its line, in the order of the
points. Keep the points in the order of the table, so that the load pushes on the soil
that stays.

## 11. Make the mesh

The mesh is fine along the wall and coarse far from it: 0.5 m elements on the wall, which
grow to 5 m at 30 m from the wall. Use exactly these values. With other values, the strut
stage of this model can fail to converge.

1. Click the **Mesh** tab. The Mesh properties window opens. If it does not open, click
   **Mesh properties…** on the tool rail.
2. In **Global element size**, type `5`.
3. In **Element order**, select **Quadratic · 6-node triangle**.
4. In the **SheetPileWall** row, type `0.5` in **Size** and `30` in **Band**.
5. Click **Apply and generate**.

![The Mesh properties window. The SheetPileWall row with its size and band is outlined.](images/crow/11_mesh_window.png)

On the computer that made this page, the mesh has 1 466 elements and 3 036 nodes, with an
average element size of 2.183 m. Gmsh can make a slightly different mesh on another
computer or operating system, so your numbers can differ a little. The Selection explorer
of the mesh shows them:

![The mesh, fine near the wall and coarse at the far side.](images/crow/11_mesh_mesh.png)

## 12. Set up the seven stages

A stage is one calculation step of the construction. Each stage starts from the stage
before it. In Staged construction mode, the check box of a row in the Model explorer says
whether that object is in the model in the selected stage.

A new project already has the initial stage. It calculates the initial stresses in the
soil. Set it to the K0 procedure:

1. Click the **Staged construction** tab.
2. In the Stages explorer, click **Initial stage**.
3. Click **Stages…**.
4. In **Stress initialisation**, select **K0 procedure**.
5. Click **Close**.

![The Stages window of the initial stage. The Stress initialisation row is outlined.](images/crow/12_stages_window.png)

The initial stage also sets the calculation type of all stages: **Mechanical (U-Pw)**. Keep
it. The K0 procedure makes the initial stresses in the soil without the wall, so switch
off the objects that are not there yet:

1. In the Stages explorer, click **Initial stage**.
2. In the Model explorer, clear the check boxes of **SheetPileWall**, **Strut**,
   **Interface**, **WaterLoad_Stage1**, **WaterLoad_Stage2**, **WaterLoad_Stage3** and
   **Load**.

![The initial stage, with the wall, strut, interface and loads switched off in the Model explorer. The Add stage button is outlined.](images/crow/12_stages_initial.png)

Then add the null step and the five construction stages:

| Stage | Name | Max iterations | Tolerated error | Switch on | Switch off |
|---|---|---|---|---|---|
| 2 | `Null step` | `150` | `0.0001` | | |
| 3 | `Wall installation` | `150` | `0.001` | SheetPileWall, Interface, Load | |
| 4 | `First excavation` | `500` | `0.001` | WaterLoad_Stage1 | Soil_Top · lift 1 |
| 5 | `Strut installation` | `150` | `0.001` | Strut | |
| 6 | `Second excavation` | `300` | `0.001` | WaterLoad_Stage2 | Soil_Top · lift 2, WaterLoad_Stage1 |
| 7 | `Third excavation` | `300` | `0.001` | WaterLoad_Stage3 | Soil_Top · lift 3, WaterLoad_Stage2 |

The null step changes nothing in the model. Kratos' own CROW test has the same stage after
the K0 procedure. The excavation stages have more iterations, because the soil yields
there.

The stage Wall installation also resets the displacements to zero. In the K0 procedure the
soil settles more than 2 m under its own weight. After the reset, the displacements show
only what the construction does. Kratos' own CROW test resets them in the same stage.

For each stage in the table:

1. In the toolbar of the Stages explorer, click **Add stage** (the first button). The new
   stage comes after the last stage.
2. Click **Stages…**. The Stages window opens with the new stage selected.
3. Type the **Name**, the **Max iterations** and the **Tolerated error**. Press Enter
   after each value.
4. For Wall installation only: select **Reset displacements to zero**.
5. Click **Close**.
6. In the Stages explorer, click the new stage.
7. In the Model explorer, select the check boxes of the objects to switch on, and clear the
   check boxes of the objects to switch off.

The Stages window of the stage Wall installation:

![The Stages window of the stage Wall installation. The Reset displacements to zero row is outlined.](images/crow/12_stages_reset.png)

After the last stage, the Stages explorer shows seven stages:

![The stage Third excavation. The Add stage button and the two water loads that it changes are outlined.](images/crow/12_stages_last.png)

## 13. Calculate and look at the wall

1. On the toolbar, click **Calculate**. Styx writes the Kratos input files and runs Kratos.
   The calculation takes a few minutes, because the Mohr-Coulomb soil yields in the
   excavation stages.
2. When the calculation is complete, Styx opens Results mode.
3. On the tool rail, click **Plot along the wall**.

![The Plot along the wall window with the bending moment in the wall for stages 3 to 7. The Plot along the wall tool is outlined.](images/crow/13_results_plot.png)

The window shows the bending moment along the wall in each stage from stage 3 on. After the
third excavation, the largest bending moment is about 341 kN·m/m, at y = −6.5 m. In
**Quantity**, select the horizontal displacement to see how the wall moves: it deflects
about 109 mm into the pit. These are the values that the benchmark BM-CROW-MC compares with
the results of Kratos' own CROW test.

**Save** saves the figure as PNG, PDF or SVG, or the numbers as CSV.

### A faster calculation: the quasi-Newton strategy (optional)

The stages use Kratos' Newton-Raphson strategy, which builds and factorises the stiffness
matrix again in every iteration. The quasi-Newton strategy factorises it once and then
updates its inverse from the residuals, so each iteration costs much less. For this model
the bending moment and the wall displacement stay the same, and Kratos took about 7 s
against about 70 s with Newton-Raphson (measured on 2026-11-16).

The strategy is a setting of each stage. For each of the seven stages:

1. In the Stages explorer, click the stage.
2. Click **Stages…**.
3. Click **Expert settings** to open them.
4. In **Strategy**, select **Quasi-Newton**. Keep **Update** at **L-BFGS**.
5. Click **Close**.

Then click **Calculate** again. In the project file, each stage now has
`"solver_settings": {"strategy_type": "quasi_newton", "quasi_newton_type": "lbfgs"}`.

The quasi-Newton strategy always uses the Sparse LU linear solver, without scaling. On a
fully coupled soil with a very low permeability it can settle a few percent too little, so
on a new model compare one calculation with a Newton-Raphson calculation.

## 14. Look at the stresses and the displacements

When the calculation was complete, Styx also opened the **Choose results** window. It is
under the plot window, and it covers the model.

1. Click **Close** in the Plot along the wall window, then click **Close** in the Choose
   results window.
2. In the Results explorer, at the bottom right, in **Stage**, select **7 Third
   excavation**.
3. In **Field**, select **Effective stresses · σxx (Pa)**. This is the horizontal
   effective stress.

![The horizontal effective stress after the third excavation. The Stage and Field lists of the Results explorer are outlined.](images/crow/14_contours_horizontal.png)

The colours show the stress on the mesh, and the legend at the right gives the values.
Compression is negative. The horizontal stress goes from about −9 kPa near the ground
surface to about −275 kPa at the bottom of the model. The pit, at the left of the wall, has
no colours, because its soil is excavated. Under the pit floor the stresses are small,
because the soil above that floor is gone.

4. In **Field**, select **Effective stresses · σyy (Pa)**. This is the vertical effective
   stress.

![The vertical effective stress after the third excavation. The Stage and Field lists are outlined.](images/crow/14_contours_vertical.png)

The vertical stress goes from about −1 kPa near the ground surface to about −600 kPa at the
bottom. Deep in the sand, the horizontal stress is about half of the vertical stress: at the
bottom, −275 kPa against −600 kPa. This ratio is close to K0 of the sand, 0.46. Near the
ground surface and near the wall, the ratio is different.

5. In **Field**, select **Deformations · |u| (m)**. This is the magnitude of the total
   displacement since the wall installation, the stage that resets the displacements.

![The magnitude of the total displacement after the third excavation. The Stage and Field lists are outlined.](images/crow/14_contours_displacement.png)

The largest displacement is about 0.45 m, at the pit floor: the floor heaves when the soil
above it is dug out. The third lift alone gives about 0.25 m of this heave. Behind the
wall, the ground surface settles up to about 0.34 m, mostly under the surcharge. To see
what one stage did by itself, select **Stage deformations · |Δu| (m)** in **Field**.

## 15. Save the project

1. Click **File** > **Save**.
2. In the save window of your browser, select a folder and click **Save**.

Styx saves the project as `CROW excavation wall.json`. Open it again later with **File** >
**Open project…**.

## What to do next

- Change one value and calculate again, for example the band of the wall mesh, or the
  depth of the third lift.
- Read [USAGE.md](https://github.com/Deltares-research/Styx-Kratos-GUI/blob/main/docs/USAGE.md) for all modes and tools of the GUI.
- Build the same model with commands in the
  [`kratos-cli` tutorial of the CROW case](https://github.com/Deltares-research/Styx-Kratos-GUI/blob/main/docs/cli_tutorials/CROW_case.md).
