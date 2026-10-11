# The command line: `kratos-cli`

`kratos-cli` does in the terminal what the GUI does in the browser: it builds a model, meshes
it, defines the construction phases, writes the Kratos deck, runs it and reads the results
back. It needs no server and no browser.

It works on the same project file the GUI's **Save** writes. A model can move between the two
at any point: build it on the command line and open it in the GUI to look at it, or save it in
the GUI and run it from a script.

## Starting it

From the repository root, or from any folder by its path:

```bash
kratos-cli.bat --help                       # Windows
./kratos-cli.sh --help                      # Linux and macOS
python -m cli --help                        # from the repository root, in its environment
```

The wrappers use the environment `run.bat` / `run.sh` make (`.venv-windows`, `.venv-linux`,
`.venv-macos`). If it is not there yet, they make it first. They run in your folder, so a
relative path you type is relative to where you are.

`kratos-cli <command> --help` lists what each command takes.

## From an empty site to results

```bash
kratos-cli new site.json --demo --dim 2 --name "Pit A"   # or without --demo: an empty site
kratos-cli show site.json
kratos-cli water site.json -2
kratos-cli set site.json mesh.element_size 1.5
kratos-cli mesh site.json
kratos-cli phases site.json defaults
kratos-cli check site.json
kratos-cli export site.json --out deck/      # Pit_A.mdpa, MaterialParameters.json, ProjectParameters.json
kratos-cli run deck/
kratos-cli results runs
kratos-cli results show 1
```

`kratos-cli calculate site.json` does `export` and `run` in one step, like the GUI's Calculate
button.

## The commands

| Command | What it does |
|---|---|
| `new FILE [--dim 2\|3] [--units SI\|kN] [--name NAME] [--demo] [--force]` | Write a new project file: an empty site, or the demo model |
| `show P` | What the model holds: layers, materials, parts, structures, water, phases, mesh |
| `check P` | That the phases run in one order and the mesh settings name only parts the model has |
| `build SCRIPT.py --out FILE` | Write the project a model script describes |
| `get P [PATH]` | Print a field as JSON (the whole project without a path) |
| `set P PATH VALUE` | Set a field |
| `add P PATH VALUE` | Add a record to a list |
| `remove P PATH` | Remove a record, or a key of a mapping |
| `dimension P 2d\|3d [--offset Z]` | Switch between the plane-strain section and the solid model |
| `units P [SI\|kN]` | Show the unit system, or convert the whole project to another |
| `water P [LEVEL\|off]` | Show, set or remove the water level |
| `domain P [--x FROM TO] [--y BOTTOM TOP] [--z FROM TO]` | Show or set the model's extents |
| `borehole P list\|add\|set\|remove ...` | Boreholes: a new one copies the last one's levels, and every layer gets levels there |
| `material P list\|presets\|add\|set\|remove ...` | Soils as Kratos property sets: `add ID [--preset m3] [NAME=VALUE ...]`, `set ID NAME=VALUE ... [--unset NAME]` |
| `layer P list\|add\|set\|split\|remove ...` | The soil stack: `add ID --material M [--bottom Y \| --thickness T]`, `set ID --bottom Y [--at BH]` |
| `excavation P [--x FROM TO] [--z FROM TO] [--levels Y ...]` | The pit, and the levels it is dug to, one lift each |
| `volume P list\|add\|import\|remove\|clear ...` | Solids drawn or imported into the model; with `--material` they are soil |
| `parts P` | Every part by its key, the names phases activate and deactivate |
| `mesh P [--size S] [--order 1\|2]` | Mesh the model and report its size. `--size` and `--order` are kept in the project |
| `phases P [list\|defaults]` | List the phases, or make the initial stage and the null step |
| `export P --out DIR [--name NAME]` | Write the Kratos deck into `DIR` |
| `run DECK [--runs-dir DIR] [--timeout S]` | Run a deck directory (or its `ProjectParameters.json`) |
| `calculate P [--runs-dir DIR] [--timeout S]` | `export` and `run` in one step |
| `results runs [--runs-dir DIR]` | The runs on this machine, newest first, numbered |
| `results show RUN [--runs-dir DIR]` | A run's stages, its files and whether it finished; `RUN` is its id or its number |

`P` is a project file (`.json`), or a model script (`.py`) for the commands that only read the
model: `show`, `check`, `get`, `mesh` (without `--size` or `--order`), `export` and `calculate`.

## The ground, command by command

An empty site, built up to a staged excavation. The numbers are in the project's units
(SI unless `new --units kN`).

