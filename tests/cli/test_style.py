"""`cli.terminal.style`: colour for a person at a terminal, and none for a pipe or a file.

Colour only adds escape codes: take them out again and the text is, character for
character, what a pipe gets. So a script reading the output, and every other test here,
sees no difference.
"""

from __future__ import annotations

import io
from unittest.mock import call

import pytest

from cli.terminal import style
from cli.terminal.shell import Shell


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


ANSWER = [
    "simple_dike  (C:\\work\\simple_dike.json)",
    "  2D plane strain, SI units, section at z = 5",
    "  domain      x 0 .. 20, y 0 .. 10",
    "  layers      soil",
    "1  initial  Initial stage",
    "     calculation: mechanical, K0 stresses, static; deactivates sheetpile_1, load",
    "soil  soil  of m_soil: 10 .. 0",
    "ok: simple_dike (2D section at z = 5, SI)",
    "Water level: 5.00 m (specific weight 10000). wrote C:\\work\\simple_dike.json",
    "no such file: x.json. `kratos-cli new x.json` makes it",
    "",
]


# ── When there is colour ────────────────────────────────────────────────────

def test_a_pipe_or_a_file_gets_no_colour():
    assert not style.enabled(io.StringIO())


def test_a_closed_stream_gets_no_colour():
    stream = io.StringIO()
    stream.close()

    assert not style.enabled(stream)


