"""A levee on a clay cover over a sand aquifer: a steady-state groundwater flow from the
river on the left to the polder on the right, out of a seepage face on the inner slope
and the polder surface.

A 90 m wide section, 22 m deep: a sand aquifer from y = -22 to -2, a clay cover from -2
to 0, and on it a clay levee with a core and an outer layer, its crest 4 m wide at
y = 6. The river stands at 5.0 m on the outer slope, the foreland and the left side;
the right side is held at -0.5 m, the polder level. The inner slope and the polder
surface are a seepage face; the crest and the bottom are closed. One "Groundwater flow"
stage.
levee_seepage.json beside it is the same model, as the GUI saves it.

    python levee_seepage.py               write the deck into this folder
    python levee_seepage.py --calculate   ... run it, and print a summary of the results
    python levee_seepage.py --gui         open the GUI on the runs in this folder
    python levee_seepage.py --out DIR     use DIR instead of this folder

Each run is made in a folder of its own beside the deck, named after the deck and the
time it started. To read a run further:

    kratos-cli results runs --runs-dir .
    kratos-cli results field 1 pw --runs-dir .
    kratos-cli results field 1 flow_rate --runs-dir .

`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, ...). The
file runs from anywhere: in the repository, or copied into a folder of your own.

SI units (N, m, s), plane strain. The four soil bodies share one set of flow properties:
a saturated hydraulic conductivity of 1 m/day, isotropic, and a Van Genuchten retention
curve (ga = 3.83 1/m, gn = 1.3774, gl = 1.25, residual saturation 0.062).
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
    sys.exit("levee_seepage.py: no checkout found; run it with the Python kratos-cli uses")


ROOT = checkout()
"""`python levee_seepage.py` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import scripting  # noqa: E402
from core.model.schemas import (CustomPart, Domain, Material,  # noqa: E402
                                MeshSettings, Project, SeepageCondition, SoilLayer, Stage,
                                WaterPressureCondition)

# The section: x from -36 to 54, the soil from y = -22 up to the ground surface at 0 and
# the levee's crest at 6. The z extent is a new project's (`kratos-cli new`), -10 to 10,
# so the plane-strain section is cut through its middle, at z = 0.
LEFT_X, RIGHT_X = -36.0, 54.0
BOTTOM_Y, GROUND_Y, CREST_Y = -22.0, 0.0, 6.0
Z0, Z1 = -10.0, 10.0

# The aquifer and the cover are layers across the whole section.
AQUIFER_TOP_Y = -2.0

# The levee, drawn on the cover. The core reaches 0.5 m into the cover under the crest;
# a drawn part takes the place of the layer it overlaps.
CORE = [(-14.0, 0.0), (0.0, 4.5), (4.0, 4.5), (18.0, 0.0), (4.0, -0.5), (0.0, -0.5)]
OUTER_LAYER = [(-18.0, 0.0), (0.0, CREST_Y), (4.0, CREST_Y), (22.0, 0.0), (18.0, 0.0),
               (4.0, 4.5), (0.0, 4.5), (-14.0, 0.0)]

# The heads, m: the river on the left, the polder on the right.
RIVER_LEVEL, POLDER_LEVEL = 5.0, -0.5
CUT_OFF = 1.0e5
"""Pa: the largest suction a fixed head may give. The river head holds the outer slope
above the river level too, up to the crest, where it is 10 kPa of suction."""
START_PHREATIC_LINE = [(LEFT_X, RIVER_LEVEL), (-2.0, RIVER_LEVEL),
                       (15.0, POLDER_LEVEL), (RIGHT_X, POLDER_LEVEL)]
"""The phreatic line the calculation starts from, m: the river level up to x = -2, just
before the crest, then dropping through the levee to the polder level at x = 15. It is
closer to the solution than one level everywhere."""


# The flow properties, SI. A conductivity K of 1 m/day is an intrinsic permeability of
# K mu / (rho_w g), with the water's unit weight of 10 kN/m3.
WATER_UNIT_WEIGHT = 10_000.0          # N/m3
VISCOSITY = 1.0e-3                    # Pa s
CONDUCTIVITY = 1.0 / 86_400.0         # m/s: 1 m/day
PERMEABILITY = CONDUCTIVITY * VISCOSITY / WATER_UNIT_WEIGHT
VAN_GENUCHTEN_GA = 3.83               # 1/m

# Linear triangles of 1 m. The seepage strategy opens or closes one node of the face per
# iteration, and the face (the inner slope and the polder) has about 55 nodes at this
# size: the iterations leave room for all of them.
ELEMENT_SIZE = 1.0
ELEMENT_ORDER = 1
MAX_ITERATIONS = 300
TOLERANCE = 1e-4

