"""`kratos-cli shell [P]`: the commands typed one after another in one process, with the
project open (plan/active/cli-plan.md, SH).

A line is a `kratos-cli` command without `kratos-cli` and without the project file:
`water -2`, `layer add L3`, `mesh`. The shell puts the open project where the
command takes one, and runs the command as `cli.terminal.main` runs it -- the same parser, the
same answers, the same refusals. Its own words: `open`, `close`, `undo`, `redo`, `cd`,
`pwd`, `source`, `help`, `exit`.

Typed at a terminal it goes on after a command fails. Read from a file or a pipe
(`kratos-cli shell P < commands.txt`) it stops at the first command that fails, as
`set -e` would, and says which.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cli.terminal import shell
from core import session

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def piped(cli, monkeypatch):
    """`piped(lines, *argv)`: `kratos-cli shell ...` with `lines` on its stdin."""
    def run(lines: str, *argv):
        monkeypatch.setattr(sys, "stdin", io.StringIO(lines))
        return cli("shell", *argv)
    return run


@pytest.fixture
def typed(capsys, monkeypatch, tmp_path):
    """`typed(lines, project)`: the shell as a person uses it, each line typed at the
    prompt; what it printed, and what it ended with."""
    def run(lines: list[str], project: Path | None = None):
        answers = iter(lines)

        def read(prompt: str) -> str:
            try:
                return next(answers)
            except StopIteration:
                raise EOFError from None
        capsys.readouterr()
        code = shell.Shell(project, read=read, interactive=True).loop()
        printed = capsys.readouterr()
        return code, printed.out, printed.err
    return run


# ── The project, put where a command takes it ───────────────────────────────

def test_a_command_is_given_the_open_project(piped, site):
    ran = piped("water -2\nshow\n", site)

    assert ran.code == 0, ran.err
    assert session.load(site).water.y == -2.0
    assert "water" in ran.out.lower()


def test_an_action_command_is_given_the_project_before_its_action(piped, site):
    ran = piped("layer add L3 --material m1\nlayer list\n", site)

    assert ran.code == 0, ran.err
    assert "L3" in [layer.id for layer in session.load(site).layers]


def test_a_project_named_on_the_line_is_the_one_used(piped, site, tmp_path):
    other = session.save(session.load(site), tmp_path / "other.json")

    assert piped(f"water {other} -3\n", site).code == 0

    assert session.load(other).water.y == -3.0
    assert session.load(site).water is None or session.load(site).water.y != -3.0


def test_a_command_that_takes_no_project_is_given_none(piped, site):
    ran = piped("results runs\n", site)

    assert ran.code == 0, ran.err


def test_node_is_given_the_project_as_its_source(piped, site):
    """`node SOURCE NODE`: a project is a SOURCE too (its deck is written in memory)."""
    ran = piped("node 1\n", site)

    assert ran.code == 0, ran.err
    assert "node 1" in ran.out.lower()


def test_deck_show_is_not_given_a_project_which_is_not_a_deck(piped, site):
    ran = piped("deck show\n", site)

    assert ran.code == 1 and "required: source" in ran.err


def test_options_before_the_command_and_a_pasted_kratos_cli_are_fine(piped, site):
    ran = piped("--json show\nkratos-cli water -1.5\n", site)

    assert ran.code == 0, ran.err
    assert json.loads(ran.out.split("\n> ", 1)[0].split("\n", 1)[1])["file"].endswith(
        "site.json")
    assert session.load(site).water.y == -1.5


def test_without_a_project_a_command_that_needs_one_says_how_to_open_one(piped):
    ran = piped("water -2\n")

    assert ran.code == 1
    assert "open" in ran.err and "new" in ran.err


# ── Its own words ───────────────────────────────────────────────────────────

def test_new_makes_a_project_and_opens_it(piped, tmp_path):
    pit = tmp_path / "pit.json"

    ran = piped(f"new {pit} --name Pit\nwater -1\n")

    assert ran.code == 0, ran.err
    assert session.load(pit).water.y == -1.0


def test_open_switches_the_project_and_close_puts_it_down(piped, site, tmp_path):
    other = session.save(session.load(site), tmp_path / "other.json")

    ran = piped(f"open {other}\nwater -4\nclose\nwater -5\n", site)

    assert session.load(other).water.y == -4.0
    assert ran.code == 1 and "open" in ran.err


def test_open_refuses_a_file_that_is_not_there(piped, tmp_path):
    ran = piped(f"open {tmp_path / 'nope.json'}\n")

    assert ran.code == 1 and "nope.json" in ran.err


def test_shell_refuses_a_project_that_is_not_there(cli, tmp_path):
    ran = cli("shell", tmp_path / "missing.json")

    assert ran.code == 1
    assert "no such file" in ran.err and "missing.json" in ran.err
    assert "`kratos-cli new " in ran.err


def test_open_refuses_a_file_with_an_unsupported_suffix(typed, tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("not a project", encoding="utf-8")

    code, out, err = typed([f"open {file}", "exit"])

    assert code == 0
    assert "not a project (.json) or a model script (.py)" in err


def test_undo_and_redo_step_through_the_edits_of_the_open_project(typed, site):
    before = site.read_bytes()

    typed(["water -2", "water -3", "undo"], site)
    assert session.load(site).water.y == -2.0

    site.write_bytes(before)
    code, out, err = typed(["water -2", "water -3", "undo", "undo", "undo"], site)
    assert site.read_bytes() == before
    assert "nothing to undo" in out + err


def test_redo_puts_back_what_undo_took(typed, site):
    typed(["water -2", "undo", "redo"], site)

    assert session.load(site).water.y == -2.0


def test_a_new_edit_after_undo_cannot_be_redone(typed, site):
    code, out, err = typed(["water -2", "undo", "water -3", "redo"], site)

    assert session.load(site).water.y == -3.0
    assert "nothing to redo" in out + err


def test_cd_and_pwd(typed, site, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()

    code, out, err = typed(["cd sub", "pwd", "water -2"], site)

    assert str(tmp_path / "sub") in out
    assert session.load(site).water.y == -2.0       # the project is held by its full path


def test_source_runs_a_file_of_lines_and_stops_at_the_first_that_fails(typed, site, tmp_path):
    lines = tmp_path / "lines.txt"
    lines.write_text("# the water first\nwater -2\nwater nonsense\nwater -3\n", encoding="utf-8")

    code, out, err = typed([f"source {lines}"], site)

    assert session.load(site).water.y == -2.0
    assert "line 3" in err


def test_source_reports_a_missing_file_and_keeps_the_shell_open(typed, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, out, err = typed([f"source {tmp_path / 'missing.txt'}", "pwd"])

    assert code == 0
    assert "missing.txt" in err
    assert str(tmp_path) in out


def test_help_lists_its_own_words_and_the_commands(typed):
    code, out, err = typed(["help"])

    for word in ("open", "undo", "source", "exit"):
        assert word in out
    assert "layer" in out and "results" in out


def test_help_lists_the_commands_under_the_step_of_the_model_they_belong_to(typed):
    code, out, err = typed(["help"])
    headings = [line for line in out.splitlines() if line and not line[0].isspace()]

    assert {"Shell", "Project", "Ground", "Structures", "Stages", "Results"} <= set(headings)
    after = out.split("\nGround\n", 1)[1].split("\n\n", 1)[0]
    assert "  material" in after and "  layer" in after
    assert "  shell " not in out                    # it is the shell already


def test_help_with_a_command_is_that_command_s_help(typed):
    code, out, err = typed(["help water"])

    assert "usage: kratos-cli water" in out


def test_exit_and_the_end_of_input_leave(typed, site):
    assert typed(["exit", "water -2"], site)[0] == 0
    assert session.load(site).water is None or session.load(site).water.y != -2.0
    assert typed(["quit"])[0] == 0
    assert typed([])[0] == 0


def test_a_shell_is_not_started_inside_the_shell(typed):
    code, out, err = typed(["shell"])

    assert "already" in out + err


# ── Words, as a person types them ───────────────────────────────────────────

def test_quotes_group_words_and_a_colour_is_not_a_comment():
    assert shell.words('material add clay --color "#c4a86a" --name "Soft clay"') == [
        "material", "add", "clay", "--color", "#c4a86a", "--name", "Soft clay"]


def test_a_windows_path_keeps_its_backslashes():
    assert shell.words(r'open C:\models\pit.json') == ["open", r"C:\models\pit.json"]
    assert shell.words(r'open "C:\my models\pit.json"') == ["open", r"C:\my models\pit.json"]


def test_a_line_that_starts_with_a_hash_is_a_comment_and_a_blank_line_is_nothing():
    assert shell.words("  # dig the pit") == []
    assert shell.words("   ") == []


def test_unbalanced_quotes_are_refused_by_the_line_not_the_shell(typed):
    code, out, err = typed(['set x name "Pit', "pwd"])

    assert "quote" in err and code == 0


def test_an_unbalanced_quote_read_from_a_pipe_stops_it_by_line(piped, site):
    ran = piped('water -2\nset name "Pit\nwater -3\n', site)

    assert ran.code == 1 and "quote" in ran.err and "line 2" in ran.err
    assert session.load(site).water.y == -2.0


# ── Failures ────────────────────────────────────────────────────────────────

def test_from_a_pipe_it_stops_at_the_first_command_that_fails(piped, site):
    ran = piped("water -2\nwater nonsense\nwater -3\n", site)

    assert ran.code == 1
    assert session.load(site).water.y == -2.0
    assert "line 2" in ran.err and "water nonsense" in ran.err


def test_at_a_terminal_it_goes_on_after_a_command_fails(typed, site):
    code, out, err = typed(["water nonsense", "water --bogus", "water -3"], site)

    assert code == 0
    assert session.load(site).water.y == -3.0


def test_a_fault_in_a_command_is_shown_and_the_shell_goes_on(typed, site, monkeypatch):
    from cli.commands import project

    def broken(args):
        raise RuntimeError("a bug")
    monkeypatch.setattr(project, "show_project", broken)

    code, out, err = typed(["show", "water -3"], site)

    assert "RuntimeError: a bug" in err
    assert session.load(site).water.y == -3.0


def test_a_byte_order_mark_from_a_powershell_pipe_is_not_part_of_the_line(piped, site):
    """`Get-Content lines.txt | kratos-cli.bat shell`: Windows PowerShell puts a BOM
    before the first line it sends a program."""
    ran = piped("\ufeff# the water\nwater -2\n", site)

    assert ran.code == 0, ran.err
    assert session.load(site).water.y == -2.0
    assert shell.words("\ufeffwater -2") == ["water", "-2"]


def test_each_line_is_echoed_when_read_from_a_pipe(piped, site):
    ran = piped("water -2\n", site)

    assert "> water -2" in ran.out


def test_a_blank_line_parts_one_echoed_command_from_the_next(piped, site):
    ran = piped("water -2\nwater -3\n", site)

    assert ran.out.startswith("> water -2\n")
    assert "\n\n> water -3\n" in ran.out


def test_at_a_terminal_a_blank_line_follows_each_answer(typed, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    code, out, err = typed(["pwd", "", "# a comment", "pwd"])

    assert out.count(f"{tmp_path}\n\n") == 2
    assert "\n\n\n" not in out.rstrip("\n")       # nothing typed, nothing added


def test_the_greeting_names_the_open_project_or_says_how_to_open_one(typed, site):
    assert "site.json" in typed([], site)[1]
    greeting = typed([])[1]
    assert "No project is open. Start one with new FILE, or open one with open FILE." \
        in greeting
    assert "leave out its file name" in greeting
    assert "help lists the commands" in greeting and "exit closes the shell" in greeting


# ── Completion ──────────────────────────────────────────────────────────────

def test_the_first_word_completes_to_a_command_or_a_word_of_the_shell():
    assert "layer" in shell.completions("lay")
    assert "undo" in shell.completions("un")


def test_the_second_word_completes_to_an_action():
    assert {"add", "list"} <= set(shell.completions("layer "))
    assert "field" in shell.completions("results fi")


def test_interrupting_input_or_a_running_command_keeps_the_shell_usable(
        monkeypatch, capsys):
    from unittest.mock import Mock

    read = Mock(side_effect=[KeyboardInterrupt, "show", "pwd", EOFError])
    run = Mock(side_effect=KeyboardInterrupt)
    instance = shell.Shell(Path("site.json"), read=read, run=run, interactive=True)
    monkeypatch.setattr(shell, "_readline", lambda _: False)

    assert instance.loop() == 0
    run.assert_called_once_with(["show", str(Path("site.json").resolve())])
    assert read.call_count == 4
    printed = capsys.readouterr()
    assert "interrupted" in printed.err
    assert str(Path.cwd()) in printed.out
    assert "Traceback" not in printed.err


def test_exit_in_piped_input_does_not_run_later_commands(capsys):
    from unittest.mock import Mock

    run = Mock()
    instance = shell.Shell(run=run, interactive=False)

    assert instance._read_lines(["quit", "pwd"], "commands.txt", top=True) == 0
    assert instance.stopped is None
    run.assert_not_called()
    assert capsys.readouterr().out == "> quit\n"


def test_open_without_arguments_reports_the_current_project_without_changing_history(
        tmp_path, capsys):
    project = tmp_path / "site.json"
    instance = shell.Shell(project, run=lambda _: 0)
    instance.undone.append(b"previous")

    assert instance.line("open") == 0
    assert instance.project == project.resolve()
    assert instance.undone == [b"previous"]
    assert "site.json" in capsys.readouterr().out


def test_unreadable_project_has_no_undo_snapshot(tmp_path, monkeypatch):
    project = tmp_path / "site.json"
    instance = shell.Shell(project, run=lambda _: 0)

    def unreadable(_path):
        raise PermissionError("project cannot be read")

    monkeypatch.setattr(Path, "read_bytes", unreadable)

    assert instance._contents() is None
    assert instance.line("show") == 0
    assert instance.undone == []


def test_an_unsuccessful_new_does_not_replace_the_open_project(tmp_path):
    instance = shell.Shell(tmp_path / "original.json", run=lambda _: 1)
    instance.undone.append(b"previous")

    assert instance.line(f"new {tmp_path / 'new.json'}") == 1
    assert instance.project == (tmp_path / "original.json").resolve()
    assert instance.undone == [b"previous"]


def test_cd_reports_failure_without_changing_directory(tmp_path, capsys):
    before = Path.cwd()
    instance = shell.Shell(run=lambda _: 0)

    assert instance.line(f'cd "{tmp_path / "missing"}"') == 1
    assert Path.cwd() == before
    assert "missing" in capsys.readouterr().err


def test_cd_without_arguments_uses_the_home_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    assert shell.Shell(run=lambda _: 0).line("cd") == 0
    assert Path.cwd() == home
    assert str(home) in capsys.readouterr().out


def test_source_without_a_filename_reports_usage(capsys):
    assert shell.Shell(run=lambda _: 0).line("source") == 2
    assert "source needs a file of lines" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    ["--help"],
    ["unknown-command"],
    ["results"],
])
def test_project_insertion_leaves_projectless_or_unrecognised_commands_to_the_parser(argv):
    assert shell._with_project(argv, None) == argv


def test_completion_of_empty_input_offers_the_commands():
    assert {"open", "undo", "layer"} <= set(shell.completions(""))


@pytest.mark.parametrize("before, expected", [
    ('open "unfinished', []),
    ("kratos-cli lay", ["layer"]),
    ("unknown-command ", []),
    ("layer add another-word", []),
])
def test_completion_handles_prefixed_malformed_and_finished_input(before, expected):
    assert shell.completions(before) == expected


def test_a_parser_without_subcommands_has_no_completions():
    import argparse

    assert shell._subcommands(argparse.ArgumentParser(add_help=False)) == {}


@pytest.mark.parametrize("history_missing", [False, True])
def test_readline_configures_completion_and_registers_bounded_history_saving(
        tmp_path, monkeypatch, history_missing):
    import atexit
    from types import SimpleNamespace
    from unittest.mock import Mock

    history = tmp_path / ".kratos_cli_history"
    readline = SimpleNamespace(
        read_history_file=Mock(side_effect=OSError("no history") if history_missing else None),
        set_completer=Mock(),
        set_completer_delims=Mock(),
        parse_and_bind=Mock(),
        get_line_buffer=Mock(return_value="layer ignored-after-cursor"),
        get_endidx=Mock(return_value=len("layer ")),
    )
    register = Mock()
    monkeypatch.setitem(sys.modules, "readline", readline)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(atexit, "register", register)
    instance = shell.Shell(run=lambda _: 0)

    assert shell._readline(instance) is True
    readline.read_history_file.assert_called_once_with(history)
    register.assert_called_once_with(shell._save_history, readline, history)
    readline.set_completer_delims.assert_called_once_with(" \t")
    readline.parse_and_bind.assert_called_once_with("tab: complete")
    complete = readline.set_completer.call_args.args[0]
    expected = shell.completions("layer ")
    assert expected
    assert complete("", 0) == expected[0] + " "
    assert complete("", len(expected)) is None
    assert not history.exists()


def test_readline_is_optional_on_platforms_without_it(monkeypatch):
    monkeypatch.setitem(sys.modules, "readline", None)

    assert shell._readline(shell.Shell(run=lambda _: 0)) is False


@pytest.mark.parametrize("set_error, write_error, writes", [
    pytest.param(None, None, 1, id="saved"),
    pytest.param(OSError("read-only"), None, 0, id="set-fails"),
    pytest.param(None, OSError("read-only"), 1, id="write-fails"),
])
def test_history_saving_is_bounded_and_tolerates_unwritable_history(
        tmp_path, set_error, write_error, writes):
    from types import SimpleNamespace
    from unittest.mock import Mock, call

    history = tmp_path / ".kratos_cli_history"
    readline = SimpleNamespace(
        set_history_length=Mock(side_effect=set_error),
        write_history_file=Mock(side_effect=write_error),
    )

    shell._save_history(readline, history)

    readline.set_history_length.assert_called_once_with(1000)
    assert readline.write_history_file.call_args_list == [call(history)] * writes


# ── Started as a user starts it ─────────────────────────────────────────────

def test_the_command_reads_its_lines_from_a_pipe(site, tmp_path):
    ran = subprocess.run([sys.executable, str(ROOT / "cli" / "__main__.py"), "shell", str(site)],
                         input="water -2\nparts\n", cwd=tmp_path, capture_output=True,
                         text=True, encoding="utf-8", timeout=300,
                         env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"})

    assert ran.returncode == 0, ran.stderr
    assert session.load(site).water.y == -2.0
