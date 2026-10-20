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

# 2. The soil block, 20 m wide and 10 m high, and a borehole.
#    The ground is at y = 10 and the water at y = 0, so the soil is dry.
#    A 2D model is a vertical cut through the site at one z (z = 0 in a new project).
#    The site's z extent matters only when the model is switched to 3D.
#    A borehole is placed on the map, as in the GUI: its --x and --y are map coordinates
#    (map y is the model's z). Its levels are --head (ground) and --water.
domain --x 0 20 --y 0 10
borehole set bh1 --name BH1 --x 0 --y 0 --head 10 --water 0

# 3. The soil: one linear elastic material, and one layer of it down to y = 0.
material add m_soil --name soil --color "#c4a86a" --law GeoLinearElasticPlaneStrain2DLaw
#    Stiffness: E = 20 MPa
material set m_soil YOUNG_MODULUS=2.0e7 POISSON_RATIO=0.3
#    Weight: 18 kN/m3 soil and 10 kN/m3 water, as densities (kg/m3)
material set m_soil DENSITY_SOLID=1834.8623853211009 DENSITY_WATER=1019.367991845056 POROSITY=0.0
#    Water: a fixed pore pressure field, and the soil's permeability (m2)
material set m_soil GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD BULK_MODULUS_SOLID=1e10 BULK_MODULUS_FLUID=2.2e9 DYNAMIC_VISCOSITY=1e-3
material set m_soil PERMEABILITY_XX=1e-5 PERMEABILITY_YY=1e-5 PERMEABILITY_XY=0.0
#    Strength (c = 1 kPa, phi = 30 degrees) and the K0 for the initial stresses
material set m_soil GEO_COHESION=1000.0 GEO_FRICTION_ANGLE=30.0 K0_NC=0.5
layer add soil --name soil --material m_soil --bottom 0

# 4. The sheet pile: a steel section, and a beam of it from (10, 10) down to (10, 3).
section add beam steel --name "Sheet pile"
#    Steel: E = 210 GPa, 7850 kg/m3
section set steel YOUNG_MODULUS=2.1e11 POISSON_RATIO=0.0 DENSITY=7850.0
#    Profile, per metre of wall: area (m2), bending stiffness I (m4), shear area (m2)
section set steel CROSS_AREA=0.015 I33=3e-4 AREA_EFFECTIVE_Y=0.0075
beam add sheetpile_1 --name sheetpile_1 --section steel --points 10 10 10 3

# 5. The load: 10 kPa downward on the surface, from x = 10 to x = 20.
load add line surcharge --name Load --x 10 20 --y 10 --components 0 -10000

# 6. The mesh: 1 m elements, linear.
set mesh.element_size 1
set mesh.order 1

# 7. The stages: K0 on the soil alone, then the sheet pile, then the load.
phases add initial --name "Initial stage" --calculation k0 --deactivate sheetpile_1 surcharge
phases add sheet_pile --name "Sheet pile" --activate sheetpile_1 --reset-displacements --max-iterations 150 --tolerance 1e-3
phases add loading --name Load --activate surcharge --max-iterations 150 --tolerance 1e-3

# 8. Check the model, write the input files, run Kratos and read the results.
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
> - `help COMMAND` lists what a command takes.
> - `source FILE` runs the lines of a file from inside the shell.
> - To open the model again later, run `cli\kratos-shell.bat` on the same folder, then
>   `open simple_dike.json`.

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
