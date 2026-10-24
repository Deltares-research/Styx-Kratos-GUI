"""`boundary`: the conditions the user prescribes on the model's boundaries and soil.

A condition is a record of `Project.boundary_conditions`, and the deck holds these and no
others: a project with no water pressure condition fixes no water pressure, whatever its
water level, and one with no displacement condition holds nothing still. Each record is
what the GUI's boundary conditions dialog makes -- its target (`--domain`, `--face`,
`--part`, `--line`, `--point`: the dialog's first question, and which one) and what it
prescribes there: displacements held at zero (`--fixed`, `--roller`, `--fix`,
`core.model.drafts.displacement_condition`), a water pressure (`--water-pressure`,
`core.model.drafts.water_pressure_condition`), or a seepage face, where water may leave
the soil in a groundwater flow calculation (`--seepage`, on a face or a line,
`core.model.drafts.seepage_condition`). `boundary standard` puts back the
supports a new project starts with. `gravity` switches the self weight on and off.

A hydrostatic water pressure given no `--reference-coordinate` is given the project's
water level, which the record then keeps as its own; the command says which level it
took. With no water level either it is refused, and the refusal names the dry options.
"""

from __future__ import annotations

import argparse

from cli.terminal.files import add_project, add_writing, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import NAME_HELP, action, coordinates, edited, existing, given, noun
from core import session
from core.kratos import condition_checks
from core.model import drafts
from core.model.schemas import FACES, Project

PRESSURE_TYPES = ("Uniform", "Hydrostatic", "Phreatic_Multi_Line")
"""`--water-pressure`: Kratos' `fluid_pressure_type`, under its own names."""

WATER_OPTIONS = {"reference_coordinate": "--reference-coordinate", "value": "--value",
                 "phreatic_line": "--phreatic-line",
                 "pressure_tension_cut_off": "--pressure-tension-cut-off"}
"""The options only a water pressure takes."""


def register(commands, common: argparse.ArgumentParser) -> None:
    actions = noun(commands, common, "boundary",
                   "list, add, change or remove the boundary conditions")
    action(actions, common, "list", list_conditions, writes=False)
    add = action(actions, common, "add", add_condition,
                 help="a support (--fixed, --roller, --fix) on a face, a soil part, a "
                      "drawn line or a point, a water pressure (--water-pressure) there "
                      "or on the whole soil, or a seepage face (--seepage) on a face or "
                      "a line")
    add.add_argument("id", nargs="?", help="its id (default: the first free one)")
    _fields(add)
    change = action(actions, common, "set", update_condition,
                    help="change the fields given; a new target replaces the old one")
    existing(change, "boundary condition", "boundary")
    _fields(change)
    switch = change.add_mutually_exclusive_group()
    switch.add_argument("--active", dest="active", action="store_const", const=True,
                        help="export it")
    switch.add_argument("--inactive", dest="active", action="store_const", const=False,
                        help="keep it in the project, but do not export it")
    remove = action(actions, common, "remove", remove_condition)
    existing(remove, "boundary condition", "boundary")
    action(actions, common, "standard", standard_conditions,
           help="the standard supports, the bottom fixed and the sides on rollers, in "
                "place of the supports on the faces")

    gravity = commands.add_parser("gravity", parents=[common],
                                  help="show, or switch on or off, the self weight",
                                  description="Whether gravity acts: the self weight of "
                                              "every body, in every stage. On in a new "
                                              "project.")
    add_project(gravity)
    gravity.add_argument("switch", nargs="?", choices=("on", "off"), type=str.lower)
    add_writing(gravity)
    gravity.set_defaults(handler=set_gravity)


