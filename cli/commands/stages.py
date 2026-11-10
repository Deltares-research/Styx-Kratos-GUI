"""`stages`: the construction sequence -- the stages Kratos runs, one after the other.

A stage says what it changes about the model it starts from: the parts it switches on
and off, and how it is solved. Each edit here is the one the GUI's Stages toolbar and
Model explorer make (`core.model.stages`), stored the way the GUI stores it
(`core.session`):

    list               the sequence (also with no action)
    show ID            what is in the model during a stage, and what it changes
    defaults           the initial stage and the null step, as "Create default stages"
    add [ID]           a stage at the end, or --before a stage (the toolbar's Insert)
    copy ID            the toolbar's Copy: the same solver settings, after the original
    set ID             a stage's name, calculation and solver settings
    remove ID          the toolbar's Delete: the stage goes, and the chain is healed
    activate ID KEY... / deactivate ID KEY...
                       parts in or out of the model from that stage on, with the
                       smallest instruction that does it, as the explorer's checkbox

A sequence that would branch, or a part the model does not have, is refused. So is
--reset-displacements or --keep-displacements on a groundwater flow stage, which has no
displacements: the GUI greys that box out.
"""

from __future__ import annotations

import argparse

from cli.terminal.files import add_project, add_writing, read, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import NAME_HELP, existing, file_of, given, id_and_name, id_help, named_ids
from core import session
from core.model import stages
from core.model.schemas import Project

CALCULATIONS = {"k0": "K0 procedure", "k0 procedure": "K0 procedure", "k0-procedure":
                "K0 procedure", "plastic": "Plastic", "null": "Null step",
                "null step": "Null step", "null-step": "Null step",
                "flow": stages.GROUNDWATER_FLOW, "groundwater flow": stages.GROUNDWATER_FLOW,
                "groundwater-flow": stages.GROUNDWATER_FLOW}


def register(commands, common: argparse.ArgumentParser) -> None:
    parser = commands.add_parser("stages", aliases=["phases"], parents=[common],
                                 help="list, add, change or remove the stages "
                                      "('phases' still works)")
    add_project(parser)
    parser.set_defaults(handler=list_stages)
    actions = parser.add_subparsers(dest="action", metavar="<action>")

    listed = actions.add_parser("list", parents=[common], help="the sequence")
    listed.set_defaults(handler=list_stages)
    show = actions.add_parser("show", parents=[common],
                              help="what is in the model during a stage")
    existing(show, "stage", "stages")
    show.set_defaults(handler=show_stage)

    whole = actions.add_parser("defaults", parents=[common],
                               help="make the initial stage and the null step, replacing "
                                    "the sequence")
    add_writing(whole)
    whole.set_defaults(handler=default_stages)

    add = actions.add_parser("add", parents=[common],
                             help="a stage at the end of the sequence, or --before one")
    add.add_argument("id", nargs="?", help=id_help("the first free stage_<n>"))
    add.add_argument("--before", metavar="STAGE",
                     help="insert it between this stage and the one it starts from")
    _stage_fields(add)
    _parts(add)
    add_writing(add)
    add.set_defaults(handler=add_stage)

    copy = actions.add_parser("copy", parents=[common],
                              help="a stage with the same solver settings, after it")
    copy.add_argument("original")
    copy.add_argument("--id", help=id_help("the first free stage_<n>"))
    _stage_fields(copy)
    _parts(copy)
    add_writing(copy)
    copy.set_defaults(handler=copy_stage)

    change = actions.add_parser("set", parents=[common], help="change a stage")
    existing(change, "stage", "stages")
    _stage_fields(change)
    change.add_argument("--parent", help="the stage it starts from")
    add_writing(change)
    change.set_defaults(handler=update_stage)

    remove = actions.add_parser("remove", parents=[common],
                                help="remove a stage; its children start from its parent")
    existing(remove, "stage", "stages")
    add_writing(remove)
    remove.set_defaults(handler=remove_stage)

    for name, wanted in (("activate", True), ("deactivate", False)):
        switch = actions.add_parser(
            name, parents=[common],
            help=f"switch parts {'into' if wanted else 'out of'} the model from a stage on")
        existing(switch, "stage", "stages")
        switch.add_argument("keys", nargs="+", metavar="KEY",
                            help="part keys, as `kratos-cli parts` lists them")
        add_writing(switch)
        switch.set_defaults(handler=switch_parts, wanted=wanted)


def _calculation(word: str) -> str:
    try:
        return CALCULATIONS[word.strip().lower()]
    except KeyError:
        raise argparse.ArgumentTypeError(
            f"{word!r} is not a calculation type: use k0, plastic, null or flow") from None


def _stage_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--calculation", type=_calculation,
                        help="k0 (the K0 procedure), plastic, null (a null step) or flow "
                             "(groundwater flow)")
    reset = parser.add_mutually_exclusive_group()
    reset.add_argument("--reset-displacements", dest="reset_displacements",
                       action="store_const", const=True,
                       help="start the stage's displacements from zero")
    reset.add_argument("--keep-displacements", dest="reset_displacements",
                       action="store_const", const=False)
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--tolerance", type=float, dest="tolerated_error",
                        help="the residual relative tolerance")
    parser.add_argument("--time-interval", type=float, help="in days")