BOUNDARY_CONDITIONS = [
    # The river: the left side, the foreland and the outer slope up to the crest.
    WaterPressureCondition(id="river_head", name="River head", on="line",
                           points=[(LEFT_X, BOTTOM_Y), (LEFT_X, GROUND_Y),
                                   (-18.0, GROUND_Y), (0.0, CREST_Y)],
                           fluid_pressure_type="Hydrostatic", is_fixed=True,
                           reference_coordinate=RIVER_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
    # The polder: the right side.
    WaterPressureCondition(id="polder_head", name="Polder head", on="line",
                           points=[(RIGHT_X, GROUND_Y), (RIGHT_X, BOTTOM_Y)],
                           fluid_pressure_type="Hydrostatic", is_fixed=True,
                           reference_coordinate=POLDER_LEVEL,
                           pressure_tension_cut_off=CUT_OFF),
    # The water may leave through the inner slope and the polder surface, from the
    # crest's inner corner on.
    SeepageCondition(id="seepage_face", name="Seepage face", on="line",
                     points=[(4.0, CREST_Y), (22.0, GROUND_Y), (RIGHT_X, GROUND_Y)]),
    # Start values: hydrostatic below a phreatic line that drops through the levee from
    # the river level to the polder level (START_PHREATIC_LINE). The crest,
    # from (0, 6) to (4, 6), and the bottom have no condition, so no water flows
    # through them.
    WaterPressureCondition(id="start", name="Start values", on="domain",
                           fluid_pressure_type="Phreatic_Multi_Line", is_fixed=False,
                           x_coordinates=[x for x, _ in START_PHREATIC_LINE],
                           y_coordinates=[y for _, y in START_PHREATIC_LINE],
                           pressure_tension_cut_off=CUT_OFF),
]


def soil(id_: str, name: str, color: str) -> Material:
    """A soil for a groundwater flow calculation. Only the permeability, the viscosity,
    the water density and the retention law change the flow; the rest is what Kratos'
    flow element checks it has."""
    return Material(id=id_, name=name, color=color,
                    constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables={
                        "GEO_DRAINAGE_TYPE": "FULLY_COUPLED",
                        "YOUNG_MODULUS": 1.0e4,
                        "POISSON_RATIO": 0.3,
                        "DENSITY_SOLID": 2.65e3,
                        "DENSITY_WATER": WATER_UNIT_WEIGHT / 9.81,
                        "POROSITY": 1.0 / 3.0,
                        "BULK_MODULUS_SOLID": 1.0e20,
                        "BULK_MODULUS_FLUID": 1.0e20,
                        "PERMEABILITY_XX": PERMEABILITY,
                        "PERMEABILITY_YY": PERMEABILITY,
                        "PERMEABILITY_XY": 0.0,
                        "DYNAMIC_VISCOSITY": VISCOSITY,
                        "BIOT_COEFFICIENT": 1.0,
                        "RETENTION_LAW": "VanGenuchtenLaw",
                        "SATURATED_SATURATION": 1.0,
                        "RESIDUAL_SATURATION": 0.0620347394540943,
                        "VAN_GENUCHTEN_AIR_ENTRY_PRESSURE":
                            WATER_UNIT_WEIGHT / VAN_GENUCHTEN_GA,   # Pa
                        "VAN_GENUCHTEN_GN": 1.3774,
                        "VAN_GENUCHTEN_GL": 1.25,
                        "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-4,
                        # Not read by the linear elastic law; the default sand's values,
                        # kept so the model is the CLI tutorial's to the last digit.
                        "GEO_COHESION": 0.0,
                        "GEO_FRICTION_ANGLE": 30.0,
                    })


def drawn(key: str, label: str, material: str,
          corners: list[tuple[float, float]]) -> CustomPart:
    """A polygon drawn in the section, extruded over the model's depth as the GUI does."""
    return CustomPart(
        key=key, label=label, source="gui", mat=material,
        recipe={"kind": "polygon_extrude", "label": label, "material": material,
                "vertices": [[x, y, Z0] for x, y in corners],
                "extrusion": [0.0, 0.0, Z1 - Z0]})


def project() -> Project:
    sand = soil("m_sand", "Sand", "#e6c86e")
    clay = soil("m_clay", "Clay", "#8fa37a")

    return scripting.with_solids(Project(
        name="levee_seepage",
        layered_soil=True,
        dimension=2,
        domain=Domain(x0=LEFT_X, x1=RIGHT_X, z0=Z0, z1=Z1,
                      y_top=CREST_Y, y_bottom=BOTTOM_Y),
        # No water table: the conditions are all the water the model has.
        materials=[sand, clay],
        layers=[SoilLayer(id="cover", name="Cover", mat=clay.id,
                          top=GROUND_Y, bottom=AQUIFER_TOP_Y),
                SoilLayer(id="aquifer", name="Aquifer", mat=sand.id,
                          top=AQUIFER_TOP_Y, bottom=BOTTOM_Y)],
        custom_parts=[drawn("levee_core", "Levee core", clay.id, CORE),
                      drawn("levee_outer", "Levee outer layer", clay.id, OUTER_LAYER)],
        boundary_conditions=BOUNDARY_CONDITIONS,

        mesh=MeshSettings(element_size=ELEMENT_SIZE, order=ELEMENT_ORDER),

        stages=[Stage(id="flow", name="Flow", calculation="Groundwater flow",
                      max_iterations=MAX_ITERATIONS, tolerated_error=TOLERANCE)],
    ))


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
