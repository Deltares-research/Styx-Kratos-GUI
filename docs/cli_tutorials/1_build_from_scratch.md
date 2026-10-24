# Simple dike, way 1: build the model from scratch

Part of [Simple dike with `kratos-cli`](README.md), which describes the model and the other
two ways to work with it.

Here you type the model command by command, from the geometry to the results, in a new
folder of your choice. The folder is made if it is not there, and the runs are written
into it too.

**Before you start**

- Kratos must be set up on this machine. If `kratos.local.json` is not in the repository
  root yet, follow steps 1 and 2 of [Setting up Kratos](../KRATOS_SETUP.md) first.
- The very first run builds the Python environment (`.venv-windows`), which can take a few
  minutes.
- In the commands below, `<repo>` is the folder you cloned this repository into, such as
  `C:\Users\you\Styx-Kratos-GUI`.

## Step by step

Open an empty shell. It asks for the folder to work in:

```powershell
<repo>\cli\kratos-shell.bat
```

```text
Folder for the model and its runs: C:\Users\you\simple_dike

kratos-cli shell: type one command per line. The open project is used, so leave out its file name.
help lists the commands, help COMMAND explains one, exit closes the shell.

No project is open. Start one with new FILE, or open one with open FILE.

kratos-cli>
```

No project is open yet: the first line below makes one. Type the lines below, or paste
them all at once. Lines starting with `#` are comments, and `.` is the folder you chose.

```text
# 1. A new 2D project. simple_dike.json is the file the model is saved in, after every
#    command; --name is the model's name, which also names the Kratos input files.
#    Axes: x runs across the section, y points up, z runs out of the section.
new simple_dike.json --dim 2 --name simple_dike

# 2. The soil block, 20 m wide and 10 m high.
#    The ground is at y = 10, the top of the domain: the first layer starts there.
#    A 2D model is a vertical cut through the site at one z (z = 0 in a new project).
#    The site's z extent matters only when the model is switched to 3D, so `domain`
#    is given no --z here.
domain --x 0 20 --y 0 10

# 3. The soil: one linear elastic material, and one layer of it down to y = 0.
#    --color is the colour the GUI draws the soil in, as #rrggbb. Colour names such
#    as brown are refused.
#    A new material starts with the values of the GUI's default loose sand. The lines
#    below replace them. The variables have Kratos' own names, in the project's units
#    (SI here). `get materials[m_soil].variables` lists the values a material has.
material add m_soil --name soil --color "#c4a86a" --law GeoLinearElasticPlaneStrain2DLaw
#    Stiffness: E = 20 MPa
material set m_soil YOUNG_MODULUS=2.0e7 POISSON_RATIO=0.3
#    Weight: 18 kN/m3 soil and 10 kN/m3 water, as densities (kg/m3)
material set m_soil DENSITY_SOLID=1834.8623853211009 DENSITY_WATER=1019.367991845056 POROSITY=0.0
#    Water: a fixed pore pressure field, and the soil's permeability (m2)
material set m_soil GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD BULK_MODULUS_SOLID=1e10 BULK_MODULUS_FLUID=2.2e9 DYNAMIC_VISCOSITY=1e-3
material set m_soil PERMEABILITY_XX=1e-5 PERMEABILITY_YY=1e-5 PERMEABILITY_XY=0.0
#    Strength (c = 1 kPa, phi = 30 degrees) and the K0 for the initial stresses.
#    K0_NC can be left out: the export then writes 1 - sin(phi), which is 0.5 here too.
material set m_soil GEO_COHESION=1000.0 GEO_FRICTION_ANGLE=30.0 K0_NC=0.5
layer add soil --name soil --material m_soil --bottom 0
#    The block stands on the supports a new project has: the bottom fixed and the sides
#    on rollers. It is dry, so it needs no water pressure condition.
boundary list

# 4. The sheet pile: define its steel and cross-section properties, then place a 2D beam
#    from the ground surface at (10, 10) down to its toe at (10, 3).
#    In `section add beam ID`, the id is how later commands refer to the section. A section
#    has no separate material: its steel properties are set on it below.
section add beam sheet_pile --name "Sheet pile"
#    Steel: E = 210 GPa, 7850 kg/m3
section set sheet_pile YOUNG_MODULUS=2.1e11 POISSON_RATIO=0.0 DENSITY=7850.0
#    Profile, per metre of wall: area (m2), bending stiffness I (m4), shear area (m2)
section set sheet_pile CROSS_AREA=0.015 I33=3e-4 AREA_EFFECTIVE_Y=0.0075
beam add sheetpile_1 --name sheetpile_1 --section sheet_pile --points 10 10 10 3

# 5. The load: 10 kN/m downward on the ground surface, from x = 10 to x = 20.
#    In the 2D section the ground surface is a line, so this is a line load.
#    In `load add line surcharge`, line is the kind of load and surcharge is its id.
#    The stages in step 7 switch the load by this id. --name Load is what the GUI shows
#    and what the Kratos files call it. Leave the id out and the name is the id as well.
#    --components is its x and y force per metre, in N/m: 0 -10000.
load add line surcharge --name Load --x 10 20 --y 10 --components 0 -10000

# 6. The mesh: about 1 m elements, linear (order 1): 3-node triangles in the soil and
#    2-node beam elements along the sheet pile, which share the soil's nodes.
#    --order 2 would give 6-node triangles. The settings are kept in the project, and
#    the model is meshed once as a check: 278 nodes, 492 elements (the soil triangles).
#    The two settings are the fields mesh.element_size and mesh.order, which
#    `set mesh.element_size 0.5` also changes, but `set` does not mesh or count.
#    A finer mesh makes a longer run: 0.4 m at order 2 on a 20 m x 20 m block gave
#    11,860 nodes and a run of about two minutes on a laptop.
mesh --size 1 --order 1

# 7. The stages: K0 on the soil alone, then the sheet pile, then the load.
#    Every part starts in the model, so the first stage switches off what is not built yet:
#    the sheet pile and the load. The later stages switch them back on, one at a time.
#    An option left out takes its default: --calculation plastic, --max-iterations 15,
#    --tolerance 1e-4, and the displacements of the stage before are kept.
#    `stages show initial` prints a stage's settings. The solver is the same for every
#    stage; "The stages, command by command" in docs/CLI.md says what it is.
stages add initial --name "Initial stage" --calculation k0 --deactivate sheetpile_1 surcharge
stages add sheet_pile --name "Sheet pile" --activate sheetpile_1 --reset-displacements --max-iterations 150 --tolerance 1e-3
stages add loading --name Load --activate surcharge --max-iterations 150 --tolerance 1e-3

# 8. Check the model, write the input files, run Kratos and read the results.
#    `run .` prints nothing until Kratos has finished. Its run folder, with a copy of
#    the input files, is made in your folder at the start; kratos.log is added at the end.
#    In `results show 1`, 1 is the run's number in `results runs` (1 is the newest),
#    not a stage. The stages it lists are picked with --stage, e.g. --stage 2.
show
check
export --out .
run .
results show 1
results field 1 uy
results profile 1 wall M

# 9. Optional: save the model as a Python script, like simple_dike.py.
script --out simple_dike.py

exit
```