def _parts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--activate", nargs="+", default=[], metavar="KEY",
                        help="parts it switches into the model")
    parser.add_argument("--deactivate", nargs="+", default=[], metavar="KEY",
                        help="parts it switches out of the model; every part starts in the "
                             "model, so the first stage switches off what is not built yet")


FIELDS = ("name", "calculation", "reset_displacements", "max_iterations", "tolerated_error",
          "time_interval")


# ── Handlers ────────────────────────────────────────────────────────────────

def list_stages(args: argparse.Namespace) -> Answer:
    project = read(args)
    return Answer(data=_records(project), lines=_listed(project))


def show_stage(args: argparse.Namespace) -> Answer:
    project = read(args)
    stage = session.find_stage(project, args.id)
    active = stages.active_parts(project, args.id)
    keys = [key for key in project.stageable_keys() if key in active]
    out = [key for key in project.stageable_keys() if key not in active]
    lines = [f"{stage.id}  {stage.name}" + (f"  (after {stage.parent})" if stage.parent
                                            else ""),
             "  " + _settings(stage),
             "  in the model: " + (", ".join(keys) or "nothing"),
             "  not in the model: " + (", ".join(out) or "nothing")]
    if stage.activate:
        lines.append("  switches on: " + ", ".join(stage.activate))
    if stage.deactivate:
        lines.append("  switches off: " + ", ".join(stage.deactivate))
    return Answer(data={"stage": stage.model_dump(mode="json"), "active": keys,
                        "inactive": out}, lines=lines)


def default_stages(args: argparse.Namespace) -> Answer:
    return _replaced(args, session.default_stages(read(args)))


@named_ids()
def add_stage(args: argparse.Namespace) -> Answer:
    project, stage = session.add_stage(read(args), before=args.before,
                                       id=args.id, **given(args, *FIELDS))
    _no_reset_in_flow(args, stage)
    return _added(args, project, stage)


@named_ids()
def copy_stage(args: argparse.Namespace) -> Answer:
    project, stage = session.add_stage(read(args), copy_of=args.original,
                                       id=args.id, **given(args, *FIELDS))
    _no_reset_in_flow(args, stage)
    return _added(args, project, stage)


def update_stage(args: argparse.Namespace) -> Answer:
    project = session.update_stage(read(args), args.id,
                                   **given(args, *FIELDS, "parent"))
    _no_reset_in_flow(args, session.find_stage(project, args.id))
    return _edited(args, project, f"changed stage {args.id}")


def remove_stage(args: argparse.Namespace) -> Answer:
    project = session.remove_stage(read(args), args.id)
    return _edited(args, project, f"removed stage {args.id}")


def switch_parts(args: argparse.Namespace) -> Answer:
    project = session.switch_parts(read(args), args.id, args.keys,
                                   args.wanted)
    did = "into" if args.wanted else "out of"
    return _edited(args, project,
                   f"{', '.join(args.keys)} {did} the model from stage {args.id} on")


# ── Shared ──────────────────────────────────────────────────────────────────

def _no_reset_in_flow(args: argparse.Namespace, stage) -> None:
    """A groundwater flow stage solves the water pressure alone: the box that resets
    its displacements is greyed out in the GUI, and the option refused here."""
    if args.reset_displacements is not None and stage.calculation == stages.GROUNDWATER_FLOW:
        raise CommandError(f"stage {stage.id!r} is a groundwater flow stage, which has no "
                           "displacements: leave out --reset-displacements and "
                           "--keep-displacements.")


def _added(args: argparse.Namespace, project: Project, stage) -> Answer:
    for keys, wanted in ((args.activate, True), (args.deactivate, False)):
        if keys:
            project = session.switch_parts(project, stage.id, keys, wanted)
    return _edited(args, project, f"added stage ({id_and_name(stage)}) after "
                                  f"{stage.parent or 'nothing: it is the first'}")


def _edited(args: argparse.Namespace, project: Project, did: str) -> Answer:
    target, where = written(args, project)
    return Answer(data={"file": file_of(target), "stages": _records(project)},
                  lines=[f"{did}; {where}"])


def _replaced(args: argparse.Namespace, project: Project) -> Answer:
    target, where = written(args, project)
    return Answer(data={"file": file_of(target), "stages": _records(project)},
                  lines=[*_listed(project), where])


def _records(project) -> list[dict]:
    return [stage.model_dump(mode="json") for stage in project.stages]


def _settings(stage) -> str:
    settings = [f"calculation: {stage.calculation}",
                f"{stage.max_iterations} iterations, tolerance {stage.tolerated_error:g}"]
    if stage.reset_displacements and stage.calculation != stages.GROUNDWATER_FLOW:
        settings.append("displacements reset")
    if stage.time_interval:
        settings.append(f"{stage.time_interval:g} days")
    return "; ".join(settings)


def _listed(project) -> list[str]:
    if not project.stages:
        return [f"No stages: {project.name} runs as one stage. `kratos-cli stages "
                "<project> defaults` makes the initial stage and the null step."]
    lines = []
    for number, stage in enumerate(project.stages, start=1):
        lines.append(f"{number}  {stage.id}  {stage.name}"
                     + (f"  (after {stage.parent})" if stage.parent else ""))
        details = [f"calculation: {stage.calculation}"]
        if stage.activate:
            details.append("activates " + ", ".join(stage.activate))
        if stage.deactivate:
            details.append("deactivates " + ", ".join(stage.deactivate))
        lines.append("     " + "; ".join(details))
    return lines