```bash
kratos-cli new pit.json --name "Pit B"
kratos-cli domain pit.json --x 0 60 --y -40 0 --z 0 10
kratos-cli borehole pit.json set bh1 --water -1
kratos-cli material pit.json presets                      # the library a soil can start from
kratos-cli material pit.json add clay --preset m3 YOUNG_MODULUS=2e6 K0_NC=0.58
kratos-cli material pit.json add sand --preset m5
kratos-cli layer pit.json add top --material clay --bottom -7
kratos-cli layer pit.json add mid --material clay --bottom -10
kratos-cli layer pit.json add bottom --material sand --bottom -40
kratos-cli excavation pit.json --x 0 6 --z 0 10 --levels -2 -4.5 -7
kratos-cli water pit.json -1
kratos-cli parts pit.json                                 # soil_top__lift1, ... for the phases
```

- **Boreholes** carry the soil stack. A new borehole is put 10 m past the last one and
  copies its levels, unless you give `--x`, `--y`, `--head` and `--water`. A model keeps at
  least one.
- **Layers** are stacked from the top. `add` puts a layer under the last one, down to
  `--bottom` or `--thickness` below it (5 m by default). `set --top` or `--bottom` moves a
  level and the neighbour's with it, at every borehole or only `--at` one, and refuses a
  level that would cross the neighbour. `split` halves a layer, and `remove` closes the
  gap with the layer above.
- **Materials** start as the GUI starts them: the default loose sand, or a library preset
  (`--preset`). The law follows the model's dimension, and the values are converted into
  the project's units. Variables given as `NAME=VALUE` are Kratos' own, in the project's
  units.
- **The excavation** is dug in its `--levels`, shallowest first. Each lift is a body of
  its own, deactivated in its own phase. In a layered model, a pit with one level is not
  dug at all, and the command says so.
- **Volumes**: in 2D, `volume add polygon --points x y x y ...` is an outline in the
  section plane, swept across the whole model. In 3D, `polygon` takes `x y z` points and
  `--extrude dx dy dz`, and there are `box` (`--origin`, `--size`) and `cylinder`
  (`--center`, `--axis`, `--radius`). `volume import FILE` reads .step, .iges, .brep, .stl
  or .obj. With `--material`, a volume is soil.
- **Coordinates are plain numbers**, `--points 0 0 6 0 3 2`, because a word starting with
  a minus, like `-3,2`, would be read as an option. A long outline can come from a file:
  `--points @outline.csv`, one point per line.

## Fields, by path

`get`, `set`, `add` and `remove` reach any field. A path names fields with dots and picks a
record in a list by its id in brackets:

```bash
kratos-cli get site.json layers[L1].tops
kratos-cli set site.json materials[m1].variables.YOUNG_MODULUS 2.5e7
kratos-cli add site.json phases '{"id": "dig_1", "name": "Dig", "parent": "null_step", "deactivate": ["soil_L1"]}'
kratos-cli add site.json materials @clay.json
kratos-cli remove site.json materials[clay2]
```

- A record is picked by its `id` (a custom part by its `key`). A list without ids takes a
  position from 0: `mesh.refinements[0].size`. A mapping takes its key either way:
  `layers[L1].tops[bh1]` or `layers[L1].tops.bh1`.
- A value is read as JSON when it is JSON (`1.5`, `true`, `null`, `[1, 2]`, `{"y": -2}`) and as
  text otherwise, so `set site.json name Pit A` needs no quotes. A number meant as text does:
  `'"12"'`. `@file.json` reads the value from a file.
- Every edit is checked as a whole model before it is written. A refusal names the field.
- `dimension`, `section_offset` and `unit_system` are not set by path. Switching them changes
  the rest of the model too, so they have their own commands.

## Where an edit is written

An edit is written back to the file it was read from. `--out FILE` writes it somewhere else and
leaves the original as it was. `--dry-run` makes and checks the edit, and writes nothing. A
model script is never written: an edit of one needs `--out`.

## The deck and the runs

`export` writes the deck the GUI's **Export** writes for the same project: the `.mdpa`,
`MaterialParameters.json`, `ProjectParameters.json`, `initial_materials.json` when there is a
K0 stage, and `kratos_gui_units.json`, the unit system of the results (Kratos ignores it). The
files are named after the project; `--name mesh` names them `mesh.mdpa`.

`run` copies the deck into a directory of its own under the runs root and runs it there, so
the deck stays as it was and every run is kept. The runs root is `KRATOS_GUI_RUNS`, or
`~/KratosGUI/runs`, which the GUI's Results mode reads too. `--runs-dir` puts the run somewhere
else. Kratos is found the way the GUI finds it: [KRATOS_SETUP.md](KRATOS_SETUP.md).

## Output and exit codes

Output is text for a person to read. `--json` (before or after the command) prints JSON for a
script instead. The exit code is 0 when the command did what it was asked, 1 when the model, a
file or Kratos refused it, and 2 when the command line itself could not be read. A refusal is
printed on stderr as `error: <reason>`; with `--json` it is also printed on stdout as
`{"ok": false, "error": ...}`. The exporter's warnings go to stderr as `warning: ...`.
