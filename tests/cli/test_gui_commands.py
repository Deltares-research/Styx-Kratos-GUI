"""Every command the GUI's command box answers has its place in the terminal
(plan/active/cli-plan.md, M7).

`docs/CLI.md`, "The GUI's command box, in the terminal", maps each one to the
`kratos-cli` command that does the same, or says it is the viewport's. This test reads
the command box's dispatchers out of the JavaScript and holds the table to them both
ways: a command the box answers and the table lacks fails, and so does a row for a
command the box no longer has. Every `kratos-cli ...` the table spells is a command and
an action the CLI's parser has.

The dispatchers, in the order the box asks them (`frontend/js/patches.js`,
`App.Command.run`):

* `App.Results.handleCommand` (`results.js`), and under it `App.ResultsPlot.command`
  (`results-plot.js`) for `results plot`;
* the small commands, each a module whose `command`/`parse` answers `false` for a line
  that is not its own (`colour`, `water`, `units`, `node`);
* the words `App.Command.run` itself tests (`phases`, `run`, `export`, `mesh`, ...);
* the mockup's interpreter (`base/js/command.js`): its mode jumps, its `switch`, and the
  canned answers of `App.CMD_RESPONSES` (`base/js/data.js`).

`App.DrawInput.handleCommand` takes coordinates while a drawing tool is placing points,
not a command word; the table says so in a line of its own.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from cli import main

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "frontend" / "js"
BASE = ROOT / "frontend" / "base" / "js"
DOC = ROOT / "docs" / "CLI.md"
SECTION = "## The GUI's command box, in the terminal"


# ── Reading the JavaScript ──────────────────────────────────────────────────

def block(source: str, opening: str) -> str:
    """The braces-balanced body that starts at the first `{` from `opening` on."""
    at = source.index(opening)
    start = source.index("{", at)
    depth = 0
    for index in range(start, len(source)):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        if depth == 0:
            return source[start:index + 1]
    raise AssertionError(f"no end to the block at {opening!r}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def module_defining(name: str) -> Path:
    """The file that sets `App.<name> = ...`."""
    found = [path for path in JS.glob("*.js") if re.search(rf"\bApp\.{name}\s*=", read(path))]
    assert len(found) == 1, f"App.{name} is defined in {found}"
    return found[0]


def not_mine_words(path: Path) -> set[str]:
    """The words a module answers: those its `!== 'word' ... return false` lines test."""
    return {word for line in read(path).splitlines()
            if re.search(r"!==\s*'\w+'.*\)\s*return false;", line)
            for word in re.findall(r"!==\s*'(\w+)'", line)}


def gui_commands() -> set[str]:
    """Every first word the command box answers."""
    words: set[str] = set()

    run = block(read(JS / "patches.js"), "App.Command.run = function (text)")
    words |= set(re.findall(r"cmd === '(\w+)'", run))
    words |= set(re.findall(r"/\^_\?(\w+)\(\?:", run))
    for handler in re.findall(r"if \((run\w+Command)\(text\)\) return;", run):
        body = block(read(JS / "patches.js"), f"function {handler}(text)")
        (module,) = set(re.findall(r"App\.(\w+)\.(?:command|parse)\(", body))
        words |= not_mine_words(module_defining(module))
    if "App.Results.handleCommand(text)" in run:
        words |= not_mine_words(module_defining("Results"))

    mockup = block(read(BASE / "command.js"), "function run(text)")
    words |= set(re.findall(r"(\w+):\s*'\w+'", block(mockup, "var modeJump")))
    words |= set(re.findall(r"case '(\w+)':", mockup))
    words |= set(re.findall(r"^\s*'(\w+)':", block(read(BASE / "data.js"),
                                                     "App.CMD_RESPONSES = "), re.M))
    return words


def results_verbs() -> set[str]:
    """What `results <verb>` takes, and "" for `results` alone."""
    body = block(read(module_defining("Results")), "function handleCommand(text)")
    return set(re.findall(r"verb === '(\w+)'", body)) | {""}


def plot_verbs() -> set[str]:
    """What `results plot <verb>` takes, and "" for a member and a quantity."""
    body = block(read(module_defining("ResultsPlot")), "function command(rest)")
    return set(re.findall(r"verb === '(\w+)'", body)) | {""}


# ── Reading the table ───────────────────────────────────────────────────────

def table() -> list[tuple[list[str], str]]:
    """(the command box's spellings, the terminal cell) per row."""
    text = read(DOC)
    assert SECTION in text, f"{DOC.name} has no section {SECTION!r}"
    section = text.split(SECTION, 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        box, terminal = (cell.strip() for cell in re.split(r"(?<!\\)\|", line)[1:3])
        rows.append((re.findall(r"`([^`]+)`", box), terminal))
    return rows


def spelled(word: str) -> str:
    return word.replace("\\|", "|").lower().lstrip("_")


def documented() -> tuple[set[str], set[str], set[str]]:
    """The command words, the `results` verbs and the `results plot` verbs the table has."""
    commands, verbs, plot = set(), set(), set()
    for spellings, _ in table():
        for spelling in spellings:
            words = [spelled(word) for word in spelling.split()]
            commands.add(words[0])
            if words[0] != "results":
                continue
            verb = words[1] if len(words) > 1 and not words[1].startswith(("<", "[")) else ""
            verbs.add(verb)
            if verb == "plot":
                rest = words[2] if len(words) > 2 else ""
                plot.add("" if rest.startswith(("<", "[")) else rest)
    return commands, verbs, plot


# ── The checks ──────────────────────────────────────────────────────────────

def test_the_reader_finds_the_dispatchers():
    """A reader that found nothing would pass everything below."""
    assert {"run", "export", "mesh", "phases", "water", "units", "node", "colour",
            "results", "view", "gotosoil", "help", "calculate"} <= gui_commands()
    assert {"runs", "open", "field", "at", "csv", "plot", "deform"} <= results_verbs()
    assert {"members", "csv", "svg"} <= plot_verbs()


def test_every_command_the_box_answers_is_in_the_table():
    missing = gui_commands() - documented()[0]
    assert not missing, f"map these in docs/CLI.md, {SECTION[3:]!r}: {sorted(missing)}"


def test_every_results_command_the_box_answers_is_in_the_table():
    commands, verbs, plot = documented()
    assert not results_verbs() - verbs, sorted(results_verbs() - verbs)
    assert not plot_verbs() - plot, sorted(plot_verbs() - plot)


def test_the_table_has_no_command_the_box_does_not_answer():
    commands, verbs, plot = documented()
    assert not commands - gui_commands(), sorted(commands - gui_commands())
    assert not verbs - results_verbs(), sorted(verbs - results_verbs())
    assert not plot - plot_verbs(), sorted(plot - plot_verbs())


def subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def test_every_row_is_mapped_to_the_terminal_or_said_to_be_the_viewport_s():
    for spellings, terminal in table():
        assert terminal.startswith("—") or "`kratos-cli " in terminal, spellings


def test_every_terminal_command_in_the_table_is_one_kratos_cli_has():
    commands = subcommands(main.parser())
    wrong = []
    for _, terminal in table():
        for spelling in re.findall(r"`kratos-cli ([^`]+)`", terminal):
            words = spelling.split()
            if words[0] == "--help":
                continue
            if words[0] not in commands:
                wrong.append(spelling)
                continue
            actions = subcommands(commands[words[0]])
            # The action follows the project (`borehole P add`) or comes first
            # (`results field RUN`); a placeholder in capitals is neither.
            asked = [word for word in words[1:3] if not word.isupper()
                     and not word.startswith(("-", "<", "["))]
            if actions and asked and not all(choice in actions
                                             for choice in spelled(asked[0]).split("|")):
                wrong.append(spelling)
    assert not wrong, wrong


@pytest.mark.parametrize("command", ["new", "water", "results"])
def test_the_parser_reader_sees_the_cli_s_commands(command):
    assert command in subcommands(main.parser())
