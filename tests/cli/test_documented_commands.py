"""The commands the documentation shows, held to what `kratos-cli` does.

Two checks, for two kinds of page:

- Every `kratos-cli` line in `docs/CLI.md` and `docs/cli_tutorials/` is one the command
  line reads: argparse takes it as written. `docs/CLI.md` is a reference, its examples
  not one session, so that is all that is checked of it.
- Every shell tutorial -- a page that starts a project with `new` in `kratos-cli shell`
  -- is followed line by line in an empty folder. Each command succeeds and prints what
  the page shows it print: nothing, when the page shows nothing. `...` on the page
  stands for a path and matches anything. A command listed with a note in a column
  (`stages show ID     what is in the model`) only has to succeed. `run`, `calculate`
  and `results` need Kratos and are left out. The Muskat tutorial, written as
  `kratos-cli` lines, has its own test (`test_muskat_tutorial.py`).

The pages are found, not named: a tutorial added later is checked too.
"""

from __future__ import annotations

import io
import re
import shlex
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest

from cli.terminal import main as cli_main
from cli.terminal.shell import Shell

DOCS = Path(__file__).resolve().parents[2] / "docs"
PAGES = [DOCS / "CLI.md", *sorted((DOCS / "cli_tutorials").glob("*.md"))]

PROMPT = re.compile(r"^(?:kratos-cli|[\w.-]+\.(?:json|py))>(?: (.*))?$")
"""A transcript line: the prompt (`kratos-cli>`, or the open project's file name), then
what was typed -- nothing, for the prompt a transcript ends on."""

NOTE = re.compile(r"\s{3,}\S.*$")
"""A note in a column after a command: `stages show ID     what is in the model`."""

PATH = re.compile(r"\.\.\.[^\s)]*")
"""`...\\folder\\file`: a path the page leaves out."""

NEEDS_KRATOS = {"run", "calculate", "results"}
MESH_DEPENDENT = {"mesh", "export", "deck", "node"}
"""What prints node and element counts, which follow gmsh's version: run, but what they
print is not compared."""


@dataclass
class Step:
    command: str
    shown: list[str] | None
    """What the page shows the command print, blank lines included; None in a script of
    bare lines, and for a command listed with a note in a column."""


def steps(page: Path) -> list[Step]:
    """The shell lines a tutorial types, in order, up to its `exit`.

    Both forms are `text` blocks: a transcript, where each typed line follows a prompt
    and what it printed follows that; and a script of bare lines, marked by its `#`
    comment lines. What comes after the first `exit` shows other ways in."""
    found: list[Step] = []
    block, script = None, False
    for line in page.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            block, script = (line[3:].strip(), False) if block is None else (None, False)
            continue
        if block != "text":
            continue
        if not line.strip():
            # A blank line in what a command printed is part of it (`same_print` drops
            # the ones at the end, before the next prompt).
            if not script and found and found[-1].shown is not None:
                found[-1].shown.append("")
            continue
        prompt = PROMPT.match(line)
        if prompt:
            if prompt.group(1):
                typed = prompt.group(1)
                # A line with a note in a column is one of a list of commands to try,
                # whose output the page does not show.
                listed = NOTE.search(typed) is not None
                found.append(Step(NOTE.sub("", typed).strip(), None if listed else []))
        elif line.lstrip().startswith("#"):
            script = True
        elif script:
            found.append(Step(line.strip(), None))
        elif found and found[-1].shown is not None:
            found[-1].shown.append(line.rstrip())
    ends = next((i for i, step in enumerate(found) if step.command == "exit"), len(found))
    return found[:ends]


def tutorials() -> list[Path]:
    """The pages that build a project from nothing in the shell."""
    return [page for page in PAGES[1:]
            if steps(page) and steps(page)[0].command.startswith("new ")]


