"""`domain`, `material`, `layer`, `line`, `body`, `parts`: the ground of a model.

Each edit is `core.session`'s, made the way the GUI's soil dialogs make it -- a moved
level moves its neighbour's, a deleted layer's neighbour closes the gap -- and each new
record starts as those dialogs start it (`core.model.drafts`). Materials are Kratos
property sets: a law and its variables under Kratos' names, typed as `NAME=VALUE` in the
project's own units. A soil model (`--model mohr-coulomb`) picks the law and fills in
the defaults the material window fills in (`core.model.soil_models`).

A line splits the layers and the soil surfaces it crosses from edge to edge, as a sheet
pile does. Each piece is a soil body with its own key (`soil_<layer>__<id>`, or
`<surface>__<id>`), which a stage can switch, and `body` names it, can give it a material
of its own, or removes it and leaves a void (`Project.split_soil`).
"""

from __future__ import annotations

import argparse

from cli.terminal.files import add_project, add_writing, read, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import (NAME_HELP, action, assignments, coordinates, edited, existing,
                                file_of, id_help, named_ids, noun)
from core import session
from core.model import drafts, soil_models, units
from core.model.schemas import Project
from core.model import udsm


def register(commands, common: argparse.ArgumentParser) -> None:
    domain = commands.add_parser("domain", parents=[common],
                                 help="show or set the model's extents")
    add_project(domain)
    domain.add_argument("--x", type=float, nargs=2, metavar=("FROM", "TO"))
    domain.add_argument("--y", type=float, nargs=2, metavar=("BOTTOM", "TOP"),
                        help="the ground level and the bottom; with layers, the top of "
                             "the first layer and the bottom of the last move with them")
    domain.add_argument("--z", type=float, nargs=2, metavar=("FROM", "TO"),
                        help="out of plane; a 2D model is the section at one z")
    add_writing(domain)
    domain.set_defaults(handler=set_domain)

    material = noun(commands, common, "material",
                     "list, add, change or remove materials (soil property sets)")
    action(material, common, "list", list_materials, writes=False)
    presets = action(material, common, "presets", list_presets, writes=False,
                     help="the material library a new soil can start from, or one preset "
                          "with all its values")
    presets.add_argument("preset", nargs="?",
                         help="a preset to show as `add --preset` would add it")
    presets.add_argument("--model", choices=sorted(MODEL_WORDS),
                         help="show it as this soil model instead of its own")
    action(material, common, "models", list_models, writes=False,
            help="the soil models (--model), each with its parameters and defaults in "
                 "the project's units")
    action(material, common, "udsm", list_udsm, writes=False,
           help="the UDSM models (--udsm) in the libraries that come with Styx, each with "
                "its parameters: the KEY=VALUE words a UDSM soil takes, and their start "
                "values in the project's units")
    add = action(material, common, "add", add_material, variables=True,
                  help="a soil: the blank soil Create soil makes, or a library preset, of a "
                       "soil model, then NAME=VALUE variables of its own")
    add.add_argument("id", nargs="?", help=id_help())
    add.add_argument("--preset", help="the library preset to start from (see `presets`)")
    _material_fields(add)
    change = action(material, common, "set", update_material, variables=True,
                     help="change NAME=VALUE variables, the soil model or law, the name or "
                          "the colour")
    existing(change, "material")
    _material_fields(change)
    change.add_argument("--unset", action="append", default=[], metavar="NAME",
                        help="leave this variable out, for the export to derive")
    remove = action(material, common, "remove", remove_material)
    existing(remove, "material")

    layer = noun(commands, common, "layer", "list, add, change, split or remove layers")
    action(layer, common, "list", list_layers, writes=False)
    add = action(layer, common, "add", add_layer,
                  help="a layer under the stack, down to --bottom or --thickness below "
                       "the last one (default 5 m)")
    add.add_argument("id", nargs="?", help=id_help())
    add.add_argument("--material", required=True)
    add.add_argument("--name", help=NAME_HELP)
    depth = add.add_mutually_exclusive_group()
    depth.add_argument("--bottom", type=float, help="its bottom")
    depth.add_argument("--thickness", type=float)
    change = action(layer, common, "set", update_layer,
                     help="change a layer; a moved level moves its neighbour's with it")
    existing(change, "layer")
    change.add_argument("--material", help="its material, which every part a line or a "
                                           "sheet pile cut off it takes too")
    change.add_argument("--name", help=NAME_HELP)
    change.add_argument("--top", type=float)
    change.add_argument("--bottom", type=float)
    split = action(layer, common, "split", split_layer,
                    help="halve a layer; the lower half becomes a new layer")
    existing(split, "layer")
    split.add_argument("new_id", nargs="?")
    remove = action(layer, common, "remove", remove_layer)
    existing(remove, "layer")

    line = noun(commands, common, "line",
                "list, add, change or remove the lines that split the soil")
    action(line, common, "list", list_lines, writes=False)
    add = action(line, common, "add", add_line,
                 help="a line; where it crosses a layer or a soil surface from one edge to "
                      "another, it becomes separate soil bodies")
    add.add_argument("id", nargs="?", help=id_help("the first free one"))
    _line_fields(add)
    change = action(line, common, "set", update_line)
    existing(change, "line")
    _line_fields(change)
    remove = action(line, common, "remove", remove_line)
    existing(remove, "line")

    body = noun(commands, common, "body",
                "list the soil bodies, name them, give them a material or remove one")
    action(body, common, "list", list_bodies, writes=False,
           help="every soil body by its key, the word a stage takes")
    change = action(body, common, "set", update_body,
                    help="change a body that a line or a sheet pile cut off; a whole layer "
                         "is changed with `layer set`, a whole soil surface with `surface`")
    change.add_argument("key", help="the body's key, as `body list` shows it")
    change.add_argument("--name", help="what to call it")
    change.add_argument("--material", help="its material, or `layer` for its layer's or soil "
                                           "surface's as it is now")
    remove = action(body, common, "remove", remove_body,
                    help="delete one body that a line or a sheet pile cut off: the soil there "
                         "becomes a void, and the rest of its layer or soil surface stays")
    remove.add_argument("key", help="the body's key, as `body list` shows it")

    parts = commands.add_parser("parts", parents=[common],
                                help="the parts of the model, and which a stage can switch")
    add_project(parts)
    parts.set_defaults(handler=list_parts)






