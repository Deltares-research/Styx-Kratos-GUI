# Styx — supported features

What Styx can do as of 2026-09-27, read from the code rather than from plans. Every row
says whether it works, and where the code lives.

| Mark | Meaning |
|---|---|
| ✅ | Works and is covered by tests |
| 🟡 | Exists, but with a limitation, or not yet confirmed by a real Kratos run |
| ❌ | Accepted by the GUI but not sent to Kratos, or not available |

Two limits run through everything below:

- **Only 2D is proven.** Every reference deck the export was checked against is 2D
  plane strain. The 3D Kratos element and law names follow Kratos' documented naming
  but have never been run.
- **No safety analysis.** There is no φ–c reduction, so no factor of safety.

---

## Part A — Kratos features

### A1. Analysis setup

| Feature | What is written | Status | Source |
|---|---|---|---|
| Kratos application | GeoMechanicsApplication, `U_Pw` solver, model part `PorousDomain` | ✅ | [kratos/processes.py](../core/kratos/processes.py) `SOLVER` |
| Orchestrator | `SequentialOrchestrator` over named stages, `GeoMechanicsAnalysis` stage | ✅ | [kratos/processes.py](../core/kratos/processes.py) `ORCHESTRATOR` |
| Analysis type | Static, Newmark scheme, Newton-Raphson, residual criterion | ✅ fixed, not selectable | [kratos/processes.py](../core/kratos/processes.py) `SOLVER` |
| Linear solver | `skyline_lu_factorization` (direct), block builder, 1 OpenMP thread | ✅ fixed | same |
| Tolerances | Relative 1e-4, absolute 1e-9, 6–15 iterations, reduction 0.5, increase 2.0 | ✅ max iterations and relative tolerance editable per phase | same |
| Time stepping | One step per stage (dt = 1); settling stages sit at negative time, as in the reference deck | ✅ | [kratos/export.py](../core/kratos/export.py) |
| Units | A project unit system, SI (N, m, kg, s) or kN (kN, m, t, s), chosen with `units <system>` or the status bar; every input is in it, the deck carries it verbatim and the results come back in it. Property sets are Kratos' own law + `Variables` | ✅ tested, the test model run in both systems | [model/units.py](../core/model/units.py), [kratos/materials.py](../core/kratos/materials.py) |
| Dynamics, consolidation, arc-length control, updated mesh | Not supported. A phase's `time_interval` is stored but not used | ❌ | [model/schemas.py](../core/model/schemas.py) `Phase` |

### A2. Continuum (soil) elements

| Dimension | Linear | Quadratic | Status |
|---|---|---|---|
| 2D plane strain | `UPwSmallStrainElement2D3N` (triangle) | `SmallStrainUPwDiffOrderElement2D6N` | ✅ checked against Kratos' reference results |
| 3D | `UPwSmallStrainElement3D4N` (tetrahedron) | `SmallStrainUPwDiffOrderElement3D10N` | 🟡 no 3D reference run |

Triangles and tetrahedra only; quadrilaterals and hexahedra are not supported. See
`ELEMENTS` in [kratos/export.py](../core/kratos/export.py).

### A3. Structural elements

| Styx object | In the GUI | Kratos element | Constitutive law | Dim | Status |
|---|---|---|---|---|---|
| `Beam` | Sheet pile | `LinearTimoshenkoCurvedBeamElement2D2N` / `2D3N` | `TimoshenkoBeamElasticConstitutiveLaw` | 2D | ✅ element from the reference deck; law from Kratos docs |
| `Member` | Bored pile, king post, strut | `LinearTimoshenkoBeamElement3D2N` / `3D3N` | same | 3D | 🟡 |
| `Panel` | Wall panel (a footprint swept between two levels) | `ShellThinElement3D3N` (a 6-node triangle is written from its corners) | `LinearElasticPlaneStress2DLaw` | 3D | 🟡 |
| `Anchor` | Anchor: a 2-node tie, head snapped onto a sheet pile, tail fixed | `LinearTrussElement2D2N` | `TrussConstitutiveLaw` + `TRUSS_PRESTRESS_PK2` | 2D | ✅ element from a Kratos reference deck |
| `SpaceAnchor` | 3D anchor, head on a panel or member | `LinearTrussElement3D2N` | same | 3D | 🟡 |
| Anchor tension / compression limits | Fields on the anchor section | Not exported; a warning says so | — | — | ❌ |

