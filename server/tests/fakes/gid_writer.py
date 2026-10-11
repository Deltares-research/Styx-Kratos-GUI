"""Synthetic GiD output for an exported deck (plan alpha 2.4).

`write_run(export, directory, fields)` lays out a run directory the way a Kratos run
leaves one: the deck as `app.calculate.write_deck` writes it, then one `.post.msh` and
one `.post.res` per stage, named by the stage's own `output_name`. The numbers are
analytic functions of the coordinates, chosen by the caller, so a test can say exactly
what every node and element should read back as.

What a real run does that this copies, because the reader depends on it:

* each stage's mesh holds only the elements *active* in that stage -- derived here the
  way Kratos derives it, by applying every stage's `stage_preprocess` activate and
  deactivate operations in turn;
* interface elements are written in no stage (the GiD writer does not emit them);
* nodal fields are written per active node, Gauss fields per element and point, under a
  `GaussPoints` declaration per element type;
* with `steps > 1`, each field is written once per step at increasing time, the way a
  stage cut on non-convergence writes it -- the last step is the stage's result.

It is a test double, not a GiD writer: the format is exactly as much of GiD's as
`app.gid_results` reads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from app import calculate
from tests import mdpa

Nodal = Callable[[float, float, float, int], tuple[float, ...]]
"""(x, y, z, stage index) -> the components at that node."""

GID_TYPES = {"2D3N": ("Triangle", 3, 3), "2D6N": ("Triangle", 6, 3),
             "3D4N": ("Tetrahedra", 4, 4), "3D10N": ("Tetrahedra", 10, 4),
             "2D2N": ("Linear", 2, 2), "3D2N": ("Linear", 2, 2),
             "2D3N_LINE": ("Linear", 3, 2), "3D3N": ("Triangle", 3, 3)}


def gid_type(kratos_class: str) -> tuple[str, int, int] | None:
    """GiD's element type, node count and Gauss point count for a Kratos class, or
    None for what the GiD writer leaves out."""
    if "Interface" in kratos_class:
        return None
    for token in ("2D10N", "3D10N", "2D6N", "3D4N", "3D3N", "2D3N", "2D2N", "3D2N"):
        if kratos_class.endswith(token):
            if token == "2D3N" and ("Beam" in kratos_class or "Line" in kratos_class):
                return GID_TYPES["2D3N_LINE"]
            return GID_TYPES.get(token)
    return None


def active_elements(deck: mdpa.Deck, params: dict) -> dict[str, set[int]]:
    """Stage name -> the element ids active in it, by Kratos' own rule: everything
    starts active, and each stage's preprocess operations switch parts off and on."""
    active = set(deck.element_ids())
    out = {}
    for stage in params["orchestrator"]["settings"]["execution_list"]:
        body = params["stages"][stage]
        for operation in (body.get("stage_preprocess") or {}).get("operations") or []:
            names = (operation.get("Parameters") or {}).get("model_part_name_list") or []
            parts = [deck.parts[n.split(".", 1)[1]] for n in names
                     if "." in n and n.split(".", 1)[1] in deck.parts]
            elements = {e for p in parts for e in p.elements}
            if "Deactivate" in operation.get("name", ""):
                active -= elements
            elif "Activate" in operation.get("name", ""):
                active |= elements
        out[stage] = set(active)
    return out


def output_base(stage_body: dict, stage: str) -> str:
    try:
        name = stage_body["stage_settings"]["output_processes"]["gid_output"][0][
            "Parameters"]["output_name"]
        return Path(name.replace("\\", "/")).name
    except (KeyError, IndexError, TypeError):
        return stage_body["stage_settings"]["problem_data"]["problem_name"]


def _mesh_text(deck: mdpa.Deck, active: set[int]) -> str:
    lines, first = [], True
    for index, block in enumerate(deck.elements):
        kind = gid_type(block.name)
        if kind is None:
            continue
        ids = [e for e in block.entries if e in active]
        if not ids:
            continue
        gid, nnode, _ = kind
        dimension = 3 if "3D" in block.name else 2
        lines.append(f'MESH "Kratos_{block.name}_Mesh_{index}" dimension {dimension} '
                     f'ElemType {gid} Nnode {nnode}')
        if first:
            lines.append("Coordinates")
            lines += [f"{n} {x!r} {y!r} {z!r}" for n, (x, y, z) in sorted(deck.nodes.items())]
            lines.append("End Coordinates")
            first = False
        lines.append("Elements")
        lines += [" ".join(str(v) for v in [e, *block.entries[e][:nnode], 0]) for e in ids]
        lines.append("End Elements")
    return "\n".join(lines) + "\n"


