"""What a new record starts as, said twice and held to one document.

The GUI starts a new soil from `App.PropertySets.KINDS.soil` and offers the six presets
of `App.MaterialLibrary`; its material window fills in a soil model's defaults with
`App.SoilModels.fill` and refuses what `App.SoilModels.problem` refuses; it starts a new sheet pile, wall, member, anchor, interface or
load from the Structure mode's own `draft` functions. The command line starts each from
`core.model.drafts`. Two copies of one table drift, so `frontend/tests/fixtures/drafts.js`
is the document both are held to: this module writes it from the Python, and
`frontend/tests/test-drafts.js` compares the JavaScript to it
(`frontend/tests/run_headless.py drafts`).

For the structures the document is a list of calls: a JavaScript function, the project
it is called on and its arguments, and what the Python twin answered for the same
project. The JavaScript is called with them and has to answer the same record, field
for field -- or refuse with the same sentence.

    python tests/test_draft_parity.py --write

rewrites it after a deliberate change. The pattern is `tests/test_stage_parity.py`'s: a
`.js` file assigning one global, which Python reads by stripping the assignment.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core import session   # noqa: E402
from core.model import drafts, soil_models, units   # noqa: E402
from core.model.schemas import DimensionUpdate, UnitsUpdate   # noqa: E402
from core.model.templates import seed_project   # noqa: E402
from tests.models.excavation import excavation_project   # noqa: E402

FIXTURE = (pathlib.Path(__file__).resolve().parents[1]
           / "frontend" / "tests" / "fixtures" / "drafts.js")

HEADER = '''/* Generated fixture -- what a new soil or structure starts as, in the one document
   the GUI (property-sets.js, material-library.js, beams.js, anchors.js, interfaces.js,
   loads.js, normal-loads.js) and the command line (core/model/drafts.py) are both held
   to. See tests/test_draft_parity.py, which writes and compares it, and
   frontend/tests/test-drafts.js, which reads it.

   Not hand-edited. `python tests/test_draft_parity.py --write` rebuilds it.
*/
window.DRAFTS_FIXTURE =
'''


def projects() -> dict:
    """The projects the structure drafts are made on, by name."""
    section, _ = session.set_dimension(seed_project(), DimensionUpdate(dimension=2))
    section_kn, _ = session.set_units(section, UnitsUpdate(unit_system="kN"))
    pile = drafts.sheet_pile(section_kn)
    section_pile_kn = section_kn.model_copy(update={
        "beams": [pile], "beam_sections": [drafts.section_for(section_kn, pile)]})
    # A pile standing 5 m out of the ground, which a point load may sit on.
    tall = drafts.sheet_pile(section, [(12, 5), (12, -6)])
    section_tall_pile = section.model_copy(update={
        "beams": [tall], "beam_sections": [drafts.section_for(section, tall)]})
    solid = seed_project()
    wall = drafts.wall(solid)
    member = drafts.member(solid)
    return {
        "section": section,
        "section_kn": section_kn,
        "dry": section.model_copy(update={"water": None, "boundary_conditions": []}),
        "section_pile_kn": section_pile_kn,
        "section_tall_pile": section_tall_pile,
        "pile": excavation_project(staged=False),
        "solid": solid,
        "solid_wall": solid.model_copy(update={
            "beams": [wall], "panel_sections": [drafts.section_for(solid, wall)]}),
        "solid_member": solid.model_copy(update={
            "beams": [member], "beam_sections": [drafts.section_for(solid, member)]}),
    }


PROJECT_FIELDS = {"name", "dimension", "unit_system", "section_offset", "domain",
                  "materials", "custom_parts", "beams", "beam_sections", "panel_sections",
                  "anchors", "anchor_sections", "interfaces", "interface_sections", "loads",
                  "normal_loads", "lines", "water", "boundary_conditions"}
"""What the draft functions read of a project, which is all the fixture carries of one."""


def _record(record) -> dict:
    """A draft as the JavaScript holds one: the fields its draft sets, and no others."""
    return record.model_dump(mode="json", exclude_unset=True)


def calls(models: dict) -> list[dict]:
    """Each structure draft, made by the Python on one of `models`: the JavaScript call
    that has to answer the same, and the answer."""
    out = []

    def call(title, js, project, args, python):
        entry = {"title": title, "call": js, "project": project, "args": args}
        try:
            made = python(models[project])
        except drafts.DraftError as refusal:
            entry["error"] = str(refusal)
        else:
            entry["result"] = ([_record(r) for r in made] if isinstance(made, list)
                               else _record(made))
        out.append(entry)

    def library(make):
        """`sectionsFor` on a project with no section of the record's kind yet: the
        default section, alone."""
        return lambda p: [drafts.section_for(p, make(p))]

    call("a sheet pile down the middle", "Beams.draft", "section", ["beam"],
         drafts.sheet_pile)
    call("a sheet pile along given points, on the first profile", "Beams.draftFromPoints",
         "pile", [[[20, 0], [20, -6]]], lambda p: drafts.sheet_pile(p, [(20, 0), (20, -6)]))
    call("a sheet pile below the model is refused", "Beams.draftFromPoints", "section",
         [[[12, 0], [12, -40]]], lambda p: drafts.sheet_pile(p, [(12, 0), (12, -40)]))
    call("a sheet pile standing out above the ground", "Beams.draftFromPoints",
         "section", [[[12, 5], [12, -6]]],
         lambda p: drafts.sheet_pile(p, [(12, 5), (12, -6)]))
    call("a sheet pile wholly above the ground is refused", "Beams.draftFromPoints",
         "section", [[[12, 5], [12, 1]]],
         lambda p: drafts.sheet_pile(p, [(12, 5), (12, 1)]))
    call("a sheet pile in the solid model is refused", "Beams.draft", "solid", ["beam"],
         drafts.sheet_pile)
    call("the profile a first sheet pile brings", "Beams.sectionsFor", "section",
         [_record(drafts.sheet_pile(models["section"]))], library(drafts.sheet_pile))
    call("a wall across the middle of the site", "Beams.draft", "solid", ["panel"],
         drafts.wall)
    call("a wall along a given footprint", "Beams.draftPanel", "solid",
         [[[5, 5], [5, 20]]], lambda p: drafts.wall(p, [(5, 5), (5, 20)]))
    call("the shell a first wall brings", "Beams.sectionsFor", "solid",
         [_record(drafts.wall(models["solid"]))], library(drafts.wall))
    call("a member standing in the middle", "Beams.draft", "solid", ["member"],
         drafts.member)
    call("a member along given points", "Beams.draftMember", "solid",
         [[[3, 0, 3], [3, -10, 3]]], lambda p: drafts.member(p, [(3, 0, 3), (3, -10, 3)]))
    call("an anchor raking back from the pile", "Anchors.draft", "pile", [], drafts.anchor)
    call("an anchor head snapped onto the pile", "Anchors.draftFromPoints", "pile",
         [[[6.4, -2], [20, -8]]], lambda p: drafts.anchor(p, (6.4, -2), (20, -8)))
    call("an anchor head far from the pile stays in the soil", "Anchors.draftFromPoints", "pile",
         [[[10, -2], [20, -8]]], lambda p: drafts.anchor(p, (10, -2), (20, -8)))
    call("a strut from the part of a pile above the ground", "Anchors.draftFromPoints",
         "section_tall_pile", [[[12.3, 4], [16, 4]], "fixed"],
         lambda p: drafts.anchor(p, (12.3, 4), (16, 4), tail_end="fixed"))
    call("a free anchor tail in the air is refused", "Anchors.draftFromPoints",
         "section_tall_pile", [[[12.3, 4], [16, 4]]],
         lambda p: drafts.anchor(p, (12.3, 4), (16, 4)))
    call("an anchor tail below the model is refused", "Anchors.draftFromPoints",
         "section_tall_pile", [[[12, 4], [16, -40]], "fixed"],
         lambda p: drafts.anchor(p, (12, 4), (16, -40), tail_end="fixed"))
    call("an anchor raking back from a pile above the ground", "Anchors.draft",
         "section_tall_pile", [], drafts.anchor)
    call("an anchor with no structure starts in the soil", "Anchors.draft", "section", [],
         drafts.anchor)
    call("an anchor head in the air on no structure is refused", "Anchors.draftFromPoints",
         "section", [[[20, 3], [25, -8]], "fixed"],
         lambda p: drafts.anchor(p, (20, 3), (25, -8), tail_end="fixed"))
    call("an anchor on a wall", "Anchors.draft", "solid_wall", [], drafts.anchor)
    call("an anchor on a member", "Anchors.draft", "solid_member", [], drafts.anchor)
    call("a first anchor in a kN model", "Anchors.draft", "section_pile_kn", [],
         drafts.anchor)
    call("the tendon a first anchor brings, in kN", "Anchors.sectionsFor",
         "section_pile_kn", [_record(drafts.anchor(models["section_pile_kn"]))],
         library(drafts.anchor))
    call("an interface on the first pile", "Interfaces.draft", "pile", [],
         drafts.interface)
    call("an interface with no pile is a free line", "Interfaces.draft", "section", [],
         drafts.interface)
    call("an interface on a part of the pile, snapped onto it", "Interfaces.draft", "pile",
         [None, [[6.3, -2], [6, -5]]],
         lambda p: drafts.interface(p, stretch_from=(6.3, -2), stretch_to=(6, -5)))
    call("an interface from one end of the pile to the other is the whole pile",
         "Interfaces.draft", "pile", [None, [[6, -12], [6, 0]]],
         lambda p: drafts.interface(p, stretch_from=(6, -12), stretch_to=(6, 0)))
    call("a From far from the pile is refused", "Interfaces.draft", "pile",
         [None, [[7.2, -2], [6, -5]]],
         lambda p: drafts.interface(p, stretch_from=(7.2, -2), stretch_to=(6, -5)))
    call("From and To at one point are refused", "Interfaces.draft", "pile",
         [None, [[6.2, -3], [6, -3]]],
         lambda p: drafts.interface(p, stretch_from=(6.2, -3), stretch_to=(6, -3)))
    call("the contact a first interface brings", "Interfaces.sectionsFor", "section",
         [_record(drafts.interface(models["section"]))], library(drafts.interface))
    call("a line across the middle of the section", "Lines.draft", "section", [],
         drafts.line)
    call("a line along points", "Lines.draft", "section", [[[0, -2], [5, -2]]],
         lambda p: drafts.line(p, [(0, -2), (5, -2)]))
    call("a line in the solid model is refused", "Lines.draft", "solid", [], drafts.line)
    call("a normal load down the middle", "NormalLoads.draft", "section", [],
         drafts.normal_load)
    call("a hydrostatic normal load takes the water level", "NormalLoads.draft", "section",
         [{"hydrostatic": True}], lambda p: drafts.normal_load(p, hydrostatic=True))
    call("a hydrostatic normal load in a dry model has no level", "NormalLoads.draft",
         "dry", [{"hydrostatic": True}], lambda p: drafts.normal_load(p, hydrostatic=True))
    call("a support on a face, fixed", "BoundaryConditions.draftDisplacement", "section",
         ["face", {"face": "left"}],
         lambda p: drafts.displacement_condition(p, "face", face="left"))
    call("a roller on the bottom", "BoundaryConditions.draftDisplacement", "section",
         ["face", {"face": "bottom", "roller": True}],
         lambda p: drafts.displacement_condition(p, "face", face="bottom", roller=True))
    call("a roller along a vertical line", "BoundaryConditions.draftDisplacement",
         "section", ["line", {"points": [[5, 0], [5, -5]], "roller": True}],
         lambda p: drafts.displacement_condition(p, "line", points=[(5, 0), (5, -5)],
                                                 roller=True))
    call("a roller along a sloping line is refused", "BoundaryConditions.draftDisplacement",
         "section", ["line", {"points": [[0, 0], [5, -5]], "roller": True}],
         lambda p: drafts.displacement_condition(p, "line", points=[(0, 0), (5, -5)],
                                                 roller=True))
    call("a support point at the centre, holding y", "BoundaryConditions.draftDisplacement",
         "section", ["point", {"fixed": [False, True, False]}],
         lambda p: drafts.displacement_condition(p, "point", fixed=(False, True, False)))
    call("a support on the whole soil is refused", "BoundaryConditions.draftDisplacement",
         "section", ["domain", {}], lambda p: drafts.displacement_condition(p, "domain"))
    call("a support line in the solid model is refused",
         "BoundaryConditions.draftDisplacement", "solid", ["line", {}],
         lambda p: drafts.displacement_condition(p, "line"))
    call("a hydrostatic pressure takes the water level",
         "BoundaryConditions.draftWaterPressure", "section", ["domain", {}],
         lambda p: drafts.water_pressure_condition(p, "domain"))
    call("a hydrostatic pressure with no level anywhere is refused",
         "BoundaryConditions.draftWaterPressure", "dry", ["domain", {}],
         lambda p: drafts.water_pressure_condition(p, "domain"))
    call("a uniform pressure along a line, initial", "BoundaryConditions.draftWaterPressure",
         "dry", ["line", {"fluid_pressure_type": "Uniform", "value": -5000,
                          "is_fixed": False}],
         lambda p: drafts.water_pressure_condition(p, "line", fluid_pressure_type="Uniform",
                                                   value=-5000, is_fixed=False))
    call("a phreatic line on a face", "BoundaryConditions.draftWaterPressure", "dry",
         ["face", {"face": "right", "fluid_pressure_type": "Phreatic_Multi_Line",
                   "x_coordinates": [0, 25], "y_coordinates": [-1, -2],
                   "pressure_tension_cut_off": 100000}],
         lambda p: drafts.water_pressure_condition(
             p, "face", face="right", fluid_pressure_type="Phreatic_Multi_Line",
             x_coordinates=[0, 25], y_coordinates=[-1, -2], pressure_tension_cut_off=100000))
    call("a water pressure point in the solid model is refused",
         "BoundaryConditions.draftWaterPressure", "solid", ["point", {}],
         lambda p: drafts.water_pressure_condition(p, "point"))
    call("a seepage face on the right face", "BoundaryConditions.draftSeepage", "section",
         ["face", {"face": "right"}],
         lambda p: drafts.seepage_condition(p, "face", face="right"))
    call("a seepage line down the right side", "BoundaryConditions.draftSeepage", "section",
         ["line", {}], lambda p: drafts.seepage_condition(p, "line"))
    call("a seepage line drawn", "BoundaryConditions.draftSeepage", "section",
         ["line", {"points": [[25, -1], [25, -6]], "name": "Exit"}],
         lambda p: drafts.seepage_condition(p, "line", points=[(25, -1), (25, -6)],
                                            name="Exit"))
    call("a seepage face on the whole soil is refused", "BoundaryConditions.draftSeepage",
         "section", ["domain", {}], lambda p: drafts.seepage_condition(p, "domain"))
    call("a seepage line in the solid model is refused", "BoundaryConditions.draftSeepage",
         "solid", ["line", {}], lambda p: drafts.seepage_condition(p, "line"))
    call("the standard supports, with ids no condition has",
         "BoundaryConditions.standardConditions", "section", [],
         drafts.standard_conditions)
    call("the standard supports of a project with none", "BoundaryConditions.standardConditions",
         "dry", [], drafts.standard_conditions)
    call("a point load", "Loads.draftPoint", "section", [[5, 0]],
         lambda p: drafts.point_load(p, (5, 0)))
    call("a point load in kN", "Loads.draftPoint", "section_kn", [[5, 0]],
         lambda p: drafts.point_load(p, (5, 0)))
    call("a point load on the head of a pile above the ground", "Loads.draftPoint",
         "section_tall_pile", [[12, 5]], lambda p: drafts.point_load(p, (12, 5)))
    call("a point load picked beside a pile above the ground snaps onto it",
         "Loads.draftPoint", "section_tall_pile", [[12.4, 4.8]],
         lambda p: drafts.point_load(p, (12.4, 4.8)))
    call("a point load in the air, off any pile, is refused", "Loads.draftPoint",
         "section_tall_pile", [[20, 5]], lambda p: drafts.point_load(p, (20, 5)))
    call("a point load in the solid model is refused", "Loads.draftPoint", "solid",
         [[5, 0]], lambda p: drafts.point_load(p, (5, 0)))
    call("a line load picked right to left", "Loads.draftFromPoints", "section",
         [[[8, 0], [2, 0]]], lambda p: drafts.line_load(p, (8, 2)))
    call("a surface load in the middle of the site", "Loads.draftSurface", "solid", [],
         drafts.surface_load)
    return out


ELASTIC_2D = soil_models.law(soil_models.LINEAR_ELASTIC, 2)
MOHR_COULOMB_2D = soil_models.law(soil_models.MOHR_COULOMB, 2)


def soil_model_cases() -> dict:
    """What `soil_models` answers, for the JavaScript twin to answer the same: the
    defaults it fills, the soils it refuses and why, what a law needs, a law's name in a
    dimension."""
    mohr_coulomb = soil_models.defaults_si(soil_models.MOHR_COULOMB)
    in_kn, _ = units.convert_variables(mohr_coulomb, "SI", "kN")

    def fill(title, before_law, before, after_law, changes, system, skip=()):
        after = {**before, **changes}
        filled = soil_models.fill(before_law, dict(before), after_law, after, system,
                                  tuple(skip))
        return {"title": title, "before_law": before_law, "before": before,
                "after_law": after_law, "changes": changes, "system": system,
                "skip": list(skip), "filled": filled, "after": after,
                "note": soil_models.filled_note(soil_models.model_of(after_law), filled)}

    def fill_choice(title, before_law, before, after_law, changes, system):
        after = {**before, **changes}
        filled = soil_models.fill_choice(before_law, dict(before), after_law, after, system)
        return {"title": title, "before_law": before_law, "before": before,
                "after_law": after_law, "changes": changes, "system": system,
                "filled": filled, "after": after}

    def problem(title, law, variables):
        return {"title": title, "law": law, "variables": variables,
                "problem": soil_models.problem(law, variables)}

    def required(law, variables):
        return {"law": law, "variables": variables,
                "required": soil_models.required(law, variables)}

    def derived(title, law, variables, system, flow=False, gravity=None, **water):
        water_variables = soil_models.water(system, gravity=gravity, **water)
        return {"title": title, "law": law, "variables": variables, "system": system,
                "flow": flow, "gravity": gravity, "water": water_variables,
                "derived": soil_models.derived(law, variables, water_variables, system, flow),
                "computed": soil_models.computed(law, variables, water_variables, system,
                                                 flow, gravity)}

    def water(system, specific_weight=None, bulk_modulus=None, viscosity=None,
              gravity=None):
        return {"system": system, "specific_weight": specific_weight,
                "bulk_modulus": bulk_modulus, "viscosity": viscosity, "gravity": gravity,
                "water": soil_models.water(system, specific_weight, bulk_modulus, viscosity,
                                           gravity)}

    def shown(model, variables, flow=False):
        return {"model": model, "variables": variables, "flow": flow,
                "shown": [p.name for p in soil_models.shown(model, variables, flow)]}

    coupled = {**mohr_coulomb, "GEO_DRAINAGE_TYPE": "FULLY_COUPLED", "POROSITY": 0.35}
    return {
        "derived": [
            derived("a new elastic soil", ELASTIC_2D,
                    soil_models.defaults_si(soil_models.LINEAR_ELASTIC), "SI"),
            derived("a new Mohr-Coulomb soil, in kN", MOHR_COULOMB_2D, in_kn, "kN"),
            derived("a coupled soil with its own water", MOHR_COULOMB_2D,
                    {**coupled, "PERMEABILITY_XX": 3.0e-12}, "SI",
                    specific_weight=9810.0, bulk_modulus=2.0e9, viscosity=1.3e-3),
            derived("a drained soil in a flow project", ELASTIC_2D,
                    {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "DENSITY_SOLID": 2000.0}, "SI",
                    flow=True),
            derived("a law of no model with a friction angle",
                    "SmallStrainUDSM2DPlaneStrainLaw", {"GEO_FRICTION_ANGLE": 25.0}, "SI"),
            derived("a drained soil carrying a permeability, written as it is", ELASTIC_2D,
                    {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD", "PERMEABILITY_XX": 3.0e-12}, "kN"),
            derived("a coupled soil carrying a permeability, written as it is", ELASTIC_2D,
                    {"GEO_DRAINAGE_TYPE": "FULLY_COUPLED", "PERMEABILITY_XX": 3.0e-12}, "kN"),
            derived("a blank soil", ELASTIC_2D, soil_models.blank_si(), "SI"),
            derived("a blank soil with the Van Genuchten law", ELASTIC_2D,
                    {**soil_models.blank_si(), "RETENTION_LAW": "VanGenuchtenLaw"}, "SI"),
            derived("a coupled soil in a project with g = 10 m/s2", MOHR_COULOMB_2D,
                    {**coupled, "PERMEABILITY_XX": 3.0e-12}, "kN", gravity=10.0),
        ],
        "water": [
            water("SI"),
            water("kN"),
            water("SI", bulk_modulus=2.0e9),
            water("kN", viscosity=1.3e-6),
            water("SI", 9810.0, 1.0e20, 1.3e-3),
            water("kN", 10.0, gravity=9.80665),
        ],
        "blank": soil_models.blank_si(),
        "fill_choice": [
            fill_choice("a blank soil made Mohr-Coulomb gets no strength", ELASTIC_2D,
                        soil_models.blank_si(), MOHR_COULOMB_2D, {}, "SI"),
            fill_choice("a complete soil made Mohr-Coulomb gets the defaults", ELASTIC_2D,
                        soil_models.defaults_si(soil_models.LINEAR_ELASTIC),
                        MOHR_COULOMB_2D, {}, "kN"),
            fill_choice("linear hardening on a complete soil brings its slopes",
                        MOHR_COULOMB_2D, mohr_coulomb, MOHR_COULOMB_2D,
                        {"GEO_COULOMB_HARDENING_TYPE": "Linear"}, "SI"),
        ],
        "shown": [
            shown(soil_models.LINEAR_ELASTIC, {}),
            shown(soil_models.MOHR_COULOMB, coupled),
            shown(soil_models.MOHR_COULOMB, {"GEO_DRAINAGE_TYPE": "CONSTANT_PW_FIELD"}),
            shown(soil_models.LINEAR_ELASTIC, {"RETENTION_LAW": "VanGenuchtenLaw"}, True),
        ],
        "defaults": {model: soil_models.defaults_si(model) for model in soil_models.MODELS},
        "fill": [
            fill("a new Mohr-Coulomb soil", None, {}, MOHR_COULOMB_2D, {}, "SI"),
            fill("an elastic soil made Mohr-Coulomb keeps its cohesion", ELASTIC_2D,
                 {"GEO_COHESION": 5.0, "YOUNG_MODULUS": 2.0e4}, MOHR_COULOMB_2D, {}, "kN"),
            fill("a Van Genuchten law brings its parameters", MOHR_COULOMB_2D, in_kn,
                 MOHR_COULOMB_2D, {"RETENTION_LAW": "VanGenuchtenLaw"}, "kN"),
            fill("a Van Genuchten parameter left out on purpose", MOHR_COULOMB_2D, in_kn,
                 MOHR_COULOMB_2D, {"RETENTION_LAW": "VanGenuchtenLaw"}, "kN",
                 skip=["VAN_GENUCHTEN_GN"]),
            fill("the tension cut-off brings its tensile strength", MOHR_COULOMB_2D, in_kn,
                 MOHR_COULOMB_2D, {"GEO_ENABLE_TENSION_CUT_OFF": True}, "kN"),
            fill("a listed variable left out stays out", MOHR_COULOMB_2D,
                 {k: v for k, v in in_kn.items() if k != "POROSITY"}, MOHR_COULOMB_2D,
                 {"YOUNG_MODULUS": 3.0e4}, "kN"),
            fill("a required variable left out comes back", MOHR_COULOMB_2D,
                 {k: v for k, v in in_kn.items() if k != "GEO_DILATANCY_ANGLE"},
                 MOHR_COULOMB_2D, {}, "kN"),
            fill("another law fills nothing", ELASTIC_2D, {"YOUNG_MODULUS": 1.0},
                 "SmallStrainUDSM2DPlaneStrainLaw", {}, "SI"),
            fill("an old Mohr-Coulomb name is Mohr-Coulomb", None, {},
                 "GeoMohrCoulombWithTensionCutOff2D", {}, "SI"),
        ],
        "problem": [
            problem("a default Mohr-Coulomb soil", MOHR_COULOMB_2D, mohr_coulomb),
            problem("dilatancy above friction", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_DILATANCY_ANGLE": 35.0}),
            problem("friction at 90 degrees", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_FRICTION_ANGLE": 90.0}),
            problem("tensile strength above the apex", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_ENABLE_TENSION_CUT_OFF": True,
                     "GEO_TENSILE_STRENGTH": 5000.0}),
            problem("tensile strength above the apex, a large one", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_COHESION": 2.0e6, "GEO_FRICTION_ANGLE": 25.0,
                     "GEO_ENABLE_TENSION_CUT_OFF": True, "GEO_TENSILE_STRENGTH": 1.0e7}),
            problem("tensile strength above the apex, a small one", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_COHESION": 0.00002,
                     "GEO_ENABLE_TENSION_CUT_OFF": True, "GEO_TENSILE_STRENGTH": 1.0}),
            problem("a tensile strength with the cut-off off is not read", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_TENSILE_STRENGTH": 5000.0}),
            problem("a tensile strength with no cut-off flag switches it on",
                    MOHR_COULOMB_2D,
                    {k: v for k, v in {**mohr_coulomb, "GEO_TENSILE_STRENGTH": 5000.0}.items()
                     if k != "GEO_ENABLE_TENSION_CUT_OFF"}),
            problem("an elastic soil is not held to it", ELASTIC_2D,
                    {**mohr_coulomb, "GEO_DILATANCY_ANGLE": 35.0}),
            problem("a linear hardening", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_COULOMB_HARDENING_TYPE": "Linear",
                     "GEO_COHESION_FUNCTION_COEFFICIENTS": 1.0e5,
                     "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS": 0.0,
                     "GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS": 0.0}),
            problem("a linear hardening that softens", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_COULOMB_HARDENING_TYPE": "Linear",
                     "GEO_COHESION_FUNCTION_COEFFICIENTS": 0.0,
                     "GEO_FRICTION_ANGLE_FUNCTION_COEFFICIENTS": -0.1,
                     "GEO_DILATANCY_ANGLE_FUNCTION_COEFFICIENTS": 0.0}),
            problem("a slope with the hardening off is not read", MOHR_COULOMB_2D,
                    {**mohr_coulomb, "GEO_COHESION_FUNCTION_COEFFICIENTS": -1.0}),
        ],
        "required": [
            required(ELASTIC_2D, {}),
            required(MOHR_COULOMB_2D, {}),
            required(MOHR_COULOMB_2D, {"GEO_ENABLE_TENSION_CUT_OFF": True}),
            required(MOHR_COULOMB_2D, {"GEO_COULOMB_HARDENING_TYPE": "Linear"}),
            required("SmallStrainUDSM2DPlaneStrainLaw", {}),
        ],
        "fresh_color": [{"used": used, "preferred": preferred,
                         "color": soil_models.fresh_color(used, preferred)}
                        for used, preferred in (
                            ([], None), (["#D8C48A", "#8fa86b"], None),
                            (["#c4a86a"], "#c4a86a"), (["#d8c48a"], "#c4a86a"),
                            (list(soil_models.PALETTE), None),
                            (list(soil_models.PALETTE) + ["#c78f70"], "#d8c48a"),
                            (list(soil_models.PALETTE) + [
                                soil_models.fresh_color(soil_models.PALETTE)], None))],
        "unread": [{"law": law, "variables": variables,
                    "unread": soil_models.unread(law, variables)}
                   for law in (ELASTIC_2D, MOHR_COULOMB_2D, "SmallStrainUDSM2DPlaneStrainLaw")
                   for variables in (
                       drafts.preset("m1")["variables"],
                       {**mohr_coulomb, "GEO_COULOMB_HARDENING_TYPE": "Linear",
                        "GEO_COHESION_FUNCTION_COEFFICIENTS": 1.0, "MY_OWN": 2.0,
                        "PERMEABILITY_ZZ": 1e-12})],
        "law_in": [{"law": law, "dimension": dim, "result": soil_models.law_in(law, dim)}
                   for law in (ELASTIC_2D, MOHR_COULOMB_2D,
                               "GeoMohrCoulombWithTensionCutOff2D",
                               "GeoMohrCoulombWithTensionCutOff3D",
                               "SmallStrainUDSM2DPlaneStrainLaw")
                   for dim in (2, 3)],
    }


def document() -> dict:
    models = projects()
    return {
        "soil_laws": {str(dimension): law for dimension, law in drafts.SOIL_LAWS.items()},
        "soil_defaults": drafts.SOIL_DEFAULTS_SI,
        "soil_models": soil_model_cases(),
        "library": drafts.LIBRARY,
        "projects": {name: project.model_dump(mode="json", include=PROJECT_FIELDS)
                     for name, project in models.items()},
        "calls": calls(models),
    }


def rendered() -> str:
    return HEADER + json.dumps(document(), indent=2, ensure_ascii=False) + ";\n"


def on_disk() -> dict:
    text = FIXTURE.read_text(encoding="utf-8")
    return json.loads(text[len(HEADER):].rstrip().rstrip(";"))


def test_the_fixture_is_what_the_python_says():
    assert FIXTURE.is_file(), "run `python tests/test_draft_parity.py --write`"
    assert on_disk() == document(), "run `python tests/test_draft_parity.py --write`"


def test_the_fixture_is_written_as_this_module_writes_it():
    assert FIXTURE.read_text(encoding="utf-8") == rendered()


def test_every_structure_tool_is_called():
    """A draft function the document does not call is one the two sides can disagree on
    unseen."""
    called = {entry["call"] for entry in calls(projects())}
    assert called >= {"Beams.draft", "Beams.draftFromPoints", "Beams.draftPanel",
                      "Beams.draftMember", "Beams.sectionsFor", "Anchors.draft",
                      "Anchors.draftFromPoints", "Anchors.sectionsFor", "Interfaces.draft",
                      "Interfaces.sectionsFor", "NormalLoads.draft", "Lines.draft",
                      "Loads.draftPoint",
                      "Loads.draftFromPoints", "Loads.draftSurface",
                      "BoundaryConditions.draftDisplacement",
                      "BoundaryConditions.draftWaterPressure",
                      "BoundaryConditions.standardConditions"}


if __name__ == "__main__" and "--write" in sys.argv:
    FIXTURE.write_text(rendered(), encoding="utf-8", newline="\n")
    print(f"wrote {FIXTURE}")
