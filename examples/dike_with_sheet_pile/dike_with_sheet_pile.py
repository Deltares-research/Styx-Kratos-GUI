"""A dike on a sand layer, reinforced with a sheet pile wall: a simplified Reevediep case.

A 70 m wide section, 17 m high: a sand layer from y = -12 to -4, split in two at x = 33,
and on it a clay body, split in eight parts. Parts 1, 2, 5, 6 and 7 are the clay itself;
parts 3, 4 and 8 are the clay cap, whose cohesion is 5 kPa instead of 2 kPa. A sheet
pile wall (AZ 36-700N) stands at x = 33, from the crest (y = 5) down to y = -8.5, with a
layer of line interface elements along each of its faces. The soil is drained
Mohr-Coulomb; the water pressure is prescribed, so only the displacements, and the wall's
rotations, are solved.

    python dike_with_sheet_pile.py               write the deck into this folder
    python dike_with_sheet_pile.py --calculate   ... run it, and print a summary
    python dike_with_sheet_pile.py --gui         open the GUI on the runs in this folder
    python dike_with_sheet_pile.py --out DIR     use DIR instead of this folder

Each run is made in a folder of its own beside the deck, named after the deck and the
time it started. To read a run further:

    kratos-cli results runs --runs-dir .
    kratos-cli results field 1 uy --runs-dir .
    kratos-cli results profile 1 wall M --runs-dir .

`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, ...). The
file runs from anywhere: in the repository, or copied into a folder of your own.

SI units (N, m), plane strain. 6-noded triangular U-Pw diff order elements
(`SmallStrainUPwDiffOrderElement2D6N`). Four stages:

1. The initial stress state by the K0 procedure. The wall and its interfaces are off;
   the cut they will be installed in is tied by master/slave constraints, which the
   export writes for a staged structure.
2. A plastic null stage, which maps inadmissible stresses back onto the yield contour.
3. The wall installation: the wall and its interfaces become active. The phreatic line
   jumps at the wall, the water being at y = 0 behind it.
4. The excavation of the two upper clay parts right of the wall (7 and 8) and of the
   interfaces along them. The reservoir rises to y = 4.5 (high water).

The model's fifth stage, a c-phi reduction that predicts failure, is not part of this
file: the project model has no such calculation type yet. The interface stiffnesses are
derived from the adjacent soil at export, as the project model does for any interface.
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
    sys.exit(
        "dike_with_sheet_pile.py: no checkout found; run it with the Python "
        "kratos-cli uses"
    )


ROOT = checkout()
"""`python dike_with_sheet_pile.py` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import scripting  # noqa: E402
from core.model.schemas import (
    Beam,
    BeamSection,
    CustomPart,  # noqa: E402
    DisplacementCondition,
    Domain,
    Interface,
    InterfaceSection,
    Material,
    MeshSettings,
    NormalLoad,
    Project,
    Stage,
    WaterPressureCondition,
)

# The section: x from 0 to 70, y from the bottom of the sand (-12) up to the crest (5).
# The z extent is a new project's (`kratos-cli new`), so the plane-strain section is cut
# through its middle, at z = 0.
LEFT_X, RIGHT_X = 0.0, 70.0
BOTTOM_Y, CREST_Y = -12.0, 5.0
Z0, Z1 = -10.0, 10.0

# The parts, each from its leftmost (top) vertex, counter-clockwise.
SAND_LEFT = [(0.0, -4.0), (0.0, -12.0), (33.0, -12.0), (33.0, -8.5), (33.0, -4.0)]
SAND_RIGHT = [(33.0, -4.0), (33.0, -8.5), (33.0, -12.0), (70.0, -12.0), (70.0, -4.0)]

