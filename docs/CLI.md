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
./kratos-cli.sh --help                      # Linux and macOS, and Git Bash on Windows
python -m cli --help                        # from the repository root, in its environment
```

The wrappers use the environment `run.bat` / `run.sh` make (`.venv-windows`, `.venv-linux`,
`.venv-macos`). If it is not there yet, they make it first. They run in your folder, so a
relative path you type is relative to where you are. In Git Bash on Windows, `kratos-cli.sh`
uses `.venv-windows`, as `kratos-cli.bat` does, so a shell script of commands runs there too.

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
kratos-cli results field 1 uy
```

`kratos-cli calculate site.json` does `export` and `run` in one step, like the GUI's Calculate
button.

A whole model to start from is in [`examples/CROW_case/`](../examples/CROW_case/README.md): the
CROW excavation wall, as a project file (`crow.json`) and as a model script (`crow.py`).

## The commands

| Command | What it does |
|---|---|
| `new FILE [--dim 2\|3] [--units SI\|kN] [--name NAME] [--demo] [--force]` | Write a new project file: an empty site, or the demo model |
| `show P` | What the model holds: layers, materials, parts, structures, water, phases, mesh |
| `check P` | That the phases run in one order and the mesh settings name only parts the model has |
| `build SCRIPT.py --out FILE` | Write the project a model script describes |
| `script P --out FILE.py [--force]` | Write the model as a model script: the Python file that builds it again |
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
| `section P list\|add\|set\|remove ...` | The sections structures are built with: `add beam\|panel\|anchor\|interface ID [NAME=VALUE ...]` |
| `beam P list\|add\|set\|remove ...` | Sheet piles, in 2D: `add [ID] [--points x y ...] [--section S]` |
| `wall P list\|add\|set\|remove ...` | Walls, in 3D: `add [ID] [--footprint x z ...] [--top Y] [--toe Y]` |
| `member P list\|add\|set\|remove ...` | Piles, king posts and struts in 3D: `add [ID] [--points x y z ...]` |
| `anchor P list\|add\|set\|remove ...` | Anchors and struts: `add [ID] [--head ...] [--tail ...] [--prestress S]`, the head snapped onto a structure |
| `interface P list\|add\|set\|remove ...` | Interfaces, in 2D: `add [ID] [--structure PILE \| --points ...] [--side both\|left\|right]` |
| `load P list\|add\|set\|remove ...` | Loads: `add point [--at X Y]`, `add line [--x FROM TO]` (2D), `add surface [--x ...] [--z ...]` (3D), `--components ...` |
| `normal-load P list\|add\|set\|remove ...` | Pressures normal to a line, in 2D: `add [ID] --points ... [--hydrostatic \| --pressure S]` |
| `parts P` | Every part by its key, the names phases activate and deactivate |
| `mesh P [--size S] [--order 1\|2]` | Mesh the model and report its size. `--size` and `--order` are kept in the project |
| `phases P [list\|show\|defaults\|staged-excavation\|add\|copy\|set\|remove\|activate\|deactivate] ...` | The construction sequence, edited as the GUI's Phases toolbar edits it |
| `node SOURCE NODE ...` | Which SubModelParts a node of the deck is in, and the nodes an interface split from it |
| `deck show SOURCE` | A deck's mesh, SubModelParts and stages |
| `export P --out DIR [--name NAME]` | Write the Kratos deck into `DIR` |
| `run DECK [--runs-dir DIR] [--timeout S]` | Run a deck directory (or its `ProjectParameters.json`) |
| `calculate P [--runs-dir DIR] [--timeout S]` | `export` and `run` in one step |
| `results runs [--runs-dir DIR]` | The runs on this machine, newest first, numbered |
| `results show\|stages\|files RUN` | A run's stages, its files and whether it finished; `RUN` is its id, its number, or a run directory |
| `results fields\|field\|at RUN ... [--stage S]` | What a stage can show, one field (`--csv` for every value), every field at one node |
| `results members\|profile RUN ...` | The walls and interfaces the run wrote curves for, and one quantity along one, stage by stage (`--csv`) |
| `results get\|archive RUN ...` | A copy of one file of a run, or the whole run as a zip |
| `shell [P]` | Type commands one after another, without `kratos-cli` and the project file |