**Beam section inputs:** E, ν, area, inertia, shear area, density, spacing, minor
inertia and torsional inertia. There is a preset close to an AZ 26-700 steel sheet pile.
In 2D the values are per metre run and divided by the spacing.

**Legacy 3D demo:** when `layered_soil=False`, the seeded excavation builds a wall ring,
a strut frame with walers, a pile group and wells as **solids** rather than as
structural elements.

### A4. Interfaces

| Feature | Detail | Status |
|---|---|---|
| Element | `Geo_UPwLineInterfacePlaneStrainElement2Plus2N` / `Geo_UPwLineInterfacePlaneStrainDiffOrderElement3Plus3N` | ✅ quadratic, from a Kratos reference deck · 🟡 linear name is inferred |
| Law | Follows the soil: `GeoInterfaceCoulombLawPlaneStrain` against Mohr-Coulomb, `GeoIncrementalLinearElasticInterfaceLaw` against Linear Elastic and in the K0 phase | ✅ matches Kratos' Mohr-Coulomb reference deck · 🟡 unrun |
| Placement | Along a sheet pile (side: both, left or right), or along a free polyline through the soil (soil against soil, a slip surface, a lining) | ✅ |
| Node splitting | Nodes are duplicated after meshing, giving a zero-thickness contact | ✅ [kratos/interfaces.py](../core/kratos/interfaces.py) |
| Stiffness | Entered as kn and ks, or derived: ks = G_soil / virtual thickness, kn from ks | ✅ |
| Strength | Against Mohr-Coulomb soil: c·R and atan(R·tan φ), where R is the contact's `R_inter` or, left blank, the soil's own. Against elastic soil: none (it cannot slip) | ✅ matches Kratos' Mohr-Coulomb reference deck · 🟡 unrun |
| Permeability | Neutral, Drain or Impermeable (stored) | 🟡 |
| 3D interfaces | Not exported; a warning says so | ❌ |

### A5. Soil constitutive models

Two models, both GeoMechanicsApplication's own, each written as itself
([kratos/materials.py](../core/kratos/materials.py)). User-defined models (UDSM/UMAT)
are next.

| Model chosen in the GUI | Written to Kratos as | Status |
|---|---|---|
| Linear Elastic | `GeoLinearElasticPlaneStrain2DLaw` / `GeoIncrementalLinearElastic3DLaw` | ✅ 2D · 🟡 3D name corrected, no tests yet |
| Mohr-Coulomb | `GeoMohrCoulombLawPlaneStrain` / `GeoMohrCoulombLaw3D` | ✅ matches Kratos' Mohr-Coulomb reference deck set by set · 🟡 no tests yet |

The K0 phase writes every soil as linear elastic, whatever its model: Kratos' own
Mohr-Coulomb staged-excavation reference does the same. The real law takes over from the next phase.

| Material input | Kratos variable | Status |
|---|---|---|
| Drainage: Drained, Undrained (A), Undrained (B), Non-porous | `GEO_DRAINAGE_TYPE`: `CONSTANT_PW_FIELD` for drained, `FULLY_COUPLED` for undrained | ✅ |
| γ_unsat, γ_sat, E, ν | `DENSITY_SOLID`, `YOUNG_MODULUS`, `POISSON_RATIO` | ✅ |
| k (m/day) | `PERMEABILITY_XX/YY(/ZZ)`, in m/s | ✅ |
| Porosity | `POROSITY`; 0.3 if left empty | ✅ |
| K0_NC | `K0_NC` plus `K0_MAIN_DIRECTION`. Mohr-Coulomb: Jaky (1 − sin φ) if left empty. Linear Elastic: required in a deck with a K0 phase, and the export refuses without it | ✅ |
| c, φ, ψ (Mohr-Coulomb) | `GEO_COHESION` (Pa), `GEO_FRICTION_ANGLE`, `GEO_DILATANCY_ANGLE`; ψ ≤ φ | ✅ |
| Tension cut-off (Mohr-Coulomb) | `GEO_ENABLE_TENSION_CUT_OFF` always written; `GEO_TENSILE_STRENGTH` (Pa, ≤ c/tan φ) when on | ✅ |
| Sub-stepping (Mohr-Coulomb) | `GEO_MAX_NUMBER_OF_SUB_STEPS`, `GEO_MAX_RELATIVE_OVERSHOOT`, only when given | ✅ |
| c, φ on a Linear Elastic soil | Not written, so its K0 cannot silently come from φ | ✅ |
| Water unit weight | `DENSITY_WATER`, the same value the hydrostatic processes use | ✅ |