MODEL_WORDS = {model.replace("_", "-"): model for model in soil_models.MODELS}
"""`--model`'s words: the soil models' ids, with a dash."""


def _material_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--color", help="a #rrggbb colour")
    parser.add_argument("--model", choices=sorted(MODEL_WORDS),
                        help="the soil model: its law for the model's dimension, and its "
                             "defaults for what the soil lacks (see `models`)")
    parser.add_argument("--law", help="any other Kratos constitutive law, written as typed "
                                      "(default: linear elastic for the model's dimension)")
    parser.add_argument("--udsm", metavar="MODEL",
                        help="a UDSM model (see `udsm`), e.g. MohrCoulomb64:1: the soil "
                             "becomes the udsm soil model with this model's start values; "
                             "its parameters are then given as KEY=VALUE, e.g. E=2e7")
    parser.add_argument("--r-inter", type=float,
                        help="the factor an interface puts on this soil's cohesion and "
                             "tan(phi), above 0 and at most 1 (default 0.7)")


def _model(args: argparse.Namespace) -> str | None:
    return MODEL_WORDS[args.model] if args.model is not None else None


# ── domain ──────────────────────────────────────────────────────────────────

def set_domain(args: argparse.Namespace) -> Answer:
    project = read(args)
    if args.x is None and args.y is None and args.z is None:
        return Answer(data=project.domain.model_dump(mode="json"),
                      lines=[_domain_line(project)])
    project, notes = session.set_domain(project, x=args.x, y=args.y, z=args.z)
    target, where = written(args, project)
    return Answer(data={"file": file_of(target), "domain": project.domain.model_dump(mode="json"),
                        "section_offset": project.section_offset, "notes": notes},
                  lines=[f"{_domain_line(project)}; {where}", *notes])


