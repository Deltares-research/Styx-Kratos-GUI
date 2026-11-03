# Styx features and their status

This page lists what Styx can do, the status of each feature, and the code that does it.
Use it to find out if a feature works before you rely on its results. The page describes
the code on 2026-10-21.

Part A lists what Styx sends to Kratos. Part B lists what the GUI and `kratos-cli` do. The
[Main gaps](#main-gaps) section lists the most important missing features.

## Status words

| Status | Meaning |
|---|---|
| Tested | It works, and automatic tests check it |
| Limited | It exists, but it has a limit, or no Kratos run has confirmed it yet |
| Not exported | Styx keeps the value in the project, but does not send it to Kratos |
| Not available | Styx does not have it |

## Limits for all features

> [!WARNING]
> Read these limits before you use the results of Styx for a design.

- **Only 2D is proven.** Each reference deck that the export is checked against is a 2D
  plane-strain model. The 3D element and law names follow the Kratos naming rules, but no
  3D model has run in a test.
- **Only linear elastic soil is tested.** The GUI suggests only the linear elastic soil
  laws. Styx writes any other law name as you type it, but no test runs it.
- **No safety analysis.** Styx has no φ–c reduction, so it gives no factor of safety.

## Part A: What Styx sends to Kratos

### A1. Analysis setup

| Feature | What Styx writes | Status | Source |
|---|---|---|---|
| Kratos application | GeoMechanicsApplication, solver type `U_Pw`, model part `PorousDomain` | Tested | [kratos/parameters.py](../core/kratos/parameters.py) `SOLVER` |
| Orchestrator | `SequentialOrchestrator` over named stages, each a `GeoMechanicsAnalysis` stage | Tested | [kratos/parameters.py](../core/kratos/parameters.py) `ORCHESTRATOR` |
| Analysis type | Static, Newmark scheme, Newton-Raphson, residual criterion. You cannot change it. | Tested | [kratos/parameters.py](../core/kratos/parameters.py) `SOLVER` |
| Linear solver | `skyline_lu_factorization` (direct), block builder, 1 thread. You cannot change it. | Tested | same |
| Tolerances | Relative 1e-4, absolute 1e-9, 6 to 15 iterations, reduction factor 0.5, increase factor 2.0. You can change the maximum number of iterations and the relative tolerance for each stage. | Tested | same |
| Time steps | One step for each stage (Δt = 1). The settling stages are at negative time, as in the reference deck. | Tested | [kratos/writer.py](../core/kratos/writer.py) |
| Units | One unit system for each project: SI (N, m, kg, s) or kN (kN, m, t, s). You type all values in it, the input files contain them without conversion, and the results come back in it. | Tested in both systems | [model/units.py](../core/model/units.py) |
| Groundwater flow | A project whose stages are all flow stages: solver type `Pw`, `Steady_State_Groundwater_Flow` (static) or `Transient_Groundwater_Flow` (dynamic), `sparse_lu` linear solver. One linear solve for a saturated soil, Newton-Raphson for a soil with another retention law. The deck holds the soil only. 2D only. A project that mixes flow and mechanical stages is refused. | Tested: the decks against the Kratos references `tests/Muskat/saturated_hydrostatic` and `van_genuchten_hydrostatic`; Kratos runs against the exact solution and the Kratos regression values (saturated), and against the Kratos regression values (Van Genuchten). The Muskat tutorial is run as a test, command by command, and cases A and C are built in the GUI: both give the decks of the model scripts and, in Kratos, the same answers | [kratos/parameters.py](../core/kratos/parameters.py) `FLOW_SOLVER` |
| Dynamics, consolidation, arc-length control, updated mesh | Not supported. The `time_interval` of a stage is not exported. | Not available | [model/schemas.py](../core/model/schemas.py) `Stage` |

### A2. Soil elements

| Dimension | Linear | Quadratic | Status |
|---|---|---|---|
| 2D plane strain | `UPwSmallStrainElement2D3N` (triangle) | `SmallStrainUPwDiffOrderElement2D6N` | Tested against the Kratos reference results |
| 3D | `UPwSmallStrainElement3D4N` (tetrahedron) | `SmallStrainUPwDiffOrderElement3D10N` | Limited: no 3D reference run |
| 2D groundwater flow | `SteadyStatePwElement2D3N` | `SteadyStatePwElement2D6N` | Tested against the exact solution of the semi-Muskat column |

Styx makes triangles and tetrahedra only. It does not make quadrilaterals or hexahedra.
See `ELEMENTS` and `FLOW_ELEMENTS` in [kratos/writer.py](../core/kratos/writer.py).

### A3. Structural elements

| Styx object | In the GUI | Kratos element | Constitutive law | Dim | Status |
|---|---|---|---|---|---|
| `Beam` | Sheet pile | `LinearTimoshenkoCurvedBeamElement2D2N` / `2D3N` | `TimoshenkoBeamElasticConstitutiveLaw` | 2D | Tested: element from the reference deck, law from the Kratos documentation |
| `Member` | Bored pile, king post, strut | `LinearTimoshenkoBeamElement3D2N` / `3D3N` | same | 3D | Limited |
| `Panel` | Wall panel (a footprint swept between two levels) | `ShellThinElement3D3N` (a 6-node triangle is written from its corners) | `LinearElasticPlaneStress2DLaw` | 3D | Limited |
| `Anchor` | Anchor: a 2-node tie, head on a sheet pile, tail fixed | `LinearTrussElement2D2N` | `TrussConstitutiveLaw`, prestress as `TRUSS_PRESTRESS_PK2` (a stress) | 2D | Tested: element from a Kratos reference deck |
| `SpaceAnchor` | 3D anchor, head on a panel or a member | `LinearTrussElement3D2N` | same | 3D | Limited |
| Anchor tension and compression limits | Fields of the anchor section | Not exported. The export shows a warning. | — | — | Not exported |

A beam section has the Kratos variables `YOUNG_MODULUS`, `POISSON_RATIO`, `DENSITY`,
`CROSS_AREA`, `I33`, and optionally `AREA_EFFECTIVE_Y`, `I22`, `TORSIONAL_INERTIA` and
`AREA_EFFECTIVE_Z`. The export calculates the missing optional values. The default section
is near an AZ 26-700 steel sheet pile. In 2D, the values are for one metre of wall: the
export divides the section values (not the density) by the `spacing`.

### A4. Interfaces

| Feature | Detail | Status |
|---|---|---|
| Element | `Geo_UPwLineInterfacePlaneStrainElement2Plus2N` / `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N` | Tested for quadratic, from a Kratos reference deck. Limited for linear: the name is inferred. |
| Law | The law of the interface section. The default is `GeoIncrementalLinearElasticInterfaceLaw`. The K0 stage always uses this law. | Tested |
| Placement | Along a whole sheet pile or the part between two points on it (From, To), or along a free line through the soil (soil against soil, a slip surface, a lining). Side: both, left or right on the screen (below or above for a flat line). Many interfaces per pile, but only one on each face over a length. | Tested |
| Ends of an interface | At the toe, one node copy for the soil around it (for one face only: the soil on that side of the pile line). Where the pile goes on, the soil beyond the end stays on the pile node, as the Kratos-side InterfaceInserter does. | Tested, also in Kratos |
| Ties before installation | A master/slave tie for each split node, also for an interface on one face only | Tested |
| Along an anchor's grout body | Not possible: the grout body is a point in the model | Not available |
| Node splitting | Styx duplicates the nodes after it makes the mesh, so the contact has zero thickness | Tested, [kratos/interfaces.py](../core/kratos/interfaces.py) |
| Stiffness | `INTERFACE_SHEAR_STIFFNESS` and `INTERFACE_NORMAL_STIFFNESS` as you type them. If you leave them out: shear = G / t of the adjacent soil (t is the virtual thickness), normal = 10 × shear. | Tested |
| Strength | If you leave them out: c × R and atan(R × tan φ) of the adjacent soil. R is the `R_inter` of the section, or else the `R_inter` of the soil (default 0.7). | Tested against the Kratos reference |
| Permeability | Neutral, Drain or Impermeable. The interface is always exported as `CONSTANT_PW_FIELD`. | Not exported |
| 3D interfaces | Not exported. The export shows a warning. | Not available |

### A5. Soil materials

A soil material is a Kratos property set: a constitutive law and its `Variables`, with the
Kratos names, in the unit system of the project. Styx writes the property set as it is,
and adds only the values that are missing
([kratos/materials.py](../core/kratos/materials.py)).

| Feature | Detail | Status |
|---|---|---|
| Soil model | A **Soil model** list in the Material set window (`--model` in the CLI): Linear elastic, Mohr-Coulomb or Other. The model sets the law and the parameters shown, in groups, with defaults ([model/soil_models.py](../core/model/soil_models.py)). | Tested |
| Linear elastic soil | `GeoLinearElasticPlaneStrain2DLaw` (2D), `GeoIncrementalLinearElastic3DLaw` (3D). The law follows the dimension of the model. | Tested in 2D. Limited in 3D. |
| Mohr-Coulomb soil | `GeoMohrCoulombLawPlaneStrain` (2D), `GeoMohrCoulombLaw3D` (3D), with `GEO_COHESION`, `GEO_FRICTION_ANGLE`, `GEO_DILATANCY_ANGLE`, `GEO_ENABLE_TENSION_CUT_OFF` and `GEO_TENSILE_STRENGTH`. A new soil has c = 1 kPa, φ = 30°, ψ = 0°, no tension cut-off and `SaturatedBelowPhreaticLevelLaw`. The old names `GeoMohrCoulombWithTensionCutOff2D/3D` become the current ones when a project loads. Hardening (`GEO_COULOMB_HARDENING_TYPE`) is not in the window; add it with **Add variable**. | Tested in 2D, in Kratos too |
| Other laws | Any law name, for example a UDSM, with its own variables. Styx writes it as typed. | Limited: no test runs it in Kratos |
| Choices | `GEO_DRAINAGE_TYPE` (`CONSTANT_PW_FIELD`, `FULLY_COUPLED`, `DRAINED`, `UNDRAINED`) and `RETENTION_LAW` (`SaturatedLaw`, `SaturatedBelowPhreaticLevelLaw`, `VanGenuchtenLaw`) are lists of the values Kratos accepts. `GEO_ENABLE_TENSION_CUT_OFF` is a check box. | Tested |
| Required variables | `YOUNG_MODULUS`, `POISSON_RATIO`, `DENSITY_SOLID` for every soil model; for Mohr-Coulomb also c, φ and ψ, and the tensile strength when the cut-off is on. The export refuses a soil without them, and a Mohr-Coulomb soil with ψ > φ, φ ≥ 90° or a tensile strength above c / tan φ. | Tested |
| Calculated variables | If they are missing: `GEO_DRAINAGE_TYPE` = `CONSTANT_PW_FIELD`, `DENSITY_WATER` from the specific weight of the water, `POROSITY` = 0.3, the bulk moduli of solid (10 GPa) and fluid (2.2 GPa), the viscosity of water (1 mPa·s), and the symmetric permeabilities. The export lists each calculated value in a warning. | Tested |
| K0 | `K0_NC`, or else Jaky's 1 − sin φ from `GEO_FRICTION_ANGLE`, in `initial_materials.json`. Without both, Kratos uses its own default. | Tested |
| K0 stage | The K0 stage runs elastic. A soil with a different law uses the linear elastic law in `initial_materials.json`, and its own law from the next stage on. | Tested |
| Soil presets | Fill, Sand loose, Sand dense, Clay soft, Clay stiff, Bedrock ([material-library.js](../frontend/js/material-library.js)) | Tested |
| Old projects | A project from before 2026-10-10 (in kN, kN/m² and m/day) is converted when it is opened, so its input files do not change ([model/migration.py](../core/model/migration.py)) | Tested |

### A6. Loads, water and boundary conditions

| Feature | Kratos | Dim | Status |
|---|---|---|---|
| Self weight | `VOLUME_ACCELERATION` on the computational part, in every stage. Gravity can be switched off for the whole model (`gravity off`, or the **Gravity** row). | 2D, 3D | Tested |
| Point load | `PointLoadCondition2D1N` / `3D1N`, `POINT_LOAD` | 2D, 3D | Tested |
| Line load | `LineLoadCondition2D2N` / `LineLoadDiffOrderCondition2D3N`, `LINE_LOAD` | 2D | Tested |
| Surface load | `UPwFaceLoadCondition3D3N` / `SurfaceLoadDiffOrderCondition3D6N`, `SURFACE_LOAD` | 3D | Limited |
| Normal load (uniform or hydrostatic) | `LineNormalLoadCondition2D2N` / `LineNormalLoadDiffOrderCondition2D3N` with `ApplyNormalLoadTableProcess` | 2D | Tested for hydrostatic, from a reference deck. Limited for uniform. |
| Change between 2D and 3D | Styx converts point, line and surface loads, and sheet piles and panels, and links them with `derived_from` | — | Tested |
| Load distribution | Uniform only. No load that changes with time. | — | Not available |
| Water pressure conditions | `ApplyScalarConstraintTableProcess`: `Uniform`, `Hydrostatic` (about the level of the condition) or `Phreatic_Multi_Line`, fixed or as start values only, on the whole soil, a soil part, a face, a drawn line or a point. Without a condition, Styx fixes no water pressure. | 2D, 3D (lines and points 2D) | Tested |
| Water conditions for each stage | A stage switches a water pressure condition on or off, as it does a load. The Kratos stage writes the conditions that its stage has on. | 2D, 3D | Tested |
| Seepage face | `GeoSeepageCondition2D2N` / `2D3N` on the mesh edges of a face or of a line along the soil's outer boundary, one `ApplySeepageBoundaryProcess`, and the `newton_raphson_with_seepage` strategy. Groundwater flow only, in every stage. A line through the soil is refused. | 2D | Tested: the deck against Kratos' `tests/seepage_tests` and the STEM Muskat geometry, and a Kratos run against the water balance and the Dupuit-Charny discharge |
| Displacement conditions | `ApplyVectorConstraintTableProcess` on a face, a soil part, a drawn line or a point, in the components x, y, z that you select. A new project has the bottom fixed and the sides on rollers. | 2D, 3D (lines and points 2D) | Tested |
| Anchor tail support | The tail node is fixed | 2D, 3D | Tested |

### A7. Construction stages

| Feature | Detail | Status |
|---|---|---|
| Stage settings | Calculation type: mechanical (`U_Pw`) or flow (`Pw`). Stress initialisation of a mechanical stage: K0 procedure, gravity loading or none. Time integration: static or dynamic (`Dynamic` for a mechanical stage, `Transient_Groundwater_Flow` for a flow stage). Every stage of a groundwater flow project is a flow stage. A new calculation type is one entry in `schemas.Stage` and `parameters.SOLVERS`. | Tested: the decks; no dynamic stage has run in Kratos in a test |
| Stage tree | Each stage has a parent, and keeps only what it switches on and off. Kratos needs one sequence, so Styx makes the tree into a list. A tree that branches is refused. | Tested |
| Staged excavation sequence | `stages P staged-excavation` (CLI) and model scripts make the full sequence: K0, null step, wall installation, then one stage for each lift with its water load, and each anchor after the lift that uncovers it. It reproduces the 7 stages of the Kratos staged-excavation reference. The GUI has no button for it. | Tested |
| Switch parts on and off | `ActivateModelPartOperation` / `DeactivateModelPartOperation` for soil bodies, lifts, beams, anchors, interfaces and loads | Tested |
| Settings for each stage | Reset displacements (`reset_totals`), maximum iterations, tolerance | Tested |
| Stresses carried to the next stage | `ApplyFinalStressesOfPreviousStageToInitialState` | Tested |
| Initial stresses | `apply_k0_procedure_process`, with its own `initial_materials.json` | Tested |
| Soil connected before the wall is built | `AssignMasterSlaveConstraintsToNeighboursUtility` ties the split nodes together until the wall is installed | Tested |
| Interface neighbour search | `FindNeighboursOfInterfacesProcess` | Tested |
| Loading type | Staged construction only | Limited |

### A8. Output that Styx asks from Kratos

| Output | Variables | Status |
|---|---|---|
| GiD ASCII files (`.post.res`, `.post.msh`), one pair for each stage | Nodal `DISPLACEMENT`, `TOTAL_DISPLACEMENT`, `WATER_PRESSURE`; `CAUCHY_STRESS_TENSOR` and `HYDRAULIC_HEAD` (not with gravity off) at the Gauss points | Tested |
| Groundwater flow, one pair of GiD files for each stage | Nodal `WATER_PRESSURE`, `EFFECTIVE_SATURATION` and `FLUID_FLUX_VECTOR` (the last two extrapolated from the Gauss points), and `NODAL_WATER_FLOW_RATE` with a seepage face; `HYDRAULIC_HEAD` at the Gauss points (not with gravity off) | Tested |
| Wall forces at the nodes | `AXIAL_FORCE`, `BENDING_MOMENT`, `SHEAR_FORCE` | Tested: a live Kratos run is checked, and agrees with the Kratos reference curves |
| Interface tractions | `GEO_EFFECTIVE_TRACTION_VECTOR`, written to JSON on the retained side | Tested |

## Part B: What the GUI and kratos-cli do

### B1. Application and projects

| Feature | Detail | Status |
|---|---|---|
| Architecture | A browser front end (three.js, no build step) and a local FastAPI server. Gmsh runs in its own worker process, so a Gmsh crash does not stop the server. | Tested |
| Start | `run.bat` or `run.sh` makes its own Python environment and starts the server. `run.bat` also opens the browser. `--check` only checks the setup. | Tested on Windows, Linux and macOS |
| Project files | New, Open, Save, Save as (a project JSON file). The server keeps the open project in memory only. | Tested |
| Undo and redo | Up to 40 steps, each a copy of the full project | Tested |
| Keyboard shortcuts | Ctrl+Z, Ctrl+Y, Ctrl+S, Ctrl+O, Ctrl+N, F5 (zoom to fit), F9 (calculate, or make the mesh in Mesh mode), Esc. The arrow keys recall earlier commands. | Tested |
| Checks | The server checks the full project at each edit | Tested |
| Display | WebGL, with a CPU renderer when no GPU is available | Tested |
| 2D and 3D | Change between a 2D plane-strain section (at a z offset that you select) and the 3D model. Loads and walls are converted. | Tested |
| Modes | Soil, Structures, Flow conditions, Mesh, Staged construction, Results | Tested. Flow conditions sets the water level and the water pressure conditions. |
| Panels | Model explorer, Selection explorer, docked panels, right-click menus | Tested |
| Navigation | Iso, top, front and side views; zoom to fit; rotate; rulers on all four edges in 2D | Tested |
| Placeholder items | Some menu items and tools of the first design do nothing. They show *"…" is not available in Styx yet*. | — |

### B2. Geometry and soil

| Feature | Detail | Status |
|---|---|---|
| Soil layers | A stack of horizontal layers across the whole domain, each with one top and one bottom. Made in **Modify soil layers** or with `kratos-cli layer`. The stack is checked for gaps. | Tested |
| Free soil polygons in the stack | Not supported. Layers are always a stack. | Not available |
| Soil surface (2D) or soil volume (3D) | Type the corners of an outline and select a material (embankment, cutting, fill, lens) | Tested |
| Excavation | A pit with several lifts. Each lift in each layer is its own soil body. Make it with `kratos-cli excavation` or a model script: the GUI shows it but cannot make it. | Tested |
| Drawing tools | Point, line, surface, box and cylinder (box and cylinder in 3D only) | Tested |
| CAD import | STEP, IGES, BREP, STL, OBJ (surfaces are made into solids) | Tested |
| Kratos `.mdpa` import | View only: a preview with a list of parts. You cannot change the mesh. | Tested |

### B3. Structures, loads and water

| Feature | Detail |
|---|---|
| Sheet piles, wall panels, members | Sections are shared, so many piles can use one profile. You edit them in the Selection explorer. |
| Anchors | The head moves onto a pile, a panel or a member. The prestress is set for each anchor. |
| Interfaces | The interface window: a sheet pile by name with **From** and **To**, or own coordinates; the faces as on the screen; the contact. Contact properties are shared. |
| Loads | Point, line and surface loads by their components. You can switch each one off. |
| Normal loads | A line with uniform or hydrostatic pressure |
| Water | One water level for the full model. A new hydrostatic condition or normal load takes it as its own level. You can change the specific weight of the water. |
| Boundary conditions | The **Boundary conditions** window: a row for each face and one for the whole soil, with the support and the water pressure on each, and the conditions on parts, lines and points. Tools draw a support or a water pressure along a line or at a point (2D). **Gravity** on or off. |

### B4. Mesh

| Setting | Options |
|---|---|
| Size and order | Global element size; linear or quadratic elements, optionally with straight edges |
| Algorithms | 2D: frontal, delaunay, meshadapt, auto. 3D: delaunay, frontal, hxt. |
| Quality | Optimisation (none, gmsh, netgen), smoothing steps, points along curves, minimum size factor |
| Local control | A target size for each soil layer and each structure; box and cylinder refinement zones; **Refine**, **Coarsen** and **Reset local refinement** |
| Selection | Only the selected layers get a mesh. Shared faces keep common nodes. |
| Mesh labels | Node and element numbers on the mesh, spread out where nodes overlap |

### B5. Calculation and export

| Feature | Detail | Status |
|---|---|---|
| Export | **File** → **Export model…** writes the Kratos input files in one ZIP file, and lists each assumption and warning | Tested |
| Calculate (F9) | Makes the mesh, writes the files, and runs Kratos in a new run folder | Tested |
| Kratos location | `kratos.local.json` or environment variables: Python of Kratos, build folder, runs folder, time limit (default 3600 s) | Tested |
| Failed runs | The log names the stage that failed | Tested |

### B6. Results mode

| Feature | Detail | Status |
|---|---|---|
| Runs | List all runs, open one, go through its stages | Tested |
| Quantities | \|u\|, u_x, u_y, u_z, total and for each stage; σ'xx, σ'yy, σ'zz, σ'xy, σ'yz, σ'xz; p', q, σ1, σ2, σ3, τ_max; pore pressure; hydraulic head (with gravity on); effective saturation, the flux q, q_x, q_y, q_z and, with a seepage face, the nodal water flow rate of a groundwater flow run. Total stresses and saturation if Kratos wrote them. | Tested |
| Signs and units | Compression is negative, as Kratos writes it. All quantities are in the unit system of the run (Pa for SI, kPa for kN); lengths in m. | Tested |
| Display | Colour bands or smooth shading, colour map, reversed scale, automatic or fixed range, deformed mesh with a selected or automatic scale | Tested |
| Loads and water | The loads and the water level of the stage on screen over the colours, when the run is of the open project (`results loads on\|off`) | Tested |
| Values at a node | All quantities at one node (`results at <node>`) | Tested |
| Plots along the wall | Bending moment M, shear force Q, normal force N, displacements ux and uy along the wall, and the tractions tn and ts along the interface, with one line for each stage. Save as SVG or CSV. | Tested |
| Export | The field on screen as CSV; one file of a run, or the full run as a ZIP file | Tested |
| Slip plane, factor of safety | Not available | Not available |

### B7. Command box and scripts in the GUI

| Command | What it does |
|---|---|
| `run <file.py>`, `load <file.py>` | Runs a Python file that returns a `Project`, and shows the model. Example: `tests/models/excavation.py`. |
| `script <file.py>` | Writes the model as a model script |
| `mesh`, `calculate`, `export` | Makes the mesh, calculates, or writes the Kratos files |
| `stages` | Opens the **Stages** window |
| `water`, `units`, `cleargeometry` | Changes the water level or the unit system, or removes drawn and imported solids |
| `boundary`, `gravity` | Lists the boundary conditions or puts the standard supports back; shows gravity or switches it on or off |
| `soillayers`, `materials` | Opens the soil windows |
| `colour`, `node` | Shows parts of the mesh in colour, or the parts that contain a node |
| `results …` | `runs`, `open`, `stage`, `fields`, `field`, `at`, `bands`, `smooth`, `map`, `deform`, `range`, `reverse`, `mesh`, `loads`, `plot`, `csv`, `files`, `get`, `zip` |
| `view`, `zoomfit`, `goto<mode>`, `clear`, `help` | Changes the view or the mode, clears the log, lists the commands |

The `Project` is a pydantic model that a script can build directly. The server also has a
REST API: `/api/project`, `/api/mesh`, `/api/calculate`, `/api/results/…`.

### B8. Command line (kratos-cli)

| Feature | Detail | Status |
|---|---|---|
| Commands | Each step of the GUI as a terminal command, on the same project file: site, soil, structures, loads, mesh, stages, export, run, results. See the [kratos-cli reference](CLI.md). | Tested |
| Shell | `kratos-cli shell` reads commands one after the other, with undo and redo, from a terminal, a file or a pipe | Tested |
| Model scripts | `script` writes the model as Python; `build` writes a project from a script. Each command that reads a model accepts a script. | Tested |
| Results | Numbers and CSV files only. Pictures need the GUI. | Tested |
| Parity with the GUI | A test checks that each command of the GUI command box has a terminal command in the reference | Tested |

### B9. Tests and benchmarks

| Item | Detail |
|---|---|
| Benchmarks | Analytical and self-consistency checks in `benchmarks/`: K0 columns, weight above and below the water, hydrostatic column, symmetric excavation, 2D against 3D, mesh convergence, order 1 against order 2, saturated block, building pit, line loads in stages, balance of reactions, the three Muskat groundwater flow cases. They need Kratos. |
| Server tests | pytest, 105 test files in `tests/`. Run them with `python tools/test.py quick`. |
| JavaScript tests | 54 test files in `frontend/tests/`, run in a browser with Playwright (`python tools/test.py browser`). The files that do not use the DOM also run without a browser under quickjs. |

## Main gaps

1. **A plastic stage applies its load in one step.** A Mohr-Coulomb soil runs in Kratos
   (the staged excavation of `tests/models/excavation.py` runs all its stages), but a
   stage that makes much of the soil yield can stop without converging, because the
   stage has no load steps. More iterations and a larger tolerance per stage can help.
   User-defined models (UDSM, UMAT) are written as typed, without a test.
2. **No factor of safety.** Styx has no φ–c reduction stage.
3. **Groundwater flow is 2D only.** A project cannot mix flow stages
   with mechanical stages, and a drawn condition line has no element size of its own
   (a box refinement gives a seepage face its fine mesh). With a Van Genuchten soil, the
   Newton-Raphson iterations can fall into a cycle on some meshes and stop without
   converging; another element size then helps.
4. **3D is not proven.** No 3D element, law or interface has run in Kratos in a test.
5. **Fixed solver settings.** The calculation type of the stages chooses the analysis
   (mechanical or groundwater flow), and the time integration static or dynamic. You
   cannot change the linear solver, and a dynamic stage runs one time step of the length
   of a static one: the time step and the Newmark and damping parameters are Kratos'
   defaults.
6. **No excavation tool in the GUI.** A pit with lifts needs `kratos-cli excavation` or a
   model script.
7. **No single-element test** to check a soil model on its own.
