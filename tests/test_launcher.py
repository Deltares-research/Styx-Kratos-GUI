"""Cross-platform launcher tests.

These tests use only the standard library so setup can be checked before pytest and
the application's runtime dependencies have been installed.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.launcher import platform_venv_name, requirements_changed, venv_python

ROOT = Path(__file__).resolve().parents[1]


class PlatformEnvironmentTests(unittest.TestCase):
    def test_windows_and_linux_never_share_a_virtual_environment(self):
        self.assertEqual(platform_venv_name("win32"), ".venv-windows")
        self.assertEqual(platform_venv_name("linux"), ".venv-linux")

    def test_virtual_environment_python_uses_the_platform_layout(self):
        root = Path("environment")
        self.assertEqual(venv_python(root, "win32"), root / "Scripts" / "python.exe")
        self.assertEqual(venv_python(root, "linux"), root / "bin" / "python")


class RequirementStampTests(unittest.TestCase):
    def test_missing_stamp_requires_installation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements.txt"
            requirements.write_text("fastapi==1\n", encoding="utf-8")

            self.assertTrue(requirements_changed(requirements, root / ".requirements.sha256"))

    def test_matching_stamp_skips_installation_and_edits_require_it(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "requirements.txt"
            stamp = root / ".requirements.sha256"
            requirements.write_text("fastapi==1\n", encoding="utf-8")

            self.assertFalse(requirements_changed(requirements, stamp, update=True))
            self.assertFalse(requirements_changed(requirements, stamp))

            requirements.write_text("fastapi==2\n", encoding="utf-8")
            self.assertTrue(requirements_changed(requirements, stamp))


class WrapperTests(unittest.TestCase):
    def test_linux_wrapper_forwards_arguments_to_the_python_launcher(self):
        source = (ROOT / "run.sh").read_text(encoding="utf-8")
        self.assertIn('-m backend.launcher "$@"', source)
        self.assertNotIn(".venv/bin/python", source)

    def test_windows_wrapper_forwards_arguments_to_the_python_launcher(self):
        source = (ROOT / "run.bat").read_text(encoding="utf-8")
        self.assertIn("-m backend.launcher --open-browser %*", source)
        self.assertNotIn(r".venv\Scripts\python.exe", source)


if __name__ == "__main__":
    unittest.main()


# ── main(), with the environment and the server stood in ────────────────────

import pytest as _pytest

from backend import launcher as _launcher


@_pytest.fixture
def stood_in(monkeypatch, tmp_path):
    calls = {"check": 0, "exec": None, "call": None}
    monkeypatch.setattr(_launcher, "ensure_environment", lambda: tmp_path / "python")
    monkeypatch.setattr(_launcher, "check_environment",
                        lambda python: calls.__setitem__("check", calls["check"] + 1))
    monkeypatch.setattr(_launcher.os, "execv", lambda exe, argv: calls.__setitem__("exec", argv))
    monkeypatch.setattr(_launcher.os, "chdir", lambda path: None)
    monkeypatch.delenv(_launcher.ALLOWED_HOSTS_ENV, raising=False)
    # Whatever this machine happens to be serving on 8000 is not these tests' business.
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: False)
    return calls


def test_check_validates_and_starts_nothing(stood_in):
    assert _launcher.main(["--check"]) == 0
    assert stood_in["check"] == 1 and stood_in["exec"] is None


def test_the_server_is_started_on_loopback_by_default(stood_in):
    _launcher.main([])

    argv = stood_in["exec"]
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert _launcher.ALLOWED_HOSTS_ENV not in _launcher.os.environ


def test_a_named_host_is_allowed_through_to_the_server(stood_in, monkeypatch):
    _launcher.main(["--host", "modelling-pc", "--port", "9000"])

    argv = stood_in["exec"]
    assert argv[argv.index("--port") + 1] == "9000"
    assert _launcher.os.environ[_launcher.ALLOWED_HOSTS_ENV] == "modelling-pc"
    monkeypatch.delenv(_launcher.ALLOWED_HOSTS_ENV)


def test_a_failed_setup_is_one_line_and_exit_code_one(monkeypatch, capsys):
    def broken():
        raise RuntimeError("Python 3.10 or newer is required; found 3.9")
    monkeypatch.setattr(_launcher, "ensure_environment", broken)

    assert _launcher.main([]) == 1
    assert "Launcher failed: Python 3.10" in capsys.readouterr().err


# ── A port that is already taken ────────────────────────────────────────────

import socket as _socket


@_pytest.fixture
def listening():
    """A socket listening on a free loopback port, like a server left running."""
    server = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen()
    yield server.getsockname()[1]
    server.close()


def test_a_port_with_a_server_on_it_is_in_use(listening):
    assert _launcher.port_in_use("127.0.0.1", listening)
    assert _launcher.port_in_use("localhost", listening)


def test_an_all_interfaces_bind_is_probed_on_loopback(listening):
    assert _launcher.port_in_use("0.0.0.0", listening)


def test_a_free_port_is_not_in_use(listening):
    port = listening
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free = probe.getsockname()[1]

    assert not _launcher.port_in_use("127.0.0.1", free)
    assert port != free


def test_a_server_already_on_the_port_is_refused_not_opened(stood_in, monkeypatch, capsys):
    """A server left running from before still holds its own project in memory, and
    its own code. The browser must not be pointed at it as if it were this one: a new
    server cannot bind the port, so it would exit, and the page would show the old
    model."""
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: True)
    opened = []
    monkeypatch.setattr(_launcher.webbrowser, "open", opened.append)
    monkeypatch.setattr(_launcher.subprocess, "call",
                        lambda argv: stood_in.__setitem__("call", argv))

    assert _launcher.main(["--open-browser"]) == 1

    assert stood_in["exec"] is None and stood_in["call"] is None and opened == []
    err = capsys.readouterr().err
    assert "8000" in err and "already" in err