def _line_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--points", nargs="+", metavar="N",
                        help="the line, x y ... as plain numbers, or @file (default for a new "
                             "line: across the middle of the section)")


def list_lines(args: argparse.Namespace) -> Answer:
    project = read(args)
    return Answer(data=[line.model_dump(mode="json") for line in project.lines],
                  lines=[f"{line.id}  {line.name}: "
                         + " .. ".join(f"{x:g},{y:g}" for x, y in line.points)
                         for line in project.lines] or ["No lines yet."])


@named_ids()
def add_line(args: argparse.Namespace) -> Answer:
    project = read(args)
    points = None if args.points is None else coordinates(args.points, 2)
    try:
        line = drafts.line(project, points, id=args.id, name=args.name)
    except drafts.DraftError as refused:
        raise CommandError(str(refused)) from None
    return edited(args, session.add_line(project, line), f"added line {line.id}")


def update_line(args: argparse.Namespace) -> Answer:
    fields = {}
    if args.name is not None:
        fields["name"] = args.name
    if args.points is not None:
        fields["points"] = coordinates(args.points, 2)
    return edited(args, session.update_line(read(args), args.id, **fields),
                  f"changed line {args.id}")


def remove_line(args: argparse.Namespace) -> Answer:
    return edited(args, session.remove_line(read(args), args.id), f"removed line {args.id}")


def list_bodies(args: argparse.Namespace) -> Answer:
    """Each row as the Model explorer shows it: the key's label, then the material."""
    project = read(args)
    materials = project.soil_body_materials
    rows = [{"key": key, "label": project.soil_body_labels[key],
             "material": materials[key]} for key in project.soil_body_keys]
    return Answer(data=rows, lines=[
        f"{row['key']}  {row['label']}  ·  {project.material(row['material']).name}"
        for row in rows] or ["No soil bodies yet."])


def update_body(args: argparse.Namespace) -> Answer:
    fields: dict[str, str | None] = {}
    if args.name is not None:
        fields["name"] = args.name
    if args.material is not None:
        fields["material"] = None if args.material == "layer" else args.material
    return edited(args, session.update_body(read(args), args.key, **fields),
                  f"changed soil body {args.key}")


def remove_body(args: argparse.Namespace) -> Answer:
    return edited(args, session.remove_body(read(args), args.key),
                  f"removed soil body {args.key}")


def _domain_line(project: Project) -> str:
    d = project.domain
    extent = f"domain x {d.x0:g} .. {d.x1:g}, y {d.y_bottom:g} .. {d.y_top:g}"
    if project.dimension == 2:
        # A 2D model is the cut at one z: the z range only bounds where it may be made.
        return f"{extent} (2D section at z = {project.section_offset:g})"
    return f"{extent}, z {d.z0:g} .. {d.z1:g}"


def list_materials(args: argparse.Namespace) -> Answer:
    project = read(args)
    return Answer(data=[m.model_dump(mode="json") for m in project.materials],
                  lines=[f"{m.id}  {m.name}  "
                         f"{soil_models.label(soil_models.model_of(m.constitutive_law))}"
                         f"{_udsm_name(m.variables)} "
                         f"({m.constitutive_law}), {len(m.variables)} variables"
                         for m in project.materials]
                  or ["No materials yet."])


def _udsm_name(variables: dict) -> str:
    """` Mohr-Coulomb (MohrCoulomb64:1)` for a UDSM soil, nothing for another."""
    model = soil_models.udsm_model(variables)
    return f" {model.name} ({model.id})" if model is not None else ""


