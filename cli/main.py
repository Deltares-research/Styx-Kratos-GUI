"""`kratos-cli`: build a model, mesh it, stage it, write its Kratos deck, run it and read
the results -- in the terminal, without the GUI or its server.

It edits the same project file the GUI's Save writes, through the same edits
(`core.session`), so a model can go from one to the other at any point. The plan and its
decisions are plan/active/cli-plan.md; `kratos-cli <command> --help` says what each
command takes.
"""

from __future__ import annotations

import argparse
import sys

from cli import output, style
from cli.commands import (analysis, edit, ground, inspection, interactive, meshing, phases,
                          project, results, structures, volumes)

GROUPS = (project, edit, ground, volumes, structures, meshing, phases, inspection, analysis,
          results, interactive)
"""The command modules, in the order a model is worked through; `--help` lists them so."""


class Parser(argparse.ArgumentParser):
    """argparse's parser, saying a command line it cannot read in the colours of the
    rest (`cli.style`). Its commands' parsers are of this class too: argparse makes a
    subparser of its parent's class."""

    def error(self, message: str):
        on = style.enabled(sys.stderr)
        sys.stderr.write(style.paint(self.format_usage().rstrip("\n"), "dim", on) + "\n")
        self.exit(2, f"{self.prog}: {style.paint('error:', 'bold red', on)} {message}\n")


def parser() -> argparse.ArgumentParser:
    top = Parser(
        prog="kratos-cli",
        description="Build, mesh, stage, export, run and read a Kratos geotechnical "
                    "model in the terminal. The project file is the one the GUI saves.")
    top.add_argument("--json", action="store_true", help="answer in JSON, for a script to read")
    # Accepted after the command as well, where it is easy to put it. Its own action,
    # not the top parser's: argparse shares an action between a parser and its parents,
    # and SUPPRESS is what keeps a command's parser from resetting the one given first.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="answer in JSON, for a script to read")
    commands = top.add_subparsers(dest="command", metavar="<command>", required=True)
    for group in GROUPS:
        group.register(commands, common)
    return top


def main(argv: list[str] | None = None) -> int:
    top = parser()
    try:
        args, extra = top.parse_known_args(argv)
        if extra:
            # A command that takes NAME=VALUE variables takes them anywhere on the line,
            # between its options too, which argparse cannot place itself; it is given
            # the words no option took, and says itself which of them is not a variable.
            if getattr(args, "variables", None) is None:
                top.error("unrecognized arguments: " + " ".join(extra))
            args.variables = [*args.variables, *extra]
        if args.json and getattr(args, "csv", False):
            top.error("--json and --csv: give one of them")
    except SystemExit as stop:
        # --help (0) and a command line argparse cannot read (2), said by argparse.
        return stop.code if isinstance(stop.code, int) else 0
    try:
        answer = args.handler(args)
    except Exception as failure:
        if isinstance(failure, refusals()):
            return output.refused(failure, args.json)
        raise
    return output.answered(answer, args.json, getattr(args, "csv", None))


def refusals() -> tuple[type[Exception], ...]:
    """The failures that are an answer -- the model, a file or Kratos said no, each with
    a message written to be read -- rather than a fault in this program, which is left
    to raise with its traceback.

    Imported only when something has failed: the geometry modules bring gmsh with them,
    and a command that never meshes should not pay for loading it.
    """
    from pydantic import ValidationError

    from core import scripting, session
    from core.analysis import calculation
    from core.geometry.cad_import import ImportRefused
    from core.geometry.meshing import MeshingError
    from core.geometry.solid_model import GeometryError
    from core.kratos.external_deck import DeckError
    from core.kratos.writer import ExportError
    from core.model.drafts import DraftError
    from core.model.phases import PhaseError
    from core.results.catalog import ResultsError
    from core.results.fields import UnknownField
    from core.results.members import UnknownQuantity

    return (output.CommandError, session.ProjectFileError, session.EditRefused,
            ValidationError, PhaseError, scripting.ScriptError, DeckError,
            calculation.CalculationError, ResultsError, GeometryError, MeshingError,
            ExportError, ImportRefused, DraftError, UnknownField, UnknownQuantity)
