# Simple dike with `kratos-cli`

A 2D plane-strain model of a soil block with a sheet pile and a line load on its surface,
built and run from PowerShell. It is the shortest of the [CLI tutorials](README.md), and a
good first one.

| Part | What it is |
|---|---|
| **Soil** | a 20 m × 10 m block, from (0, 0) m to (20, 10) m; linear elastic, E = 20 MPa, ν = 0.3, unit weight 18 kN/m³, dry |
| **Sheet pile** | a steel beam at x = 10 m, from the ground surface (y = 10 m) down to y = 3 m; E = 210 GPa, A = 0.015 m²/m, I = 3·10⁻⁴ m⁴/m |
| **Load** | 10 kN/m downward on the ground surface, from x = 10 m to x = 20 m (a line load in the 2D section) |
| **Mesh** | 1 m linear triangles |
| **Stages** | 1 K0 on the soil alone → 2 the sheet pile is installed → 3 the load is applied |

There are three ways to work with it. Pick one:

| | Way | Start from | Good for |
|---|---|---|---|
| [1](1_build_from_scratch.md) | [Build it from scratch in the shell](1_build_from_scratch.md) | nothing | learning the commands, making your own model |
| [2](2_open_in_the_shell.md) | [Open the ready-made model in the shell](2_open_in_the_shell.md) | `simple_dike.py` | looking around the model and its results |
| [3](3_run_the_python_script.md) | [Run the Python script](3_run_the_python_script.md) | `simple_dike.py` | one command: write, run, summarise |

In the commands below, `<repo>` is the folder you cloned this repository into, such as
`C:\Users\you\Styx-Kratos-GUI`. The ready-made model is in
[`examples/simple_dike/`](../../examples/simple_dike/).

---

## What gets written

| File | What it is |
|---|---|
| `simple_dike.json` | the model (way 1 only; ways 2 and 3 read `simple_dike.py`) |
| `simple_dike.mdpa`, `ProjectParameters.json`, `MaterialParameters.json`, ... | the Kratos input files (the deck) |
| `simple_dike_<date>_<time>\` | one folder per run: a copy of the deck, `kratos.log`, the results (`*.post.res`, `*.post.msh`) and the sheet-pile curves (`*_output_wall.json`) |
| `uy.csv` | every `uy` value, if you asked for it with `--csv` |
