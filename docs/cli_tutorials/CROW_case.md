# CROW excavation wall with `kratos-cli`

A staged sheet-pile excavation, the CROW excavation wall, built and run from PowerShell:
from an empty project to the bending moment in the wall. You never need the GUI, but you can
open the model in it at any point.

Every command below was run on 2026-10-16, and the output shown is what it printed (long
paths are shortened to `...\`).

## What you build

A 2D plane-strain section, 80 m wide and 60 m deep, in SI units (m, N, Pa, kg/m³):

```text
             x = 0       x = 5                                         x = 80
                           ↓ ↓ ↓ ↓ ↓ ↓  surcharge 20 kN/m  ↓ ↓ ↓ ↓ ↓ ↓
  y = 0        +-----------+--------------------------------------------+
               |  lift 1  =|  strut at -1.5      water table at -1.5    |
  y = -2       | - - - - - |                                            |
               |  lift 2   |                                            |
  y = -5       | - - - - - |  Upper ground                              |
               |  lift 3   |                                            |
  y = -8       +-----------+--------------------------------------------+
               |           |  Upper ground                              |
  y = -12      +-----------+--------------------------------------------+
               |           '  wall toe at -13                           |
               |              Deep sand                                 |
  y = -60      +--------------------------------------------------------+
         symmetry plane
```

- A 13 m sheet pile at x = 5, with a strut at −1.5 m.
- The pit, between the wall and the symmetry plane, is dug in three lifts: to −2, −5 and −8 m.
- The water table is at −1.5 m. A 20 kN/m surcharge sits on the retained side.
- Seven stages: K0, a null step, the wall, the first lift, the strut, the second and the
  third lift.

## Three ways to work with it

| | Way | Start from | Good for |
|---|---|---|---|
| [1](#way-1-build-the-model-from-scratch) | [Build it from scratch in the shell](#way-1-build-the-model-from-scratch) | nothing | learning the commands, making your own model (about 15 minutes) |
| [2](#way-2-open-the-ready-made-model-in-the-shell) | [Open the ready-made model in the shell](#way-2-open-the-ready-made-model-in-the-shell) | `crow.py` | looking around the model and its results |
| [3](#way-3-run-the-python-script) | [Run the Python script](#way-3-run-the-python-script) | `crow.py` | one command: write the deck and run it |

Ways 2 and 3 share one set-up step, [Before ways 2 and 3](#before-ways-2-and-3).

In the commands below, `<repo>` is the folder you cloned this repository into, such as
`C:\Users\you\Styx-Kratos-GUI`. The ready-made model, `crow.json` and `crow.py`, is in
[`examples/CROW_case/`](../../examples/CROW_case/).

---

## Way 1: build the model from scratch

Here you type every part of the model yourself, run it in Kratos, and read the results back,
in a new folder of your choice. The folder is made if it is not there, and the runs are
written into it too.

### Before you start

- Kratos must be set up on this machine. If `kratos.local.json` is not in the repository
  root yet, follow steps 1 and 2 of [Setting up Kratos](../KRATOS_SETUP.md) first. You only
  need it from part 4 on.
- The very first run builds the Python environment (`.venv-windows`), which can take a few
  minutes.

Open an empty shell in a working folder of your own, so the files the tutorial writes stay
out of the repository:

```powershell
<repo>\cli\kratos-shell.bat $HOME\crow     # or without a folder: it asks for one
```

```text
kratos-cli shell: type one command per line. The open project is used, so leave out its file name.
help lists the commands, help COMMAND explains one, exit closes the shell.

No project is open. Start one with new FILE, or open one with open FILE.

kratos-cli>
```

The shell is in `$HOME\crow`: every file from here on is written there, and so is every run
(`KRATOS_GUI_RUNS` is set to that folder).

In the shell you leave out `kratos-cli.bat` and the project file on every line, and `undo`
and `redo` work. Each line is still an ordinary command: to run one on its own in PowerShell,
put `<repo>\kratos-cli.bat` in front and the project file after the command word.

| In the shell | The same command on its own, in PowerShell |
|---|---|
| `parts` | `<repo>\kratos-cli.bat parts $HOME\crow\crow.json` |
| `layer add L_top ...` | `<repo>\kratos-cli.bat layer $HOME\crow\crow.json add L_top ...` |

> [!TIP]
> - `help` lists every command; `help layer` or `layer add --help` shows what one takes.
> - Coordinates are plain numbers separated by spaces: `--x 0 80`, not `0,80`.
> - Quotes group words: `--name "Upper ground"`. A `#` inside a word is not a comment
>   (`--color "#c4a86a"`); only a line that starts with `#` is.
> - A command that fails changes nothing. `undo` takes back the last command that did change
>   the project.

### Part 1: the ground

#### Step 1. Create the project

```text
kratos-cli> new crow.json --force --dim 2 --name "CROW excavation wall"
wrote crow.json: CROW excavation wall (2D section at z = 0, SI)
open  crow.json  (...\crow)
crow.json>
```

`new` writes an empty 2D project in SI units and opens it: the prompt now shows its name.
`--force` replaces a `crow.json` that is already there. The name also names the deck's files
(`CROW_excavation_wall.mdpa`).

#### Step 2. The site

```text
crow.json> domain --x 0 80 --y -60 0 --z 0 10
domain x 0 .. 80, y -60 .. 0 (2D section at z = 5); wrote ...\crow.json
The section at z = 0 is outside the new domain, so it is cut through its middle, at z = 5.

crow.json> borehole set bh1 --name BH1 --x 0 --y 0 --head 0 --water -1.5
changed borehole bh1; wrote ...\crow.json
```

- The `--z` extent has no effect in plane strain: the section is taken through its middle.
- A new project already has one borehole, `bh1`. It goes at the symmetry plane, with the
  ground at 0 and the phreatic level at −1.5.

#### Step 3. The soils

Materials are Kratos property sets: Kratos' own law and variable names, in SI. Nothing is
converted on export. The model has two soils:

| | `m_upper`, Upper ground | `m_lower`, Deep sand |
|---|---|---|
| `YOUNG_MODULUS` (Pa) | 900 000 | 7 428 600 |
| `POISSON_RATIO` | 0.2 | 0.3 |
| unit weight (kN/m³) | 18 | 20 |
| `GEO_COHESION` (Pa) | 1000 | 0 |
| `GEO_FRICTION_ANGLE` (°) | 22.3 | 32.7 |
| `PERMEABILITY_XX`, `_YY` (m²) | 1/86 400 | 5/86 400 |
| `K0_NC` | 0.62 | 0.46 |

`DENSITY_SOLID` is the unit weight divided by g (18 000 / 9.81 and 20 000 / 9.81). Each soil
is one line:

```text
crow.json> material add m_upper --name "Upper ground" --color "#c4a86a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD YOUNG_MODULUS=900000.0 POISSON_RATIO=0.2 DENSITY_SOLID=1834.8623853211009 DENSITY_WATER=1019.367991845056 POROSITY=0.0 BULK_MODULUS_SOLID=10000000000.0 BULK_MODULUS_FLUID=2200000000.0 DYNAMIC_VISCOSITY=0.001 PERMEABILITY_XX=1.1574074074074073e-05 PERMEABILITY_YY=1.1574074074074073e-05 PERMEABILITY_XY=0.0 GEO_COHESION=1000.0 GEO_FRICTION_ANGLE=22.3 K0_NC=0.62
added material m_upper; wrote ...\crow.json

crow.json> material add m_lower --name "Deep sand" --color "#b08a6a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD YOUNG_MODULUS=7428600.0 POISSON_RATIO=0.3 DENSITY_SOLID=2038.735983690112 DENSITY_WATER=1019.367991845056 POROSITY=0.0 BULK_MODULUS_SOLID=10000000000.0 BULK_MODULUS_FLUID=2200000000.0 DYNAMIC_VISCOSITY=0.001 PERMEABILITY_XX=5.787037037037037e-05 PERMEABILITY_YY=5.787037037037037e-05 PERMEABILITY_XY=0.0 GEO_COHESION=0.0 GEO_FRICTION_ANGLE=32.7 K0_NC=0.46
added material m_lower; wrote ...\crow.json
```

Useful here:

- `material list` shows the soils there are.
- `material set m_upper YOUNG_MODULUS=1e6` changes one value.
- `material presets` lists the library soils (`m1` Fill ... `m6` Bedrock), and
  `material add ID --preset m3` starts from one instead of typing every variable.

#### Step 4. The soil layers

Layers are stacked from the top, each under the one before:

```text
crow.json> layer add L_top --name Soil_Top --material m_upper --bottom -8
crow.json> layer add L_mid --name Soil_Middle --material m_upper --bottom -12
crow.json> layer add L_bot --name Soil_Bottom --material m_lower --bottom -60
```

The upper ground is split at −8 as well as at −12, so that the deepest lift of the pit ends
exactly on a layer boundary.

#### Step 5. The pit and the pore pressure

```text
crow.json> excavation --x 0 5 --z 0 10 --levels -2 -5 -8
excavation x 0 .. 5, z 0 .. 10, dug to -2, -5, -8; wrote ...\crow.json

crow.json> boundary add pore_pressure --name "Pore pressure" --domain --water-pressure Hydrostatic --reference-coordinate -1.5
added pore_pressure  Pore pressure  water pressure on the whole soil; hydrostatic about -1.5 m, fixed; wrote ...\crow.json
```

- The pit runs from the symmetry plane (x = 0) to the wall (x = 5). Each level is one lift,
  and each lift becomes a soil part of its own, which a stage can switch off.
- The pore pressure is a boundary condition: hydrostatic on the whole soil, zero at the
  phreatic level −1.5 m, and fixed in every stage. Without it the deck fixes no water
  pressure. The model sets no project water level (`water`): the condition and the water
  loads of step 9 carry the level themselves.
- `boundary list` shows the conditions. A new project already has the displacement
  conditions: the bottom fixed, and the left and right sides on rollers.

**Check your progress.** `parts` lists the part keys the stages switch on and off:

```text
crow.json> parts
soil_L_top  Soil_Top
soil_L_mid  Soil_Middle
soil_L_bot  Soil_Bottom
soil_L_top__lift1  Soil_Top · lift 1
soil_L_top__lift2  Soil_Top · lift 2
soil_L_top__lift3  Soil_Top · lift 3
soil_L_mid__pit  Soil_Middle · below the pit
soil_L_bot__pit  Soil_Bottom · below the pit
```

`show` summarises the whole model at any time.

### Part 2: the wall, the strut and the loads

A structure is built from a **section**, which holds its Kratos variables, and a
**geometry**. Each step adds the section first, then the structure.

#### Step 6. The sheet pile wall

```text
crow.json> section add beam sheetpile --name "Sheet pile" --spacing 1 YOUNG_MODULUS=8444900000.0 POISSON_RATIO=0.0 DENSITY=298.36 CROSS_AREA=0.4924 I33=0.009948850085333335 AREA_EFFECTIVE_Y=10.0
added beam section sheetpile (Sheet pile); wrote ...\crow.json

crow.json> beam add sheetpile --name SheetPileWall --section sheetpile --points 5 0 5 -13
added sheet pile sheetpile (SheetPileWall); wrote ...\crow.json
```

- Per metre of wall: E = 8.44 GPa, A = 0.4924 m², I = 9.95·10⁻³ m⁴, density 298 kg/m³.
- The wall is a solid plate 0.4924 m thick: `I33` is t³/12. The large `AREA_EFFECTIVE_Y`
  (twenty times the area) leaves shear deformation out.
- `--points 5 0 5 -13` runs the wall from the ground surface at x = 5 m down to its toe at
  y = −13 m.

#### Step 7. The strut

A strut is an anchor whose free end is a pinned support:

```text
crow.json> section add anchor strand --name Strut --spacing 1 --tension-limit none --compression-limit none YOUNG_MODULUS=210000000000.0 CROSS_AREA=4.7619e-05 DENSITY=0.0
added anchor section strand (Strut); wrote ...\crow.json

crow.json> anchor add strut --name Strut --section strand --head 5 -1.5 --tail 4 -1.5
added anchor strut (Strut); wrote ...\crow.json
```

- One strut per metre of wall (`--spacing 1`): E = 210 GPa, A = 4.76·10⁻⁵ m².
- The strut is massless and has no force limits (`none` clears a limit).
- Its head is snapped onto the wall, because it becomes one of the wall's nodes. A head more
  than 1 m from any structure is refused.

#### Step 8. The interface between wall and soil

```text
crow.json> section add interface contact --name "Wall contact" --material none --r-inter 0.7 --virtual-thickness 1.0
added interface section contact (Wall contact); wrote ...\crow.json

crow.json> interface add wall_contact --name Interface --section contact --structure sheetpile --side both
added interface wall_contact (Interface); wrote ...\crow.json
```

- `--material none`: each stretch of the interface takes the soil it runs against, reduced
  by `R_inter` = 0.7.
- `--side both` puts the interface on both faces of the wall.
- The stiffnesses are derived from that soil: shear = G / virtual thickness, normal =
  10 x shear. To use your own, type them on the section, in N/m³:
  `section set contact INTERFACE_NORMAL_STIFFNESS=1e9 INTERFACE_SHEAR_STIFFNESS=1e8`.
  `section list` shows which ones are typed and which are derived.
- `R_inter` reduces the soil's cohesion and tan φ. Only a Coulomb law
  (`--law GeoInterfaceCoulombLawPlaneStrain`) reads the strength; the default elastic law
  reads the two stiffnesses only.

#### Step 9. The loads

The surcharge: 20 kN/m on the retained surface, from the wall to the right edge. Its
components are in N/m:

```text
crow.json> load add line surcharge --name Load --x 5 80 --y 0 --components 0 -20000
added line load surcharge (Load); wrote ...\crow.json
```

One hydrostatic water load per lift. Each runs along that lift's floor from the symmetry plane
to the wall, then up the exposed face of the wall to the water table. A normal load presses
on the soil on the right of its line as drawn, where its arrows point in the GUI, so the
ground that stays is on the right of this walk. Its pressure is zero at its
`--reference-coordinate`, the phreatic level:

```text
crow.json> normal-load add water_1 --name WaterLoad_Stage1 --hydrostatic --reference-coordinate -1.5 --points 0 -2 5 -2 5 -1.5
crow.json> normal-load add water_2 --name WaterLoad_Stage2 --hydrostatic --reference-coordinate -1.5 --points 0 -5 5 -5 5 -1.5
crow.json> normal-load add water_3 --name WaterLoad_Stage3 --hydrostatic --reference-coordinate -1.5 --points 0 -8 5 -8 5 -1.5
```

### Part 3: the mesh and the stages

#### Step 10. The mesh

The mesh settings are fields of the project. The size per body and the refinement box have
no option of their own, so they are set by path with `set` and `add`. `mesh` takes the element
size and order, keeps them in the project, and meshes:

```text
crow.json> set mesh.body_sizes.sheetpile 0.5
crow.json> add mesh.refinements '{"kind": "box", "size": 0.75, "thickness": 45.0, "x_min": -1.0, "x_max": 8.0, "y_min": -16.0, "y_max": 1.0, "z_min": -1.0, "z_max": 11.0}'
crow.json> mesh --size 5.0 --order 2
4299 nodes, 2087 elements (2087 Triangle 6)
```

| Setting | Why |
|---|---|
| `element_size 5.0` | 5 m elements far from the pit. |
| `order 2` | 6-node triangles. |
| `body_sizes.sheetpile 0.5` | The wall at 0.5 m: 26 equal beam elements. |
| the box refinement | 0.75 m round the pit and the wall's toe, growing back to 5 m over 45 m. |

`mesh` runs gmsh and reports the size. It is only a check: `export` meshes anyway.
`get mesh` prints the settings back.

#### Step 11. The construction stages

One command derives the whole sequence from the model:

```text
crow.json> stages staged-excavation
1  initial  Initial stage
     calculation: K0 procedure; deactivates sheetpile, strut, wall_contact, surcharge, water_1, water_2, water_3
2  null_step  Null step  (after initial)
     calculation: Null step
3  install_sheetpile  SheetPileWall installation  (after null_step)
     calculation: Plastic; activates sheetpile, wall_contact, surcharge
4  dig_1  First excavation  (after install_sheetpile)
     calculation: Plastic; activates water_1; deactivates soil_L_top__lift1
5  install_strut  Strut installation  (after dig_1)
     calculation: Plastic; activates strut
6  dig_2  Second excavation  (after install_strut)
     calculation: Plastic; activates water_2; deactivates soil_L_top__lift2, water_1
7  dig_3  Third excavation  (after dig_2)
     calculation: Plastic; activates water_3; deactivates soil_L_top__lift3, water_2
```

In words: settle the ground with K0, take a null step, install the wall with its interface
and the surcharge, then dig lift by lift with that lift's water load, and put the strut in
right after the lift that exposes its head.

To look at a stage, or change one:

```text
crow.json> stages show dig_2                             what is in the model during that stage
crow.json> stages set dig_1 --max-iterations 300         more iterations for the first dig
crow.json> stages deactivate dig_3 strut                 take the strut out from dig_3 on
crow.json> undo                                          ...and put it back
```

`undo` takes back one command that changed the project. A command that changed nothing (for
example setting a value it already has) is not a step.

### Part 4: the deck and the run

#### Step 12. Check and export the deck

```text
crow.json> check
ok: CROW excavation wall (2D section at z = 5, SI)

crow.json> export --out deck
wrote the Kratos deck CROW_excavation_wall to deck:
  CROW_excavation_wall.mdpa
  MaterialParameters.json
  initial_materials.json
  ProjectParameters.json
  kratos_gui_units.json
4299 nodes, 2087 elements (2087 Triangle 6)
next: kratos-cli run deck
note: interface section 'Wall contact' against 'Upper ground' (Interface_Soil_Top, ...): normal stiffness 3.75e+06 and shear stiffness 3.75e+05 N/m³, 10 G / t and G / t (E = 9e+05 Pa, nu = 0.2, t = 1 m); cohesion 700 Pa = 0.7 x 1000, ...
note: interface section 'Wall contact' against 'Deep sand' (Interface_Soil_Bottom, Interface_Soil_Bottom_pit): ...
```

The notes say what the exporter took from the soil beside the interface, which is what this
model asks for: one line per soil, with the parts of the interface against it and the
numbers. Nothing needs to be done about them. The cohesion and friction angle are read only by a Coulomb law; this interface uses the default elastic law, which reads the two stiffnesses. The files are named after the project;
`--name mesh` would write `mesh.mdpa` instead.

#### Step 13. Look into the deck (optional)

```text
crow.json> deck show deck
CROW_excavation_wall.mdpa: 2D, 4392 nodes, x 0 .. 80, y -60 .. 0
  elements:
    2087 SmallStrainUPwDiffOrderElement2D6N (continuum)
    26 LinearTimoshenkoCurvedBeamElement2D3N (beam)
    1 LinearTrussElement2D2N (truss)
    52 Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N (interface)
  ...
  33 SubModelParts:
  ...
  7 stages:
  ...

crow.json> node deck 30
Node 30 at (1.842, -12.000, 0.000)
  SubModelParts: Soil_Middle_pit, Soil_Bottom_pit
```

The deck has 4392 nodes, not 4299, because the interface splits each wall node into one per
side. `node` says which SubModelParts a node is in, and which nodes share its position.

#### Step 14. Run it

```text
crow.json> run deck
run CROW_excavation_wall_2026-10-16_00-50 finished in 5.6 s: 25 files in ...\crow\CROW_excavation_wall_2026-10-16_00-50
next: kratos-cli results show CROW_excavation_wall_2026-10-16_00-50
```

`run` copies the deck into a new run folder and runs Kratos there. Your `deck\` stays as it
was, and every run is kept.

- The run folder is made under the runs root: `KRATOS_GUI_RUNS`, which `kratos-shell.bat`
  set to your working folder. Without it, the runs root is `~/KratosGUI/runs`.
  `--runs-dir DIR` puts one run somewhere else.
- `calculate` does steps 12 and 14 in one go, without a `deck\` folder of your own.

### Part 5: the results

Every `results` command names a run in one of three ways: its **number** in `results runs`
(1 is the newest), its **id**, or the **path** of its folder, wherever that is. Below, `1`
means "the run just made".

#### Did it finish?

```text
crow.json> results runs
1 run in ...\crow:
  1  CROW_excavation_wall_2026-10-16_00-50  7 stage(s) with results, 31 files

crow.json> results show 1
CROW_excavation_wall_2026-10-16_00-50  (deck CROW_excavation_wall, started 2026-10-16T00:50)
  complete, SI units, 31 files, 5.9 MB
    1  Initial stage                 results
    2  Null step                     results
    3  SheetPileWall installation    results  +2 series
    4  First excavation              results  +2 series
    5  Strut installation            results  +2 series
    6  Second excavation             results  +2 series
    7  Third excavation              results  +2 series
```

"+2 series" means the stage also wrote curves along the wall and along the interface.

#### The wall, stage by stage

```text
crow.json> results members 1
This run wrote curves for:
  interface   stages 3, 4, 5, 6, 7  tn, ts
  wall        stages 3, 4, 5, 6, 7  M, Q, N, ux, uy

crow.json> results profile 1 wall M
Bending moment (N·m/m) along the wall, 5 stages:
    3  SheetPileWall installation    min -417 at y 0, max 53902 at y -6.00
    4  First excavation              min -1034 at y -12.5, max 81124 at y -6.50
    5  Strut installation            min -1034 at y -12.5, max 81124 at y -6.50
    6  Second excavation             min -1541 at y -12.5, max 1.27e+5 at y -4.50
    7  Third excavation              min -3499 at y -12.5, max 3.30e+5 at y -6.00

crow.json> results profile 1 wall ux
Horizontal total displacement (m) along the wall, 5 stages:
    ...
    7  Third excavation              min -0.0671 at y -6.50, max -0.0066 at y 0
```

After the last lift, the wall carries about 330 kN·m/m at −6 m and deflects 67 mm into the
pit.

| Along | Quantities |
|---|---|
| the wall | `M`, `Q`, `N`, `ux`, `uy` |
| the interface | `tn`, `ts`, or a word of the label: `results profile 1 interface normal` |

**Write a curve to a file**, for Excel or a plot of your own:

```text
crow.json> results profile 1 wall M --stage 7 --csv wall_M.csv
wrote wall_M.csv (53 rows)
```

The CSV has one row per wall node: `stage,name,node,y [m],M [N·m/m]`. Always give `--csv` a
file name: in Windows PowerShell 5.1, redirecting with `>` would save the file as UTF-16.

#### Fields over the whole mesh

```text
crow.json> results fields 1
Stage 7 (Third excavation) offers:
  Deformations
    u         |u|                             m       nodes
    ux        u_x                             m       nodes
    uy        u_y                             m       nodes
  ...
  Effective stresses
    sxx       σxx                             Pa      elements/nodes
    syy       σyy                             Pa      elements/nodes
  ...
  Groundwater
    pw        Pore pressure                   Pa      nodes

crow.json> results field 1 uy
u_y (m), stage 7 (Third excavation): -0.3399 to 0.3896 over 4392 nodes
  min -0.3399 at node 14
  max 0.3896 at node 12

crow.json> results field 1 syy --stage third --csv syy_stage7.csv
wrote syy_stage7.csv (1876 rows)

crow.json> results at 1 14 --stage 7                    every field at node 14
```

- **Which stage.** Without `--stage`, a command reads the last stage. `--stage` takes the
  stage's **number** (`7`) or **words of its name** (`third`, `"first excavation"`), not its
  id (`dig_3`).
- **Stresses** are read per element, as Kratos computed them. `--location nodes` averages
  them onto the nodes.
- **Why 0.34 m?** That settlement is at the far-right corner (node 14). It is the total since
  the start, K0 stage included, in an elastic soil. The last lift adds less than a
  millimetre there: `results at 1 14 --stage 7` shows Δu_y = −9.79e-4 m. To see what one
  stage did, read the stage fields `du`, `dux` and `duy`.

#### The raw files

```text
crow.json> results files 1                           every file of the run, with its size
crow.json> results get 1 kratos.log --out logs/      copy one into logs\ (made if need be)
crow.json> results archive 1                         the whole run as a .zip, here
```

### Part 6: keep the model

#### Step 15. Open it in the GUI

The project file and the runs are the GUI's own. Start the GUI with the runs root set to
your working folder, so its Results mode finds the runs there:

```powershell
$env:KRATOS_GUI_RUNS = "$HOME\crow"; <repo>\run.bat
```

1. **Open** `crow.json`. You see the model you typed: layers, wall, strut, loads and stages.
2. **Results** mode lists the same runs. Open `CROW_excavation_wall_2026-10-16_00-50` for
   the deformed mesh, the contours and the wall plots.

#### Step 16. Save it as a Python script

```text
crow.json> script --out crow.py
wrote crow.py: CROW excavation wall (2D section at z = 5, SI)
next: run crow.py in the GUI's command box, or python crow.py --out deck/
```

`crow.py` holds the whole model as readable Python, every value typed out: the same file as
the ready-made [`crow.py`](../../examples/CROW_case/crow.py) that ways 2 and 3 start from. Next
time, start from it instead of typing the model again:

| Where | What |
|---|---|
| the GUI's command box | `run crow.py` opens the model |
| PowerShell | `<repo>\kratos-cli.bat show $HOME\crow\crow.py`, and every command that only reads a model |
| PowerShell | `<repo>\.venv-windows\Scripts\python.exe $HOME\crow\crow.py --calculate` writes the deck and runs it |

#### Step 17. Leave the shell

```text
crow.json> exit
```

### All in one go

[`crow.json`](../../examples/CROW_case/crow.json) is the whole model: the file steps 1 to 11
build, and the same file the GUI saves. Open the shell in a new folder:

```powershell
<repo>\cli\kratos-shell.bat $HOME\my_crow
```

Then open the JSON file and calculate it. `calculate` meshes the model, writes the Kratos
input files into a run folder in `my_crow`, and runs them:

```text
open <repo>\examples\CROW_case\crow.json
calculate
results show 1
results profile 1 wall M
exit
```

Edits made in the shell are saved into the file that is open. To make a model of your own,
copy `crow.json`, change its values (sizes, materials, stages, ...) and `open` your copy
instead. `check` tells you whether it can be meshed and staged.

**Your own commands from a file.** Put steps 1 to 12 in a text file, one shell line per
command (a line that starts with `#` is a comment), say `crow.txt` in your working folder.
Any of these then builds `crow.json` and `deck\` in a few seconds, in the folder the shell
is in:

| From | Type |
|---|---|
| inside the shell | `source crow.txt` |
| PowerShell, in the working folder | `Get-Content crow.txt \| <repo>\kratos-cli.bat shell` |
| cmd, in the working folder | `<repo>\kratos-cli.bat shell < crow.txt` |

Read from a file like this, the shell echoes each line and stops at the first command that
fails, naming its line. Then go on with part 4: `run deck`, `results profile 1 wall M`.

---

## Before ways 2 and 3

Run [`kratos-init-powershell.bat`](../../cli/kratos-init-powershell.bat), in the `cli` folder:
double-click it, or from PowerShell:

```powershell
<repo>\cli\kratos-init-powershell.bat
```

It asks for the **project folder**: the folder that holds the model's `.py` file, here
`<repo>\examples\CROW_case`.

It then opens a PowerShell that is ready for ways 2 and 3:

- it is in the project folder;
- `$repo`, `$model`, `$cli` and `$py` are set (it prints them);
- `KRATOS_GUI_RUNS` is the project folder, so runs are written there and read from there;
- the first time, it builds the Python environment (`.venv-windows`), which can take a few
  minutes.

If Kratos is not set up on this machine yet, it says so and stops: follow steps 1 and 2 of
[Setting up Kratos](../KRATOS_SETUP.md), then run it again. `exit` closes the PowerShell it
opened.

> [!IMPORTANT]
> Type every command that uses `$repo`, `$model`, `$cli` or `$py` in **that** PowerShell.
> In any other window they are empty, and PowerShell answers with an error such as
> *The term '\kratos-cli.bat' is not recognized*.

---

## Way 2: open the ready-made model in the shell

In the PowerShell from [Before ways 2 and 3](#before-ways-2-and-3), open the shell on
`crow.py`:

```powershell
& $cli shell crow.py
```

Then type these lines. `deck` is a folder in the model's folder, and `1` is the newest run.

```text
# The model
show
parts
stages list

# Write the input files, then run them
export --out deck
run deck

# The runs and their stages
results runs
results show 1
results fields 1

# Fields: last stage by default, or pick one with --stage (a number or a name)
results field 1 uy
results field 1 uy --stage 4
results field 1 syy
results at 1 14

# The wall and the interface: M, Q, N, ux or uy along the wall; tn or ts along the interface
results members 1
results profile 1 wall M
results profile 1 wall ux
results profile 1 interface tn

# Every value, to a CSV file
results field 1 uy --csv uy.csv
results profile 1 wall M --stage 7 --csv wall_M.csv

exit
```

What each `results` line prints, and how to read it, is in
[Part 5: the results](#part-5-the-results) of way 1.

### One command at a time, without the shell

Every shell line also works on its own: put `& $cli` in front, and the model file after the
command name. In the model's folder:

```powershell
& $cli show   crow.py                        # what the model holds
& $cli parts  crow.py                        # its parts
& $cli stages crow.py list                   # its stages
& $cli export crow.py --out deck             # write the input files
& $cli run    deck --runs-dir .              # run Kratos
& $cli results profile 1 wall M --runs-dir . # read a result
```

---

## Way 3: run the Python script

In the PowerShell from [Before ways 2 and 3](#before-ways-2-and-3):

```powershell
& $py crow.py --out deck                  # write the input files into deck\
& $py crow.py --out deck --calculate      # write them, then run Kratos on them
& $py crow.py --calculate                 # mesh, write and run in one go, as `calculate` does
& $py crow.py --out $HOME\deck            # write them somewhere else instead
```

`crow.py` needs `--out`, `--calculate` or both; with neither it says so and stops. The run
is written into the project folder, and the script prints where. It does not print a
summary of the results: to read them, open the model in the shell
([way 2](#way-2-open-the-ready-made-model-in-the-shell)) and use its `results` lines, such
as `results show 1` and `results profile 1 wall M`.

---

## What gets written

| File | What it is |
|---|---|
| `crow.json` | the model (way 1 only; ways 2 and 3 read `crow.py`) |
| `deck\` | the Kratos input files: `CROW_excavation_wall.mdpa`, `ProjectParameters.json`, `MaterialParameters.json`, `initial_materials.json`, `kratos_gui_units.json` |
| `CROW_excavation_wall_<date>_<time>\` | one folder per run: a copy of the deck, `kratos.log`, the results (`*.post.res`, `*.post.msh`) and the curves along the wall and the interface (`*_output_wall.json`, `*_output_interface.json`) |
| `crow.py` | the model as a Python script (way 1, step 16) |
| `wall_M.csv`, `syy_stage7.csv`, `uy.csv` | every value of a curve or a field, if you asked for it with `--csv` |

Way 1 writes into the working folder you chose; ways 2 and 3 into the project folder,
`<repo>\examples\CROW_case`.

---

## When something goes wrong

| What you see | What it means |
|---|---|
| `error: ...`, and nothing changed | The command was refused as a whole, and the project was not written. The message names the field. |
| `no stage matches 'dig_3'` | `--stage` takes the stage's number or words of its name, not the stage id. |
| `error: no project is open` | Start with `new FILE` or `open FILE`, or name the project on the line. |
| `note: interface section 'Wall contact' against ...` | What the interface took from the soil: see step 12. |
| `'/c/Users/...' is not a run` | A Git Bash path given to a Windows program. Use `C:/Users/...`, or the run's number. |
| `nothing to undo` | `undo` steps back only through commands of this shell session that changed the project. |
| *The term '\kratos-cli.bat' is not recognized* | `$cli` is empty: type the command in the PowerShell from [Before ways 2 and 3](#before-ways-2-and-3). |
| `crow.py: error: give --out DIR ...` | `crow.py` needs `--out DIR`, `--calculate` or both. |
| What a command takes | `help COMMAND` in the shell, or `<repo>\kratos-cli.bat COMMAND --help` in PowerShell. |

Every command is described in [CLI.md](../CLI.md).