def _results_text(deck: mdpa.Deck, active: set[int], stage_index: int,
                  nodal: dict[str, Nodal], gauss: dict[str, Nodal], steps: int) -> str:
    used = {n for block in deck.elements if gid_type(block.name)
            for e in block.entries if e in active for n in block.entries[e]}
    lines = ["GiD Post Results File 1.0"]
    sets = {}
    for block in deck.elements:
        kind = gid_type(block.name)
        if kind is None or kind[0] == "Linear":
            continue
        name = f"{block.name}_gp"
        # One Gauss set per element class, over every block of that class: a deck has a
        # block per part, and the class's set covers all of them, as Kratos writes it.
        if name in sets:
            sets[name][0].append(block)
            continue
        sets[name] = ([block], kind)
        lines += [f'GaussPoints "{name}" ElemType {kind[0]}',
                  f"Number Of Gauss Points: {kind[2]}", "Natural Coordinates: Internal",
                  "End GaussPoints"]
    for step in range(1, steps + 1):
        time = step / steps
        weight = step / steps          # earlier steps are partial: only the last is whole
        for variable, function in nodal.items():
            sample = function(0.0, 0.0, 0.0, stage_index)
            kind = "Scalar" if len(sample) == 1 else "Vector"
            lines.append(f'Result "{variable}" "Kratos" {time!r} {kind} OnNodes')
            lines.append("Values")
            for n in sorted(used):
                x, y, z = deck.nodes[n]
                values = [v * weight for v in function(x, y, z, stage_index)]
                lines.append(" ".join([str(n)] + [repr(v) for v in values]))
            lines.append("End Values")
        for variable, function in gauss.items():
            for name, (blocks, kind) in sets.items():
                entries = {e: nodes for block in blocks
                           for e, nodes in block.entries.items() if e in active}
                lines.append(f'Result "{variable}" "Kratos" {time!r} Matrix '
                             f'OnGaussPoints "{name}"')
                lines.append("Values")
                for e, nodes in entries.items():
                    corners = nodes[:kind[2]]
                    cx = sum(deck.nodes[n][0] for n in corners) / len(corners)
                    cy = sum(deck.nodes[n][1] for n in corners) / len(corners)
                    cz = sum(deck.nodes[n][2] for n in corners) / len(corners)
                    row = [repr(v * weight) for v in function(cx, cy, cz, stage_index)]
                    lines.append(" ".join([str(e)] + row))
                    lines += [" ".join(row)] * (kind[2] - 1)
                lines.append("End Values")
    return "\n".join(lines) + "\n"


def write_run(export: dict, directory: Path, nodal: dict[str, Nodal],
              gauss: dict[str, Nodal] | None = None, steps: int = 1,
              through: int | None = None) -> dict[str, set[int]]:
    """Write the deck and synthetic results for its stages into `directory`.

    `through` stops after that many stages, the way a run that failed in the next one
    leaves its directory. Returns stage name -> active element ids, for the test to
    compare against.
    """
    directory.mkdir(parents=True, exist_ok=True)
    calculate.write_deck(export, directory)
    deck = mdpa.parse(export["mdpa"])
    params = json.loads(export["project_parameters"])
    active = active_elements(deck, params)
    order = params["orchestrator"]["settings"]["execution_list"]
    for index, stage in enumerate(order[:through] if through else order, start=1):
        base = output_base(params["stages"][stage], stage)
        (directory / f"{base}.post.msh").write_text(_mesh_text(deck, active[stage]),
                                                     encoding="utf-8")
        (directory / f"{base}.post.res").write_text(
            _results_text(deck, active[stage], index, nodal, gauss or {}, steps),
            encoding="utf-8")
    return active
