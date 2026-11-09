# CROW excavation wall, from the command line

A 2D excavation pit behind a sheet pile wall with one strut, dug in three lifts, as
`kratos-cli` builds and runs it. It is the Mohr-Coulomb case of the CROW model that Kratos
validates itself with. The same model is here twice:

| File | What it is |
|---|---|
| `crow.json` | The project file, as the GUI's **Save** and `kratos-cli new` write it |
| `crow.py` | The model script `kratos-cli script crow.json --out crow.py` writes from it |

Every command that reads a model takes either one. The commands below run from this folder;
from anywhere else, give the paths to `kratos-cli` and the files.

## The model

- **Site**: 80 m wide, 60 m deep, groundwater at -1.5 m.
- **Soil**: `Soil_Top` (0 to -8 m) and `Soil_Middle` (-8 to -12 m) of *Clay*, and
  `Soil_Bottom` (-12 to -60 m) of *Sand*, both Mohr-Coulomb. The wall interface is a
  Coulomb interface that takes each soil's own strength reduction.
- **Structures**: a sheet pile wall at x = 5 m down to -13 m, with a wall interface, and a
  strut at -1.5 m.
- **Loads**: a 20 kN/m surcharge behind the wall, and the water in the pit at each lift.
- **Lines**: the wall and two lines cut the clay into three lifts, to -2, -5 and
  -8 m. Each lift is a soil body that a stage switches off.
- **Stages**: initial stage (K0 procedure), null step, wall installation, first
  excavation, strut installation, second and third excavation.

## The project file

```bash
kratos-cli.bat check crow.json           # Windows; ./kratos-cli.sh on Linux, macOS, Git Bash
kratos-cli.bat show crow.json
kratos-cli.bat stages crow.json list
kratos-cli.bat export crow.json --out deck/
kratos-cli.bat run deck/
kratos-cli.bat results show 1
kratos-cli.bat results field 1 uy
```

`kratos-cli calculate crow.json` does `export` and `run` in one step. `kratos-cli.bat` is in
the repository root (`..\..\kratos-cli.bat` from here), or on your `PATH`.

An edit such as `kratos-cli set crow.json mesh.element_size 4` writes into `crow.json`. To try changes
without touching the example, copy it first.

## The model script

```bash
kratos-cli.bat check crow.py             # every command that reads a model takes the script
python crow.py --out deck/               # write the Kratos deck
python crow.py --calculate               # write the deck and run it
```

`python` is the environment `kratos-cli` runs in: `..\..\.venv-windows\Scripts\python.exe`
on Windows, `../../.venv-linux/bin/python` on Linux. The script finds the checkout from its
own location, so it runs wherever the repository is.

The script is plain Python: put in constants or loops, change a value, and run it again.
`kratos-cli` commands that edit a model only edit `crow.json`; they do not write the script.
To bring the script up to date with the project file:

```bash
kratos-cli.bat script crow.json --out crow.py --force
```

That writes the checkout's own path into `ROOT`; put back
`ROOT = Path(__file__).resolve().parents[2]` before committing it.

The commands are all in [docs/CLI.md](../../docs/CLI.md).
