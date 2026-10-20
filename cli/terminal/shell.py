"""`kratos-cli shell [P]`: the commands, typed one after another in one process, with a
project open (plan/active/cli-plan.md, SH).

A line is a `kratos-cli` command without `kratos-cli` and without the project file --
`water -2`, `borehole add bh4`, `mesh`, `results field 1 uy`. The open project goes where
the command takes one (`_with_project`): after the command word (`borehole P add`), or
after the action for a command whose action comes first. A project or a
deck named on the line is the one used. The line then runs as `cli.terminal.main` runs any
command line, so the shell has no commands, answers or refusals of its own to drift
from the terminal's -- only these words:

    open FILE   close   new FILE ...   undo   redo   cd DIR   pwd   source FILE
    help [COMMAND]   exit   quit

`undo` and `redo` step through the edits of the open project file, as the GUI's do: each
command that changed the file is one step.

**Typed, or read.** At a terminal there is a prompt, and the shell goes on after a
command fails or faults (the fault's traceback is shown). Read from a pipe or a file
(`kratos-cli shell P < commands.txt`), each line is echoed as `> line` and the first
command that fails stops it, as `set -e` would; the exit code is then 1, and the error
names the line. `source FILE` reads a file the same way from inside the shell.

**Words** are split as a POSIX shell splits them -- quotes group, `#` starts a comment
only at the beginning of a line (a colour is `#c4a86a`) -- except that a backslash is
kept, because it is a Windows path's separator.

Commands run in this process, so a line costs no new Python and no new import: a model
typed here is built in a fraction of the time the same commands take one by one.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys
import textwrap
import traceback
from collections.abc import Callable
from pathlib import Path

from cli.terminal import output, style

WORDS = {
    "open": ("open FILE", "work on another project file (.json, or a .py to read)"),
    "close": ("close", "put the project down"),
    "new": ("new FILE ...", "make a project file, as `kratos-cli new`, and open it"),
    "undo": ("undo", "take back the last edit of the open project"),
    "redo": ("redo", "put back what undo took"),
    "cd": ("cd DIR", "go to another folder; the open project stays open"),
    "pwd": ("pwd", "the folder relative paths are read from"),
    "source": ("source FILE", "run the lines of a file; the first that fails stops it"),
    "help": ("help [COMMAND]", "this, or what COMMAND takes"),
    "exit": ("exit, quit", "leave (also Ctrl-D, or Ctrl-Z then Enter on Windows)"),
    "quit": None,
}
"""The shell's own words, and how `help` says each: as typed, and what it does."""

PROJECT_SLOT = "project"
"""The positional the open project goes into. A command whose project has another name
says which with a `project_slot` default (`node`, whose SOURCE may be a project)."""

MODEL_SUFFIXES = (".json", ".py")


class Leave(Exception):
    """`exit`."""


BOM = "\ufeff"
"""What Windows PowerShell puts before the first line it pipes into a program."""


def words(line: str) -> list[str]:
    """The words of `line`, as the shell runs them; [] for a blank line or a comment."""
    line = line.lstrip(BOM)
    if not line.strip() or line.lstrip().startswith("#"):
        return []
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.escape = ""
    return list(lexer)


def _has_words(line: str) -> bool:
    """Whether `line` is more than a blank line or a comment -- an unbalanced quote too,
    which is refused."""
    try:
        return bool(words(line))
    except ValueError:
        return True


def _hidden(text: str) -> str:
    """`text`'s escape codes fenced off for readline, which then counts only the rest."""
    return style.ESCAPE.sub(lambda code: f"\001{code.group()}\002", text)


