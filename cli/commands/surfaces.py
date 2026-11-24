"""`surface`: the soil surfaces of a 2D model, as Soil > Create soil surface… draws them.

A soil surface is an outline in the section's x-y plane with a material, for an
embankment, a cutting or a lens. It is the same record a 2D `volume add polygon` makes: the
outline swept across the whole model along z (`core.model.drafts.section_prism`), so the
GUI and `volume list` show it too. A line across it from one edge to another cuts it into
soil bodies (`<key>__part1`, ...), which `body` lists and names. A 3D model has soil
volumes instead: `volume add polygon ... --extrude`.

Coordinates are plain numbers, `--points 0 0 3 0 3 3 0 3`, or `--points @outline.csv`
with one point per line.
"""

from __future__ import annotations

import argparse
import json

from cli.terminal.files import read, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import action, coordinates, noun
from core import gmsh_worker, session
from core.model import drafts
from core.model.schemas import CustomPart, Project

DEFAULT_LABEL = "Soil surface"
"""What the GUI's window calls a surface whose name is left empty."""


def register(commands, common: argparse.ArgumentParser) -> None:
    surface = noun(commands, common, "surface",
                   "draw, change, list or remove the soil surfaces of a 2D model")
    action(surface, common, "list", list_surfaces, writes=False,
           help="the soil surfaces, and the soil bodies a line cut each into")
    add = action(surface, common, "add", add_surface,
                 help="draw a soil surface: its corners and its material")
    add.add_argument("--points", nargs="+", metavar="N", required=True,
                     help="the corners, x y ... in order, or @file with one point per line")
    add.add_argument("--material", required=True, help="the material it is made of")
    add.add_argument("--label", help=f"what to call it (default: {DEFAULT_LABEL})")
    change = action(surface, common, "set", update_surface,
                    help="change the corners, the material or the name of a soil surface")
    change.add_argument("key", help="the surface's key, as `surface list` shows it")
    change.add_argument("--points", nargs="+", metavar="N",
                        help="the new corners, x y ... in order, or @file")
    change.add_argument("--material", help="its new material, for every body of it too")
    change.add_argument("--label", help="what to call it")
    remove = action(surface, common, "remove", remove_surface,
                    help="remove a soil surface and the soil bodies cut from it")
    remove.add_argument("key", help="the surface's key, as `surface list` shows it")
    intersect = action(surface, common, "intersect", intersect_surfaces,
                       help="split two overlapping soil surfaces into the part of each "
                            "outside the other and the overlap, which takes the first's "
                            "material")
    intersect.add_argument("key", help="the surface whose material the overlap takes")
    intersect.add_argument("other", help="the surface it overlaps")


def _two_dimensional(project: Project) -> None:
    session.require_parametric(project, "drawn into")
    if project.dimension != 2:
        raise CommandError("a 3D model has soil volumes, not surfaces: use `volume add polygon "
                           "--points x y z ... --extrude dx dy dz`")


def _is_surface(part: CustomPart) -> bool:
    """A part the Create soil surface… window draws and edits: an outline swept along z
    with a material."""
    return (part.mat is not None and part.section_outline() is not None
            and part.recipe is not None and part.recipe.get("kind") == "polygon_extrude")


def _surfaces(project: Project) -> list[CustomPart]:
    return [part for part in project.custom_parts if _is_surface(part)]


def _surface(project: Project, key: str) -> CustomPart:
    found = next((part for part in _surfaces(project) if part.key == key), None)
    if found is None:
        listed = ", ".join(part.key for part in _surfaces(project)) or "none"
        raise CommandError(f"no soil surface {key!r} (the soil surfaces: {listed})")
    return found