def list_udsm(args: argparse.Namespace) -> Answer:
    system = read(args).unit_system
    lines = []
    for model in udsm.models():
        lines.append(f"{model.id}  {model.name}  ({model.file}, UDSM_NUMBER {model.number})")
        for i, p in enumerate(model.parameters):
            unit = udsm.unit_label(p, system)
            value = soil_models.udsm_default(model, i, system)
            lines.append(f"  {p.key} = {_shown(value)}" + (f" {unit}" if unit else "")
                         + f"  ({p.label})")
        if not model.known:
            lines.append("  No start values are known for this model: give every value.")
    lines += [f"Left out: {problem}" for problem in udsm.problems()]
    return Answer(data=udsm.table(), lines=lines or ["No UDSM models on this system."])


def list_models(args: argparse.Namespace) -> Answer:
    system = read(args).unit_system
    lines = []
    for word, model in MODEL_WORDS.items():
        found = soil_models.MODELS[model]
        lines.append(f"{word}  {found.label}  " + ", ".join(
            f"{law} ({dim}D)" for dim, law in found.laws.items()))
        lines += [f"  {title}: " + "; ".join(_parameter_line(p, system) for p in group)
                  for title, group in found.groups]
    table = soil_models.table()["models"]
    return Answer(data=[{"model": word, **table[model]} for word, model in MODEL_WORDS.items()],
                  lines=lines)


