# The command line: `kratos-cli`

`kratos-cli` does in the terminal what the GUI does in the browser: it builds a model, meshes
it, defines the construction stages, writes the Kratos deck, runs it and reads the results
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

`kratos-cli <command> --help` lists what each command takes. `kratos-cli --version` says
which version of Styx you have, as **Help > About** does in the GUI. Give it in a bug report.

## From an empty site to results

```bash
kratos-cli new site.json --demo --dim 2 --name "Pit A"   # or without --demo: an empty site
kratos-cli show site.json
kratos-cli water site.json -2                 # the level a new water pressure condition takes
kratos-cli boundary site.json set pore_pressure --reference-coordinate -2
kratos-cli set site.json mesh.element_size 1.5
kratos-cli mesh site.json
kratos-cli stages site.json add                 # the initial stage (an empty site has it already)
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
[`examples/Muskat_case/`](../examples/Muskat_case/README.md) is a groundwater flow model: the
semi-Muskat column of Kratos' tests, with a saturated soil (an exact answer) and a Van
Genuchten soil.

## The commands

| Command | What it does |
|---|---|
| `new FILE [--dim 2\|3] [--units SI\|kN] [--name NAME] [--demo] [--force]` | Write a new project file: an empty site, or the demo model |
| `show P` | What the model holds: layers, materials, parts, structures, water, conditions, gravity, stages, mesh |
| `check P` | That the stages run in one order, the mesh settings name only parts the model has and a groundwater flow project can be exported, and what the export will warn about the boundary conditions |
| `build SCRIPT.py --out FILE` | Write the project a model script describes |
| `script P --out FILE.py [--force]` | Write the model as a model script: the Python file that builds it again |
| `get P [PATH]` | Print a field as JSON (the whole project without a path) |
| `set P PATH VALUE` | Set a field |
| `add P PATH VALUE` | Add a record to a list |
| `remove P PATH` | Remove a record, or a key of a mapping |
| `dimension P 2d\|3d [--offset Z]` | Switch between the plane-strain section and the solid model |
| `units P [SI\|kN]` | Show the unit system, or convert the whole project to another |
| `water P [LEVEL\|off]` | Show, set or remove the water level. It fixes no pressure by itself: a new hydrostatic condition or normal load takes it as its level |
| `fluid P [--bulk-modulus K] [--viscosity MU] [--unset FIELD ...]` | Show or set the water in every soil's pores, one for the whole project: `BULK_MODULUS_FLUID` and `DYNAMIC_VISCOSITY`. Unset, each is water's at 20 °C |
| `domain P [--x FROM TO] [--y BOTTOM TOP] [--z FROM TO]` | Show or set the model's extents. `--y` is the bottom and the ground level; with layers, it moves the top of the first layer and the bottom of the last |
| `material P list\|presets\|models\|add\|set\|remove ...` | Soils as Kratos property sets: `add ID [--preset m3] [--model mohr-coulomb] [NAME=VALUE ...]`, `set ID [--model M] NAME=VALUE ... [--unset NAME]`; `models` lists each soil model with its parameters and defaults |
| `layer P list\|add\|set\|split\|remove ...` | The soil stack: `add ID --material M [--bottom Y \| --thickness T]`, `set ID [--top Y] [--bottom Y]` |
| `line P list\|add\|set\|remove ...` | The lines that split the soil: `add ID --points X Y X Y ...` |
| `body P list\|set ...` | The soil bodies by their keys: `set KEY [--name NAME] [--material M]` |
| `volume P list\|add\|import\|remove\|clear ...` | Solids drawn or imported into the model; with `--material` they are soil |
| `section P list\|add\|set\|remove ...` | The sections structures are built with: `add beam\|panel\|anchor\|interface ID [NAME=VALUE ...]` |
| `beam P list\|add\|set\|remove ...` | Sheet piles, in 2D: `add [ID] [--points x y ...] [--section S]` |
| `wall P list\|add\|set\|remove ...` | Walls, in 3D: `add [ID] [--footprint x z ...] [--top Y] [--toe Y]` |
| `member P list\|add\|set\|remove ...` | Piles, king posts and struts in 3D: `add [ID] [--points x y z ...]` |
| `anchor P list\|add\|set\|remove ...` | Anchors and struts: `add [ID] [--head ...] [--tail ...] [--prestress S]`, the head snapped onto a structure |
| `interface P list\|add\|set\|remove ...` | Interfaces, in 2D: `add [ID] [--structure PILE [--from X Y] [--to X Y] \| --points ...] [--side both\|left\|right\|below\|above]`; `set ID --whole-pile` |
| `load P list\|add\|set\|remove ...` | Loads: `add point [--at X Y]`, `add line [--x FROM TO]` (2D), `add surface [--x ...] [--z ...]` (3D), `--components ...` |
| `normal-load P list\|add\|set\|remove ...` | Pressures normal to a line, in 2D: `add [ID] --points ... [--hydrostatic [--reference-coordinate Y] \| --pressure S]` |
| `boundary P list\|add\|set\|remove\|standard ...` | The boundary conditions: `add [ID] --face F\|--part KEY\|--line ...\|--point X Y --fixed\|--roller\|--fix AXIS ...` for a support, `add [ID] --domain\|... --water-pressure TYPE ...` for a water pressure, `add [ID] --face F\|--line ... --seepage` for a seepage face; `standard` puts back the standard supports |
| `gravity P [G]` | Show whether the self weight acts, or set g in m/s² (9.81 in a new project). The initial stage's stress initialisation decides whether the self weight acts |
| `parts P` | Every part by its key, and every support, water pressure condition and seepage face: the names stages activate and deactivate |
| `mesh P [--size S] [--order 1\|2] [--body-size KEY S] [--band KEY B]` | Mesh the model and report its size. The settings given are kept in the project, as the **Mesh properties** window keeps them. `--body-size` is the element size at one object, by its key: a layer (`soil_<layer>`) or soil body, a sheet pile, an anchor (at its head), an interface, a normal load, a soil line, a load, a boundary condition, or a face of the model (`face_bottom`, `face_left`, `face_right`, `face_top`, and in 3D `face_front`, `face_back`). A condition on a face keeps its size as the size of that face, and a condition on a soil part as the size of that part; a condition on the whole soil is refused. `none` takes the size and its band away. `--band` is the distance over which that size grows back to the element size; `none` takes it away |
| `stages P [list\|show\|add\|copy\|set\|remove\|activate\|deactivate] ...` | The construction sequence, edited as the GUI's Stages toolbar edits it. `phases` is the old name and still works |
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
| `picture geometry\|mesh P ...` | Save a picture of the model or its mesh, as the GUI's camera button does. See [Pictures](#pictures). |
| `picture stage P [--stage S\|all]` | Save a picture of one stage, or of every stage (the default) |
| `picture result RUN [FIELD\|all] [--stage S\|all] ...` | Save a picture of a result, or of every field and stage |
| `shell [P]` | Type commands one after another, without `kratos-cli` and the project file |

`P` is a project file (`.json`), or a model script (`.py`) for the commands that only read the
model: `show`, `check`, `get`, the `list` actions, `parts`, `stages show`, `node`, `mesh`
(without `--size` or `--order`), `export` and `calculate`.


## Pictures

`kratos-cli picture` saves the pictures of the GUI's camera button, as PNG, PDF or SVG at 300 dpi:

```bash
kratos-cli picture mesh site.json --out mesh.png
kratos-cli picture stage site.json --format png,pdf --out pictures/
kratos-cli picture result 1 uy --stage all --map viridis --out pictures/
kratos-cli picture result 1 --field all --stage 3 --csv --out pictures/
kratos-cli picture stage site.json --format pdf --one-pdf --out stages.pdf
```

The command draws with the GUI's own page, so the pictures are the same, and each one shows the
whole model. It starts the Styx server and Chrome or Edge with no window. Set `KRATOS_GUI_BROWSER` to the program if the command
does not find one. On a computer with neither browser, the command stops and says so.

| Option | What it does |
|---|---|
| `--format LIST` | `png`, `pdf` and `svg`, with a comma between them (default: `png`) |
| `--width CM` | The width of the picture (default: 16) |
| `--view front\|top\|side\|iso` | The camera, in a 3D model |
| `--no-rulers`, `--no-axes`, `--grid` | What to leave out, or add |
| `--out PATH` | A file, or a folder. A path that ends in `/` makes the folder. More than one file needs a folder. A file must end in its format, as `.png`. |
| `--force` | Overwrite files that exist |

These are the words of `picture save` in the GUI's command box: `--format`, `--width`,
`--stage all`, `--field all`, `--one-pdf`, `--no-legend`, `--no-rulers`, `--no-axes`, `--grid` and
`--csv` mean the same in both.

`picture stage` and `picture result` also take `--one-pdf`, which puts all the pictures in one PDF
file, one per page. It needs `pdf` in `--format`.

`picture result` takes the field as `FIELD` or as `--field FIELD`, and `all` for every field.
It also takes `--no-legend`, `--csv` (the field values too), `--map`, `--bands`,
`--range MIN MAX`, `--deform` and `--mesh`, which mean what the `results` commands of the GUI's
command box mean, and `--project P` to draw the loads and the water of the model over the result.
A run in a folder outside the runs root must keep its name, `<deck>_<date>_<time>`.

## Axes

x runs across the section, y points up, and z runs out of the section. The command line,
the project file and the GUI use these same three names.

A 2D model is the vertical cut through the site at one z, in the middle of the z extent:
z = 0 in a new project. `dimension P 2d --offset Z` cuts it at another z. In 2D,
`domain --z` only bounds where that cut may be, so a 2D model can leave it out.

## The ground, command by command

An empty site, built up to a staged excavation. The numbers are in the project's units
(SI unless `new --units kN`).

```bash
kratos-cli new pit.json --name "Pit B"
kratos-cli domain pit.json --x 0 60 --y -40 0 --z 0 10
kratos-cli material pit.json presets                      # the library a soil can start from
kratos-cli material pit.json add clay --preset m3 YOUNG_MODULUS=2e6 K0_NC=0.58
kratos-cli material pit.json add sand --preset m5 --model mohr-coulomb
kratos-cli layer pit.json add top --material clay --bottom -7
kratos-cli layer pit.json add mid --material clay --bottom -10
kratos-cli layer pit.json add bottom --material sand --bottom -40
kratos-cli water pit.json -1
kratos-cli fluid pit.json                                 # the water every soil is written with
kratos-cli boundary pit.json add pore --domain --water-pressure Hydrostatic   # about -1 m
kratos-cli parts pit.json                                 # soil_top, ... for the stages
```

- **Layers** are stacked from the top. Each layer has one top and one bottom, and spans
  the whole domain. The first layer starts at the top of the domain. The domain's height
  is the stack's: the top of the first layer is the ground level, for example NAP +1.7
  m, and the bottom of the last layer is the bottom of the model. Move one, and the other
  moves with it. `add` puts a layer
  under the last one, down to `--bottom` or `--thickness` below it (5 m by default).
  `set --top` or `--bottom` moves a level and the neighbour's with it, and refuses a
  level that would cross the neighbour. `split` halves a layer, and `remove` closes the
  gap with the layer above.
- **Materials** start as the GUI's **Create soil** starts them: linear elastic,
  `CONSTANT_PW_FIELD` and saturated below the phreatic level, with nothing else; the command
  lists what is still to fill in before a calculation. Or from a library preset
  (`--preset`). The law follows the model's dimension, and the values are converted into
  the project's units. Variables given as `NAME=VALUE` are Kratos' own, in the project's
  units; `get P materials[ID].variables` lists the values a material has.
  `GEO_DRAINAGE_TYPE` is `CONSTANT_PW_FIELD` (the GUI's "Mechanical only") or
  `FULLY_COUPLED` (its "Fully coupled"). `DRAINED` given becomes `CONSTANT_PW_FIELD`.
  `UNDRAINED` given becomes `FULLY_COUPLED` with its own permeability, and `set` says
  so. A permeability given to a soil that does not read it is kept, and `set` says that
  it is not used. `--color` is a `#rrggbb` colour, such as `#c4a86a`. Without it, `add`
  gives a colour no other soil has, as the GUI does. The export derives some variables
  that are left out, and its warning lists them. It also derives `K0_NC`, as ν / (1 − ν)
  for a linear elastic soil and 1 − sin φ for a Mohr-Coulomb one, into
  `initial_materials.json`, but that warning does not list it. `--r-inter` is the factor
  an interface puts on this soil's cohesion and tan φ (default 0.7), the **Rinter** field
  of the Soil materials window.
