"""`stages`: the construction sequence -- the stages Kratos runs, one after the other.

A stage says what it changes about the model it starts from: the parts it switches on
and off, and how it is solved. Each edit here is the one the GUI's Stages toolbar and
Model explorer make (`core.model.stages`), stored the way the GUI stores it
(`core.session`):

    list               the sequence (also with no action)
    show ID            what is in the model during a stage, and what it changes
    add [ID]           a stage at the end, or --before a stage (the toolbar's Insert)
    copy ID            the toolbar's Copy: the same solver settings, after the original
    set ID             a stage's name, calculation type, stress initialisation,
                       time integration and solver settings -- the expert ones with
                       --solver KEY=VALUE, and back to their defaults with
                       --solver-default KEY
    remove ID          the toolbar's Delete: the stage goes, and the chain is healed
    activate ID KEY... / deactivate ID KEY...
                       parts in or out of the model from that stage on, with the
                       smallest instruction that does it, as the explorer's checkbox

A sequence that would branch, or a part the model does not have, is refused. So is
--reset-displacements or --keep-displacements on a flow stage, which has no
displacements: the GUI greys that box out; and a stress initialisation other than none
on a flow stage, which has no stresses: the GUI hides that row. So is a convergence
criterion the stage's calculation type does not have: a mechanical stage converges on
the residual or the displacement, a flow stage on the water pressure or the residual.
Making the sequence a flow one sets the stress initialisation to none, the
convergence criterion to the water pressure one and the expert solver settings back to
their defaults, as the GUI does. An expert setting a stage cannot have is refused by
name, with the ones it can.
"""

from __future__ import annotations

import argparse

from cli.terminal.files import add_project, add_writing, read, written
from cli.terminal.output import Answer, CommandError
from cli.terminal.words import NAME_HELP, existing, file_of, given, id_and_name, id_help, named_ids
from core import session
from core.model import solver, stages, units
from core.model.schemas import Project

CALCULATIONS = {"mechanical": "mechanical", "upw": "mechanical", "u_pw": "mechanical",
                "flow": stages.FLOW, "pw": stages.FLOW, "groundwater flow": stages.FLOW,
                "groundwater-flow": stages.FLOW}
STRESS_INITIALISATIONS = {"k0": "K0", "gravity": "gravity", "none": "none"}
TIME_INTEGRATIONS = {"static": "static", "dynamic": "dynamic"}
CRITERIA = {
    word: criterion
    for criterion in ("residual_criterion", "displacement_criterion",
                      "water_pressure_criterion")
    for stem in (criterion.removesuffix("_criterion"),)
    for word in (criterion, stem, stem.replace("_", "-"), stem.replace("_", " "))
}
"""Kratos' names for the convergence criteria, with and without `_criterion`, and with
hyphens or spaces for the underscores."""


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


def _choice(words: dict[str, str], what: str, use: str):
    def parse(word: str) -> str:
        try:
            return words[word.strip().lower()]
        except KeyError:
            raise argparse.ArgumentTypeError(
                f"{word!r} is not a {what}: use {use}") from None
    return parse


def _stage_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help=NAME_HELP)
    parser.add_argument("--calculation",
                        type=_choice(CALCULATIONS, "calculation type", "mechanical or flow"),
                        help="mechanical (deformation and water pressure, Kratos' U_Pw) or "
                             "flow (the water pressure alone, Kratos' Pw)")
    parser.add_argument("--stress-initialisation", "--stresses",
                        dest="stress_initialisation",
                        type=_choice(STRESS_INITIALISATIONS, "stress initialisation",
                                     "k0, gravity or none"),
                        help="of a mechanical stage: k0 (the K0 procedure), gravity "
                             "(gravity loading) or none")
    parser.add_argument("--time-integration",
                        type=_choice(TIME_INTEGRATIONS, "time integration",
                                     "static or dynamic"),
                        help="static or dynamic")
    reset = parser.add_mutually_exclusive_group()
    reset.add_argument("--reset-displacements", dest="reset_displacements",
                       action="store_const", const=True,
                       help="start the stage's displacements from zero")
    reset.add_argument("--keep-displacements", dest="reset_displacements",
                       action="store_const", const=False)
    parser.add_argument("--convergence-criterion", "--convergence",
                        dest="convergence_criterion",
                        type=_choice(CRITERIA, "convergence criterion",
                                     "residual, displacement or water_pressure"),
                        help="of a mechanical stage: residual (the default) or "
                             "displacement; of a flow stage: water_pressure (the default) "
                             "or residual")
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--tolerance", type=float, dest="tolerated_error",
                        help="the convergence criterion's relative tolerance")
    parser.add_argument("--absolute-tolerance", type=float,
                        help="the convergence criterion's absolute tolerance")
    parser.add_argument("--duration", type=float,
                        help="how long the stage lasts, in the project's unit of time (s)")
    parser.add_argument("--time-step", type=float,
                        help="the step it is solved in, in the same unit; at most the "
                             "duration")
    parser.add_argument("--solver", nargs="+", default=[], metavar="KEY=VALUE",
                        help="expert solver settings, by the names `stages show` lists: "
                             "e.g. strategy_type=newton_raphson linear_solver_type=amgcl. "
                             "A mechanical stage is solved by newton_raphson unless it "
                             "says otherwise")
    parser.add_argument("--solver-default", nargs="+", default=[], metavar="KEY",
                        help="put expert solver settings back to their defaults")


