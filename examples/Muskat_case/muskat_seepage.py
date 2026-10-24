"""The Muskat problem: a steady-state groundwater flow through a dam of soil, out of a
seepage face above the tail water.

The STEM Muskat geometry (Deltares' FEA-Tools `GeometryGenerator`), built as a Styx
model: a 1.62 m by 4 m column of a Van Genuchten soil, the water held at a level of 3.0 m
on the left face, the tail water at 0.48 m on the right face, and above it a seepage
face where the water leaves the soil. One "Groundwater flow" stage.
muskat_seepage.json beside it is the same model, as the GUI saves it.

    python muskat_seepage.py               write the deck into this folder
    python muskat_seepage.py --calculate   ... run it, and print a summary of the results
    python muskat_seepage.py --gui         open the GUI on the runs in this folder
    python muskat_seepage.py --out DIR     use DIR instead of this folder

Each run is made in a folder of its own beside the deck, named after the deck and the
time it started. To read a run further:

    kratos-cli results runs --runs-dir .
    kratos-cli results field 1 pw --runs-dir .
    kratos-cli results field 1 flow_rate --runs-dir .

`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, ...). The
file runs from anywhere: in the repository, or copied into a folder of your own.

SI units (N, m, s), plane strain. Kratos' seepage strategy decides, node by node while it
iterates, where the seepage face is open: there the water pressure is zero and the water
flows out. The water leaves the face between the tail water and an exit point at about
1.85 m. The water that comes in on the left leaves on the right, and the discharge,
1.89e-5 m3/s per metre, is within 1 % of Dupuit and Charny's K (H1² - H2²) / 2L =
1.88e-5 (the unsaturated soil above the phreatic line carries a little water too).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
"""This file's folder, where the deck is written."""


def checkout() -> Path:
    """The checkout, where `core` is: a folder above this file while it is in the
    repository, or else the one the running Python environment is in (`.venv-windows`
    and the others sit in the checkout's root), for a copy in a folder of your own."""
    for folder in [*HERE.parents, Path(sys.prefix).resolve().parent]:
        if (folder / "core" / "model" / "schemas.py").is_file():
            return folder
    sys.exit("muskat_seepage.py: no checkout found; run it with the Python kratos-cli uses")


