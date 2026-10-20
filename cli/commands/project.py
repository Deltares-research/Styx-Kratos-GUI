"""`new`, `show`, `check`, `build`, `dimension`, `units`, `water`: the project file, and
the edits that have a command of their own because they carry the rest of the model
with them (`core.session.set_dimension`, `set_units`, `set_water_level`)."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands.meshing import nothing_to_mesh
from cli.terminal.files import add_project, add_writing, written
from cli.terminal.output import Answer, CommandError
from core import session
from core.model import phases
from core.model.schemas import DimensionUpdate, MeshRequest, Project, UnitsUpdate
from core.model.templates import blank_project, seed_project

REMOVE = ("off", "none", "remove")
"""What `water` takes for "no water level", as the GUI's `water` command does."""


def register(commands, common: argparse.ArgumentParser) -> None:
    new = commands.add_parser("new", parents=[common], help="start a project file",
                              description="Write a new project file: an empty site, or "
                                          "the demo model with --demo.")
    new.add_argument("path", type=Path, help="the project file to write (.json)")
    new.add_argument("--dim", type=int, choices=(2, 3),
                     help="2 for a plane-strain section (the default), 3 for a solid model")
    new.add_argument("--units", choices=("SI", "kN"), help="the unit system (default SI)")
    new.add_argument("--name", help="the project's name, which also names its deck")
    new.add_argument("--demo", action="store_true", help="start from the demo model")
    new.add_argument("--force", action="store_true", help="replace a file that is there")
    new.set_defaults(handler=new_project)

    show = commands.add_parser("show", parents=[common], help="say what a model is")
    add_project(show)
    show.set_defaults(handler=show_project)

    check = commands.add_parser("check", parents=[common],
                                help="check that a model can be meshed and staged")
    add_project(check)
    check.set_defaults(handler=check_project)

    build = commands.add_parser("build", parents=[common],
                                help="write the project a model script describes")
    build.add_argument("script", type=Path, help="the model script (.py)")
    build.add_argument("--out", type=Path, required=True, metavar="FILE",
                       help="the project file to write (.json)")
    build.set_defaults(handler=build_project)

    script = commands.add_parser(
        "script", parents=[common], help="write the model as a Python file that builds it",
        description="Write the model as one model script: the Python file that builds it "
                    "again, every value typed out. `run FILE` opens it in the GUI, every "
                    "command that reads a model takes it, and `python FILE --out DIR` "
                    "writes its Kratos deck.")
    add_project(script)
    script.add_argument("--out", type=Path, required=True, metavar="FILE",
                        help="the model script to write (.py)")
    script.add_argument("--force", action="store_true", help="replace a file that is there")
    script.set_defaults(handler=write_script)

    dimension = commands.add_parser(
        "dimension", parents=[common], help="switch between 2D and 3D",
        description="Switch between the plane-strain section and the solid model. "
                    "Loads, walls and soil laws are translated with it.")
    add_project(dimension)
    dimension.add_argument("to", choices=("2", "3", "2d", "3d"), type=str.lower)
    dimension.add_argument("--offset", type=float,
                           help="where the 2D section is cut, as a world z (default: "
                                "the middle of the domain)")
    add_writing(dimension)
    dimension.set_defaults(handler=switch_dimension)

    unit = commands.add_parser("units", parents=[common],
                               help="show the unit system, or convert to another")
    add_project(unit)
    unit.add_argument("system", nargs="?", choices=("SI", "kN"))
    add_writing(unit)
    unit.set_defaults(handler=switch_units)

    water = commands.add_parser("water", parents=[common],
                                help="show, set or remove the water level")
    add_project(water)
    water.add_argument("level", nargs="?",
                       help="the phreatic level y in metres, or off to remove it")
    add_writing(water)
    water.set_defaults(handler=set_water)


# ── The project file ────────────────────────────────────────────────────────

def new_project(args: argparse.Namespace) -> Answer:
    if args.path.exists() and not args.force:
        raise CommandError(f"{args.path} is already there. Give --force to replace it.")
    project = seed_project() if args.demo else blank_project()
    notes: list[str] = []
    if args.dim is not None and args.dim != project.dimension:
        project, notes = session.set_dimension(project, DimensionUpdate(dimension=args.dim))
    if args.units is not None and args.units != project.unit_system:
        project, more = session.set_units(project, UnitsUpdate(unit_system=args.units))
        notes += more
    if args.name is not None:
        project = session.with_value(project, "name", args.name)
    session.save(project, args.path)
    return Answer(data={"file": str(args.path), **summary(project)},
                  lines=[f"wrote {args.path}: {headline(project)}", *notes])