def same_print(shown: list[str], printed: list[str]) -> bool:
    """Whether `printed` is what the page shows, a `...` path matching any path. Blank
    lines at the end do not count; a command the page shows print nothing prints
    nothing."""
    shown, printed = _trimmed(shown), _trimmed(printed)
    if len(shown) != len(printed):
        return False
    return all(re.fullmatch(".*".join(re.escape(part) for part in PATH.split(want.rstrip())),
                            got.rstrip())
               for want, got in zip(shown, printed))


def _trimmed(lines: list[str]) -> list[str]:
    end = len(lines)
    while end and not lines[end - 1].strip():
        end -= 1
    return lines[:end]


def follow(page: Path, folder: Path, monkeypatch) -> list[tuple[Step, int, list[str]]]:
    """Each step of `page` typed into one shell in `folder`: the step, its exit code and
    what it printed."""
    monkeypatch.chdir(folder)
    shell = Shell(interactive=False)
    done = []
    for step in steps(page):
        if step.command.split()[0] in NEEDS_KRATOS:
            continue
        printed = io.StringIO()
        with redirect_stdout(printed), redirect_stderr(io.StringIO()):
            code = shell.line(step.command)
        done.append((step, code, printed.getvalue().splitlines()))
    return done


def test_the_tutorials_are_found():
    """Or the test below would pass on nothing."""
    assert len(tutorials()) >= 2
    assert all(len(steps(page)) >= 20 for page in tutorials())


def test_what_a_page_shows_a_command_print_is_read_whole(tmp_path):
    """A blank line inside the output is part of it, a command shown printing nothing
    must print nothing, and a command listed with a note is only run."""
    page = tmp_path / "page.md"
    page.write_text("\n".join([
        "```text", "kratos-cli> new a.json", "first", "", "second", "",
        "a.json> undo", "a.json> stages show dig     what is in the model", "shown?",
        "```"]), encoding="utf-8")

    assert steps(page) == [Step("new a.json", ["first", "", "second", ""]),
                           Step("undo", []), Step("stages show dig", None)]
    assert same_print(["first", "", "second", ""], ["first", "", "second"])
    assert not same_print(["first", "second"], ["first", "", "second"])
    assert not same_print([], ["wrote a.json"])


@pytest.mark.parametrize("page", tutorials(), ids=lambda page: page.stem)
def test_a_tutorial_runs_as_written(page, tmp_path, monkeypatch):
    done = follow(page, tmp_path, monkeypatch)

    assert [(step.command, code) for step, code, _ in done if code != 0] == []
    differs = [(step.command, step.shown, printed) for step, _, printed in done
               if step.shown is not None and step.command.split()[0] not in MESH_DEPENDENT
               and not same_print(step.shown, printed)]
    assert differs == []


# ── Every documented command line ───────────────────────────────────────────

def documented_lines(page: Path) -> list[str]:
    """Every `kratos-cli` line of a page's command blocks, and of its `PS>` transcript
    lines: what a reader copies into a terminal."""
    found, block = [], None
    for line in page.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            block = None if block is not None else line[3:].strip()
            continue
        typed = line.strip()
        if block == "text" and typed.startswith("PS> "):
            typed = typed[4:]
        elif block not in ("bash", "sh", "powershell", "console"):
            continue
        if typed.startswith("kratos-cli "):
            found.append(typed)
    return found


def unreadable(argv: list[str]) -> str | None:
    """Why `kratos-cli` cannot read `argv` (`cli.terminal.main.main`), or None."""
    said = io.StringIO()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(said):
            args, extra = cli_main.parser().parse_known_args(argv)
    except SystemExit as stop:
        return None if stop.code in (0, None) else said.getvalue().strip()
    if extra and getattr(args, "variables", None) is None:
        return "unrecognized arguments: " + " ".join(extra)
    return None


def test_the_documented_command_lines_are_found():
    found = {page.name: len(documented_lines(page)) for page in PAGES}
    assert found["CLI.md"] >= 60
    assert sum(found.values()) >= 100


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.stem)
def test_every_documented_command_line_is_one_kratos_cli_reads(page):
    unread = {line: why for line in documented_lines(page)
              if (why := unreadable(shlex.split(line, comments=True)[1:]))}
    assert unread == {}