- **Soil models**: `--model linear-elastic` or `--model mohr-coulomb` sets the law for the
  model's dimension, as the **Soil model** list of the Soil material window does. The
  values the soil already has stay, except those another model reads and this one does
  not: `--model linear-elastic` leaves out the strength and the hardening, as a linear
  elastic soil has none. The values the model needs and the soil does not
  have get the model's defaults, and the command prints their names; a soil that still
  has empty values, such as a new one, gets none of the values the law needs, as in the
  GUI. Setting a choice
  such as `RETENTION_LAW=VanGenuchtenLaw`, `GEO_ENABLE_TENSION_CUT_OFF=true` or
  `GEO_COULOMB_HARDENING_TYPE=Linear` fills in
  the defaults of the values it brings in the same way. `material P models` lists each
  model: its laws, its parameters in groups, each default in the project's units, the
  values a choice can take and when a parameter is used. `--law` is for any other law,
  for example a UDSM. It is written as you type it. `--model` and `--law` cannot be
  given together.
- **Lines** split the soil. Where a line crosses a layer from one edge to another, the
  layer becomes separate soil bodies, and each is a SubModelPart that a stage can switch
  off. A sheet pile splits the soil the same way, also when it is `--inactive`. A part of
  a line that ends inside the soil splits nothing, and the command says so when no part of
  the line splits anything. A line may be a polyline, and lines may cross. In 3D a line
  cuts across the whole z range; it is drawn in 2D. The commands are in
  [The structures, command by command](#the-structures-command-by-command).

  A layer that is cut has no plain key any more: each piece is `soil_<layer>__<id>`, with
  a new id `part1`, `part2`, ... in the order the pieces are made. `body list` shows the
  pieces from the top down, and `get bodies` a point inside each. A piece keeps its key,
  name and material when another line is added. A stage that named the whole layer then
  names each of its pieces. An edit that takes away a piece a stage still names is refused.
  `body set --material layer` gives a body its layer's material as it is now. A body keeps
  its material in every stage. `layer set --material` gives every body of that layer the
  new material, also a body given one of its own. In a model script, `lines=` and
  `bodies=` say the same. A record
  `SoilBody(id="lift1", name="lift 1", layer="top", point=(2.5, -1))` chooses the key of
  the piece its `point` lies in.
- **A project saved with an excavation** opens with lines and soil bodies in its place: a
  line on each side of the pit, a line at each level, and the bodies `lift1`, `lift2`, ...,
  `pit` and `outside`. A stage that named the whole layer then names the ground outside the
  pit. A pit with one level was never dug, so it just goes. A 3D pit narrower than the
  model in z cannot be made of lines, and the file is refused.
- **Volumes**: in 2D, `volume add polygon --points x y x y ...` is an outline in the
  section plane, swept across the whole model. In 3D, `polygon` takes `x y z` points and
  `--extrude dx dy dz`, and there are `box` (`--origin`, `--size`) and `cylinder`
  (`--center`, `--axis`, `--radius`). `volume import FILE` reads .step, .iges, .brep, .stl
  or .obj. With `--material`, a volume is soil.
- **The water level** fixes no pressure by itself. A water pressure condition does
  (`boundary`, below): `boundary add --domain --water-pressure Hydrostatic` gives the
  soil hydrostatic pore pressures about the water level, and keeps that level as its own.
- **The water in the pores** is the project's, not each soil's: every soil is written
  with the same `DENSITY_WATER`, `BULK_MODULUS_FLUID` and `DYNAMIC_VISCOSITY`. `fluid`
  without a value says what they are. `--bulk-modulus` (a stress) and `--viscosity` set
  them in the project's units (Pa and Pa·s in SI, kPa and kPa·s in kN), and `--unset
  bulk_modulus dynamic_viscosity` gives them back to water's at 20 °C: 2.2 GPa and
  1 mPa·s. `DENSITY_WATER` is not set here: it is the water level's specific weight over
  g. A soil that sets one of the three itself is refused; a file saved when each soil
  had its own water is read with the first soil's, and says which soils changed.
- **Coordinates are plain numbers**, `--points 0 0 6 0 3 2`, because a word starting with
  a minus, like `-3,2`, would be read as an option. A long outline can come from a file:
  `--points @outline.csv`, one point per line.

## The structures, command by command

The wall, the props and the loads of the pit above, then its stages:

```bash
kratos-cli section pit.json add beam az26 --name "AZ 26" CROSS_AREA=0.015 I33=3e-4
kratos-cli beam pit.json add sheet --points 6 0 6 -12        # on az26, the first profile
kratos-cli line pit.json add floor_1 --points 0 -2 6 -2       # with the wall, the lifts
kratos-cli line pit.json add floor_2 --points 0 -4.5 6 -4.5
kratos-cli body pit.json list                                 # the pieces, and their keys
kratos-cli body pit.json set soil_top__part3 --name "lift 1"
kratos-cli body pit.json set soil_top__part4 --name "lift 3" --material sand
kratos-cli anchor pit.json add strut --head 6 -1 --tail 5 -1
kratos-cli anchor pit.json add tie --head 6.3 -3.5 --prestress 1e5
kratos-cli interface pit.json add contact --structure sheet --side right
kratos-cli interface pit.json add upper --structure sheet --side left --from 6 0 --to 6 -1
kratos-cli load pit.json add line surcharge --x 6 60 --components 0 -10000
kratos-cli normal-load pit.json add water_1 --hydrostatic --points 0 -2 6 -2 6 -1
kratos-cli mesh pit.json --body-size sheet 0.5
```

- **Where a new one goes.** A structure given no geometry is put where the GUI's tool
  puts a new one: a sheet pile down the middle of the section to half its depth, a wall
  across the middle of the site, an anchor a quarter of the way down the first pile and
  raking back 10 m at 35 degrees, an interface on the first pile, a 20 kN load.
- **Ids and names.** Other commands and the stages refer to a record by its id. `--name`
  is what the GUI shows and what the Kratos files call it. With no id typed, the name is
  the id too: `load add line --name Heavy` makes a load whose id is `Heavy`. This holds
  for every `add` command. With neither an id nor a name, a structure, load, boundary
  condition or stage gets the first free id, as in the GUI (`beam_1`,
  `anchor_2`, `load_3`), and a material, layer or section is refused.
- **Sections.** A structure is built with the first section of its kind, or `--section`.
  The first structure of a kind brings the GUI's default section with it (an AZ 26
  profile, a 0.4 m wall, a four-strand tendon, a contact), and the command says so.
  `section set ID NAME=VALUE ...` changes its Kratos variables, in the project's units,
  and `--unset NAME` leaves one out for the export to derive. `--spacing` belongs to beam
  and anchor sections; `--tension-limit` and `--compression-limit` to anchors;
  `--material`, `--r-inter`, `--virtual-thickness` and `--permeability` to interfaces.
  `none` clears an optional one. An interface's stiffnesses are
  `INTERFACE_NORMAL_STIFFNESS=...` and `INTERFACE_SHEAR_STIFFNESS=...`; left out, they are
  derived from the soil each stretch runs against, and `section list` says which. A
  Coulomb section (`--law GeoInterfaceCoulombLawPlaneStrain`) given a linear elastic
  soil with `--material`, which has no strength to give, gets the Mohr-Coulomb defaults
  as its own `GEO_COHESION` and `GEO_FRICTION_ANGLE`, as in the GUI, and the command
  says so; set them after.
- **Which side a normal load presses on.** The soil on the right of its line as drawn,
  where its arrows point in the GUI: `water_1` above runs along the pit floor to the wall
  and then up the wall face, with the retained ground on its right. On the outside of the
  model a normal load presses in whichever way it is drawn. `export` warns about a load
  that pulls on the soil, or whose arrows point out of it.
- **A sheet pile may stand out of the soil**, as one above a dike's crest or in a dug
  pit: the piece outside the soil stays in the model as long as some of the pile is in
  it. Its interface stops where the soil does.
- **Dimensions.** A sheet pile, an interface, a normal load and point and line loads are
  2D; a wall, a member and a surface load are 3D. Switching the dimension carries walls
  and loads across, as the GUI does (`dimension`).
- **Interfaces.** An interface on a sheet pile holds the whole pile, or the part from
  `--from` to `--to`. Each point is moved onto the pile; a point more than 0.5 m away is
  refused. `interface set ID --whole-pile` holds the whole pile again, and `interface
  list` shows the part (`along sheet from (6, 0) to (6, -1), left`). `--side` names a
  face as the GUI shows it, whichever way the pile was drawn: `left` is the face toward
  -x and `right` the face toward +x; on a line flatter than 45 degrees the faces are
  `below` and `above`. `both` is for a pile only. Two interfaces may hold the two faces
  of one pile, or two parts of one face, but not the same face over the same length.
  An interface on its own points may not run along a sheet pile: put it on the pile.
- **Anchors.** The head is snapped onto the nearest pile, wall or member within a metre,
  because it becomes one of its nodes; a head further away is refused. With no `--tail`,
  the anchor rakes back from its head. A strut is an anchor whose tail is a pinned support.
- **Removing.** A structure a stage names, or a pile an anchor or an interface depends
  on, is not removed; the refusal names what still uses it. A section in use is not
  removed either.
- **Ids are part keys.** A stage switches a structure by its id, so no two parts share
  one, and `wall`, `struts`, `anchors`, `piles`, `water`, `wells` and `excavation` are
  taken.

## The boundary conditions, command by command

The deck holds the conditions the model lists, and no others. `boundary list` shows them.
A new project, and a project file saved before the conditions existed, has the standard
supports: the bottom fixed (`fixed_bottom`), the left and right sides on rollers that hold
x (`roller_left`, `roller_right`), and the front and back on rollers that hold z
(`roller_front`, `roller_back`, which a 2D section leaves out, as plane strain holds z
already). It has no water pressure condition.

```bash
kratos-cli boundary pit.json set fixed_bottom --roller          # the bottom holds y only
kratos-cli boundary pit.json add strip --line 0 -12 6 -12 --fix y
kratos-cli boundary pit.json add pin --point 30 -40 --fixed
kratos-cli boundary pit.json standard                           # the standard supports back
kratos-cli boundary pit.json add pore --domain --water-pressure Hydrostatic --reference-coordinate -1
kratos-cli boundary pit.json add head --face right --water-pressure Hydrostatic --reference-coordinate 0 --pressure-tension-cut-off 1e5
kratos-cli boundary pit.json add well --point 30 -20 --water-pressure Uniform --value -150000
kratos-cli boundary pit.json add start --domain --water-pressure Phreatic_Multi_Line --phreatic-line 0 -1 60 -3 --initial
kratos-cli boundary pit.json set head --inactive
kratos-cli boundary pit.json remove well
kratos-cli boundary dam.json add exit --seepage --line 1.62 0.48 1.62 4     # a seepage face
```

- **Supports.** `--fixed` holds x, y and z; `--roller` holds the component normal to its
  face (x on the left and right, y on the bottom and top, z on the front and back), or to a
  vertical (x) or horizontal (y) line; `--fix x y` holds the components named. A 2D deck
  never holds z. A support is not put on the whole soil. A model with no support and no
  anchor can move as a rigid body; the export and `check` warn about it. `standard`
  replaces the supports on the faces with the standard ones and keeps the rest. In a 2D
  model, `list`, `standard` and `show` leave out the front and back supports, as the GUI
  does, and say so: they stay in the project for the solid model.
- **Where.** One of `--domain` (the whole soil), `--face bottom|left|right|top|front|back`
  (front and back exist in 3D only), `--part KEY` (a soil part, as `parts` lists it: a layer
  `soil_<id>` with all its pieces, one body, or a custom part with a material), `--line X Y
  X Y ...` or `--point X Y` (drawn in the 2D section, and left out of a 3D deck). `set` with
  another of these moves the condition.
- **Water pressure.** `--water-pressure` takes Kratos' `fluid_pressure_type`:
  `Hydrostatic` is zero at `--reference-coordinate` (in metres) and grows with depth below
  it; `Uniform` is `--value` at every node, a stress in the project's units with Kratos'
  sign (compression negative); `Phreatic_Multi_Line` is hydrostatic below the line
  `--phreatic-line X Y X Y ...`, x increasing. Above the level the pressure is held at zero
  unless `--pressure-tension-cut-off` allows suction up to that value.
- **Its own level.** A `Hydrostatic` condition given no `--reference-coordinate` takes the
  water level, keeps it as its own, and says so. With no water level either it is refused.
  A dry model needs no water pressure condition, unless a soil couples the water pressure
  to the deformation (`GEO_DRAINAGE_TYPE`): then `--water-pressure Uniform --value 0` on
  the whole soil, which the export's warning asks for.
- **Fixed or initial.** A condition holds the pressure in every stage it is on in
  (`--fixed`, the default). `--initial` gives start values only, which the calculation
  then changes.
- **Per stage.** A water pressure condition is on in every stage until a stage switches
  it off: `stages P deactivate STAGE ID` and `stages P activate STAGE ID`, as for a part
  (below). A stage with no condition on keeps the pressures the last stage ended with:
  Kratos leaves the nodes of a `Hydrostatic` or `Phreatic_Multi_Line` condition fixed at
  those values. A `Uniform` condition frees its nodes when its stage ends, so in a soil
  that couples the water pressure to the deformation the pressure is then free, and the
  export warns about it. A condition a stage names cannot be removed; take it out of
  those stages first. A support is switched per stage the same way, and is on in every
  stage until one switches it off.
- **Seepage face.** `--seepage` makes a seepage face, where water may leave the soil in a
  groundwater flow calculation: on `--face F`, or on `--line X Y X Y ...` along the soil's
  outer boundary. It takes no other option. Kratos' seepage strategy decides, node by node
  while it iterates, where the face is open: there the water pressure is zero and the water
  flows out; elsewhere the face is closed, as a boundary with no condition is. It opens or
  closes one node per iteration, so the export warns when a stage allows fewer iterations
  than the seepage faces it has on have nodes. A seepage line through the soil is refused,
  and a deformation calculation leaves a seepage face out, with a warning. It is on in
  every stage until a stage switches it off (`stages P deactivate STAGE ID`), as a water
  pressure condition is.
- **Overlap.** The export writes the start values first, then the fixed conditions from the
  least to the most specific target: the whole soil, a part, a face, a line, a point. On a
  node two of them share, the more specific one wins. Two fixed conditions on the same kind
  of target that share nodes give a warning.
- **Gravity.** There is no switch of its own: whether the self weight acts is decided by
  the initial stage's stress initialisation (`stages P set initial
  --stress-initialisation ...`). `k0` and `gravity` put it on every body, structures too,
  in every stage; `none` leaves it out of every stage, for a model loaded by its
  conditions alone. A flow sequence always has it. `show P` and `gravity P` say which.
  `gravity P 9.80665` sets the acceleration g in m/s², as **File** → **Project
  properties…** does in the GUI. The water keeps its specific weight: its density is
  written as the specific weight divided by g.
- `check` prints what the export will warn about the conditions: a model nothing holds, a
  water level that fixes nothing, a coupled soil with no water pressure condition or a
  stage that leaves its water free, a condition this dimension does not have.

## The stages, command by command

A stage says what it changes about the model it starts from: the parts, the supports, the
water pressure conditions and the seepage faces it switches on and off, and how it is
solved. `kratos-cli parts P`
lists the keys a stage can switch.

Stages were called *phases* before Styx took Kratos' word for them. The old name still
works everywhere: `kratos-cli phases ...`, a `phases` path in `get`, `set`, `add` and
`remove`, a project file saved with a `phases` list (it opens with `stages`), and the
`/api/project/phases` routes. Styx saves the file with `stages`, which older versions of
Styx cannot read.

```bash
kratos-cli stages pit.json set initial --stress-initialisation k0   # a new project has it
kratos-cli stages pit.json add null_step --name "Null step" --max-iterations 150
kratos-cli stages pit.json deactivate initial sheet strut tie contact surcharge water_1
kratos-cli stages pit.json add wall --name Wall --activate sheet contact surcharge --reset-displacements
kratos-cli stages pit.json add dig_1 --name "Dig 1" --activate water_1 --deactivate soil_top__part3 --max-iterations 150 --tolerance 1e-3
kratos-cli stages pit.json add props --name "Strut and tie" --activate strut tie
kratos-cli stages pit.json add dig_2 --name "Dig 2" --deactivate soil_top__part1
kratos-cli stages pit.json show dig_2              # what is in the model then
kratos-cli boundary pit.json add low --domain --water-pressure Hydrostatic --reference-coordinate -6
kratos-cli stages pit.json deactivate initial low  # the low level is off at first ...
kratos-cli stages pit.json activate dig_2 low      # ... and on from dig_2, in place of pore
kratos-cli stages pit.json deactivate dig_2 pore
kratos-cli stages pit.json list
```

- **The initial stage.** A new project starts with one stage, `initial` ("Initial
  stage"), mechanical with gravity loading. It chooses the calculation type and the
  stress initialisation of the whole sequence. It cannot be removed, and nothing goes
  `--before` it. `add` on a project saved without stages makes it.
- **`add [ID]`** puts a stage at the end of the sequence (the toolbar's Add); with
  `--before STAGE` it goes between that stage and the one it starts from (Insert).
  **`copy STAGE`** puts a stage with the same solver settings right after `STAGE` (Copy),
  and the stages after it then start from the copy; a copy has no stress
  initialisation. **`remove`** heals the chain: the removed stage's children start from
  its parent.
- **`activate` / `deactivate STAGE KEY ...`** put parts in or out of the model in that
  stage alone, as the Model explorer's checkbox does: the other stages keep what they
  had. It is done with the smallest instruction that does it: switching a part back to
  what the stage inherits drops the instruction. A stage added later starts with the
  parts of the stage before it. `add` and `copy` take `--activate` and `--deactivate`
  the same way.
- **`set STAGE`** changes `--name`, `--calculation mechanical|flow`,
  `--stress-initialisation k0|gravity|none`, `--time-integration static|dynamic`,
  `--reset-displacements` / `--keep-displacements`, `--convergence-criterion`,
  `--max-iterations`, `--tolerance` and `--absolute-tolerance` (the convergence
  criterion's relative and absolute tolerance), `--start-time`, `--duration`,
  `--time-step`,
  `--solver KEY=VALUE ...`, `--solver-default KEY ...` and `--parent`. `add` and `copy`
  take the same options.
- **`--calculation`** is what the sequence solves for, set on the initial stage and
  given to every stage; a later stage refuses it. **`mechanical`** (also `upw`) is the
  deformation of the soil with the water pressure in it, Kratos' `U_Pw` solver.
  **`flow`** (also `pw` and `groundwater-flow`) is the flow of the water alone, on the
  soil, Kratos' `Pw` solver. A flow stage has no displacements, so it refuses
  `--reset-displacements` and `--keep-displacements`.
- **`--stress-initialisation`** is how the initial stage of a mechanical sequence sets
  up the stresses; a later stage refuses it. **`k0`** derives them from the self weight
  and each soil's K0 (the K0 procedure), **`gravity`** solves for them under the self
  weight (gravity loading), and **`none`** sets up none, and leaves the self weight out
  of every stage. A flow sequence has no stresses: it refuses `k0` and `gravity`, and
  `--calculation flow` sets the stress initialisation to `none`.
- **`--convergence-criterion`** (also `--convergence`) is what Kratos checks to decide
  that the stage has converged. A mechanical stage takes **`residual`** (the default) or
  **`displacement`**; a flow stage **`water_pressure`** (the default) or **`residual`**.
  A flow stage of a project saved before the criterion could be chosen keeps the
  `residual` it was solved on.
  Each refuses the other's. Kratos' own names, with `_criterion`, work too.
  A new `--calculation` gives a stage on the other type's criterion the new type's
  default.
- **`--time-integration`** is **`static`** (equilibrium; a steady state for a flow stage)
  or **`dynamic`** (in time: Kratos' `Dynamic` solution type with inertia for a
  mechanical stage, `Transient_Groundwater_Flow` for a flow stage).
- **Defaults.** A stage that is not given these options has the initial stage's
  calculation type, no stress initialisation (the initial stage itself: gravity loading),
  static time integration, the calculation type's convergence criterion, at most 15
  iterations, a relative tolerance of 1e-4 and an absolute one of 1e-9 (1e-12 on the
  displacement criterion and 1e-8 on the water pressure, which a new criterion takes
  along unless the stage has its own absolute tolerance), the displacements
  of the stage before kept, and a duration of 1 s in one time step of 1 s.
  `stages show ID` prints a stage's settings.
- **`--start-time`** is when the initial stage starts, in the project's unit of time
  (0 unless it is set). Every later stage starts where the stage before it ended, so a
  later stage refuses it; `stages show ID` prints when a stage starts.
- **`--duration`** is how long the stage lasts and **`--time-step`** the step Kratos
  solves it in, both in the project's unit of time (seconds in every unit system). The
  stage runs from where the stage before it ended, in `duration / time-step` steps; a
  step longer than the duration is refused.
- **A seepage face** (`boundary add --seepage`, above) makes every flow stage that has
  it on use Kratos' seepage strategy, `newton_raphson_with_seepage`, with one attempt per step. It
  is written in a 2D groundwater flow calculation only; a mechanical deck leaves it out.
- **`--solver KEY=VALUE ...`** sets a stage's expert solver settings, the ones the
  Stages window shows under **Expert settings**: the strategy, the linear solver, the
  time step control, the time scheme of a dynamic stage, and the assembly.
  `stages show ID` lists the ones that apply to the stage, with their values, a `*` on
  the ones the stage set, and the reason for a fixed one. A switch takes `true` or
  `false`, and a choice takes its value or its label in any case.
  **`--solver-default KEY ...`** puts settings back to their defaults:

  ```bash
  kratos-cli stages pit.json set dig_1 --solver strategy_type=newton_raphson linear_solver_type=amgcl
  kratos-cli stages pit.json set dig_1 --solver-default linear_solver_type
  ```

  A setting a stage cannot have, or a value it cannot take, is refused, with the
  settings it can have. Each setting the stage does not set has the default for its
  calculation type and time integration. A mechanical stage is solved by Newton-Raphson
  (`strategy_type=newton_raphson`) with the scaled `LinearSolversApplication.sparse_lu`
  linear solver unless the stage chooses another. The quasi-Newton strategy
  (`strategy_type=quasi_newton`) always uses that linear solver, unscaled: it
  factorises the stiffness matrix once and reuses it. Unscaled, a fully coupled soil
  with a very low permeability can settle a few percent too little. A flow stage uses the strategy its soil calls for: one linear solve
  for a saturated soil, Newton-Raphson for a soil with another retention law. Its linear
  solver is `sparse_lu`. A step that does not converge is not tried again
  (`number_cycles=1`); with more attempts, each is smaller. A dynamic mechanical stage on
  `scheme_type=backward_euler` is Kratos' quasi-static U-Pw, without inertia. A new
  `--calculation` puts every stage's expert settings back to the new type's defaults.
  [`core/model/solver.py`](../core/model/solver.py) lists every setting, with its
  default and when it applies. `SOLVER` and `FLOW_SOLVER` in
  [`core/kratos/parameters.py`](../core/kratos/parameters.py) are the rest of what
  `ProjectParameters.json` gets.
- A sequence that would branch, two stages starting from one, is refused, because Kratos
  runs one sequence. So is a part the model does not have.

## The shell

```text
> kratos-cli shell pit.json
pit.json> water -2
pit.json> layer add L4 --material sand --thickness 10
pit.json> undo
pit.json> stages add
pit.json> calculate
pit.json> results field 1 uy
pit.json> exit
```

`kratos-cli shell P` opens the project and reads commands one after another. A line is a
`kratos-cli` command without `kratos-cli` and without the project file; the shell puts
the open project where the command takes one (`layer P add`, `node P 30`). A project
named on the line is the one used (`water other.json -3`), and a command that takes no
project, `results` or `run`, is given none. Everything else is the command as it is in the
terminal: the same options, answers, `--json`, refusals and exit codes. A line that starts
with `kratos-cli` is read without it, so a `next: kratos-cli ...` hint can be pasted as
printed. `help COMMAND` prints the command's usage as the terminal has it, with the
project file as `project`: in the shell, leave it out.

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
loads, the mesh, the stages), one constructor per record, with Kratos' own variable names as
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
kratos-cli results members 1                        # wall, interface_left, interface_right, ...
kratos-cli results profile 1 wall M --csv wall_M.csv
kratos-cli results profile 1 interface_right normal # the normal traction, by a word of it
kratos-cli results get 1 kratos.log --out logs/
kratos-cli results archive 1                        # <run>.zip, here
kratos-cli results field D:/copied/Pit_A_2026-10-12_09-14 uy   # a run anywhere
```

- **`RUN`** is a run's id, its number in `results runs`, or the path of a run directory,
  wherever it is: one copied off another machine reads the same, whatever its folder is
  called. In `results show 1`, `1` is the newest run, not a stage.
- **`--stage`** takes a stage's number, as `results show` lists it, or words of its name.
  Without it, the last stage that wrote results is read, which is where the GUI's Results
  mode opens a run.
- **Pictures.** The command line gives numbers and CSV files. To see a field drawn on the
  mesh, or a profile as a plot, open the run in the GUI's Results mode: start the GUI with
  the same `KRATOS_GUI_RUNS` as the run was made with.
- **A field** is one of the names `results fields` lists, as in the GUI's results log
  (`u`, `uy`, `syy`, `p`, `q`, `pw`, ...). A stress is read per element, as the solver
  computed it, unless `--location nodes` averages it onto the nodes.
- **`profile MEMBER [QUANTITY]`**: `M`, `Q`, `N`, `ux`, `uy` along a wall, `tn`, `ts` along
  an interface, or a word of the label (`moment`, `shear`, `normal`). Without a quantity it
  is the bending moment. `--stage` narrows it to one stage.
- **Which interface members a run has.** Each face of the wall has its own member:
  `interface_left` and `interface_right`, the faces toward -x and +x
  (`results profile 1 interface_left tn`). An interface flatter than 45 degrees has
  `interface_below` and `interface_above` instead. A member holds the stretch of the wall
  whose contact is on in that stage, so the face a pit is dug against starts at the pit
  floor. With more than one interface, the member names start with the interface's id: `contact_left`.
  `results members` lists them.
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
| `clearmesh` | — the viewport's: kratos-cli keeps no mesh, and each `mesh` or `export` makes it again |
| `stages`, `phases` | `kratos-cli stages P` |
| `water <level>`, `water off` | `kratos-cli water P LEVEL`, `kratos-cli water P off` |
| `boundary`, `boundary list`, `boundary standard` | `kratos-cli boundary P list`, `kratos-cli boundary P standard` |
| `gravity`, `gravity 9.80665` | `kratos-cli gravity P`, `kratos-cli gravity P 9.80665` |
| `units`, `units <system>` | `kratos-cli units P`, `kratos-cli units P kN` |
| `node <id>` | `kratos-cli node P NODE` |
| `cleargeometry` | `kratos-cli volume P clear` |
| `soillayers` | `kratos-cli layer P` (the window, as commands) |
| `materials` | `kratos-cli material P` (the window, as commands) |
| `calculate` | `kratos-cli calculate P` (the box only says to press Calculate) |
| `help` | `kratos-cli --help` |
| `soillayer`, `plate`, `beam`, `anchor` | `kratos-cli layer P add`, `kratos-cli wall P add`, `kratos-cli beam P add`, `kratos-cli anchor P add` (the box answers these with a placeholder and builds nothing) |
| `point`, `line`, `surface` | — a placeholder answer in the box; nothing is built |
| `colour <part>`, `color <part>` | — the viewport's: a part drawn in its own colour |
| `picture`, `picture copy` | — the viewport's: the Save picture window, and the clipboard |
| `picture save [--format LIST] [--stage all] [--field all] ...` | `kratos-cli picture geometry P`, `kratos-cli picture mesh P`, `kratos-cli picture stage P`, `kratos-cli picture result RUN` |
| `view iso\|top\|front\|side`, `zoomfit`, `clear` | — the viewport's and the log's |
| `gotosoil`, `gotostructures`, `gotomesh`, `gotoflow`, `gotoflowconditions`, `gotostaged` | — the viewport's: the mode tabs |
| `results` | `kratos-cli results show RUN` |
| `results runs`, `results list` | `kratos-cli results runs` |
| `results open <id\|n>` | `kratos-cli results show RUN`: every `results` command names its run |
| `results stage <n\|name>`, `results phase <n\|name>` | `--stage S` on `kratos-cli results fields\|field\|at\|profile` |
| `results fields` | `kratos-cli results fields RUN` |
| `results field <name> [nodes\|elements]` | `kratos-cli results field RUN NAME --location nodes` |
| `results at <node>` | `kratos-cli results at RUN NODE` |
| `results csv` | `kratos-cli results field RUN NAME --csv FILE` |
| `results plot [member] [quantity]` | `kratos-cli results profile RUN MEMBER QUANTITY` |
| `results plot members`, `results plot list` | `kratos-cli results members RUN` |
| `results plot csv` | `kratos-cli results profile RUN MEMBER --csv FILE` |
| `results plot svg`, `results plot png`, `results plot pdf` | — the viewport's: a picture of the plot |
| `results files` | `kratos-cli results files RUN` |
| `results get <file>` | `kratos-cli results get RUN FILE` |
| `results zip`, `results archive` | `kratos-cli results archive RUN` |
| `results deform`, `results bands`, `results smooth`, `results map`, `results range`, `results mesh`, `results loads`, `results reverse`, `results reversed` | — the viewport's: how a field is drawn |

While a drawing tool is placing points, typing `x y` or `x y z` places the next one. In the
terminal, the points are the command's own: `--points`, `--head`, `--at`.

## Fields, by path

`get`, `set`, `add` and `remove` reach any field. A path names fields with dots and picks a
record in a list by its id in brackets:

```bash
kratos-cli get site.json layers[L1].top
kratos-cli set site.json materials[m1].variables.YOUNG_MODULUS 2.5e7
kratos-cli add site.json stages '{"id": "dig_1", "name": "Dig", "parent": "null_step", "deactivate": ["soil_L1"]}'
kratos-cli add site.json materials @clay.json
kratos-cli remove site.json materials[clay2]
```

- A record is picked by its `id` (a custom part by its `key`). A list without ids takes a
  position from 0: `mesh.refinements[0].size`. A mapping takes its key either way:
  `materials[m1].variables[YOUNG_MODULUS]` or `materials[m1].variables.YOUNG_MODULUS`.
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

A mesh size belongs to its body. An edit that takes a body away, such as `layer remove`,
`layer split` or `layer set --top` taking a soil body out of every layer, removes
that body's size too, so `check` and `mesh` still accept the file. The edit says which
sizes it removed, and their values, as a `note:` line after its answer, also with
`--dry-run`. If the body comes back, set its size again.

```bash
kratos-cli layer pit.json split L_top
# note: Removed the mesh size of soil_L_top__lift3 (1): the edit took that body away. ...
```

If a file has a size for a body that the model does not have, `check` and `mesh` refuse
the file and name that body. Correct the name with `set`, or remove the size:

```bash
kratos-cli remove pit.json mesh.body_sizes.strut
```

## The deck and the runs

`export` writes the deck the GUI's **Export** writes for the same project: the `.mdpa`,
`MaterialParameters.json`, `ProjectParameters.json`, `initial_materials.json` when there is a
K0 stage, and `kratos_gui_units.json`, the unit system of the results (Kratos ignores it). The
files are named after the project; `--name mesh` names them `mesh.mdpa`.

`run` copies the deck into a directory of its own under the runs root and runs it there, so
the deck stays as it was and every run is kept. The runs root is `KRATOS_GUI_RUNS`, or
`~/KratosGUI/runs`, which the GUI's Results mode reads too. `--runs-dir` puts the run somewhere
else. Kratos is found the way the GUI finds it: [KRATOS_SETUP.md](KRATOS_SETUP.md).

`run` and `calculate` print nothing while Kratos runs. The run directory and its copy of
the deck are there from the start; `kratos.log`, Kratos' own output, is written into it
when the run ends. The run time grows quickly with the mesh: `mesh P` reports the number
of nodes and elements before a run, and `--timeout` (an hour by default) stops a run that
takes too long.

## Output and exit codes

Output is text for a person to read. `--json` (before or after the command) prints JSON for a
script instead. The exit code is 0 when the command did what it was asked, 1 when the model, a
file or Kratos refused it, and 2 when the command line itself could not be read. A refusal is
printed on stderr as `error: <reason>`; with `--json` it is also printed on stdout as
`{"ok": false, "error": ...}`. The exporter's warnings go to stderr as `warning: ...`.
`--csv`, for the commands with a table (`results field`, `results profile`), prints that
table as CSV, or writes it into the file it is given; it does not go with `--json`.