def show_project(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    data = {"file": str(args.project), **summary(project)}
    return Answer(data=data, lines=described(data))


def check_project(args: argparse.Namespace) -> Answer:
    """What the schema cannot say on its own: that there is something to mesh, that the
    phases run in one order, and that the mesh settings name only bodies the model has.
    Loading has validated the rest."""
    project = session.load(args.project)
    if project.deck is None:
        empty = nothing_to_mesh(project)
        if empty:
            raise CommandError(empty)
        phases.linearise(project)
        unknown = session.unknown_mesh_keys(project, MeshRequest(**project.mesh.model_dump()))
        if unknown:
            raise CommandError("the mesh settings name bodies this model does not have: "
                               + ", ".join(unknown))
    return Answer(data={"ok": True, "file": str(args.project), **summary(project)},
                  lines=[f"ok: {headline(project)}"])


def build_project(args: argparse.Namespace) -> Answer:
    if args.script.suffix.lower() != ".py":
        raise CommandError(f"{args.script} is not a model script (.py).")
    project = session.load(args.script)
    session.save(project, args.out)
    return Answer(data={"file": str(args.out), **summary(project)},
                  lines=[f"wrote {args.out}: {headline(project)}"])


def write_script(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    session.write_script(project, args.out, force=args.force, source=args.project)
    return Answer(data={"file": str(args.out), **summary(project)},
                  lines=[f"wrote {args.out}: {headline(project)}",
                         f"next: run {args.out.name} in the GUI's command box, or "
                         f"python {args.out.name} --out deck/"])


# ── The edits with a command of their own ───────────────────────────────────

def switch_dimension(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    project, notes = session.set_dimension(project, DimensionUpdate(
        dimension=2 if args.to[0] == "2" else 3, section_offset=args.offset))
    target, where = written(args, project)
    return Answer(data={"file": _file(target), "dimension": project.dimension,
                        "section_offset": project.section_offset, "notes": notes},
                  lines=[f"{headline(project)}; {where}", *notes])


def switch_units(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    if args.system is None:
        return Answer(data={"unit_system": project.unit_system},
                      lines=[f"{project.name} is in {project.unit_system} units."])
    project, notes = session.set_units(project, UnitsUpdate(unit_system=args.system))
    target, where = written(args, project)
    return Answer(data={"file": _file(target), "unit_system": project.unit_system,
                        "notes": notes},
                  lines=[f"{project.name} is now in {project.unit_system} units; {where}",
                         *notes])


def set_water(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    if args.level is None:
        return Answer(data={"water": _water(project)}, lines=[_water_line(project)])
    if args.level.lower() in REMOVE:
        level = None
    else:
        try:
            level = float(args.level)
        except ValueError:
            raise CommandError(f"{args.level!r} is not a water level. Give the level in "
                               "metres, e.g. -1.5, or off to remove it.") from None
    project = session.set_water_level(project, level)
    target, where = written(args, project)
    return Answer(data={"file": _file(target), "water": _water(project)},
                  lines=[f"{_water_line(project)} {where}"])


# ── Saying what a model is ──────────────────────────────────────────────────

def summary(project: Project) -> dict:
    """What `show` says, as data: the counts and the names a next command needs."""
    return {
        "name": project.name,
        "dimension": project.dimension,
        "unit_system": project.unit_system,
        "section_offset": project.section_offset if project.dimension == 2 else None,
        "domain": project.domain.model_dump(mode="json"),
        "boreholes": [b.id for b in project.boreholes],
        "materials": [m.id for m in project.materials],
        "layers": [layer.id for layer in project.layers],
        "bodies": project.soil_body_keys,
        "parts": project.part_keys(),
        "structures": {"beams": len(project.beams), "anchors": len(project.anchors),
                       "interfaces": len(project.interfaces), "loads": len(project.loads),
                       "normal_loads": len(project.normal_loads)},
        "custom_parts": [p.key for p in project.custom_parts],
        "water": _water(project),
        "phases": [p.id for p in project.phases],
        "mesh": {"element_size": project.mesh.element_size, "order": project.mesh.order},
        "deck": project.deck.directory if project.deck is not None else None,
    }


def headline(project: Project) -> str:
    kind = (f"2D section at z = {project.section_offset:g}" if project.dimension == 2
            and project.section_offset is not None else
            "2D section" if project.dimension == 2 else "3D solid model")
    return f"{project.name} ({kind}, {project.unit_system})"


def described(data: dict) -> list[str]:
    def names(values: list) -> str:
        return ", ".join(values) if values else "none"

    domain = data["domain"]
    structures = ", ".join(f"{count} {kind.replace('_', ' ')}"
                           for kind, count in data["structures"].items())
    water = data["water"]
    lines = [
        f"{data['name']}  ({data['file']})",
        f"  {'2D plane strain' if data['dimension'] == 2 else '3D solid'}, "
        f"{data['unit_system']} units"
        + (f", section at z = {data['section_offset']:g}"
           if data["section_offset"] is not None else ""),
        f"  domain      x {domain['x0']:g} .. {domain['x1']:g}, "
        f"y {domain['y_bottom']:g} .. {domain['y_top']:g}, "
        f"z {domain['z0']:g} .. {domain['z1']:g}",
        f"  boreholes   {names(data['boreholes'])}",
        f"  materials   {names(data['materials'])}",
        f"  layers      {names(data['layers'])}",
        f"  parts       {names(data['parts'])}",
        f"  structures  {structures}",
        f"  water       {'none' if water is None else format(water['y'], '.2f') + ' m'}",
        f"  phases      {names(data['phases'])}",
        f"  mesh        element size {data['mesh']['element_size']:g}, "
        f"order {data['mesh']['order']}",
    ]
    if data["deck"]:
        lines.append(f"  deck        {data['deck']}")
    return lines


def _water(project: Project) -> dict | None:
    return project.water.model_dump(mode="json") if project.water is not None else None


def _water_line(project: Project) -> str:
    if project.water is None:
        return "No water level."
    return (f"Water level: {project.water.y:.2f} m (specific weight "
            f"{project.water_specific_weight:g}).")


def _file(target: Path | None) -> str | None:
    return str(target) if target is not None else None
