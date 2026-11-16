"""`mesh` and `export`: the model's mesh, and the Kratos deck written from it.

gmsh runs in this process (`core.gmsh_worker.run_here`): a command runs one job and
exits. The jobs are the ones the GUI's routes hand the worker, with the same settings
-- the project's own (`Project.mesh`) -- so the deck written here is the deck the GUI
exports for the same file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.terminal.files import add_project, add_writing, read, written
from cli.terminal.output import Answer, CommandError
from core import gmsh_worker, session
from core.analysis import calculation
from core.model.schemas import ExportRequest, MeshRequest, Project


def register(commands, common: argparse.ArgumentParser) -> None:
    mesh = commands.add_parser(
        "mesh", parents=[common], help="mesh the model and say how big the mesh is",
        description="Mesh the model with its own mesh settings. --size and --order "
                    "change those settings and keep them in the project.")
    add_project(mesh)
    mesh.add_argument("--size", type=float, help="the element size, in metres")
    mesh.add_argument("--order", type=int, choices=(1, 2), help="linear (1) or quadratic (2)")
    mesh.add_argument("--body-size", nargs=2, action="append", default=[],
                      metavar=("KEY", "SIZE"),
                      help="the element size at one object, by its key: a layer "
                           "(soil_<layer>) or soil body, a sheet pile, an anchor (at its "
                           "head), an interface, a normal load, a soil line, a load, a "
                           "boundary condition, or a face of the model (face_bottom, "
                           "face_left, face_right, face_top, and face_front, face_back "
                           "in 3D). A condition on a face takes the size of that face, "
                           "one on a soil part the size of that part. none takes the "
                           "size and its band away. Repeat for more")
    mesh.add_argument("--band", nargs=2, action="append", default=[],
                      metavar=("KEY", "BAND"),
                      help="the distance, in metres, over which the size of --body-size "
                           "grows back to the element size away from its object; none or "
                           "0 takes the band away. Repeat for more")
    add_writing(mesh)
    mesh.set_defaults(handler=mesh_model)

    export = commands.add_parser(
        "export", parents=[common], help="write the model's Kratos deck",
        description="Mesh the model and write its Kratos deck into a directory: the "
                    ".mdpa, MaterialParameters.json and ProjectParameters.json (with "
                    "initial_materials.json for a K0 stage). `kratos-cli run DIR` runs it.")
    add_project(export)
    export.add_argument("--out", type=Path, required=True, metavar="DIR",
                        help="the directory to write the deck into")
    export.add_argument("--name", help="what to name the deck's files (default: after the "
                                       "project), e.g. mesh for mesh.mdpa")
    export.set_defaults(handler=export_deck)


def mesh_model(args: argparse.Namespace) -> Answer:
    project = read(args)
    session.require_parametric(project, "meshed")
    changed = _with_settings(project, args)
    mesh = gmsh_worker.run_here(gmsh_worker.mesh_job, changed.model_dump_json(),
                                mesh_settings(changed).model_dump_json())
    _refuse_empty(changed, mesh["stats"])
    lines = [_stats_line(mesh["stats"])]
    target = None
    if changed != project:
        target, where = written(args, changed)
        lines.append(f"mesh settings kept: {where}")
    return Answer(data={"file": str(target) if target else None, "stats": mesh["stats"],
                        "meshed_keys": mesh["meshed_keys"], "bbox": mesh["bbox"]},
                  lines=lines)


def export_deck(args: argparse.Namespace) -> Answer:
    project = read(args)
    session.require_parametric(project, "exported")
    named = project.model_copy(update={"name": args.name}) if args.name else project
    export = exported(named)
    args.out.mkdir(parents=True, exist_ok=True)
    files = calculation.write_deck(export, args.out)
    return Answer(
        data={"directory": str(args.out), "deck_name": export["deck_name"],
              "files": files, "stats": export["stats"], "warnings": export["warnings"],
              "notes": export.get("notes", [])},
        lines=[f"wrote the Kratos deck {export['deck_name']} to {args.out}:",
               *(f"  {name}" for name in files),
               _stats_line(export["stats"]),
               f"next: kratos-cli run {args.out}"],
        warnings=export["warnings"], notes=export.get("notes", []))


def mesh_settings(project: Project) -> MeshRequest:
    """The project's own mesh settings as a request, refused if they name a body the
    model does not have -- as the routes refuse one (`session.unknown_mesh_keys`)."""
    settings = MeshRequest(**project.mesh.model_dump())
    unknown = session.unknown_mesh_keys(project, settings)
    if unknown:
        raise CommandError("the mesh settings name objects this model does not have: "
                           + ", ".join(unknown) + ". A size can be given to: "
                           + ", ".join(_offered_keys(project)) + ". Correct the name, "
                           f"or take the size away: kratos-cli mesh FILE --body-size "
                           f"{unknown[0]} none")
    return settings


def exported(project: Project) -> dict:
    """The deck of `project`, as `POST /api/export/mdpa` makes it: meshed with the
    project's own settings, the materials file included."""
    settings = ExportRequest(**mesh_settings(project).model_dump(), include_materials=True)
    export = gmsh_worker.run_here(gmsh_worker.export_job, project.model_dump_json(),
                                  settings.model_dump_json())
    _refuse_empty(project, export["stats"])
    return export