class Shell:
    def __init__(self, project: Path | None = None, *,
                 read: Callable[[str], str] | None = None, interactive: bool | None = None,
                 run: Callable[[list[str]], int] | None = None):
        self.project = Path(project).resolve() if project is not None else None
        self.interactive = sys.stdin.isatty() if interactive is None else interactive
        self.read = read or input
        if run is None:
            from cli.terminal.main import main
            run = main
        self.run = run
        self.readline = False
        """Whether readline reads the lines, and so needs the prompt's colour fenced."""
        self.stopped: str | None = None
        """Why lines read from the input stopped, for the command to answer with."""
        self.undone: list[bytes] = []
        self.redone: list[bytes] = []

    # ── The loop ───────────────────────────────────────────────────────────

    def loop(self) -> int:
        """Read and run lines to the end of the input or `exit`. 0, or 1 when a line
        read from a pipe failed."""
        if self.interactive:
            self.readline = _readline(self)
            self._greet()
            return self._typed()
        return self._read_lines(sys.stdin, "the input", top=True)

    def _greet(self) -> None:
        on = style.enabled(sys.stdout)
        print()
        print(f"{style.paint('kratos-cli shell:', 'bold', on)} type one command per line. "
              "The open project is used, so leave out its file name.")
        print(f"{style.paint('help', 'cyan', on)} lists the commands, "
              f"{style.paint('help COMMAND', 'cyan', on)} explains one, "
              f"{style.paint('exit', 'cyan', on)} closes the shell.")
        print()
        self._say_open()
        print()

    def _say_open(self) -> None:
        on = style.enabled(sys.stdout)
        if self.project is None:
            # Not a warning: it is how every shell started without a project begins.
            print(f"No project is open. Start one with {style.paint('new FILE', 'cyan', on)}, "
                  f"or open one with {style.paint('open FILE', 'cyan', on)}.")
            return
        print(f"{style.paint('open', 'bold green', on)}  "
              f"{style.paint(self.project.name, 'bold', on)}  "
              f"{style.paint(f'({self.project.parent})', 'dim', on)}")

    def _typed(self) -> int:
        while True:
            try:
                line = self.read(self.prompt())
            except EOFError:
                print()
                return 0
            except KeyboardInterrupt:
                print()
                continue
            try:
                self.line(line)
            except Leave:
                return 0
            except KeyboardInterrupt:
                output.error("interrupted")
            if _has_words(line):
                sys.stderr.flush()
                print()                             # a blank line before the next prompt

    def _read_lines(self, lines, where: str, top: bool = False) -> int:
        echoed = False
        for number, line in enumerate(lines, start=1):
            line = line.rstrip("\r\n").lstrip(BOM)
            if line.strip() and not line.lstrip().startswith("#"):
                if echoed:
                    print()
                self._echo(line)
                echoed = True
            try:
                code = self.line(line)
            except Leave:
                return 0
            if code:
                why = f"stopped at line {number} of {where}: `{line.strip()}` failed (exit {code})"
                if top:
                    self.stopped = why
                else:
                    output.error(why)
                return 1
        return 0

    def _echo(self, line: str) -> None:
        on = style.enabled(sys.stdout)
        print(f"{style.paint('>', 'bold magenta', on)} {style.paint(line, 'bold', on)}")
        sys.stdout.flush()

    def prompt(self) -> str:
        on = style.enabled(sys.stdout)
        name = self.project.name if self.project else "kratos-cli"
        painted = [style.paint(name, "bold cyan", on), style.paint(">", "bold magenta", on)]
        if on and self.readline:
            # readline counts what is between \001 and \002 as taking no room.
            painted = [_hidden(text) for text in painted]
        return f"{painted[0]}{painted[1]} "

    # ── One line ───────────────────────────────────────────────────────────

    def line(self, line: str) -> int:
        """Run one line; its exit code (0 for a blank line or a word of the shell's)."""
        try:
            argv = words(line)
        except ValueError as failure:            # an unbalanced quote
            output.error(f"{failure}: close the quote")
            return 2
        if argv[:1] == ["kratos-cli"]:
            argv = argv[1:]
        if not argv:
            return 0
        word = argv[0]
        if word in ("exit", "quit"):
            raise Leave
        own = getattr(self, f"_{word}", None) if word in WORDS else None
        if own is not None:
            return own(argv[1:])
        if word == "shell":
            output.error("this is the shell already")
            return 1
        return self._command(argv)

    def _command(self, typed: list[str]) -> int:
        argv = _with_project(typed, self.project)
        if argv is None:
            output.error("no project is open: `open FILE` opens one, `new FILE` makes "
                         "one, or name the file on the line.")
            return 1
        before = self._contents()
        try:
            code = self.run(argv)
        except KeyboardInterrupt:
            raise
        except Exception:                           # noqa: BLE001 - shown, then on
            traceback.print_exc()
            output.error("that was a fault in kratos-cli, not in the model: the "
                         "traceback above says where.")
            code = 1
        after = self._contents()
        if before is not None and after != before:
            self.undone.append(before)
            self.redone.clear()
        return code

    def _contents(self) -> bytes | None:
        if self.project is None or self.project.suffix.lower() != ".json":
            return None
        try:
            return self.project.read_bytes()
        except OSError:
            return None

    # ── Its own words ──────────────────────────────────────────────────────

    def _open(self, args: list[str]) -> int:
        if not args:
            self._say_open()
            return 0
        path = Path(args[0]).expanduser()
        if not path.is_file():
            output.error(f"no such file: {path}")
            return 1
        if path.suffix.lower() not in MODEL_SUFFIXES:
            output.error(f"{path.name} is not a project (.json) or a model script (.py)")
            return 1
        self._switch(path)
        self._say_open()
        return 0

    def _close(self, args: list[str]) -> int:
        self._switch(None)
        self._say_open()
        return 0

    def _new(self, args: list[str]) -> int:
        code = self._command(["new", *args])
        target = next((word for word in args if not word.startswith("-")), None)
        if code == 0 and target is not None:
            self._switch(Path(target))
            self._say_open()
        return code

    def _switch(self, path: Path | None) -> None:
        self.project = path.resolve() if path is not None else None
        self.undone.clear()
        self.redone.clear()

    def _undo(self, args: list[str]) -> int:
        return self._step(self.undone, self.redone, "undo")

    def _redo(self, args: list[str]) -> int:
        return self._step(self.redone, self.undone, "redo")

    def _step(self, source: list[bytes], target: list[bytes], what: str) -> int:
        if not source or self.project is None:
            print(style.paint(f"nothing to {what}", "dim", style.enabled(sys.stdout)))
            return 0
        current = self._contents()
        if current is not None:
            target.append(current)
        self.project.write_bytes(source.pop())
        on = style.enabled(sys.stdout)
        print(f"{style.paint(what + ':', 'bold green', on)} "
              f"{style.paint(self.project.name, 'bold', on)} is as it was "
              f"{'before' if what == 'undo' else 'after'} that edit")
        return 0

    def _cd(self, args: list[str]) -> int:
        try:
            os.chdir(Path(args[0]).expanduser() if args else Path.home())
        except OSError as failure:
            output.error(str(failure))
            return 1
        print(os.getcwd())
        return 0

    def _pwd(self, args: list[str]) -> int:
        print(os.getcwd())
        return 0

    def _source(self, args: list[str]) -> int:
        if not args:
            output.error("source needs a file of lines")
            return 2
        path = Path(args[0]).expanduser()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as failure:
            output.error(str(failure))
            return 1
        return self._read_lines(lines, path.name)

    def _help(self, args: list[str]) -> int:
        if args:
            return self.run([args[0], "--help"])
        on = style.enabled(sys.stdout)
        sections = [("Shell", [said for said in WORDS.values() if said]), *_command_groups()]
        width = max(len(name) for _, rows in sections for name, _ in rows) + 3
        columns = shutil.get_terminal_size((100, 24)).columns
        for heading, rows in sections:
            print(style.paint(heading, "bold", on))
            for name, what in rows:
                said = textwrap.wrap(what, max(columns - width - 3, 30)) or [""]
                print(f"  {style.paint(name.ljust(width), 'cyan', on)}{said[0]}")
                for more in said[1:]:
                    print(" " * (width + 2) + more)
            print()
        print(f"Every command is typed without the project file: the open one is used. "
              f"{style.paint('help COMMAND', 'cyan', on)} says what COMMAND takes.")
        return 0