**Soil presets:** Fill, Sand loose, Sand dense, Clay soft, Clay stiff, Bedrock
([material-library.js](../frontend/js/material-library.js)).

### A6. Loads, water and boundary conditions

| Feature | Kratos | Dim | Status |
|---|---|---|---|
| Self weight | `VOLUME_ACCELERATION` on the computational part, in every stage | 2D/3D | ✅ |
| Point load | `PointLoadCondition2D1N` / `3D1N`, `POINT_LOAD` | 2D/3D | ✅ |
| Line load | `LineLoadCondition2D2N` / `LineLoadDiffOrderCondition2D3N`, `LINE_LOAD` | 2D | ✅ |
| Surface load | `UPwFaceLoadCondition3D3N` / `SurfaceLoadDiffOrderCondition3D6N`, `SURFACE_LOAD` | 3D | 🟡 |
| Normal load (Uniform or Hydrostatic) | `LineNormalLoadCondition2D2N` / `LineNormalLoadDiffOrderCondition2D3N` + `ApplyNormalLoadTableProcess` | 2D | ✅ hydrostatic, from a reference · 🟡 uniform |
| Switching 2D ↔ 3D | Point ↔ line ↔ surface load and sheet pile ↔ panel are converted, and linked by `derived_from` | — | ✅ tested |
| Load distribution | Uniform only; no time-dependent load for now | — | ❌ |
| Pore pressure | `ApplyScalarConstraintTableProcess`, hydrostatic about **one horizontal phreatic level** for the whole model | 2D/3D | ✅ |
| Phreatic level per borehole, sloping line, or level per phase | A per-borehole level is stored but not exported | — | ❌ |
| Boundary conditions | `Bottom_Fixed` fully fixed; left, right, front and back edges as rollers; top surface free | 2D/3D | ✅ |
| Anchor tail support | The tail node is fixed | 2D/3D | ✅ |

### A7. Staged construction

| Feature | Detail | Status |
|---|---|---|
| Phase types | K0 procedure, Plastic, Null step | ✅ |
| Phase tree | Each phase has a parent and stores only what it switches on and off. Kratos needs one sequence, so the tree is flattened; a tree that branches is rejected | ✅ |
| Default sequence | Initial stage (K0), null step, wall installation, then one excavation stage per lift (the water load moves down with it), with each anchor installed after the lift that exposes it | ✅ reproduces the 7 stages of Kratos' staged-excavation reference |
| Switching parts on and off | `ActivateModelPartOperation` / `DeactivateModelPartOperation` for soil bodies, lifts, beams, anchors, interfaces and loads | ✅ |
| Settings per phase | Reset displacements (`reset_totals`), max iterations, tolerance | ✅ |
| Stress carry-over | `ApplyFinalStressesOfPreviousStageToInitialState` | ✅ |
| Initial stresses | `apply_k0_procedure_process`, with its own `initial_materials.json` | ✅ |
| Soil kept connected before the wall is built | `AssignMasterSlaveConstraintsToNeighboursUtility` ties the split nodes together until the wall is installed | ✅ |
| Interface neighbour search | `FindNeighboursOfInterfacesProcess` | ✅ |
| Loading type | Staged construction only | 🟡 |

### A8. Output requested from Kratos