> [!TIP]
> - `undo` and `redo` step back and forward through the edits.
> - `help COMMAND` lists what a command takes. Its usage line shows the project file as
>   `project`, which the shell fills in: leave it out.
> - A hint such as `next: kratos-cli results show ...` can be pasted as it is: the shell
>   ignores a leading `kratos-cli`.
> - `source FILE` runs the lines of a file from inside the shell.
> - To open the model again later, run `cli\kratos-shell.bat` on the same folder, then
>   `open simple_dike.json`.

The shell reads the results as numbers and CSV files; it draws no pictures. To see a
field drawn on the mesh, start the GUI on the same runs folder and open the run in its
Results mode. In PowerShell:

```powershell
$env:KRATOS_GUI_RUNS = "C:\Users\you\simple_dike"
<repo>\run.bat
```

## All in one go

[`simple_dike.json`](../../examples/simple_dike/simple_dike.json) is the whole model: the
file the steps above build, and the same file the GUI saves.

Open the shell in a new folder:

```powershell
<repo>\cli\kratos-shell.bat $HOME\my_dike
```

Then open the JSON file and calculate it. `calculate` meshes the model, writes the Kratos
input files into a run folder in `my_dike`, and runs them:

```text
open <repo>\examples\simple_dike\simple_dike.json
calculate
results show 1
exit
```

To make a model of your own, copy `simple_dike.json`, change its values (sizes,
materials, stages, ...) and `open` your copy instead. `check` tells you whether it can be
meshed and staged.

What ends up in the folder is listed in [What gets written](README.md#what-gets-written).
