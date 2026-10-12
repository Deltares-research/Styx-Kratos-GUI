"""`node` and `deck show`: what a Kratos deck is made of, read off the deck itself.

`node` says which SubModelParts a node is in, by the number the `.mdpa` gives it -- what
the GUI's `node <id>` command and right-click say (`frontend/js/node-parts.js`). An
interface splits a node into two or three at one position, so the others there are
named too. `deck show` summarises a deck: its mesh, its SubModelParts and its stages.

Both read a deck directory, a `.mdpa` on its own, or a project: a project's answer is
read off the deck it would export (`core.gmsh_worker.node_parts_job`), so a part's name
and a node's number are exactly what Kratos is given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cli.commands.meshing import mesh_settings
from cli.output import Answer, CommandError
from core import gmsh_worker, session
from core.kratos import deck_files, external_deck, mdpa_reader, node_parts

DECIMALS = 6
"""Micrometres: closer than this is one position, which an interface split leaves."""


def register(commands, common: argparse.ArgumentParser) -> None:
    node = commands.add_parser(
        "node", parents=[common], help="which SubModelParts a node of the deck is in",
        description="Which SubModelParts each node is in, by the number the .mdpa gives "
                    "it. SOURCE is a deck directory, an .mdpa, or a project, whose deck "
                    "is written in memory to answer.")
    node.add_argument("source", type=Path)
    node.add_argument("nodes", nargs="+", type=int, metavar="NODE")
    # A project is a SOURCE too, so the shell gives `node` the open one (cli/shell.py).
    node.set_defaults(handler=show_nodes, project_slot="source")

    deck = commands.add_parser("deck", parents=[common], help="look into a Kratos deck")
    actions = deck.add_subparsers(dest="action", metavar="<action>", required=True)
    show = actions.add_parser(
        "show", parents=[common], help="a deck's mesh, SubModelParts and stages",
        description="Summarise a deck: a directory, its ProjectParameters.json, or an "
                    ".mdpa on its own (which has no stages).")
    show.add_argument("source", type=Path)
    show.set_defaults(handler=show_deck)


# ── node ────────────────────────────────────────────────────────────────────

def show_nodes(args: argparse.Namespace) -> Answer:
    payload = _node_parts(args.source)
    coordinates = {row[0]: row[1:] for row in payload["nodes"]}
    parts_of: dict[int, list[str]] = {node: [] for node in coordinates}
    for part in payload["parts"]:
        for node in part["nodes"]:
            if node in parts_of and part["name"] not in parts_of[node]:
                parts_of[node].append(part["name"])
    at: dict[str, list[int]] = {}
    for node, xyz in coordinates.items():
        at.setdefault(_position(xyz), []).append(node)

    answers, lines = [], []
    for node in args.nodes:
        if node not in coordinates:
            raise CommandError(f"Node {node} is not in this deck, which has "
                               f"{len(coordinates)} nodes (numbered as the .mdpa is "
                               "written).")
        twins = sorted(other for other in at[_position(coordinates[node])] if other != node)
        answers.append({"node": node, "at": list(coordinates[node]),
                        "parts": parts_of[node],
                        "same_position": [{"node": other, "parts": parts_of[other]}
                                          for other in twins]})
        lines += [f"Node {node} at {_where(coordinates[node])}",
                  f"  SubModelParts: {_parts(parts_of[node])}"]
        if twins:
            lines.append("  Same position (split by an interface):")
            lines += [f"    node {other}: {_parts(parts_of[other])}" for other in twins]
    return Answer(data=answers, lines=lines)


def _node_parts(source: Path) -> dict:
    mdpa = _mdpa_of(source)
    if mdpa is not None:
        return node_parts.node_parts(mdpa.read_text(encoding="utf-8", errors="replace"))
    project = session.load(source)
    if project.deck is not None:
        return node_parts.node_parts(_deck_mdpa(Path(project.deck.directory),
                                                project.deck.parameters)
                                     .read_text(encoding="utf-8", errors="replace"))
    return gmsh_worker.run_here(gmsh_worker.node_parts_job, project.model_dump_json(),
                                mesh_settings(project).model_dump_json())


def _position(xyz) -> str:
    return ",".join(f"{value:.{DECIMALS}f}" for value in xyz)


def _where(xyz) -> str:
    # A coordinate within half a millimetre of zero is zero, not "-0.000".
    return "(" + ", ".join(f"{value if abs(value) >= 5e-4 else 0.0:.3f}" for value in xyz) + ")"


def _parts(names: list[str]) -> str:
    return ", ".join(names) if names else "no SubModelPart"


# ── deck show ───────────────────────────────────────────────────────────────

def show_deck(args: argparse.Namespace) -> Answer:
    source = args.source
    stages = []
    if source.suffix.lower() == ".mdpa":
        if not source.is_file():
            raise CommandError(f"no such file: {source}")
        mdpa = source
    else:
        directory, parameters = _deck_location(source)
        project = external_deck.deck_project(directory, parameters)
        stages = project.phases
        mdpa = _deck_mdpa(directory, parameters)
    try:
        model = mdpa_reader.import_mdpa(mdpa.read_text(encoding="utf-8", errors="replace"))
    except mdpa_reader.ImportError_ as failure:
        raise CommandError(f"{mdpa.name}: {failure}") from None

    x0, y0, z0, x1, y1, z1 = model.bbox
    data = {"file": str(mdpa), "dimension": model.dimension, "bbox": list(model.bbox),
            "nodes": len(model.nodes),
            "elements": [entity.to_dict() for entity in model.elements],
            "conditions": [entity.to_dict() for entity in model.conditions],
            "parts": [part.to_dict() for part in model.parts.values()],
            "stages": [stage.model_dump(mode="json") for stage in stages]}
    extent = f"x {x0:g} .. {x1:g}, y {y0:g} .. {y1:g}" + (
        f", z {z0:g} .. {z1:g}" if model.dimension == 3 else "")
    lines = [f"{mdpa.name}: {model.dimension}D, {len(model.nodes)} nodes, {extent}"]
    for title, entities in (("elements", model.elements), ("conditions", model.conditions)):
        if entities:
            # One line per class: the deck writes a block per part, which says nothing
            # the SubModelParts below do not.
            counted: dict[tuple[str, str], int] = {}
            for entity in entities:
                key = (entity.kratos_class, entity.kind)
                counted[key] = counted.get(key, 0) + len(entity.entries)
            lines.append(f"  {title}:")
            lines += [f"    {count} {name} ({kind})" for (name, kind), count in counted.items()]
    lines.append(f"  {len(model.parts)} SubModelParts:")
    for part in model.parts.values():
        counts = [f"{len(part.nodes)} nodes"]
        counts += [f"{len(part.elements)} elements"] if part.elements else []
        counts += [f"{len(part.conditions)} conditions"] if part.conditions else []
        lines.append(f"    {part.name}  {part.kind}, {', '.join(counts)}")
    if stages:
        lines.append(f"  {len(stages)} stages:")
        for number, stage in enumerate(stages, start=1):
            change: list[str] = [stage.calculation]
            if stage.activate:
                change.append("activates " + ", ".join(stage.activate))
            if stage.deactivate:
                change.append("deactivates " + ", ".join(stage.deactivate))
            lines.append(f"    {number}  {stage.id}  " + "; ".join(change))
    return Answer(data=data, lines=lines)


# ── Finding the deck ────────────────────────────────────────────────────────

def _mdpa_of(source: Path) -> Path | None:
    """The `.mdpa` `source` is, or the one its deck reads; None for a project."""
    if source.suffix.lower() == ".mdpa":
        if not source.is_file():
            raise CommandError(f"no such file: {source}")
        return source
    if source.is_dir() or _is_parameters(source):
        return _deck_mdpa(*_deck_location(source))
    if not source.exists():
        raise CommandError(f"no such file or deck: {source}")
    return None


def _deck_location(source: Path) -> tuple[Path, str]:
    if source.is_dir():
        return source, deck_files.PARAMETERS_NAME
    if source.is_file():
        return source.parent, source.name
    raise CommandError(f"no such deck: {source}")


def _deck_mdpa(directory: Path, parameters: str) -> Path:
    deck = external_deck.deck_project(directory, parameters).deck
    if deck is None:        # a deck's own project always carries it
        raise CommandError(f"no deck in {directory}")
    return Path(deck.directory) / f"{external_deck.deck_name(deck)}.mdpa"


def _is_parameters(source: Path) -> bool:
    """Whether a `.json` is a deck's parameters rather than a project: it has stages."""
    if source.suffix.lower() != ".json" or not source.is_file():
        return False
    try:
        content = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(content, dict) and isinstance(content.get("stages"), dict)