def list_surfaces(args: argparse.Namespace) -> Answer:
    project = read(args)
    if project.dimension != 2:
        return Answer(data=[], lines=["No soil surfaces: a 3D model has soil volumes, which "
                                      "`volume list` lists."])
    pieces = {key: [body for body, *_ in project.soil_bodies()
                    if body.partition("__")[0] == key]
              for key in project.cut_parts()}
    rows, lines = [], []
    for part in _surfaces(project):
        outline = part.section_outline()
        assert outline is not None
        rows.append({"key": part.key, "label": part.label, "material": part.mat,
                     "points": [list(point) for point in outline[0]],
                     "bodies": pieces.get(part.key, [])})
        lines.append(f"{part.key}  {part.label}  ·  {project.material(str(part.mat)).name}: "
                     + " .. ".join(f"{x:g},{y:g}" for x, y in outline[0])
                     + (f"  (cut into {', '.join(pieces[part.key])})"
                        if part.key in pieces else ""))
    return Answer(data=rows, lines=lines or ["No soil surfaces yet."])


def add_surface(args: argparse.Namespace) -> Answer:
    project = read(args)
    _two_dimensional(project)
    recipe = drafts.section_prism(project, coordinates(args.points, 2))
    recipe["label"] = args.label if args.label is not None else DEFAULT_LABEL
    recipe["material"] = args.material
    project, part = _built(project, recipe)
    return _answer(args, project, part.key, "added")


def update_surface(args: argparse.Namespace) -> Answer:
    project = read(args)
    _two_dimensional(project)
    part = _surface(project, args.key)
    outline = part.section_outline()
    assert outline is not None
    points = coordinates(args.points, 2) if args.points is not None else list(outline[0])
    recipe = drafts.section_prism(project, points)
    recipe["label"] = args.label if args.label is not None else part.label
    recipe["material"] = args.material if args.material is not None else part.mat
    recipe["replace"] = part.key
    project, part = _built(project, recipe)
    return _answer(args, project, part.key, "changed")


def remove_surface(args: argparse.Namespace) -> Answer:
    project = read(args)
    _two_dimensional(project)
    _surface(project, args.key)
    project = session.without_custom_part(project, args.key)
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None},
                  lines=[f"removed soil surface {args.key}; {where}"])


def intersect_surfaces(args: argparse.Namespace) -> Answer:
    project = read(args)
    _two_dimensional(project)
    first, second = _surface(project, args.key), _surface(project, args.other)
    plan = session.intersection_plan(project, first.key, second.key)
    try:
        built = [gmsh_worker.run_here(gmsh_worker.create_job, json.dumps(recipe))
                 for recipe, _ in plan]
    except ValueError as failure:
        raise CommandError(str(failure)) from None
    before = {part.key for part in project.custom_parts}
    project = session.with_intersection(project, plan, built)
    made = [part for part in project.custom_parts
            if part.key not in before or part.key in (first.key, second.key)]
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None,
                        "parts": [part.model_dump(mode="json") for part in made]},
                  lines=[f"intersected {first.label} with {second.label}: "
                         + ", ".join(part.label for part in made) + f"; {where}"])


def _built(project: Project, recipe: dict) -> tuple[Project, CustomPart]:
    """`project` with the surface gmsh built from `recipe`, as the GUI's window sends it."""
    session.check_recipe(project, recipe)
    try:
        built = gmsh_worker.run_here(gmsh_worker.create_job, json.dumps(recipe))
    except ValueError as failure:
        # `core.geometry.primitives` says what it cannot build, and why.
        raise CommandError(str(failure)) from None
    return session.with_created_part(project, recipe, built)


def _answer(args: argparse.Namespace, project: Project, key: str, done: str) -> Answer:
    part = next(p for p in project.custom_parts if p.key == key)
    target, where = written(args, project)
    notes = [f"{part.label} is cut into "
             + ", ".join(body for body, *_ in project.soil_bodies()
                         if body.partition("__")[0] == key)
             + "; `body list` names them"] if key in project.cut_parts() else []
    return Answer(data={"file": str(target) if target else None,
                        "part": part.model_dump(mode="json"), "notes": notes},
                  lines=[f"{done} soil surface {key} ({part.label}, "
                         f"{project.material(str(part.mat)).name}); {where}", *notes])
