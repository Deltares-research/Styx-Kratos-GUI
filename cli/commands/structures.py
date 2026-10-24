"""`section`, `beam`, `wall`, `member`, `anchor`, `interface`, `load`, `normal-load`: the
structures of a model and the sections they are built with.

Each new structure starts where the GUI's Structure mode puts one (`core.model.drafts`):
a sheet pile down the middle of the section, an anchor raking back from a quarter of the
way down the pile, an interface on the first pile, a 20 kN load. The first of a kind
brings the GUI's default section with it, and `section set` changes that section's
numbers -- Kratos' variables, `NAME=VALUE` in the project's units, as a material's are.

What is a sheet pile in a section is a wall or a member in the solid model, so `beam`
works in 2D and `wall` and `member` in 3D. An anchor head is snapped onto the nearest
structure, within a metre, because it becomes one of that structure's nodes. A strut is
an anchor: its head on the wall and its tail a pinned support.
"""

from __future__ import annotations

import argparse

from cli.terminal.output import Answer, CommandError
from cli.terminal.words import (NAME_HELP, action, assignments, coordinates, edited, existing,
                                given, id_and_name, id_help, named_ids, noun)
from core import session
from core.model import drafts
from core.model.schemas import Project

KINDS = tuple(drafts.SECTION_DEFAULTS_SI)

SECTION_OPTIONS = {
    "spacing": ("beam", "anchor"), "tension_limit": ("anchor",),
    "compression_limit": ("anchor",), "material": ("interface",), "r_inter": ("interface",),
    "virtual_thickness": ("interface",), "permeability": ("interface",),
}
"""The section fields only some kinds have, and which."""

NOUNS = {"beam": "sheet pile", "panel": "wall", "member": "member", "anchor": "anchor",
         "anchor3d": "anchor", "interface": "interface", "normal": "normal load",
         "point": "point load", "line": "line load", "surface": "surface load"}


def register(commands, common: argparse.ArgumentParser) -> None:
    _register_sections(commands, common)
    _register_beams(commands, common)
    _register_anchors(commands, common)
    _register_interfaces(commands, common)
    _register_loads(commands, common)


# ── section ─────────────────────────────────────────────────────────────────

def _register_sections(commands, common) -> None:
    sections = noun(commands, common, "section",
                    "list, add, change or remove the sections structures are built with")
    action(sections, common, "list", list_sections, writes=False)
    add = action(sections, common, "add", add_section, variables=True,
                 help="a section: the GUI's default of its kind, then NAME=VALUE variables "
                      "of its own")
    add.add_argument("kind", choices=KINDS,
                     help="beam (sheet piles and members), panel (walls), anchor, interface")
    add.add_argument("id", nargs="?", help=id_help())
    _section_fields(add)
    add.epilog = SECTION_VARIABLES
    change = action(sections, common, "set", update_section, variables=True,
                    help="change NAME=VALUE variables and the fields given")
    change.epilog = SECTION_VARIABLES
    existing(change, "section")
    change.add_argument("--kind", choices=KINDS, help="when two kinds share the id")
    _section_fields(change)
    change.add_argument("--unset", action="append", default=[], metavar="NAME",
                        help="leave this variable out, for the export to derive")
    remove = action(sections, common, "remove", remove_section)
    existing(remove, "section")
    remove.add_argument("--kind", choices=KINDS, help="when two kinds share the id")


SECTION_VARIABLES = (
    "Variables are NAME=VALUE words anywhere on the line: Kratos' names, in the project's "
    "units. An interface section takes INTERFACE_NORMAL_STIFFNESS and "
    "INTERFACE_SHEAR_STIFFNESS, stiffness per area; left out, the export derives them from "
    "the soil each stretch of the interface runs against (shear = G / virtual thickness, "
    "normal = 10 x shear). A Coulomb law (--law GeoInterfaceCoulombLawPlaneStrain) also "
    "reads GEO_COHESION and GEO_FRICTION_ANGLE, derived from the soil with --r-inter when "
    "left out.")
"""What `section add` and `section set` say about their NAME=VALUE words."""