| Output | Variables | Status |
|---|---|---|
| GiD ASCII files (`.post.res`, `.post.msh`), one per stage | Nodal `DISPLACEMENT`, `TOTAL_DISPLACEMENT`, `WATER_PRESSURE`; Gauss-point `CAUCHY_STRESS_TENSOR` | ✅ |
| Wall forces at the nodes | `AXIAL_FORCE`, `BENDING_MOMENT`, `SHEAR_FORCE` | ✅ a live Kratos run is regression-tested; validated against Kratos' own curves |
| Interface tractions | `GEO_EFFECTIVE_TRACTION_VECTOR`, written to JSON on the retained side | ✅ |

---

## Part B — GUI features

### B1. Application and project

| Feature | Detail | Status |
|---|---|---|
| Architecture | Browser front end (three.js, no build step) talking to a local FastAPI server; Gmsh runs in its own single worker process so a crash cannot take the server down | ✅ |
| Starting it | `run.bat` / `run.sh` sets up its own Python environment and opens the browser; `--check` only checks the setup | ✅ Windows and Linux |
| Project files | New, Open, Save, Save as (project JSON) | ✅ |
| Undo and redo | Up to 40 steps, each a snapshot of the whole project | ✅ |
| Keyboard shortcuts | Ctrl+Z / Y / S / O / N; F9 calculates, or regenerates the mesh in Mesh mode; Esc; arrow keys recall earlier commands | ✅ |
| Validation | The server checks the whole project on every edit | ✅ |
| Rendering | WebGL, with a CPU fallback when the GPU is unavailable | ✅ |
| 2D and 3D | Switch between a 2D plane-strain section (at a chosen offset) and the 3D model; loads and walls are converted | ✅ |
| Modes | Soil, Structures, Mesh, Flow conditions, Staged construction, Results | ✅ Flow conditions only edits the water level |
| Panels | Model tree, property grids, docked panels, right-click menus (e.g. delete drawn or imported parts) | ✅ |
| Navigation | Iso, top, front and side views; zoom to fit; orbit; measuring rulers on all four edges in 2D | ✅ |

### B2. Geometry and soil

| Feature | Detail | Status |
|---|---|---|
| Boreholes | Add by clicking, or with `borehole x y` | ✅ |
| Soil layers | A stack of layers with a top and bottom at each borehole, interpolated in between; the stack is checked for gaps | ✅ |
| Free-form soil polygons | Not supported; layers are always a stack | ❌ |
| Excavation | Floor level plus several lifts; each lift crossed with each layer becomes its own soil body | ✅ |
| Drawing tools | Point, line, polygon, box, cylinder, load | ✅ |
| Soil volume dialog | Draw a polygon and extrude it (embankment, cutting, fill pad, lens); giving it a material turns it into soil | ✅ |
| CAD import | STEP, IGES, BREP, STL, OBJ (surfaces are rebuilt into solids) | ✅ |
| Kratos `.mdpa` import | View only: a preview with a checklist of parts; the mesh cannot be edited | ✅ |

### B3. Structures, loads and water

| Feature | Detail |
|---|---|
| Sheet piles, panels, members | Sections are shared, so many piles can use one profile; edited in a property panel |
| Anchors | The head snaps to a pile, panel or member; prestress is set per anchor |
| Interfaces | A **Side** row picks which face comes loose; contact properties are shared; with no pile it draws a free line |
| Loads | Point, line and surface loads given by their components; each can be switched off |
| Normal loads | A polyline with Uniform or Hydrostatic pressure |
| Water | One phreatic level for the whole model, drawn as a plane; water unit weight editable |

### B4. Mesh

| Setting | Options |
|---|---|
| Size and order | Global element size; linear or quadratic elements, optionally with straight edges |
| Algorithms | 2D: frontal, delaunay, meshadapt, auto. 3D: delaunay, frontal, hxt |
| Quality | Optimisation (none, gmsh, netgen), smoothing 0–100, points per curvature, minimum size factor |
| Local control | Target size per soil layer; box and cylinder refinement zones; Refine, Coarsen and Reset buttons |
| Selection | Only ticked layers are meshed; shared faces keep common nodes |
| Mesh labels | Node and element numbers drawn on the mesh, fanned out where nodes overlap |

