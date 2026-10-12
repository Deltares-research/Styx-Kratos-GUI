# Tutorial: a staged sheet-pile excavation with `kratos-cli`

This tutorial builds a staged sheet-pile excavation in the terminal, from an empty project
to the bending moment in the wall. You type every part of the model yourself, run it in
Kratos, and read the results back. You never need the GUI, but you can open the model in it
at any point (part 6).

It takes about 15 minutes. Every command below was run on 2026-10-12, and the output shown is
what it printed (long paths are shortened to `...\`).

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

When you are done, your working folder holds:

| File | What it is |
|---|---|
| `excavation.json` | The project. The GUI's **Open** reads it. |
| `deck/` | The Kratos deck: `.mdpa`, `ProjectParameters.json`, `MaterialParameters.json`, `initial_materials.json`. |
| `excavation_model.py` | The same model as a Python script (optional, part 6). |

The run itself goes under `~/KratosGUI/runs/`, where the GUI's Results mode finds it too.

---

## Before you start

The commands below are for **PowerShell**, started in the repository root. In cmd, type
`kratos-cli.bat` instead of `.\kratos-cli.bat`; in Git Bash, `./kratos-cli.sh`.

**1. Kratos** must be findable the way the GUI finds it ([KRATOS_SETUP.md](KRATOS_SETUP.md)).
You only need it from part 4 on.

**2. Make a working folder** for the files the tutorial writes, so they stay out of the
repository:

```powershell
mkdir D:\work\excavation
```

**3. Start the shell** from the repository root, then go into the working folder:

```text
PS D:\> cd D:\Checkouts\Private\Kratos-GUI
PS D:\Checkouts\Private\Kratos-GUI> .\kratos-cli.bat shell
kratos-cli shell: a command as after `kratos-cli`, without the project file. `help` lists them; `exit` leaves.
No project is open: `open FILE`, or `new FILE`.
kratos-cli> cd D:\work\excavation
D:\work\excavation
kratos-cli>
```

`.\kratos-cli.bat` uses the `.venv-windows` environment, and makes it the first time if it is
missing. The shell's `cd` moves it into the working folder: every file from here on is
written there.

In the shell you leave out `.\kratos-cli.bat` and the project file on every line, and `undo`
and `redo` work. Each line is still an ordinary command: to run one on its own in PowerShell,
put `.\kratos-cli.bat` in front and the project file after the command word.

| In the shell | The same command on its own, from the repository root |
|---|---|
| `water -1.5` | `.\kratos-cli.bat water D:\work\excavation\excavation.json -1.5` |
| `layer add L_top ...` | `.\kratos-cli.bat layer D:\work\excavation\excavation.json add L_top ...` |

> **Tips for typing in the shell**
>
> - `help` lists every command; `help layer` or `layer add --help` shows what one takes.
> - Coordinates are plain numbers separated by spaces: `--x 0 80`, not `0,80`.
> - Quotes group words: `--name "Upper ground"`. A `#` inside a word is not a comment
>   (`--color "#c4a86a"`); only a line that starts with `#` is.
> - A command that fails changes nothing. `undo` takes back the last command that did change
>   the project.

---

## Part 1: the ground

### Step 1. Create the project

```text
kratos-cli> new excavation.json --force --dim 2 --name "Excavation wall"
wrote excavation.json: Excavation wall (2D section at z = 10, SI)
open: ...\excavation.json
excavation.json>
```

`new` writes an empty 2D project in SI units and opens it: the prompt now shows its name.
`--force` replaces a `excavation.json` that is already there. The name also names the deck's files
(`Excavation_wall.mdpa`).

### Step 2. The site

```text
excavation.json> domain --x 0 80 --y -60 0 --z 0 10
domain x 0 .. 80, y -60 .. 0, z 0 .. 10; wrote ...\excavation.json
The section at z = 10 is outside the new domain, so it is cut through its middle, at z = 5.

excavation.json> borehole set bh1 --name BH1 --x 0 --y 0 --head 0 --water -1.5
changed borehole bh1; wrote ...\excavation.json
```

- The `--z` extent has no effect in plane strain: the section is taken through its middle.
- A new project already has one borehole, `bh1`. It goes at the symmetry plane, with the
  ground at 0 and the phreatic level at −1.5.

### Step 3. The soils

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
excavation.json> material add m_upper --name "Upper ground" --color "#c4a86a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD YOUNG_MODULUS=900000.0 POISSON_RATIO=0.2 DENSITY_SOLID=1834.8623853211009 DENSITY_WATER=1019.367991845056 POROSITY=0.0 BULK_MODULUS_SOLID=10000000000.0 BULK_MODULUS_FLUID=2200000000.0 DYNAMIC_VISCOSITY=0.001 PERMEABILITY_XX=1.1574074074074073e-05 PERMEABILITY_YY=1.1574074074074073e-05 PERMEABILITY_XY=0.0 GEO_COHESION=1000.0 GEO_FRICTION_ANGLE=22.3 K0_NC=0.62
added material m_upper; wrote ...\excavation.json

excavation.json> material add m_lower --name "Deep sand" --color "#b08a6a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD YOUNG_MODULUS=7428600.0 POISSON_RATIO=0.3 DENSITY_SOLID=2038.735983690112 DENSITY_WATER=1019.367991845056 POROSITY=0.0 BULK_MODULUS_SOLID=10000000000.0 BULK_MODULUS_FLUID=2200000000.0 DYNAMIC_VISCOSITY=0.001 PERMEABILITY_XX=5.787037037037037e-05 PERMEABILITY_YY=5.787037037037037e-05 PERMEABILITY_XY=0.0 GEO_COHESION=0.0 GEO_FRICTION_ANGLE=32.7 K0_NC=0.46
added material m_lower; wrote ...\excavation.json
```

Useful here:

- `material list` shows the soils there are.
- `material set m_upper YOUNG_MODULUS=1e6` changes one value.
- `material presets` lists the library soils (`m1` Fill ... `m6` Bedrock), and
  `material add ID --preset m3` starts from one instead of typing every variable.

### Step 4. The soil layers

Layers are stacked from the top, each under the one before:

```text
excavation.json> layer add L_top --name Soil_Top --material m_upper --bottom -8
excavation.json> layer add L_mid --name Soil_Middle --material m_upper --bottom -12
excavation.json> layer add L_bot --name Soil_Bottom --material m_lower --bottom -60
```

The upper ground is split at −8 as well as at −12, so that the deepest lift of the pit ends
exactly on a layer boundary.

### Step 5. The pit and the water level

```text
excavation.json> excavation --x 0 5 --z 0 10 --levels -2 -5 -8
excavation x 0 .. 5, z 0 .. 10, dug to -2, -5, -8; wrote ...\excavation.json

excavation.json> water -1.5
Water level: -1.50 m (specific weight 10000). wrote ...\excavation.json
```

The pit runs from the symmetry plane (x = 0) to the wall (x = 5). Each level is one lift, and
each lift becomes a soil part of its own, which a stage can switch off.

**Check your progress.** `parts` lists the part keys the stages switch on and off:

```text
excavation.json> parts
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

---

## Part 2: the wall, the strut and the loads

A structure is built from a **section**, which holds its Kratos variables, and a
**geometry**. Each step adds the section first, then the structure.

### Step 6. The sheet pile wall

```text
excavation.json> section add beam sheetpile --name "Sheet pile" --spacing 1 YOUNG_MODULUS=8444900000.0 POISSON_RATIO=0.0 DENSITY=298.36 CROSS_AREA=0.4924 I33=0.009948850085333335 AREA_EFFECTIVE_Y=10.0
added beam section sheetpile; wrote ...\excavation.json

excavation.json> beam add sheetpile --name SheetPileWall --section sheetpile --points 5 0 5 -13
added sheet pile sheetpile (SheetPileWall); wrote ...\excavation.json
```

- The wall is a solid plate 0.4924 m thick: `I33` is t³/12. The large `AREA_EFFECTIVE_Y`
  (twenty times the area) leaves shear deformation out.
- `--points 5 0 5 -13` runs the wall from the ground surface at x = 5 down to its toe at −13.

### Step 7. The strut

A strut is an anchor whose free end is a pinned support:

```text
excavation.json> section add anchor strand --name Strut --spacing 1 --tension-limit none --compression-limit none YOUNG_MODULUS=210000000000.0 CROSS_AREA=4.7619e-05 DENSITY=0.0
added anchor section strand; wrote ...\excavation.json

excavation.json> anchor add strut --name Strut --section strand --head 5 -1.5 --tail 4 -1.5
added anchor strut (Strut); wrote ...\excavation.json
```

- The strut is massless and has no force limits (`none` clears a limit).
- Its head is snapped onto the wall, because it becomes one of the wall's nodes. A head more
  than 1 m from any structure is refused.

### Step 8. The interface between wall and soil

```text
excavation.json> section add interface contact --name "Wall contact" --material none --r-inter 0.7 --virtual-thickness 1.0
added interface section contact; wrote ...\excavation.json

excavation.json> interface add wall_contact --name Interface --section contact --structure sheetpile --side both
added interface wall_contact (Interface); wrote ...\excavation.json
```

- `--material none`: each stretch of the interface takes the soil it runs against, reduced
  by `R_inter` = 0.7.
- `--side both` puts the interface on both faces of the wall.

### Step 9. The loads

The surcharge: 20 kN/m on the retained surface, from the wall to the right edge. Its
components are in N/m:

```text
excavation.json> load add line surcharge --name Load --x 5 80 --y 0 --components 0 -20000
added line load surcharge (Load); wrote ...\excavation.json
```

One hydrostatic water load per lift. Each runs from the water table down the exposed face of
the wall, then back along that lift's floor to the symmetry plane:

```text
excavation.json> normal-load add water_1 --name WaterLoad_Stage1 --hydrostatic --points 5 -1.5 5 -2 0 -2
excavation.json> normal-load add water_2 --name WaterLoad_Stage2 --hydrostatic --points 5 -1.5 5 -5 0 -5
excavation.json> normal-load add water_3 --name WaterLoad_Stage3 --hydrostatic --points 5 -1.5 5 -8 0 -8
```

---

## Part 3: the mesh and the stages

### Step 10. The mesh

The mesh settings are fields of the project. They have no command of their own, so they are
set by path with `set` and `add`:

```text
excavation.json> set mesh.element_size 5.0
excavation.json> set mesh.order 2
excavation.json> set mesh.body_sizes.sheetpile 0.5
excavation.json> add mesh.refinements '{"kind": "box", "size": 0.75, "thickness": 45.0, "x_min": -1.0, "x_max": 8.0, "y_min": -16.0, "y_max": 1.0, "z_min": -1.0, "z_max": 11.0}'
excavation.json> mesh
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

### Step 11. The construction stages

One command derives the whole sequence from the model:

```text
excavation.json> phases staged-excavation
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
excavation.json> phases show dig_2                             what is in the model during that stage
excavation.json> phases set dig_1 --max-iterations 300         more iterations for the first dig
excavation.json> phases deactivate dig_3 strut                 take the strut out from dig_3 on
excavation.json> undo                                          ...and put it back
```

`undo` takes back one command that changed the project. A command that changed nothing (for
example setting a value it already has) is not a step.

---

## Part 4: the deck and the run

### Step 12. Check and export the deck

```text
excavation.json> check
ok: Excavation wall (2D section at z = 5, SI)

excavation.json> export --out deck
wrote the Kratos deck Excavation_wall to deck:
  Excavation_wall.mdpa
  MaterialParameters.json
  initial_materials.json
  ProjectParameters.json
  kratos_gui_units.json
4299 nodes, 2087 elements (2087 Triangle 6)
next: kratos-cli run deck
warning: Derived where a property set left them out (type a value to replace it): interface section 'Wall contact': GEO_DRAINAGE_TYPE; interface section 'Wall contact': INTERFACE_NORMAL_STIFFNESS; ...
```

The warning is expected: the exporter derives the interface's stiffness and strength from
the soil beside it, which is what this model intends. The files are named after the project;
`--name mesh` would write `mesh.mdpa` instead.

### Step 13. Look into the deck (optional)

```text
excavation.json> deck show deck
Excavation_wall.mdpa: 2D, 4392 nodes, x 0 .. 80, y -60 .. 0
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

excavation.json> node deck 30
Node 30 at (1.842, -12.000, 0.000)
  SubModelParts: Soil_Middle_pit, Soil_Bottom_pit
```

The deck has 4392 nodes, not 4299, because the interface splits each wall node into one per
side. `node` says which SubModelParts a node is in, and which nodes share its position.

### Step 14. Run it

```text
excavation.json> run deck
run Excavation_wall_2026-10-12_04-00 finished in 4.8 s: 25 files in C:\Users\<you>\KratosGUI\runs\Excavation_wall_2026-10-12_04-00
next: kratos-cli results show Excavation_wall_2026-10-12_04-00
```

`run` copies the deck into a new folder under the runs root and runs Kratos there. Your
`deck/` stays as it was, and every run is kept.

- The runs root is `KRATOS_GUI_RUNS`, or `~/KratosGUI/runs` when that is not set.
  `--runs-dir DIR` puts one run somewhere else.
- `calculate` does steps 12 and 14 in one go, without a `deck/` folder of your own.

---

## Part 5: the results

Every `results` command names a run in one of three ways: its **number** in `results runs`
(1 is the newest), its **id**, or the **path** of its folder, wherever that is. Below, `1`
means "the run just made".

### Did it finish?

```text
excavation.json> results runs
1 run in C:\Users\<you>\KratosGUI\runs:
  1  Excavation_wall_2026-10-12_04-00  7 stage(s) with results, 31 files

excavation.json> results show 1
Excavation_wall_2026-10-12_04-00  (deck Excavation_wall, started 2026-10-12T04:00)
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

### The wall, stage by stage

```text
excavation.json> results members 1
This run wrote curves for:
  interface   stages 3, 4, 5, 6, 7  tn, ts
  wall        stages 3, 4, 5, 6, 7  M, Q, N, ux, uy

excavation.json> results profile 1 wall M
Bending moment (N·m/m) along the wall, 5 stages:
    3  SheetPileWall installation    min -417 at y 0, max 53902 at y -6.00
    4  First excavation              min -1034 at y -12.5, max 81124 at y -6.50
    5  Strut installation            min -1034 at y -12.5, max 81124 at y -6.50
    6  Second excavation             min -1541 at y -12.5, max 1.27e+5 at y -4.50
    7  Third excavation              min -3499 at y -12.5, max 3.30e+5 at y -6.00

excavation.json> results profile 1 wall ux
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
excavation.json> results profile 1 wall M --stage 7 --csv wall_M.csv
wrote wall_M.csv (53 rows)
```

The CSV has one row per wall node: `stage,phase,node,y [m],M [N·m/m]`. Always give `--csv` a
file name: in Windows PowerShell 5.1, redirecting with `>` would save the file as UTF-16.

### Fields over the whole mesh

```text
excavation.json> results fields 1
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

excavation.json> results field 1 uy
u_y (m), stage 7 (Third excavation): -0.3399 to 0.3896 over 4392 nodes
  min -0.3399 at node 14
  max 0.3896 at node 12

excavation.json> results field 1 syy --stage third --csv syy_stage7.csv
wrote syy_stage7.csv (1876 rows)

excavation.json> results at 1 14 --stage 7                    every field at node 14
```

- **Which stage.** Without `--stage`, a command reads the last stage. `--stage` takes the
  stage's **number** (`7`) or **words of its name** (`third`, `"first excavation"`), not the
  phase id (`dig_3`).
- **Stresses** are read per element, as Kratos computed them. `--location nodes` averages
  them onto the nodes.
- **Why 0.34 m?** That settlement is at the far-right corner (node 14). It is the total since
  the start, K0 stage included, in an elastic soil. The last lift adds less than a
  millimetre there: `results at 1 14 --stage 7` shows Δu_y = −9.79e-4 m. To see what one
  stage did, read the phase fields `du`, `dux` and `duy`.

### The raw files

```text
excavation.json> results files 1                           every file of the run, with its size
excavation.json> results get 1 kratos.log --out logs/      copy one into logs\ (made if need be)
excavation.json> results archive 1                         the whole run as a .zip, here
```

---

## Part 6: keep the model

### Step 15. Open it in the GUI

The project file and the runs are the GUI's own:

1. Start the GUI (`run.bat`) and **Open** `excavation.json`. You see the model you typed: layers,
   wall, strut, loads and stages.
2. **Results** mode lists the same runs. Open `Excavation_wall_2026-10-12_04-00` for
   the deformed mesh, the contours and the wall plots.

### Step 16. Save it as a Python script

```text
excavation.json> script --out excavation_model.py
wrote excavation_model.py: Excavation wall (2D section at z = 5, SI)
next: run excavation_model.py in the GUI's command box, or python excavation_model.py --out deck/
```

`excavation_model.py` holds the whole model as readable Python, every value typed out. Next time,
start from it instead of typing the model again:

| Where | What |
|---|---|
| the GUI's command box | `run excavation_model.py` opens the model |
| PowerShell, in the repository root | `.\kratos-cli.bat show D:\work\excavation\excavation_model.py`, and every command that only reads a model |
| PowerShell, in the repository root | `.\.venv-windows\Scripts\python.exe D:\work\excavation\excavation_model.py --calculate` writes the deck and runs it |

### Step 17. Leave the shell

```text
excavation.json> exit
```

---

## The whole model in one go

Put steps 1 to 12 in a text file, one shell line per command (a line that starts with `#`
is a comment), say `excavation.txt` in `D:\work\excavation`. Any of these then builds
`excavation.json` and `deck/` in a few seconds, in the folder the shell is in:

| From | Type |
|---|---|
| inside the shell, after `cd D:\work\excavation` | `source excavation.txt` |
| PowerShell, in `D:\work\excavation` | `Get-Content excavation.txt \| D:\Checkouts\Private\Kratos-GUI\kratos-cli.bat shell` |
| cmd, in `D:\work\excavation` | `D:\Checkouts\Private\Kratos-GUI\kratos-cli.bat shell < excavation.txt` |

Read from a file like this, the shell echoes each line and stops at the first command that
fails, naming its line. Then go on with part 4: `run deck`, `results profile 1 wall M`.

---

## When something goes wrong

| What you see | What it means |
|---|---|
| `error: ...`, and nothing changed | The command was refused as a whole, and the project was not written. The message names the field. |
| `no stage matches 'dig_3'` | `--stage` takes the stage's number or words of its name, not the phase id. |
| `error: no project is open` | Start with `new FILE` or `open FILE`, or name the project on the line. |
| `warning: Derived where a property set left them out` | Expected for this interface: see step 12. |
| `'/c/Users/...' is not a run` | A Git Bash path given to a Windows program. Use `C:/Users/...`, or the run's number. |
| `nothing to undo` | `undo` steps back only through commands of this shell session that changed the project. |
| What a command takes | `help COMMAND` in the shell, or `.\kratos-cli.bat COMMAND --help` in PowerShell. |

Every command is described in [CLI.md](CLI.md).
