# Groundwater flow: the Muskat column with `kratos-cli`

Three steady-state groundwater flow models of one soil column, built and run from
PowerShell. Each one changes the model before it:

| Case | Soil | Right face | What it shows |
|---|---|---|---|
| A | saturated | held at a water level of 1.6 m | a flow with an exact answer |
| B | Van Genuchten | held at 1.62 m | an unsaturated zone above the phreatic line |
| C | Van Genuchten | tail water up to 0.48 m, a seepage face above it | where the water leaves the soil |

Cases A and B are Kratos' own tests `tests/Muskat/saturated_hydrostatic` and
`van_genuchten_hydrostatic`. Case C is the full Muskat problem.

Every command below was run on 2026-10-24, and the output shown is what it printed (long
paths are shortened to `...\`). The ready-made models are in
[`examples/Muskat_case/`](../../examples/Muskat_case/README.md).

## Before you start

- Kratos must be set up on this machine: see [Setting up Kratos](../KRATOS_SETUP.md). Case C
  needs a Kratos build that has the seepage condition (`GeoSeepageCondition2D2N`).
- Work in a folder of your own, so the files stay out of the repository. In the commands,
  `kratos-cli` is `<repo>\kratos-cli.bat`.
- To write the runs into that folder too, set `$env:KRATOS_GUI_RUNS = (Get-Location)`.

## Case A: a saturated column

### The model

```powershell
kratos-cli new muskat.json --force --dim 2 --name "Semi-Muskat"
kratos-cli domain muskat.json --x 0 1.62 --y 0 4 --z 0 1
kratos-cli borehole muskat.json set bh1 --x 0 --y 0 --head 4 --water 0
```

The column is 1.62 m wide and 4 m high. The borehole puts the ground surface at 4 m.

The soil is the reference deck's, value for value. The flow uses the intrinsic permeability
(`PERMEABILITY_XX`, m²), the viscosity, the water density and the retention law. Kratos'
flow element also checks that the other values are there.

```powershell
kratos-cli material muskat.json add sand --name Sand --color "#c4a86a" --law GeoLinearElasticPlaneStrain2DLaw GEO_DRAINAGE_TYPE=FULLY_COUPLED YOUNG_MODULUS=1e4 POISSON_RATIO=0.4 DENSITY_SOLID=2290 DENSITY_WATER=1019.37 POROSITY=0.3333 BULK_MODULUS_SOLID=6.7e19 BULK_MODULUS_FLUID=1e20 PERMEABILITY_XX=6.9444e-13 PERMEABILITY_YY=6.9444e-13 PERMEABILITY_XY=0 DYNAMIC_VISCOSITY=1e-3 BIOT_COEFFICIENT=1 RETENTION_LAW=SaturatedLaw SATURATED_SATURATION=0.403
kratos-cli layer muskat.json add soil --name Soil --material sand --bottom 0
```

### The water

The left face is held at a water level of 3.0 m and the right face at 1.6 m:

```text
PS> kratos-cli boundary muskat.json add left_head --name "Left head" --face left --water-pressure Hydrostatic --reference-coordinate 3 --pressure-tension-cut-off 1e5
added left_head  Left head  water pressure on the left face; hydrostatic about 3 m, cut-off 100000, fixed; wrote muskat.json

PS> kratos-cli boundary muskat.json add right_head --name "Right head" --face right --water-pressure Hydrostatic --reference-coordinate 1.6 --pressure-tension-cut-off 1e5
added right_head  Right head  water pressure on the right face; hydrostatic about 1.6 m, cut-off 100000, fixed; wrote muskat.json
```

`--pressure-tension-cut-off 1e5` lets the suction above each level grow to 100 kPa. The
top and the bottom have no water pressure condition, so no water flows through them.

### The calculation

One phase, of the type Groundwater flow, and a mesh of quadratic triangles of 0.4 m:

```text
PS> kratos-cli phases muskat.json add flow --name Flow --calculation flow
added phase flow (Flow) after nothing: it is the first; wrote muskat.json

PS> kratos-cli set muskat.json mesh.element_size 0.4
PS> kratos-cli set muskat.json mesh.order 2
```

A new project has the standard supports. A groundwater flow calculation calculates the
water pressure only, so it leaves them out, and the list says so:

```text
PS> kratos-cli boundary muskat.json list
fixed_bottom  Fixed bottom  displacement on the bottom face; fixed in x y z
roller_left  Roller left  displacement on the left face; fixed in x
roller_right  Roller right  displacement on the right face; fixed in x
left_head  Left head  water pressure on the left face; hydrostatic about 3 m, cut-off 100000, fixed
right_head  Right head  water pressure on the right face; hydrostatic about 1.6 m, cut-off 100000, fixed
The front and back supports are kept for the solid model; the 2D section holds z by itself.
A groundwater flow calculation leaves the supports out: it solves the water pressure alone.
```

### Run it

```text
PS> kratos-cli calculate muskat.json
run Semi_Muskat_2026-10-24_01-22 finished in 0.3 s: 3 files in ...\Semi_Muskat_2026-10-24_01-22

PS> kratos-cli results field 1 pw
Pore pressure (Pa), stage 1 (Flow): -30000 to 24000 over 263 nodes

PS> kratos-cli results field 1 fluxx
q_x (m/s), stage 1 (Flow): 6.00e-6 to 6.00e-6 over 263 nodes
```

These are the exact values. The head falls linearly from 3.0 m on the left to 1.6 m on
the right, so the water pressure is 1e4 (y - h(x)) Pa: -30 kPa at the bottom left and
24 kPa (suction) at the top right. The flux is the same everywhere:
q = K × 1.4 / 1.62 = 6.00e-6 m/s, with the hydraulic conductivity K = 6.94e-6 m/s.

## Case B: a Van Genuchten soil

Start from case A, in a copy:

```powershell
Copy-Item muskat.json muskat_vg.json
```

Give the soil a Van Genuchten retention law. Above the phreatic line, its saturation and
its permeability then fall with the suction:

```powershell
kratos-cli material muskat_vg.json set sand RETENTION_LAW=VanGenuchtenLaw RESIDUAL_SATURATION=0.025 VAN_GENUCHTEN_AIR_ENTRY_PRESSURE=2611 VAN_GENUCHTEN_GN=1.377 VAN_GENUCHTEN_GL=1.25 MINIMUM_RELATIVE_PERMEABILITY=1e-5
kratos-cli boundary muskat_vg.json set right_head --reference-coordinate 1.62
```

The flow is now nonlinear, and Kratos solves it with Newton-Raphson iterations. They start
from a phreatic line. `--initial` gives start values only, which the calculation then
changes:

```text
PS> kratos-cli boundary muskat_vg.json add start --name "Initial phreatic line" --domain --water-pressure Phreatic_Multi_Line --phreatic-line -0.25 3.22 0.05 3.22 1.6 0.48 1.7 0.48 --initial
added start  Initial phreatic line  water pressure on the whole soil; phreatic line (-0.25, 3.22) -> (0.05, 3.22) -> (1.6, 0.48) -> (1.7, 0.48), initial; wrote muskat_vg.json
```

The reference deck allows 100 iterations, with a relative tolerance of 1e-3:

```powershell
kratos-cli phases muskat_vg.json set flow --max-iterations 100 --tolerance 1e-3
kratos-cli set muskat_vg.json mesh.element_size 0.1
```

> [!NOTE]
> With this soil, the iterations can fall into a cycle and stop without converging on some
> meshes: 0.2 m and 0.15 m do, 0.4 m and 0.1 m do not. If a run stops with "The maximum
> number of cycles is reached without convergence", change the element size.

```text
PS> kratos-cli calculate muskat_vg.json
run Semi_Muskat_2026-10-24_01-22_2 finished in 0.7 s: 3 files in ...\Semi_Muskat_2026-10-24_01-22_2

PS> kratos-cli results field 1 effective_saturation
Effective saturation (-), stage 1 (Flow): 0.4309 to 1.02 over 3207 nodes
```

The soil is saturated below the phreatic line and less so above it. Kratos calculates the
saturation at the Gauss points and extrapolates it to the nodes, so it can show a little
above 1. At the nodes Kratos' own test checks, this model gives Kratos' values to within
about 15 Pa of water pressure and 0.02 of saturation.

## Case C: a seepage face

Start from case B, in a copy:

```powershell
Copy-Item muskat_vg.json muskat_seepage.json
kratos-cli boundary muskat_seepage.json remove right_head
kratos-cli boundary muskat_seepage.json remove start
```

The right face now has two parts. Below 0.48 m the tail water holds it. Above, the
water may leave the soil: a seepage face. Both are lines drawn along the face:

```text
PS> kratos-cli boundary muskat_seepage.json add tail_water --name "Tail water" --line 1.62 0 1.62 0.48 --water-pressure Hydrostatic --reference-coordinate 0.48 --pressure-tension-cut-off 1e5
added tail_water  Tail water  water pressure on line (1.62, 0) -> (1.62, 0.48); hydrostatic about 0.48 m, cut-off 100000, fixed; wrote muskat_seepage.json

PS> kratos-cli boundary muskat_seepage.json add seepage_face --name "Seepage face" --seepage --line 1.62 0.48 1.62 4
added seepage_face  Seepage face  seepage on line (1.62, 0.48) -> (1.62, 4); water may leave the soil here; wrote muskat_seepage.json
```

A seepage face is on the soil's outer boundary: on a face (`--face`), or on a line along
it. The export refuses a seepage line through the soil.

The calculation starts from a horizontal water level at 3.0 m, as Kratos' seepage tests do:

```powershell
kratos-cli boundary muskat_seepage.json add start --name "Start values" --domain --water-pressure Hydrostatic --reference-coordinate 3 --pressure-tension-cut-off 1e5 --initial
kratos-cli phases muskat_seepage.json set flow --tolerance 1e-4
```

Kratos' seepage strategy decides, node by node, where the face is open. It changes one
node per iteration, so the face gets a fine mesh, and the phase keeps its 100 iterations.
The mesh is linear triangles of 0.4 m, refined to 0.04 m along the right face:

```powershell
kratos-cli set muskat_seepage.json mesh.element_size 0.4
kratos-cli set muskat_seepage.json mesh.order 1
kratos-cli add muskat_seepage.json mesh.refinements '{"kind": "box", "size": 0.04, "thickness": 0.5, "x_min": 1.5, "x_max": 1.62, "y_min": 0, "y_max": 4, "z_min": 0, "z_max": 1}'
```

The face then has 89 nodes, of which about 35 open, one per iteration. If a phase allows
fewer iterations than its seepage faces have nodes, `export` and `calculate` warn that it
may stop too soon.

```text
PS> kratos-cli calculate muskat_seepage.json
run Semi_Muskat_2026-10-24_01-22_3 finished in 0.6 s: 3 files in ...\Semi_Muskat_2026-10-24_01-22_3

PS> kratos-cli results field 1 flow_rate
Nodal water flow rate (m³/s/m), stage 1 (Flow): -3.67e-6 to 8.63e-7 over 669 nodes
```

`flow_rate` is the water each node takes in (negative) or lets out (positive), per metre of
the section. The face is open, at zero water pressure, from the tail water up to an exit
point at about 1.85 m, and closed above it. The water that comes in on the left,
1.893e-5 m³/s per metre, leaves on the right. This is within 1 % of the discharge of Dupuit
and Charny, K (3.0² - 0.48²) / (2 × 1.62) = 1.88e-5 m³/s per metre. The unsaturated soil
above the phreatic line carries a little water too.

## In the GUI

Open any of the three files with **File > Open project…** and click **Calculate**. The
seepage face is in **Model conditions > Boundary conditions** in the Model explorer, with a
line and arrows out of the soil when its eye is on. To make one in the GUI:

- In the **Boundary conditions** window, choose **Seepage face** in the water pressure
  column of a face.
- In **Create boundary condition**, choose the condition **Seepage face**, on a face or a
  line.
- In Flow conditions mode, open the rail's water pressure tool, choose **Seepage line**
  and draw the line.