def _section_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--law", help="the Kratos constitutive law")
    parser.add_argument("--spacing", help="beam, anchor: out-of-plane centres, in metres")
    parser.add_argument("--tension-limit", help="anchor: the working limit, a force, or none")
    parser.add_argument("--compression-limit", help="anchor: a force, or none (a tendon)")
    parser.add_argument("--material",
                        help="interface: take the stiffness and strength from this material "
                             "along the whole interface (default, none: from the soil on "
                             "each side, stretch by stretch)")
    parser.add_argument("--r-inter",
                        help="interface: the factor on the soil's cohesion and tan(phi), 0 "
                             "to 1, or none for each soil's own; only a Coulomb law reads "
                             "the strength, the default elastic law reads the stiffnesses "
                             "only")
    parser.add_argument("--virtual-thickness",
                        help="interface: in metres; a derived stiffness is the soil's shear "
                             "modulus over it")
    parser.add_argument("--permeability", choices=("Neutral", "Drain", "Impermeable"),
                        help="interface")


def list_sections(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    rows, lines = [], []
    for kind, field in drafts.SECTION_FIELDS.items():
        for section in getattr(project, field):
            rows.append({"kind": kind, **section.model_dump(mode="json")})
            line = (f"{kind}  {section.id}  {section.name}  {section.constitutive_law}, "
                    f"{len(section.variables)} variables")
            if kind == "interface":
                line += "; " + _interface_stiffness(section)
            lines.append(line)
    return Answer(data=rows, lines=lines or ["No sections yet."])


def _interface_stiffness(section) -> str:
    """The two stiffnesses as typed, or that the export derives them -- the GUI's two
    stiffness rows say the same."""
    typed = [(label, section.number(name)) for label, name in
             (("normal", "INTERFACE_NORMAL_STIFFNESS"), ("shear", "INTERFACE_SHEAR_STIFFNESS"))]
    return ", ".join(f"{label} stiffness {value:g}" if value is not None
                     else f"{label} stiffness derived from the soil"
                     for label, value in typed)


@named_ids(required=True)
def add_section(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    section = drafts.section(project, args.kind, args.id, name=args.name)
    project = session.add_section(project, args.kind, section)
    fields = _section_values(args, args.kind)
    variables = assignments(args.variables)
    if fields or variables:
        project = session.update_section(project, args.id, kind=args.kind,
                                         variables=variables, **fields)
    return edited(args, project, f"added {args.kind} section ({id_and_name(section)})")


def update_section(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    kind, _ = session.find_section(project, args.id, args.kind)
    fields = _section_values(args, kind)
    if args.name is not None:
        fields["name"] = args.name
    project = session.update_section(project, args.id, kind=kind,
                                     variables=assignments(args.variables),
                                     unset=args.unset, **fields)
    return edited(args, project, f"changed {kind} section {args.id}")


def remove_section(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    kind, _ = session.find_section(project, args.id, args.kind)
    return edited(args, session.remove_section(project, args.id, kind),
                  f"removed {kind} section {args.id}")


def _section_values(args: argparse.Namespace, kind: str) -> dict:
    """The section fields the command line gave, by their schema names, refused for a
    kind that does not have them. `none` clears an optional one."""
    out = {}
    if args.law is not None:
        out["constitutive_law"] = args.law
    for field, kinds in SECTION_OPTIONS.items():
        word = getattr(args, field)
        if word is None:
            continue
        option = "--" + field.replace("_", "-")
        if kind not in kinds:
            raise CommandError(f"{option} is not a field of a {kind} section; it is a "
                               f"field of a {' or '.join(kinds)} section.")
        if field in ("material", "permeability"):
            out[field] = None if word.lower() == "none" else word
        else:
            out[field] = _number(word, option)
    return out


def _number(word: str, option: str) -> float | None:
    if word.lower() == "none":
        return None
    try:
        return float(word)
    except ValueError:
        raise CommandError(f"{option} takes a number, or none") from None


# ── beam, wall, member ──────────────────────────────────────────────────────

def _register_beams(commands, common) -> None:
    for name, kind, help in (
            ("beam", "beam", "sheet piles, in a 2D section"),
            ("wall", "panel", "walls, in the solid model: a plan footprint swept down"),
            ("member", "member", "piles, king posts and struts in the solid model")):
        actions = noun(commands, common, name, f"list, add, change or remove {help}")
        listed = action(actions, common, "list", list_structures, writes=False)
        listed.set_defaults(kinds=(kind,))
        add = action(actions, common, "add", add_structure,
                     help=f"a {NOUNS[kind]}; with no geometry, where the GUI puts a new one")
        add.add_argument("id", nargs="?", help=id_help("the first free one"))
        _beam_fields(add, kind)
        add.set_defaults(kinds=(kind,))
        change = action(actions, common, "set", update_structure)
        existing(change, name)
        _beam_fields(change, kind)
        _active(change)
        change.set_defaults(kinds=(kind,))
        remove = action(actions, common, "remove", remove_structure)
        existing(remove, name)
        remove.set_defaults(kinds=(kind,))


def _beam_fields(parser: argparse.ArgumentParser, kind: str) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--section", help="the section it is built with (default: the "
                                          "first there is, or the GUI's default)")
    if kind == "panel":
        parser.add_argument("--footprint", nargs="+", metavar="N",
                            help="its plan outline, x z ... , or @file")
        parser.add_argument("--top", type=float, help="the level it hangs from")
        parser.add_argument("--toe", type=float, help="the level of its toe")
    else:
        parser.add_argument("--points", nargs="+", metavar="N",
                            help=("x y ..." if kind == "beam" else "x y z ...")
                            + " as plain numbers, or @file")


def _active(parser: argparse.ArgumentParser) -> None:
    switch = parser.add_mutually_exclusive_group()
    switch.add_argument("--active", dest="active", action="store_const", const=True,
                        help="export it")
    switch.add_argument("--inactive", dest="active", action="store_const", const=False,
                        help="keep it in the project, but do not export it")


# ── anchor ──────────────────────────────────────────────────────────────────

def _register_anchors(commands, common) -> None:
    actions = noun(commands, common, "anchor",
                   "list, add, change or remove anchors and struts")
    listed = action(actions, common, "list", list_structures, writes=False)
    listed.set_defaults(kinds=("anchor", "anchor3d"))
    add = action(actions, common, "add", add_structure,
                 help="an anchor: the head snapped onto the nearest structure, the tail a "
                      "fixed point (default: 10 m back and down at 35 degrees)")
    add.add_argument("id", nargs="?", help=id_help("the first free one"))
    _anchor_fields(add)
    add.set_defaults(kinds=("anchor", "anchor3d"))
    change = action(actions, common, "set", update_structure)
    existing(change, "anchor")
    _anchor_fields(change)
    _active(change)
    change.set_defaults(kinds=("anchor", "anchor3d"))
    remove = action(actions, common, "remove", remove_structure)
    existing(remove, "anchor")
    remove.set_defaults(kinds=("anchor", "anchor3d"))


def _anchor_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--section", help="its tendon (default: the first there is)")
    parser.add_argument("--head", nargs="+", metavar="N",
                        help="on a pile, a wall or a member: x y in 2D, x y z in 3D")
    parser.add_argument("--tail", nargs="+", metavar="N", help="the fixed end")
    parser.add_argument("--prestress", type=float,
                        help="TRUSS_PRESTRESS_PK2, a stress, positive in tension")


# ── interface ───────────────────────────────────────────────────────────────

def _register_interfaces(commands, common) -> None:
    actions = noun(commands, common, "interface",
                   "list, add, change or remove interfaces (2D only)")
    listed = action(actions, common, "list", list_structures, writes=False)
    listed.set_defaults(kinds=("interface",))
    add = action(actions, common, "add", add_structure,
                 help="an interface on a sheet pile (default: the first), or a free line "
                      "with --points")
    add.add_argument("id", nargs="?", help=id_help("the first free one"))
    _interface_fields(add)
    add.set_defaults(kinds=("interface",))
    change = action(actions, common, "set", update_structure)
    existing(change, "interface")
    _interface_fields(change)
    _active(change)
    change.set_defaults(kinds=("interface",))
    remove = action(actions, common, "remove", remove_structure)
    existing(remove, "interface")
    remove.set_defaults(kinds=("interface",))


def _interface_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--section", help="its contact properties (default: the first)")
    place = parser.add_mutually_exclusive_group()
    place.add_argument("--structure", help="the sheet pile it follows")
    place.add_argument("--points", nargs="+", metavar="N",
                       help="a free line x y ..., splitting soil from soil")
    parser.add_argument("--side", choices=("both", "left", "right"),
                        help="which soil is detached; left is to the left walking the line")


# ── load, normal-load ───────────────────────────────────────────────────────

def _register_loads(commands, common) -> None:
    actions = noun(commands, common, "load", "list, add, change or remove loads")
    listed = action(actions, common, "list", list_structures, writes=False)
    listed.set_defaults(kinds=("point", "line", "surface"))
    add = action(actions, common, "add", add_structure,
                 help="a load, down unless --components says otherwise: 20 kN for a "
                      "point, 20 kN/m for a line (2D), 20 kN/m2 for a surface (3D)")
    add.add_argument("load_kind", choices=("point", "line", "surface"),
                     help="the kind of load: point or line in 2D, surface in 3D")
    add.add_argument("id", nargs="?", help=id_help("the first free load_<n>"))
    _load_fields(add)
    add.set_defaults(kinds=("point", "line", "surface"))
    change = action(actions, common, "set", update_structure)
    existing(change, "load")
    _load_fields(change)
    _active(change)
    change.set_defaults(kinds=("point", "line", "surface"))
    remove = action(actions, common, "remove", remove_structure)
    existing(remove, "load")
    remove.set_defaults(kinds=("point", "line", "surface"))

    actions = noun(commands, common, "normal-load",
                   "list, add, change or remove pressures normal to a line (2D only)")
    listed = action(actions, common, "list", list_structures, writes=False)
    listed.set_defaults(kinds=("normal",))
    add = action(actions, common, "add", add_structure,
                 help="a pressure normal to a line: uniform, or hydrostatic from the water")
    add.add_argument("id", nargs="?", help=id_help("the first free one"))
    _normal_load_fields(add)
    add.set_defaults(kinds=("normal",))
    change = action(actions, common, "set", update_structure)
    existing(change, "normal load", "normal-load")
    _normal_load_fields(change)
    _active(change)
    change.set_defaults(kinds=("normal",))
    remove = action(actions, common, "remove", remove_structure)
    existing(remove, "normal load", "normal-load")
    remove.set_defaults(kinds=("normal",))


def _load_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--at", type=float, nargs=2, metavar=("X", "Y"), help="point")
    parser.add_argument("--x", type=float, nargs=2, metavar=("FROM", "TO"),
                        help="line, surface")
    parser.add_argument("--z", type=float, nargs=2, metavar=("FROM", "TO"), help="surface")
    parser.add_argument("--y", type=float,
                        help="line, surface: its level (default: the top of the model)")
    parser.add_argument("--components", type=float, nargs="+", metavar="F",
                        help="x y in 2D, x y z in 3D, in the project's units: N or kN for "
                             "a point, N/m or kN/m for a line, Pa or kPa for a surface; "
                             "down is negative")


def _normal_load_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--points", nargs="+", metavar="N",
                        help="the line, x y ...; it presses on the soil on the right of "
                             "the line as drawn, where its arrows point in the GUI")
    kind = parser.add_mutually_exclusive_group()
    kind.add_argument("--hydrostatic", dest="hydrostatic", action="store_const", const=True,
                      help="from the water level down, as the water pressure on a face")
    kind.add_argument("--uniform", dest="hydrostatic", action="store_const", const=False,
                      help="--pressure everywhere along the line")
    parser.add_argument("--pressure", type=float,
                        help="a stress, compression positive, for a uniform load")
    parser.add_argument("--reference-coordinate", type=float, metavar="Y",
                        help="a hydrostatic load's water level, in metres (default: the "
                             "project's, copied into the load)")


# ── list, add, set, remove ──────────────────────────────────────────────────

def _records(project: Project, kinds: tuple[str, ...]) -> list:
    if "point" in kinds:
        # The loads of this dimension, as the GUI's tree lists them: a pad kept from the
        # solid model is not a load of the section, nor its line one of the solid model.
        kinds = ("point", "line") if project.dimension == 2 else ("surface",)
    return [record for field in session.STRUCTURES for record in getattr(project, field)
            if record.kind in kinds]


def list_structures(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    records = _records(project, args.kinds)
    return Answer(data=[record.model_dump(mode="json") for record in records],
                  lines=[_line(record) for record in records]
                  or [f"No {NOUNS[args.kinds[0]]}s yet."])


@named_ids()
def add_structure(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    record = _drafted(project, args)
    section = drafts.section_for(project, record)
    kind = drafts.section_kind(record)
    if section is not None and kind is not None and getattr(args, "section", None) is not None:
        library = getattr(project, drafts.SECTION_FIELDS[kind])
        raise CommandError(
            f"there is no {kind} section {args.section!r}; there are: "
            + (", ".join(s.id for s in library) or "none")
            + f". Add one first: kratos-cli section {args.project} add {kind} {args.section}")
    project = session.add_structure(project, record, section)
    answer = edited(args, project, f"added {NOUNS[record.kind]} ({id_and_name(record)})")
    if section is not None:
        answer.lines.append(
            f"with a new {drafts.section_kind(record)} section ({id_and_name(section)}); "
            f"change it with `kratos-cli section {args.project} set "
            f"{section.id} NAME=VALUE ...`")
    return answer


def update_structure(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    record = _own(project, args.id, args.kinds)
    fields = _fields(project, record, args)
    return edited(args, session.update_structure(project, args.id, **fields),
                  f"changed {NOUNS[record.kind]} {args.id}")


def remove_structure(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    record = _own(project, args.id, args.kinds)
    return edited(args, session.remove_structure(project, args.id),
                  f"removed {NOUNS[record.kind]} {args.id}")


def _own(project: Project, id: str, kinds: tuple[str, ...]):
    """The structure `id`, which has to be of this command's kinds."""
    record = session.find_structure(project, id)
    if record.kind not in kinds:
        command = {"beam": "beam", "panel": "wall", "member": "member", "anchor": "anchor",
                   "anchor3d": "anchor", "interface": "interface",
                   "normal": "normal-load"}.get(record.kind, "load")
        raise CommandError(f"{id} is a {NOUNS[record.kind]}; use `kratos-cli {command}`")
    return record


def _drafted(project: Project, args: argparse.Namespace):
    """The new structure the command line describes, started as the GUI starts one."""
    kind = args.kinds[0]
    named = {"id": args.id, "name": args.name}
    if kind == "beam":
        return drafts.sheet_pile(project, _points(args.points, 2), section=args.section,
                                 **named)
    if kind == "panel":
        return drafts.wall(project, _points(args.footprint, 2, "--footprint"),
                           section=args.section, top=args.top, toe=args.toe, **named)
    if kind == "member":
        return drafts.member(project, _points(args.points, 3), section=args.section,
                             **named)
    if kind == "anchor":
        width = _width(project)
        return drafts.anchor(project, _point(args.head, width, "--head"),
                             _point(args.tail, width, "--tail"), section=args.section,
                             prestress=args.prestress or 0.0, **named)
    if kind == "interface":
        return drafts.interface(project, args.structure, _points(args.points, 2),
                                side=args.side, section=args.section, **named)
    if kind == "normal":
        return drafts.normal_load(project, _points(args.points, 2),
                                  hydrostatic=bool(args.hydrostatic),
                                  pressure=args.pressure or 0.0,
                                  reference_coordinate=args.reference_coordinate, **named)
    components = _components(project, args.components)
    if args.load_kind == "point":
        return drafts.point_load(project, args.at, components=components, **named)
    if args.load_kind == "line":
        return drafts.line_load(project, args.x, y=args.y, components=components, **named)
    return drafts.surface_load(project, args.x, args.z, components=components, **named)


def _fields(project: Project, record, args: argparse.Namespace) -> dict:
    """The fields of `record` the command line changes, by their schema names."""
    fields = given(args, "name", "active")
    if getattr(args, "section", None) is not None:
        fields["section"] = args.section
    kind = record.kind
    if kind in ("beam", "member") and args.points is not None:
        fields["points"] = coordinates(args.points, 2 if kind == "beam" else 3)
    if kind == "panel":
        if args.footprint is not None:
            fields["footprint"] = coordinates(args.footprint, 2, "--footprint")
        fields.update({name: value for name, value in
                       (("y_top", args.top), ("y_toe", args.toe)) if value is not None})
    if kind in ("anchor", "anchor3d"):
        width = 2 if kind == "anchor" else 3
        if args.head is not None:
            fields["head"] = drafts.anchor_head(project, _point(args.head, width, "--head"))
        if args.tail is not None:
            fields["tail"] = _point(args.tail, width, "--tail")
        fields.update(given(args, "prestress"))
    if kind == "interface":
        if args.structure is not None:
            fields.update(structure=args.structure, points=None)
        if args.points is not None:
            fields.update(structure=None, points=coordinates(args.points, 2))
        fields.update(given(args, "side"))
    if kind == "normal":
        if args.points is not None:
            fields["points"] = coordinates(args.points, 2)
        if args.hydrostatic is not None:
            fields["fluid_pressure_type"] = "Hydrostatic" if args.hydrostatic else "Uniform"
        fields.update(given(args, "pressure", "reference_coordinate"))
        # A load made hydrostatic takes the project's level as a new one does
        # (`drafts.normal_load`), so it says what it is measured from.
        if (args.hydrostatic and record.reference_coordinate is None
                and "reference_coordinate" not in fields and project.water is not None):
            fields["reference_coordinate"] = project.water.y
    if kind in ("point", "line", "surface"):
        if args.at is not None:
            fields["x"], fields["y"] = args.at
        if args.x is not None:
            fields["x0"], fields["x1"] = sorted(args.x)
        if args.z is not None:
            fields["z0"], fields["z1"] = sorted(args.z)
        if args.y is not None and kind != "point":
            fields["y"] = args.y
        if args.components is not None:
            fields["components"] = _components(project, args.components,
                                               3 if kind == "surface" else 2)
    return fields


def _width(project: Project) -> int:
    return 2 if project.dimension == 2 else 3


def _points(words: list[str] | None, size: int, option: str = "--points"):
    return None if words is None else coordinates(words, size, option)


def _point(words: list[str] | None, size: int, option: str):
    if words is None:
        return None
    points = coordinates(words, size, option)
    if len(points) != 1:
        raise CommandError(f"{option} takes one point, {size} numbers")
    return points[0]


def _components(project: Project, values: list[float] | None, size: int | None = None):
    if values is None:
        return None
    size = size or _width(project)
    if len(values) != size:
        raise CommandError(f"--components takes {size} numbers here: "
                           + ("x y" if size == 2 else "x y z"))
    return tuple(values)


def _line(record) -> str:
    """One structure, in a line of text."""
    kind = record.kind
    where = ""
    if kind in ("beam", "member", "normal") or (kind == "interface" and record.points):
        where = " -> ".join(_xy(point) for point in record.points)
    elif kind == "panel":
        where = (" -> ".join(_xy(point) for point in record.footprint)
                 + f", {record.y_top:g} .. {record.y_toe:g}")
    elif kind in ("anchor", "anchor3d"):
        where = f"{_xy(record.head)} -> {_xy(record.tail)}"
    elif kind == "interface":
        where = f"along {record.structure}, {record.side}"
    elif kind == "point":
        where = f"at {_xy((record.x, record.y))}"
    elif kind == "line":
        where = f"x {record.x0:g} .. {record.x1:g} at y {record.y:g}"
    elif kind == "surface":
        where = f"x {record.x0:g} .. {record.x1:g}, z {record.z0:g} .. {record.z1:g}"
    if kind in ("point", "line", "surface"):
        where += "; " + _xy(record.components)
    if kind == "normal":
        where += (f"; {record.pressure:g} uniform" if record.fluid_pressure_type == "Uniform"
                  else "; hydrostatic about the water level"
                  if record.reference_coordinate is None
                  else f"; hydrostatic about {record.reference_coordinate:g} m")
    section = f"  section {record.section}" if hasattr(record, "section") else ""
    side = f", {record.side}" if kind == "interface" and record.points else ""
    return (f"{record.id}  {record.name}  {where}{side}{section}"
            + ("" if record.active else "  (inactive)"))


def _xy(values) -> str:
    return "(" + ", ".join(f"{value:g}" for value in values) + ")"
