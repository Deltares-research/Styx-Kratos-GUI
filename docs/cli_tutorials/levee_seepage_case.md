# Groundwater flow: seepage through a levee with `kratos-cli`

A steady-state groundwater flow under and through a clay levee, built and run from
PowerShell. The commands build the same model as
[`examples/levee_seepage/levee_seepage.py`](../../examples/levee_seepage/levee_seepage.py):
the Kratos input files they write are identical.

For the ready-made model and a comparison of its results with a reference calculation are in
[`examples/levee_seepage/`](../../examples/levee_seepage/README.md).

## What you build

A 2D plane-strain section, 90 m wide and 28 m high, in SI units (m, N, Pa, kg/m³):

![Levee section](levee_model.svg)


- A sand aquifer from y = −22 to −2 m and a clay cover from −2 to 0 m, across the section.
- A clay levee on the cover, drawn as two polygons: a core, which reaches 0.5 m into the
  cover, and an outer layer around it, with its crest from (0, 6) to (4, 6).
- The river, at 5.0 m, holds the left side, the foreland and the outer slope; the right
  side is held at the polder level, −0.5 m. The inner slope and the polder surface are a
  seepage face. The crest and the bottom are closed.
- One stage of the type Groundwater flow. There is no construction sequence, so this
  tutorial does not go into stages.

## Before you start

- Kratos must be set up on this machine: see [Setting up Kratos](../KRATOS_SETUP.md).
- Work in a folder of your own, so the files stay out of the repository.
- In the commands, `kratos-cli` is `<repo>\kratos-cli.bat`, where `<repo>` is the folder
  you cloned this repository into. It is convenient to make it a name in your PowerShell, and write the runs
  into your folder too:

```powershell
Set-Alias kratos-cli <repo>\kratos-cli.bat
$env:KRATOS_GUI_RUNS = (Get-Location)
```

Every command below can then be pasted as it is.

## Step 1. The project and the section

```text
PS> kratos-cli new levee.json --force --dim 2 --name levee_seepage
wrote levee.json: levee_seepage (2D section at z = 0, SI)

PS> kratos-cli domain levee.json --x -36 54 --y -22 6
domain x -36 .. 54, y -22 .. 6 (2D section at z = 0); wrote levee.json
```

The name `levee_seepage` also names the deck's files (`levee_seepage.mdpa`).

## Step 2. The soils

All four soil bodies share one set of flow properties, as in the model script:

| Property | Value |
|---|---|
| saturated hydraulic conductivity K | 1 m/day, isotropic |
| `PERMEABILITY_XX`, `_YY` | K μ / (ρw g) = 1.1574074074074074e-12 m², with a water unit weight of 10 kN/m³ |
| `DYNAMIC_VISCOSITY` | 1e-3 Pa s |
| `DENSITY_WATER` | 10 000 / 9.81 = 1019.367991845056 kg/m³ |
| `RETENTION_LAW` | `VanGenuchtenLaw` |
| `VAN_GENUCHTEN_AIR_ENTRY_PRESSURE` | 10 000 / ga = 2610.9660574412533 Pa, with ga = 3.83 1/m |
| `VAN_GENUCHTEN_GN`, `_GL` | 1.3774, 1.25 |
| `RESIDUAL_SATURATION` | 0.0620347394540943 |
| `MINIMUM_RELATIVE_PERMEABILITY` | 1e-4 |

Only the permeability, the viscosity, the water density and the retention law change the
flow. Kratos' flow element checks that the other values are there. The values are typed
out in full, so they are the script's to the last digit. A new soil starts from the
default sand, which has Young's modulus, Poisson's ratio, a cohesion, a friction angle etc.; these properties will not be used in the intended flow computation here.
As they also do not harm the computation, they are left as is. You may use `material m_sand --unset <property>` to remove them.

