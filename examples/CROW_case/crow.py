"""CROW excavation wall, as a model script.

Written by kratos-cli from crow.json on 2026-10-21. Every value is the model's own,
typed out; constants and loops can be put in by hand.

    run crow.py                   in the GUI's command box: open it there
    kratos-cli show crow.py       and every kratos-cli command that reads a model
    python crow.py --out deck/    write its Kratos deck: ProjectParameters.json,
                                  MaterialParameters.json and the .mdpa
    python crow.py --calculate    write the deck and run it, as Calculate does

`python` is the environment kratos-cli runs in (.venv-windows, .venv-linux, ...).
"""

from __future__ import annotations

import sys
from pathlib import Path


def checkout() -> Path:
    """The checkout, where `core` is: a folder above this file, or the one the Python
    that runs it is in (.venv-windows and the others sit in the checkout's root)."""
    here = Path(__file__).resolve().parent
    for folder in [here, *here.parents, Path(sys.prefix).resolve().parent]:
        if (folder / "core" / "model" / "schemas.py").is_file():
            return folder
    if "core" in sys.modules:                       # opened inside Styx, which has it
        return Path(sys.modules["core"].__file__).resolve().parents[1]
    sys.exit(f"{Path(__file__).name}: no Styx checkout found; run it with the Python "
             "that kratos-cli uses")


ROOT = checkout()
"""`python <this file>` needs it on the path."""
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model.schemas import (  # noqa: E402
    Anchor, AnchorRows, AnchorSection, Beam, BeamSection, Borehole, BoxRefinement, Domain,
    Excavation, Interface, InterfaceSection, LineLoad, Material, MeshSettings, NormalLoad,
    Phase, Piles, Project, SoilLayer, Struts, Wall, WaterLevel, Wells)


# ── The site ──────────────────────────────────────────────────────────────────────────────

DOMAIN = Domain(x0=0.0, x1=80.0, z0=0.0, z1=10.0, y_top=0.0, y_bottom=-60.0)

BOREHOLES = [Borehole(id="bh1", name="BH1", x=0.0, y=0.0, head=0.0, water=-1.5)]


# ── The soil ──────────────────────────────────────────────────────────────────────────────

MATERIALS = [
    Material(
        id="m_upper",
        name="Upper ground",
        constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
        variables={
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 900000.0,
            "POISSON_RATIO": 0.2,
            "DENSITY_SOLID": 1834.8623853211009,
            "POROSITY": 0.0,
            "PERMEABILITY_XX": 1.1574074074074073e-05,
            "GEO_COHESION": 1000.0,
            "GEO_FRICTION_ANGLE": 22.3,
            "DENSITY_WATER": 1019.367991845056,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_YY": 1.1574074074074073e-05,
            "PERMEABILITY_XY": 0.0,
            "K0_NC": 0.62,
        },
        color="#c4a86a",
    ),
    Material(
        id="m_lower",
        name="Deep sand",
        constitutive_law="GeoLinearElasticPlaneStrain2DLaw",
        variables={
            "GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD",
            "YOUNG_MODULUS": 7428600.0,
            "POISSON_RATIO": 0.3,
            "DENSITY_SOLID": 2038.735983690112,
            "POROSITY": 0.0,
            "PERMEABILITY_XX": 5.787037037037037e-05,
            "GEO_COHESION": 0.0,
            "GEO_FRICTION_ANGLE": 32.7,
            "DENSITY_WATER": 1019.367991845056,
            "BULK_MODULUS_SOLID": 10000000000.0,
            "BULK_MODULUS_FLUID": 2200000000.0,
            "DYNAMIC_VISCOSITY": 0.001,
            "PERMEABILITY_YY": 5.787037037037037e-05,
            "PERMEABILITY_XY": 0.0,
            "K0_NC": 0.46,
        },
        color="#b08a6a",
    ),
]