def test_force_color_gives_colour_to_a_pipe(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert style.enabled(io.StringIO())


def test_no_color_takes_it_away_even_at_a_terminal(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert not style.enabled(Terminal())


def test_a_dumb_terminal_gets_no_colour(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")

    assert not style.enabled(Terminal())


def test_a_terminal_uses_the_console_capability_check(monkeypatch):
    from unittest.mock import Mock

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    check = Mock(return_value=True)
    monkeypatch.setattr(style, "_reads_escape_codes", check)
    stream = Terminal()

    assert style.enabled(stream)
    check.assert_called_once_with(stream)


def test_non_windows_terminals_need_no_console_mode_setup(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(style, "sys", SimpleNamespace(platform="linux"))

    assert style._reads_escape_codes(Terminal())


@pytest.fixture
def windows_console(monkeypatch):
    import ctypes
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock

    kernel = SimpleNamespace(GetConsoleMode=Mock(), SetConsoleMode=Mock(return_value=1))
    runtime = SimpleNamespace(get_osfhandle=Mock(return_value=123))
    stream = SimpleNamespace(fileno=Mock(return_value=7))
    monkeypatch.setattr(style, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(kernel32=kernel), raising=False)
    monkeypatch.setitem(sys.modules, "msvcrt", runtime)
    return kernel, runtime, stream


@pytest.mark.parametrize("initial_mode, set_result, expected, set_calls", [
    (0x0001, 1, True, [call(123, 0x0005)]),
    (0x0001, 0, False, [call(123, 0x0005)]),
    (0x0005, 1, True, []),
])
def test_windows_console_enables_virtual_terminal_processing_only_when_needed(
        windows_console, initial_mode, set_result, expected, set_calls):
    kernel, runtime, stream = windows_console

    def get_mode(handle, mode):
        assert handle == 123
        mode._obj.value = initial_mode
        return 1

    kernel.GetConsoleMode.side_effect = get_mode
    kernel.SetConsoleMode.return_value = set_result

    assert style._reads_escape_codes(stream) is expected
    stream.fileno.assert_called_once_with()
    runtime.get_osfhandle.assert_called_once_with(7)
    assert kernel.SetConsoleMode.call_args_list == set_calls


def test_windows_stream_without_a_console_gets_no_escape_codes(windows_console):
    kernel, _, stream = windows_console
    kernel.GetConsoleMode.return_value = 0

    assert not style._reads_escape_codes(stream)
    kernel.SetConsoleMode.assert_not_called()


@pytest.mark.parametrize("failure_at, error", [
    ("fileno", ValueError("closed stream")),
    ("handle", OSError("invalid handle")),
    ("get_mode", AttributeError("console API unavailable")),
    ("set_mode", OSError("cannot set console mode")),
])
def test_windows_console_setup_failures_disable_colour(windows_console, failure_at, error):
    kernel, runtime, stream = windows_console
    kernel.GetConsoleMode.return_value = 1
    operation = {
        "fileno": stream.fileno,
        "handle": runtime.get_osfhandle,
        "get_mode": kernel.GetConsoleMode,
        "set_mode": kernel.SetConsoleMode,
    }[failure_at]
    operation.side_effect = error

    assert not style._reads_escape_codes(stream)


# ── What colour does to the text ────────────────────────────────────────────

def test_without_colour_paint_is_the_text_itself():
    assert style.paint("error:", "bold red", False) == "error:"
    assert style.answer(ANSWER, False) == ANSWER


def test_with_colour_paint_wraps_the_text_in_escape_codes():
    painted = style.paint("error:", "bold red", True)

    assert painted == "\033[1;31merror:\033[0m"
    assert style.plain(painted) == "error:"


def test_colour_changes_no_character_of_an_answer():
    painted = style.answer(ANSWER, True)

    assert painted != ANSWER
    assert [style.plain(line) for line in painted] == ANSWER


def test_a_line_with_lines_under_it_is_a_heading():
    painted = style.answer(ANSWER, True)

    assert painted[0].startswith(style.paint("simple_dike", "bold", True))
    assert painted[4].startswith(style.paint("1  initial  Initial stage", "bold", True))


def test_what_is_said_in_brackets_at_the_end_is_quieter():
    painted = style.answer(ANSWER, True)

    assert painted[0].endswith(style.paint("(C:\\work\\simple_dike.json)", "dim", True))


def test_the_label_of_an_indented_line_and_the_id_of_a_row_stand_out():
    painted = style.answer(ANSWER, True)

    assert style.paint("domain", "cyan", True) in painted[2]
    assert style.paint("calculation:", "cyan", True) in painted[5]
    assert painted[6].startswith(style.paint("soil", "cyan", True))


def test_done_is_green_and_a_command_to_type_is_marked():
    painted = style.answer(ANSWER, True)

    assert painted[7].startswith(style.paint("ok:", "bold green", True))
    assert style.paint("wrote", "green", True) in painted[8]
    assert style.paint("`kratos-cli new x.json`", "cyan", True) in painted[9]


# ── Where it is used ────────────────────────────────────────────────────────

def test_an_error_is_red_at_a_terminal_and_plain_in_a_pipe(cli, site, monkeypatch):
    plain = cli("water", site, "nonsense").err
    monkeypatch.setenv("FORCE_COLOR", "1")
    painted = cli("water", site, "nonsense").err

    assert style.paint("error:", "bold red", True) in painted
    assert style.plain(painted) == plain


def test_a_command_line_argparse_cannot_read_is_said_in_colour_too(cli, site, monkeypatch):
    plain = cli("water", site, "--bogus").err
    monkeypatch.setenv("FORCE_COLOR", "1")
    painted = cli("water", site, "--bogus").err

    assert "error: unrecognized arguments: --bogus" in plain
    assert style.paint("error:", "bold red", True) in painted
    assert style.plain(painted) == plain


def test_an_answer_is_in_colour_at_a_terminal(cli, site, monkeypatch):
    plain = cli("show", site).out
    monkeypatch.setenv("FORCE_COLOR", "1")
    painted = cli("show", site).out

    assert painted != plain and style.plain(painted) == plain


def test_json_is_never_in_colour(cli, site, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")

    assert "\033[" not in cli("show", site, "--json").out


def test_the_prompt_names_the_project_in_colour(site, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    prompt = Shell(site, interactive=True, run=lambda argv: 0).prompt()

    assert "\033[" in prompt
    assert style.plain(prompt) == "site.json> "


def test_without_colour_the_prompt_is_plain(site):
    assert Shell(site, interactive=True, run=lambda argv: 0).prompt() == "site.json> "


@pytest.mark.parametrize("readline", [True, False])
def test_the_prompt_s_codes_are_hidden_from_readline_only_when_it_is_there(
        site, monkeypatch, readline):
    """readline counts every character of the prompt unless the codes are fenced off by
    \\001 and \\002; without readline those two would be printed."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    shell = Shell(site, interactive=True, run=lambda argv: 0)
    shell.readline = readline

    assert ("\001" in shell.prompt()) is readline
