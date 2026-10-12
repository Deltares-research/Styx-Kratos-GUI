"""`kratos-cli.bat` and `kratos-cli.sh`: the command, started the way a user starts it.

Both run in the user's own folder, so a relative path on the command line is theirs, and
both use the platform environment `backend.launcher` makes (`.venv-windows`, ...) --
making it first, the way `run.bat` would, when it is not there yet. Neither puts the
user's folder on Python's path: a `core/` or `cli/` of theirs must not stand in for ours.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend import launcher
from tests import shell

ROOT = Path(__file__).resolve().parents[2]
BAT = ROOT / "kratos-cli.bat"
SH = ROOT / "kratos-cli.sh"


def decoys(folder: Path) -> None:
    """A `core` and a `cli` package in the user's folder that would break the command if
    they were imported instead of the repository's."""
    for name in ("core", "cli"):
        (folder / name).mkdir()
        (folder / name / "__init__.py").write_text("raise ImportError('decoy')\n",
                                                   encoding="utf-8")


def test_the_windows_wrapper_runs_the_command_in_the_windows_environment():
    source = BAT.read_text(encoding="utf-8")

    assert launcher.platform_venv_name("win32") + r"\Scripts\python.exe" in source
    assert r"cli\__main__.py" in source and "%*" in source
    assert "-m backend.launcher --check" in source


def test_the_posix_wrapper_runs_the_command_in_the_platform_environment():
    source = SH.read_text(encoding="utf-8")

    for platform in ("linux", "darwin"):
        assert launcher.platform_venv_name(platform) in source
    assert "cli/__main__.py" in source and '"$@"' in source
    assert "-m backend.launcher --check" in source
    assert source.startswith("#!/usr/bin/env bash")


def test_the_posix_wrapper_uses_the_windows_environment_in_git_bash():
    """Git Bash on Windows says MINGW64_NT-..., MSYS_NT-... or CYGWIN_NT-...; there the
    environment is the one `run.bat` makes, with its python under Scripts."""
    source = SH.read_text(encoding="utf-8")

    assert "MINGW*|MSYS*|CYGWIN*)" in source
    assert launcher.platform_venv_name("win32") + "/Scripts/python.exe" in source


def test_the_command_file_puts_the_repository_on_the_path_not_the_user_s_folder(tmp_path):
    decoys(tmp_path)

    ran = subprocess.run([sys.executable, str(ROOT / "cli" / "__main__.py"), "--json", "new",
                          "here.json"], cwd=tmp_path, capture_output=True, text=True,
                         encoding="utf-8", timeout=120)

    assert ran.returncode == 0, ran.stderr
    assert json.loads(ran.stdout)["file"].endswith("here.json")


@pytest.mark.skipif(sys.platform != "win32", reason="a Windows batch file")
@pytest.mark.skipif(not launcher.venv_python(ROOT / launcher.platform_venv_name()).exists(),
                    reason="no platform environment made yet")
def test_the_windows_wrapper_works_from_the_user_s_folder(tmp_path):
    decoys(tmp_path)

    ran = subprocess.run(["cmd", "/c", str(BAT), "--json", "new", "here.json"],
                         cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                         timeout=120)

    assert ran.returncode == 0, ran.stderr
    assert (tmp_path / "here.json").is_file()


@pytest.mark.skipif(shell.bash() is None, reason="no bash on this machine")
@pytest.mark.skipif(not launcher.venv_python(ROOT / launcher.platform_venv_name()).exists(),
                    reason="no platform environment made yet")
def test_the_posix_wrapper_works_from_the_user_s_folder(tmp_path):
    """On Linux and macOS, and in Git Bash on Windows."""
    decoys(tmp_path)

    ran = subprocess.run([str(shell.bash()), SH.as_posix(), "--json", "new", "here.json"],
                         cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                         timeout=120)

    assert ran.returncode == 0, ran.stderr
    assert (tmp_path / "here.json").is_file()
