"""`domain`, `material`, `layer`, `excavation`, `parts`: the ground of a model.

Each edit is `core.session`'s, made the way the GUI's soil dialogs make it -- a moved
level moves its neighbour's, a deleted layer's neighbour closes the gap -- and each new
record starts as those dialogs start it (`core.model.drafts`). Materials are Kratos
property sets: a law and its variables under Kratos' names, typed as `NAME=VALUE` in the
project's own units. A soil model (`--model mohr-coulomb`) picks the law and fills in
the defaults the material window fills in (`core.model.soil_models`).
"""

from __future__ import annotations

import argparse

from cli.terminal.files import add_project, add_writing, read, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import (NAME_HELP, action, assignments, edited, existing, file_of,
                                id_help, named_ids, noun)
from core import session
from core.model import drafts, soil_models, units
from core.model.schemas import Project


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
    action(material, common, "presets", list_presets, writes=False,
            help="the material library a new soil can start from")
    action(material, common, "models", list_models, writes=False,
            help="the soil models (--model), each with its parameters and defaults in "
                 "the project's units")
    add = action(material, common, "add", add_material, variables=True,
                  help="a soil: the default sand, or a library preset, of a soil model, "
                       "then NAME=VALUE variables of its own")
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
    change.add_argument("--material")
    change.add_argument("--name", help=NAME_HELP)
    change.add_argument("--top", type=float)
    change.add_argument("--bottom", type=float)
    split = action(layer, common, "split", split_layer,
                    help="halve a layer; the lower half becomes a new layer")
    existing(split, "layer")
    split.add_argument("new_id", nargs="?")
    remove = action(layer, common, "remove", remove_layer)
    existing(remove, "layer")

    excavation = commands.add_parser("excavation", parents=[common],
                                     help="show or set the pit and the levels it is dug to")
    add_project(excavation)
    excavation.add_argument("--x", type=float, nargs=2, metavar=("FROM", "TO"))
    excavation.add_argument("--z", type=float, nargs=2, metavar=("FROM", "TO"))
    excavation.add_argument("--levels", type=float, nargs="+", metavar="Y",
                            help="the levels it is dug to, shallowest first: one lift each")
    add_writing(excavation)
    excavation.set_defaults(handler=set_excavation)

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


def _model(args: argparse.Namespace) -> str | None:
    return MODEL_WORDS[args.model] if args.model is not None else None


# ── domain, excavation ──────────────────────────────────────────────────────

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


def set_excavation(args: argparse.Namespace) -> Answer:
    project = read(args)
    if args.x is None and args.z is None and args.levels is None:
        pit = project.excavation
        return Answer(data=pit.model_dump(mode="json") if pit is not None else None,
                      lines=[_pit_line(project)])
    project, notes = session.set_excavation(project, x=args.x, z=args.z, levels=args.levels)
    target, where = written(args, project)
    return Answer(data={"file": file_of(target),
                        "excavation": project.pit().model_dump(mode="json"),
                        "notes": notes},
                  lines=[f"{_pit_line(project)}; {where}", *notes])


def _domain_line(project: Project) -> str:
    d = project.domain
    extent = f"domain x {d.x0:g} .. {d.x1:g}, y {d.y_bottom:g} .. {d.y_top:g}"
    if project.dimension == 2:
        # A 2D model is the cut at one z: the z range only bounds where it may be made.
        return f"{extent} (2D section at z = {project.section_offset:g})"
    return f"{extent}, z {d.z0:g} .. {d.z1:g}"


def _pit_line(project: Project) -> str:
    pit = project.excavation
    if pit is None:
        return "no excavation"
    return (f"excavation x {pit.x0:g} .. {pit.x1:g}, z {pit.z0:g} .. {pit.z1:g}, dug to "
            + ", ".join(f"{level:g}" for level in pit.levels))


# ── materials ───────────────────────────────────────────────────────────────

def list_materials(args: argparse.Namespace) -> Answer:
    project = read(args)
    return Answer(data=[m.model_dump(mode="json") for m in project.materials],
                  lines=[f"{m.id}  {m.name}  "
                         f"{soil_models.label(soil_models.model_of(m.constitutive_law))} "
                         f"({m.constitutive_law}), {len(m.variables)} variables"
                         for m in project.materials]
                  or ["No materials yet."])


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
    return text


def list_presets(args: argparse.Namespace) -> Answer:
    return Answer(data=drafts.LIBRARY, lines=[
        f"{entry['id']}  {entry['name']}  E = {entry['variables']['YOUNG_MODULUS']:g} Pa"
        for entry in drafts.LIBRARY])


@named_ids(required=True)
def add_material(args: argparse.Namespace) -> Answer:
    project = read(args)
    try:
        material, notes = drafts.soil(project, args.id, name=args.name, preset=args.preset,
                                      color=args.color, law=args.law, model=_model(args))
    except drafts.DraftError as failure:
        raise CommandError(str(failure)) from None
    project = session.add_material(project, material)
    variables = assignments(args.variables)
    if variables:
        project = session.update_material(project, args.id, variables=variables)
    answer = edited(args, project, f"added material {args.id}")
    answer.lines += notes
    return answer


def update_material(args: argparse.Namespace) -> Answer:
    notes: list[str] = []
    project = session.update_material(read(args), args.id,
                                      name=args.name, color=args.color, law=args.law,
                                      model=_model(args),
                                      variables=assignments(args.variables),
                                      unset=args.unset, notes=notes)
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