LAYERS = [
    SoilLayer(
        id="L_top",
        name="Soil_Top",
        mat="m_upper",
        tops={"bh1": 0.0},
        bots={"bh1": -8.0},
    ),
    SoilLayer(
        id="L_mid",
        name="Soil_Middle",
        mat="m_upper",
        tops={"bh1": -8.0},
        bots={"bh1": -12.0},
    ),
    SoilLayer(
        id="L_bot",
        name="Soil_Bottom",
        mat="m_lower",
        tops={"bh1": -12.0},
        bots={"bh1": -60.0},
    ),
]

EXCAVATION = Excavation(
    x0=0.0,
    x1=5.0,
    z0=0.0,
    z1=10.0,
    floor_y=-8.0,
    levels=[-2.0, -5.0, -8.0],
)

WATER = WaterLevel(y=-1.5)


# ── The structures ────────────────────────────────────────────────────────────────────────

BEAM_SECTIONS = [
    BeamSection(
        id="sheetpile",
        name="Sheet pile",
        variables={
            "YOUNG_MODULUS": 8444900000.0,
            "POISSON_RATIO": 0.0,
            "DENSITY": 298.36,
            "CROSS_AREA": 0.4924,
            "I33": 0.009948850085333335,
            "AREA_EFFECTIVE_Y": 10.0,
        },
    ),
]

BEAMS = [
    Beam(
        id="sheetpile",
        name="SheetPileWall",
        section="sheetpile",
        points=[(5.0, 0.0), (5.0, -13.0)],
    ),
]

ANCHOR_SECTIONS = [
    AnchorSection(
        id="strand",
        name="Strut",
        variables={
            "YOUNG_MODULUS": 210000000000.0,
            "CROSS_AREA": 4.7619e-05,
            "DENSITY": 0.0,
        },
        spacing=1.0,
    ),
]

ANCHORS = [
    Anchor(id="strut", name="Strut", section="strand", head=(5.0, -1.5), tail=(4.0, -1.5)),
]

INTERFACE_SECTIONS = [InterfaceSection(id="contact", name="Wall contact", r_inter=0.7)]

INTERFACES = [
    Interface(
        id="wall_contact",
        name="Interface",
        section="contact",
        structure="sheetpile",
    ),
]


# ── The loads ─────────────────────────────────────────────────────────────────────────────

LOADS = [
    LineLoad(
        id="surcharge",
        name="Load",
        x0=5.0,
        x1=80.0,
        y=0.0,
        components=(0.0, -20000.0),
    ),
]

NORMAL_LOADS = [
    NormalLoad(
        id="water_1",
        name="WaterLoad_Stage1",
        points=[(5.0, -1.5), (5.0, -2.0), (0.0, -2.0)],
        fluid_pressure_type="Hydrostatic",
    ),
    NormalLoad(
        id="water_2",
        name="WaterLoad_Stage2",
        points=[(5.0, -1.5), (5.0, -5.0), (0.0, -5.0)],
        fluid_pressure_type="Hydrostatic",
    ),
    NormalLoad(
        id="water_3",
        name="WaterLoad_Stage3",
        points=[(5.0, -1.5), (5.0, -8.0), (0.0, -8.0)],
        fluid_pressure_type="Hydrostatic",
    ),
]


# ── The seeded demo pit ───────────────────────────────────────────────────────────────────
# The demo's own wall ring, struts, anchors, piles and wells. A layered model builds
# none of them; the schema requires them all the same.

WALL = Wall(thickness=0.5, top_y=0.0, toe_y=-1.0)

STRUTS = Struts(xs=[], y=0.0, radius=0.1)

ANCHOR_ROWS = AnchorRows(xs=[], head_y=0.0, length=1.0, inclination_deg=45.0, radius=0.1)

PILES = Piles(xs=[], zs=[], radius=0.1, length=1.0, top_y=0.0)