def _parts(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--activate", nargs="+", default=[], metavar="KEY",
                        help="parts it switches into the model")
    parser.add_argument("--deactivate", nargs="+", default=[], metavar="KEY",
                        help="parts it switches out of the model; every part starts in the "
                             "model, so the first stage switches off what is not built yet")


FIELDS = ("name", "calculation", "stress_initialisation", "time_integration",
          "reset_displacements", "convergence_criterion", "max_iterations",
          "tolerated_error", "absolute_tolerance", "duration", "time_step")


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
             "  " + _settings(stage, units.label(units.TIME, project.unit_system)),
             "  in the model: " + (", ".join(keys) or "nothing"),
             "  not in the model: " + (", ".join(out) or "nothing")]
    if stage.activate:
        lines.append("  switches on: " + ", ".join(stage.activate))
    if stage.deactivate:
        lines.append("  switches off: " + ", ".join(stage.deactivate))
    rows = _solver_rows(project, stage)
    lines.append("  expert solver settings (* set on this stage; --solver KEY=VALUE "
                 "changes one):")
    lines += [f"    {row['key']} = {solver.label(row['key'], row['value'])}"
              + (" *" if row["overridden"] else "")
              + (f"  (fixed: {row['locked']})" if row["locked"] else "")
              for row in rows]
    return Answer(data={"stage": stage.model_dump(mode="json"), "active": keys,
                        "inactive": out, "solver_settings": rows}, lines=lines)


def _solver_rows(project: Project, stage) -> list[dict]:
    """The expert settings that apply to `stage`, as the GUI's stage panel shows them."""
    return solver.resolve(stage.calculation, stage.time_integration,
                          stage.solver_settings, stages.model_strategy(project, stage))


@named_ids()
def add_stage(args: argparse.Namespace) -> Answer:
    fields = _fields(args)
    _with_solver(args, fields, {})
    project, stage = session.add_stage(read(args), before=args.before,
                                       id=args.id, **fields)
    _no_reset_in_flow(args, stage)
    return _added(args, project, stage)


@named_ids()
def copy_stage(args: argparse.Namespace) -> Answer:
    project = read(args)
    fields = _fields(args)
    original = session.find_stage(project, args.original)
    _with_solver(args, fields, original.solver_settings)
    project, stage = session.add_stage(project, copy_of=args.original, id=args.id,
                                       **fields)
    _no_reset_in_flow(args, stage)
    return _added(args, project, stage)


def update_stage(args: argparse.Namespace) -> Answer:
    project = read(args)
    fields = _fields(args, "parent")
    stage = session.find_stage(project, args.id)
    # A stage made another calculation type starts from that type's defaults.
    changes_type = fields.get("calculation", stage.calculation) != stage.calculation
    _with_solver(args, fields, {} if changes_type else stage.solver_settings)
    project = session.update_stage(project, args.id, **fields)
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

