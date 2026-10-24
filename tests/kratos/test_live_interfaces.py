"""Interfaces in a running deck: the contact holds what it should, by running Kratos.
Opt-in: `pytest --run-kratos`.

The deck-shape tests (`tests/test_kratos_interfaces.py`) say what is written. These say
the wall and the soil it is written against behave as one model when they should.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import materials, writer
from core.model.schemas import InterfaceSection, Material, Project
from core.model.templates import seed_project
from core.results import catalog, members
from tests import mdpa
from tests.models import drawn_ground
from tests.results_run import require_kratos

pytestmark = pytest.mark.kratos


@pytest.fixture(scope="module", autouse=True)
def runs_root(tmp_path_factory):
    require_kratos()
    previous = os.environ.get(calculation.RUNS_ENV)
    os.environ[calculation.RUNS_ENV] = str(tmp_path_factory.mktemp("interface-runs"))
    catalog.forget_cache()
    yield
    if previous is None:
        os.environ.pop(calculation.RUNS_ENV, None)
    else:
        os.environ[calculation.RUNS_ENV] = previous
    catalog.forget_cache()


def run(project: Project) -> tuple[dict, dict]:
    with solid_model.session():
        export = writer.export_project(project)
    outcome = calculation.run(export)
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])
    return export, outcome


def test_a_water_load_on_a_wall_face_beside_dug_drawn_soil_runs():
    """The trench water presses on the wall face where the drawn fill was dug away.
    That load stays on the wall's own nodes, and Kratos looks for an element with that
    edge: only the contact element has it. Without a contact along the drawn fill the
    stage stopped before its first step ("found without any corresponding element")."""
    run(drawn_ground.project())



def test_a_pile_standing_out_of_the_ground_runs():
    """The same model with the pile 1 m above the fill, as a dike's sheet pile stands
    above its crest. The piece above the ground has nodes no soil element holds; before
    the pile is installed no element holds them at all, and every stage still runs."""
    run(drawn_ground.standing_pile_project())

# ── After Kratos' tests/test_interface.py ──────────────────────────────────

def pile_and_soil(export: dict, outcome: dict, stage: str = "2_Push"
                  ) -> tuple[dict[int, dict], dict[int, float]]:
    """The pile's own output by node, and every soil node's x displacement."""
    directory = Path(outcome["directory"])
    wall = members.read_output(
        (directory / f"{stage}__output_wall.json").read_text(encoding="utf-8"))
    run_id = directory.name
    number = int(stage.split("_", 1)[0])
    displacement = catalog.stage_results(run_id, number).field("DISPLACEMENT").values
    deck = mdpa.parse(export["mdpa"])
    soil = {n for block in deck.elements if block.name.startswith("SmallStrainUPw")
            for nodes in block.entries.values() for n in nodes}
    return wall, {n: displacement[n][0] for n in soil if n in displacement}


def peak(wall: dict[int, dict], variable: str) -> float:
    return max((v[variable] for v in wall.values() if variable in v), key=abs)


def test_a_stiff_interface_carries_the_pile_as_bonding_does():
    """`test_interface_on_beam`: with a very stiff contact the pile moves and bends as
    it does welded to the soil. A contact missing along part of the pile -- the drawn
    fill, before every soil body was a soil body to it -- fails this by a factor."""
    stiff = {"INTERFACE_NORMAL_STIFFNESS": 1e12, "INTERFACE_SHEAR_STIFFNESS": 1e12}
    bonded_wall, _ = pile_and_soil(*run(drawn_ground.pushed_pile_project(interface=False)))
    contact_wall, _ = pile_and_soil(*run(drawn_ground.pushed_pile_project(variables=stiff)))
    for variable in ("TOTAL_DISPLACEMENT_X", "BENDING_MOMENT"):
        assert peak(contact_wall, variable) == pytest.approx(peak(bonded_wall, variable),
                                                             rel=0.01), variable


def test_a_weak_interface_lets_the_pile_move_through_the_soil():
    """`test_weak_interface_on_beam`: with a contact of almost no stiffness the pushed
    pile moves and the ground beside it hardly does. Kratos asks for a factor of 1e8
    with a 10 N push; here the push is 10 kN/m and the pile's own weight goes into the
    ground through the same weak springs, which moves it about a millimetre, so the
    factor is 1e4 (2.7e4 when written)."""
    weak = {"INTERFACE_NORMAL_STIFFNESS": 1e2, "INTERFACE_SHEAR_STIFFNESS": 1e2}
    wall, soil = pile_and_soil(*run(drawn_ground.pushed_pile_project(variables=weak)))
    pile = abs(peak(wall, "TOTAL_DISPLACEMENT_X"))
    ground = max(abs(u) for u in soil.values())
    assert pile > 1e4 * ground, (pile, ground)


COULOMB_CONTACT = "GeoInterfaceCoulombLawPlaneStrain"


# ── After Kratos' test_mohr_coulomb_with_tension_cutoff.py ─────────────────

SLIPPED = r"""
import importlib, json
import KratosMultiphysics as Kratos
from KratosMultiphysics.project import Project