def _fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--domain", action="store_true",
                        help="the whole soil (water pressure only)")
    target.add_argument("--face", choices=FACES,
                        help="a face of the model; front and back exist in 3D only")
    target.add_argument("--part", metavar="KEY",
                        help="a soil part, as `parts` lists it: a layer soil_<id> with all "
                             "its lifts, one body, or a custom part with a material")
    target.add_argument("--line", nargs="+", metavar="N",
                        help="a drawn line in the 2D section, x y x y ..., or @file")
    target.add_argument("--point", nargs="+", metavar="N",
                        help="a point in the 2D section, x y")
    parser.add_argument("--seepage", action="store_true",
                        help="a seepage face, where water may leave the soil in a "
                             "groundwater flow calculation: on a face, or a line along the "
                             "soil's outer boundary")
    parser.add_argument("--water-pressure", choices=PRESSURE_TYPES, metavar="TYPE",
                        help="Uniform (--value), Hydrostatic (--reference-coordinate) or "
                             "Phreatic_Multi_Line (--phreatic-line)")
    parser.add_argument("--reference-coordinate", type=float, metavar="Y",
                        help="Hydrostatic: the level where the pressure is zero, in metres "
                             "(default: the project's water level)")
    parser.add_argument("--value", type=float, metavar="STRESS",
                        help="Uniform: the pressure, in the project's units, Kratos' sign "
                             "(compression negative)")
    parser.add_argument("--phreatic-line", nargs="+", metavar="N",
                        help="Phreatic_Multi_Line: its points x y x y ..., x increasing")
    parser.add_argument("--pressure-tension-cut-off", type=float, metavar="STRESS",
                        help="Hydrostatic, Phreatic_Multi_Line: the most suction above the "
                             "level (default 0: no suction)")
    held = parser.add_mutually_exclusive_group()
    held.add_argument("--fixed", dest="is_fixed", action="store_const", const=True,
                      help="a support: x, y and z held. A water pressure: held at these "
                           "values (its default)")
    held.add_argument("--roller", action="store_true",
                      help="a support holding the component normal to its face, or to a "
                           "vertical (x) or horizontal (y) line")
    held.add_argument("--fix", nargs="+", choices=("x", "y", "z"), metavar="AXIS",
                      help="a support holding these components: x, y, z")
    held.add_argument("--initial", dest="is_fixed", action="store_const", const=False,
                      help="a water pressure: start values only, which the calculation "
                           "then changes")


# ── list, add, set, remove ──────────────────────────────────────────────────

def listed_lines(project: Project) -> list[str]:
    """The conditions, one line each, as `boundary list` prints them and the GUI's
    command box says them (`App.BoundaryConditions.command`): a 2D model's front and
    back supports are left out, with a note that they are, and a groundwater flow
    project's supports are noted as left out of its deck."""
    records = condition_checks.listed(project)
    lines = [line(record) for record in records] or ["No boundary conditions yet."]
    if len(records) < len(project.boundary_conditions):
        lines.append(condition_checks.SECTION_NOTE)
    if any(condition_checks.unused_in_flow(project, record) for record in records):
        lines.append(condition_checks.FLOW_NOTE)
    return lines


