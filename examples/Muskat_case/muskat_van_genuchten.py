"""The semi-Muskat column, Van Genuchten soil: a steady-state groundwater flow between two
heads, with an unsaturated zone above the phreatic line.

Kratos' GeoMechanicsApplication test `tests/Muskat/van_genuchten_hydrostatic`, built as a
Styx model: a 1.62 m by 4 m column of a Van Genuchten soil, the water held at a level of
3.0 m on the left face and 1.62 m on the right, started from a phreatic line, and one
flow stage. muskat_van_genuchten.json beside it is the same model, as the
GUI saves it.

    python muskat_van_genuchten.py               write the deck into this folder
    python muskat_van_genuchten.py --calculate   ... run it, and print a summary of the results
    python muskat_van_genuchten.py --gui         open the GUI on the runs in this folder
    python muskat_van_genuchten.py --out DIR     use DIR instead of this folder

Each run is made in a folder of its own beside the deck, named after the deck and the
time it started. To read a run further:

    kratos-cli results runs --runs-dir .
    kratos-cli results field 1 pw --runs-dir .
    kratos-cli results field 1 effective_saturation --runs-dir .

`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, ...). The
file runs from anywhere: in the repository, or copied into a folder of your own.

SI units (N, m, s), plane strain. Above the phreatic line the soil is unsaturated: its
saturation and its permeability fall with the suction (Van Genuchten), so the flow is
nonlinear and Kratos solves it with Newton-Raphson iterations. There is no exact answer;
at the nodes Kratos' own test checks, this model gives Kratos' values to within about
15 Pa of water pressure and 0.02 of saturation.
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
    sys.exit("muskat_van_genuchten.py: no checkout found; run it with the Python kratos-cli "
             "uses")


ROOT = checkout()
"""`python muskat_van_genuchten.py` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model.schemas import (Fluid, Domain, Material,  # noqa: E402
                                MeshSettings, Project, SoilLayer, Stage,
                                WaterPressureCondition)

# The column: (0, 0) to (1.62, 4).
WIDTH, HEIGHT = 1.62, 4.0

# The water levels the two faces are held at, and the largest suction they give.
LEFT_LEVEL, RIGHT_LEVEL = 3.0, 1.62
CUT_OFF = 1.0e5
"""Pa: the pressure_tension_cut_off of the reference deck."""

# The phreatic line the calculation starts from, point by point: start values only,
# which the two fixed heads replace on the faces.
PHREATIC_X = [-0.25, 0.05, 1.6, 1.7]
PHREATIC_Y = [3.22, 3.22, 0.48, 0.48]

# Quadratic triangles of 0.1 m. With this soil, Newton-Raphson can fall into a cycle and
# stop without converging on some meshes (0.2 m and 0.15 m do); 0.1 m converges.
ELEMENT_SIZE = 0.1
ELEMENT_ORDER = 2

# The deck's Newton-Raphson settings: on the residual criterion, rather than on the water
# pressure a flow stage converges on unless it says otherwise, at most 100 iterations,
# relative tolerance 1e-3, absolute tolerance 1e-15.
CONVERGENCE_CRITERION = "residual_criterion"
MAX_ITERATIONS = 100
TOLERANCE = 1e-3
ABSOLUTE_TOLERANCE = 1e-15

# The two heads and the start values. No support: a groundwater flow calculation solves
# the water pressure alone, and a face with no water pressure condition (the top and the
# bottom) lets no water through.
BOUNDARY_CONDITIONS = [
    WaterPressureCondition(id="left_head", name="Left head", on="face", face="left",
                           fluid_pressure_type="Hydrostatic", is_fixed=True,
                           reference_coordinate=LEFT_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
    WaterPressureCondition(id="right_head", name="Right head", on="face", face="right",
                           fluid_pressure_type="Hydrostatic", is_fixed=True,
                           reference_coordinate=RIGHT_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
    WaterPressureCondition(id="initial_phreatic", name="Initial phreatic line", on="domain",
                           fluid_pressure_type="Phreatic_Multi_Line", is_fixed=False,
                           x_coordinates=PHREATIC_X, y_coordinates=PHREATIC_Y,
                           z_coordinates=[0.0] * len(PHREATIC_X)),
]


def project() -> Project:
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
                        "POROSITY": 0.3333,
                        "BULK_MODULUS_SOLID": 6.7e19,
                        "PERMEABILITY_XX": 6.9444e-13,   # m2, intrinsic
                        "PERMEABILITY_YY": 6.9444e-13,
                        "PERMEABILITY_XY": 0.0,
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
        # The reference deck's water: incompressible, so the flow is steady at once.
        fluid=Fluid(bulk_modulus=1.0e20),
        name="muskat_van_genuchten",
        layered_soil=True,
        dimension=2,
        domain=Domain(x0=0.0, x1=WIDTH, z0=0.0, z1=1.0, y_top=HEIGHT, y_bottom=0.0),
        # No water table: the two heads and the start values are all the water the model has.
        materials=[soil],
        layers=[SoilLayer(id="soil", name="soil", mat=soil.id,
                          top=HEIGHT, bottom=0.0)],
        boundary_conditions=BOUNDARY_CONDITIONS,

        mesh=MeshSettings(element_size=ELEMENT_SIZE, order=ELEMENT_ORDER),

        stages=[Stage(id="flow", name="Flow", calculation="flow",
                      convergence_criterion=CONVERGENCE_CRITERION,
                      max_iterations=MAX_ITERATIONS, tolerated_error=TOLERANCE,
                      absolute_tolerance=ABSOLUTE_TOLERANCE)],
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
                            ["field", "1", "effective_saturation"], ["field", "1", "flux"]):
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