with open("ProjectParameters.json", encoding="utf-8") as handle:
    project = Project(Kratos.Parameters(handle.read()))
entry = Kratos.Registry[project.GetSettings()["orchestrator"]["name"].GetString()]
getattr(importlib.import_module(entry["ModuleName"]), entry["ClassName"])(project).Run()
variable = Kratos.KratosGlobals.GetVariable
part = project.GetModel()["PorousDomain"]
with open("slipped.json", "w", encoding="utf-8") as handle:
    json.dump([
        [element.Properties[variable("GEO_COHESION")],
         element.Properties[variable("GEO_FRICTION_ANGLE")],
         [list(point) for point in element.CalculateOnIntegrationPoints(
             variable("GEO_EFFECTIVE_TRACTION_VECTOR"), part.ProcessInfo)]]
        for element in part.Elements
        if element.Properties.Has(variable("INTERFACE_SHEAR_STIFFNESS"))], handle)
"""

PULL = 150_000.0
"""N/m up on the pile head: enough for the contact to slip along the fill and the top
of the layer, not enough to pull the pile out."""

SOFT = {"INTERFACE_NORMAL_STIFFNESS": 1e7, "INTERFACE_SHEAR_STIFFNESS": 1e6}
"""Pa/m. The Coulomb law hands Newton its elastic stiffness, also where the contact
slips, so the iterations creep; with the stiffness derived from the soil (1e8 Pa/m)
they had not converged after 50."""


def slipped(variables: dict, tmp_path: Path) -> list[tuple[float, float, float, float]]:
    """(c, phi, tn, ts) at every integration point of the contact, the pile pulled up."""
    project = drawn_ground.pushed_pile_project(variables=SOFT | variables,
                                               law=COULOMB_CONTACT, load=(0.0, PULL),
                                               max_iterations=50)
    with solid_model.session():
        export = writer.export_project(project)
    calculation.write_deck(export, tmp_path)
    python, environment = calculation.interpreter()
    done = subprocess.run([python, "-c", SLIPPED], cwd=tmp_path, env=environment,
                          capture_output=True, text=True, timeout=600)
    written = tmp_path / "slipped.json"
    assert written.is_file(), done.stdout[-600:] + done.stderr[-600:]
    return [(c, phi, tn, ts)
            for c, phi, points in json.loads(written.read_text(encoding="utf-8"))
            for tn, ts, *_ in points]


def strength(c: float, phi: float, tn: float) -> float:
    """The shear the contact holds, Kratos' `CoulombYieldSurface`: the Mohr-Coulomb
    surface of its soils, F = tau + sigma sin(phi) - c cos(phi), with the contact's
    traction for (sigma, tau). Less than the textbook c - sigma tan(phi) by cos(phi)."""
    return c * math.cos(math.radians(phi)) - tn * math.sin(math.radians(phi))


def held_to_its_strength(points: list[tuple[float, float, float, float]]) -> None:
    """No point carries more shear than its strength, and the upper ones slip at it."""
    for c, phi, tn, ts in points:
        assert abs(ts) <= strength(c, phi, tn) * 1.01 + 1.0, (c, phi, tn, ts)
    at_it = [p for p in points if strength(*p[:3]) > 1.0
             and abs(p[3]) >= 0.99 * strength(*p[:3])]
    assert len(at_it) >= 4, points


@pytest.mark.parametrize("typed", [False, True], ids=["derived", "typed"])
def test_a_coulomb_contact_slips_at_its_strength(typed, tmp_path):
    """`interface_coulomb_2plus2`: the contact sheared until it slips carries the shear
    its strength allows and no more. Here the pile is pulled out of the ground. Once
    with the strength derived from each soil it runs against, c r and atan(r tan phi),
    once with c and phi typed on the section, used as they stand."""
    typed_values = {"GEO_COHESION": 2_000.0, "GEO_FRICTION_ANGLE": 25.0}
    points = slipped(typed_values if typed else {}, tmp_path)
    r = 0.7
    wanted = ({(2_000.0, 25.0)} if typed else
              {(r * 1_000.0, math.degrees(math.atan(r * math.tan(math.radians(30.0))))),
               (r * 1_500.0, math.degrees(math.atan(r * math.tan(math.radians(40.0)))))})
    got = {(c, phi) for c, phi, _, _ in points}
    assert len(got) == len(wanted)
    for c, phi in wanted:
        assert any(c == pytest.approx(gc) and phi == pytest.approx(gphi, abs=1e-3)
                   for gc, gphi in got), (c, phi, got)
    held_to_its_strength(points)


# ── After Kratos' crow_validation/mohr_coulomb_clay-sand ───────────────────


def geomechanics_tests() -> Path:
    """`GeoMechanicsApplication/tests` in the Kratos source beside the configured build."""
    build = os.environ.get(calculation.KRATOS_ENV) or calculation._settings().get("kratos")
    folder = (Path(build).parents[1] / "applications" / "GeoMechanicsApplication"
              / "tests") if build else None
    if folder is None or not (folder / "crow_validation").is_dir():
        pytest.skip(f"no Kratos source with tests/crow_validation beside the build {build!r}")
    return folder


def test_the_reference_coulomb_contacts_are_what_their_soils_derive():
    """The CROW reference with Mohr-Coulomb soils writes one Coulomb contact per soil:
    stiffnesses G / t and 10 G / t with t = 1 m, cohesion and tan(phi) reduced by one
    Rinter per soil. The factor is read off the friction angles; the cohesion and both
    stiffnesses are then the export's own derivation, held to the reference's numbers."""
    reference = json.loads((geomechanics_tests() / "crow_validation" / "mohr_coulomb_clay-sand"
                            / "MaterialParameters.json").read_text(encoding="utf-8"))
    by_id = {p["properties_id"]: p["Material"] for p in reference["properties"]}
    for soil_id, contact_id in ((1, 3), (2, 4)):
        soil, contact = by_id[soil_id], by_id[contact_id]
        assert contact["constitutive_law"]["name"] == COULOMB_CONTACT
        wanted = contact["Variables"]
        r_inter = (math.tan(math.radians(wanted["GEO_FRICTION_ANGLE"]))
                   / math.tan(math.radians(soil["Variables"]["GEO_FRICTION_ANGLE"])))
        material = Material(id=f"soil_{soil_id}", name=f"Soil {soil_id}", color="#b08a6a",
                            constitutive_law=soil["constitutive_law"]["name"],
                            variables=dict(soil["Variables"]))
        section = InterfaceSection(id="contact", name="Contact",
                                   constitutive_law=COULOMB_CONTACT, r_inter=r_inter,
                                   virtual_thickness=1.0)
        got = materials._interface_variables(section, seed_project(), [], material)
        for name in ("INTERFACE_NORMAL_STIFFNESS", "INTERFACE_SHEAR_STIFFNESS",
                     "GEO_COHESION", "GEO_FRICTION_ANGLE"):
            assert got[name] == pytest.approx(wanted[name], rel=1e-4, abs=1e-9), \
                (soil_id, name)
        assert got["GEO_DILATANCY_ANGLE"] == 0.0


# ── After Kratos' test_line_interface_elements.py ──────────────────────────

TRACTIONS = r"""
import json
import KratosMultiphysics as Kratos
import KratosMultiphysics.GeoMechanicsApplication as Geo
from KratosMultiphysics.GeoMechanicsApplication import geomechanics_analysis

