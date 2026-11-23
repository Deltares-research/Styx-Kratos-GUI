# Styx features and their status

This page lists what Styx can do, the status of each feature, and the code that does it.
Use it to find out if a feature works before you rely on its results. The page describes
the code on 2026-11-19.

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
- **Only linear elastic and Mohr-Coulomb soil are tested.** The GUI offers these two soil
  models. Styx writes any other law name as you type it, but no test runs it.
- **No safety analysis.** Styx has no φ–c reduction, so it gives no factor of safety.

## Part A: What Styx sends to Kratos

### A1. Analysis setup

| Feature | What Styx writes | Status | Source |
|---|---|---|---|
| Kratos application | GeoMechanicsApplication, solver type `U_Pw`, model part `PorousDomain` | Tested | [kratos/parameters.py](../core/kratos/parameters.py) `SOLVER` |
| Orchestrator | `SequentialOrchestrator` over named stages, each a `GeoMechanicsAnalysis` stage | Tested | [kratos/parameters.py](../core/kratos/parameters.py) `ORCHESTRATOR` |
| Analysis type | Static, or dynamic with Newmark or Backward Euler (Kratos' quasi-static U-Pw for a mechanical stage); Rayleigh damping is set for each dynamic mechanical stage. The strategy is chosen for each stage in its expert settings: Newton-Raphson (the default for a mechanical stage), quasi-Newton, Newton-Raphson with line search, or one linear solve; each with its own parameters. A flow stage's default is what its model calls for: one linear solve for a saturated soil, Newton-Raphson for one whose permeability depends on the water pressure, Newton-Raphson with seepage with a seepage face. The convergence criterion is chosen for each stage: residual (the default) or displacement for a mechanical stage; water pressure (the default) or residual for a flow stage; a flow stage of a project saved before the criterion could be chosen keeps the residual it was solved on. Kratos' `displacement_and_water_pressure_criterion` is not offered: Kratos 10.4.4 cannot build it. | Tested | [kratos/parameters.py](../core/kratos/parameters.py) `SOLVER` |
| Linear solver | Chosen for each stage in its expert settings: `sparse_lu` or `skyline_lu_factorization` (direct), `amgcl`, `bicgstab` or `cg` (iterative), each with its own parameters. The default is `sparse_lu`, scaled. The quasi-Newton strategy always uses `sparse_lu`, unscaled, shown but not changeable: a fully coupled soil with a very low permeability then settles a few percent too little (5% for 1e-16 m²), as the system is too badly conditioned to factorise unscaled. Block builder, 1 thread. | Tested | [model/solver.py](../core/model/solver.py) |
| Tolerances | Relative 1e-4, absolute 1e-9 (1e-12 on the displacement criterion, 1e-8 on the water pressure), 6 to 15 iterations, one attempt per step, reduction factor 0.5, increase factor 2.0 (1.0 for a dynamic mechanical stage, whose Newmark result changes when its step grows, and for an iterating flow stage). A stage solved in several steps can need an absolute tolerance of 1e-8: the steps after it has settled start from a round-off residual that 1e-9 cannot be met below. You can change the maximum number of iterations and the relative and absolute tolerances of the convergence criterion for each stage, and the time step control in its expert settings. | Tested | same |
| Time steps | Each stage has a duration and a time step, in the project's unit of time (seconds); by default 1 s each, so one step for each stage. The first stage starts at time 0 and each stage starts where the one before it ended. | Tested | [kratos/writer.py](../core/kratos/writer.py) |
| Units | One unit system for each project: SI (N, m, kg, s) or kN (kN, m, t, s). You type all values in it, the input files contain them without conversion, and the results come back in it. | Tested in both systems | [model/units.py](../core/model/units.py) |
| Groundwater flow | A project whose stages are all flow stages: solver type `Pw`, `Steady_State_Groundwater_Flow` (static) or `Transient_Groundwater_Flow` (dynamic), `sparse_lu` linear solver. One linear solve for a saturated soil, Newton-Raphson for a soil with another retention law. The deck holds the soil only. 2D only. A project that mixes flow and mechanical stages is refused. | Tested: the decks against the Kratos references `tests/Muskat/saturated_hydrostatic` and `van_genuchten_hydrostatic`; Kratos runs against the exact solution and the Kratos regression values (saturated), and against the Kratos regression values (Van Genuchten). The Muskat tutorial is run as a test, command by command, and cases A and C are built in the GUI: both give the decks of the model scripts and, in Kratos, the same answers | [kratos/parameters.py](../core/kratos/parameters.py) `FLOW_SOLVER` |
| Consolidation, arc-length control | Not supported. A dynamic stage and the updated mesh (`move_mesh_flag`, in a stage's expert settings) are written to the deck, but no test runs them in Kratos. | Not available | [model/schemas.py](../core/model/schemas.py) `Stage` |

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
| `Anchor` | Anchor: a 2-node tie, head free (on a sheet pile or a soil node) or fixed, tail free (a soil node) or fixed | `LinearTrussElement2D2N` | `TrussConstitutiveLaw`, prestress as `TRUSS_PRESTRESS_PK2` (a stress) | 2D | Tested: element from a Kratos reference deck |
| `SpaceAnchor` | 3D anchor, head free (on a panel, a member or a soil node) or fixed, tail free or fixed | `LinearTrussElement3D2N` | same | 3D | Limited |
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
| Law | The law of the interface section: **Elastic** (`GeoIncrementalLinearElasticInterfaceLaw`, the default), which reads the stiffnesses only, or **Coulomb** (`GeoInterfaceCoulombLawPlaneStrain`), which reads a strength too. The K0 stage always uses the elastic law. | Tested |
| Placement | Along a whole sheet pile or the part between two points on it (From, To), or along a free line through the soil (soil against soil, a slip surface, a lining). Side: both, left or right on the screen (below or above for a flat line). Many interfaces per pile, but only one on each face over a length. | Tested |
| Ends of an interface | At the toe, one node copy for the soil around it (for one face only: the soil on that side of the pile line). Where the pile goes on, the soil beyond the end stays on the pile node, as the Kratos-side InterfaceInserter does. | Tested, also in Kratos |
| Ties before installation | A master/slave tie for each split node, also for an interface on one face only | Tested |
| Along an anchor's grout body | Not possible: the grout body is a point in the model | Not available |
| Node splitting | Styx duplicates the nodes after it makes the mesh, so the contact has zero thickness | Tested, [kratos/interfaces.py](../core/kratos/interfaces.py) |
| Stiffness | `INTERFACE_SHEAR_STIFFNESS` and `INTERFACE_NORMAL_STIFFNESS` as you type them. If you leave them out: shear = G / t of the adjacent soil (t is the virtual thickness), normal = 10 × shear. | Tested |
| Strength | Read by a Coulomb law only. **From the soil**: c × R and atan(R × tan φ) of the adjacent soil. R is the `R_inter` of the section, or else the `R_inter` of the soil (default 0.7). **Set on the interface**: the `GEO_COHESION` and `GEO_FRICTION_ANGLE` you type. A linear elastic soil has no strength to give, so a Coulomb contact against one needs its own; the export refuses it otherwise. A Coulomb contact given a linear elastic soil (its law or its soil changed, in the GUI or with `kratos-cli section add/set`) gets the Mohr-Coulomb defaults as its own strength, and a note says so. A project saved before 2026-11-02 whose Coulomb contact names a linear elastic soil with c and φ keeps the strength its input files had, as the contact's own; one that names no soil is named when the file is opened. | Tested against the Kratos reference |
| Permeability | Neutral, Drain or Impermeable. The interface is always exported as drained (`CONSTANT_PW_FIELD`). | Not exported |
| 3D interfaces | Not exported. The export shows a warning. | Not available |

### A5. Soil materials

A soil material is a Kratos property set: a constitutive law and its `Variables`, with the
Kratos names, in the unit system of the project. Styx writes the property set as it is,
and adds only the values that are missing
([kratos/materials.py](../core/kratos/materials.py)).

| Feature | Detail | Status |
|---|---|---|
| Soil model | A **Soil model** list in the Soil material window (`--model` in the CLI): Linear elastic, Mohr-Coulomb or Other. The model sets the law and the parameters shown, in groups, with defaults ([model/soil_models.py](../core/model/soil_models.py)). A model chosen leaves out what another model reads and it does not, in the GUI and the CLI alike: Linear elastic leaves out the strength and the hardening. The window keeps them aside while it is open, so choosing Mohr-Coulomb again brings them back. | Tested |
| Linear elastic soil | `GeoLinearElasticPlaneStrain2DLaw` (2D), `GeoIncrementalLinearElastic3DLaw` (3D). The law follows the dimension of the model. | Tested in 2D. Limited in 3D. |
| Mohr-Coulomb soil | `GeoMohrCoulombLawPlaneStrain` (2D), `GeoMohrCoulombLaw3D` (3D), with `GEO_COHESION`, `GEO_FRICTION_ANGLE`, `GEO_DILATANCY_ANGLE`, `GEO_ENABLE_TENSION_CUT_OFF` and `GEO_TENSILE_STRENGTH`. A new soil has c = 1 kPa, φ = 30°, ψ = 0°, no tension cut-off and `SaturatedBelowPhreaticLevelLaw`. The old names `GeoMohrCoulombWithTensionCutOff2D/3D` become the current ones when a project loads. **Hardening**: None (the default, not written) or Linear (`GEO_COULOMB_HARDENING_TYPE`). Linear shows the three slopes Kratos reads, per unit of plastic strain: `GEO_COHESION_FUNCTION_COEFFICIENTS` (a stress), `GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS` and `GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS` (in radians). Each starts at 0 when Linear is chosen, and one left out is written as 0. Each is written as a one-entry vector; a negative one is refused. | Tested in 2D, in Kratos too |
| Other laws | Any law name, for example a UDSM, with its own variables. Styx writes it as typed. | Limited: no test runs it in Kratos |
| Choices | `GEO_DRAINAGE_TYPE` (`CONSTANT_PW_FIELD`, `FULLY_COUPLED`, shown as "Mechanical only" and "Fully coupled", each with a line under the list saying what it solves; see Mechanical-only soil and Undrained soil) and `RETENTION_LAW` (`SaturatedLaw`, `SaturatedBelowPhreaticLevelLaw`, `VanGenuchtenLaw`) are lists of the values Kratos accepts. `GEO_COULOMB_HARDENING_TYPE` (`None`, `Linear`) too. `GEO_ENABLE_TENSION_CUT_OFF` is a check box. | Tested |
| Required variables | `YOUNG_MODULUS`, `POISSON_RATIO`, `DENSITY_SOLID`, `POROSITY` for every soil model; for Mohr-Coulomb also c, φ and ψ, and the tensile strength when the cut-off is on. The export refuses a soil without them, and a Mohr-Coulomb soil with ψ > φ, φ ≥ 90° or a tensile strength above c / tan φ. | Tested |
| Water | One for the whole project, in every soil: `DENSITY_WATER` from the specific weight of the water level, and `BULK_MODULUS_FLUID` and `DYNAMIC_VISCOSITY` from **Water** in the Soil materials window (`kratos-cli fluid`), water's at 20 °C (2.2 GPa, 1 mPa·s) when not set. A soil cannot carry its own. A project saved before 2026-11-02, whose soils each carried their water, takes the first soil's bulk modulus and viscosity; opening it (GUI Open or any `kratos-cli` command) warns, per soil, about every water value its input files no longer get. | Tested |
| Calculated variables | If they are missing: `GEO_DRAINAGE_TYPE` = `CONSTANT_PW_FIELD`, the bulk modulus of the grains (10 GPa), the symmetric permeabilities, a permeability of 1 m/day for a `FULLY_COUPLED` soil, `MINIMUM_RELATIVE_PERMEABILITY` = 1e-4 for a soil whose retention law is not `SaturatedLaw` (Kratos checks it for every drainage type), `VAN_GENUCHTEN_GL` = 1.25 for a soil with `VanGenuchtenLaw` (the same), and the Biot coefficient 1 − K / K_s. The Soil materials window shows each value; the export writes each and lists it in a warning, except a `FULLY_COUPLED` soil's Biot coefficient outside a groundwater flow project: Kratos derives that one from the soil's current stiffness, which for a soil that yields is not the elastic value the window shows. | Tested |
| Mechanical-only soil | A `CONSTANT_PW_FIELD` soil ("Mechanical only") solves the displacements with prescribed pore pressures: its water pressures are the ones the water conditions set, and the deformation does not change them. Kratos' own `DRAINED` is not offered: Kratos calculates it as a `FULLY_COUPLED` soil. A mechanical-only soil shows no permeability, and Kratos reads none: `kratos-cli material set` keeps one that is given and says that it is not used. `DRAINED` in a saved project, a script or `kratos-cli material set` becomes `CONSTANT_PW_FIELD`, and the input files do not change. A `DRAINED` soil saved before 2026-11-02 was written as Kratos' `DRAINED`, which Kratos calculates as `FULLY_COUPLED` with the soil's own permeability. It is now written as `CONSTANT_PW_FIELD`, which can change the results. Opening such a project names each of these soils, except in a groundwater flow project, which reads no drainage type. | Tested |
| Undrained soil | `UNDRAINED` is not a drainage type. Kratos assembles it as a `FULLY_COUPLED` soil. An `UNDRAINED` soil in a saved project, a script or `kratos-cli material set` becomes `FULLY_COUPLED` with its own permeability, the one the export wrote for it. Its undrained Poisson's ratio is dropped. Opening such a project names each of these soils, and so does `material set`. A low permeability does not make a soil undrained: a stage is static (consolidation is not supported), so a load does not raise the water pressure of a `FULLY_COUPLED` soil, whatever its permeability. For an undrained soil, use a `CONSTANT_PW_FIELD` soil with undrained values (total stresses): the undrained Young's modulus, a Poisson's ratio close to 0.5 and, for Mohr-Coulomb, the undrained shear strength as cohesion with a friction angle of 0. | Tested |
| New soil | **Create soil** in the Soil materials window and `kratos-cli material add` (without `--preset`) make the same soil: linear elastic, `CONSTANT_PW_FIELD`, `SaturatedBelowPhreaticLevelLaw` with its saturations, and nothing else ([soil_models.py](../core/model/soil_models.py) `blank_si`). Both say what it still needs before a calculation. Every soil created, duplicated or added from a preset, in the GUI or with `kratos-cli material add`, gets a colour no other soil of the project has: a preset its own while it is free ([soil_models.py](../core/model/soil_models.py) `fresh_color`). A model chosen for a soil that still has empty values fills in none that the law needs. | Tested |
| K0 | `K0_NC`, or else ν / (1 − ν) for a linear elastic soil and Jaky's 1 − sin φ for a Mohr-Coulomb one, in `initial_materials.json`. A linear elastic soil takes ν / (1 − ν) even when it has a friction angle. Before 2026-11 it took Jaky's. The new rule applies to existing projects too: migration does not write the old K0 into them, so a saved project with a linear elastic soil and no `K0_NC` now starts from different initial stresses. Opening such a project names each soil, with its old and its new K0. Type `K0_NC` to keep the old value. | Tested |
| Shown, not written | The unit weight dry and saturated of a soil, and its Darcy permeability k = κ γw / μ. | Tested |
| K0 stage | The K0 stage runs elastic. A soil with a different law uses the linear elastic law in `initial_materials.json`, and its own law from the next stage on. | Tested |
| Soil presets | The default soils of D-Stability and D-Settlement: Embankment, Clay shallow and deep, Organic clay, Peat shallow and deep, Clay with silt, Sand with clay, Sand, Sand permeable and less permeable, and Bedrock ([drafts.py](../core/model/drafts.py) `LIBRARY`, [material-library.js](../frontend/js/material-library.js)). Each can be added as a Mohr-Coulomb or a linear elastic soil, in the material window's **Model** list and with `kratos-cli material add --preset ID --model M` | Tested |
| Old projects | A project from before 2026-10-10 (in kN, kN/m² and m/day) is converted when it is opened, so its input files do not change, except the K0 of a soil without `K0_NC` (see K0) ([model/migration.py](../core/model/migration.py)). A project saved before 2026-11-02 gets `POROSITY` = 0.3 for a soil without one, the value the export filled in then. Its `DRAINED` soils are written as `CONSTANT_PW_FIELD` (see Mechanical-only soil), and its `UNDRAINED` soils are now `FULLY_COUPLED` (see Undrained soil). | Tested |

### A6. Loads, water and boundary conditions

| Feature | Kratos | Dim | Status |
|---|---|---|---|
| Self weight | `VOLUME_ACCELERATION` on the computational part, which holds the nodes of every body, structures included, in every stage, with g = 9.81 m/s² or the project's own g (`gravity 9.80665`, or **File** → **Project properties…**). In a mechanical sequence the initial stage's stress initialisation decides it: K0 or gravity loading has it, none has none; the initial stage's **Gravity** row in the **Stages** window says which. A flow sequence always has it. | 2D, 3D | Tested |
| Point load | `PointLoadCondition2D1N` / `3D1N`, `POINT_LOAD` | 2D, 3D | Tested |
| Line load | `LineLoadCondition2D2N` / `LineLoadDiffOrderCondition2D3N`, `LINE_LOAD` | 2D | Tested |
| Surface load | `UPwFaceLoadCondition3D3N` / `SurfaceLoadDiffOrderCondition3D6N`, `SURFACE_LOAD` | 3D | Limited |
| Normal load (uniform or hydrostatic) | `LineNormalLoadCondition2D2N` / `LineNormalLoadDiffOrderCondition2D3N` with `ApplyNormalLoadTableProcess` | 2D | Tested for hydrostatic, from a reference deck. Limited for uniform. |
| Change between 2D and 3D | Styx converts point, line and surface loads, and sheet piles and panels, and links them with `derived_from` | — | Tested |
| Load distribution | Uniform only. No load that changes with time. | — | Not available |
| Water pressure conditions | `ApplyScalarConstraintTableProcess`: `Uniform`, `Hydrostatic` (about the level of the condition) or `Phreatic_Multi_Line`, and head lines (a `Phreatic_Multi_Line` to Kratos), fixed or as start values only, on the whole soil, a soil part, a face, a drawn line or a point. A phreatic line on the whole soil or on a drawn line is the whole soil's water, one on in each stage. As start values, a phreatic or head line is written in the stage it comes on only, so a later stage carries on from the pressure the stage before left. A project saved before 2026-11-18 with a phreatic line drawn on a line (then a pressure on that line only) opens with a level one as a `Hydrostatic` condition on that line, and a sloping one as the whole soil's water, with a note. Without a condition, Styx fixes no water pressure. | 2D, 3D (lines and points 2D) | Tested |
| Water of each soil | Each soil takes the phreatic line (the default, on the whole soil wherever it is drawn), a head line (a sloping polyline, written as a `Phreatic_Multi_Line` on the soils that take it only), or `Interpolate_Line` (`ApplyConstantInterpolateLinePressureProcess`): the pressures on its edges, which the soils around it set, interpolated over its depth. For aquifers and aquitards. | 2D (a head line on the whole soil in 3D too) | Tested: the deck, and in Kratos 10.4.4 a clay interpolated between sand and an aquifer under a sloping head line, both lines drawn on lines, at every node |
| Water conditions for each stage | A stage switches a water pressure condition on or off, as it does a load. The Kratos stage writes the conditions that its stage has on. | 2D, 3D | Tested |
| Water on the ground | The `Phreatic_Multi_Line` water pressure condition (on any target; on a soil part, that part's surface only) whose level is above the soil adds the water's weight as a normal load on the exposed surface below it: the ground surface, the floor and faces of a dug pit, and the face of a wall. It is worked out for each stage, from the soil that the stage has. It always pushes on the soil or the wall. A soil edge is written in the order of the element that stays, and a wall drawn with the water on its left gets the pressure node by node, negative. A phreatic multi-line is written as one `Phreatic_Line` for each segment, because Kratos has no multi-line normal load. Where you drew a normal load, yours is used there instead. The Flow conditions and Calculation settings tabs show it for the stage chosen in the Stage list beside the tabs: the open water filled in light blue up to the phreatic line, small arrows into the soil and the deepest pressure (`frontend/js/surface-water.js`). A `Hydrostatic` condition on a line or a face is drawn in 2D in indigo: the line thick where it is under water, and a filled pressure diagram along it. The Model explorer lists the stages that have it under the phreatic line. A 3D model adds none, and the export warns. | 2D | Tested on the deck, not yet in a Kratos run |
| Wet surface | Under a phreatic line as start values that stands above the ground, the water pressure on the exposed soil surface is fixed to the line's: one `ApplyScalarConstraintTableProcess` (`Phreatic_Multi_Line`, fixed) on the wet nodes, worked out for each stage like the load, and written in a flow deck too. A stage that leaves part of it dry writes those nodes again as start values, which frees them: Kratos keeps a node that a phreatic process fixed fixed after its stage. A flow stage with such a line needs no other fixed condition. | 2D | Tested: the deck, and in Kratos 10.4.4 a column under 1 m of water then lowered below the ground, or with the water switched off, hydrostatic about each level in turn at every node |
| Seepage face | `GeoSeepageCondition2D2N` / `2D3N` on the mesh edges of a face or of a line along the soil's outer boundary, one `ApplySeepageBoundaryProcess`, and the `newton_raphson_with_seepage` strategy. Groundwater flow only, in every stage; a mechanical deck leaves it out and says so. A line through the soil is refused. | 2D | Tested: the deck against Kratos' `tests/seepage_tests` and the STEM Muskat geometry, and a Kratos run against the water balance and the Dupuit-Charny discharge |
| Displacement conditions | `ApplyVectorConstraintTableProcess` on a face, a soil part, a drawn line or a point, in the components x, y, z that you select. A new project has the bottom fixed and the sides on rollers. | 2D, 3D (lines and points 2D) | Tested |
| Anchor ends | **Head end** free: the head node is a node of the structure it is on, or of the soil mesh. **Tail end** free: the tail node is a node of the soil mesh. Fixed: the end node is in no other element and is fixed; a fixed head is not moved onto a structure. A new anchor has both ends free; a project saved without the settings keeps a free head and a fixed tail. | 2D, 3D | Tested |

### A7. Construction stages

| Feature | Detail | Status |
|---|---|---|
| Stage settings | A new project starts with its initial stage, which cannot be deleted or preceded. Calculation type, chosen in the initial stage for every stage: mechanical (`U_Pw`) or flow (`Pw`). Stress initialisation, of the initial stage of a mechanical sequence only: K0 procedure, gravity loading (the default) or none. Time integration: static or dynamic (`Dynamic` for a mechanical stage, `Transient_Groundwater_Flow` for a flow stage). Every stage of a groundwater flow project is a flow stage. A new calculation type is one entry in `schemas.Stage` and `parameters.SOLVERS`. | Tested: the decks; no dynamic stage has run in Kratos in a test |
| Stage tree | Each stage has a parent, and keeps only what it switches on and off. Kratos needs one sequence, so Styx makes the tree into a list. A tree that branches is refused. | Tested |
| Staged excavation | A wall and lines split the soil into lifts, and a stage switches each lift off. `tests/models/excavation.py` and the tutorial model have the 7 stages of the Kratos staged-excavation reference: K0, null step, wall installation, then one stage for each lift with its water load, and the strut after the lift that uncovers it. | Tested |
| Switch parts on and off | `ActivateModelPartOperation` / `DeactivateModelPartOperation` for soil bodies, lifts, beams, anchors, interfaces and loads | Tested |
| Settings for each stage | Reset displacements (`reset_totals`), convergence criterion, maximum iterations, relative and absolute tolerance, and the expert solver settings: strategy, linear solver, time step control, time scheme of a dynamic stage, assembly. Only those that apply are shown, each with the default for the stage's calculation type and time integration | Tested |
| Stresses carried to the next stage | `ApplyFinalStressesOfPreviousStageToInitialState` for the interfaces, beams and anchors in two stages in a row. This includes the two-stage deck of a project without stages. The soil keeps its own stress. A prestressed anchor also gets a **temporary workaround**: `kratos_gui_prestress_workaround.py`, shipped with the deck. Without it, Kratos adds the prestress again in every stage. The workaround goes once Kratos is fixed. In 3D, Kratos cannot carry the forces of a wall panel or a member, and the export warns when one is in two stages in a row. | Tested, in Kratos too (2D) |
| Initial stresses | `apply_k0_procedure_process`, with its own `initial_materials.json` | Tested |
| Soil connected before the wall is built | `AssignMasterSlaveConstraintsToNeighboursUtility` ties the split nodes together until the wall is installed | Tested |
| Interface neighbour search | `FindNeighboursOfInterfacesProcess`, in the stage an interface arrives in, so it starts from the stress of its soil | Tested |
| Loading type | Staged construction only | Limited |

### A8. Output that Styx asks from Kratos

| Output | Variables | Status |
|---|---|---|
| GiD ASCII files (`.post.res`, `.post.msh`), one pair for each stage | Nodal `DISPLACEMENT`, `TOTAL_DISPLACEMENT`, `WATER_PRESSURE`, and `REACTION` when the stage computes reactions (the default); `CAUCHY_STRESS_TENSOR` and `HYDRAULIC_HEAD` (not without the self weight) at the Gauss points | Tested; `REACTION` in a Kratos run: the vertical reactions of the initial stage of a staged excavation add up to the weight of the model |
| Groundwater flow, one pair of GiD files for each stage | Nodal `WATER_PRESSURE`, `EFFECTIVE_SATURATION` and `FLUID_FLUX_VECTOR` (the last two extrapolated from the Gauss points), `NODAL_WATER_FLOW_RATE` with a seepage face, and `REACTION_WATER_PRESSURE` when the stage computes reactions (the default); `HYDRAULIC_HEAD` at the Gauss points. `REACTION_WATER_PRESSURE` is the nodal water flow rate with the opposite sign. Every flow strategy computes it; only the seepage strategy computes `NODAL_WATER_FLOW_RATE`, which is zero otherwise. | Tested; in a Kratos run the two are equal and opposite at every node of the Muskat seepage case, and the flow in and out of the saturated column is Darcy's |
| Wall forces at the nodes | `AXIAL_FORCE`, `BENDING_MOMENT`, `SHEAR_FORCE` | Tested: a live Kratos run is checked, and agrees with the Kratos reference curves |
| Interface tractions | `GEO_EFFECTIVE_TRACTION_VECTOR`, written to JSON on the retained side | Tested |

## Part B: What the GUI and kratos-cli do

### B1. Application and projects

| Feature | Detail | Status |
|---|---|---|
| Architecture | A browser front end (three.js, no build step) and a local FastAPI server. Gmsh runs in its own worker process, so a Gmsh crash does not stop the server. | Tested |
| Start | `run.bat` or `run.sh` makes its own Python environment and starts the server. `run.bat` also opens the browser when the server is ready. `--check` only checks the setup. | Tested on Windows, Linux and macOS |
| Project files | New, Open, Save, Save as (a project JSON file). The server keeps the open project in memory only. | Tested |
| Undo and redo | Up to 40 steps, each a copy of the full project | Tested |
| Keyboard shortcuts | Ctrl+Z, Ctrl+Y, Ctrl+S, Ctrl+O, Ctrl+N, F1 (the documentation site), F5 (zoom to fit), F9 (calculate, or make the mesh in Mesh mode), Esc. The arrow keys recall earlier commands. | Tested |
| Help | **Help** → **Documentation** (F1) and **GUI tutorials** open the documentation site, published from `main` on GitHub Pages, in a new browser tab ([documentation.js](../frontend/js/documentation.js)) | Tested |
| Checks | The server checks the full project at each edit | Tested |
| Display | WebGL, with a CPU renderer when no GPU is available | Tested |
| Pictures | The view as PNG, PDF or SVG at 300 dpi, in a width that you select, from the camera button, the File menu or a right click. Copy to the clipboard. Every stage and every result field into one folder, with the field values as CSV. `kratos-cli picture` makes the same pictures with Chrome or Edge. SVG and PDF are vector, except contour colours and 3D faces, which are an image at 300 dpi. | Tested. Opening in Word, Adobe Reader and Inkscape is checked by hand. |
| Feedback | The **Feedback** button, **Help** → **Send feedback…**, a button in the title bar of each window, and `feedback [text]` add a report to the writer's ZIP file of the day in `~/KratosGUI/feedback`, one folder per report: the message, where in the app it was written, a picture of the whole Styx window (the open windows, what was typed in them, the Session log) and one of the view, the files the user adds (a pasted screenshot, a document, any file), the model, the logs of the GUI and the server, and the log of the open run. After a server error, a failed calculation or a script error, a note offers to save a report about it. `kratos-cli feedback` saves the same report. | Tested |
| 2D and 3D | Change between a 2D plane-strain section (at a z offset that you select) and the 3D model. Loads and walls are converted. | Tested |
| Modes | Soil, Structures, Flow conditions, Mesh, Calculation settings, Results | Tested. Flow conditions sets the water level and the water pressure conditions. Calculation settings makes the stages and sets how each is calculated. |
| Stage list | Beside the mode tabs. Soil, Structures and Flow conditions show the chosen stage and switch parts and conditions on and off in it; a part switched off is drawn faint. Results shows the chosen stage of the run. Greyed in Mesh: Kratos uses one mesh for every stage, so a part a stage switches off is still meshed. | Tested |
| Panels | Model explorer, Selection explorer, docked panels, right-click menus | Tested |
| Navigation | Iso, top, front and side views; zoom to fit; rotate; rulers on all four edges in 2D | Tested |

### B2. Geometry and soil

| Feature | Detail | Status |
|---|---|---|
| Soil layers | A stack of horizontal layers across the whole domain, each with one top and one bottom. Made in **Modify soil layers** or with `kratos-cli layer`. The stack is checked for gaps. | Tested |
| Free soil polygons in the stack | Not supported. Layers are always a stack. | Not available |
| Soil surface (2D) or soil volume (3D) | Type the corners of an outline and select a material (embankment, cutting, fill, lens). In 2D also `kratos-cli surface`. | Tested |
| Lines that split the soil | Drawn with **Create line**, typed in the Line window, or `kratos-cli line`. Where a line or a sheet pile crosses a layer or a soil surface from edge to edge, it becomes separate soil bodies. A stage can switch each off, and each can have its own name and material (for all stages). A new line is made in the 2D section only; in 3D a line cuts across the whole z range. In 3D a line splits a soil volume only when the volume is a polygon extruded along z, or a box; an imported solid or a cylinder stays whole. | Tested |
| Old saved excavations | A project saved with an excavation pit opens with lines and soil bodies in its place. | Tested |
| Drawn solids | Box, cylinder and extruded polygon with `kratos-cli volume add`; with `--material` they are soil. The GUI has no tool for them. | Limited |
| CAD import | STEP, IGES, BREP, STL, OBJ (surfaces are made into solids) with `kratos-cli volume import`; with `--material` the solid is soil. Not in the GUI. | Limited |
| Kratos `.mdpa` import | View only: a preview with a list of parts. You cannot change the mesh. | Tested |

### B3. Structures, loads and water

| Feature | Detail |
|---|---|
| Sheet piles, wall panels, members | Sections are shared, so many piles can use one profile. You edit them in the Selection explorer. |
| Anchors | A free head moves onto a pile, a panel or a member; a fixed head stays where it is typed. The prestress is set for each anchor. |
| Interfaces | The interface window: a sheet pile by name with **From** and **To**, or own coordinates; the faces as on the screen; the contact. Contact properties are shared. |
| Loads | Point, line and surface loads by their components. You can switch each one off. |
| Normal loads | A line with uniform or hydrostatic pressure |
| Water | One water level for the full model. A new hydrostatic condition or normal load takes it as its own level. You can change the specific weight of the water. |
| Boundary conditions | The **Boundary conditions** window: a row for each face and one for the whole soil, with the support and the water pressure on each, and the conditions on parts, lines and points. Tools draw a support or a water pressure along a line or at a point (2D). |

### B4. Mesh

| Setting | Options |
|---|---|
| Size and order | Global element size; linear or quadratic elements, optionally with straight edges |
| Algorithms | 2D: frontal, delaunay, meshadapt, auto. 3D: delaunay, frontal, hxt. |
| Quality | Optimisation (none, gmsh, netgen), smoothing steps, points along curves, minimum size factor |
| Local control | An element size and a band (the distance over which the size grows back to the global size) for each soil layer and body, structure, interface, normal load, soil line, condition on a line or at a point, and point load, in the Selection explorer, the **Mesh properties** window and `kratos-cli mesh`; **Refine mesh**, **Coarsen mesh** and **Reset local refinement** on the selected object. Box and cylinder refinement zones from a model script or `kratos-cli add` still mesh. |
| Whole model | Every soil layer and soil body gets a mesh, also when it is hidden or another object is selected, as with `kratos-cli mesh`. Shared faces keep common nodes. To leave a part out of the mesh, remove it from the model. |
| Mesh labels | Node and element numbers on the mesh, spread out where nodes overlap |

### B5. Calculation and export

| Feature | Detail | Status |
|---|---|---|
| Export | **File** → **Export model…** writes the Kratos input files in one ZIP file, and lists each assumption and warning | Tested |
| Calculate (F9) | Uses the mesh of the model (makes one if there is none), writes the files, and runs Kratos in a new run folder | Tested |
| Stop a calculation | While Kratos runs, Calculate is a **Stop** button (also in the Convergence window and the Stages menu, and `calculate stop`). Kratos stops at once; the model does not change, and the run folder keeps the results of the stages that finished. <kbd>Ctrl</kbd>+<kbd>C</kbd> does the same in `kratos-cli`. | Tested |
| Kratos location | `kratos.local.json` or environment variables: Python of Kratos, build folder, runs folder, time limit (default 3600 s) | Tested |
| Failed runs | The log names the stage that failed | Tested |
| Convergence while Kratos runs | The **Convergence** window opens with Calculate and shows the relative and the absolute residual of each iteration, about once a second, until the run ends. `kratos-cli run --follow` and `calculate --follow` print the same iterations. The points arrive one by one only where the Kratos build shares the C runtime of its Python, which is so on the Windows build that the tests use. Linux is not tested. | Limited |

### B6. Results mode

| Feature | Detail | Status |
|---|---|---|
| Runs | List all runs, open one, go through its stages | Tested |
| Quantities | In groups. **Deformations** and **Stage deformations**: \|u\|, u_x, u_y, total and for each stage. **Effective stresses** (and **Total stresses** if Kratos wrote them): σ'xx, σ'yy, σ'zz, σ'xy; p', q, σ1, σ2, σ3, τ_max. **Water pressure and head**: pore pressure; hydraulic head (with the self weight), from the soil's integration points only. **Groundwater flow**: the flux \|q\|, q_x, q_y, and the nodal water flow rate (positive out) of every groundwater flow stage. **Saturation**: effective saturation, and the degree of saturation if Kratos wrote it. **Nodal forces**: the reaction \|R\|, R_x, R_y, per metre of the section. In a 2D section the z components (u_z, q_z, R_z, σ'yz, σ'xz) are not offered: they are zero. | Tested |
| Signs and units | Compression is negative, as Kratos writes it. All quantities are in the unit system of the run (Pa for SI, kPa for kN); lengths in m. | Tested |
| Display | Colour bands or smooth shading, colour map, reversed scale, automatic or fixed range, deformed mesh with a selected or automatic scale | Tested |
| Loads and water | The loads and the water level of the stage on screen over the colours (without their text labels), when the run is of the open project (`results loads on\|off`) | Tested |
| Zero pressure line | The line where the pore pressure is zero, drawn as a wide light-blue line over the colours: always after a groundwater flow stage; after a coupled (mechanical) stage when switched on (`results zeroline on\|off`, off by default). In 2D it continues along the stage's phreatic line where that line runs outside the soil | Tested |
| Integration points | A stress or the hydraulic head, computed at the integration points, is drawn per element (the default) or averaged to the nodes, one choice for all of them (`results location elements\|nodes`, the **Location** box, *Results → Integration points*) | Tested |
| Arrows | A vector (the displacement, the flux, the reaction) as arrows over the colours: any vector the stage has, over any field, such as the flux over the head (`results arrows on\|off\|<field>`). One arrow for each square of the arrow length; the longest arrow is 4 % of the model | Tested |
| Totals | The nodal water flow rate and the reaction components are added up over the model: the water that comes in and goes out (and the difference: what the pores stored in a transient stage), or what the supports carry | Tested |
| Values at a node | All quantities at one node (`results at <node>`) | Tested |
| Plots along the wall | Bending moment M, shear force Q, normal force N, displacements ux and uy along the wall, and the tractions tn and ts along the interface, with one line for each stage. Save as PNG, PDF, SVG or CSV. | Tested |
| Convergence plot | The residuals of each iteration of any run, also of a run that failed, read from its `kratos.log`: targets, iterations where the criterion was met, steps cut back or at the iteration limit, and the fraction of unbalance when Kratos printed it. Each criterion (residual, displacement, water pressure) has its own colour, so a run whose stages use different criteria is read right. A slider, or `results convergence stage N`, shows one stage alone. The plot grows with its window. Save as PNG, PDF, SVG or CSV. A deck with two convergence criteria prints two lines per iteration, and the plot counts both as iterations. | Tested |
| Export | The field on screen as CSV; one file of a run, or the full run as a ZIP file | Tested |
| Slip plane, factor of safety | Not available | Not available |

### B7. Command box and scripts in the GUI

| Command | What it does |
|---|---|
| `run <file.py>`, `load <file.py>` | Runs a Python file that returns a `Project`, and shows the model. Example: `tests/models/excavation.py`. |
| `script <file.py>` | Writes the model as a model script |
| `mesh`, `calculate`, `export` | Makes the mesh, calculates, or writes the Kratos files |
| `stages` | Opens the **Stages** window |
| `water`, `units`, `domain`, `cleargeometry` | Changes the water level, the unit system or the size of the soil block, or removes drawn and imported solids |
| `boundary`, `gravity` | Lists the boundary conditions or puts the standard supports back; shows whether the self weight acts, or sets g |
| `soillayers`, `materials` | Opens the soil windows |
| `colour`, `node` | Shows parts of the mesh in colour, or the parts that contain a node |
| `results …` | `runs`, `open`, `stage`, `fields`, `field`, `location`, `arrows`, `at`, `bands`, `smooth`, `map`, `deform`, `range`, `reverse`, `mesh`, `loads`, `zeroline`, `plot`, `convergence`, `csv`, `files`, `get`, `zip` |
| `feedback [text]` | Opens the **Send feedback** window, with the text in it |
| `view`, `zoomfit`, `goto<mode>`, `clear`, `help` | Changes the view or the mode, clears the log, lists the commands |

The `Project` is a pydantic model that a script can build directly. The server also has a
REST API: `/api/project`, `/api/mesh`, `/api/calculate`, `/api/calculate/status`,
`/api/results/…`.

### B8. Command line (kratos-cli)

| Feature | Detail | Status |
|---|---|---|
| Commands | Each step of the GUI as a terminal command, on the same project file: site, soil, structures, loads, mesh, stages, export, run, results. See the [kratos-cli reference](CLI.md). | Tested |
| Shell | `kratos-cli shell` reads commands one after the other, with undo and redo, from a terminal, a file or a pipe | Tested |
| Model scripts | `script` writes the model as Python; `build` writes a project from a script. Each command that reads a model accepts a script. | Tested |
| Results | `results` gives numbers and CSV files. `picture` saves pictures with Chrome or Edge. | Tested |
| Feedback | `feedback "MESSAGE"` adds the report of the GUI's Feedback window to the same ZIP file of the day, with the project file, the run and the files of `--attach`. After an error that no command expected, `kratos-cli` says how to report it. | Tested |
| Parity with the GUI | A test checks that each command of the GUI command box has a terminal command in the reference | Tested |

### B9. Tests and benchmarks

| Item | Detail |
|---|---|
| Benchmarks | Analytical and self-consistency checks in `benchmarks/`: K0 columns, weight above and below the water, hydrostatic column, symmetric excavation, 2D against 3D, mesh convergence, order 1 against order 2, saturated block, building pit, line loads in stages, balance of reactions, the three Muskat groundwater flow cases. They need Kratos. |
| Server tests | pytest, 151 test files in `tests/`. Run them with `python tools/test.py quick`. |
| JavaScript tests | 80 test files in `frontend/tests/`, run in a browser with Playwright (`python tools/test.py browser`). The files that do not use the DOM also run without a browser under quickjs. |

## Main gaps

1. **A stage applies its load in one step by default.** A Mohr-Coulomb soil runs in
   Kratos (the staged excavation of `tests/models/excavation.py` runs all its stages),
   but a stage that makes much of the soil yield can stop without converging in one
   step. A time step shorter than the stage's duration, more iterations, or a larger
   tolerance can help.
   User-defined models (UDSM, UMAT) are written as typed, without a test.
2. **No factor of safety.** Styx has no φ–c reduction stage.
3. **Groundwater flow is 2D only.** A project cannot mix flow stages
   with mechanical stages. With a Van Genuchten soil, the
   Newton-Raphson iterations can fall into a cycle on some meshes and stop without
   converging; another element size then helps.
4. **3D is not proven.** No 3D element, law or interface has run in Kratos in a test.
   Kratos cannot carry the forces of a wall panel or a member from one stage to the
   next. A panel starts each stage at zero force. A quadratic member stops the run, and
   a linear one carries a stress of the wrong size. The export warns when one is in two
   stages in a row.
5. **Only the solver settings listed.** A stage's expert settings offer the
   strategies and linear solvers above, not all of Kratos': no arc-length or piping
   strategy, and no Pardiso or other linear solver this Kratos build does not have.
6. **No single-element test** to check a soil model on its own.
