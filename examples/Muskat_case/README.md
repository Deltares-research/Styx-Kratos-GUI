# Semi-Muskat column, groundwater flow

A steady-state groundwater flow through a column of saturated soil, between two faces held
at different water levels. The model is Kratos' GeoMechanicsApplication test
`tests/Muskat/saturated_hydrostatic`, with the same soil, heads and solver.

| File | What it is |
|---|---|
| `muskat_saturated.json` | The project file, as the GUI's **Save** and `kratos-cli new` write it |
| `muskat_saturated.py` | The same model as a model script |

## The model

- **Soil**: a column 1.62 m wide and 4 m high, one saturated soil (`SaturatedLaw`), with an
  intrinsic permeability of 6.9444e-13 m² (a hydraulic conductivity K of 6.94e-6 m/s).
- **Water**: the left face is held at a water level of 3.0 m and the right face at 1.6 m
  (two fixed Hydrostatic water pressure conditions). The top and the bottom have no
  condition, so no water flows through them.
- **Supports**: none. A groundwater flow calculation solves the water pressure only.
- **Mesh**: quadratic triangles of 0.4 m, refined to 0.0625 m along the right face.
- **Phases**: one phase, of the type **Groundwater flow**.

## The exact answer

The head falls linearly from the left face to the right face:
h(x) = 3.0 - 1.4 x / 1.62 m. So:

- The water pressure is 1e4 (y - h(x)) Pa (Kratos' sign: suction is positive). It goes from
  -30 kPa at the bottom left corner to 24 kPa at the top right corner.
- The flux is horizontal and the same everywhere: q = K × 1.4 / 1.62 = 6.00e-6 m/s.

The mesh holds a linear head exactly, so a run gives these values to within the
precision of the result files.

## In the GUI

1. Open `muskat_saturated.json` with **File > Open project…**, or type
   `run examples/Muskat_case/muskat_saturated.py` in the command box.
2. Click **Calculate**.
3. In **Results**, show **Pore pressure**, **Hydraulic head** or **q_x**.

## From the command line

```bash
kratos-cli.bat check muskat_saturated.json        # Windows; ./kratos-cli.sh on Linux, macOS, Git Bash
kratos-cli.bat phases muskat_saturated.json
kratos-cli.bat calculate muskat_saturated.json
kratos-cli.bat results field 1 pw
kratos-cli.bat results field 1 fluxx
```

The model script writes the deck and runs it:

```bash
python muskat_saturated.py --out deck/            # write the Kratos deck
python muskat_saturated.py --calculate            # write the deck, run it, print the results
```

`python` is the environment `kratos-cli` runs in: `..\..\.venv-windows\Scripts\python.exe`
on Windows, `../../.venv-linux/bin/python` on Linux.

The commands are all in [docs/CLI.md](../../docs/CLI.md).
