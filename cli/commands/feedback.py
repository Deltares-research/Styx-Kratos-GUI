"""`feedback`: a feedback report as a ZIP file, the one the GUI's Feedback window saves.

    kratos-cli feedback "MESSAGE" [--kind KIND] [--name NAME] [--project FILE] [--run RUN]
                                  [--attach FILE ...]

The kinds are the GUI's: `bug` (something is wrong), `confusing`, `missing` and `good`
(something works well). The project file goes in the report as it is, and so do the files
of `--attach` (a screenshot, a document, any file) and the Kratos log and parameter files of
the run. The report goes in the
writer's ZIP file of the day, the one the GUI adds to, in the feedback folder
(`~/KratosGUI/feedback`, or `KRATOS_GUI_FEEDBACK`) or in `--out`. `core/feedback.py` writes it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands import results as run_commands
from cli.terminal.files import add_runs_dir, environment
from cli.terminal.output import Answer, CommandError
from core import feedback
from core.version import describe


def register(commands, common: argparse.ArgumentParser) -> None:
    parser = commands.add_parser(
        "feedback", parents=[common], help="save a feedback report in your ZIP file of the day",
        description="Save what you want to say about Styx, with the model and the run it is "
                    "about. All your reports of one day go in one ZIP file, the one the GUI's "
                    "Feedback window adds to, in ~/KratosGUI/feedback or "
                    "$KRATOS_GUI_FEEDBACK.")
    parser.add_argument("message", help="what happened, or what you would like to see")
    parser.add_argument("--kind", choices=list(feedback.KINDS), default="bug",
                        help="; ".join(f"{kind}: {said.lower()}"
                                       for kind, said in feedback.KINDS.items())
                             + " (default: bug)")
    parser.add_argument("--name", default="",
                        help="your name, so that the report can be followed up")
    parser.add_argument("--project", type=Path, metavar="FILE",
                        help="the project file (.json) or model script (.py) it is about; "
                             "a copy goes in the report")
    parser.add_argument("--run", metavar="RUN",
                        help="the run it is about: its id, its number in `results runs`, or a "
                             "run directory; its Kratos log and parameter files go in the report")
    parser.add_argument("--attach", type=Path, metavar="FILE", action="append", default=[],
                        help="a file to add to the report: a screenshot, a document, any file; "
                             "give it once for each file")
    add_runs_dir(parser)
    parser.add_argument("--out", type=Path, metavar="DIR",
                        help="the folder to save the report in (default: the feedback folder)")
    parser.set_defaults(handler=save_feedback)


def save_feedback(args: argparse.Namespace) -> Answer:
    project, project_file = None, "project.json"
    if args.project is not None:
        if not args.project.is_file():
            raise CommandError(f"no such project file: {args.project}")
        project = args.project.read_text(encoding="utf-8", errors="replace")
        project_file = args.project.name
    for path in args.attach:
        if not path.is_file():
            raise CommandError(f"no such file to attach: {path}")
    attachments = [(path.name, path.read_bytes()) for path in args.attach]
    with environment(args):
        run = run_commands._run(args.run) if args.run else None
        report = feedback.Report(kind=args.kind, message=args.message, name=args.name,
                                 source="kratos-cli", version=describe(),
                                 context={"command": "kratos-cli feedback"},
                                 project=project, project_file=project_file,
                                 attachments=attachments, run=run)
        if run is not None and feedback.run_directory(run) is None:
            raise CommandError(f"no such run: {args.run}. `kratos-cli results runs` lists them.")
        try:
            saved = feedback.write(report, args.out)
        except feedback.FeedbackError as failure:
            raise CommandError(str(failure)) from failure
    path = saved.path
    held = "1 report" if saved.reports == 1 else f"{saved.reports} reports"
    return Answer(data={"path": str(path), "folder": str(path.parent), "name": path.name,
                        "report": saved.report, "files": saved.files,
                        "reports": saved.reports},
                  lines=[f"added {saved.report} to {path} ({held} in it now)",
                         "At the end of the day, send this file to the Styx team, or put it "
                         "in the workshop's shared folder."])