```text
PS> kratos-cli material levee.json add m_sand --name Sand --color "#e6c86e" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=FULLY_COUPLED YOUNG_MODULUS=1e4 POISSON_RATIO=0.3 DENSITY_SOLID=2650.0 DENSITY_WATER=1019.367991845056 POROSITY=0.3333333333333333 BULK_MODULUS_SOLID=1e20 BULK_MODULUS_FLUID=1e20 PERMEABILITY_XX=1.1574074074074074e-12 PERMEABILITY_YY=1.1574074074074074e-12 PERMEABILITY_XY=0.0 DYNAMIC_VISCOSITY=1e-3 BIOT_COEFFICIENT=1.0 RETENTION_LAW=VanGenuchtenLaw SATURATED_SATURATION=1.0 RESIDUAL_SATURATION=0.0620347394540943 VAN_GENUCHTEN_AIR_ENTRY_PRESSURE=2610.9660574412533 VAN_GENUCHTEN_GN=1.3774 VAN_GENUCHTEN_GL=1.25 MINIMUM_RELATIVE_PERMEABILITY=1e-4
added material m_sand; wrote levee.json

PS> kratos-cli material levee.json add m_clay --name Clay --color "#8fa37a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=FULLY_COUPLED YOUNG_MODULUS=1e4 POISSON_RATIO=0.3 DENSITY_SOLID=2650.0 DENSITY_WATER=1019.367991845056 POROSITY=0.3333333333333333 BULK_MODULUS_SOLID=1e20 BULK_MODULUS_FLUID=1e20 PERMEABILITY_XX=1.1574074074074074e-12 PERMEABILITY_YY=1.1574074074074074e-12 PERMEABILITY_XY=0.0 DYNAMIC_VISCOSITY=1e-3 BIOT_COEFFICIENT=1.0 RETENTION_LAW=VanGenuchtenLaw SATURATED_SATURATION=1.0 RESIDUAL_SATURATION=0.0620347394540943 VAN_GENUCHTEN_AIR_ENTRY_PRESSURE=2610.9660574412533 VAN_GENUCHTEN_GN=1.3774 VAN_GENUCHTEN_GL=1.25 MINIMUM_RELATIVE_PERMEABILITY=1e-4
added material m_clay; wrote levee.json
```

> [!TIP]
> Write `2650.0`, `1.0` and `0.0`, not `2650`, `1` and `0`: a whole number is kept as
> one, and the deck then says `2650` where the script's says `2650.0`. Kratos reads both
> the same; the files only differ in that.

## Step 3. The layers

The first layer starts at the top of the domain (here the top of the dike at 6 m), so the cover's top is moved down to
the ground surface at 0 m. The levee comes on top of it in step 4.

```text
PS> kratos-cli layer levee.json add cover --name Cover --material m_clay --bottom -2
added layer cover; wrote levee.json

PS> kratos-cli layer levee.json set cover --top 0
changed layer cover; wrote levee.json

PS> kratos-cli layer levee.json add aquifer --name Aquifer --material m_sand --bottom -22
added layer aquifer; wrote levee.json

PS> kratos-cli layer levee.json list
cover  Cover  of m_clay: 0 .. -2
aquifer  Aquifer  of m_sand: -2 .. -22
```

## Step 4. The levee

The levee is created by drawing two polygons drawn in the section, each a soil body of clay. The core runs
from (−14, 0) up to 4.5 m and down to (18, 0), and reaches 0.5 m into the cover; a drawn
part takes the place of the layer it overlaps. The outer layer wraps the core, from
(−18, 0) over the crest to (22, 0):

```text
PS> kratos-cli volume levee.json add polygon --label "Levee core" --material m_clay --points -14 0 0 4.5 4 4.5 18 0 4 -0.5 0 -0.5
added drawn_0 (Levee core, soil of m_clay); wrote levee.json

PS> kratos-cli volume levee.json add polygon --label "Levee outer layer" --material m_clay --points -18 0 0 6 4 6 22 0 18 0 4 4.5 0 4.5 -14 0
added drawn_1 (Levee outer layer, soil of m_clay); wrote levee.json
```

`volume add` names a drawn part `drawn_0`, `drawn_1`, ..., gives it its material's colour
and keeps its label in its recipe. The model script calls the parts `levee_core` and
`levee_outer`, draws them grey. These lines make the
parts the script's:

```text
PS> kratos-cli set levee.json "custom_parts[drawn_0].key" levee_core
custom_parts[drawn_0].key = "levee_core"; wrote levee.json

PS> kratos-cli set levee.json "custom_parts[drawn_1].key" levee_outer
custom_parts[drawn_1].key = "levee_outer"; wrote levee.json

PS> kratos-cli set levee.json "custom_parts[levee_core].color" "#888888"
custom_parts[levee_core].color = "#888888"; wrote levee.json

PS> kratos-cli set levee.json "custom_parts[levee_outer].color" "#888888"
custom_parts[levee_outer].color = "#888888"; wrote levee.json

PS> kratos-cli parts levee.json
soil_cover  Cover
soil_aquifer  Aquifer
levee_core  Levee core (soil of m_clay)
levee_outer  Levee outer layer (soil of m_clay)
```

The key is what the stages and the deck's part names use; the colour shows in the GUI.

## Step 5. The water

A new project has standard supports that block the normal movement of sides by rollers and fix the bottom motion in all directions.
A groundwater flow calculation does not make use of them. The front and back rollers are there
for a 3D model and are not listed in 2D:

```text
PS> kratos-cli boundary levee.json list
fixed_bottom  Fixed bottom  displacement on the bottom face; fixed in x y z
roller_left  Roller left  displacement on the left face; fixed in x
roller_right  Roller right  displacement on the right face; fixed in x
The front and back supports are kept for the solid model; the 2D section holds z by itself.
```

