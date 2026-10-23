"""A 2D soil block with one embedded sheet pile and a line load on its surface.

The model of docs/cli_tutorials/README.md: a 20 m x 10 m block, a sheet pile
in the middle from the surface down to y = 3, and a line load on the surface to the
right of it, meshed at 1 m with linear triangles. simple_dike.json beside it is the same
model, as the tutorial's commands build it.

    python simple_dike.py                  write the deck into this folder
    python simple_dike.py --calculate      ... run it, and print a summary of the results
    python simple_dike.py --gui            open the GUI on the runs in this folder
    python simple_dike.py --out DIR        use DIR instead of this folder

Each run is made in a folder of its own beside the deck, named after the deck and the
time it started (`simple_dike_<date>_<time>/`): a copy of the deck, Kratos' log,
the GiD result files (`*.post.res`, `*.post.msh`) and the sheet pile's curves
(`*_output_wall.json`). The deck itself stays as it was written. To read a run further:

    kratos-cli results runs --runs-dir .
    kratos-cli results field 1 uy --runs-dir .
    kratos-cli results profile 1 wall M --runs-dir .

`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, ...). The
file runs from anywhere: in the repository, or copied into a folder of your own.

SI units (N, m), dry, plane strain. Three stages: K0 on the soil alone, then the sheet
pile is installed, then the load is applied. The block stands on a fixed bottom with
rollers on its sides; it is dry, so it has no water pressure condition (its soil keeps
the water pressure it starts with, zero).
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
    sys.exit("simple_dike.py: no checkout found; run it with the Python kratos-cli uses")


ROOT = checkout()
"""`python simple_dike.py` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model.schemas import (AnchorRows, Beam, BeamSection, Borehole,  # noqa: E402
                                DisplacementCondition, Domain, Excavation, LineLoad,
                                Material, MeshSettings, Phase, Piles, Project, SoilLayer,
                                Struts, Wall, Wells)

# The soil block: (0, 0) to (20, 10).
DOMAIN_LEFT_X, DOMAIN_RIGHT_X = 0.0, 20.0
DOMAIN_BOTTOM_Y, DOMAIN_TOP_Y = 0.0, 10.0

# The sheet pile: (10, 10) to (10, 3).
SHEET_PILE_X = 10.0
SHEET_PILE_TOE_Y = 3.0

# The load: (10, 10) to (20, 10), right of the sheet pile.
LOAD_X0, LOAD_X1 = 10.0, 20.0
LOAD = -10_000.0
"""N/m, downward: 10 kN/m along the ground surface. The demo leaves the size to the
Kratos deck."""

ELEMENT_SIZE = 1.0
ELEMENT_ORDER = 1

# The supports: the bottom fixed in x and y, the sides on rollers held in x. The
# plane-strain section holds z by itself. No water pressure condition: the block is dry.
BOUNDARY_CONDITIONS = [
    DisplacementCondition(id="fixed_bottom", name="Fixed bottom", on="face", face="bottom",
                          fixed=(True, True, True)),
    DisplacementCondition(id="roller_left", name="Roller left", on="face", face="left",
                          fixed=(True, False, False)),
    DisplacementCondition(id="roller_right", name="Roller right", on="face", face="right",
                          fixed=(True, False, False)),
]