def _shown(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{value:g}" if isinstance(value, float) else str(value)


def _parameter_line(p: soil_models.Parameter, system: str) -> str:
    """One parameter as `material models` lists it: its default in the project's units
    (or "derived"), the values it can take, and when it is listed at all."""
    value = soil_models.default_in(p, system)
    if value is None:
        text = (f"{p.name} derived" if p.absent is None
                else f"{p.name} = {_shown(p.absent)} when left out")
    else:
        quantity = units.VARIABLES.get(p.name)
        unit = units.label(quantity, system) if quantity is not None else ""
        text = f"{p.name} = {_shown(value)}" + (f" {unit}" if unit else "")
    if p.required:
        text += " (required)"
    if p.choices:
        text += f" [{' | '.join(p.choices)}]"
    if p.when is not None:
        text += f", when {p.when[0]} is " + " or ".join(_shown(v) for v in p.when[1])
    if p.flow:
        text += (", when GEO_DRAINAGE_TYPE is " + " or ".join(soil_models.FLOWING)
                 + " or the project a groundwater flow calculation")
    return text


def list_presets(args: argparse.Namespace) -> Answer:
    if args.preset is None and args.model is not None:
        # The list shows each soil as its own model, so --model would change nothing.
        raise CommandError("--model needs a preset ID: `material P presets ID --model M`")
    if args.preset is not None:
        return _show_preset(args)
    return Answer(data=drafts.LIBRARY, lines=[
        f"{entry['id']}  {entry['name']}  ({soil_models.label(entry['model'])})  "
        f"E = {entry['variables']['YOUNG_MODULUS']:g} Pa"
        for entry in drafts.LIBRARY] + [
        "Each is added as its own soil model; --model adds it as another, as the "
        "material window's Model list does. `presets ID` shows one."])


def _show_preset(args: argparse.Namespace) -> Answer:
    """One preset as `material add --preset` would add it, in the project's units, as
    the material window's library Properties… shows it; nothing is written."""
    project = read(args)
    try:
        material, notes = drafts.soil(project, args.preset, preset=args.preset,
                                      model=_model(args))
    except drafts.DraftError as failure:
        raise CommandError(str(failure)) from None
    system = project.unit_system
    lines = [f"{material.name}  {soil_models.label(soil_models.model_of(material.constitutive_law))}"
             f" ({material.constitutive_law}), not in the project"]
    for name, value in material.variables.items():
        quantity = units.VARIABLES.get(name)
        unit = units.label(quantity, system) if quantity is not None else ""
        lines.append(f"  {name} = {_shown(value)}" + (f" {unit}" if unit else ""))
    lines.append(f"  R_inter = {_shown(material.r_inter)}, interface permeability "
                 f"{material.interface_permeability}")
    return Answer(data=material.model_dump(mode="json"), lines=lines + notes)


@named_ids(required=True)
def add_material(args: argparse.Namespace) -> Answer:
    project = read(args)
    model = _model(args)
    if args.udsm is not None and model is None and args.law is None:
        model = soil_models.UDSM
    try:
        material, notes = drafts.soil(project, args.id, name=args.name, preset=args.preset,
                                      color=args.color, law=args.law, model=model)
    except drafts.DraftError as failure:
        raise CommandError(str(failure)) from None
    project = session.add_material(project, material)
    variables = assignments(args.variables)
    if variables or args.r_inter is not None or args.udsm is not None:
        project = session.update_material(project, args.id, variables=variables,
                                          r_inter=args.r_inter, udsm=args.udsm)
    answer = edited(args, project, f"added material {args.id}")
    answer.lines += notes
    # A new soil is blank, as the GUI's Create soil makes it: said, as its window says it.
    added = project.material(args.id)
    lacks = soil_models.missing(added.constitutive_law, added.variables)
    if lacks:
        answer.lines.append(f"Still to fill in before a calculation: {', '.join(lacks)} "
                            f"(`material set {args.id} NAME=VALUE`).")
    return answer


def update_material(args: argparse.Namespace) -> Answer:
    notes: list[str] = []
    project = session.update_material(read(args), args.id,
                                      name=args.name, color=args.color, law=args.law,
                                      model=_model(args),
                                      variables=assignments(args.variables),
                                      unset=args.unset, notes=notes,
                                      r_inter=args.r_inter, udsm=args.udsm)
    answer = edited(args, project, f"changed material {args.id}")
    answer.lines += notes
    return answer


def remove_material(args: argparse.Namespace) -> Answer:
    project = session.remove_material(read(args), args.id)
    return edited(args, project, f"removed material {args.id}")




# ── layers ──────────────────────────────────────────────────────────────────

def list_layers(args: argparse.Namespace) -> Answer:
    project = read(args)
    lines = []
    for layer in project.layers:
        lines.append(f"{layer.id}  {layer.name}  of {layer.mat}: "
                     f"{layer.top:g} .. {layer.bottom:g}")
    return Answer(data=[layer.model_dump(mode="json") for layer in project.layers],
                  lines=lines or ["No layers yet."])


@named_ids(required=True)
def add_layer(args: argparse.Namespace) -> Answer:
    project = session.add_layer(read(args), args.id, args.material,
                                name=args.name, bottom=args.bottom, thickness=args.thickness)
    return edited(args, project, f"added layer {args.id}")


def update_layer(args: argparse.Namespace) -> Answer:
    project = session.update_layer(read(args), args.id,
                                   material=args.material, name=args.name, top=args.top,
                                   bottom=args.bottom)
    return edited(args, project, f"changed layer {args.id}")


def split_layer(args: argparse.Namespace) -> Answer:
    before = read(args)
    project = session.split_layer(before, args.id, args.new_id)
    new = project.layers[[layer.id for layer in project.layers].index(args.id) + 1].id
    return edited(args, project, f"split layer {args.id}; its lower half is {new}")


def remove_layer(args: argparse.Namespace) -> Answer:
    project = session.remove_layer(read(args), args.id)
    return edited(args, project, f"removed layer {args.id}")


# ── parts ───────────────────────────────────────────────────────────────────

def list_parts(args: argparse.Namespace) -> Answer:
    """Every part of the model by its key -- the names stages activate and deactivate --
    with what to call it and whether a stage can switch it."""
    project = read(args)
    labels = session.part_names(project)
    for part in project.custom_parts:
        if part.mat:
            labels[part.key] += f" (soil of {part.mat})"
    stageable = project.stageable_keys()
    keys = list(dict.fromkeys([*project.part_keys(), *stageable]))
    rows = [{"key": key, "label": labels.get(key, key), "stageable": key in stageable}
            for key in keys]
    return Answer(data=rows, lines=[
        f"{row['key']}  {row['label']}" + ("" if row["stageable"] else "  (not staged)")
        for row in rows] or ["No parts yet."])
