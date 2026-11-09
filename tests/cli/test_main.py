"""`kratos-cli` itself: the command table, the exit codes, and how a refusal is said.

Exit codes (plan/active/cli-plan.md D7): 0 when the command did what it was asked, 1
when the model or Kratos refused it, 2 when the command line itself was wrong. A refusal
goes to stderr as `error: <reason>`; with `--json` it is also the answer on stdout, so a
script reading stdout always gets JSON.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

COMMANDS = ["new", "show", "check", "build", "script", "get", "set", "add", "remove",
            "dimension", "units", "water", "domain", "material", "layer", "line", "body",
            "volume", "section", "beam", "wall", "member", "anchor", "interface", "load",
            "normal-load", "parts", "mesh", "stages", "node", "deck", "export", "run",
            "calculate", "results", "shell"]


def test_an_argument_no_command_takes_is_a_usage_error(cli, site):
    ran = cli("show", site, "--frobnicate")

    assert ran.code == 2
    assert "--frobnicate" in ran.err


def test_help_lists_every_command(cli):
    ran = cli("--help")

    assert ran.code == 0
    for command in COMMANDS:
        assert command in ran.out


def test_every_id_a_command_takes_says_what_it_is():
    """`layer set L1`: the help of each action says what its id is and where the ids
    are listed, so `help layer set` answers what `L1` is."""
    import argparse

    from cli.terminal.main import parser

    def bare(command: argparse.ArgumentParser, path: str):
        for action in command._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    yield from bare(sub, f"{path} {name}")
            elif action.dest == "id" and not action.help:
                yield path

    missing = list(bare(parser(), "kratos-cli"))
    assert not missing, f"an id without help: {missing}"


def test_no_command_is_a_usage_error(cli):
    ran = cli()

    assert ran.code == 2
    assert "usage" in ran.err.lower()


def test_an_unknown_command_is_a_usage_error(cli):
    assert cli("frobnicate").code == 2


REMOVED = [
    (["excavation", "{site}", "add", "pit"],
     "excavation is gone: split the soil with `line add`."),
    (["stages", "{site}", "staged-excavation"],
     "staged-excavation is gone: add each stage with `stages add`."),
]


@pytest.mark.parametrize("argv, said", REMOVED)
def test_a_removed_command_says_what_to_use_instead(cli, site, argv, said):
    ran = cli(*[word.format(site=site) for word in argv])

    assert ran.code == 2
    assert said in ran.err
    assert "invalid choice" not in ran.err


def test_a_removed_word_under_another_command_is_only_an_invalid_choice(cli, site):
    ran = cli("layer", site, "staged-excavation")

    assert ran.code == 2
    assert "invalid choice" in ran.err and "is gone" not in ran.err


@pytest.mark.parametrize("argv, said", REMOVED)
def test_a_removed_command_says_the_same_in_the_shell(cli, site, monkeypatch, argv, said):
    line = " ".join(word for word in argv if word != "{site}")
    monkeypatch.setattr(sys, "stdin", io.StringIO(line + "\n"))

    ran = cli("shell", site)

    assert ran.code == 1
    assert said in ran.err


def test_the_removed_commands_are_in_no_help_and_no_completion(cli, capsys):
    from cli.terminal import shell

    lines = iter(["help", "help stages"])

    def read(prompt: str) -> str:
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    said = cli("--help").out + cli("stages", "--help").out
    shell.Shell(None, read=read, interactive=True).loop()
    said += capsys.readouterr().out
    offered = shell.completions("") + shell.completions("stages ")

    assert "excavation" not in said
    assert not [word for word in offered if "excavation" in word]
    assert "line" in offered and "add" in offered


def test_a_refusal_is_one_line_on_stderr_and_exit_1(cli, tmp_path):
    ran = cli("show", tmp_path / "nope.json")

    assert ran.code == 1
    assert ran.err.startswith("error: no such file")
    assert "nope.json" in ran.err
    assert "Traceback" not in ran.err


def test_a_refusal_with_json_is_also_json_on_stdout(cli, tmp_path):
    ran = cli("--json", "show", tmp_path / "nope.json")

    assert ran.code == 1
    answer = ran.json()
    assert answer["ok"] is False
    assert "nope.json" in answer["error"]


def test_a_field_that_does_not_validate_is_named(cli, site):
    ran = cli("set", site, "mesh.element_size", "-1")

    assert ran.code == 1
    assert "mesh.element_size" in ran.err
    assert "greater than 0" in ran.err


def test_it_runs_as_a_module_from_any_folder(tmp_path):
    """What the wrappers start: `python -m cli`, with the repository on the path and the
    user's own folder as the working directory, so relative paths are theirs."""
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    ran = subprocess.run([sys.executable, "-m", "cli", "--json", "new", "here.json"],
                         cwd=tmp_path, env=environment, capture_output=True, text=True,
                         encoding="utf-8", timeout=120)

    assert ran.returncode == 0, ran.stderr
    assert json.loads(ran.stdout)["file"].endswith("here.json")
    assert (tmp_path / "here.json").is_file()
