# Simple dike with `kratos-cli`

A 2D plane-strain model of a soil block with a sheet pile and a surface load, built and run
from PowerShell.

| Part | What it is |
|---|---|
| **Soil** | a 20 m × 10 m block, from (0, 0) to (20, 10), linear elastic |
| **Sheet pile** | a steel beam at x = 10, from the surface (y = 10) down to y = 3 |
| **Load** | 10 kPa downward on the surface, from x = 10 to x = 20 |
| **Mesh** | 1 m linear triangles |
| **Stages** | 1 K0 on the soil alone → 2 the sheet pile is installed → 3 the load is applied |

There are three ways to work with it. Pick one:

| | Way | Start from | Good for |
|---|---|---|---|
| [1](#1-build-the-model-from-scratch) | Build it from scratch in the shell | nothing | learning the commands, making your own model |
| [2](#2-open-the-ready-made-model-in-the-shell) | Open the ready-made model in the shell | `simple_dike.py` | looking around the model and its results |
| [3](#3-run-the-python-script) | Run the Python script | `simple_dike.py` | one command: write, run, summarise |

In the commands below, `<repo>` is the folder you cloned this repository into, such as
`C:\Users\you\Styx-Kratos-GUI`. The ready-made model is in
[`examples/simple_dike/`](examples/simple_dike/).

---

## 1. Build the model from scratch

The model typed command by command, from geometry to results, in a new folder of your choice.
The folder is made if it is not there, and the runs are written into it too.

The only thing it needs is Kratos on this machine. If `kratos.local.json` is not in the
repository root yet, follow steps 1 and 2 of [Setting up Kratos](docs/KRATOS_SETUP.md)
first. The very first run also builds the Python environment (`.venv-windows`), which can
take a few minutes.

### Step by step

Open an empty shell:

```powershell
<repo>\kratos-shell.bat   # asks for a "path" + "folder name" to create
```

Then type these lines. Lines starting with `#` are comments; `.` is the new folder.

```text
# 1. A new 2D project; the shell opens it, and every edit is saved into it
new simple_dike.json --dim 2 --name simple_dike

# 2. The soil block, and a borehole with the ground at 10 (dry: water at the bottom)
domain --x 0 20 --y 0 10 --z 0 10
borehole set bh1 --name BH1 --x 0 --y 0 --head 10 --water 0

# 3. The soil: a material, and one layer down to y = 0
material add m_soil --name soil --color "#c4a86a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=CONSTANT_PW_FIELD YOUNG_MODULUS=2.0e7 POISSON_RATIO=0.3 DENSITY_SOLID=1834.8623853211009 DENSITY_WATER=1019.367991845056 POROSITY=0.0 BULK_MODULUS_SOLID=1e10 BULK_MODULUS_FLUID=2.2e9 DYNAMIC_VISCOSITY=1e-3 PERMEABILITY_XX=1e-5 PERMEABILITY_YY=1e-5 PERMEABILITY_XY=0.0 GEO_COHESION=1000.0 GEO_FRICTION_ANGLE=30.0 K0_NC=0.5
layer add soil --name soil --material m_soil --bottom 0

# 4. The sheet pile: a steel section, and the beam from (10, 10) to (10, 3)
section add beam steel --name "Sheet pile" YOUNG_MODULUS=2.1e11 POISSON_RATIO=0.0 DENSITY=7850.0 CROSS_AREA=0.015 I33=3e-4 AREA_EFFECTIVE_Y=0.0075
beam add sheetpile_1 --name sheetpile_1 --section steel --points 10 10 10 3

# 5. The load: 10 kPa down, on the surface from x = 10 to 20
load add line load --name Load --x 10 20 --y 10 --components 0 -10000

# 6. The mesh: 1 m, linear
set mesh.element_size 1
set mesh.order 1

# 7. The stages
phases add initial --name "Initial stage" --calculation k0 --deactivate sheetpile_1 load
phases add sheet_pile --name "Sheet pile" --activate sheetpile_1 --reset-displacements --max-iterations 150 --tolerance 1e-3
phases add loading --name Load --activate load --max-iterations 150 --tolerance 1e-3

# 8. Check it, write the input files, run Kratos, read the results
show
check
export --out .
run .
results show 1
results field 1 uy
results profile 1 wall M

# 9. Optional: save the model as a Python script, like simple_dike.py
script --out simple_dike.py

exit
```

> [!TIP]
> - `undo` and `redo` step back and forward through the edits.
> - `help COMMAND` lists what a command takes.
> - `source FILE` runs the lines of a file from inside the shell.
> - Later, `kratos-shell.bat` on that folder, then `open simple_dike.json`, opens the model again.

### All in one go

[`simple_dike.json`](examples/simple_dike/simple_dike.json) is the whole model: the same file the
step-by-step commands above build, and the one the GUI saves. Open the shell in the new
folder, as above:

```powershell
<repo>\kratos-shell.bat $HOME\my_dike
```

Then open the JSON file and calculate it. `calculate` meshes the model, writes the Kratos
input files into a run folder in `my_dike` in your home folder, and runs them:

```text
open <repo>\examples\simple_dike\simple_dike.json
calculate
results show 1
exit
```

To make another model, copy `simple_dike.json`, change its values (sizes, materials,
stages, ...), and `open` your copy instead. `check` says whether it can be meshed and staged.

---

## Before ways 2 and 3

Run [`kratos-init-powershell.bat`](kratos-init-powershell.bat), at the repository root: double-click it, or
from PowerShell:

```powershell
<repo>\kratos-init-powershell.bat
```

It asks for the **project folder**: the folder that holds the model's `.py` file, such as
`<repo>\examples\simple_dike`.

It then opens a PowerShell that is ready for ways 2 and 3:

- it is in the project folder;
- `$repo`, `$model`, `$cli` and `$py` are set (it prints them);
- `KRATOS_GUI_RUNS` is the project folder, so runs are written there and read from there;
- the first time, it builds the Python environment (`.venv-windows`), which can take a few
  minutes.

If Kratos is not set up on this machine yet, it says so and stops: follow steps 1 and 2 of
[Setting up Kratos](docs/KRATOS_SETUP.md), then run it again. `exit` closes the
PowerShell it opened.

> [!IMPORTANT]
> Type every command that uses `$repo`, `$model`, `$cli` or `$py` in **that** PowerShell.
> In any other window they are empty, and PowerShell answers with an error such as
> *The term '\kratos-cli.bat' is not recognized*.

---

## 2. Open the ready-made model in the shell

In the PowerShell from [Before ways 2 and 3](#before-ways-2-and-3), open the shell on
`simple_dike.py`:

```powershell
& $cli shell simple_dike.py
```

Then type these lines. `.` is the model's folder, and `1` is the newest run.

```text
# The model
show
parts
phases list

# Write the input files, then run them
export --out .
run .

# The runs and their stages
results runs
results show 1
results fields 1

# Fields: last stage by default, or pick one with --stage (a number or a name)
results field 1 uy
results field 1 uy --stage 2
results field 1 syy
results at 1 6

# The sheet pile: M, Q, N, ux or uy along it
results members 1
results profile 1 wall M

# Every value, to a CSV file
results field 1 uy --csv uy.csv

exit
```

---

## 3. Run the Python script

In the same PowerShell:

```powershell
& $py simple_dike.py                      # write the input files into this folder
& $py simple_dike.py --calculate          # write them, run Kratos, print a results summary
& $py simple_dike.py --out $HOME\deck     # write them somewhere else instead
```

`--calculate` prints the stages, the settlement (`uy`), the horizontal displacement (`ux`)
and the bending moment along the sheet pile. To look further, open the model in the shell
([way 2](#2-open-the-ready-made-model-in-the-shell)) and use its `results` lines.

---

## One command at a time, without the shell

Every shell line also works on its own: put `& $cli` in front, and the model file after the
command name. In the model's folder:

```powershell
& $cli show   simple_dike.py                 # what the model holds
& $cli parts  simple_dike.py                 # its parts
& $cli phases simple_dike.py list            # its stages
& $cli export simple_dike.py --out .         # write the input files
& $cli run    . --runs-dir .                 # run Kratos
& $cli results field 1 uy --runs-dir .       # read a result
```

## What gets written

| File | What it is |
|---|---|
| `simple_dike.json` | the model (way 1 only; ways 2 and 3 read `simple_dike.py`) |
| `simple_dike.mdpa`, `ProjectParameters.json`, `MaterialParameters.json`, ... | the Kratos input files (the deck) |
| `simple_dike_<date>_<time>\` | one folder per run: a copy of the deck, `kratos.log`, the results (`*.post.res`, `*.post.msh`) and the sheet-pile curves (`*_output_wall.json`) |
| `uy.csv` | every `uy` value, if you asked for it with `--csv` |
