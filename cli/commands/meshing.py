"""`mesh` and `export`: the model's mesh, and the Kratos deck written from it.

gmsh runs in this process (`core.gmsh_worker.run_here`): a command runs one job and
exits. The jobs are the ones the GUI's routes hand the worker, with the same settings
-- the project's own (`Project.mesh`) -- so the deck written here is the deck the GUI
exports for the same file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.files import add_project, add_writing, written
from cli.output import Answer, CommandError
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
    project = session.load(args.project)
    session.require_parametric(project, "meshed")
    changed = _with_settings(project, args)
    mesh = gmsh_worker.run_here(gmsh_worker.mesh_job, changed.model_dump_json(),
                                mesh_settings(changed).model_dump_json())
    lines = [_stats_line(mesh["stats"])]
    target = None
    if changed != project:
        target, where = written(args, changed)
        lines.append(f"mesh settings kept: {where}")
    return Answer(data={"file": str(target) if target else None, "stats": mesh["stats"],
                        "meshed_keys": mesh["meshed_keys"], "bbox": mesh["bbox"]},
                  lines=lines)


def export_deck(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    session.require_parametric(project, "exported")
    named = project.model_copy(update={"name": args.name}) if args.name else project
    export = exported(named)
    args.out.mkdir(parents=True, exist_ok=True)
    files = calculation.write_deck(export, args.out)
    return Answer(
        data={"directory": str(args.out), "deck_name": export["deck_name"],
              "files": files, "stats": export["stats"], "warnings": export["warnings"]},
        lines=[f"wrote the Kratos deck {export['deck_name']} to {args.out}:",
               *(f"  {name}" for name in files),
               _stats_line(export["stats"]),
               f"next: kratos-cli run {args.out}"],
        warnings=export["warnings"])


def mesh_settings(project: Project) -> MeshRequest:
    """The project's own mesh settings as a request, refused if they name a body the
    model does not have -- as the routes refuse one (`session.unknown_mesh_keys`)."""
    settings = MeshRequest(**project.mesh.model_dump())
    unknown = session.unknown_mesh_keys(project, settings)
    if unknown:
        raise CommandError("the mesh settings name bodies this model does not have: "
                           + ", ".join(unknown))
    return settings


def exported(project: Project) -> dict:
    """The deck of `project`, as `POST /api/export/mdpa` makes it: meshed with the
    project's own settings, the materials file included."""
    settings = ExportRequest(**mesh_settings(project).model_dump(), include_materials=True)
    return gmsh_worker.run_here(gmsh_worker.export_job, project.model_dump_json(),
                                settings.model_dump_json())


def _with_settings(project: Project, args: argparse.Namespace) -> Project:
    if args.size is not None:
        project = session.with_value(project, "mesh.element_size", args.size)
    if args.order is not None:
        project = session.with_value(project, "mesh.order", args.order)
    return project


def _stats_line(stats: dict) -> str:
    kinds = ", ".join(f"{count} {kind}" for kind, count in sorted(stats.get("by_type", {}).items()))
    return (f"{stats['nodes']} nodes, {stats['elements']} elements"
            + (f" ({kinds})" if kinds else ""))
