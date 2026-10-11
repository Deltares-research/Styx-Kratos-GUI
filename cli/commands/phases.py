"""`phases`: the construction sequence -- the stages Kratos runs, one after the other.

`list` says what the sequence is; `defaults` makes the initial stage and the null step
(`core.session.default_phases`), and replaces whatever is there, as the GUI's "Create
default phases" does. Any phase can be edited by path meanwhile -- `kratos-cli set
site.json phases[dig_1].deactivate '["soil_L1"]'` -- and is checked to run in one order.
"""

from __future__ import annotations

import argparse

from cli.files import add_project, add_writing, written
from cli.output import Answer
from core import session


def register(commands, common: argparse.ArgumentParser) -> None:
    phases = commands.add_parser("phases", parents=[common],
                                 help="list the phases, or make the default ones")
    add_project(phases)
    phases.add_argument("action", choices=("list", "defaults"), nargs="?", default="list")
    add_writing(phases)
    phases.set_defaults(handler=phases_command)


def phases_command(args: argparse.Namespace) -> Answer:
    project = session.load(args.project)
    if args.action == "defaults":
        project = session.default_phases(project)
        target, where = written(args, project)
        return Answer(data={"file": str(target) if target else None,
                            "phases": _records(project)},
                      lines=[*_listed(project), where])
    return Answer(data=_records(project), lines=_listed(project))


def _records(project) -> list[dict]:
    return [phase.model_dump(mode="json") for phase in project.phases]


def _listed(project) -> list[str]:
    if not project.phases:
        return [f"No phases: {project.name} runs as one stage. `kratos-cli phases "
                "<project> defaults` makes the initial stage and the null step."]
    lines = []
    for number, phase in enumerate(project.phases, start=1):
        lines.append(f"{number}  {phase.id}  {phase.name}"
                     + (f"  (after {phase.parent})" if phase.parent else ""))
        details = [f"calculation: {phase.calculation}"] if getattr(phase, "calculation", None) else []
        if phase.activate:
            details.append("activates " + ", ".join(phase.activate))
        if phase.deactivate:
            details.append("deactivates " + ", ".join(phase.deactivate))
        if details:
            lines.append("     " + "; ".join(details))
    return lines
