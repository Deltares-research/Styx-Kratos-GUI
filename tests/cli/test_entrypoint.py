"""The public module and wrapper-file entry points, without running a command."""

from __future__ import annotations

import io
import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from cli.terminal import main as terminal_main


@pytest.mark.parametrize("argv, code", [
    (["show", "site.json"], 0),
    (["shell", "site.json"], 0),
    (["show", "missing.json"], 1),
    (["unknown-command"], 2),
])
def test_module_dispatches_the_command_and_forwards_its_exit_code(
        monkeypatch, argv, code):
    stdout = Mock(spec=["reconfigure"])
    stderr = Mock(spec=["reconfigure"])
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "argv", ["kratos-cli", *argv])
    original_path = list(sys.path)

    def dispatch():
        assert sys.argv[1:] == argv
        stdout.reconfigure.assert_called_once_with(encoding="utf-8")
        stderr.reconfigure.assert_called_once_with(encoding="utf-8")
        return code

    main = Mock(side_effect=dispatch)
    exit_ = Mock()
    monkeypatch.setattr(terminal_main, "main", main)
    monkeypatch.setattr(sys, "exit", exit_)

    runpy.run_module("cli", run_name="__main__")

    main.assert_called_once_with()
    exit_.assert_called_once_with(code)
    assert sys.path == original_path


def test_wrapper_file_uses_the_repository_path_and_accepts_plain_streams(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    original_tail = sys.path[1:]
    monkeypatch.setattr(sys, "path", ["user-folder", *original_tail])
    monkeypatch.setattr(sys, "argv", ["kratos-cli", "--help"])
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())

    def dispatch():
        assert sys.path == [str(root), *original_tail]
        assert sys.argv[1:] == ["--help"]
        return 0

    main = Mock(side_effect=dispatch)
    exit_ = Mock()
    monkeypatch.setattr(terminal_main, "main", main)
    monkeypatch.setattr(sys, "exit", exit_)

    runpy.run_path(str(root / "cli" / "__main__.py"), run_name="__main__")

    main.assert_called_once_with()
    exit_.assert_called_once_with(0)