# Left of the wall.
CLAY_1 = [
    (0.0, 3.0),
    (0.0, -4.0),
    (33.0, -4.0),
    (33.0, -0.286),
    (31.0, 0.0),
    (30.16, 4.2),
    (27.0, 4.2),
    (22.0, 3.0),
    (19.0, 3.0),
]
CLAY_2 = [(30.16, 4.2), (31.0, 0.0), (33.0, -0.286), (33.0, 2.296), (33.0, 4.2)]
CLAY_CAP_3 = [
    (19.0, 3.0),
    (22.0, 3.0),
    (27.0, 4.2),
    (30.16, 4.2),
    (30.0, 5.0),
    (27.0, 5.0),
]
CLAY_CAP_4 = [(30.0, 5.0), (30.16, 4.2), (33.0, 4.2), (33.0, 5.0)]

# Right of the wall.
CLAY_5 = [
    (33.0, -0.286),
    (33.0, -4.0),
    (70.0, -4.0),
    (70.0, 1.0),
    (43.0, 1.0),
    (38.0, -1.0),
]
CLAY_6 = [(33.0, 2.296), (33.0, -0.286), (38.0, -1.0), (43.0, 1.0), (41.0, 1.0)]
CLAY_7 = [(33.0, 4.2), (33.0, 2.296), (41.0, 1.0), (34.6, 4.2)]
CLAY_CAP_8 = [(33.0, 5.0), (33.0, 4.2), (34.6, 4.2)]

LEFT_PARTS = ["sand_left", "clay_1", "clay_2", "clay_cap_3", "clay_cap_4"]
RIGHT_PARTS = ["sand_right", "clay_5", "clay_6", "clay_7", "clay_cap_8"]
EXCAVATED_PARTS = ["clay_7", "clay_cap_8"]

# The sheet pile wall, from its top down.
WALL_X = 33.0
WALL = [
    (33.0, 5.0),
    (33.0, 4.2),
    (33.0, 2.296),
    (33.0, -0.286),
    (33.0, -4.0),
    (33.0, -8.5),
]
UPPER_CONTACT_START = (33.0, 2.296)
"""Where the wall's contact with the excavated parts (7 and 8) begins."""

# The water, m. The reservoir stands at 3.5 ("dagelijkse omstandigheden") or at 4.5
# ("hoogwater"); the line then falls through (42, 0), or, with the wall in place, to the
# wall, where it jumps to the level behind it, 0.
DAILY_LEVEL, HIGH_LEVEL = 3.5, 4.5
BEHIND_LEVEL = 0.0
PHREATIC_BEFORE_WALL = [(0.0, 3.5), (21.0, 3.5), (42.0, 0.0), (70.0, 0.0)]
PHREATIC_LEFT_DAILY = [(0.0, 3.5), (21.0, 3.5), (33.0, 1.5), (70.0, 1.5)]
PHREATIC_LEFT_HIGH = [(0.0, 4.5), (25.0, 4.5), (33.0, 2.382), (70.0, 2.382)]
RESERVOIR_DAILY = [(0.0, 3.0), (19.0, 3.0), (21.0, 3.5)]
RESERVOIR_HIGH = [(0.0, 3.0), (19.0, 3.0), (25.0, 4.5)]
"""The soil surface the reservoir presses on, from the left side to the waterline."""

G = 9.81
WATER_UNIT_WEIGHT = 10_000.0  # N/m3
POROSITY = 0.3333
DENSITY_WATER = WATER_UNIT_WEIGHT / G

ELEMENT_SIZE = 2.0
FINE_ELEMENT_SIZE = 0.5
"""The size in the parts where failure is expected (clay parts 2 and 4) and in the wall."""
ELEMENT_ORDER = 2
MAX_ITERATIONS = 150
TOLERANCE = 1e-3
EXCAVATION_ITERATIONS = 300
EXCAVATION_TOLERANCE = 1e-2
"""The excavation stage is close to failure: its residual falls slowly, so it gets more
iterations and a looser tolerance than the others."""

BOUNDARY_CONDITIONS = [
    DisplacementCondition(
        id="fixed_bottom",
        name="Fixed bottom",
        on="face",
        face="bottom",
        fixed=(True, True, True),
    ),
    DisplacementCondition(
        id="roller_left",
        name="Roller left",
        on="face",
        face="left",
        fixed=(True, False, False),
    ),
    DisplacementCondition(
        id="roller_right",
        name="Roller right",
        on="face",
        face="right",
        fixed=(True, False, False),
    ),
    # Stages 1 and 2: one phreatic line over the whole soil.
    WaterPressureCondition(
        id="water_before_wall",
        name="Water, no wall",
        on="domain",
        fluid_pressure_type="Phreatic_Multi_Line",
        is_fixed=True,
        x_coordinates=[x for x, _ in PHREATIC_BEFORE_WALL],
        y_coordinates=[y for _, y in PHREATIC_BEFORE_WALL],
    ),
]

