"""`shell`: the commands typed one after another, with a project open (`cli/terminal/shell.py`)."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.terminal.output import Answer


def register(commands, common: argparse.ArgumentParser) -> None:
    shell = commands.add_parser(
        "shell", parents=[common], help="type commands one after another, a project open",
        description="Type kratos-cli commands one after another, without `kratos-cli` and "
                    "without the project file: `water -2`, `mesh`, `results runs`. The "
                    "shell puts the open project where a command takes one. Its own "
                    "words are open, close, new, undo, redo, cd, pwd, source, help and "
                    "exit. Read from a pipe or a file, it stops at the first command "
                    "that fails.")
    shell.add_argument("project", type=Path, nargs="?",
                       help="the project file (.json) or model script (.py) to open")
    shell.set_defaults(handler=run_shell)


def run_shell(args: argparse.Namespace) -> Answer:
    from cli.terminal.shell import Shell

    if args.project is not None and not args.project.is_file():
        from cli.terminal.output import CommandError
        raise CommandError(f"no such file: {args.project}. `kratos-cli new {args.project}` "
                           "makes it, or start the shell without one and `new` it there.")
    shell = Shell(args.project)
    code = shell.loop()
    return Answer(data={"ok": code == 0}, lines=[],
                  error=(shell.stopped or "the shell stopped") if code else None)
