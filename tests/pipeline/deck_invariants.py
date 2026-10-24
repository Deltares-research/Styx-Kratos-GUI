"""Every structural rule a Kratos deck written by this tool must satisfy (plan alpha 2.1).

`check_deck(export)` takes what `core.kratos.writer.export_project` returns and gives back a list
of violations, each a sentence naming the rule and the offending thing; empty means
sound. It re-reads the deck through `tests.mdpa` -- independent of `core.kratos.writer` -- so a
rule that holds says the *files* are right, not that two copies of one helper agree.

`tests/conftest.py` runs it on every deck any test exports, so a new feature that breaks
one of these is caught by whichever test first exports it, not only by the tests written
for it. What it cannot see is a deck that is structurally sound and physically wrong; that
is what running Kratos is for (plan sec 8).
"""

from __future__ import annotations

import json
import re

from tests import mdpa

ROOT = "PorousDomain"
RUNTIME_PARTS = {"porous_computational_model_part"}
"""Parts Kratos makes itself when the solver starts, which no .mdpa declares."""

PART_KEYS = ("model_part_name", "master_model_part_name", "slave_model_part_name")
PART_LIST_KEYS = ("model_part_name_list", "problem_domain_sub_model_part_list",
                  "body_domain_sub_model_part_list", "processes_sub_model_part_list")

MATERIAL_FILES = {"MaterialParameters.json": "materials",
                  "initial_materials.json": "initial_materials"}

DIMENSION_TOKEN = re.compile(r"([23])D(\d+)N")
SOIL_LINEAR = "UPwSmallStrainElement2D3N"
SOIL_QUADRATIC = "SmallStrainUPwDiffOrderElement2D6N"


def check_deck(export: dict) -> list[str]:
    deck = mdpa.parse(export["mdpa"])
    params = json.loads(export["project_parameters"])
    files = {name: json.loads(export[key]) for name, key in MATERIAL_FILES.items()
             if export.get(key)}
    out: list[str] = []
    out += _connectivity(deck)
    out += _properties(deck)
    out += _materials(deck, files)
    out += _references(deck, params)
    out += _stages(params)
    out += _orphans(deck)
    out += _dimension(deck)
    out += _order(deck)
    out += _units(files, export.get("unit_system", "SI"))
    out += _k0(deck, params, files)
    out += _condition_order(deck)
    out += _mesh_read_once(params)
    return out


# 1. every element and condition names nodes the deck has
def _connectivity(deck) -> list[str]:
    known = set(deck.nodes)
    out = []
    for block in deck.elements + deck.conditions:
        for entity, nodes in block.entries.items():
            missing = [n for n in nodes if n not in known]
            if missing:
                out.append(f"rule 1: {block.name} {entity} uses undeclared nodes {missing[:5]}")
    return out


# 2. every property an entity uses is declared
def _properties(deck) -> list[str]:
    declared = set(deck.properties)
    used = {p for block in deck.elements + deck.conditions for p in block.properties.values()}
    return [f"rule 2: properties {sorted(used - declared)} are used but never declared"] \
        if used - declared else []


# 3, 4. every material entry names a part with entities; property ids are unique
def _materials(deck, files) -> list[str]:
    out = []
    for name, document in files.items():
        ids = []
        for entry in document.get("properties", []):
            part = entry.get("model_part_name", "")
            bare = part[len(ROOT) + 1:] if part.startswith(ROOT + ".") else None
            if bare is None or bare not in deck.parts:
                out.append(f"rule 3: {name} sets a material on {part!r}, which the deck lacks")
            elif not deck.parts[bare].elements:
                out.append(f"rule 3: {name} sets a material on {part!r}, which has no elements")
            ids.append(entry.get("properties_id"))
        duplicated = sorted({i for i in ids if ids.count(i) > 1})
        if duplicated:
            out.append(f"rule 4: {name} reuses properties_id {duplicated}")
    return out


# 5, 7. every part a stage names -- processes, activations, solver lists -- exists
def _references(deck, params) -> list[str]:
    known = set(deck.parts) | RUNTIME_PARTS
    out = []
    for stage, body in (params.get("stages") or {}).items():
        for path, name in _part_names(body, stage):
            bare = name[len(ROOT) + 1:] if name.startswith(ROOT + ".") else name
            if bare != ROOT and bare not in known:
                out.append(f"rule 5: {path} names {name!r}, which the deck lacks")
    return out


