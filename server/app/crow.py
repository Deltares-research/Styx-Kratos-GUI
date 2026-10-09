"""The CROW sheet-pile excavation, built as a `Project` and exported by this pipeline.

The same model `demo_crow_excavation_wall.py` describes, but built from this repo's own
`Project` schema and exported through `app.build` -> `app.meshing` -> `app.kratos`
instead of through STEM and gmsh_utils. `crow_excavation_wall.mdpa` in the repo root is
what the result is checked against (`tests/test_crow_reference.py`), and
`plan/staged-construction-plan.md` sec 3 is why this exists: it is the model that says
the GUI's own model can express a real staged excavation, not a demonstration in its own
right.

Every dimension below is read off `demo_crow_excavation_wall.py`'s constants. The one
thing that is *derived* rather than copied is the soil: the demo names eight bodies by
hand, where here they fall out of three soil layers crossed with three excavation lifts
(`Project.soil_bodies`). That is the whole point of the exercise -- a user draws layers
and digs lifts; they do not name Cartesian products -- so the names differ from the
reference's even though the bodies are the same. See the reference test for what
"the same" is checked to mean.

`layered_soil=True` chooses the build path that makes the soil out of layers and
whatever the user drew into it, rather than the one that also raises the seeded 3D wall
ring, strut frame and pile group around the pit. CROW has none of those: its wall is a
drawn sheet pile and its strut is a drawn anchor, so that is the path it needs. (The
flag was called `simple_example` until this model made the name untenable -- nobody
would call this deck simple. The old spelling is still read from saved files.)

Run it from the repository root:

    python examples/crow/crow.py --out <dir>

or, in the GUI's command box, to look at the model rather than write it out:

    run examples/crow/crow.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app import build, kratos, phases
from app.schemas import (Anchor, AnchorSection, Beam, BeamSection, Borehole,
                         BoxRefinement, Domain, Excavation, Interface, InterfaceSection,
                         LineLoad, Material, MeshRequest, MeshSettings, NormalLoad,
                         Piles, Project, SoilLayer, Struts, Wall, Wells, WaterLevel,
                         AnchorRows)

WALL_X = 5.0
DOMAIN_LEFT_X, DOMAIN_RIGHT_X = 0.0, 80.0
DOMAIN_BOTTOM_Y, DOMAIN_TOP_Y = -60.0, 0.0
FIRST, SECOND, THIRD = -2.0, -5.0, -8.0
BOTTOM_LAYER_TOP_Y = -12.0
WALL_TOE_Y = -13.0
ANCHOR_Y, ANCHOR_END_X = -1.5, 4.0

ELEMENT_SIZE_GLOBAL = 5.0
"""The far field, 70 m from anything that moves. The demo uses 8 m and pins every soil
body to 2 m, which comes to the same total but spends it evenly; this spends it where
the excavation is and lets the rest grow out to 5 m."""

ELEMENT_SIZE_WALL = 0.5
"""The wall itself, finer than the ground around it and -- more to the point -- *uniform*
along its whole length.

Left to the box refinement below, the wall took 0.75 m and gmsh then fitted a whole
number of elements into each stretch between the lift levels, so it came out in three
sizes: 0.5 m at the toe, 0.667 m and 0.75 m above. Comparing a run against the
validation deck, every node outside tolerance lay in a 0.667 m or 0.75 m element and
none lay in the 0.5 m band. It is worst at the head, where the surcharge starts exactly
at the wall: one 0.75 m element cannot represent that shear gradient, and the value
extrapolated to the free head came out at 3360 against the reference's 1986, where both
should tend to zero.

0.5 m divides every stretch of this wall -- 1.5, 0.5, 3, 3, 4 and 1 m -- so the whole
13 m comes out as 26 equal elements with no size change anywhere."""

ELEMENT_SIZE_EXCAVATION = 0.75
"""The pit, the wall, and the ground immediately behind it -- everything the answer is
actually read from. `MeshSettings.body_sizes` takes a structure's part key like a soil
body's, so the wall asks for this the same way the lifts do."""