`P` is a project file (`.json`), or a model script (`.py`) for the commands that only read the
model: `show`, `check`, `get`, the `list` actions, `parts`, `phases show`, `node`, `mesh`
(without `--size` or `--order`), `export` and `calculate`.

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

## The structures, command by command

The wall, the props and the loads of the pit above, then its stages:

```bash
kratos-cli section pit.json add beam az26 --name "AZ 26" CROSS_AREA=0.015 I33=3e-4
kratos-cli beam pit.json add sheet --points 6 0 6 -12        # on az26, the first profile
kratos-cli anchor pit.json add strut --head 6 -1 --tail 5 -1
kratos-cli anchor pit.json add tie --head 6.3 -3.5 --prestress 1e5
kratos-cli interface pit.json add contact --structure sheet
kratos-cli load pit.json add line surcharge --x 6 60 --components 0 -10000
kratos-cli normal-load pit.json add water_1 --hydrostatic --points 6 -1 6 -2 0 -2
kratos-cli set pit.json mesh.body_sizes.sheet 0.5
```

- **Where a new one goes.** A structure given no geometry is put where the GUI's tool
  puts a new one: a sheet pile down the middle of the section to half its depth, a wall
  across the middle of the site, an anchor a quarter of the way down the first pile and
  raking back 10 m at 35 degrees, an interface on the first pile, a 20 kN load. An id not
  given is the first free one, as in the GUI (`beam_1`, `anchor_2`, `load_3`).
- **Sections.** A structure is built with the first section of its kind, or `--section`.
  The first structure of a kind brings the GUI's default section with it (an AZ 26
  profile, a 0.4 m wall, a four-strand tendon, a contact), and the command says so.
  `section set ID NAME=VALUE ...` changes its Kratos variables, in the project's units,
  and `--unset NAME` leaves one out for the export to derive. `--spacing` belongs to beam
  and anchor sections; `--tension-limit` and `--compression-limit` to anchors;
  `--material`, `--r-inter`, `--virtual-thickness` and `--permeability` to interfaces.
  `none` clears an optional one.
- **Dimensions.** A sheet pile, an interface, a normal load and point and line loads are
  2D; a wall, a member and a surface load are 3D. Switching the dimension carries walls
  and loads across, as the GUI does (`dimension`).
- **Anchors.** The head is snapped onto the nearest pile, wall or member within a metre,
  because it becomes one of its nodes; a head further away is refused. With no `--tail`,
  the anchor rakes back from its head. A strut is an anchor whose tail is a pinned support.
- **Removing.** A structure a phase names, or a pile an anchor or an interface depends
  on, is not removed; the refusal names what still uses it. A section in use is not
  removed either.
- **Ids are part keys.** A phase switches a structure by its id, so no two parts share
  one, and `wall`, `struts`, `anchors`, `piles`, `water`, `wells` and `excavation` are
  taken.

## The stages, command by command

A phase says what it changes about the model it starts from: the parts it switches on and
off, and how it is solved. `kratos-cli parts P` lists the keys a phase can switch.

```bash
kratos-cli phases pit.json staged-excavation       # derived from the model, all at once
# or one by one:
kratos-cli phases pit.json defaults                # the initial stage and the null step
kratos-cli phases pit.json deactivate initial sheet strut tie contact surcharge water_1
kratos-cli phases pit.json add wall --name Wall --activate sheet contact surcharge --reset-displacements
kratos-cli phases pit.json add dig_1 --name "Dig 1" --activate water_1 --deactivate soil_top__lift1 --max-iterations 150 --tolerance 1e-3
kratos-cli phases pit.json add props --name "Strut and tie" --activate strut tie
kratos-cli phases pit.json add dig_2 --name "Dig 2" --deactivate soil_top__lift2
kratos-cli phases pit.json show dig_2              # what is in the model then
kratos-cli phases pit.json list
```

