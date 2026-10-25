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

from core import scripting
from core.analysis import calculation
from core.geometry import solid_model
from core.kratos import materials, writer
from core.model.schemas import InterfaceSection, Material, Stage, Project
from core.model.templates import seed_project
from core.results import catalog, members
from tests import mdpa
from tests.models import drawn_ground, excavation
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


def test_a_contact_on_one_face_of_a_part_of_a_pile_runs():
    """The staged excavation with its contact on the retained face only, from the strut
    head down to the toe. Above the head the pile goes on: the soil there stays on the
    pile's own node at the head, and the soil the contact holds has a copy. At
    the toe the retained soil has its own copy, tied to the other soil until the wall
    is installed. Every stage runs.

    With the pile's node kept for the held soil at the head as well, the last contact
    element has it on both sides, and Kratos stops in the installation stage with "Bad
    optional access": `UPwInterfaceElement::Initialize` takes the side its neighbour
    is on from the element's first node alone."""
    project = excavation.excavation_project()
    contact = project.interfaces[0].model_copy(update={
        "side": "right", "stretch": ((excavation.WALL_X, excavation.STRUT_Y),
                                     (excavation.WALL_X, excavation.WALL_TOE_Y))})
    project = project.model_copy(update={"interfaces": [contact]})

    export, _ = run(project)

    deck = mdpa.parse(export["mdpa"])
    held = [deck.nodes[n][1] for block in deck.elements if "Interface" in block.name
            for nodes in block.entries.values() for n in nodes[:len(nodes) // 2]]
    assert max(held) == excavation.STRUT_Y, "no contact above the strut head"
    assert min(held) == excavation.WALL_TOE_Y


def test_a_contact_on_one_face_of_a_whole_pile_runs():
    """The drawn ground with its contact on the left face only: at the toe the left
    soil has a copy and the rest keeps the pile's node. Every stage runs."""
    project = drawn_ground.project()
    contact = project.interfaces[0].model_copy(update={"side": "left"})
    run(project.model_copy(update={"interfaces": [contact]}))


CONTACTS = r"""
import importlib, json
import KratosMultiphysics as Kratos
from KratosMultiphysics.project import Project

with open("ProjectParameters.json", encoding="utf-8") as handle:
    project = Project(Kratos.Parameters(handle.read()))
entry = Kratos.Registry[project.GetSettings()["orchestrator"]["name"].GetString()]
getattr(importlib.import_module(entry["ModuleName"]), entry["ClassName"])(project).Run()
variable = Kratos.KratosGlobals.GetVariable
part = project.GetModel()["PorousDomain"]
names = ("INTERFACE_NORMAL_STIFFNESS", "INTERFACE_SHEAR_STIFFNESS", "GEO_COHESION",
         "GEO_FRICTION_ANGLE")


def at_points(element, name):
    return [list(point) for point in element.CalculateOnIntegrationPoints(
        variable(name), part.ProcessInfo)]


with open("contacts.json", "w", encoding="utf-8") as handle:
    json.dump([
        {"nodes": [node.Id for node in element.GetNodes()],
         "properties": {name: element.Properties[variable(name)] for name in names
                        if element.Properties.Has(variable(name))},
         "traction": at_points(element, "GEO_EFFECTIVE_TRACTION_VECTOR"),
         "relative": at_points(element, "GEO_RELATIVE_DISPLACEMENT_VECTOR")}
        for element in part.Elements
        if element.Properties.Has(variable("INTERFACE_SHEAR_STIFFNESS"))], handle)
"""
"""Runs a deck to its end and writes, per contact element, its nodes, its properties and
its traction (normal, shear) and relative displacement (opening, slip) at each
integration point. What `results profile` reads is the traction extrapolated to the
nodes; this is the value the law computed."""


def contacts(project: Project, directory: Path) -> tuple[dict, list[dict]]:
    """`project` exported and run in `directory`, and every contact element at the end."""
    with solid_model.session():
        export = writer.export_project(project)
    calculation.write_deck(export, directory)
    python, environment = calculation.interpreter()
    done = subprocess.run([python, "-c", CONTACTS], cwd=directory, env=environment,
                          capture_output=True, text=True, timeout=600)
    written = directory / "contacts.json"
    assert written.is_file(), done.stdout[-600:] + done.stderr[-600:]
    return export, json.loads(written.read_text(encoding="utf-8"))


def displacements(outcome: dict, stage: int) -> dict[int, list[float]]:
    return catalog.stage_results(Path(outcome["directory"]).name,
                                 stage).field("DISPLACEMENT").values


# ── Master and slave, after Kratos' test_master_slave_constraints.py ───────

def tie_pairs(deck: mdpa.Deck) -> list[tuple[int, int]]:
    """(master, slave) per tied point: the two copies of one soil node, one per face."""
    masters = {deck.nodes[n]: n for n in deck.parts["Wall_contact_Master"].nodes}
    return [(masters[deck.nodes[n]], n) for n in deck.parts["Wall_contact_Slave"].nodes]


def uneven_fills() -> dict:
    """The drawn-ground model with the right fill made of the layer's soil: softer and
    lighter than the left fill, so the two faces of the future wall settle by different
    amounts, and only the tie can hold them together."""
    data = drawn_ground.drawn_ground_project().model_dump()
    right = next(part for part in data["custom_parts"] if part["key"] == "drawn_1")
    right["mat"] = right["recipe"]["material"] = "m_ground"
    return data


def without_the_tie(export: dict) -> dict:
    doc = json.loads(export["project_parameters"])
    for stage in doc["stages"].values():
        processes = stage["stage_settings"]["processes"]["constraints_process_list"]
        processes[:] = [p for p in processes if p["process_name"]
                        != "AssignMasterSlaveConstraintsToNeighboursUtility"]
    return export | {"project_parameters": json.dumps(doc)}


def run_export(export: dict) -> dict:
    outcome = calculation.run(export)
    assert outcome["ok"], (outcome["stage"], (outcome["error"] or "")[-600:])
    return outcome


@pytest.fixture(scope="module")
def tied():
    """The uneven fills split along the wall line and tied, run; its first stage is the
    K0 stage, before the wall and its contact are installed."""
    project = scripting.with_solids(Project.model_validate(uneven_fills()))
    with solid_model.session():
        export = writer.export_project(project)
    return export, run_export(export)


def test_before_installation_the_tie_holds_the_split_soil_as_one(tied):
    """Before the wall is installed the soil along its line is split and nothing but
    the tie joins the two faces. The ground then has to settle as if it had never been
    split: every node as in the same model without an interface, and the two copies of
    each split node by the same amount. The results file keeps six decimals, so equal
    means equal to 1e-6 m."""
    export, outcome = tied
    data = uneven_fills()
    data["interfaces"] = []
    for stage in data["stages"]:
        for key in ("activate", "deactivate"):
            stage[key] = [k for k in stage[key] if k != "wall_contact"]
    bonded_export, bonded_outcome = run(scripting.with_solids(Project.model_validate(data)))

    deck, bonded_deck = mdpa.parse(export["mdpa"]), mdpa.parse(bonded_export["mdpa"])
    split, whole = displacements(outcome, 1), displacements(bonded_outcome, 1)
    at = {xyz: n for n, xyz in bonded_deck.nodes.items()}
    compared = 0
    for node, xyz in deck.nodes.items():
        if node in split and xyz in at:
            assert split[node][:2] == pytest.approx(whole[at[xyz]][:2], abs=1e-6), xyz
            compared += 1
    assert compared > len(deck.nodes) // 2
    pairs = tie_pairs(deck)
    assert len(pairs) == 8, "both copies of every node along the wall above its toe"
    for master, slave in pairs:
        assert split[master][:2] == pytest.approx(split[slave][:2], abs=1e-6)


def test_without_the_tie_the_two_faces_settle_apart(tied):
    """The check above can tell: the same deck with the tie left out lets the softer
    right fill settle past the left one along the split, by about half a millimetre."""
    export, _ = tied
    outcome = run_export(without_the_tie(export))
    u = displacements(outcome, 1)
    apart = max(abs(u[master][1] - u[slave][1])
                for master, slave in tie_pairs(mdpa.parse(export["mdpa"])))
    assert apart > 1e-4, apart


@pytest.mark.parametrize("stiffness, apart", [(1e2, True), (1e12, False)],
                         ids=["weak", "stiff"])
def test_once_the_wall_is_installed_its_contact_holds_the_faces_not_the_tie(stiffness,
                                                                           apart):
    """In the stage that installs the wall the tie is gone and the contact is what
    joins each face to the wall. A surcharge on the left fill alone settles the left
    face: through a weak contact the right face hardly follows, through a stiff one it
    moves with the wall, as one. A tie left in place would hold the faces together
    through the weak contact too."""
    data = drawn_ground.drawn_ground_project(staged=False).model_dump()
    data["normal_loads"] = [{"id": "surcharge", "name": "Surcharge", "pressure": 50_000.0,
                             "points": [(drawn_ground.DOMAIN_LEFT_X, drawn_ground.DOMAIN_TOP_Y),
                                        (drawn_ground.WALL_X, drawn_ground.DOMAIN_TOP_Y)]}]
    data["interface_sections"][0]["variables"] = {"INTERFACE_NORMAL_STIFFNESS": stiffness,
                                                  "INTERFACE_SHEAR_STIFFNESS": stiffness}
    built = ["sheetpile", "wall_contact", "surcharge"]
    data["stages"] = [
        Stage(id="initial", name="Initial", calculation="K0 procedure",
              deactivate=built).model_dump(),
        Stage(id="load", name="Load", parent="initial", activate=built,
              reset_displacements=True).model_dump(),
    ]
    export, outcome = run(scripting.with_solids(Project.model_validate(data)))
    u = displacements(outcome, 2)
    for master, slave in tie_pairs(mdpa.parse(export["mdpa"])):
        left, right = u[master][1], u[slave][1]
        assert left < 0.0, "the master is the left face's copy, under the surcharge"
        if apart:
            assert abs(left) > 1.5 * abs(right), (left, right)
        else:
            assert left == pytest.approx(right, abs=1e-5)


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


# ── What an elastic contact carries ────────────────────────────────────────

ELASTIC_PULL = 100_000.0
"""N/m up on the pile head, carried by the default elastic contact."""


@pytest.fixture(scope="module")
def pulled(tmp_path_factory):
    """The pile pulled up through an elastic contact with the stiffness derived from
    the soil: the project, the deck and every contact element at the end."""
    project = drawn_ground.pushed_pile_project(load=(0.0, ELASTIC_PULL))
    export, elements = contacts(project, tmp_path_factory.mktemp("pulled"))
    return project, mdpa.parse(export["mdpa"]), elements


def along(deck: mdpa.Deck, element: dict) -> tuple[float, float, float]:
    """The element's length and the y of its two ends, off its structure-side nodes."""
    (xa, ya, _), (xb, yb, _) = (deck.nodes[n] for n in element["nodes"][:2])
    return math.hypot(xb - xa, yb - ya), ya, yb


def test_a_contact_starts_from_the_stress_in_the_ground_beside_it(pulled):
    """The traction is the stress the contact started with plus its stiffness times its
    opening and slip. Kratos starts a contact, when it is installed, from the stress of
    the soil element beside it -- which the deck names to it -- so after the K0 stage
    the normal traction starts at K0 times the vertical stress, here dry soil, and the
    shear at nought. A contact that found no soil element beside it starts at nought,
    and the pile then stands in ground that pushes on it with nothing."""
    project, deck, elements = pulled
    fill, ground = project.material("m_fill"), project.material("m_ground")
    weight = {key: m.variables["DENSITY_SOLID"] * 9.81 for key, m in
              (("fill", fill), ("ground", ground))}
    top = drawn_ground.DOMAIN_TOP_Y
    layer = drawn_ground.LAYER_TOP_Y

    def vertical(y: float) -> float:
        return (weight["fill"] * (top - max(y, layer))
                + weight["ground"] * max(layer - y, 0.0))

    for element in elements:
        _, ya, yb = along(deck, element)
        in_fill = (ya + yb) / 2 > layer
        k0 = materials.jaky(fill if in_fill else ground)
        normal, shear = (element["properties"][name] for name in
                         ("INTERFACE_NORMAL_STIFFNESS", "INTERFACE_SHEAR_STIFFNESS"))
        # Lobatto points: one end, the middle, the other end.
        for y, (tn, ts, *_), (un, us, *_) in zip((ya, (ya + yb) / 2, yb),
                                                element["traction"], element["relative"]):
            assert tn - normal * un == pytest.approx(-k0 * vertical(y), rel=0.01, abs=50.0)
            assert ts == pytest.approx(shear * us, rel=1e-6, abs=1e-6)


def test_the_contact_carries_the_pull_on_the_pile_into_the_ground(pulled):
    """The pile hangs in the contact and nothing else: its toe stands on a copy of the
    soil node that only contact elements reach. The shear along both faces, integrated
    over the pile, is the pull less the pile's own weight."""
    project, deck, elements = pulled
    carried = 0.0
    for element in elements:
        length, _, _ = along(deck, element)
        shears = [abs(point[1]) for point in element["traction"]]
        # Three-point Lobatto, end, middle, end: weights 1/3, 4/3, 1/3 on a half-length of 1.
        carried += length / 2 * (shears[0] + 4 * shears[1] + shears[2]) / 3
    section = project.beam_sections[0].variables
    length = drawn_ground.DOMAIN_TOP_Y - drawn_ground.WALL_TOE_Y
    weight = section["DENSITY"] * section["CROSS_AREA"] * 9.81 * length
    assert carried == pytest.approx(ELASTIC_PULL - weight, rel=0.005)


COULOMB_CONTACT = "GeoInterfaceCoulombLawPlaneStrain"


# ── After Kratos' test_mohr_coulomb_with_tension_cutoff.py ─────────────────

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
    _, elements = contacts(project, tmp_path)
    return [(e["properties"]["GEO_COHESION"], e["properties"]["GEO_FRICTION_ANGLE"], tn, ts)
            for e in elements for tn, ts, *_ in e["traction"]]


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