def _fields(args: argparse.Namespace, *more: str) -> dict:
    """The fields given, by their schema names. A stage made a flow stage has no
    stresses to initialise, so unless the command says otherwise its stress
    initialisation goes back to none, as the GUI's does. (Its convergence criterion goes
    to the new type's default in `stages.edited`.)"""
    fields = given(args, *FIELDS, *more)
    if fields.get("calculation", "mechanical") != "mechanical":
        fields.setdefault("stress_initialisation", "none")
    return fields


def _with_solver(args: argparse.Namespace, fields: dict, current: dict) -> None:
    """`fields` with the stage's expert settings as `--solver` and `--solver-default`
    leave them, starting from `current`, when either was given. The schema refuses a
    value a setting cannot have (`core.model.solver.problems`)."""
    if not args.solver and not args.solver_default:
        return
    settings = dict(current)
    for key in args.solver_default:
        _setting(key)
        settings.pop(key, None)
    for pair in args.solver:
        key, sep, text = pair.partition("=")
        if not sep:
            raise CommandError(f"--solver takes KEY=VALUE, not {pair!r}: e.g. "
                               "strategy_type=newton_raphson")
        settings[key.strip()] = _solver_value(key.strip(), text.strip())
    fields["solver_settings"] = settings


def _setting(key: str) -> dict:
    try:
        return solver.BY_KEY[key]
    except KeyError:
        raise CommandError(f"there is no solver setting {key!r}: use one of "
                           f"{', '.join(solver.BY_KEY)}") from None


TRUE, FALSE = ("true", "yes", "on", "1"), ("false", "no", "off", "0")


def _solver_value(key: str, text: str) -> object:
    """`text` as the value of setting `key`: true or false for a switch, a number, or
    one of a choice's values -- or its label, in any case."""
    setting = _setting(key)
    if setting["kind"] == "check":
        if text.lower() in TRUE + FALSE:
            return text.lower() in TRUE
        raise CommandError(f"{key} is true or false, not {text!r}")
    if setting["kind"] == "number":
        try:
            number = float(text)
        except ValueError:
            raise CommandError(f"{key} is a number, not {text!r}") from None
        return int(number) if setting.get("integer") and number == int(number) else number
    for value, label in setting["options"]:
        if text.lower() in (value.lower(), label.lower()):
            return value
    raise CommandError(f"{key} is one of {', '.join(v for v, _ in setting['options'])}, "
                       f"not {text!r}")


def _no_reset_in_flow(args: argparse.Namespace, stage) -> None:
    """A flow stage solves the water pressure alone: the box that resets its
    displacements is greyed out in the GUI, and the option refused here."""
    if args.reset_displacements is not None and stage.calculation == stages.FLOW:
        raise CommandError(f"stage {stage.id!r} is a flow stage, which has no "
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


def _records(project) -> list[dict]:
    return [stage.model_dump(mode="json") for stage in project.stages]


def _settings(stage, second: str) -> str:
    """`second` is the project's unit of time, as it is labelled."""
    settings = [_calculation(stage),
                f"{stage.convergence_criterion.replace('_', ' ')}, "
                f"{stage.max_iterations} iterations, tolerance {stage.tolerated_error:g} "
                f"(absolute {stage.absolute_tolerance:g})"]
    if stage.reset_displacements and stage.calculation != stages.FLOW:
        settings.append("displacements reset")
    settings.append(f"{stage.duration:g} {second} in steps of {stage.time_step:g} {second}")
    return "; ".join(settings)


def _listed(project) -> list[str]:
    if not project.stages:
        return [f"No stages: {project.name} runs as one stage. `kratos-cli stages "
                "<project> add` makes the first one."]
    lines = []
    for number, stage in enumerate(project.stages, start=1):
        lines.append(f"{number}  {stage.id}  {stage.name}"
                     + (f"  (after {stage.parent})" if stage.parent else ""))
        details = [_calculation(stage)]
        if stage.activate:
            details.append("activates " + ", ".join(stage.activate))
        if stage.deactivate:
            details.append("deactivates " + ", ".join(stage.deactivate))
        lines.append("     " + "; ".join(details))
    return lines


def _calculation(stage) -> str:
    """`calculation: mechanical, K0 stresses, static` -- the three choices of a stage."""
    words = [stage.calculation]
    if stage.stress_initialisation != "none":
        words.append(f"{stage.stress_initialisation} stresses")
    words.append(stage.time_integration)
    return "calculation: " + ", ".join(words)
