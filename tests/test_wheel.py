"""The wheel that `pyproject.toml` builds: its commands and its version.

An installed wheel has no `run.bat` and no `kratos-cli.bat`; its commands are the
`[project.scripts]` entries, so each one must name a function that starts the same
thing the matching file starts in a checkout.
"""

import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

from core import version

ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def entry_point(name):
    module, function = PROJECT["project"]["scripts"][name].split(":")
    return getattr(importlib.import_module(module), function)


def test_the_gui_command_is_the_launcher_that_run_bat_starts():
    from backend import launcher

    assert entry_point("deltaresstyx") is launcher.main


def test_the_cli_command_is_the_kratos_cli_that_the_wrappers_start():
    from cli import __main__ as cli_main

    assert entry_point("kratos-cli") is cli_main.run


def test_the_wheel_takes_its_version_from_core_version():
    """The release workflow checks the tag against `VERSION`; a second number in
    `pyproject.toml` could ship a wheel that says another version than the app."""
    assert "version" not in PROJECT["project"]
    assert "version" in PROJECT["project"]["dynamic"]
    assert PROJECT["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "core.version.VERSION"}


def test_the_cli_command_runs_and_answers_in_utf8():
    ran = subprocess.run(
        [sys.executable, "-c", "from cli.__main__ import run; raise SystemExit(run())",
         "--version"],
        cwd=ROOT, capture_output=True, timeout=60)

    assert ran.returncode == 0, ran.stderr.decode("utf-8", "replace")
    assert version.VERSION in ran.stdout.decode("utf-8")
