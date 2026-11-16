"""Cross-platform launcher tests.

These tests use only the standard library so setup can be checked before pytest and
the application's runtime dependencies have been installed.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend import launcher as _launcher
from backend.launcher import platform_venv_name, requirements_changed, venv_python

ROOT = Path(__file__).resolve().parents[1]


class PlatformEnvironmentTests(unittest.TestCase):
    def test_windows_and_linux_never_share_a_virtual_environment(self):
        self.assertEqual(platform_venv_name("win32"), ".venv-windows")
        self.assertEqual(platform_venv_name("linux"), ".venv-linux")
        self.assertEqual(platform_venv_name("darwin"), ".venv-macos")
        self.assertEqual(platform_venv_name("custom/os"), ".venv-custom-os")

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


def test_launcher_refuses_an_unsupported_python_before_setup(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher, "sys", SimpleNamespace(
        version_info=(3, 9), version="3.9.9"))
    create = Mock()
    monkeypatch.setattr(_launcher.venv, "EnvBuilder", create)

    with _pytest.raises(RuntimeError, match="Python 3.10 or newer.*found 3.9.9"):
        _launcher.ensure_environment()
    create.assert_not_called()


def test_launcher_does_not_stamp_a_failed_dependency_install(tmp_path, monkeypatch):
    from unittest.mock import Mock

    environment = tmp_path / "environment"
    environment.mkdir()
    python = environment / "python.exe"
    python.touch()
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example==1\n", encoding="ascii")
    monkeypatch.setattr(_launcher, "_ensure_supported_python", lambda: None)
    monkeypatch.setattr(_launcher, "ROOT", tmp_path)
    monkeypatch.setattr(_launcher, "REQUIREMENTS", requirements)
    monkeypatch.setattr(_launcher, "platform_venv_name", lambda: "environment")
    monkeypatch.setattr(_launcher, "venv_python", lambda _: python)
    failure = _launcher.subprocess.CalledProcessError(1, ["pip"])
    monkeypatch.setattr(_launcher.subprocess, "check_call", Mock(side_effect=failure))

    with _pytest.raises(_launcher.subprocess.CalledProcessError):
        _launcher.ensure_environment()

    assert not (environment / ".requirements.sha256").exists()


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
    monkeypatch.setattr(_launcher.subprocess, "Popen",
                        lambda argv: stood_in.__setitem__("call", argv))

    assert _launcher.main(["--open-browser"]) == 1

    assert stood_in["exec"] is None and stood_in["call"] is None and opened == []
    err = capsys.readouterr().err
    assert "8000" in err and "already" in err


def test_opening_the_browser_preserves_the_server_exit_status(stood_in, monkeypatch):
    from unittest.mock import MagicMock, Mock

    server = MagicMock()
    server.__enter__.return_value = server
    server.wait.return_value = 7
    popen = Mock(return_value=server)
    thread = Mock()
    factory = Mock(return_value=thread)
    monkeypatch.setattr(_launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(_launcher.threading, "Thread", factory)

    assert _launcher.main(["--open-browser", "--port", "9000"]) == 7
    assert popen.call_args.args[0][-2:] == ["--port", "9000"]
    factory.assert_called_once_with(
        target=_launcher.open_when_ready,
        args=("http://127.0.0.1:9000/", "127.0.0.1", 9000, server), daemon=True)
    thread.start.assert_called_once_with()
    assert stood_in["exec"] is None


class _Server:
    """A stand-in for the server process: running until told otherwise."""

    def __init__(self, exits_after: int | None = None):
        self.polls = 0
        self.exits_after = exits_after

    def poll(self):
        self.polls += 1
        if self.exits_after is not None and self.polls > self.exits_after:
            return 1
        return None


def test_the_browser_opens_only_once_the_server_answers(monkeypatch):
    """Opening before the server is up shows "site can't be reached" for a few seconds."""
    answers = iter([False, False, True])
    opened = []
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: next(answers))
    monkeypatch.setattr(_launcher.webbrowser, "open", opened.append)

    assert _launcher.open_when_ready("http://127.0.0.1:8000/", "127.0.0.1", 8000,
                                     _Server(), interval=0)
    assert opened == ["http://127.0.0.1:8000/"]


def test_the_browser_stays_closed_when_the_server_exits_first(monkeypatch):
    opened = []
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: False)
    monkeypatch.setattr(_launcher.webbrowser, "open", opened.append)

    assert not _launcher.open_when_ready("http://127.0.0.1:8000/", "127.0.0.1", 8000,
                                         _Server(exits_after=3), interval=0)
    assert opened == []


def test_the_browser_stays_closed_when_the_server_never_answers(monkeypatch):
    opened = []
    monkeypatch.setattr(_launcher, "port_in_use", lambda host, port: False)
    monkeypatch.setattr(_launcher.webbrowser, "open", opened.append)

    assert not _launcher.open_when_ready("http://127.0.0.1:8000/", "127.0.0.1", 8000,
                                         _Server(), timeout=0.05, interval=0.01)
    assert opened == []


def test_a_failed_server_exec_is_reported_as_a_launcher_error(
        stood_in, monkeypatch, capsys):
    from unittest.mock import Mock

    monkeypatch.setattr(_launcher.os, "execv",
                        Mock(side_effect=OSError("cannot start server")))

    assert _launcher.main([]) == 1
    assert "Launcher failed: cannot start server" in capsys.readouterr().err


@_pytest.mark.parametrize("environment_exists, python_exists", [
    (False, False),
    (True, False),
    (True, True),
])
def test_launcher_creates_missing_environment_and_reuses_existing_one(
        tmp_path, monkeypatch, environment_exists, python_exists):
    from unittest.mock import Mock

    environment = tmp_path / ".venv-windows"
    python = environment / "python.exe"
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example==1\n", encoding="ascii")
    if environment_exists:
        environment.mkdir()
    if python_exists:
        python.touch()
    monkeypatch.setattr(_launcher, "ROOT", tmp_path)
    monkeypatch.setattr(_launcher, "REQUIREMENTS", requirements)
    monkeypatch.setattr(_launcher, "platform_venv_name", lambda: ".venv-windows")
    monkeypatch.setattr(_launcher, "venv_python", lambda _: python)

    def create(folder):
        assert folder == environment
        environment.mkdir(exist_ok=True)
        python.touch()

    builder = Mock()
    builder.create.side_effect = create
    factory = Mock(return_value=builder)
    install = Mock()
    monkeypatch.setattr(_launcher.venv, "EnvBuilder", factory)
    monkeypatch.setattr(_launcher.subprocess, "check_call", install)

    assert _launcher.ensure_environment() == python
    if python_exists:
        factory.assert_not_called()
        builder.create.assert_not_called()
    else:
        factory.assert_called_once_with(
            with_pip=True, clear=environment_exists)
        builder.create.assert_called_once_with(environment)
    install.assert_called_once_with(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check",
         "-r", str(requirements)], cwd=tmp_path)
    assert not _launcher.requirements_changed(
        requirements, environment / ".requirements.sha256")
    factory.reset_mock()
    builder.create.reset_mock()
    install.reset_mock()

    assert _launcher.ensure_environment() == python
    factory.assert_not_called()
    builder.create.assert_not_called()
    install.assert_not_called()
