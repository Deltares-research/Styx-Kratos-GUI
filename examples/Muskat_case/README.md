# Semi-Muskat column, groundwater flow

A steady-state groundwater flow through a column of soil, between two faces held at
different water levels. The two models are Kratos' GeoMechanicsApplication tests
`tests/Muskat/saturated_hydrostatic` and `tests/Muskat/van_genuchten_hydrostatic`, with
the same soil, heads and solver settings.

| File | What it is |
|---|---|
| `muskat_saturated.json` | Case A, a saturated soil: the project file, as the GUI's **Save** and `kratos-cli new` write it |
| `muskat_saturated.py` | Case A as a model script |
| `muskat_van_genuchten.json` | Case B, a Van Genuchten soil: the project file |
| `muskat_van_genuchten.py` | Case B as a model script |

## The models

Both models have:

- **Column**: 1.62 m wide and 4 m high, one soil with an intrinsic permeability of
  6.9444e-13 m² (a saturated hydraulic conductivity K of 6.94e-6 m/s).
- **Water**: the left face is held at a water level of 3.0 m (a fixed Hydrostatic water
  pressure condition). The top and the bottom have no condition, so no water flows
  through them.
- **Supports**: none. A groundwater flow calculation solves the water pressure only.
- **Phases**: one phase, of the type **Groundwater flow**.

| | Case A, saturated | Case B, Van Genuchten |
|---|---|---|
| Retention law | `SaturatedLaw` | `VanGenuchtenLaw` |
| Right face level | 1.6 m | 1.62 m |
| Start values | none | a phreatic line from (−0.25, 3.22) to (1.7, 0.48), not fixed |
| Solver | one linear solve | Newton-Raphson, at most 100 iterations, tolerance 1e-3 |
| Mesh | quadratic, 0.4 m, 0.0625 m along the right face | quadratic, 0.1 m |

## Case A: the exact answer

The head falls linearly from the left face to the right face:
h(x) = 3.0 - 1.4 x / 1.62 m. So:

- The water pressure is 1e4 (y - h(x)) Pa (Kratos' sign: suction is positive). It goes from
  -30 kPa at the bottom left corner to 24 kPa at the top right corner.
- The flux is horizontal and the same everywhere: q = K × 1.4 / 1.62 = 6.00e-6 m/s.

The mesh holds a linear head exactly, so a run gives these values to within the
precision of the result files.

## Case B: Kratos' values

Above the phreatic line the soil is unsaturated. Its saturation and its permeability fall
with the suction, so the flow is nonlinear and has no exact answer. Kratos' own test
checks the water pressure, the saturation and the flux at six nodes. At those points
this model gives Kratos' values to within about 15 Pa of water pressure and 0.02 of
saturation.

> [!NOTE]
> With this soil, the Newton-Raphson iterations can fall into a cycle and stop without
> converging on some meshes: 0.2 m and 0.15 m do, 0.4 m and 0.1 m do not. If a run of
> case B stops with "The maximum number of cycles is reached without convergence", change
> the element size.

The effective saturation that the results show can be a little above 1 (up to 1.02). Kratos
calculates it at the Gauss points and extrapolates it to the nodes.

## In the GUI

1. Open `muskat_saturated.json` or `muskat_van_genuchten.json` with
   **File > Open project…**, or type `run examples/Muskat_case/muskat_saturated.py` in the
   command box.
2. Click **Calculate**.
3. In **Results**, show **Pore pressure**, **Hydraulic head**, **Effective saturation** or
   **q_x**.

## From the command line

```bash
kratos-cli.bat check muskat_saturated.json        # Windows; ./kratos-cli.sh on Linux, macOS, Git Bash
kratos-cli.bat phases muskat_saturated.json
kratos-cli.bat calculate muskat_saturated.json
kratos-cli.bat results field 1 pw
kratos-cli.bat results field 1 fluxx
```

The model scripts write the deck and run it:

```bash
python muskat_saturated.py --out deck/            # write the Kratos deck
python muskat_van_genuchten.py --calculate        # write the deck, run it, print the results
```

`python` is the environment `kratos-cli` runs in: `..\..\.venv-windows\Scripts\python.exe`
on Windows, `../../.venv-linux/bin/python` on Linux.

The commands are all in [docs/CLI.md](../../docs/CLI.md).