def _part_names(node, path):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}/{key}"
            if key in PART_KEYS and isinstance(value, str):
                yield here, value
            elif key in PART_LIST_KEYS and isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield here, item
            else:
                yield from _part_names(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _part_names(value, f"{path}[{index}]")


# 6. the run order and the stages are the same set, each once
def _stages(params) -> list[str]:
    order = ((params.get("orchestrator") or {}).get("settings") or {}).get("execution_list")
    stages = params.get("stages")
    if order is None and stages is None:
        return []
    order, stages = order or [], stages or {}
    out = []
    if len(order) != len(set(order)):
        out.append(f"rule 6: execution_list repeats a stage: {order}")
    if set(order) != set(stages):
        out.append(f"rule 6: execution_list {sorted(set(order))} and stages "
                   f"{sorted(stages)} differ")
    return out


# 8. no node is left out of every element and condition
def _orphans(deck) -> list[str]:
    used = {n for block in deck.elements + deck.conditions
            for nodes in block.entries.values() for n in nodes}
    orphans = sorted(set(deck.nodes) - used)
    return [f"rule 8: {len(orphans)} nodes belong to no element or condition, "
            f"e.g. {orphans[:5]}"] if orphans else []


def deck_dimension(deck) -> int:
    return 2 if all(abs(z) <= 1e-12 for _, _, z in deck.nodes.values()) else 3


# 9. element and condition names match the dimension of the deck
def _dimension(deck) -> list[str]:
    dimension = deck_dimension(deck)
    out = []
    for block in deck.elements + deck.conditions:
        token = DIMENSION_TOKEN.search(block.name)
        if token and int(token.group(1)) != dimension:
            out.append(f"rule 9: {block.name} in a {dimension}D deck")
    return out


# 10. in a section, line entities follow the soil's order (a truss is always 2-node)
def _order(deck) -> list[str]:
    if deck_dimension(deck) != 2:
        return []
    names = {block.name for block in deck.elements + deck.conditions}
    if SOIL_QUADRATIC in names and SOIL_LINEAR not in names:
        wrong = [n for n in names if "Truss" not in n
                 and (n.endswith("2D2N") or n.endswith("2Plus2N"))]
        return [f"rule 10: linear {n} in a quadratic section" for n in sorted(wrong)]
    if SOIL_LINEAR in names and SOIL_QUADRATIC not in names:
        wrong = [n for n in names if n != SOIL_LINEAR
                 and (n.endswith("2D3N") or n.endswith("3Plus3N"))]
        return [f"rule 10: quadratic {n} in a linear section" for n in sorted(wrong)]
    if SOIL_LINEAR in names and SOIL_QUADRATIC in names:
        return ["rule 10: linear and quadratic soil elements in one section"]
    return []


# 11. one unit system: nothing that carries a force or a mass reads like another system's
#
# The deck is in the project's system (`core/model/units.py`). A Young's modulus a thousand times
# too small for it, or a density a thousand times off either way, is a value typed in the
# wrong system -- the 1000x slip this deck once had in every number.
def _units(files, system: str = "SI") -> list[str]:
    from core.model import units
    least_modulus = units.from_si(1e3, units.STRESS, system)
    least_density = units.from_si(100.0, units.DENSITY, system)
    most_density = units.from_si(1e5, units.DENSITY, system)
    stress, density = units.label(units.STRESS, system), units.label(units.DENSITY, system)
    out = []
    for name, document in files.items():
        for entry in document.get("properties", []):
            variables = (entry.get("Material") or {}).get("Variables") or {}
            part = entry.get("model_part_name")
            modulus = variables.get("YOUNG_MODULUS")
            if isinstance(modulus, (int, float)) and modulus < least_modulus:
                out.append(f"rule 11: {name} {part} YOUNG_MODULUS {modulus} {stress} is "
                           f"too small for the {system} system")
            solid = variables.get("DENSITY_SOLID")
            if isinstance(solid, (int, float)) and solid > 0 and not (
                    least_density <= solid <= most_density):
                out.append(f"rule 11: {name} {part} DENSITY_SOLID {solid} {density} does "
                           f"not belong to the {system} system")
    return out


# 12. a K0 stage gives every soil it solves a K0_NC
def _k0(deck, params, files) -> list[str]:
    if not files:
        # `export_project(..., include_materials=False)`: a mesh exported for its numbering
        # (labels, node parts), which nobody runs. With no material file at all there is
        # nothing to check -- one present but not the one a stage reads still fails.
        return []
    out = []
    for stage, body in (params.get("stages") or {}).items():
        settings = body.get("stage_settings") or {}
        processes = [p for group in (settings.get("processes") or {}).values() for p in group]
        if not any(p.get("python_module") == "apply_k0_procedure_process" for p in processes):
            continue
        solver = settings.get("solver_settings") or {}
        material_file = (solver.get("material_import_settings") or {}).get("materials_filename")
        document = files.get(material_file)
        if document is None:
            out.append(f"rule 12: stage {stage} runs K0 on {material_file!r}, "
                       "which the export did not write")
            continue
        by_part = {e["model_part_name"]: (e.get("Material") or {}).get("Variables") or {}
                   for e in document.get("properties", [])}
        for part in solver.get("problem_domain_sub_model_part_list") or []:
            variables = by_part.get(f"{ROOT}.{part}")
            if variables is not None and "DENSITY_SOLID" in variables \
                    and "K0_NC" not in variables:
                out.append(f"rule 12: stage {stage} runs K0 but {part} has no K0_NC "
                           f"in {material_file}")
    return out


# 13. every condition is its element's own edge or face, in the element's own order
#
# Kratos finds a condition's element by comparing node-id sequences
# (GeoMechanicsApplication/custom_utilities/neighbouring_element_finder.hpp): a face may
# be *rotated*, a line not even that, and neither may be *reversed* -- a reversed one is
# "found without any corresponding element" and the run stops before its first step.
# The orders below are Kratos' own GenerateEdges / GenerateFaces (kratos/geometries/),
# written here independently of core.kratos.writer.
SOIL_EDGES = {3: ((0, 1), (1, 2), (2, 0)), 6: ((0, 1, 3), (1, 2, 4), (2, 0, 5))}
SOIL_FACES = {4: ((2, 3, 1), (0, 3, 2), (0, 1, 3), (0, 2, 1)),
              10: ((0, 2, 1, 6, 5, 4), (0, 3, 2, 7, 9, 6), (0, 1, 3, 4, 8, 7),
                   (2, 3, 1, 9, 8, 5))}


def _rotations(face: tuple[int, ...]) -> set[tuple[int, ...]]:
    corners = 3
    out = set()
    for k in range(corners):
        rotated = face[k:corners] + face[:k]
        if len(face) > corners:
            mid = face[corners:]
            rotated += mid[k:] + mid[:k]
        out.add(rotated)
    return out


def _condition_order(deck) -> list[str]:
    # The water pressure elements of a groundwater flow deck are soil too: a seepage
    # face is found by its element the same way.
    soil = [b for b in deck.elements
            if ("SmallStrain" in b.name or "SteadyStatePw" in b.name)
            and "Interface" not in b.name]
    dimension = deck_dimension(deck)
    allowed: set[tuple[int, ...]] = set()
    for block in soil:
        for row in block.entries.values():
            table = SOIL_EDGES if dimension == 2 else SOIL_FACES
            for local in table.get(len(row), ()):
                own = tuple(row[i] for i in local)
                allowed |= {own} if dimension == 2 else _rotations(own)
    # A line element is its own only edge: a load on a wall face, whose nodes the
    # interface split left to the beam alone, finds the beam (the test model's water
    # loads do).
    for block in deck.elements:
        if "Beam" in block.name:
            allowed |= {tuple(row) for row in block.entries.values()}
    # A line interface element has two edges, its two sides: the first half of its nodes
    # as written, the second half reversed (Kratos' interface_geometry.hpp,
    # GenerateTwoSides). A load drawn down a wall that was drawn up finds the contact
    # on the face it was drawn along.
    if dimension == 2:
        for block in deck.elements:
            if "LineInterface" not in block.name:
                continue
            for row in block.entries.values():
                half = len(row) // 2
                first, second = tuple(row[:half]), row[half:]
                allowed.add(first)
                allowed.add((second[1], second[0], *second[2:]))
    out = []
    for block in deck.conditions:
        rows = [r for r in block.entries.values() if len(r) > 1]
        wrong = [r for r in rows if tuple(r) not in allowed]
        if wrong:
            out.append(f"rule 13: {len(wrong)} of {len(rows)} {block.name} are not an edge or "
                       f"face of their element in its own order, e.g. {wrong[0]}")
    return out


# 14. the mesh is read once: by the first stage, never again
#
# A stage reads the .mdpa through its preprocess modeler or through its solver's
# `input_type: "mdpa"`. Twice in one stage adds every element a second time ("an element
# with the same Id already exists"); again in a later stage replaces the model and
# everything the stages before it did. A one-phase deck once did the first.
def _mesh_read_once(params) -> list[str]:
    order = ((params.get("orchestrator") or {}).get("settings") or {}).get("execution_list")
    if not order:
        return []
    out = []
    for index, name in enumerate(order):
        stage = params["stages"][name]
        modelers = (stage.get("stage_preprocess") or {}).get("modelers") or []
        solver = stage["stage_settings"]["solver_settings"]
        reads = sum(1 for m in modelers if "ImportMDPA" in m.get("name", "")) + int(
            (solver.get("model_import_settings") or {}).get("input_type") == "mdpa")
        wanted = 1 if index == 0 else 0
        if reads != wanted:
            out.append(f"rule 14: stage {name} reads the mesh {reads} times, not {wanted}")
    return out