with open("ProjectParameters.json", encoding="utf-8") as handle:
    parameters = Kratos.Parameters(handle.read())
simulation = geomechanics_analysis.GeoMechanicsAnalysis(Kratos.Model(), parameters)
simulation.Run()
part = simulation._list_of_output_processes[0].model_part
print("TRACTIONS" + json.dumps([
    [list(point) for point in element.CalculateOnIntegrationPoints(
        Geo.GEO_EFFECTIVE_TRACTION_VECTOR, part.ProcessInfo)]
    for element in part.Elements]))
"""


def test_an_interface_traction_is_normal_then_shear_and_compression_is_negative(tmp_path):
    """What `results profile ... interface tn` and `ts` read: component 0 of
    GEO_EFFECTIVE_TRACTION_VECTOR is the normal traction, component 1 the shear, and a
    contact pressed shut has a negative normal traction. Kratos' own Neumann case on the
    3+3 line element, run on the build Styx runs, so a Kratos that changes either is
    caught here and not in a results plot."""
    source = geomechanics_tests() / "line_interface_elements"
    shutil.copytree(source / "Neumann_single_stage", tmp_path / "case")
    shutil.copytree(source / "common", tmp_path / "common")
    python, environment = calculation.interpreter()
    done = subprocess.run([python, "-c", TRACTIONS], cwd=tmp_path / "case", env=environment,
                          capture_output=True, text=True, timeout=300)
    line = next((line for line in done.stdout.splitlines() if line.startswith("TRACTIONS")),
                None)
    assert line, done.stdout[-600:] + done.stderr[-600:]
    tractions = json.loads(line[len("TRACTIONS"):])
    # The values Kratos' test asserts: a normal traction of 333 Pa pressing the contact
    # shut and a shear of 667 Pa, at every integration point of both elements.
    for element in tractions:
        for normal, shear in element:
            assert normal == pytest.approx(-333.0)
            assert shear == pytest.approx(-667.0)