WELLS = Wells(positions=[], radius=0.1, top_y=0.0, length=1.0)


# ── The mesh ──────────────────────────────────────────────────────────────────────────────

MESH = MeshSettings(
    element_size=5.0,
    body_sizes={"sheetpile": 0.5},
    refinements=[
        BoxRefinement(
            kind="box",
            size=0.75,
            thickness=45.0,
            x_min=-1.0,
            x_max=8.0,
            z_min=-1.0,
            z_max=11.0,
            y_min=-16.0,
            y_max=1.0,
        ),
    ],
)


# ── The construction phases ───────────────────────────────────────────────────────────────

PHASES = [
    Phase(
        id="initial",
        name="Initial stage",
        calculation="K0 procedure",
        deactivate=[
            "sheetpile",
            "strut",
            "wall_contact",
            "surcharge",
            "water_1",
            "water_2",
            "water_3",
        ],
    ),
    Phase(
        id="null_step",
        name="Null step",
        parent="initial",
        calculation="Null step",
        max_iterations=150,
    ),
    Phase(
        id="install_sheetpile",
        name="SheetPileWall installation",
        parent="null_step",
        activate=["sheetpile", "wall_contact", "surcharge"],
        reset_displacements=True,
        max_iterations=150,
        tolerated_error=0.001,
    ),
    Phase(
        id="dig_1",
        name="First excavation",
        parent="install_sheetpile",
        activate=["water_1"],
        deactivate=["soil_L_top__lift1"],
        max_iterations=150,
        tolerated_error=0.001,
    ),
    Phase(
        id="install_strut",
        name="Strut installation",
        parent="dig_1",
        activate=["strut"],
        max_iterations=150,
        tolerated_error=0.001,
    ),
    Phase(
        id="dig_2",
        name="Second excavation",
        parent="install_strut",
        activate=["water_2"],
        deactivate=["soil_L_top__lift2", "water_1"],
        max_iterations=150,
        tolerated_error=0.001,
    ),
    Phase(
        id="dig_3",
        name="Third excavation",
        parent="dig_2",
        activate=["water_3"],
        deactivate=["soil_L_top__lift3", "water_2"],
        max_iterations=150,
        tolerated_error=0.001,
    ),
]


def project() -> Project:
    """The model, as one Project."""
    return Project(
        name="CROW excavation wall",
        dimension=2,
        section_offset=5.0,
        domain=DOMAIN,
        boreholes=BOREHOLES,
        materials=MATERIALS,
        layers=LAYERS,
        excavation=EXCAVATION,
        water=WATER,
        beam_sections=BEAM_SECTIONS,
        beams=BEAMS,
        anchor_sections=ANCHOR_SECTIONS,
        anchors=ANCHORS,
        interface_sections=INTERFACE_SECTIONS,
        interfaces=INTERFACES,
        loads=LOADS,
        normal_loads=NORMAL_LOADS,
        wall=WALL,
        struts=STRUTS,
        anchor_rows=ANCHOR_ROWS,
        piles=PILES,
        wells=WELLS,
        mesh=MESH,
        phases=PHASES,
    )


def main(argv: list[str] | None = None) -> int:
    """`--out DIR` writes the Kratos deck; `--calculate` runs it, as Calculate does."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, metavar="DIR",
                        help="write the Kratos deck into DIR")
    parser.add_argument("--calculate", action="store_true",
                        help="run the deck (the one written into --out, when given)")
    args = parser.parse_args(argv)
    if args.out is None and not args.calculate:
        parser.error("give --out DIR to write the deck, --calculate to run it, or both")
    from cli.terminal.main import main as kratos_cli

    if args.out is None:
        return kratos_cli(["calculate", __file__])
    code = kratos_cli(["export", __file__, "--out", str(args.out)])
    return kratos_cli(["run", str(args.out)]) if code == 0 and args.calculate else code


if __name__ == "__main__":
    sys.exit(main())
