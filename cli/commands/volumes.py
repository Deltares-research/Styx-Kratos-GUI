"""`volume`: solids drawn or imported into the model -- an embankment, a fill, a block.

A volume given a material is soil: it takes the material's colour and is meshed as a soil
body. In a 2D model a volume is an outline in the section's x-y plane, swept across the
whole model along z (`core.model.drafts.section_prism`), as the GUI's soil-volume dialog
draws it; in 3D it is a polygon extruded through space, a box or a cylinder. gmsh builds
the solid in this process (`core.gmsh_worker.run_here`), and `core.session` adds it.

Coordinates are plain numbers, `--points 0 0 6 0 3 2`, because a shell word that starts
with a minus -- `-3,2` -- would be read as an option. A long outline can come from a
file: `--points @outline.csv`, one point per line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cli.terminal.files import add_project, add_writing, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import coordinates
from core import gmsh_worker, session
from core.geometry.cad_import import CAD_EXTENSIONS, MESH_EXTENSIONS
from core.model import drafts
from core.model.schemas import Project

IMPORTABLE = sorted(CAD_EXTENSIONS) + sorted(MESH_EXTENSIONS)


def register(commands, common: argparse.ArgumentParser) -> None:
    volume = commands.add_parser("volume", parents=[common],
                                 help="draw, import, list or remove solids in the model")
    add_project(volume)
    actions = volume.add_subparsers(dest="action", metavar="<action>", required=True)

    listed = actions.add_parser("list", parents=[common], help="the drawn and imported solids")
    listed.set_defaults(handler=list_volumes)

    add = actions.add_parser(
        "add", parents=[common], help="draw a solid",
        description="Draw a solid. polygon: in 2D, --points x y ... in the section plane; "
                    "in 3D, --points x y z ... and --extrude dx dy dz. box: --origin and "
                    "--size. cylinder: --center, --axis and --radius.")
    add.add_argument("kind", choices=("polygon", "box", "cylinder"))
    add.add_argument("--points", nargs="+", metavar="N",
                     help="the corners as plain numbers, or @file with one point per line")
    add.add_argument("--extrude", type=float, nargs=3, metavar=("DX", "DY", "DZ"))
    add.add_argument("--origin", type=float, nargs=3, metavar=("X", "Y", "Z"))
    add.add_argument("--size", type=float, nargs=3, metavar=("DX", "DY", "DZ"))
    add.add_argument("--center", type=float, nargs=3, metavar=("X", "Y", "Z"))
    add.add_argument("--axis", type=float, nargs=3, metavar=("DX", "DY", "DZ"))
    add.add_argument("--radius", type=float)
    _part_fields(add)
    add_writing(add)
    add.set_defaults(handler=add_volume)

    imported = actions.add_parser("import", parents=[common], help="import a CAD solid",
                                  description="Import solids from " + ", ".join(IMPORTABLE))
    imported.add_argument("file", type=Path)
    _part_fields(imported)
    add_writing(imported)
    imported.set_defaults(handler=import_volume)

    remove = actions.add_parser("remove", parents=[common], help="remove one solid")
    remove.add_argument("key")
    add_writing(remove)
    remove.set_defaults(handler=remove_volume)

    clear = actions.add_parser("clear", parents=[common], help="remove every solid")
    add_writing(clear)
    clear.set_defaults(handler=clear_volumes)


def _part_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--label", help="what to call it")
    parser.add_argument("--material", help="make it soil of this material")


def list_volumes(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    rows = [part.model_dump(mode="json") for part in project.custom_parts]
    lines = [f"{part.key}  {part.label}  "
             + (f"soil of {part.mat}" if part.mat else "display only")
             + f"  ({part.recipe['kind'] if part.recipe else 'imported'})"
             for part in project.custom_parts]
    return Answer(data=rows, lines=lines or ["No drawn or imported solids."])


def add_volume(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    session.require_parametric(project, "drawn into")
    recipe = _recipe(project, args)
    session.check_recipe(project, recipe)
    try:
        built = gmsh_worker.run_here(gmsh_worker.create_job, json.dumps(recipe))
    except ValueError as failure:
        # `core.geometry.primitives` says what it cannot build, and why.
        raise CommandError(str(failure)) from None
    project, part = session.with_created_part(project, recipe, built)
    return _added(args, project, part.key)


def import_volume(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    session.require_parametric(project, "drawn into")
    extension = args.file.suffix.lower()
    if extension not in IMPORTABLE:
        raise CommandError(f"{args.file.name} is not a file this importer reads: use "
                           + ", ".join(IMPORTABLE) + ".")
    if not args.file.is_file():
        raise CommandError(f"no such file: {args.file}")
    built = gmsh_worker.run_here(gmsh_worker.import_job, str(args.file.resolve()), extension)
    project, part = session.with_imported_part(project, args.file.name, built,
                                               source=args.file)
    if args.label is not None:
        project = session.with_value(project, f"custom_parts[{part.key}].label", args.label)
    if args.material is not None:
        project = session.assign_part_material(project, part.key, args.material)
    return _added(args, project, part.key)


def remove_volume(args: argparse.Namespace) -> Answer:
    project = session.without_custom_part(session.load(args.project), args.key)
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None},
                  lines=[f"removed {args.key}; {where}"])


def clear_volumes(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    project = session.without_custom_parts(project, [p.key for p in project.custom_parts])
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None},
                  lines=[f"removed every drawn and imported solid; {where}"])


def _added(args: argparse.Namespace, project: Project, key: str) -> Answer:
    part = next(p for p in project.custom_parts if p.key == key)
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None,
                        "part": part.model_dump(mode="json")},
                  lines=[f"added {key} ({part.label}"
                         + (f", soil of {part.mat}" if part.mat else "") + f"); {where}"])


def _recipe(project: Project, args: argparse.Namespace) -> dict:
    """What `core.geometry.primitives` builds, from the command line, with the label and
    the material riding along as the GUI's dialogs send them."""
    if args.kind == "polygon":
        if project.dimension == 2:
            if args.extrude is not None:
                raise CommandError("a 2D volume is swept across the whole model, so it "
                                   "takes no --extrude; give its outline with --points x y ...")
            recipe = drafts.section_prism(project, coordinates(args.points, 2))
        else:
            if args.extrude is None:
                raise CommandError("a 3D polygon needs --extrude dx dy dz")
            recipe = {"kind": "polygon_extrude",
                      "vertices": [list(p) for p in coordinates(args.points, 3)],
                      "extrusion": list(args.extrude)}
    elif args.kind == "box":
        _need(args, "origin", "size")
        recipe = {"kind": "box", "origin": list(args.origin), "size": list(args.size)}
    else:
        _need(args, "center", "axis", "radius")
        recipe = {"kind": "cylinder", "center": list(args.center), "axis": list(args.axis),
                  "radius": args.radius}
    if args.label is not None:
        recipe["label"] = args.label
    if args.material is not None:
        recipe["material"] = args.material
    return recipe


def _need(args: argparse.Namespace, *names: str) -> None:
    missing = [f"--{name}" for name in names if getattr(args, name) is None]
    if missing:
        raise CommandError(f"a {args.kind} needs " + " and ".join(missing))