def nothing_to_mesh(project: Project) -> str | None:
    """Why `project` would mesh to nothing, or None (`session.nothing_to_mesh`), with
    the command that fixes it."""
    empty = session.nothing_to_mesh(project)
    return f"{empty} `layer add` adds a soil layer." if empty else None


def _refuse_empty(project: Project, stats: dict) -> None:
    """A mesh with no elements is refused, not reported: a deck of 0 nodes runs in
    Kratos without complaint and computes nothing."""
    if stats["elements"] == 0:
        raise CommandError(nothing_to_mesh(project) or "the mesh has no elements.")


def _with_settings(project: Project, args: argparse.Namespace) -> Project:
    if args.size is not None:
        project = session.with_value(project, "mesh.element_size", args.size)
    if args.order is not None:
        project = session.with_value(project, "mesh.order", args.order)
    sizes = dict(project.mesh.body_sizes)
    bands = dict(project.mesh.size_bands)
    for key, size in args.body_size:
        key = _size_key("--body-size", project, key)
        if size.lower() == "none":
            sizes.pop(key, None)
            bands.pop(key, None)
        else:
            sizes[key] = _number("--body-size", key, size)
    for key, band in args.band:
        key = _size_key("--band", project, key)
        value = 0.0 if band.lower() == "none" else _number("--band", key, band)
        if value == 0.0:
            bands.pop(key, None)
        elif key not in sizes:
            raise CommandError(f"--band {key}: give {key} a size first, with "
                               f"--body-size {key} SIZE")
        else:
            bands[key] = value
    if args.body_size or args.band:
        project = session.with_value(project, "mesh", {
            **project.mesh.model_dump(), "body_sizes": sizes, "size_bands": bands})
    return project


def _offered_keys(project: Project) -> list[str]:
    """The keys a new size can name in this dimension, as the GUI's Mesh properties
    window lists them (`Project.listed_mesh_size_keys`)."""
    return project.listed_mesh_size_keys()


def _size_key(option: str, project: Project, key: str) -> str:
    """The key the size of the object `key` is kept under (`Project.mesh_size_key_of`),
    as the Mesh group of the GUI's Selection explorer keeps it: a condition on a face
    takes the size of the face, one on a soil part the size of the part. One on the
    whole soil is refused: the whole soil is meshed at the element size."""
    sized = project.mesh_size_key_of(key)
    if sized is None:
        raise CommandError(f"{option} {key}: it acts on the whole soil, which is meshed at "
                           "the element size; change that with --size")
    return sized


def _number(option: str, key: str, text: str) -> float:
    try:
        return float(text)
    except ValueError:
        raise CommandError(f"{option} {key}: {text!r} is not a number or none") from None


def _stats_line(stats: dict) -> str:
    kinds = ", ".join(f"{count} {kind}" for kind, count in sorted(stats.get("by_type", {}).items()))
    return (f"{stats['nodes']} nodes, {stats['elements']} elements"
            + (f" ({kinds})" if kinds else ""))
