"""`phases`: the construction sequence -- the stages Kratos runs, one after the other.

A phase says what it changes about the model it starts from: the parts it switches on
and off, and how it is solved. Each edit here is the one the GUI's Phases toolbar and
Model explorer make (`core.model.phases`), stored the way the GUI stores it
(`core.session`):

    list               the sequence (also with no action)
    show ID            what is in the model during a phase, and what it changes
    defaults           the initial stage and the null step, as "Create default phases"
    staged-excavation  the whole sequence derived from the model: settle, build the
                       wall, then dig and prop lift by lift
    add [ID]           a phase at the end, or --before a phase (the toolbar's Insert)
    copy ID            the toolbar's Copy: the same solver settings, after the original
    set ID             a phase's name, calculation and solver settings
    remove ID          the toolbar's Delete: the phase goes, and the chain is healed
    activate ID KEY... / deactivate ID KEY...
                       parts in or out of the model from that phase on, with the
                       smallest instruction that does it, as the explorer's checkbox

A sequence that would branch, or a part the model does not have, is refused.
"""

from __future__ import annotations

import argparse

from cli.terminal.files import add_project, add_writing, written
from cli.terminal.output import Answer
from cli.terminal.words import file_of, given
from core import session
from core.model import phases
from core.model.schemas import Project

CALCULATIONS = {"k0": "K0 procedure", "k0 procedure": "K0 procedure", "k0-procedure":
                "K0 procedure", "plastic": "Plastic", "null": "Null step",
                "null step": "Null step", "null-step": "Null step"}


def register(commands, common: argparse.ArgumentParser) -> None:
    parser = commands.add_parser("phases", parents=[common],
                                 help="list, add, change or remove the phases")
    add_project(parser)
    parser.set_defaults(handler=list_phases)
    actions = parser.add_subparsers(dest="action", metavar="<action>")

    listed = actions.add_parser("list", parents=[common], help="the sequence")
    listed.set_defaults(handler=list_phases)
    show = actions.add_parser("show", parents=[common],
                              help="what is in the model during a phase")
    show.add_argument("id")
    show.set_defaults(handler=show_phase)

    for name, handler, help in (
            ("defaults", default_phases, "make the initial stage and the null step, "
                                         "replacing the sequence"),
            ("staged-excavation", staged_phases,
             "derive the whole staged-excavation sequence from the model, replacing it")):
        whole = actions.add_parser(name, parents=[common], help=help)
        add_writing(whole)
        whole.set_defaults(handler=handler)

    add = actions.add_parser("add", parents=[common],
                             help="a phase at the end of the sequence, or --before one")
    add.add_argument("id", nargs="?", help="its id (default: the first free phase_<n>)")
    add.add_argument("--before", metavar="PHASE",
                     help="insert it between this phase and the one it starts from")
    _phase_fields(add)
    _parts(add)
    add_writing(add)
    add.set_defaults(handler=add_phase)

    copy = actions.add_parser("copy", parents=[common],
                              help="a phase with the same solver settings, after it")
    copy.add_argument("original")
    copy.add_argument("--id", help="the copy's id (default: the first free phase_<n>)")
    _phase_fields(copy)
    _parts(copy)
    add_writing(copy)
    copy.set_defaults(handler=copy_phase)

    change = actions.add_parser("set", parents=[common], help="change a phase")
    change.add_argument("id")
    _phase_fields(change)
    change.add_argument("--parent", help="the phase it starts from")
    add_writing(change)
    change.set_defaults(handler=update_phase)

    remove = actions.add_parser("remove", parents=[common],
                                help="remove a phase; its children start from its parent")
    remove.add_argument("id")
    add_writing(remove)
    remove.set_defaults(handler=remove_phase)

    for name, wanted in (("activate", True), ("deactivate", False)):
        switch = actions.add_parser(
            name, parents=[common],
            help=f"switch parts {'into' if wanted else 'out of'} the model from a phase on")
        switch.add_argument("id")
        switch.add_argument("keys", nargs="+", metavar="KEY",
                            help="part keys, as `kratos-cli parts` lists them")
        add_writing(switch)
        switch.set_defaults(handler=switch_parts, wanted=wanted)


def _calculation(word: str) -> str:
    try:
        return CALCULATIONS[word.strip().lower()]
    except KeyError:
        raise argparse.ArgumentTypeError(
            f"{word!r} is not a calculation type: use k0, plastic or null") from None


def _phase_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name")
    parser.add_argument("--calculation", type=_calculation,
                        help="k0 (the K0 procedure), plastic or null (a null step)")
    reset = parser.add_mutually_exclusive_group()
    reset.add_argument("--reset-displacements", dest="reset_displacements",
                       action="store_const", const=True,
                       help="start the phase's displacements from zero")
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
                        help="parts it switches out of the model")