# ── Where the project goes ──────────────────────────────────────────────────

def _with_project(argv: list[str], project: Path | None) -> list[str] | None:
    """`argv` with the open project put where its command takes one; None when it takes
    one, none is open and none is named on the line."""
    at = next((i for i, word in enumerate(argv) if not word.startswith("-")), None)
    if at is None:
        return argv
    command = _subcommands(_parser()).get(argv[at])
    if command is None:
        return argv                                 # argparse will say it is not one
    slot, where = _slot(command), at + 1
    if slot is None:
        action = argv[at + 1] if at + 1 < len(argv) else None
        sub = _subcommands(command).get(action) if action is not None else None
        slot = _slot(sub) if sub is not None else None
        if slot is None:
            return argv
        where = at + 2
    if where < len(argv) and _named(argv[where], slot):
        return argv
    if project is None:
        return None
    return [*argv[:where], str(project), *argv[where:]]


def _named(word: str, slot: str) -> bool:
    """Whether `word`, where the project would go, is a project or a deck itself."""
    path = Path(word)
    if path.suffix.lower() in MODEL_SUFFIXES:
        return True
    return slot == "source" and (path.is_dir() or path.suffix.lower() == ".mdpa")


def _slot(parser: argparse.ArgumentParser) -> str | None:
    positionals = [action.dest for action in parser._actions
                   if not action.option_strings
                   and not isinstance(action, argparse._SubParsersAction)]
    slot = parser.get_default("project_slot") or PROJECT_SLOT
    return positionals[0] if positionals and positionals[0] == slot else None