### B5. Calculate and export

| Feature | Detail | Status |
|---|---|---|
| Export | File ▸ Export writes `.mdpa`, `MaterialParameters.json` and `ProjectParameters.json`, and lists every assumption and warning | ✅ |
| Calculate (F9) | Meshes the model, writes the files and runs Kratos in a new folder for each run | ✅ |
| Pointing to Kratos | `kratos.local.json` or environment variables: Python interpreter, Kratos build folder, runs folder, time limit (default 3600 s) | ✅ |
| Failed runs | Says which stage failed | ✅ |

### B6. Results mode

| Feature | Detail | Status |
|---|---|---|
| Runs | List every run, open one, step through its phases | ✅ |
| Quantities | \|u\|, u_x, u_y, u_z, both total and per phase; σ'xx, σ'yy, σ'zz, σ'xy, σ'yz, σ'xz; p', q, σ1, σ2, σ3, τ_max; pore pressure; total stresses, hydraulic head and saturation when Kratos wrote them | ✅ |
| Signs and units | Compression is negative, as in Plaxis; every quantity in the run's own unit system (Pa for SI, kPa for kN), lengths in m | ✅ tested |
| Display | Colour bands or smooth shading, colour map, reversed scale, automatic or fixed range, deformed shape with a chosen or automatic scale | ✅ |
| Node readout | Every quantity at one node (`results at <node>`) | ✅ |
| Export | The field on screen as CSV; any file from a run, or the whole run as a zip | ✅ |
| Wall force diagrams (N, Q, M) | Computed and tested on the server, but **not drawn** in the GUI | ❌ |
| Interface results, slip plane, factor of safety | Not available | ❌ |

### B7. Command line and scripting

| Command | What it does |
|---|---|
| `run <file.py>` or `load` | Runs a Python file that returns a `Project` and shows the model, e.g. `tests/models/excavation.py` |
| `export` | Writes the Kratos files |
| `cleargeometry` | Removes drawn and imported geometry |
| `results …` | `runs`, `open`, `phase`, `fields`, `field`, `at`, `bands`, `smooth`, `map`, `deform`, `range`, `reverse`, `csv`, `files`, `get`, `zip` |
| `view`, `zoomfit`, `goto<mode>` | Camera and mode changes |
| `soillayers`, `materials`, `mesh`, `borehole` | Open the dialogs, generate the mesh, add a borehole |
| Python | The `Project` is a plain pydantic model that scripts can build directly. There is also a REST API: `/api/project`, `/api/mesh`, `/api/calculate`, `/api/results/…` |

### B8. Testing and validation

| Item | Detail |
|---|---|
| Benchmarks | Analytical checks in `benchmarks` (K0 columns, hydrostatic, weight above and below water, reaction balance, symmetric pit, 2D/3D, mesh convergence), and a live Kratos run of the staged test model, skipped where Kratos is not installed |
| Server tests | pytest, 45 test files (run with Python 3.11, which has gmsh) |
| JavaScript tests | 33 browser test files; the ones that don't use the DOM also run headless under quickjs (`frontend/tests/run_headless.py`) |

---

## Main gaps

1. **Mohr-Coulomb has not been run yet.** The deck matches Kratos' Mohr-Coulomb
   reference materials file set by set; the wall curves still need a real run
   (`mohr_coulomb_project` in `tests/models/excavation.py`). No user-defined (UDSM/UMAT) models yet.
2. **No factor of safety.** There is no φ–c reduction phase.
3. **Only one flat water table.** No sloping phreatic line, no level per phase, no
   groundwater flow calculation.
4. **Wall force diagrams are not drawn.** Kratos writes them and the tests check them,
   but the Results view doesn't plot them.
5. **3D is unproven.** The 3D element, law and interface names have not been run in
   Kratos.
6. **Solver settings are fixed.** The analysis type and linear solver can't be chosen.
7. **No single-element test** for checking a soil model on its own.