# With the wall in place the water pressure jumps at it, which one phreatic line cannot
# do (its x increases). So the lines of the reservoir side cover the whole soil, running
# on level beyond the wall, and conditions on the parts right of the wall come after
# them: where two fix the same node the later wins, and they put the level behind the
# wall, 0, there.
WATER_LEFT_DAILY = WaterPressureCondition(
    id="water_daily",
    name="Water, daily, reservoir side",
    on="domain",
    fluid_pressure_type="Phreatic_Multi_Line",
    is_fixed=True,
    x_coordinates=[x for x, _ in PHREATIC_LEFT_DAILY],
    y_coordinates=[y for _, y in PHREATIC_LEFT_DAILY],
)
WATER_LEFT_HIGH = WaterPressureCondition(
    id="water_high",
    name="Water, high, reservoir side",
    on="domain",
    fluid_pressure_type="Phreatic_Multi_Line",
    is_fixed=True,
    x_coordinates=[x for x, _ in PHREATIC_LEFT_HIGH],
    y_coordinates=[y for _, y in PHREATIC_LEFT_HIGH],
)
WATER_RIGHT = [
    WaterPressureCondition(
        id=f"water_behind_{part}",
        name=f"Water, behind wall, {part}",
        on="part",
        part=part,
        fluid_pressure_type="Hydrostatic",
        is_fixed=True,
        reference_coordinate=BEHIND_LEVEL,
    )
    for part in RIGHT_PARTS
]
BOUNDARY_CONDITIONS += [WATER_LEFT_DAILY, WATER_LEFT_HIGH, *WATER_RIGHT]


def ids(records) -> list[str]:
    return [record.id for record in records]


def soil(
    id_: str,
    name: str,
    color: str,
    *,
    young: float,
    cohesion: float,
    friction_angle: float,
    unit_weight: float,
    k0: float,
) -> Material:
    """A drained Mohr-Coulomb soil whose saturated and unsaturated unit weights are the
    same. Kratos weighs a point at (1 - n) rho_s g + n S gamma_w; the solid density is
    what makes that the soil's unit weight when saturated."""
    solid_density = (unit_weight / G - POROSITY * DENSITY_WATER) / (1.0 - POROSITY)
    return Material(
        id=id_,
        name=name,
        color=color,
        constitutive_law="GeoMohrCoulombLawPlaneStrain",
        variables={
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": young,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": solid_density,
            "POROSITY": POROSITY,
            "BULK_MODULUS_SOLID": 1.0e12,
            "PERMEABILITY_XX": 1.0e-5,
            "PERMEABILITY_YY": 1.0e-5,
            "PERMEABILITY_XY": 0.0,
            "RETENTION_LAW": "SaturatedBelowPhreaticLevelLaw",
            "SATURATED_SATURATION": 1.0,
            "RESIDUAL_SATURATION": 1.0e-10,
            "MINIMUM_RELATIVE_PERMEABILITY": 1.0e-4,
            "GEO_COHESION": cohesion,
            "GEO_FRICTION_ANGLE": friction_angle,
            "GEO_DILATANCY_ANGLE": 0.0,
            "GEO_ENABLE_TENSION_CUT_OFF": False,
            "K0_NC": k0,
        },
    )


def drawn(
    key: str, label: str, material: str, corners: list[tuple[float, float]]
) -> CustomPart:
    """A polygon drawn in the section, extruded over the model's depth as the GUI does."""
    return CustomPart(
        key=key,
        label=label,
        source="gui",
        mat=material,
        recipe={
            "kind": "polygon_extrude",
            "label": label,
            "material": material,
            "vertices": [[x, y, Z0] for x, y in corners],
            "extrusion": [0.0, 0.0, Z1 - Z0],
        },
    )


