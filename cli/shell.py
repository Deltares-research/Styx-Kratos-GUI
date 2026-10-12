"""`kratos-cli shell [P]`: the commands, typed one after another in one process, with a
project open (plan/active/cli-plan.md, SH).

A line is a `kratos-cli` command without `kratos-cli` and without the project file --
`water -2`, `borehole add bh4`, `mesh`, `results field 1 uy`. The open project goes where
the command takes one (`_with_project`): after the command word (`borehole P add`), or
after the action for a command whose action comes first. A project or a
deck named on the line is the one used. The line then runs as `cli.main` runs any
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
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

WORDS = {
    "open": "open FILE        work on another project file (.json, or a .py to read)",
    "close": "close            put the project down",
    "new": "new FILE ...     make a project file, as `kratos-cli new`, and open it",
    "undo": "undo             take back the last edit of the open project",
    "redo": "redo             put back what undo took",
    "cd": "cd DIR           go to another folder; the open project stays open",
    "pwd": "pwd              the folder relative paths are read from",
    "source": "source FILE      run the lines of a file; the first that fails stops it",
    "help": "help [COMMAND]   this, or what COMMAND takes",
    "exit": "exit, quit       leave (also Ctrl-D, or Ctrl-Z then Enter on Windows)",
    "quit": "",
}
"""The shell's own words, and the line `help` says each in."""

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


class Shell:
    def __init__(self, project: Path | None = None, *,
                 read: Callable[[str], str] | None = None, interactive: bool | None = None,
                 run: Callable[[list[str]], int] | None = None):
        self.project = Path(project).resolve() if project is not None else None
        self.interactive = sys.stdin.isatty() if interactive is None else interactive
        self.read = read or input
        if run is None:
            from cli.main import main
            run = main
        self.run = run
        self.stopped: str | None = None
        """Why lines read from the input stopped, for the command to answer with."""
        self.undone: list[bytes] = []
        self.redone: list[bytes] = []

    # ── The loop ───────────────────────────────────────────────────────────

    def loop(self) -> int:
        """Read and run lines to the end of the input or `exit`. 0, or 1 when a line
        read from a pipe failed."""
        if self.interactive:
            _readline(self)
            print("kratos-cli shell: a command as after `kratos-cli`, without the project "
                  "file. `help` lists them; `exit` leaves.")
            if self.project is None:
                print("No project is open: `open FILE`, or `new FILE`.")
            return self._typed()
        return self._read_lines(sys.stdin, "the input", top=True)

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
                print("interrupted", file=sys.stderr)

    def _read_lines(self, lines, where: str, top: bool = False) -> int:
        for number, line in enumerate(lines, start=1):
            line = line.rstrip("\r\n").lstrip(BOM)
            if line.strip() and not line.lstrip().startswith("#"):
                print(f"> {line}")
            try:
                code = self.line(line)
            except Leave:
                return 0
            if code:
                why = f"stopped at line {number} of {where}: `{line.strip()}` failed (exit {code})"
                if top:
                    self.stopped = why
                else:
                    print(f"error: {why}", file=sys.stderr)
                return 1
        return 0

    def prompt(self) -> str:
        return f"{self.project.name if self.project else 'kratos-cli'}> "

    # ── One line ───────────────────────────────────────────────────────────

    def line(self, line: str) -> int:
        """Run one line; its exit code (0 for a blank line or a word of the shell's)."""
        try:
            argv = words(line)
        except ValueError as failure:            # an unbalanced quote
            print(f"error: {failure}: close the quote", file=sys.stderr)
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
            print("error: this is the shell already", file=sys.stderr)
            return 1
        return self._command(argv)

    def _command(self, typed: list[str]) -> int:
        argv = _with_project(typed, self.project)
        if argv is None:
            print("error: no project is open: `open FILE` opens one, `new FILE` makes "
                  "one, or name the file on the line.", file=sys.stderr)
            return 1
        before = self._contents()
        try:
            code = self.run(argv)
        except KeyboardInterrupt:
            raise
        except Exception:                           # noqa: BLE001 - shown, then on
            traceback.print_exc()
            print("error: that was a fault in kratos-cli, not in the model: the "
                  "traceback above says where.", file=sys.stderr)
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
            print(f"open: {self.project}" if self.project else "No project is open.")
            return 0
        path = Path(args[0]).expanduser()
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 1
        if path.suffix.lower() not in MODEL_SUFFIXES:
            print(f"error: {path.name} is not a project (.json) or a model script (.py)",
                  file=sys.stderr)
            return 1
        self._switch(path)
        print(f"open: {self.project}")
        return 0

    def _close(self, args: list[str]) -> int:
        self._switch(None)
        print("No project is open.")
        return 0

    def _new(self, args: list[str]) -> int:
        code = self._command(["new", *args])
        target = next((word for word in args if not word.startswith("-")), None)
        if code == 0 and target is not None:
            self._switch(Path(target))
            print(f"open: {self.project}")
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
            print(f"nothing to {what}")
            return 0
        current = self._contents()
        if current is not None:
            target.append(current)
        self.project.write_bytes(source.pop())
        print(f"{what}: {self.project.name} is as it was "
              f"{'before' if what == 'undo' else 'after'} that edit")
        return 0

    def _cd(self, args: list[str]) -> int:
        try:
            os.chdir(Path(args[0]).expanduser() if args else Path.home())
        except OSError as failure:
            print(f"error: {failure}", file=sys.stderr)
            return 1
        print(os.getcwd())
        return 0

    def _pwd(self, args: list[str]) -> int:
        print(os.getcwd())
        return 0

    def _source(self, args: list[str]) -> int:
        if not args:
            print("error: source needs a file of lines", file=sys.stderr)
            return 2
        path = Path(args[0]).expanduser()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as failure:
            print(f"error: {failure}", file=sys.stderr)
            return 1
        return self._read_lines(lines, path.name)

    def _help(self, args: list[str]) -> int:
        if args:
            return self.run([args[0], "--help"])
        print("The shell's own words:")
        for line in WORDS.values():
            if line:
                print(f"  {line}")
        print("\nAnd every kratos-cli command, without the project file:")
        self.run(["--help"])
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
        from cli.main import parser
        _PARSER = parser()
    return _PARSER


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


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


def _readline(shell: Shell) -> None:
    """Line editing, history kept across sessions and Tab completion, where Python has
    readline (Linux, macOS). Windows' console edits and recalls lines by itself."""
    try:
        import readline
    except ImportError:
        return
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


def _save_history(readline, history: Path) -> None:
    try:
        readline.set_history_length(1000)
        readline.write_history_file(history)
    except OSError:
        pass