_PARSER: argparse.ArgumentParser | None = None


def _parser() -> argparse.ArgumentParser:
    global _PARSER
    if _PARSER is None:
        from cli.terminal.main import parser
        _PARSER = parser()
    return _PARSER


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def _command_groups() -> list[tuple[str, list[tuple[str, str]]]]:
    """The commands under the step of the model each belongs to -- the module of
    `cli.commands` that registers it, in `cli.terminal.main.GROUPS`' order -- each with its help;
    `shell` left out."""
    from cli.terminal.main import GROUPS

    said = {}
    for action in _parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            said = {choice.dest: choice.help or "" for choice in action._choices_actions}
    common = argparse.ArgumentParser(add_help=False)
    groups = []
    for group in GROUPS:
        commands = argparse.ArgumentParser(add_help=False).add_subparsers()
        group.register(commands, common)
        rows = [(name, said.get(name, "")) for name in commands.choices if name != "shell"]
        if rows:
            groups.append((group.__name__.rsplit(".", 1)[-1].capitalize(), rows))
    return groups


# ── Completion ──────────────────────────────────────────────────────────────

def completions(before: str) -> list[str]:
    """What the word being typed can become, given the line up to the cursor: a command
    or a word of the shell first, then an action of that command."""
    try:
        typed = words(before)
    except ValueError:
        return []
    if before and before[-1].isspace():
        typed.append("")
    if not typed:
        typed = [""]
    *done, current = typed
    if done[:1] == ["kratos-cli"]:
        done = done[1:]
    if not done:
        names = [*_subcommands(_parser()), *(w for w in WORDS if w != "new")]
        return sorted(name for name in names if name.startswith(current))
    if len(done) == 1:
        command = _subcommands(_parser()).get(done[0])
        if command is not None:
            return sorted(action for action in _subcommands(command)
                          if action.startswith(current))
    return []


def _readline(shell: Shell) -> bool:
    """Line editing, history kept across sessions and Tab completion, where Python has
    readline (Linux, macOS); whether it has. Windows' console edits and recalls lines by
    itself."""
    try:
        import readline
    except ImportError:
        return False
    history = Path.home() / ".kratos_cli_history"
    try:
        readline.read_history_file(history)
    except OSError:
        pass
    import atexit
    atexit.register(_save_history, readline, history)

    def complete(text: str, state: int) -> str | None:
        found = completions(readline.get_line_buffer()[:readline.get_endidx()])
        return f"{found[state]} " if state < len(found) else None
    readline.set_completer(complete)
    readline.set_completer_delims(" \t")
    readline.parse_and_bind("tab: complete")
    return True


def _save_history(readline, history: Path) -> None:
    try:
        readline.set_history_length(1000)
        readline.write_history_file(history)
    except OSError:
        pass