- **`staged-excavation`** derives the whole sequence from the model, as a model script's
  `phases.staged_excavation_phases` does: settle the ground, install each wall with its
  interfaces and the loads, then dig lift by lift with its water load, each anchor after
  the lift that exposes its head. **`defaults`** makes only the initial stage and the
  null step, as the GUI's Create default phases does. Both replace the sequence there is.
- **`add [ID]`** puts a phase at the end of the sequence (the toolbar's Add); with
  `--before PHASE` it goes between that phase and the one it starts from (Insert).
  **`copy PHASE`** puts a phase with the same solver settings right after `PHASE` (Copy),
  and the phases after it then start from the copy. **`remove`** heals the chain: the
  removed phase's children start from its parent.
- **`activate` / `deactivate PHASE KEY ...`** put parts in or out of the model from that
  phase on, as the Model explorer's checkbox does, with the smallest instruction that
  does it: switching a part back to what the phase inherits drops the instruction.
  `add` and `copy` take `--activate` and `--deactivate` the same way.
- **`set PHASE`** changes `--name`, `--calculation k0|plastic|null`,
  `--reset-displacements` / `--keep-displacements`, `--max-iterations`, `--tolerance`
  (the residual relative tolerance), `--time-interval` (days) and `--parent`.
- A sequence that would branch, two phases starting from one, is refused, because Kratos
  runs one sequence. So is a part the model does not have.

## The shell

```text
> kratos-cli shell pit.json
pit.json> water -2
pit.json> borehole add bh2 --x 30
pit.json> undo
pit.json> phases staged-excavation
pit.json> calculate
pit.json> results field 1 uy
pit.json> exit
```

`kratos-cli shell P` opens the project and reads commands one after another. A line is a
`kratos-cli` command without `kratos-cli` and without the project file; the shell puts
the open project where the command takes one (`borehole P add`, `node P 30`). A project
named on the line is the one used (`water other.json -3`), and a command that takes no
project, `results` or `run`, is given none. Everything else is the command as it is in the
terminal: the same options, answers, `--json`, refusals and exit codes.

- **Its own words:** `open FILE`, `close`, `new FILE ...` (which opens what it makes),
  `undo` and `redo` (the edits of the open project, one command each, as in the GUI),
  `cd DIR`, `pwd`, `source FILE` (the lines of a file), `help [COMMAND]`, `exit`.
- **Typed at a terminal**, it goes on after a command fails. On Linux and macOS, Tab
  completes a command and its action, and the lines are kept in `~/.kratos_cli_history`;
  in Windows' console the arrow keys recall the lines of this session.
- **Read from a file or a pipe**, `kratos-cli shell pit.json < build.txt` (in PowerShell,
  which has no `<`: `Get-Content build.txt | kratos-cli.bat shell pit.json`), each line is
  echoed as `> line` and the first command that fails stops it, with exit code 1 and the
  number of the line. `source FILE` reads a file the same way inside the shell.
- **Words** are split as a shell splits them: quotes group (`--name "Soft clay"`), and a
  line that starts with `#` is a comment, but a `#` inside a word is not (`--color
  "#c4a86a"`). A backslash stays as typed, so a Windows path needs no doubling.
- **It is fast.** Every command runs in the one process, so a line costs no new Python:
  a model of forty commands that takes forty seconds as forty `kratos-cli` calls takes a
  few seconds in the shell.

## The model as a script

```bash
kratos-cli script pit.json --out pit.py       # the whole model, as one Python file
kratos-cli show pit.py                        # every command that reads a model takes it
python pit.py --out deck/                     # its Kratos deck, as `kratos-cli export` writes it
python pit.py --calculate                     # and run it, as Calculate does
```

`script` writes the model as the Python that builds it again: a `project()` that returns
it, grouped as a hand-written model script is (the site, the soil, the structures, the
loads, the mesh, the phases), one constructor per record, with Kratos' own variable names as
the keys. The next session opens that file instead of typing the model again: `run pit.py`
in the GUI's command box, or `kratos-cli ... pit.py`. In the GUI, `script pit.py` writes the
same file from the open model.

- **Every value is typed out.** The file says `x0=6.0`, not why. It is plain Python, so
  constants and loops can be put in by hand afterwards. A field left at its default is left
  out.
- **The file runs on its own.** `python pit.py --out deck/` writes `ProjectParameters.json`,
  `MaterialParameters.json` and the `.mdpa`; `--calculate` also runs them. `python` is the
  environment `kratos-cli` runs in (`.venv-windows\Scripts\python.exe` on Windows). The
  file names the checkout it was written from, where it finds `core`; change that line when
  the checkout moves.
- **Drawn and imported solids** are `.brep` files under `.data/`, which the project points
  at. When one is gone, the script builds it again: a drawn solid from its recipe, an
  imported one from the file it was imported from, which `volume import` records. A solid
  imported in the GUI's browser has no file to go back to; import it again with
  `kratos-cli volume import` to make the script carry it.
- **A deck case** is written as the `deck_project(...)` it was opened with.
- An existing file is replaced only with `--force`: a script may have been edited by hand.

## Looking into a deck

```bash
kratos-cli deck show deck/          # the mesh, its SubModelParts and the stages
kratos-cli node deck/ 30 34         # which SubModelParts nodes 30 and 34 are in
kratos-cli node pit.json 30         # the same, for the deck pit.json would export
```

`node` gives the parts a node is in by the number the `.mdpa` gives it, and the other
nodes at its position: an interface splits a wall's node into two or three, one for each
side. `SOURCE` is a deck directory, its `ProjectParameters.json`, an `.mdpa`, or a project.
For a project the deck is written in memory, which meshes the model.

## Reading the results

```bash
kratos-cli results runs                             # numbered, newest first
kratos-cli results show 1                           # its stages, and whether it finished
kratos-cli results fields 1                         # what the last stage can show
kratos-cli results field 1 uy                       # its range, and where it is reached
kratos-cli results field 1 syy --stage "first excavation" --csv syy.csv
kratos-cli results at 1 1234 --stage 4              # every field at node 1234
kratos-cli results members 1                        # wall, interface, and their quantities
kratos-cli results profile 1 wall M --csv wall_M.csv
kratos-cli results profile 1 interface normal       # the normal traction, by a word of it
kratos-cli results get 1 kratos.log --out logs/
kratos-cli results archive 1                        # <run>.zip, here
kratos-cli results field D:/copied/Pit_A_2026-10-12_09-14 uy   # a run anywhere
```

- **`RUN`** is a run's id, its number in `results runs`, or the path of a run directory,
  wherever it is: one copied off another machine reads the same, whatever its folder is
  called.
- **`--stage`** takes a stage's number or words of its phase. Without it, the last stage
  that wrote results is read, which is where the GUI's Results mode opens a run.
- **A field** is one of the names `results fields` lists, as in the GUI's results log
  (`u`, `uy`, `syy`, `p`, `q`, `pw`, ...). A stress is read per element, as the solver
  computed it, unless `--location nodes` averages it onto the nodes.
- **`profile MEMBER [QUANTITY]`**: `M`, `Q`, `N`, `ux`, `uy` along a wall, `tn`, `ts` along
  an interface, or a word of the label (`moment`, `shear`, `normal`). Without a quantity it
  is the bending moment. `--stage` narrows it to one stage.
- **`--csv FILE`** writes the file the GUI saves (`results csv`, and the plot window's
  `results plot csv`), number for number, in UTF-8. `--csv` alone prints it, for a pipe;
  in Windows PowerShell 5.1, `>` would save that as UTF-16, so give the file instead. `--json` gives what the GUI's `/api/results`
  routes answer for the same question.
- The numbers are the run's own, in its project's units, which `results show` names.

## The GUI's command box, in the terminal

Every command the GUI's command box answers, and what does the same in the terminal.
`tests/cli/test_gui_commands.py` reads the command box's dispatchers and fails while a
command it answers is missing here, so a new one has to be mapped or said to be the
viewport's. A command can also be typed with a leading `_` in the box (`_mesh`).

| In the command box | In the terminal |
|---|---|
| `run <file.py>`, `load <file.py>` | `kratos-cli build SCRIPT.py --out P`; or give the `.py` to any command that only reads the model |
| `script <file.py> [--force]` | `kratos-cli script P --out FILE.py` |
| `export` | `kratos-cli export P --out DIR` |
| `mesh` | `kratos-cli mesh P` |
| `phases` | `kratos-cli phases P` |
| `water <level>`, `water off` | `kratos-cli water P LEVEL`, `kratos-cli water P off` |
| `units`, `units <system>` | `kratos-cli units P`, `kratos-cli units P kN` |
| `node <id>` | `kratos-cli node P NODE` |
| `cleargeometry` | `kratos-cli volume P clear` |
| `borehole <x> <y>` | `kratos-cli borehole P add --x X --y Y` |
| `soillayers` | `kratos-cli layer P`, `kratos-cli borehole P` (the window, as commands) |
| `materials` | `kratos-cli material P` (the window, as commands) |
| `calculate` | `kratos-cli calculate P` (the box only says to press Calculate) |
| `help` | `kratos-cli --help` |
| `soillayer`, `plate`, `beam`, `anchor` | `kratos-cli layer P add`, `kratos-cli wall P add`, `kratos-cli beam P add`, `kratos-cli anchor P add` (the box answers these with a placeholder and builds nothing) |
| `point`, `line`, `surface` | — a placeholder answer in the box; nothing is built |
| `colour <part>`, `color <part>` | — the viewport's: a part drawn in its own colour |
| `view iso\|top\|front\|side`, `zoomfit`, `clear` | — the viewport's and the log's |
| `gotosoil`, `gotostructures`, `gotomesh`, `gotoflow`, `gotoflowconditions`, `gotostaged` | — the viewport's: the mode tabs |
| `results` | `kratos-cli results show RUN` |
| `results runs`, `results list` | `kratos-cli results runs` |
| `results open <id\|n>` | `kratos-cli results show RUN`: every `results` command names its run |
| `results phase <n\|name>`, `results stage <n\|name>` | `--stage S` on `kratos-cli results fields\|field\|at\|profile` |
| `results fields` | `kratos-cli results fields RUN` |
| `results field <name> [nodes\|elements]` | `kratos-cli results field RUN NAME --location nodes` |
| `results at <node>` | `kratos-cli results at RUN NODE` |
| `results csv` | `kratos-cli results field RUN NAME --csv FILE` |
| `results plot [member] [quantity]` | `kratos-cli results profile RUN MEMBER QUANTITY` |
| `results plot members`, `results plot list` | `kratos-cli results members RUN` |
| `results plot csv` | `kratos-cli results profile RUN MEMBER --csv FILE` |
| `results plot svg` | — the viewport's: a picture of the plot |
| `results files` | `kratos-cli results files RUN` |
| `results get <file>` | `kratos-cli results get RUN FILE` |
| `results zip`, `results archive` | `kratos-cli results archive RUN` |
| `results deform`, `results bands`, `results smooth`, `results map`, `results range`, `results mesh`, `results reverse`, `results reversed` | — the viewport's: how a field is drawn |

While a drawing tool is placing points, typing `x y` or `x y z` places the next one. In the
terminal, the points are the command's own: `--points`, `--head`, `--at`.

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
`--csv`, for the commands with a table (`results field`, `results profile`), prints that
table as CSV, or writes it into the file it is given; it does not go with `--json`.