def list_conditions(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    records = condition_checks.listed(project)
    return Answer(data=[record.model_dump(mode="json") for record in records],
                  lines=listed_lines(project))


def add_condition(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    support = args.roller or args.fix is not None
    if args.seepage:
        return _add_seepage(args, project)
    if args.water_pressure is None and not support and args.is_fixed is not True:
        raise CommandError("say what the condition prescribes: --fixed, --roller or "
                           "--fix AXIS ... for a support, --water-pressure "
                           + "|".join(PRESSURE_TYPES) + ", or --seepage")
    target = _target(args)
    if target is None:
        raise CommandError("say where it acts: --domain, --face FACE, --part KEY, "
                           "--line X Y X Y ... or --point X Y")
    if args.water_pressure is None:
        _only_water(args, "a support")
        support_record = drafts.displacement_condition(
            project, target.pop("on"), id=args.id, name=args.name, roller=args.roller,
            fixed=_components(args.fix), **target)
        return edited(args, session.add_condition(project, support_record),
                      f"added {line(support_record)}")
    if support:
        raise CommandError("--roller and --fix are a support's; a water pressure is "
                           "--fixed or --initial")
    if args.water_pressure == "Phreatic_Multi_Line" and args.phreatic_line is None:
        raise CommandError("a Phreatic_Multi_Line needs its points: --phreatic-line "
                           "X Y X Y ...")
    record = drafts.water_pressure_condition(
        project, target.pop("on"), id=args.id, name=args.name,
        fluid_pressure_type=args.water_pressure,
        is_fixed=True if args.is_fixed is None else args.is_fixed,
        value=args.value if args.value is not None else 0.0,
        reference_coordinate=args.reference_coordinate,
        pressure_tension_cut_off=(args.pressure_tension_cut_off
                                  if args.pressure_tension_cut_off is not None else 0.0),
        **_phreatic(args), **target)
    project = session.add_condition(project, record)
    answer = edited(args, project, f"added {line(record)}")
    if (record.fluid_pressure_type == "Hydrostatic"
            and args.reference_coordinate is None):
        answer.lines.append(f"its level is the project's water level, "
                            f"{record.reference_coordinate:g} m; it keeps it if the water "
                            "level changes")
    return answer


def _add_seepage(args: argparse.Namespace, project: Project) -> Answer:
    """`add --seepage`: a seepage face on a face or a line, and nothing else."""
    _only_seepage(args)
    target = _target(args)
    if target is None or target["on"] not in ("face", "line"):
        raise CommandError("a seepage face is on --face FACE or --line X Y X Y ..., along "
                           "the soil's outer boundary")
    record = drafts.seepage_condition(project, target.pop("on"), id=args.id,
                                      name=args.name, **target)
    return edited(args, session.add_condition(project, record), f"added {line(record)}")


def _only_seepage(args: argparse.Namespace) -> None:
    """Refuse what a seepage face does not take: what a support or a water pressure
    prescribes."""
    others = [option for option, given_value in (
        ("--water-pressure", args.water_pressure), ("--roller", args.roller or None),
        ("--fix", args.fix), ("--fixed or --initial", args.is_fixed),
        *((option, getattr(args, field)) for field, option in WATER_OPTIONS.items()))
        if given_value is not None]
    if others:
        raise CommandError(f"{', '.join(others)} do not belong to a seepage face: it "
                           "prescribes nothing but where water may leave the soil")


def update_condition(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    record = session.find_condition(project, args.id)
    if record.kind == "seepage":
        _only_seepage(args)
        fields = given(args, "name", "active")
        target = _target(args)
        if target is not None:
            if target["on"] not in ("face", "line"):
                raise CommandError("a seepage face is on --face FACE or --line X Y X Y ...")
            fields.update(target)
        project = session.update_condition(project, args.id, **fields)
        return edited(args, project,
                      f"changed {line(session.find_condition(project, args.id))}")
    if args.seepage:
        raise CommandError(f"{args.id} is a {record.kind.replace('_', ' ')} condition; "
                           "remove it and add a seepage face instead")
    if record.kind == "displacement":
        return _update_support(args, project, record)
    if args.roller or args.fix is not None:
        raise CommandError(f"{args.id} is a water pressure; --roller and --fix are a "
                           "support's")
    fields = given(args, "name", "active", "is_fixed", "value", "reference_coordinate",
                   "pressure_tension_cut_off")
    if args.water_pressure is not None:
        fields["fluid_pressure_type"] = args.water_pressure
    fields.update(_phreatic(args))
    target = _target(args)
    if target is not None:
        fields.update(target)
    if (fields.get("fluid_pressure_type") == "Hydrostatic"
            and record.reference_coordinate is None and "reference_coordinate" not in fields):
        # As a new record is given it (`drafts.water_pressure_condition`).
        if project.water is None:
            raise CommandError("a Hydrostatic water pressure needs the level where its "
                               "pressure is zero: give --reference-coordinate Y")
        fields["reference_coordinate"] = project.water.y
    project = session.update_condition(project, args.id, **fields)
    return edited(args, project, f"changed {line(session.find_condition(project, args.id))}")


def _update_support(args: argparse.Namespace, project: Project, record) -> Answer:
    """`set` on a displacement condition: its target, and the components it holds."""
    if args.water_pressure is not None or args.is_fixed is False:
        raise CommandError(f"{args.id} is a support; --water-pressure and --initial are a "
                           "water pressure's")
    _only_water(args, "a support")
    fields = given(args, "name", "active")
    target = _target(args)
    if target is not None:
        fields.update(target)
    if args.is_fixed:
        fields["fixed"] = (True, True, True)
    elif args.fix is not None:
        fields["fixed"] = _components(args.fix)
    elif args.roller:
        moved = {"on": record.on, "face": record.face, "part": record.part,
                 "points": record.points}
        if target is not None:
            moved = {"face": None, "part": None, "points": None, **target}
        fields["fixed"] = drafts.displacement_condition(
            project, moved.pop("on"), roller=True, **moved).fixed
    project = session.update_condition(project, args.id, **fields)
    return edited(args, project, f"changed {line(session.find_condition(project, args.id))}")


def standard_conditions(args: argparse.Namespace) -> Answer:
    project = session.standard_conditions(session.load(args.project))
    answer = edited(args, project, "the standard supports: the bottom fixed, the sides on "
                                   "rollers")
    answer.lines += listed_lines(project)
    return answer


def set_gravity(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    if args.switch is None:
        return Answer(data={"gravity": project.gravity}, lines=[_gravity_line(project)])
    project = session.set_gravity(project, args.switch == "on")
    target, where = written(args, project)
    return Answer(data={"file": str(target) if target else None, "gravity": project.gravity},
                  lines=[f"{_gravity_line(project)} {where}"])


def _gravity_line(project: Project) -> str:
    return ("Gravity is on: every body has its self weight." if project.gravity else
            "Gravity is off: no body has a self weight.")


def remove_condition(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    record = session.find_condition(project, args.id)
    return edited(args, session.remove_condition(project, args.id),
                  f"removed {record.kind.replace('_', ' ')} condition {args.id}")


def _target(args: argparse.Namespace) -> dict | None:
    """`on` and the field it names, from the one target option given, or None."""
    if args.domain:
        return {"on": "domain"}
    if args.face is not None:
        return {"on": "face", "face": args.face}
    if args.part is not None:
        return {"on": "part", "part": args.part}
    if args.line is not None:
        return {"on": "line", "points": coordinates(args.line, 2, "--line")}
    if args.point is not None:
        points = coordinates(args.point, 2, "--point")
        if len(points) != 1:
            raise CommandError("--point takes one point, x y")
        return {"on": "point", "points": points}
    return None


def _only_water(args: argparse.Namespace, what: str) -> None:
    """Refuse the water pressure's options on `what`."""
    given_options = [option for field, option in WATER_OPTIONS.items()
                     if getattr(args, field) is not None]
    if given_options:
        raise CommandError(f"{', '.join(given_options)} belong to a water pressure, not to "
                           f"{what}")


def _components(axes: list[str] | None) -> tuple[bool, bool, bool] | None:
    """`--fix x y` as the record's `fixed`."""
    if axes is None:
        return None
    return ("x" in axes, "y" in axes, "z" in axes)


def _phreatic(args: argparse.Namespace) -> dict:
    """`--phreatic-line` as the record's coordinate lists."""
    if args.phreatic_line is None:
        return {}
    points = coordinates(args.phreatic_line, 2, "--phreatic-line")
    return {"x_coordinates": [x for x, _ in points], "y_coordinates": [y for _, y in points]}


# ── Saying what a condition is ──────────────────────────────────────────────

def target(record) -> str:
    """Where `record` acts, in words."""
    if record.on == "domain":
        return "the whole soil"
    if record.on == "face":
        return f"the {record.face} face"
    if record.on == "part":
        return f"part {record.part}"
    where = " -> ".join(_xy(point) for point in record.points or [])
    return f"{record.on} {where}"


def prescribed(record) -> str:
    """What `record` prescribes, in words."""
    if record.kind == "displacement":
        held = [axis for axis, fixed in zip("xyz", record.fixed) if fixed]
        return "fixed in " + " ".join(held)
    if record.kind == "seepage":
        return "water may leave the soil here"
    if record.fluid_pressure_type == "Uniform":
        what = f"{record.value:g} uniform"
    elif record.fluid_pressure_type == "Hydrostatic":
        what = f"hydrostatic about {record.reference_coordinate:g} m"
    else:
        what = "phreatic line " + " -> ".join(
            _xy(point) for point in zip(record.x_coordinates or [],
                                        record.y_coordinates or []))
    if record.fluid_pressure_type != "Uniform" and record.pressure_tension_cut_off:
        what += f", cut-off {record.pressure_tension_cut_off:g}"
    return what + (", fixed" if record.is_fixed else ", initial")


def line(record) -> str:
    """One condition, in a line of text."""
    return (f"{record.id}  {record.name}  {record.kind.replace('_', ' ')} on "
            f"{target(record)}; {prescribed(record)}"
            + ("" if record.active else "  (inactive)"))


def _xy(values) -> str:
    return "(" + ", ".join(f"{value:g}" for value in values) + ")"


def summary(project: Project) -> list[dict]:
    """The conditions as `show` lists them: id, kind and where."""
    return [{"id": c.id, "kind": c.kind, "on": target(c), "active": c.active}
            for c in condition_checks.listed(project)]