The riverside boundary condition specifies the water level in the river and includes the left side, the foreland and the outer slope up to the crest's outer
corner, all as one line that connects the line pieces. The polder side boundary condition specifies the far field groundwater level in the polder on the right side:

```text
PS> kratos-cli boundary levee.json add river_head --name "River head" --line -36 -22 -36 0 -18 0 0 6 --water-pressure Hydrostatic --reference-coordinate 5 --pressure-tension-cut-off 1e5
added river_head  River head  water pressure on line (-36, -22) -> (-36, 0) -> (-18, 0) -> (0, 6); hydrostatic about 5 m, cut-off 100000, fixed; wrote levee.json

PS> kratos-cli boundary levee.json add polder_head --name "Polder head" --line 54 0 54 -22 --water-pressure Hydrostatic --reference-coordinate -0.5 --pressure-tension-cut-off 1e5
added polder_head  Polder head  water pressure on line (54, 0) -> (54, -22); hydrostatic about -0.5 m, cut-off 100000, fixed; wrote levee.json
```

`--pressure-tension-cut-off 1e5` lets the suction above each level grow to 100 kPa. The
river head also holds the outer slope above 5.0 m, up to the crest, where it is 10 kPa of
suction.

The water may leave the soil through the inner slope and the polder surface, from the
crest's inner corner (4, 6) on:

```text
PS> kratos-cli boundary levee.json add seepage_face --name "Seepage face" --seepage --line 4 6 22 0 54 0
added seepage_face  Seepage face  seepage on line (4, 6) -> (22, 0) -> (54, 0); water may leave the soil here; wrote levee.json
```

The crest, from (0, 6) to (4, 6), and the bottom have no boundary condition specified, so no water flows
through them.

The flow is nonlinear, because of the Van Genuchten retention law and the seepage face, and the
nonlinear iteration strategy starts from a given initial field for the water pressure. These are hydrostatic below a phreatic line that
drops through the levee from the river level to the polder level. `--initial` makes them
start values only, which the calculation then changes:

```text
PS> kratos-cli boundary levee.json add start --name "Start values" --domain --water-pressure Phreatic_Multi_Line --phreatic-line -36 5 -2 5 15 -0.5 54 -0.5 --pressure-tension-cut-off 1e5 --initial
added start  Start values  water pressure on the whole soil; phreatic line (-36, 5) -> (-2, 5) -> (15, -0.5) -> (54, -0.5), cut-off 100000, initial; wrote levee.json

PS> kratos-cli boundary levee.json list
fixed_bottom  Fixed bottom  displacement on the bottom face; fixed in x y z
roller_left  Roller left  displacement on the left face; fixed in x
roller_right  Roller right  displacement on the right face; fixed in x
river_head  River head  water pressure on line (-36, -22) -> (-36, 0) -> (-18, 0) -> (0, 6); hydrostatic about 5 m, cut-off 100000, fixed
polder_head  Polder head  water pressure on line (54, 0) -> (54, -22); hydrostatic about -0.5 m, cut-off 100000, fixed
seepage_face  Seepage face  seepage on line (4, 6) -> (22, 0) -> (54, 0); water may leave the soil here
start  Start values  water pressure on the whole soil; phreatic line (-36, 5) -> (-2, 5) -> (15, -0.5) -> (54, -0.5), cut-off 100000, initial
The front and back supports are kept for the solid model; the 2D section holds z by itself.
```

The supports stay in the list, but the Groundwater flow stage does not use them, so they
do not change the deck. The last line is printed for every 2D model.

## Step 6. The calculation and the mesh

One stage, of the type Groundwater flow. Kratos' seepage strategy opens or closes one
node of the seepage face per iteration, and the face has about 55 nodes on this mesh,
the stage allows 300 iterations to allow for opening or closing of all these nodes and convergence of the water pressure field.
The mesh is made with linear interpolation triangles of 1 m:

```text
PS> kratos-cli stages levee.json add flow --name Flow --calculation flow
added stage (id flow, name Flow) after nothing: it is the first; wrote levee.json

PS> kratos-cli stages levee.json set flow --max-iterations 300 --tolerance 1e-4
changed stage flow; wrote levee.json

PS> kratos-cli set levee.json mesh.element_size 1
mesh.element_size = 1; wrote levee.json

PS> kratos-cli set levee.json mesh.order 1
mesh.order = 1; wrote levee.json
```

If a stage allows fewer iterations than its seepage faces have nodes, `export` and
`calculate` warn that it may stop too soon.

## Step 7. Check it