def project() -> Project:
    sand = soil(
        "m_sand",
        "Sand",
        "#e6c86e",
        young=10.0e6,
        cohesion=0.0,
        friction_angle=30.0,
        unit_weight=19_000.0,
        k0=0.5,
    )
    clay = soil(
        "m_clay",
        "Clay",
        "#8fa37a",
        young=1.0e6,
        cohesion=2_000.0,
        friction_angle=24.0,
        unit_weight=18_000.0,
        k0=0.5933,
    )
    clay_cap = soil(
        "m_clay_cap",
        "Clay cap",
        "#6f8a5e",
        young=1.0e6,
        cohesion=5_000.0,
        friction_angle=24.0,
        unit_weight=18_000.0,
        k0=0.5933,
    )

    # The AZ 36-700N, per metre of wall.
    sheet_pile = BeamSection(
        id="az_36_700n",
        name="AZ 36-700N",
        variables={
            "YOUNG_MODULUS": 200.0e9,
            "POISSON_RATIO": 0.0,
            "DENSITY": 7_850.0,
            "CROSS_AREA": 2.159e-2,
            "I33": 8.9610e-4,
            "AREA_EFFECTIVE_Y": 2.591e-2,
        },
    )  # 1.2 times the area: the shear correction

    # One contact per side and stretch, so that the contact with the excavated parts,
    # on the right of the upper stretch, can be switched off on its own.
    contact = InterfaceSection(id="contact", name="Wall contact")
    contacts = [
        Interface(
            id="contact_lower",
            name="Contact, lower stretch",
            section=contact.id,
            structure="sheet_pile_wall",
            stretch=(WALL[-1], UPPER_CONTACT_START),
        ),
        Interface(
            id="contact_upper_left",
            name="Contact, upper stretch, left",
            section=contact.id,
            structure="sheet_pile_wall",
            side="left",
            stretch=(UPPER_CONTACT_START, WALL[0]),
        ),
        Interface(
            id="contact_upper_right",
            name="Contact, upper stretch, right",
            section=contact.id,
            structure="sheet_pile_wall",
            side="right",
            stretch=(UPPER_CONTACT_START, WALL[0]),
        ),
    ]
    to_install = ["sheet_pile_wall", *ids(contacts)]

    return scripting.with_solids(
        Project(
            name="dike_with_sheet_pile",
            layered_soil=True,
            dimension=2,
            domain=Domain(
                x0=LEFT_X, x1=RIGHT_X, z0=Z0, z1=Z1, y_top=CREST_Y, y_bottom=BOTTOM_Y
            ),
            materials=[sand, clay, clay_cap],
            layers=[],
            custom_parts=[
                drawn("sand_left", "Sand, left", sand.id, SAND_LEFT),
                drawn("sand_right", "Sand, right", sand.id, SAND_RIGHT),
                drawn("clay_1", "Clay 1", clay.id, CLAY_1),
                drawn("clay_2", "Clay 2", clay.id, CLAY_2),
                drawn("clay_cap_3", "Clay cap 3", clay_cap.id, CLAY_CAP_3),
                drawn("clay_cap_4", "Clay cap 4", clay_cap.id, CLAY_CAP_4),
                drawn("clay_5", "Clay 5", clay.id, CLAY_5),
                drawn("clay_6", "Clay 6", clay.id, CLAY_6),
                drawn("clay_7", "Clay 7", clay.id, CLAY_7),
                drawn("clay_cap_8", "Clay cap 8", clay_cap.id, CLAY_CAP_8),
            ],
            beam_sections=[sheet_pile],
            beams=[
                Beam(
                    id="sheet_pile_wall",
                    name="Sheet pile wall",
                    section=sheet_pile.id,
                    points=WALL,
                )
            ],
            interface_sections=[contact],
            interfaces=contacts,
            normal_loads=[
                NormalLoad(
                    id="reservoir_daily",
                    name="Reservoir, daily",
                    points=RESERVOIR_DAILY,
                    fluid_pressure_type="Hydrostatic",
                    reference_coordinate=DAILY_LEVEL,
                ),
                NormalLoad(
                    id="reservoir_high",
                    name="Reservoir, high water",
                    points=RESERVOIR_HIGH,
                    fluid_pressure_type="Hydrostatic",
                    reference_coordinate=HIGH_LEVEL,
                ),
            ],
            boundary_conditions=BOUNDARY_CONDITIONS,
            mesh=MeshSettings(
                element_size=ELEMENT_SIZE,
                order=ELEMENT_ORDER,
                body_sizes={
                    "clay_2": FINE_ELEMENT_SIZE,
                    "clay_cap_4": FINE_ELEMENT_SIZE,
                    "sheet_pile_wall": FINE_ELEMENT_SIZE,
                },
            ),
            stages=[
                Stage(
                    id="initial",
                    name="Initial stress state",
                    calculation="K0 procedure",
                    deactivate=[
                        *to_install,
                        "reservoir_high",
                        WATER_LEFT_DAILY.id,
                        WATER_LEFT_HIGH.id,
                        *ids(WATER_RIGHT),
                    ],
                ),
                Stage(
                    id="null_step",
                    name="Plastic null step",
                    parent="initial",
                    max_iterations=MAX_ITERATIONS,
                    tolerated_error=TOLERANCE,
                ),
                # The wall's deflection is measured from the ground it was installed in.
                Stage(
                    id="install_wall",
                    name="Sheet pile wall installation",
                    parent="null_step",
                    reset_displacements=True,
                    activate=[*to_install, WATER_LEFT_DAILY.id, *ids(WATER_RIGHT)],
                    deactivate=["water_before_wall"],
                    max_iterations=MAX_ITERATIONS,
                    tolerated_error=TOLERANCE,
                ),
                Stage(
                    id="excavation",
                    name="Clay excavation and high water",
                    parent="install_wall",
                    activate=["reservoir_high", WATER_LEFT_HIGH.id],
                    deactivate=[
                        *EXCAVATED_PARTS,
                        "contact_upper_right",
                        "reservoir_daily",
                        WATER_LEFT_DAILY.id,
                        *[f"water_behind_{part}" for part in EXCAVATED_PARTS],
                    ],
                    max_iterations=EXCAVATION_ITERATIONS,
                    tolerated_error=EXCAVATION_TOLERANCE,
                ),
            ],
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Write the Kratos deck into this folder (or `--out DIR`); `--calculate` also runs it
    there, and `--gui` opens the GUI with that folder as its runs root."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        metavar="DIR",
        default=HERE,
        help="write the deck and the runs into DIR (default: this file's folder)",
    )
    parser.add_argument(
        "--calculate",
        action="store_true",
        help="also run the deck, and print a summary of the results",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="open the GUI, whose Results mode lists the runs in DIR",
    )
    args = parser.parse_args(argv)
    from cli.terminal.main import main as kratos_cli

    folder = str(args.out.resolve())
    code = kratos_cli(["export", __file__, "--out", folder])
    if code == 0 and args.calculate:
        code = kratos_cli(["run", folder, "--runs-dir", folder])
        if code == 0:
            # Run 1 is the newest: the one just made. A field is read at the last stage.
            for command in (
                ["show", "1"],
                ["field", "1", "uy"],
                ["field", "1", "ux"],
                ["profile", "1", "wall", "M"],
            ):
                print()
                kratos_cli(["results", *command, "--runs-dir", folder])
    if code == 0 and args.gui:
        code = gui(args.out)
    return code


def gui(runs: Path) -> int:
    """Start the GUI (as run.bat does) with `runs` as the folder its Results mode reads."""
    import os
    import subprocess

    print(
        f"\nopening the GUI on the runs in {runs}; in it, press Results and pick a run.\n"
        "Ctrl+C here stops it."
    )
    environment = os.environ | {"KRATOS_GUI_RUNS": str(runs.resolve())}
    try:
        return subprocess.call(
            [sys.executable, "-m", "backend.launcher", "--open-browser"],
            cwd=ROOT,
            env=environment,
        )
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