ROOT = checkout()
"""`python muskat_seepage.py` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model.schemas import (Borehole, BoxRefinement, Domain,  # noqa: E402
                                Material, MeshSettings, Project, SeepageCondition,
                                SoilLayer, Stage, WaterPressureCondition)

# The column: (0, 0) to (1.62, 4).
WIDTH, HEIGHT = 1.62, 4.0

# The upstream level on the left face, the tail water on the right face, and the largest
# suction they give.
LEFT_LEVEL, TAIL_LEVEL = 3.0, 0.48
CUT_OFF = 1.0e5
"""Pa: the pressure_tension_cut_off of the Kratos decks."""

# Linear triangles of 0.4 m, and 0.04 m along the right face, where the seepage face
# opens and closes node by node.
ELEMENT_SIZE = 0.4
ELEMENT_ORDER = 1
RIGHT_FACE_SIZE = 0.04

# The seepage strategy opens or closes one node of the face per iteration. The face has
# 89 nodes at this size, of which about 35 open, in as many iterations. The tolerance is
# that of Kratos' seepage tests.
MAX_ITERATIONS = 100
TOLERANCE = 1e-4

# The two heads, the seepage face and the start values. No support: a groundwater flow
# calculation solves the water pressure alone, and a face with no condition (the top and
# the bottom) lets no water through.
BOUNDARY_CONDITIONS = [
    WaterPressureCondition(id="left_head", name="Left head", on="face", face="left",
                           fluid_pressure_type="Hydrostatic", is_fixed=True,
                           reference_coordinate=LEFT_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
    WaterPressureCondition(id="tail_water", name="Tail water", on="line",
                           points=[(WIDTH, 0.0), (WIDTH, TAIL_LEVEL)],
                           fluid_pressure_type="Hydrostatic", is_fixed=True,
                           reference_coordinate=TAIL_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
    SeepageCondition(id="seepage_face", name="Seepage face", on="line",
                     points=[(WIDTH, TAIL_LEVEL), (WIDTH, HEIGHT)]),
    # Start values: hydrostatic about the upstream level, as Kratos' seepage tests start.
    WaterPressureCondition(id="start", name="Start values", on="domain",
                           fluid_pressure_type="Hydrostatic", is_fixed=False,
                           reference_coordinate=LEFT_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
]


def project() -> Project:
    borehole = "bh1"
    # The reference deck's material, value for value. Only the permeability, the
    # viscosity, the water density and the retention law change the flow; the rest is
    # what Kratos' flow element checks it has.
    soil = Material(id="m_soil", name="soil", color="#c4a86a",
                    constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables={
                        "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
                        "YOUNG_MODULUS": 1.0e4,
                        "POISSON_RATIO": 0.4,
                        "DENSITY_SOLID": 2.29e3,
                        "DENSITY_WATER": 1.01937e3,
                        "POROSITY": 0.3333,
                        "BULK_MODULUS_SOLID": 6.7e19,
                        "BULK_MODULUS_FLUID": 1.0e20,
                        "PERMEABILITY_XX": 6.9444e-13,   # m2, intrinsic
                        "PERMEABILITY_YY": 6.9444e-13,
                        "PERMEABILITY_XY": 0.0,
                        "DYNAMIC_VISCOSITY": 1.0e-3,
                        "BIOT_COEFFICIENT": 1.0,
                        "RETENTION_LAW": "VanGenuchtenLaw",
                        "SATURATED_SATURATION": 0.403,
                        "RESIDUAL_SATURATION": 0.025,
                        "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE": 2.611e3,   # Pa
                        "VAN_GENUCHTEN_GN": 1.377,
                        "VAN_GENUCHTEN_GL": 1.25,
                        "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-5,
                    })

    return Project(
        name="muskat_seepage",
        layered_soil=True,
        dimension=2,
        domain=Domain(x0=0.0, x1=WIDTH, z0=0.0, z1=1.0, y_top=HEIGHT, y_bottom=0.0),
        # No water table: the conditions are all the water the model has.
        boreholes=[Borehole(id=borehole, name="BH1", x=0.0, y=0.0, head=HEIGHT, water=0.0)],
        materials=[soil],
        layers=[SoilLayer(id="soil", name="soil", mat=soil.id,
                          tops={borehole: HEIGHT}, bots={borehole: 0.0})],
        boundary_conditions=BOUNDARY_CONDITIONS,

        mesh=MeshSettings(element_size=ELEMENT_SIZE, order=ELEMENT_ORDER, refinements=[
            BoxRefinement(kind="box", size=RIGHT_FACE_SIZE, thickness=0.5,
                          x_min=WIDTH - 0.12, x_max=WIDTH, y_min=0.0, y_max=HEIGHT,
                          z_min=0.0, z_max=1.0)]),

        stages=[Stage(id="flow", name="Flow", calculation="Groundwater flow",
                      max_iterations=MAX_ITERATIONS, tolerated_error=TOLERANCE)],
    )


def main(argv: list[str] | None = None) -> int:
    """Write the Kratos deck into this folder (or `--out DIR`); `--calculate` also runs it
    there, and `--gui` opens the GUI with that folder as its runs root."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, metavar="DIR", default=HERE,
                        help="write the deck and the runs into DIR (default: this file's folder)")
    parser.add_argument("--calculate", action="store_true",
                        help="also run the deck, and print a summary of the results")
    parser.add_argument("--gui", action="store_true",
                        help="open the GUI, whose Results mode lists the runs in DIR")
    args = parser.parse_args(argv)
    from cli.terminal.main import main as kratos_cli

    folder = str(args.out.resolve())
    code = kratos_cli(["export", __file__, "--out", folder])
    if code == 0 and args.calculate:
        code = kratos_cli(["run", folder, "--runs-dir", folder])
        if code == 0:
            # Run 1 is the newest: the one just made.
            for command in (["show", "1"], ["field", "1", "pw"],
                            ["field", "1", "flow_rate"], ["field", "1", "flux"]):
                print()
                kratos_cli(["results", *command, "--runs-dir", folder])
    if code == 0 and args.gui:
        code = gui(args.out)
    return code


def gui(runs: Path) -> int:
    """Start the GUI (as run.bat does) with `runs` as the folder its Results mode reads."""
    import os
    import subprocess

    print(f"\nopening the GUI on the runs in {runs}; in it, press Results and pick a run.\n"
          "Ctrl+C here stops it.")
    environment = os.environ | {"KRATOS_GUI_RUNS": str(runs.resolve())}
    try:
        return subprocess.call([sys.executable, "-m", "backend.launcher", "--open-browser"],
                               cwd=ROOT, env=environment)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