```text
PS> kratos-cli check levee.json
ok: levee_seepage (2D section at z = 0, SI)

PS> kratos-cli show levee.json
levee_seepage  (levee.json)
  2D plane strain, SI units, section at z = 0.5
  domain      x -36 .. 54, y -22 .. 0
  materials   m_sand, m_clay
  layers      cover, aquifer
  parts       soil_cover, soil_aquifer, levee_core, levee_outer
  structures  none
  water       none
  conditions  fixed_bottom (displacement on the bottom face), roller_left (displacement on the left face), roller_right (displacement on the right face), river_head (water pressure on line (-36, -22) -> (-36, 0) -> (-18, 0) -> (0, 6)), polder_head (water pressure on line (54, 0) -> (54, -22)), seepage_face (seepage on line (4, 6) -> (22, 0) -> (54, 0)), start (water pressure on the whole soil)
  gravity     on
  stages      flow
  mesh        element size 1, order 1
```

`show` gives the domain as `y -22 .. 0`: the command line keeps the domain's top at the
top of the first layer, the ground surface. The levee above it is drawn parts, which the
mesher takes as they are, so the mesh and the Kratos input files do not depend on the
domain's top.

## Step 8. Run it

```text
PS> kratos-cli calculate levee.json
run levee_seepage_<YYYY-MM-DD>_<hh-mm> finished in <t> s: 3 files in <your folder>\levee_seepage_<YYYY-MM-DD>_<hh-mm>
next: kratos-cli results show levee_seepage_<YYYY-MM-DD>_<hh-mm>

PS> kratos-cli results show 1
levee_seepage_<YYYY-MM-DD>_<hh-mm>  (deck levee_seepage, started <YYYY-MM-DD>T<hh:mm>)
  complete, SI units, 8 files, 1013.4 KB
    1  Flow                          results
```

`calculate` meshes the model, writes the deck into a new run folder and runs Kratos there.
The run folder is in `KRATOS_GUI_RUNS`, the folder you set it to; `1` is the newest run.
The parts in `<...>` differ with every run: `<YYYY-MM-DD>` and `<hh-mm>` are the date and
time the run started, `<t>` is how long it took (about 25 s), and `<your folder>` is the
folder `KRATOS_GUI_RUNS` is set to.


## Step 9. The results

```text
PS> kratos-cli results field 1 pw
Pore pressure (Pa), stage 1 (Flow): -2.70e+5 to 16796 over 2628 nodes
  min -2.70e+5 at node 9
  max 16796 at node 16
`--csv` writes every value.

PS> kratos-cli results field 1 flow_rate
Nodal water flow rate (m³/s/m), stage 1 (Flow): -3.08e-6 to 6.10e-6 over 2628 nodes
  min -3.08e-6 at node 236
  max 6.10e-6 at node 15
`--csv` writes every value.

PS> kratos-cli results field 1 effective_saturation
Effective saturation (-), stage 1 (Flow): 0.4838 to 1.04 over 2628 nodes
  min 0.4838 at node 16
  max 1.04 at node 2565
`--csv` writes every value.
```

- Kratos' sign for the water pressure is suction positive. The fixed river head gives compression of
  −270 kPa at the bottom left corner. The largest suction, 16.8 kPa, is in the soil of
  the outer layer at the crest's inner corner (4, 6), where the soil is least saturated.
- `flow_rate` is the water each node takes in (negative) or lets out (positive), per
  metre of the section. The water comes in from the river and leaves through the seepage
  face and the polder side.
- Kratos calculates the saturation at the Gauss points and extrapolates it to the nodes,
  so it can show a little above 1.

What these results mean, and how they compare with a reference calculation of the same
section, is in the example's [README](../../examples/levee_seepage/README.md#the-results).

## The same model as the script

To check that the commands built the model script's model, write the script's model as a
project file and export both:

```powershell
kratos-cli build <repo>\examples\levee_seepage\levee_seepage.py --out script.json
kratos-cli export levee.json --out deck_cli
kratos-cli export script.json --out deck_script
```

The two decks, `levee_seepage.mdpa`, `ProjectParameters.json`, `MaterialParameters.json`
and `kratos_gui_units.json`, are identical: Kratos calculates the same model.

## In the GUI

Open `levee.json` with **File > Open project…** and click **Calculate**. To see the runs
made above, start the GUI with the runs root set to your folder:

```powershell
$env:KRATOS_GUI_RUNS = (Get-Location); <repo>\run.bat
```

In **Results**, show **Pore pressure**, **Hydraulic head**, **Effective saturation** or
**Nodal water flow rate**. The seepage face is in **Model conditions > Boundary
conditions** in the Model explorer.

## In the shell

The same commands work in `kratos-cli shell`, one per line, without `kratos-cli` and the
project file: `new levee.json --force --dim 2 --name levee_seepage`, then
`domain --x -36 54 --y -22 6, and so on. See also [CROW_case.md](CROW_case.md) for the
shell, and [CLI.md](../CLI.md) for every command.