REFINED_REACH = WALL_X + 3.0
REFINED_DEPTH = WALL_TOE_Y - 3.0
REFINED_BAND = 45.0
"""How far past the refined box the element size takes to grow back to
`ELEMENT_SIZE_GLOBAL`. Without a band the mesh steps from 0.75 m to 8 m across one
element edge; with it, the size roughly doubles every 10 m out to the far boundary,
which is what a graded excavation mesh looks like and what keeps the elements at the
transition well shaped.""" 
ELEMENT_ORDER = 2

WATER_Y = -1.5
"""The hydrostatic reference the reference deck's every water process carries
(`reference_coordinate: -1.5`), and the level its `WaterLoad_Stage*` loads are derived
from."""

SURCHARGE = -20.0
"""kN/m per metre run, downward: the reference's `LINE_LOAD` of -20000 N/m on `Load`."""

# The out-of-plane extent. A plane-strain model is a slice, and the section is taken
# through the middle of it; the depth itself is arbitrary and never reaches the deck.
Z0, Z1 = 0.0, 10.0
SECTION_Z = 5.0


def crow_project(staged: bool = True) -> Project:
    """The CROW model, as this application's user would have built it.

    `staged` fills in `Project.phases` with `phases.staged_excavation_phases`, which for this
    model reproduces the reference deck's seven stages exactly -- so the export is the
    seven-stage deck `staged_construction_for_generated_mesh.json` is, not a single
    stage of it. Pass `staged=False` for the same geometry with no construction
    sequence, which is what the mdpa comparison in `tests/test_crow_reference.py` uses:
    phases change no geometry, and a test about the mesh should not depend on them.
    """
    borehole = "bh1"
    # Two materials, as the reference's two soil property sets: the upper ground down to
    # -12 and the stiffer sand below it. K0_NC, porosity and the drainage type are the
    # reference's own rather than left to this exporter's defaults: the user owns those
    # values. The reference's 0.62 and 0.46 are Jaky at these friction angles, so the
    # typed numbers and the fallback agree here -- which is what makes checking them
    # worth doing.
    #
    # `E` is kN/m2, like everything else in a `Project` (`app/schemas.py`). These two
    # were typed as 9.0e3 and 7.43e4 until the export was compared against
    # `MaterialParameters_for_generated_mesh.json`, which carries 9.0e5 Pa and 7.4286e6
    # Pa -- a decimal slip of exactly 10x in both, which for a while cancelled half of
    # the exporter's own 1000x units bug and made the deck look nearly right.
    upper = Material(id="m_upper", name="Upper ground", model="Mohr-Coulomb",
                     type="Drained", color="#c4a86a", g_unsat=18.0, g_sat=20.0,
                     E=9.0e2, nu=0.2, c=1.0, phi=22.3, k=1.0,
                     porosity=0.0, k0_nc=0.62)
    lower = Material(id="m_lower", name="Deep sand", model="Mohr-Coulomb",
                     type="Drained", color="#b08a6a", g_unsat=20.0, g_sat=22.0,
                     E=7.4286e3, nu=0.3, c=0.0, phi=32.7, k=5.0,
                     porosity=0.0, k0_nc=0.46)

    # Three layers, not two: the reference splits the right-hand ground at -8 as well as
    # at -12 (Soil_Top_Right / Soil_Middle_Right), and -8 is where the digging stops.
    # Splitting the layer there is what makes the deepest lift end on a layer boundary
    # instead of part way through one.
    layers = [
        SoilLayer(id="L_top", name="Soil_Top", mat=upper.id,
                  tops={borehole: DOMAIN_TOP_Y}, bots={borehole: THIRD}),
        SoilLayer(id="L_mid", name="Soil_Middle", mat=upper.id,
                  tops={borehole: THIRD}, bots={borehole: BOTTOM_LAYER_TOP_Y}),
        SoilLayer(id="L_bot", name="Soil_Bottom", mat=lower.id,
                  tops={borehole: BOTTOM_LAYER_TOP_Y}, bots={borehole: DOMAIN_BOTTOM_Y}),
    ]

    # The wall. `E`, the area and the density are the reference's own numbers; the
    # second moment and the shear area are the *stiffnesses* its own numbers stand for.
    #
    # The reference pairs its beam with `TimoshenkoBeamPlaneStrainElasticConstitutiveLaw`,
    # which idealises the wall as a solid plate and derives both the area and the second
    # moment from a single `THICKNESS` of 0.4924. That is not a plate anybody rolled: it
    # is the thickness whose t^3/12 gives the second moment this case wants, and
    # (12 * 9.9489e-3)^(1/3) is 0.4924 to four figures. We pair the beam with
    # `TimoshenkoBeamElasticConstitutiveLaw` instead, which takes area and inertia
    # separately -- a real sheet pile's are not related by t^3/12 -- so the same wall is
    # stated directly rather than through a thickness.
    #
    # It was `inertia=4.0e-3`, a number with no counterpart anywhere in the reference and
    # no source but this file, which made the wall two and a half times too soft in
    # bending. `tests/test_crow_reference.py` now compares EI, EA and GA_s rather than
    # the numbers they are spelled with, so the two cannot drift again.
    plate = 0.4924
    sheet_pile = BeamSection(id="sheetpile", name="Sheet pile", E=8.4449e6, nu=0.0,
                             area=plate, inertia=plate ** 3 / 12.0,
                             # Twenty times the section: the reference's way of saying
                             # that shear deformation is not part of this model.
                             shear_area=10.0, density=298.36)
    # Massless, as the reference's tendon is: a prestressed strut's own weight is
    # beside the point next to the force it carries.
    strand = AnchorSection(id="strand", name="Strut", E=2.1e8, area=4.7619e-5,
                           density=0.0, spacing=1.0)
    # No `material`: each stretch of the contact takes the soil it actually runs
    # against, which is how the reference groups its eight interfaces into two property
    # sets -- one for the contacts on the upper ground, one for those on the sand.
    # `virtual_thickness` is the element size normal to the interface, 1 m in the
    # reference, and the stiffnesses follow from it: shear is that soil's shear modulus,
    # normal is ten times it.
    contact = InterfaceSection(id="contact", name="Wall contact",
                               r_inter=0.7, virtual_thickness=1.0)

    project = Project(
        name="CROW excavation wall",
        # The model carries the density it wants meshing at, rather than leaving it to
        # be typed in: 2 m through the soil, which is what the reference deck is meshed
        # at, against a coarser global default for anything else. `body_sizes` is keyed
        # by *layer*, which is what the Mesh properties dialog lists and what
        # `Project.expand_body_keys` spreads over the lifts dug out of each one.
        # Graded, not uniform, and the box does all of it. Nothing is given a
        # `body_sizes` entry on purpose: a body that asks for a size is held to it
        # throughout, so refining the pit that way would also pin the 48 m of sand
        # *underneath* it -- most of a mesh, spent where nothing happens. The box is
        # bounded in depth as well as in width, which a body is not.
        mesh=MeshSettings(
            element_size=ELEMENT_SIZE_GLOBAL, order=ELEMENT_ORDER,
            # The wall asks for its own size, and gets it: the box field and this one
            # are combined by taking the smaller, so 0.5 m wins along the wall while
            # the soil around it stays at the box's 0.75 m.
            body_sizes={"sheetpile": ELEMENT_SIZE_WALL},
            refinements=[BoxRefinement(
                kind="box", size=ELEMENT_SIZE_EXCAVATION, thickness=REFINED_BAND,
                x_min=DOMAIN_LEFT_X - 1.0, x_max=REFINED_REACH,
                y_min=REFINED_DEPTH, y_max=DOMAIN_TOP_Y + 1.0,
                z_min=Z0 - 1.0, z_max=Z1 + 1.0)]),
        layered_soil=True,
        dimension=2,
        section_offset=SECTION_Z,
        domain=Domain(x0=DOMAIN_LEFT_X, x1=DOMAIN_RIGHT_X, z0=Z0, z1=Z1,
                      y_top=DOMAIN_TOP_Y, y_bottom=DOMAIN_BOTTOM_Y),
        boreholes=[Borehole(id=borehole, name="BH1", x=DOMAIN_LEFT_X, y=Z0,
                            head=DOMAIN_TOP_Y, water=WATER_Y)],
        materials=[upper, lower],
        layers=layers,
        # The pit: against the left edge, which is the model's symmetry plane, and dug
        # in the three lifts the reference stages.
        excavation=Excavation(x0=DOMAIN_LEFT_X, x1=WALL_X, z0=Z0, z1=Z1,
                              levels=[FIRST, SECOND, THIRD]),
        # Unused by this build path; present because the schema carries them for the
        # seeded example. Emptied rather than left at their defaults so nothing of the
        # seeded pit furniture can reach the deck.
        wall=Wall(thickness=0.5, top_y=DOMAIN_TOP_Y, toe_y=WALL_TOE_Y),
        struts=Struts(xs=[], y=ANCHOR_Y, radius=0.1),
        anchor_rows=AnchorRows(xs=[], head_y=ANCHOR_Y, length=1.0,
                               inclination_deg=45.0, radius=0.1),
        piles=Piles(xs=[], zs=[], radius=0.1, length=1.0, top_y=DOMAIN_TOP_Y),
        wells=Wells(positions=[], radius=0.1, length=1.0, top_y=DOMAIN_TOP_Y),
        water=WaterLevel(y=WATER_Y),
        beam_sections=[sheet_pile],
        beams=[Beam(id="sheetpile", name="SheetPileWall", section=sheet_pile.id,
                    points=[(WALL_X, DOMAIN_TOP_Y), (WALL_X, WALL_TOE_Y)])],
        anchor_sections=[strand],
        # Node to node: one end on the wall, the other in no element at all. The free
        # end becomes its own pinned support part -- the reference's `Strut_Support`.
        anchors=[Anchor(id="strut", name="Strut", section=strand.id,
                        head=(WALL_X, ANCHOR_Y), tail=(ANCHOR_END_X, ANCHOR_Y))],
        interface_sections=[contact],
        interfaces=[Interface(id="wall_contact", name="Interface", section=contact.id,
                              structure="sheetpile", side="both")],
        # The surcharge on the retained surface, right of the wall.
        loads=[LineLoad(id="surcharge", name="Load", x0=WALL_X, x1=DOMAIN_RIGHT_X,
                        y=DOMAIN_TOP_Y, components=(0.0, SURCHARGE))],
        # One water load per lift: the exposed wall face down to that level, then that
        # level's floor back to the symmetry plane. Hydrostatic from `water`.
        #
        # It starts at the water table, not at the ground surface. Above the phreatic
        # level the hydrostatic pressure is negative and Kratos clips it to zero, so
        # conditions up there do nothing -- but they are still conditions, meshed and
        # carried through every stage, and the reference deck has none of them.
        normal_loads=[
            NormalLoad(id=f"water_{index}", name=f"WaterLoad_Stage{index}",
                       fluid_pressure_type="Hydrostatic",
                       points=[(WALL_X, WATER_Y), (WALL_X, level),
                               (DOMAIN_LEFT_X, level)])
            for index, level in enumerate((FIRST, SECOND, THIRD), start=1)
        ],
    )
    if not staged:
        return project
    return Project.model_validate(
        project.model_dump()
        | {"phases": [phase.model_dump() for phase in phases.staged_excavation_phases(project)]})


def export(project: Project | None = None) -> dict:
    """Mesh and export the model, in a gmsh session of this function's own.

    The mesh settings come off the project rather than being passed in, so this and the
    GUI's own Generate-mesh both mesh it the same way: one density, carried by the
    model, not two that can drift.
    """
    project = project or crow_project()
    with build.session():
        return kratos.export_project(
            project, MeshRequest(**project.mesh.model_dump()))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("crow_out"),
                        help="directory to write the deck into")
    args = parser.parse_args(argv[1:])

    result = export()
    args.out.mkdir(parents=True, exist_ok=True)
    name = result["deck_name"]
    (args.out / f"{name}.mdpa").write_text(result["mdpa"], encoding="utf-8")
    (args.out / "MaterialParameters.json").write_text(result["materials"],
                                                      encoding="utf-8")
    if result["initial_materials"]:
        (args.out / "initial_materials.json").write_text(result["initial_materials"],
                                                         encoding="utf-8")
    (args.out / "ProjectParameters.json").write_text(result["project_parameters"],
                                                     encoding="utf-8")
    for warning in result["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    stats = json.loads(json.dumps(result["stats"]))
    print(f"wrote {args.out / f'{name}.mdpa'}  ({stats})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