FIELDS = ("name", "calculation", "reset_displacements", "max_iterations", "tolerated_error",
          "time_interval")


# ── Handlers ────────────────────────────────────────────────────────────────

def list_phases(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    return Answer(data=_records(project), lines=_listed(project))


def show_phase(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    phase = session.find_phase(project, args.id)
    active = phases.active_parts(project, args.id)
    keys = [key for key in project.stageable_keys() if key in active]
    out = [key for key in project.stageable_keys() if key not in active]
    lines = [f"{phase.id}  {phase.name}" + (f"  (after {phase.parent})" if phase.parent
                                            else ""),
             "  " + _settings(phase),
             "  in the model: " + (", ".join(keys) or "nothing"),
             "  not in the model: " + (", ".join(out) or "nothing")]
    if phase.activate:
        lines.append("  switches on: " + ", ".join(phase.activate))
    if phase.deactivate:
        lines.append("  switches off: " + ", ".join(phase.deactivate))
    return Answer(data={"phase": phase.model_dump(mode="json"), "active": keys,
                        "inactive": out}, lines=lines)


def default_phases(args: argparse.Namespace) -> Answer:
    return _replaced(args, session.default_phases(session.load(args.project)))


def staged_phases(args: argparse.Namespace) -> Answer:
    return _replaced(args, session.staged_excavation_phases(session.load(args.project)))


def add_phase(args: argparse.Namespace) -> Answer:
    project, phase = session.add_phase(session.load(args.project), before=args.before,
                                       id=args.id, **given(args, *FIELDS))
    return _added(args, project, phase)


def copy_phase(args: argparse.Namespace) -> Answer:
    project, phase = session.add_phase(session.load(args.project), copy_of=args.original,
                                       id=args.id, **given(args, *FIELDS))
    return _added(args, project, phase)


def update_phase(args: argparse.Namespace) -> Answer:
    project = session.update_phase(session.load(args.project), args.id,
                                   **given(args, *FIELDS, "parent"))
    return _edited(args, project, f"changed phase {args.id}")


def remove_phase(args: argparse.Namespace) -> Answer:
    project = session.remove_phase(session.load(args.project), args.id)
    return _edited(args, project, f"removed phase {args.id}")


def switch_parts(args: argparse.Namespace) -> Answer:
    project = session.switch_parts(session.load(args.project), args.id, args.keys,
                                   args.wanted)
    did = "into" if args.wanted else "out of"
    return _edited(args, project,
                   f"{', '.join(args.keys)} {did} the model from phase {args.id} on")


# ── Shared ──────────────────────────────────────────────────────────────────

def _added(args: argparse.Namespace, project: Project, phase) -> Answer:
    for keys, wanted in ((args.activate, True), (args.deactivate, False)):
        if keys:
            project = session.switch_parts(project, phase.id, keys, wanted)
    return _edited(args, project, f"added phase {phase.id} ({phase.name}) after "
                                  f"{phase.parent or 'nothing: it is the first'}")


def _edited(args: argparse.Namespace, project: Project, did: str) -> Answer:
    target, where = written(args, project)
    return Answer(data={"file": file_of(target), "phases": _records(project)},
                  lines=[f"{did}; {where}"])


def _replaced(args: argparse.Namespace, project: Project) -> Answer:
    target, where = written(args, project)
    return Answer(data={"file": file_of(target), "phases": _records(project)},
                  lines=[*_listed(project), where])


def _records(project) -> list[dict]:
    return [phase.model_dump(mode="json") for phase in project.phases]


def _settings(phase) -> str:
    settings = [f"calculation: {phase.calculation}",
                f"{phase.max_iterations} iterations, tolerance {phase.tolerated_error:g}"]
    if phase.reset_displacements:
        settings.append("displacements reset")
    if phase.time_interval:
        settings.append(f"{phase.time_interval:g} days")
    return "; ".join(settings)


def _listed(project) -> list[str]:
    if not project.phases:
        return [f"No phases: {project.name} runs as one stage. `kratos-cli phases "
                "<project> defaults` makes the initial stage and the null step."]
    lines = []
    for number, phase in enumerate(project.phases, start=1):
        lines.append(f"{number}  {phase.id}  {phase.name}"
                     + (f"  (after {phase.parent})" if phase.parent else ""))
        details = [f"calculation: {phase.calculation}"]
        if phase.activate:
            details.append("activates " + ", ".join(phase.activate))
        if phase.deactivate:
            details.append("deactivates " + ", ".join(phase.deactivate))
        lines.append("     " + "; ".join(details))
    return lines