def project() -> Project:
    borehole = "bh1"
    soil = Material(id="m_soil", name="soil", color="#c4a86a",
                    constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
                    variables={
                        "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
                        "YOUNG_MODULUS": 2.0e7,
                        "POISSON_RATIO": 0.3,
                        "DENSITY_SOLID": 18_000.0 / 9.81,    # unit weight over g: kg/m3
                        "DENSITY_WATER": 10_000.0 / 9.81,
                        "POROSITY": 0.0,
                        "BULK_MODULUS_SOLID": 1.0e10,
                        "BULK_MODULUS_FLUID": 2.2e9,
                        "DYNAMIC_VISCOSITY": 1.0e-3,
                        "PERMEABILITY_XX": 1.0e-5,
                        "PERMEABILITY_YY": 1.0e-5,
                        "PERMEABILITY_XY": 0.0,
                        "GEO_COHESION": 1_000.0,
                        "GEO_FRICTION_ANGLE": 30.0,
                        "K0_NC": 0.5,
                    })

    # A steel sheet pile, per metre of wall.
    sheet_pile = BeamSection(id="sheet_pile", name="Sheet pile", variables={
        "YOUNG_MODULUS": 2.1e11, "POISSON_RATIO": 0.0, "DENSITY": 7_850.0,
        "CROSS_AREA": 0.015, "I33": 3.0e-4, "AREA_EFFECTIVE_Y": 0.0075})

    return Project(
        name="simple_dike",
        layered_soil=True,
        dimension=2,
        domain=Domain(x0=DOMAIN_LEFT_X, x1=DOMAIN_RIGHT_X, z0=0.0, z1=10.0,
                      y_top=DOMAIN_TOP_Y, y_bottom=DOMAIN_BOTTOM_Y),
        # Dry: the phreatic level is the bottom of the block, and there is no water table.
        boreholes=[Borehole(id=borehole, name="BH1", x=DOMAIN_LEFT_X, y=0.0,
                            head=DOMAIN_TOP_Y, water=DOMAIN_BOTTOM_Y)],
        materials=[soil],
        layers=[SoilLayer(id="soil", name="soil", mat=soil.id,
                          tops={borehole: DOMAIN_TOP_Y}, bots={borehole: DOMAIN_BOTTOM_Y})],

        beam_sections=[sheet_pile],
        beams=[Beam(id="sheetpile_1", name="sheetpile_1", section=sheet_pile.id,
                    points=[(SHEET_PILE_X, DOMAIN_TOP_Y), (SHEET_PILE_X, SHEET_PILE_TOE_Y)])],
        loads=[LineLoad(id="surcharge", name="Load", x0=LOAD_X0, x1=LOAD_X1,
                        y=DOMAIN_TOP_Y, components=(0.0, LOAD))],
        boundary_conditions=BOUNDARY_CONDITIONS,

        mesh=MeshSettings(element_size=ELEMENT_SIZE, order=ELEMENT_ORDER),

        phases=[
            # The ground alone, its stresses set by K0.
            Phase(id="initial", name="Initial stage", calculation="K0 procedure",
                  deactivate=["sheetpile_1", "surcharge"]),
            # Displacements reset, so what follows is measured from the ground it went into.
            Phase(id="sheet_pile", name="Sheet pile", parent="initial",
                  activate=["sheetpile_1"], reset_displacements=True,
                  max_iterations=150, tolerated_error=1e-3),
            Phase(id="loading", name="Load", parent="sheet_pile",
                  activate=["surcharge"], max_iterations=150, tolerated_error=1e-3),
        ],

        # Required by the schema. A layered model with one excavation level cuts no
        # pit and builds none of the 3D demo structures, so none of this is in the deck.
        excavation=Excavation(x0=0.0, x1=1.0, z0=0.0, z1=1.0, levels=[DOMAIN_TOP_Y - 1.0]),
        wall=Wall(thickness=0.5, top_y=DOMAIN_TOP_Y, toe_y=DOMAIN_TOP_Y - 1.0),
        struts=Struts(xs=[], y=DOMAIN_TOP_Y, radius=0.1),
        anchor_rows=AnchorRows(xs=[], head_y=DOMAIN_TOP_Y, length=1.0, inclination_deg=45.0,
                               radius=0.1),
        piles=Piles(xs=[], zs=[], radius=0.1, length=1.0, top_y=DOMAIN_TOP_Y),
        wells=Wells(positions=[], radius=0.1, top_y=DOMAIN_TOP_Y, length=1.0),
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
            # Run 1 is the newest: the one just made. A field is read at the last stage.
            for command in (["show", "1"], ["field", "1", "uy"], ["field", "1", "ux"],
                            ["profile", "1", "wall", "M"]):
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
